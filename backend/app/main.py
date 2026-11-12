import shutil
import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from starlette.middleware.trustedhost import TrustedHostMiddleware
from starlette.responses import JSONResponse

from app.api.videos import router
from app.api.analysis import router as analysis_router
from app.api.learning import router as learning_router
from app.config import Settings
from app.services.repository import Repository
from app.services.analysis_worker import AnalysisWorker
from app.services.learning import LearningService
from app.api.imports import router as imports_router
from app.services.douyin_import import DouyinImportService


class LocalUploadGuard:
    """Bound request bytes before multipart spooling, including chunked requests."""

    def __init__(self, app, limit: int, allowed_origins: tuple[str, ...]):
        self.app = app
        self.limit = limit
        self.allowed_origins = frozenset(allowed_origins)

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        headers = dict(scope["headers"])
        origin = headers.get(b"origin", b"").decode()
        if scope["method"] in {"POST", "PUT", "DELETE", "PATCH"} and origin and origin not in self.allowed_origins:
            return await JSONResponse({"detail": "Only the local player may modify this library."}, status_code=403)(scope, receive, send)
        if scope["method"] != "POST" or scope["path"] not in {"/api/videos", "/api/imports/douyin"}:
            return await self.app(scope, receive, send)
        limit = self.limit if scope['path'] == '/api/videos' else 64 * 1024
        try:
            declared = int(headers.get(b"content-length", b"0"))
        except ValueError:
            return await JSONResponse({"detail": "Invalid Content-Length."}, status_code=400)(scope, receive, send)
        if declared < 0:
            return await JSONResponse({"detail": "Invalid Content-Length."}, status_code=400)(scope, receive, send)
        if declared > limit:
            return await JSONResponse({"detail": "Import request exceeds the configured size limit."}, status_code=413)(scope, receive, send)
        consumed = 0

        async def bounded_receive():
            nonlocal consumed
            message = await receive()
            if message["type"] == "http.request":
                consumed += len(message.get("body", b""))
                if consumed > limit:
                    raise HTTPException(413, "Upload exceeds the configured video size limit.")
            return message

        await self.app(scope, bounded_receive, send)


def create_app(settings: Settings | None = None, *, import_client_factory=None, import_public_page_extractor=None) -> FastAPI:
    settings = settings or Settings.from_env()
    repository = Repository(settings.data_dir / "library.sqlite3")

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        settings.media_dir.mkdir(parents=True, exist_ok=True)
        repository.initialize()
        repository.recover_interrupted_jobs()
        app.state.worker = AnalysisWorker(repository, settings)
        app.state.learning = LearningService(repository, settings)
        app.state.imports = DouyinImportService(repository, settings, app.state.worker,
            public_page_extractor=import_public_page_extractor,
            **({'client_factory': import_client_factory} if import_client_factory else {}))
        try:
            yield
        finally:
            await asyncio.to_thread(app.state.imports.shutdown)
            await asyncio.to_thread(app.state.worker.shutdown)
            await asyncio.to_thread(app.state.learning.shutdown)

    app = FastAPI(title="Douyin Language Player", version="0.4.5", lifespan=lifespan)
    app.state.settings = settings
    app.state.repository = repository
    # Small multipart overhead allowance; import_video enforces the exact file limit.
    app.add_middleware(LocalUploadGuard, limit=settings.max_upload_bytes + 64 * 1024, allowed_origins=settings.allowed_origins)
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=["127.0.0.1", "localhost", "testserver"])
    app.include_router(router)
    app.include_router(analysis_router)
    app.include_router(learning_router)
    app.include_router(imports_router)

    @app.get("/api/health")
    def health():
        return {"status": "ok", "phase": 4, "version": "0.4.5", "ffprobe_available": shutil.which(settings.ffprobe) is not None,
                "max_download_bytes": settings.max_download_bytes,
                "ffmpeg_available": shutil.which(settings.ffmpeg) is not None,
                "max_upload_bytes": settings.max_upload_bytes,
                "ocr_available": app.state.worker.availability_error is None,
                "ocr_error": app.state.worker.availability_error,
                "dictionary_available": app.state.learning.dictionary.available,
                "translation_available": app.state.learning.translator.available}

    return app


app = create_app()
