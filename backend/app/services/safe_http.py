"""Direct HTTPS with validated DNS addresses pinned to the actual TLS socket."""
import http.client
import ipaddress
import socket
import ssl
import threading
import time
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeout
from urllib.parse import urljoin, urlsplit, urlunsplit

from app.services.douyin_urls import ImportCancelled, ImportFailure
from app.models.imports import ImportDiagnostic
from app.services.import_diagnostics import endpoint_facts, http_failure, log_diagnostic

PAGE_DOMAINS = ('douyin.com', 'iesdouyin.com')
MEDIA_DOMAINS = PAGE_DOMAINS + ('douyinvod.com', 'snssdk.com', 'amemv.com', 'zjcdn.com', 'bytecdn.cn')
_DNS = ThreadPoolExecutor(max_workers=2, thread_name_prefix='import-dns')


class RequestContext:
    def __init__(self, event: threading.Event, timeout: float):
        self.event = event
        self.deadline = time.monotonic() + timeout
        self.operation = 'resolve_url'
        self.diagnostics: list[ImportDiagnostic] = []

    def record(self, event, **facts):
        entry = ImportDiagnostic(operation=self.operation, event=event, **facts)
        if len(self.diagnostics) < 128: self.diagnostics.append(entry)
        log_diagnostic(entry)

    def begin(self, operation):
        self.operation = operation
        self.record('started')

    def check(self):
        if self.event.is_set(): raise ImportCancelled()
        if time.monotonic() >= self.deadline:
            raise ImportFailure('timeout', 'The import timed out. Retry later or import a local MP4.', True)

    def remaining(self):
        self.check()
        return max(.1, self.deadline - time.monotonic())


def validate_network_url(url: str, role: str) -> str:
    try:
        parsed = urlsplit(url)
        host = (parsed.hostname or '').lower()
        if parsed.username or parsed.password or any(ord(char) < 33 or char == '\\' for char in url): raise ValueError()
        domains = PAGE_DOMAINS if role == 'page' else MEDIA_DOMAINS
        if not any(host == base or host.endswith('.' + base) for base in domains): raise ValueError()
        if parsed.scheme == 'http' and parsed.port in (None, 80):
            parsed = parsed._replace(scheme='https', netloc=host)
        elif parsed.scheme != 'https' or parsed.port not in (None, 443): raise ValueError()
        return urlunsplit((parsed.scheme, host, parsed.path or '/', parsed.query, ''))
    except (ValueError, UnicodeError):
        raise ImportFailure('unsafe_url', 'The link or a remote redirect points outside the permitted public Douyin/media hosts.') from None


def public_addresses(host: str, resolver=socket.getaddrinfo):
    addresses = resolver(host, 443, type=socket.SOCK_STREAM)
    if not addresses:
        raise ImportFailure('network_error', 'The remote host has no usable DNS addresses.', True)
    for family, _, _, _, address in addresses:
        ip = ipaddress.ip_address(address[0].split('%')[0])
        if family not in (socket.AF_INET, socket.AF_INET6) or not ip.is_global or ip.is_multicast:
            raise ImportFailure('unsafe_address', 'A remote host resolved to a local, private, reserved or otherwise non-public network address.')
    return addresses


class PinnedHTTPSConnection(http.client.HTTPSConnection):
    def __init__(self, host, addresses, timeout):
        super().__init__(host, port=443, timeout=timeout, context=ssl.create_default_context())
        self.addresses = addresses

    def connect(self):
        last = None
        deadline = time.monotonic() + self.timeout
        for family, _, _, _, address in self.addresses:
            remaining = deadline - time.monotonic()
            if remaining <= 0: break
            raw = socket.socket(family, socket.SOCK_STREAM)
            raw.settimeout(remaining)
            try:
                raw.connect(address)  # Numeric validated sockaddr: no second DNS lookup.
                raw.settimeout(max(.01, deadline - time.monotonic()))
                self.sock = self._context.wrap_socket(raw, server_hostname=self.host)
                return
            except OSError as exc:
                last = exc; raw.close()
        raise last or OSError('No usable public address within the connection deadline')


class SafeResponse:
    def __init__(self, response, connection, url, context, limit):
        self.raw, self.connection, self.url, self.context, self.limit = response, connection, url, context, limit
        self.headers = response.headers
        self.status = response.status
        self.received = 0
        self.closed = False
        value = self.headers.get('Content-Length')
        try:
            self.length = int(value) if value is not None else None
            if self.length is not None and (self.length < 0 or self.length > limit): raise ValueError()
        except ValueError:
            self.close()
            raise ImportFailure('size_limit', 'The remote response exceeds the configured size limit or has an invalid length.') from None

    def read(self, size=-1):
        self.context.check()
        if size == 0: return b''
        try:
            if self.connection.sock:
                self.connection.sock.settimeout(min(15, self.context.remaining()))
            size = min(size if size is not None and size >= 0 else self.limit + 1, self.limit + 1)
            data = self.raw.read(size)
        except (OSError, http.client.HTTPException) as exc:
            self.context.record('transport_error', exception_type=type(exc).__name__)
            raise ImportFailure('network_error', 'The remote download was interrupted. Retrying is possible; local MP4 import remains available.', True) from None
        self.received += len(data)
        if self.received > self.limit:
            raise ImportFailure('size_limit', 'The download exceeds the configured size limit.')
        if not data and self.length is not None and self.received != self.length:
            raise ImportFailure('incomplete_download', 'The remote server sent an incomplete video. A partial file will not be imported.', True)
        return data

    def close(self):
        self.closed = True
        self.raw.close(); self.connection.close()

    def readable(self): return True

    def __enter__(self): return self
    def __exit__(self, *_): self.close()


class SafeHTTPClient:
    def __init__(self, context, connection_factory=PinnedHTTPSConnection, resolver=socket.getaddrinfo):
        self.context, self.connection_factory, self.resolver = context, connection_factory, resolver
        self.last_error = None

    def _resolve(self, host):
        future = _DNS.submit(public_addresses, host, self.resolver)
        deadline = time.monotonic() + min(10, self.context.remaining())
        try:
            while True:
                self.context.check()
                if time.monotonic() >= deadline:
                    raise ImportFailure('network_error', 'DNS lookup timed out. Retry later or use local MP4 import.', True)
                try: return future.result(timeout=.1)
                except FutureTimeout: continue
                except socket.gaierror:
                    self.context.record('transport_error', exception_type='gaierror')
                    raise ImportFailure('network_error', 'Could not resolve the remote host. Check the network connection.', True) from None
        finally:
            if not future.done(): future.cancel()

    def open(self, url, *, role='extractor', limit=16 * 1024 * 1024, headers=None):
        try:
            for _ in range(6):
                self.context.check()
                url = validate_network_url(url, role)
                facts = endpoint_facts(url)
                parsed = urlsplit(url)
                addresses = self._resolve(parsed.hostname)
                connection = self.connection_factory(parsed.hostname, addresses, min(15, self.context.remaining()))
                # Never forward credentials, browser cookies, proxy headers or arbitrary metadata headers.
                safe_headers = {'User-Agent': 'Mozilla/5.0', 'Accept': '*/*', 'Accept-Encoding': 'identity', 'Referer': 'https://www.douyin.com/'}
                for key, value in (headers or {}).items():
                    if key.lower() in ('user-agent', 'accept') and isinstance(value, str) and not any(char in value for char in '\r\n'):
                        safe_headers[key] = value[:1000]
                try:
                    connection.request('GET', urlunsplit(('', '', parsed.path, parsed.query, '')), headers=safe_headers)
                    response = connection.getresponse()
                except (OSError, http.client.HTTPException) as exc:
                    connection.close()
                    self.context.record('transport_error', exception_type=type(exc).__name__, **facts)
                    raise ImportFailure('network_error', 'Could not establish a verified HTTPS connection to Douyin/media. Check the network and retry.', True) from None
                self.context.record('http_response', http_status=response.status, **facts)
                if response.status in (301, 302, 303, 307, 308):
                    location = response.headers.get('Location')
                    response.close(); connection.close()
                    if not location: raise ImportFailure('invalid_redirect', 'The remote server returned a redirect without a destination.')
                    url = urljoin(url, location)
                    continue
                if response.status >= 400:
                    status = response.status
                    response.close(); connection.close()
                    raise http_failure(status, self.context.operation, facts['endpoint'])
                if response.status != 200:
                    response.close(); connection.close()
                    raise ImportFailure('incomplete_download', 'The remote server returned a partial or unexpected response. It cannot be imported as a complete video.', True)
                if response.headers.get('Content-Encoding', 'identity').lower() not in ('identity', ''):
                    response.close(); connection.close()
                    raise ImportFailure('unsupported_encoding', 'The remote server ignored the uncompressed-response request. This response cannot be imported safely.')
                return SafeResponse(response, connection, url, self.context, limit)
            raise ImportFailure('redirect_limit', 'The link has too many redirects. Try its normal Douyin video URL instead.')
        except ImportFailure as exc:
            exc.operation = exc.operation or self.context.operation
            self.last_error = exc
            raise
