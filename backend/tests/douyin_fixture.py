"""Deterministic HTTPS transport fixtures. Never imported by production application code."""
import io
import json
import socket
import subprocess
import threading
import time
from email.message import Message
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

from app.services.safe_http import SafeHTTPClient

VIDEO_ID = '6961737553342991651'
NORMAL_URL = f'https://www.douyin.com/video/{VIDEO_ID}'


class FixtureNetwork:
    def __init__(self, media, *, media_length=True, delay=0):
        self.media = media
        self.media_length = media_length
        self.delay = delay
        self.calls = []
        self.replies = {}
        self.lock = threading.Lock()

    def factory(self, context):
        network = self
        class Connection:
            sock = None
            def __init__(self, host, addresses, timeout): self.host = host
            def request(self, method, path, headers):
                self.path = path
                with network.lock: network.calls.append((self.host, path, headers))
            def getresponse(self): return network.response(self.host, self.path)
            def close(self): pass
        return SafeHTTPClient(context, Connection, lambda *_args, **_kwargs: [(socket.AF_INET, socket.SOCK_STREAM, 6, '', ('93.184.216.34', 443))])

    def response(self, host, path):
        key = (host, path)
        if key in self.replies:
            reply = self.replies[key]
            if callable(reply): return reply()
            return RawResponse(*reply)
        if host == 'v.douyin.com':
            return RawResponse(b'', 302, {'Location': NORMAL_URL})
        if host == 'www.douyin.com' and path.startswith('/video/') and not path.endswith('/bad'):
            return RawResponse(b'<html>public video page</html>')
        if path.startswith('/aweme/v1/web/aweme/detail/'):
            video_id = parse_qs(urlsplit(path).query)['aweme_id'][0]
            if video_id.endswith('999'): return RawResponse(b'', 403)
            if video_id.endswith('995'): return RawResponse(b'', 401)
            if video_id.endswith('994'): return RawResponse(b'not JSON', 200, {'Content-Type': 'text/html'})
            if video_id.endswith('998'): return RawResponse(b'{}')
            name = 'slow' if video_id.endswith('997') else 'unknown' if video_id.endswith('996') else 'video'
            detail = dict(aweme_id=video_id, desc='Chinese learning clip', author=dict(nickname='Test creator', unique_id='fixture'),
                          video=dict(width=360, height=640, duration=8000,
                          play_addr=dict(url_list=[f'https://media.douyinvod.com/{name}.mp4'], data_size=len(self.media))))
            return RawResponse(json.dumps({'aweme_detail': detail}).encode(), 200, {'Content-Type': 'application/json'})
        if host == 'media.douyinvod.com':
            return RawResponse(self.media, 200, {'Content-Length': str(len(self.media))} if self.media_length and not path.startswith(('/unknown', '/slow')) else {},
                               delay=.3 if path.startswith('/slow') else self.delay)
        return RawResponse(b'', 404)


class RawResponse(io.BytesIO):
    def __init__(self, body=b'', status=200, headers=None, delay=0):
        super().__init__(body)
        self.status, self.delay = status, delay
        self.headers = Message()
        for name, value in (headers or {}).items(): self.headers[name] = value

    def read(self, amount=-1):
        if self.delay: time.sleep(self.delay)
        return super().read(min(amount, 8192) if self.delay and amount and amount > 0 else amount)


def make_browser_app():
    from app.main import create_app
    from app.config import Settings
    from scripts.generate_test_video import generate
    settings = Settings.from_env()
    # Every browser run uses its own data root. This is real captioned media, not a claimed live download.
    fixture = generate(settings.data_dir / 'network-fixture.mp4')
    distinct = fixture.with_name('network-unique.mp4')
    subprocess.run(['ffmpeg', '-y', '-v', 'error', '-i', str(fixture), '-c', 'copy', '-metadata',
                    'comment=Phase 4 controlled network fixture', '-movflags', '+faststart', str(distinct)], check=True)
    from app.services.douyin_extractor import YtDlpExtractor
    return create_app(settings, import_client_factory=FixtureNetwork(distinct.read_bytes()).factory,
                      import_public_page_extractor=YtDlpExtractor())
