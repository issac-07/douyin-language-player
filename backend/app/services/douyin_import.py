"""Single bounded import worker, independent of the OCR and language queues."""
import logging
import shutil
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from uuid import UUID, uuid4

from fastapi import HTTPException, UploadFile
from yt_dlp.version import __version__ as YTDLP_VERSION
from app.models.imports import ImportJob
from app.models.schemas import ImportResult
from app.services.douyin_extractor import YtDlpExtractor
from app.services.public_edge_extractor import PublicEdgeExtractor
from app.services.douyin_urls import ImportCancelled, ImportFailure, canonical_video_url, parse_douyin_input
from app.services.import_media import prepare_media
from app.services.safe_http import RequestContext, SafeHTTPClient
from app.services.video_import import import_video

TERMINAL = {'completed', 'failed', 'cancelled'}
logger = logging.getLogger(__name__)


class DouyinImportService:
    def __init__(self, repository, settings, analysis_worker, *, client_factory=SafeHTTPClient, extractor=None, public_page_extractor=None):
        self.repository, self.settings, self.analysis_worker = repository, settings, analysis_worker
        self.client_factory, self.extractor = client_factory, extractor or YtDlpExtractor()
        self.public_page_extractor = public_page_extractor or PublicEdgeExtractor(settings.node)
        self.pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix='douyin-import')
        self.lock = threading.RLock()
        self.events = {}
        self.closing = False
        self.temp_root = (settings.data_dir / 'downloads').resolve()
        self.temp_root.mkdir(parents=True, exist_ok=True)
        # Recover only app-owned UUID directories. Never traverse symlinks/junctions or arbitrary paths.
        for job in repository.list_imports(100000):
            if job.status not in TERMINAL:
                job.status, job.error_code, job.error = 'failed', 'interrupted', 'The backend stopped during this import. Retry the link or import a local MP4.'
                job.completed_at = datetime.now(timezone.utc)
                repository.save_import(job)
            self._cleanup(job.id)

    def _cleanup(self, job_id):
        target = self.temp_root / str(UUID(str(job_id)))
        if target.is_dir() and not target.is_symlink() and not target.is_junction() and target.resolve().parent == self.temp_root:
            shutil.rmtree(target)

    def start(self, request):
        url = parse_douyin_input(request.text)
        with self.lock:
            if self.closing: raise HTTPException(503, 'The import worker is shutting down.')
            if len(self.events) >= 4: raise HTTPException(429, 'The URL import queue is full. Wait or cancel an import.')
            job = ImportJob(id=uuid4(), input_url=url, created_at=datetime.now(timezone.utc), analyze_after_import=request.analyze_after_import, extractor_version=YTDLP_VERSION,
                            extraction_method='public_page' if request.use_public_page else 'direct')
            self.repository.save_import(job)
            event = threading.Event()
            self.events[job.id] = event
            self.pool.submit(self._run, job, request, event)
            return job.model_copy(deep=True)

    def get(self, job_id):
        job = self.repository.get_import(job_id)
        if not job: raise HTTPException(404, 'URL import job not found.')
        return job

    def cancel(self, job_id):
        with self.lock:
            job = self.get(job_id)
            if job.status not in TERMINAL:
                if event := self.events.get(job_id): event.set()
                job.status = 'cancelled'
                job.completed_at = datetime.now(timezone.utc)
                self.repository.save_import(job)
            return job

    def _run(self, job, request, event):
        started = time.monotonic()
        context = RequestContext(event, self.settings.import_timeout_seconds)
        folder = self.temp_root / str(job.id)
        def save(**changes):
            with self.lock:
                context.check()
                for key, value in changes.items(): setattr(job, key, value)
                job.diagnostics = list(context.diagnostics)
                job.elapsed_seconds = round(time.monotonic() - started, 3)
                self.repository.save_import(job)
        def complete(result):
            # Called inside publication lock: cancellation cannot race the library commit.
            job.video = self.repository.attach_source(result.video, job.metadata)
            job.reused = result.reused
            if request.analyze_after_import:
                configured = request.roi_confirmed and request.processing_settings is not None
                if configured or self.repository.has_settings(job.video.id):
                    try:
                        settings = request.processing_settings if configured else self.repository.get_settings(job.video.id)
                        analysis = self.analysis_worker.start(job.video, settings, False)
                        job.analysis_job_id = analysis.job.id
                        job.analysis_message = 'Reused cached analysis.' if analysis.cached else 'Chinese subtitle analysis queued.'
                    except HTTPException as exc:
                        job.analysis_message = f'Video imported. Analysis could not start: {exc.detail}'
                    except Exception:
                        logger.exception('Automatic OCR could not start after URL import')
                        job.analysis_message = 'Video imported. Automatic analysis could not start; select its subtitle region and try Analyze again.'
                else:
                    job.analysis_message = 'Select and save the subtitle region in OCR settings, then choose Analyze. Automatic analysis needs a confirmed region.'
            # Publication has already committed under the lock. Finalize even if the
            # deadline expires during this short commit; never report stored media as timed out.
            job.status, job.completed_at = 'completed', datetime.now(timezone.utc)
            context.record('completed')
            job.diagnostics = list(context.diagnostics)
            job.elapsed_seconds = round(time.monotonic() - started, 3)
            self.repository.save_import(job)
        try:
            folder.mkdir()
            for attempt in range(1, job.max_attempts + 1):
                try:
                    save(status='resolving', attempt=attempt, bytes_downloaded=0, total_bytes=None)
                    context.begin('resolve_url')
                    client = self.client_factory(context)
                    canonical = canonical_video_url(job.input_url)
                    if not canonical:
                        with client.open(job.input_url, role='page') as response:
                            canonical = canonical_video_url(response.url)
                        if not canonical: raise ImportFailure('unresolved_link', 'This short link did not resolve to a video. It may be expired; use a normal Douyin video URL or local MP4.')
                    save(canonical_url=canonical)
                    context.record('completed')
                    existing = self.repository.find_source(canonical)
                    if existing and (self.settings.media_dir / f'{existing.id}.mp4').is_file():
                        job.metadata = self.repository.get_source(canonical)
                        with self.lock:
                            context.check()
                            complete(ImportResult(video=existing, reused=True))
                        return
                    extractor = self.public_page_extractor if request.use_public_page else self.extractor
                    media = extractor.extract(canonical, client)
                    save(metadata=media.metadata, status='downloading')
                    source = folder / 'download.media'
                    context.begin('download_media')
                    with client.open(media.url, role='media', limit=min(self.settings.max_download_bytes, self.settings.max_upload_bytes)) as response:
                        save(total_bytes=response.length)
                        last_save = 0
                        with source.open('wb') as target:
                            while chunk := response.read(256 * 1024):
                                context.check()
                                target.write(chunk)
                                job.bytes_downloaded += len(chunk)
                                if time.monotonic() - last_save >= .2:
                                    save(); last_save = time.monotonic()
                        save()
                    save(status='validating')
                    context.begin('validate_media')
                    path, conversion = prepare_media(source, self.settings, context, media.metadata.duration)
                    save(status='importing', conversion=conversion)
                    context.begin('import_library')
                    with path.open('rb') as stream:
                        import_video(UploadFile(file=stream, filename=f'douyin-{media.metadata.video_id}.mp4'), self.settings, self.repository,
                                     check=context.check, publication_guard=lambda: self.lock, on_import=complete)
                    return
                except ImportFailure as exc:
                    context.record('failed', category=exc.code, http_status=exc.http_status)
                    if not exc.retryable or attempt == job.max_attempts: raise
                    save(error=f'{exc.message} Retrying ({attempt + 1}/{job.max_attempts})…', error_code=exc.code)
                    if event.wait(min(2, .5 * attempt)): raise ImportCancelled()
                    save(error=None, error_code=None)
        except ImportCancelled:
            with self.lock:
                job.status, job.completed_at = 'cancelled', datetime.now(timezone.utc)
                self.repository.save_import(job)
        except Exception as exc:
            with self.lock:
                if event.is_set(): job.status = 'cancelled'
                else:
                    job.status = 'failed'
                    job.error_code = exc.code if isinstance(exc, ImportFailure) else 'invalid_media' if isinstance(exc, HTTPException) else 'import_error'
                    job.error = exc.message if isinstance(exc, ImportFailure) else str(exc.detail) if isinstance(exc, HTTPException) else 'The video could not be imported. Retry later or import a local MP4.'
                    job.error_operation = (exc.operation or context.operation) if isinstance(exc, ImportFailure) else context.operation
                    job.upstream_http_status = exc.http_status if isinstance(exc, ImportFailure) else None
                    if not isinstance(exc, (ImportFailure, HTTPException)):
                        job.error_code = 'download_failure' if context.operation == 'download_media' else 'import_error'
                        context.record('failed', category=job.error_code, exception_type=type(exc).__name__)
                job.diagnostics = list(context.diagnostics)
                job.completed_at = datetime.now(timezone.utc)
                job.elapsed_seconds = round(time.monotonic() - started, 3)
                self.repository.save_import(job)
        finally:
            try: self._cleanup(job.id)
            finally:
                with self.lock: self.events.pop(job.id, None)

    def shutdown(self):
        with self.lock:
            self.closing = True
            for job_id in list(self.events): self.cancel(job_id)
        self.pool.shutdown(wait=True, cancel_futures=False)
