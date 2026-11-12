# Phase 4 validation — Douyin URL import

Verified on **12 November 2026 (Australia/Sydney)** in the existing Windows workspace. Phases 1–3 are preserved. No account system, cloud deployment or extension was added.

For the subsequent root-cause investigation, opt-in public-page method with successful real downloads, corrected error categories and **138 backend / 8 Edge** test results, see [PHASE4_IMPORT_DEBUG.md](PHASE4_IMPORT_DEBUG.md). The counts and failed live captures below describe the initial Phase 4 implementation run.

## Outcome

The real URL-import implementation is installed and integrated with the existing player/library/OCR/language pipeline. Deterministic network tests successfully import real complete MP4s through the actual yt-dlp extractor, FFmpeg/FFprobe and existing import service. Edge verifies playback, OCR, pinyin, Vietnamese, in-video interactive subtitles and right-side dictionary lookup on those imported files.

**No successful live Douyin download is claimed.** The user's public short link resolved correctly, but its anonymous metadata request returned HTTP 403. The application displayed its access-denied message and local MP4 fallback; it imported no substitute video. This is a platform-access limitation, not a mocked success.

## Implemented

- Standard `https://www.douyin.com/video/<id>` links, `https://v.douyin.com/<token>/` links, sharing text, and standard homepage `modal_id` links. Standard source URLs are canonicalized; legacy iesdouyin share URLs are accepted as redirect destinations. Unsupported platforms, malformed URLs, credentials, custom ports and ambiguous multiple links are rejected.
- Separate, replaceable `MediaExtractor` protocol and pinned yt-dlp adapter. Only the Douyin extractor is registered. Anonymous metadata and permitted complete progressive MP4 streams only.
- Persisted background jobs with pending/resolving/downloading/validating/importing/completed/failed/cancelled status, measured byte progress or an indeterminate bar, cancellation, bounded retries, errors and elapsed time.
- Controlled temporary downloads; FFprobe stream inspection; full packet-integrity check; announced-duration comparison; unchanged compatible MP4s; container-only remuxing and selective incompatible-stream transcoding for Edge. No trimming flags are used.
- Existing import service for MP4 validation, SHA-256, UUID storage and deduplication. Source title/creator/canonical URL and multiple source associations persist in additive SQLite schema version 4. Repeat canonical-source imports reuse a present local copy. Different source URLs with identical bytes reuse the same video and analysis caches.
- URL/local options above the existing workspace, job resumption after reload, cancel/error/fallback UI, metadata and opening in the existing player. Import inputs collapse after completion to leave viewing space. Source information appears in recents and player details.
- Optional analysis only with explicitly confirmed valid ROI/settings or saved settings on the reused/imported video. New videos guide the user to select a region. The existing OCR worker/cache is reused; no default ROI is silently treated as configured.

## Downloader investigation

Selected **yt-dlp 2026.10.26**, installed from PyPI and pinned in both direct and complete dependency files. The Python package is Unlicense. The adapter retrieves metadata; it never delegates network downloading or subprocess execution to yt-dlp.

The [pinned Douyin extractor source](https://github.com/yt-dlp/yt-dlp/blob/2026.10.26/yt_dlp/extractor/tiktok.py) requests the public web-detail endpoint and explicitly reports that fresh cookies may be needed when anonymous metadata is absent. That behavior was checked rather than assuming all Douyin URLs work. Its cookie-generation TODO is not implemented or worked around here. See the [official release](https://github.com/yt-dlp/yt-dlp/releases/tag/2026.10.26) and [PyPI package](https://pypi.org/project/yt-dlp/2026.10.26/).

[F2](https://github.com/Johnserf-Seed/f2) and its [Douyin API implementation](https://github.com/Johnserf-Seed/f2/blob/main/f2/apps/douyin/api.py) were examined as an open-source alternative. Its broader cookie/signature/device/proxy mechanisms do not provide a verified anonymous replacement within this task's access boundary, so it was not installed or represented as a working fallback. Public share-page data was also checked on the supplied video's official pages: HTTP 200 contained a verification script, with no embedded `_ROUTER_DATA`/`RENDER_DATA` video metadata. No unverified page parser, signing workaround, browser-cookie capture, paid API or challenge solver was added.

## Live tests

These used the production network client and real DNS/HTTPS, without fixture/extractor injection:

| Input | Result | Time |
| --- | --- | --- |
| User-provided `https://v.douyin.com/CF6Py5zaDbs/` | Resolved to `https://www.douyin.com/video/7688193503570005299`; metadata HTTP 403; `failed/access_denied`; zero media bytes; no library video | 2.109 s wall, 1.844 s worker |
| Published yt-dlp test URL `https://www.douyin.com/video/6961737553342991651` | Metadata HTTP 403; `failed/access_denied`; zero media bytes | 0.844 s wall |
| User link through the normal app in Microsoft Edge | Same canonical video and access-denied outcome; fallback visible; no JavaScript errors; 390 px responsive width check passed | 4.063 s worker in final capture |

Reports live under `data/validation/phase4-live-user-link.json`, `phase4-live.json` and `phase4-edge-live-user-link.json`. The Edge report is from the real app on **5173/8000**, not the isolated fixture server. Normal media and earlier analysis data remain present. Screenshots: [real Edge failure](../data/validation/phase4-edge-live-user-link.png) and [mobile](../data/validation/phase4-edge-live-user-link-mobile.png).

Access can vary by region, link lifetime and platform policy. These failures do not prove that every public URL is inaccessible, nor do deterministic successes prove current live availability. No live download throughput or long-video success figure is available from these runs.

## Automated checks

The complete `.\scripts\test.cmd` runner covers all earlier phases plus Phase 4:

| Check | Result |
| --- | --- |
| Backend pytest | 104 passed |
| Frontend Vitest | 11 passed |
| TypeScript + Vite production build | Passed |
| Microsoft Edge/Playwright | 7 passed |
| `pip check` | No broken requirements |

The 54 additional backend cases cover share text/URL parsing, unsupported schemes/hosts, credentials/ports, private/reserved IPv4/IPv6 and mixed DNS answers, redirect rejection before connection, actual TLS address pinning, anonymous headers, requested-video identity matching, state transitions, confirmed-ROI gating, full real-media import/range playback, hash/source deduplication, persistence, missing/denied anonymous metadata, transient retries, unknown lengths/byte limits, cancellation during download/validation/import, timeout, partial responses/mismatched lengths, corrupt packets despite matching length, full-duration remux/transcode, restart recovery and request/origin bounds. Auto-analysis dispatch is isolated with a mock in one unit test; the browser tests run actual OCR/translation.

Only HTTPS transport is replaced in routine URL tests. `backend/tests/douyin_fixture.py` supplies published-response-shaped JSON and an original generated MP4 to the real extractor. The production app has no environment flag for fake media. Playwright's explicit test app factory uses a fresh isolated library, then exercises actual decoding, OCR, installed CPU translation and dictionary data. The new fixture has distinct container metadata so earlier local-file tests cannot accidentally satisfy the new-media ROI test through deduplication.

The two new Edge workflows verify share text → import → the single existing player → full-duration decoding/playback → region selection → real OCR → pinyin/Vietnamese overlay → right dictionary; repeat import/cache reuse and persistence; unsupported platform/access denial; unknown-length progress; cancellation and local fallback. The earlier five browser tests still cover local import, portrait/landscape, responsive controls, seek/fullscreen, ROI editing, OCR corrections/export, overlay placement, modes/settings, wordbook and uninterrupted playback. Fixture-based design capture: [imported learning view](../data/validation/phase4-edge-import-learning.png) and [controlled access error](../data/validation/phase4-edge-access-failure.png).

The final combined run passed with backend tests at 40 seconds and Edge at about one minute, plus frontend checks (CPU load affects timing). The real 8-second fixture's complete URL-import-plus-learning browser workflow took 8.8 seconds in that Edge run; this includes local OCR and cached/local translation, not internet download performance. Actual video/audio duration was checked at about 8 seconds before and after conversion. Neither short fixture timing nor metadata checks constitute a successful long live-video download test.

## Security and operational limits

- Input domains are exactly `douyin.com`, `www.douyin.com` and `v.douyin.com`. Network page hosts are restricted to Douyin/iesdouyin suffixes; extractor/media hosts additionally allow `douyinvod.com`, `snssdk.com`, `amemv.com`, `zjcdn.com`, `bytecdn.cn`, with suffix boundaries. New delivery domains fail closed until reviewed.
- Every redirect is checked before connecting. All DNS answers must be public unicast addresses; private, loopback, link-local, reserved, multicast and mixed public/private answers fail. Numeric addresses are pinned to TLS sockets while certificates/hostnames are verified with SNI. Proxies and browser credential stores are unused. Returned HTTP media URLs are upgraded to HTTPS before any connection.
- At most five redirects, four active/queued jobs, one active downloader, three total attempts, 15-second connection/read timeouts, 10-second DNS wait, 16 MiB metadata response limit and 64 KiB submission body limit. Declared and actual media bytes are limited; unrequested partial responses fail. The effective media cap is the smaller of download and existing upload limits.
- Active-job deadline defaults to 900 seconds; queued waiting time is separate. Cancellation prevents final library publication immediately. FFmpeg work is stopped on cancellation/deadline. A running bounded FFprobe inspection may finish its current call (up to 30 seconds) before cleanup. Temporary directories are removed on completion/failure/cancellation and recovered on restart, with UUID and resolved-parent checks before recursive removal.
- All filenames are generated; shell commands are never built from URLs/titles. FFmpeg/FFprobe use argument arrays, fixed input format allowlists and `file,pipe` protocol restrictions. Signed CDN URLs and cookies are not persisted in source metadata or public errors.
- Compatible MP4s retain their exact downloaded bytes. H.264 8-bit + AAC/MP3 is accepted; incompatible streams may require lossy conversion (H.264 CRF 18 / AAC 192k), only where needed. FFmpeg must support the source codec. No claim is made for DRM, live playlists, separate audio/video, arbitrary CDN domains, browser-specific profiles beyond the tested formats, or restricted media.
- The current public extractor can be rejected by Douyin even when the video can be watched through its own website. The app never requests cookies, login, signing/challenge bypass or an external parsing service. Use the local MP4 fallback for authorized files when access fails.
- One backend process per library; multiple workers/shared-library processes are unsupported. Source cache reuse opens the existing local copy, even if the remote title/content later changes. Missing local media triggers a fresh download attempt.

## Windows install, launch and test

Existing environment: Python 3.12.10, Node 24.21.0, npm 11.19.0, FFmpeg/FFprobe 9.0 and installed Edge. Project-only dependencies were used; no system-wide settings or execution policy changed.

```powershell
Set-Location D:\Projects\douyin-language-player
.\.venv\Scripts\python.exe -m pip install -r backend\requirements-dev.lock.txt
npm.cmd --prefix frontend ci --cache .npm-cache
# Only if language resources are not already installed:
.\.venv\Scripts\python.exe scripts\setup_language_resources.py
```

Launch in two terminals (stop an existing instance first):

```powershell
# Terminal 1, project root
.\.venv\Scripts\python.exe -m uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8000
```

```powershell
# Terminal 2
Set-Location D:\Projects\douyin-language-player\frontend
npm.cmd run dev
```

Open `http://127.0.0.1:5173`. The existing `.\scripts\start-backend.cmd` and `.\scripts\start-frontend.cmd` remain valid. The normal backend was restarted with Phase 4; its PID/log files are `data/backend.pid`, `backend-phase4.log`, `backend-phase4-error.log`. The existing frontend serves the updated source. Neither test server replaces the normal library.

Configuration, set before starting the backend:

```powershell
$env:DLP_MAX_DOWNLOAD_MB = '512'
$env:DLP_IMPORT_TIMEOUT_SECONDS = '900'
# Existing upload cap also applies to URL imports:
$env:DLP_MAX_UPLOAD_MB = '512'
# Optional executable paths:
$env:DLP_FFMPEG = 'ffmpeg'
$env:DLP_FFPROBE = 'ffprobe'
```

Run deterministic tests:

```powershell
.\scripts\test.cmd
# Or individually:
.\.venv\Scripts\python.exe -m pytest backend/tests -q
npm.cmd --prefix frontend test
npm.cmd --prefix frontend run build
npm.cmd --prefix frontend run test:e2e
```

Opt-in live tests (network outcomes can fail; exit code 1 from the Python smoke test means no successful import):

```powershell
.\.venv\Scripts\python.exe -X utf8 scripts\smoke_douyin_import.py --url https://v.douyin.com/CF6Py5zaDbs/ --timeout 90 --output data/validation/phase4-live-user-link.json
# Normal 5173/8000 app must be running for this UI check:
node frontend/scripts/validate-live-import.mjs https://v.douyin.com/CF6Py5zaDbs/
```

The Python command isolates its library under `data/validation/phase4-live-<UUID>`. The Edge command uses the normal library and records the real success/failure; its UI-verification exit code does not mean the media download succeeded. Existing real-video Phase 3 validation remains documented separately.
