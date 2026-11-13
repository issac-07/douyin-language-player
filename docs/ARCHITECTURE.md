# Local architecture — Phases 1–4

## OCR performance update

`OCRPerformance` is optional inside the existing processing-settings JSON. Absent fields preserve the original two-thread ORT/seek/exact-reuse path and its cache identity; no database tables or schema version were changed. Newly unconfigured videos receive Auto/Balanced (ORT CPU, four intra-op threads, one inter-op thread). Accurate uses seeking and disables stroke reuse; Balanced uses sequential decoding and only original exact-crop reuse. Fast explicitly opts into experimental, fail-closed, high-contrast white-stroke reuse with a two-second verification deadline. Sample FPS and user ROI never change with modes.

`ocr_runtime.py` resolves policy and model/runtime/configuration identity before cache lookup. `openvino_backend.py` replaces only RapidOCR 1.4.4 detection/recognition inference sessions using the same bundled ONNX files, FP32 hints, preprocessing, CTC alphabet and postprocessing. It compiles explicit CPU/GPU devices and checks `EXECUTION_DEVICES`; Intel GPU never silently falls back. Classification remains disabled. OpenVINO is optional in an isolated environment and is not imported by ordinary ORT processing.

`SequentialFrameSource` grabs frames in order and retrieves only selected images. It emits actual decoded PTS, auto-rotates like the original source, checks cancellation between every decoded frame and bounds memory to current images. For VFR it selects the first frame at/after each sampling target, which can differ from the old seeking behavior; Accurate remains available. It never synthesizes media timestamps from average FPS.

The existing serial worker retains one engine keyed by backend/thread configuration, preserves cancellation/publication locking, and throttles progress-only SQLite writes to at most one every 750ms. Final transcript publication remains atomic. Execution metadata records requested/actual backend, threads, decoder, reuse algorithm, stage devices and fallback state. Existing completed transcripts and manual corrections stay active until a new job succeeds. Progressive transcripts remain deferred.

See [OCR performance validation](OCR_PERFORMANCE_VALIDATION.md) for the frozen-reference benchmark, actual measurements, quality checks, optional setup and current limitations. Language processing/translation is excluded from OCR benchmarks.

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

Segments retain Chinese text, confidence, original OCR text, visual timing and corrections. Frame/OCR/subtitle services remain independent of React. Phases 3 and 4 extend them as described below. Accounts and cloud services remain outside the implemented scope.

## Phase 3 language data and worker

`services/chinese_processing.py` uses one Jieba tokenizer and sentence-context Pypinyin. Tokens retain exact Unicode codepoint offsets and the source text, including punctuation/whitespace. Productive 一/不 tone changes are applied across word boundaries while preserving ordinal/serial-number readings. Polyphonic and neutral-tone choices remain dependent on linguistic data and can be ambiguous.

`services/dictionary.py` queries an indexed, read-only SQLite conversion of the full CC-CEDICT dataset, including simplified/traditional entries, alternate pinyin and original English definitions. It invents neither part-of-speech labels nor Vietnamese definitions. `scripts/setup_language_resources.py` downloads the upstream gzip, preserves its hash/source/licence and builds the local database. Dictionary attribution appears in the UI and CSV.

`services/translation.py` directly loads `MarianTokenizer` / `MarianMTModel` with Transformers 4.57.6 and CPU PyTorch 2.9.1, using `local_files_only=True`, fixed beam search and no remote code. The official model revision and file hashes are recorded in `data/resources/opus-mt-zh-vi/local-model.json`. Runtime requests never download weights. Missing models and inference errors return explicit status, not fabricated Vietnamese. Input limits reject rather than silently truncate.

`services/learning.py` keeps this work separate from OCR. Its single translation worker loads one model and caches output by source text + model/revision/generation configuration. A bounded in-memory set prevents duplicate concurrent translation work. `GET /videos/{id}/learning` returns words/pinyin immediately and schedules uncached translations; the frontend polls while results are pending. Unfinished persisted pending entries can be rescheduled after restart. Shutdown stops queue submission and waits for the active model call.

Schema version 3 adds `language_cache`, `translation_cache`, `translation_overrides`, `vocabulary` and `player_settings`. It preserves all earlier data. Manual translations match segment ID **and source text**; changing Chinese invalidates their use. Writes check active analysis/revision/source text inside the transaction. Language response ownership is checked against the currently displayed analysis and each segment's revision/text before it can render. Editing Chinese starts regeneration; prior text/model cache entries remain reusable for identical sentences.

Vocabulary stores actual dictionary entries, pinyin, status and personal notes, deduplicated by word. CSV uses standard quoting, UTF-8 BOM and spreadsheet-safe text. Player appearance/playback settings are global to the local library and validated by Pydantic; the React hook debounces and serializes writes, and only acknowledges the latest save. The last selected video ID is kept in browser storage.

## Phase 3 in-video UI

`InteractiveSubtitleOverlay` lives within `.video-stage`. It computes the `object-fit: contain` rectangle from the source dimensions and stage size. Its default bottom anchor is eight pixels above the saved OCR ROI; horizontal/vertical offsets use actual displayed image dimensions. Measured overlay size clamps it inside the image. Text wraps; oversized captions reduce effective font size to fit the available height. Requested font sizes and line visibility remain editable in the player settings menu.

Each generated Chinese word is a keyboard-accessible button with its own pinyin above it. Noninteractive layer areas have `pointer-events: none`; only Chinese word buttons receive pointer events. Word clicks stop propagation and update the sidebar, leaving playback alone unless explicitly enabled. Minimal mode disables/removes the generated Chinese hit targets; transcript tokens remain selectable. The original hardcoded pixels are never annotated with fake hit targets or rewritten.

`DictionaryPanel` and `VocabularyPanel` occupy the fixed secondary grid column, so selection does not resize the player or move subtitles. On narrow screens they flow below the player; dictionary details are collapsible. Fullscreen requests the entire learning workspace, keeping a sidebar beside the actual video rather than placing a dictionary modal inside it. Appearance controls remain inside the player and constrain their own menu to its bounds.

The main generated language display is never a shelf below the video. The transcript remains a secondary editing/navigation view. Machine translation is labeled separately from verified dictionary definitions and personal translation overrides. Raw model quality is not assumed to be factual accuracy.

## Phase 4 URL imports

`POST /api/imports/douyin` validates a `DouyinImportRequest`, extracts exactly one supported HTTPS link, and enqueues it in `DouyinImportService`. `GET /api/imports`, `GET /api/imports/{id}` and `POST /api/imports/{id}/cancel` expose persisted status. A separate single-worker executor accepts at most four pending/running imports; OCR/translation keep their existing queues. Jobs transition through pending, resolving, downloading, validating, importing and completed, or terminate as failed/cancelled. Transient failures retry up to three total attempts with cancelable backoff under a single active-job deadline. Startup marks interrupted imports failed and removes only their verified UUID temporary directories. Run one backend process per library.

`douyin_urls.py` normalizes the accepted standard, modal and short-link forms. `MediaExtractor` is the replaceable boundary: canonical URL + safe client → allowlisted metadata + progressive media URL. `YtDlpExtractor` registers only the pinned Douyin extractor and overrides all network I/O. yt-dlp does not download, load browser cookies, use proxies/netrc, execute external downloaders or persist signed CDN URLs. No production fixture/fake-success mode exists. Test-only transport injection is available on the app factory; fixtures live under `backend/tests` and only the isolated Playwright server imports them.

`SafeHTTPClient` follows at most five redirects after the initial request. Every destination is checked for scheme, credentials, port and permitted host suffix, then all DNS addresses are checked for public unicast routability. The TLS socket connects to the validated numeric address with certificate/hostname verification and the original hostname as SNI; it never resolves that host again while connecting. Thus validation and connection cannot diverge through DNS rebinding. Short-link navigation uses only Douyin/iesdouyin hosts; extractor/media hosts additionally allow specific ByteDance CDN suffixes. Each redirected connection is revalidated. HTTP media URLs supplied by the extractor are upgraded to HTTPS; no insecure HTTP connection is made. Request headers exclude cookies, authorization and arbitrary remote headers. HTTP 401/403, challenge/unsupported responses and missing anonymous media produce explicit fallback errors.

Downloads stream into `data/downloads/<job UUID>/download.media`, with response-byte limits even when length is unknown. Metadata bodies are independently limited to 16 MiB. Unrequested partial responses, mismatched declared lengths and corrupt/truncated packets cannot publish. FFprobe reads real stream properties; FFmpeg walks every selected packet without re-encoding to detect incomplete files. All FFmpeg/FFprobe calls use argument arrays, fixed input formats and only local file/pipe protocols. There are no duration-cutting flags. Compatible H.264 8-bit/AAC-or-MP3 MP4s stay byte-identical; other containers are remuxed and only incompatible video/audio streams are transcoded. Conversion is size/time/cancellation bounded and its full duration is checked again.

The resulting file enters the existing `import_video` upload service via a file-backed `UploadFile`. That service retains MP4 validation, hashing, duplicate detection and UUID storage. Optional cancellation checks and a publication guard serialize final library publication with cancellation. SHA-256 reuse preserves all existing OCR/language data. Additive schema version 4 adds `import_jobs` and `video_sources`; existing video JSON gains optional source/title/creator fields with backwards-compatible defaults. Canonical-source cache hits avoid repeat downloads when the media file exists. Multiple source URLs can associate with the same content hash.

Automatic analysis runs only when the request explicitly confirms valid processing settings or the imported/deduplicated video already has saved settings. It calls the existing `AnalysisWorker.start(force=False)` and therefore reuses completed analysis caches. OCR errors do not turn an otherwise valid media import into a failure. Unconfigured new media gets a region-selection message.

React's `DouyinImportPanel` polls the independent job ID, aborts polling on unmount, resumes a remembered job after reload, and passes completed videos into the existing `App` library/selection state. It renders measured bytes or indeterminate progress and leaves existing playback/OCR/language/sidebar components in place. Completion collapses the input controls for viewing space. It creates no second player or subtitle shelf.

`import_diagnostics.py` records bounded typed facts at each import operation. HTTP status is retained independently of interpretation; 403 does not become a login requirement. Explicit authentication, geo, unavailability, unsupported extraction, compatibility, network and download failures are distinguished. Raw yt-dlp warning/exception text and response data are never logged; only class names and fixed reason codes survive. Job JSON stores the failing operation, HTTP status, installed extractor version and up to 128 events, preserving old records through defaults. Old undiagnosed failures are not retroactively assigned a new cause. See [the debug investigation](PHASE4_IMPORT_DEBUG.md) for real upstream traces and the decision not to adopt an unmerged verification-related workaround.

An explicitly selected `use_public_page` request uses `PublicEdgeExtractor` instead of the default direct extractor. It launches the maintained project Playwright/Edge runtime with a fresh disposable profile and ordinary official-page JavaScript. Only matching public video metadata is read; session cookies remain inside the browser. No account, existing profile, custom signature or challenge interaction is used. A per-job CONNECT proxy validates HTTPS destinations against a fixed site/asset allowlist, rejects private DNS, pins numeric public addresses and bounds connections/traffic/time while Edge retains TLS verification. Loopback proxy bypass and direct UDP/QUIC are disabled. Private/deleted/live/DRM flags are rejected. The browser closes before the same safe cookie-free media downloader, parser/validator and library importer run. The method defaults off and is disclosed beside its checkbox. Real authorized imports through this method succeeded; details and limits are in the debug report.
