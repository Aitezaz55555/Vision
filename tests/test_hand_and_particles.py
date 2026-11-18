"""
Test suite verifying:
1. AdaptiveSmoother stability & agility
2. Hand gesture classifier logic
3. ParticleSystem physics & ripples
4. Interface hologram offline rendering with telemetry & particles
"""
import sys
import os
import time
import math
import unittest
import numpy as np

# Ensure project root is in sys.path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from modules.hand_tracking import AdaptiveSmoother, SingleHandInfo, TrackingTelemetry
from modules.particles import ParticleSystem, RippleWave
import interface


class TestHandAndParticles(unittest.TestCase):

    def test_adaptive_smoother(self):
        np.random.seed(42)
        smoother = AdaptiveSmoother(min_alpha=0.2, max_alpha=0.9, vel_scale=5.0)

        # 1. Static position: check noise damping
        pos = np.array([10.0, 20.0, 30.0], dtype=np.float32)
        smoother.filter(pos, timestamp=0.0)
        
        noisy_results = []
        for i in range(1, 20):
            noise = np.random.uniform(-0.1, 0.1, size=3).astype(np.float32)
            filtered = smoother.filter(pos + noise, timestamp=i * 0.033)
            noisy_results.append(filtered)
        
        # Filtered output should stay close to original (within 0.10, suppressing noise fluctuations)
        diff = np.max(np.abs(noisy_results[-1] - pos))
        self.assertLess(diff, 0.10, f"Smoother failed to suppress static noise! Diff: {diff}")

        # 2. Fast movement: check agility
        fast_target = np.array([50.0, 60.0, 70.0], dtype=np.float32)
        filtered_fast = smoother.filter(fast_target, timestamp=20 * 0.033)
        dist_to_target = np.linalg.norm(fast_target - filtered_fast)
        self.assertLess(dist_to_target, 15.0)

    def test_particle_system(self):
        ps = ParticleSystem(count=60)
        self.assertEqual(len(ps.particles), 60)

        # Initial update
        fingertips = [(0.5, 0.5, 0.0), (0.6, 0.4, 0.1)]
        palms = [(0.5, 0.5, 0.0)]
        ps.update(dt=0.033, fingertips_3d=fingertips, palm_centers_3d=palms, gesture="OPEN_PALM")
        
        # Test collapse factor expansion on OPEN_PALM
        self.assertGreater(ps.collapse_factor, 1.0)

        # Test collapse on CLOSED_FIST
        for _ in range(30):
            ps.update(dt=0.033, fingertips_3d=fingertips, palm_centers_3d=palms, gesture="CLOSED_FIST")
        self.assertLess(ps.collapse_factor, 0.6)

        # Test ripples
        ps.trigger_ripple(x=200, y=200, max_radius=100)
        self.assertEqual(len(ps.ripples), 1)
        for _ in range(15):
            ps.update(dt=0.05, fingertips_3d=[], palm_centers_3d=[], gesture="NONE")
        # Ripple should finish and deactivate
        self.assertEqual(len(ps.ripples), 0)

    def test_interface_offline_render(self):
        ps = ParticleSystem(count=40)
        
        # Fake telemetry with 2 hands
        telemetry = TrackingTelemetry(
            hands_count=2,
            active_gesture="DUAL_OPEN_PALMS",
            gesture_event=None,
            drag_dx=0.01,
            drag_dy=-0.01,
            zoom_factor=1.05,
            hand_roll=0.15,
            hand_depth=0.25,
            fingertip_points=[(0.3, 0.4, 0.0), (0.7, 0.4, 0.0), (0.35, 0.35, 0.0), (0.65, 0.35, 0.0)],
            palm_points=[(0.3, 0.5, 0.0), (0.7, 0.5, 0.0)],
            status_label="2 HAND(S) // DUAL_OPEN_PALMS",
            confidence=0.92,
            preview_frame=np.zeros((240, 320, 3), dtype=np.uint8)
        )

        t0 = time.time()
        for frame_idx in range(10):
            now = t0 + frame_idx * 0.033
            img = interface.render(
                yaw=0.1 * frame_idx,
                pitch=0.15,
                zoom=1.0,
                t=now - t0,
                particle_system=ps,
                telemetry=telemetry
            )
            self.assertIsNotNone(img)
            self.assertEqual(img.shape, (interface.H, interface.W, 3))
            self.assertEqual(img.dtype, np.uint8)

            # Test scanline
            interface.draw_scanline(img, now - t0)

            # Test PIP
            interface.draw_camera_pip(img, telemetry.preview_frame, interface.K)


if __name__ == "__main__":
    unittest.main()
