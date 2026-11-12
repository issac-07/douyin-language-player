# Phase 4 import debugging and verified public-page fix

Investigated **12 November 2026, Australia/Sydney**, in the existing Windows project. No Phase 1–3 playback, OCR, subtitle, dictionary or vocabulary implementation was replaced.

## Outcome

**A real import of the authorized user link succeeded.** The direct yt-dlp API request still returns HTTP 403, but the new explicitly selected **Use public-page import (isolated Edge)** method retrieves the requested metadata through the ordinary official page and imports its accessible media through the existing pipeline.

The first successful run imported **46,100,815 bytes**, **285.882993 seconds**, **1920×1080 H.264/AAC**, without remuxing/transcoding, in **30.781 seconds** wall time. Its existing playback endpoint returned HTTP 206. A subsequent successful run using the actual per-request API option completed in **37.953 seconds**. These were real network downloads, not test fixtures. Final-second decoding and real OCR/pinyin/Vietnamese/right-sidebar dictionary checks were also exercised on the downloaded MP4.

The direct cookie-free method remains the default. Public-page import requires explicit selection and a fresh temporary Edge session. The user's existing profiles, cookies and credentials are never accessed. Website JavaScript executes normally; the app does not inject a signature implementation, interact with login/verification prompts, solve CAPTCHAs or alter account access.

## Root cause and original error

The installed official downloader is **yt-dlp 2026.10.26**. Its `DouyinIE._real_extract` requests `https://www.douyin.com/aweme/v1/web/aweme/detail/` with `aweme_id`, using `_download_json(..., fatal=False)`. It does not establish the ordinary webpage's session/request state.

The original authorized URL `https://v.douyin.com/CF6Py5zaDbs/` resolves correctly:

| Operation | Direct extractor result |
| --- | --- |
| Short URL | HTTP 302 to an official iesdouyin page |
| Official share page | HTTP 302 to `www.douyin.com` |
| Canonical video page | HTTP 200; ID `7688193503570005299` |
| Direct web-detail API request | **HTTP 403**, before any media URL |
| Media downloading | Not attempted because direct metadata extraction failed |

The app formerly turned every HTTP 401/403 into `access_denied` with a message implying anonymous/account restrictions. It also suppressed the original cause of missing/invalid metadata behind `anonymous_unavailable`. Explicit restricted metadata shared the access-denied label. These categories overstated what the evidence proved.

The app's `http.client` transport receives a response rather than a status exception, so its old original exception was its own `ImportFailure`. An isolated subprocess using **unmodified official yt-dlp and its standard transport** reproduced `HTTPError(403)` → nonfatal metadata warning → `ExtractorError`, **“Fresh cookies (not necessarily logged in) are needed”** → `DownloadError`. Thus the failure was not solely caused by the app's transport or frontend. Neither a 403 nor that generic fresh-session message proves that account login is required. No explicit geographic restriction was returned for this link.

A normal fresh Edge visit received metadata HTTP 200 and playable video. The official page sometimes uses a regional Douyin host such as `www-hj.douyin.com`; a direct unsigned request to that host also returned 403. Merely changing the API hostname was not a fix.

Evidence: [direct app/native comparison](../data/validation/phase4-debug/real-diagnostics.json), [direct import failure](../data/validation/phase4-debug/import-smoke.json), [ordinary page observation](../data/validation/phase4-debug/public-edge-page.json), [first real import](../data/validation/phase4-debug/public-edge-import.json), and [per-request API import](../data/validation/phase4-debug/public-edge-api-import.json).

## Upstream review

- [Issue #17981](https://github.com/yt-dlp/yt-dlp/issues/17981) describes metadata HTTP 403 followed by the fresh-cookies error; its discussion distinguishes this from an actual cookie check.
- [Issue #9667](https://github.com/yt-dlp/yt-dlp/issues/9667) documents the older generic error, including empty/invalid JSON despite supplied cookies. It remains open.
- The [official latest release](https://github.com/yt-dlp/yt-dlp/releases/latest) was still **2026.10.26** when checked. Inspected [official master](https://github.com/yt-dlp/yt-dlp/blob/master/yt_dlp/extractor/tiktok.py) retained the same direct request. Neither contains the proposed session/signature fix. No ineffective dependency upgrade or unreviewed fork was installed.

### PR #17826

The [PR](https://github.com/yt-dlp/yt-dlp/pull/17826) was **open and unmerged**, at `728fe46fbaa97d6f03efcaf9e766d4db63338b8d`. Metadata was last updated 9 November 2026; its latest commit was a 29 October merge from master. There were no formal submitted reviews. [The diff](https://github.com/yt-dlp/yt-dlp/pull/17826/files) changed one extractor file, 64 additions/6 deletions, without adding automated live extraction tests. All eight retrieved [checks](https://github.com/yt-dlp/yt-dlp/pull/17826/checks) passed, including core/static/workflow checks; this does not establish live compatibility. The legacy combined-status API had no legacy status entries and returned pending. Saved review metadata is `data/validation/phase4-debug/upstream-review.json`.

The author declares the original code available under **Unlicense**, consistent with yt-dlp. Licensing was not the blocker. The proposed code registers anonymous cookies, signs metadata requests and substitutes a server trace header for a value normally issued after verification. Its discussion expressly describes that substitution. The unmerged verification-related mechanism was not executed, copied into the app or installed. Upstream success reports were not represented as our test results.

The PR also supplies a Douyin Referer for CDN downloads. The app's existing safe downloader already sends that fixed Referer; that equivalent cannot repair the earlier metadata failure. The implemented alternative uses ordinary official-page execution through maintained **Playwright 1.65.0 / installed Microsoft Edge**, then the installed yt-dlp media parser, rather than the PR's custom protocol/signature changes.

[F2's crawler](https://github.com/Johnserf-Seed/f2/blob/main/f2/apps/douyin/crawler.py) was also reviewed: it expects cookie configuration and uses A-Bogus/X-Bogus managers, so it was not adopted as a verified cookie-free replacement. A simple mobile HTML probe found page state without usable `videoInfoRes`; no speculative HTML parser was shipped.

## Implemented fix and safety boundary

`DouyinImportRequest.use_public_page` defaults to **false**. The frontend exposes a clearly labeled checkbox describing the temporary session. The selected method is persisted on the job. Without that explicit selection, the original direct method runs and reports its actual result. Existing canonical-source/hash caches still avoid unnecessary downloading.

When selected, `PublicEdgeExtractor` launches a bounded Node helper using the already-installed project Playwright dependency and a **new disposable Edge session**. It opens only the canonical official video page. Cookies remain inside the browser: no cookies API, user profile import, cookie-file export, HTTP cookie forwarding or account credentials are used. The helper accepts only an HTTPS Douyin web-detail response whose returned video ID matches the requested ID. Only required public video fields cross the private stdout pipe, bounded to 16 MiB; headers, session state and raw error messages do not. The browser closes before media downloading.

The maintained installed Douyin parser normalizes those actual fields. Explicit private/friends/followers/deleted/live/DRM flags are rejected. The existing `SafeHTTPClient` downloads the selected progressive MP4 **without browser cookies**, with the fixed Referer, original byte/time limits and cancellation. FFprobe, full packet-integrity checks, complete-duration comparison, hash/deduplication, library storage, range playback and optional configured-ROI OCR are unchanged.

The browser's network traffic uses a temporary loopback **CONNECT proxy**, with no TLS interception or cookie/header inspection. It accepts only HTTPS port 443 on a reviewed fixed Douyin/ByteDance media/static-asset domain allowlist. All DNS answers must be public; numeric addresses are pinned and cached per session. Edge retains certificate/hostname verification. Redirects require another checked connection. Plain HTTP, local/private IPs, custom ports, credentials and other destinations fail closed. Chromium proxies implicit loopback destinations too; nonproxied UDP/WebRTC and QUIC are disabled. Service workers/downloads are disabled and unnecessary image/font/media resources are blocked in the metadata browser.

The proxy allows at most 64 concurrent tunnels, with a 96 MiB aggregate encrypted-traffic cap and the active job deadline. The helper has a 40-second metadata wait and a 60-second outer limit. Cancellation closes the browser/proxy; a stuck helper is terminated only through its still-owned process tree. Main downloaded media remains independently bounded by the existing limits. Unknown/new asset hosts fail closed until reviewed. Static asset suffixes were identified from the actual official page; an initial incomplete host list/connection limit caused timed-out tests before correction.

Automatic approval review initially rejected the fresh-session test under the prior cookie constraints. The user then **explicitly authorized the isolated public-page test**. Only after that authorization were the successful tests run. The implemented app makes this session-based method an explicit opt-in, rather than silently changing the default cookie-free behavior. The initial rejection is resolved; no blocked command was executed indirectly before authorization.

## Corrected error reporting

`import_diagnostics.py` records operation, numeric HTTP status, approved hostname, fixed endpoint label, exception class and fixed reason codes. It traverses yt-dlp's nested `exc_info` and causes. Jobs persist the failing operation, status, extractor version, method and up to 128 events; older JSON records remain readable.

| Evidence | Category |
| --- | --- |
| Site HTTP 403 | `site_http_403`, with no inferred account requirement |
| Endpoint HTTP 401 or explicit authentication requirement | `login_required` |
| Explicit geographic exception | `geographic_restriction` |
| Explicit unavailable/private video or missing public link | `video_unavailable` |
| Invalid/missing metadata, changed API or generic fresh-session error | `extractor_compatibility` |
| Unsupported extractor/URL | `unsupported_extractor`, `invalid_url`, `unsupported_platform` |
| DNS/connection/timeout | `network_error`, `timeout` |
| Media URL unavailable after metadata succeeded | `download_failure` |

A metadata API 404 is treated as a changed endpoint, not proof that a video was deleted. Browser failure does not invent a login/geographic explanation. Frontend **Diagnostic details** expose the recorded stage/status/version. Historical generic failures ask for a retry to obtain actual evidence; their old causes are not fabricated. Logs exclude raw messages/bodies/URLs/paths/queries/headers/cookies/credentials/signatures. Sentinel-secret regression tests verify sanitization.

## Validation

The complete `.\scripts\test.cmd` runner passed:

| Check | Result |
| --- | --- |
| Backend, including every earlier phase and new proxy/dispatch tests | **138 passed** (72.62 seconds) |
| Frontend Vitest | **11 passed** |
| TypeScript + Vite production build | **Passed** |
| Edge/Playwright | **8 passed** (about 1.6 minutes) |
| Dependency check | No broken requirements |

Routine network tests remain deterministic. The explicit public-page UI/API choice is exercised with a test-only injected provider; that is not used as proof of a real browser download. Separate authorized real runs above establish actual metadata/download/import success. Initial isolated failures were not hidden or replaced with fixtures.

The actual downloaded file was processed by the existing real OCR and language engines. A first broad ROI included the creator watermark, producing poor OCR samples. The crop was refined to the hardcoded dialogue area (`x=.10, y=.85, width=.80, height=.12`), excluding that watermark. The final run produced **80 dialogue subtitle segments** in approximately **99.4 seconds**. Real samples include `你看看这道题` and `不是你说让我过来当面教我吗`. Validation uses 0.5 FPS across the full clip; this is a functional check with approximately two-second sampling uncertainty, not a claim that every short caption is captured. No dialogue is invented from audio. Real OCR/translations can require correction.

The actual-file Edge check verifies final-second decoding, in-video pinyin/Chinese/Vietnamese, dictionary definitions in the right sidebar and no dictionary modal or JavaScript errors. Reports/capture: `data/validation/phase4-debug/imported-learning.json`, `live-import-learning-edge.json`, and `live-import-learning.png`. These are distinct from synthetic browser fixtures. The normal library's previous videos remain preserved.

## Windows use and reproduction

Use the existing project environment: Python 3.12, Node 24, FFmpeg/FFprobe and installed Microsoft Edge. Public-page mode also needs the project's existing **Playwright 1.65.0** Node dependency (`npm.cmd --prefix frontend ci` includes it). No new system installer, fork, paid API or Docker was used. The library remains modular if a future supported direct extractor fixes the API.

Launch the app in two terminals from `D:\Projects\douyin-language-player`:

```powershell
.\scripts\start-backend.cmd
```

```powershell
.\scripts\start-frontend.cmd
```

Open `http://127.0.0.1:5173`, paste the link, select **Use public-page import (isolated Edge)** and click **Import link**. Configure the OCR region before analysis. Existing settings/cache are reused for identical media. The direct method remains useful for supported links and does not launch Edge.

```powershell
# Direct-method root-cause reproduction; metadata comparison is read-only:
.\.venv\Scripts\python.exe -X utf8 scripts\diagnose_douyin_import.py --url https://v.douyin.com/CF6Py5zaDbs/

# Explicit isolated public-page import, using the actual per-request API option:
.\.venv\Scripts\python.exe -X utf8 scripts\smoke_douyin_import.py --url https://v.douyin.com/CF6Py5zaDbs/ --timeout 180 --public-edge-test --output data/validation/phase4-debug/public-edge-api-import.json

# Complete deterministic regression suite:
.\scripts\test.cmd
```

Optional actual-file validation after a successful report exists:

```powershell
.\.venv\Scripts\python.exe -X utf8 scripts\validate_imported_ocr.py
node frontend/scripts/validate-public-import-learning.mjs
```

Set `DLP_NODE` before backend launch only if Node is outside PATH. Existing media caps/deadlines still apply. Normal backend logs are under `data/backend-phase4-debug*.log`; restart an older backend to load the new request field.

## Remaining limits

One authorized public video was successfully imported twice through the new method; this is not a guarantee for every link, region or later site version. Login/private/DRM media and interactive verification remain unsupported. Missing Node/Playwright/Edge, changed site schemas/assets, denied requests or verification prompts return an error and preserve local MP4 import. A normal browser page can behave differently across sessions. No unmerged PR behavior is claimed as tested. The direct library method still fails with metadata 403 for the tested link. All browser-session activity is opt-in and isolated.
