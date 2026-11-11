"""Real, offline Chinese PP-OCRv4 through RapidOCR's bundled ONNX models."""
import hashlib
import importlib.metadata
import importlib.util
import re
from pathlib import Path
from time import perf_counter

import cv2
import numpy as np

from app.services.pipeline import FrameSample, OCRObservation

CHINESE = re.compile(r"[\u3400-\u9fff]")
PIPELINE_VERSION = "subtitle-v2.4:confident-replacements:chinese-lines:raw-clahe:conf=.60:similarity=.82:uncertain-gap=.60"


def engine_identity() -> str:
    spec = importlib.util.find_spec("rapidocr_onnxruntime")
    if not spec or not spec.origin:
        raise RuntimeError("RapidOCR is missing. Install backend/requirements-dev.lock.txt with the project Python.")
    package = Path(spec.origin).parent
    digest = hashlib.sha256()
    for name in ("config.yaml", "models/ch_PP-OCRv4_det_infer.onnx", "models/ch_PP-OCRv4_rec_infer.onnx", "models/ch_ppocr_mobile_v2.0_cls_infer.onnx"):
        path = package / name
        if not path.is_file():
            raise RuntimeError("RapidOCR's bundled models are missing. Reinstall rapidocr-onnxruntime==1.4.4.")
        with path.open("rb") as source:
            while chunk := source.read(1024 * 1024):
                digest.update(chunk)
    return f"rapidocr-{importlib.metadata.version('rapidocr-onnxruntime')}:onnx-{importlib.metadata.version('onnxruntime')}:cv-{cv2.__version__}:{digest.hexdigest()}:{PIPELINE_VERSION}"


class RapidOCREngine:
    def __init__(self):
        from rapidocr_onnxruntime import RapidOCR

        self.version = engine_identity()
        # Restrict native threads so a normal laptop can keep playing video.
        self.engine = RapidOCR(intra_op_num_threads=2, inter_op_num_threads=1, use_cls=False, text_score=0.3,
                               det_limit_side_len=736, det_limit_type="max")

    def recognize(self, sample: FrameSample) -> OCRObservation:
        image = sample.image
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        if float(gray.std()) < 1.5:
            return OCRObservation(sample.timestamp, "", 0)
        scale = min(2.0, max(1.0, 64 / image.shape[0]))
        scale = min(scale, 1600 / max(image.shape[:2]))
        resized = cv2.resize(image, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC) if scale != 1 else image
        started = perf_counter()
        calls = 1

        def run(source):
            padded = cv2.copyMakeBorder(source, 16, 16, 16, 16, cv2.BORDER_REPLICATE)
            result, _ = self.engine(padded, use_cls=False)
            rows = [(np.array(box, dtype=float), text.strip(), float(score)) for box, text, score in (result or []) if text.strip() and score >= 0.3]
            if not any(CHINESE.search(text) for _, text, _ in rows):
                return [], 0.0
            # Group by text-line center, then order each line from left to right.
            rows.sort(key=lambda row: float(row[0][:, 1].mean()))
            lines = []
            for row in rows:
                cy = float(row[0][:, 1].mean())
                height = max(1, float(np.ptp(row[0][:, 1])))
                if lines and abs(cy - lines[-1][0]) < height * 0.55:
                    lines[-1][1].append(row)
                else:
                    lines.append((cy, [row]))
            # Ignore isolated Latin/numeric background noise while retaining numbers
            # and punctuation within Chinese subtitle lines.
            lines = [(cy, line) for cy, line in lines if any(CHINESE.search(row[1]) for row in line)]
            ordered = []
            for _, line in lines:
                line.sort(key=lambda row: float(row[0][:, 0].min()))
                ordered.extend(line)
            confidence = sum(score * len(text) for _, text, score in ordered) / max(1, sum(len(text) for _, text, _ in ordered))
            return lines, confidence

        lines, confidence = run(resized)
        if confidence < 0.70:
            calls += 1
            enhanced = cv2.createCLAHE(clipLimit=2, tileGridSize=(8, 8)).apply(cv2.cvtColor(resized, cv2.COLOR_BGR2GRAY))
            fallback, fallback_confidence = run(cv2.cvtColor(enhanced, cv2.COLOR_GRAY2BGR))
            if fallback_confidence > confidence:
                lines, confidence = fallback, fallback_confidence
        text = "\n".join("".join(row[1] for row in line) for _, line in lines)
        boxes = tuple(tuple(float(v) for v in ((box - 16) / scale).clip(min=0).flatten()) for _, line in lines for box, _, _ in line)
        return OCRObservation(sample.timestamp, text, min(1, max(0, confidence)), boxes,
                              perf_counter() - started, calls)
