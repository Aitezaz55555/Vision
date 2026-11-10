@echo off
setlocal enabledelayedexpansion
title VISION 1.2 - AI Voice Assistant

:: ============================================================================
:: VISION 1.2 - Windows 11 One-Click Launcher
:: ============================================================================

:: 1. Determine project directory dynamically from batch file location
set "PROJECT_DIR=%~dp0"
if "%PROJECT_DIR:~-1%"=="\" set "PROJECT_DIR=%PROJECT_DIR:~0,-1%"

:: 2. Navigate to project root
cd /d "%PROJECT_DIR%"

echo ===================================================
echo               VISION 1.2 - Launcher
echo ===================================================
echo Project Directory: %PROJECT_DIR%
echo.

:: 3. Read configured Ollama model from vision_config.json
set "CONFIGURED_MODEL=llama3.2:1b"
if exist "vision_config.json" (
    for /f "tokens=1* delims=:" %%A in ('findstr /i "\"ollama_model\"" vision_config.json') do (
        set "VAL=%%B"
        set "VAL=!VAL:"=!"
        set "VAL=!VAL:,=!"
        set "VAL=!VAL: =!"
        if not "!VAL!"=="" set "CONFIGURED_MODEL=!VAL!"
    )
)
echo [CONFIG] Target AI Model: %CONFIGURED_MODEL%

:: 4. Check whether Python is available
where python >nul 2>nul
if %errorlevel% neq 0 (
    echo.
    echo [ERROR] Python is not found in system PATH.
    echo Please install Python 3.10 - 3.13 from: https://www.python.org/downloads/
    echo Make sure to check "Add Python to PATH" during installation.
    echo.
    pause
    exit /b 1
)

:: 5. Check virtual environment
if not exist "%PROJECT_DIR%\.venv\Scripts\activate.bat" (
    echo.
    echo [WARNING] Virtual environment was not found in .venv.
    echo Running setup_windows.bat to configure dependencies...
    echo.
    call "%PROJECT_DIR%\setup_windows.bat"
    if not exist "%PROJECT_DIR%\.venv\Scripts\activate.bat" (
        echo [ERROR] Setup failed to create virtual environment. Aborting.
        pause
        exit /b 1
    )
)

:: 6. Activate virtual environment
call "%PROJECT_DIR%\.venv\Scripts\activate.bat"
if %errorlevel% neq 0 (
    echo [ERROR] Failed to activate virtual environment.
    pause
    exit /b 1
)
echo [OK] Virtual environment activated.

:: 7. Check / Start Ollama Service via Python (Robust & cross-version)
python -c "import vision; sys_ok = vision.is_ollama_service_running(); exit(0 if sys_ok else 1)" >nul 2>nul
if %errorlevel% neq 0 (
    echo [INFO] Starting local Ollama service...
    python -c "import vision; vision.start_ollama_service()" >nul 2>nul
)

:: 8. Launch actual application entry point: vision.py
echo ===================================================
echo   Starting VISION 1.2 AI Assistant...
echo   [Press Ctrl+C to stop]
echo ===================================================
echo.

python "%PROJECT_DIR%\vision.py" %*
set "APP_EXIT_CODE=%errorlevel%"

:: Error handling & keep terminal open
if %APP_EXIT_CODE% neq 0 (
    echo.
    echo ===================================================
    echo [ERROR] VISION 1.2 exited with code %APP_EXIT_CODE%.
    echo ===================================================
    pause
    exit /b %APP_EXIT_CODE%
)

echo.
echo [INFO] VISION closed cleanly.
pause
exit /b 0
