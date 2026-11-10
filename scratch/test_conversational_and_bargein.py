"""
Comprehensive Verification Suite for VISION AI Conversational Engine & Instant Barge-In
Tests:
1. clean_text_for_speech: Removes markdown bold, headers, code, bullet lists.
2. split_stream_into_sentences: Streaming sentence chunking, abbreviations, decimals.
3. detect_conversation_mode: Normal vs Detailed vs Entertainment modes.
4. prepare_chat_messages: Context injection, creator attribution, multi-turn history.
5. Instant Barge-In: Verification of millisecond stop latency, queue purging, and state transition.
6. Router Barge-in Intents: Pattern matching for all stop/interruption keywords.
7. Contextual follow-up and pronoun resolution.
"""

import os
import sys
import time
import threading

# Add workspace to path
WORKSPACE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if WORKSPACE not in sys.path:
    sys.path.insert(0, WORKSPACE)

from modules.context import ConversationContext
from modules.router import match_deterministic_intent
from modules.tts_stream import (
    clean_text_for_speech, split_stream_into_sentences,
    StreamingTTSManager, BARGE_IN_KEYWORDS
)
from modules.chat import (
    detect_conversation_mode, build_system_prompt, prepare_chat_messages
)


def test_clean_text_for_speech():
    print("[Test 1] Testing clean_text_for_speech...")
    raw = (
        "Here is the answer:\n"
        "# Summary\n"
        "**Black holes** are *extremely* dense objects.\n"
        "```python\nprint('hello')\n```\n"
        "- Point 1: Gravity is strong.\n"
        "- Point 2: Nothing escapes, not even light.\n"
        "Visit https://nasa.gov for more details."
    )
    cleaned = clean_text_for_speech(raw)
    assert "**" not in cleaned, "Bold markdown markers not removed"
    assert "```" not in cleaned, "Code fences not removed"
    assert "#" not in cleaned, "Header hashes not removed"
    assert "https://" not in cleaned, "Raw URL not cleaned"
    assert "Black holes are extremely dense objects" in cleaned, "Core content lost"
    print("  -> Passed clean_text_for_speech verification.")


def test_sentence_boundary_splitting():
    print("[Test 2] Testing sentence boundary streaming splitter...")
    tokens = [
        "Good ", "morning ", "Sir. ", "Dr. ", "Smith ", "said ",
        "that ", "pi ", "is ", "approximately ", "3.14 ", "in ", "mathematics! ",
        "Isn't ", "that ", "fascinating? ", "Let ", "us ", "explore ", "further."
    ]

    def token_gen():
        for t in tokens:
            yield t

    cancel_event = threading.Event()
    sentences = list(split_stream_into_sentences(token_gen(), cancel_event))
    print("  -> Extracted sentences:", sentences)

    assert len(sentences) >= 3, f"Expected at least 3 sentences, got {len(sentences)}"
    assert any("Good morning Sir." in s for s in sentences), "First sentence missed"
    # Verify Dr. Smith did not split on Dr.
    assert any("Dr. Smith" in s for s in sentences), "Split erroneously on abbreviation 'Dr.'"
    # Verify 3.14 did not split on decimal
    assert any("3.14" in s for s in sentences), "Split erroneously on decimal 3.14"
    print("  -> Passed sentence boundary streaming verification.")


def test_conversation_mode_detection():
    print("[Test 3] Testing conversation mode detection...")
    assert detect_conversation_mode("Can you explain in detail how neural networks work?") == "detailed"
    assert detect_conversation_mode("Give me a step by step breakdown of photosynthesis") == "detailed"
    assert detect_conversation_mode("Tell me a funny joke") == "entertainment"
    assert detect_conversation_mode("Tell me a sci-fi story about robots") == "entertainment"
    assert detect_conversation_mode("Share an interesting fact about space") == "entertainment"
    assert detect_conversation_mode("What is the capital of France?") == "normal"
    assert detect_conversation_mode("How are you feeling today?") == "normal"
    print("  -> Passed conversation mode detection verification.")


def test_chat_messages_and_attribution():
    print("[Test 4] Testing chat messages and creator attribution...")
    ctx = ConversationContext()
    ctx.add_turn("Tell me about black holes", "Black holes are regions of spacetime where gravity is strong.", "chat")

    memory = {
        "name": "Taha",
        "notes": ["Likes astronomy", "Working on AI"],
        "last_conversation": []
    }

    mode, messages = prepare_chat_messages(
        user_prompt="How are they formed?",
        context=ctx,
        memory=memory,
        assistant_name="Vision",
        creator_name="Shaikh Taha"
    )

    system_content = messages[0]["content"]
    assert "Shaikh Taha" in system_content, "Creator attribution missing from system prompt"
    assert "Vision" in system_content, "Assistant name missing from system prompt"
    assert "Taha" in system_content, "User name missing from system prompt"
    assert "Likes astronomy" in system_content, "User notes missing from system prompt"

    # Verify recent context turn was included
    assert any(m.get("content") == "Tell me about black holes" for m in messages), "Previous turn user prompt missing"
    assert any("Black holes are regions" in m.get("content", "") for m in messages), "Previous turn assistant reply missing"
    # Verify current prompt is at end
    assert messages[-1]["content"] == "How are they formed?"
    print("  -> Passed multi-turn chat messages and attribution verification.")


def test_deterministic_router_bargein():
    print("[Test 5] Testing intent router barge-in keywords...")
    ctx = ConversationContext()

    stop_phrases = [
        "stop",
        "stop speaking",
        "be quiet",
        "shut up",
        "shutup",
        "that's enough",
        "thats enough",
        "enough",
        "cancel",
        "pause",
        "ruk jao",
        "ruko",
        "chup",
        "chup raho",
    ]

    for phrase in stop_phrases:
        intent, _ = match_deterministic_intent(phrase, ctx)
        assert intent == "tts_stop", f"Phrase '{phrase}' expected 'tts_stop', got '{intent}'"

    # Verify 'stop vision' terminates vision, not tts_stop
    intent, _ = match_deterministic_intent("stop vision", ctx)
    assert intent == "stop", f"Phrase 'stop vision' expected 'stop', got '{intent}'"
    print("  -> Passed deterministic router barge-in keyword verification.")


def test_instant_barge_in_latency():
    print("[Test 6] Testing instant barge-in latency and queue cancellation...")
    state_log = []

    def mock_state_callback(state, text="", result=""):
        state_log.append((state, time.time()))

    tts = StreamingTTSManager(
        state_callback=mock_state_callback
    )

    # Simulate 5 sentences streaming in
    def fake_stream():
        for i in range(1, 6):
            if tts.cancel_event.is_set():
                break
            time.sleep(0.04)
            yield f"This is sentence number {i} of the long AI response."

    # Launch playback in background thread
    playback_results = []

    def run_playback():
        res = tts.speak_stream(fake_stream())
        playback_results.append(res)

    t_thread = threading.Thread(target=run_playback, daemon=True)
    t_start = time.time()
    t_thread.start()

    # Let it start playing
    time.sleep(0.08)

    # TRIGGER IMMEDIATE BARGE-IN
    t_interrupt = time.time()
    tts.interrupt(reason="test barge in")
    t_interrupted_done = time.time()

    latency_ms = (t_interrupted_done - t_interrupt) * 1000.0
    print(f"  -> Measured Barge-In Interruption Latency: {latency_ms:.2f} ms")

    t_thread.join(timeout=1.0)

    assert not t_thread.is_alive(), "Playback thread did not exit promptly"
    assert tts.cancel_event.is_set(), "Cancel event was not set"
    assert not tts.is_playing.is_set(), "is_playing was not cleared"

    # Verify state callback received 'interrupted'
    states = [s[0] for s in state_log]
    assert "interrupted" in states, f"Interrupted state not recorded in states: {states}"

    # Latency requirement: barge-in execution must be sub-100ms
    assert latency_ms < 100.0, f"Barge-in latency too high: {latency_ms} ms"
    print("  -> Passed instant barge-in latency verification.")


def test_contextual_follow_up():
    print("[Test 7] Testing contextual pronoun and target resolution...")
    ctx = ConversationContext()
    ctx.update_action("open_app", {"app": "chrome"}, "Opening Google Chrome")

    target, category = ctx.resolve_target("close it")
    assert target == "chrome" and category == "app", f"Failed to resolve 'it' to chrome: {target}, {category}"

    ctx.update_action("open_site", {"site": "youtube"}, "Opening YouTube")
    target, category = ctx.resolve_target("that website")
    assert target == "youtube" and category == "site", f"Failed to resolve 'that website' to youtube: {target}, {category}"

    ctx.update_action("open_folder", {"folder": "downloads"}, "Opening Downloads folder")
    target, category = ctx.resolve_target("that folder")
    assert target == "downloads" and category == "folder", f"Failed to resolve 'that folder' to downloads: {target}, {category}"

    print("  -> Passed contextual target resolution verification.")


def main():
    print("=" * 60)
    print(">> RUNNING VISION AI CONVERSATIONAL & BARGE-IN TEST SUITE <<")
    print("=" * 60)

    test_clean_text_for_speech()
    test_sentence_boundary_splitting()
    test_conversation_mode_detection()
    test_chat_messages_and_attribution()
    test_deterministic_router_bargein()
    test_instant_barge_in_latency()
    test_contextual_follow_up()

    print("\n" + "=" * 60)
    print(">> ALL 7/7 ADVANCED CONVERSATIONAL & BARGE-IN TESTS PASSED! <<")
    print("=" * 60)


if __name__ == "__main__":
    main()
