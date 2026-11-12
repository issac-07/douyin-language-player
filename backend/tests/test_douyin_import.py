import socket
import subprocess
import threading
import time
from unittest.mock import Mock
from dataclasses import replace
from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from app.main import create_app
from app.services.douyin_urls import ImportFailure, parse_douyin_input
from app.services.safe_http import RequestContext, public_addresses, validate_network_url
from app.services.import_media import prepare_media
from app.services.video_import import probe_video
from app.services.repository import Repository
from .douyin_fixture import FixtureNetwork, RawResponse, NORMAL_URL, VIDEO_ID


def wait(client, job, expected='completed'):
    deadline = time.monotonic() + 20
    seen = set()
    while time.monotonic() < deadline:
        result = client.get(f"/api/imports/{job['id']}").json()
        seen.add(result['status'])
        if result['status'] in ('completed', 'failed', 'cancelled'):
            assert result['status'] == expected, result
            return result, seen
        time.sleep(.02)
    raise AssertionError('URL import did not terminate')


@pytest.mark.parametrize('text,expected', [
    (NORMAL_URL, NORMAL_URL), (NORMAL_URL + '/?from=share', NORMAL_URL),
    (f'https://douyin.com/?modal_id={VIDEO_ID}', NORMAL_URL),
    ('3.82 分享中文 #学习 https://v.douyin.com/AbC123/ 复制此链接，打开抖音', 'https://v.douyin.com/AbC123/'),
    ('看这里：https://v.douyin.com/AbC123/。', 'https://v.douyin.com/AbC123/'),
])
def test_parse(text, expected): assert parse_douyin_input(text) == expected


@pytest.mark.parametrize('text', [
    '', 'not a url', 'https://tiktok.com/video/1234567890', 'https://www.douyin.com.evil.test/video/1234567890',
    'https://www.douyin.com@127.0.0.1/video/1234567890', 'https://127.0.0.1/video/1234567890',
    'http://www.douyin.com/video/1234567890', 'https://www.douyin.com:8000/video/1234567890',
    'https://www.douyin.com/video/no', 'https://v.douyin.com/abc/../../x',
    NORMAL_URL + ' https://v.douyin.com/Other/', 'https://www.douyin.com\\@localhost/video/1234567890',
])
def test_reject_input(text):
    with pytest.raises(ImportFailure): parse_douyin_input(text)


@pytest.mark.parametrize('url', ['https://localhost/', 'https://127.0.0.1/', 'file:///C:/Windows/win.ini',
    'https://douyin.com.evil.test/', 'https://media.douyinvod.com:8443/x', 'https://user:pass@douyin.com/', 'https://[::1]/'])
def test_network_allowlist(url):
    with pytest.raises(ImportFailure): validate_network_url(url, 'media')


@pytest.mark.parametrize('address', ['127.0.0.1', '10.0.0.1', '169.254.169.254', '192.168.1.1', '100.64.0.1', '0.0.0.0', '224.0.0.1', '::1', 'fe80::1', '::ffff:127.0.0.1'])
def test_private_dns(address):
    family = socket.AF_INET6 if ':' in address else socket.AF_INET
    with pytest.raises(ImportFailure, match='non-public'):
        public_addresses('www.douyin.com', lambda *a, **kw: [(family, 1, 6, '', (address, 443))])


def test_redirect_security_and_anonymous_headers():
    network = FixtureNetwork(b'x')
    network.replies[('v.douyin.com', '/Bad/')] = (b'', 302, {'Location': 'https://127.0.0.1/private'})
    client = network.factory(RequestContext(threading.Event(), 10))
    with pytest.raises(ImportFailure, match='outside'): client.open('https://v.douyin.com/Bad/', role='page')
    assert len(network.calls) == 1
    with pytest.raises(ImportFailure):
        client.open(NORMAL_URL + '/bad', headers={'Cookie': 'secret', 'Authorization': 'secret'})
    assert not any(key.lower() in ('cookie', 'authorization') for key in network.calls[-1][2])


def test_complete_import_library_dedup_and_persistence(settings, video_path):
    network = FixtureNetwork(video_path.read_bytes(), delay=.005)
    with TestClient(create_app(settings, import_client_factory=network.factory)) as client:
        request = client.post('/api/imports/douyin', json={'text': '分享 https://v.douyin.com/Abc123/', 'analyze_after_import': True})
        assert request.status_code == 202, request.text
        job, seen = wait(client, request.json())
        assert job['bytes_downloaded'] == len(network.media)
        assert job['conversion'] == 'none'
        assert job['video']['duration'] == pytest.approx(8, abs=.05)
        assert job['video']['source_url'] == NORMAL_URL
        assert job['metadata']['extractor_version'] == '2026.10.26'
        assert 'Select and save' in job['analysis_message']
        assert job['analysis_job_id'] is None
        video = job['video']
        response = client.get(video['media_url'], headers={'Range': 'bytes=0-1023'})
        assert response.status_code == 206 and response.content == network.media[:1024]
        assert client.get(f"/api/videos/{video['id']}/subtitles").status_code == 200
        assert client.get('/api/health').json()['ocr_available']
        calls = len(network.calls)
        repeated, _ = wait(client, client.post('/api/imports/douyin', json={'text': NORMAL_URL}).json())
        assert repeated['reused'] and repeated['video']['id'] == video['id'] and len(network.calls) == calls
        # Another source URL with identical bytes reuses the existing hash and library entry.
        other, _ = wait(client, client.post('/api/imports/douyin', json={'text': NORMAL_URL[:-3] + '888'}).json())
        assert other['reused'] and other['video']['id'] == video['id']
        assert len(client.get('/api/videos').json()) == 1
        assert not list((settings.data_dir / 'downloads').iterdir())
    with TestClient(create_app(settings, import_client_factory=network.factory)) as reopened:
        assert reopened.get('/api/videos').json()[0]['source_url'] == NORMAL_URL
        assert reopened.get(f"/api/imports/{job['id']}").json()['status'] == 'completed'


@pytest.mark.parametrize('suffix,code', [('999', 'site_http_403'), ('998', 'extractor_compatibility')])
def test_restricted_no_fabricated_success(settings, video_path, suffix, code):
    network = FixtureNetwork(video_path.read_bytes())
    with TestClient(create_app(settings, import_client_factory=network.factory)) as client:
        job, _ = wait(client, client.post('/api/imports/douyin', json={'text': NORMAL_URL[:-3] + suffix}).json(), 'failed')
        assert job['error_code'] == code and 'MP4' in job['error']
        assert not client.get('/api/videos').json()
        assert not list(settings.media_dir.iterdir())


def test_retry_cancel_unknown_length_limits(settings, video_path):
    network = FixtureNetwork(video_path.read_bytes(), media_length=False, delay=.03)
    attempts = []
    def response():
        attempts.append(1)
        return RawResponse(b'', 503) if len(attempts) < 3 else RawResponse(network.media)
    network.replies[('media.douyinvod.com', '/video.mp4')] = response
    with TestClient(create_app(settings, import_client_factory=network.factory)) as client:
        job, _ = wait(client, client.post('/api/imports/douyin', json={'text': NORMAL_URL}).json())
        assert job['attempt'] == 3 and job['total_bytes'] is None
        current = client.post('/api/imports/douyin', json={'text': NORMAL_URL[:-3] + '997'}).json()
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline:
            if client.get(f"/api/imports/{current['id']}").json()['status'] == 'downloading': break
            time.sleep(.02)
        cancelled = client.post(f"/api/imports/{current['id']}/cancel").json()
        assert cancelled['status'] == 'cancelled'
        time.sleep(.7)
        assert client.get(f"/api/imports/{current['id']}").json()['status'] == 'cancelled'
        assert len(client.get('/api/videos').json()) == 1
    assert not list((settings.data_dir / 'downloads').iterdir())
    with TestClient(create_app(replace(settings, max_download_bytes=100), import_client_factory=network.factory)) as client:
        job, _ = wait(client, client.post('/api/imports/douyin', json={'text': NORMAL_URL[:-3] + '996'}).json(), 'failed')
        assert job['error_code'] == 'size_limit'


@pytest.mark.parametrize('body,length,code', [(b'not media', None, 'invalid_media'), (b'x', 100, 'incomplete_download')])
def test_bad_media_cleanup(settings, body, length, code):
    network = FixtureNetwork(body)
    network.replies[('media.douyinvod.com', '/video.mp4')] = (body, 200, {'Content-Length': str(length)} if length else {})
    with TestClient(create_app(settings, import_client_factory=network.factory)) as client:
        job, _ = wait(client, client.post('/api/imports/douyin', json={'text': NORMAL_URL}).json(), 'failed')
        assert job['error_code'] == code
        assert not client.get('/api/videos').json()
    assert not list((settings.data_dir / 'downloads').iterdir())


def test_video_conversion_full_duration(settings, video_path, tmp_path):
    source = tmp_path / 'incompatible.mkv'
    subprocess.run(['ffmpeg', '-y', '-v', 'error', '-i', str(video_path), '-c:v', 'mpeg4', '-c:a', 'pcm_s16le', str(source)], check=True)
    path, conversion = prepare_media(source, settings, RequestContext(threading.Event(), 30), 8)
    metadata = probe_video(path, settings.ffprobe)
    assert conversion == 'transcode'
    assert metadata['video_codec'] == 'h264' and metadata['audio_codec'] == 'aac'
    assert metadata['duration'] == pytest.approx(8, abs=.1)
    with pytest.raises(ImportFailure, match='shorter'):
        prepare_media(source, settings, RequestContext(threading.Event(), 30), 100)


def test_all_job_states_and_confirmed_roi(settings, video_path, monkeypatch):
    network = FixtureNetwork(video_path.read_bytes())
    states = []
    original = Repository.save_import
    def record(repository, job):
        states.append(job.status)
        original(repository, job)
    monkeypatch.setattr(Repository, 'save_import', record)
    with TestClient(create_app(settings, import_client_factory=network.factory)) as client:
        worker = client.app.state.worker
        start = worker.start = Mock(return_value=Mock(job=Mock(id=UUID('00000000-0000-0000-0000-000000000001')), cached=True))
        job, _ = wait(client, client.post('/api/imports/douyin', json={'text': NORMAL_URL, 'analyze_after_import': True,
                     'processing_settings': {'roi': {'x': .05, 'y': .6, 'width': .9, 'height': .3}, 'sample_fps': 2}, 'roi_confirmed': True}).json())
        assert start.call_count == 1 and job['analysis_job_id']
        assert list(dict.fromkeys(states)) == ['pending', 'resolving', 'downloading', 'validating', 'importing', 'completed']
        # Auto-analysis itself is mocked here; browser tests exercise the real OCR path.


@pytest.mark.parametrize('stage', ['validating', 'importing'])
def test_cancel_before_publication_never_stores_video(settings, video_path, monkeypatch, stage):
    from app.services import douyin_import
    entered, release = threading.Event(), threading.Event()
    original = douyin_import.prepare_media if stage == 'validating' else douyin_import.import_video
    def paused(*args, **kwargs):
        entered.set()
        assert release.wait(10)
        return original(*args, **kwargs)
    monkeypatch.setattr(douyin_import, 'prepare_media' if stage == 'validating' else 'import_video', paused)
    network = FixtureNetwork(video_path.read_bytes())
    with TestClient(create_app(settings, import_client_factory=network.factory)) as client:
        job = client.post('/api/imports/douyin', json={'text': NORMAL_URL}).json()
        assert entered.wait(10)
        cancelled = client.post(f"/api/imports/{job['id']}/cancel").json()
        assert cancelled['status'] == 'cancelled'
        release.set()
    assert not list(settings.media_dir.iterdir())
    assert not list((settings.data_dir / 'downloads').iterdir())


def test_import_timeout_no_commit(settings, video_path):
    network = FixtureNetwork(video_path.read_bytes(), delay=.08)
    with TestClient(create_app(replace(settings, import_timeout_seconds=.1), import_client_factory=network.factory)) as client:
        job, _ = wait(client, client.post('/api/imports/douyin', json={'text': NORMAL_URL}).json(), 'failed')
        assert job['error_code'] == 'timeout'
        assert not client.get('/api/videos').json()


def test_truncated_packets_even_when_content_length_matches(settings, video_path):
    network = FixtureNetwork(video_path.read_bytes()[:video_path.stat().st_size // 2])
    with TestClient(create_app(settings, import_client_factory=network.factory)) as client:
        job, _ = wait(client, client.post('/api/imports/douyin', json={'text': NORMAL_URL}).json(), 'failed')
        assert job['error_code'] == 'incomplete_media', job
        assert not client.get('/api/videos').json()


def test_remux_preserves_h264_and_aac(settings, video_path, tmp_path):
    source = tmp_path / 'source.mkv'
    subprocess.run(['ffmpeg', '-y', '-v', 'error', '-i', str(video_path), '-c', 'copy', str(source)], check=True)
    path, conversion = prepare_media(source, settings, RequestContext(threading.Event(), 30), 8)
    assert conversion == 'remux'
    assert probe_video(path, settings.ffprobe)['duration'] == pytest.approx(8, abs=.1)


def test_mixed_dns_and_redirect_private_rejected_before_connection():
    from app.services.safe_http import SafeHTTPClient
    def mixed(*args, **kwargs):
        return [(socket.AF_INET, 1, 6, '', ('93.184.216.34', 443)), (socket.AF_INET, 1, 6, '', ('127.0.0.1', 443))]
    connection = Mock()
    with pytest.raises(ImportFailure, match='non-public'):
        SafeHTTPClient(RequestContext(threading.Event(), 10), connection, mixed).open(NORMAL_URL)
    connection.assert_not_called()
    network = FixtureNetwork(b'')
    network.replies[('v.douyin.com', '/Bad/')] = (b'', 302, {'Location': 'https://internal.douyin.com/'})
    client = network.factory(RequestContext(threading.Event(), 10))
    public_resolver = client.resolver
    client.resolver = lambda host, *args, **kw: mixed() if host == 'internal.douyin.com' else public_resolver(host)
    with pytest.raises(ImportFailure, match='non-public'): client.open('https://v.douyin.com/Bad/', role='page')
    assert len(network.calls) == 1


def test_restart_recovers_interrupted_job_and_cleans_only_owned_directory(settings):
    from datetime import datetime, timezone
    from uuid import uuid4
    from app.models.imports import ImportJob
    repo = Repository(settings.data_dir / 'library.sqlite3')
    repo.initialize()
    job = ImportJob(id=uuid4(), input_url=NORMAL_URL, created_at=datetime.now(timezone.utc), status='downloading')
    repo.save_import(job)
    owned = settings.data_dir / 'downloads' / str(job.id)
    owned.mkdir(parents=True)
    (owned / 'partial').write_bytes(b'x')
    unrelated = settings.data_dir / 'downloads' / 'keep-me.txt'
    unrelated.write_text('unrelated')
    with TestClient(create_app(settings)) as client:
        recovered = client.get(f'/api/imports/{job.id}').json()
        assert recovered['status'] == 'failed' and recovered['error_code'] == 'interrupted'
    assert not owned.exists() and unrelated.exists()


def test_json_request_bounds_and_origin(client):
    assert client.post('/api/imports/douyin', content=b'x' * 70000, headers={'Content-Type': 'application/json'}).status_code == 413
    assert client.post('/api/imports/douyin', json={'text': NORMAL_URL}, headers={'Origin': 'https://evil.test'}).status_code == 403
    assert client.post('/api/imports/douyin', json={'text': NORMAL_URL, 'cookies': 'secret'}).status_code == 422


def test_partial_http_response_is_never_imported(settings, video_path):
    network = FixtureNetwork(video_path.read_bytes())
    network.replies[('media.douyinvod.com', '/video.mp4')] = (network.media, 206, {'Content-Length': str(len(network.media))})
    with TestClient(create_app(settings, import_client_factory=network.factory)) as client:
        job, _ = wait(client, client.post('/api/imports/douyin', json={'text': NORMAL_URL}).json(), 'failed')
        assert job['error_code'] == 'incomplete_download'
        assert not client.get('/api/videos').json()


def test_dns_is_pinned_to_verified_tls_socket(monkeypatch):
    import ssl
    from app.services.safe_http import PinnedHTTPSConnection
    verified = [(socket.AF_INET, 1, 6, '', ('93.184.216.34', 443))]
    connection = PinnedHTTPSConnection('www.douyin.com', verified, 1)
    assert connection._context.check_hostname and connection._context.verify_mode == ssl.CERT_REQUIRED
    raw = Mock()
    monkeypatch.setattr(socket, 'socket', Mock(return_value=raw))
    # A second DNS lookup would now resolve privately; connecting must not perform one.
    resolve_again = Mock(return_value=[(socket.AF_INET, 1, 6, '', ('127.0.0.1', 443))])
    monkeypatch.setattr(socket, 'getaddrinfo', resolve_again)
    connection._context = Mock()
    connection.connect()
    resolve_again.assert_not_called()
    raw.connect.assert_called_once_with(('93.184.216.34', 443))
    connection._context.wrap_socket.assert_called_once_with(raw, server_hostname='www.douyin.com')


def test_metadata_must_match_requested_video(settings, video_path):
    import json
    network = FixtureNetwork(video_path.read_bytes())
    endpoint = f'/aweme/v1/web/aweme/detail/?aweme_id={VIDEO_ID}'
    payload = json.loads(network.response('www.douyin.com', endpoint).read())
    payload['aweme_detail']['aweme_id'] = '1111111111111111111'
    network.replies[('www.douyin.com', endpoint)] = (json.dumps(payload).encode(), 200, {})
    with TestClient(create_app(settings, import_client_factory=network.factory)) as client:
        job, _ = wait(client, client.post('/api/imports/douyin', json={'text': NORMAL_URL}).json(), 'failed')
        assert job['error_code'] == 'metadata_mismatch'
        assert not client.get('/api/videos').json()
