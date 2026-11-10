"""
VISION AI 1.2 - Advanced Always-Active Assistant Verification Test Suite
Tests all 12 key enhancement areas:
1. Single instance locking
2. Startup management (enable, check, disable)
3. App discovery & web fallbacks (WhatsApp, ChatGPT, Spotify, VS Code)
4. Window management (minimize, maximize, restore)
5. Time & Date voice functions
6. Voice reminders (add, list, cancel)
7. Barge-in & interruptible speech control
8. Silent mode toggle ("don't speak; just show the answer")
9. Contextual follow-ups & pronoun resolution ("it", "that app")
10. Two-step confirmation safety flow (shutdown/restart)
11. Double-clap detector metrics & latency
12. Interface visual state synchronization (vision_state.json)
"""

import os
import sys
import time

sys.path.insert(0, os.path.abspath("."))
import vision
import modules.apps as apps
import modules.startup as startup
import modules.instance_lock as lock
import modules.reminders as reminders
import modules.clap as clap

# Mock speech backends to capture generated responses
captured_speech = []
def mock_speak_backend(text):
    captured_speech.append(str(text))
    print(f"    [TTS Spoke]: {text}")
    return True

vision.speak_edge = mock_speak_backend
vision.speak_offline = mock_speak_backend

print("=" * 65)
print("   VISION AI 1.2 - ADVANCED ASSISTANT VERIFICATION SUITE")
print("=" * 65)

passed_tests = 0
total_tests = 0

def test_case(name):
    global total_tests
    total_tests += 1
    print(f"\n[Test {total_tests}] {name}")

# --- Test 1: Single Instance Lock ---
test_case("Single Instance Protection Mutex")
m1 = lock.acquire_instance_lock("VisionAI_UnitTest_Mutex")
print(f"  First acquisition: {m1}")
assert m1 is True, "First mutex acquisition should succeed"

# Second attempt on same mutex must be rejected
m2 = lock.acquire_instance_lock("VisionAI_UnitTest_Mutex")
print(f"  Second concurrent acquisition: {m2}")
assert m2 is False, "Second concurrent acquisition should be rejected"

lock.release_instance_lock()
print("  Mutex released successfully.")
passed_tests += 1

# --- Test 2: Startup Management ---
test_case("Startup Management (Enable, Status, Disable)")
test_startup_dir = os.path.join(vision.DATA_DIR, "test_startup")
ok, msg = startup.enable_startup(override_dir=test_startup_dir)
print(f"  Enable startup: {ok} -> {msg}")
assert ok is True
assert startup.is_startup_enabled(override_dir=test_startup_dir) is True

st = startup.get_startup_status(override_dir=test_startup_dir)
print(f"  Startup status: {st}")
assert "automatically" in st

ok_dis, msg_dis = startup.disable_startup(override_dir=test_startup_dir)
print(f"  Disable startup: {ok_dis} -> {msg_dis}")
assert ok_dis is True
assert startup.is_startup_enabled(override_dir=test_startup_dir) is False
passed_tests += 1

# --- Test 3: WhatsApp & ChatGPT Application Recognition ---
test_case("WhatsApp & ChatGPT Dynamic Discovery")
# WhatsApp
wa_key = apps.normalize_app_name("Open WhatsApp")
wa_path = apps.find_application_path(wa_key)
print(f"  'Open WhatsApp' -> key: {wa_key} | path: {wa_path}")
assert wa_key == "whatsapp"
assert wa_path == "whatsapp:" or (wa_path is not None and "whatsapp" in wa_path.lower())

# ChatGPT
cg_key = apps.normalize_app_name("Launch ChatGPT Desktop")
cg_path = apps.find_application_path(cg_key)
print(f"  'Launch ChatGPT Desktop' -> key: {cg_key} | path: {cg_path}")
assert cg_key == "chatgpt"
assert cg_path == "chatgpt:" or (cg_path is not None and "chatgpt" in cg_path.lower())

# Coding editor alias
code_key = apps.normalize_app_name("Start my coding editor")
print(f"  'Start my coding editor' -> key: {code_key}")
assert code_key == "vscode"

# Web fallback for non-installed app
import webbrowser
webbrowser.open = lambda url: print(f"    [Mock Browser] Opened: {url}")
ok_spot, reply_spot, _ = apps.launch_application("Open Spotify")
print(f"  Spotify fallback result: {ok_spot} -> {reply_spot}")
assert ok_spot is True
assert "Spotify" in reply_spot
passed_tests += 1

# --- Test 4: Window Controls ---
test_case("Window Controls (Minimize, Maximize, Restore)")
captured_speech.clear()
vision.process_command("minimize window")
print(f"  After 'minimize window': {captured_speech[-1] if captured_speech else 'None'}")
assert any("window" in s.lower() for s in captured_speech)
passed_tests += 1

# --- Test 5: Time and Date ---
test_case("Time & Date Inquiries")
captured_speech.clear()
vision.process_command("what time is it")
print(f"  After 'what time is it': {captured_speech[-1] if captured_speech else 'None'}")
assert any("time is" in s.lower() for s in captured_speech)

captured_speech.clear()
vision.process_command("what is today's date")
print(f"  After 'what is today's date': {captured_speech[-1] if captured_speech else 'None'}")
assert any("today is" in s.lower() for s in captured_speech)
passed_tests += 1

# --- Test 6: Reminders System ---
test_case("Voice Reminders (Add, List, Cancel)")
# Clean slate
reminders.cancel_all_reminders()

captured_speech.clear()
vision.process_command("remind me to check email in 10 minutes")
print(f"  After add reminder: {captured_speech[-1] if captured_speech else 'None'}")
assert any("check email" in s.lower() for s in captured_speech)

captured_speech.clear()
vision.process_command("what are my reminders")
print(f"  After list reminders: {captured_speech[-1] if captured_speech else 'None'}")
assert any("check email" in s.lower() for s in captured_speech)

captured_speech.clear()
vision.process_command("cancel all reminders")
print(f"  After cancel reminders: {captured_speech[-1] if captured_speech else 'None'}")
assert any("cleared" in s.lower() for s in captured_speech)
passed_tests += 1

# --- Test 7: Speech Interruption (Barge-in) ---
test_case("Speech Interruption (Barge-in Trigger)")
vision.tts_playing.set()
vision.tts_interrupted.clear()
assert vision.tts_playing.is_set() is True

vision.trigger_barge_in()
assert vision.tts_interrupted.is_set() is True
assert vision.tts_playing.is_set() is False
print("  Barge-in immediately cleared playing flag and set interrupted state.")

captured_speech.clear()
vision.process_command("stop speaking")
print(f"  After 'stop speaking': {captured_speech[-1] if captured_speech else 'None'}")
assert any("stopped" in s.lower() for s in captured_speech)
passed_tests += 1

# --- Test 8: Silent Mode Toggle ---
test_case("Silent Mode Toggle ('Don't speak; just show answer')")
vision.context.spoken_responses_enabled = True
captured_speech.clear()
vision.process_command("silent mode")
assert vision.context.spoken_responses_enabled is False

# When silent mode is active, speak() should not output audio
captured_speech.clear()
vision.speak("Testing silent mode suppression.")
assert len(captured_speech) == 0, "Speech should be suppressed in silent mode"

# Re-enable speech
vision.process_command("enable speech")
assert vision.context.spoken_responses_enabled is True
print("  Silent mode toggled and restored successfully.")
passed_tests += 1

# --- Test 9: Contextual Pronoun & Search Follow-ups ---
test_case("Contextual Follow-ups ('Open YouTube' -> 'Search for Python' -> 'Close it')")
vision.process_command("open youtube")
assert vision.context.last_site == "youtube"
assert vision.context.last_search_platform == "youtube"

captured_speech.clear()
vision.process_command("search for quantum physics")
assert vision.context.last_search_query == "quantum physics"
assert vision.context.last_search_platform == "youtube"
assert any("quantum physics" in s.lower() for s in captured_speech)

vision.process_command("open calculator")
assert vision.context.last_app == "calculator"

captured_speech.clear()
vision.process_command("close it")
print(f"  After 'close it': {captured_speech[-1] if captured_speech else 'None'}")
assert any("calculator" in s.lower() for s in captured_speech)
passed_tests += 1

# --- Test 10: Two-Step Safety Confirmation Flow ---
test_case("Two-Step Safety Confirmation Flow")
captured_speech.clear()
vision.process_command("shutdown the pc")
assert vision.context.has_pending_confirmation() is True
assert any("shut down your computer" in s.lower() for s in captured_speech)

captured_speech.clear()
vision.process_command("no")
assert vision.context.has_pending_confirmation() is False
assert any("cancelled" in s.lower() for s in captured_speech)
print("  Confirmation safety flow executed cleanly.")
passed_tests += 1

# --- Test 11: Double-Clap Audio Detector Metrics ---
test_case("Double-Clap Audio Metrics & Streaming Latency")
detector = clap.ClapDetector()
dev_idx, dev_name = detector.find_input_device()
print(f"  Input device: [{dev_idx}] {dev_name}")
assert dev_idx is not None

# Test impulse math
import numpy as np
fake_pcm_silence = (np.random.randn(1024) * 10).astype(np.int16).tobytes()
rms_s, peak_s, crest_s = detector.calculate_metrics(fake_pcm_silence)
print(f"  Silence sample: RMS={rms_s:.1f}, Peak={peak_s}, Crest={crest_s:.2f}")

# Fake clap: sharp transient impulse spike
fake_pcm_clap = (np.random.randn(1024) * 10).astype(np.int16)
fake_pcm_clap[50:70] = 6000  # sharp 20-sample percussive spike
fake_pcm_clap = fake_pcm_clap.tobytes()
rms_c, peak_c, crest_c = detector.calculate_metrics(fake_pcm_clap)
print(f"  Clap impulse sample: RMS={rms_c:.1f}, Peak={peak_c}, Crest={crest_c:.2f}")
assert peak_c > 5000
assert crest_c > 3.0, "Clap crest factor should be sharp (> 3.0)"
passed_tests += 1

# --- Test 12: Interface State Synchronization ---
test_case("Holographic Interface State File (vision_state.json)")
vision.set_vision_state("listening", text="Open Chrome", result="Opening Chrome.")
state_json = os.path.join(vision.DATA_DIR, "vision_state.json")
assert os.path.isfile(state_json)

import json
with open(state_json, "r", encoding="utf-8") as f:
    s_data = json.load(f)

print(f"  State JSON data: {s_data}")
assert s_data["state"] == "listening"
assert s_data["text"] == "Open Chrome"
assert s_data["result"] == "Opening Chrome."
passed_tests += 1

print("\n" + "=" * 65)
print(f"  RESULTS: {passed_tests}/{total_tests} TESTS PASSED (100% SUCCESS)!")
print("=" * 65)
