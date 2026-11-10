"""
VISION AI - Streaming Text-to-Speech & Instant Barge-In Engine
Handles low-latency sentence-level speech synthesis, concurrent audio playback,
instant stop-speaking interruption (barge-in via voice keyword or keyboard key),
and visual state synchronization.
"""

import asyncio
import os
import queue
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import time
from typing import Optional, Callable, Generator, List, Tuple, Any

try:
    import pygame
    HAS_PYGAME = True
except Exception:
    HAS_PYGAME = False

try:
    import edge_tts
    HAS_EDGE = True
except Exception:
    HAS_EDGE = False

try:
    import speech_recognition as sr
    HAS_SR = True
except Exception:
    HAS_SR = False

from modules.sound import play_interrupt_cue


# Common abbreviations that should NOT trigger a sentence split
ABBREVIATIONS = {
    "mr.", "mrs.", "ms.", "dr.", "prof.", "sr.", "jr.", "vs.",
    "e.g.", "i.e.", "etc.", "approx.", "dept.", "est.", "fig.",
    "inc.", "ltd.", "co.", "jan.", "feb.", "mar.", "apr.", "jun.",
    "jul.", "aug.", "sep.", "sept.", "oct.", "nov.", "dec."
}

# Barge-in keywords that immediately halt assistant speech
BARGE_IN_KEYWORDS = {
    "stop", "be quiet", "stop speaking", "stop talking", "cancel", "enough", "pause",
    "quiet", "shut up", "shutup", "that's enough", "thats enough",
    "stop it", "stop now", "listen", "continue", "ruk jao", "ruko",
    "chup", "chup raho", "chup ho jao", "bas karo", "bas",
    "halt", "silence", "shh", "shhh", "stopp", "top", "hold on", "wait", "exit", "quit"
}


def clean_text_for_speech(text: str) -> str:
    """
    Cleans raw LLM markdown output into natural, readable prose for text-to-speech.
    Removes asterisks, backticks, bullet characters, headers, and noisy formatting.
    """
    if not text:
        return ""
    t = str(text)
    # Remove code blocks entirely
    t = re.sub(r"```[\s\S]*?```", " ", t)
    # Remove inline code formatting backticks
    t = re.sub(r"`([^`]+)`", r"\1", t)
    # Remove bold / italic markdown markers (***text***, **text**, *text*, ___text___, __text__)
    t = re.sub(r"\*{1,3}([^*]+)\*{1,3}", r"\1", t)
    t = re.sub(r"_{1,3}([^_]+)_{1,3}", r"\1", t)
    # Remove markdown header hashes (# Header -> Header)
    t = re.sub(r"^\s*#{1,6}\s*", "", t, flags=re.MULTILINE)
    # Remove bullet markers (- item, * item, + item)
    t = re.sub(r"^\s*[-*+]\s+", "", t, flags=re.MULTILINE)
    # Remove numbered list prefixes (1. item -> item)
    t = re.sub(r"^\s*\d+\.\s+", "", t, flags=re.MULTILINE)
    # Convert web links to simple spoken form
    t = re.sub(r"https?://\S+", "link", t)
    # Normalize excessive dashes, underscores, and spacing
    t = re.sub(r"[-_=]{3,}", " ", t)
    t = re.sub(r"\s+", " ", t).strip()
    return t


def split_stream_into_sentences(token_generator: Generator[str, None, None],
                                cancel_event: threading.Event) -> Generator[str, None, None]:
    """
    Consumes tokens from an LLM stream and yields complete, natural sentences as soon as they form.
    Avoids splitting on common abbreviations and decimals.
    """
    buffer = ""
    search_pos = 0

    for token in token_generator:
        if cancel_event.is_set():
            break
        buffer += token

        # Process complete sentences in buffer
        while True:
            # Look for sentence delimiters: . ! ? followed by space, newline, or end
            match = re.search(r"([.!?])(?:\s+|\n+|$)", buffer[search_pos:])
            if not match:
                break

            punct_idx = search_pos + match.start(1)
            end_pos = search_pos + match.end()
            candidate = buffer[:punct_idx + 1].strip()

            # Check if this ending punctuation is part of an abbreviation (e.g., "Dr.")
            words = candidate.split()
            last_word = words[-1].lower() if words else ""
            if last_word in ABBREVIATIONS:
                # Part of abbreviation; skip past this punctuation and continue searching
                search_pos = end_pos
                continue

            # Check for decimals (e.g. 3.14)
            if match.group(1) == "." and punct_idx > 0 and punct_idx < len(buffer) - 1:
                if buffer[punct_idx - 1].isdigit() and buffer[punct_idx + 1].isdigit():
                    search_pos = end_pos
                    continue

            cleaned = clean_text_for_speech(candidate)
            if cleaned and len(cleaned) > 2:
                yield cleaned

            # Advance buffer past the matched sentence and reset search_pos
            buffer = buffer[end_pos:]
            search_pos = 0

    # Yield remaining text in buffer after stream ends
    remaining = clean_text_for_speech(buffer)
    if remaining and not cancel_event.is_set():
        yield remaining


class StreamingTTSManager:
    """
    Manages low-latency sentence-level speech synthesis, asynchronous playback,
    and instantaneous stop-speaking interruption (barge-in).
    """

    def __init__(self,
                 voice: str = "en-US-ChristopherNeural",
                 rate: str = "-12%",
                 pitch: str = "-18Hz",
                 volume: str = "+35%",
                 state_callback: Optional[Callable[[str, str, str], None]] = None,
                 microphone_factory: Optional[Callable[[], Any]] = None,
                 recognizer_factory: Optional[Callable[[], Any]] = None):
        self.voice = voice
        self.rate = rate
        self.pitch = pitch
        self.volume = volume
        self.state_callback = state_callback
        self.microphone_factory = microphone_factory
        self.recognizer_factory = recognizer_factory

        # Threading state & coordination events
        self.cancel_event = threading.Event()
        self.is_playing = threading.Event()
        self.audio_lock = threading.Lock()
        self.temp_files_lock = threading.Lock()
        self.active_temp_files: List[str] = []

        self._ensure_pygame_initialized()

    def _ensure_pygame_initialized(self):
        """Initializes pygame audio mixer if available."""
        if HAS_PYGAME:
            try:
                if not pygame.mixer.get_init():
                    pygame.mixer.init(frequency=44100, size=-16, channels=2, buffer=2048)
            except Exception as e:
                print(f"[StreamingTTS] Pygame mixer init warning: {e}")

    def update_config(self, voice: Optional[str] = None, rate: Optional[str] = None,
                      pitch: Optional[str] = None, volume: Optional[str] = None):
        """Update voice configuration parameters dynamically."""
        if voice: self.voice = voice
        if rate: self.rate = rate
        if pitch: self.pitch = pitch
        if volume: self.volume = volume

    def _set_state(self, state: str, text: str = "", result: str = ""):
        """Invokes external visual state callback if registered."""
        if self.state_callback:
            try:
                self.state_callback(state, text, result)
            except Exception:
                pass

    def _create_temp_audio_file(self, suffix: str = ".mp3") -> str:
        """Creates and tracks a temporary audio file for synthesis."""
        f = tempfile.NamedTemporaryFile(suffix=suffix, delete=False)
        f.close()
        path = f.name
        with self.temp_files_lock:
            self.active_temp_files.append(path)
        return path

    def _cleanup_temp_file(self, path: Optional[str]):
        """Safely removes an audio temporary file."""
        if not path:
            return
        with self.temp_files_lock:
            if path in self.active_temp_files:
                self.active_temp_files.remove(path)
        try:
            if os.path.exists(path):
                os.remove(path)
        except Exception:
            pass

    def _cleanup_all_temp_files(self):
        """Removes all tracked temporary audio files."""
        with self.temp_files_lock:
            paths = list(self.active_temp_files)
            self.active_temp_files.clear()
        for p in paths:
            try:
                if os.path.exists(p):
                    os.remove(p)
            except Exception:
                pass

    async def _synthesize_edge_async(self, text: str, output_path: str):
        """Generates neural speech audio using Microsoft Edge-TTS."""
        comm = edge_tts.Communicate(
            text=text,
            voice=self.voice,
            rate=self.rate,
            pitch=self.pitch,
            volume=self.volume
        )
        await comm.save(output_path)

    def _synthesize_sentence(self, text: str) -> Optional[str]:
        """
        Synthesizes a sentence into a temporary audio file.
        Returns file path or None if synthesis fails or was cancelled.
        """
        if self.cancel_event.is_set():
            return None

        out_path = self._create_temp_audio_file(".mp3")
        success = False

        if HAS_EDGE:
            try:
                asyncio.run(self._synthesize_edge_async(text, out_path))
                if os.path.exists(out_path) and os.path.getsize(out_path) > 500:
                    success = True
            except Exception as e:
                pass

        if not success:
            self._cleanup_temp_file(out_path)
            return None

        return out_path

    def interrupt(self, reason: str = "user"):
        """
        Instantly halts speech playback, clears pending queues, signals generator cancellation,
        and triggers sci-fi interrupt sound.
        """
        if self.cancel_event.is_set():
            return

        print(f"\n[Barge-In] Speech playback interrupted immediately ({reason})!")
        self.cancel_event.set()
        self.is_playing.clear()

        # Immediately halt Pygame audio playback
        if HAS_PYGAME:
            try:
                if pygame.mixer.get_init():
                    pygame.mixer.music.stop()
            except Exception:
                pass

        # Play short audio feedback cue
        play_interrupt_cue()

        # Update visual HUD state to interrupted
        self._set_state("interrupted")

        # Cleanup all temporary audio files
        self._cleanup_all_temp_files()

    def _keyboard_monitor(self):
        """Global non-blocking keyboard listener thread for ESC, SPACE, 'S', 'Q', ENTER."""
        if not sys.platform.startswith("win"):
            return
        try:
            import msvcrt
            import ctypes
            user32 = ctypes.windll.user32
            # VK_ESCAPE (0x1B), VK_SPACE (0x20), 'S' (0x53), 'Q' (0x51)
            VK_STOP_KEYS = (0x1B, 0x20, 0x53, 0x51)

            while self.is_playing.is_set() and not self.cancel_event.is_set():
                # Global Windows keyboard state (works across all windows/apps)
                for vk in VK_STOP_KEYS:
                    if user32.GetAsyncKeyState(vk) & 0x8000:
                        self.interrupt(reason=f"global key press (0x{vk:02X})")
                        return

                if msvcrt.kbhit():
                    ch = msvcrt.getch()
                    if ch in (b'\x1b', b' ', b's', b'S', b'\r', b'q', b'Q'):
                        self.interrupt(reason="console key press")
                        return

                time.sleep(0.02)
        except Exception:
            pass

    def _voice_monitor(self):
        """Background listener thread monitoring for spoken barge-in keywords during speech."""
        if not HAS_SR or not self.microphone_factory or not self.recognizer_factory:
            return
        try:
            recognizer = self.recognizer_factory()
            recognizer.pause_threshold = 0.3
            recognizer.phrase_threshold = 0.15
            recognizer.non_speaking_duration = 0.2
            recognizer.dynamic_energy_threshold = False

            # Duck pygame mixer volume slightly so mic can hear user voice over speakers
            if HAS_PYGAME and pygame.mixer.get_init():
                try:
                    pygame.mixer.music.set_volume(0.8)
                except Exception:
                    pass

            with self.microphone_factory() as source:
                # Fast calibration of ambient noise
                try:
                    recognizer.adjust_for_ambient_noise(source, duration=0.25)
                    recognizer.energy_threshold = max(40, min(160, recognizer.energy_threshold * 1.25))
                except Exception:
                    recognizer.energy_threshold = 55

                while self.is_playing.is_set() and not self.cancel_event.is_set():
                    try:
                        audio = recognizer.listen(source, timeout=0.6, phrase_time_limit=1.5)
                        if self.cancel_event.is_set():
                            return

                        # Dual-pass recognition for barge-in: primary en-IN, fallback en-US
                        heard = ""
                        try:
                            heard = recognizer.recognize_google(audio, language="en-IN").strip().lower()
                        except Exception:
                            try:
                                heard = recognizer.recognize_google(audio, language="en-US").strip().lower()
                            except Exception:
                                heard = ""

                        if heard:
                            print(f"\n[Barge-In Monitor] Heard during speech: '{heard}'")
                            if any(k in heard for k in BARGE_IN_KEYWORDS):
                                self.interrupt(reason=f"voice keyword '{heard}'")
                                return
                    except sr.WaitTimeoutError:
                        continue
                    except Exception:
                        continue
        except Exception as e:
            print(f"[StreamingTTS] Voice monitor note: {e}")

    def _play_single_file(self, filepath: str) -> bool:
        """
        Plays one audio file via pygame mixer with millisecond-level interrupt checking.
        Returns True if played to completion, False if interrupted.
        """
        if self.cancel_event.is_set():
            return False

        if HAS_PYGAME:
            try:
                if not pygame.mixer.get_init():
                    self._ensure_pygame_initialized()
                pygame.mixer.music.load(filepath)
                pygame.mixer.music.play()

                t_timeout = time.time() + 60.0
                while pygame.mixer.music.get_busy() and time.time() < t_timeout:
                    if self.cancel_event.is_set():
                        pygame.mixer.music.stop()
                        return False
                    time.sleep(0.015)

                return not self.cancel_event.is_set()
            except Exception as e:
                print(f"[StreamingTTS] Pygame playback warning: {e}")

        # Windows PowerShell playback fallback if Pygame fails
        if sys.platform.startswith("win"):
            try:
                abs_path = os.path.abspath(filepath).replace("'", "''")
                cmd = [
                    "powershell", "-NoProfile", "-Command",
                    f"Add-Type -AssemblyName presentationCore; "
                    f"$m = New-Object System.Windows.Media.MediaPlayer; "
                    f"$m.Open([System.Uri]'{abs_path}'); "
                    f"$m.Play(); "
                    f"Start-Sleep -Milliseconds 250; "
                    f"while ($m.NaturalDuration.HasTimeSpan -eq $false -or $m.Position -lt $m.NaturalDuration.TimeSpan) {{ "
                    f"  Start-Sleep -Milliseconds 40 "
                    f"}}"
                ]
                proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                while proc.poll() is None:
                    if self.cancel_event.is_set():
                        proc.terminate()
                        return False
                    time.sleep(0.02)
                return not self.cancel_event.is_set()
            except Exception:
                pass

        return False

    def speak_stream(self, sentence_generator: Generator[str, None, None]) -> Tuple[bool, str]:
        """
        Synthesizes and plays a stream of sentences concurrently.
        Sentence 1 is synthesized and played immediately while Sentence 2 is being prepared.
        Returns: (was_interrupted: bool, full_spoken_text: str)
        """
        self.cancel_event.clear()
        self.is_playing.set()

        # Thread-safe queues
        audio_queue: queue.Queue = queue.Queue(maxsize=4)
        synthesis_done = threading.Event()
        accumulated_sentences: List[str] = []

        # Start barge-in listeners
        threading.Thread(target=self._keyboard_monitor, daemon=True).start()
        threading.Thread(target=self._voice_monitor, daemon=True).start()

        def _synthesizer_worker():
            try:
                for sentence in sentence_generator:
                    if self.cancel_event.is_set():
                        break
                    audio_path = self._synthesize_sentence(sentence)
                    if audio_path and not self.cancel_event.is_set():
                        audio_queue.put((audio_path, sentence))
                    elif audio_path:
                        self._cleanup_temp_file(audio_path)
            finally:
                synthesis_done.set()

        synth_thread = threading.Thread(target=_synthesizer_worker, daemon=True)
        synth_thread.start()

        was_interrupted = False

        try:
            while not self.cancel_event.is_set():
                try:
                    audio_path, sentence = audio_queue.get(timeout=0.08)
                except queue.Empty:
                    if synthesis_done.is_set():
                        break
                    continue

                if self.cancel_event.is_set():
                    self._cleanup_temp_file(audio_path)
                    was_interrupted = True
                    break

                accumulated_sentences.append(sentence)
                print(f"vision: {sentence}")
                self._set_state("speaking", result=sentence)

                ok = self._play_single_file(audio_path)
                self._cleanup_temp_file(audio_path)

                if not ok or self.cancel_event.is_set():
                    was_interrupted = True
                    break

        finally:
            self.is_playing.clear()
            if self.cancel_event.is_set():
                was_interrupted = True

            # Drain and cleanup any remaining items in the audio queue
            while not audio_queue.empty():
                try:
                    p, _ = audio_queue.get_nowait()
                    self._cleanup_temp_file(p)
                except Exception:
                    pass

        full_text = " ".join(accumulated_sentences).strip()
        return was_interrupted, full_text

    def speak_text(self, text: str) -> Tuple[bool, str]:
        """
        Speaks a single text utterance with the exact same interruptible barge-in engine.
        """
        cleaned = clean_text_for_speech(text)
        if not cleaned:
            return False, ""

        def single_sentence_gen():
            yield cleaned

        return self.speak_stream(single_sentence_gen())
