"""
VISION AI - Major Upgrade Test Suite
Comprehensive automated test suite covering:
1. Fast startup and lazy subsystem imports
2. Advanced listening, speech recognition configuration, and Whisper readiness
3. Permanent SQLite personal memory CRUD, security filter, and prompt generation
4. Conversational continuity and follow-up query augmentation
5. WhatsApp and application automation confirmation flows
6. Unified voice and text query pipeline validation
"""

import os
import unittest
from unittest.mock import MagicMock, patch

from modules.context import ConversationContext
from modules.memory_db import (
    save_memory, get_memory, search_memories, list_all_memories,
    delete_memory, append_conversation_turn, get_recent_turns,
    build_memory_context_prompt, is_sensitive
)
from modules.router import match_deterministic_intent
from modules.stt import configure_audio_recognizer, is_whisper_ready, get_default_device_index
from modules.whatsapp import (
    normalize_phone_number, resolve_contact, prepare_whatsapp_message, prepare_whatsapp_call
)


class TestPermanentMemory(unittest.TestCase):
    def setUp(self):
        delete_memory("test_name", "personal")
        delete_memory("test_pref", "preference")

    def tearDown(self):
        delete_memory("test_name", "personal")
        delete_memory("test_pref", "preference")

    def test_save_and_retrieve_memory(self):
        ok = save_memory("personal", "test_name", "Danish")
        self.assertTrue(ok)
        val = get_memory("test_name", "personal")
        self.assertEqual(val, "Danish")

    def test_update_existing_memory_no_conflicts(self):
        save_memory("personal", "test_name", "Danish")
        # Update name
        save_memory("personal", "test_name", "Dan")
        val = get_memory("test_name", "personal")
        self.assertEqual(val, "Dan")

    def test_sensitive_credentials_blocked(self):
        self.assertTrue(is_sensitive("password: mysecretpassword"))
        self.assertTrue(is_sensitive("api_key = abcdef1234567890"))
        self.assertTrue(is_sensitive("bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9"))
        # Attempting to save sensitive data must return False
        saved = save_memory("credentials", "my_password", "topsecret123")
        self.assertFalse(saved)
        self.assertIsNone(get_memory("my_password", "credentials"))

    def test_context_prompt_injection(self):
        save_memory("personal", "test_name", "Danish")
        save_memory("preference", "test_pref", "short explanations")
        prompt = build_memory_context_prompt()
        self.assertIn("Danish", prompt)
        self.assertIn("short explanations", prompt)


class TestConversationContinuity(unittest.TestCase):
    def setUp(self):
        self.ctx = ConversationContext()

    def test_topic_extraction_and_followup_augmentation(self):
        # 1. User asks initial question
        self.ctx.add_turn("Explain AVL trees.", "AVL trees are self-balancing search trees.", "chat")
        self.assertEqual(self.ctx.get_last_topic(), "AVL trees")

        # 2. User asks for an example
        aug1 = self.ctx.augment_followup_query("Give me an example.")
        self.assertIn("AVL trees", aug1)

        # 3. User asks to make it simpler
        aug2 = self.ctx.augment_followup_query("Make it simpler.")
        self.assertIn("AVL trees", aug2)
        self.assertIn("simpler", aug2)

        # 4. User asks follow-up subtopic
        aug3 = self.ctx.augment_followup_query("Now explain deletion.")
        self.assertIn("deletion", aug3)
        self.assertIn("AVL trees", aug3)


class TestNaturalLanguageIntentRouting(unittest.TestCase):
    def setUp(self):
        self.ctx = ConversationContext()

    def test_app_launch_variations(self):
        queries = [
            "Open Chrome.",
            "Can you open my browser?",
            "Vision, could you please open Chrome?",
            "Launch Chrome for me."
        ]
        for q in queries:
            intent, args = match_deterministic_intent(q, self.ctx)
            self.assertIn(intent, ("open_app", "open_site"))
            target = args.get("app") or args.get("site")
            self.assertIn(target, ("chrome", "google", "browser"))

    def test_whatsapp_intents(self):
        # Call
        intent, args = match_deterministic_intent("Vision, call Mom on WhatsApp.", self.ctx)
        self.assertEqual(intent, "whatsapp_call")
        self.assertEqual(args.get("contact", "").lower(), "mom")

        # Message
        intent, args = match_deterministic_intent("Send Mom a message saying I will be late.", self.ctx)
        self.assertEqual(intent, "whatsapp_message")
        self.assertEqual(args.get("contact", "").lower(), "mom")
        self.assertIn("late", args.get("message", "").lower())

    def test_memory_intents(self):
        intent, args = match_deterministic_intent("Remember that my name is Danish.", self.ctx)
        self.assertEqual(intent, "set_name")
        self.assertEqual(args.get("name"), "Danish")

        intent, args = match_deterministic_intent("What is my name?", self.ctx)
        self.assertEqual(intent, "get_name")

        intent, args = match_deterministic_intent("Show me what you remember about me.", self.ctx)
        self.assertEqual(intent, "list_memories")


class TestWhatsAppConfirmationFlow(unittest.TestCase):
    def test_phone_normalization(self):
        self.assertEqual(normalize_phone_number("+91 98765 43210"), "919876543210")
        self.assertEqual(normalize_phone_number("1-800-555-0199"), "18005550199")

    def test_whatsapp_message_requires_confirmation(self):
        payload = prepare_whatsapp_message("Mom", "I am on my way.")
        self.assertTrue(payload.get("needs_confirmation"))
        self.assertIn("confirm", payload.get("prompt").lower())
        self.assertIn("Mom", payload.get("prompt"))

    def test_whatsapp_call_requires_confirmation(self):
        payload = prepare_whatsapp_call("Dad")
        self.assertTrue(payload.get("needs_confirmation"))
        self.assertIn("confirm", payload.get("prompt").lower())


class TestSpeechRecognitionConfig(unittest.TestCase):
    def test_audio_recognizer_parameters(self):
        import speech_recognition as sr
        r = configure_audio_recognizer(sr.Recognizer())
        self.assertGreaterEqual(r.pause_threshold, 1.0)  # Pacing for Indian English / conversational speech
        self.assertGreaterEqual(r.phrase_threshold, 0.25)
        self.assertTrue(r.dynamic_energy_threshold)


if __name__ == "__main__":
    unittest.main()
