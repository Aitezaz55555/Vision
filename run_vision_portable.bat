@echo off
setlocal enabledelayedexpansion
title VISION 1.2 - Portable USB Launcher

:: ============================================================================
:: VISION 1.2 - USB Portable Launcher
:: Completely self-contained for External USB Flash Drives & External SSDs
:: ============================================================================

:: 1. Dynamic Root Resolution (Works on ANY drive letter: E:, F:, G:, D:, etc.)
set "PROJECT_DIR=%~dp0"
if "%PROJECT_DIR:~-1%"=="\" set "PROJECT_DIR=%PROJECT_DIR:~0,-1%"

:: Extract current drive letter (e.g. "E:")
set "DRIVE_LETTER=%~d0"

:: Navigate to USB project root
cd /d "%PROJECT_DIR%"

echo ===================================================
echo        VISION 1.2 - Portable USB Edition
echo ===================================================
echo USB Drive:        %DRIVE_LETTER%
echo Project Path:     %PROJECT_DIR%
echo.

:: 2. Verify Drive Accessibility and Writable Permissions
set "WRITE_TEST_FILE=%PROJECT_DIR%\data\.write_test"
if not exist "%PROJECT_DIR%\data" mkdir "%PROJECT_DIR%\data" >nul 2>nul
echo test > "%WRITE_TEST_FILE%" 2>nul
if not exist "%WRITE_TEST_FILE%" (
    echo [ERROR] USB Drive is read-only or not writable!
    echo Please check write-protection on your external drive.
    pause
    exit /b 1
)
del "%WRITE_TEST_FILE%" >nul 2>nul

:: 3. Ensure Portable Project Directories Exist
if not exist "%PROJECT_DIR%\data" mkdir "%PROJECT_DIR%\data" >nul 2>nul
if not exist "%PROJECT_DIR%\data\screenshots" mkdir "%PROJECT_DIR%\data\screenshots" >nul 2>nul
if not exist "%PROJECT_DIR%\data\photos" mkdir "%PROJECT_DIR%\data\photos" >nul 2>nul
if not exist "%PROJECT_DIR%\data\logs" mkdir "%PROJECT_DIR%\data\logs" >nul 2>nul

:: Signal portable execution to Python
set "VISION_PORTABLE=1"

:: 4. Read configured Ollama model from vision_config.json
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

:: 5. Python Environment Detection
where python >nul 2>nul
if %errorlevel% neq 0 (
    echo.
    echo [ERROR] Python was not found on this Windows laptop.
    echo To run VISION portably, the host computer must have Python 3.10 to 3.13 installed.
    echo Download: https://www.python.org/downloads/ - check "Add Python to PATH".
    echo.
    pause
    exit /b 1
)

:: 6. Portable Virtual Environment Check & Auto-Healing
set "VENV_DIR=%PROJECT_DIR%\.venv"
set "PYTHON_EXE="

if exist "%VENV_DIR%\Scripts\python.exe" (
    "%VENV_DIR%\Scripts\python.exe" -c "import sys; sys.exit(0)" >nul 2>nul
    if !errorlevel! equ 0 set "PYTHON_EXE=%VENV_DIR%\Scripts\python.exe"
)

if defined PYTHON_EXE (
    echo [OK] Compatible virtual environment found in .venv.
) else (
    echo [SETUP] Virtual environment is missing or incompatible with this PC.
    echo [SETUP] Configuring compatible virtual environment on this PC...
    call "%PROJECT_DIR%\setup_windows.bat"
    if not exist "%VENV_DIR%\Scripts\python.exe" (
        echo [ERROR] Portable environment configuration failed.
        pause
        exit /b 1
    )
    set "PYTHON_EXE=%VENV_DIR%\Scripts\python.exe"
)

:: Activate the virtual environment
call "%VENV_DIR%\Scripts\activate.bat"

:: 7. Optional Portable Ollama Models Directory Configuration
set "PORTABLE_MODELS_DIR=%PROJECT_DIR%\OllamaModels"
if not exist "%PORTABLE_MODELS_DIR%" mkdir "%PORTABLE_MODELS_DIR%" >nul 2>nul

echo.
echo [PORTABILITY] Portable models directory: %PORTABLE_MODELS_DIR%
echo Do you want Ollama to store/load AI models directly from this USB drive?
echo Press ENTER for YES [recommended for USB], or type N for host computer storage.
set "USE_PORTABLE_MODELS=Y"
set /p USE_PORTABLE_MODELS="Choice [Y/n] (Press ENTER for Yes): "

if /i not "!USE_PORTABLE_MODELS!"=="N" (
    set "OLLAMA_MODELS=%PORTABLE_MODELS_DIR%"
    echo [OK] OLLAMA_MODELS configured for this session: %PORTABLE_MODELS_DIR%
) else (
    echo [OK] Using host computer default Ollama models storage.
)
echo.

:: 8. Check / Start Ollama Service via Python (Robust & cross-version)
python -c "import vision; sys_ok = vision.is_ollama_service_running(); exit(0 if sys_ok else 1)" >nul 2>nul
if %errorlevel% neq 0 (
    echo [INFO] Starting Ollama background server...
    python -c "import vision; vision.start_ollama_service()" >nul 2>nul
)

:: 9. Launch Application Entry Point
echo ===================================================
echo     Launching VISION 1.2 from USB Drive...
echo     [Press Ctrl+C to stop]
echo ===================================================
echo.

python "%PROJECT_DIR%\vision.py" %*
set "APP_EXIT_CODE=%errorlevel%"

:: 10. Error Handling & Keep Terminal Open
if %APP_EXIT_CODE% neq 0 (
    echo.
    echo ===================================================
    echo [ERROR] VISION 1.2 stopped with code %APP_EXIT_CODE%.
    echo ===================================================
    pause
    exit /b %APP_EXIT_CODE%
)

echo.
echo [INFO] VISION 1.2 closed cleanly.
pause
exit /b 0
