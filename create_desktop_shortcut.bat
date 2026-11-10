@echo off
setlocal
title VISION 1.2 - Create Desktop Shortcut
echo Creating desktop shortcut for VISION 1.2...
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0create_shortcut.ps1"
echo.
pause
