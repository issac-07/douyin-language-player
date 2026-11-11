# Phase 1–3 dependency and asset notices

The source UI, SVG icons and generated test content are original to this project. No Miteiru source or assets are included. Dependency licences below were reviewed against installed package metadata and npm's lock-file metadata. This inventory does not replace each dependency's complete upstream licence, copyright or NOTICE text; keep those notices when redistributing the corresponding software.

## Python

Exact tested versions are in `backend/requirements-dev.lock.txt`. Complete notices are included in the distributions under `.venv/Lib/site-packages/*dist-info/licenses` or their licence metadata/files.

| Packages | Licence |
| --- | --- |
| FastAPI, AnyIO, Pydantic, pydantic-core, typing-inspection, annotated-doc, annotated-types, h11, iniconfig, pluggy, pytest, truststore | MIT |
| Uvicorn, Starlette, Click, Colorama, IDNA, httpx2, httpcore2 | BSD-3-Clause |
| Pygments | BSD-2-Clause |
| python-multipart, opentelemetry-api | Apache-2.0 |
| packaging | Apache-2.0 OR BSD-2-Clause |
| typing-extensions | PSF-2.0 |

## JavaScript / TypeScript

Exact versions, including optional platform-specific packages, are in `frontend/package-lock.json`. Upstream licence/NOTICE files are retained in `frontend/node_modules` after installation.

| Packages | Licence |
| --- | --- |
| React, React DOM, scheduler, Vite, Vitest, React Vite plugin, Rolldown, React type packages and most build/test utilities | MIT |
| TypeScript and platform binaries, Playwright and its test/core packages, detect-libc, expect-type | Apache-2.0 |
| Lightning CSS and platform binaries | MPL-2.0 |
| picocolors | ISC |
| source-map-js | BSD-3-Clause |
| tslib | 0BSD |

Lightning CSS is an unmodified build dependency. Its MPL notice and source availability requirements apply to redistribution of that component; no changes to it are made here. MIT/BSD/ISC/0BSD dependencies require retention of their respective licence/copyright notices as applicable. Apache packages may also include NOTICE files and patent terms. Review complete upstream notices when packaging a redistributed application; this source checkout is not a bundled installer.

## External tools and assets

- FFmpeg/FFprobe are invoked from the user's installation and are not bundled. The verified Gyan FFmpeg 9.0 binary reports `--enable-gpl --enable-version3`; its applicable GNU GPL terms remain with that external distribution. No executable is downloaded by the app.
- Edge is an existing Microsoft browser installation used for tests, not redistributed.
- Microsoft YaHei and Segoe UI are existing Windows fonts, not copied or bundled.
- The synthetic video generator creates original color patterns, a sine tone and original short caption text for testing. It downloads no media.
- RapidOCR 1.4.4 is Apache-2.0 and supplies its bundled Chinese PP-OCRv4 detector/recognizer plus classifier models. These are installed from its upstream wheel, with the upstream notices retained in the environment. Model/config SHA-256 identity is included in analysis metadata. See [RapidOCR](https://github.com/RapidAI/RapidOCR) and [the installed release](https://pypi.org/project/rapidocr-onnxruntime/1.4.4/).
- ONNX Runtime is MIT; OpenCV is Apache-2.0. Their binary wheels include additional third-party notices that must be preserved on redistribution. In particular, OpenCV's wheel may include FFmpeg components under their applicable LGPL terms; the separately installed GPL FFmpeg executable is a distinct distribution.
- NumPy is BSD-3-Clause with bundled native-library notices (including OpenBLAS/LAPACK and toolchain components); Pillow is MIT-CMU; Shapely is BSD-3-Clause with a bundled GEOS library under LGPL terms; Pyclipper, Six and PyYAML are MIT; FlatBuffers is Apache-2.0; Protobuf is BSD-3-Clause; tqdm uses MPL-2.0 and MIT notices. Exact versions are locked and complete notices remain in their installed distributions. No native dependency is modified here.
- Phase 3 adds Jieba and Pypinyin (MIT), Transformers/SentencePiece/Safetensors/Hugging Face Hub (Apache-2.0), Sacremoses (MIT), and CPU PyTorch (BSD-3-Clause plus its bundled notices). The complete tested dependency set is pinned in the lock file, with installed notices retained.

## Phase 3 language resources

**CC-CEDICT contributors, distributed by MDBG:** downloaded from the [official export](https://www.mdbg.net/chinese/dictionary?page=cedict), under [Creative Commons Attribution-ShareAlike 4.0](https://creativecommons.org/licenses/by-sa/4.0/). The installed snapshot contains 125,405 entries; its gzip SHA-256 is `c4450a361f0659bb1bf152577d07cc45f65dc280616b68b23bafc6fec817155b`. `data/resources/cedict-source.json` records these details. The SQLite conversion preserves the original entries/meanings, with no dictionary corrections added. UI links and vocabulary CSV include attribution/licence. Retain the source attribution/licence and applicable ShareAlike conditions when distributing this data or adaptations; the dictionary licence is separate from application source code.

**Helsinki-NLP / University of Helsinki OPUS-MT:** [opus-mt-zh-vi](https://huggingface.co/Helsinki-NLP/opus-mt-zh-vi), official revision `67ea2dbfbaf13a16772a40346d3d72b59e591443`, Apache-2.0 as stated by its model card. Model weights, tokenizer and card are downloaded explicitly into `data/resources/opus-mt-zh-vi`; the local manifest preserves file hashes. No model training or weight changes are performed. Keep the upstream model card, licence and applicable notices when redistributing model resources.

The project does not redistribute the real user video. Validation reads the local authorized copy and stores only local reports/screenshots. Translation text is model-generated; verified CC-CEDICT dictionary meanings are a separate source.
