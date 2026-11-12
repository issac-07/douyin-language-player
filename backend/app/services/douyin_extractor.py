"""Extractor boundary: metadata only. All I/O uses our pinned, anonymous transport."""
import math
from dataclasses import dataclass
from typing import Protocol

from yt_dlp import YoutubeDL
from yt_dlp.extractor.tiktok import DouyinIE
from yt_dlp.networking.common import Response
from yt_dlp.version import __version__

from app.models.imports import SourceMetadata
from app.services.douyin_urls import ImportCancelled, ImportFailure
from app.services.safe_http import validate_network_url
from app.services.import_diagnostics import ExtractorDiagnosticLogger, classify_extractor_failure


@dataclass(frozen=True)
class ExtractedMedia:
    metadata: SourceMetadata
    url: str


class MediaExtractor(Protocol):
    def extract(self, canonical_url: str, client) -> ExtractedMedia: ...


class YtDlpExtractor:
    def extract(self, canonical_url, client):
        client.context.begin('extract_metadata')
        client.last_error = None
        class AnonymousResponse(Response):
            def read(self, amt=None):
                try: return self.fp.read(amt)
                except ImportFailure as exc:
                    client.last_error = exc
                    raise

        class AnonymousYoutubeDL(YoutubeDL):
            def urlopen(self, request):
                client.context.check()
                if not isinstance(request, str) and (request.data is not None or request.method != 'GET'):
                    raise ImportFailure('unsupported_request', 'The extractor requested an unsupported network operation.')
                response = client.open(request if isinstance(request, str) else request.url,
                                       headers={} if isinstance(request, str) else request.headers)
                return AnonymousResponse(response, response.url, response.headers, response.status)

        try:
            with AnonymousYoutubeDL({
                'quiet': True, 'no_warnings': False, 'logger': ExtractorDiagnosticLogger(client.context),
                'skip_download': True, 'cachedir': False, 'proxy': '', 'usenetrc': False,
                'cookiefile': None, 'cookiesfrombrowser': None, 'extractor_retries': 0,
                'writesubtitles': False, 'writeautomaticsub': False,
            }, auto_init=False) as downloader:
                downloader.add_info_extractor(DouyinIE())
                info = downloader.extract_info(canonical_url, download=False, process=False, ie_key='Douyin')
        except ImportCancelled:
            raise
        except Exception as exc:
            client.context.check()
            raise classify_extractor_failure(exc, client) from None
        return self.media_from_info(info, canonical_url, client.context)

    @staticmethod
    def media_from_info(info, canonical_url, context, provider='yt-dlp'):
        context.check()
        if not info or info.get('_type', 'video') != 'video' or info.get('is_live') or info.get('has_drm'):
            raise ImportFailure('unsupported_media', 'Only complete, non-DRM public video files are supported; live streams and playlists cannot be imported.')
        if str(info.get('id')) != canonical_url.rsplit('/', 1)[-1]:
            raise ImportFailure('metadata_mismatch', 'Douyin returned metadata for a different video. No media was imported. Retry the correct public link or use a local MP4.')
        if info.get('availability') == 'needs_auth':
            raise ImportFailure('login_required', 'The metadata explicitly identifies this video as requiring account authentication. This app does not access accounts. Import an authorized local MP4 instead.')
        if info.get('availability') not in (None, 'public', 'unlisted'):
            raise ImportFailure('video_unavailable', 'The metadata marks this video as private, subscription-only or otherwise restricted. Import an authorized local MP4 instead.')
        formats = []
        for item in info.get('formats', []):
            if (item.get('has_drm') or item.get('fragments') or item.get('vcodec') == 'none'
                    or item.get('acodec') == 'none' or item.get('ext') != 'mp4'
                    or item.get('protocol', 'https') not in ('http', 'https')):
                continue
            try: url = validate_network_url(item.get('url', ''), 'media')
            except ImportFailure: continue
            formats.append((item, url))
        if not formats:
            raise ImportFailure('unsupported_media', 'No permitted complete MP4 stream was available. Fragmented streams, separate audio/video and DRM are not supported. Import a local MP4 instead.')
        # Prefer browser-compatible media first, then the best available resolution/bitrate.
        item, url = max(formats, key=lambda pair: (pair[0].get('vcodec') in ('h264', 'avc1'),
                       pair[0].get('height') or 0, pair[0].get('tbr') or 0, pair[0].get('filesize') or 0))
        duration = info.get('duration')
        if duration is not None and (not isinstance(duration, (int, float)) or not math.isfinite(duration) or duration <= 0): duration = None
        def text(value, limit):
            return ''.join(char for char in value if char.isprintable())[:limit] if isinstance(value, str) else None
        return ExtractedMedia(SourceMetadata(video_id=canonical_url.rsplit('/', 1)[-1], canonical_url=canonical_url,
                              title=text(info.get('title'), 500), uploader=text(info.get('channel') or info.get('uploader'), 200),
                              duration=duration, extractor=provider, extractor_version=__version__), url)
