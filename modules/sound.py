"""
VISION AI - Audio Cues and System Chimes
Generates and plays crisp sci-fi activation and notification sounds.
Works out of the box using Windows winsound or pygame without external media files.
"""

import sys
import threading


def play_activation_chime():
    """Plays an instant futuristic upward dual-tone chime on activation."""
    def _play():
        if sys.platform.startswith("win"):
            try:
                import winsound
                # Upward futuristic chime: 784 Hz (G5) -> 1046 Hz (C6)
                winsound.Beep(784, 100)
                winsound.Beep(1046, 160)
                return
            except Exception:
                pass

    threading.Thread(target=_play, daemon=True).start()


def play_interrupt_cue():
    """Plays a short subtle acknowledgment blip when speech is interrupted."""
    def _play():
        if sys.platform.startswith("win"):
            try:
                import winsound
                winsound.Beep(440, 80)
                return
            except Exception:
                pass

    threading.Thread(target=_play, daemon=True).start()
