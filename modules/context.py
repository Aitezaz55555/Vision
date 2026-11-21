"""
VISION AI - Conversation Context & State Memory Module
Maintains short-term conversational context, tracks immediate previous actions,
resolves pronoun references (e.g. 'it', 'that app', 'that folder'), and handles
safety confirmation flows for sensitive operations.
"""

import time
from typing import Optional, Dict, Any, Tuple


class ConversationContext:
    def __init__(self, max_history: int = 6):
        self.max_history = max_history
        self.last_action: Optional[str] = None
        self.last_app: Optional[str] = None
        self.last_site: Optional[str] = None
        self.last_search_platform: Optional[str] = "google"
        self.last_search_query: Optional[str] = None
        self.last_folder: Optional[str] = None
        self.last_file: Optional[str] = None
        self.last_spoken_reply: Optional[str] = None
        self.spoken_responses_enabled: bool = True
        
        # Pending confirmation for sensitive/destructive operations
        self.pending_confirmation: Optional[Dict[str, Any]] = None
        
        # Chronological turn history: list of dicts with timestamp, user, vision, intent
        self.turns = []

    def set_confirmation(self, action_type: str, callback_args: Dict[str, Any], prompt_msg: str):
        """Arm a sensitive action requiring explicit user confirmation."""
        self.pending_confirmation = {
            "type": action_type,
            "args": callback_args,
            "prompt": prompt_msg,
            "armed_at": time.time(),
        }

    def clear_confirmation(self):
        """Disarm any pending confirmation."""
        self.pending_confirmation = None

    def has_pending_confirmation(self, timeout_sec: float = 30.0) -> bool:
        """Returns True if a confirmation is waiting and has not expired."""
        if not self.pending_confirmation:
            return False
        if time.time() - self.pending_confirmation.get("armed_at", 0) > timeout_sec:
            self.pending_confirmation = None
            return False
        return True

    def update_action(self, intent: str, args: Dict[str, Any], reply: str):
        """Update recent action context after successful execution."""
        self.last_action = intent

        if intent in ("open_app", "close_app") and "app" in args:
            self.last_app = args["app"]
        elif intent == "open_site" and "site" in args:
            self.last_site = args["site"]
            if args["site"] in ("youtube", "google"):
                self.last_search_platform = args["site"]
        elif intent == "search":
            if "platform" in args:
                self.last_search_platform = args["platform"]
            if "query" in args:
                self.last_search_query = args["query"]
        elif intent in ("open_folder", "list_files") and "folder" in args:
            self.last_folder = args["folder"]
        elif intent == "open_file" and "file" in args:
            self.last_file = args["file"]

    def add_turn(self, user_text: str, vision_reply: str, intent: str):
        """Append a conversational turn and maintain bounded history."""
        self.last_spoken_reply = vision_reply
        self.turns.append({
            "timestamp": time.time(),
            "user": user_text,
            "vision": vision_reply,
            "intent": intent,
        })
        if len(self.turns) > self.max_history:
            self.turns.pop(0)

    def resolve_target(self, text: str) -> Tuple[Optional[str], str]:
        """
        Resolves ambiguous references like 'it', 'that app', 'the previous website', 'that folder'.
        Returns (resolved_value, category) e.g. ('chrome', 'app') or ('youtube', 'site').
        """
        import re
        t = text.lower().strip()
        # Strip action prefixes if present (e.g. 'close it' -> 'it')
        t = re.sub(r"^(?:close|quit|exit|kill|open|launch|start|explore|show|find)\s+", "", t).strip()
        
        # Check for app references
        if t in ("it", "that", "that app", "that application", "the app", "this app", "this application"):
            if self.last_app:
                return self.last_app, "app"
            if self.last_site:
                return self.last_site, "site"

        # Check for site/tab references
        if t in ("that website", "that site", "the site", "the website", "previous website", "previous site"):
            if self.last_site:
                return self.last_site, "site"

        # Check for folder references
        if t in ("that folder", "the folder", "the directory", "that directory", "it"):
            if self.last_folder:
                return self.last_folder, "folder"

        return None, "unknown"

    def get_last_topic(self) -> Optional[str]:
        """Extract primary subject/topic from the most recent conversational turn."""
        if not self.turns:
            return None
        last_turn = self.turns[-1]
        u = last_turn.get("user", "")
        import re
        clean = re.sub(
            r"^(?:can you |could you |please )?(?:explain|describe|tell me about|what is|what are|define|how does|why is|teach me about)\s+",
            "", u, flags=re.I
        ).strip(" ?.")
        return clean if clean else u.strip(" ?.")

    def augment_followup_query(self, query: str) -> str:
        """
        Connects short-term follow-up queries ('give me an example', 'make it simpler', 'now explain deletion')
        with the active topic from the preceding turn to preserve conversational continuity.
        """
        import re
        q = query.strip().rstrip(".?!")
        topic = self.get_last_topic()
        if not topic:
            return query

        # Pattern: "give me an example" / "show an example"
        if re.search(r"^(?:give (?:me )?(?:an? )?example|show (?:me )?an? example|another example)\b", q, re.I):
            return f"Give an illustrative, concrete example of {topic}."

        # Pattern: "make it simpler" / "simplify that"
        if re.search(r"^(?:make it (?:simpler|shorter|easier|brief)|simplify (?:it|that|this))\b", q, re.I):
            return f"Make the previous explanation of {topic} simpler and more concise."

        # Pattern: "now explain deletion" / "what about deletion"
        m_sub = re.search(r"^(?:now explain|what about|how about|explain)\s+([a-zA-Z0-9_\-\s]+)$", q, re.I)
        if m_sub:
            sub = m_sub.group(1).strip()
            if topic.lower() not in sub.lower():
                return f"Explain {sub} in the context of {topic}."

        # Pattern: "continue" / "tell me more"
        if re.search(r"^(?:continue|tell me more|go on|elaborate further)\b", q, re.I):
            return f"Continue elaborating further on {topic}."

        return q
