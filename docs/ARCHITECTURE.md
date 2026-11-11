# Local architecture — Phases 1 and 2

Vite proxies `/api` to FastAPI. HTML5 video plays the original MP4 using byte-range requests. Playback and subtitle selection use actual `video.currentTime`, including seek events, rather than wall-clock estimates. Everything runs locally.

## Modules

| Module | Responsibility |
| --- | --- |
| `config.py`, `api/videos.py`, `services/video_import.py` | Preserved Phase 1 import, validation, fingerprinting and UUID-safe media API |
| `models/schemas.py` | Typed ROI/settings, jobs, metrics, segments and corrections |
| `services/repository.py` | SQLite schema migration, analyses, active pointers and revision-checked edits |
| `services/pipeline.py` | Reusable frame/OCR protocols, observations and cache identity |
| `services/video_frames.py` | Timestamp-preserving samples and normalized cropping |
| `services/ocr_engine.py` | Real CPU RapidOCR, model identity, reading order and preprocessing fallback |
| `services/subtitle_detection.py` | Normalization, confidence filtering, merging, disappearance and timing inference |
| `services/analysis_worker.py` | Bounded CPU queue, measured progress and serialized cancellation/publication |
| `api/analysis.py` | Preview, start/status/cancel/results, correction and export endpoints |
| `OCRWorkspace.tsx` | Per-video session and abortable polling |
| `ROIEditor.tsx`, `services/roi.ts` | Draw/move/resize with letterbox-aware coordinates |
| `Transcript.tsx` | Corrections, deletion, timestamp seeking and downloads |
| `VideoPlayer.tsx`, `services/playback.ts` | Existing playback controls plus synchronized Chinese text |

Backend paths are under `backend/app`; frontend paths are under `frontend/src`.

## Frame and OCR pipeline

The worker receives a video identity and a settings snapshot. OpenCV's FFmpeg backend seeks to requested samples (default 2 FPS), then reads decoder `CAP_PROP_POS_MSEC`; repeated timestamps are not emitted twice. FFprobe's media duration bounds processing. Missing/invalid decoder timestamps cause an actionable error rather than fabricated timings. OpenCV auto-orientation applies rotation before cropping. Seeking avoids exposing every frame to Python/OCR, though the codec may internally decode frames between keyframes.

The ROI is normalized relative to the actual oriented image. The editor computes the image's contained rectangle in the preview box; pointer positions are normalized only within that rectangle, excluding black bars. The backend applies floor/ceil pixel bounds and clamps to the frame. Numeric validation and keyboard movement remain available.

RapidOCR 1.4.4's self-contained wheel bundles Chinese PP-OCRv4 detection/recognition models and a classifier. A single engine is loaded lazily per worker. The application disables orientation classification for horizontal subtitles and uses two intra-operation threads plus one inter-operation thread. Execution is CPU-only by default, with no inference-time network/model downloads.

Recognition first uses a minimally resized crop with border padding. For weak/no text it tries grayscale CLAHE, retaining the original result if enhancement is worse. Uniform blank crops return empty. Latin/numeric-only lines are excluded; Chinese-containing lines retain mixed digits/punctuation. Reading order groups text lines vertically, then sorts boxes horizontally. Segment metadata retains the first observation's boxes in crop pixel coordinates.

Exact consecutive grayscale-crop equality permits observation reuse with a new timestamp. Any pixel difference runs fresh OCR; this conservative visual check avoids skipping subtle character changes. It is less effective on moving backgrounds. Metrics distinguish sampled frames, OCR calls (including fallback) and reused frames.

## Subtitle inference

Unicode, spaces and punctuation are normalized for comparison. Exact matches merge. Longer near-matches use a 0.82 similarity threshold and confidence-weighted text voting. Different high-confidence equal-length readings count as replacements. Confidence below 0.60 cannot start a subtitle; temporary uncertain observations can bridge up to 0.60 seconds. A confirmed empty observation closes a segment, so a later identical sentence starts separately.

Starts come from first accepted observations. Ends come from a change/disappearance observation, or the final accepted observation plus the sampling period, bounded by media duration. JSON explicitly identifies sampled visual timing and its uncertainty. At 2 FPS uncertainty is approximately 0.5 seconds. Shorter subtitles can be missed. Similarity remains heuristic: unstable OCR may split text, and very similar sentences may merge. Manual correction is expected for imperfect media. No speech or word timing is inferred.

## Persistence and concurrency

SQLite schema version 2 adds `analyses`, `subtitle_segments` and `active_analyses` without replacing the Phase 1 `videos`/`processing_settings` tables. Repository operations use separate short-lived connections, WAL, a busy timeout and transactions.

Jobs persist all five statuses, settings, engine identity, real progress, errors, metrics and timestamps. Completed results and their active pointer commit together. There is no progressive publication in this phase. Failed/cancelled reruns preserve the previous completed transcript. Startup marks interrupted jobs failed with a rerun message.

Cache identity includes video SHA-256, ROI/sampling settings, pipeline/configuration version, model/config hashes and RapidOCR/ONNX Runtime/OpenCV versions. Cached reads retain corrections. Force creates a fresh analysis identity; previous analyses remain stored and exportable by ID. Default numeric settings use canonical float values so saving/reloading does not change their identity.

A single `ThreadPoolExecutor` worker keeps inference off the HTTP event loop. At most eight jobs may be queued/running, one per video; each is limited to 100,000 requested samples. Cancellation sets an event and persists status under the same lock used for publication. Each frame and the final commit check that event. Native inference finishes its current call, but cannot publish after cancellation. Shutdown cancels and joins the worker.

The React workspace is keyed by video UUID. Polls carry both video and job identity, abort on switching/unmount and reject mismatched responses. Edits include expected analysis ID and revision, checked inside SQLite's write transaction. Overlapping times are rejected. A stale edit cannot silently apply to a newer transcript.

Run one backend process per library. Multiple Uvicorn workers or separate servers sharing one database are unsupported because queue ownership and restart recovery are process-local.

## Future language boundary

Segments retain Chinese text, confidence, original OCR text, visual timing and corrections. Phase 3 can add tokens, pinyin, definitions and translations without changing video/analysis ownership. Frame/OCR/subtitle services remain independent of React. No language feature, downloader, account or cloud service is simulated in Phase 2.
