# v4.7 — OCR P1 improvements, language selection and storage

Implemented in the original `D:\Projects\douyin-language-player` checkout on `codex/ocr-p1-improvements`, branched at the Fast-OCR commit `5f0a9c8`. The original checkout was on `fix-v1` at that same commit when inspected. Existing uncommitted v4.6 files were retained and extended. No commit, push, extension, new checkout or worktree was created.

## Fixes and behavior

- The 98% symptom was caused by saving progress in the coarse sampling loop only. `refine_starts` subsequently processed many additional original frames with no progress writes. A worker heartbeat now persists elapsed time/current stage every 750 ms during model initialization, decoding/OCR and refinement, including an in-flight native call. It reports worker liveness, not a guarantee that a native call will finish. The UI clock advances separately and warns after ten seconds without a received worker update. No finish-time estimate is invented.
- Sampling percentage is explicitly labeled as the fraction of video sampled. Model initialization and refinement use an indeterminate progress bar with real segment counters. Completion/100% is published through the existing atomic SQLite result transaction. Language preparation has its own ready/total count after Chinese OCR results have been saved; it is not falsely included in the OCR percentage. Cancellation remains serialized with publication and preserves previous completed results.
- Confident insertions/deletions now split captions, including 我喜欢你 → 我不喜欢你, numbers and names. Previously only equal-length confident replacements overrode fuzzy similarity. An added/removed OCR line is checked against the following observation to avoid splitting a stable caption for a transient background detection. A confirmed line change retains the first observation timestamp. Moderate-confidence changes require a stable recent source consensus and a matching subsequent observation; the retained boundary remains the first candidate timestamp. Ambiguous short/low-confidence changes can still be merged. A structural candidate at end-of-input is retained conservatively rather than erased; noisy final single-frame detections can still survive.
- The OCR pipeline identity is versioned so newly computed results cannot reuse the old faulty merge algorithm's identity. Old records/corrections remain readable. A new successful analysis can change the active transcript; export corrections before starting a new analysis under a changed pipeline/settings identity.
- Timing refinement still checks adjacent original decoded frames. It reuses recognition only for pixel-identical consecutive crops; calls, reused refinement frames and refinement wall time are recorded separately. This is conservative and does not eliminate the expensive scan of changing backgrounds. It refines starts and shared adjacent boundaries, not every disappearance/end boundary.
- Per-presented-frame player synchronization and the existing ordered 1/2/4 GPU lanes were already implemented in v4.6 and are retained. No extra GPU concurrency is silently enabled.

## English and Vietnamese

- Separate persisted controls select sentence translation and word meanings. Sentences use direct Chinese→English or direct Chinese→Vietnamese local Marian models. Vietnamese sentence translation was already direct; it did not pass through English.
- Installed `Helsinki-NLP/opus-mt-zh-en`, revision `cf109095479db38d6df799875e34039d4938aaa6`. PyTorch weights are approximately 312 MB, with tokenizer/config files in `data/resources/opus-mt-zh-en`. The model repository identifies its license as CC BY 4.0. No TensorFlow/Rust duplicate weights were downloaded. The existing Vietnamese installation was preserved.
- Example actual English output for 今天我们一起去吃饭: “We're going to dinner today.” This verifies real inference, not general superiority over Vietnamese or correctness for slang/names.
- Target/model/revision/generation version participate in translation cache identity. English and Vietnamese manual overrides are stored separately; old Vietnamese overrides remain readable. APIs carry explicit target language to avoid a preference change redirecting a request. English and Vietnamese have separate single-worker translation queues so a long Vietnamese queue cannot block all English requests. Models load lazily; using both languages increases RAM use.
- CC-CEDICT entries remain verified Chinese-English source entries. Optional Vietnamese word output is explicitly labeled direct machine translation of the isolated Chinese word, not a Vietnamese dictionary definition or a translated English gloss. English definitions remain visible for source comparison.
- Exact dictionary misses can show verified component entries, separately labeled; these are never assembled into a fabricated full-word/name definition. Unknown names remain unknown, with manual notes/save available. No NER, name glossary or automatic Sino-Vietnamese name conversion was added.

## Basic and advanced controls

Basic presets explicitly change sampling: speed=1 FPS, balanced=2 FPS, timing=5 FPS plus refinement. All use the same existing model and portable Auto/ORT Balanced CPU policy. Fewer samples may miss short captions; more samples/refinement cost more time and do not guarantee recognition accuracy. Applying a preset preserves ROI and shows the resulting configuration. CPU/GPU/runtime changes appear as Custom. Switching control views alone does not change settings. Advanced controls retain ROI, sampling, CPU threads/runtime, backend, mode, timing and GPU requests. Unsupported OpenVINO choices are disabled after backend capability probing; availability refers to the backend Python runtime, not just installed hardware.

## Storage

Expand **Local storage / Dung lượng lưu trữ**, then **Check storage usage**. It reports actual configured paths, media bytes per video, database, dictionary/models, tests, browser-test data, validation and optional runtime. Groups are categories, not a complete disk inventory; database WAL/temp logs and other folders are not included in a total. Directory traversal excludes symlinks/junctions.

Explicitly confirmed cleanup can remove machine translation cache, token/pinyin cache, or inactive uncorrected OCR history. History cleanup preserves active analyses, edited captions and analyses with manual translation overrides. Cleanup refuses while OCR/translation work is owned by a worker. It does not delete media, dictionaries/models, saved vocabulary or external source videos. Existing selected-video deletion remains available with confirmation. SQLite freed pages are reused and may not immediately shrink the file. No automatic quota, scheduled purge, VACUUM, or test-artifact deletion was added. Repeated forced OCR still creates history until the user cleans it.

## Real-media measurements

Reproduce with the optional OpenVINO Python: `data/ocr-env/Scripts/python.exe scripts/benchmark_p1.py`. It reads the normal library only, processes the first eight seconds of each source at 5 FPS with the source's saved ROI, and writes `data/validation/v47-benchmark.json`. Two warm repetitions follow a first processing pass. Engines initialize once per configuration and are reused across the two sources; the second source's first pass is not a cold engine. Initialization and processing times are separate. No other test workload ran during this measurement.

| Configuration | 1920×1080 warm median s | 1280×720 warm median s |
| --- | ---: | ---: |
| Original CPU / seek / 2 threads | 14.322 | 2.477 |
| Balanced CPU / sequential / 4 threads | 7.895 | 1.320 |
| Fast CPU | 8.493 | 1.449 |
| GPU 1 lane | 4.463 | 0.806 |
| GPU 2 lanes | 2.720 | 0.538 |
| GPU 4 lanes | 2.043 | 0.395 |

40 sampled frames per source; 53 OCR passes for the 1080p clip and 61 for 720p. Per-frame text matched the Balanced control across every configuration. Fast reused **zero frames** on both sources and was slower than Balanced. No Fast speedup is claimed. GPU engine initialization measured 2.221/3.876/8.746 s for 1/2/4 lanes; more lanes remain opt-in and can hurt short/cold jobs. The two videos have different content/ROI, so this is not evidence that lowering resolution alone causes the measured difference. No full-video speed, device utilization, peak memory or human-labeled OCR accuracy claim is made. Summed inference work can overlap decoding and exceed wall time for parallel lanes.

## Validation and limits

- Full backend suite: **180 passed, 2 optional runtime skips**. Includes heartbeat during blocked refinement, cancellation preserving active data, negation/insertion/deletion/name/number regressions, storage retention, direct English inference and language-isolated manual overrides.
- Optional OpenVINO suite: **6 passed**, including real GPU serial/parallel equivalence and native refinement.
- Frontend: **11 unit tests passed**, TypeScript/Vite production build passed.
- Full Edge suite: **10 passed**. The complete ten-test suite passed again after the final language guards, layout and consensus changes. Checked playback/seek/fullscreen, ROI/OCR, cancellation, corrections, dictionary/vocabulary, English/Vietnamese switching and persistence, custom presets, storage inventory and Douyin import fixtures.
- Initial failures were retained during diagnosis: over-splitting a transient extra detected line; a too-specific English test that required “eat” when the real valid output was “dinner”; browser tests interacting with advanced-only fields before settings loaded; and an old version assertion. The implementation/test expectations were corrected and the relevant complete suites rerun.
- Screenshot: `frontend/test-results/v47-language-storage.png`. Browser tests and model/real-media runs use separate test/validation folders and do not publish into the normal library.
- Recognition remains RapidOCR 1.4.4 / bundled PP-OCRv4, including its existing raw/CLAHE low-confidence fallback and editable transcript. We researched PP-OCRv5/v6, but did not change OCR weights/runtime packages without a same-video human-ground-truth comparison. No universal accuracy or zero-delay guarantee, cross-frame recognition batching, general scene-invariant skipping, automatic name understanding or extension is claimed.

## Isolated real GPU job and normal application

`scripts/validate_p1_real.py` cut/imported an eight-second prefix into a new validation-only library and ran Intel GPU / Accurate / four lanes / timing refinement. Polling observed initializing → reading_and_ocr → refining → completed, with live elapsed/heartbeat updates during refinement. Result: 17 sampled frames, 22 refinement frames, 65 total OCR passes, two segments, 12.195 s elapsed, 7.144 s engine initialization and 2.959 s refinement. Exact-crop refinement reuse was zero on this real sample; no refinement speedup is claimed. Full report: `data/validation/v47-real-job.json`. This is not a rerun of the complete problematic 154-second video, nor a general proof against native-driver hangs.

The normal backend was restarted only after confirming zero active OCR/import jobs. It now reports 0.4.7 on port 8000; the original optional OpenVINO environment reports CPU and Intel GPU available. The normal frontend remains on port 5173. Refresh the browser to load v4.7. Normal library media and analyses were not replaced by validation results, and no normal cache cleanup was invoked.

## Sources reviewed

- [PaddleOCR recognition model documentation](https://github.com/PaddlePaddle/PaddleOCR/blob/main/docs/version3.x/module_usage/text_recognition.en.md): candidate model accuracy/speed numbers are benchmark-specific, not proof on these clips.
- [PaddleOCR pipeline documentation](https://github.com/PaddlePaddle/PaddleOCR/blob/main/docs/version3.x/pipeline_usage/OCR.md): newer model evaluations use differing datasets; do not directly compare their published percentages.
- [Official Chinese-English Marian repository](https://huggingface.co/Helsinki-NLP/opus-mt-zh-en/tree/main): direct language direction, weight size, files and license.
- [OpenVINO request ownership/async inference](https://docs.openvino.ai/2026/openvino-workflow/running-inference/inference-request/python-api-advanced-inference.html): existing independent lane ownership is retained; throughput and latency are different measurements.
