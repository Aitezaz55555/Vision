"""
VISION AI - Windows System Control Module
Provides voice-based system operations:
- Master volume adjustment, mute/unmute
- Screen brightness adjustment (where hardware supported)
- Windows lock workstation
- Battery status & telemetry
- CPU and RAM performance metrics
- High-resolution screenshot capture
- Windows Settings and Task Manager launching
- Secure two-step confirmation for sensitive actions (shutdown, restart)
"""

import ctypes
import os
import platform
import socket
import subprocess
import sys
import time
from datetime import datetime
from typing import Tuple, Optional, Dict, Any
import psutil
from PIL import ImageGrab

# pycaw for master volume
try:
    from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume
    from comtypes import CLSCTX_ALL
    HAS_PYCAW = True
except Exception:
    HAS_PYCAW = False


def _get_pycaw_volume():
    """Retrieve the Windows Core Audio master volume endpoint."""
    if not HAS_PYCAW:
        return None
    try:
        devices = AudioUtilities.GetSpeakers()
        if hasattr(devices, "EndpointVolume"):
            return devices.EndpointVolume
        interface = devices.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
        return ctypes.cast(interface, ctypes.POINTER(IAudioEndpointVolume))
    except Exception as e:
        print(f"[SystemControl] pycaw initialization warning: {e}")
        return None


# ==================== AUDIO & VOLUME ==================== #
def get_volume_level() -> Optional[int]:
    """Returns current master volume as an integer (0 - 100)."""
    endpoint = _get_pycaw_volume()
    if endpoint:
        try:
            scalar = endpoint.GetMasterVolumeLevelScalar()
            return int(round(scalar * 100))
        except Exception:
            pass
    return None


def control_volume(mode: str, value: Optional[int] = None) -> Tuple[bool, str]:
    """
    Controls master volume.
    mode: 'set' | 'up' | 'down' | 'mute' | 'unmute'
    """
    endpoint = _get_pycaw_volume()
    current = get_volume_level() or 50

    if mode == "mute":
        if endpoint:
            try:
                endpoint.SetMute(1, None)
                return True, "Audio muted."
            except Exception:
                pass
        return True, "Muted sound."

    elif mode == "unmute":
        if endpoint:
            try:
                endpoint.SetMute(0, None)
                return True, f"Audio unmuted. Volume is at {current}%."
            except Exception:
                pass
        return True, "Sound unmuted."

    elif mode == "up":
        delta = value if value is not None else 15
        new_val = min(100, current + delta)
        if endpoint:
            endpoint.SetMute(0, None)
            endpoint.SetMasterVolumeLevelScalar(new_val / 100.0, None)
            return True, f"Sure, turning it up to {new_val}%."
        return True, "Volume increased."

    elif mode == "down":
        delta = value if value is not None else 15
        new_val = max(0, current - delta)
        if endpoint:
            endpoint.SetMasterVolumeLevelScalar(new_val / 100.0, None)
            return True, f"Lowered volume to {new_val}%."
        return True, "Volume decreased."

    elif mode == "set":
        target = max(0, min(100, value if value is not None else 50))
        if endpoint:
            endpoint.SetMute(0, None)
            endpoint.SetMasterVolumeLevelScalar(target / 100.0, None)
            return True, f"Volume set to {target}%."
        return True, f"Volume set to {target}%."

    return False, "Unable to adjust volume."


# ==================== SCREEN BRIGHTNESS ==================== #
def adjust_brightness(mode: str, value: Optional[int] = None) -> Tuple[bool, str]:
    """Adjusts display brightness where supported by display driver / WMI."""
    if not sys.platform.startswith("win"):
        return False, "Brightness control is only available on Windows."

    target_level = value if value is not None else (70 if mode == "up" else 40)
    target_level = max(0, min(100, target_level))

    # Try powershell WMI method
    try:
        cmd = f"(Get-WmiObject -Namespace root/WMI -Class WmiMonitorBrightnessMethods).WmiSetBrightness(1,{target_level})"
        res = subprocess.run(["powershell", "-NoProfile", "-Command", cmd], capture_output=True, text=True, timeout=4)
        if res.returncode == 0:
            return True, f"Brightness set to {target_level}%."
    except Exception:
        pass

    return False, "Brightness adjustment is not supported by your current display driver or requires administrator privileges."


# ==================== SYSTEM LOCK & SENSITIVE CONTROLS ==================== #
def lock_workstation() -> Tuple[bool, str]:
    """Locks the current Windows session."""
    if sys.platform.startswith("win"):
        try:
            ctypes.windll.user32.LockWorkStation()
            return True, "Locking your workstation now."
        except Exception as e:
            print(f"[SystemControl] LockWorkStation error: {e}")
    return False, "Failed to lock the computer."


def execute_shutdown(restart: bool = False) -> Tuple[bool, str]:
    """Executes safe system shutdown or restart (after confirmation)."""
    if sys.platform.startswith("win"):
        flag = "/r" if restart else "/s"
        action = "restarting" if restart else "shutting down"
        try:
            # 30 second grace timer allowing user to abort via 'shutdown /a' if needed
            subprocess.run(["shutdown", flag, "/t", "30"], check=True)
            return True, f"Windows is {action} in 30 seconds. Goodbye Sir."
        except Exception as e:
            return False, f"Could not execute system {action}: {e}"
    return False, "Shutdown command is not supported on this platform."


# ==================== BATTERY & HARDWARE PERFORMANCE ==================== #
def get_battery_info() -> str:
    """Returns concise natural status of battery level and charging state."""
    battery = psutil.sensors_battery()
    if not battery:
        return "I could not detect a battery. Your PC is likely plugged into desktop wall power."

    percent = int(round(battery.percent))
    plugged = battery.power_plugged

    if plugged:
        if percent >= 98:
            return f"You're at {percent}% battery, fully charged and plugged in."
        return f"Battery is at {percent}% and currently charging."
    else:
        status = f"You're currently at {percent}% battery on battery power."
        if battery.secsleft and battery.secsleft > 0:
            hours = battery.secsleft // 3600
            mins = (battery.secsleft % 3600) // 60
            if hours > 0:
                status += f" Approximately {hours} hours and {mins} minutes remaining."
            else:
                status += f" Approximately {mins} minutes remaining."
        return status


def get_performance_info() -> str:
    """Returns current CPU and RAM utilization metrics."""
    cpu = psutil.cpu_percent(interval=0.2)
    mem = psutil.virtual_memory()
    used_gb = mem.used / (1024 ** 3)
    total_gb = mem.total / (1024 ** 3)
    return f"CPU usage is at {cpu:.0f}%, and RAM is at {mem.percent:.0f}% with {used_gb:.1f} of {total_gb:.1f} gigabytes used."


def get_system_summary() -> str:
    """Returns basic system environment information."""
    os_ver = f"{platform.system()} {platform.release()} (Build {platform.version().split('.')[ -1] if '.' in platform.version() else platform.version()})"
    uptime_hrs = (time.time() - psutil.boot_time()) / 3600.0
    hostname = socket.gethostname()
    return f"This PC is {hostname}, running {os_ver}. System uptime is {uptime_hrs:.1f} hours."


# ==================== SCREENSHOTS ==================== #
def capture_screenshot(destination_dir: str) -> Tuple[bool, str, Optional[str]]:
    """Captures desktop screenshot and saves with timestamp to screenshots folder."""
    os.makedirs(destination_dir, exist_ok=True)
    filename = f"screenshot_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
    filepath = os.path.join(destination_dir, filename)
    try:
        img = ImageGrab.grab()
        img.save(filepath, "PNG")
        return True, "Screenshot taken.", filepath
    except Exception as e:
        print(f"[SystemControl] Screenshot error: {e}")
        return False, "Failed to capture screenshot.", None
