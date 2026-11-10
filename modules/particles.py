"""
VISION AI - Interactive 3D Holographic Particle System
Simulates a quantum particle swarm that dynamically responds to hand positions,
fingertip gravity, open-palm expansion bursts, closed-fist singularity collapse,
and expanding shockwave ripple effects.
"""

import math
import random
from typing import List, Tuple, Optional
import numpy as np
import cv2


class RippleWave:
    """Expanding 2D/3D circular shockwave ripple."""
    def __init__(self, x: float, y: float, max_radius: float = 240.0, speed: float = 380.0, color=(255, 225, 110)):
        self.x = x
        self.y = y
        self.radius = 8.0
        self.max_radius = max_radius
        self.speed = speed
        self.color = color
        self.alpha = 1.0
        self.active = True

    def update(self, dt: float):
        self.radius += self.speed * dt
        progress = self.radius / max(1.0, self.max_radius)
        if progress >= 1.0:
            self.alpha = 0.0
            self.active = False
        else:
            self.alpha = max(0.0, float((1.0 - progress) ** 1.3))
        if self.radius >= self.max_radius:
            self.active = False

    def draw(self, layer: np.ndarray, glow_layer: np.ndarray, K: float = 1.0):
        if not self.active or self.alpha <= 0.02:
            return
        r = int(self.radius)
        col = tuple(int(c * self.alpha) for c in self.color)
        center = (int(self.x), int(self.y))
        th1 = max(1, int(1.5 * K))
        th2 = max(3, int(4 * K))
        cv2.circle(layer, center, r, col, th1, cv2.LINE_AA)
        cv2.circle(glow_layer, center, r, col, th2, cv2.LINE_AA)


class Particle:
    """Individual 3D quantum particle with Newtonian physics, attraction, and drag."""
    def __init__(self, x: float, y: float, z: float):
        self.x = x
        self.y = y
        self.z = z
        self.ox = x
        self.oy = y
        self.oz = z
        self.vx = random.uniform(-0.05, 0.05)
        self.vy = random.uniform(-0.05, 0.05)
        self.vz = random.uniform(-0.05, 0.05)
        self.size = random.uniform(1.2, 2.6)
        self.brightness = random.uniform(0.6, 1.0)
        self.orbit_speed = random.uniform(0.2, 0.8)
        self.orbit_phase = random.uniform(0, math.tau)
        self.orbit_radius = math.hypot(x, y, z)
        self.life = 1.0

    def reset_random(self, radius_min: float = 0.4, radius_max: float = 1.8):
        theta = random.uniform(0, math.tau)
        phi = random.uniform(-math.pi / 2, math.pi / 2)
        r = random.uniform(radius_min, radius_max)
        self.x = r * math.cos(phi) * math.cos(theta)
        self.y = r * math.sin(phi)
        self.z = r * math.cos(phi) * math.sin(theta)
        self.ox, self.oy, self.oz = self.x, self.y, self.z
        self.orbit_radius = r
        self.vx, self.vy, self.vz = 0.0, 0.0, 0.0


class ParticleSystem:
    """
    3D Particle Dynamics Simulator that connects hand landmarks to fluid visual effects.
    """
    def __init__(self, count: int = 240):
        self.particles: List[Particle] = []
        for _ in range(count):
            p = Particle(0, 0, 0)
            p.reset_random(0.35, 1.9)
            self.particles.append(p)

        self.ripples: List[RippleWave] = []
        self.prev_time = 0.0
        self.burst_energy = 0.0
        self.collapse_factor = 1.0

    def trigger_ripple(self, x: float, y: float, max_radius: float = 280.0, color=(255, 225, 110)):
        """Emits an outward holographic ripple shockwave."""
        self.ripples.append(RippleWave(x, y, max_radius=max_radius, color=color))
        # Keep ripples bounded
        if len(self.ripples) > 6:
            self.ripples.pop(0)

    def trigger_burst(self, intensity: float = 1.0):
        """Triggers radial explosive dispersion (e.g. on Open Palm)."""
        self.burst_energy = min(2.5, self.burst_energy + intensity)

    def update(self, dt: float,
               fingertips_3d: List[Tuple[float, float, float]],
               palm_centers_3d: List[Tuple[float, float, float]],
               gesture: str = "NONE"):
        dt = max(1e-4, min(0.08, dt))

        # Handle gesture influence
        target_collapse = 1.0
        if gesture == "CLOSED_FIST":
            target_collapse = 0.28   # Collapse toward core singularity
        elif gesture in ("OPEN_PALM", "DUAL_OPEN_PALMS"):
            target_collapse = 1.45   # Expand outward
        self.collapse_factor += (target_collapse - self.collapse_factor) * min(1.0, dt * 5.0)

        # Decay burst energy
        self.burst_energy = max(0.0, self.burst_energy - dt * 2.2)

        # Update ripples
        for r in self.ripples:
            r.update(dt)
        self.ripples = [r for r in self.ripples if r.active]

        for p in self.particles:
            # 1. Base orbital motion
            p.orbit_phase += p.orbit_speed * dt
            target_r = p.orbit_radius * self.collapse_factor
            target_x = target_r * math.cos(p.orbit_phase)
            target_y = p.oy * self.collapse_factor + math.sin(p.orbit_phase * 1.5) * 0.1
            target_z = target_r * math.sin(p.orbit_phase)

            # Spring return toward orbital position
            fx = (target_x - p.x) * 1.8
            fy = (target_y - p.y) * 1.8
            fz = (target_z - p.z) * 1.8

            # 2. Attraction toward active fingertips
            for fx_pt, fy_pt, fz_pt in fingertips_3d:
                # Convert normalized screen coords [0..1] to 3D hologram space roughly [-1.5..1.5]
                hx = (fx_pt - 0.5) * 3.2
                hy = (fy_pt - 0.5) * 2.2
                hz = (fz_pt) * 1.5
                dist_sq = (hx - p.x) ** 2 + (hy - p.y) ** 2 + (hz - p.z) ** 2 + 0.05
                dist = math.sqrt(dist_sq)
                if dist < 1.4:
                    pull = 1.2 / dist_sq
                    fx += (hx - p.x) * pull
                    fy += (hy - p.y) * pull
                    fz += (hz - p.z) * pull

            # 3. Burst explosion force
            if self.burst_energy > 0.05:
                dist_center = math.hypot(p.x, p.y, p.z) + 0.1
                outward = (self.burst_energy * 2.5) / dist_center
                fx += (p.x / dist_center) * outward
                fy += (p.y / dist_center) * outward
                fz += (p.z / dist_center) * outward

            # Apply forces with damping
            p.vx = (p.vx + fx * dt) * 0.88
            p.vy = (p.vy + fy * dt) * 0.88
            p.vz = (p.vz + fz * dt) * 0.88

            p.x += p.vx * dt
            p.y += p.vy * dt
            p.z += p.vz * dt

    def render(self, layer: np.ndarray, glow_layer: np.ndarray,
               R: np.ndarray, camd: float, base_focal: float,
               W: int, H: int, K: float,
               color_bright: Tuple[int, int, int],
               color_mid: Tuple[int, int, int]):
        """Projects and draws interactive particles and active ripples."""
        # 1. Draw ripples first (background layer)
        for r in self.ripples:
            r.draw(layer, glow_layer, K)

        if not self.particles:
            return

        # 2. Project particle coordinates
        coords = np.array([[p.x, p.y, p.z] for p in self.particles], dtype=np.float32)
        rot_pts = coords @ R.T
        z = rot_pts[:, 2] + camd
        valid = z > 0.2

        if not np.any(valid):
            return

        pz = z[valid]
        scale = base_focal / pz
        px = (rot_pts[valid, 0] * scale + W / 2.0).astype(np.int32)
        py = (rot_pts[valid, 1] * scale + H / 2.0).astype(np.int32)

        indices = np.where(valid)[0]
        for idx, sx, sy, sz, sc in zip(indices, px, py, pz, scale):
            if 0 <= sx < W and 0 <= sy < H:
                p = self.particles[idx]
                depth_alpha = max(0.2, min(1.0, 1.6 - (sz - camd) / 2.0))
                brightness = p.brightness * depth_alpha

                col_b = tuple(int(c * brightness) for c in color_bright)
                radius = max(1, int(p.size * K * (sc / (base_focal / 4.0))))

                cv2.circle(layer, (sx, sy), radius, col_b, -1, cv2.LINE_AA)
                if radius >= 2:
                    cv2.circle(glow_layer, (sx, sy), radius * 2, col_b, -1, cv2.LINE_AA)
                    cv2.circle(layer, (sx, sy), 1, (255, 255, 245), -1, cv2.LINE_AA)
