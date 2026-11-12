"""Preserve complete compatible files; remux/transcode only the incompatible streams."""
import subprocess
import time
from pathlib import Path

from fastapi import HTTPException
from app.services.douyin_urls import ImportFailure
from app.services.video_import import probe_video


def run_ffmpeg(command, errors_path, settings, context, destination=None):
    process = None
    try:
        with errors_path.open('wb') as errors:
            process = subprocess.Popen(command, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=errors,
                                       creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
            while process.poll() is None:
                context.check()
                if destination and destination.exists() and destination.stat().st_size > min(settings.max_download_bytes, settings.max_upload_bytes):
                    raise ImportFailure('size_limit', 'The converted video exceeds the configured size limit.')
                if errors_path.stat().st_size > 1024 * 1024:
                    raise ImportFailure('invalid_media', 'The media contains too many stream errors to import safely.')
                time.sleep(.05)
            return process.returncode
    except FileNotFoundError:
        raise HTTPException(503, 'FFmpeg is unavailable. Install FFmpeg and restart the backend.') from None
    finally:
        if process and process.poll() is None:
            process.kill(); process.wait()


def prepare_media(source: Path, settings, context, expected_duration=None):
    context.check()
    metadata = probe_video(source, settings.ffprobe, require_mp4=False)
    context.check()
    if expected_duration and metadata['duration'] + max(1.5, expected_duration * .0001) < expected_duration:
        raise ImportFailure('incomplete_media', 'The downloaded video is shorter than its published duration. It will not be imported as a complete video.')
    # Walk every packet without re-encoding: metadata duration alone can describe a truncated MP4.
    integrity = [settings.ffmpeg, '-nostdin', '-hide_banner', '-loglevel', 'error', '-xerror', '-err_detect', 'explode',
                 '-protocol_whitelist', 'file,pipe', '-format_whitelist', 'mov,matroska,webm,mpegts,avi,flv,ogg',
                 '-i', str(source), '-map', '0:v:0', '-map', '0:a:0?', '-c', 'copy', '-f', 'null', '-']
    if run_ffmpeg(integrity, source.with_suffix('.integrity.log'), settings, context):
        raise ImportFailure('incomplete_media', 'The downloaded media contains incomplete or corrupt packets. A partial video will not be imported.')
    context.check()
    video_ok = metadata['video_codec'] == 'h264' and metadata['pixel_format'] in ('yuv420p', 'yuvj420p')
    audio_ok = metadata['audio_codec'] in (None, 'aac', 'mp3')
    with source.open('rb') as stream:
        header = stream.read(12)
    container_ok = len(header) == 12 and header[4:8] == b'ftyp' and header[8:12] != b'qt  '
    if video_ok and audio_ok and container_ok:
        return source, 'none'
    destination = source.with_name('compatible.mp4')
    command = [settings.ffmpeg, '-nostdin', '-hide_banner', '-loglevel', 'error', '-y',
               '-xerror', '-protocol_whitelist', 'file,pipe', '-format_whitelist', 'mov,matroska,webm,mpegts,avi,flv,ogg', '-i', str(source), '-map', '0:v:0', '-map', '0:a:0?',
               '-c:v', 'copy' if video_ok else 'libx264']
    if not video_ok: command += ['-crf', '18', '-preset', 'medium', '-pix_fmt', 'yuv420p']
    command += ['-c:a', 'copy' if audio_ok else 'aac']
    if not audio_ok: command += ['-b:a', '192k']
    command += ['-movflags', '+faststart', str(destination)]
    if run_ffmpeg(command, source.with_suffix('.ffmpeg.log'), settings, context, destination):
        raise ImportFailure('unsupported_codec', 'FFmpeg could not convert this video to an Edge-compatible MP4. Import a locally converted H.264/AAC MP4 instead.')
    context.check()
    if destination.stat().st_size > min(settings.max_download_bytes, settings.max_upload_bytes):
        raise ImportFailure('size_limit', 'The converted video exceeds the configured size limit.')
    converted = probe_video(destination, settings.ffprobe)
    if converted['duration'] + .25 < metadata['duration']:
        raise ImportFailure('incomplete_media', 'Video conversion did not preserve the full duration.')
    return destination, 'remux' if video_ok and audio_ok else 'transcode'
