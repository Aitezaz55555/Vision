@echo off
setlocal
cd /d "%~dp0"
title VISION AI - Stop Assistant

echo ===================================================
echo             STOPPING VISION AI
echo ===================================================
echo.

if exist ".venv\Scripts\python.exe" (
    .venv\Scripts\python.exe -c "import os, psutil; killed = 0; [exec('p.kill(); killed += 1', {'p': p, 'killed': killed}) for p in psutil.process_iter(['pid', 'name', 'cmdline']) if p.name().lower().startswith(('python', 'pythonw')) and p.pid != os.getpid() and any(k in ' '.join(p.info.get('cmdline') or []) for k in ['vision.py', 'interface.py'])]; print('[OK] VISION processes checked and stopped.')"
) else (
    taskkill /F /FI "WINDOWTITLE eq VISION*" >nul 2>&1
    taskkill /F /IM pythonw.exe >nul 2>&1
    echo [OK] Sent termination signal.
)

:: Clear speaking flag if left over
if exist "data\speaking.flag" del /f /q "data\speaking.flag" >nul 2>&1
if exist "speaking.flag" del /f /q "speaking.flag" >nul 2>&1

echo.
echo ===================================================
echo [SUCCESS] VISION AI has been stopped.
echo ===================================================
echo.
pause
