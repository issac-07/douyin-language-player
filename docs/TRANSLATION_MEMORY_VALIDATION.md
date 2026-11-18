# Translation memory management validation

Implemented in original `D:\Projects\douyin-language-player`, branch `v2---Update-UI`. No commit/push or model/data deletion.

- Default idle timeout: 180 seconds after translation activity ends, with no scheduled work. A background maintenance thread unloads model processes/Marian weights; cached reads and status polling do not refresh the idle timer.
- `Free model memory` pauses uncached translation, skips obsolete queued work through a generation counter, waits for any in-flight sentence to finish/save, then unloads models. This avoids automatic reload by ongoing UI polls. Cached/manual translations stay readable. `Resume translation` re-enables work and refreshes the transcript/selected-word request.
- `paused` is explicit in API/UI. Memory status polling is read-only. A shared inference lock prevents unloading during model execution or a concurrent load. Normal shutdown stops the maintenance thread, cancels queued jobs and closes model processes. Forced backend termination remains outside graceful shutdown guarantees.
- Timeout can be overridden with `DLP_TRANSLATION_IDLE_SECONDS`; pause is backend-session state and resets on restart.

Validation:
- Existing backend regression tests (`test_translation_selection`, `test_hymt`, `test_learning`): **15 passed**.
- New memory tests: **3 passed**. Verify release during active work, queue skipping, paused polling, cache preservation/resume; real model process exit after idle unload and successful reload; actual background timer unload with 0.2-second test timeout and thread shutdown.
- Frontend production build passed, including final paused-state wording in transcript/dictionary.
- Real Edge: **1 passed** (18.9s), checking manual release, unloaded/paused status, cached Vietnamese subtitle retained, uncached English paused without reloading, resume and successful English translation. Screenshot: ignored `frontend/test-results/model-memory-controls.png`.
- Inspected the original backend's single 7B child process, verified zero active OCR/import jobs, then restarted the original backend with the change. Requested manual release so the live app starts this session paused with models unloaded; the user can resume via the new button.

SSD files (model weights, videos, dictionary, cached translations, vocabulary and manual corrections) are retained. Unloading releases active model resources; Windows may retain reclaimable file cache, so Task Manager total memory need not instantly fall by the model file size.
