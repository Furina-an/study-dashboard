@echo off
setlocal
REM ---------- Port (cloud can inject PORT env var) ----------
if defined PORT (set "APP_PORT=%PORT%") else (set "APP_PORT=8000")
title StudyDash Launcher
cd /d "%~dp0"

echo ==========================================
echo   StudyDash - One-click Launcher
echo ==========================================
echo.

REM ---------- 1. Backend venv ----------
if exist "backend\.venv\Scripts\python.exe" goto backend_ready
echo [1/4] First run: creating venv and installing backend deps
pushd backend
python -m venv .venv
if errorlevel 1 goto :fail
.venv\Scripts\python.exe -m pip install -r requirements.txt
if errorlevel 1 goto :fail
popd
goto backend_done
:backend_ready
echo [1/4] Backend env ready.
:backend_done

REM ---------- 2. Frontend deps ----------
if exist "frontend\node_modules" goto frontend_ready
echo [2/4] First run: installing frontend deps (need internet)
pushd frontend
call npm.cmd install
if errorlevel 1 goto :fail
popd
goto frontend_done
:frontend_ready
echo [2/4] Frontend deps ready.
:frontend_done

REM ---------- 3. Build frontend if missing ----------
if exist "frontend\dist\index.html" goto dist_ready
echo [3/4] Building frontend pages
pushd frontend
call npm.cmd run build
if errorlevel 1 goto :fail
popd
goto dist_done
:dist_ready
echo [3/4] Frontend pages built.
:dist_done

REM ---------- 4. Check if backend already running ----------
curl -s http://127.0.0.1:%APP_PORT%/api/health 2>nul | findstr /C:"ok" >nul
if not errorlevel 1 goto :open

REM ---------- 5. Start backend (log to backend\backend.log) ----------
echo [4/4] Starting backend service
start "" /B cmd /c "cd /d %~dp0backend && .venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port %APP_PORT% >> backend.log 2>&1"

REM ---------- Wait for backend (max 30s) ----------
echo Waiting for backend to be ready (up to 30s)
set /a tries=0
:wait_loop
set /a tries+=1
if %tries% gtr 30 goto :timeout
curl -s http://127.0.0.1:%APP_PORT%/api/health 2>nul | findstr /C:"ok" >nul
if not errorlevel 1 goto :open
ping -n 2 127.0.0.1 >nul
goto :wait_loop

:open
echo.
echo Backend is ready. Opening browser...
start "" "http://127.0.0.1:%APP_PORT%"
echo.
echo App URL: http://127.0.0.1:%APP_PORT%
echo Backend log: backend\backend.log
echo Dev mode: cd frontend ^&^& npm.cmd run dev
echo Stop: close this window.
echo.
pause
exit /b 0

:timeout
echo.
echo [ERROR] Backend did not start within 30s.
echo [HINT] Check backend\backend.log below:
echo ------------------------------------------
type "%~dp0backend\backend.log" 2>nul
echo ------------------------------------------
echo [HINT] Common causes:
echo   - Port %APP_PORT% is occupied by another program (set PORT to another value)
echo   - Missing Python deps (run: cd backend ^&^& .venv\Scripts\python.exe -m pip install -r requirements.txt)
echo   - Python version too new/old for dependencies (see README)
echo.
pause
exit /b 1

:fail
echo.
echo [ERROR] Setup failed. Check the messages above.
pause
exit /b 1