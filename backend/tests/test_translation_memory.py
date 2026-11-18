import threading
import time

from app.models.learning import Translation


def eventually(predicate, timeout=30):
    deadline=time.monotonic()+timeout
    while time.monotonic()<deadline:
        value=predicate()
        if value:
            return value
        time.sleep(.02)
    raise AssertionError('Condition timed out')


def test_release_during_work_skips_queue_and_polling_does_not_reload(client,monkeypatch):
    service=client.app.state.learning
    translator=service.translator
    translator.available=True
    entered,finish=threading.Event(),threading.Event()
    calls=[]
    def translate(text):
        calls.append(text)
        if text=='first':
            entered.set()
            assert finish.wait(5)
        return Translation(status='completed',text='translated '+text,model=translator.identity)
    monkeypatch.setattr(translator,'translate',translate)
    service.translation('first')
    assert entered.wait(5)
    service.translation('second')
    try:
        response=client.post('/api/translation-memory/release')
        assert response.status_code==202
        assert response.json()['paused'] and response.json()['release_pending']
        assert service.translation('second').status=='paused'
        assert not service._expire_idle(now=service.last_activity+1000) # in-flight work is protected
    finally:
        finish.set()
    eventually(lambda:not service.memory_status()['release_pending'])
    assert calls==['first']
    assert service.translation('first').text=='translated first' # cache remains readable while paused
    for _ in range(5):
        assert service.translation('second').status=='paused'
    assert calls==['first']
    assert client.post('/api/translation-memory/resume').json()['paused'] is False
    service.translation('second')
    eventually(lambda:service.translation('second').status=='completed')
    assert calls==['first','second']


def test_real_idle_unload_preserves_cache_and_can_reload(client):
    service=client.app.state.learning
    service.translation('你好，今天怎么样？')
    eventually(lambda:service.translation('你好，今天怎么样？').status=='completed')
    backend=service.translator.backend
    process=backend.process
    assert process is not None and process.poll() is None
    assert not service._expire_idle(now=service.last_activity+service.idle_seconds-1)
    assert service._expire_idle(now=service.last_activity+service.idle_seconds+1)
    assert process.poll() is not None and backend.process is None
    assert not client.get('/api/translation-memory').json()['model_loaded']
    assert service.translation('你好，今天怎么样？').status=='completed'
    assert backend.process is None # cached reads do not load weights or reset the idle deadline
    service.translation('我们明天见。')
    eventually(lambda:service.translation('我们明天见。').status=='completed')
    new_process=backend.process
    assert new_process is not None and new_process.poll() is None
    client.post('/api/translation-memory/release')
    eventually(lambda:not service.memory_status()['release_pending'])
    assert new_process.poll() is not None and backend.process is None

def test_maintenance_timer_unloads_without_user_request(settings,monkeypatch):
    from fastapi.testclient import TestClient
    from app.main import create_app
    monkeypatch.setenv('DLP_TRANSLATION_IDLE_SECONDS','0.2')
    with TestClient(create_app(settings)) as client:
        service=client.app.state.learning
        service.translation('今天天气不错。')
        eventually(lambda:service.translation('今天天气不错。').status=='completed')
        eventually(lambda:not service.memory_status()['model_loaded'])
        assert not service.memory_status()['paused']
        assert service.translation('今天天气不错。').status=='completed'
    assert not service.maintenance.is_alive()
