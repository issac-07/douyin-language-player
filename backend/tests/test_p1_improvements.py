import threading
import time
from datetime import datetime, timezone
from uuid import UUID, uuid4

from app.models.schemas import AnalysisJob, JobStatus, ProcessingSettings, SubtitleSegment
from app.services.pipeline import OCRObservation
from app.services.translation import LocalTranslator
from backend.tests.test_analysis_api import wait_for_job


def seed(client, imported, edited=False):
    repo = client.app.state.repository
    job = AnalysisJob(id=uuid4(), video_id=UUID(imported['id']), cache_key='test', engine_version='test',
        settings=ProcessingSettings(), status=JobStatus.COMPLETED, created_at=datetime.now(timezone.utc), total_frames=16, timestamp_uncertainty=.5)
    segment = SubtitleSegment(id=uuid4(), start_time=.5, end_time=2, text='今天我们一起去吃饭', confidence=.99, edited=edited)
    repo.save_job(job); repo.complete(job, [segment])
    return job, segment


def test_heartbeat_during_refinement_and_cancellation_preserves_results(client, imported, monkeypatch):
    old, _ = seed(client, imported)
    entered, release = threading.Event(), threading.Event()
    class Engine:
        def recognize(self, sample):
            return OCRObservation(sample.timestamp, '今天我们一起去吃饭', .99)
    def blocking(*args, on_progress):
        on_progress(0, 1); entered.set(); release.wait(8)
    monkeypatch.setattr('app.services.analysis_worker.refine_starts', blocking)
    client.app.state.worker.engine = Engine()
    base = f"/api/videos/{imported['id']}"
    try:
        result = client.post(base+'/analyses', json={'force':True, 'settings':{'performance':{'refine_timing':True}}})
        job = result.json()['job']
        assert entered.wait(5)
        time.sleep(.85)
        first = client.get(f"/api/analysis-jobs/{job['id']}").json()
        time.sleep(.85)
        second = client.get(f"/api/analysis-jobs/{job['id']}").json()
        assert first['stage'] == second['stage'] == 'refining'
        assert second['updated_at'] > first['updated_at']
        assert second['metrics']['total_seconds'] > first['metrics']['total_seconds']
        assert second['progress'] < 1
        assert client.post(f"/api/analysis-jobs/{job['id']}/cancel").json()['status'] == 'cancelled'
    finally:
        release.set()
    assert client.get(base+'/subtitles').json()['analysis']['id'] == str(old.id)


def test_storage_cleanup_preserves_active_corrected_and_vocabulary(client, imported, settings):
    corrected, _ = seed(client, imported, edited=True)
    disposable, _ = seed(client, imported)
    active, _ = seed(client, imported)
    word = client.put('/api/vocabulary', json={'word':'今天'}).json()
    media = settings.media_dir / f"{imported['id']}.mp4"
    before = media.read_bytes()
    inventory = client.get('/api/storage').json()
    assert inventory['groups']['media']['bytes'] == len(before)
    assert inventory['counts']['analyses'] == 3
    response = client.post('/api/storage/cleanup', json={'kind':'uncorrected_history'})
    assert response.status_code == 200
    assert response.json()['deleted_records'] == 1
    repo = client.app.state.repository
    assert repo.get_job(corrected.id) is not None
    assert repo.get_job(disposable.id) is None
    assert repo.get_job(active.id) is not None
    assert media.read_bytes() == before
    assert client.get('/api/vocabulary').json() == [word]
    assert client.post('/api/storage/cleanup', json={'kind':'media'}).status_code == 422
    assert client.post('/api/storage/cleanup', json={'kind':'translation_cache'}).status_code == 200


def test_direct_english_model_and_language_isolated_overrides(client, imported, settings):
    result = LocalTranslator(settings.resource_dir, 'en').translate('今天我们一起去吃饭')
    assert result.status == 'completed', result.error
    assert any(word in result.text.lower() for word in ('eat', 'dinner'))
    assert result.target_language == 'en'
    assert 'zh->en:' in result.model
    job, segment = seed(client, imported)
    base = f"/api/videos/{imported['id']}"
    body = {'analysis_id':str(job.id), 'revision':0, 'source_text':segment.text, 'translation':'My English correction', 'target_language':'en'}
    response = client.put(base+f'/subtitles/{segment.id}/translation', json=body)
    assert response.status_code == 200, response.text
    english = client.get(base+'/learning?target=en').json()
    vietnamese = client.get(base+'/learning?target=vi').json()
    assert english['segments'][0]['translation']['status'] == 'manual'
    assert english['segments'][0]['translation']['target_language'] == 'en'
    assert vietnamese['segments'][0]['translation']['text'] != body['translation']
    assert vietnamese['segments'][0]['translation']['status'] != 'manual'
    body.update(translation='Bản sửa tiếng Việt', target_language='vi')
    assert client.put(base+f'/subtitles/{segment.id}/translation', json=body).status_code == 200
    assert client.get(base+'/learning?target=en').json()['segments'][0]['translation']['text'] == 'My English correction'
    client.post('/api/storage/cleanup', json={'kind':'translation_cache'})
    assert client.get(base+'/learning?target=vi').json()['segments'][0]['translation']['text'] == body['translation']


def test_cleanup_refuses_active_workers(client):
    event_id = uuid4()
    client.app.state.worker.events[event_id] = threading.Event()
    try:
        response = client.post('/api/storage/cleanup', json={'kind':'translation_cache'})
        assert response.status_code == 409
    finally:
        client.app.state.worker.events.pop(event_id)
