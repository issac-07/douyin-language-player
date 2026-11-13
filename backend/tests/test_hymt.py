from pathlib import Path
from unittest.mock import Mock

import pytest

from app.config import Settings
from app.services.hymt import HyMTBackend
from app.services.learning import LearningService, cache_key
from app.services.repository import Repository
from app.services.translation import LocalTranslator


def test_hymt_failure_is_explicit_and_never_uses_marian(tmp_path, monkeypatch):
    monkeypatch.delenv('DLP_TRANSLATION_ENGINE', raising=False)
    engine = Mock(available=True, identity='hymt-test')
    engine.translate.side_effect = TimeoutError('request deadline')
    translator = LocalTranslator(tmp_path, backend=engine)
    result = translator.translate('你好')
    assert result.status == 'failed' and result.text is None
    assert 'deadline' in result.error and 'hymt-test' in result.model
    assert translator.translate('中' * 1001).status == 'failed'
    engine.translate.assert_called_once_with('你好', 'vi')


def test_both_languages_share_one_engine_and_separate_cache(tmp_path, monkeypatch):
    monkeypatch.delenv('DLP_TRANSLATION_ENGINE', raising=False)
    repo = Repository(tmp_path / 'library.sqlite3')
    repo.initialize()
    service = LearningService(repo, Settings(data_dir=tmp_path, resource_dir=tmp_path))
    try:
        assert service.translators['vi'].backend is service.translators['en'].backend
        vi = service.translators['vi'].identity
        en = service.translators['en'].identity
        assert cache_key('你好', vi) != cache_key('你好', en)
        assert cache_key('你好', vi) != cache_key('你好', 'zh->vi:Helsinki-NLP/opus-mt-zh-vi:beam4-v1')
    finally:
        service.shutdown()
    assert service.translator.backend.closed


@pytest.mark.parametrize('reason, content', [('length', 'partial'), ('stop', '')])
def test_reject_truncated_or_empty_output(tmp_path, monkeypatch, reason, content):
    engine = HyMTBackend(tmp_path)
    monkeypatch.setattr(engine, '_start', lambda: None)
    request = Mock(return_value={'choices': [{'finish_reason': reason, 'message': {'content': content}}]})
    monkeypatch.setattr(engine, '_request', request)
    with pytest.raises(ValueError):
        engine.translate('你好', 'en')
    body = request.call_args.args[1]
    assert len(body['messages']) == 1
    assert '英语' in body['messages'][0]['content']
    assert body['max_tokens'] == 1024
    engine.close()
