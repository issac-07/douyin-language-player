"""Opt-in real-network diagnostics. No cookies, signed requests or raw remote data are logged."""
import argparse
import json
import subprocess
import sys
import threading
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'backend'))
from yt_dlp import YoutubeDL
from yt_dlp.extractor.tiktok import DouyinIE
from yt_dlp.version import __version__
from app.services.douyin_extractor import YtDlpExtractor
from app.services.douyin_urls import ImportFailure, canonical_video_url, parse_douyin_input
from app.services.import_diagnostics import ExtractorDiagnosticLogger, classify_extractor_failure, endpoint_facts, http_failure
from app.services.safe_http import SafeHTTPClient, RequestContext, validate_network_url


def failure(error):
    return {'category': error.code, 'operation': error.operation, 'http_status': error.http_status, 'message': error.message}


def native_probe(canonical):
    """Official release in a fresh child process, with its own standard transport for comparison."""
    if canonical_video_url(parse_douyin_input(canonical)) != canonical:
        raise ValueError('Canonical public Douyin URL required')
    context = RequestContext(threading.Event(), 40)
    context.begin('extract_metadata')
    client = SimpleNamespace(context=context, last_error=None)
    class ReportingYoutubeDL(YoutubeDL):
        def urlopen(self, request):
            url = request if isinstance(request, str) else request.url
            facts = endpoint_facts(validate_network_url(url, 'extractor'))
            try:
                response = super().urlopen(request)
                context.record('http_response', http_status=response.status, **facts)
                return response
            except Exception as exc:
                status = getattr(exc, 'status', None)
                if isinstance(status, int): client.last_error = http_failure(status, context.operation, facts['endpoint'])
                context.record('upstream_error', http_status=status if isinstance(status, int) else None,
                               exception_type=type(exc).__name__, **facts)
                raise
    report = {'version': __version__, 'transport': 'official yt-dlp, isolated process', 'cookies_supplied': False}
    try:
        with ReportingYoutubeDL({'quiet': True, 'logger': ExtractorDiagnosticLogger(context), 'skip_download': True,
                'cookiefile': None, 'cookiesfrombrowser': None, 'usenetrc': False, 'proxy': '', 'cachedir': False,
                'extractor_retries': 0, 'retries': 0, 'socket_timeout': 15, 'plugin_dirs': []}, auto_init=False) as ydl:
            ydl.add_info_extractor(DouyinIE())
            info = ydl.extract_info(canonical, download=False, process=False, ie_key='Douyin')
            report.update(status='metadata_extracted', video_id=info.get('id'), formats_count=len(info.get('formats', [])))
    except Exception as exc:
        error = classify_extractor_failure(exc, client)
        report.update(status='failed', error=failure(error))
    report['diagnostics'] = [item.model_dump(exclude_none=True) for item in context.diagnostics]
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--url', required=True)
    parser.add_argument('--native-only', action='store_true', help=argparse.SUPPRESS)
    parser.add_argument('--output', type=Path, default=ROOT / 'data/validation/phase4-debug/real-diagnostics.json')
    args = parser.parse_args()
    if args.native_only:
        print(json.dumps(native_probe(args.url)))
        return
    context = RequestContext(threading.Event(), 50)
    client = SafeHTTPClient(context)
    report = {'tested_at': datetime.now(timezone.utc).isoformat(), 'real_network': True, 'version': __version__}
    canonical = None
    try:
        url = parse_douyin_input(args.url)
        context.begin('resolve_url')
        canonical = canonical_video_url(url)
        if not canonical:
            with client.open(url, role='page') as response: canonical = canonical_video_url(response.url)
        report['resolution'] = {'status': 'completed' if canonical else 'unresolved', 'canonical_url': canonical}
        if not canonical: raise ImportFailure('unresolved_link', 'No video URL was resolved.')
        media = YtDlpExtractor().extract(canonical, client)
        report['app_extraction'] = {'status': 'completed', 'video_id': media.metadata.video_id, 'duration': media.metadata.duration}
        # The separate smoke command owns real download/import, never this metadata diagnostic.
        report['media_download'] = {'status': 'not_attempted', 'reason': 'Run smoke_douyin_import.py for complete media import.'}
    except ImportFailure as exc:
        report['app_extraction'] = {'status': 'failed', 'error': failure(exc)}
        report['media_download'] = {'status': 'not_attempted', 'reason': 'No media URL: metadata extraction did not complete.'}
    report['app_diagnostics'] = [item.model_dump(exclude_none=True) for item in context.diagnostics]
    if canonical:
        try:
            process = subprocess.run([sys.executable, '-X', 'utf8', __file__, '--url', canonical, '--native-only'],
                        capture_output=True, text=True, encoding='utf-8', timeout=50,
                        creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
            report['official_release_comparison'] = json.loads(process.stdout) if process.returncode == 0 else {'status': 'child_failed', 'exit_code': process.returncode}
        except subprocess.TimeoutExpired:
            report['official_release_comparison'] = {'status': 'network_timeout'}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2), encoding='utf-8')
    print(json.dumps(report, indent=2))


if __name__ == '__main__': main()
