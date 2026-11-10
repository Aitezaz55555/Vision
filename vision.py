import asyncio
import json
import math
import os
import re
import shutil
import struct
import subprocess
import sys
import tempfile
import threading
import time
import urllib.parse
import webbrowser
from datetime import datetime
from typing import Optional, Dict, Any, Tuple, List

os.environ.setdefault("MPLCONFIGDIR", os.path.join(tempfile.gettempdir(), "matplotlib"))

import cv2
import ollama
import pyaudio
import speech_recognition as sr

from modules import (
    ConversationContext,
    launch_application, close_application, normalize_app_name, find_application_path, control_window,
    control_volume, get_volume_level, adjust_brightness,
    lock_workstation, execute_shutdown, get_battery_info,
    get_performance_info, get_system_summary, capture_screenshot,
    open_website, search_web, sanitize_url,
    open_folder, list_files_in_folder, search_and_open_file,
    match_deterministic_intent, parse_intent_with_ollama,
    ClapDetector, acquire_instance_lock, release_instance_lock,
    enable_startup, disable_startup, is_startup_enabled, get_startup_status,
    play_activation_chime, play_interrupt_cue,
    add_reminder, list_reminders, cancel_all_reminders, start_reminder_scheduler,
    StreamingTTSManager, split_stream_into_sentences, clean_text_for_speech,
    detect_conversation_mode, build_system_prompt, prepare_chat_messages, stream_ollama_tokens
)

# Global short-term conversation context
context = ConversationContext()

try:
    import edge_tts          # natural neural voices (needs internet)
    HAS_EDGE = True
except Exception:
    HAS_EDGE = False

try:
    import pygame
    HAS_PYGAME = True
except Exception:
    HAS_PYGAME = False

try:
    import pyttsx3
    HAS_PYTTSX3 = True
except Exception:
    HAS_PYTTSX3 = False

try:
    from ctypes import cast, POINTER
    from comtypes import CLSCTX_ALL
    from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume
    HAS_PYCAW = True
except Exception:
    HAS_PYCAW = False

try:
    from PIL import ImageGrab
    HAS_PIL = True
except Exception:
    HAS_PIL = False

try:
    import psutil
    HAS_PSUTIL = True
except Exception:
    HAS_PSUTIL = False


# ==================== CONFIG & PORTABLE PATHS ==================== #
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_FILE = os.path.join(SCRIPT_DIR, "vision_config.json")


def load_config():
    defaults = {
        "assistant_name": "Vision",
        "creator_name": "Taha",
        "ollama_model": "llama3.2:1b",
        "ollama_api_url": "http://127.0.0.1:11434",
        "tts_engine": "edge",
        "edge_voice": "en-US-ChristopherNeural",
        "edge_rate": "-12%",
        "edge_pitch": "-18Hz",
        "edge_volume": "+50%",
        "play_volume": 2.5,
        "ultron_effect": True,
        "clap_threshold": 2000,
        "data_dir": "data",
        "portable_mode": False,
        "portable_models_dir": "OllamaModels",
    }
    if os.path.isfile(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                loaded = json.load(f)
                defaults.update(loaded)
        except Exception as e:
            print(f"[Config] Error loading {CONFIG_FILE}: {e}")
    return defaults


CONFIG = load_config()

ASSISTANT_NAME = CONFIG.get("assistant_name", "Vision")
CREATOR_NAME = CONFIG.get("creator_name", "Taha")
OLLAMA_MODEL = os.environ.get("VISION_OLLAMA_MODEL", CONFIG.get("ollama_model", "llama3.2:1b"))
OLLAMA_API_URL = os.environ.get("OLLAMA_HOST", CONFIG.get("ollama_api_url", "http://127.0.0.1:11434"))

# Portable Data Directory (relative to project root on USB drive)
DATA_DIR_NAME = CONFIG.get("data_dir", "data")
DATA_DIR = os.path.join(SCRIPT_DIR, DATA_DIR_NAME)
os.makedirs(DATA_DIR, exist_ok=True)

MEMORY_FILE = os.path.join(DATA_DIR, "memory.json")
SCREENSHOTS_DIR = os.path.join(DATA_DIR, "screenshots")
PHOTOS_DIR = os.path.join(DATA_DIR, "photos")
LOGS_DIR = os.path.join(DATA_DIR, "logs")
os.makedirs(SCREENSHOTS_DIR, exist_ok=True)
os.makedirs(PHOTOS_DIR, exist_ok=True)
os.makedirs(LOGS_DIR, exist_ok=True)

STATE_FILE = os.path.join(DATA_DIR, "vision_state.txt")
FALLBACK_STATE_FILE = os.path.join(tempfile.gettempdir(), "vision_state.txt")
STATE_JSON_FILE = os.path.join(DATA_DIR, "vision_state.json")
FALLBACK_STATE_JSON = os.path.join(tempfile.gettempdir(), "vision_state.json")
INTERFACE_PATH = os.path.join(SCRIPT_DIR, "interface.py")
INTERFACE_ARGS = []

# ---- Voice ----
TTS_ENGINE = CONFIG.get("tts_engine", "edge")
EDGE_VOICE = CONFIG.get("edge_voice", "en-US-ChristopherNeural")
EDGE_RATE = CONFIG.get("edge_rate", "-12%")
EDGE_PITCH = CONFIG.get("edge_pitch", "-18Hz")
EDGE_VOLUME = CONFIG.get("edge_volume", "+50%")
PLAY_VOLUME = float(CONFIG.get("play_volume", 2.5))
ULTRON_EFFECT = bool(CONFIG.get("ultron_effect", True))
ULTRON_FX = ["compand", "0.02,0.2", "6:-70,-60,-20", "-5", "-90", "0.1",
             "pitch", "-80",
             "chorus", "0.7", "0.9", "55", "0.4", "0.25", "2", "-t",
             "equalizer", "2800", "1.0q", "+3",
             "bass", "+3",
             "pad", "0", "0.5",
             "reverb", "20", "50", "60",
             "norm", "-0.5"]
SOX_PATH = shutil.which("sox")
VOICE_CANDIDATES = ["Ralph", "Daniel", "Alex", "Fred"]
VOICE_RATE = 150

# ---- Double clap ----
CLAP_THRESHOLD = CONFIG.get("clap_threshold", "auto")
CLAP_MIN_INTERVAL = 0.10
CLAP_MAX_INTERVAL = 0.85
CLAP_DEBOUNCE = 0.08
AUDIO_CHUNK = 1024
AUDIO_RATE = 44100
AUDIO_FORMAT = pyaudio.paInt16
AUDIO_CHANNELS = 1

# ---- Listening ----
WAKE_LISTEN_TIMEOUT = 4
WAKE_PHRASE_TIME = 3
COMMAND_LISTEN_TIMEOUT = 4
COMMAND_PHRASE_TIME = 8
MAX_AUDIO_FAILURES = 3
CALIBRATION_INTERVAL = 120
WAKE_PHRASES = ["hey vision", "hey visions", "a vision", "hey vishon", "hey vizhan"]

# ==================== STATE ==================== #
conversation_mode = False
initial_clap_activation_done = False
clap_trigger_event = threading.Event()
audio_lock = threading.Lock()
audio_failure_count = 0
last_calibration_time = 0
interface_proc = None


def pick_voice():
    if sys.platform == "darwin":
        try:
            out = subprocess.run(["say", "-v", "?"], capture_output=True, text=True, timeout=5).stdout
            for name in VOICE_CANDIDATES:
                if re.search(rf"^{re.escape(name)}\s", out, re.MULTILINE):
                    return name
        except Exception:
            pass
    return None


VOICE = pick_voice()


def set_vision_state(state: str, text: str = "", result: str = ""):
    """Updates atomic visual state JSON and text files for the interface."""
    state_obj = {
        "state": state,
        "text": text,
        "result": result,
        "timestamp": time.time(),
    }
    # Write JSON
    for p in (STATE_JSON_FILE, FALLBACK_STATE_JSON):
        try:
            with open(p, "w", encoding="utf-8") as f:
                json.dump(state_obj, f)
        except Exception:
            pass

    # Write text for backward compatibility
    simple_txt = "speaking" if state == "speaking" else "idle"
    for p in (STATE_FILE, FALLBACK_STATE_FILE):
        try:
            with open(p, "w", encoding="utf-8") as f:
                f.write(simple_txt)
        except Exception:
            pass


def set_speaking(flag):
    """Tell the interface whether Vision is speaking (interface turns red)."""
    set_vision_state("speaking" if flag else "idle")


set_speaking(False)

# ==================== SPEECH RECOGNIZER ==================== #
def get_microphone():
    """Return sr.Microphone with configured device_index if specified in config, else default."""
    cfg_idx = CONFIG.get("microphone_device_index", None)
    if cfg_idx is not None and isinstance(cfg_idx, int):
        try:
            return sr.Microphone(device_index=cfg_idx)
        except Exception:
            pass
    return sr.Microphone()


def create_recognizer():
    r = sr.Recognizer()
    r.pause_threshold = float(CONFIG.get("pause_threshold", 0.5))
    r.phrase_threshold = float(CONFIG.get("phrase_threshold", 0.2))
    r.non_speaking_duration = float(CONFIG.get("non_speaking_duration", 0.3))
    r.energy_threshold = int(CONFIG.get("energy_threshold", 150))
    r.dynamic_energy_threshold = True
    return r


recognizer = create_recognizer()


def calibrate_microphone_once(force=False):
    global last_calibration_time
    now = time.time()
    if not force and last_calibration_time and (now - last_calibration_time) < CALIBRATION_INTERVAL:
        return
    try:
        print("Calibrating microphone for ambient noise...")
        with audio_lock:
            with get_microphone() as source:
                recognizer.adjust_for_ambient_noise(source, duration=0.8)
        recognizer.energy_threshold = max(80, min(250, recognizer.energy_threshold))
        last_calibration_time = time.time()
        print(f"Microphone calibrated (energy threshold {int(recognizer.energy_threshold)})")
    except Exception as e:
        print(f"Microphone calibration warning: {e}")


def reset_audio_pipeline(reason="audio recovery"):
    global recognizer, audio_failure_count
    print(f"[Audio] Resetting recognizer: {reason}")
    recognizer = create_recognizer()
    audio_failure_count = 0


def note_audio_failure(reason):
    global audio_failure_count
    audio_failure_count += 1
    print(f"[Audio] warning ({audio_failure_count}/{MAX_AUDIO_FAILURES}): {reason}")
    if audio_failure_count >= MAX_AUDIO_FAILURES:
        reset_audio_pipeline(reason)


def safe_listen(timeout=5, phrase_time=6, mode="command"):
    """Open the microphone for one bounded listen cycle, then release it."""
    try:
        with audio_lock:
            with get_microphone() as source:
                print(f"Listening ({mode})...")
                audio = recognizer.listen(source, timeout=max(1, int(timeout)),
                                          phrase_time_limit=max(1, int(phrase_time)))
        text = recognizer.recognize_google(audio, language="en-IN").strip()
        if text:
            global audio_failure_count
            audio_failure_count = 0
            print(f"Heard ({mode}): {text}")
        return text
    except sr.WaitTimeoutError:
        return ""
    except sr.UnknownValueError:
        note_audio_failure("speech was not understood")
    except sr.RequestError as e:
        note_audio_failure(f"recognition service error: {e}")
    except OSError as e:
        note_audio_failure(f"microphone error: {e}")
    except Exception as e:
        note_audio_failure(f"unexpected listen error: {e}")
    return ""


def listen_for_command(timeout=COMMAND_LISTEN_TIMEOUT, phrase_time=COMMAND_PHRASE_TIME):
    return safe_listen(timeout, phrase_time, "command")


def listen_for_wake_word():
    return safe_listen(WAKE_LISTEN_TIMEOUT, WAKE_PHRASE_TIME, "wake")


# ==================== MEMORY ==================== #
def load_memory():
    default = {"name": "", "notes": [], "last_conversation": []}
    try:
        if not os.path.exists(MEMORY_FILE):
            with open(MEMORY_FILE, "w", encoding="utf-8") as f:
                json.dump(default, f, indent=4)
        with open(MEMORY_FILE, "r", encoding="utf-8") as f:
            memory = json.load(f)
        for key, val in default.items():
            memory.setdefault(key, val)
        return memory
    except Exception as e:
        print("Memory load error:", e)
        return default


def save_memory(memory):
    tmp_path = MEMORY_FILE + ".tmp"
    try:
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(memory, f, indent=4)
        os.replace(tmp_path, MEMORY_FILE)
    except Exception as e:
        print("Memory save error:", e)
        if os.path.exists(tmp_path):
            try:
                os.remove(tmp_path)
            except Exception:
                pass


def save_conversation(user_text, vision_reply):
    memory = load_memory()
    memory["last_conversation"].append({
        "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "user": user_text,
        "vision": vision_reply,
    })
    memory["last_conversation"] = memory["last_conversation"][-10:]
    save_memory(memory)


# ==================== INTERFACE (interface.py runs as a separate process) ==================== #
def interface_running():
    return interface_proc is not None and interface_proc.poll() is None


def open_interface():
    global interface_proc
    if interface_running():
        return True
    if not os.path.exists(INTERFACE_PATH):
        speak("Sir, I could not find the interface file")
        return False
    try:
        interface_proc = subprocess.Popen([sys.executable, INTERFACE_PATH] + INTERFACE_ARGS, cwd=SCRIPT_DIR)
        print("Interface opened")
        return True
    except Exception as e:
        print("Interface start error:", e)
        speak("Sir, the interface failed to start")
        return False


def close_interface():
    global interface_proc
    if interface_running():
        try:
            interface_proc.terminate()
            interface_proc.wait(timeout=3)
        except Exception:
            try:
                interface_proc.kill()
            except Exception:
                pass
        interface_proc = None
        return True
    interface_proc = None
    return False


def shutdown_app():
    set_speaking(False)
    close_interface()
    threading.Timer(0.5, os._exit, args=(0,)).start()


# ==================== SPEAK ==================== #
def _tmp(suffix):
    f = tempfile.NamedTemporaryFile(suffix=suffix, delete=False)
    f.close()
    return f.name


def _rm(*paths):
    for p in paths:
        if p and os.path.exists(p):
            try:
                os.remove(p)
            except Exception:
                pass


async def _edge_save(text, path):
    comm = edge_tts.Communicate(text, EDGE_VOICE, rate=EDGE_RATE, pitch=EDGE_PITCH, volume=EDGE_VOLUME)
    await comm.save(path)


# ==================== STREAMING TTS & INSTANT BARGE-IN ENGINE ==================== #
tts_manager = StreamingTTSManager(
    voice=EDGE_VOICE,
    rate=EDGE_RATE,
    pitch=EDGE_PITCH,
    volume=EDGE_VOLUME,
    state_callback=set_vision_state,
    microphone_factory=get_microphone,
    recognizer_factory=create_recognizer
)

# Backward-compatibility alias for tests and background listeners
tts_interrupted = tts_manager.cancel_event
tts_playing = tts_manager.is_playing

# Backward-compatibility hooks
speak_edge = None
speak_offline = None


def trigger_barge_in(reason: str = "user"):
    """Immediately halts audio playback, cancels Ollama generation, and notifies interface."""
    tts_manager.interrupt(reason=reason)


def speak(text):
    """Speaks a message with instant barge-in support."""
    if not context.spoken_responses_enabled:
        print("[Silent Mode] vision:", text)
        set_vision_state("executing", result=str(text))
        return

    cleaned = str(text).replace("\n", " ").strip().lstrip("-")
    if not cleaned:
        return
    print("vision:", cleaned)
    if callable(speak_edge):
        try:
            return speak_edge(cleaned)
        except Exception:
            pass
    tts_manager.speak_text(cleaned)


def time_greeting():
    hour = datetime.now().hour
    return "Good morning" if hour < 12 else "Good afternoon" if hour < 17 else "Good evening"


# ==================== OLLAMA MANAGER & DETECTION ==================== #
def find_ollama_executable():
    """Locate ollama executable across PATH, standard Windows paths, and project-local paths."""
    cmd = shutil.which("ollama") or shutil.which("ollama.exe")
    if cmd:
        return cmd

    candidates = [
        os.path.expandvars(r"%LOCALAPPDATA%\Programs\Ollama\ollama.exe"),
        os.path.expandvars(r"%ProgramFiles%\Ollama\ollama.exe"),
        os.path.expandvars(r"%ProgramFiles(x86)%\Ollama\ollama.exe"),
        os.path.join(SCRIPT_DIR, "Ollama", "ollama.exe"),
        os.path.join(SCRIPT_DIR, "ollama.exe"),
    ]
    for p in candidates:
        if os.path.isfile(p):
            return p
    return None


def is_ollama_service_running(host=None):
    """Check whether local Ollama service is reachable on its API."""
    import urllib.request
    url = (host or OLLAMA_API_URL).rstrip("/") + "/api/tags"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "VISION-Assistant"})
        with urllib.request.urlopen(req, timeout=2.5) as resp:
            return resp.status == 200
    except Exception:
        return False


def start_ollama_service():
    """Attempt to start local Ollama server if not currently running."""
    if is_ollama_service_running():
        return True

    exe = find_ollama_executable()
    if not exe:
        print("[Ollama] Could not locate ollama.exe on this system.")
        return False

    print(f"[Ollama] Starting local Ollama service using {exe}...")
    try:
        env = os.environ.copy()
        # Only use portable models if explicitly in portable mode with an existing populated directory
        if os.environ.get("VISION_PORTABLE") == "1" and CONFIG.get("portable_mode", False):
            portable_models = os.path.join(SCRIPT_DIR, CONFIG.get("portable_models_dir", "OllamaModels"))
            if os.path.isdir(portable_models) and os.listdir(portable_models):
                env["OLLAMA_MODELS"] = portable_models
                print(f"[Ollama] Portable models directory active: {portable_models}")

        if sys.platform.startswith("win"):
            flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
            subprocess.Popen([exe, "serve"], env=env, creationflags=flags)
        else:
            subprocess.Popen([exe, "serve"], env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

        for _ in range(16):
            time.sleep(0.5)
            if is_ollama_service_running():
                print("[Ollama] Local Ollama service is up and running!")
                return True
    except Exception as e:
        print(f"[Ollama] Error starting service: {e}")

    return is_ollama_service_running()


def get_installed_ollama_models():
    """Retrieve list of locally installed Ollama models via API."""
    import urllib.request
    url = OLLAMA_API_URL.rstrip("/") + "/api/tags"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "VISION-Assistant"})
        with urllib.request.urlopen(req, timeout=3.0) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            return [m.get("name", "") for m in data.get("models", [])]
    except Exception as e:
        return []


def verify_ollama_model(model_name=None):
    """
    Verify whether the target model or a compatible version is installed.
    Matches exact (e.g. 'llama3.2:1b') or base names (e.g. 'llama3.2:1b-instruct-q4_K_M').
    """
    target_model = model_name or OLLAMA_MODEL
    models = get_installed_ollama_models()
    for m in models:
        if m == target_model:
            return True, m
        if target_model.startswith(m) or m.startswith(target_model):
            return True, m
        if m.split(":")[0] == target_model.split(":")[0]:
            return True, m
    return False, target_model


# ==================== STREAMING CONVERSATIONAL AI (Ollama) ==================== #
def stream_conversational_response(prompt: str) -> Tuple[bool, str]:
    """
    Streams conversational AI response from Ollama, splits tokens into sentences,
    and plays sentence 1 immediately while sentence 2 is being generated.
    Supports Normal, Detailed, and Entertainment modes with instant barge-in.
    Returns: (was_interrupted: bool, full_reply: str)
    """
    if not is_ollama_service_running():
        start_ollama_service()

    active_model = OLLAMA_MODEL
    is_installed, resolved_model = verify_ollama_model(OLLAMA_MODEL)
    if is_installed:
        active_model = resolved_model
    else:
        available = get_installed_ollama_models()
        if available:
            # Seamlessly pick the first available model so user is never blocked
            active_model = available[0]
            print(f"[Ollama] Model '{OLLAMA_MODEL}' not found. Seamlessly using installed model '{active_model}'.")
            update_config("ollama_model", active_model)
        else:
            msg = f"Sir, no models are currently installed in Ollama. Please run 'ollama pull {OLLAMA_MODEL}' in your command prompt."
            print(f"[Ollama] {msg}")
            speak(msg)
            return False, msg

    memory = load_memory()
    mode, messages = prepare_chat_messages(
        user_prompt=prompt,
        context=context,
        memory=memory,
        assistant_name=ASSISTANT_NAME,
        creator_name=CREATOR_NAME
    )

    print(f"[Ollama Chat] Streaming response in mode='{mode}' model='{active_model}'...")
    set_vision_state("generating", text=prompt)

    token_gen = stream_ollama_tokens(
        ollama_client=ollama,
        model_name=active_model,
        messages=messages,
        cancel_event=tts_manager.cancel_event,
        max_tokens=600 if mode == "detailed" else (400 if mode == "entertainment" else 350)
    )

    sentence_gen = split_stream_into_sentences(token_gen, tts_manager.cancel_event)

    was_interrupted, full_reply = tts_manager.speak_stream(sentence_gen)

    if not was_interrupted:
        context.add_turn(prompt, full_reply, "chat")
        save_conversation(prompt, full_reply)
        set_vision_state("idle", result=full_reply)
    else:
        print("\n[Barge-In] Conversational generation and playback stopped!")
        set_vision_state("interrupted")
        time.sleep(0.2)
        set_vision_state("listening")

    return was_interrupted, full_reply


def ask_local_ai(prompt: str) -> str:
    """Non-streaming backward-compatibility wrapper."""
    _, reply = stream_conversational_response(prompt)
    return reply


# ==================== BASIC ACTIONS ==================== #
def open_path(path):
    """Cross-platform path/file opener: os.startfile on Windows, open on macOS, xdg-open on Linux."""
    try:
        if sys.platform.startswith("win"):
            os.startfile(os.path.abspath(path))
        elif sys.platform == "darwin":
            subprocess.run(["open", path])
        else:
            subprocess.run(["xdg-open", path])
    except Exception as e:
        print("Error opening path:", e)


def open_folder_anywhere(name):
    try:
        target = name.strip().lower()
        if sys.platform.startswith("win"):
            search_roots = [
                os.path.expanduser("~/Desktop"),
                os.path.expanduser("~/Documents"),
                os.path.expanduser("~/Downloads"),
                os.path.expanduser("~"),
            ]
            found = None
            for root in search_roots:
                if not os.path.isdir(root):
                    continue
                try:
                    for entry in os.scandir(root):
                        if entry.is_dir() and target in entry.name.lower():
                            found = entry.path
                            break
                except Exception:
                    continue
                if found:
                    break

            if found:
                speak("Opening folder")
                open_path(found)
            else:
                speak("Folder not found Sir")
        else:
            result = subprocess.run(["mdfind", name], capture_output=True, text=True)
            folders = [f for f in result.stdout.strip().split("\n") if os.path.isdir(f)]
            if folders:
                speak("Opening folder")
                subprocess.run(["open", folders[0]])
            else:
                speak("Folder not found Sir")
    except Exception as e:
        print("Folder search error:", e)
        speak("Error while opening folder")


def create_folder(name):
    try:
        path = os.path.join(os.path.expanduser("~/Desktop"), name)
        if os.path.exists(path):
            speak("Folder already exists")
        else:
            os.makedirs(path)
            speak(f"Folder {name} created successfully")
    except Exception as e:
        print("Folder error:", e)
        speak("Error creating folder")


def play_song(song):
    """Opens YouTube search results for the song."""
    if not song:
        speak("Please tell me the song name.")
        return
    speak(f"Playing {song} on YouTube")
    webbrowser.open(f"https://www.youtube.com/results?search_query={urllib.parse.quote(song)}")


def take_screenshot():
    os.makedirs(SCREENSHOTS_DIR, exist_ok=True)
    path = os.path.join(SCREENSHOTS_DIR, f"screenshot_{datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}.png")
    success = False
    if HAS_PIL:
        try:
            img = ImageGrab.grab()
            img.save(path)
            success = True
        except Exception as e:
            print("PIL ImageGrab error:", e)

    if not success and sys.platform == "darwin" and shutil.which("screencapture"):
        try:
            subprocess.run(["screencapture", "-x", path])
            success = True
        except Exception:
            pass

    if success and os.path.exists(path):
        open_path(path)
        return path

    speak("Failed to take screenshot Sir")
    return None


def take_photo():
    try:
        camera = cv2.VideoCapture(0)
        if not camera.isOpened():
            speak("Camera not found")
            return None
        speak("Opening camera. Get ready.")
        time.sleep(3)
        ret, frame = camera.read()
        camera.release()
        if not ret:
            speak("Failed to capture photo")
            return None
        os.makedirs(PHOTOS_DIR, exist_ok=True)
        path = os.path.join(PHOTOS_DIR, f"photo_{datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}.jpg")
        cv2.imwrite(path, frame)
        open_path(path)
        speak("Photo captured successfully")
        return path
    except Exception as e:
        print("Camera error:", e)
        speak("Error while taking photo")
        return None


PERMISSION_HINT = "Sorry Sir, I could not do that. Please allow permission for audio control."
VOLUME_STEP = 10


def run_osascript(script):
    try:
        result = subprocess.run(["osascript", "-e", script], capture_output=True, text=True, timeout=10)
        if result.returncode != 0:
            print("osascript error:", result.stderr.strip())
            return None
        return result.stdout.strip()
    except Exception as e:
        print("osascript exception:", e)
        return None


def _to_int(value, default=None):
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return default


# Volume control is handled by modules.system.control_volume


def get_battery_status():
    if HAS_PSUTIL:
        try:
            battery = psutil.sensors_battery()
            if battery is not None:
                pct = int(battery.percent)
                charging = battery.power_plugged
                reply = f"Battery is at {pct} percent and {'charging' if charging else 'not charging'}"
                speak(reply)
                return reply
        except Exception as e:
            print("psutil battery error:", e)

    if sys.platform.startswith("win"):
        try:
            import ctypes
            class SYSTEM_POWER_STATUS(ctypes.Structure):
                _fields_ = [
                    ('ACLineStatus', ctypes.c_byte),
                    ('BatteryFlag', ctypes.c_byte),
                    ('BatteryLifePercent', ctypes.c_byte),
                    ('SystemStatusFlag', ctypes.c_byte),
                    ('BatteryLifeTime', ctypes.c_ulong),
                    ('BatteryFullLifeTime', ctypes.c_ulong),
                ]
            status = SYSTEM_POWER_STATUS()
            if ctypes.windll.kernel32.GetSystemPowerStatus(ctypes.byref(status)):
                pct = status.BatteryLifePercent
                if pct != 255:
                    charging = status.ACLineStatus == 1
                    reply = f"Battery is at {pct} percent and {'charging' if charging else 'not charging'}"
                    speak(reply)
                    return reply
        except Exception as e:
            print("Windows battery error:", e)

    if sys.platform == "darwin":
        try:
            out = subprocess.run(["pmset", "-g", "batt"], capture_output=True, text=True, timeout=5).stdout
            m = re.search(r"(\d+)%", out)
            if m:
                charging = re.search(r"\bcharging\b|\bfinishing charge\b", out) and "discharging" not in out
                reply = f"Battery is at {m.group(1)} percent and {'charging' if charging else 'not charging'}"
                speak(reply)
                return reply
        except Exception as e:
            print("pmset battery error:", e)

    reply = "I could not read the battery level or your system is connected to AC power without a battery"
    speak(reply)
    return reply


def open_app(app_name):
    if app_name == "youtube":
        reply = "Opening YouTube"
        speak(reply)
        webbrowser.open("https://youtube.com")
    elif app_name in ("safari", "edge", "browser"):
        reply = "Opening browser"
        speak(reply)
        if sys.platform.startswith("win"):
            try:
                subprocess.Popen(["cmd", "/c", "start", "msedge"], shell=True)
            except Exception:
                webbrowser.open("https://google.com")
        elif sys.platform == "darwin":
            subprocess.run(["open", "-a", "Safari"])
        else:
            webbrowser.open("https://google.com")
    elif app_name == "chrome":
        reply = "Opening Chrome"
        speak(reply)
        if sys.platform.startswith("win"):
            try:
                subprocess.Popen(["cmd", "/c", "start", "chrome"], shell=True)
            except Exception:
                webbrowser.open("https://google.com")
        elif sys.platform == "darwin":
            subprocess.run(["open", "-a", "Google Chrome"])
        else:
            webbrowser.open("https://google.com")
    else:
        reply = "Sorry Sir, I do not know that app"
        speak(reply)
    return reply


def introduce_yourself():
    name = load_memory().get("name", "").strip()
    known = f" I remember you, {name}." if name else ""
    speak(f"Hello. I am {ASSISTANT_NAME}. Created by {CREATOR_NAME}.{known} "
          "I am not just an assistant. I am fast, intelligent, and always watching. What is your command?")


# ==================== ACTIVE MODE ==================== #
def enter_active_mode():
    global conversation_mode
    conversation_mode = True
    set_vision_state("listening")


def exit_active_mode():
    global conversation_mode
    conversation_mode = False
    set_vision_state("monitoring")
    print("\n[Standby] Vision is in background standby. Clap twice to activate!")


def run_active_listening_loop():
    print("[Active mode] Continuous listening ON...")
    silence_count = 0
    max_silence = 4  # after 4 consecutive empty listens (~16s), return to standby

    while conversation_mode:
        set_vision_state("listening")
        command = listen_for_command()
        if command:
            silence_count = 0
            set_vision_state("processing", text=command)
            process_command(command)
            if not conversation_mode:
                break
        else:
            silence_count += 1
            if silence_count >= max_silence:
                print("[Active mode] Inactivity timeout. Returning to background standby.")
                exit_active_mode()
                break
            time.sleep(0.05)


# ==================== COMMAND UNDERSTANDING ==================== #
FILLER_PHRASES = ["can you", "could you", "would you", "will you", "can u", "please", "kindly",
                  "zara", "jara", "ek baar", "yaar", "bhai", "mere liye", "for me", "hey", "okay", "ok", "vision"]
OPEN_WORDS = ["open", "launch", "start", "run", "kholo", "khol", "kholna", "kholiye", "kholdo",
              "khol do", "khol de", "chalu", "chalao", "chala do", "chalana"]
APP_ALIASES = {
    "youtube": ["youtube", "you tube"],
    "safari": ["safari"],
    "chrome": ["google chrome", "chrome", "crome"],
    "edge": ["edge", "microsoft edge", "ms edge", "browser", "internet explorer"],
}
PLAY_WORDS = ["play", "bajao", "baja do", "bajana", "sunao", "suna do", "sunna", "lagao", "laga do"]
SONG_WORDS = ["song", "songs", "gana", "gaana", "gaane", "music"]
SEARCH_WORDS = ["search", "find", "look up", "dhundo", "dhundh", "dhoondo", "khojo", "khoj"]
CREATE_WORDS = ["create", "make", "new", "generate", "banao", "bana do", "bana", "naya", "nayi"]
CLEAR_WORDS = ["clear", "reset", "delete", "erase", "wipe", "mita", "hata", "bhula", "saaf"]
INTERFACE_WORDS = ["interface", "hologram", "holo gram", "holographic", "holo"]
VOLUME_WORDS = ["volume", "sound", "awaaz", "awaz", "avaaz", "aawaz"]
UP_WORDS = ["increase", "up", "raise", "badhao", "badha", "badhana", "zyada", "jyada", "tez", "louder", "more", "higher", "high"]
DOWN_WORDS = ["decrease", "down", "lower", "reduce", "kam", "kamm", "kum", "dheema", "dheemi", "less", "quieter", "low"]
NUM_WORDS = {"zero": 0, "ten": 10, "twenty": 20, "thirty": 30, "forty": 40, "fifty": 50,
             "sixty": 60, "seventy": 70, "eighty": 80, "ninety": 90, "hundred": 100}
QUESTION_STARTS = ("what", "why", "how", "who", "when", "where", "which", "tell me", "explain",
                   "kya", "kaun", "kyun", "kyu", "kaise", "kitna", "kitne", "kab", "kahan", "batao")

SLEEP_RE = re.compile(r"\b(?:go to sleep|sleep mode|sleep now|sleep vision|vision sleep|stop listening|"
                      r"so jao|so ja|chup ho jao|chup ho ja|chup raho|take a break)\b")
STOP_RE = re.compile(r"\b(?:(?:stop|exit|quit|shut ?down|terminate|close|band)\s+(?:karo\s+)?vision|"
                     r"vision\s+(?:stop|exit|quit|shut ?down|terminate|band(?:\s+(?:karo|ho\s+jao|kar\s+do))?)|"
                     r"exit program|quit program)\b")


def _pattern(words):
    return r"\b(?:" + "|".join(re.escape(w) for w in sorted(words, key=len, reverse=True)) + r")\b"


def has_any(text, words):
    return re.search(_pattern(words), text) is not None


def strip_words(text, words):
    return re.sub(r"\s+", " ", re.sub(_pattern(words), " ", text)).strip()


def prepare_command(text):
    """Returns (raw, cmd): raw = lowercase without punctuation, cmd = raw without filler words."""
    raw = re.sub(r"[.,!?;:\"]", " ", text.lower())
    raw = re.sub(r"\s+", " ", raw).strip()
    return raw, strip_words(raw, FILLER_PHRASES)


def find_app(text):
    best, best_len = None, 0
    for app_name, aliases in APP_ALIASES.items():
        for alias in aliases:
            if re.search(rf"\b{re.escape(alias)}\b", text) and len(alias) > best_len:
                best, best_len = app_name, len(alias)
    return best


def looks_like_question(cmd):
    return cmd.startswith(QUESTION_STARTS) or cmd.endswith(" kya hai")


def parse_level_request(cmd):
    """Returns (mode, value): ('set', 0-100) / ('up'|'down', step|None) / (None, None)."""
    direction = "down" if has_any(cmd, DOWN_WORDS) else "up" if has_any(cmd, UP_WORDS) else None
    m = re.search(r"\bby\s+(\d{1,3})\b", cmd) or re.search(r"\b(\d{1,3})\s+(?:percent\s+)?se\b", cmd)
    if m and direction:
        return direction, min(100, int(m.group(1)))
    m = re.search(r"\b(\d{1,3})\b", cmd)
    if m:
        return "set", min(100, int(m.group(1)))
    for word, num in NUM_WORDS.items():
        if re.search(rf"\b{word}\b", cmd):
            return "set", num
    if has_any(cmd, ["full", "max", "maximum"]):
        return "set", 100
    if has_any(cmd, ["half"]):
        return "set", 50
    if has_any(cmd, ["min", "minimum"]):
        return "set", 0
    return (direction, None) if direction else (None, None)


def detect_intent(cmd, raw):
    """Rule-based intent detection. Returns (intent, args) or (None, {})."""
    toks = cmd.split()
    app_found = find_app(cmd)

    if SLEEP_RE.search(raw) or ("sleep" in toks and len(toks) <= 3):
        return "sleep", {}
    if STOP_RE.search(raw):
        return "stop", {}

    if has_any(cmd, ["battery"]):
        return "battery", {}

    if has_any(cmd, INTERFACE_WORDS):
        if has_any(cmd, ["close", "stop", "exit", "quit", "hide", "off", "band", "hatao", "hata", "kill"]):
            return "interface", {"action": "close"}
        return "interface", {"action": "open"}

    if has_any(cmd, ["unmute"]):
        return "volume", {"mode": "unmute", "value": None}
    if has_any(cmd, ["mute"]):
        return "volume", {"mode": "mute", "value": None}
    if has_any(cmd, VOLUME_WORDS):
        mode, value = parse_level_request(cmd)
        if mode:
            return "volume", {"mode": mode, "value": value}

    # memory: name
    if has_any(cmd, ["my name", "mera naam", "mera name", "call me"]):
        if has_any(cmd, ["what", "kya", "do you know", "batao", "pata", "who"]):
            return "get_name", {}
        m = re.search(r"(?:my name is|my name's|call me|mera naam|mera name)\s+(.+?)(?:\s+(?:hai|he|h|hain))?$", cmd)
        return "set_name", {"name": m.group(1).strip() if m else ""}

    # memory: notes / history
    m = re.search(r"\b(?:remember this|remember that|yaad rakho|yaad rakhna|note this|note down|note kar lo|note karo|note kar)\b\s*(?:ki\s+|that\s+)?(.*)$", cmd)
    if m:
        return "add_note", {"note": m.group(1).strip()}
    if has_any(cmd, ["notes"]):
        return ("clear_notes", {}) if has_any(cmd, CLEAR_WORDS) else ("show_notes", {})
    if has_any(cmd, ["what did we talk about", "last conversation", "previous conversation", "chat history",
                     "humne kya baat", "hamne kya baat", "pichli baat", "pehle kya baat"]):
        return "history", {}
    if has_any(cmd, ["memory"]) and has_any(cmd, CLEAR_WORDS):
        return "clear_memory", {}

    if has_any(cmd, ["tell me about yourself", "introduce yourself", "who are you", "what are you",
                     "apne bare mein", "apne baare mein", "apna parichay", "tum kaun ho", "aap kaun ho",
                     "kaun ho tum", "kaun ho aap"]):
        return "introduce", {}

    if has_any(cmd, ["screenshot", "screen shot", "screen capture", "capture screen", "capture the screen"]):
        return "screenshot", {}
    if has_any(cmd, ["photo", "picture", "selfie", "pic"]) and (
        has_any(cmd, ["take", "click", "capture", "nikalo", "nikal", "khicho", "kheencho", "le lo", "lo", "lena", "kar"])
        or "selfie" in toks
    ):
        return "take_photo", {}

    # folders
    if has_any(cmd, ["folder"]) and has_any(cmd, CREATE_WORDS):
        name = ""
        m = re.search(r"(?:named|called)\s+(.+)$", cmd)
        if m:
            name = m.group(1)
        else:
            m = re.search(r"(.+?)\s+(?:naam|name)\s+(?:ka|ki|se)\s+folder", cmd)
            if m:
                name = strip_words(m.group(1), CREATE_WORDS + ["a", "the", "ek", "folder"])
        return "create_folder", {"name": strip_words(name, ["folder", "on desktop", "desktop"]) if name else ""}
    if has_any(cmd, ["folder"]) and has_any(cmd, OPEN_WORDS + ["show", "dikhao", "dikha do", "find", "dhundo"]):
        name = strip_words(cmd, OPEN_WORDS + ["show", "dikhao", "dikha do", "find", "dhundo", "folder", "the", "my", "a",
                                              "ka", "ki", "ko", "me", "mein", "wala", "mera", "meri", "mujhe"])
        return "open_folder", {"name": name}

    # search
    if has_any(cmd, SEARCH_WORDS):
        platform = "youtube" if app_found == "youtube" else "google"
        query = strip_words(cmd, SEARCH_WORDS + ["youtube", "you tube", "google", "on", "in", "for", "at", "about",
                                                 "par", "pe", "per", "mein", "me", "se", "ko", "ka", "ki", "karo",
                                                 "kar", "do", "de", "kardo", "the", "a"])
        return "search", {"platform": platform, "query": query}

    # play song
    if has_any(cmd, PLAY_WORDS) or (has_any(cmd, SONG_WORDS) and has_any(cmd, OPEN_WORDS)):
        song = strip_words(cmd, PLAY_WORDS + OPEN_WORDS + SONG_WORDS + [
            "video", "youtube", "you tube", "on", "pe", "par", "per", "mujhe", "ek", "the", "a", "for", "me", "mein",
            "ka", "ki", "ko", "do", "de", "karo", "kar", "hai", "chahiye", "suna", "baja", "laga", "chala"])
        return "play_song", {"song": song}

    # open app
    if app_found and (has_any(cmd, OPEN_WORDS) or cmd in [a for al in APP_ALIASES.values() for a in al]):
        return "open_app", {"app": app_found}

    return None, {}


# ==================== INTENT EXECUTION ==================== #
def ask_followup(question, timeout=8, phrase_time=8):
    speak(question)
    return listen_for_command(timeout=timeout, phrase_time=phrase_time)


def execute_intent(intent, args, original_command):
    reply = ""

    # Windows Applications
    if intent == "open_app":
        app_target = args.get("app", "")
        ok, reply, key = launch_application(app_target)
        context.update_action("open_app", {"app": key or app_target}, reply)
        speak(reply)

    elif intent == "close_app":
        app_target = args.get("app", "")
        ok, reply = close_application(app_target)
        context.update_action("close_app", {"app": app_target}, reply)
        speak(reply)

    # Browser & Web
    elif intent == "open_site":
        site_target = args.get("site", "")
        ok, reply, key = open_website(site_target)
        context.update_action("open_site", {"site": key or site_target}, reply)
        speak(reply)

    elif intent == "search":
        platform = str(args.get("platform", "google")).lower()
        query = str(args.get("query", "")).strip() or ask_followup("What should I search for?", 8, 10)
        if query:
            ok, reply = search_web(query, platform)
            context.update_action("search", {"query": query, "platform": platform}, reply)
            speak(reply)
        else:
            reply = "I did not get the search query."
            speak(reply)

    elif intent == "play_song":
        song = str(args.get("song", "")).strip()
        play_song(song)
        context.update_action("search", {"query": song, "platform": "youtube"}, f"Playing {song}")
        reply = f"Play request processed for {song}"

    # Files & Folders
    elif intent == "open_folder":
        folder_target = str(args.get("folder", "") or args.get("name", "")).strip()
        if not folder_target:
            folder_target = ask_followup("Which folder should I open?")
        if folder_target:
            ok, reply, path = open_folder(folder_target)
            context.update_action("open_folder", {"folder": folder_target}, reply)
            speak(reply)
        else:
            reply = "I did not get the folder name."
            speak(reply)

    elif intent == "list_files":
        folder_target = str(args.get("folder", "downloads")).strip()
        ok, reply, _ = list_files_in_folder(folder_target)
        context.update_action("list_files", {"folder": folder_target}, reply)
        speak(reply)

    elif intent == "create_folder":
        name = str(args.get("name", "")).strip() or ask_followup("What should I name the folder?", 10, 12)
        if name:
            create_folder(name.lower().strip())
            reply = f"Folder creation processed for {name}"
        else:
            reply = "I did not get the folder name"
            speak(reply)

    # System Controls
    elif intent == "volume_up":
        ok, reply = control_volume("up")
        speak(reply)

    elif intent == "volume_down":
        ok, reply = control_volume("down")
        speak(reply)

    elif intent == "volume_set":
        ok, reply = control_volume("set", args.get("value"))
        speak(reply)

    elif intent == "volume_mute":
        ok, reply = control_volume("mute")
        speak(reply)

    elif intent == "volume_unmute":
        ok, reply = control_volume("unmute")
        speak(reply)

    elif intent == "volume":
        ok, reply = control_volume(args.get("mode", "up"), args.get("value"))
        speak(reply)

    elif intent == "brightness_up":
        ok, reply = adjust_brightness("up")
        speak(reply)

    elif intent == "brightness_down":
        ok, reply = adjust_brightness("down")
        speak(reply)

    elif intent == "brightness_set":
        ok, reply = adjust_brightness("set", args.get("value"))
        speak(reply)

    elif intent == "battery":
        reply = get_battery_info()
        speak(reply)

    elif intent == "performance":
        reply = get_performance_info()
        speak(reply)

    elif intent == "system_info":
        reply = get_system_summary()
        speak(reply)

    elif intent == "lock_workstation":
        ok, reply = lock_workstation()
        speak(reply)

    elif intent == "task_manager":
        ok, reply, _ = launch_application("taskmgr")
        speak(reply)

    elif intent == "settings":
        ok, reply, _ = launch_application("settings")
        speak(reply)

    # Sensitive System Operations (Requiring Confirmation)
    elif intent == "shutdown_request":
        context.set_confirmation("shutdown", {}, "Sir, are you sure you want to shut down your PC?")
        reply = "Sir, you have requested to shut down your computer. Are you sure you want to proceed? Please say yes or no."
        speak(reply)

    elif intent == "restart_request":
        context.set_confirmation("restart", {}, "Sir, are you sure you want to restart your PC?")
        reply = "Sir, you have requested to restart your computer. Are you sure you want to proceed? Please say yes or no."
        speak(reply)

    elif intent == "confirm_action":
        if args.get("proceed"):
            action = context.pending_confirmation.get("type") if context.pending_confirmation else None
            context.clear_confirmation()
            if action == "shutdown":
                ok, reply = execute_shutdown(restart=False)
                speak(reply)
            elif action == "restart":
                ok, reply = execute_shutdown(restart=True)
                speak(reply)
            else:
                reply = "Confirmed, action executed Sir."
                speak(reply)
        else:
            context.clear_confirmation()
            reply = "Operation cancelled Sir."
            speak(reply)

    # Screenshots & Media
    elif intent == "screenshot":
        ok, reply, path = capture_screenshot(SCREENSHOTS_DIR)
        speak(reply)

    elif intent == "take_photo":
        path = take_photo()
        reply = f"Photo captured and saved at {path}" if path else "Photo capture failed"
        speak(reply)

    # Holographic Interface
    elif intent == "interface":
        if str(args.get("action", "open")).lower() == "close":
            reply = "Interface closed" if close_interface() else "The interface is not running"
            speak(reply)
        elif interface_running():
            reply = "The interface is already running"
            speak(reply)
        else:
            reply = "Activating interface"
            speak(reply)
            open_interface()

    # Personal Memory & Notes
    elif intent == "set_name":
        name = str(args.get("name", "")).strip().title()
        if name:
            memory = load_memory()
            memory["name"] = name
            save_memory(memory)
            reply = f"Okay Sir, I will remember that your name is {name}"
        else:
            reply = "Please tell me your name properly"
        speak(reply)

    elif intent == "get_name":
        name = load_memory().get("name", "").strip()
        reply = f"Your name is {name}" if name else "I do not know your name yet"
        speak(reply)

    elif intent == "add_note":
        note = str(args.get("note", "")).strip()
        if note:
            memory = load_memory()
            memory["notes"].append(note)
            save_memory(memory)
            reply = "Okay Sir, I saved that in memory"
        else:
            reply = "Please say something to remember"
        speak(reply)

    elif intent == "show_notes":
        notes = load_memory().get("notes", [])
        if notes:
            speak("Your saved notes are")
            for i, note in enumerate(notes, start=1):
                speak(f"Note {i}: {note}")
            reply = "Notes read"
        else:
            reply = "You do not have any saved notes"
            speak(reply)

    elif intent == "clear_notes":
        memory = load_memory()
        memory["notes"] = []
        save_memory(memory)
        reply = "All your notes have been cleared"
        speak(reply)

    elif intent == "history":
        conversations = load_memory().get("last_conversation", [])
        if conversations:
            speak("Here are your last conversations. Check the terminal.")
            for item in conversations:
                print("-" * 50)
                print("Time:", item.get("time", "Unknown"))
                print("You:", item.get("user", ""))
                print("Vision:", item.get("vision", ""))
            reply = "Conversations shown"
        else:
            reply = "No previous conversation found"
            speak(reply)

    elif intent == "clear_memory":
        save_memory({"name": "", "notes": [], "last_conversation": []})
        reply = "Memory cleared successfully"
        speak(reply)

    elif intent == "introduce":
        introduce_yourself()
        reply = "Introduction completed"

    # Window Management
    elif intent in ("window_minimize", "window_maximize", "window_restore"):
        action = intent.replace("window_", "")
        ok, reply = control_window(action)
        speak(reply)

    # Time & Date
    elif intent == "get_time":
        reply = f"The time is {datetime.now().strftime('%I:%M %p')} Sir."
        speak(reply)

    elif intent == "get_date":
        reply = f"Today is {datetime.now().strftime('%A, %B %d, %Y')} Sir."
        speak(reply)

    # Reminders
    elif intent == "add_reminder":
        task = args.get("task", "")
        delay = args.get("delay", 60.0)
        ok, reply = add_reminder(task, delay)
        speak(reply)

    elif intent == "list_reminders":
        ok, reply, _ = list_reminders()
        speak(reply)

    elif intent == "cancel_reminders":
        ok, reply = cancel_all_reminders()
        speak(reply)

    # Startup Management
    elif intent == "startup_enable":
        ok, reply = enable_startup()
        speak(reply)

    elif intent == "startup_disable":
        ok, reply = disable_startup()
        speak(reply)

    elif intent == "startup_status":
        reply = get_startup_status()
        speak(reply)

    # Speech Control & Barge-in
    elif intent == "tts_stop":
        trigger_barge_in()
        set_vision_state("interrupted")
        time.sleep(0.15)
        set_vision_state("listening")
        return ""

    elif intent == "tts_repeat":
        last = context.last_spoken_reply
        if last:
            speak(f"I said: {last}")
        else:
            speak("I haven't said anything yet Sir.")

    elif intent == "tts_slower":
        VOICE_RATE = max(100, VOICE_RATE - 20)
        EDGE_RATE = "-22%"
        reply = "I will speak slower from now on Sir."
        speak(reply)

    elif intent == "tts_faster":
        VOICE_RATE = min(220, VOICE_RATE + 20)
        EDGE_RATE = "+0%"
        reply = "I will speak faster from now on Sir."
        speak(reply)

    elif intent == "tts_disable_speech":
        context.spoken_responses_enabled = False
        reply = "Silent mode enabled. Spoken voice responses are now muted."
        print("vision:", reply)
        set_vision_state("executing", result=reply)

    elif intent == "tts_enable_speech":
        context.spoken_responses_enabled = True
        reply = "Voice responses have been re-enabled Sir."
        speak(reply)

    elif intent == "set_sensitivity":
        lvl = args.get("level", "medium")
        CONFIG["clap_sensitivity"] = lvl
        reply = f"Clap detection sensitivity adjusted to {lvl} Sir."
        speak(reply)

    elif intent == "sleep":
        reply = "Understood Sir. Going to sleep. Say Hey Vision to wake me up."
        speak(reply)
        exit_active_mode()

    elif intent == "stop":
        reply = "Shutting down. Goodbye Sir"
        speak(reply)
        save_conversation(original_command, reply)
        raise SystemExit

    return reply


def process_command(command):
    original = command.strip()
    if not original:
        return
    try:
        set_vision_state("processing", text=original)

        # Fast Deterministic & Contextual Pattern Matching
        intent, args = match_deterministic_intent(original, context)

        # Default fallback to conversational AI (Chatbot Mode)
        if intent is None or intent == "chat":
            intent, args = "chat", {}

        print(f"[Routed Intent] {intent} -> {args}")

        if intent == "chat":
            was_interrupted, reply = stream_conversational_response(original)
        else:
            reply = execute_intent(intent, args, original)
            if reply and not tts_manager.cancel_event.is_set():
                set_vision_state("executing", text=original, result=str(reply or ""))
                context.add_turn(original, reply or "", intent)
                save_conversation(original, reply or "")

    except SystemExit:
        raise
    except Exception as e:
        print("Command execution error:", e)
        set_vision_state("error", text=original, result=str(e))
        speak("I encountered an error processing that command Sir.")


# ==================== CONTINUOUS CLAP & ACTIVATION ENGINE ==================== #
clap_detector: Optional[ClapDetector] = None
activation_trigger_event = threading.Event()


def on_double_clap_detected():
    """Fired immediately when a valid double-clap pattern is recognized."""
    print("\n[Clap Detector] DOUBLE CLAP DETECTED! Activating Vision...")
    set_vision_state("clap_detected")
    play_activation_chime()
    activation_trigger_event.set()


def keyboard_activation_listener():
    """Non-blocking keyboard activation listener: Press ENTER, SPACE, or any key to wake VISION immediately."""
    try:
        if sys.platform.startswith("win"):
            import msvcrt
            while True:
                if not conversation_mode and msvcrt.kbhit():
                    ch = msvcrt.getch()
                    print("\n[Manual Activation] Keyboard key detected! Activating Vision...")
                    on_double_clap_detected()
                time.sleep(0.04)
        else:
            import select
            while True:
                if not conversation_mode and sys.stdin in select.select([sys.stdin], [], [], 0.1)[0]:
                    sys.stdin.readline()
                    print("\n[Manual Activation] Keyboard key detected! Activating Vision...")
                    on_double_clap_detected()
                time.sleep(0.04)
    except Exception:
        pass


def is_wake_phrase(text):
    t = re.sub(r"\s+", " ", re.sub(r"[^a-z ]", " ", text.lower())).strip()
    return any(p in t for p in WAKE_PHRASES) or t in ("vision", "hey vision")


def start_vision():
    global clap_detector

    calibrate_microphone_once(force=True)

    # Initialize and start continuous background ClapDetector
    clap_detector = ClapDetector(
        device_index=CONFIG.get("microphone_device_index"),
        sensitivity=CONFIG.get("clap_sensitivity", "medium"),
        diagnostic_mode=CONFIG.get("debug_audio_meter", False),
        on_double_clap=on_double_clap_detected
    )
    clap_detector.start()

    # Start non-blocking keyboard listener thread
    threading.Thread(target=keyboard_activation_listener, daemon=True).start()

    first_boot = True
    print("\n" + "=" * 60)
    print(">> VISION AI ACTIVE IN BACKGROUND // DOUBLE CLAP TO ACTIVATE <<")
    print("   (Or press ENTER/SPACE to wake instantly)")
    print("=" * 60 + "\n")

    while True:
        try:
            set_vision_state("monitoring")
            if clap_detector:
                clap_detector.resume()

            # Wait for double-clap or keyboard activation
            while True:
                if activation_trigger_event.wait(timeout=0.3):
                    activation_trigger_event.clear()
                    break

            # Transition from Standby to Active Listening
            if clap_detector:
                clap_detector.pause()

            set_vision_state("activating")
            time.sleep(0.2)
            open_interface()

            if first_boot:
                speak(f"{time_greeting()} Sir. Vision online. All systems running at optimal performance. What is the plan?")
                first_boot = False
            else:
                speak("Yes Sir. I am listening.")

            enter_active_mode()
            run_active_listening_loop()

        except SystemExit:
            break
        except Exception as e:
            print("Main loop recovery warning:", e)
            reset_audio_pipeline(f"main loop recovery: {e}")
            time.sleep(0.5)


def main():
    # 1. Enforce single-instance execution
    if not acquire_instance_lock():
        print("[VISION AI] Another instance is already running in the background. Exiting cleanly.")
        return

    try:
        # 2. Start background voice reminders scheduler
        start_reminder_scheduler(notify_callback=speak)

        # 3. Enter always-active main engine
        start_vision()
    except (SystemExit, KeyboardInterrupt):
        pass
    finally:
        if clap_detector:
            clap_detector.stop()
        release_instance_lock()
        shutdown_app()


if __name__ == "__main__":
    main()
