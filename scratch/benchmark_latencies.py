"""
Benchmark actual latencies for VISION AI 1.2 components:
- Intent recognition latency (deterministic vs fallback)
- Application launch & discovery latency (cached vs filesystem)
- TTS synthesis & startup latency
- Barge-in interrupt response time
- Double-clap impulse verification time
"""

import os
import sys
import time

sys.path.insert(0, os.path.abspath("."))
import modules.router as router
import modules.apps as apps
import modules.clap as clap
import modules.context as context

print("=" * 65)
print("     VISION AI 1.2 - PERFORMANCE & LATENCY BENCHMARK")
print("=" * 65)

# 1. Intent Recognition Latency
ctx = context.ConversationContext()
queries = [
    "open chrome",
    "open whatsapp",
    "what is my battery percentage",
    "what time is it",
    "remind me to call John in 10 minutes",
    "increase the volume",
    "minimize window"
]

latencies = []
for q in queries:
    t0 = time.perf_counter()
    intent, args = router.match_deterministic_intent(q, ctx)
    dt_ms = (time.perf_counter() - t0) * 1000
    latencies.append(dt_ms)
    print(f"  [Intent] '{q[:35]:35}' -> {intent:18} in {dt_ms:.3f} ms")

avg_intent_ms = sum(latencies) / len(latencies)
print(f"  => Average Tier 1 Intent Recognition Latency: {avg_intent_ms:.3f} ms\n")

# 2. Application Resolution Latency
app_queries = ["whatsapp", "chatgpt", "chrome", "vscode", "calculator", "spotify"]
app_latencies = []
for a in app_queries:
    t0 = time.perf_counter()
    target = apps.find_application_path(a)
    dt_ms = (time.perf_counter() - t0) * 1000
    app_latencies.append(dt_ms)
    print(f"  [App Discovery] '{a:12}' -> {str(target)[:30]:30} in {dt_ms:.3f} ms")

avg_app_ms = sum(app_latencies) / len(app_latencies)
print(f"  => Average App Discovery Latency: {avg_app_ms:.3f} ms\n")

# 3. Double-Clap Math & Verification Latency
detector = clap.ClapDetector()
import numpy as np
fake_chunk = (np.random.randn(1024) * 50).astype(np.int16).tobytes()

clap_math_latencies = []
for _ in range(50):
    t0 = time.perf_counter()
    r, p, c = detector.calculate_metrics(fake_chunk)
    dt_ms = (time.perf_counter() - t0) * 1000
    clap_math_latencies.append(dt_ms)

avg_clap_ms = sum(clap_math_latencies) / len(clap_math_latencies)
print(f"  => Average Clap Chunk Analysis Time (1024 samples): {avg_clap_ms:.4f} ms")

print("=" * 65)
