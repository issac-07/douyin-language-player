import json
import threading
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from yt_dlp.utils import DownloadError, ExtractorError, GeoRestrictedError, UnsupportedError

from app.main import create_app
from app.services.douyin_urls import ImportFailure
from app.services.import_diagnostics import ExtractorDiagnosticLogger, classify_extractor_failure, endpoint_facts, http_failure
from app.services.safe_http import RequestContext
from .douyin_fixture import FixtureNetwork, NORMAL_URL, VIDEO_ID
from .test_douyin_import import wait


@pytest.mark.parametrize('status,operation,endpoint,expected', [
    (403, 'extract_metadata', 'web_detail_api', 'site_http_403'),
    (403, 'download_media', 'media_file', 'site_http_403'),
    (401, 'extract_metadata', 'web_detail_api', 'login_required'),
    (404, 'extract_metadata', 'web_detail_api', 'extractor_compatibility'),
    (404, 'resolve_url', 'short_link', 'video_unavailable'),
    (410, 'resolve_url', 'video_page', 'video_unavailable'),
    (404, 'download_media', 'media_file', 'download_failure'),
    (500, 'extract_metadata', 'web_detail_api', 'remote_error'),
])
def test_http_status_requires_operation_context(status, operation, endpoint, expected):
    error = http_failure(status, operation, endpoint)
    assert error.code == expected and error.operation == operation and error.http_status == status
    if status == 403: assert 'does not prove that login is required' in error.message


@pytest.mark.parametrize('error,expected', [
    (ExtractorError('Fresh cookies (not necessarily logged in) are needed', expected=True), 'extractor_compatibility'),
    (ExtractorError('Login required. Use credentials', expected=True), 'login_required'),
    (ExtractorError('This video is no longer available', expected=True), 'video_unavailable'),
    (GeoRestrictedError('Not available in your region'), 'geographic_restriction'),
    (UnsupportedError(NORMAL_URL), 'unsupported_extractor'),
    (OSError('sensitive filesystem path'), 'network_error'),
    (ValueError('sensitive payload'), 'extractor_compatibility'),
])
def test_nested_original_exceptions_are_classified(error, expected):
    context = RequestContext(threading.Event(), 10)
    context.begin('extract_metadata')
    # The real yt-dlp DownloadError carries its ExtractorError in exc_info.
    wrapped = DownloadError('hidden raw error', exc_info=(type(error), error, None))
    result = classify_extractor_failure(wrapped, SimpleNamespace(context=context, last_error=None))
    assert result.code == expected
    assert 'sensitive' not in result.message
    assert any(entry.exception_type == type(error).__name__ for entry in context.diagnostics)


def test_sanitized_logs_never_contain_remote_credentials(caplog):
    context = RequestContext(threading.Event(), 10)
    context.begin('extract_metadata')
    secret = 'DO_NOT_LEAK_TEST_SECRET'
    url = f'https://media.douyinvod.com/{secret}?token={secret}'
    logger = ExtractorDiagnosticLogger(context)
    logger.warning(f'Failed HTTP Error 403: {url}; Cookie={secret}; Authorization={secret}')
    logger.error(f'Fresh cookies are needed: {secret}')
    context.record('http_response', http_status=403, **endpoint_facts(url))
    error = classify_extractor_failure(ExtractorError(f'Fresh cookies are needed {url}', expected=True), SimpleNamespace(context=context, last_error=None))
    context.record('failed', category=error.code)
    serialized = json.dumps([entry.model_dump() for entry in context.diagnostics])
    assert secret not in serialized + caplog.text + error.message
    assert 'extract_metadata' in caplog.text and 'extractor_compatibility' in caplog.text
    assert 'fresh_session_cookies_reported_not_login_proof' in serialized


@pytest.mark.parametrize('suffix,category,status', [('999', 'site_http_403', 403), ('995', 'login_required', 401), ('994', 'extractor_compatibility', None)])
def test_job_persists_failing_operation_without_assuming_login(settings, video_path, suffix, category, status):
    network = FixtureNetwork(video_path.read_bytes())
    with TestClient(create_app(settings, import_client_factory=network.factory)) as client:
        job, _ = wait(client, client.post('/api/imports/douyin', json={'text': NORMAL_URL[:-3] + suffix}).json(), 'failed')
        assert job['error_code'] == category
        assert job['error_operation'] == 'extract_metadata'
        assert job['upstream_http_status'] == status
        assert job['extractor_version'] == '2026.10.26'
        assert any(event['operation'] == 'extract_metadata' for event in job['diagnostics'])
        assert not client.get('/api/videos').json()
        assert not list((settings.data_dir / 'downloads').iterdir())
    with TestClient(create_app(settings, import_client_factory=network.factory)) as client:
        stored = client.get(f"/api/imports/{job['id']}").json()
        assert stored['diagnostics'] == job['diagnostics']


@pytest.mark.parametrize('status,category', [(403, 'site_http_403'), (404, 'download_failure')])
def test_media_download_failure_is_not_metadata_or_login_failure(settings, video_path, status, category):
    network = FixtureNetwork(video_path.read_bytes())
    network.replies[('media.douyinvod.com', '/video.mp4')] = (b'', status, {})
    with TestClient(create_app(settings, import_client_factory=network.factory)) as client:
        job, _ = wait(client, client.post('/api/imports/douyin', json={'text': NORMAL_URL}).json(), 'failed')
        assert job['metadata'] is not None
        assert job['error_code'] == category and job['error_operation'] == 'download_media'
        assert job['upstream_http_status'] == status
        assert not client.get('/api/videos').json()


def test_invalid_input_has_machine_readable_category(client):
    response = client.post('/api/imports/douyin', json={'text': 'https://tiktok.com/video/123'})
    assert response.status_code == 422
    assert response.json()['error_code'] == 'unsupported_platform'
    assert response.json()['operation'] == 'validate_url'
