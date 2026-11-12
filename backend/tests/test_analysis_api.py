import threading
import time
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from app.services.pipeline import OCRObservation


def wait_for_job(client, job_id, timeout=45):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        job = client.get(f"/api/analysis-jobs/{job_id}").json()
        if job["status"] not in ("pending", "processing"):
            return job
        time.sleep(.05)
    pytest.fail("OCR worker did not finish in the integration-test time limit")


def test_real_analysis_edit_cache_exports_and_restart(client, imported, settings):
    video_id = imported["id"]
    base = f"/api/videos/{video_id}"
    preview = client.get(base + "/preview?timestamp=1")
    assert preview.status_code == 200
    assert preview.headers["content-type"] == "image/jpeg"
    assert float(preview.headers["x-frame-timestamp"]) == pytest.approx(1)
    started = client.post(base + "/analyses", json={})
    assert started.status_code == 202, started.text
    job_id = started.json()["job"]["id"]
    job = wait_for_job(client, job_id)
    assert job["status"] == "completed", job
    assert job["metrics"]["frames_processed"] == 16
    assert job["metrics"]["unique_segments"] == 3
    document = client.get(base + "/subtitles").json()
    assert [s["text"] for s in document["segments"]] == ["今天我们一起去吃饭", "你在干什么？", "我不知道发生了什么"]
    assert [(s["start_time"], s["end_time"]) for s in document["segments"]] == [(.5, 2.5), (3, 5), (5.5, 7.5)]
    segment = document["segments"][0]
    patch = {"analysis_id": job_id, "revision": segment["revision"], "text": "今天我们一起去吃饭！", "start_time": .6, "end_time": 2.4}
    edited = client.patch(base + f"/subtitles/{segment['id']}", json=patch)
    assert edited.status_code == 200, edited.text
    assert edited.json()["segments"][0]["edited"] is True
    assert client.patch(base + f"/subtitles/{segment['id']}", json=patch).status_code == 409
    # Overlap, end beyond media and empty content must not corrupt the document.
    for changes in ({"end_time": 3.5}, {"end_time": 50}, {"text": "  "}, {"start_time": 3}):
        assert client.patch(base + f"/subtitles/{segment['id']}", json={**patch, "revision": 1, **changes}).status_code == 422
    cached = client.post(base + "/analyses", json={}).json()
    assert cached["cached"] is True and cached["job"]["id"] == job_id
    assert client.get(base + "/subtitles").json()["segments"][0]["text"] == patch["text"]
    exported = client.get(base + "/export?format=json")
    assert exported.json()["analysis"]["engine_version"]
    assert exported.json()["segments"][0]["metadata"]["original_ocr_text"]
    srt = client.get(base + "/export?format=srt")
    assert "00:00:00,600 --> 00:00:02,400" in srt.text
    assert patch["text"] in srt.text
    assert "attachment" in srt.headers["content-disposition"]
    with TestClient(create_app(settings)) as restarted:
        assert restarted.get(base + "/subtitles").json()["segments"] == edited.json()["segments"]
    last = document["segments"][-1]
    response = client.delete(base + f"/subtitles/{last['id']}?analysis_id={job_id}&revision=0")
    assert response.status_code == 200
    assert len(response.json()["segments"]) == 2
    cancelled = client.post(base + "/analyses", json={"force": True}).json()["job"]
    client.post(f"/api/analysis-jobs/{cancelled['id']}/cancel")
    assert wait_for_job(client, cancelled["id"])["status"] == "cancelled"
    assert len(client.get(base + "/subtitles").json()["segments"]) == 2


def test_cancellation_during_inference_cannot_publish_results(client, imported):
    entered, release = threading.Event(), threading.Event()

    class BlockingEngine:
        def recognize(self, sample):
            entered.set()
            release.wait(10)
            return OCRObservation(sample.timestamp, "不能保存", .99)

    client.app.state.worker.engine = BlockingEngine()
    base = f"/api/videos/{imported['id']}"
    try:
        result = client.post(base + "/analyses", json={}).json()
        assert entered.wait(5)
        conflict = client.post(base + "/analyses", json={"force": True})
        assert conflict.status_code == 409
        cancelled = client.post(f"/api/analysis-jobs/{result['job']['id']}/cancel").json()
        assert cancelled["status"] == "cancelled"
    finally:
        release.set()
    client.app.state.worker.pool.shutdown(wait=True)
    assert client.get(base + "/subtitles").json()["segments"] == []
    assert client.get(f"/api/analysis-jobs/{result['job']['id']}").json()["status"] == "cancelled"


def test_failure_and_invalid_inputs_are_actionable(client, imported):
    class BrokenEngine:
        def recognize(self, sample):
            raise RuntimeError("Test-only inference failure")

    client.app.state.worker.engine = BrokenEngine()
    base = f"/api/videos/{imported['id']}"
    job = client.post(base + "/analyses", json={}).json()["job"]
    result = wait_for_job(client, job["id"])
    assert result["status"] == "failed"
    assert "Test-only inference failure" in result["error"]
    assert client.get(base + "/subtitles").json()["analysis"] is None
    assert client.get(base + "/export").status_code == 404
    assert client.get(f"/api/analysis-jobs/{uuid4()}").status_code == 404
    assert client.post(f"/api/videos/{uuid4()}/analyses", json={}).status_code == 404
    assert client.post(base + "/analyses", json={"settings": {"roi": {"x": .9, "width": .9}}}).status_code == 422


def test_restart_marks_interrupted_job_failed(client, imported, settings):
    from datetime import datetime, timezone
    from app.models.schemas import AnalysisJob, ProcessingSettings

    job = AnalysisJob(id=uuid4(), video_id=UUID(imported["id"]), cache_key="test", engine_version="test", settings=ProcessingSettings(), created_at=datetime.now(timezone.utc), total_frames=16, timestamp_uncertainty=.5)
    client.app.state.repository.save_job(job)
    with TestClient(create_app(settings)) as restarted:
        response = restarted.get(f"/api/analysis-jobs/{job.id}").json()
        assert response["status"] == "failed"
        assert "stopped" in response["error"]


def test_v1_schema_migrates_without_losing_existing_media(client, imported, video_path, tmp_path):
    import json
    import shutil
    import sqlite3
    from app.config import Settings

    legacy = tmp_path / "phase1-library"
    media = legacy / "media"
    media.mkdir(parents=True)
    shutil.copyfile(video_path, media / f"{imported['id']}.mp4")
    with sqlite3.connect(legacy / "library.sqlite3") as db:
        db.executescript("CREATE TABLE videos (id TEXT PRIMARY KEY, sha256 TEXT NOT NULL UNIQUE, payload TEXT NOT NULL); CREATE TABLE processing_settings (video_id TEXT PRIMARY KEY REFERENCES videos(id), payload TEXT NOT NULL); PRAGMA user_version=1;")
        db.execute("INSERT INTO videos VALUES(?,?,?)", (imported["id"], imported["sha256"], json.dumps(imported)))
    with TestClient(create_app(Settings(data_dir=legacy))) as restarted:
        assert restarted.get(f"/api/videos/{imported['id']}").json() == imported
        assert restarted.get(imported["media_url"]).status_code == 200
        assert restarted.get(f"/api/videos/{imported['id']}/subtitles").json()["analysis"] is None
    with sqlite3.connect(legacy / "library.sqlite3") as db:
        assert db.execute("PRAGMA user_version").fetchone()[0] == 4
