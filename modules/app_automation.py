"""
VISION AI - Windows Application Automation Subsystem
Provides robust, verified desktop interaction, window control, keyboard automation,
process discovery, and state inspection using native Win32 APIs and psutil.
"""

import ctypes
import os
import subprocess
import time
from typing import List, Dict, Any, Optional, Tuple

import psutil

# Optional Win32 GUI imports with graceful fallback
try:
    import win32gui
    import win32process
    import win32con
    import win32api
    HAS_WIN32 = True
except Exception:
    HAS_WIN32 = False


def list_open_windows() -> List[Dict[str, Any]]:
    """List all currently visible top-level desktop windows with titles and process IDs."""
    if not HAS_WIN32:
        return []

    windows = []
    def _enum_handler(hwnd, _):
        if win32gui.IsWindowVisible(hwnd) and win32gui.GetWindowText(hwnd):
            title = win32gui.GetWindowText(hwnd).strip()
            if title and not win32gui.GetParent(hwnd):
                try:
                    _, pid = win32process.GetWindowThreadProcessId(hwnd)
                    proc_name = psutil.Process(pid).name() if psutil.pid_exists(pid) else "unknown"
                    windows.append({
                        "hwnd": hwnd,
                        "title": title,
                        "pid": pid,
                        "process": proc_name
                    })
                except Exception:
                    pass
        return True

    try:
        win32gui.EnumWindows(_enum_handler, None)
    except Exception as e:
        print(f"[Automation] EnumWindows notice: {e}")
    return windows


def find_window_by_name(query: str) -> Optional[Dict[str, Any]]:
    """Find a window whose title or process name contains query (case-insensitive)."""
    q = query.lower().strip()
    for w in list_open_windows():
        if q in w["title"].lower() or q in w["process"].lower():
            return w
    return None


def focus_window(query_or_hwnd: Any) -> bool:
    """Bring target window to the foreground and set focus."""
    if not HAS_WIN32:
        return False

    hwnd = query_or_hwnd if isinstance(query_or_hwnd, int) else None
    if hwnd is None and isinstance(query_or_hwnd, str):
        w = find_window_by_name(query_or_hwnd)
        if w:
            hwnd = w["hwnd"]

    if not hwnd:
        return False

    try:
        # If minimized, restore it first
        if win32gui.IsIconic(hwnd):
            win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
        
        # Attach thread input to ensure SetForegroundWindow succeeds
        current_thread_id = win32api.GetCurrentThreadId()
        window_thread_id, _ = win32process.GetWindowThreadProcessId(hwnd)
        
        if current_thread_id != window_thread_id:
            ctypes.windll.user32.AttachThreadInput(current_thread_id, window_thread_id, True)
            win32gui.SetForegroundWindow(hwnd)
            win32gui.SetFocus(hwnd)
            ctypes.windll.user32.AttachThreadInput(current_thread_id, window_thread_id, False)
        else:
            win32gui.SetForegroundWindow(hwnd)
            win32gui.SetFocus(hwnd)
        time.sleep(0.1)
        return True
    except Exception as e:
        print(f"[Automation] Focus error on window {hwnd}: {e}")
        return False


def send_keystrokes_to_app(app_name: str, keys: str) -> bool:
    """Focus target application and send typed text."""
    if not focus_window(app_name):
        return False
    time.sleep(0.15)
    return type_text_native(keys)


def send_shortcut(app_name: str, modifier: str, key_char: str) -> bool:
    """Send shortcut like Ctrl+F or Alt+C to target app."""
    if not focus_window(app_name):
        return False
    time.sleep(0.1)

    vk_map = {
        "ctrl": 0x11,
        "alt": 0x12,
        "shift": 0x10,
        "enter": 0x0D,
        "esc": 0x1B,
        "tab": 0x09
    }

    mod_vk = vk_map.get(modifier.lower(), 0x11)
    target_vk = ord(key_char.upper()) if len(key_char) == 1 else vk_map.get(key_char.lower(), 0)

    try:
        user32 = ctypes.windll.user32
        # Key down modifier
        user32.keybd_event(mod_vk, 0, 0, 0)
        time.sleep(0.05)
        # Key down target
        user32.keybd_event(target_vk, 0, 0, 0)
        time.sleep(0.05)
        # Key up target
        user32.keybd_event(target_vk, 0, 2, 0)
        time.sleep(0.05)
        # Key up modifier
        user32.keybd_event(mod_vk, 0, 2, 0)
        return True
    except Exception as e:
        print(f"[Automation] Send shortcut failed: {e}")
        return False


def type_text_native(text: str) -> bool:
    """Type text into the currently active control using SendInput."""
    try:
        user32 = ctypes.windll.user32
        for char in text:
            # Handle standard ASCII characters via VkKeyScan
            vk = user32.VkKeyScanW(ord(char))
            virtual_key = vk & 0xFF
            shift_state = (vk >> 8) & 0xFF

            if shift_state & 1:  # Shift needed
                user32.keybd_event(0x10, 0, 0, 0)

            user32.keybd_event(virtual_key, 0, 0, 0)
            time.sleep(0.01)
            user32.keybd_event(virtual_key, 0, 2, 0)

            if shift_state & 1:
                user32.keybd_event(0x10, 0, 2, 0)
            time.sleep(0.01)
        return True
    except Exception as e:
        print(f"[Automation] Type text failed: {e}")
        return False
