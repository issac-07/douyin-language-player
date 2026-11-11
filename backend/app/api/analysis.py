from typing import Literal
import json
from uuid import UUID

import cv2
from fastapi import APIRouter, HTTPException, Query, Request
from starlette.responses import Response

from app.api.videos import require_video
from app.models.schemas import AnalysisJob, AnalysisRequest, AnalysisStarted, SubtitleDocument, SubtitleEdit
from app.services.video_frames import read_frame

router = APIRouter(prefix="/api", tags=["subtitle analysis"])


@router.get("/videos/{video_id}/preview")
def preview(request: Request, video_id: UUID, timestamp: float = Query(default=1, ge=0, allow_inf_nan=False)):
    video = require_video(request, video_id)
    if timestamp >= video.duration:
        timestamp = max(0, video.duration - 0.1)
    path = request.app.state.settings.media_dir / f"{video_id}.mp4"
    if not path.is_file():
        raise HTTPException(410, "Cached media is missing. Reimport the original MP4.")
    try:
        frame = read_frame(path, timestamp)
        image = frame.image
        scale = min(1, 1280 / max(image.shape[:2]))
        if scale < 1:
            image = cv2.resize(image, None, fx=scale, fy=scale)
        ok, encoded = cv2.imencode(".jpg", image, [cv2.IMWRITE_JPEG_QUALITY, 90])
        if not ok:
            raise ValueError("Could not encode this preview.")
        return Response(encoded.tobytes(), media_type="image/jpeg", headers={"X-Frame-Timestamp": str(frame.timestamp), "Cache-Control": "no-store"})
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc


@router.post("/videos/{video_id}/analyses", response_model=AnalysisStarted, status_code=202)
def start_analysis(request: Request, video_id: UUID, body: AnalysisRequest):
    video = require_video(request, video_id)
    settings = body.settings or request.app.state.repository.get_settings(video_id)
    return request.app.state.worker.start(video, settings, body.force)


@router.get("/videos/{video_id}/analyses/latest", response_model=AnalysisJob | None)
def latest_analysis(request: Request, video_id: UUID):
    require_video(request, video_id)
    return request.app.state.repository.latest_job(video_id)


@router.get("/analysis-jobs/{job_id}", response_model=AnalysisJob)
def get_job(request: Request, job_id: UUID):
    job = request.app.state.repository.get_job(job_id)
    if not job:
        raise HTTPException(404, "Analysis job not found.")
    return job


@router.post("/analysis-jobs/{job_id}/cancel", response_model=AnalysisJob)
def cancel_job(request: Request, job_id: UUID):
    return request.app.state.worker.cancel(job_id)


@router.get("/videos/{video_id}/subtitles", response_model=SubtitleDocument)
def subtitles(request: Request, video_id: UUID):
    require_video(request, video_id)
    return request.app.state.repository.document(video_id)


@router.patch("/videos/{video_id}/subtitles/{segment_id}", response_model=SubtitleDocument)
def edit_subtitle(request: Request, video_id: UUID, segment_id: UUID, body: SubtitleEdit):
    video = require_video(request, video_id)
    repo = request.app.state.repository
    document = repo.document(video_id)
    segment = next((s for s in document.segments if s.id == segment_id), None)
    if not segment:
        raise HTTPException(404, "Subtitle not found. Reload the transcript.")
    if body.end_time > video.duration + 0.001:
        raise HTTPException(422, "Subtitle end exceeds the video's duration.")
    segment.text, segment.start_time, segment.end_time = body.text, body.start_time, body.end_time
    segment.edited, segment.revision = True, body.revision + 1
    try:
        changed = repo.change_segment(video_id, body.analysis_id, segment_id, body.revision, segment)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    if not changed:
        raise HTTPException(409, "This transcript changed during editing. Reload before saving again.")
    request.app.state.learning.document(repo.document(video_id))
    return repo.document(video_id)


@router.delete("/videos/{video_id}/subtitles/{segment_id}", response_model=SubtitleDocument)
def delete_subtitle(request: Request, video_id: UUID, segment_id: UUID, analysis_id: UUID, revision: int = Query(ge=0)):
    require_video(request, video_id)
    repo = request.app.state.repository
    if not repo.change_segment(video_id, analysis_id, segment_id, revision, None):
        raise HTTPException(409, "This transcript changed or was already deleted. Reload the transcript.")
    return repo.document(video_id)


def srt_time(seconds: float) -> str:
    milliseconds = max(0, round(seconds * 1000))
    hours, remainder = divmod(milliseconds, 3_600_000)
    minutes, remainder = divmod(remainder, 60_000)
    seconds, milliseconds = divmod(remainder, 1000)
    return f"{hours:02}:{minutes:02}:{seconds:02},{milliseconds:03}"


@router.get("/videos/{video_id}/export")
def export_subtitles(request: Request, video_id: UUID, format: Literal["json", "srt"] = "json", analysis_id: UUID | None = None):
    require_video(request, video_id)
    document = request.app.state.repository.document(video_id, analysis_id)
    if not document.analysis:
        raise HTTPException(404, "No completed analysis is available to export.")
    if format == "json":
        payload = document.model_dump(mode='json')
        payload['language'] = request.app.state.learning.document(document).model_dump(mode='json')
        content = json.dumps(payload, ensure_ascii=False, indent=2)
        media_type = "application/json"
    else:
        content = "\n\n".join(f"{index}\n{srt_time(segment.start_time)} --> {srt_time(segment.end_time)}\n{segment.text}" for index, segment in enumerate(document.segments, 1))
        content += "\n" if content else ""
        media_type = "application/x-subrip"
    return Response(content.encode("utf-8"), media_type=media_type,
                    headers={"Content-Disposition": f'attachment; filename="subtitles-{video_id}.{format}"'})
