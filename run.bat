@echo off
REM ============================================================
REM  Raftaar Traffic System - one-click launcher
REM  Builds the dashboard (if needed), starts FastAPI and opens
REM  http://localhost:8000 - everything runs from that one link.
REM
REM  Usage:  run.bat            normal start
REM          run.bat rebuild    force a fresh dashboard build
REM  Port:   set PORT=9000 before running to use another port.
REM ============================================================
setlocal
cd /d "%~dp0"

if "%PORT%"=="" set PORT=8000
set URL=http://localhost:%PORT%

echo.
echo   RAFTAAR - Traffic Speed + Number Plate System
echo   ---------------------------------------------

REM ---- Python virtual environment ----------------------------
if not exist ".venv\Scripts\python.exe" (
    echo [setup] Creating Python virtual environment...
    python -m venv .venv || goto :error
    echo [setup] Installing backend packages ^(first run takes a while^)...
    ".venv\Scripts\python.exe" -m pip install -e . || goto :error
)

if not exist "weights\yolov8n.pt" (
    echo [warn] weights\yolov8n.pt not found - download YOLOv8n into the weights folder.
)

REM ---- Dashboard build ---------------------------------------
if /i "%1"=="rebuild" if exist "frontend\dist" rmdir /s /q "frontend\dist"

if not exist "frontend\dist\index.html" (
    where npm >nul 2>nul || (
        echo [error] Node.js / npm not found. Install Node.js from https://nodejs.org
        goto :error
    )
    pushd frontend
    if not exist "node_modules" (
        echo [setup] Installing dashboard packages...
        call npm install || (popd & goto :error)
    )
    echo [build] Building dashboard...
    call npm run build || (popd & goto :error)
    popd
)

REM ---- Start ---------------------------------------------------
echo.
echo   Open:  %URL%
echo   Stop:  press Ctrl+C in this window
echo.
start "" cmd /c "timeout /t 4 /nobreak >nul & start %URL%"
".venv\Scripts\python.exe" -m uvicorn app.main:app --host 127.0.0.1 --port %PORT%
goto :eof

:error
echo.
echo [error] Startup failed - see the messages above.
pause
exit /b 1
