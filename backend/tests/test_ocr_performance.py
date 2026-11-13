from dataclasses import replace
from pathlib import Path

import cv2
import numpy as np
import pytest
from PIL import Image, ImageDraw, ImageFont

from app.models.schemas import OCRPerformance, ProcessingSettings, ROI
from app.services.ocr_reuse import SubtitleReuse
from app.services.ocr_runtime import resolve_runtime
from app.services.pipeline import FrameSample, OCRObservation, analysis_cache_key
from app.services.video_frames import OpenCVFrameSource, SequentialFrameSource


def caption(text='我喜欢你', shift=0, background=25, blur=False):
    image = Image.new('RGB', (640, 180), (background, background, background))
    font = ImageFont.truetype('C:/Windows/Fonts/msyh.ttc', 36)
    draw = ImageDraw.Draw(image)
    for index, line in enumerate(text.split('\n')):
        draw.text((30 + shift, 10 + index * 65), line, font=font, fill='white', stroke_width=2, stroke_fill='black')
    result = cv2.cvtColor(np.array(image), cv2.COLOR_RGB2BGR)
    return cv2.GaussianBlur(result, (9, 9), 3) if blur else result


def observation(confidence=.99):
    return OCRObservation(0, '我喜欢你', confidence, ((25, 5, 190, 5, 190, 60, 25, 60),))


def test_runtime_policy_and_legacy_cache_compatibility():
    settings = ProcessingSettings()
    assert 'performance' not in settings.model_dump()
    legacy = resolve_runtime(settings)
    assert (legacy.backend, legacy.threads, legacy.decoder, legacy.reuse) == ('ort', 2, 'seek', 'accurate')
    balanced = resolve_runtime(ProcessingSettings(performance=OCRPerformance()))
    assert (balanced.backend, balanced.threads, balanced.decoder, balanced.reuse) == ('ort', 4, 'sequential', 'accurate')
    assert legacy.identity != balanced.identity
    assert analysis_cache_key('video', settings, legacy.identity) != analysis_cache_key('video', ProcessingSettings(performance=OCRPerformance()), balanced.identity)
    gpu = resolve_runtime(ProcessingSettings(performance=OCRPerformance(backend='intel-gpu')))
    assert gpu.backend == 'openvino-gpu'
    fast = resolve_runtime(ProcessingSettings(performance=OCRPerformance(mode='fast')))
    assert fast.reuse == 'fast'
    assert fast.identity != balanced.identity


@pytest.mark.parametrize('values', [{'backend': 'cuda'}, {'mode': 'unsafe'}, {'cpu_threads': 16}, {'cpu_runtime': 'remote'}])
def test_invalid_performance_settings_rejected(values):
    from pydantic import ValidationError
    with pytest.raises(ValidationError):
        OCRPerformance(**values)


def test_subtitle_strokes_allow_only_dark_background_changes_and_expire():
    reuse = SubtitleReuse()
    reuse.remember(caption(), observation())
    assert reuse.can_reuse(caption(background=65), .5)
    assert not reuse.can_reuse(caption(background=65), 2)
    assert not reuse.can_reuse(caption(), 0)
    assert not reuse.can_reuse(caption(), -.5)
    assert not reuse.can_reuse(np.zeros((20, 20, 3), np.uint8), .5)
    reuse.remember(caption(), observation(.8))
    assert not reuse.can_reuse(caption(), .5)


@pytest.mark.parametrize('text,shift,blur', [
    ('我喜欢他', 0, False), ('我不喜欢你', 0, False), ('我欢你', 0, False),
    ('', 0, False), ('我喜欢你\n今天一起吃饭', 0, False),
    ('我喜欢你', 25, False), ('我喜欢你', 3, False), ('我喜欢你', 0, True),
])
def test_reuse_rejects_character_negation_disappearance_lines_position_animation_blur(text, shift, blur):
    reuse = SubtitleReuse()
    reuse.remember(caption(), observation())
    assert not reuse.can_reuse(caption(text, shift=shift, blur=blur), .5)


def test_complex_moving_background_and_disappearance_reappearance():
    reuse = SubtitleReuse()
    reuse.remember(caption(), observation())
    image = caption()
    image[100:130, 350:420] = 255
    assert not reuse.can_reuse(image, .5)
    reuse.remember(caption(''), OCRObservation(.5, '', 0))
    assert not reuse.can_reuse(caption(), 1)


def test_sequential_decoding_matches_original_cfr_pixels_and_times(video_path):
    settings = ProcessingSettings()
    expected = list(OpenCVFrameSource(8).samples(str(video_path), settings))
    actual = list(SequentialFrameSource(8).samples(str(video_path), settings))
    assert len(expected) == len(actual) == 16
    for left, right in zip(expected, actual):
        assert left.timestamp == pytest.approx(right.timestamp, abs=1e-6)
        assert np.array_equal(left.image, right.image)
    source = SequentialFrameSource(8, lambda: True)
    assert list(source.samples(str(video_path), settings)) == []


def test_high_sample_rate_does_not_duplicate_sequential_frames(video_path):
    samples = list(SequentialFrameSource(1).samples(str(video_path), ProcessingSettings(sample_fps=10)))
    assert len({s.timestamp for s in samples}) == len(samples) == 10


def test_rotation_and_vfr_use_real_source_timestamps(video_path, tmp_path):
    import json
    import subprocess
    rotated = tmp_path / 'rotated.mp4'
    subprocess.run(['ffmpeg', '-v', 'error', '-y', '-i', str(video_path), '-c', 'copy',
                    '-metadata:s:v:0', 'rotate=90', str(rotated)], check=True, timeout=30)
    settings = ProcessingSettings()
    expected = list(OpenCVFrameSource(8).samples(str(rotated), settings))
    actual = list(SequentialFrameSource(8).samples(str(rotated), settings))
    assert len(expected) == len(actual) == 16
    for left, right in zip(expected, actual):
        assert left.timestamp == pytest.approx(right.timestamp)
        assert np.array_equal(left.image, right.image)
    assert actual[0].image.shape[1] > actual[0].image.shape[0]
    vfr = tmp_path / 'vfr.mp4'
    subprocess.run(['ffmpeg', '-v', 'error', '-y', '-i', str(video_path), '-vf',
                    r'select=not(mod(n\,5))+not(mod(n\,7))', '-fps_mode', 'vfr',
                    '-c:v', 'libx264', '-an', str(vfr)], check=True, timeout=45)
    metadata = json.loads(subprocess.check_output(['ffprobe', '-v', 'error', '-select_streams', 'v:0',
                          '-show_frames', '-show_entries', 'frame=best_effort_timestamp_time', '-of', 'json', str(vfr)]))
    pts = [float(frame['best_effort_timestamp_time']) for frame in metadata['frames']]
    samples = list(SequentialFrameSource(7.5).samples(str(vfr), settings))
    assert [s.timestamp for s in samples] == pytest.approx([next(t for t in pts if t + 1e-6 >= index / 2) for index in range(15)], abs=1e-5)


def test_cancellation_during_sequential_decoding(video_path):
    calls = 0
    def cancelled():
        nonlocal calls
        calls += 1
        return calls > 5
    samples = list(SequentialFrameSource(8, cancelled).samples(str(video_path), ProcessingSettings()))
    assert len(samples) == 1
    assert calls == 6


def test_real_model_reuse_quality_on_mandatory_edge_cases():
    """Actual PP-OCRv4 on generated Chinese frames, no mocked recognition."""
    from app.services.ocr_engine import RapidOCREngine
    engine = RapidOCREngine(threads=4)
    cases = [caption(), caption(background=65), caption('我喜欢他'), caption('我不喜欢你'),
             caption('我喜欢你'), caption(''), caption(), caption('我喜欢你\n今天一起吃饭'),
             caption(shift=25), caption(shift=3), caption(blur=True), caption(), caption('')]
    reuse = SubtitleReuse()
    previous = None
    avoided = 0
    for index, image in enumerate(cases):
        sample = FrameSample(index * .5, image)
        baseline = engine.recognize(sample)
        if reuse.can_reuse(image, sample.timestamp):
            assert previous is not None
            assert previous.text == baseline.text
            assert previous.confidence >= .95
            actual = replace(previous, timestamp=sample.timestamp)
            avoided += 1
        else:
            actual = baseline
            reuse.remember(image, actual)
        assert actual.timestamp == sample.timestamp
        previous = actual
    assert avoided >= 1


def test_gpu_unavailable_is_an_error_not_a_cpu_fallback(monkeypatch):
    import sys
    from types import SimpleNamespace
    from app.services.openvino_backend import replace_sessions
    monkeypatch.setitem(sys.modules, 'openvino', SimpleNamespace(Core=lambda: SimpleNamespace(available_devices=['CPU'])))
    with pytest.raises(RuntimeError, match='GPU is unavailable'):
        replace_sessions(SimpleNamespace(), 'openvino-gpu', 4)


def test_backend_rejects_wrong_execution_device():
    from app.services.openvino_backend import OpenVINOSession
    class WrongDevice:
        def read_model(self, model):
            return None
        def compile_model(self, *args):
            from types import SimpleNamespace
            return SimpleNamespace(get_property=lambda name: ['CPU'])
    # Only meaningful in the optional environment; normal CPU-only tests remain valid.
    pytest.importorskip('openvino')
    with pytest.raises(RuntimeError, match='No silent device fallback'):
        OpenVINOSession(WrongDevice(), Path('unused.onnx'), 'GPU', 4)


def test_balanced_api_actual_device_cache_and_legacy_transcript_preserved(client, imported):
    from backend.tests.test_analysis_api import wait_for_job
    base = f"/api/videos/{imported['id']}"
    first = client.post(base + '/analyses', json={'settings': ProcessingSettings().model_dump()}).json()['job']
    assert wait_for_job(client, first['id'])['status'] == 'completed'
    original = client.get(base + '/subtitles').json()
    performance = ProcessingSettings(performance=OCRPerformance()).model_dump()
    started = client.post(base + '/analyses', json={'settings': performance}).json()
    assert not started['cached']
    balanced = wait_for_job(client, started['job']['id'])
    assert balanced['status'] == 'completed', balanced
    assert balanced['execution']['actual_backend'] == 'ort'
    assert balanced['execution']['decoder'] == 'sequential'
    assert balanced['execution']['threads'] == 4
    assert balanced['execution']['fallback'] is False
    assert balanced['metrics']['frames_processed'] == 16
    assert balanced['metrics']['decode_seconds'] > 0
    current = client.get(base + '/subtitles').json()
    assert [(s['text'], s['start_time'], s['end_time']) for s in current['segments']] == [(s['text'], s['start_time'], s['end_time']) for s in original['segments']]
    cached = client.post(base + '/analyses', json={'settings': performance}).json()
    assert cached['cached'] and cached['job']['id'] == balanced['id']
    restored = client.post(base + '/analyses', json={'settings': ProcessingSettings().model_dump()}).json()
    assert restored['cached'] and restored['job']['id'] == first['id']
    assert client.get(base + '/subtitles').json()['segments'] == original['segments']
