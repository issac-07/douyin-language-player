from pathlib import Path
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app
from scripts.generate_test_video import generate


def pytest_configure(config):
    # Sandboxed and normal Windows processes can have different temp-folder ACLs.
    # A fresh project-local directory avoids reusing another identity's pytest temp.
    if not config.option.basetemp:
        root = Path(__file__).resolve().parents[2]
        parent = root / "data" / "tests"
        parent.mkdir(parents=True, exist_ok=True)
        config.option.basetemp = str(parent / f"run-{uuid4().hex}")


@pytest.fixture(scope="session")
def video_path(tmp_path_factory) -> Path:
    return generate(tmp_path_factory.mktemp("fixtures") / "test.mp4")


@pytest.fixture
def settings(tmp_path) -> Settings:
    return Settings(data_dir=tmp_path, max_upload_bytes=4 * 1024 * 1024)


@pytest.fixture
def client(settings):
    with TestClient(create_app(settings)) as connection:
        yield connection


@pytest.fixture
def imported(client, video_path):
    with video_path.open("rb") as source:
        result = client.post("/api/videos", files={"file": ("中文.mp4", source, "video/mp4")})
    assert result.status_code == 201, result.text
    return result.json()["video"]
