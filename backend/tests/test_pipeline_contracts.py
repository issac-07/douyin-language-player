import pytest
from pydantic import ValidationError

from app.models.schemas import ProcessingSettings, ROI
from app.services.pipeline import analysis_cache_key


@pytest.mark.parametrize("values", [{"x": 0.8, "width": 0.9}, {"y": -0.1}, {"height": 0}, {"width": float("nan")}])
def test_roi_rejects_invalid_bounds(values):
    with pytest.raises(ValidationError):
        ROI(**values)


def test_cache_key_accounts_for_content_settings_and_model():
    settings = ProcessingSettings()
    baseline = analysis_cache_key("hash-a", settings, "engine-v1")
    assert baseline == analysis_cache_key("hash-a", ProcessingSettings(), "engine-v1")
    assert baseline == analysis_cache_key("hash-a", ProcessingSettings.model_validate_json(settings.model_dump_json()), "engine-v1")
    assert baseline != analysis_cache_key("hash-b", settings, "engine-v1")
    assert baseline != analysis_cache_key("hash-a", settings, "engine-v2")
    assert baseline != analysis_cache_key("hash-a", ProcessingSettings(sample_fps=3), "engine-v1")
    assert baseline != analysis_cache_key("hash-a", ProcessingSettings(roi=ROI(y=0.5)), "engine-v1")


def test_processing_settings_persist_and_validate(client, imported, settings):
    from fastapi.testclient import TestClient
    from app.main import create_app

    url = f"/api/videos/{imported['id']}/processing-settings"
    assert client.get(url).json()["sample_fps"] == 2
    value = {"sample_fps": 3, "roi": {"x": 0, "y": 0.5, "width": 1, "height": 0.4}}
    assert client.put(url, json=value).status_code == 200
    with TestClient(create_app(settings)) as restarted:
        assert restarted.get(url).json() == value
    assert client.put(url, json={**value, "sample_fps": 0}).status_code == 422
    assert client.put(url, json={**value, "roi": {**value["roi"], "width": 1.5}}).status_code == 422
    assert client.get(url).json() == value
