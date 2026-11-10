"""
VISION AI - Windows Application Control Module
Manages dynamic discovery, launching, closing, and window control of Windows applications.
Supports Start Menu shortcuts, Windows App Paths registry, standard PATH binaries,
registered UWP protocol activations, official Web fallbacks, and application caching.
"""

import json
import os
import shutil
import subprocess
import sys
import webbrowser
import winreg
from typing import Optional, Dict, Tuple, List
import psutil


# Canonical aliases mapping user spoken names to app keys
APP_ALIASES: Dict[str, List[str]] = {
    "chrome": ["google chrome", "chrome", "crome", "google browser", "google"],
    "vscode": ["vs code", "vscode", "visual studio code", "code editor", "coding editor",
               "my coding editor", "start coding", "code"],
    "whatsapp": ["whatsapp", "whatsapp desktop", "what's app", "whats app", "watsapp",
                 "take me to whatsapp", "open whatsapp"],
    "chatgpt": ["chatgpt", "chat gpt", "chatgpt desktop", "open ai", "openai", "gpt"],
    "notepad": ["notepad", "text editor", "note pad"],
    "calculator": ["calculator", "calc", "calculate", "calci"],
    "explorer": ["file explorer", "explorer", "my files", "files", "windows explorer", "my computer"],
    "edge": ["microsoft edge", "edge", "ms edge", "edge browser", "default browser"],
    "firefox": ["firefox", "mozilla firefox", "mozilla"],
    "opera": ["opera", "opera gx", "opera browser"],
    "taskmgr": ["task manager", "taskmgr", "task monitor", "processes", "system monitor"],
    "settings": ["settings", "windows settings", "system settings", "control panel"],
    "cmd": ["command prompt", "terminal", "cmd", "cmd prompt"],
    "powershell": ["powershell", "power shell", "ps"],
    "word": ["word", "ms word", "microsoft word"],
    "excel": ["excel", "ms excel", "microsoft excel"],
    "powerpoint": ["powerpoint", "power point", "ppt", "ms powerpoint"],
    "paint": ["paint", "ms paint", "drawing"],
    "spotify": ["spotify", "spotify music", "music app", "music player"],
    "discord": ["discord"],
    "snippingtool": ["snipping tool", "snip", "screen capture tool"],
    "camera": ["camera", "webcam"],
}

# Known process image names for closing applications gracefully
APP_PROCESS_MAP: Dict[str, List[str]] = {
    "chrome": ["chrome.exe"],
    "vscode": ["Code.exe"],
    "whatsapp": ["WhatsApp.exe"],
    "chatgpt": ["ChatGPT.exe"],
    "notepad": ["Notepad.exe", "notepad.exe"],
    "calculator": ["CalculatorApp.exe", "calc.exe", "Calculator.exe"],
    "explorer": ["explorer.exe"],
    "edge": ["msedge.exe"],
    "firefox": ["firefox.exe"],
    "opera": ["opera.exe"],
    "taskmgr": ["Taskmgr.exe", "taskmgr.exe"],
    "cmd": ["cmd.exe"],
    "powershell": ["powershell.exe", "pwsh.exe"],
    "word": ["WINWORD.EXE", "winword.exe"],
    "excel": ["EXCEL.EXE", "excel.exe"],
    "powerpoint": ["POWERPNT.EXE", "powerpnt.exe"],
    "paint": ["mspaint.exe"],
    "spotify": ["Spotify.exe"],
    "discord": ["Discord.exe"],
}

# Direct UWP/Windows protocol schemes or system executables
BUILTIN_COMMANDS: Dict[str, str] = {
    "calculator": "calc.exe",
    "notepad": "notepad.exe",
    "explorer": "explorer.exe",
    "taskmgr": "taskmgr.exe",
    "settings": "ms-settings:",
    "cmd": "cmd.exe",
    "powershell": "powershell.exe",
    "paint": "mspaint.exe",
    "snippingtool": "snippingtool.exe",
    "camera": "microsoft.windows.camera:",
}

# Registered Windows URI protocols for store/packaged desktop apps
APP_PROTOCOLS: Dict[str, str] = {
    "whatsapp": "whatsapp:",
    "chatgpt": "chatgpt:",
    "spotify": "spotify:",
    "settings": "ms-settings:",
    "camera": "microsoft.windows.camera:",
    "calculator": "calc:",
}

# Official web fallbacks when desktop application is not installed
WEB_FALLBACKS: Dict[str, Tuple[str, str]] = {
    "whatsapp": ("https://web.whatsapp.com", "WhatsApp Web"),
    "chatgpt": ("https://chatgpt.com", "ChatGPT"),
    "spotify": ("https://open.spotify.com", "Spotify Web Player"),
    "discord": ("https://discord.com/app", "Discord"),
}

CACHE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data", "app_cache.json")
_cached_app_paths: Optional[Dict[str, str]] = None


def normalize_app_name(raw_name: str) -> str:
    """Normalize user spoken phrase to identify canonical application key."""
    cleaned = raw_name.lower().strip()
    for filler in ("open", "launch", "start", "run", "close", "kill", "exit", "stop",
                   "please", "the", "my", "take me to", "take me", "desktop"):
        if cleaned.startswith(filler + " "):
            cleaned = cleaned[len(filler) + 1:].strip()
        if cleaned.endswith(" " + filler):
            cleaned = cleaned[:-len(filler) - 1].strip()

    # Exact match in canonical keys
    if cleaned in APP_ALIASES:
        return cleaned

    # Check aliases
    for canonical, aliases in APP_ALIASES.items():
        if cleaned == canonical or cleaned in aliases:
            return canonical
        for alias in aliases:
            if alias in cleaned or cleaned in alias:
                return canonical

    return cleaned


def is_protocol_registered(protocol_name: str) -> bool:
    """Checks whether a URI protocol scheme (e.g. 'whatsapp', 'chatgpt') is registered in Windows Registry."""
    if not sys.platform.startswith("win"):
        return False
    proto = protocol_name.rstrip(":")
    for root_key in (winreg.HKEY_CLASSES_ROOT, winreg.HKEY_CURRENT_USER):
        sub = proto if root_key == winreg.HKEY_CLASSES_ROOT else rf"Software\Classes\{proto}"
        try:
            with winreg.OpenKey(root_key, sub):
                return True
        except Exception:
            pass
    return False


def get_app_paths_registry() -> Dict[str, str]:
    """Dynamically scan Windows App Paths registry entries (HKCU & HKLM)."""
    registered = {}
    if not sys.platform.startswith("win"):
        return registered

    for root_key in (winreg.HKEY_CURRENT_USER, winreg.HKEY_LOCAL_MACHINE):
        try:
            with winreg.OpenKey(root_key, r"Software\Microsoft\Windows\CurrentVersion\App Paths") as key:
                count = winreg.QueryInfoKey(key)[0]
                for i in range(count):
                    try:
                        subkey_name = winreg.EnumKey(key, i)
                        with winreg.OpenKey(key, subkey_name) as subkey:
                            exe_path, _ = winreg.QueryValueEx(subkey, "")
                            clean = subkey_name.lower().replace(".exe", "")
                            registered[clean] = os.path.expandvars(exe_path)
                    except Exception:
                        pass
        except Exception:
            pass
    return registered


def scan_start_menu_shortcuts() -> Dict[str, str]:
    """Scan Start Menu directories for .lnk shortcuts."""
    shortcuts = {}
    if not sys.platform.startswith("win"):
        return shortcuts

    roots = [
        os.path.expandvars(r"%APPDATA%\Microsoft\Windows\Start Menu\Programs"),
        os.path.expandvars(r"%ProgramData%\Microsoft\Windows\Start Menu\Programs"),
    ]
    for r in roots:
        if not os.path.isdir(r):
            continue
        try:
            for root, _, files in os.walk(r):
                for f in files:
                    if f.lower().endswith(".lnk"):
                        name = f[:-4].lower().strip()
                        shortcuts[name] = os.path.join(root, f)
        except Exception:
            pass
    return shortcuts


def refresh_app_cache() -> Dict[str, str]:
    """Re-scans system for installed applications and persists to disk cache."""
    global _cached_app_paths
    cache: Dict[str, str] = {}

    # 1. Start Menu shortcuts
    shortcuts = scan_start_menu_shortcuts()
    cache.update(shortcuts)

    # 2. Registry App Paths
    reg = get_app_paths_registry()
    cache.update(reg)

    _cached_app_paths = cache
    try:
        os.makedirs(os.path.dirname(CACHE_FILE), exist_ok=True)
        with open(CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(cache, f, indent=2)
    except Exception as e:
        print(f"[AppManager] Warning writing cache: {e}")

    return cache


def get_cached_apps() -> Dict[str, str]:
    """Returns in-memory or loaded disk cache of discovered applications."""
    global _cached_app_paths
    if _cached_app_paths is not None:
        return _cached_app_paths

    if os.path.isfile(CACHE_FILE):
        try:
            with open(CACHE_FILE, "r", encoding="utf-8") as f:
                _cached_app_paths = json.load(f)
                return _cached_app_paths
        except Exception:
            pass

    return refresh_app_cache()


def find_application_path(app_key: str) -> Optional[str]:
    """
    Locates an application executable using multi-tier discovery:
    1. Built-in system command/protocol
    2. Registered Windows URI protocol (e.g. whatsapp:, chatgpt:)
    3. Common executable candidates
    4. Cached / live registry App Paths & Start Menu shortcuts
    5. Windows PATH resolution
    """
    # 1. Built-in command or protocol
    if app_key in BUILTIN_COMMANDS:
        return BUILTIN_COMMANDS[app_key]

    # 2. Registered Windows URI protocol
    if app_key in APP_PROTOCOLS:
        proto = APP_PROTOCOLS[app_key]
        if is_protocol_registered(proto):
            return proto

    # 3. Common direct binary candidates
    direct_candidates = {
        "vscode": ["code.cmd", "code.exe",
                   os.path.expandvars(r"%LOCALAPPDATA%\Programs\Microsoft VS Code\Code.exe"),
                   os.path.expandvars(r"%ProgramFiles%\Microsoft VS Code\Code.exe")],
        "chrome": ["chrome.exe",
                   os.path.expandvars(r"%ProgramFiles%\Google\Chrome\Application\chrome.exe"),
                   os.path.expandvars(r"%ProgramFiles(x86)%\Google\Chrome\Application\chrome.exe")],
        "edge": ["msedge.exe",
                 os.path.expandvars(r"%ProgramFiles(x86)%\Microsoft\Edge\Application\msedge.exe"),
                 os.path.expandvars(r"%ProgramFiles%\Microsoft\Edge\Application\msedge.exe")],
        "whatsapp": ["WhatsApp.exe",
                     os.path.expandvars(r"%LOCALAPPDATA%\WhatsApp\WhatsApp.exe"),
                     os.path.expandvars(r"%LOCALAPPDATA%\Programs\WhatsApp\WhatsApp.exe")],
        "chatgpt": ["ChatGPT.exe",
                    os.path.expandvars(r"%LOCALAPPDATA%\Programs\ChatGPT\ChatGPT.exe")],
        "spotify": ["Spotify.exe",
                    os.path.expandvars(r"%APPDATA%\Spotify\Spotify.exe")],
        "discord": [os.path.expandvars(r"%LOCALAPPDATA%\Discord\Update.exe")],
    }
    if app_key in direct_candidates:
        for c in direct_candidates[app_key]:
            found = shutil.which(c) if not os.path.isabs(c) else c
            if found and (os.path.isfile(found) or shutil.which(found)):
                return found

    # 4. Search cached apps (shortcuts and App Paths)
    cached = get_cached_apps()
    if app_key in cached and (os.path.exists(cached[app_key]) or cached[app_key].endswith(":")):
        return cached[app_key]

    for name, path in cached.items():
        if app_key in name or name in app_key:
            if os.path.exists(path):
                return path

    # 5. PATH resolution
    which_res = shutil.which(app_key)
    if which_res:
        return which_res

    return None


def launch_application(raw_name: str) -> Tuple[bool, str, Optional[str]]:
    """
    Launches a Windows application by natural name.
    If the desktop app is not installed, seamlessly falls back to official web app.
    Returns (success: bool, spoken_reply: str, canonical_key: Optional[str]).
    """
    app_key = normalize_app_name(raw_name)
    target = find_application_path(app_key)

    display_name = app_key.replace("vscode", "VS Code").replace("chatgpt", "ChatGPT").replace("whatsapp", "WhatsApp").title()

    if not target:
        # Check if an official Web Fallback exists
        if app_key in WEB_FALLBACKS:
            web_url, web_name = WEB_FALLBACKS[app_key]
            webbrowser.open(web_url)
            reply = f"{display_name} desktop app is not installed. Opening {web_name} in your browser."
            return True, reply, app_key

        # Graceful failure without popping up Windows error dialog
        return False, f"Sorry Sir, I could not find {display_name} on this computer.", None

    try:
        if target.endswith(":") or target.startswith("ms-settings:") or target.startswith("microsoft.windows.") or target.startswith("calc:"):
            # Protocol activation (e.g. 'whatsapp:', 'chatgpt:', 'ms-settings:')
            os.startfile(target)
        elif target.lower().endswith(".lnk"):
            # Shell shortcut activation
            os.startfile(target)
        else:
            # Standalone binary
            subprocess.Popen([target], shell=False)

        # Varied natural confirmations
        confirmations = {
            "vscode": "Launching VS Code now.",
            "chrome": "Opening Google Chrome.",
            "notepad": "Opening Notepad.",
            "calculator": "Starting Calculator.",
            "explorer": "Opening File Explorer.",
            "edge": "Opening Microsoft Edge.",
            "settings": "Opening Windows Settings.",
            "taskmgr": "Opening Task Manager.",
            "whatsapp": "Opening WhatsApp.",
            "chatgpt": "Opening ChatGPT.",
            "spotify": "Opening Spotify.",
        }
        reply = confirmations.get(app_key, f"Opening {display_name}.")
        return True, reply, app_key
    except Exception as e:
        print(f"[AppManager] Launch error for {app_key} ({target}): {e}")
        # If protocol activation failed, try web fallback if available
        if app_key in WEB_FALLBACKS:
            web_url, web_name = WEB_FALLBACKS[app_key]
            webbrowser.open(web_url)
            return True, f"Could not launch {display_name} desktop app. Opening {web_name} in your browser instead.", app_key

        return False, f"Failed to launch {display_name}.", None


def close_application(raw_name: str) -> Tuple[bool, str]:
    """
    Closes a running Windows application gracefully by natural name.
    Returns (success: bool, spoken_reply: str).
    """
    app_key = normalize_app_name(raw_name)
    display_name = app_key.replace("vscode", "VS Code").replace("chatgpt", "ChatGPT").replace("whatsapp", "WhatsApp").title()

    # Get target process names
    proc_targets = APP_PROCESS_MAP.get(app_key, [f"{app_key}.exe"])

    terminated_count = 0
    try:
        for proc in psutil.process_iter(["pid", "name"]):
            try:
                pname = proc.info.get("name") or ""
                if any(t.lower() == pname.lower() for t in proc_targets):
                    proc.terminate()
                    terminated_count += 1
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
    except Exception as e:
        print(f"[AppManager] Process iteration error: {e}")

    if terminated_count > 0:
        return True, f"Closed {display_name}."

    # Try taskkill as fallback
    try:
        for t in proc_targets:
            res = subprocess.run(["taskkill", "/IM", t], capture_output=True, text=True, timeout=3)
            if res.returncode == 0:
                return True, f"Closed {display_name}."
    except Exception:
        pass

    return False, f"{display_name} is not currently running."


def control_window(action: str) -> Tuple[bool, str]:
    """
    Controls foreground window state: 'minimize', 'maximize', 'restore'.
    Uses Windows User32 APIs via ctypes.
    """
    if not sys.platform.startswith("win"):
        return False, "Window control is only supported on Windows."

    try:
        import ctypes
        user32 = ctypes.windll.user32
        hwnd = user32.GetForegroundWindow()
        if not hwnd:
            return False, "No active window found to control."

        SW_MAXIMIZE = 3
        SW_MINIMIZE = 6
        SW_RESTORE = 9

        cmd_map = {
            "maximize": (SW_MAXIMIZE, "Window maximized."),
            "minimize": (SW_MINIMIZE, "Window minimized."),
            "restore": (SW_RESTORE, "Window restored."),
        }

        if action in cmd_map:
            code, msg = cmd_map[action]
            user32.ShowWindow(hwnd, code)
            return True, msg

        return False, f"Unknown window action: {action}"
    except Exception as e:
        return False, f"Window control error: {e}"
