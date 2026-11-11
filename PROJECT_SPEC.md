# MASTER PROMPT: Build a Douyin Language Learning Video Player with OCR

## 1. Your Role

You are a senior full-stack software engineer, Python computer vision engineer, and language-learning software architect.

Your task is to **design, implement, test, and document a fully functional local web application** called **Douyin Language Player**.

The application should provide a language-learning experience inspired by the open-source video player Miteiru:

https://github.com/hockyy/miteiru

The primary innovation is automatically generating interactive Chinese subtitles using OCR on text already embedded in Douyin videos.

**This is a real software engineering task, not a UI mockup.**

I expect an executable project with working backend, frontend, OCR pipeline, video playback, subtitle synchronization, dictionary integration, and installation instructions.

Use original UI code. Do not copy copyrighted branding or assets. Review the licences of any code, models or dictionaries you reuse.

---

## 2. Project Goals

I am learning Mandarin Chinese through Douyin (抖音) short videos.

Many Douyin videos already have Chinese subtitles hardcoded into the video frames, usually near the bottom.

These subtitles frequently appear at the beginning of a spoken sentence and remain visible while the character is speaking.

I want to exploit this by extracting the Chinese text directly from video frames instead of relying on speech recognition.

The final application should allow me to:

1. Paste a Douyin video URL or import a local MP4.
2. Watch the video in a built-in player.
3. Automatically detect Chinese subtitles using OCR.
4. Generate timestamped subtitle segments.
5. Automatically split the Chinese text into individual words.
6. Display pinyin above the Chinese words.
7. Display Vietnamese translations and vocabulary meanings.
8. Click on words to view definitions and save vocabulary.
9. Synchronize interactive subtitles with video playback.
10. Reuse previously generated subtitles without processing the video again.

The application must work locally on Windows, preferably without paid APIs or subscriptions.

**Do not implement a Chrome Extension yet.** However, design reusable modules so that an Extension can be integrated in the future.

---

## 3. Technology Stack

Use the following preferred architecture unless there is a well-justified technical reason to change it.

### Frontend

- React
- TypeScript
- Vite
- Modern CSS or Tailwind CSS
- HTML5 video element
- Responsive, dark-mode interface

### Backend

- Python
- FastAPI
- Uvicorn
- SQLite for local persistence

### Computer Vision

- RapidOCR with ONNX Runtime
- OpenCV for image preprocessing and frame extraction
- FFmpeg where appropriate for video processing and media compatibility

### Chinese Language Processing

- Jieba for Chinese word segmentation
- Pypinyin for tone-marked Hanyu Pinyin
- CC-CEDICT for Chinese-English dictionary lookup
- A genuinely implemented Chinese-to-Vietnamese translation module

Consider `Helsinki-NLP/opus-mt-zh-vi` as the initial offline translation model. Verify its current Transformers API, Python compatibility, installation requirements, runtime performance and output quality before integrating it.

### Douyin Video Import

- yt-dlp or a maintained Douyin-compatible downloader
- FFmpeg where required
- Graceful handling of unavailable or unsupported videos

The app must not bypass DRM, private access restrictions, authentication or access controls.

Use publicly accessible or appropriately authorised media. Review applicable terms and licences.

### General Requirements

- Prefer free and open-source dependencies.
- Prefer CPU-compatible libraries.
- GPU acceleration should be optional, not mandatory.
- No paid translation API should be necessary.
- Docker must not be required for local development.
- Provide Windows PowerShell installation commands.
- Verify current package documentation and pin compatible versions.

---

## 4. Video Input System

Implement two input methods.

### Method A: Local Video

Allow users to select or upload a local MP4 file.

Requirements:

- Validate the file format.
- Read video duration and resolution.
- Display the video in the player.
- Support play, pause, seek, playback speed and fullscreen.
- Handle unsupported codecs gracefully.
- Allow users to restart subtitle processing.

Local MP4 input must be fully functional even if the Douyin downloader fails.

### Method B: Douyin URL

Provide a URL input box.

Example:

`https://v.douyin.com/...`

Expected workflow:

User pastes URL → clicks Import → backend validates the URL → resolves the permitted video resource → obtains playable media → displays video → enables OCR analysis.

Requirements:

- Support normal and shortened Douyin sharing links where technically possible.
- Extract useful metadata when available.
- Show download/import progress.
- Avoid redundant downloads.
- Store media locally when needed, with configurable cache cleanup.
- Validate domains and redirects to prevent SSRF.
- Provide actionable error messages.

If the downloader fails because of platform restrictions or changes, explain the failure and offer local MP4 import.

Do not fake success or silently substitute another video.

---

## 5. OCR Subtitle Extraction Engine

**This is the most important component of the entire project. Prioritize its reliability.**

### 5.1 Extract Video Frames

For an imported video:

1. Read its duration, dimensions and frame rate.
2. Sample frames at configurable timestamps.
3. Default to approximately 2 sampled frames per second for offline analysis.
4. Allow adjustment based on speed and subtitle duration.
5. Preserve the actual timestamp of each sampled frame.

Avoid decoding every frame unnecessarily.

### 5.2 Subtitle Region Detection

Douyin subtitles frequently appear near the bottom of the frame.

Implement a configurable subtitle Region of Interest (ROI).

Default:

- Use a sensible lower portion of the video.
- Represent crop coordinates using normalized values.
- Do not assume all videos have the same resolution or aspect ratio.

The frontend must provide:

- A preview frame.
- A draggable and resizable crop rectangle.
- The ability to save the selected ROI.
- A way to rerun OCR with updated settings.

This is important because subtitles may appear in different positions.

### 5.3 Image Preprocessing

Experiment with:

- Cropping
- Resizing
- Contrast enhancement
- Grayscale
- Thresholding when appropriate
- Noise reduction

Use the original or minimally processed image as a fallback if preprocessing reduces OCR accuracy.

### 5.4 Chinese OCR

Use RapidOCR to detect Chinese text.

Return:

- Recognized text
- Confidence score
- Source timestamp
- Bounding boxes when available

Handle:

- Simplified Chinese
- Traditional Chinese where supported
- Punctuation
- Multiple subtitle lines
- Chinese characters mixed with numbers
- Text with outlines or colored backgrounds

Filter unrelated text such as watermarks, buttons and user-interface labels where reasonably possible.

### 5.5 Subtitle Change Detection

The application must NOT produce a duplicate subtitle for every sampled frame.

Example:

A sentence remains visible for four seconds, and the system processes eight frames.

The expected result is ONE subtitle segment, not eight.

Implement:

1. Frame-level visual change detection.
2. OCR text normalization.
3. Text similarity comparison.
4. Confidence-based filtering.
5. Merging of consecutive identical or nearly identical subtitle observations.
6. Detection of subtitle disappearance.
7. Detection of new subtitle appearance.

Do not merge genuinely separate occurrences of the same sentence across unrelated time intervals.

Handle short gaps or temporary OCR errors intelligently.

### 5.6 Subtitle Timestamp Generation

Each subtitle must have:

- Start time
- End time
- Chinese text
- OCR confidence
- Processing metadata

Infer start/end times from sampled observations.

Explicitly acknowledge timestamp uncertainty caused by frame sampling.

Optionally refine subtitle boundaries through additional nearby frame samples.

Do not claim word-level audio timestamps were obtained from OCR.

### 5.7 Subtitle Correction

Users must be able to:

- Edit incorrect Chinese text.
- Modify start/end timestamps.
- Delete a segment.
- Add a missing segment.
- Merge or split subtitle segments.
- Re-run OCR for a selected interval.

When Chinese text is edited, regenerate the associated pinyin, word segmentation and translation.

### 5.8 Export

Provide JSON and SRT exports.

The JSON format must retain detailed metadata that SRT cannot represent.

---

## 6. Chinese Language Processing

After obtaining a subtitle sentence, process it into interactive language-learning data.

### 6.1 Word Segmentation

Use Jieba to segment Chinese text into meaningful words.

Example:

Input:

`今天我们一起去吃饭`

Expected segmentation:

`今天 | 我们 | 一起 | 去 | 吃饭`

Preserve the original sentence and character offsets.

Allow later manual correction of word segmentation.

### 6.2 Pinyin

Use Pypinyin with tone marks.

Example:

- 今天 → jīntiān
- 我们 → wǒmen
- 一起 → yìqǐ
- 吃饭 → chīfàn

Handle context-sensitive pronunciation and polyphonic characters as accurately as practical.

Display pinyin directly above its corresponding Chinese word.

### 6.3 Dictionary

Integrate CC-CEDICT for vocabulary lookup.

For each word, return when available:

- Chinese characters
- Pinyin
- English definition
- Part of speech, if reliably available
- Additional dictionary meanings

Do not invent definitions that do not exist in the source.

### 6.4 Vietnamese Translation

Vietnamese is my preferred translation language.

Implement sentence-level Chinese-to-Vietnamese translation using a free local model where feasible.

Requirements:

- Display a natural Vietnamese sentence translation.
- Cache translation results.
- Allow manual editing.
- Clearly distinguish sentence translations from dictionary word definitions.
- Gracefully handle model installation or inference failures.

If reliable Vietnamese word-level definitions are unavailable, display verified English dictionary meanings as a fallback instead of fabricating Vietnamese definitions.

Translation must be a real implementation, not hardcoded sample outputs.

---

## 7. Interactive Video Player

Build a polished video player inspired by the language-learning workflow of Miteiru.

### Player Layout

Main area:

- Video player
- Interactive subtitle overlay
- Chinese words with pinyin
- Optional Vietnamese translation

Secondary area:

- Subtitle transcript
- Vocabulary details
- Saved words
- OCR processing controls

### Playback Features

Support:

- Play / pause
- Seek
- Playback speed: 0.5×, 0.75×, 1×, 1.25×, 1.5× and 2×
- Volume and mute
- Fullscreen
- Keyboard shortcuts
- Previous and next subtitle
- Replay current subtitle
- Optional auto-pause after each subtitle

### Subtitle Synchronization

Use the actual `video.currentTime` to determine the active subtitle.

Do not rely on estimated wall-clock timers.

Seeking, pausing or changing playback speed must not break subtitle synchronization.

### Interactive Subtitle Display

For every active subtitle:

- Render Chinese words separately.
- Show pinyin above the words.
- Show Vietnamese sentence translation underneath.
- Make each word clickable.
- Open a dictionary panel when a word is clicked.
- Allow saving vocabulary.

The default layout should avoid covering important parts of the video.

Implement controls for subtitle size, position and visibility.

### Vocabulary Learning

Allow users to:

- Save words.
- Mark words as New, Learning or Known.
- Add personal notes.
- View saved vocabulary.
- Export vocabulary as CSV for later use in Anki.

AnkiConnect integration is optional and should not block core functionality.

---

## 8. Processing Workflow

The application should distinguish between video import, OCR analysis and playback.

Expected flow:

1. User imports a video.
2. Video becomes playable.
3. User chooses the subtitle region.
4. User clicks Analyze.
5. Background processing begins.
6. Progress is displayed in the UI.
7. OCR segments are saved.
8. Chinese words and pinyin are generated.
9. Vietnamese translations are generated where possible.
10. The video player displays synchronized interactive subtitles.

Use a local background worker or job queue appropriate for FastAPI.

Implement job statuses:

- Pending
- Processing
- Completed
- Failed
- Cancelled

Show meaningful progress and errors.

**Do not block the UI while processing a long video.**

Support progressive availability of completed subtitle segments if feasible.

For the MVP, preprocessing before uninterrupted playback is acceptable. Do not pretend that OCR from a live frame always has zero delay.

---

## 9. Data Persistence and Cache

Use SQLite to store:

- Imported video metadata
- Video source information
- Subtitle segments
- OCR confidence
- Subtitle corrections
- Word segmentation and pinyin
- Translations
- Saved vocabulary
- Processing jobs and settings

Cache analysis results.

The cache key must account for:

- Video identity or content fingerprint
- Selected subtitle region
- OCR configuration
- Processing model/version

Users should not have to process the same video repeatedly unless settings or source content change.

---

## 10. Backend API

Design clear FastAPI endpoints for:

- Local video upload
- Douyin URL import
- Video metadata retrieval
- Media playback with reliable seeking/range support
- Starting OCR processing
- Checking processing progress
- Cancelling a processing job
- Retrieving subtitle segments
- Updating subtitle text and timestamps
- Retrieving language-learning data
- Saving vocabulary
- Exporting subtitles and vocabulary

Use Pydantic models and typed API responses.

Implement input validation, file size limits, safe local file handling and appropriate error responses.

---

## 11. Frontend Design

Create a modern dark-themed interface inspired by high-quality media players.

The homepage should contain:

**Import panel**

- Paste Douyin link
- Upload MP4
- Recent videos

**Video workspace**

- Large video player
- OCR configuration
- Processing status
- Interactive subtitle overlay
- Transcript panel
- Vocabulary dictionary

**Settings**

- Subtitle region
- OCR sampling rate
- Chinese font size
- Pinyin visibility
- Translation visibility
- Preferred language
- Playback settings
- Cache management

The UI must be genuinely connected to the backend.

Do not use fake progress indicators, fake OCR results, fake translations or static hardcoded demos as the production implementation.

---

## 12. Project Structure

Use a maintainable structure similar to:

```text
douyin-language-player/
├── frontend/
│   ├── src/
│   │   ├── components/
│   │   ├── pages/
│   │   ├── hooks/
│   │   ├── services/
│   │   └── types/
│   └── package.json
├── backend/
│   ├── app/
│   │   ├── api/
│   │   ├── models/
│   │   ├── services/
│   │   │   ├── video_import.py
│   │   │   ├── video_frames.py
│   │   │   ├── ocr_engine.py
│   │   │   ├── subtitle_detection.py
│   │   │   ├── chinese_processing.py
│   │   │   ├── translation.py
│   │   │   └── cache.py
│   │   └── main.py
│   ├── tests/
│   └── requirements.txt
├── data/
├── scripts/
├── README.md
└── .gitignore
```

You may improve the structure if necessary.

Keep OCR, subtitle processing, language processing and video import separate from the UI.

These modules must be reusable in a future Chrome Extension.

---

## 13. Testing Requirements

Provide automated tests for the important logic.

### OCR Tests

Create or include a small, legally usable synthetic test video with Chinese subtitles.

Test:

- Correct Chinese OCR extraction
- Multiple subtitle changes
- Duplicate subtitle merging
- Blank frames
- Low-confidence OCR
- Subtitle timestamp generation

### Chinese Processing Tests

Use example sentences such as:

- 今天我们一起去吃饭
- 你在干什么？
- 我不知道发生了什么

Verify segmentation, pinyin generation and valid output structure.

### Playback Tests

Verify:

- MP4 import
- Video play/pause
- Seeking
- Correct subtitle selection at specific timestamps
- Subtitle editing
- Saved vocabulary persistence

### Integration Tests

Verify at least one end-to-end workflow:

Import local MP4 → analyze subtitles → generate pinyin → display synchronized interactive subtitles → save vocabulary.

Test URL importing independently and document any live Douyin accessibility limitations.

Do not claim Douyin URL importing has passed unless it was tested successfully with a real accessible video.

---

## 14. Performance and Reliability

Optimize for a normal Windows laptop CPU.

Use batching, caching and change detection where beneficial.

Avoid:

- Running OCR on every frame
- Re-translating identical sentences
- Reinitializing OCR models for every frame
- Blocking video playback during processing
- Processing entire video files in memory unnecessarily

Measure and report:

- OCR inference time
- Total analysis time
- Number of frames processed
- Number of unique subtitle segments
- Average OCR confidence

Performance targets are goals, not guarantees.

Be explicit about the difference between offline preprocessing latency and real-time extension latency.

---

## 15. Security and Licences

Handle imported URLs securely.

Prevent:

- Arbitrary local file access
- Path traversal
- SSRF through user-submitted URLs
- Unsafe subprocess invocation
- Excessive file sizes or uncontrolled downloads

Use safe command argument lists for FFmpeg and downloader processes.

Do not require login credentials or expose browser cookies.

Review third-party software, model and dictionary licences. Include any attribution and distribution requirements in the README.

Respect platform access restrictions and only process content the user is authorised to access.

---

## 16. Implementation Instructions

**You must actually implement the application. Do not stop after generating a plan.**

Work in this order:

### Phase 1 — Runnable Foundation

Create the actual frontend and backend project.

Implement local MP4 import and video playback.

Verify that the app starts and loads a video successfully.

### Phase 2 — Working OCR Pipeline

Implement frame extraction, adjustable subtitle ROI, RapidOCR, subtitle-change detection and timestamp generation.

Test on synthetic and sample subtitle images.

### Phase 3 — Language Learning Features

Implement Jieba, Pypinyin, dictionary lookup, Vietnamese translation and interactive subtitle rendering.

Ensure words are clickable and the active subtitle follows video playback.

### Phase 4 — Douyin Link Import

Implement the URL ingestion component using a suitable downloader.

Test it where permitted and available.

If Douyin import fails, keep local MP4 workflows fully functional and report the specific limitation.

### Phase 5 — Testing and Documentation

Run tests and fix implementation errors.

Include a complete README with installation, run commands, dependencies, architecture, troubleshooting and known limitations.

---

## 17. Windows Installation Experience

Assume the development machine runs Windows 11 with VS Code.

Provide PowerShell commands for:

1. Checking Python and Node.js versions.
2. Installing dependencies.
3. Checking FFmpeg.
4. Starting FastAPI.
5. Starting the React frontend.
6. Opening the application in a browser.
7. Running tests.

Create convenient startup scripts where possible.

Never assume software is already installed without checking.

---

## 18. Definition of Done

The MVP is complete only when the following workflow succeeds:

**A.** I launch the local application.

**B.** I import an MP4 video containing hardcoded Chinese subtitles.

**C.** The video plays with functional playback controls.

**D.** I choose the subtitle region.

**E.** I click Analyze and the application runs real OCR.

**F.** Repeated frames showing the same subtitle are consolidated into appropriate subtitle segments.

**G.** The generated Chinese text has real, correctly aligned pinyin and word segmentation.

**H.** The player displays interactive subtitles synchronized with playback.

**I.** I can click Chinese words to inspect their dictionary entries.

**J.** I can view Vietnamese sentence translations when the translation model is available.

**K.** I can edit an OCR mistake, and the corrections persist.

**L.** I can save vocabulary and reopen a previously processed video without re-running OCR.

**M.** I can paste a Douyin URL, and the application attempts to import supported, accessible media, with understandable errors and an MP4 fallback.

Do not consider a static UI mockup or a demo returning hardcoded OCR results a completed MVP.

---

## 19. Expected Deliverables

Produce:

1. A real, runnable source-code project.
2. The complete frontend and backend implementation.
3. Required configuration and dependency files.
4. A working OCR processing pipeline.
5. A sample test video or reproducible test fixture generator.
6. Automated tests.
7. Full installation and run instructions.
8. A clear explanation of known limitations.

If you have access to a coding environment, create and edit the actual project files directly, execute the relevant commands and verify the results.

If you do not have access to a filesystem or execution environment, output complete runnable source files rather than pseudocode.

Clearly distinguish what has been implemented, what has been tested and what remains unverified.

If the implementation is too large for one response, work through the phases sequentially without abandoning the MVP requirements.

**Begin by briefly explaining the architecture and then immediately implement Phase 1. Continue through the remaining phases using actual code and tests. Do not ask unnecessary clarification questions; make sensible engineering decisions and document them.**



## Critical Product Requirement: Subtitle-First Learning Experience

This application must preserve the central experience of Miteiru: I can watch a video naturally while interacting with Chinese vocabulary.

OCR is only the mechanism for obtaining the subtitle text; it must not become the primary user experience.

The intended workflow is:

1. Import a video from Douyin or local MP4.
2. Analyze its hardcoded Chinese subtitles using OCR.
3. Generate timestamped Chinese subtitle segments.
4. Process each segment into segmented Chinese words, pinyin, vocabulary definitions and Vietnamese translations.
5. Play the video with the interactive language-learning subtitles synchronized to its timeline.
6. Allow clicking words, replaying sentences, pausing automatically and saving vocabulary.

Display the OCR-generated subtitles within the video player experience, not merely in a text results table.

Preserve the original video and audio. Do not require the user to view extracted frames separately.

For the first version, no login or account system is required. Store data locally.

Design the application so that a future Chrome Extension can use the same OCR and language-processing modules to annotate Douyin videos directly in the browser.
