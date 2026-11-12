import socket
import threading
from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient
from app.main import create_app
from app.services.browser_proxy import PublicBrowserProxy
from app.services.douyin_urls import ImportCancelled, ImportFailure
from app.services.public_edge_extractor import PublicEdgeExtractor
from app.services.safe_http import RequestContext
from .douyin_fixture import FixtureNetwork, NORMAL_URL
from .test_douyin_import import wait


@pytest.mark.parametrize('target', ['127.0.0.1:443', 'localhost:443', '[::1]:443', 'www.douyin.com.evil.test:443',
    'www.douyin.com:80', 'user:pass@www.douyin.com:443', 'www.douyin.com:443/path', 'www.douyin.com:443?x=y'])
def test_browser_proxy_rejects_destinations_before_dns(target):
    proxy = PublicBrowserProxy(RequestContext(threading.Event(), 10))
    proxy.client._resolve = Mock()
    try:
        with pytest.raises((ValueError, ImportFailure)): proxy.destination(target)
        proxy.client._resolve.assert_not_called()
    finally: proxy.server.server_close()


def test_browser_proxy_pins_and_caches_public_addresses():
    proxy = PublicBrowserProxy(RequestContext(threading.Event(), 10))
    addresses = [(socket.AF_INET, 1, 6, '', ('93.184.216.34', 443))]
    proxy.client._resolve = Mock(return_value=addresses)
    try:
        assert proxy.destination('www.douyin.com:443') == ('www.douyin.com', addresses)
        assert proxy.destination('www.douyin.com:443')[1] == addresses
        assert proxy.client._resolve.call_count == 1
    finally: proxy.server.server_close()


def test_browser_proxy_rejects_private_dns_and_plain_http():
    context = RequestContext(threading.Event(), 10)
    with PublicBrowserProxy(context) as proxy:
        proxy.client.resolver = lambda *_a, **_k: [(socket.AF_INET, 1, 6, '', ('127.0.0.1', 443))]
        with pytest.raises(ImportFailure, match='non-public'): proxy.destination('www.douyin.com:443')
        with socket.create_connection(proxy.server.server_address, timeout=2) as connection:
            connection.sendall(b'GET http://127.0.0.1/private HTTP/1.1\r\nHost: localhost\r\n\r\n')
            assert not connection.recv(1024)


def test_public_page_cancelled_before_browser_start():
    event = threading.Event(); event.set()
    with pytest.raises(ImportCancelled):
        PublicEdgeExtractor().extract(NORMAL_URL, Mock(context=RequestContext(event, 10)))


def test_public_page_is_explicit_per_request(settings, video_path, monkeypatch):
    from app.services import douyin_import
    from app.services.douyin_extractor import YtDlpExtractor
    network = FixtureNetwork(video_path.read_bytes())
    called = []
    class FixturePublicPage:
        def __init__(self, node): pass
        def extract(self, url, client):
            called.append(url)
            return YtDlpExtractor().extract(url, client)
    monkeypatch.setattr(douyin_import, 'PublicEdgeExtractor', FixturePublicPage)
    with TestClient(create_app(settings, import_client_factory=network.factory)) as client:
        direct, _ = wait(client, client.post('/api/imports/douyin', json={'text': NORMAL_URL}).json())
        assert not called and direct['extraction_method'] == 'direct'
        # Use a distinct source to bypass source-cache reuse for this dispatch test.
        url = NORMAL_URL[:-3] + '777'
        public, _ = wait(client, client.post('/api/imports/douyin', json={'text': url, 'use_public_page': True}).json())
        assert called == [url] and public['extraction_method'] == 'public_page'
