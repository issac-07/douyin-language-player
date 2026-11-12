"""Per-job CONNECT proxy: public DNS is pinned, TLS/cookies stay inside fresh Edge.

No TLS interception, cookie inspection, credentials, signature generation or page
modification. Chromium is configured to proxy loopback too and disable direct UDP.
"""
import select
import socket
import socketserver
import threading
from urllib.parse import urlsplit

from app.services.douyin_urls import ImportFailure
from app.services.safe_http import SafeHTTPClient, MEDIA_DOMAINS

ASSET_DOMAINS = MEDIA_DOMAINS + ('douyinstatic.com', 'byteimg.com', 'pstatp.com', 'bytetos.com',
    'ibytedtos.com', 'douyinpic.com', 'bytedance.com', 'bytedanceapi.com', 'zijieapi.com', 'volccdn.com',
    'byted-static.com', 'ibytedapm.com', 'bytegoofy.com', 'applogcdn.com', 'bytescm.com', 'yhgfb-cn-static.com', 'bytednsdoc.com')
ASSET_HOSTS = ('lf-waf-js.byted-static.com', 'lf3-short.ibytedapm.com', 'lf-security.bytegoofy.com',
    'lf-static.applogcdn.com', 'lf-cdn-tos.bytescm.com', 'lf-rc1.yhgfb-cn-static.com',
    'lf-ucenter-web.yhgfb-cn-static.com', 'lf-rc2.yhgfb-cn-static.com', 'lf3-static.bytednsdoc.com')


class PublicBrowserProxy:
    def __init__(self, context):
        self.context = context
        self.client = SafeHTTPClient(context)
        self.budget = 96 * 1024 * 1024
        self.lock = threading.Lock()
        self.slots = threading.BoundedSemaphore(64)
        self.address_cache = {}
        self.sockets = set()
        self.closing = threading.Event()
        owner = self
        class Handler(socketserver.BaseRequestHandler):
            def handle(self): owner.handle(self.request)
        class Server(socketserver.ThreadingTCPServer):
            daemon_threads = True
            block_on_close = False
        self.server = Server(('127.0.0.1', 0), Handler)
        self.thread = threading.Thread(target=self.server.serve_forever, kwargs={'poll_interval': .1}, daemon=True)

    @property
    def url(self): return f'http://127.0.0.1:{self.server.server_address[1]}'

    def destination(self, target):
        parsed = urlsplit('https://' + target)
        host = (parsed.hostname or '').lower()
        if (parsed.port != 443 or parsed.username or parsed.password or parsed.path or parsed.query or parsed.fragment
                or (host not in ASSET_HOSTS and not any(host == base or host.endswith('.' + base) for base in ASSET_DOMAINS))):
            raise ImportFailure('unsafe_url', 'The public-page browser requested a destination outside permitted HTTPS hosts.')
        with self.lock: cached = self.address_cache.get(host)
        if cached is None:
            cached = self.client._resolve(host)
            with self.lock: self.address_cache[host] = cached
        return host, cached

    def handle(self, incoming):
        if not self.slots.acquire(blocking=False): return
        outgoing = None
        try:
            incoming.settimeout(min(5, self.context.remaining()))
            request = b''
            while b'\r\n\r\n' not in request:
                chunk = incoming.recv(4096)
                if not chunk: return
                request += chunk
                if len(request) > 16384: return
            header, extra = request.split(b'\r\n\r\n', 1)
            method, target, version = header.split(b'\r\n', 1)[0].decode('ascii').split(' ')
            if method != 'CONNECT' or version not in ('HTTP/1.0', 'HTTP/1.1'): return
            host, addresses = self.destination(target)
            for family, kind, protocol, _, address in addresses:
                self.context.check()
                candidate = socket.socket(family, socket.SOCK_STREAM)
                candidate.settimeout(min(5, self.context.remaining()))
                try: candidate.connect(address)
                except OSError: candidate.close(); continue
                outgoing = candidate
                break
            if not outgoing: return
            with self.lock: self.sockets.update((incoming, outgoing))
            incoming.sendall(b'HTTP/1.1 200 Connection Established\r\n\r\n')
            if extra: outgoing.sendall(extra)
            for item in (incoming, outgoing): item.settimeout(1)
            while not self.closing.is_set():
                self.context.check()
                ready, _, _ = select.select([incoming, outgoing], [], [], .2)
                for source in ready:
                    data = source.recv(65536)
                    if not data: return
                    with self.lock:
                        self.budget -= len(data)
                        if self.budget < 0: return
                    (outgoing if source is incoming else incoming).sendall(data)
        except Exception:
            # Never log proxy requests, TLS bytes, target queries or browser headers.
            pass
        finally:
            with self.lock:
                self.sockets.discard(incoming)
                self.sockets.discard(outgoing)
            if outgoing: outgoing.close()
            self.slots.release()

    def __enter__(self):
        self.thread.start()
        return self

    def __exit__(self, *_):
        self.closing.set()
        with self.lock:
            for item in list(self.sockets):
                try: item.shutdown(socket.SHUT_RDWR)
                except OSError: pass
        self.server.shutdown(); self.server.server_close(); self.thread.join(timeout=2)
