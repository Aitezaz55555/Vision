@echo off
setlocal
cd /d "%~dp0"
title VISION AI - Push to GitHub (Aitezaz55555)

echo ===================================================
echo     VISION AI - Push to GitHub (Aitezaz55555)
echo ===================================================
echo Target Remote: https://github.com/Aitezaz55555/Vision.git
echo.
echo If you have not created the repository on GitHub yet:
echo   1. Visit https://github.com/new
echo   2. Name: Vision
echo   3. Leave it empty (do NOT check Initialize with README)
echo   4. Click "Create repository"
echo.
set /p CONTINUE="Press ENTER once the repository is created on GitHub (or 'q' to quit): "
if /i "%CONTINUE%"=="q" exit /b 0

echo.
echo Pushing all files and commits to https://github.com/Aitezaz55555/Vision.git...
git push -u origin main

if %errorlevel% equ 0 (
    echo.
    echo ===================================================
    echo [SUCCESS] Successfully pushed all files to GitHub!
    echo URL: https://github.com/Aitezaz55555/Vision
    echo ===================================================
) else (
    echo.
    echo ===================================================
    echo [NOTICE] Push failed or authentication required.
    echo Verify that https://github.com/Aitezaz55555/Vision exists.
    echo ===================================================
)

pause
