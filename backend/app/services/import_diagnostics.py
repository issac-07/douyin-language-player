"""Diagnostic facts only: never log raw exceptions, URLs, headers or response bodies."""
import logging
import re
from urllib.parse import urlsplit

from app.services.douyin_urls import ImportFailure

logger = logging.getLogger('app.import_diagnostics')
OPERATION_LABELS = {
    'resolve_url': 'resolving the sharing link',
    'extract_metadata': 'extracting video metadata',
    'download_media': 'downloading the video',
    'validate_media': 'validating the downloaded video',
    'import_library': 'saving the video to the library',
}


def endpoint_facts(url):
    parsed = urlsplit(url)
    host = parsed.hostname
    if host == 'v.douyin.com': endpoint = 'short_link'
    elif parsed.path == '/aweme/v1/web/aweme/detail/': endpoint = 'web_detail_api'
    elif parsed.path.startswith(('/video/', '/share/video/')): endpoint = 'video_page'
    elif host and (host == 'douyin.com' or host.endswith(('.douyin.com', '.iesdouyin.com'))): endpoint = 'site_page'
    else: endpoint = 'media_file'
    # A host is included only after URL allowlist validation. Paths/queries can contain secrets.
    return dict(host=host, endpoint=endpoint)


def http_failure(status, operation, endpoint=None):
    label = OPERATION_LABELS.get(operation, 'contacting the remote site')
    facts = dict(http_status=status, operation=operation)
    if status == 403:
        return ImportFailure('site_http_403', f'The remote site returned HTTP 403 while {label}. This may be an extractor compatibility or site-policy issue; HTTP 403 alone does not prove that login is required. Try another public link or import a local MP4.', **facts)
    if status == 401:
        return ImportFailure('login_required', f'The remote endpoint requires authentication (HTTP 401) while {label}. This app does not access accounts or browser cookies. Import an authorized local MP4 instead.', **facts)
    if status in (404, 410):
        if endpoint == 'web_detail_api':
            return ImportFailure('extractor_compatibility', 'The metadata endpoint is unavailable or has changed. Update/review the extractor; this does not establish that the video was deleted. Local MP4 import remains available.', **facts)
        if operation == 'download_media':
            return ImportFailure('download_failure', 'The media URL is unavailable or expired. Retry extraction or import a local MP4.', True, **facts)
        return ImportFailure('video_unavailable', 'The public video or sharing link is unavailable or expired. Try another public link or a local MP4.', **facts)
    return ImportFailure('remote_error', f'The remote server returned HTTP {status} while {label}. Retry later or import a local MP4.', status == 429 or 500 <= status <= 599, **facts)


def exception_chain(error):
    """yt-dlp also carries errors in exc_info/cause, outside Python's normal chain."""
    pending, seen, result = [error], set(), []
    while pending and len(result) < 8:
        current = pending.pop(0)
        if not isinstance(current, BaseException) or id(current) in seen: continue
        seen.add(id(current)); result.append(current)
        pending.extend([getattr(current, 'cause', None), current.__cause__, current.__context__])
        info = getattr(current, 'exc_info', None)
        if isinstance(info, tuple) and len(info) > 1: pending.append(info[1])
    return result


class ExtractorDiagnosticLogger:
    def __init__(self, context): self.context = context
    def debug(self, *_): pass
    def _notice(self, message):
        # Inspect in memory, record only a fixed vocabulary. Raw messages may contain signed URLs.
        text = str(message).lower()
        reason = None
        if 'fresh cookies' in text: reason = 'fresh_session_cookies_reported_not_login_proof'
        elif 'failed to parse json' in text: reason = 'invalid_metadata_json'
        match = re.search(r'http (?:error )?(\d{3})', text)
        if match or reason:
            self.context.record('extractor_notice', http_status=int(match[1]) if match else None, upstream_reason=reason)
    warning = _notice
    error = _notice


def classify_extractor_failure(error, client):
    from yt_dlp.utils import ExtractorError, GeoRestrictedError, UnsupportedError
    context = client.context
    chain = exception_chain(error)
    for item in chain:
        # Class names cannot contain raw URL/header/body values.
        context.record('exception', exception_type=type(item).__name__)
    if any(isinstance(item, GeoRestrictedError) for item in chain):
        return ImportFailure('geographic_restriction', 'The extractor explicitly reported a geographic restriction. No regional restriction bypass is attempted. Import an authorized local MP4 instead.')
    if any(isinstance(item, UnsupportedError) for item in chain):
        return ImportFailure('unsupported_extractor', 'The installed extractor does not support this video URL. Use a supported public Douyin video URL or import a local MP4.')
    for item in chain:
        if isinstance(item, ExtractorError) and item.expected:
            text = getattr(item, 'orig_msg', str(item)).lower()
            if re.match(r'^(?:login required|(?:please )?(?:log|sign) in\b|this video requires authentication)', text):
                return ImportFailure('login_required', 'The extractor explicitly reported that authentication is required. This app does not access accounts or browser cookies. Import an authorized local MP4 instead.')
            if re.match(r'^(?:video (?:is )?unavailable|this video (?:has been removed|is (?:unavailable|no longer available|private)))', text):
                return ImportFailure('video_unavailable', 'The extractor explicitly reported that this video is unavailable or private. Try another public link or import an authorized local MP4.')
    if client.last_error:
        return client.last_error
    for item in chain:
        status = getattr(item, 'status', None)
        if not isinstance(status, int): status = getattr(item, 'code', None)
        if isinstance(status, int) and 400 <= status <= 599:
            return http_failure(status, context.operation, 'web_detail_api')
    if any(isinstance(item, OSError) or type(item).__name__ in ('TransportError', 'RequestError', 'SSLError', 'ProxyError') for item in chain):
        return ImportFailure('network_error', 'The extractor could not reach the remote site. Check the network and retry, or import a local MP4.', True)
    # The installed Douyin extractor uses this message for missing sessions, invalid JSON
    # and nonfatal HTTP errors. It is explicitly NOT evidence of account login requirements.
    if any('fresh cookies' in str(item).lower() for item in chain):
        context.record('extractor_notice', upstream_reason='fresh_session_cookies_reported_not_login_proof')
    return ImportFailure('extractor_compatibility', 'The extractor could not read usable Douyin metadata. The site may have changed or require an anonymous session that this extractor cannot establish. This does not establish that account login is required. Try another public link or import a local MP4.')


def log_diagnostic(event):
    # event is constructed exclusively from typed, allowlisted facts; no exception formatting.
    logger.log(logging.WARNING if event.event == 'failed' else logging.INFO,
               'douyin_import %s', event.model_dump_json(exclude_none=True))
