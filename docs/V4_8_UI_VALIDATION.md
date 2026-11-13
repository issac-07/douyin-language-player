# v4.8 UI/UX — a quieter learning workspace

Verified 13 November 2026 (Australia/Sydney). UI-only changes in the original `D:\Projects\douyin-language-player` project. No OCR/model/runtime/settings algorithm, API, schema, player media timing or translation algorithm changes. No commit or push.

## Branch and starting point

The original checkout initially had clean `Fast-OCR` at `c8ddad8`, containing committed v4.7. `codex/ocr-p1-improvements` still pointed to its ancestor `5f0a9c8`. The user explicitly chose the codex branch. Its reference was fast-forwarded to `c8ddad8` (no divergent commits), then the checkout switched while preserving the UI working changes. `Fast-OCR` and `main` were not moved. No separate checkout/worktree was created or used for implementation.

## Behavior

- **Import another video** is collapsed by default, including restored failed or active imports. Expanding/closing preserves typed sharing text during the mounted session. Successful local/URL imports close the form. A failed URL job shows one short status plus **View error details**, not a full diagnostic wall. Immediate submission errors are also compact. Error codes, HTTP stage, transport diagnostics, local-file fallback and retry entry remain available inside the disclosure. An active import continues polling while hidden; progress and Cancel stay outside the form. Import options/public-page consent remain explicitly opt-in under **Import options & help**. The empty library still offers its MP4 drop target and a visible way to add a link.
- OCR state is outside the collapsed settings panel, so users can see the current stage and cancel without opening settings. A live job has one readable stage label, measured/indeterminate progress as appropriate and Cancel. Initialization/refinement do not show a fabricated percentage. Completed/cancelled/failed states become compact rows with no lingering progress bar. Retry is available for failed analysis, retaining the export-corrections notice when a prior transcript exists.
- **Processing details** is closed by default and exposes elapsed time, sampled frames, refinement counts, OCR calls/reuse, actual/requested execution and model identity. The elapsed clock and worker-staleness check remain intact. A worker update warning stays visible. There is no estimated finish time or false completion state.
- Language processing is a short line separate from OCR. Space is reserved for changing language status, rather than inserting long counts above the video. Sentence and word-language controls remain separate and persistent, with simplified visible labels.
- Basic/Advanced mode and preset values are unchanged. Explanations of presets, CPU/runtime, GPU/timing, ROI selection and cache behavior are native keyboard/touch-accessible disclosures beside their relevant controls. Save/cache notifications are shorter. Rescan/export warnings stay visible rather than being hidden only in hover help. General blocking action errors remain reachable even when the settings panel is closed.
- Video codec/dimensions/file size now live in **Video details**. Local storage remains closed until opened; cleanup confirmations and actions are unchanged. Global success notifications can be dismissed.
- Dark styling is retained with improved control spacing, borders, readable selectors, focus outlines and action hierarchy. Mobile transcript content now has a bounded scroll region (also focusable for keyboard scrolling), so a long transcript does not create an enormous page. Fullscreen still keeps the player and learning sidebar.

## Validation

- TypeScript/Vite production build passed; **11 frontend unit tests passed**.
- **12 Edge tests passed**: existing import/playback/seek/fullscreen, real OCR, corrections/cache/export/cancel, vocabulary/dictionary/language selection, plus UI coverage for pending/model/OCR/refinement/completed/failed/cancelled states, disclosure default/keyboard toggling, failure restoration after reload, retained URL draft, hiding active imports with cancellation still available and mobile overflow checks.
- OCR state-matrix assertions use intercepted responses only in isolated browser tests. Existing actual OCR and import integration tests still run real media/model paths. Routine Douyin HTTPS responses remain fixture-backed; this release does not claim a new live Douyin download.
- The normal app on port 5173 was opened in a fresh Edge session, not just checked for HTTP 200: v4.8 rendered, import was collapsed and no JavaScript page errors occurred. Desktop 1440×1000 and mobile 390×844 were captured and visually inspected. Mobile horizontal overflow was false. The long real transcript revealed an excessively tall mobile page; bounded scrolling was added and checked again.
- During validation, a dismiss button changed an exact text selector; the notification text was wrapped separately. A decorative '+' also changed a button's accessible name; an explicit dynamic aria-label fixed keyboard/automation identification. Test expectations were updated for intentional shortened labels and the newly collapsed import/help UI; backend assertions were not removed.
- Implementation writes were applied atomically to reduce the risk of Vite observing a temporarily empty source file. No normal backend/frontend restart or port change was needed.

Screenshots in `data/validation`: `v48-live-desktop.png`, `v48-live-mobile.png`. Isolated browser captures under `frontend/test-results` include `v48-quiet-workspace.png`, `v48-quiet-mobile.png`, `v48-desktop.png`, `v48-mobile.png`.

## Use and remaining limits

Refresh port 5173 to see the **v4.8 UI**. The unchanged backend API still reports **0.4.7**; that is intentional for this UI-only release. Expand **Import another video**, **Processing details**, **Video details** or the contextual help only when needed. Import errors do not automatically expand diagnostic text.

No formal screen-reader audit was performed; native details/buttons, focus indicators and browser keyboard checks were used. URL drafts persist across opening/closing during the current session, not browser reloads. Settings changes/active progress values are not altered by presentation changes. Model inaccuracies and existing sampling/refinement limitations remain those documented for v4.7. No extension, OCR performance claim, automatic storage cleanup or new UI dependency was introduced.
