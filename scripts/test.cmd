@echo off
cd /d "%~dp0.."
".venv\Scripts\python.exe" -m pytest backend/tests -q
if errorlevel 1 exit /b 1
cd frontend
call npm.cmd test
if errorlevel 1 exit /b 1
call npm.cmd run build
if errorlevel 1 exit /b 1
call npm.cmd run test:e2e
