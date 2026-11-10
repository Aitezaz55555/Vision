# VISION 1.2 — USB Portable Edition Manual

> **Windows 11 + External USB Flash Drive / External SSD Deployment Guide**  
> *Original Assistant by Shaikh Taha | Windows 11 & Portable Engineering by Antigravity*

---

## Table of Contents
1. [Overview & Architecture](#1-overview--architecture)
2. [Preparing Your USB Drive or External SSD](#2-preparing-your-usb-drive-or-external-ssd)
3. [How to Launch VISION](#3-how-to-launch-vision)
   - [Method A: One-Click Desktop Shortcut](#method-a-one-click-desktop-shortcut-recommended)
   - [Method B: Direct USB Launcher](#method-b-direct-usb-launcher)
4. [Dynamic Drive Letter Resolution](#4-dynamic-drive-letter-resolution)
5. [Host Computer Requirements & Environment Management](#5-host-computer-requirements--environment-management)
6. [Storing AI Models on the USB Drive (`OLLAMA_MODELS`)](#6-storing-ai-models-on-the-usb-drive-ollama_models)
7. [Running VISION Completely Offline](#7-running-vision-completely-offline)
8. [Directory Structure of the Portable Drive](#8-directory-structure-of-the-portable-drive)
9. [Troubleshooting & FAQs](#9-troubleshooting--faqs)

---

## 1. Overview & Architecture

VISION 1.2 is a local AI voice assistant and holographic visualizer designed originally for macOS by Shaikh Taha. This portable edition brings native Windows 11 support and enables VISION to be run directly from an external USB drive (flash drive, external NVMe SSD, or external hard drive) on any compatible Windows PC.

### Portability Highlights
* **Zero Hardcoded Drive Letters:** Never assumes drive `E:`, `F:`, or `C:`. Resolves its path dynamically at runtime (`%~dp0` and `$PSScriptRoot`).
* **Self-Contained Data Storage:** Conversation histories, personal memory (`memory.json`), screenshots, camera snapshots, and logs are strictly saved inside the project directory under `data/`.
* **Portable AI Model Support:** Supports redirecting Ollama's model storage to `OllamaModels\` on your USB drive so you never need to redownload LLMs across different computers.
* **Double-Click Desktop Shortcut:** Generates a desktop shortcut (`VISION AI.lnk`) pointing back to the portable batch script without opening Antigravity, VS Code, or the terminal manually.

---

## 2. Preparing Your USB Drive or External SSD

### Hardware Recommendations
- **Storage Size:** 16 GB or larger (32 GB+ recommended if storing multiple local LLMs).
- **Filesystem Format:** **NTFS** or **exFAT** (NTFS is recommended for performance and full Windows file compatibility).
- **Interface:** USB 3.0 or higher / External SSD (USB-C NVMe recommended for fastest loading).

### Setup Steps
1. Insert your USB drive into your Windows computer.
2. Copy the entire `Vision` folder to the root of your USB drive (e.g., `E:\Vision`).
3. Ensure the drive is writable (not locked with a hardware read-only switch).
4. Run `setup_windows.bat` once on the machine (or allow `run_vision_portable.bat` to auto-configure the virtual environment).

---

## 3. How to Launch VISION

### Method A: One-Click Desktop Shortcut (Recommended)
1. Plug your USB drive into your Windows laptop.
2. In File Explorer, open your USB drive's `Vision` folder.
3. Double-click `create_desktop_shortcut.bat` (or run `create_shortcut.ps1`).
4. A shortcut named **VISION AI** will appear on your Windows Desktop.
5. Simply **double-click "VISION AI" on your desktop** to start VISION!

### Method B: Direct USB Launcher
1. Open your USB drive in Windows File Explorer.
2. Double-click `run_vision_portable.bat`.
3. The launcher automatically:
   - Validates write permissions and free disk space.
   - Activates or configures the compatible virtual environment.
   - Detects or starts the local Ollama LLM server.
   - Launches the voice assistant and the 3D holographic interface.

---

## 4. Dynamic Drive Letter Resolution

Windows assigns drive letters dynamically (e.g., your USB might be `E:` today, `F:` tomorrow on another laptop, or `D:` on a desktop with only one internal drive).

VISION avoids broken paths through the following mechanisms:

1. **Batch Files (`%~dp0`):**
   ```bat
   set "PROJECT_DIR=%~dp0"
   if "%PROJECT_DIR:~-1%"=="\" set "PROJECT_DIR=%PROJECT_DIR:~0,-1%"
   cd /d "%PROJECT_DIR%"
   ```
   This guarantees that the active working directory is always anchored to the script's physical location on the USB drive, regardless of which drive letter Windows assigns.

2. **PowerShell Shortcut Generator (`$MyInvocation.MyCommand.Definition`):**
   Dynamically queries the USB location at creation time and sets both `TargetPath` and `WorkingDirectory` to the active USB path.

3. **Python Dynamic Anchoring (`os.path.dirname(os.path.abspath(__file__))`):**
   All data paths (`data/memory.json`, `data/screenshots/`, `data/logs/`, `vision_config.json`) are resolved relative to the executing Python script.

---

## 5. Host Computer Requirements & Environment Management

### Minimum Host Requirements
* **OS:** Windows 10 (64-bit build 19041+) or Windows 11.
* **Python:** Python 3.10, 3.11, 3.12, or 3.13 installed with **"Add Python to PATH"** enabled.
* **Audio:** Microphone and speakers/headphones connected.
* **Camera:** Webcam connected (required only for hand tracking or taking photos).
* **RAM:** 8 GB minimum (16 GB recommended for running local LLMs).

### How Virtual Environments Work Across Different PCs
Python virtual environments (`.venv`) store references to the host machine's Python executable. When moving a USB drive from Machine A to Machine B:
* If Machine B has Python installed at a different path or architecture, the launcher's portability check detects this:
  ```bat
  "%VENV_DIR%\Scripts\python.exe" -c "import sys; sys.exit(0)"
  ```
* If incompatible, `run_vision_portable.bat` automatically runs `setup_windows.bat` to re-link `.venv` for Machine B without deleting your conversation data or models.

---

## 6. Storing AI Models on the USB Drive (`OLLAMA_MODELS`)

By default, Ollama stores downloaded LLMs in `%USERPROFILE%\.ollama\models` on the internal `C:` drive. When using VISION portably across multiple computers, you can store your models directly on your USB drive:

1. `run_vision_portable.bat` prompts on startup:
   ```
   [PORTABILITY] Portable models directory: E:\Vision\OllamaModels
   Do you want Ollama to store/load AI models directly from this USB drive?
   (Press ENTER for YES [recommended for USB], or type N for host computer's storage)
   ```
2. Press **ENTER** (or `Y`).
3. The script sets the environment variable `OLLAMA_MODELS=E:\Vision\OllamaModels` for that session only.
4. When you run `ollama pull llama3.2:1b`, the entire model is stored on the USB drive.
5. Moving the USB drive to another PC allows you to use the model immediately without re-downloading!

---

## 7. Running VISION Completely Offline

VISION is engineered to provide essential voice assistant capabilities even when no internet connection is present:

| Feature | Online | Offline | Fallback Mechanism |
|---|---|---|---|
| **AI LLM Chat** | Supported | Supported | Local Ollama runs 100% on CPU/GPU offline |
| **Holographic UI** | Supported | Supported | Standalone OpenCV 3D engine |
| **System Commands** | Supported | Supported | Native Windows APIs (volume, battery, apps) |
| **Memory Storage** | Supported | Supported | Local `data/memory.json` |
| **Hand Tracking** | Supported | Supported | Local `hand_landmarker.task` file |
| **Text-to-Speech** | `edge-tts` (Neural) | Offline Fallback | Native Windows SAPI5 (`pyttsx3`) |
| **Speech-to-Text** | Google Speech API | Limited | Prompts for terminal text command |
| **Web Search** | Google / YouTube | Unavailable | Informs user that internet is offline |

---

## 8. Directory Structure of the Portable Drive

```
<USB-Drive>:\Vision\
│
├── run_vision_portable.bat     # Portable USB Launcher (Dynamic Paths)
├── run_vision.bat              # Standard Windows Launcher
├── setup_windows.bat           # Automated Environment Setup & Dependency Installer
├── create_shortcut.ps1         # Dynamic Desktop Shortcut Creator
├── create_desktop_shortcut.bat # Double-click wrapper for shortcut creation
│
├── vision.py                   # Core Voice Assistant & Coordinator
├── interface.py                # 3D Holographic Visualizer (OpenCV + MediaPipe)
├── vision_config.json          # Unified Configuration File
├── requirements-windows.txt    # Windows Dependency Specification
├── hand_landmarker.task        # MediaPipe Hand Landmark TFLite Model (~7.8 MB)
│
├── README_WINDOWS.md           # Windows 11 Technical Documentation
├── README_PORTABLE.md          # Portable USB Manual (This File)
│
├── data\                       # Portable Application Storage
│   ├── memory.json             # Persistent User Notes & Identity Memory
│   ├── vision_state.txt        # Inter-process UI State (blue/red)
│   ├── screenshots\            # Saved Desktop Screenshots
│   ├── photos\                 # Saved Webcam Captures
│   └── logs\                   # Runtime Logs & Diagnostics
│
├── OllamaModels\               # Optional USB Storage for Ollama GGUF Models
└── .venv\                      # Windows Python Virtual Environment
```

---

## 9. Troubleshooting & FAQs

### Q1: The launcher says "Virtual environment was created on a different computer".
**A:** This is normal when moving the USB drive between PCs with different Python install paths. Simply press **Y** or let the script auto-run `setup_windows.bat`. It will update the local virtual environment in under a minute using cached packages.

### Q2: I double-clicked `run_vision_portable.bat` and the window closed instantly.
**A:** The launcher includes defensive `pause` and error traps. If this happens, open Windows Command Prompt manually, navigate to your USB drive (`cd /d E:\Vision`), and run `run_vision_portable.bat` to see the exact message. Usually, this means Python is not installed or not in PATH.

### Q3: How do I change the speech voice?
**A:** Open `vision_config.json` in Notepad and modify `"tts_voice"`.
- Male: `"en-US-ChristopherNeural"`
- Female: `"en-US-JennyNeural"`
- Indian Accent: `"en-IN-PrabhatNeural"` or `"en-IN-NeerjaNeural"`

### Q4: Hand tracking is not responding to my gestures.
**A:**
1. Ensure your webcam is connected and accessible.
2. Check Windows Camera Privacy Settings: **Settings > Privacy & security > Camera** (Ensure camera access is toggled **ON**).
3. Ensure `hand_landmarker.task` is located in the root of `Vision\`.

### Q5: How do I safely disconnect my USB drive?
**A:** 
1. Close VISION by pressing **Ctrl+C** or `q` in the holographic window.
2. Wait 2 seconds for audio and memory files to complete writing.
3. In the Windows System Tray (near the clock), click **Safely Remove Hardware and Eject Media**, select your USB drive, and disconnect it.

---
*Created for the VISION 1.2 Windows Portability Release.*
