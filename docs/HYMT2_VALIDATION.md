# Hy-MT2 Q8 integration validation

Date: 2026-11-13. Original checkout: `D:\Projects\douyin-language-player`, branch `v2---Update-UI`. No commit/push, no worktree switch.

- Installed official `tencent/Hy-MT2-1.8B-GGUF`, revision `a0c709d9fac510f2c807aa3af52872340dc37a4a`, `Hy-MT2-1.8B-Q8_0.gguf` (1,908,528,192 bytes).
- SHA-256 verified: `5c3fe0b1408a5ceb0143184ef247b11b579c525f4b02b060e6c851bb76fef1a4`.
- Official llama.cpp b12347 Windows Vulkan archive also checksum verified. Runtime notices/licenses retained in extracted directory. Downloads remain under ignored data/resources.
- Model now defaults for Chinese→Vietnamese and Chinese→English; a single managed model process serves both. Legacy Marian is opt-in through environment, never a silent fallback.
- Existing cache keys include target/model/revision/quantization/runtime/prompt identity. Existing manual overrides retained. No OCR rerun or library migration required.
- Unit/integration: `python -m pytest backend/tests/test_hymt.py backend/tests/test_learning.py backend/tests/test_p1_improvements.py -q`: **18 passed**. Covers real OCR→translation, dictionary/pinyin/vocabulary, manual overrides, separate target caches, explicit failure and truncated output rejection.
- Frontend production build passed.
- Real Edge: `npx playwright test --project=phase3 --no-deps -g 'unified English/Vietnamese'`: **1 passed** (13.6s test). Video OCR, both translated overlays, reload persistence, dictionary and storage inventory verified.
- Final runtime flags (`--offline`, log verbosity 4) were separately verified with six real translations. Log reports Intel Arc 130T Vulkan0, **33/33 layers offloaded**; model buffer ~1,815 MiB, KV ~256 MiB, compute ~56 MiB. These are runtime buffers, not total application RAM or dedicated iGPU VRAM.
- Initial cold translation ~9.95s (includes startup/shader work); second run first request ~1.94s. Five subsequent short requests ~0.28–0.96s on second run. Small smoke sample, not a general throughput benchmark. Details in ignored `data/validation/hymt-smoke.json`.

Quality limit: `今天我们一起去吃饭` → `Hôm nay chúng ta cùng đi ăn nhé.`; `你在干什么？` → `Bạn đang làm gì vậy?`. However `苹果肌始终保持扁平` still mistranslates the facial term 苹果肌 as an apple/body muscle. No claim that all contextual errors are fixed. No neighbouring-sentence context, domain glossary, OCR correction, ASR, or larger model was added. The English translation also infers tense without context. Human review remains useful.

Runtime requests stay on authenticated loopback with no proxy and explicit offline mode. Loading/generation bounded to 120s, failed generation terminated before retry; process closed with LearningService shutdown. The model is lazy-loaded on first translation. Existing models, video library, OCR, dictionary and vocabulary files are preserved. The stock startup scripts now pick up Hy-MT2 automatically.

## Three-model picker update — 2026-11-13

Implemented in the same original checkout and branch. Previous uncommitted changes preserved; no commit/push.

- Explicitly installed `Hy-MT2-7B-Q4_K_M.gguf`, 4,624,648,896 bytes, official Tencent revision `ab8472660ac61fac25f1af43fac2599d52a8a775`. Verified SHA-256 `9f96256500f3fc1ab4d64336b58f52a949a95ad7516b0c229476eef782f9f77b` before publishing manifest. Model/runtime files remain in ignored `data/resources/hy-mt2-7b-q4km/`.
- Added persisted three-model picker above the video: original OPUS/Marian, Hy-MT2 1.8B Q8, Hy-MT2 7B Q4_K_M. Availability comes from backend catalog; unavailable models are disabled, with no automatic download/fallback.
- Requests and responses explicitly identify selected model; frontend rejects late responses from another model/language. Cache identities separate all three models and both target languages. Changing model keeps existing OCR analysis. Transcript source labels use the actual cached translation identity, rather than assuming selected model generated it. Manual corrections remain shared across models and labelled Edited by you.
- One inference worker serves all models/targets. On an uncached model change, previous backend process or Marian weights are unloaded before new inference. One in-flight sentence may finish; obsolete queued work is skipped. Cached translations do not require reloading a model.
- Processing elapsed time and video details use compact units (`330` seconds → `5m30s`). Seek clock/subtitle timestamp editing retain existing conventional formats.
- Added centered header inner container matching main's 1800px maximum width and responsive padding. Header background remains full width.

Validation:

- Relevant backend baseline: **18 passed** (`test_hymt`, `test_learning`, `test_p1_improvements`). New selection integration: **1 passed**, covering distinct caches, saved selection, manual overrides, invalid-model validation and catalog. Final targeted rerun: **5 passed** (selection + Hy-MT contract tests).
- Frontend production build passed; **14 unit tests passed**, including duration boundaries and `5m30s`.
- Real Edge `translation model selection, truthful source labels, cache reuse and centered header`: **1 passed, 39.4s**. Exercised all three real models, 7B Chinese→Vietnamese/English, retained OCR analysis ID, cached switch-back, persisted selection/reload, correct source labels. Measured matching header/main left and right content edges at widths 2560, 1920, 1000, 390 with no horizontal page overflow.
- Inspected light/dark screenshots saved under ignored `frontend/test-results/model-selection-{light,dark}.png`.
- 7B runtime log confirms **33/33 layers offloaded to Intel GPU/Vulkan**, model buffer ~4403 MiB. This is not total application RAM or dedicated VRAM.
- Restarted the original local backend after verifying zero active OCR/import tasks; live `http://127.0.0.1:8000/api/translation-models` reports all three available, frontend `http://127.0.0.1:5173` returns HTTP 200.

No model-quality guarantee added: sentence-only translation still lacks neighbouring-line/visual context. Existing 1.8B quality caveats above remain relevant.
