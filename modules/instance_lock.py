"""
VISION AI - Single Instance Lock
Ensures only one instance of VISION AI runs at a time on Windows.
Prevents multiple background processes from contending for the microphone or audio stream.
"""

import sys
import os

_mutex_handle = None


def acquire_instance_lock(mutex_name: str = "VisionAI_Assistant_SingleInstance_Mutex") -> bool:
    """
    Acquires a named Windows mutex to guarantee single-instance execution.
    Returns True if this is the only instance, False if another instance is already active.
    """
    global _mutex_handle

    if not sys.platform.startswith("win"):
        # On non-Windows platforms, use a lockfile
        lock_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data", "vision.lock")
        os.makedirs(os.path.dirname(lock_file), exist_ok=True)
        try:
            import fcntl
            f = open(lock_file, "w")
            fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
            _mutex_handle = f
            return True
        except Exception:
            return False

    try:
        import ctypes
        from ctypes import wintypes

        kernel32 = ctypes.windll.kernel32
        ERROR_ALREADY_EXISTS = 183

        # Create named mutex
        handle = kernel32.CreateMutexW(None, False, mutex_name)
        last_error = kernel32.GetLastError()

        if last_error == ERROR_ALREADY_EXISTS:
            if handle:
                kernel32.CloseHandle(handle)
            return False

        _mutex_handle = handle
        return True
    except Exception as e:
        print(f"[InstanceLock] Warning checking mutex: {e}")
        return True


def release_instance_lock():
    """Releases the instance mutex if held."""
    global _mutex_handle
    if _mutex_handle and sys.platform.startswith("win"):
        try:
            import ctypes
            ctypes.windll.kernel32.CloseHandle(_mutex_handle)
        except Exception:
            pass
        _mutex_handle = None
