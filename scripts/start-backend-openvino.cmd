@echo off
cd /d "%~dp0.."
if not exist "data\ocr-env\Scripts\python.exe" (
  echo Set up the optional isolated OpenVINO environment as described in docs/OCR_PERFORMANCE_VALIDATION.md.
  exit /b 1
)
"data\ocr-env\Scripts\python.exe" -m uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8000
