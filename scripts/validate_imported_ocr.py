"""Run real OCR/language processing on the actual successfully imported public MP4."""
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'backend'))
from fastapi.testclient import TestClient
from app.config import Settings
from app.main import create_app


def main():
    source = json.loads((ROOT / 'data/validation/phase4-debug/public-edge-import.json').read_text())
    assert source['status'] == 'completed'
    library, video = Path(source['library']), source['video']
    report = {'library': str(library), 'video_id': video['id'], 'real_import': True}
    with TestClient(create_app(Settings(data_dir=library))) as client:
        response = client.post(f"/api/videos/{video['id']}/analyses", json={'settings': {
            'roi': {'x': .10, 'y': .85, 'width': .80, 'height': .12}, 'sample_fps': .5}, 'force': False})
        assert response.status_code == 202, response.text
        job = response.json()['job']
        deadline = time.monotonic() + 360
        previous = -1
        while time.monotonic() < deadline:
            job = client.get(f"/api/analysis-jobs/{job['id']}").json()
            progress = int(job['progress'] * 10)
            if progress != previous: print('OCR progress:', round(job['progress'] * 100, 1), flush=True); previous = progress
            if job['status'] in ('completed', 'failed', 'cancelled'): break
            time.sleep(.5)
        assert job['status'] == 'completed', job
        document = client.get(f"/api/videos/{video['id']}/subtitles").json()
        report.update(ocr_job=job, subtitle_count=len(document['segments']), samples=[item['text'] for item in document['segments'][:5]])
        deadline = time.monotonic() + 150
        while time.monotonic() < deadline:
            learning = client.get(f"/api/videos/{video['id']}/learning").json()
            completed = [item for item in learning['segments'] if item['translation']['status'] == 'completed']
            if completed: break
            time.sleep(1)
        report['translated_segments'] = len(completed)
        report['learning_segment'] = completed[0] if completed else None
        assert document['segments'] and completed, report
        report['status'] = 'passed'
    target = ROOT / 'data/validation/phase4-debug/imported-learning.json'
    target.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding='utf-8')
    print(json.dumps({key: report[key] for key in ('status', 'subtitle_count', 'translated_segments', 'samples')}, ensure_ascii=False))


if __name__ == '__main__': main()
