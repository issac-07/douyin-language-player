# Douyin Language Player — Phase 4

**Language picker update:** a two-button English/Tiếng Việt switch with flags controls both sentence translations and selected-word meanings, including Vocabulary and empty-library views. Existing language choices follow the prior sentence language. See [behavior and validation](docs/LANGUAGE_PICKER_VALIDATION.md).

**Display controls update:** equal-width word status buttons; independent transcript Pinyin/Translation toggles; Chinese/Pinyin/Translate controls beside a styled Delete button; distinct selected-word colors, themed scrollbars and a light/dark Subtitle appearance panel. See [usage and validation](docs/DISPLAY_CONTROLS_VALIDATION.md).

**Word controls update:** three mutually exclusive New/Learning/Known buttons and a same-row Save/Saved toggle, with notes preserved on status changes and immediate unsave/resave. The speaker automatically uses Microsoft Xiaoxiao Online when exposed by the browser; no pronunciation/provider settings or model downloads. Paused transcript seeks remain synchronized. See [behavior, validation and limits](docs/WORD_CONTROLS_VALIDATION.md).

**V2.1 UI / v2---Update-UI:** dedicated Vocabulary page with search/status filters/notes, one sun/moon theme switch, warmer light colors, import below the player, and transcript pinyin + Chinese + selected sentence translation with continuous reading highlight through gaps. See [changes, usage, validation and limits](docs/V2_1_UI_VALIDATION.md).

**V2 UI / v2---Update-UI:** shared Paper Studio light and warm cinema dark themes, video-left / transcript-word-summary-library-right watch layout, ruby pinyin without visible transcript timestamps, expandable editing/dictionary tools and local-Mandarin pronunciation when a compatible OS/browser voice is installed. No Mandarin voice is currently available in the tested Edge installation; the button explains that limitation. See [layout, tests, usage and limitations](docs/V2_UI_VALIDATION.md).

**v4.8 UI:** a quieter workspace with collapsed import/error/processing details, compact live OCR stages, on-demand help, simplified language controls and bounded mobile transcript scrolling. OCR, translation and data behavior stay unchanged; the backend API remains 0.4.7. See [UI changes, usage and validation](docs/V4_8_UI_VALIDATION.md).

**v4.7 / OCR P1 improvements:** live stage/elapsed reporting during refinement, insertion/deletion merge fixes, direct Chinese→English or Chinese→Vietnamese sentence selection, separately labeled word meanings, Basic/Advanced OCR controls, hardware availability checks and local storage/explicit cache-history cleanup. The English model is installed locally; use `python scripts/setup_language_resources.py --translation-only --target en` for another installation. The OCR recognition model is unchanged and Fast showed no real-video skip benefit. See [validation, measurements, usage and remaining limits](docs/V4_7_VALIDATION.md).

**v4.6 / Fast-OCR:** per-video-frame subtitle synchronization, bounded decode prefetch, optional two-frame start-boundary refinement and 1/2/4 parallel Intel GPU OCR lanes. Buttons are now **Create / open subtitles** (cache-or-scan) and **Scan OCR again** (force). Old settings/corrections remain usable. GPU concurrency is opt-in and Fast is still experimental. See [measurements, tests and limits](docs/V4_6_VALIDATION.md).

**v4.5:** the header now shows the release label. To remove an imported video, select it and choose **Delete selected video**, then confirm. This removes the cached library copy and its transcripts/corrections, keeps the original source and saved vocabulary, and refuses deletion while imports/OCR are active. See [research and next OCR experiments](docs/V4_5_RESEARCH.md); this release does not change OCR performance algorithms.

**OCR performance update:** new videos default to Auto/CPU + Balanced (four ONNX threads, sequential sampling, unchanged 2 FPS). Existing saved settings and corrected transcript caches retain original behavior. Open **Subtitle analysis settings → OCR performance** to select Accurate, Balanced, or experimental Fast, and inspect the actual execution backend. Optional OpenVINO CPU/Intel GPU uses `scripts/start-backend-openvino.cmd` after isolated setup. See [measured results, limits and reproduction](docs/OCR_PERFORMANCE_VALIDATION.md). **Restore original CPU OCR** restores the original settings/cache identity. No extension was added.

A local React + TypeScript / FastAPI player with Chinese OCR and language-learning subtitles **inside the video**. Phase 4 adds anonymous Douyin URL import to the existing local library. See [Phase 4 validation](docs/PHASE4_VALIDATION.md) and [Phase 3 language/overlay validation](docs/PHASE3_VALIDATION.md).

**Live verified fix:** the supplied `v.douyin.com/CF6Py5zaDbs/` link successfully imported through **Use public-page import (isolated Edge)**: 46.1 MB, about 4m46s, 1920×1080 H.264/AAC. The direct yt-dlp API method still returns metadata HTTP 403. Public-page mode is explicitly opt-in and uses a new temporary session; it never reads your existing profiles/cookies or interacts with login/verification prompts. See the real results and limits in the [debug report](docs/PHASE4_IMPORT_DEBUG.md).

The [Phase 4 import investigation](docs/PHASE4_IMPORT_DEBUG.md) reviews upstream issues/PR #17826 and the implemented ordinary-public-page alternative. HTTP 403 is reported separately from explicit login, availability, network and compatibility failures. Expand **Diagnostic details** after a failed import for its actual stage/status. Older generic failures must be retried to obtain that evidence.

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
- Jieba words with source character offsets and context-aware tone-marked Pypinyin, displayed above their corresponding clickable Chinese words inside the video.
- A compact, adjustable Vietnamese sentence translation beneath those words, also inside the video. Position follows the displayed image and OCR region; no subtitle shelf or modified MP4 is created.
- Verified CC-CEDICT English definitions in the right sidebar, saved vocabulary with New/Learning/Known status and notes, and Anki-friendly vocabulary CSV export.
- Real CPU Chinese→Vietnamese Marian inference with model/text caching, manual sentence translation corrections and explicit unavailable/error states.
- Persistent appearance controls: three font sizes, vertical/horizontal position, opacity, color, shadow, per-line/all visibility, Interactive/Minimal modes and reset. Dictionary selection keeps playback going unless opt-in pause is enabled. Sentence replay/navigation and optional auto-pause are supported.
- Douyin standard URLs, short links and sharing text; a replaceable yt-dlp metadata adapter; anonymous HTTPS downloads with redirect/DNS checks and pinned public addresses, bounded retries, cancellation, progress and temporary-file cleanup.
- Packet integrity checks, full-duration validation, compatible-file preservation, remuxing or stream-selective H.264/AAC conversion; the existing import service owns hashing, deduplication and library publication. Titles, creators and canonical source associations persist in SQLite.
- URL/local import options, existing-player opening, reloadable job status and local-file fallback. Optional automatic OCR uses only a confirmed/saved region and existing analysis caches.

**Not implemented:** automatic storage quotas/purge, manual segment creation/merge/split, interval-only OCR reruns or AnkiConnect. No language data is fabricated. There are no accounts, cloud services or extension. URL imports never read existing browser cookies or credentials and do not implement custom signing/challenge workarounds, DRM/private/live content or fragmented/separate streams. Opt-in public-page mode keeps ordinary site cookies inside a fresh disposable Edge session.

## Windows prerequisites

Run from PowerShell in `D:\Projects\douyin-language-player`:

```powershell
python --version
node --version
npm.cmd --version
ffmpeg -version
ffprobe -version
```

Verified here with **Python 3.12.10, Node 24.21.0, npm 11.19.0 and FFmpeg/FFprobe 9.0**. Use Python 3.12 and Node 24 LTS for this pinned set. RapidOCR requires Python below 3.13. FFprobe inspects imports; FFmpeg checks URL-download integrity, converts incompatible streams and generates fixtures. Edge is used for browser tests. No Docker/GPU is required. OCR models arrive in the RapidOCR wheel; Vietnamese model/dictionary installation is an explicit setup step below. Playback and inference then work offline.

If a prerequisite is missing, install it using its official installer and reopen PowerShell. Dependencies below install only into this project. Commands use `npm.cmd` and the virtual environment's Python directly, so no PowerShell execution-policy change or environment activation is necessary. The Python launcher `py` was unavailable in the verified environment; use `python`.

## Install

```powershell
Set-Location D:\Projects\douyin-language-player
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r backend\requirements-dev.lock.txt
Set-Location frontend
npm.cmd ci --cache .npm-cache
Set-Location ..
.\.venv\Scripts\python.exe scripts\setup_language_resources.py
```

Python's complete tested dependency set is pinned in `backend/requirements-dev.lock.txt`; direct dependencies live in `requirements.txt` and `requirements-dev.txt`. The frontend has exact direct versions and `package-lock.json` for transitive versions. Installation and Douyin URL imports need internet access. Imported-file playback, OCR, dictionary and installed translation inference work offline. The downloader is pinned to **yt-dlp 2026.10.26**.

Stop any existing backend before updating resources. The lock includes the official CPU PyTorch wheel index. The setup script installs **125,405 CC-CEDICT entries** and the official **Helsinki-NLP/opus-mt-zh-vi** model under `data/resources`, preserving its pinned revision and file hashes in `local-model.json`. Translation weights are about 312 MB; CPU PyTorch is a separate dependency download. No CUDA, paid API, account or system-wide install is used. For a partial setup, the script supports `--dictionary-only` and `--translation-only`.

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

Use **Import from Douyin URL**, paste a public link or sharing text and choose **Import link**. Progress is measured when the server provides a byte length; otherwise it is indeterminate. **Cancel import** prevents library publication. A successful import opens the same player, with its original complete audio/video. Import options collapse to leave room for viewing; **Import another video** opens them again. Restricted/unavailable links show the reason and **Import a local MP4 instead**.

For the tested link, select **Use public-page import (isolated Edge)** before importing. This opens the official page normally in a temporary browser, then passes its actual public metadata into the existing downloader. It requires Node, the project's installed Playwright dependency and Microsoft Edge. The browser does not download the MP4 or export cookies; the existing safe downloader retrieves the accessible media after the browser closes. Direct cookie-free import remains the default.

**Analyze after import** uses the imported media's saved OCR settings. A new video needs a subtitle region first: open **Subtitle analysis settings**, choose/save its region and analyze normally. Identical media reuses the existing library entry and cached analysis. Downloading never guesses a region or starts OCR with an unconfirmed default.

Import your own MP4 with **Import MP4** or **Import Local MP4**, or generate the synthetic test fixture:

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

Sampling estimates subtitle visibility, not speech or word boundaries. At 2 FPS the uncertainty is approximately 0.5 seconds; shorter subtitles can be missed. OCR is offline preprocessing and can take minutes for long videos. Language processing adds word/pinyin data and cached Vietnamese translations after OCR.

## Learn while watching

After OCR completes, segmentation/pinyin become available and local translation runs in the background. Existing Phase 2 analyses can gain language data without rerunning OCR.

- The generated overlay contains **pinyin → clickable Chinese → Vietnamese** inside the actual video image. It defaults just above the saved OCR region, respects black bars, and stays inside the image when resizing/fullscreen. The original hardcoded pixels are unchanged and are not clickable.
- Click a generated Chinese word to update **Dictionary** in the right sidebar. The player dimensions and subtitle position stay fixed. On narrow screens the dictionary is a collapsible section below the player, never a video-covering modal.
- Use the **Subtitle appearance** sliders icon in the player controls for font sizes, offsets, color/opacity/shadow, visibility and display mode. **Minimal** hides generated Chinese while retaining pinyin/Vietnamese; select vocabulary from transcript words in that mode. Settings save locally to SQLite and work in fullscreen. **Reset to Defaults** restores compact defaults.
- **Save Vocabulary** stores the selected word, verified English dictionary entries, status and notes. Edit the wordbook from the **Vocabulary** tab and use **Export vocabulary CSV** for Anki/manual import. CSV is UTF-8 with standard quoting; formula-leading cell text is escaped for spreadsheet safety.
- Vietnamese is a **sentence translation**, not a Vietnamese word definition. Use **Edit Vietnamese translation** on a transcript row to correct it; the correction persists for that exact source text. Editing Chinese regenerates its tokens, pinyin and translation, without carrying an old translation onto changed Chinese.
- **Previous / Replay / Next subtitle** controls navigate sentences. Appearance settings offer opt-in pause on word selection and auto-pause at a subtitle end. Auto-pause follows media events, not word/audio alignment.

The selected Marian model is real and CPU-friendly, but can mistranslate slang, pronouns or names. Transcript translations are labeled as machine-generated and can be edited. English definitions are verified source entries, not invented Vietnamese glosses. Contextual pinyin/segmentation are also automatic and can be imperfect for ambiguous readings. See the validation report for actual quality examples.

## Tests and build

```powershell
.\.venv\Scripts\python.exe -m pytest backend\tests -q
Set-Location frontend
npm.cmd test
npm.cmd run build
npm.cmd run test:e2e
```

Or, from the root: `.\scripts\test.cmd`. Language tests require the local resources above. See [Phase 4 results and live test instructions](docs/PHASE4_VALIDATION.md), [Phase 3 results](docs/PHASE3_VALIDATION.md), [Phase 2 results](docs/PHASE2_VALIDATION.md), and historical [Phase 1 results](docs/PHASE1_VALIDATION.md).

The browser suite generates its fixture and launches isolated backend/frontend servers on **8011 / 5174**, with data under a unique `data\e2e\run-*` directory. It uses the already installed Edge browser (`channel: 'msedge'`), and does not install browsers or touch the normal library. Close other processes on those test ports before running. If Edge is absent, install it separately or configure Playwright to use a browser already available on your machine.

The suite retains all earlier import/playback/OCR/language checks and adds URL parsing, SSRF/address pinning, job transitions/retries/cancellation, media integrity/conversion, deduplication/persistence, precise diagnostics, public-page proxy/dispatch checks and import-to-learning integration. Current results: **160 backend tests passed (one optional OpenVINO-only skip), 11 frontend tests and 8 Edge tests passed**, plus TypeScript/build. The optional OpenVINO environment passed all **23 OCR performance checks**. Routine network responses are deterministic fixtures; separate Phase 4 real tests successfully downloaded the authorized link and verified its downstream workflow. Screenshots appear under `frontend\test-results` and `data\validation`; see the reports for exact paths and limitations.

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
| GET | `/api/videos/{id}/learning` | Segmented words, pinyin, translation status/results and analysis identity |
| POST | `/api/videos/{id}/learning/retry` | Retry failed/unavailable sentence translations |
| PUT | `/api/videos/{id}/subtitles/{segment_id}/translation` | Manual translation with expected analysis/revision/source text |
| GET | `/api/dictionary?word=今天` | Verified CC-CEDICT English entries, source and licence |
| GET / PUT | `/api/vocabulary` | List or save words, status and notes |
| DELETE | `/api/vocabulary/{word_id}` | Remove a saved word |
| GET | `/api/vocabulary/export/csv` | UTF-8 vocabulary CSV |
| GET / PUT | `/api/player-settings` | Persistent global appearance/playback preferences |

See [architecture and concurrency details](docs/ARCHITECTURE.md). Run only one backend process per library; multiple Uvicorn workers sharing this local queue/database are unsupported.

## Data and configuration

Defaults: `data\library.sqlite3` stores videos, jobs, source associations, subtitle corrections, language/translation caches, manual translations, vocabulary and player preferences; `data\media\<uuid>.mp4` stores imported MP4s. Schema version 4 adds URL job/source tables while preserving earlier records. Local uploads and compatible URL MP4s retain their original bytes; incompatible URL streams may be converted. Reimporting identical bytes reuses the entry. Analysis stays local. Original source files are never modified. Subtitle JSON exports include a `language` section; SRT remains the corrected Chinese transcript.

Set environment variables **before starting the backend** if needed:

```powershell
$env:DLP_DATA_DIR = 'D:\Projects\douyin-language-player\data'
$env:DLP_MAX_UPLOAD_MB = '512'
$env:DLP_MAX_DOWNLOAD_MB = '512'
$env:DLP_IMPORT_TIMEOUT_SECONDS = '900'
$env:DLP_FFMPEG = 'ffmpeg'
$env:DLP_FFPROBE = 'ffprobe'
$env:DLP_RESOURCE_DIR = 'D:\Projects\douyin-language-player\data\resources'
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
- **Douyin HTTP 403 / extractor compatibility:** expand **Diagnostic details** for the actual stage/status/version. HTTP 403 and fresh-session messages alone do not prove an account requirement. The direct official extractor still fails for the supplied link; the explicitly selected isolated public-page method succeeded. It never reads existing browser cookies or uses custom verification workarounds. Restricted links and missing prerequisites still have local MP4 fallback.
- **Port already in use:** stop the prior app instance or choose alternate ports and update the proxy and allowed origin together. Vite uses a strict port and does not silently choose another one.
- **Cached media missing:** reimport the original identical MP4 to restore its entry. The backend responds with 410 for a missing stored file.
- **Invalid region settings:** values are fractions of the video image, excluding black bars. Coordinates stay within 0–1, sizes are positive and the rectangle must fit. Saving settings alone does not run OCR.
- **No subtitles / unrelated text:** preview a subtitle and tighten the crop. The preserved Phase 1 default ends at 90% height; very low subtitles need the rectangle moved down. The supplied real video needed approximately `x=.10, y=.87, width=.80, height=.12`. Small text, movement and low contrast can reduce accuracy.
- **OCR dependency/DLL error:** use Python 3.12 and the pinned requirements, then restart. ONNX Runtime needs the Microsoft Visual C++ runtime; if a missing runtime DLL is reported, install the official Microsoft runtime separately. This project runs no system runtime installer.
- **Settings changed but old subtitles remain:** the previous completed transcript stays available until another analysis succeeds. Click Analyze; changing a crop does not silently start work.
- **Restart during OCR:** rerun the failed job. Partial observations are not advertised as a completed transcript.
- **Vietnamese/dictionary unavailable:** install the language requirements and run `scripts/setup_language_resources.py`, then restart the backend. No model downloads occur from playback requests. English dictionary data and sentence translations are independent; either can fail without preventing local playback.
- **Unexpected translation/pinyin:** review and correct OCR text first. The small local model has no broader conversation context and may produce inaccurate names/slang. Edit the Vietnamese sentence in the transcript. Dictionary entries list their actual alternate readings rather than invented definitions.
- **Overlay too high/low:** default placement is above the selected OCR rectangle. Tighten an over-large ROI or use the vertical slider; offsets are relative to video height and are clamped inside the displayed image. Very long text wraps and reduces effective size as needed to fit.
- **Large/slow imports:** the progress bar measures transmitted bytes; after 100%, the backend still checks/hash-inspects the file. The UI labels that inspection stage without inventing a percentage. The upload request has a five-minute frontend timeout and FFprobe has a 30-second inspection timeout.

## Documentation and licence notes

The interface and icons are original, inspired by [Miteiru](https://github.com/hockyy/miteiru). No Miteiru source/branding/assets are reused. RapidOCR bundles Chinese OCR models. The explicit resource setup downloads the attributed dictionary and translation model described here.

Implementation references checked for this environment: [FastAPI file uploads](https://fastapi.tiangolo.com/tutorial/request-files/), [Starlette file/range responses](https://starlette.dev/responses/), [Starlette's current test client](https://starlette.dev/testclient/), [Vite requirements](https://vite.dev/guide/) and [Playwright installation/browser support](https://playwright.dev/docs/intro).

OCR references: [RapidOCR upstream](https://github.com/RapidAI/RapidOCR), [the pinned self-contained distribution](https://pypi.org/project/rapidocr-onnxruntime/1.4.4/), and [OpenCV capture/timestamp/orientation properties](https://docs.opencv.org/4.x/d4/d15/group__videoio__flags__base.html).

Language references: [Jieba](https://github.com/fxsjy/jieba), [Pypinyin](https://pypinyin.readthedocs.io/zh-cn/master/usage.html), [CC-CEDICT / MDBG](https://www.mdbg.net/chinese/dictionary?page=cedict) ([CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/)), [Marian model API](https://huggingface.co/docs/transformers/model_doc/marian), and [Helsinki-NLP/opus-mt-zh-vi](https://huggingface.co/Helsinki-NLP/opus-mt-zh-vi) (Apache-2.0). Attribution is also displayed in the dictionary sidebar and vocabulary CSV. The derived dictionary database preserves the original entries; no dictionary edits are shipped.

Dependencies retain their upstream notices; see [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md). FFmpeg is separately installed and not redistributed here. The verified Gyan build reports GPL/version-3 features. Future redistribution of native libraries, models or browsers must retain applicable licences/notices. Synthetic test footage/audio/text are original. Windows fonts are not bundled.
