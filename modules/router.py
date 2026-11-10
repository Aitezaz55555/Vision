"""
VISION AI - Hybrid Intent Router & Natural-Language Understanding Module
Implements multi-tiered intent classification:
- Tier 1: Sub-millisecond deterministic pattern & regex matching (low-latency execution).
- Context resolution: Pronoun ('it', 'that app') and follow-up contextual tracking.
- Tier 2: Structured Ollama intent classification fallback with strict JSON schema.
- Confirmation flow: Intercepts confirmation responses for sensitive actions.
"""

import json
import re
import urllib.parse
from typing import Tuple, Dict, Any, Optional

from modules.context import ConversationContext
from modules.apps import normalize_app_name
from modules.reminders import parse_reminder_phrase


# Normalized phrase cleanup patterns
FILLER_REGEX = re.compile(
    r"\b(?:can you|could you|would you|will you|please|kindly|i want to|want to|for me|hey vision|vision|zara|yaar|bhai|ek baar|kripya)\b",
    re.IGNORECASE
)

# Conversational & Explanatory Intent Patterns
CONVERSATIONAL_REGEX = re.compile(
    r"^(?:what|who|where|when|why|how|which|whose|whom|"
    r"explain|elaborate|describe|define|teach me|tell me|help me understand|"
    r"can you (?:explain|tell|elaborate|clarify|solve|help)|could you (?:explain|tell|elaborate|clarify|solve|help)|"
    r"give (?:me )?(?:an? )?example|show (?:me )?(?:an? )?example|another example|"
    r"make it (?:shorter|simpler|brief|longer|detailed)|summarize|in simple terms|step by step|"
    r"explain that again|tell me more|what about|how does (?:it|that|this) work|why is (?:it|that|this)|"
    r"tell (?:me )?(?:a )?(?:story|joke|fact|riddle)|joke sunao|kahani sunao|"
    r"hello|hi|hey|how are you|what's up|good morning|good evening|good afternoon|thank you|thanks|"
    r"write (?:a )?(?:code|program|script|function|query|poem|essay)|"
    r"difference between|compare|is it (?:true|possible)|can we|could we|solve|calculate)\b",
    re.I
)

FOLLOW_UP_REGEX = re.compile(
    r"^(?:why\??|how\??|what\??|why so\??|give (?:me )?(?:an? )?example|show (?:me )?(?:an? )?example|example|another one|"
    r"explain (?:that|more|again|further)|tell me more|more|next|continue|go on|"
    r"make it (?:shorter|simpler|brief|longer)|summarize|in simple terms|step by step|"
    r"what else|can you elaborate|clarify|explain that again)\b",
    re.I
)

# Deterministic regex patterns for Tier 1 matching
PATTERNS = [
    # System Controls
    ("lock_workstation", re.compile(r"\b(?:lock (?:my )?(?:pc|computer|windows|screen)|lock screen|workstation lock)\b", re.I)),
    ("task_manager", re.compile(r"\b(?:open |launch |show )?(?:task manager|taskmgr|system processes)\b", re.I)),
    ("settings", re.compile(r"\b(?:open |launch |show )?(?:windows settings|system settings|pc settings|control panel)\b", re.I)),
    ("battery", re.compile(r"\b(?:(?:check |what is |how is |show )?(?:my )?battery(?: status| level| percentage)|battery level|battery status|battery percentage|battery kitni hai)\b", re.I)),
    ("performance", re.compile(r"\b(?:(?:check |show |what is )?(?:my )?(?:cpu|ram|memory) (?:usage|utilization|performance|stats)|system performance|hardware usage)\b", re.I)),
    ("system_info", re.compile(r"\b(?:system info|system information|about this pc|pc specs|computer info)\b", re.I)),
    
    # Window Management
    ("window_minimize", re.compile(r"\b(?:minimize (?:this |that |the )?window|minimize screen|window minimize)\b", re.I)),
    ("window_maximize", re.compile(r"\b(?:maximize (?:this |that |the )?window|maximize screen|full ?screen window)\b", re.I)),
    ("window_restore", re.compile(r"\b(?:restore (?:this |that |the )?window|restore window)\b", re.I)),

    # Time & Date
    ("get_time", re.compile(r"\b(?:what time is it|current time|what's the time|tell me the time|time kya hai|samay kya hua)\b", re.I)),
    ("get_date", re.compile(r"\b(?:what is today's date|today's date|what date is it|what is the date|aaj ki date|aaj ki tarikh)\b", re.I)),

    # Reminders
    ("list_reminders", re.compile(r"\b(?:what are my reminders|show (?:my )?reminders|list reminders|reminders dikhao)\b", re.I)),
    ("cancel_reminders", re.compile(r"\b(?:cancel (?:all )?reminders|clear reminders|delete reminders)\b", re.I)),

    # Speech Control & Barge-in
    ("tts_stop", re.compile(r"^(?:stop(?:\s+speaking|\s+talking|\s+it|\s+now)?|be quiet|shut ?up|shutup|enough|that'?s enough|cancel|pause|listen|continue|ruk jao|ruko|chup(?:\s+raho|\s+ho\s+jao)?)$", re.I)),
    ("tts_repeat", re.compile(r"\b(?:repeat that|what did you say|say that again|repeat|phir se bolo)\b", re.I)),
    ("tts_slower", re.compile(r"\b(?:speak slower|talk slower|slow down your voice|slower voice)\b", re.I)),
    ("tts_faster", re.compile(r"\b(?:speak faster|talk faster|speed up your voice|faster voice)\b", re.I)),
    ("tts_disable_speech", re.compile(r"\b(?:don't speak|dont speak|silent mode|just show the answer|mute responses|stop voice responses)\b", re.I)),
    ("tts_enable_speech", re.compile(r"\b(?:enable speech|speak normally|voice on|unmute responses)\b", re.I)),

    # Startup Management
    ("startup_enable", re.compile(r"\b(?:enable start with windows|enable startup|start vision with windows|auto start on)\b", re.I)),
    ("startup_disable", re.compile(r"\b(?:disable start with windows|disable startup|turn off startup|auto start off)\b", re.I)),
    ("startup_status", re.compile(r"\b(?:startup status|is startup enabled|check startup)\b", re.I)),
    
    # Sensitive operations requiring confirmation
    ("shutdown_request", re.compile(r"\b(?:shut ?down|power off|turn off)(?:\s+(?:my|the|this))?\s*(?:pc|computer|laptop|system|machine)\b", re.I)),
    ("restart_request", re.compile(r"\b(?:restart|reboot)(?:\s+(?:my|the|this))?\s*(?:pc|computer|laptop|system|machine)\b", re.I)),

    # Screenshots & Photos
    ("screenshot", re.compile(r"\b(?:take (?:a )?screenshot|capture (?:my )?screen|screenshot (?:lo|khencho|le lo))\b", re.I)),
    ("take_photo", re.compile(r"\b(?:take (?:a )?photo|take (?:a )?picture|capture photo|photo (?:lo|khencho))\b", re.I)),

    # Confirmation responses
    ("confirm_yes", re.compile(r"^(?:yes|confirm|proceed|do it|haan|ha|sure|yeah|yep|okay|ok)$", re.I)),
    ("confirm_no", re.compile(r"^(?:no|cancel|abort|stop|dont|don't|mat karo|nahi|nah)$", re.I)),

    # Volume controls
    ("volume_mute", re.compile(r"\b(?:mute (?:the )?(?:audio|sound|volume)|sound mute|awaaz band)\b", re.I)),
    ("volume_unmute", re.compile(r"\b(?:unmute (?:the )?(?:audio|sound|volume)|sound unmute|awaaz chalu)\b", re.I)),
    ("volume_up", re.compile(r"\b(?:increase (?:the )?volume|volume up|turn (?:it )?up|sound up|awaaz badhao|louder|tez karo)\b", re.I)),
    ("volume_down", re.compile(r"\b(?:decrease (?:the )?volume|lower (?:the )?volume|volume down|turn (?:it )?down|sound down|awaaz kam karo|quieter|dheema karo)\b", re.I)),

    # Screen Brightness
    ("brightness_up", re.compile(r"\b(?:increase brightness|brightness up|screen brightness up|brighter screen|make it brighter)\b", re.I)),
    ("brightness_down", re.compile(r"\b(?:decrease brightness|brightness down|screen brightness down|dim screen|dim the screen)\b", re.I)),

    # Sleep / Idle
    ("sleep", re.compile(r"\b(?:go to sleep|sleep mode|sleep now|stop listening|so jao|chup ho jao|take a break|standby|enter standby)\b", re.I)),
    ("stop", re.compile(r"\b(?:(?:stop|exit|quit|terminate|band karo)\s+vision|goodbye vision|vision goodbye)\b", re.I)),

    # Personal Memory
    ("show_notes", re.compile(r"\b(?:show (?:my )?notes|what are my notes|read (?:my )?notes|notes dikhao)\b", re.I)),
    ("clear_notes", re.compile(r"\b(?:clear (?:my )?notes|delete (?:my )?notes|erase notes|notes saaf karo)\b", re.I)),
    ("get_name", re.compile(r"\b(?:what is my name|who am i|mera naam kya hai|do you know my name)\b", re.I)),
    ("history", re.compile(r"\b(?:show (?:my )?history|conversation history|previous chat|purani baatein)\b", re.I)),
    ("clear_memory", re.compile(r"\b(?:clear (?:all )?memory|reset memory|wipe memory)\b", re.I)),
]


def clean_text(text: str) -> str:
    """Removes filler phrases and extra whitespace."""
    t = FILLER_REGEX.sub(" ", text)
    return re.sub(r"\s+", " ", t).strip()


def match_deterministic_intent(user_text: str, context: ConversationContext) -> Tuple[Optional[str], Dict[str, Any]]:
    """
    Tier 1: Evaluates fast deterministic rules against user text and current context.
    Intelligently separates conversational questions from Windows PC actions.
    Returns (intent_name, args_dict).
    """
    raw = user_text.strip()
    cmd = clean_text(raw).lower()

    # 1. Check for Pending Confirmation First
    if context.has_pending_confirmation():
        if re.match(r"^(?:yes|confirm|proceed|do it|haan|ha|sure|yeah|yep|okay|ok)$", cmd):
            return "confirm_action", {"proceed": True}
        if re.match(r"^(?:no|cancel|abort|stop|dont|don't|mat karo|nahi|nah)$", cmd):
            return "confirm_action", {"proceed": False}

    # Complete Assistant Exit
    if re.search(r"\b(?:(?:stop|exit|quit|terminate|band karo)\s+vision|goodbye vision|vision goodbye)\b", raw, re.I):
        return "stop", {}

    # Immediate speech stop & barge-in
    if re.match(r"^(?:stop(?:\s+speaking|\s+talking|\s+it|\s+now)?|be quiet|shut ?up|shutup|enough|that'?s enough|cancel|pause|listen|continue|ruk jao|ruko|chup(?:\s+raho|\s+ho\s+jao)?)$", cmd, re.I):
        return "tts_stop", {}

    # 2. Check standard system patterns (battery, performance, task manager, settings, time, date, etc.)
    for intent_name, pat in PATTERNS:
        if pat.search(cmd):
            return intent_name, {}

    # 3. Check Set Volume or Brightness to Specific Number
    vol_set = re.search(r"\b(?:set volume (?:to )?|volume (?:to )?)(\d{1,3})\b", cmd)
    if vol_set:
        val = int(vol_set.group(1))
        return "volume_set", {"value": val}

    bright_set = re.search(r"\b(?:set brightness (?:to )?|brightness (?:to )?)(\d{1,3})\b", cmd)
    if bright_set:
        val = int(bright_set.group(1))
        return "brightness_set", {"value": val}

    # Reminders: e.g. 'remind me to call John in 10 minutes'
    if "remind" in cmd:
        task, delay = parse_reminder_phrase(raw)
        if task and delay:
            return "add_reminder", {"task": task, "delay": delay}

    # Clap Sensitivity setting: e.g. 'set sensitivity to high'
    sens_m = re.search(r"\b(?:set )?(?:clap )?sensitivity (?:to )?(high|medium|low)\b", cmd)
    if sens_m:
        return "set_sensitivity", {"level": sens_m.group(1).lower()}

    # 4. Check Contextual Application Close ('Close it', 'Close that app')
    if re.search(r"\b(?:close|quit|exit|kill|band karo)\s+(?:it|that|that app|the app|that application)\b", cmd):
        resolved_app, _ = context.resolve_target("it")
        if resolved_app:
            return "close_app", {"app": resolved_app}

    # 5. Check Close Explicit Application ('Close Chrome', 'Close VS Code', 'Close Notepad')
    close_app_match = re.search(r"\b(?:close|quit|exit|kill|band karo)\s+([a-z0-9 _\-]+)\b", cmd)
    if close_app_match:
        target = close_app_match.group(1).strip()
        if target not in ("vision", "interface", "hologram", "window", "speech", "speaking"):
            from modules.apps import APP_ALIASES, BUILTIN_COMMANDS
            norm = normalize_app_name(target)
            if norm in APP_ALIASES or norm in BUILTIN_COMMANDS:
                return "close_app", {"app": norm}

    # 6. Check Open Folder ('Open Downloads', 'Open my Documents folder')
    folder_match = re.search(r"\b(?:open|show|explore|kholo)\s+(?:my\s+)?(downloads|documents|desktop|pictures|videos|music)(?:\s+folder)?\b", cmd)
    if folder_match:
        return "open_folder", {"folder": folder_match.group(1)}

    # 7. Check List Files in Folder ('List files in Downloads', 'What is in my Documents')
    list_files_match = re.search(r"\b(?:list files|show files|what is in|files in)\s+(?:my\s+)?(downloads|documents|desktop|pictures|videos|music)(?:\s+folder)?\b", cmd)
    if list_files_match:
        return "list_files", {"folder": list_files_match.group(1)}

    # 8. Check Open Specific Website ('Open YouTube', 'Open ChatGPT', 'Open GitHub', 'Open reddit.com')
    site_match = re.search(r"\b(?:open|launch|kholo)\s+(youtube|chatgpt|google|github|reddit|wikipedia|twitter|gmail|netflix|amazon)\b", cmd)
    if site_match:
        return "open_site", {"site": site_match.group(1)}

    # Check URL domain directly
    domain_match = re.search(r"\b([a-zA-Z0-9\-]+\.(?:com|org|net|io|edu|gov|ai))\b", cmd)
    if domain_match:
        return "open_site", {"site": domain_match.group(1)}

    # 9. Check Open Application ('Open Chrome', 'Launch VS Code', 'Start Calculator', 'Open Notepad')
    open_app_match = re.search(r"\b(?:open|launch|start|run|kholo|chalao)\s+([a-z0-9 _\-]+)\b", cmd)
    if open_app_match:
        target = open_app_match.group(1).strip()
        from modules.apps import APP_ALIASES, BUILTIN_COMMANDS
        norm = normalize_app_name(target)
        if norm in APP_ALIASES or norm in BUILTIN_COMMANDS:
            return "open_app", {"app": norm}

    # 10. Check Personal Identity & Notes
    name_match = re.search(r"\b(?:my name is|call me|mera naam)\s+([a-zA-Z]+)\b", raw, re.I)
    if name_match:
        return "set_name", {"name": name_match.group(1).title()}

    note_match = re.search(r"\b(?:remember that|save note|add note|yaad rakhna ki)\s+(.+)\b", cmd)
    if note_match:
        return "add_note", {"note": note_match.group(1).strip()}

    # 11. Check Search Commands ('search for python tutorials', 'find latest news on youtube')
    if re.search(r"\b(?:search|find|look up)\b", cmd):
        plat = None
        m_plat = re.search(r"\b(?:on|in)?\s*(youtube|google)\b", cmd, re.I)
        working_cmd = cmd
        if m_plat:
            plat = m_plat.group(1).lower()
            working_cmd = re.sub(r"\b(?:on|in)?\s*(youtube|google)\b", "", working_cmd, flags=re.I).strip()

        # Strip search verb prefixes
        query = re.sub(r"^(?:now )?(?:search (?:for )?|find |look up )", "", working_cmd, flags=re.I).strip()
        query = re.sub(r"^(?:for |about |tutorials on |videos of )", "", query, flags=re.I).strip()

        platform = plat if plat else (context.last_search_platform or "google")
        return "search", {"query": query, "platform": platform}

    # 12. Check for Conversational Questions & Discussions
    if CONVERSATIONAL_REGEX.search(cmd):
        return "chat", {}

    # Check for Follow-Up context if recent dialogue exists
    if FOLLOW_UP_REGEX.search(cmd) and (getattr(context, "turns", None) or getattr(context, "last_action", "") == "chat"):
        return "chat", {}

    # All unhandled queries are naturally conversational AI queries
    return "chat", {}


def parse_intent_with_ollama(user_text: str, context: ConversationContext, ollama_client: Any, model_name: str) -> Optional[Tuple[str, Dict[str, Any]]]:
    """
    Tier 2: Fallback structured intent extraction with local Ollama LLM.
    Enforces a strict JSON response schema and validates actions against an allowlist.
    """
    try:
        last_action_desc = f"Last action: {context.last_action}, Last app: {context.last_app}, Last site: {context.last_site}"
        system_prompt = (
            "You are an intent classification engine for VISION Windows Assistant. "
            "Analyze the user command and return ONLY a valid JSON object matching this schema:\n"
            "{\n"
            '  "intent": "open_app" | "close_app" | "search" | "open_site" | "open_folder" | "system_control" | "chat",\n'
            '  "target": "<app or site or folder name if applicable>",\n'
            '  "query": "<search query if applicable>"\n'
            "}\n"
            f"Context: {last_action_desc}\n"
            "If the request is a general question or conversational request, set intent to 'chat'."
        )

        response = ollama_client.chat(
            model=model_name,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_text}
            ],
            options={"num_predict": 60, "temperature": 0.1}
        )

        raw_content = response["message"]["content"].strip()
        # Extract json object if surrounded by markdown code fences
        json_match = re.search(r"\{.*\}", raw_content, re.DOTALL)
        if json_match:
            data = json.loads(json_match.group(0))
            intent = data.get("intent")
            target = data.get("target", "")
            query = data.get("query", "")

            # Strict allowlist verification
            if intent == "open_app" and target:
                return "open_app", {"app": target}
            elif intent == "close_app" and target:
                return "close_app", {"app": target}
            elif intent == "search" and query:
                return "search", {"query": query, "platform": "google"}
            elif intent == "open_site" and target:
                return "open_site", {"site": target}
            elif intent == "open_folder" and target:
                return "open_folder", {"folder": target}
            elif intent == "chat":
                return "chat", {}
    except Exception as e:
        print(f"[IntentRouter] Ollama classification notice: {e}")

    return None
