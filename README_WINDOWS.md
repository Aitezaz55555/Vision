# VISION 1.2 – Windows 11 Edition

VISION 1.2 is an advanced AI Voice Assistant featuring an animated 3D holographic interface, powered by a local Ollama LLM backend, with multi-language voice support (English, Hindi, and Hinglish).

---

## Key Features

- **Conversational Intelligence & Multi-Mode AI:**
  - **General-Purpose AI Knowledge:** Direct, intuitive explanations across science, programming, math, tech, pop culture, anime, movies, and casual conversation.
  - **Multi-Turn Context & Pronoun Resolution:** Remembers previous conversation context (e.g. *"Tell me about black holes"* -> *"How are they formed?"*).
  - **Conversational Modes:**
    - *Normal Mode (Default):* Concise, natural 2–4 sentence spoken answers without wordy essays.
    - *Detailed Mode:* Deep, step-by-step breakdowns when asked (*"Explain in detail"*, *"Step by step"*).
    - *Entertainment Mode:* Engaging sci-fi stories, witty jokes, and fascinating real-world facts (*"Tell me a story"*, *"Tell a joke"*, *"Share an interesting fact"*).
  - **Natural Spoken Formatting:** Strips markdown bolding, code fences, bullet characters, and noisy symbols so the voice flows smoothly.
- **Low-Latency Streaming TTS & Instant Barge-In:**
  - **Sentence-Level Streaming Pipeline:** Streams tokens from Ollama, splits at sentence boundaries, and begins synthesizing and speaking Sentence 1 immediately while Sentence 2 is being generated—reducing response latency from seconds to under 600ms!
  - **Sub-Millisecond Barge-In (< 1.5ms):** Saying *"Stop"*, *"Stop speaking"*, *"Be quiet"*, *"Shut up"*, *"That's enough"*, *"Cancel"*, *"Pause"*, *"Ruk jao"*, or pressing **Esc**/**Space** instantly stops audio playback, breaks Ollama token generation, discards queued sentences, plays a sci-fi acknowledgment cue, and immediately returns to listening mode!
- **Always-Active Background Operation:**
  - Automatic startup with Windows (`VisionAI_Startup.vbs` in Startup folder or via `manage_startup.bat`).
  - Silent background runner (`run_vision_silent.vbs`) running on `pythonw.exe` without opening any command prompt window.
  - Single-instance protection via Windows Named Mutex, preventing multiple background instances from contending for the microphone.
- **Continuous Background Double-Clap Activation:**
  - Low-latency streaming engine with Exponential Moving Average (EMA) ambient floor tracking.
  - Impulse verification (Peak, RMS, and Crest Factor >= 2.2) to distinguish claps from speech or background noise.
  - Automatically returns to background standby monitoring whenever VISION goes idle or to sleep.
  - Plays a crisp futuristic upward chime and shows activation state on HUD.
  - Instant manual activation via **Enter** or **Space** key.
- **Interruptible Speech (Barge-In):**
  - Instant voice interrupt: Saying *"Stop"*, *"Be quiet"*, *"Cancel"*, *"Enough"*, or *"Pause"* cuts off speech immediately and returns to listening mode.
  - Keyboard interrupt: Pressing **Esc**, **Space**, or **S** during speech halts playback instantly.
  - Speech modifications: *"Repeat that"*, *"Speak slower"*, *"Speak faster"*, *"Silent mode"* (*"Don't speak; just show the answer"*), and *"Enable speech"*.
- **Improved Application Discovery & Web Fallbacks:**
  - Supports WhatsApp Desktop (`whatsapp:`) and ChatGPT Desktop (`chatgpt:`) via registered Windows URI protocols.
  - Seamless Web Fallback: If desktop applications are missing, automatically notifies the user and opens the official web application (`web.whatsapp.com`, `chatgpt.com`, `open.spotify.com`) in the default browser without popping up Windows error dialogs!
  - Application aliases: *"Take me to WhatsApp"*, *"Start my coding editor"*, *"Open Spotify"*, *"Start Calculator"*.
- **Productivity & Smart Assistant Features:**
  - **Voice Reminders:** *"Remind me to call John in 10 minutes"*, *"What are my reminders?"*, *"Cancel all reminders"*.
  - **Window Controls:** *"Minimize window"*, *"Maximize window"*, *"Restore window"*.
  - **Time & Date:** *"What time is it?"*, *"What is today's date?"*.
  - **Startup Settings:** *"Enable start with Windows"*, *"Disable startup"*, *"Startup status"*.
- **Holographic Interface (`interface.py`):**
  - Real-time 3D projected holographic core with bloom rendering, comets, HUD arcs, and interactive mouse / hand tracking controls.
  - Dynamic Palette: Stays **blue** during idle / listening mode, transitions to glowing **red** while Vision is speaking.
  - Live HUD Status Bar: Displays real-time state (`MONITORING // CLAP TO WAKE`, `LISTENING`, `PROCESSING`, `SPEAKING`, `INTERRUPTED`), recognized voice text, and execution results.
- **Genuine Local AI:** Powered by **Ollama** running locally on your laptop (default: `llama3.2:1b`), retaining recent conversation context without external API keys or paid subscriptions.
- **High-Quality Speech:**
  - Online: Ultra-realistic neural speech synthesis via `edge-tts` (`en-US-ChristopherNeural`).
  - Offline Fallback: Built-in Windows SAPI5 voice engine via `pyttsx3` / Windows Speech API.
- **Native Windows 11 PC Control:**
  - Core Audio master volume control, screen brightness adjustment, workstation locking (`LockWorkStation`), Task Manager, and Windows Settings.
  - Two-step safety confirmation for sensitive actions (shutdown, restart).
  - Screenshots saved to `screenshots/` and webcam photos saved to `photos/`.
- **Modular Architecture (`modules/`):** Clean separation across `clap.py`, `apps.py`, `system.py`, `browser.py`, `files.py`, `context.py`, `router.py`, `reminders.py`, `startup.py`, `instance_lock.py`, and `sound.py`.

---

## System Requirements

- **Operating System:** Windows 11 (64-bit)
- **Python:** Python 3.10 – 3.13 (Python 3.13 fully supported)
- **Audio Hardware:** Working microphone and speakers / headphones
- **Camera (Optional):** Required only for photo capture and MediaPipe hand gesture controls
- **RAM:** Minimum 8 GB (16 GB recommended)
- **AI Backend:** Ollama for Windows

---

## Quick Start (Automated)

### 1. Setup Environment
Simply double-click:
```cmd
setup_windows.bat
```
This automatically creates the `.venv` virtual environment and installs all Windows-compatible dependencies.

### 2. Install Ollama & Pull the AI Model
If Ollama is not already running:
1. Download Ollama from [https://ollama.com/download/windows](https://ollama.com/download/windows) and run the installer.
2. In Command Prompt or PowerShell, pull the recommended lightweight model:
   ```cmd
   ollama pull llama3.2:1b
   ```
3. Ensure Ollama service is running (`ollama serve` or Ollama system tray app).

### 3. Launch Vision
Double-click:
```cmd
run_vision.bat
```
Or run from your terminal:
```cmd
.venv\Scripts\activate
python vision.py
```

---

## Manual Setup

If you prefer setting up manually from Command Prompt:

```cmd
:: 1. Create and activate virtual environment
python -m venv .venv
.venv\Scripts\activate

:: 2. Install Windows dependencies
pip install --upgrade pip
pip install -r requirements-windows.txt

:: 3. Launch Vision
python vision.py
```

To test only the holographic interface:
```cmd
python interface.py        :: Default resolution (1280x800)
python interface.py --sd   :: Lighter resolution (1280x720)
python interface.py --hd   :: Full HD resolution (1920x1080)
```

---

## Example Voice Commands

| Category | Say (English / Hindi / Hinglish) | Action |
|---|---|---|
| **Wake-up** | Double Clap (or Enter / Space, or *"Hey Vision"*) | Activates Vision, plays chime, opens holographic HUD |
| **Barge-in / Stop** | *"Stop"*, *"Be quiet"*, *"Cancel"*, *"Enough"*, *"Pause"*, *"Ruko"* | Immediately cuts off speech playback and enters listening mode |
| **Speech Controls** | *"Repeat that"*, *"Speak slower"*, *"Speak faster"*, *"Silent mode"* | Repeats last reply, adjusts voice speed, or suppresses speech output |
| **App Launch** | *"Open WhatsApp"*, *"Open ChatGPT"*, *"Start my coding editor"*, *"Open Chrome"* | Launches desktop apps via URI protocol/executables with web fallback |
| **App Close** | *"Close WhatsApp"*, *"Close Chrome"*, *"Close it"*, *"Band karo"* | Gracefully terminates target application using process mapping |
| **Window Controls** | *"Minimize window"*, *"Maximize window"*, *"Restore window"* | Manages active foreground window on Windows desktop |
| **Time & Date** | *"What time is it?"*, *"What is today's date?"*, *"Time batao"* | Reports current time and formatted date |
| **Reminders** | *"Remind me to call John in 10 minutes"*, *"Show reminders"* | Schedules local voice notification reminders with countdown tracking |
| **Startup Control** | *"Enable start with Windows"*, *"Disable startup"*, *"Startup status"* | Configures automatic silent background execution on Windows boot |
| **Browser & Search** | *"Open YouTube"*, *"Search Google for Python tutorials"*, *"Open ChatGPT"* | Opens sites in default browser and routes web search queries |
| **Contextual Search** | *"Search for quantum computing"* (after opening YouTube) | Automatically inherits previous search platform |
| **System Telemetry** | *"What is my CPU usage?"*, *"Check RAM"*, *"Performance status"* | Reports real-time CPU % and RAM memory utilization |
| **Battery** | *"Battery status"*, *"Battery kitni hai"* | Reports percentage and charging state |
| **Volume Control** | *"Volume 50"*, *"Increase volume"*, *"Mute sound"*, *"Unmute"* | Adjusts Windows master volume via Core Audio |
| **Screen Brightness** | *"Increase brightness"*, *"Brightness 70"*, *"Dim screen"* | Adjusts display brightness where supported |
| **Workstation Lock** | *"Lock PC"*, *"Lock my screen"*, *"Lock workstation"* | Immediately locks Windows session |
| **System Utilities** | *"Open Task Manager"*, *"Open Windows Settings"* | Quick-launches essential Windows system tools |
| **File Navigation** | *"Open my Downloads folder"*, *"Open Documents"*, *"Open Desktop"* | Opens standard and custom user directories in File Explorer |
| **Directory Listing** | *"List files in my downloads"*, *"Downloads mein kya hai"* | Inspects directory and speaks recent contents |
| **Safety Confirmation** | *"Shutdown PC"* -> Vision: *"Are you sure?"* -> *"Yes"* / *"No"* | Two-step confirmation prevents accidental shutdowns or reboots |
| **Screenshot** | *"Take a screenshot"*, *"Screen capture karo"* | Captures screen to `screenshots/` and opens |
| **Camera** | *"Take a photo"*, *"Selfie lo"* | Takes picture from webcam to `photos/` |
| **Personal Memory** | *"My name is Alex"*, *"What is my name?"* | Remembers and recalls user identity |
| **Notes** | *"Remember that my meeting is at 5 PM"*, *"Show my notes"* | Saves and reads personal notes |
| **AI Chat** | *"Who was Nikola Tesla?"*, *"Explain general relativity"* | Local Ollama LLM answers naturally with conversational context |
| **Interface** | *"Open interface"*, *"Close interface"* | Toggles holographic window |
| **Sleep / Standby** | *"Go to sleep"*, *"Take a break"*, *"So jao"* | Enters background standby, continuously monitoring for double claps |

---

## Interface Controls

| Input | Action |
|---|---|
| **Mouse Drag** | Rotate holographic sphere |
| **Mouse Scroll** or `+` / `-` | Zoom in / Zoom out |
| `[` and `]` | Decrease / Increase neon glow intensity |
| `R` | Reset view angle and zoom |
| `F` | Toggle fullscreen mode |
| `Q` or `Esc` | Quit interface |
| **Single Hand (Webcam)** | Smooth rotation tracking |
| **Two-Hand Pinch (Webcam)** | Dynamic zoom in / out |

---

## Windows 11 Privacy & Permissions

Ensure Windows privacy settings allow microphone and camera access:
1. Open **Settings** (`Win + I`) -> **Privacy & security**.
2. Under **App permissions**:
   - **Microphone:** Turn ON and verify *"Let desktop apps access your microphone"* is ON.
   - **Camera:** Turn ON and verify *"Let desktop apps access your camera"* is ON (if using photos/hand tracking).

---

## Configuration

You can customize Vision settings at the top of `vision.py`:
- `CREATOR_NAME` – Name Vision references as its creator (default: `"Taha"`).
- `OLLAMA_MODEL` – Local Ollama model (default: `"llama3.2:1b"`).
- `EDGE_VOICE` – Neural voice style (e.g., `"en-US-ChristopherNeural"`, `"en-US-GuyNeural"`).
- `CLAP_THRESHOLD` – Sensitivity for double-clap detection (default: `2000`).

---

## License

MIT License – Originally created by Shaikh Taha, modified for full Windows 11 compatibility.
