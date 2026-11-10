"""
VISION AI - Advanced Hand Tracking & Gesture Recognition Engine
Provides high-accuracy real-time multi-hand tracking, 21-landmark 3D extraction,
adaptive low-pass jitter smoothing, velocity tracking, and gesture classification
(Open Palm, Fist, Pinch, Two-Fingers, Index Point, Swipe, and Dual-Hand Resonance).
"""

import math
import os
import subprocess
import sys
import threading
import time
import urllib.request
from dataclasses import dataclass, field
from typing import List, Tuple, Dict, Optional, Any

import cv2
import numpy as np

try:
    import mediapipe as mp
    HAS_MP = True
except Exception:
    HAS_MP = False

MODEL_URL = ("https://storage.googleapis.com/mediapipe-models/hand_landmarker/"
             "hand_landmarker/float16/1/hand_landmarker.task")

SCRIPT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MODEL_PATH = os.path.join(SCRIPT_DIR, "hand_landmarker.task")

# 21 Hand Landmark connections for holographic skeleton visualization
HAND_CONNECTIONS = [
    (0, 1), (1, 2), (2, 3), (3, 4),        # Thumb
    (0, 5), (5, 6), (6, 7), (7, 8),        # Index
    (0, 9), (9, 10), (10, 11), (11, 12),   # Middle
    (0, 13), (13, 14), (14, 15), (15, 16), # Ring
    (0, 17), (17, 18), (18, 19), (19, 20), # Pinky
    (5, 9), (9, 13), (13, 17)              # Palm Knuckle Arc
]


def ensure_model_exists() -> str:
    """Ensures hand_landmarker.task is downloaded and valid."""
    if os.path.exists(MODEL_PATH) and os.path.getsize(MODEL_PATH) > 1_000_000:
        return MODEL_PATH

    print("[HandTracking] Downloading MediaPipe hand landmarker model (~7.8 MB)...")
    tmp = MODEL_PATH + ".part"
    curl_cmd = "curl.exe" if sys.platform.startswith("win") else "curl"
    try:
        subprocess.run([curl_cmd, "-L", "-f", "-s", "-o", tmp, MODEL_URL], check=True, timeout=120)
        if os.path.exists(tmp) and os.path.getsize(tmp) > 1_000_000:
            os.replace(tmp, MODEL_PATH)
            return MODEL_PATH
    except Exception as e:
        print(f"[HandTracking] Download error with curl: {e}, falling back to urllib...")
        try:
            urllib.request.urlretrieve(MODEL_URL, tmp)
            if os.path.exists(tmp) and os.path.getsize(tmp) > 1_000_000:
                os.replace(tmp, MODEL_PATH)
                return MODEL_PATH
        except Exception as e2:
            print(f"[HandTracking] Urllib failed: {e2}")

    return MODEL_PATH


def open_camera():
    """Opens webcam using native Windows DSHOW or MSMF backend with retry."""
    backends = [cv2.CAP_DSHOW, cv2.CAP_MSMF, cv2.CAP_ANY] if sys.platform.startswith("win") else [cv2.CAP_ANY]
    for idx in range(4):
        for be in backends:
            try:
                cap = cv2.VideoCapture(idx, be)
                if not cap.isOpened():
                    cap.release()
                    continue
                t_end = time.time() + 3.0
                while time.time() < t_end:
                    ok, frm = cap.read()
                    if ok and frm is not None and frm.size > 0:
                        print(f"[HandTracking] Webcam opened on device index {idx} ({be})")
                        cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
                        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
                        cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
                        return cap
                    time.sleep(0.04)
                cap.release()
            except Exception:
                pass
    return None


class AdaptiveSmoother:
    """
    Adaptive low-pass exponential filter with velocity-sensitive smoothing.
    High smoothing (low alpha) when still to eliminate jitter;
    Snappy response (high alpha) during rapid hand movements.
    """
    def __init__(self, min_alpha: float = 0.22, max_alpha: float = 0.88, vel_scale: float = 8.0):
        self.min_alpha = min_alpha
        self.max_alpha = max_alpha
        self.vel_scale = vel_scale
        self.value: Optional[np.ndarray] = None
        self.prev_time: float = 0.0

    def filter(self, current: np.ndarray, timestamp: float) -> np.ndarray:
        if self.value is None:
            self.value = np.array(current, dtype=np.float32)
            self.prev_time = timestamp
            return self.value

        dt = max(1e-4, timestamp - self.prev_time)
        self.prev_time = timestamp

        velocity = np.linalg.norm(current - self.value) / dt
        norm_vel = min(1.0, velocity / self.vel_scale)
        alpha = self.min_alpha + (self.max_alpha - self.min_alpha) * (norm_vel ** 1.4)

        self.value = alpha * current + (1.0 - alpha) * self.value
        return self.value

    def reset(self):
        self.value = None


@dataclass
class SingleHandInfo:
    landmarks: np.ndarray           # (21, 3) normalized [0..1]
    smoothed_landmarks: np.ndarray  # (21, 3) filtered
    palm_center: Tuple[float, float, float]
    wrist: Tuple[float, float, float]
    hand_size: float
    roll_angle: float               # Radians
    pitch_angle: float              # Radians
    fingers_extended: List[bool]    # [Thumb, Index, Middle, Ring, Pinky]
    finger_spread: float
    is_pinch: bool
    pinch_point: Tuple[float, float, float]
    gesture: str
    handedness: str                 # "Left" or "Right"


@dataclass
class TrackingTelemetry:
    hands_count: int = 0
    hands: List[SingleHandInfo] = field(default_factory=list)
    active_gesture: str = "NONE"
    gesture_event: Optional[str] = None
    drag_dx: float = 0.0
    drag_dy: float = 0.0
    zoom_factor: float = 1.0
    hand_roll: float = 0.0
    hand_depth: float = 1.0
    fingertip_points: List[Tuple[float, float, float]] = field(default_factory=list)
    palm_points: List[Tuple[float, float, float]] = field(default_factory=list)
    status_label: str = "STANDBY"
    confidence: float = 0.0
    preview_frame: Optional[np.ndarray] = None


class HandTracker:
    """
    High-performance asynchronous Hand Tracker utilizing MediaPipe HandLandmarker.
    Operates capture and inference in a dedicated background worker to preserve 60 FPS UI rendering.
    """

    def __init__(self):
        self.running = True
        self.lock = threading.Lock()
        self.cap = None
        self.detector = None
        self.status = "INITIALIZING..."

        # Smoothing filters for up to 2 hands (21 landmarks * 3 coords = 63 dims)
        self.smoothers = [AdaptiveSmoother(min_alpha=0.25, max_alpha=0.90) for _ in range(2)]
        self.prev_palm_pos = [None, None]
        self.prev_pinch_dist = None

        # Gesture state machine & cooldowns
        self.last_gesture = "NONE"
        self.last_event_time = 0.0
        self.swipe_history: List[Tuple[float, float]] = []  # (timestamp, x_pos)

        # Output telemetry snapshot
        self.telemetry = TrackingTelemetry()

        # Start camera & detector
        self.cap = open_camera()
        if self.cap is None:
            self.status = "CAMERA UNAVAILABLE"
            print("[HandTracking] Warning: Camera not detected. Mouse interaction active.")
        else:
            self.status = "LOADING MODEL..."
            threading.Thread(target=self._worker_loop, daemon=True).start()

    def _init_mediapipe(self) -> bool:
        if not HAS_MP:
            self.status = "MEDIAPIPE NOT INSTALLED"
            return False
        try:
            from mediapipe.tasks import python as mp_python
            from mediapipe.tasks.python import vision
            model = ensure_model_exists()
            opts = vision.HandLandmarkerOptions(
                base_options=mp_python.BaseOptions(model_asset_path=model),
                running_mode=vision.RunningMode.VIDEO,
                num_hands=2,
                min_hand_detection_confidence=0.42,
                min_hand_presence_confidence=0.40,
                min_tracking_confidence=0.45
            )
            self.detector = vision.HandLandmarker.create_from_options(opts)
            self._start_time = time.time()
            self._last_timestamp_ms = 0
            self.status = "SHOW HANDS"
            return True
        except Exception as e:
            self.status = "MODEL ERROR"
            print(f"[HandTracking] Error initializing MediaPipe: {e}")
            return False

    def _worker_loop(self):
        if not self._init_mediapipe():
            return

        while self.running and self.cap is not None:
            ok, frame = self.cap.read()
            if not ok or frame is None:
                time.sleep(0.015)
                continue

            # Mirror frame horizontally for natural intuitive interaction
            frame = cv2.flip(frame, 1)
            t_now = time.time()
            ts_ms = max(self._last_timestamp_ms + 1, int((t_now - self._start_time) * 1000))
            self._last_timestamp_ms = ts_ms

            try:
                rgb = np.ascontiguousarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
                mp_img = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
                results = self.detector.detect_for_video(mp_img, ts_ms)
                self._process_detection(frame, results, t_now)
            except Exception as e:
                time.sleep(0.01)

    def _process_detection(self, frame: np.ndarray, results: Any, t_now: float):
        raw_hands = getattr(results, "hand_landmarks", []) or []
        handedness_list = getattr(results, "handedness", []) or []
        fh, fw = frame.shape[:2]

        processed_hands: List[SingleHandInfo] = []
        fingertip_pts: List[Tuple[float, float, float]] = []
        palm_pts: List[Tuple[float, float, float]] = []

        dx, dy = 0.0, 0.0
        zoom_factor = 1.0
        primary_roll = 0.0
        overall_depth = 1.0
        active_gesture = "NONE"
        gesture_event = None

        n_hands = len(raw_hands)

        for i, landmarks in enumerate(raw_hands[:2]):
            coords = np.array([[lm.x, lm.y, lm.z] for lm in landmarks], dtype=np.float32)
            smoothed = self.smoothers[i].filter(coords, t_now)

            # Handedness label
            h_label = "Hand"
            if i < len(handedness_list) and handedness_list[i]:
                h_label = handedness_list[i][0].category_name

            # Palm center: average of Wrist (0), Index MCP (5), Pinky MCP (17)
            p_center = ((smoothed[0] + smoothed[5] + smoothed[17]) / 3.0)
            wrist_pt = smoothed[0]

            # Hand size metric (Wrist to Middle MCP distance)
            hand_size = float(np.linalg.norm(smoothed[9] - smoothed[0]))

            # Hand Roll: angle of vector from wrist to middle MCP in radians
            v_arm = smoothed[9][:2] - smoothed[0][:2]
            roll = float(math.atan2(v_arm[0], -v_arm[1]))  # 0 when upright, -pi..+pi

            # Hand Pitch / Tilt: Z distance between wrist and knuckles
            pitch = float(smoothed[9][2] - smoothed[0][2])

            # Finger extensions
            # Index, Middle, Ring, Pinky: tip distance to wrist vs pip distance to wrist
            ext_index = np.linalg.norm(smoothed[8] - smoothed[0]) > np.linalg.norm(smoothed[6] - smoothed[0]) * 1.10
            ext_middle = np.linalg.norm(smoothed[12] - smoothed[0]) > np.linalg.norm(smoothed[10] - smoothed[0]) * 1.10
            ext_ring = np.linalg.norm(smoothed[16] - smoothed[0]) > np.linalg.norm(smoothed[14] - smoothed[0]) * 1.10
            ext_pinky = np.linalg.norm(smoothed[20] - smoothed[0]) > np.linalg.norm(smoothed[18] - smoothed[0]) * 1.10
            # Thumb: tip distance to pinky MCP vs IP distance to pinky MCP
            ext_thumb = np.linalg.norm(smoothed[4] - smoothed[17]) > np.linalg.norm(smoothed[3] - smoothed[17]) * 1.15

            fingers_ext = [bool(ext_thumb), bool(ext_index), bool(ext_middle), bool(ext_ring), bool(ext_pinky)]

            # Finger spread: average distance between adjacent fingertips
            spread = float((
                np.linalg.norm(smoothed[4] - smoothed[8]) +
                np.linalg.norm(smoothed[8] - smoothed[12]) +
                np.linalg.norm(smoothed[12] - smoothed[16]) +
                np.linalg.norm(smoothed[16] - smoothed[20])
            ) / (4.0 * max(1e-3, hand_size)))

            # Pinch detection (Thumb Tip 4 to Index Tip 8)
            pinch_dist = np.linalg.norm(smoothed[4] - smoothed[8])
            is_pinch = (pinch_dist / max(1e-3, hand_size)) < 0.42
            pinch_mid = tuple(((smoothed[4] + smoothed[8]) / 2.0).tolist())

            # Individual gesture classification
            num_ext = sum(fingers_ext)
            g = "UNKNOWN"
            if is_pinch:
                g = "PINCH"
            elif num_ext == 0 or (num_ext == 1 and ext_thumb and hand_size > 0.05):
                g = "CLOSED_FIST"
            elif num_ext >= 4 and spread > 0.40:
                g = "OPEN_PALM"
            elif ext_index and ext_middle and not ext_ring and not ext_pinky:
                g = "TWO_FINGERS"
            elif ext_index and not ext_middle and not ext_ring and not ext_pinky:
                g = "INDEX_POINT"
            else:
                g = "RELAXED"

            single_info = SingleHandInfo(
                landmarks=coords,
                smoothed_landmarks=smoothed,
                palm_center=(float(p_center[0]), float(p_center[1]), float(p_center[2])),
                wrist=(float(wrist_pt[0]), float(wrist_pt[1]), float(wrist_pt[2])),
                hand_size=hand_size,
                roll_angle=roll,
                pitch_angle=pitch,
                fingers_extended=fingers_ext,
                finger_spread=spread,
                is_pinch=is_pinch,
                pinch_point=(float(pinch_mid[0]), float(pinch_mid[1]), float(pinch_mid[2])),
                gesture=g,
                handedness=h_label
            )
            processed_hands.append(single_info)

            # Collect interaction points
            palm_pts.append((float(p_center[0]), float(p_center[1]), float(p_center[2])))
            for idx_tip in (4, 8, 12, 16, 20):
                if fingers_ext[(idx_tip // 4) - 1] or is_pinch:
                    pt = smoothed[idx_tip]
                    fingertip_pts.append((float(pt[0]), float(pt[1]), float(pt[2])))

            # Draw sci-fi wireframe directly on webcam preview frame
            for a, b in HAND_CONNECTIONS:
                p1 = (int(smoothed[a][0] * fw), int(smoothed[a][1] * fh))
                p2 = (int(smoothed[b][0] * fw), int(smoothed[b][1] * fh))
                cv2.line(frame, p1, p2, (0, 230, 255), 1, cv2.LINE_AA)
            for pt in smoothed:
                cv2.circle(frame, (int(pt[0] * fw), int(pt[1] * fh)), 2, (255, 255, 255), -1, cv2.LINE_AA)
            if is_pinch:
                cv2.circle(frame, (int(pinch_mid[0] * fw), int(pinch_mid[1] * fh)), 7, (0, 140, 255), 2, cv2.LINE_AA)

        # Multi-hand coordination & high-level gestures
        if n_hands == 2:
            h1, h2 = processed_hands[0], processed_hands[1]
            # Dual open palms -> Resonance Boost
            if h1.gesture == "OPEN_PALM" and h2.gesture == "OPEN_PALM":
                active_gesture = "DUAL_OPEN_PALMS"
            elif h1.is_pinch and h2.is_pinch:
                # Two-hand pinch zoom
                d_pinch = math.hypot(h1.pinch_point[0] - h2.pinch_point[0], h1.pinch_point[1] - h2.pinch_point[1])
                if self.prev_pinch_dist:
                    zoom_factor = max(0.6, min(1.6, (d_pinch / max(1e-3, self.prev_pinch_dist)) ** 1.5))
                self.prev_pinch_dist = d_pinch
                active_gesture = "DUAL_PINCH_ZOOM"
            else:
                self.prev_pinch_dist = None
                active_gesture = f"{h1.gesture} + {h2.gesture}"

            # Translation based on midpoint between both palms
            p_mid_x = (h1.palm_center[0] + h2.palm_center[0]) / 2.0
            p_mid_y = (h1.palm_center[1] + h2.palm_center[1]) / 2.0
            if self.prev_palm_pos[0]:
                dx = p_mid_x - self.prev_palm_pos[0][0]
                dy = p_mid_y - self.prev_palm_pos[0][1]
            self.prev_palm_pos[0] = (p_mid_x, p_mid_y)
            primary_roll = (h1.roll_angle + h2.roll_angle) / 2.0
            overall_depth = (h1.hand_size + h2.hand_size) / 2.0

        elif n_hands == 1:
            h1 = processed_hands[0]
            self.prev_pinch_dist = None
            active_gesture = h1.gesture
            primary_roll = h1.roll_angle
            overall_depth = h1.hand_size

            # Translation from palm motion
            px, py = h1.palm_center[0], h1.palm_center[1]
            if self.prev_palm_pos[0]:
                raw_dx = px - self.prev_palm_pos[0][0]
                raw_dy = py - self.prev_palm_pos[0][1]
                # Filter out micro-jitter
                if abs(raw_dx) > 0.0018 or abs(raw_dy) > 0.0018:
                    dx, dy = raw_dx, raw_dy
            self.prev_palm_pos[0] = (px, py)

            # Swipe recognition based on horizontal velocity
            self.swipe_history.append((t_now, px))
            self.swipe_history = [(t, x) for t, x in self.swipe_history if t_now - t <= 0.35]
            if len(self.swipe_history) >= 4 and (t_now - self.last_event_time > 0.65):
                dt = self.swipe_history[-1][0] - self.swipe_history[0][0]
                total_dx = self.swipe_history[-1][1] - self.swipe_history[0][1]
                if dt > 0.06:
                    vel = total_dx / dt
                    if vel > 1.3:
                        gesture_event = "SWIPE_RIGHT"
                        self.last_event_time = t_now
                        print("[Gesture Event] SWIPE RIGHT triggered!")
                    elif vel < -1.3:
                        gesture_event = "SWIPE_LEFT"
                        self.last_event_time = t_now
                        print("[Gesture Event] SWIPE LEFT triggered!")
        else:
            self.prev_palm_pos[0] = None
            self.prev_pinch_dist = None
            self.smoothers[0].reset()
            self.smoothers[1].reset()

        # Build telemetry state
        with self.lock:
            self.telemetry = TrackingTelemetry(
                hands_count=n_hands,
                hands=processed_hands,
                active_gesture=active_gesture,
                gesture_event=gesture_event,
                drag_dx=dx,
                drag_dy=dy,
                zoom_factor=zoom_factor,
                hand_roll=primary_roll,
                hand_depth=overall_depth,
                fingertip_points=fingertip_pts,
                palm_points=palm_pts,
                status_label=f"{n_hands} HAND(S) // {active_gesture}" if n_hands > 0 else "SHOW HANDS",
                confidence=0.88 if n_hands > 0 else 0.0,
                preview_frame=frame
            )

    def poll(self) -> TrackingTelemetry:
        """Returns the latest tracking telemetry atomically."""
        with self.lock:
            return self.telemetry

    def stop(self):
        """Cleanly releases camera and background resources."""
        self.running = False
        time.sleep(0.08)
        if self.cap is not None:
            try:
                self.cap.release()
            except Exception:
                pass
        self.cap = None
