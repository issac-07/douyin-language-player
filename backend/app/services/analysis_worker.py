"""A bounded single-worker CPU queue; all completion/cancellation transitions serialize."""
import logging
import math
import threading
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from datetime import datetime, timezone
from time import perf_counter
from uuid import UUID, uuid4

import cv2
import numpy as np
from fastapi import HTTPException

from app.config import Settings
from app.models.schemas import AnalysisJob, AnalysisStarted, JobStatus, ProcessingSettings, Video
from app.services.ocr_engine import RapidOCREngine, engine_identity
from app.services.pipeline import analysis_cache_key
from app.services.repository import Repository
from app.services.subtitle_detection import SubtitleDetector
from app.services.video_frames import OpenCVFrameSource

logger = logging.getLogger(__name__)
TERMINAL = {JobStatus.COMPLETED, JobStatus.CANCELLED, JobStatus.FAILED}


class AnalysisWorker:
    def __init__(self, repository: Repository, settings: Settings):
        self.repository, self.settings = repository, settings
        self.pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix="subtitle-ocr")
        self.lock = threading.RLock()
        self.events: dict[UUID, threading.Event] = {}
        self.engine = None
        self.closing = False
        try:
            self.engine_version = engine_identity()
            self.availability_error = None
        except Exception as exc:
            self.engine_version = "unavailable"
            self.availability_error = str(exc)

    def start(self, video: Video, settings: ProcessingSettings, force: bool) -> AnalysisStarted:
        with self.lock:
            if self.closing:
                raise HTTPException(503, "The OCR worker is shutting down. Restart the backend.")
            if self.availability_error:
                raise HTTPException(503, self.availability_error)
            path = self.settings.media_dir / f"{video.id}.mp4"
            if not path.is_file():
                raise HTTPException(410, "The cached MP4 is missing. Reimport the original video.")
            key = analysis_cache_key(video.sha256, settings, self.engine_version)
            latest = self.repository.latest_job(video.id)
            if latest and latest.status not in TERMINAL:
                if latest.cache_key == key and not force:
                    return AnalysisStarted(job=latest)
                raise HTTPException(409, "This video already has an active analysis. Cancel it before rerunning with new settings.")
            self.repository.save_settings(video.id, settings)
            cached = self.repository.latest_job(video.id, key)
            if cached and not force:
                self.repository.activate(cached)
                return AnalysisStarted(job=cached, cached=True)
            if len(self.events) >= 8:
                raise HTTPException(429, "The local OCR queue is full. Wait for a video to finish or cancel an analysis.")
            total = math.ceil(video.duration * settings.sample_fps)
            if total > 100_000:
                raise HTTPException(422, "This would sample over 100,000 frames. Reduce the sampling rate or trim the video.")
            job = AnalysisJob(id=uuid4(), video_id=video.id, cache_key=key, engine_version=self.engine_version,
                              settings=settings, total_frames=total, created_at=datetime.now(timezone.utc),
                              timestamp_uncertainty=1 / settings.sample_fps)
            self.repository.save_job(job)
            event = threading.Event()
            self.events[job.id] = event
            self.pool.submit(self._run, job, video, event)
            return AnalysisStarted(job=job)

    def cancel(self, job_id: UUID) -> AnalysisJob:
        with self.lock:
            job = self.repository.get_job(job_id)
            if not job:
                raise HTTPException(404, "Analysis job not found.")
            if job.status not in TERMINAL:
                if event := self.events.get(job_id):
                    event.set()
                job.status = JobStatus.CANCELLED
                job.completed_at = datetime.now(timezone.utc)
                self.repository.save_job(job)
            return job

    def _run(self, job: AnalysisJob, video: Video, event: threading.Event):
        started = perf_counter()
        samples = None
        try:
            with self.lock:
                if event.is_set():
                    return
                job.status = JobStatus.PROCESSING
                self.repository.save_job(job)
            if self.engine is None:
                self.engine = RapidOCREngine()
            detector = SubtitleDetector(job.settings.sample_fps, video.duration)
            samples = OpenCVFrameSource(video.duration).samples(str(self.settings.media_dir / f"{video.id}.mp4"), job.settings)
            previous_image, previous_observation = None, None
            for sample in samples:
                if event.is_set():
                    return
                fingerprint = cv2.cvtColor(sample.image, cv2.COLOR_BGR2GRAY)
                # Exact crop equality only: never skip a subtly changed character.
                if previous_image is not None and fingerprint.shape == previous_image.shape and np.array_equal(fingerprint, previous_image):
                    observation = replace(previous_observation, timestamp=sample.timestamp, inference_seconds=0, calls=0)
                    job.metrics.reused_frames += 1
                else:
                    observation = self.engine.recognize(sample)
                previous_image, previous_observation = fingerprint, observation
                detector.observe(observation)
                job.metrics.frames_processed += 1
                job.metrics.ocr_calls += observation.calls
                job.metrics.inference_seconds += observation.inference_seconds
                job.metrics.total_seconds = perf_counter() - started
                job.progress = min(0.99, (sample.timestamp + 1 / job.settings.sample_fps) / video.duration)
                with self.lock:
                    if event.is_set():
                        return
                    self.repository.save_job(job)
            segments = detector.finish()
            with self.lock:
                if event.is_set():
                    return
                job.metrics.total_seconds = perf_counter() - started
                job.metrics.unique_segments = len(segments)
                job.metrics.average_confidence = sum(s.confidence for s in segments) / len(segments) if segments else 0
                job.status = JobStatus.COMPLETED
                job.progress = 1
                job.completed_at = datetime.now(timezone.utc)
                self.repository.complete(job, segments)
        except Exception as exc:
            logger.exception("OCR job %s failed", job.id)
            with self.lock:
                if not event.is_set():
                    job.status = JobStatus.FAILED
                    job.error = f"OCR analysis failed: {exc}. Check the local dependencies and selected region, then rerun."
                    job.completed_at = datetime.now(timezone.utc)
                    job.metrics.total_seconds = perf_counter() - started
                    self.repository.save_job(job)
        finally:
            if samples:
                samples.close()
            with self.lock:
                self.events.pop(job.id, None)

    def shutdown(self):
        with self.lock:
            self.closing = True
            for job_id in tuple(self.events):
                self.cancel(job_id)
        self.pool.shutdown(wait=True, cancel_futures=True)
