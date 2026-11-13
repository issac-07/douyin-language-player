# OCR performance validation — local MP4 only

Measured 12 November 2026, Australia/Sydney, in the existing `D:\Projects\douyin-language-player` checkout at `31da9f3` plus the working changes described here. No commit/push, new worktree, driver installation, global PATH/power-setting change, downloader rewrite or extension was performed. Another existing detached worktree was observed and left untouched.

## A. System and inference stack

- Windows 11, build 26300; Python 3.12.10; Intel Core Ultra 5 225H, 14 logical CPUs. User target configuration: 32 GB RAM/NVMe Lenovo 83JK. RAM capacity and thermals were not independently measured because CIM access was denied.
- OpenVINO discovery: CPU `Intel(R) Core(TM) Ultra 5 225H`, GPU `Intel(R) Arc(TM) 130T GPU (16GB) (iGPU)`, NPU `Intel(R) AI Boost`. The 16GB device label is shared-memory reporting, not dedicated VRAM. NPU inference was not attempted.
- Existing graphics driver, read from the display registry: **32.0.101.8801**. No driver was changed.
- Observed Windows power scheme: **Balanced**, AC power connected, battery 100%. No system setting was changed. Edge, Task Manager, ChatGPT, editors and messaging apps were open. A one-second process snapshot showed the benchmark Python process consuming 4.125 CPU seconds and Edge/Task Manager 0.359/0.281. This is an observation, not a controlled idle-machine guarantee.
- `rapidocr-onnxruntime==1.4.4`, `onnxruntime==1.31.1`, `opencv-python==4.13.0.92`, `numpy==2.2.6`. Neither `rapidocr` nor `rapidocr-openvino` was installed. The latest RapidOCR interface was not substituted for the installed API.
- Optional **OpenVINO 2026.4.0** and telemetry dependency were installed only into `data/ocr-env`. That environment imports the project's existing dependencies through a `.pth` file; its NumPy was pinned back to 2.2.6 before comparisons. The working `.venv` was not modified. Telemetry emitted access warnings and stated that no data would be sent; no permission/global-directory change was made to silence them.
- Detection: `ch_PP-OCRv4_det_infer.onnx`. Recognition: `ch_PP-OCRv4_rec_infer.onnx`. Bundled `ch_ppocr_mobile_v2.0_cls_infer.onnx` contributes to the original model identity but classification is **disabled**, as before. Recognition retains the original model's CTC alphabet and line batching.
- Original engine identity includes SHA-256 of config plus all three model files and exact library versions. Individual ONNX SHA-256 values are recorded in each newer raw JSON's `system.models`, e.g. `data/ocr-bench/combined-ort-real.json`. Original source hashes are recorded in `original_source_hashes`.

| Model | SHA-256 |
| --- | --- |
| PP-OCRv4 detection | `d2a7720d45a54257208b1e13e36a8479894cb74155a5efe29462512d42f49da9` |
| PP-OCRv4 recognition | `48fc40f24f6d2a207a2b1091d3437eb3cc3eb6b676dc3ef9c37384005483683b` |
| Bundled classifier (disabled) | `e47acedf663230f8863ff1ab0e64dd2d82b838fceb5957146dab185a89d6215c` |

The official sources reviewed were [RapidOCR](https://github.com/RapidAI/RapidOCR), [ONNX Runtime threading](https://onnxruntime.ai/docs/performance/tune-performance/threading.html), [OpenVINO installation](https://docs.openvino.ai/2026/get-started/install-openvino/install-openvino-pip.html), [system requirements](https://docs.openvino.ai/2026/about-openvino/release-notes-openvino/system-requirements.html), [Intel GPU configuration](https://docs.openvino.ai/2026/get-started/install-openvino/configurations/configurations-intel-gpu.html), and [CPU scheduling](https://docs.openvino.ai/2026/openvino-workflow/running-inference/inference-devices-and-modes/cpu-device/performance-hint-and-thread-scheduling.html). Actual installed source and successful inference determined compatibility.

## B. Reproducible baseline and isolation

`scripts/benchmark_ocr.py` freezes the original OCR, frame source and subtitle detector directly from Git commit **31da9f3** into a fresh isolated output directory. Original output is saved before comparisons. Every repetition uses a fresh SQLite database, new video/job/segment identities, and fresh decoding/OCR. Model instances are retained for warm repetitions. No analysis cache is returned. The normal library, media, corrections, settings, language caches and vocabulary are never opened for writing by this harness. The source MP4 is read directly without copying or modifying it.

Datasets:

| Dataset | Source / analyzed duration | Resolution | ROI x,y,w,h | Sampling | Frames / segments |
| --- | --- | --- | --- | --- | --- |
| Original generated portrait fixture | 8s / full 8s | 360×640 | .05,.60,.90,.30 | 2 FPS | 16 / 3 |
| Authorized existing real MP4 `3c7e8121-18c8-4987-b848-b8cd2bd3dd3f.mp4` | 928.169s / **first 30s only** | 1920×1080 | .10,.87,.80,.12 | 2 FPS | 60 / 9 |

Real source SHA-256: `fec49fe431b887e532382b8bd30a3e4bd4cafea3d6a9eee1d73a7ddf1d371ead`. This is the previously authorized and validated user MP4, not unrelated private media. No new real Douyin download was needed. Results below are **not** a measured speedup for the entire 928-second video.

Original configuration: two ORT intra-op threads, one inter-op thread, CPU execution, OpenCV default 14 threads, per-target timestamp seeking, exact grayscale-crop reuse, minimally resized/padded input, original CLAHE fallback, unchanged confidence/merge thresholds. The OCR model, ROI, sampling and postprocessing remained fixed during backend comparisons.

Original full-fixture warm times: **3.3824, 3.1442, 3.1430s**, median **3.1442s**. Cold end-to-end: **7.1585s**, including **0.8246s** model initialization; 20 OCR passes including fallback.

Original real-prefix warm times: **15.3237, 15.8940, 14.8020s**, median **15.3237s**. Cold end-to-end: **19.1410s**, including **0.7293s** initialization; 84 OCR passes including fallback. Representative output includes `妈妈说我注定会成为哥哥的妻子`.

The original synthetic caption text and boundaries are all recovered: 今天我们一起去吃饭 (.5–2.5), 你在干什么？ (3–5), 我不知道发生了什么 (5.5–7.5).

## C. Independent optimization results

Every successful experiment below has one cold run plus three warm repetitions. Individual values, timing breakdowns, memory and quality flags are retained in [OCR_PERFORMANCE_RESULTS.csv](OCR_PERFORMANCE_RESULTS.csv). Detailed observations, source hashes, exact configurations and segment diffs are in `data/ocr-bench/*.json` (ignored local artifacts, deliberately not publishing the user's transcript in Git).

### Real-video 30-second prefix

| Experiment | Warm median (s) | Cold end-to-end (s) | Initialization (s) | Peak process working set MiB | Text/times vs original |
| --- | ---: | ---: | ---: | ---: | --- |
| Original ORT CPU, 2 threads | 15.324 | 19.141 | .729 | 358.8 | Reference |
| ORT CPU, 2 threads, instrumented recheck | 15.445 | See CSV | See CSV | See CSV | Exact |
| ORT CPU, 4 threads only | 11.982 | 16.046 | .783 | 361.0 | Exact |
| ORT CPU, 8 threads only | 23.258 | 29.715 | .896 | 362.1 | Exact |
| OpenVINO CPU, explicit FP32, 4 threads | 9.301 | 12.246 | 1.964 | 689.2 | Exact |
| OpenVINO GPU, explicit FP32 | 8.935 | 44.521 | 6.224 | 1116.4 | Exact |
| Original inference + sequential decoding only | 17.935 | 16.258 | .422 | 355.8 | Exact |
| Original inference + experimental stroke reuse only | 23.939 | 26.524 | .419 | 359.7 | Exact; **zero skips** |
| ORT 4 threads + OpenCV 1 thread | 16.540 | 20.152 | .534 | 358.9 | Exact |
| Final default: ORT 4 + sequential + throttled writes | **9.675** | **14.759** | .474 | 356.6 | **Exact** |
| Optional combined OpenVINO CPU + sequential + throttled writes | **6.528** | **8.756** | 1.815 | 689.2 | **Exact** |

The combined default warm times were **11.4094, 9.6748, 9.4709s**. Optional combined OpenVINO CPU: **6.5279, 6.3923, 6.8830s**. Against the initial baseline median these are **1.58×** and **2.35×** respectively. All retain **60 samples, 84 OCR passes and nine segments**. Detection makes 84 neural inference calls; recognition makes 58 batch inference calls, for 142 stage-level neural calls. The original pass counter and actual neural-stage counters are both retained; they should not be confused.

Warm median timing scopes for that real prefix (seconds; nested scopes must not be added):

| Scope | Original 2-thread detailed repeat | Combined ORT CPU | Combined OpenVINO CPU |
| --- | ---: | ---: | ---: |
| Frame decode/crop | 2.9231 | .6499 | .6326 |
| Model-input preprocessing | 1.8124 | 1.8573 | 1.8267 |
| Detection neural inference | 8.8109 | 5.8693 | 3.1405 |
| Recognition neural inference | 1.0594 | .7843 | .4913 |
| Primary complete OCR passes | 8.6283 | 6.3725 | 4.1277 |
| Fallback complete OCR passes | 3.3536 | 2.4707 | 1.6040 |
| Detector/CTC postprocessing | .1424 | .1780 | .1261 |
| Subtitle merging | .0028 | .0030 | .0026 |
| SQLite writes | .4053 | .0843 | .0506 |
| Complete recognize wrapper | 12.0832 | 8.9360 | 5.8112 |

The initial reference's warm recognize median was **11.9535s**, including **8.7700s detection** and **1.0580s recognition** neural inference. Finer preprocessing/fallback wrappers were added to the identical-output two-thread repeat; these were not available in the first frozen output. A missing timing field in that first JSON means **not instrumented**, not zero measured time. The original repeat's median total was 15.445s, close to the initial 15.324s.

Timings drifted substantially during the extended session. A later original-baseline recheck produced **23.0797, 20.7495, 21.5136s**, median **21.5136s**, with identical output. Temperature/clock throttling was not reliably observable, so its cause is **not established**. No slow repetition was discarded. Thus isolated stage measurements and exact output comparisons are stronger evidence than assuming all matrix rows had identical thermal/background conditions. The headline uses the faster initial baseline rather than the slower recheck. The standalone sequential and reuse rows do not establish an end-to-end win by themselves.

### Full 8-second synthetic fixture

| Experiment | Warm median (s) | OCR passes | Segments | Exact text/times |
| --- | ---: | ---: | ---: | --- |
| Original CPU | 3.1442 | 20 | 3 | Reference |
| ORT 4 threads only | 2.0395 | 20 | 3 | Yes |
| ORT 8 threads only | 5.5440 | 20 | 3 | Yes |
| OpenVINO CPU | 1.5761 | 20 | 3 | Yes |
| OpenVINO GPU | 1.1776 | 20 | 3 | Yes |
| Combined default ORT | **2.5489** | 20 | 3 | **Yes** |
| Combined optional OpenVINO CPU | **1.3564** | 20 | 3 | **Yes** |

The combined default fixture improvement is **1.23×**, not the larger result from the isolated four-thread experiment. GPU cold full-fixture time was **35.3785s**, including initialization and first-use shape/kernel compilation. Warm throughput alone would give a misleading recommendation for short videos. The adapter compiles explicit GPU models and records `EXECUTION_DEVICES=['GPU.0']` for both detection and recognition; classification is disabled. The requests actually ran and produced matching output. There was **no CPU execution fallback** in these GPU experiments. GPU utilization/temperature counters and device-memory peaks were not reliably measured; process RSS excludes some driver/device allocations.

### Decoding and database work

Decode-only real-prefix runs: seek **3.7793, 4.2623, 4.9688s**, median **4.2623s**; sequential **.5863, .5838, .7478s**, median **.5863s**. The emitted 60 crop pixel hashes and actual timestamps match exactly on this CFR source. This is approximately **7.27× faster frame extraction**, **not** a 7.27× OCR inference improvement. Sequential decoding retrieves only sampled images but internally decodes intervening frames; it holds bounded images and checks cancellation each decoded frame.

Progress-only SQLite writes are throttled to 750ms in production/combined experiments; completion remains atomic and cancellation locking is unchanged. No partial transcript replaces completed/corrected data. A decode-only harness bug initially attempted publication without a persisted job; the isolated run failed its foreign-key check. The harness was corrected to persist its initial job, and both decode experiments were rerun successfully. No production database was involved.

Raw timing scopes are explicit and nested: frame reading includes crop creation; `preprocessing` times detector input transforms and recognizer normalization; detection/recognition inference times surround actual runtime calls; `primary_pass` and `fallback_pass` surround complete RapidOCR passes; `ocr_postprocessing` includes detector/CTC output processing; merging and SQLite are separate. Outer crop grayscale/resize/CLAHE/reading-order overhead is included in recognition/decode totals rather than falsely presented as isolated neural inference. Do **not** add nested timing columns together. Cold time includes model initialization and all first-use work; warm runs reuse models, never transcript results. Process peak memory is a lifetime high-water mark, not a separate per-repetition allocation.

## D. Quality, safeguards and limits

- All successful backend and combined runs retain identical segment text/start/end times on both benchmark datasets. All candidate observation texts match the frozen original at every sampled timestamp. No caption loss, new merge, character change or timing deviation was found there; maximum paired timing difference is zero. This compares against the original, not an independently transcribed entire video.
- Two real-video crops were separately reviewed visually at .5s and 120s. Both original and four-thread CPU return exactly `妈妈说我注定会成为哥哥的妻子` and `老登你给我接电话`: zero normalized character errors on this **22-character subset**, not a whole-video CER claim. Images/results: `data/ocr-bench/quality/caption-0.5.png`, `caption-120.png`, `manual-subset.json`.
- New tests include actual-model recognition/reuse over moving dark backgrounds, a changed character, added/removed negation, disappearance/reappearance, second lines, position changes, animated movement, complex bright background changes, blur and low confidence. No false reuse was observed in the checked cases. A brief change at a sampled frame is rejected; captions wholly between samples can still be missed, as before.
- Experimental reuse checks exact high-contrast white-stroke features inside OCR-derived boxes **and outside them throughout the unchanged user ROI**. It requires high confidence, sufficient sharp foreground and a bounded two-second verification interval. It never shrinks the ROI or changes historical timestamps. State is recreated per job and reset after uncertain OCR. A reused observation receives the new frame's actual timestamp.
- **Reuse avoided zero OCR passes on either benchmark video.** Its matching is intentionally too strict to claim a useful general speedup. Fast remains explicit experimental opt-in and is not recommended. Colored/low-contrast typography or changes invisible to the white-stroke signature need broader validation; no universal safety claim is made. Accurate and Balanced disable it. We did not relax safeguards merely to increase skip counts.
- CFR and rotated-video tests require exact original/sequential crop equality. VFR tests compare actual decoded timestamps against FFprobe PTS. Sequential VFR selects the first frame at/after each requested target, which can differ from legacy OpenCV seeking. Accurate mode retains seeking if that distinction matters. Arbitrary broken media/codecs remain subject to decoder support.
- Eight ORT threads and forcing one OpenCV thread were not selected. There is no lowering of sampling FPS, smaller model, automatic ROI change, quantization, preprocessing change, cloud inference or fabricated subtitle/translation data.
- Progressive subtitle publication remains deferred: it would change correction/publication ownership and is a separate perceived-latency feature. Completed results remain protected until a new job succeeds.

## E. Reproduction and runtime use

Run from the existing project root. Benchmark output paths are project-local isolated artifacts. These commands do not modify the normal library:

```powershell
# Freeze and measure the original implementation (cold + 3 warm runs):
.\.venv\Scripts\python.exe scripts\benchmark_ocr.py data\fixtures\mandarin-test.mp4 --output data\ocr-bench\baseline-fixture.json
.\.venv\Scripts\python.exe scripts\benchmark_ocr.py data\media\3c7e8121-18c8-4987-b848-b8cd2bd3dd3f.mp4 --seconds 30 --roi .10,.87,.80,.12 --output data\ocr-bench\baseline-real.json

# Tune only ORT threads; repeat with --threads 2 / 4 / 8:
.\.venv\Scripts\python.exe scripts\benchmark_ocr.py data\media\3c7e8121-18c8-4987-b848-b8cd2bd3dd3f.mp4 --seconds 30 --roi .10,.87,.80,.12 --engine ort --threads 4 --reference data\ocr-bench\baseline-real.json --output data\ocr-bench\ort-4-real.json

# Final default, same models/ROI/FPS, no heuristic:
.\.venv\Scripts\python.exe scripts\benchmark_ocr.py data\media\3c7e8121-18c8-4987-b848-b8cd2bd3dd3f.mp4 --seconds 30 --roi .10,.87,.80,.12 --engine ort --threads 4 --decoder sequential --write-policy throttled --reference data\ocr-bench\baseline-real.json --output data\ocr-bench\combined-ort-real.json

# Decoder isolation; repeat with --decoder seek:
.\.venv\Scripts\python.exe scripts\benchmark_ocr.py data\media\3c7e8121-18c8-4987-b848-b8cd2bd3dd3f.mp4 --seconds 30 --roi .10,.87,.80,.12 --decode-only --decoder sequential --output data\ocr-bench\decode-sequential-real.json

# Reuse only (experimental, not a default):
.\.venv\Scripts\python.exe scripts\benchmark_ocr.py data\media\3c7e8121-18c8-4987-b848-b8cd2bd3dd3f.mp4 --seconds 30 --roi .10,.87,.80,.12 --reuse fast --reference data\ocr-bench\baseline-real.json --output data\ocr-bench\reuse-real.json

.\.venv\Scripts\python.exe scripts\validate_ocr_quality.py
.\.venv\Scripts\python.exe scripts\summarize_ocr_benchmarks.py
Import-Csv docs\OCR_PERFORMANCE_RESULTS.csv | Format-Table experiment,kind,seconds,warm_median,ocr_passes,exact_text_and_times
```

Optional environment setup, leaving `.venv` unchanged (already performed on this machine):

```powershell
.\.venv\Scripts\python.exe -m venv --system-site-packages data\ocr-env
$projectSite = (Resolve-Path .venv\Lib\site-packages).Path
Set-Content data\ocr-env\Lib\site-packages\project-dependencies.pth -Value $projectSite
.\data\ocr-env\Scripts\python.exe -m pip install -r backend\requirements-openvino.txt numpy==2.2.6
.\data\ocr-env\Scripts\python.exe -m pip check
.\data\ocr-env\Scripts\python.exe -c "import openvino as ov; c=ov.Core(); print([(d,c.get_property(d,'FULL_DEVICE_NAME')) for d in c.available_devices])"

# Repeat with --engine openvino-gpu to require actual GPU execution:
.\data\ocr-env\Scripts\python.exe scripts\benchmark_ocr.py data\media\3c7e8121-18c8-4987-b848-b8cd2bd3dd3f.mp4 --seconds 30 --roi .10,.87,.80,.12 --engine openvino-cpu --threads 4 --reference data\ocr-bench\baseline-real.json --output data\ocr-bench\openvino-cpu-real.json
```

In the existing application, expand **Subtitle analysis settings → OCR performance**. New videos default to **Auto / Balanced / ONNX Runtime**. Existing saved JSON without performance fields keeps its original behavior/cache identity. Explicit CPU can use ONNX Runtime or optional OpenVINO CPU. Intel GPU requires the optional environment: stop the existing backend normally and run `scripts\start-backend-openvino.cmd` instead of the ordinary backend launcher. Keep only one backend process per library. The frontend and library remain the same. Requesting an unavailable GPU/OpenVINO runtime produces a useful failed-job error and preserves the previous transcript; it does not silently run on CPU.

**Restore original CPU OCR** removes the new performance fields, selecting two ORT threads, timestamp seeking and original exact-crop reuse. The old engine/settings cache identity is retained, so existing corrected results can be loaded. **Analyze Video** may reuse a completed result; use **Rerun OCR** only when fresh inference is intended, and export corrections first. The ordinary `scripts\start-backend.cmd` always remains usable without OpenVINO.

Regression commands:

```powershell
.\.venv\Scripts\python.exe -m pytest backend\tests -q
npm.cmd --prefix frontend test
npm.cmd --prefix frontend run build
npm.cmd --prefix frontend run test:e2e
.\.venv\Scripts\python.exe -m pip check
.\data\ocr-env\Scripts\python.exe -m pytest backend\tests\test_ocr_performance.py -q
```

## F. Recommendation and validation status

Default for new videos: **Auto → ONNX Runtime CPU, Balanced, four intra-op/one inter-op threads, sequential decoding, original sample rate and exact reuse**. It improves both checked datasets without adding runtime dependencies, has modest startup/memory costs and preserves the original path. Existing configured videos are not silently changed. Optional OpenVINO CPU is the fastest measured combined pipeline here and is useful when its extra memory/runtime dependency is acceptable. GPU is a manual option for experimentation or already-warm longer workloads; its expensive startup and limited advantage over OpenVINO CPU do not justify automatic selection.

Backend regression: **160 passed, 1 skipped** in 95.38s. The skip is an optional OpenVINO device-identity unit check in the unchanged `.venv`; running the complete performance test file in `data/ocr-env` gave **23 passed** in 17.38s, including that check. Frontend Vitest: **11 passed**. TypeScript/Vite build: **passed**. Both environments' `pip check`: **no broken requirements**. The actual OCR integration tests were retained; inference was not replaced with mocks.

The first Edge run timed out selecting a new dropdown by its exact wrapping-label text before OCR began. Explicit accessible labels were added to all three performance selects and the complete suite was rerun. All eight workflows passed in the sandbox, but Windows process restrictions prevented test-server teardown. The final complete run outside that sandbox exited **0: 8 passed in 57.8s**, including the new Balanced selection/device display, all earlier OCR/correction/cache/cancellation/video-switching checks, language/vocabulary/fullscreen, and controlled Douyin import success/failure workflows. These are regression fixtures, not a new live Douyin network claim. After the last device-reporting change, performance tests were rerun in the original environment: **22 passed, 1 optional skip**; TypeScript/build passed again.

The existing normal backend was verified idle before reload. It now runs the tested code on **127.0.0.1:8000**, using the isolated optional OpenVINO environment; Auto/Balanced still selects ORT CPU. Actual listener PID is recorded in `data/backend.pid`; logs are `data/backend-ocr-performance.log` and `data/backend-ocr-performance-error.log`. No second backend was started against the library. API snapshots before/after reload matched **all three videos, active transcript IDs and complete segment/correction data, two saved vocabulary records and player preferences exactly**. Evidence: `data/validation/ocr-reload-before.json` and `ocr-reload-after.json`. The new OpenAPI settings schema and OCR/dictionary/translation health were verified. Refresh the existing frontend to use the new controls. The original `.venv` and ordinary CPU launcher remain intact.

No full-video speedup, broad real-world CER, reliable thermal/GPU utilization figure, NPU result or general-purpose safe-skip claim is implied.
