"""Compare two previously documented, visually reviewable real-video captions.

Writes only isolated validation outputs; does not open the application database.
"""
import json
import sys
from pathlib import Path
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'backend'))
sys.path.insert(0, str(ROOT / 'scripts'))
import cv2
from benchmark_ocr import load_reference
from app.models.schemas import ROI
from app.services.ocr_engine import RapidOCREngine
from app.services.pipeline import FrameSample
from app.services.subtitle_detection import normalized
from app.services.video_frames import crop_frame, read_frame


def distance(left, right):
    row = list(range(len(right) + 1))
    for index, char in enumerate(left, 1):
        next_row = [index]
        for offset, other in enumerate(right, 1):
            next_row.append(min(next_row[-1] + 1, row[offset] + 1, row[offset-1] + (char != other)))
        row = next_row
    return row[-1]


if __name__ == '__main__':
    destination = ROOT / 'data' / 'ocr-bench' / 'quality'
    destination.mkdir(parents=True, exist_ok=True)
    original = load_reference(destination, 'ocr_engine').RapidOCREngine()
    optimized = RapidOCREngine(threads=4)
    path = ROOT / 'data/media/3c7e8121-18c8-4987-b848-b8cd2bd3dd3f.mp4'
    result = []
    for timestamp, expected in [(0.5, '妈妈说我注定会成为哥哥的妻子'), (120, '老登你给我接电话')]:
        frame = read_frame(path, timestamp)
        image = crop_frame(frame.image, ROI(x=.10, y=.87, width=.80, height=.12))
        cv2.imwrite(str(destination / f'caption-{timestamp:g}.png'), image)
        sample = FrameSample(frame.timestamp, image)
        baseline, candidate = original.recognize(sample), optimized.recognize(sample)
        result.append(dict(timestamp=frame.timestamp, expected=expected, original=baseline.text, optimized=candidate.text,
                           original_character_errors=distance(normalized(expected), normalized(baseline.text)),
                           optimized_character_errors=distance(normalized(expected), normalized(candidate.text))))
    (destination / 'manual-subset.json').write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(result, ensure_ascii=True))
