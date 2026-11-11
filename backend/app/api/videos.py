from uuid import UUID

from fastapi import APIRouter, HTTPException, Request, UploadFile
from starlette.responses import FileResponse

from app.models.schemas import ImportResult, ProcessingSettings, Video
from app.services.video_import import import_video

router = APIRouter(prefix="/api/videos", tags=["videos"])


def require_video(request: Request, video_id: UUID) -> Video:
    video = request.app.state.repository.get_video(video_id)
    if video is None:
        raise HTTPException(404, "Video not found. Import a local MP4 to get started.")
    return video


@router.get("", response_model=list[Video])
def list_videos(request: Request):
    return request.app.state.repository.list_videos()


@router.post("", response_model=ImportResult, status_code=201)
def upload_video(request: Request, file: UploadFile):
    return import_video(file, request.app.state.settings, request.app.state.repository)


@router.get("/{video_id}", response_model=Video)
def video_metadata(request: Request, video_id: UUID):
    return require_video(request, video_id)


@router.api_route("/{video_id}/media", methods=["GET", "HEAD"], response_class=FileResponse)
def video_media(request: Request, video_id: UUID):
    require_video(request, video_id)
    path = request.app.state.settings.media_dir / f"{video_id}.mp4"
    if not path.is_file():
        raise HTTPException(410, "The cached video file is missing. Import the original MP4 again to restore it.")
    return FileResponse(path, media_type="video/mp4", headers={"X-Content-Type-Options": "nosniff"})


@router.get("/{video_id}/processing-settings", response_model=ProcessingSettings)
def get_processing_settings(request: Request, video_id: UUID):
    require_video(request, video_id)
    return request.app.state.repository.get_settings(video_id)


@router.put("/{video_id}/processing-settings", response_model=ProcessingSettings)
def save_processing_settings(request: Request, video_id: UUID, settings: ProcessingSettings):
    require_video(request, video_id)
    request.app.state.repository.save_settings(video_id, settings)
    return settings
