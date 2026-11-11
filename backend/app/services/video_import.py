import hashlib
import json
import math
import subprocess
import tempfile
from datetime import datetime, timezone
from fractions import Fraction
from pathlib import Path
from uuid import uuid4

from fastapi import HTTPException, UploadFile

from app.config import Settings
from app.models.schemas import ImportResult, Video
from app.services.repository import Repository


def probe_video(path: Path, executable: str) -> dict:
    try:
        result = subprocess.run(
            [executable, "-v", "error", "-protocol_whitelist", "file,pipe", "-show_format", "-show_streams", "-of", "json", str(path)],
            capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=30,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
    except FileNotFoundError as exc:
        raise HTTPException(503, "FFprobe is unavailable. Install FFmpeg and add its bin folder to PATH, then restart the backend.") from exc
    except subprocess.TimeoutExpired as exc:
        raise HTTPException(422, "Video inspection timed out. Try a smaller or repaired MP4 file.") from exc
    try:
        metadata = json.loads(result.stdout)
        if result.returncode or "mp4" not in metadata["format"]["format_name"].split(","):
            raise ValueError("Not an MP4")
        streams = metadata["streams"]
        video = next(s for s in streams if s.get("codec_type") == "video" and not s.get("disposition", {}).get("attached_pic"))
        audio = next((s for s in streams if s.get("codec_type") == "audio"), None)
        duration = float(metadata["format"].get("duration", video.get("duration", 0)))
        width, height = int(video["width"]), int(video["height"])
        if not math.isfinite(duration) or duration <= 0 or width <= 0 or height <= 0:
            raise ValueError("Invalid dimensions or duration")
        try:
            fps = float(Fraction(video.get("avg_frame_rate", "0/1")))
        except (ValueError, ZeroDivisionError):
            fps = 0.0
        rotation = next((int(s["rotation"]) for s in video.get("side_data_list", []) if "rotation" in s), int(video.get("tags", {}).get("rotate", 0)))
        if abs(rotation) % 180 == 90:
            width, height = height, width
        return dict(duration=duration, width=width, height=height, fps=fps,
                    video_codec=video.get("codec_name", "unknown"),
                    audio_codec=audio.get("codec_name", "unknown") if audio else None)
    except (ValueError, KeyError, StopIteration, TypeError) as exc:
        raise HTTPException(422, "This file is not a readable MP4 video. Export it as MP4 with H.264 video and AAC audio, then import again.") from exc


def import_video(upload: UploadFile, settings: Settings, repository: Repository) -> ImportResult:
    # Never use the supplied filename as a filesystem path.
    name = (upload.filename or "").replace("\\", "/").rsplit("/", 1)[-1]
    if not name.lower().endswith(".mp4"):
        raise HTTPException(415, "Choose an .mp4 video file.")
    if len(name) > 240:
        raise HTTPException(422, "The filename is too long. Rename the file to fewer than 240 characters.")
    staged: Path | None = None
    candidate: Path | None = None
    try:
        fingerprint = hashlib.sha256()
        total = 0
        with tempfile.NamedTemporaryFile(dir=settings.media_dir, suffix=".upload", delete=False) as target:
            staged = Path(target.name)
            while chunk := upload.file.read(1024 * 1024):
                total += len(chunk)
                if total > settings.max_upload_bytes:
                    raise HTTPException(413, f"Video exceeds the {settings.max_upload_bytes // (1024 * 1024)} MB upload limit.")
                fingerprint.update(chunk)
                target.write(chunk)
        with staged.open("rb") as source:
            header = source.read(16)
        if len(header) < 12 or header[4:8] != b"ftyp" or header[8:12] == b"qt  ":
            raise HTTPException(422, "The file does not have a valid MP4 header. Renaming another format to .mp4 will not convert it.")
        digest = fingerprint.hexdigest()
        existing = repository.by_hash(digest)
        if existing and (settings.media_dir / f"{existing.id}.mp4").is_file():
            return ImportResult(video=existing, reused=True)
        metadata = probe_video(staged, settings.ffprobe)
        video_id = existing.id if existing else uuid4()
        warning = None
        if metadata["video_codec"] != "h264" or metadata["audio_codec"] not in (None, "aac", "mp3"):
            warning = "This codec may not play in your browser. If playback fails, convert a copy to H.264 video and AAC audio with FFmpeg (see README)."
        video = existing or Video(
            id=video_id, original_name=name, sha256=digest, size_bytes=total,
            created_at=datetime.now(timezone.utc), media_url=f"/api/videos/{video_id}/media",
            codec_warning=warning, **metadata,
        )
        candidate = settings.media_dir / f"{video_id}.mp4"
        staged.replace(candidate)
        staged = None
        saved = repository.add(video)
        if saved.id != video_id:
            candidate.unlink(missing_ok=True)
        candidate = None
        return ImportResult(video=saved, reused=saved.id != video_id or existing is not None)
    finally:
        if staged:
            staged.unlink(missing_ok=True)
        if candidate:
            candidate.unlink(missing_ok=True)
