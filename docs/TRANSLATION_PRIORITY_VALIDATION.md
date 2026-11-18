# Prioritized subtitle translation validation

Original checkout: `D:\Projects\douyin-language-player`; branch `v2---Update-UI`. Existing memory-management changes retained. No model/prompt change, download, commit or push.

- Replaced FIFO inference executor with one reorderable worker. Waiting jobs use current document priorities; the running sentence is never interrupted. Release-memory control tasks retain precedence and shutdown cancels waiting futures.
- Without a selected time, uncached subtitles schedule chronologically. Transcript click/keyboard selection and video seeks send a focus time; the sentence at/before the position is first, followed by nearby lines with a slight preference for upcoming subtitles. New seeks reorder pending jobs, including already queued work. Ordinary playback does not send repeated priority changes. Changing language/model resets focus.
- First 10 priority jobs can enter even if the normal 512 waiting-task limit is reached; bounded overflow avoids making a selected late sentence wait behind the queue-capacity limit.
- Returned transcript order and sentence IDs remain unchanged. Cache identities, manual overrides, model selection, free-memory/pause/resume and idle unload remain intact.
- Moved model attribution to a single line immediately below the Transcript title. Per-sentence reading rows no longer show model-source lines. Manual-edit attribution remains available in expandable tools and the header notes mixed user edits.

Validation:
- **20 backend tests passed**: language/OCR regression, Hy-MT contracts, separate model caches/manual corrections, memory release/idle/resume, and new priority tests. Priority tests block real worker execution deterministically to verify 0→6→9 on successive clicks, no duplicate translation or misassigned results, and immediate selection of sentence 599 with a 600-sentence document.
- Frontend production build passed.
- **2 real Edge tests passed**: three-model selection/source labels/reload/responsive header, plus explicit transcript selection/seek focus requests, language-change reset and exactly one source line under Transcript (none under sentence rows). Final run: 56.7 seconds total.
- Inspected screenshot `frontend/test-results/priority-transcript.png` (ignored artifact).
- Restarted original local backend after checking no active OCR/import jobs; preserved prior paused state. Live OpenAPI exposes the validated focus parameter; frontend returns HTTP 200.

This reduces waiting for the requested region, not per-token inference cost. Cold model load and one currently running sentence can still delay the first prioritized result. Text generation/quality and sentence-only prompts are unchanged.
