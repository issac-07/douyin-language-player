from pathlib import Path

import cv2
import numpy as np
import pytest
from PIL import Image, ImageDraw, ImageFont

from app.models.schemas import ProcessingSettings, ROI
from app.services.ocr_engine import RapidOCREngine
from app.services.pipeline import FrameSample
from app.services.subtitle_detection import normalized
from app.services.video_frames import OpenCVFrameSource, crop_bounds, crop_frame, read_frame


@pytest.fixture(scope="session")
def real_engine():
    return RapidOCREngine()


def test_frame_sampling_preserves_actual_timestamps_and_crops(video_path):
    settings = ProcessingSettings()
    samples = list(OpenCVFrameSource(8).samples(str(video_path), settings))
    assert len(samples) == 16
    assert [s.timestamp for s in samples] == pytest.approx([i / 2 for i in range(16)], abs=1 / 24)
    assert samples[0].image.shape[:2] == (192, 324)
    original = read_frame(video_path, 1)
    assert original.timestamp == pytest.approx(1, abs=1 / 24)
    assert np.array_equal(crop_frame(original.image, settings.roi), samples[2].image)


def test_normalized_crop_bounds_include_edges():
    assert crop_bounds(ROI(x=0, y=0, width=1, height=1), 360, 640) == (0, 0, 360, 640)
    assert crop_bounds(ROI(x=.1, y=.5, width=.8, height=.4), 1920, 1080) == (192, 540, 1728, 972)


@pytest.mark.parametrize("timestamp,expected", [(1, "今天我们一起去吃饭"), (4, "你在干什么"), (6, "我不知道发生了什么")])
def test_real_chinese_ocr_from_decoded_video(real_engine, video_path, timestamp, expected):
    sample = read_frame(video_path, timestamp)
    result = real_engine.recognize(FrameSample(sample.timestamp, crop_frame(sample.image, ROI())))
    assert normalized(expected) in normalized(result.text)
    assert result.timestamp == pytest.approx(timestamp, abs=1 / 24)
    assert result.confidence > .75
    assert result.boxes
    assert result.inference_seconds > 0


def test_real_ocr_blank_image(real_engine):
    result = real_engine.recognize(FrameSample(0, np.zeros((120, 640, 3), dtype=np.uint8)))
    assert result.text == ""
    assert result.confidence == 0


def test_real_multiline_and_mixed_numbers(real_engine):
    font_path = Path("C:/Windows/Fonts/msyh.ttc")
    if not font_path.is_file():
        pytest.skip("The Windows Chinese fixture font is not installed.")
    image = Image.new("RGB", (640, 180), "black")
    draw = ImageDraw.Draw(image)
    font = ImageFont.truetype(str(font_path), 36)
    draw.text((30, 15), "今天我们一起去吃饭", font=font, fill="white")
    draw.text((30, 90), "现在是2026年", font=font, fill="white")
    result = real_engine.recognize(FrameSample(2, cv2.cvtColor(np.array(image), cv2.COLOR_RGB2BGR)))
    assert "今天我们一起去吃饭" in result.text
    assert "现在是2026年" in result.text
    assert "\n" in result.text
