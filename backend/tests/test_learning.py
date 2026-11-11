import json
import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from app.services.chinese_processing import process_chinese
from app.services.dictionary import Dictionary
from app.services.translation import LocalTranslator


@pytest.mark.parametrize('text', ['今天我们一起去吃饭', '你在干什么？', '我不知道发生了什么', '银行行长', '今天2026年🙂'])
def test_sentence_processing_preserves_original_offsets(text):
    tokens = process_chinese(text)
    assert ''.join(token.text for token in tokens) == text
    for token in tokens:
        assert text[token.start:token.end] == token.text
        if token.selectable:
            assert token.pinyin


def test_segmentation_and_contextual_pinyin():
    tokens = process_chinese('今天我们一起去吃饭')
    assert [token.text for token in tokens] == ['今天', '我们', '一起', '去', '吃饭']
    assert [token.pinyin for token in tokens] == ['jīn tiān', 'wǒ men', 'yì qǐ', 'qù', 'chī fàn']
    assert 'háng' in ' '.join(token.pinyin for token in process_chinese('银行行长'))
    assert process_chinese('一样')[0].pinyin == 'yí yàng'
    assert ' '.join(token.pinyin for token in process_chinese('不对')) == 'bú duì'
    assert 'yī' in ' '.join(token.pinyin for token in process_chinese('第一天'))


def test_real_dictionary_and_missing_word():
    dictionary = Dictionary(Path('data/resources').resolve())
    result = dictionary.lookup('今天')
    assert result.available
    assert any('today' in meaning.lower() for entry in result.entries for meaning in entry.meanings)
    assert result.license == 'CC-BY-SA-4.0'
    assert dictionary.lookup('不存在词语不存在').entries == []


def test_real_local_vietnamese_model():
    translator = LocalTranslator(Path('data/resources').resolve())
    first = translator.translate('今天我们一起去吃饭')
    second = translator.translate('你在干什么？')
    assert first.status == second.status == 'completed'
    assert 'Hôm nay' in first.text
    assert 'làm gì' in second.text
    assert first.text != second.text
    assert first.seconds > 0


def test_missing_model_and_dictionary_are_explicit(tmp_path):
    result = LocalTranslator(tmp_path).translate('你好')
    assert result.status == 'unavailable' and result.text is None
    assert Dictionary(tmp_path).lookup('你好').available is False


def wait_learning(client, base):
    deadline = time.monotonic() + 45
    while time.monotonic() < deadline:
        response = client.get(base + '/learning')
        assert response.status_code == 200, response.text
        result = response.json()
        if result['segments'] and all(segment['translation']['status'] != 'pending' for segment in result['segments']):
            return result
        time.sleep(.1)
    pytest.fail('Local translation did not complete')


def test_actual_ocr_to_language_corrections_vocabulary_and_settings(client, imported, settings):
    from backend.tests.test_analysis_api import wait_for_job

    base = f"/api/videos/{imported['id']}"
    job = client.post(base + '/analyses', json={}).json()['job']
    assert wait_for_job(client, job['id'])['status'] == 'completed'
    result = wait_learning(client, base)
    assert len(result['segments']) == 3
    assert all(segment['translation']['status'] == 'completed' for segment in result['segments'])
    assert [token['text'] for token in result['segments'][0]['tokens']] == ['今天', '我们', '一起', '去', '吃饭']
    assert 'Hôm nay' in result['segments'][0]['translation']['text']
    saved = client.put('/api/vocabulary', json={'word': '今天', 'status': 'learning', 'notes': 'My first saved word'}).json()
    assert saved['entries'] and saved['pinyin'] == 'jīn tiān'
    updated = client.put('/api/vocabulary', json={'word': '今天', 'status': 'known', 'notes': 'Reviewed'}).json()
    assert updated['id'] == saved['id']
    assert len(client.get('/api/vocabulary').json()) == 1
    csv = client.get('/api/vocabulary/export/csv')
    assert csv.status_code == 200 and '今天' in csv.text and 'Reviewed' in csv.text
    subtitle = client.get(base + '/subtitles').json()['segments'][0]
    manual = {'analysis_id': job['id'], 'revision': subtitle['revision'], 'source_text': subtitle['text'], 'translation': 'Hôm nay chúng ta cùng đi ăn.'}
    assert client.put(base + f"/subtitles/{subtitle['id']}/translation", json=manual).status_code == 200
    assert client.get(base + '/learning').json()['segments'][0]['translation']['status'] == 'manual'
    player = client.get('/api/player-settings').json()
    player.update({'mode': 'minimal', 'font_size': 26, 'background_opacity': .7, 'vertical_offset': -5})
    assert client.put('/api/player-settings', json=player).status_code == 200
    assert client.put('/api/player-settings', json={**player, 'font_size': 500}).status_code == 422
    with TestClient(create_app(settings)) as restarted:
        assert restarted.get('/api/player-settings').json() == player
        assert restarted.get('/api/vocabulary').json()[0]['status'] == 'known'
        assert restarted.get(base + '/learning').json()['segments'][0]['translation']['text'] == manual['translation']
    patch = {'analysis_id': job['id'], 'revision': subtitle['revision'], 'text': '你在干什么？', 'start_time': .5, 'end_time': 2.5}
    assert client.patch(base + f"/subtitles/{subtitle['id']}", json=patch).status_code == 200
    changed = wait_learning(client, base)
    assert changed['segments'][0]['translation']['status'] == 'completed'
    assert changed['segments'][0]['text'] == '你在干什么？'
    assert changed['segments'][0]['tokens'][0]['text'] != '今天'
    assert client.put(base + f"/subtitles/{subtitle['id']}/translation", json=manual).status_code == 409
    assert client.delete(f"/api/vocabulary/{saved['id']}").status_code == 204
    assert client.get('/api/vocabulary').json() == []
