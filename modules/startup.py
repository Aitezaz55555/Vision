"""
VISION AI - Windows Startup Manager
Configures VISION AI to start automatically on Windows logon in the background
without displaying a command window, without requiring administrator privileges.
"""

import os
import sys
from typing import Tuple


def get_project_root() -> str:
    """Returns absolute path to the project root directory."""
    return os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))


def get_windows_startup_dir(override_dir: str = None) -> str:
    """Returns the current user's Windows Startup folder or override directory for testing."""
    if override_dir:
        return override_dir
    return os.path.expandvars(r"%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup")


def get_startup_vbs_path(override_dir: str = None) -> str:
    """Returns path to the startup launcher script in the Startup folder."""
    return os.path.join(get_windows_startup_dir(override_dir), "VisionAI_Startup.vbs")


def generate_silent_launcher_vbs() -> str:
    """
    Generates a silent VBScript launcher in the project root that dynamically
    resolves its own folder (works on any USB drive letter or path) and starts
    VISION AI via pythonw.exe without opening any Command Prompt window.
    """
    proj = get_project_root()
    vbs_path = os.path.join(proj, "run_vision_silent.vbs")
    content = '''Dim fso, scriptDir, WshShell, pythonwExe, visionPy
Set fso = CreateObject("Scripting.FileSystemObject")
scriptDir = fso.GetParentFolderName(WScript.ScriptFullName)
Set WshShell = CreateObject("WScript.Shell")
WshShell.CurrentDirectory = scriptDir

pythonwExe = fso.BuildPath(scriptDir, ".venv\\Scripts\\pythonw.exe")
If Not fso.FileExists(pythonwExe) Then
    pythonwExe = fso.BuildPath(scriptDir, ".venv\\pythonw.exe")
End If
If Not fso.FileExists(pythonwExe) Then
    pythonwExe = "pythonw.exe"
End If

visionPy = fso.BuildPath(scriptDir, "vision.py")
If fso.FileExists(visionPy) Then
    WshShell.Run """" & pythonwExe & """ """ & visionPy & """", 0, False
End If

Set WshShell = Nothing
Set fso = Nothing
'''
    with open(vbs_path, "w", encoding="utf-8") as f:
        f.write(content)

    return vbs_path


def is_startup_enabled(override_dir: str = None) -> bool:
    """Checks whether the startup script exists in the Windows Startup directory."""
    return os.path.isfile(get_startup_vbs_path(override_dir))


def enable_startup(override_dir: str = None) -> Tuple[bool, str]:
    """
    Enables automatic background startup with Windows for the current user.
    Uses the per-user Startup directory without requiring admin rights.
    Gracefully handles USB drive letter changes and drive disconnection.
    """
    if not sys.platform.startswith("win"):
        return False, "Automatic startup with Windows is only supported on Windows operating systems."

    try:
        startup_dir = get_windows_startup_dir(override_dir)
        if not os.path.isdir(startup_dir):
            os.makedirs(startup_dir, exist_ok=True)

        proj = get_project_root()

        # Also generate local silent runner inside project
        generate_silent_launcher_vbs()

        # Write Startup VBScript that dynamically detects USB drive changes and exits silently if disconnected
        vbs_content = f'''Dim fso, WshShell, d, candidatePath, foundProj, pythonwExe, visionPy
Set fso = CreateObject("Scripting.FileSystemObject")
Set WshShell = CreateObject("WScript.Shell")

foundProj = ""
' 1. Check original configured directory first
candidatePath = "{proj}"
If fso.FolderExists(candidatePath) Then
    If fso.FileExists(fso.BuildPath(candidatePath, "vision.py")) Then
        foundProj = candidatePath
    End If
End If

' 2. If drive letter changed (common with USB drives), scan all ready drives
If foundProj = "" Then
    For Each d in fso.Drives
        If d.IsReady Then
            candidatePath = d.DriveLetter & ":\\Vision"
            If fso.FolderExists(candidatePath) Then
                If fso.FileExists(fso.BuildPath(candidatePath, "vision.py")) Then
                    foundProj = candidatePath
                    Exit For
                End If
            End If
        End If
    Next
End If

' 3. If USB drive is not connected, exit cleanly without showing any error popup
If foundProj = "" Then
    Set fso = Nothing
    Set WshShell = Nothing
    WScript.Quit 0
End If

WshShell.CurrentDirectory = foundProj
pythonwExe = fso.BuildPath(foundProj, ".venv\\Scripts\\pythonw.exe")
If Not fso.FileExists(pythonwExe) Then
    pythonwExe = fso.BuildPath(foundProj, ".venv\\pythonw.exe")
End If
If Not fso.FileExists(pythonwExe) Then
    pythonwExe = "pythonw.exe"
End If

visionPy = fso.BuildPath(foundProj, "vision.py")
If fso.FileExists(visionPy) Then
    WshShell.Run """" & pythonwExe & """ """ & visionPy & """", 0, False
End If

Set WshShell = Nothing
Set fso = Nothing
'''
        target_path = get_startup_vbs_path(override_dir)
        with open(target_path, "w", encoding="utf-8") as f:
            f.write(vbs_content)

        return True, "Vision has been configured to start automatically in the background when Windows starts."
    except Exception as e:
        return False, f"Failed to enable startup: {e}"


def disable_startup(override_dir: str = None) -> Tuple[bool, str]:
    """
    Disables automatic startup by removing the script from the Startup folder.
    """
    try:
        target_path = get_startup_vbs_path(override_dir)
        if os.path.isfile(target_path):
            os.remove(target_path)
            return True, "Automatic startup with Windows has been disabled."
        return True, "Automatic startup is already disabled."
    except Exception as e:
        return False, f"Failed to disable startup: {e}"


def get_startup_status(override_dir: str = None) -> str:
    """Returns human-readable startup status."""
    if is_startup_enabled(override_dir):
        return "Vision is currently configured to start automatically in the background on Windows startup."
    return "Vision is currently configured for manual startup."
