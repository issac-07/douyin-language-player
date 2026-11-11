"""Run the real production analysis API on a supplied video in an isolated library."""
import argparse
import json
import sys
import time
from pathlib import Path
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from fastapi.testclient import TestClient
from app.config import Settings
from app.main import create_app


def validate(path: Path, roi: dict, sample_fps: float = 2):
    destination = ROOT / "data" / "validation" / f"run-{uuid4().hex}"
    with TestClient(create_app(Settings(data_dir=destination))) as client:
        with path.open("rb") as source:
            response = client.post("/api/videos", files={"file": (path.name, source, "video/mp4")})
        response.raise_for_status()
        video = response.json()["video"]
        response = client.post(f"/api/videos/{video['id']}/analyses", json={"settings": {"roi": roi, "sample_fps": sample_fps}})
        response.raise_for_status()
        job = response.json()["job"]
        while job["status"] in ("pending", "processing"):
            time.sleep(0.5)
            job = client.get(f"/api/analysis-jobs/{job['id']}").json()
        document = client.get(f"/api/videos/{video['id']}/subtitles").json()
        report = {"source_name": path.name, "video": video, "job": job, "document": document}
        output = destination / "report.json"
        output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps({"report": str(output), "status": job["status"], "metrics": job["metrics"],
                          "segments": [{k: s[k] for k in ("start_time", "end_time", "text", "confidence")} for s in document["segments"]]}, ensure_ascii=True))
        if job["status"] != "completed":
            raise RuntimeError(job["error"])


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("video", type=Path)
    parser.add_argument("--roi", default="0.05,0.60,0.90,0.30", help="normalized x,y,width,height")
    parser.add_argument("--fps", type=float, default=2)
    args = parser.parse_args()
    validate(args.video.resolve(), dict(zip(("x", "y", "width", "height"), map(float, args.roi.split(",")), strict=True)), args.fps)
