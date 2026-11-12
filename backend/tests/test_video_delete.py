from datetime import datetime, timezone
from pathlib import Path
from uuid import UUID, uuid4
import threading

from app.models.schemas import AnalysisJob, JobStatus, ProcessingSettings, SubtitleSegment


def seed_transcript(client, imported):
    repo = client.app.state.repository
    job = AnalysisJob(id=uuid4(), video_id=UUID(imported['id']), cache_key='delete-test', engine_version='test',
                      settings=ProcessingSettings(), status=JobStatus.COMPLETED, created_at=datetime.now(timezone.utc),
                      total_frames=16, timestamp_uncertainty=.5)
    segment = SubtitleSegment(id=uuid4(), start_time=.5, end_time=2, text='今天', confidence=.99, edited=True)
    repo.save_job(job)
    repo.complete(job, [segment])
    with repo.connect() as db:
        db.execute('INSERT INTO translation_overrides VALUES(?,?,?)', (str(segment.id), '今天', 'Hôm nay'))
        db.execute('INSERT INTO video_sources VALUES(?,?,?)', ('https://www.douyin.com/video/123', imported['id'], '{}'))
        db.execute('INSERT INTO import_jobs VALUES(?,?)', ('history', '{"video":{"id":"'+imported['id']+'"}}'))
    return job


def test_delete_removes_owned_data_and_cache_preserves_source_and_vocabulary(client, imported, settings, video_path):
    seed_transcript(client, imported)
    saved = client.put('/api/vocabulary', json={'word': '今天', 'status': 'learning', 'notes': 'keep'}).json()
    cached = settings.media_dir / f"{imported['id']}.mp4"
    original = video_path.read_bytes()
    response = client.delete(f"/api/videos/{imported['id']}")
    assert response.status_code == 200, response.text
    assert response.json() == {'deleted': True, 'media_cleanup_pending': False}
    assert not cached.exists()
    assert video_path.read_bytes() == original
    assert client.get('/api/videos').json() == []
    assert client.get(imported['media_url']).status_code == 404
    assert client.get('/api/vocabulary').json() == [saved]
    with client.app.state.repository.connect() as db:
        for table in ['analyses', 'subtitle_segments', 'active_analyses', 'translation_overrides', 'video_sources', 'import_jobs', 'processing_settings']:
            assert db.execute(f'SELECT COUNT(*) FROM {table}').fetchone()[0] == 0
    with video_path.open('rb') as source:
        restored = client.post('/api/videos', files={'file': ('again.mp4', source, 'video/mp4')})
    assert restored.status_code == 201
    assert restored.json()['video']['id'] != imported['id']


def test_delete_locked_file_rolls_back_transcripts(client, imported, monkeypatch):
    job = seed_transcript(client, imported)
    original = Path.replace
    def locked(path, target):
        if path.name == f"{imported['id']}.mp4":
            raise PermissionError('locked')
        return original(path, target)
    monkeypatch.setattr(Path, 'replace', locked)
    assert client.delete(f"/api/videos/{imported['id']}").status_code == 409
    document = client.get(f"/api/videos/{imported['id']}/subtitles").json()
    assert document['analysis']['id'] == str(job.id)
    assert document['segments'][0]['edited']
    assert client.get(imported['media_url']).status_code == 200


def test_delete_busy_and_origin_guards(client, imported):
    key = uuid4()
    client.app.state.worker.events[key] = threading.Event()
    try:
        assert client.delete(f"/api/videos/{imported['id']}").status_code == 409
    finally:
        client.app.state.worker.events.clear()
    assert client.delete(f"/api/videos/{imported['id']}", headers={'Origin': 'https://example.com'}).status_code == 403
    assert client.delete(f'/api/videos/{uuid4()}').status_code == 404
    assert client.delete('/api/videos/not-an-id').status_code == 422


def test_delete_missing_cached_file_and_version(client, imported, settings):
    (settings.media_dir / f"{imported['id']}.mp4").unlink()
    assert client.delete(f"/api/videos/{imported['id']}").status_code == 200
    assert client.get('/api/health').json()['version'] == '0.4.5'
