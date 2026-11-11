# Phase 3 validation — in-video interactive subtitles

Verified on Windows on **12 November 2026 (Australia/Sydney)**. Implementation extends the Phase 2 player and OCR/database contracts. No login, cloud hosting or extension was added.

## Implemented

- Jieba segmentation with exact source offsets, sentence-context tone-marked Pypinyin and productive 一/不 tone changes. Source text/punctuation are preserved.
- Full local CC-CEDICT lookup, including simplified/traditional forms, alternative readings and verified English definitions. No Vietnamese word definitions or parts of speech are invented.
- Real CPU Chinese→Vietnamese inference with the official `Helsinki-NLP/opus-mt-zh-vi` Marian model, background processing, source/model cache keys, manual corrections and graceful failure/unavailable states.
- Saved vocabulary, New/Learning/Known status, personal notes, persistence and UTF-8 CSV export for Anki/manual import.
- A reusable `InteractiveSubtitleOverlay` **inside `.video-stage`**, with pinyin directly above each clickable Chinese word and Vietnamese underneath. No primary subtitle shelf exists below the video and no new text is burned into the source MP4.
- ROI-aware placement above hardcoded subtitles, actual contained-video bounds, responsive font sizing/wrapping, manual offsets and fullscreen support. Noninteractive overlay regions pass pointer events through; word buttons remain keyboard/pointer accessible.
- Persistent three font sizes, opacity, color, shadow, horizontal/vertical adjustments, each line/all visibility, Interactive/Minimal modes and Reset to Defaults. Preferences live in SQLite; the last video ID is remembered in browser storage.
- Dictionary details in the right sidebar only. Narrow screens use a collapsible below-player panel. Dictionary selection leaves playback and player dimensions unchanged unless opt-in pause is enabled.
- Sentence navigation/replay, opt-in word-selection pause, and optional auto-pause at subtitle boundaries. Fullscreen contains the player **and** sidebar so definitions do not become a video modal.
- Additive schema version 3. Correcting Chinese regenerates its language data; manual translation overrides cannot attach to changed text/revisions/analyses. Existing Phase 1/2 data remains usable.

See [ARCHITECTURE.md](ARCHITECTURE.md) for module/worker/cache details and [THIRD_PARTY_NOTICES.md](../THIRD_PARTY_NOTICES.md) for dependency/resource licences.

## Environment and installation

Python **3.12.10**, Node **24.21.0**, npm **11.19.0**, FFmpeg/FFprobe **9.0**, existing Microsoft Edge. Python dependencies are project-local. No GPU/CUDA, system runtime installer or execution-policy change was used.

```powershell
Set-Location D:\Projects\douyin-language-player
.\.venv\Scripts\python.exe -m pip install -r backend\requirements-dev.lock.txt
npm.cmd --prefix frontend ci --cache .npm-cache
.\.venv\Scripts\python.exe scripts\setup_language_resources.py
```

Stop an existing backend before updating resources, then restart it. Models/dictionary are downloaded only by this explicit setup command; inference uses local files. CPU PyTorch comes from its official CPU wheel index, recorded in the lock file.

Pinned language dependencies include Jieba 0.42.1, Pypinyin 0.55.0, Transformers 4.57.6, CPU PyTorch 2.9.1, SentencePiece 0.2.3 and Sacremoses 0.1.1. Direct `MarianTokenizer`/`MarianMTModel` loading was tested rather than relying on a translation pipeline API whose availability differs across Transformers major versions.

## Resource provenance

**Dictionary:** 125,405 CC-CEDICT entries from MDBG, **CC BY-SA 4.0**, original meanings preserved. Gzip SHA-256: `c4450a361f0659bb1bf152577d07cc45f65dc280616b68b23bafc6fec817155b`. Source/hash/attribution/licence are recorded in `data/resources/cedict-source.json`; the indexed local database is 15,261,696 bytes. Attribution is visible in the dictionary and vocabulary CSV.

**Translation:** official [Helsinki-NLP/opus-mt-zh-vi](https://huggingface.co/Helsinki-NLP/opus-mt-zh-vi), revision `67ea2dbfbaf13a16772a40346d3d72b59e591443`, Apache-2.0 according to its model card. The 312,087,009-byte weights and tokenizer/config files are installed under `data/resources/opus-mt-zh-vi`. `local-model.json` records individual file hashes and revision. Inference uses local files, CPU evaluation mode and deterministic beam search; no remote code/API is called.

## Final test results

The complete `.\scripts\test.cmd` launcher finished with exit code 0:

| Check | Result |
| --- | --- |
| Backend pytest, including all earlier phases | **50 passed** |
| Frontend Vitest | **11 passed** |
| TypeScript check and Vite production build | **Passed** |
| Edge/Playwright suite | **5 passed** |
| Separate real-user-video Edge probe | **Passed** |
| `pip check` | No broken requirements |

Reproduce:

```powershell
.\scripts\test.cmd
```

Or individually:

```powershell
.\.venv\Scripts\python.exe -m pytest backend\tests -q
npm.cmd --prefix frontend test
npm.cmd --prefix frontend run build
npm.cmd --prefix frontend run test:e2e
```

The browser suite uses isolated ports 8011/5174 and unique data directories. Phase 1/2 tests run first. Language tests upload and analyze real generated MP4s; no OCR, dictionary or translation API is mocked. Deliberate worker failure/cancellation unit doubles remain clearly isolated to those tests.

### Backend checks

Tests cover source reconstruction/character offsets, the specified example sentences, expected segmentation, tone-marked/contextual pinyin, 一/不 sandhi, actual CC-CEDICT definitions, unknown words, actual Vietnamese model inference, missing resources, OCR→language integration, cached results, manual translation persistence, regeneration after Chinese changes, stale edit rejection, saved-word deduplication/status/notes/deletion/CSV, settings persistence/validation, and prior import/OCR/cancellation/migration/export behavior.

Actual sentence processing returned `今天 | 我们 | 一起 | 去 | 吃饭`, including `一起 → yì qǐ`; contextual checks include 银行/行长, 一样 → yí yàng and 不对 → bú duì. Ambiguous/neutral-tone readings are still data-dependent rather than guaranteed correct.

### Edge UI checks

The five browser workflows cover:

- Original MP4 playback, import, seeking, speed, mute, fullscreen and reload behavior.
- Real OCR, visual ROI draw/move/resize, cancellation and safe video switching.
- Overlay ancestry inside the stage, pinyin alignment, actual Chinese/Vietnamese text and bounds above the ROI.
- Font-size changes, persistence, all-subtitle hiding/restoration, reset and Minimal mode. Minimal keeps pinyin/Vietnamese while transcript words remain selectable.
- Word pointer/keyboard selection, verified sidebar definitions, no dictionary dialog/modal, unchanged player dimensions, and continued playback by default.
- Vocabulary save/status/notes, actual CSV download and reload persistence.
- Opt-in pause on word selection, auto-pause at a subtitle end and sentence navigation.
- Portrait, landscape, fullscreen, a 390px mobile layout and long-caption wrapping without clipped text in the checked case.
- Manual Vietnamese correction immediately updating the active in-video sentence and surviving reload.

Screenshots were visually reviewed in Edge:

| Artifact | What it shows |
| --- | --- |
| `frontend/test-results/phase3-portrait.png` | Compact in-video words/pinyin/Vietnamese and right dictionary |
| `frontend/test-results/phase3-landscape.png` | Landscape source with original hardcoded text intact |
| `frontend/test-results/phase3-fullscreen.png` | Fullscreen player plus separate dictionary sidebar |
| `frontend/test-results/phase3-mobile.png` | In-video language overlay and collapsible dictionary below |
| `frontend/test-results/phase3-long-caption.png` | Wrapped long Chinese sentence and real local translation |
| `frontend/test-results/phase3-real-video.png` | Actual user video at 120s with word selection and right-side English definition |

Screenshots/test artifacts are local ignored outputs, not production demo data.

## Actual translation performance and quality

The existing isolated Phase 2 real-video validation library contains the completed 415-segment OCR analysis of the 928.169-second user MP4. Phase 3 processed those actual OCR texts without rerunning OCR or modifying the normal library.

Final fresh-cache run: **415/415 translations completed**, **70.238s** end-to-end language preparation. A subsequent full 415-segment cached request took **0.516s**. Timings include service/model loading, language preparation and polling; tests were also using CPU, so these are observations rather than guarantees. Individual warm short-sentence inference examples were around 0.18–0.27s. No GPU was used.

Raw report: `data/validation/run-9cdaa450257e419290e5b2676e818075/language-report.json`. Logs: `data/validation/phase3-language-final.log`.

Reproduce against an **isolated, inactive validation library**, not a currently running app database:

```powershell
.\.venv\Scripts\python.exe scripts\validate_learning.py `
  --data-dir data\validation\run-9cdaa450257e419290e5b2676e818075 --fresh
```

The `--fresh` flag clears only generated language/translation caches in that chosen validation library. It does not remove OCR segments or edit source videos. Omit it to inspect cache behavior.

Actual model output for 今天我们一起去吃饭 was `Hôm nay chúng ta sẽ cùng ăn tối.`; 你在干什么？ produced `Anh đang làm gì vậy?`. These are runtime outputs, not application literals. The first introduces a dinner nuance absent from the original. On the real slang sentence 老登你给我接电话, the model produced `Anh trả lời điện thoại của tôi, Billy.`: the name **Billy is not in the Chinese source**. This is a concrete quality limitation, not a verified translation. Other context-dependent pronouns/slang may also be wrong. Completed inference does not mean 415 translations were semantically validated. Machine translations are labeled and can be manually corrected.

### Real-video Edge review

The separate review script served the existing validated library on temporary ports 8012/5175, sought the actual MP4 to 120s, rendered real cached words/pinyin/Vietnamese above the original Chinese, selected 你, verified the English definition in the right sidebar, and checked that playback continued. It captured the design and stopped its temporary servers.

```powershell
Set-Location frontend
node scripts\validate-real-language.mjs `
  ..\data\validation\run-9cdaa450257e419290e5b2676e818075
```

This uses the existing local real-video cache. It does not seed the normal library or claim a live Douyin URL import.

## Launch and limits

From the project root, in separate terminals:

```powershell
.\scripts\start-backend.cmd
```

```powershell
.\scripts\start-frontend.cmd
```

Open `http://127.0.0.1:5173`. After an update, restart any old backend so the schema/API match the frontend. Background-server logs/PID, if this session replaces an existing app instance, remain under `data/backend-*.log` and `data/backend.pid` as documented in Phase 2.

For the current handoff, both existing OCR jobs were checked as completed before replacing the old Phase 2 backend. The frontend was started on 5173 after its previous instance was no longer listening. Phase 3 health/dictionary checks were verified through the backend and frontend proxy; existing videos/analyses were preserved. Refresh the open app to fetch the new language API. This background frontend's PID/logs are in `data/frontend.pid` and `data/frontend-*.log`; it can be stopped with `Stop-Process -Id ([int](Get-Content data/frontend.pid))` while that recorded instance is running.

Known limits: OCR timing retains its sampling uncertainty; pinyin/segmentation and small-model translations need review; very long captions may require smaller settings or a larger/fullscreen player. Cached language data does not improve an OCR mistake. A sentence exceeding model/token limits gets an error rather than silent truncation. Missing resources do not block video playback. Dictionary definitions are English, not Vietnamese word glosses. No external translation service, Douyin URL import, accounts, cloud, Chrome extension, AnkiConnect or manual add/merge/split workflow was implemented here.
