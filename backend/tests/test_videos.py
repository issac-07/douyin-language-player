from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app


def test_real_mp4_metadata_and_deduplication(client, imported, video_path, settings):
    assert imported["duration"] == pytest.approx(8, abs=0.15)
    assert (imported["width"], imported["height"]) == (360, 640)
    assert imported["fps"] == pytest.approx(24)
    assert imported["video_codec"] == "h264"
    assert imported["audio_codec"] == "aac"
    assert imported["original_name"] == "中文.mp4"
    assert imported["codec_warning"] is None
    with video_path.open("rb") as source:
        duplicate = client.post("/api/videos", files={"file": ("again.mp4", source)})
    assert duplicate.status_code == 201
    assert duplicate.json()["reused"] is True
    assert duplicate.json()["video"]["id"] == imported["id"]
    assert len(client.get("/api/videos").json()) == 1
    assert len(list(settings.media_dir.glob("*.mp4"))) == 1
    assert not list(settings.media_dir.glob("*.upload"))


def test_range_playback_and_head(client, imported, video_path):
    url = imported["media_url"]
    original = video_path.read_bytes()
    response = client.get(url, headers={"Range": "bytes=100-199"})
    assert response.status_code == 206
    assert response.content == original[100:200]
    assert response.headers["content-range"] == f"bytes 100-199/{len(original)}"
    assert response.headers["accept-ranges"] == "bytes"
    assert client.get(url, headers={"Range": "bytes=-20"}).content == original[-20:]
    assert client.get(url, headers={"Range": f"bytes={len(original) + 1}-"}).status_code == 416
    assert client.get(url).content == original
    head = client.head(url)
    assert head.status_code == 200
    assert head.content == b""
    assert int(head.headers["content-length"]) == len(original)


@pytest.mark.parametrize("name,content,status", [
    ("movie.avi", b"anything", 415),
    ("empty.mp4", b"", 422),
    ("renamed.mp4", b"this is not a video", 422),
    ("broken.mp4", b"\x00\x00\x00\x18ftypisom" + b"\x00" * 50, 422),
])
def test_invalid_import_cleans_up(client, settings, name, content, status):
    response = client.post("/api/videos", files={"file": (name, content)})
    assert response.status_code == status
    assert client.get("/api/videos").json() == []
    assert list(settings.media_dir.iterdir()) == []


def test_filename_traversal_is_not_used_as_path(client, video_path, settings):
    with video_path.open("rb") as source:
        response = client.post("/api/videos", files={"file": ("../../unsafe.mp4", source)})
    assert response.status_code == 201
    video = response.json()["video"]
    assert video["original_name"] == "unsafe.mp4"
    assert (settings.media_dir / f"{video['id']}.mp4").is_file()
    assert not (settings.data_dir / "unsafe.mp4").exists()


def test_body_size_limit_before_multipart_spooling(tmp_path):
    with TestClient(create_app(Settings(data_dir=tmp_path, max_upload_bytes=10))) as client:
        response = client.post("/api/videos", files={"file": ("large.mp4", b"x" * 70000)})
        assert response.status_code == 413
        assert list((tmp_path / "media").iterdir()) == []


def test_exact_file_limit_even_within_multipart_allowance(tmp_path, video_path):
    with TestClient(create_app(Settings(data_dir=tmp_path, max_upload_bytes=100))) as client:
        with video_path.open("rb") as source:
            response = client.post("/api/videos", files={"file": ("large.mp4", source)})
        assert response.status_code == 413
        assert list((tmp_path / "media").iterdir()) == []


def test_chunked_request_limit_without_content_length(tmp_path):
    with TestClient(create_app(Settings(data_dir=tmp_path, max_upload_bytes=10))) as client:
        chunks = iter([
            b'--boundary\r\nContent-Disposition: form-data; name="file"; filename="large.mp4"\r\nContent-Type: video/mp4\r\n\r\n',
            b"x" * 70000,
            b"\r\n--boundary--\r\n",
        ])
        response = client.post("/api/videos", headers={"Content-Type": "multipart/form-data; boundary=boundary"}, content=chunks)
        assert response.status_code == 413
        assert list((tmp_path / "media").iterdir()) == []


def test_metadata_persists_across_app_restart(client, imported, settings):
    with TestClient(create_app(settings)) as restarted:
        assert restarted.get(f"/api/videos/{imported['id']}").json() == imported
        assert restarted.get(imported["media_url"], headers={"Range": "bytes=0-9"}).status_code == 206


def test_missing_media_can_be_restored(client, imported, settings, video_path):
    (settings.media_dir / f"{imported['id']}.mp4").unlink()
    assert client.get(imported["media_url"]).status_code == 410
    with video_path.open("rb") as source:
        restored = client.post("/api/videos", files={"file": ("restore.mp4", source)})
    assert restored.status_code == 201
    assert restored.json()["video"]["id"] == imported["id"]
    assert client.get(imported["media_url"]).status_code == 200


def test_unknown_and_invalid_ids(client):
    assert client.get(f"/api/videos/{uuid4()}").status_code == 404
    assert client.get("/api/videos/not-a-uuid/media").status_code == 422


def test_missing_ffprobe_is_actionable(tmp_path, video_path):
    with TestClient(create_app(Settings(data_dir=tmp_path, ffprobe="not-a-real-ffprobe-executable"))) as client:
        assert client.get("/api/health").json()["ffprobe_available"] is False
        with video_path.open("rb") as source:
            response = client.post("/api/videos", files={"file": ("test.mp4", source)})
        assert response.status_code == 503
        assert "FFprobe" in response.json()["detail"]
        assert list((tmp_path / "media").iterdir()) == []


def test_reject_untrusted_browser_origin_and_host(client):
    assert client.post("/api/videos", headers={"Origin": "https://untrusted.example"}).status_code == 403
    assert client.get("/api/health", headers={"Host": "untrusted.example"}).status_code == 400
