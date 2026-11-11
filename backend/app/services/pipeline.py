"""Reusable OCR boundaries, independent of the web API and frontend."""
import hashlib
import json
from dataclasses import dataclass
from typing import Iterable, Protocol

from app.models.schemas import ProcessingSettings


@dataclass(frozen=True)
class FrameSample:
    timestamp: float  # Actual media timestamp, in seconds.
    image: object  # BGR OpenCV ndarray; keep transport/protocol independent of the UI.


@dataclass(frozen=True)
class OCRObservation:
    timestamp: float
    text: str
    confidence: float
    boxes: tuple[tuple[float, ...], ...] = ()
    inference_seconds: float = 0
    calls: int = 0


class FrameSource(Protocol):
    def samples(self, path: str, settings: ProcessingSettings) -> Iterable[FrameSample]: ...


class OCREngine(Protocol):
    @property
    def version(self) -> str: ...

    def recognize(self, sample: FrameSample) -> OCRObservation: ...


def analysis_cache_key(video_sha256: str, settings: ProcessingSettings, engine_version: str) -> str:
    payload = {"schema": 2, "video": video_sha256, "settings": settings.model_dump(), "engine": engine_version}
    return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
