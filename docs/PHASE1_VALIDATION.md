# Phase 1 verification

Verified on Windows on 11 November 2026 (Australia/Sydney).

## Environment

- Python 3.12.10, with dependencies installed in the project `.venv`.
- Node 24.21.0 / npm 11.19.0, with dependencies installed in `frontend/node_modules`.
- FFmpeg / FFprobe 9.0, already installed on the machine.
- Existing Microsoft Edge browser, driven headlessly by Playwright.
- No system installation, execution-policy change, cloud deployment or downloaded model was required.

## Final results

The complete `.\scripts\test.cmd` launcher finished with exit code 0:

| Check | Result |
| --- | --- |
| Backend pytest suite | **21 passed**, no warnings |
| Frontend Vitest suite | **5 passed** |
| TypeScript check and Vite production build | **Passed** |
| Playwright real-browser suite | **2 passed** |
| `pip check` | No broken requirements |
| `npm audit --audit-level=high` | 0 reported vulnerabilities |

Both documented Windows startup scripts were also executed. FastAPI started on `127.0.0.1:8000`; Vite started on `127.0.0.1:5173`. The frontend returned HTTP 200 and its `/api/health` proxy returned `status: ok`, `ffprobe_available: true`, `ocr_available: false`.

## Playback evidence

The browser tests uploaded a real generated 8-second 360×640 MP4 through the frontend to the backend. The browser decoded a 360×640 video, advanced actual `currentTime` during play, held it while paused, sought to four seconds, applied 1.5× speed, muted, entered/exited fullscreen and responded to keyboard playback/seek commands. Reload restored the library entry and saved sampling settings. Reimport reused the stored video instead of duplicating it. A separate mobile check verified invalid MP4 rejection and no horizontal overflow at 390px width. No network/media API mocks were used.

Backend assertions additionally verified range byte equality against the original file, suffix ranges, unsatisfiable ranges, HEAD, complete file equality, invalid extensions/headers, unreadable media, upload limits including chunked requests, safe filenames, missing-FFprobe errors, missing-media restoration, SQLite restart persistence, ROI validation and cache identity changes.

Synthetic Chinese captions were visually checked on an extracted test-only preview at one second. This confirms that the fixture has burned-in Chinese text; it is not an OCR accuracy test.

## Limits

No user-provided media was available in the initially empty project. Playback is verified on the reproducible synthetic H.264/AAC fixture; arbitrary codec support still depends on the installed browser. Fullscreen/browser checks ran in Edge only. OCR, language processing, translations, vocabulary persistence and Douyin import are not implemented or verified in Phase 1. This validation does not claim that the full project MVP is complete.

Test servers are shut down by Playwright. Tests use isolated project-local data directories and do not seed the normal library with demo content. Temporary test data and screenshots remain under ignored `data/` and `frontend/test-results/` paths for inspection; they may be removed after the processes have stopped.
