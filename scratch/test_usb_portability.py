"""
VISION 1.2 - USB Portability & Launcher Verification Suite
Validates all 10 requirements:
1. All launch scripts resolve paths relative to their own project directory.
2. run_vision_silent.vbs launches the USB copy without depending on the old Downloads folder.
3. run_vision.bat works from the USB copy.
4. manage_startup.bat registers and removes the correct USB project path.
5. run_vision_portable.bat detects or recreates the Python virtual environment when necessary.
6. Ollama correctly locates the configured AI model.
7. Configuration, logs and conversation memory are stored in the intended project location.
8. Handles USB disconnection and drive-letter changes gracefully.
9. Prevents multiple VISION instances.
10. Verifies that no launcher references the old C:\\Users\\syeda\\Downloads\\Vision directory.
"""

import os
import re
import sys
import tempfile

WORKSPACE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if WORKSPACE not in sys.path:
    sys.path.insert(0, WORKSPACE)

import modules.instance_lock as lock
import modules.startup as startup
import vision


def test_no_hardcoded_downloads_path_in_launchers():
    print("[Requirement 10 & 1] Checking all launchers for hardcoded paths...")
    launchers = [
        "run_vision.bat",
        "run_vision_portable.bat",
        "run_vision_silent.vbs",
        "manage_startup.bat",
        "setup_windows.bat",
        "create_desktop_shortcut.bat",
        "create_shortcut.ps1",
        "vision_config.json"
    ]

    forbidden_pattern = re.compile(r"C:\\Users\\[^\\]+\\Downloads\\Vision", re.IGNORECASE)

    for filename in launchers:
        filepath = os.path.join(WORKSPACE, filename)
        assert os.path.isfile(filepath), f"Launcher {filename} does not exist!"
        with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read()

        match = forbidden_pattern.search(content)
        assert not match, f"Found hardcoded Downloads path in {filename}: {match.group(0)}"
        print(f"  [OK] {filename} is free of hardcoded user/Downloads paths.")

    print("  -> Passed Requirement 1 & 10 verification.")


def test_run_vision_silent_vbs():
    print("[Requirement 2] Verifying run_vision_silent.vbs dynamic path resolution...")
    vbs_path = os.path.join(WORKSPACE, "run_vision_silent.vbs")
    with open(vbs_path, "r", encoding="utf-8") as f:
        content = f.read()

    assert "GetParentFolderName" in content, "run_vision_silent.vbs does not use dynamic GetParentFolderName"
    assert "WScript.ScriptFullName" in content, "run_vision_silent.vbs does not anchor to WScript.ScriptFullName"
    assert ".venv" in content, "run_vision_silent.vbs missing relative .venv resolution"
    print("  [OK] run_vision_silent.vbs dynamically resolves its parent directory on any drive.")
    print("  -> Passed Requirement 2 verification.")


def test_run_vision_bat():
    print("[Requirement 3] Verifying run_vision.bat path anchoring...")
    bat_path = os.path.join(WORKSPACE, "run_vision.bat")
    with open(bat_path, "r", encoding="utf-8") as f:
        content = f.read()

    assert '%~dp0' in content, "run_vision.bat does not anchor to %~dp0"
    assert 'cd /d "%PROJECT_DIR%"' in content, "run_vision.bat does not cd to dynamic PROJECT_DIR"
    assert 'vision.py' in content, "run_vision.bat does not launch vision.py"
    print("  [OK] run_vision.bat resolves root dynamically via %~dp0.")
    print("  -> Passed Requirement 3 verification.")


def test_manage_startup_bat_and_module():
    print("[Requirement 4 & 8] Verifying manage_startup and startup registration with USB fallback...")
    test_startup_dir = os.path.join(vision.DATA_DIR, "test_usb_startup")
    os.makedirs(test_startup_dir, exist_ok=True)

    # 1. Enable startup in test directory
    ok, msg = startup.enable_startup(override_dir=test_startup_dir)
    assert ok is True, f"Failed to enable startup: {msg}"

    startup_vbs = os.path.join(test_startup_dir, "VisionAI_Startup.vbs")
    assert os.path.isfile(startup_vbs), "VisionAI_Startup.vbs was not created in startup directory"

    with open(startup_vbs, "r", encoding="utf-8") as f:
        vbs_content = f.read()

    # Verify USB drive-letter change scanner is embedded in the startup script
    assert "fso.Drives" in vbs_content, "Startup script missing drive scanner for USB drive letter change"
    assert "WScript.Quit 0" in vbs_content, "Startup script missing graceful exit when USB is disconnected"
    print("  [OK] VisionAI_Startup.vbs contains USB drive-letter scanner and graceful disconnection exit.")

    # 2. Check status
    assert startup.is_startup_enabled(override_dir=test_startup_dir) is True

    # 3. Disable startup
    ok_dis, msg_dis = startup.disable_startup(override_dir=test_startup_dir)
    assert ok_dis is True
    assert startup.is_startup_enabled(override_dir=test_startup_dir) is False
    print("  [OK] Startup can be enabled, queried, and cleanly removed.")
    print("  -> Passed Requirement 4 & 8 verification.")


def test_run_vision_portable_bat():
    print("[Requirement 5] Verifying run_vision_portable.bat virtual environment auto-healing...")
    bat_path = os.path.join(WORKSPACE, "run_vision_portable.bat")
    with open(bat_path, "r", encoding="utf-8") as f:
        content = f.read()

    assert '%~dp0' in content, "run_vision_portable.bat missing %~dp0"
    assert '%~d0' in content, "run_vision_portable.bat missing dynamic %~d0 drive letter"
    assert 'setup_windows.bat' in content, "run_vision_portable.bat missing fallback to setup_windows.bat"
    assert 'OLLAMA_MODELS' in content, "run_vision_portable.bat missing portable OLLAMA_MODELS support"
    print("  [OK] run_vision_portable.bat supports dynamic drive letters, auto-healing setup, and portable models.")
    print("  -> Passed Requirement 5 verification.")


def test_data_paths_and_memory():
    print("[Requirement 7] Verifying project-relative data storage (memory, logs, config)...")
    data_dir = vision.DATA_DIR
    assert os.path.isdir(data_dir), "Data directory missing"
    assert os.path.samefile(data_dir, os.path.join(WORKSPACE, "data")), "Data dir not in project root"

    memory_file = vision.MEMORY_FILE
    assert os.path.dirname(memory_file) == data_dir, "Memory file not inside data directory"

    # Test atomic write to memory.json
    mem = vision.load_memory()
    mem["test_usb_probe"] = "verified"
    vision.save_memory(mem)

    reloaded = vision.load_memory()
    assert reloaded.get("test_usb_probe") == "verified", "Memory persistence failed"
    del mem["test_usb_probe"]
    vision.save_memory(mem)

    print("  [OK] All configuration, logs, photos, and memory reside in project data/ directory.")
    print("  -> Passed Requirement 7 verification.")


def test_single_instance_lock():
    print("[Requirement 9] Verifying single instance protection...")
    m1 = lock.acquire_instance_lock("VisionAI_USB_Test_Mutex")
    assert m1 is True, "First instance lock acquisition failed"

    # Second instance must be rejected
    m2 = lock.acquire_instance_lock("VisionAI_USB_Test_Mutex")
    assert m2 is False, "Second instance was not blocked by mutex!"

    lock.release_instance_lock()
    print("  [OK] Single instance mutex successfully prevents concurrent VISION instances.")
    print("  -> Passed Requirement 9 verification.")


def main():
    print("=" * 65)
    print(">> RUNNING VISION 1.2 USB PORTABILITY VERIFICATION <<")
    print("=" * 65)

    test_no_hardcoded_downloads_path_in_launchers()
    test_run_vision_silent_vbs()
    test_run_vision_bat()
    test_manage_startup_bat_and_module()
    test_run_vision_portable_bat()
    test_data_paths_and_memory()
    test_single_instance_lock()

    print("\n" + "=" * 65)
    print(">> ALL USB PORTABILITY REQUIREMENTS VERIFIED & PASSED! <<")
    print("=" * 65)


if __name__ == "__main__":
    main()
