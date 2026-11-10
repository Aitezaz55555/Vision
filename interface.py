import math
import os
import random
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import urllib.request

os.environ.setdefault("MPLCONFIGDIR", os.path.join(tempfile.gettempdir(), "matplotlib"))

import cv2
import numpy as np

from modules.hand_tracking import HandTracker, TrackingTelemetry, SingleHandInfo
from modules.particles import ParticleSystem

try:
    import mediapipe as mp
    HAS_MP = True
except Exception:  # mediapipe not installed
    HAS_MP = False

# Resolution:  --sd (1280x720) | default (1280x800) | --hd (1920x1080)
if "--sd" in sys.argv:
    W, H = 1280, 720
elif "--hd" in sys.argv:
    W, H = 1920, 1080
else:
    W, H = 1280, 800
K = H / 720.0                    # scale factor for sizes/thickness
GLOW = [1.0]                     # glow strength (change live with [ and ])
WIN = "VISION"
F = 1.5 * H                      # focal length
AUTO_SPEED = 0.25                # rad/sec (slow continuous rotation)
ZOOM_MIN, ZOOM_MAX = 0.45, 3.6

# ---- BLUE palette (BGR) ----
C_BRIGHT = (255, 225, 110)
C_MID = (255, 160, 45)
C_DEEP = (215, 95, 20)
C_TEXT = (255, 235, 140)
C_WHITE = (255, 250, 235)

import json

# ---- While Vision speaks the interface turns red (vision.py writes this file) ----
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_STATE_FILE = os.path.join(SCRIPT_DIR, "data", "vision_state.txt")
DATA_STATE_JSON = os.path.join(SCRIPT_DIR, "data", "vision_state.json")
TEMP_STATE_FILE = os.path.join(tempfile.gettempdir(), "vision_state.txt")


def _get_active_state_file():
    if os.path.isfile(DATA_STATE_FILE):
        return DATA_STATE_FILE
    return TEMP_STATE_FILE


_BLUE = dict(C_BRIGHT=C_BRIGHT, C_MID=C_MID, C_DEEP=C_DEEP, C_TEXT=C_TEXT, C_WHITE=C_WHITE)
_RED = dict(C_BRIGHT=(70, 70, 255), C_MID=(38, 42, 232), C_DEEP=(18, 22, 190),
            C_TEXT=(135, 145, 255), C_WHITE=(235, 240, 255))
RED_K = [0.0]                    # 0 = blue, 1 = red (smooth transition)
_state_cache = [0.0, False]
_state_data = {
    "state": "idle",
    "text": "",
    "result": "",
    "timestamp": 0.0
}


def get_vision_state_info():
    """Read full state info (every ~60 ms) from JSON or text file."""
    global _state_data
    now = time.time()
    if now - _state_cache[0] > 0.06:
        _state_cache[0] = now
        # Try JSON first
        if os.path.isfile(DATA_STATE_JSON):
            try:
                with open(DATA_STATE_JSON, "r", encoding="utf-8") as f:
                    _state_data = json.load(f)
                    _state_cache[1] = (_state_data.get("state") == "speaking")
                    return _state_data
            except Exception:
                pass

        # Fallback to text file
        state_file = _get_active_state_file()
        try:
            with open(state_file, "r", encoding="utf-8") as f:
                txt = f.read().strip()
            fresh = (now - os.path.getmtime(state_file)) < 120
            _state_data["state"] = txt if fresh else "idle"
            _state_cache[1] = (txt == "speaking" and fresh)
        except Exception:
            _state_cache[1] = False
    return _state_data


def vision_speaking():
    """Read the state file (every ~60 ms). True if it says 'speaking' and is fresh."""
    get_vision_state_info()
    return _state_cache[1]


def set_palette(k):
    """Blend blue <-> red. Drawing functions read these globals at call time."""
    g = globals()
    for name in _BLUE:
        g[name] = tuple(int(_BLUE[name][i] * (1 - k) + _RED[name][i] * k) for i in range(3))


def col(c, b=1.0):
    return tuple(int(max(0, min(255, v * b))) for v in c)


def mix(c, w, a):
    """Mix colour c towards w (white) by amount a."""
    a = max(0.0, min(1.0, a))
    return tuple(int(c[i] * (1 - a) + w[i] * a) for i in range(3))


random.seed(7)
rng = np.random.default_rng(7)


# ------------------------------------------------------------------ geometry
def rot_x(a):
    c, s = math.cos(a), math.sin(a)
    return np.array([[1, 0, 0], [0, c, -s], [0, s, c]])


def rot_y(a):
    c, s = math.cos(a), math.sin(a)
    return np.array([[c, 0, s], [0, 1, 0], [-s, 0, c]])


def rot_z(a):
    c, s = math.cos(a), math.sin(a)
    return np.array([[c, -s, 0], [s, c, 0], [0, 0, 1]])


def icosphere(sub=1):
    t = (1 + 5 ** 0.5) / 2
    v = [(-1, t, 0), (1, t, 0), (-1, -t, 0), (1, -t, 0), (0, -1, t), (0, 1, t),
         (0, -1, -t), (0, 1, -t), (t, 0, -1), (t, 0, 1), (-t, 0, -1), (-t, 0, 1)]
    f = [(0, 11, 5), (0, 5, 1), (0, 1, 7), (0, 7, 10), (0, 10, 11), (1, 5, 9),
         (5, 11, 4), (11, 10, 2), (10, 7, 6), (7, 1, 8), (3, 9, 4), (3, 4, 2),
         (3, 2, 6), (3, 6, 8), (3, 8, 9), (4, 9, 5), (2, 4, 11), (6, 2, 10),
         (8, 6, 7), (9, 8, 1)]
    verts = [np.array(p, float) / np.linalg.norm(p) for p in v]
    cache = {}

    def mid(a, b):
        k = (min(a, b), max(a, b))
        if k in cache:
            return cache[k]
        p = verts[a] + verts[b]
        verts.append(p / np.linalg.norm(p))
        cache[k] = len(verts) - 1
        return cache[k]

    for _ in range(sub):
        nf = []
        for a, b, c in f:
            ab, bc, ca = mid(a, b), mid(b, c), mid(c, a)
            nf += [(a, ab, ca), (b, bc, ab), (c, ca, bc), (ab, bc, ca)]
        f = nf
    edges = set()
    for a, b, c in f:
        for p, q in ((a, b), (b, c), (c, a)):
            edges.add((min(p, q), max(p, q)))
    return np.array(verts), np.array(sorted(edges))


CORE_V, CORE_E = icosphere(1)
INNER_V, INNER_E = icosphere(0)

# Small faceted crystal at the centre.
CRYSTAL_V = np.array([
    (0, 1, 0), (1, 0, 0), (0, 0, 1),
    (-1, 0, 0), (0, 0, -1), (0, -1, 0)
], dtype=float)
CRYSTAL_F = [(0, 1, 2), (0, 2, 3), (0, 3, 4), (0, 4, 1),
             (5, 2, 1), (5, 3, 2), (5, 4, 3), (5, 1, 4)]
CRYSTAL_E = sorted({tuple(sorted(edge)) for face in CRYSTAL_F
                    for edge in ((face[0], face[1]), (face[1], face[2]), (face[2], face[0]))})

# latitude rings (dense near the equator)
u = np.linspace(-1, 1, 24)
LAT_ANG = np.sign(u) * (np.abs(u) ** 1.6) * 1.35
_a = np.linspace(0, 2 * math.pi, 72)
LAT_RINGS = [np.stack([math.cos(g) * np.cos(_a), np.full_like(_a, math.sin(g)),
                       math.cos(g) * np.sin(_a)], 1) for g in LAT_ANG]

# fine circle (more points for smooth outer rings)
_b = np.linspace(0, 2 * math.pi, 181)
UNIT_CIRCLE = np.stack([np.cos(_b), np.zeros_like(_b), np.sin(_b)], 1)

# Gyroscope rings: (radius, tilt_x, tilt_z, spin speed, comet speed, comet tail)
GYROS = [
    (1.00, 1.15, 0.00, 0.30, 0.22, 0.20),
    (1.00, 0.35, 1.05, -0.24, -0.17, 0.20),
    (1.00, -0.75, -0.80, 0.18, 0.27, 0.16),
    (1.24, 0.55, 0.35, -0.10, 0.12, 0.10),
]

# tilted orbits
ORBITS = []
for _ in range(8):
    a = rng.uniform(0.3, 0.75)
    b = a * rng.uniform(0.45, 0.85)
    R_ = rot_x(rng.uniform(0, 3.14)) @ rot_y(rng.uniform(0, 3.14)) @ rot_z(rng.uniform(0, 3.14))
    pts = np.stack([a * np.cos(_a), b * np.sin(_a), np.zeros_like(_a)], 1)
    ORBITS.append((pts @ R_.T, rng.uniform(0.08, 0.22) * rng.choice([-1, 1])))


def fib_sphere(n):
    i = np.arange(n) + 0.5
    phi = np.arccos(1 - 2 * i / n)
    th = math.pi * (1 + 5 ** 0.5) * i
    return np.stack([np.cos(th) * np.sin(phi), np.cos(phi), np.sin(th) * np.sin(phi)], 1)


SHELL = fib_sphere(340)


def rand_dirs(n):
    v = rng.normal(size=(n, 3))
    return v / np.linalg.norm(v, axis=1, keepdims=True)


NODES = rand_dirs(18) * rng.uniform(1.9, 3.25, (18, 1))
STARS = rand_dirs(48) * rng.uniform(2.1, 4.1, (48, 1))

TOKENS = ["0xFF3A", "TLS 1.3", "AES-256", "RSA 4096", "SYNC OK", "200 OK", "ACK", ">>> RDY",
          "sys.init()", "malloc()", "fork()", "exec()", "spawn()", "void*", "fn main", "impl Orb",
          "arc::new", "async ()", "use std", "ptr_ref", "mutex.lk", "kernel.d", "core.0", "hash256",
          "SIGTERM", "01101001", "10110100", "IRQ 0x7", "DMA xfer", "TCP/SYN", "HTTP/2", "eth0: UP",
          "pipe |>", "::bind", ".unwrap", "chmod +x", "HEAP 4K", "REG EAX", "PATCH /", ">> SCAN", "FAULT 0",
          "latency"]
LAB_DIR = rand_dirs(140)
LAB_DIR[:, 1] *= 0.85
LAB_POS = LAB_DIR * (0.35 + 0.72 * rng.random((140, 1)) ** 0.5)
LAB_TXT = [random.choice(TOKENS) for _ in range(140)]


# ------------------------------------------------------------------ rendering
def project(P, R, camd):
    c = P @ R.T
    depth = np.maximum(camd + c[:, 2], 0.12)
    s = F / depth
    ox = S.get("offset_x", 0.0)
    oy = S.get("offset_y", 0.0)
    x = np.clip(W / 2 + c[:, 0] * s + ox, -30000, 30000)
    y = np.clip(H / 2 - c[:, 1] * s + oy, -30000, 30000)
    return x, y, s, c[:, 2]


def poly(layer, P, R, camd, color, th=1):
    x, y, _, _ = project(P, R, camd)
    pts = np.stack([x, y], 1).astype(np.int32).reshape(-1, 1, 2)
    cv2.polylines(layer, [pts], False, color, th, cv2.LINE_AA)


def shaded_ring(layer, glow, P, R, camd, color, th, gth, bmin, bmax, t=0.0, speed=0.0, tail=0.15):
    """Thin depth-shaded ring: front side bright, back side dim.
    If speed != 0 a glowing comet (white-hot head + tail) travels around the ring.
    Core line goes on `layer` (sharp), halo goes on `glow` (for bloom)."""
    x, y, s, z = project(P, R, camd)
    n = len(P) - 1
    xs = x.astype(np.int32).tolist()
    ys = y.astype(np.int32).tolist()
    zm = (z[:-1] + z[1:]) * 0.5
    front = np.clip(0.5 - zm / 2.0, 0.0, 1.0)
    br = bmin + (bmax - bmin) * front
    boost = np.zeros(n)
    head = 0
    if speed:
        head_f = ((t * speed) % 1.0) * n
        d = (head_f - np.arange(n)) % n
        boost = np.clip(1.0 - d / max(1.0, tail * n), 0.0, 1.0) ** 1.5
        head = int(head_f) % n
    brl, bol = br.tolist(), boost.tolist()
    for i in range(n):
        bo = bol[i]
        c = col(mix(color, C_WHITE, 0.35 + bo * 0.6), brl[i] + bo * 0.9)
        p1, p2 = (xs[i], ys[i]), (xs[i + 1], ys[i + 1])
        cv2.line(layer, p1, p2, c, th + (1 if bo > 0.55 else 0), cv2.LINE_AA)
        if gth:
            cv2.line(glow, p1, p2, col(color, brl[i] * 0.85 + bo * 1.1), gth, cv2.LINE_AA)
    if speed:
        hp, hb = (xs[head], ys[head]), brl[head]
        r1 = max(2, int(2.2 * K))
        cv2.circle(glow, hp, r1 * 4, col(C_BRIGHT, 0.5 + hb * 0.8), -1, cv2.LINE_AA)
        cv2.circle(layer, hp, r1, col(C_WHITE, 0.6 + hb), -1, cv2.LINE_AA)


def tick_ring(layer, glow, R, camd, radius, n, t, tilt, spin, color, bmin, bmax, yoff=0.0):
    """Clock / scale style ring with tick marks."""
    k = np.arange(n)
    ang = k * 2 * math.pi / n + spin * t
    ln = np.where(k % 10 == 0, 0.075, np.where(k % 5 == 0, 0.045, 0.022))
    ca, sa = np.cos(ang), np.sin(ang)
    inner = np.stack([radius * ca, np.zeros(n), radius * sa], 1) @ tilt.T
    outer = np.stack([(radius + ln) * ca, np.zeros(n), (radius + ln) * sa], 1) @ tilt.T
    inner[:, 1] += yoff
    outer[:, 1] += yoff
    x1, y1, _, z1 = project(inner, R, camd)
    x2, y2, _, _ = project(outer, R, camd)
    front = np.clip(0.5 - z1 / 2.0, 0.0, 1.0)
    for i in range(n):
        longt = (i % 10 == 0)
        b = bmin + (bmax - bmin) * front[i] * (1.0 if longt else 0.7)
        p1, p2 = (int(x1[i]), int(y1[i])), (int(x2[i]), int(y2[i]))
        cv2.line(layer, p1, p2, col(mix(color, C_WHITE, 0.3), b), 1, cv2.LINE_AA)
        if longt:
            cv2.line(glow, p1, p2, col(color, b * 0.9), max(2, int(2 * K)), cv2.LINE_AA)


def draw_hud(layer, glow, center, rad, t, zoom):
    """Screen-space rotating HUD arcs + tick marks around the sphere."""
    if rad < 30 or rad > 4 * W:
        return
    th2 = max(2, int(2 * K))
    r1 = int(rad * 1.40)
    for i in range(12):
        a0 = i * 30 + t * 10
        cv2.ellipse(layer, center, (r1, r1), 0, a0, a0 + 20, col(C_MID, 0.75), 1, cv2.LINE_AA)
    r2 = int(rad * 1.48)
    for i in range(3):
        a0 = i * 120 - t * 16
        cv2.ellipse(layer, center, (r2, r2), 0, a0, a0 + 62, col(C_WHITE, 0.95), 1, cv2.LINE_AA)
        cv2.ellipse(glow, center, (r2, r2), 0, a0, a0 + 62, col(C_BRIGHT, 1.0), th2 * 2, cv2.LINE_AA)
    r3 = rad * 1.56
    for i in range(72):
        a = math.radians(i * 5 + t * 4)
        ln = (9 if i % 6 == 0 else 4) * K
        ca, sa = math.cos(a), math.sin(a)
        p1 = (int(center[0] + ca * r3), int(center[1] + sa * r3))
        p2 = (int(center[0] + ca * (r3 + ln)), int(center[1] + sa * (r3 + ln)))
        cv2.line(layer, p1, p2, col(C_BRIGHT, 0.55 if i % 6 else 0.9), 1, cv2.LINE_AA)


def draw_title(layer, glow, t):
    """'VISION' title at the top centre: neon text with glow."""
    text = "V I S I O N"
    fs = 1.05 * K
    th = max(1, int(2 * K))
    (tw, tht), _ = cv2.getTextSize(text, cv2.FONT_HERSHEY_SIMPLEX, fs, th)
    x0 = int(W / 2 - tw / 2)
    y0 = int(28 * K + tht + 14 * K)
    pulse = 0.88 + 0.12 * math.sin(t * 2.0)
    cv2.putText(glow, text, (x0, y0), cv2.FONT_HERSHEY_SIMPLEX, fs,
                col(C_BRIGHT, 1.0 * pulse), th + max(3, int(3 * K)), cv2.LINE_AA)
    cv2.putText(layer, text, (x0, y0), cv2.FONT_HERSHEY_SIMPLEX, fs,
                col(mix(C_BRIGHT, C_WHITE, 0.55), pulse), th, cv2.LINE_AA)
    # thin side lines
    ly = y0 - tht // 2
    gap, ln = int(26 * K), int(150 * K)
    for sgn in (-1, 1):
        xa = int(W / 2 + sgn * (tw / 2 + gap))
        xb = xa + sgn * ln
        cv2.line(layer, (xa, ly), (xb, ly), col(C_BRIGHT, 0.8 * pulse), 1, cv2.LINE_AA)
        cv2.line(glow, (xa, ly), (xb, ly), col(C_BRIGHT, 0.8 * pulse), max(3, int(3 * K)), cv2.LINE_AA)
        cv2.circle(layer, (xa, ly), max(2, int(2.5 * K)), col(C_WHITE, 1.0), -1, cv2.LINE_AA)


def draw_status_panel(layer, glow, t):
    """Draws sleek sci-fi HUD status bar at bottom showing state, recognized speech, and results."""
    info = get_vision_state_info()
    st = str(info.get("state", "idle")).lower()

    state_labels = {
        "idle": "STANDBY // READY",
        "monitoring": "MONITORING // CLAP TO ACTIVATE",
        "clap_detected": "CLAP DETECTED // ACTIVATING",
        "activating": "VISION ONLINE // SYSTEMS OPTIMAL",
        "listening": "LISTENING FOR COMMAND...",
        "processing": "PROCESSING QUERY...",
        "generating": "GENERATING AI RESPONSE...",
        "executing": "EXECUTING COMMAND...",
        "speaking": "VISION SPEAKING...",
        "interrupted": "SPEECH INTERRUPTED // READY",
        "error": "SYSTEM ERROR",
    }
    status_text = state_labels.get(st, f"STATUS: {st.upper()}")
    gesture_st = S.get("gesture_label", "")
    if gesture_st:
        status_text = f"{status_text}  //  {gesture_st}"

    pulse = 0.82 + 0.18 * math.sin(t * 3.5 if st in ("listening", "speaking", "generating", "clap_detected") else t * 1.5)
    fs = 0.52 * K
    th = max(1, int(1.5 * K))

    # Center position near bottom
    (tw, tht), _ = cv2.getTextSize(status_text, cv2.FONT_HERSHEY_SIMPLEX, fs, th)
    x0 = int(W / 2 - tw / 2)
    y0 = int(H - 34 * K)

    # Glowing status badge
    cv2.putText(glow, status_text, (x0, y0), cv2.FONT_HERSHEY_SIMPLEX, fs,
                col(C_BRIGHT, 1.2 * pulse), th + max(2, int(2 * K)), cv2.LINE_AA)
    cv2.putText(layer, status_text, (x0, y0), cv2.FONT_HERSHEY_SIMPLEX, fs,
                col(mix(C_BRIGHT, C_WHITE, 0.65), pulse), th, cv2.LINE_AA)

    # Corner brackets around status
    bw = tw + int(36 * K)
    bx1, bx2 = int(W / 2 - bw / 2), int(W / 2 + bw / 2)
    by = y0 - tht // 2
    cv2.line(layer, (bx1, by - 6), (bx1, by + 6), col(C_BRIGHT, pulse), 1, cv2.LINE_AA)
    cv2.line(layer, (bx2, by - 6), (bx2, by + 6), col(C_BRIGHT, pulse), 1, cv2.LINE_AA)

    # If recent command was recognized, display above status
    heard_text = info.get("text", "").strip()
    if heard_text and (time.time() - info.get("timestamp", 0) < 15.0):
        h_fs = 0.44 * K
        sub_text = f'"{heard_text[:65]}"'
        (stw, stht), _ = cv2.getTextSize(sub_text, cv2.FONT_HERSHEY_SIMPLEX, h_fs, 1)
        sx0 = int(W / 2 - stw / 2)
        sy0 = y0 - int(22 * K)
        cv2.putText(layer, sub_text, (sx0, sy0), cv2.FONT_HERSHEY_SIMPLEX, h_fs,
                    col(C_TEXT, 0.85), 1, cv2.LINE_AA)


_BG = {}


def get_bg(k=0.0):
    key = (W, H)
    if key not in _BG:
        yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
        d = np.sqrt(((xx - W / 2) / (W / 2)) ** 2 + ((yy - H / 2) / (H / 2)) ** 2)
        g = np.clip(1.0 - d * 0.85, 0, 1) ** 2
        blue = np.zeros((H, W, 3), np.uint8)
        blue[..., 0] = (g * 36 + 3).astype(np.uint8)
        blue[..., 1] = (g * 13 + 1).astype(np.uint8)
        blue[..., 2] = (g * 2).astype(np.uint8)
        red = np.zeros((H, W, 3), np.uint8)
        red[..., 0] = (g * 2).astype(np.uint8)
        red[..., 1] = (g * 5 + 1).astype(np.uint8)
        red[..., 2] = (g * 34 + 3).astype(np.uint8)
        _BG.clear()
        _BG[key] = (blue, red)
    blue, red = _BG[key]
    if k < 0.01:
        return blue
    if k > 0.99:
        return red
    return cv2.addWeighted(blue, 1.0 - k, red, k, 0)


def draw_fingertip_beacons(layer, glow, fingertips, center, K):
    """Draws holographic tracking reticles and targeting beams at active fingertips."""
    for pt in fingertips:
        fx = int(pt[0] * W)
        fy = int(pt[1] * H)
        if 0 <= fx < W and 0 <= fy < H:
            r1 = max(8, int(13 * K))
            cv2.circle(glow, (fx, fy), r1, C_BRIGHT, max(2, int(2 * K)), cv2.LINE_AA)
            cv2.circle(layer, (fx, fy), r1, col(C_BRIGHT, 0.85), 1, cv2.LINE_AA)
            cv2.circle(layer, (fx, fy), max(2, int(2.5 * K)), (255, 255, 255), -1, cv2.LINE_AA)
            tick = int(5 * K)
            cv2.line(layer, (fx - r1 - tick, fy), (fx - r1 + 2, fy), C_BRIGHT, 1, cv2.LINE_AA)
            cv2.line(layer, (fx + r1 - 2, fy), (fx + r1 + tick, fy), C_BRIGHT, 1, cv2.LINE_AA)
            cv2.line(layer, (fx, fy - r1 - tick), (fx, fy - r1 + 2), C_BRIGHT, 1, cv2.LINE_AA)
            cv2.line(layer, (fx, fy + r1 - 2), (fx, fy + r1 + tick), C_BRIGHT, 1, cv2.LINE_AA)
            # Subtle targeting beam to center
            cv2.line(layer, (fx, fy), center, col(C_MID, 0.22), 1, cv2.LINE_AA)


def draw_camera_pip(img, preview_frame, K):
    """Draws a sleek semi-transparent sci-fi tracking HUD box in top-left corner."""
    if preview_frame is None or not S.get("show_camera", True):
        return
    pip_w = int(170 * K)
    pip_h = int(128 * K)
    if pip_w <= 30 or pip_h <= 30 or pip_w + 30 >= W or pip_h + 30 >= H:
        return
    small_cam = cv2.resize(preview_frame, (pip_w, pip_h), interpolation=cv2.INTER_AREA)
    tinted = (small_cam.astype(np.float32) * [1.1, 0.9, 0.6]).clip(0, 255).astype(np.uint8)
    x1, y1 = int(24 * K), int(24 * K)
    x2, y2 = x1 + pip_w, y1 + pip_h
    img[y1:y2, x1:x2] = cv2.addWeighted(img[y1:y2, x1:x2], 0.35, tinted, 0.65, 0)
    cv2.rectangle(img, (x1, y1), (x2, y2), C_MID, 1, cv2.LINE_AA)
    lbl = "HAND OPTICS // ACTIVE (C: toggle)"
    cv2.putText(img, lbl, (x1 + 4, y1 - 6), cv2.FONT_HERSHEY_SIMPLEX, 0.30 * K, C_BRIGHT, 1, cv2.LINE_AA)


def render(yaw, pitch, zoom, t, particle_system=None, telemetry=None):
    roll = S.get("roll", 0.0)
    R = rot_z(roll) @ rot_x(pitch) @ rot_y(yaw)
    camd = 4.0 / zoom
    base = F / 4.0
    T1 = max(1, round(0.6 * K))      # fine single line
    T2 = max(2, round(2 * K))        # thick line
    GTH = max(4, round(5 * K))       # halo line thickness (glow layer)
    layer = np.zeros((H, W, 3), np.uint8)
    glow_layer = np.zeros_like(layer)

    # Twinkling stars
    x, y, s, cz = project(STARS, R, camd)
    for i, (xi, yi, si) in enumerate(zip(x, y, s)):
        if 0 <= xi < W and 0 <= yi < H:
            tw = 0.55 + 0.45 * math.sin(t * 2.3 + i * 1.7)
            radius = max(1, int(1.0 * K * si / base))
            px, py = int(xi), int(yi)
            cv2.circle(layer, (px, py), radius, col(C_BRIGHT, tw), -1, cv2.LINE_AA)
            if radius >= 2:
                cv2.circle(layer, (px, py), 1, (255, 255, 235), -1, cv2.LINE_AA)

    # latitude rings (dim wire grid)
    for ring in LAT_RINGS:
        poly(layer, ring, R, camd, col(C_MID, 0.30), T1)

    # data-dot shell with scan wave
    shell = SHELL @ rot_y(t * 0.15).T
    x, y, s, z = project(shell, R, camd)
    wave = 0.5 + 0.5 * np.sin(shell[:, 1] * 4.0 - t * 2.2)
    front = np.clip(0.5 - z / 2.0, 0.0, 1.0)
    for xi, yi, fr, wv in zip(x.tolist(), y.tolist(), front.tolist(), wave.tolist()):
        b = (0.15 + 0.85 * fr) * (0.40 + 0.60 * wv)
        r = 2 if (wv > 0.92 and fr > 0.5) else 1
        c = col(mix(C_BRIGHT, C_WHITE, 0.6 if r == 2 else 0.2), b)
        cv2.circle(layer, (int(xi), int(yi)), max(1, int(r * K)), c, -1, cv2.LINE_AA)

    # Gyroscope outer rings: thin, glowing, spinning on different axes, with comets
    for rad, tx, tz, spin, cspeed, tail in GYROS:
        Rr = rot_y(spin * t) @ rot_x(tx) @ rot_z(tz)
        pts = (UNIT_CIRCLE * rad) @ Rr.T
        shaded_ring(layer, glow_layer, pts, R, camd, C_BRIGHT, T1, GTH, 0.30, 1.0,
                    t=t, speed=cspeed, tail=tail)

    # Equator tick ring (slightly tilted)
    tick_ring(layer, glow_layer, R, camd, 1.08, 120, t, rot_z(0.22), 0.10, C_BRIGHT, 0.2, 0.95)

    # Orbits with travelling light
    for i, (pts, sp) in enumerate(ORBITS):
        po = pts @ rot_y(t * 0.07 * (1 + i % 3)).T
        shaded_ring(layer, glow_layer, po, R, camd, C_MID, T1, 3, 0.15, 0.55,
                    t=t + i * 0.37, speed=sp, tail=0.14)

    # ---- centre energy beat modulated by hand collapse/expansion ----
    collapse = particle_system.collapse_factor if particle_system else 1.0
    beat = 0.5 + 0.5 * math.sin(t * (4.8 if collapse < 0.6 else 3.4))
    beat = beat ** 1.3
    pulse = (0.5 + 0.9 * beat) * max(0.35, collapse)
    core_k = (0.7 + 0.6 * beat) * collapse

    # core (spinning wireframe)
    Rc = rot_y(t * 0.6) @ rot_x(t * 0.35)
    for V, E, sc, th, bb in ((CORE_V, CORE_E, 0.20, T1, 0.85), (INNER_V, INNER_E, 0.11, T1, 0.6)):
        x, y, s, _ = project((V * sc * core_k) @ Rc.T, R, camd)
        for a, b2 in E:
            cv2.line(layer, (int(x[a]), int(y[a])), (int(x[b2]), int(y[b2])),
                     col(C_BRIGHT, bb), th, cv2.LINE_AA)
        for i in range(len(V)):
            cv2.circle(layer, (int(x[i]), int(y[i])), max(1, int(2.5 * K * s[i] / base)),
                       col((255, 255, 220)), -1, cv2.LINE_AA)

    cx, cy, cs, _ = project(np.zeros((1, 3)), R, camd)
    center = (int(cx[0]), int(cy[0]))
    crystal_r = max(4, int(0.15 * cs[0] * pulse * collapse))

    # Pulsing energy rings around the crystal
    for mult, b_, cc in ((2.8, 0.72, C_MID), (1.45, 0.92, C_BRIGHT)):
        rr = max(int(crystal_r * mult), 18 if mult > 2 else 10)
        cv2.circle(layer, center, rr, col(cc, b_ * pulse), max(1, T1), cv2.LINE_AA)
        cv2.circle(glow_layer, center, rr, col(cc, b_ * pulse), max(3, T2 * 2), cv2.LINE_AA)
    cv2.circle(glow_layer, center, int(crystal_r * (0.8 + 0.9 * beat)),
               col(C_BRIGHT, 0.12 + 0.30 * beat), -1, cv2.LINE_AA)

    # shockwave rings: expand from the centre and fade out
    for k in range(3):
        ph = (t * 0.8 + k / 3.0) % 1.0
        rr = int(crystal_r * (1.4 + ph * 6.0))
        bw = (1.0 - ph) ** 1.6
        cv2.circle(layer, center, rr, col(mix(C_BRIGHT, C_WHITE, 0.4), 0.9 * bw), 1, cv2.LINE_AA)
        cv2.circle(glow_layer, center, rr, col(C_BRIGHT, 0.9 * bw), max(3, T2 * 2), cv2.LINE_AA)

    crystal_rot = rot_y(t * 0.8) @ rot_x(t * 0.35)
    crystal_points = (CRYSTAL_V * (0.15 * pulse)) @ crystal_rot.T
    qx, qy, qs, qz = project(crystal_points, R, camd)
    face_layer = np.zeros_like(layer)
    face_order = sorted(range(len(CRYSTAL_F)),
                        key=lambda i: sum(qz[v] for v in CRYSTAL_F[i]), reverse=True)
    for face_i in face_order:
        face = CRYSTAL_F[face_i]
        pts = np.array([(int(qx[v]), int(qy[v])) for v in face], dtype=np.int32)
        shade = 0.24 if face_i % 2 == 0 else 0.14
        cv2.fillConvexPoly(face_layer, pts, col(C_BRIGHT, shade * pulse), cv2.LINE_AA)
    cv2.addWeighted(layer, 1.0, face_layer, 0.72, 0, dst=layer)
    for a, b2 in CRYSTAL_E:
        p1, p2 = (int(qx[a]), int(qy[a])), (int(qx[b2]), int(qy[b2]))
        cv2.line(layer, p1, p2, col(C_WHITE, 1.0 * pulse), max(1, round(K)), cv2.LINE_AA)
        cv2.line(glow_layer, p1, p2, col(C_BRIGHT, 1.0 * pulse), max(2, round(2 * K)), cv2.LINE_AA)
    highlight = (int(qx[0]), int(qy[0]))
    cv2.circle(layer, highlight, max(1, int(0.045 * crystal_r)), col((255, 255, 235)), -1, cv2.LINE_AA)

    nx, ny, ns, nz = project(NODES, R, camd)
    # glowing nodes
    for xi, yi, si, zi in zip(nx, ny, ns, nz):
        if -50 < xi < W + 50 and -50 < yi < H + 50:
            r = int(min(16, max(1, 1.35 * K * si / base)))
            front = 0.72 + 0.28 * (0.5 - zi / 2)
            px, py = int(xi), int(yi)
            cv2.circle(glow_layer, (px, py), r * 2, col(C_BRIGHT, front), -1, cv2.LINE_AA)
            cv2.circle(layer, (px, py), r, col(C_BRIGHT, front), -1, cv2.LINE_AA)
            cv2.circle(layer, (px, py), 1, (255, 255, 235), -1, cv2.LINE_AA)

    # Floating hologram words
    x, y, s, cz = project(LAB_POS, R, camd)
    for i in range(len(LAB_TXT)):
        xi, yi = x[i], y[i]
        if xi < -250 or xi > W + 250 or yi < -100 or yi > H + 100:
            continue
        fs = 0.22 * K * s[i] / base
        if fs < 0.14 or fs > 4:
            continue
        front = 0.5 - cz[i] / 2
        b = 0.45 + 0.55 * max(0.0, min(1.0, front))
        tw = 0.8 + 0.2 * math.sin(t * 3.0 + i * 1.3)       # each word shimmers slightly
        b *= tw
        th = 1 if fs < 1.2 else (2 if fs < 2.5 else 3)
        pos = (int(xi), int(yi))
        # big neon halo (glow layer) - 2 passes: thick + thin
        cv2.putText(glow_layer, LAB_TXT[i], pos, cv2.FONT_HERSHEY_SIMPLEX, fs,
                    col(C_BRIGHT, 1.25 * b), th + 4, cv2.LINE_AA)
        cv2.putText(glow_layer, LAB_TXT[i], pos, cv2.FONT_HERSHEY_SIMPLEX, fs,
                    col(C_BRIGHT, 1.4 * b), th + 1, cv2.LINE_AA)
        # bright white-hot core text
        cv2.putText(layer, LAB_TXT[i], pos, cv2.FONT_HERSHEY_SIMPLEX, fs,
                    col(mix(C_TEXT, C_WHITE, 0.55), min(1.4, b * 1.35)), th, cv2.LINE_AA)

    # Render interactive particle system
    if particle_system:
        particle_system.render(layer, glow_layer, R, camd, base, W, H, K, C_BRIGHT, C_MID)

    # Render fingertip beacons
    if telemetry and telemetry.fingertip_points:
        draw_fingertip_beacons(layer, glow_layer, telemetry.fingertip_points, center, K)

    # Special two-fingers focused beam
    if telemetry and telemetry.active_gesture == "TWO_FINGERS" and len(telemetry.fingertip_points) >= 2:
        p1 = (int(telemetry.fingertip_points[0][0] * W), int(telemetry.fingertip_points[0][1] * H))
        p2 = (int(telemetry.fingertip_points[1][0] * W), int(telemetry.fingertip_points[1][1] * H))
        cv2.line(glow_layer, p1, p2, col(C_BRIGHT, 1.4), max(3, int(3 * K)), cv2.LINE_AA)
        cv2.line(layer, p1, p2, (255, 255, 255), max(1, int(1.5 * K)), cv2.LINE_AA)

    # Special dual-palm resonance bridge
    if telemetry and telemetry.active_gesture == "DUAL_OPEN_PALMS" and len(telemetry.palm_points) >= 2:
        p1 = (int(telemetry.palm_points[0][0] * W), int(telemetry.palm_points[0][1] * H))
        p2 = (int(telemetry.palm_points[1][0] * W), int(telemetry.palm_points[1][1] * H))
        cv2.line(glow_layer, p1, p2, col(C_WHITE, 1.3), max(4, int(4 * K)), cv2.LINE_AA)
        cv2.line(layer, p1, p2, col(C_BRIGHT, 1.0), max(2, int(2 * K)), cv2.LINE_AA)
        mid = ((p1[0] + p2[0]) // 2, (p1[1] + p2[1]) // 2)
        cv2.circle(glow_layer, mid, int(45 * K), C_BRIGHT, max(3, int(3 * K)), cv2.LINE_AA)

    # HUD arcs around the sphere
    draw_hud(layer, glow_layer, center, cs[0], t, zoom)
    draw_title(layer, glow_layer, t)
    draw_status_panel(layer, glow_layer, t)

    # ---- bloom ----
    src = cv2.addWeighted(glow_layer, 1.0, layer, 0.45, 0)
    small = cv2.resize(src, (W // 3, H // 3), interpolation=cv2.INTER_AREA)
    tight = cv2.GaussianBlur(small, (0, 0), 1.2 * K)    # bright edge bloom
    middle = cv2.GaussianBlur(small, (0, 0), 3.7 * K)   # luminous local halo
    wide = cv2.GaussianBlur(small, (0, 0), 9.5 * K)     # soft atmospheric glow
    gk = GLOW[0]
    bloom = cv2.addWeighted(tight, 0.95 * gk, middle, 1.15 * gk, 0)
    bloom = cv2.addWeighted(bloom, 1.0, wide, 0.9 * gk, 0)
    glow = cv2.resize(bloom, (W, H), interpolation=cv2.INTER_LINEAR)
    out = cv2.addWeighted(layer, 1.18, glow, 0.66, 0)
    out = cv2.add(out, get_bg(RED_K[0]))
    out[::4] = (out[::4] * 0.94).astype(np.uint8)       # very faint scanlines
    if random.random() < 0.05:                          # slight hologram flicker
        out = cv2.convertScaleAbs(out, alpha=0.93)
    return out


# ------------------------------------------------------------------ app state / UI
S = dict(
    yaw=0.0,
    pitch=0.15,
    roll=0.0,
    vyaw=AUTO_SPEED,
    vpitch=0.0,
    vroll=0.0,
    zoom=1.0,
    zoom_t=1.0,
    offset_x=0.0,
    offset_y=0.0,
    target_offset_x=0.0,
    target_offset_y=0.0,
    drag=False,
    lx=0,
    ly=0,
    mdx=0.0,
    mdy=0.0,
    show_camera=True,
    gesture_label="",
)


def clampz(z):
    return max(ZOOM_MIN, min(ZOOM_MAX, z))


def press(name):
    if name == "+":
        S["zoom_t"] = clampz(S["zoom_t"] * 1.25)
    elif name == "-":
        S["zoom_t"] = clampz(S["zoom_t"] / 1.25)
    else:
        S.update(
            yaw=0.0,
            pitch=0.15,
            roll=0.0,
            zoom_t=1.0,
            vyaw=AUTO_SPEED,
            vpitch=0.0,
            vroll=0.0,
            offset_x=0.0,
            offset_y=0.0,
            target_offset_x=0.0,
            target_offset_y=0.0,
        )


def on_mouse(ev, x, y, flags, _):
    if ev == cv2.EVENT_LBUTTONDOWN:
        S["drag"], S["lx"], S["ly"] = True, x, y
    elif ev == cv2.EVENT_MOUSEMOVE and S["drag"]:
        S["mdx"] += (x - S["lx"]) / W
        S["mdy"] += (y - S["ly"]) / W
        S["lx"], S["ly"] = x, y
    elif ev == cv2.EVENT_LBUTTONUP:
        S["drag"] = False
    elif ev == cv2.EVENT_MOUSEWHEEL:
        S["zoom_t"] = clampz(S["zoom_t"] * (1.1 if flags > 0 else 1 / 1.1))


def draw_scanline(img, t):
    """Transparent beam with a soft halo, moving smoothly up and down."""
    span = max(1, H - 1)
    phase = (t * 190) % (2 * span)
    y_float = phase if phase <= span else 2 * span - phase
    y = int(y_float)
    frac = y_float - y
    tint = np.empty((1, W, 3), dtype=np.uint8)
    tint[:] = C_BRIGHT
    for offset, alpha in ((-3, 0.035), (-2, 0.07), (-1, 0.16),
                          (0, 0.68), (1, 0.16), (2, 0.07), (3, 0.035)):
        for yy, weight in ((y + offset, 1.0 - frac), (y + offset + 1, frac)):
            if 0 <= yy < H and weight > 0.001:
                row = img[yy:yy + 1]
                a = alpha * weight
                img[yy:yy + 1] = cv2.addWeighted(row, 1.0 - a, tint, a, 0)


def sync_render_size():
    """Match the render canvas to the resizable window (capped to save power)."""
    global W, H, K, F
    try:
        _, _, view_w, view_h = cv2.getWindowImageRect(WIN)
    except cv2.error:
        return
    if view_w < 320 or view_h < 240:
        return
    scale = min(1.0, 1600 / view_w, 1000 / view_h)
    new_w = max(320, int(view_w * scale))
    new_h = max(240, int(view_h * scale))
    if new_w != W or new_h != H:
        W, H = new_w, new_h
        K = H / 720.0
        F = 1.5 * H


def main():
    tracker = HandTracker()
    particle_system = ParticleSystem(count=240)
    cv2.namedWindow(WIN, cv2.WINDOW_NORMAL)
    cv2.resizeWindow(WIN, W, H)
    cv2.setMouseCallback(WIN, on_mouse)
    full = False                       # press F to toggle fullscreen
    t0 = last = time.time()
    last_burst_time = 0.0

    while True:
        frame_start = time.time()
        now = frame_start
        dt = max(1e-3, min(0.08, now - last))
        last = now

        telemetry = tracker.poll()

        # Update gesture status & dynamics from telemetry
        if telemetry.hands_count > 0:
            S["gesture_label"] = telemetry.active_gesture if telemetry.active_gesture != "NONE" else f"{telemetry.hands_count} HAND(S)"

            # Smooth palm roll/tilt
            target_roll = -telemetry.hand_roll * 0.8
            S["roll"] += (target_roll - S["roll"]) * min(1.0, dt * 5.0)

            # Hologram translation tracking primary palm position
            if telemetry.palm_points:
                px, py, _ = telemetry.palm_points[0]
                S["target_offset_x"] = (px - 0.5) * W * 0.45
                S["target_offset_y"] = (py - 0.5) * H * 0.45

            # Zoom factor from two-hand pinch / depth
            if abs(telemetry.zoom_factor - 1.0) > 1e-4:
                S["zoom_t"] = clampz(S["zoom_t"] * telemetry.zoom_factor)

            # Open palm burst
            if telemetry.active_gesture in ("OPEN_PALM", "DUAL_OPEN_PALMS"):
                if now - last_burst_time > 0.4:
                    particle_system.trigger_burst(0.85)
                    last_burst_time = now

            # Gesture events (e.g. Swipes)
            if telemetry.gesture_event == "SWIPE_RIGHT":
                S["vyaw"] += 3.5
                cx = W / 2 + S["offset_x"]
                cy = H / 2 + S["offset_y"]
                particle_system.trigger_ripple(cx, cy, max_radius=320.0, color=(255, 235, 140))
            elif telemetry.gesture_event == "SWIPE_LEFT":
                S["vyaw"] -= 3.5
                cx = W / 2 + S["offset_x"]
                cy = H / 2 + S["offset_y"]
                particle_system.trigger_ripple(cx, cy, max_radius=320.0, color=(140, 235, 255))
        else:
            S["gesture_label"] = ""
            S["target_offset_x"] = 0.0
            S["target_offset_y"] = 0.0
            S["roll"] += (0.0 - S["roll"]) * min(1.0, dt * 4.0)

        # Smooth screen translation
        S["offset_x"] += (S["target_offset_x"] - S["offset_x"]) * min(1.0, dt * 6.5)
        S["offset_y"] += (S["target_offset_y"] - S["offset_y"]) * min(1.0, dt * 6.5)

        # Update 3D particle dynamics
        particle_system.update(
            dt,
            fingertips_3d=telemetry.fingertip_points,
            palm_centers_3d=telemetry.palm_points,
            gesture=telemetry.active_gesture
        )

        # Rotational inputs (hand drag + mouse drag)
        dx = telemetry.drag_dx + S["mdx"]
        dy = telemetry.drag_dy + S["mdy"]
        S["mdx"] = S["mdy"] = 0.0

        if abs(dx) > 1e-5 or abs(dy) > 1e-5:         # active manual manipulation
            a_y, a_p = -dx * 6.0, -dy * 5.0
            S["yaw"] += a_y
            S["pitch"] += a_p
            S["vyaw"] = 0.6 * S["vyaw"] + 0.4 * (a_y / dt)
            S["vpitch"] = 0.6 * S["vpitch"] + 0.4 * (a_p / dt)
        else:                                         # inertia -> decay to slow ambient spin
            k = min(1.0, dt * 1.5)
            S["vyaw"] += (AUTO_SPEED - S["vyaw"]) * k
            S["vpitch"] += (0.0 - S["vpitch"]) * k
            S["yaw"] += S["vyaw"] * dt
            S["pitch"] += S["vpitch"] * dt

        S["pitch"] = max(-1.4, min(1.4, S["pitch"]))
        S["zoom"] += (S["zoom_t"] - S["zoom"]) * min(1.0, dt * 8.0)

        # Red palette transition while Vision is speaking
        target = 1.0 if vision_speaking() else 0.0
        if abs(target - RED_K[0]) > 0.002:
            RED_K[0] += (target - RED_K[0]) * min(1.0, dt * 7.0)
            set_palette(RED_K[0])
        elif RED_K[0] != target:
            RED_K[0] = target
            set_palette(target)

        # Render hologram frame
        img = render(S["yaw"], S["pitch"], S["zoom"], now - t0,
                     particle_system=particle_system, telemetry=telemetry)
        draw_scanline(img, now - t0)

        # Camera picture-in-picture tracking HUD
        if S.get("show_camera", True) and telemetry.preview_frame is not None:
            draw_camera_pip(img, telemetry.preview_frame, K)

        cv2.imshow(WIN, img)

        k = cv2.waitKey(1) & 0xFF
        sync_render_size()
        if k in (27, ord("q")):
            break
        elif k in (ord("c"), ord("C")):
            S["show_camera"] = not S.get("show_camera", True)
        elif k in (ord("+"), ord("=")):
            press("+")
        elif k in (ord("-"), ord("_")):
            press("-")
        elif k == ord("]"):
            GLOW[0] = min(3.0, GLOW[0] * 1.2)
        elif k == ord("["):
            GLOW[0] = max(0.2, GLOW[0] / 1.2)
        elif k == ord("r"):
            press("RESET")
        elif k == ord("f"):
            full = not full
            cv2.setWindowProperty(WIN, cv2.WND_PROP_FULLSCREEN,
                                  cv2.WINDOW_FULLSCREEN if full else cv2.WINDOW_NORMAL)

        # Maintain smooth target framerate (45-60 FPS)
        time.sleep(max(0.0, 1.0 / 45.0 - (time.time() - frame_start)))

    tracker.stop()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
