# Subtitle display controls and theme refinements

Implemented 13 November 2026 in the original D:/Projects/douyin-language-player project on v2---Update-UI, retaining existing uncommitted work. No commit/push, branch change, dependency/model download or backend/schema change was performed.

## Behavior

- New/Learning/Known remain three mutually exclusive buttons, now using three equal grid columns. Save/Saved stays at the right on the same row. Existing save/status/unsave behavior is retained.
- Transcript has independent Pinyin and Translation toggles in its heading, using aria-pressed. Chinese remains visible and clickable. The reading view hides only the chosen annotation layer; optional translation editing tools remain under the row menu. Transcript preferences use browser-local dlp-transcript-display storage and persist across reloads/video changes. Internal auto-follow accounts for changed row heights.
- The player has Chinese/Pinyin/Translate toggles at the left of the row beneath the main playback controls, sharing the row with a visibly bordered Delete selected video button at the right. These use the existing persisted player appearance settings and synchronize with the appearance panel. Enabling Chinese from Minimal mode switches to Interactive so Chinese actually appears. If the master subtitle switch was off, a quick toggle enables only the selected layer; the master CC control remains available for global visibility. Burned-in text in the original video is unaffected.
- The selected-word card below Transcript uses a separate sage surface in both themes. Transcript scrollbar tracks use the page background with theme-aware thumbs, with standard and WebKit scrollbar styles.
- Subtitle appearance uses theme surfaces, borders, readable labels/values, a themed sticky heading/Close button, selectors, sliders, checkboxes and status text. Active/hovered player icons use the theme accent instead of the previous green background. Mobile overflow remains bounded and the settings panel can scroll.

## Validation

- TypeScript/Vite production build passed.
- All 19 Edge integration tests passed. The new display test covers transcript/video independence, visibility of all three video layers, saving/reloading preferences, equality of status-button widths, settings checkbox synchronization, card color differentiation, themed panel/scrollbar styles, and mobile alignment of subtitle controls with deletion.
- After refining the master-off case, the targeted display integration test passed again and the production build was rerun successfully.
- The normal application at port 5173 was inspected using actual local video/transcript data in fresh Edge sessions at 1440px desktop and 390px mobile widths. Light/dark settings panels, distinct word-card surfaces and controls were visually inspected. No page JavaScript errors or horizontal overflow were observed. Equal mobile status widths differed by only subpixel rounding (about 0.02px). Normal-app inspection did not save/delete user vocabulary or change persisted player appearance values.
- Captures: data/validation/display-controls-light.png, display-controls-dark.png, display-settings-mobile.png and display-controls-mobile.png. Test fixture captures also live under frontend/test-results.
- git diff --check passed; backend diff is empty. OCR timestamps, recognition/translation models, saved vocabulary records and original media are unchanged by this display patch. No physical mobile-device or formal screen-reader audit is claimed.
