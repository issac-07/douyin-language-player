# v4.6 — Fast-OCR synchronization and bounded parallel processing

Implemented for the user's existing **Fast-OCR** branch. No commit/push, driver installation, model replacement, FPS reduction or ROI change. Baseline v4.5 settings/corrected transcript caches remain readable. The two new processing flags serialize only when enabled so old serialized settings retain their cache identity. Fast's changed algorithm gets a new version identity. Existing transcripts remain active until a successful new analysis.

## Shipped

- Player checks current media time on every presented video frame using requestVideoFrameCallback, with animation-frame fallback. Active subtitle changes update immediately; unchanged-sentence UI refreshes are capped at 10 Hz to avoid rebuilding long transcripts every frame. Seek, pause, speed, fullscreen and auto-pause retain media-time ownership. No zero-delay guarantee is made for browser rendering.
- Optional **Refine subtitle start timing** inspects decoded original frames within one coarse sampling interval before each accepted start. It requires two adjacent frames with matching Chinese and confidence >=.8 before moving a start earlier. For adjacent captions the prior end moves to the same verified boundary, preventing overlap. Crops, actual decoder timestamps and the user's ROI are preserved. Additional frames/calls are counted separately. Disappearance/end-only boundaries are not independently refined; very long OCR misses and unreadable early characters are not reconstructed or guessed.
- Sequential decoding now runs in a bounded producer with at most two upcoming frames, overlapping decode with OCR. Cancellation drains owned in-flight calls and closes generators before removing queue ownership. No completed/corrected transcript can be published after cancellation.
- Optional **1/2/4 parallel GPU requests** use independently owned RapidOCR pipelines, each with its own detection/recognition request and GPU compiled-model queue. OpenVINO start_async/wait copies inputs and outputs; separate executor lanes allow multiple frames in flight. Results merge in source timestamp order regardless of completion order. This is app-level concurrency, not a claim that simply changing NUM_STREAMS makes a synchronous loop faster. Each compiled pipeline still reports its actual GPU.0 device and one stream per lane. CPU and Fast use one lane. Fast explicitly stays serial because its reuse decision depends on the preceding accepted observation.
- Fast v2 checks grayscale contrast at the union of old/current white-stroke pixels, including outside previous boxes, tolerating at most 12 grayscale levels of compression variation per guarded pixel. Strong stroke changes force OCR; confidence, bounds and verification deadline remain. It is still experimental and not a general solution for colored/low-contrast text.
- Clearer buttons: **Create / open subtitles** uses matching cache or runs OCR; **Scan OCR again** forces a fresh scan. Language preparation remains a separate downstream task. The interface explains both.
- Visible **v4.6**, API 0.4.6; larger bordered delete button. Fixed a library-refresh race exposed by delete-last-video followed immediately by upload: stale library responses no longer erase newly imported selections.

## Measurements: same real MP4, ROI and 5 FPS

Source: previously authorized `data/media/3c7e8121-18c8-4987-b848-b8cd2bd3dd3f.mp4` from the original project. Analyzed first **8 seconds only**, 1920x1080, ROI (.10,.87,.80,.12), 5 FPS, **40 sampled frames / 53 OCR passes**. Real inference, no transcript cache or translation. `scripts/benchmark_ocr_lanes.py` records one cold and three warm repetitions per lane count; no normal library/database writes.

| GPU lanes | Engine initialization s | First processing run s | Three warm processing runs s | Warm median s |
| --- | ---: | ---: | --- | ---: |
| 1 | 2.165 | 8.915 | 3.289, 3.334, 3.231 | 3.289 |
| 2 | 2.568 | 8.594 | 2.371, 2.306, 2.419 | 2.371 |
| 4 | 5.287 | 8.502 | 1.951, 2.138, 2.059 | 2.059 |

All sampled texts, call counts and consolidated segment start/end times matched the serial control exactly. Warm processing improved **1.39x at two lanes / 1.60x at four** in this sample. Initialization plus first-run cost did not improve: approximately 11.08 / 11.16 / 13.79s respectively. More lanes increase memory and compilation work. Therefore default remains one; try four explicitly for warm/long jobs and verify on your video. This is not a full-video speedup or a claim of 100% GPU utilization. Lane-specific peak/device memory, clocks and thermals were not measured.

Raw JSON: `data/ocr-lanes.json` in the development worktree. Reproduction: run `D:\Projects\douyin-language-player\data\ocr-env\Scripts\python.exe scripts\benchmark_ocr_lanes.py` from the checkout with the authorized source still present. The script pins the exact source/ROI/FPS above.

Fast comparison: `data/ocr-v46-baseline.json` and `data/ocr-v46-fast.json`, same real prefix/5 FPS/ORT four threads. **Zero frames reused**, identical output in all repetitions. No real-video skip speedup is claimed; keep Fast experimental. Initial control processing overlapped a test run, so its wall-time comparison is not evidence of a speed win. Compression tolerance and changed-character/negation/add-line safety cases are tested independently.

## Validation and failures corrected

- Full original-environment backend suite: **169 passed, 2 optional skips**. New scheduling/refinement/reuse checks include actual model inference, real media timestamps, ordered concurrency, error propagation and generator cleanup.
- Optional OpenVINO environment scheduling file: **6 passed**, including an actual GPU API job at 5 FPS comparing one vs two lanes.
- Frontend: **11 passed**, TypeScript/Vite build passed. Edge: **9 passed**, including suppression of timeupdate while verifying the in-video caption changes, import, delete, cancellation, corrections, cache, dictionary, Vietnamese, vocabulary and fullscreen.
- An initial GPU test incorrectly expected the 2 FPS fixture's three segments at 5 FPS. The serial 5 FPS pipeline also detects extra noisy snippets on the moving synthetic background. The test now compares serial and parallel at the SAME FPS, requires the three known captions, and retains exact text/time comparison. This is a baseline OCR quality limit, not removed by parallelization.
- Initial browser regression exposed the library-load race described above; fixed and the complete suite rerun successfully.
- A benchmark initially referenced a removed cache UUID from the user's current library and failed before inference. The corrected benchmark uses the already-authorized stable source above. No deleted user file was restored or substituted silently.

Metrics: decode_seconds is measured inside the decoder producer; pipeline_wait_seconds measures consumer waiting and is nested with processing. With concurrent lanes, summed inference_seconds is work across lanes and can exceed elapsed wall time. These are not GPU utilization counters and should not be added together.

## Use and limits

Under OCR performance select **Intel GPU / Balanced**, then **Parallel GPU requests = 2 or 4**. Same sample rate and ROI. **Refine subtitle start timing** costs extra OCR near boundaries; enable for synchronization accuracy, not to claim faster inference. Use **Scan OCR again** for a fresh comparison; **Create / open subtitles** may return cached corrected results. Save/export corrections before forcing a new transcript. CPU original/Accurate remains available.

Source references: [OpenVINO request ownership and async API](https://docs.openvino.ai/2026/openvino-workflow/running-inference/inference-request/python-api-advanced-inference.html), [throughput hints](https://docs.openvino.ai/2026/openvino-workflow/running-inference/optimize-inference/high-level-performance-hints.html), [presented-video-frame callbacks](https://developer.mozilla.org/en-US/docs/Web/API/HTMLVideoElement/requestVideoFrameCallback). No extension, progressive provisional transcript publication or NPU work is included. Recognition batching remains RapidOCR's existing within-frame batching; cross-frame batching and broad safe OCR skipping are not established.
