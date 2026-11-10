# Vision – AI Voice Assistant with Interactive Holographic Interface

Vision is an intelligent voice assistant with a futuristic, animated 3D holographic interface, built for **Windows 11** and **macOS** in Python. Activate it with a **double clap** or the wake phrase **"Hey Vision"**, and an immersive 3D holographic interface appears with live hand tracking, physics-driven particle swarms, and neural voice capabilities.

Vision stays blue while idle, transitions to glowing red while speaking, and provides instant conversational responses and Windows system automation.

---

## Key Features

- **Activation:** Dual-clap detection or wake phrase `"Hey Vision"` (with background monitoring and hotkey fallback).
- **Holographic 3D Interface (`interface.py`):**
  - Spinning 3D icosphere core, gyroscope rings, orbital particle swarms, and depth-shaded bloom.
  - Asynchronous MediaPipe hand tracking running in a background thread for buttery-smooth 45–60 FPS rendering.
  - Adaptive velocity-aware landmark smoothing (`AdaptiveSmoother`) that eliminates static jitter while maintaining high agility during fast motions.
  - Real-time 3D particle simulation with gravitational attraction to fingertips, singularity collapse, and explosive radial bursts.
  - Picture-in-Picture (PIP) sci-fi camera HUD overlay toggleable with `C`.
- **Intelligent Windows 11 Automation:**
  - Launch, switch, and close applications (Chrome, VS Code, Notepad, Calculator, Explorer, etc.).
  - Windows volume control, battery monitoring, screenshots, and webcam capture.
  - USB drive portability and background startup automation (`run_vision_silent.vbs`, `manage_startup.bat`).
- **Conversational AI & Interruption:**
  - Powered by local Ollama LLMs (`llama3`, `deepseek-r1`, `mistral`) with zero cloud lock-in.
  - Instant voice barge-in / interruption: speak or double-clap while Vision is talking to immediately halt speech and issue a new command.
- **Natural Neural Voice:** High-fidelity TTS via `edge-tts` with fallback to Windows SAPI5 / pyttsx3.
- **Persistent Memory:** Remembers user name, context, notes, and conversation history (`memory.json`).

---

## Holographic Hand Gestures & Interaction

The interface connects hand landmarks directly to the 3D hologram and quantum particle swarm:

| Gesture / Input | Effect in Interface |
|---|---|
| **Palm Movement (X / Y)** | Translates the entire 3D hologram smoothly across the screen following your hand |
| **Palm Roll / Tilt** | Tilts and rolls the hologram rings and core along the palm axis |
| **`OPEN_PALM`** | Triggers an explosive radial energy burst and expands core diameter |
| **`CLOSED_FIST`** | Singularity collapse: pulls particle swarm and core into a concentrated high-density state |
| **`PINCH` / Dual Pinch** | Precision reticle targeting; two-hand pinch dynamically zooms the hologram in and out |
| **`TWO_FINGERS`** | Emits a high-energy glowing laser beam between your index and middle fingertips |
| **`INDEX_POINT`** | Highlights single-point tracking beacon with targeting lines |
| **`SWIPE_LEFT` / `SWIPE_RIGHT`** | Generates an instant rotational spin impulse and outward holographic shockwave ripples |
| **`DUAL_OPEN_PALMS`** | Connects both hands with an energy resonance bridge and pulsating central orb |
| **Key `C`** | Toggles the sci-fi webcam PIP preview in the top-left corner |
| **Mouse Drag & Scroll** | Manual camera rotation and zoom controls |
| **Key `+` / `-`** | Step zoom in / zoom out |
| **Key `[` / `]`** | Adjust bloom glow intensity |
| **Key `R` / `F`** | Reset orientation / Toggle fullscreen |
| **Key `Q` / `Esc`** | Exit interface |

## Project structure

```
vision-assistant/
├── vision.py          # main assistant (voice, commands, memory, AI)
├── interface.py       # holographic interface (OpenCV window)
├── requirements.txt
├── .gitignore
├── LICENSE
└── README.md
```

## Setup (macOS)

### 1. Prerequisites

- macOS with a microphone (camera optional – only for hand tracking)
- Python **3.10 – 3.12** (recommended; `mediapipe` may not support newer versions yet)
- [Homebrew](https://brew.sh)

```bash
brew install portaudio     # required to build PyAudio
brew install sox           # optional: metallic "Ultron" voice effect
```

### 2. Get the code

```bash
git clone https://github.com/<your-username>/vision-assistant.git
cd vision-assistant
```

### 3. Create a virtual environment and install dependencies

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 4. Install Ollama and a model (for AI chat)

```bash
brew install ollama
ollama serve &            # or open the Ollama app
ollama pull llama3
```

You can use another model by changing `OLLAMA_MODEL` in `vision.py`.

### 5. Allow macOS permissions

`System Settings → Privacy & Security`:

| Permission | Why |
|---|---|
| **Microphone** | voice commands and clap detection |
| **Camera** | photo command and hand tracking |
| **Accessibility / Automation** | volume control |
| **Screen Recording** | screenshots |

Give these to the app you run Vision from (Terminal, iTerm or VS Code), then **fully quit and reopen** it.

### 6. Run

```bash
python vision.py
```

Clap twice (or, if no input device is found, say "Hey Vision"). To test only the interface:

```bash
python interface.py            # add --sd (lighter) or --hd (Full HD)
```

## Example commands

| Say | What happens |
|---|---|
| "Open YouTube" / "youtube kholo" | opens YouTube |
| "Play Believer" / "believer gana sunao" | opens YouTube results |
| "Search Python tutorials on Google" | Google search |
| "Take a screenshot" | saves to `screenshots/` |
| "Take a photo" | saves to `photos/` |
| "Create a folder named projects" | creates it on the Desktop |
| "Volume 40" / "increase volume" / "mute" | controls volume |
| "Battery" | reads battery status |
| "My name is Alex" / "What is my name" | memory |
| "Remember that my exam is on Friday" | saves a note |
| "Close interface" / "Open interface" | controls the UI window |
| "Go to sleep" | Vision stops listening until "Hey Vision" |
| "Stop Vision" | shuts down |
| anything else (e.g. "Who invented the telephone?") | answered by the local AI |

## Interface controls

| Input | Action |
|---|---|
| Mouse drag | rotate |
| Scroll / `+` `-` | zoom |
| `[` `]` | glow down / up |
| `R` | reset view |
| `F` | fullscreen |
| `Q` / `Esc` | quit |
| One hand (camera) | rotate |
| Pinch with both hands | zoom |

## Configuration

Edit the top of `vision.py`:

- `CREATOR_NAME` – the name Vision says it was created by
- `EDGE_VOICE`, `EDGE_RATE`, `EDGE_PITCH` – voice style
- `CLAP_THRESHOLD` – lower it if claps aren't detected, raise it if it triggers by itself
- `OLLAMA_MODEL` – which local model to use
- `INTERFACE_ARGS` – e.g. `["--hd"]`

## Troubleshooting

- **`PyAudio` fails to install:** run `brew install portaudio`, then `pip install pyaudio` again.
- **Camera not found:** check the Camera permission and close Zoom/FaceTime, then restart your terminal.
- **Hand model download error:** download [hand_landmarker.task](https://storage.googleapis.com/mediapipe-models/hand_landmarker/hand_landmarker/float16/1/hand_landmarker.task) and place it next to `interface.py`. The interface still works with the mouse.
- **"AI is not responding":** make sure Ollama is running and the model is pulled (`ollama list`).
- **Voice sounds robotic:** `edge-tts` needs internet; offline it falls back to the macOS voice.
- Speech recognition uses Google's free web service, so it also needs internet.

## Notes

- Built for macOS (uses `afplay`, `say`, `open`, `osascript`, `pmset`, `screencapture`).
- `memory.json`, screenshots and photos stay on your machine and are git-ignored.

## License

MIT – see [LICENSE](LICENSE).
