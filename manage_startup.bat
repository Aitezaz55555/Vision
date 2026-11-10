@echo off
setlocal
cd /d "%~dp0"
title VISION AI - Startup Configuration

echo ===================================================
echo           VISION AI - STARTUP MANAGER
echo ===================================================
echo.

if not exist ".venv\Scripts\python.exe" (
    echo [ERROR] Virtual environment not found. Please run setup_windows.bat first.
    pause
    exit /b 1
)

:MENU
echo [1] Check Startup Status
echo [2] Enable Auto-Start with Windows (Silent Background)
echo [3] Disable Auto-Start with Windows
echo [4] Launch VISION Silently in Background Right Now
echo [5] Exit
echo.
set /p CHOICE="Select an option (1-5): "

if "%CHOICE%"=="1" (
    echo.
    .venv\Scripts\python.exe -c "import modules.startup as s; print(s.get_startup_status())"
    echo.
    goto MENU
)
if "%CHOICE%"=="2" (
    echo.
    .venv\Scripts\python.exe -c "import modules.startup as s; ok, msg = s.enable_startup(); print(msg)"
    echo.
    goto MENU
)
if "%CHOICE%"=="3" (
    echo.
    .venv\Scripts\python.exe -c "import modules.startup as s; ok, msg = s.disable_startup(); print(msg)"
    echo.
    goto MENU
)
if "%CHOICE%"=="4" (
    echo.
    echo Starting VISION AI silently in the background...
    wscript.exe run_vision_silent.vbs
    echo VISION is now running in the background. Clap twice to activate!
    echo.
    pause
    exit /b 0
)
if "%CHOICE%"=="5" (
    exit /b 0
)

echo Invalid choice. Please try again.
echo.
goto MENU
