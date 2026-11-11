"""Validate real language processing against an existing completed local OCR analysis."""
import argparse
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'backend'))

from fastapi.testclient import TestClient
from app.config import Settings
from app.main import create_app


def validate(data_dir: Path, fresh: bool = False):
    with TestClient(create_app(Settings(data_dir=data_dir))) as client:
        if fresh:
            with client.app.state.repository.connect() as db:
                db.execute('DELETE FROM language_cache')
                db.execute('DELETE FROM translation_cache')
        videos = client.get('/api/videos').json()
        video = next((video for video in videos if client.get(f"/api/videos/{video['id']}/subtitles").json()['analysis']), None)
        if not video:
            raise RuntimeError('This library has no completed OCR analysis.')
        endpoint = f"/api/videos/{video['id']}/learning"
        started = time.perf_counter()
        while True:
            result = client.get(endpoint).json()
            completed = sum(segment['translation']['status'] in ('completed', 'manual') for segment in result['segments'])
            pending = sum(segment['translation']['status'] == 'pending' for segment in result['segments'])
            print(f"Translated {completed}/{len(result['segments'])}; {pending} pending", flush=True)
            if not pending:
                break
            time.sleep(2)
        elapsed = time.perf_counter() - started
        cached_started = time.perf_counter()
        cached = client.get(endpoint).json()
        cached_seconds = time.perf_counter() - cached_started
        report = {'video_id': video['id'], 'source_name': video['original_name'], 'segments': len(result['segments']),
                  'translated': completed, 'total_seconds': elapsed, 'cached_request_seconds': cached_seconds,
                  'dictionary': client.get('/api/dictionary', params={'word': '今天'}).json(), 'document': cached}
        path = data_dir / 'language-report.json'
        path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
        print(json.dumps({'report': str(path), 'segments': len(result['segments']), 'translated': completed, 'total_seconds': elapsed,
                          'cached_request_seconds': cached_seconds, 'examples': result['segments'][:3]}, ensure_ascii=True), flush=True)
        if completed != len(result['segments']):
            raise RuntimeError('Some translations failed; inspect language-report.json.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--data-dir', type=Path, required=True, help='Existing isolated validation library, not an active app database')
    parser.add_argument('--fresh', action='store_true', help='Clear only generated language/translation caches in this isolated library first')
    args = parser.parse_args()
    validate(args.data_dir.resolve(), args.fresh)
