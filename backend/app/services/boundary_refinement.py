"""Confirm caption starts with two adjacent decoded frames; never guess offsets."""
import cv2
import numpy as np
from dataclasses import replace
from time import perf_counter
from app.services.pipeline import FrameSample
from app.services.subtitle_detection import normalized
from app.services.video_frames import crop_frame


def refine_starts(path, segments, settings, engine, cancelled, metrics, on_progress=lambda done, total: None):
    started = perf_counter()
    capture = cv2.VideoCapture(str(path), cv2.CAP_FFMPEG)
    try:
        if not capture.isOpened():
            raise ValueError('Could not open media for timing refinement.')
        capture.set(cv2.CAP_PROP_ORIENTATION_AUTO, 1)
        previous_segment = None
        for index, segment in enumerate(segments):
            on_progress(index, len(segments))
            if cancelled(): return
            original = segment.start_time
            lower_limit = (previous_segment.start_time + .001) if previous_segment is not None else 0.0
            lower = max(lower_limit, original - 1 / settings.sample_fps)
            if original <= lower:
                previous_segment = segment
                continue
            capture.set(cv2.CAP_PROP_POS_MSEC, lower * 1000)
            candidate = None
            previous_crop, previous_observation = None, None
            last_time = -1.0
            while not cancelled():
                ok, image = capture.read()
                if not ok: break
                timestamp = capture.get(cv2.CAP_PROP_POS_MSEC) / 1000
                if timestamp <= last_time or timestamp < 0:
                    raise ValueError('Invalid decoded timestamp during refinement.')
                last_time = timestamp
                if timestamp > original + .001: break
                if timestamp < lower - .001: continue
                crop = crop_frame(image, settings.roi)
                if previous_crop is not None and np.array_equal(crop, previous_crop):
                    observation = replace(previous_observation, timestamp=timestamp, calls=0, inference_seconds=0)
                    metrics.refinement_reused_frames += 1
                else:
                    observation = engine.recognize(FrameSample(timestamp, crop))
                previous_crop, previous_observation = crop, observation
                metrics.refinement_frames += 1
                metrics.ocr_calls += observation.calls
                metrics.inference_seconds += observation.inference_seconds
                if observation.confidence >= .8 and normalized(observation.text) == normalized(segment.text):
                    if candidate is not None:
                        segment.start_time = candidate
                        if previous_segment is not None and previous_segment.end_time > candidate:
                            previous_segment.metadata.update(coarse_end_time=previous_segment.end_time, boundary_refined=True)
                            previous_segment.end_time = candidate
                        segment.metadata.update(coarse_start_time=original, boundary_refined=True,
                                                timing_source='two_adjacent_decoded_frames', timestamp_uncertainty=timestamp-candidate)
                        break
                    candidate = timestamp
                else:
                    candidate = None
            previous_crop, previous_observation = None, None
            previous_segment = segment
        on_progress(len(segments), len(segments))
    finally:
        capture.release()
        metrics.refinement_seconds += perf_counter() - started
