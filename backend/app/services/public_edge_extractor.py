"""Ordinary official-page fallback, never a modified or signed private API client."""
import json
import shutil
import subprocess
import threading
import time
import os

from yt_dlp import YoutubeDL
from yt_dlp.extractor.tiktok import DouyinIE
from app.config import PROJECT_ROOT
from app.services.browser_proxy import PublicBrowserProxy
from app.services.douyin_extractor import YtDlpExtractor
from app.services.douyin_urls import ImportFailure
from app.services.import_diagnostics import ExtractorDiagnosticLogger


class PublicEdgeExtractor:
    def __init__(self, node='node'): self.node = node

    def extract(self, canonical_url, client):
        context = client.context
        context.check()
        context.begin('extract_metadata')
        context.record('public_page_fallback_started')
        helper = PROJECT_ROOT / 'frontend/scripts/extract-douyin-public.mjs'
        if not shutil.which(self.node) or not helper.is_file():
            raise ImportFailure('extractor_compatibility', 'The public-page fallback needs the project Node dependencies and installed Microsoft Edge. Local MP4 import remains available.')
        chunks, overflow = [], threading.Event()
        process = None
        with PublicBrowserProxy(context) as proxy:
            try:
                process = subprocess.Popen([self.node, str(helper), canonical_url, proxy.url],
                    stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                    creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
                def read():
                    total = 0
                    while data := process.stdout.read(65536):
                        total += len(data)
                        if total > 16 * 1024 * 1024: overflow.set(); return
                        chunks.append(data)
                reader = threading.Thread(target=read, daemon=True)
                reader.start()
                deadline = time.monotonic() + 60
                while process.poll() is None:
                    context.check()
                    if overflow.is_set() or time.monotonic() > deadline:
                        raise ImportFailure('extractor_compatibility', 'The ordinary public-page fallback did not provide bounded metadata in time. No login or verification workaround was attempted. Import a local MP4 instead.')
                    time.sleep(.1)
                reader.join(timeout=2)
                if process.returncode or overflow.is_set(): raise ValueError()
                result = json.loads(b''.join(chunks))
                if result.get('status') != 'ok':
                    for entry in result.get('diagnostics', [])[:12]:
                        host = entry.get('host', '')
                        if host.endswith('.douyin.com') and isinstance(entry.get('status'), int):
                            context.record('public_page_http_response', host=host, http_status=entry['status'], endpoint='web_detail_api')
                    raise ValueError()
                detail = result['detail']
                if str(detail.get('aweme_id')) != canonical_url.rsplit('/', 1)[-1]: raise ValueError()
                video = detail.get('video') or {}
                if detail.get('is_live') or video.get('has_drm') or video.get('is_drm') or video.get('drm_type') not in (None, 0, '0', ''):
                    raise ImportFailure('unsupported_media', 'Live or DRM-protected media is not imported. Choose an authorized public non-DRM video.')
                labels = [item.get('text') for item in detail.get('hybrid_label') or [] if isinstance(item, dict)]
                if any(item in ('Private', 'Friends only', 'Followers only') for item in labels) or detail.get('status', {}).get('is_private') or detail.get('status', {}).get('is_delete'):
                    raise ImportFailure('video_unavailable', 'The public page identifies this video as restricted. Import an authorized local MP4 instead.')
                # Reuse the maintained installed parser, offline. It receives only actual public-page data.
                with YoutubeDL({'quiet': True, 'logger': ExtractorDiagnosticLogger(context), 'writesubtitles': False,
                                'cookiefile': None, 'cookiesfrombrowser': None, 'cachedir': False}, auto_init=False) as ydl:
                    extractor = DouyinIE(ydl)
                    info = extractor._parse_aweme_video_app(detail)
                media = YtDlpExtractor.media_from_info(info, canonical_url, context, 'public-edge-page+yt-dlp-parser')
                context.record('public_page_metadata_received')
                return media
            except (ValueError, KeyError, TypeError, OSError):
                raise ImportFailure('extractor_compatibility', 'The ordinary public page did not expose usable video metadata. A login or verification prompt is not bypassed. Try another public link or import a local MP4.') from None
            finally:
                if process:
                    if process.poll() is None:
                        try: process.stdin.write(b'cancel\n'); process.stdin.flush(); process.wait(timeout=3)
                        except (OSError, subprocess.TimeoutExpired):
                            if process.poll() is None:
                                # Kill only this still-owned helper process tree on Windows.
                                if os.name == 'nt':
                                    subprocess.run(['taskkill', '/PID', str(process.pid), '/T', '/F'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=10,
                                                   creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
                                else: process.kill()
                                process.wait(timeout=10)
                    process.stdin.close(); process.stdout.close()


class CompatibleDouyinExtractor:
    def __init__(self, node='node'):
        self.primary, self.fallback = YtDlpExtractor(), PublicEdgeExtractor(node)

    def extract(self, canonical_url, client):
        try: return self.primary.extract(canonical_url, client)
        except ImportFailure as error:
            if error.code not in ('site_http_403', 'extractor_compatibility'): raise
            client.context.record('direct_extractor_failed', category=error.code, http_status=error.http_status)
            return self.fallback.extract(canonical_url, client)
