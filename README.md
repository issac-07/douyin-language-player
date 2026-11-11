# Douyin Language Player — Phase 2

A local React + TypeScript / FastAPI workspace with real Chinese subtitle OCR. Phases 1 and 2 from `PROJECT_SPEC.md` are implemented; the full language-learning MVP is not complete yet. See [Phase 2 validation](docs/PHASE2_VALIDATION.md) for tests, measurements and limitations.

Implemented:

- MP4 file picker and initial empty-player drag/drop, real multipart upload with measured upload progress, format checks and FFprobe metadata.
- Local SQLite library, persistent imported media, SHA-256 deduplication, recent videos and restoration of missing media by reimporting the original file.
- Dark responsive player with real play/pause, seek slider, ±5-second seek, volume/mute, all six required speeds and fullscreen. Portrait videos retain their original aspect ratio and audio.
- Keyboard shortcuts: Space/K play/pause, left/right seek five seconds, M mute, F fullscreen. Controls keep their native keyboard behavior while focused.
- HTTP range/HEAD playback, actionable invalid-file/missing-codec/backend errors and a default 512 MiB per-file limit.
- Visual subtitle-region editor with drawing, movement, corner resizing, numeric controls and letterbox-aware normalized coordinates.
- OpenCV sampling (2 FPS by default), real offline Chinese PP-OCRv4 via RapidOCR/CPU ONNX Runtime, preprocessing fallback and duplicate merging.
- Background analysis with measured progress, cancellation, useful errors and results isolated by video and analysis identity.
- Persistent timestamped subtitles, text/time corrections, deletion, cache reuse, JSON/SRT export and synchronized Chinese text in the player.
- Backend and frontend tests, plus real Edge playback/OCR workflows using a reproducible Chinese-captioned MP4. A real user video was also analyzed.

**Not implemented:** pinyin, dictionary, Vietnamese translation, saved vocabulary, Douyin URL downloads, cache cleanup UI, manual segment creation/merge/split, or interval-only reruns. No language data is fabricated. There are no accounts, cloud services or extension.

## Windows prerequisites

Run from PowerShell in `D:\Projects\douyin-language-player`:

```powershell
python --version
node --version
npm.cmd --version
ffmpeg -version
ffprobe -version
```

Verified here with **Python 3.12.10, Node 24.21.0, npm 11.19.0 and FFmpeg/FFprobe 9.0**. Use Python 3.12 and Node 24 LTS for this pinned set. The selected self-contained RapidOCR distribution requires Python below 3.13. FFprobe is required for importing; FFmpeg generates test fixtures and can convert media manually. Edge is used for browser tests. No Docker or GPU is required. Chinese model weights arrive in the RapidOCR dependency wheel, with no first-run download or paid service.

If a prerequisite is missing, install it using its official installer and reopen PowerShell. Dependencies below install only into this project. Commands use `npm.cmd` and the virtual environment's Python directly, so no PowerShell execution-policy change or environment activation is necessary. The Python launcher `py` was unavailable in the verified environment; use `python`.

## Install

```powershell
Set-Location D:\Projects\douyin-language-player
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r backend\requirements-dev.lock.txt
Set-Location frontend
npm.cmd ci --cache .npm-cache
Set-Location ..
```

Python's complete tested dependency set is pinned in `backend/requirements-dev.lock.txt`; direct dependencies live in `requirements.txt` and `requirements-dev.txt`. The frontend has exact direct versions and `package-lock.json` for transitive versions. Installation needs internet access; the installed application does not.

## Launch

Terminal 1, from the project root:

```powershell
.\.venv\Scripts\python.exe -m uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8000
```

Terminal 2:

```powershell
Set-Location D:\Projects\douyin-language-player\frontend
npm.cmd run dev
```

Open the frontend:

```powershell
Start-Process 'http://127.0.0.1:5173'
```

Alternatively, run `.\scripts\start-backend.cmd` and `.\scripts\start-frontend.cmd` in separate terminals. Stop each with Ctrl+C. The scripts bind to loopback only. API health is at `http://127.0.0.1:8000/api/health`; interactive API docs are at `http://127.0.0.1:8000/docs`.

Import your own MP4 with **Import MP4**, or generate the synthetic test fixture:

```powershell
.\.venv\Scripts\python.exe scripts\generate_test_video.py
```

Select `data\fixtures\mandarin-test.mp4`. It is an eight-second 360×640 H.264/AAC video with generated color patterns, a quiet sine tone and three burned-in Chinese sentences separated by blank intervals. OCR tests decode this actual video and run the real model. Caption generation uses the installed Microsoft YaHei font; the font is not bundled.

## Extract subtitles

1. Import a video and pause on a frame with Chinese subtitles.
2. Expand **Subtitle analysis settings** below the player. Choose **Use current frame**.
3. Draw around the Chinese text in the preview. Drag the rectangle to move it; drag a corner to resize it. Black bars are excluded. Focus the rectangle and use arrows to move it (Shift moves faster), or enter numeric coordinates. Keep unrelated background text outside the crop.
4. Start with **2 samples/second** (configurable 0.25–10), then click **Analyze Video**. Settings are saved automatically. **Save settings** alone does not run OCR.
5. The progress display measures processed frames. Playback and video switching remain available. **Cancel analysis** prevents the job from publishing results, though a native model call may still finish internally.
6. Click transcript timestamps to seek. Extracted Chinese text follows actual video time; the captions button toggles it. **Edit subtitle** corrects text/start/end times; **Delete subtitle** removes a bad segment.
7. Export UTF-8 **JSON** for full metadata or **SRT** for other players. **Analyze Video** reuses an identical completed analysis, including corrections. **Rerun OCR** creates a fresh transcript; export corrections you wish to keep first. Failed/cancelled runs preserve the previous completed transcript.

Sampling estimates subtitle visibility, not speech or word boundaries. At 2 FPS the uncertainty is approximately 0.5 seconds; shorter subtitles can be missed. OCR is offline preprocessing and can take minutes for long videos. Pinyin, dictionary interactions and Vietnamese translation belong to Phase 3.

## Tests and build

```powershell
.\.venv\Scripts\python.exe -m pytest backend\tests -q
Set-Location frontend
npm.cmd test
npm.cmd run build
npm.cmd run test:e2e
```

Or, from the root: `.\scripts\test.cmd`. See [Phase 2 results](docs/PHASE2_VALIDATION.md) and historical [Phase 1 results](docs/PHASE1_VALIDATION.md).

The browser suite generates its fixture and launches isolated backend/frontend servers on **8011 / 5174**, with data under a unique `data\e2e\run-*` directory. It uses the already installed Edge browser (`channel: 'msedge'`), and does not install browsers or touch the normal library. Close other processes on those test ports before running. If Edge is absent, install it separately or configure Playwright to use a browser already available on your machine.

The suite retains Phase 1 import/playback checks and adds real frame/Chinese OCR tests, merging, blank/multiline images, timing, persistence/migration, cache reuse, edit conflicts, exports, in-flight cancellation and video switching. Screenshots appear under `frontend\test-results` as `player-desktop.png`, `player-mobile.png`, `ocr-workspace.png` and `ocr-workspace-mobile.png`. Synthetic OCR has known ground truth; arbitrary user videos still need review. No translation or live Douyin URL functionality is claimed.

## API

| Method | Path | Behavior |
| --- | --- | --- |
| GET | `/api/health` | Backend/FFprobe/OCR dependency availability and upload limit |
| POST | `/api/videos` | Multipart `file`; validated MP4 import, metadata and `reused` flag |
| GET | `/api/videos` | Imported video library, newest first |
| GET | `/api/videos/{id}` | Video metadata |
| GET / HEAD | `/api/videos/{id}/media` | Original MP4 bytes; range/206/416 support |
| GET / PUT | `/api/videos/{id}/processing-settings` | Validated normalized ROI and sample rate |
| GET | `/api/videos/{id}/preview?timestamp=1` | Actual JPEG preview with decoded timestamp header |
| POST | `/api/videos/{id}/analyses` | Start/cache analysis; body may contain `settings` and `force` (default false) |
| GET | `/api/videos/{id}/analyses/latest` | Latest job for this video |
| GET | `/api/analysis-jobs/{job_id}` | Persisted status, progress, error and metrics |
| POST | `/api/analysis-jobs/{job_id}/cancel` | Cancel queued/processing work |
| GET | `/api/videos/{id}/subtitles` | Current completed analysis and corrected segments |
| PATCH | `/api/videos/{id}/subtitles/{segment_id}` | Edit text/start/end with expected `analysis_id` and `revision` |
| DELETE | `/api/videos/{id}/subtitles/{segment_id}?analysis_id=...&revision=...` | Delete from the matching current transcript |
| GET | `/api/videos/{id}/export?format=json` | JSON or `format=srt`; optional `analysis_id` pins a completed analysis |

See [architecture and concurrency details](docs/ARCHITECTURE.md). Run only one backend process per library; multiple Uvicorn workers sharing this local queue/database are unsupported.

## Data and configuration

Defaults: `data\library.sqlite3` stores metadata, settings, jobs and subtitle corrections; `data\media\<uuid>.mp4` stores original uploaded bytes. Schema version 2 adds OCR tables without replacing Phase 1 video records. Reimporting identical bytes reuses the entry. Files and OCR stay local. The app uses no external fonts, artwork, telemetry or API calls. Media is copied into the library; the source is not modified.

Set environment variables **before starting the backend** if needed:

```powershell
$env:DLP_DATA_DIR = 'D:\Projects\douyin-language-player\data'
$env:DLP_MAX_UPLOAD_MB = '512'
$env:DLP_FFPROBE = 'ffprobe'
```

`DLP_DATA_DIR` can be another directory you choose; allow disk space for media and temporary upload spooling. Storage cleanup remains manual. Back up the database and media together while the backend is stopped. To reset the library, stop the backend and remove only that chosen data directory after backing up anything needed. Never remove your original sources.

Cache identity covers video SHA-256, region, sampling, pipeline/configuration version, model/config hashes, and RapidOCR/ONNX Runtime/OpenCV versions. Force creates a new analysis while retaining the prior transcript until success. Interrupted jobs become failed on restart. One job can be active per video, at most eight are queued/running, and each is limited to 100,000 requested samples.

The frontend proxies API requests to `http://127.0.0.1:8000`. Set `DLP_API_URL` in the frontend terminal if using another backend port. For a different frontend port, explicitly set backend `DLP_ALLOWED_ORIGINS` to a comma-separated list of permitted origins (defaults include localhost/127.0.0.1 on 5173 and 8000). This is an upload-origin guard; there is no account or network-facing authentication. Keep servers bound to loopback.

## Troubleshooting

- **npm.ps1 / scripts disabled:** use `npm.cmd` and the provided `.cmd` launchers. No system execution-policy changes are needed.
- **FFprobe unavailable:** add the installed FFmpeg `bin` directory to PATH, reopen the terminal and restart the backend, or set `DLP_FFPROBE` to the full executable path. Health checks expose this prerequisite.
- **Video codec unsupported:** MP4 is a container; browser support depends on its streams and your Windows/browser codec support. H.264 8-bit yuv420p plus AAC is the tested combination. The app reports media errors instead of substituting another video. Convert a separate copy with:

  ```powershell
  ffmpeg -i 'input.mp4' -c:v libx264 -pix_fmt yuv420p -c:a aac -movflags +faststart 'compatible-copy.mp4'
  ```

- **Backend unreachable / Vite proxy error:** start FastAPI first on 8000, check `/api/health`, then refresh the library or retry the upload.
- **Port already in use:** stop the prior app instance or choose alternate ports and update the proxy and allowed origin together. Vite uses a strict port and does not silently choose another one.
- **Cached media missing:** reimport the original identical MP4 to restore its entry. The backend responds with 410 for a missing stored file.
- **Invalid region settings:** values are fractions of the video image, excluding black bars. Coordinates stay within 0–1, sizes are positive and the rectangle must fit. Saving settings alone does not run OCR.
- **No subtitles / unrelated text:** preview a subtitle and tighten the crop. The preserved Phase 1 default ends at 90% height; very low subtitles need the rectangle moved down. The supplied real video needed approximately `x=.10, y=.87, width=.80, height=.12`. Small text, movement and low contrast can reduce accuracy.
- **OCR dependency/DLL error:** use Python 3.12 and the pinned requirements, then restart. ONNX Runtime needs the Microsoft Visual C++ runtime; if a missing runtime DLL is reported, install the official Microsoft runtime separately. This project runs no system runtime installer.
- **Settings changed but old subtitles remain:** the previous completed transcript stays available until another analysis succeeds. Click Analyze; changing a crop does not silently start work.
- **Restart during OCR:** rerun the failed job. Partial observations are not advertised as a completed transcript.
- **Large/slow imports:** the progress bar measures transmitted bytes; after 100%, the backend still checks/hash-inspects the file. The UI labels that inspection stage without inventing a percentage. The upload request has a five-minute frontend timeout and FFprobe has a 30-second inspection timeout.

## Documentation and licence notes

The interface and icons are original, inspired by [Miteiru](https://github.com/hockyy/miteiru). No Miteiru source, branding, artwork or dictionary data is reused. RapidOCR includes Chinese model weights; no dictionary or translation model is included.

Implementation references checked for this environment: [FastAPI file uploads](https://fastapi.tiangolo.com/tutorial/request-files/), [Starlette file/range responses](https://starlette.dev/responses/), [Starlette's current test client](https://starlette.dev/testclient/), [Vite requirements](https://vite.dev/guide/) and [Playwright installation/browser support](https://playwright.dev/docs/intro).

OCR references: [RapidOCR upstream](https://github.com/RapidAI/RapidOCR), [the pinned self-contained distribution](https://pypi.org/project/rapidocr-onnxruntime/1.4.4/), and [OpenCV capture/timestamp/orientation properties](https://docs.opencv.org/4.x/d4/d15/group__videoio__flags__base.html).

Dependencies retain their upstream notices; see [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md). FFmpeg is separately installed and not redistributed here. The verified Gyan build reports GPL/version-3 features. Future redistribution of native libraries, models or browsers must retain applicable licences/notices. Synthetic test footage/audio/text are original. Windows fonts are not bundled.
