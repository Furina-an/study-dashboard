@echo off
setlocal
REM ---------- Backend-only launcher (for npm run dev workflow) ----------
if defined PORT (set "APP_PORT=%PORT%") else (set "APP_PORT=8000")
title StudyDash Backend
cd /d "%~dp0backend"
if exist ".venv\Scripts\python.exe" goto ready
echo First run: creating venv and installing deps
python -m venv .venv
if errorlevel 1 goto :fail
.venv\Scripts\python.exe -m pip install -r requirements.txt
if errorlevel 1 goto :fail
:ready
echo Starting backend on http://127.0.0.1:%APP_PORT%  (Ctrl+C to stop)
.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port %APP_PORT%
pause
exit /b 0
:fail
echo [ERROR] Setup failed.
pause
exit /b 1