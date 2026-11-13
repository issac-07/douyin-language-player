"""Opt-in REAL network smoke test, isolated from the user's normal library."""
import argparse
import json
import sys
import time
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'backend'))
from fastapi.testclient import TestClient
from app.config import Settings
from app.main import create_app


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--url', required=True, help='Public video URL you are authorized to import')
    parser.add_argument('--timeout', type=float, default=90)
    parser.add_argument('--public-edge-test', action='store_true', help='Explicitly test the isolated public-page candidate; never reads existing browser profiles')
    parser.add_argument('--output', type=Path, default=ROOT / 'data/validation/phase4-live.json')
    args = parser.parse_args()
    library = ROOT / 'data/validation' / f'phase4-live-{uuid4().hex}'
    settings = replace(Settings.from_env(), data_dir=library, import_timeout_seconds=args.timeout)
    started = time.monotonic()
    with TestClient(create_app(settings)) as client:  # No fixture transport or extractor injection.
        response = client.post('/api/imports/douyin', json={'text': args.url, 'use_public_page': args.public_edge_test})
        if response.status_code != 202:
            report = {'status': 'rejected', 'detail': response.json()}
        else:
            job = response.json()
            print(f"Real anonymous import job: {job['id']}", flush=True)
            previous = None
            while True:
                job = client.get(f"/api/imports/{job['id']}").json()
                if job['status'] != previous:
                    print(job['status'], flush=True); previous = job['status']
                if job['status'] in ('completed', 'failed', 'cancelled'): break
                time.sleep(.25)
            report = job
            if job.get('video'):
                playback = client.get(job['video']['media_url'], headers={'Range': 'bytes=0-1023'})
                report['playback_range_status'] = playback.status_code
                report['playback_range_bytes'] = len(playback.content)
    report.update(tested_at=datetime.now(timezone.utc).isoformat(), real_network=True, library=str(library),
                  wall_seconds=round(time.monotonic() - started, 3))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding='utf-8')
    print(json.dumps({key: report.get(key) for key in ('status', 'error_code', 'error', 'wall_seconds')}, ensure_ascii=False))
    print(f'Report: {args.output}')
    return 0 if report['status'] == 'completed' else 1


if __name__ == '__main__': raise SystemExit(main())
