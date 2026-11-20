"""
VISION AI - Natural Voice Intelligence & Intent Understanding Test Suite
Tests:
- All 17 user conversational and control examples
- Natural language variation robustness (with/without wake words, polite prefixes)
- Immediate speech interruption ('stop', 'be quiet', 'cancel')
- System awareness (RAM, running apps, CPU)
- File, document, and notes discovery
- Contextual continuity & follow-ups
"""

import unittest
from modules.context import ConversationContext
from modules.router import match_deterministic_intent, clean_user_input


class TestNaturalVoiceAndIntents(unittest.TestCase):

    def setUp(self):
        self.context = ConversationContext()

    def test_clean_user_input(self):
        """Verify robust normalization of speech transcripts."""
        cases = [
            ("Vision, open Chrome.", ("open Chrome", "open chrome")),
            ("Hey Vision can you please find my DBMS notes?", ("find my DBMS notes", "find my dbms notes")),
            ("Vision, how much RAM is currently being used?", ("how much RAM is currently being used", "how much ram is currently being used")),
            ("Ok Vision, tell me what applications are running!", ("what applications are running", "what applications are running")),
            ("Vision, stop speaking.", ("stop speaking", "stop speaking")),
            ("Please summarise this PDF...", ("summarise this PDF", "summarise this pdf")),
        ]
        for inp, (expected_raw, expected_low) in cases:
            raw_c, low_c = clean_user_input(inp)
            self.assertEqual(raw_c, expected_raw)
            self.assertEqual(low_c, expected_low)

    def test_seventeen_user_examples(self):
        """Verifies the exact 17 natural user requests from the prompt."""
        test_cases = [
            ("Vision, open Chrome.", "open_app", "chrome"),
            ("Vision, can you find my DBMS notes?", "find_files", "dbms notes"),
            ("Vision, explain this concept.", "chat", None),
            ("Vision, search the internet for the latest developments in AI.", "search", "latest developments in ai"),
            ("Vision, what is happening in the technology world today?", "chat", None),
            ("Vision, open my project folder.", "open_folder", "project"),
            ("Vision, summarise this PDF.", "summarize_document", "pdf"),
            ("Vision, remind me about my assignment.", "add_reminder", "assignment"),
            ("Vision, how much RAM is currently being used?", "system_ram", None),
            ("Vision, tell me what applications are running.", "list_running_apps", None),
            ("Vision, stop speaking.", "tts_stop", None),
            ("Vision, repeat that.", "tts_repeat", None),
            ("Vision, make your explanation simpler.", "chat", None),
            ("Vision, compare these two approaches.", "chat", None),
            ("Vision, continue from where we stopped.", "tts_continue", None),
            ("Vision, I have another question.", "chat", None),
            ("Vision, remember this for our current project.", "add_project_note", None),
        ]

        for query, expected_intent, expected_arg_val in test_cases:
            intent, args = match_deterministic_intent(query, self.context)
            self.assertEqual(intent, expected_intent, f"Query '{query}' expected '{expected_intent}' but got '{intent}'")
            if expected_arg_val is not None:
                found_match = any(expected_arg_val in str(v).lower() for v in args.values())
                self.assertTrue(found_match, f"Expected '{expected_arg_val}' in args for query '{query}', got {args}")

    def test_barge_in_variations(self):
        """Immediate voice cancellation should always route to tts_stop."""
        barge_ins = [
            "stop", "stop speaking", "be quiet", "shut up", "cancel", "pause",
            "wait", "enough", "that's enough", "ruk jao", "ruko", "chup ho jao"
        ]
        for phrase in barge_ins:
            intent, _ = match_deterministic_intent(phrase, self.context)
            self.assertEqual(intent, "tts_stop", f"Barge-in '{phrase}' did not route to tts_stop")

    def test_dictation_mode_intents(self):
        """Dictation start/stop intents."""
        self.assertEqual(match_deterministic_intent("start dictation", self.context)[0], "dictation_start")
        self.assertEqual(match_deterministic_intent("enter dictation mode", self.context)[0], "dictation_start")
        self.assertEqual(match_deterministic_intent("stop dictation", self.context)[0], "dictation_stop")

    def test_system_awareness_queries(self):
        """RAM, CPU, and running apps variations."""
        ram_queries = ["how much ram is used", "check ram", "ram usage", "how much memory is free"]
        for q in ram_queries:
            self.assertEqual(match_deterministic_intent(q, self.context)[0], "system_ram")

        apps_queries = ["what apps are running", "what applications are open", "list running apps"]
        for q in apps_queries:
            self.assertEqual(match_deterministic_intent(q, self.context)[0], "list_running_apps")


if __name__ == "__main__":
    unittest.main()
