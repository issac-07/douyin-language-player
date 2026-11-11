"""Seek to requested samples and preserve decoder timestamps, not wall-clock time."""
import math
from pathlib import Path
from typing import Iterator

import cv2
import numpy as np

from app.models.schemas import ProcessingSettings, ROI
from app.services.pipeline import FrameSample


def crop_bounds(roi: ROI, width: int, height: int) -> tuple[int, int, int, int]:
    x1, y1 = int(roi.x * width), int(roi.y * height)
    x2 = min(width, math.ceil((roi.x + roi.width) * width))
    y2 = min(height, math.ceil((roi.y + roi.height) * height))
    return x1, y1, max(x1 + 1, x2), max(y1 + 1, y2)


def crop_frame(image: np.ndarray, roi: ROI) -> np.ndarray:
    height, width = image.shape[:2]
    x1, y1, x2, y2 = crop_bounds(roi, width, height)
    return np.ascontiguousarray(image[y1:y2, x1:x2])


def read_frame(path: str | Path, timestamp: float) -> FrameSample:
    capture = cv2.VideoCapture(str(path), cv2.CAP_FFMPEG)
    try:
        if not capture.isOpened():
            raise ValueError("OpenCV could not open this video. Convert a copy to H.264/AAC and reimport it.")
        capture.set(cv2.CAP_PROP_ORIENTATION_AUTO, 1)
        capture.set(cv2.CAP_PROP_POS_MSEC, timestamp * 1000)
        ok, image = capture.read()
        if not ok:
            raise ValueError("Could not decode a preview at this timestamp. Choose an earlier frame.")
        actual = capture.get(cv2.CAP_PROP_POS_MSEC) / 1000
        if not math.isfinite(actual) or actual < 0 or (timestamp > 0.1 and actual == 0):
            raise ValueError("The decoder did not provide usable timestamps. Remux this video with FFmpeg.")
        return FrameSample(actual, image)
    finally:
        capture.release()


class OpenCVFrameSource:
    def __init__(self, duration: float | None = None):
        self.duration = duration

    def samples(self, path: str, settings: ProcessingSettings) -> Iterator[FrameSample]:
        capture = cv2.VideoCapture(path, cv2.CAP_FFMPEG)
        try:
            if not capture.isOpened():
                raise ValueError("OpenCV could not decode this video. Convert a copy to H.264/AAC.")
            capture.set(cv2.CAP_PROP_ORIENTATION_AUTO, 1)
            fps, count = capture.get(cv2.CAP_PROP_FPS), capture.get(cv2.CAP_PROP_FRAME_COUNT)
            if fps <= 0 or count <= 0:
                raise ValueError("The video does not expose a usable frame rate or duration.")
            duration = self.duration if self.duration is not None else count / fps
            previous = -1.0
            for index in range(math.ceil(duration * settings.sample_fps)):
                requested = index / settings.sample_fps
                capture.set(cv2.CAP_PROP_POS_MSEC, requested * 1000)
                ok, image = capture.read()
                if not ok:
                    if requested >= duration - 1 / fps:
                        break
                    raise ValueError(f"Frame decoding failed near {requested:.2f}s. Repair or convert the MP4 before retrying.")
                timestamp = capture.get(cv2.CAP_PROP_POS_MSEC) / 1000
                if not math.isfinite(timestamp) or timestamp < 0 or (requested > 0.1 and timestamp == 0):
                    raise ValueError("Decoder timestamps are unavailable; remux the video with FFmpeg before analyzing.")
                if timestamp <= previous:
                    continue  # Sample rates above the source FPS must not duplicate frames.
                previous = timestamp
                yield FrameSample(timestamp, crop_frame(image, settings.roi))
        finally:
            capture.release()
