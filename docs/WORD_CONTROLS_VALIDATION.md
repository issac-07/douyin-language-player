# Current word controls and transcript synchronization

Updated 13 November 2026 in the original D:/Projects/douyin-language-player project, branch v2---Update-UI. No branch change, commit/push, model/voice download or dependency installation was performed. Backend and translation resources remain unchanged.

## Current interface

Selected word has three mutually exclusive status buttons (New/Learning/Known) on the left and one Save/Saved button on the right, on the same line. A new word initially has no chosen status, and Save is disabled until a status is chosen. Choosing a word or status does not save it automatically. Saving changes the button to Saved with a contrasting background (dark in light mode). There is no success message, extra saved icon, separate remove button or undo toast.

Click Saved to unsave. The status and notes snapshot remain in the mounted card; click Save again to restore it. Changing the status of a saved word changes the button back to Save; saving preserves the stored notes. Errors alone appear below the controls. Pending actions are locked against duplicate clicks. The transient restore snapshot does not survive a page reload or switching to a different word.

The speaker automatically requests Microsoft Xiaoxiao Online (Natural), matching either the Xiaoxiao or 晓晓 browser voice name with zh-CN locale and online identity. No pronunciation settings, provider selector, voice selector, checkbox or permanently displayed installation note remains. Text is sent to the selected online voice only after a speaker click. No other voice is silently substituted. A late voice list is retried briefly; word changes/unmount cancel speech and pending lookups, and speech errors/timeouts release the button for retry.

This uses the browser SpeechSynthesis API, not a private Edge endpoint, edge-tts package, downloaded model or paid API. If Edge does not expose Xiaoxiao to webpage JavaScript, pressing the speaker displays an unavailable-voice error. A voice visible in Edge's own Read aloud menu is not guaranteed to be available to a webpage.

Transcript jumps retain the shared player seek path, pre-paint updates, suppression of intermediate seek time updates, and sub-microsecond timestamp normalization from the previous patch. Stored OCR times, gaps and exports are unchanged; no fixed delay is added.

## Validation and limits

- Production TypeScript/Vite build passed; all 18 Edge tests passed, including existing import/OCR/translation/export/playback/deletion flows.
- Current tests cover the one-row status-buttons/Save layout, explicit saves, status and note persistence, Saved/unsave/resave restoration, paused transcript jumps, exact Xiaoxiao selection, missing voice, speech cancellation and network-error retry without settings UI. Speech behavior is tested with controlled voice doubles; actual audible Xiaoxiao playback is not claimed.
- Normal-app desktop/mobile captures were inspected: data/validation/word-controls-desktop.png and word-controls-mobile.png; the saved appearance is also captured in frontend/test-results/quick-word-actions.png. No horizontal overflow or application JavaScript exception was observed. The existing favicon.ico 404 remains unrelated to these controls. Normal-app visual checks do not save/delete user words.
- The fresh headless Edge session still enumerated no Mandarin voices. The requested voice must be exposed in the user's browser session for native speech playback to work.
- git diff --check passed. No backend, OCR/translation algorithm or resource/model files changed. The previous 13-unit-test result remains applicable to the unchanged playback helper; this update validates its UI through the browser suite.

Translation quality and the apple-cheek translation example are unchanged. No Hunyuan, Piper or Windows speech package was downloaded.
