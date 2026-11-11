"""Consolidate sampled visual observations; these are not audio alignments."""
import re
import unicodedata
from collections import defaultdict
from difflib import SequenceMatcher
from uuid import uuid4

from app.models.schemas import SubtitleSegment
from app.services.pipeline import OCRObservation


def normalized(text: str) -> str:
    return re.sub(r"[\W_]+", "", unicodedata.normalize("NFKC", text), flags=re.UNICODE)


def same_subtitle(left: str, right: str) -> bool:
    a, b = normalized(left), normalized(right)
    if min(len(a), len(b)) < 4:
        return a == b
    return SequenceMatcher(None, a, b).ratio() >= 0.82


class SubtitleDetector:
    def __init__(self, sample_fps: float, duration: float):
        self.period = 1 / sample_fps
        self.duration = duration
        self.segments: list[SubtitleSegment] = []
        self.current: list[OCRObservation] = []
        self.uncertain_since: float | None = None

    def _close(self, end: float):
        if not self.current:
            return
        votes = defaultdict(float)
        for observation in self.current:
            votes[observation.text] += observation.confidence
        text = max(votes, key=votes.get)
        start = self.current[0].timestamp
        end = min(self.duration, max(start + 0.001, end))
        self.segments.append(SubtitleSegment(
            id=uuid4(), start_time=start, end_time=end, text=text,
            confidence=sum(o.confidence for o in self.current) / len(self.current),
            metadata={"observations": len(self.current), "timestamp_uncertainty": self.period,
                      "timing_source": "sampled_video_frames", "first_boxes_crop_pixels": self.current[0].boxes,
                      "original_ocr_text": text},
        ))
        self.current = []
        self.uncertain_since = None

    def observe(self, observation: OCRObservation):
        if not observation.text.strip():
            # A confirmed disappearance separates even identical later sentences.
            self._close(self.uncertain_since if self.uncertain_since is not None else observation.timestamp)
            return
        if observation.confidence < 0.60:
            if self.current:
                if self.uncertain_since is None:
                    self.uncertain_since = observation.timestamp
                if observation.timestamp - self.uncertain_since >= 0.60:
                    self._close(self.uncertain_since)
            return
        if self.current:
            recent = max(self.current[-3:], key=lambda o: o.confidence)
            confident_change = (normalized(recent.text) != normalized(observation.text)
                                and len(normalized(recent.text)) == len(normalized(observation.text))
                                and recent.confidence >= 0.95 and observation.confidence >= 0.95)
            if confident_change or not same_subtitle(recent.text, observation.text) or observation.timestamp - self.current[-1].timestamp > self.period + 0.60:
                self._close(self.uncertain_since if self.uncertain_since is not None else observation.timestamp)
        self.current.append(observation)
        self.uncertain_since = None

    def finish(self) -> list[SubtitleSegment]:
        if self.current:
            self._close(self.uncertain_since if self.uncertain_since is not None else self.current[-1].timestamp + self.period)
        return self.segments
