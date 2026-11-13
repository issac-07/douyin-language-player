import re
from urllib.parse import parse_qs, urlsplit


class ImportFailure(Exception):
    def __init__(self, code: str, message: str, retryable: bool = False, *, http_status: int | None = None, operation: str | None = None):
        super().__init__(message)
        self.code, self.message, self.retryable = code, message, retryable
        self.http_status, self.operation = http_status, operation


class ImportCancelled(Exception):
    pass


def canonical_video_url(url: str) -> str | None:
    parsed = urlsplit(url)
    host = (parsed.hostname or '').lower()
    if host in ('www.douyin.com', 'douyin.com'):
        match = re.fullmatch(r'/video/(\d{10,24})/?', parsed.path)
        video_id = match[1] if match else None
        if parsed.path in ('', '/'):
            values = parse_qs(parsed.query).get('modal_id', [])
            if len(values) == 1 and re.fullmatch(r'\d{10,24}', values[0]): video_id = values[0]
        if video_id:
            return f'https://www.douyin.com/video/{video_id}'
    if host in ('www.iesdouyin.com', 'iesdouyin.com'):
        match = re.fullmatch(r'/share/video/(\d{10,24})/?', parsed.path)
        if match: return f'https://www.douyin.com/video/{match[1]}'
    return None


def parse_douyin_input(text: str) -> str:
    if not text or len(text) > 8192:
        raise ImportFailure('invalid_url', 'Paste one Douyin video link or its sharing text (up to 8,192 characters).')
    urls = re.findall(r'https?://[^\s<>"\'，。！？、（）【】《》]+', text, flags=re.I)
    urls = list(dict.fromkeys(url.rstrip('.,;!)]}，。') for url in urls))
    if len(urls) != 1:
        raise ImportFailure('invalid_url', 'Paste exactly one HTTPS Douyin video URL, optionally inside its sharing text.')
    url = urls[0]
    try:
        parsed = urlsplit(url)
        if parsed.scheme.lower() != 'https' or parsed.username or parsed.password or parsed.port not in (None, 443):
            raise ValueError()
        if any(ord(char) < 33 or char == '\\' for char in url): raise ValueError()
        host = (parsed.hostname or '').lower()
        if host not in ('douyin.com', 'www.douyin.com', 'v.douyin.com'):
            raise ImportFailure('unsupported_platform', 'Only public Douyin links are supported. You can still import a local MP4.')
        if canonical := canonical_video_url(url): return canonical
        if host == 'v.douyin.com' and re.fullmatch(r'/[A-Za-z0-9_-]{2,128}/?', parsed.path):
            return f'https://v.douyin.com/{parsed.path.strip("/")}/'
    except (ValueError, UnicodeError):
        pass
    raise ImportFailure('invalid_url', 'Use an HTTPS v.douyin.com short link or www.douyin.com/video/<id> URL without credentials or custom ports.')
