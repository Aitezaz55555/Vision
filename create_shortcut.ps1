# ==============================================================================
# VISION 1.2 - Desktop Shortcut Generator
# Creates a portable desktop shortcut pointing to run_vision_portable.bat
# Dynamically resolves the USB drive letter and runs without admin privileges.
# ==============================================================================

[CmdletBinding()]
param(
    [string]$DestinationDir = ""
)

$ErrorActionPreference = "Stop"

Write-Host "===================================================" -ForegroundColor Cyan
Write-Host "     VISION 1.2 - Desktop Shortcut Generator       " -ForegroundColor Cyan
Write-Host "===================================================" -ForegroundColor Cyan
Write-Host ""

try {
    # 1. Determine script directory (project root on USB drive)
    $scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Definition
    if (-not $scriptDir) {
        $scriptDir = (Get-Item -Path ".").FullName
    }

    $targetBatch = Join-Path $scriptDir "run_vision_portable.bat"
    if (-not (Test-Path $targetBatch)) {
        # Fallback to run_vision.bat if portable launcher is missing
        $targetBatch = Join-Path $scriptDir "run_vision.bat"
        if (-not (Test-Path $targetBatch)) {
            Write-Host "[ERROR] Neither run_vision_portable.bat nor run_vision.bat was found in: $scriptDir" -ForegroundColor Red
            exit 1
        }
    }

    # 2. Locate user's Desktop directory
    $desktopDir = $DestinationDir
    if (-not $desktopDir) {
        # Try Registry User Shell Folders first (handles OneDrive desktop redirection accurately)
        try {
            $regPath = Get-ItemPropertyValue -Path "HKCU:\Software\Microsoft\Windows\CurrentVersion\Explorer\User Shell Folders" -Name "Desktop" -ErrorAction SilentlyContinue
            if ($regPath) {
                $desktopDir = [System.Environment]::ExpandEnvironmentVariables($regPath)
            }
        } catch {}

        # Fallback to .NET SpecialFolder
        if (-not $desktopDir) {
            try {
                $special = [Environment]::GetFolderPath([Environment+SpecialFolder]::DesktopDirectory)
                if ($special) { $desktopDir = $special }
            } catch {}
        }

        # Fallback to standard USERPROFILE\Desktop
        if (-not $desktopDir -and $env:USERPROFILE) {
            $candidate = Join-Path $env:USERPROFILE "Desktop"
            $desktopDir = $candidate
        }
    }

    if (-not $desktopDir) {
        Write-Host "[ERROR] Could not resolve the Desktop directory path." -ForegroundColor Red
        exit 1
    }

    $shortcutPath = Join-Path $desktopDir "VISION AI.lnk"

    # 3. Create WScript.Shell COM Object
    $wshShell = New-Object -ComObject WScript.Shell
    $shortcut = $wshShell.CreateShortcut($shortcutPath)

    # 4. Configure Shortcut properties
    $shortcut.TargetPath = $targetBatch
    $shortcut.WorkingDirectory = $scriptDir
    $shortcut.Description = "VISION 1.2 - AI Voice Assistant"

    # Icon configuration: Use custom icon if present, otherwise shell32.dll holographic/display icon
    $customIcon = Join-Path $scriptDir "assets\vision.ico"
    if (Test-Path $customIcon) {
        $shortcut.IconLocation = "$customIcon,0"
    } else {
        $shortcut.IconLocation = "$env:SystemRoot\System32\shell32.dll,13"
    }

    $shortcut.Save()

    # Also save a copy inside the project folder for immediate local launch convenience
    $localShortcutPath = Join-Path $scriptDir "VISION AI.lnk"
    try {
        $localShortcut = $wshShell.CreateShortcut($localShortcutPath)
        $localShortcut.TargetPath = $targetBatch
        $localShortcut.WorkingDirectory = $scriptDir
        $localShortcut.Description = "VISION 1.2 - AI Voice Assistant"
        $localShortcut.IconLocation = "$env:SystemRoot\System32\shell32.dll,13"
        $localShortcut.Save()
    } catch {}

    # 5. Clean up COM object
    [System.Runtime.Interopservices.Marshal]::ReleaseComObject($wshShell) | Out-Null

    Write-Host "[OK] Desktop shortcut created successfully!" -ForegroundColor Green
    Write-Host "     Name:     VISION AI.lnk" -ForegroundColor White
    Write-Host "     Location: $shortcutPath" -ForegroundColor White
    Write-Host "     Target:   $targetBatch" -ForegroundColor White
    Write-Host "     WorkDir:  $scriptDir" -ForegroundColor White
    Write-Host ""
    Write-Host "You can now double-click 'VISION AI' on your Desktop to start VISION!" -ForegroundColor Cyan
    Write-Host ""
    exit 0
}
catch {
    Write-Host "[ERROR] Failed to create desktop shortcut: $_" -ForegroundColor Red
    exit 1
}
