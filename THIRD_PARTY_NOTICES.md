# Phase 1 and 2 dependency and asset notices

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
- No Vietnamese translation model or CC-CEDICT data is installed in Phase 2. Those integrations require their own licence/provenance review.
