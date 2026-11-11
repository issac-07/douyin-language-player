# Phase 2 — OCR Subtitle Extraction Engine validation

Verified on Windows, 11–12 November 2026 (Australia/Sydney). Phase 1 was extended in place; this does not claim completion of the Phase 3 language-learning MVP.

## Implemented behavior

- Real OpenCV/FFmpeg-backed frame sampling, default 2 FPS, with decoder video timestamps and rotation-aware normalized cropping. Only requested samples reach OCR; codecs may decode additional internal frames when seeking.
- Actual JPEG preview and an accessible draw/move/corner-resize region editor. Pointer mapping excludes letterboxing/pillarboxing; numeric region controls and keyboard movement persist in the existing settings system.
- Real Chinese PP-OCRv4 via `rapidocr-onnxruntime==1.4.4`, `onnxruntime==1.31.1`, `opencv-python==4.13.0.92`, and `numpy==2.2.6`. Bundled models are installed in the project virtual environment. No inference service or first-run model download is used.
- Minimal-image OCR plus a CLAHE grayscale fallback, confidence filtering, reading order, multiline Chinese and numbers mixed into Chinese lines. Exact unchanged crops can reuse prior observations.
- Duplicate merging, transient low-confidence handling, change/disappearance detection and separate later repetitions. Segment text uses confidence-weighted votes. Timing represents sampled subtitle visibility and retains confidence and uncertainty metadata.
- One bounded local CPU worker with persisted statuses/progress/errors, cancellation checks, restart recovery and atomic result publication.
- Additive SQLite schema version 2, configuration/model-aware cache identity, corrected-subtitle persistence and revision/analysis guards against stale edits.
- Real Analyze/Rerun/Cancel controls, synchronized player captions, transcript seeking, text/time edits, deletion and UTF-8 JSON/SRT exports.
- No fabricated pinyin, dictionary entries, translations or URL downloads. No account, cloud or extension work.

Implementation and concurrency details are in [ARCHITECTURE.md](ARCHITECTURE.md). Installed library/model licence notes are in [THIRD_PARTY_NOTICES.md](../THIRD_PARTY_NOTICES.md).

## Environment and exact Windows commands

Python 3.12.10, Node 24.21.0, npm 11.19.0, FFmpeg/FFprobe 9.0, and an existing Microsoft Edge installation. No global installation or execution-policy change was made. The selected self-contained RapidOCR package supports Python below 3.13; use Python 3.12.

From the project root:

```powershell
Set-Location D:\Projects\douyin-language-player
python --version
node --version
ffmpeg -version
ffprobe -version
.\.venv\Scripts\python.exe -m pip install -r backend\requirements-dev.lock.txt
npm.cmd --prefix frontend ci --cache .npm-cache
.\.venv\Scripts\python.exe -m pytest backend\tests -q
npm.cmd --prefix frontend test
npm.cmd --prefix frontend run build
npm.cmd --prefix frontend run test:e2e
```

The existing `.\scripts\test.cmd` runs all tests/builds in sequence. Browser tests start isolated servers on ports 8011 and 5174, use a separate unique data directory, and shut down those servers afterward. The Phase 2 browser project depends on the Phase 1 project so the original empty-library playback test runs first. OCR integration is not mocked in the end-to-end test. Small worker failure/cancellation unit tests use explicit test doubles to make race conditions deterministic.

Run the application in two terminals:

```powershell
# Terminal 1, project root
.\scripts\start-backend.cmd
```

```powershell
# Terminal 2, project root
.\scripts\start-frontend.cmd
```

Open `http://127.0.0.1:5173`. Restart an already-running backend after installing the new dependencies; startup performs the additive database migration. Use one backend process per library.

## Automated results

| Check | Final result |
| --- | --- |
| Backend pytest suite, including original Phase 1 tests | **40 passed** |
| Frontend Vitest suite, including original playback tests | **11 passed** |
| TypeScript check + Vite production build | **Passed** |
| Edge/Playwright browser suite | **3 passed** |
| `pip check` | No broken requirements |

Coverage includes actual sampled video frames and Chinese recognition, crop pixel bounds, multiline/mixed-number text, blank images, repeated subtitle consolidation, disappearing/reappearing text, text changes, low confidence, sample uncertainty, SQLite migration/restart persistence, cache reuse after corrections, invalid/overlapping times, edit revision conflicts, exports, inference failure, and cancellation during an in-flight model call. Original upload, invalid-file, size-limit, range/HEAD, deduplication, playback, speed, mute, fullscreen and keyboard tests remain passing.

The real-browser OCR test draws, moves and resizes the crop on a portrait preview in a wide box, analyzes a real uploaded MP4, checks three Chinese segments, seeks through text and blank intervals, edits text/times, downloads both formats, reloads, verifies corrected cache reuse, cancels a rerun, and switches videos during another analysis. Completion of the second video's worker never changes the first video's transcript. It also checks the OCR workspace at a 390px mobile width. Screenshots are under `frontend/test-results/ocr-workspace.png` and `ocr-workspace-mobile.png`.

## Synthetic video: known ground truth

Generate and validate actual burned-in Chinese subtitles:

```powershell
.\.venv\Scripts\python.exe scripts\generate_test_video.py
.\.venv\Scripts\python.exe scripts\validate_ocr.py data\fixtures\mandarin-test.mp4
```

The eight-second 360×640 H.264/AAC video is generated locally from color patterns, a sine tone, and Chinese text. It uses the installed Microsoft YaHei font without copying/distributing that font. The generator is unchanged from Phase 1; OCR reads actual decoded frames rather than SRT fixture text.

At 2 FPS and ROI `(0.05, 0.60, 0.90, 0.30)`, final-pipeline validation returned:

| Visible interval | Actual OCR segment text | Generated start/end |
| --- | --- | --- |
| 0.5–2.5s | 今天我们一起去吃饭 | 0.500–2.500s |
| 3.0–5.0s | 你在干什么？ | 3.000–5.000s |
| 5.5–7.5s | 我不知道发生了什么 | 5.500–7.500s |

All three texts and sampled boundaries matched the fixture. The repeated frames became three segments rather than a segment per frame. Blank subtitle intervals created no segments.

Measured final run: **16 sampled frames**, **20 OCR calls** including fallback, **3 segments**, **7.116s OCR time**, **7.952s total worker time**, mean segment confidence **0.9577**. Raw report: `data/validation/run-7b9d889bb0fe4110a74e28017a073c81/report.json`. Measurements were taken while the longer real-video validation was also using CPU; they are observations, not performance guarantees. Total worker time excludes upload/hash and includes model initialization/decoding/OCR/merging. OCR time surrounds recognition/fallback plus associated result processing, and excludes initial model loading.

## Real user-provided MP4

The existing local library contains `FDown.vn_douyin_downloader_89cc.mp4`, stored as `data/media/3c7e8121-18c8-4987-b848-b8cd2bd3dd3f.mp4`: 171,806,212 bytes, 1920×1080, 30 FPS, H.264/AAC, duration **928.169 seconds**. Its existing content SHA-256 is `fec49fe431b887e532382b8bd30a3e4bd4cafea3d6a9eee1d73a7ddf1d371ead`.

Preview frames were checked at 30s and 120s. The 120s frame visibly contains Chinese text near the bottom. A tight region `(0.10, 0.87, 0.80, 0.12)` excludes most of the image and captures those subtitles. Validation imports a separate copy into an isolated `data/validation/run-*` library; it does not overwrite the existing video's metadata, settings or results.

Reproduce:

```powershell
.\.venv\Scripts\python.exe scripts\validate_ocr.py `
  data\media\3c7e8121-18c8-4987-b848-b8cd2bd3dd3f.mp4 `
  --roi 0.10,0.87,0.80,0.12 --fps 2
```

Final full-video run with the current **subtitle-v2.4** pipeline:

| Metric | Measured value |
| --- | --- |
| Video duration | 928.169s |
| Sample rate | 2 FPS |
| Decoded sampled frames | **1,857** |
| OCR calls, including fallback | **2,431** |
| Exact unchanged crops reused | 0 |
| Generated subtitle segments | **415** |
| OCR time | **431.849s** |
| Total worker time | **557.511s** (9m 17.5s) |
| Mean segment confidence | **0.9810** |

Raw final report: `data/validation/run-9cdaa450257e419290e5b2676e818075/report.json`. For example, actual OCR returned `妈妈说我注定会成为哥哥的妻子` at 0.5–3.5s, and `老登你给我接电话` at 120.0–121.5s. The latter matches the Chinese visible in the checked 120s preview. The moving footage did not permit exact-crop reuse; the frame/OCR counts make that explicit. Runtime depends on CPU, region size, sample rate, scene content and concurrent work.

No manually transcribed full-video ground truth was supplied, so this confirms real processing and usable extracted text, not a character-error-rate or timing-accuracy claim. Model confidence is not measured transcription accuracy. No live Douyin URL download was attempted or validated.

## Normal application handoff

An existing Phase 1 backend was still running on port 8000 while its Vite frontend ran on 5173. The old project backend was identified by its Uvicorn command and replaced with the project virtual environment's Phase 2 backend; the existing frontend was retained. The original video entry was preserved by migration. Validation results remain in isolated libraries, so no test/demo transcript was inserted into the normal library.

The replacement backend runs hidden, with its actual listening process ID in `data/backend.pid` and logs in `data/backend-stdout.log` / `backend-stderr.log`. Both the direct and frontend-proxied health checks returned `phase: 2`, `ocr_available: true`, and `ocr_error: null`. To stop that specific background instance from the project root:

```powershell
$backendPid = [int](Get-Content data\backend.pid)
$backendProcess = Get-CimInstance Win32_Process -Filter "ProcessId = $backendPid"
if ($backendProcess.CommandLine -like '*uvicorn app.main:app*--port 8000*') {
  Stop-Process -Id $backendPid
}
```

Subsequent launches with the documented `.cmd` scripts run in your terminals and stop with Ctrl+C as usual. Keep only one backend on port 8000.

## Known limits

- Sample timing has approximately one sampling-interval uncertainty (0.5s at 2 FPS), plus decoder frame granularity. It is not speech/word alignment. Short-lived text can be missed.
- Fuzzy merging and confidence filtering are heuristics. Similar phrases may merge, unstable recognition may split, and an empty OCR miss can close a segment. Corrections remain necessary on difficult footage.
- The preserved default ROI ends at 90% image height; subtitles lower than that require visual adjustment. Avoid watermarks/background text; isolated numeric/Latin-only captions are deliberately excluded by this Chinese subtitle pipeline.
- CPU preprocessing has measurable latency. Only exact unchanged crops reuse OCR; moving backgrounds usually do not. GPU acceleration is not configured.
- One CPU job runs at a time, up to eight can be queued/running, and each has a 100,000-requested-sample limit. Cancellation is cooperative between frames/after inference, not forced termination of a native call.
- Results publish at completion; progressive partial subtitles, interval-only reruns and manual add/merge/split are not provided. Forced reruns create fresh transcripts; export corrections first.
- The UI operates on the current completed transcript. Historical completed analyses remain in the database and exportable by analysis ID, without a history browser or cache cleanup UI.
- Test browser: installed Edge on Windows. Other browsers/codecs and every variable-frame-rate/rotation combination are not exhaustively validated; unusable decoder timestamps produce an error.
- No pinyin/dictionary/Vietnamese translation/vocabulary data exists yet. These remain Phase 3 rather than placeholders pretending to work.
