"""
VISION AI - Conversational Engine & Intent Pipeline Unit Tests
Verifies:
1. Intent routing separation: PC automation commands vs General conversational AI questions.
2. Follow-up handling and multi-turn context awareness.
3. Barge-in / speech interruption intent matching.
4. Spoken text formatting and cleaning.
5. Mode selection and message building.
"""

import unittest
from modules.context import ConversationContext
from modules.router import match_deterministic_intent
from modules.chat import detect_conversation_mode, build_system_prompt, prepare_chat_messages
from modules.tts_stream import clean_text_for_speech


class TestConversationPipeline(unittest.TestCase):

    def setUp(self):
        self.context = ConversationContext()

    def test_pc_control_commands_routing(self):
        """PC control commands must route to specific tool intents, not chat."""
        test_cases = [
            ("open chrome", "open_app", {"app": "chrome"}),
            ("launch notepad", "open_app", {"app": "notepad"}),
            ("close chrome", "close_app", {"app": "chrome"}),
            ("increase the volume", "volume_up", {}),
            ("decrease volume", "volume_down", {}),
            ("take a screenshot", "screenshot", {}),
            ("what time is it", "get_time", {}),
            ("today's date", "get_date", {}),
            ("open downloads folder", "open_folder", {"folder": "downloads"}),
            ("open youtube", "open_site", {"site": "youtube"}),
        ]
        for query, expected_intent, expected_args in test_cases:
            intent, args = match_deterministic_intent(query, self.context)
            self.assertEqual(intent, expected_intent, f"Failed for query: '{query}'")
            for k, v in expected_args.items():
                self.assertEqual(args.get(k), v, f"Arg mismatch for query: '{query}'")

    def test_conversational_questions_routing(self):
        """Conversational questions must route to 'chat'."""
        queries = [
            "What is Python?",
            "Explain quantum physics in simple terms",
            "Why is the sky blue?",
            "Tell me a story about a futuristic AI",
            "Tell me a funny joke",
            "How does a neural network work?",
            "Who was Alan Turing?",
            "Can you explain recursion with an example?",
            "Calculate 25 multiplied by 4",
            "What is the capital of France?",
            "Hello Vision how are you today?",
        ]
        for query in queries:
            intent, _ = match_deterministic_intent(query, self.context)
            self.assertEqual(intent, "chat", f"Query '{query}' should route to 'chat' but got '{intent}'")

    def test_follow_up_conversational_routing(self):
        """Follow-up questions after chat should route back to 'chat'."""
        # Establish prior chat turn
        self.context.add_turn("What is Python?", "Python is a high-level programming language.", "chat")

        follow_ups = [
            "Why?",
            "Give me an example",
            "Explain that again",
            "Make it shorter",
            "Tell me more",
            "How does that work?",
            "Another one",
        ]
        for fu in follow_ups:
            intent, _ = match_deterministic_intent(fu, self.context)
            self.assertEqual(intent, "chat", f"Follow-up '{fu}' should route to 'chat' but got '{intent}'")

    def test_barge_in_and_speech_control_intents(self):
        """Voice interruption commands must immediately route to 'tts_stop'."""
        stop_phrases = [
            "stop",
            "stop speaking",
            "be quiet",
            "shut up",
            "cancel",
            "listen",
            "continue",
            "ruk jao",
            "chup ho jao",
            "enough",
        ]
        for sp in stop_phrases:
            intent, _ = match_deterministic_intent(sp, self.context)
            self.assertEqual(intent, "tts_stop", f"Barge-in phrase '{sp}' must route to 'tts_stop', got '{intent}'")

    def test_spoken_text_cleaning(self):
        """Ensures raw markdown bold, bullets, code blocks, etc. are stripped for TTS."""
        raw_markdown = "**Python** is an *interpreted* language:\n- Easy to read\n- Powerful\n`print('hello')`"
        cleaned = clean_text_for_speech(raw_markdown)
        self.assertNotIn("**", cleaned)
        self.assertNotIn("- Easy", cleaned)
        self.assertNotIn("`", cleaned)
        self.assertIn("Python is an interpreted language", cleaned)

    def test_chat_mode_selection(self):
        """Verifies intelligent chat mode determination."""
        self.assertEqual(detect_conversation_mode("Explain in detail how backpropagation works"), "detailed")
        self.assertEqual(detect_conversation_mode("Tell me a funny joke"), "entertainment")
        self.assertEqual(detect_conversation_mode("What is the speed of light?"), "normal")

    def test_message_history_injection(self):
        """Verifies context history is injected for multi-turn dialogue."""
        self.context.add_turn("What is Python?", "Python is an interpreted programming language.", "chat")
        self.context.add_turn("Why is it interpreted?", "Because it executes code line by line.", "chat")

        mode, messages = prepare_chat_messages(
            user_prompt="Give me an example",
            context=self.context,
            memory={},
            assistant_name="Vision",
            creator_name="Sir"
        )
        # Should have system prompt + 2 past turns (4 messages) + current user message = 6 messages
        self.assertEqual(len(messages), 6)
        self.assertEqual(messages[0]["role"], "system")
        self.assertEqual(messages[1]["role"], "user")
        self.assertEqual(messages[1]["content"], "What is Python?")
        self.assertEqual(messages[2]["role"], "assistant")
        self.assertEqual(messages[3]["role"], "user")
        self.assertEqual(messages[3]["content"], "Why is it interpreted?")
        self.assertEqual(messages[5]["role"], "user")
        self.assertEqual(messages[5]["content"], "Give me an example")


if __name__ == "__main__":
    unittest.main()
