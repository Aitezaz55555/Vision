"""
VISION AI - High-Performance Continuous Double-Clap Detection Engine
Provides low-latency, adaptive transient peak impulse detection using continuous
audio streaming with Exponential Moving Average (EMA) ambient floor tracking.
"""

import math
import os
import struct
import sys
import threading
import time
from typing import Optional, Callable, Dict, Any, Tuple
import pyaudio


class ClapDetector:
    """
    Continuous background double-clap detector with adaptive ambient tracking,
    crest factor impulse verification, and instant activation trigger.
    """

    def __init__(
        self,
        device_index: Optional[int] = None,
        min_interval: float = 0.10,
        max_interval: float = 0.85,
        debounce: float = 0.08,
        sensitivity: str = "medium",
        diagnostic_mode: bool = False,
        on_double_clap: Optional[Callable[[], None]] = None,
        on_single_clap: Optional[Callable[[float], None]] = None,
    ):
        self.device_index = device_index
        self.min_interval = min_interval
        self.max_interval = max_interval
        self.debounce = debounce
        self.sensitivity = sensitivity.lower()
        self.diagnostic_mode = diagnostic_mode
        self.on_double_clap = on_double_clap
        self.on_single_clap = on_single_clap

        # Audio stream parameters
        self.format = pyaudio.paInt16
        self.channels = 1
        self.rate = 44100
        self.chunk = 1024  # ~23ms window

        # State flags
        self._running = False
        self._paused = False
        self._thread: Optional[threading.Thread] = None
        self._pa: Optional[pyaudio.PyAudio] = None
        self._stream: Optional[pyaudio.Stream] = None

        # Telemetry / metrics
        self.ambient_rms = 15.0
        self.ambient_peak = 120.0
        self.last_clap_time = 0.0
        self.first_clap_time = 0.0
        self.clap_count = 0
        self.last_interval = 0.0
        self.measured_latencies = []

        # Sensitivity multipliers
        mults = {"high": (2.6, 2.8), "low": (4.2, 4.5), "medium": (3.2, 3.5)}
        self.rms_mult, self.peak_mult = mults.get(self.sensitivity, (3.2, 3.5))

    @staticmethod
    def calculate_metrics(raw_pcm: bytes) -> Tuple[float, int, float]:
        """Calculates RMS, Peak amplitude, and Crest factor (Peak / RMS)."""
        count = len(raw_pcm) // 2
        if count == 0:
            return 0.0, 0, 0.0
        shorts = struct.unpack(f"{count}h", raw_pcm)
        peak = max(abs(s) for s in shorts)
        rms = math.sqrt(sum(s * s for s in shorts) / count)
        crest = peak / (rms + 1e-6)
        return rms, peak, crest

    def find_input_device(self) -> Tuple[Optional[int], str]:
        """Resolves configured device index or system default capture device."""
        pa = pyaudio.PyAudio()
        try:
            if self.device_index is not None:
                try:
                    info = pa.get_device_info_by_index(self.device_index)
                    if info.get("maxInputChannels", 0) > 0:
                        name = info.get("name", "Unknown")
                        return self.device_index, name
                except Exception:
                    pass

            try:
                default_info = pa.get_default_input_device_info()
                if default_info.get("maxInputChannels", 0) > 0:
                    return default_info.get("index"), default_info.get("name", "Default Mic")
            except Exception:
                pass

            for i in range(pa.get_device_count()):
                try:
                    info = pa.get_device_info_by_index(i)
                    if info.get("maxInputChannels", 0) > 0:
                        return i, info.get("name", "Fallback Mic")
                except Exception:
                    continue

            return None, "No input device"
        finally:
            pa.terminate()

    def start(self):
        """Starts the continuous background clap detection thread."""
        if self._running:
            return
        self._running = True
        self._paused = False
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()

    def pause(self):
        """Temporarily pauses clap processing (e.g. while SpeechRecognition is active)."""
        self._paused = True

    def resume(self):
        """Resumes background clap monitoring."""
        self.clap_count = 0
        self.first_clap_time = 0.0
        self.last_clap_time = 0.0
        self._paused = False

    def stop(self):
        """Stops the detection thread and releases audio resources."""
        self._running = False
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=1.0)
        self._cleanup_stream()

    def _cleanup_stream(self):
        if self._stream:
            try:
                self._stream.stop_stream()
                self._stream.close()
            except Exception:
                pass
            self._stream = None
        if self._pa:
            try:
                self._pa.terminate()
            except Exception:
                pass
            self._pa = None

    def _run_loop(self):
        """Continuous audio streaming and percussive transient detection loop."""
        dev_idx, dev_name = self.find_input_device()
        if dev_idx is None:
            print("[ClapDetector] Error: No working microphone input device found.")
            self._running = False
            return

        try:
            self._pa = pyaudio.PyAudio()
            self._stream = self._pa.open(
                format=self.format,
                channels=self.channels,
                rate=self.rate,
                input=True,
                input_device_index=dev_idx,
                frames_per_buffer=self.chunk,
            )
        except Exception as e:
            print(f"[ClapDetector] Audio stream initialization error on {dev_name}: {e}")
            self._cleanup_stream()
            self._running = False
            return

        # Initial baseline calibration over 15 frames (~350ms)
        warmup_rms, warmup_peaks = [], []
        for _ in range(15):
            try:
                data = self._stream.read(self.chunk, exception_on_overflow=False)
                r, p, _ = self.calculate_metrics(data)
                warmup_rms.append(r)
                warmup_peaks.append(p)
            except Exception:
                pass

        if warmup_rms:
            self.ambient_rms = sum(warmup_rms) / len(warmup_rms)
            self.ambient_peak = sum(warmup_peaks) / len(warmup_peaks)

        if self.diagnostic_mode:
            print(f"\n[ClapDetector Diagnostic Active] Device: [{dev_idx}] {dev_name}")
            print(f"  Ambient Floor: RMS={self.ambient_rms:.1f}, Peak={self.ambient_peak:.0f}")

        last_diag_print = time.time()

        while self._running:
            if self._paused:
                time.sleep(0.04)
                continue

            try:
                data = self._stream.read(self.chunk, exception_on_overflow=False)
            except Exception:
                time.sleep(0.01)
                continue

            rms, peak, crest = self.calculate_metrics(data)
            now = time.time()

            # Dynamic adaptive thresholds with sane safety bounds
            target_rms = max(24.0, self.ambient_rms * self.rms_mult)
            target_peak = max(180, int(self.ambient_peak * self.peak_mult))

            # Exponential Moving Average for ambient noise floor (only when no impulse)
            is_impulse = (rms > target_rms) and (peak > target_peak) and (crest >= 2.2)

            if not is_impulse:
                self.ambient_rms = 0.96 * self.ambient_rms + 0.04 * rms
                self.ambient_peak = 0.96 * self.ambient_peak + 0.04 * peak

            # Diagnostic telemetry output
            if self.diagnostic_mode and (now - last_diag_print >= 2.0):
                print(f"[Clap Diag] RMS: {rms:5.1f} (Floor:{self.ambient_rms:4.1f}|Target>{target_rms:4.1f}) "
                      f"Peak: {peak:5d} (Target>{target_peak:4d}) Crest: {crest:4.1f} Claps: {self.clap_count}")
                last_diag_print = now

            if is_impulse:
                # Debounce: ignore ringing / reflections within 80ms of same clap
                if now - self.last_clap_time < self.debounce:
                    continue

                self.last_clap_time = now

                if self.clap_count == 0:
                    self.clap_count = 1
                    self.first_clap_time = now
                    if self.diagnostic_mode:
                        print(f"  -> [Clap 1/2] Peak: {peak} | RMS: {rms:.1f} | Crest: {crest:.1f} -> Awaiting 2nd clap...")
                    if self.on_single_clap:
                        try:
                            self.on_single_clap(now)
                        except Exception:
                            pass
                else:
                    interval = now - self.first_clap_time
                    if interval < self.min_interval:
                        # Too close (echo / reverb)
                        continue

                    if interval <= self.max_interval:
                        self.last_interval = interval
                        activation_start = time.perf_counter()
                        if self.diagnostic_mode:
                            print(f"\n  *** [DOUBLE CLAP CONFIRMED!] Interval: {interval * 1000:.1f}ms! ***")

                        self.clap_count = 0
                        self.first_clap_time = 0.0

                        # Fire double clap callback immediately
                        if self.on_double_clap:
                            try:
                                self.on_double_clap()
                                latency_ms = (time.perf_counter() - activation_start) * 1000
                                self.measured_latencies.append(latency_ms)
                                if self.diagnostic_mode:
                                    print(f"  -> Activation callback executed in {latency_ms:.2f}ms\n")
                            except Exception as e:
                                print(f"[ClapDetector] Callback error: {e}")

                        # Short cooldown after successful activation
                        time.sleep(0.12)
                    else:
                        # Previous clap expired, this is new first clap
                        self.clap_count = 1
                        self.first_clap_time = now
                        if self.diagnostic_mode:
                            print(f"  -> [Clap 1/2 (prior expired)] Peak: {peak} -> Awaiting 2nd clap...")

            elif self.clap_count == 1 and (now - self.first_clap_time > self.max_interval):
                self.clap_count = 0
                if self.diagnostic_mode:
                    print("  [Clap Timeout] Second clap did not arrive within interval window.")

        self._cleanup_stream()
