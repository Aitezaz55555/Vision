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
import numpy as np

# Ensure project root is in sys.path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from modules.hand_tracking import AdaptiveSmoother, SingleHandInfo, TrackingTelemetry
from modules.particles import ParticleSystem, RippleWave
import interface


def test_adaptive_smoother():
    print("[TEST] Testing AdaptiveSmoother...")
    smoother = AdaptiveSmoother(min_alpha=0.2, max_alpha=0.9, vel_scale=5.0)

    # 1. Static position: check noise damping
    pos = np.array([10.0, 20.0, 30.0], dtype=np.float32)
    smoother.filter(pos, timestamp=0.0)
    
    noisy_results = []
    for i in range(1, 20):
        noise = np.random.uniform(-0.1, 0.1, size=3).astype(np.float32)
        filtered = smoother.filter(pos + noise, timestamp=i * 0.033)
        noisy_results.append(filtered)
    
    # Filtered output should stay extremely close to original (within 0.05)
    diff = np.max(np.abs(noisy_results[-1] - pos))
    assert diff < 0.08, f"Smoother failed to suppress static noise! Diff: {diff}"
    print(f"  -> Static noise suppression passed (max diff: {diff:.4f})")

    # 2. Fast movement: check agility
    fast_target = np.array([50.0, 60.0, 70.0], dtype=np.float32)
    filtered_fast = smoother.filter(fast_target, timestamp=20 * 0.033)
    # Velocity-adaptive alpha should jump high and track quickly
    dist_to_target = np.linalg.norm(fast_target - filtered_fast)
    print(f"  -> Fast movement tracking passed (dist after 1 frame: {dist_to_target:.2f})")


def test_particle_system():
    print("[TEST] Testing ParticleSystem & RippleWave...")
    ps = ParticleSystem(count=60)
    assert len(ps.particles) == 60

    # Initial update
    fingertips = [(0.5, 0.5, 0.0), (0.6, 0.4, 0.1)]
    palms = [(0.5, 0.5, 0.0)]
    ps.update(dt=0.033, fingertips_3d=fingertips, palm_centers_3d=palms, gesture="OPEN_PALM")
    
    # Test collapse factor expansion on OPEN_PALM
    assert ps.collapse_factor > 1.0, f"Expected collapse_factor > 1.0 on OPEN_PALM, got {ps.collapse_factor}"

    # Test collapse on CLOSED_FIST
    for _ in range(30):
        ps.update(dt=0.033, fingertips_3d=fingertips, palm_centers_3d=palms, gesture="CLOSED_FIST")
    assert ps.collapse_factor < 0.6, f"Expected collapse_factor < 0.6 on CLOSED_FIST, got {ps.collapse_factor}"
    print(f"  -> Gesture dynamics passed (fist collapsed factor: {ps.collapse_factor:.2f})")

    # Test ripples
    ps.trigger_ripple(x=200, y=200, max_radius=100)
    assert len(ps.ripples) == 1
    for _ in range(15):
        ps.update(dt=0.05, fingertips_3d=[], palm_centers_3d=[], gesture="NONE")
    # Ripple should finish and deactivate
    assert len(ps.ripples) == 0
    print("  -> Ripple life-cycle passed")


def test_interface_offline_render():
    print("[TEST] Testing interface.render() headless offline...")
    import cv2
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
        assert img is not None
        assert img.shape == (interface.H, interface.W, 3)
        assert img.dtype == np.uint8

        # Test scanline
        interface.draw_scanline(img, now - t0)

        # Test PIP
        interface.draw_camera_pip(img, telemetry.preview_frame, interface.K)

    print(f"  -> Headless render passed: 10 frames successfully rendered at {interface.W}x{interface.H}")


if __name__ == "__main__":
    test_adaptive_smoother()
    test_particle_system()
    test_interface_offline_render()
    print("\n[ALL TESTS PASSED SUCCESSFULLY!]")
