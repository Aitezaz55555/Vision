"""
VISION AI - File and Folder Management Module
Supports voice-based navigation for Windows folders, safe local file searching,
directory listing, and strict safety boundaries preventing unauthorized modifications.
"""

import os
import sys
from typing import Tuple, Optional, List, Dict


# Common Windows user directories
STANDARD_FOLDERS: Dict[str, str] = {
    "downloads": os.path.expanduser("~/Downloads"),
    "documents": os.path.expanduser("~/Documents"),
    "desktop": os.path.expanduser("~/Desktop"),
    "pictures": os.path.expanduser("~/Pictures"),
    "videos": os.path.expanduser("~/Videos"),
    "music": os.path.expanduser("~/Music"),
}

# Restricted system roots that should never be searched or modified by voice
FORBIDDEN_ROOTS = [
    os.environ.get("SystemRoot", r"C:\Windows").lower(),
    os.environ.get("ProgramFiles", r"C:\Program Files").lower(),
    os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)").lower(),
]


def is_path_safe(target_path: str) -> bool:
    """Ensures a path does not target critical Windows system directories."""
    abs_p = os.path.abspath(target_path).lower()
    for forbidden in FORBIDDEN_ROOTS:
        if abs_p.startswith(forbidden):
            return False
    return True


def open_folder(folder_name: str) -> Tuple[bool, str, Optional[str]]:
    """
    Opens standard user folders or searches for folder by name.
    Returns (success: bool, spoken_reply: str, resolved_path: Optional[str]).
    """
    import subprocess
    key = folder_name.lower().strip()
    for filler in ("my", "the", "folder", "directory"):
        key = key.replace(filler, "").strip()

    def _safe_open(p: str):
        norm = os.path.normpath(os.path.abspath(p))
        if sys.platform.startswith("win"):
            try:
                os.startfile(norm)
            except Exception:
                try:
                    subprocess.Popen(["explorer.exe", norm])
                except Exception as e:
                    print(f"[FileModule] Explorer launch error: {e}")
        elif sys.platform == "darwin":
            subprocess.run(["open", norm])
        else:
            subprocess.run(["xdg-open", norm])

    # Check standard folders
    if key in STANDARD_FOLDERS:
        path = STANDARD_FOLDERS[key]
        if os.path.isdir(path):
            _safe_open(path)
            return True, f"Opening your {key.title()} folder.", path

    # Search in user directories
    search_roots = [
        os.path.expanduser("~/Downloads"),
        os.path.expanduser("~/Documents"),
        os.path.expanduser("~/Desktop"),
        os.path.expanduser("~"),
    ]
    for root in search_roots:
        if not os.path.isdir(root):
            continue
        try:
            for entry in os.scandir(root):
                if entry.is_dir() and key in entry.name.lower():
                    if is_path_safe(entry.path):
                        _safe_open(entry.path)
                        return True, f"Opening folder {entry.name}.", entry.path
        except Exception:
            continue

    return False, f"Sorry Sir, I could not find a folder named {folder_name}.", None


def list_files_in_folder(folder_name: str, max_items: int = 8) -> Tuple[bool, str, List[str]]:
    """
    Lists files inside a specified standard or user directory.
    """
    key = folder_name.lower().strip()
    for filler in ("my", "the", "folder", "directory", "in"):
        key = key.replace(filler, "").strip()

    target_dir = STANDARD_FOLDERS.get(key)
    if not target_dir or not os.path.isdir(target_dir):
        # Fallback to search
        for root in (os.path.expanduser("~/Desktop"), os.path.expanduser("~/Documents"), os.path.expanduser("~/Downloads")):
            candidate = os.path.join(root, key)
            if os.path.isdir(candidate):
                target_dir = candidate
                break

    if not target_dir or not os.path.isdir(target_dir):
        return False, f"Could not find the {folder_name} folder.", []

    try:
        entries = [e.name for e in os.scandir(target_dir) if not e.name.startswith((".", "$"))]
        total = len(entries)
        sample = entries[:max_items]

        if total == 0:
            return True, f"The {key.title()} folder is currently empty.", []

        summary = f"Found {total} items in {key.title()}. Recent files include {', '.join(sample[:3])}."
        print(f"\n[Folder Contents - {target_dir}] ({total} items):")
        for idx, item in enumerate(sample, 1):
            print(f"  {idx}. {item}")
        if total > max_items:
            print(f"  ... and {total - max_items} more items.")

        return True, summary, sample
    except Exception as e:
        print(f"[FileManager] Directory listing error: {e}")
        return False, f"Could not read contents of {folder_name}.", []


def search_and_open_file(filename_query: str) -> Tuple[bool, str, Optional[str]]:
    """
    Searches for a file by name in allowed user directories and opens it.
    """
    q = filename_query.lower().strip()
    if not q:
        return False, "Please tell me the file name.", None

    search_roots = [
        os.path.expanduser("~/Desktop"),
        os.path.expanduser("~/Downloads"),
        os.path.expanduser("~/Documents"),
    ]

    for root in search_roots:
        if not os.path.isdir(root):
            continue
        try:
            for dirpath, _, filenames in os.walk(root):
                for f in filenames:
                    if q in f.lower():
                        full_path = os.path.join(dirpath, f)
                        if is_path_safe(full_path):
                            if sys.platform.startswith("win"):
                                os.startfile(full_path)
                            return True, f"Opening file {f}.", full_path
        except Exception:
            continue

    return False, f"I could not locate a file matching {filename_query}.", None
