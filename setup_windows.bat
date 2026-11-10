@echo off
setlocal enabledelayedexpansion
title VISION 1.2 - Windows 11 Setup & Dependency Installer

echo ==============================================================================
echo                      VISION 1.2 - Setup Automation
echo                   Windows 11 + External USB Edition
echo ==============================================================================
echo.

set "SCRIPT_DIR=%~dp0"
if "%SCRIPT_DIR:~-1%"=="\" set "SCRIPT_DIR=%SCRIPT_DIR:~0,-1%"
cd /d "%SCRIPT_DIR%"

:: ------------------------------------------------------------------------------
:: 1 & 2. Check Python installation and Version Compatibility (3.10 - 3.13)
:: ------------------------------------------------------------------------------
echo [STEP 1/7] Checking Python installation and version...
where python >nul 2>nul
if %errorlevel% neq 0 (
    echo.
    echo [ERROR] Python was not found in system PATH.
    echo Please install Python 3.10 - 3.13 from:
    echo   https://www.python.org/downloads/
    echo IMPORTANT: Remember to check "Add Python to PATH" during installation.
    echo.
    pause
    exit /b 1
)

for /f "tokens=*" %%v in ('python --version 2^>^&1') do set "PY_VER=%%v"
echo [OK] Found %PY_VER%

:: Verify major/minor version (3.10 to 3.13)
python -c "import sys; v = sys.version_info; sys.exit(0 if (v.major == 3 and 10 <= v.minor <= 13) else 1)" >nul 2>nul
if %errorlevel% neq 0 (
    echo [WARNING] Python version may not be in the tested 3.10-3.13 range.
    echo VISION 1.2 is optimized for Python 3.10, 3.11, 3.12, or 3.13 on Windows 11.
    echo Proceeding anyway...
)

:: ------------------------------------------------------------------------------
:: 3 & 4. Check pip and Create Virtual Environment
:: ------------------------------------------------------------------------------
echo.
echo [STEP 2/7] Checking pip and Virtual Environment...
python -m pip --version >nul 2>nul
if %errorlevel% neq 0 (
    echo [ERROR] pip module is not installed for Python.
    echo Run: python -m ensurepip --upgrade
    pause
    exit /b 1
)

set "VENV_DIR=%SCRIPT_DIR%\.venv"
if not exist "%VENV_DIR%\Scripts\activate.bat" (
    echo [INFO] Creating new virtual environment at "%VENV_DIR%"...
    python -m venv "%VENV_DIR%"
    if %errorlevel% neq 0 (
        echo [ERROR] Failed to create virtual environment. Check disk space and permissions.
        pause
        exit /b 1
    )
    echo [OK] Virtual environment created successfully.
) else (
    echo [OK] Virtual environment exists at "%VENV_DIR%".
)

:: Activate the venv
call "%VENV_DIR%\Scripts\activate.bat"
if %errorlevel% neq 0 (
    echo [ERROR] Failed to activate virtual environment.
    pause
    exit /b 1
)

:: ------------------------------------------------------------------------------
:: 5 & 6. Upgrade pip and Install Dependencies from requirements-windows.txt
:: ------------------------------------------------------------------------------
echo.
echo [STEP 3/7] Installing Windows 11 dependencies from requirements-windows.txt...
python -m pip install --upgrade pip --quiet
python -m pip install -r "%SCRIPT_DIR%\requirements-windows.txt"
if %errorlevel% neq 0 (
    echo.
    echo [ERROR] One or more dependencies failed to install.
    echo Please review the pip error output above.
    pause
    exit /b 1
)
echo [OK] All requirements installed successfully.

:: ------------------------------------------------------------------------------
:: 7. Verify Critical Core Packages
:: ------------------------------------------------------------------------------
echo.
echo [STEP 4/7] Verifying critical modules...
set "VERIFY_FAILED=0"

for %%P in (speech_recognition pyaudio cv2 mediapipe pycaw edge_tts ollama pygame pyttsx3 PIL psutil) do (
    python -c "import %%P" >nul 2>nul
    if !errorlevel! neq 0 (
        echo   [FAIL] Module '%%P' failed to import.
        set "VERIFY_FAILED=1"
    ) else (
        echo   [PASS] Module '%%P' is verified.
    )
)

if "!VERIFY_FAILED!"=="1" (
    echo.
    echo [ERROR] One or more critical modules failed verification.
    pause
    exit /b 1
)
echo [OK] All critical modules verified.

:: ------------------------------------------------------------------------------
:: 8. Create Application Data Directories
:: ------------------------------------------------------------------------------
echo.
echo [STEP 5/7] Preparing portable data directories...
if not exist "%SCRIPT_DIR%\data" mkdir "%SCRIPT_DIR%\data" >nul 2>nul
if not exist "%SCRIPT_DIR%\data\screenshots" mkdir "%SCRIPT_DIR%\data\screenshots" >nul 2>nul
if not exist "%SCRIPT_DIR%\data\photos" mkdir "%SCRIPT_DIR%\data\photos" >nul 2>nul
if not exist "%SCRIPT_DIR%\data\logs" mkdir "%SCRIPT_DIR%\data\logs" >nul 2>nul
echo [OK] Data directories ready (data/, screenshots/, photos/, logs/).

:: ------------------------------------------------------------------------------
:: 9. Ensure Hand Tracking Model is Available (hand_landmarker.task)
:: ------------------------------------------------------------------------------
echo.
echo [STEP 6/7] Checking MediaPipe hand landmark model...
if not exist "%SCRIPT_DIR%\hand_landmarker.task" (
    echo [INFO] Downloading hand_landmarker.task model [~7.8 MB]...
    curl.exe -L -o "%SCRIPT_DIR%\hand_landmarker.task" "https://storage.googleapis.com/mediapipe-models/hand_landmarker/hand_landmarker/float16/1/hand_landmarker.task"
    if %errorlevel% neq 0 (
        echo [WARNING] Failed to download hand_landmarker.task. Hand tracking will be disabled.
    ) else (
        echo [OK] hand_landmarker.task downloaded successfully.
    )
) else (
    echo [OK] hand_landmarker.task model is present.
)

:: ------------------------------------------------------------------------------
:: 10. Check Ollama Installation & Configured Model
:: ------------------------------------------------------------------------------
echo.
echo [STEP 7/7] Checking Ollama Local AI LLM Service...
set "CONFIGURED_MODEL=llama3.2:1b"
if exist "%SCRIPT_DIR%\vision_config.json" (
    for /f "tokens=1* delims=:" %%A in ('findstr /i "\"ollama_model\"" "%SCRIPT_DIR%\vision_config.json"') do (
        set "VAL=%%B"
        set "VAL=!VAL:"=!"
        set "VAL=!VAL:,=!"
        set "VAL=!VAL: =!"
        if not "!VAL!"=="" set "CONFIGURED_MODEL=!VAL!"
    )
)

set "OLLAMA_EXE="
where ollama >nul 2>nul && for /f "delims=" %%I in ('where ollama') do if not defined OLLAMA_EXE set "OLLAMA_EXE=%%I"
if not defined OLLAMA_EXE if exist "%LOCALAPPDATA%\Programs\Ollama\ollama.exe" set "OLLAMA_EXE=%LOCALAPPDATA%\Programs\Ollama\ollama.exe"
if not defined OLLAMA_EXE if exist "%ProgramFiles%\Ollama\ollama.exe" set "OLLAMA_EXE=%ProgramFiles%\Ollama\ollama.exe"

if defined OLLAMA_EXE (
    echo [OK] Ollama is installed at: "%OLLAMA_EXE%"
    powershell -NoProfile -Command "try { $r = Invoke-RestMethod -Uri 'http://127.0.0.1:11434/api/tags' -TimeoutSec 2; $names = $r.models | ForEach-Object { $_.name }; if ($names -match '%CONFIGURED_MODEL%') { exit 0 } else { exit 2 } } catch { exit 1 }" >nul 2>nul
    set "OLL_STATUS=!errorlevel!"
    if "!OLL_STATUS!"=="0" (
        echo [OK] AI model '%CONFIGURED_MODEL%' is installed and ready.
    ) else if "!OLL_STATUS!"=="2" (
        echo [NOTICE] Model '%CONFIGURED_MODEL%' is not yet pulled.
        echo To download it, run: "%OLLAMA_EXE%" pull %CONFIGURED_MODEL%
    ) else (
        echo [NOTICE] Ollama service is not currently running. It will start automatically when launching VISION.
    )
) else (
    echo [WARNING] Ollama is not installed on this system.
    echo To enable genuine local AI conversational chat:
    echo   1. Download Ollama for Windows: https://ollama.com/download/windows
    echo   2. Run the installer.
    echo   3. Pull the recommended model: ollama pull %CONFIGURED_MODEL%
)

:: ------------------------------------------------------------------------------
:: Final Summary
:: ------------------------------------------------------------------------------
echo.
echo ==============================================================================
echo                      SETUP COMPLETED SUCCESSFULLY!
echo ==============================================================================
echo VISION 1.2 is now ready for use on this Windows 11 machine.
echo.
echo Launch Options:
echo   - Standard PC launch:        run_vision.bat
echo   - Portable USB launch:       run_vision_portable.bat
echo   - Create Desktop Shortcut:   create_desktop_shortcut.bat (or create_shortcut.ps1)
echo ==============================================================================
echo.
pause
