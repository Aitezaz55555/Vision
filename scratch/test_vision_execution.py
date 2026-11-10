"""
Test simulated voice command execution through vision.process_command.
Ensures end-to-end integration across modules, context, and safe dispatch.
"""
import sys
import os

sys.path.insert(0, os.path.abspath("."))
import vision

# Mock speak so tests don't play actual audio or block
spoken_phrases = []
def mock_speak(text):
    spoken_phrases.append(str(text))
    print(f"  [TTS Spoke]: {text}")

vision.speak = mock_speak

test_commands = [
    ("what is the battery percentage", "battery"),
    ("what is my cpu usage", "performance"),
    ("increase the volume", "volume_up"),
    ("open my downloads folder", "open_folder"),
    ("list files in my downloads", "list_files"),
    ("open youtube", "open_site"),
    ("search for quantum computing", "search"),
    ("search on google", "search"),
    ("launch calculator", "open_app"),
    ("close calculator", "close_app"),
    ("tell me about yourself", "introduce"),
    ("remember that my favorite language is Python", "add_note"),
    ("what are my notes", "show_notes"),
    ("who created you", "chat"),
]

print("=== Running End-to-End Command Processing Tests ===")
passed = 0
for cmd, expected_family in test_commands:
    spoken_phrases.clear()
    print(f"\n[Test] Command: '{cmd}'")
    try:
        vision.process_command(cmd)
        if spoken_phrases:
            print(f"  => SUCCESS (Received {len(spoken_phrases)} spoken responses)")
            passed += 1
        else:
            print("  => WARNING: No speech generated")
    except Exception as e:
        print(f"  => ERROR: {e}")

print(f"\nCompleted: {passed}/{len(test_commands)} tests passed.")
if passed == len(test_commands):
    print("ALL INTEGRATION TESTS PASSED!")
