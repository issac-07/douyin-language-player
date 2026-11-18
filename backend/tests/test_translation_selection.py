import time

from app.models.learning import Translation
from backend.tests.test_p1_improvements import seed


def wait(client, url):
    for _ in range(100):
        data = client.get(url).json()
        if all(s['translation']['status'] != 'pending' for s in data['segments']):
            return data
        time.sleep(.01)
    raise AssertionError('Translation did not complete')


def test_model_selection_caches_and_manual_override(client, imported, monkeypatch):
    service = client.app.state.learning
    _, segment = seed(client, imported)
    calls = []
    for model_id, pair in service.model_translators.items():
        for target, translator in pair.items():
            translator.available = True
            def translate(text, translator=translator, model_id=model_id, target=target):
                calls.append((model_id, target, text))
                return Translation(status='completed', text=f'{model_id}:{target}:result', model=translator.identity, target_language=target)
            monkeypatch.setattr(translator, 'translate', translate)
    base = f"/api/videos/{imported['id']}"
    for model_id in ('marian', 'hymt-1.8b-q8', 'hymt-7b-q4km'):
        result = wait(client, f'{base}/learning?target=vi&model={model_id}')
        assert result['translation_model'] == model_id
        assert result['segments'][0]['translation']['text'] == f'{model_id}:vi:result'
    assert len(calls) == 3
    wait(client, f'{base}/learning?target=vi&model=marian')
    assert len(calls) == 3  # original cache is retained, not overwritten by 7B
    settings = client.get('/api/player-settings').json()
    settings['translation_model'] = 'hymt-7b-q4km'
    assert client.put('/api/player-settings', json=settings).status_code == 200
    assert client.get('/api/player-settings').json()['translation_model'] == 'hymt-7b-q4km'
    assert client.get(base+'/learning').json()['translation_model'] == 'hymt-7b-q4km'
    assert client.get(base+'/learning?model=not-a-model').status_code == 422
    document = client.get(base+'/subtitles').json()
    body = {'analysis_id':document['analysis']['id'], 'revision':segment.revision,
            'source_text':segment.text, 'translation':'My correction', 'target_language':'vi'}
    assert client.put(f'{base}/subtitles/{segment.id}/translation?model=marian',json=body).status_code == 200
    for model_id in service.model_translators:
        result=client.get(f'{base}/learning?model={model_id}').json()['segments'][0]['translation']
        assert result['status'] == 'manual' and result['text'] == 'My correction' and result['model'] is None
    assert len(client.get('/api/translation-models').json()) == 3
