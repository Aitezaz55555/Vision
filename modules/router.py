"""
VISION AI - Advanced Natural-Language Understanding & Intelligent Intent Router
Provides sub-millisecond intent classification, intelligent query cleaning,
pronoun/follow-up resolution, and comprehensive routing across:
- Speech interruption & Barge-in
- System performance, RAM, CPU, and running applications
- File & document search and summarization
- Application and window management
- Web and research intelligence
- Scheduling, reminders, and project memory
- Natural conversational AI (Chatbot mode)
"""

import json
import re
import urllib.parse
from typing import Tuple, Dict, Any, Optional

from modules.context import ConversationContext
from modules.apps import normalize_app_name, APP_ALIASES, BUILTIN_COMMANDS
from modules.reminders import parse_reminder_phrase


# Leading assistant name and polite starter cleanup
FILLER_STARTERS = re.compile(
    r"^(?:(?:hey|hello|hi|ok|okay)\s+)?(?:vision|vizhan|taha)[,\s:]*"
    r"(?:(?:can\s+you\s+(?:please\s+)?|could\s+you\s+(?:please\s+)?|would\s+you\s+|will\s+you\s+|please\s+|kindly\s+|i\s+want\s+you\s+to\s+|tell\s+me\s+)?(?:\s*))",
    re.I
)

POLITE_STARTERS = re.compile(
    r"^(?:can\s+you\s+(?:please\s+)?|could\s+you\s+(?:please\s+)?|would\s+you\s+|will\s+you\s+|please\s+|kindly\s+|tell\s+me\s+)",
    re.I
)

# Conversational & Explanatory Intent Patterns
CONVERSATIONAL_REGEX = re.compile(
    r"^(?:what|who|where|when|why|how|which|whose|whom|"
    r"explain|elaborate|describe|define|teach me|tell me|help me understand|"
    r"can you (?:explain|tell|elaborate|clarify|solve|help)|could you (?:explain|tell|elaborate|clarify|solve|help)|"
    r"give (?:me )?(?:an? )?example|show (?:me )?(?:an? )?example|another example|"
    r"make (?:it|your explanation) (?:shorter|simpler|brief|longer|detailed)|summarize|in simple terms|step by step|"
    r"explain that again|tell me more|what about|how does (?:it|that|this) work|why is (?:it|that|this)|"
    r"tell (?:me )?(?:a )?(?:story|joke|fact|riddle)|joke sunao|kahani sunao|"
    r"hello|hi|hey|how are you|what's up|good morning|good evening|good afternoon|thank you|thanks|"
    r"write (?:a )?(?:code|program|script|function|query|poem|essay)|"
    r"difference between|compare|is it (?:true|possible)|can we|could we|solve|calculate|"
    r"i have (?:another|a) question)\b",
    re.I
)

FOLLOW_UP_REGEX = re.compile(
    r"^(?:why\??|how\??|what\??|why so\??|give (?:me )?(?:an? )?example|show (?:me )?(?:an? )?example|example|another one|"
    r"explain (?:that|more|again|further)|tell me more|more|next|continue|go on|"
    r"make (?:it|your explanation) (?:shorter|simpler|brief|longer)|summarize|in simple terms|step by step|"
    r"what else|can you elaborate|clarify|explain that again|compare these|compare them|another question)\b",
    re.I
)


def clean_user_input(text: str) -> Tuple[str, str]:
    """
    Cleans raw voice transcripts:
    - Strips leading wake words and assistant names ('Vision, ...')
    - Strips polite conversational prefixes ('Can you please ...')
    - Strips trailing punctuation ('.', '?', '!')
    Returns (cleaned_natural_text, normalized_lowercase_text).
    """
    t = text.strip()
    t = FILLER_STARTERS.sub("", t).strip()
    t = POLITE_STARTERS.sub("", t).strip()
    t_clean = re.sub(r"[?!.,;:]+$", "", t).strip()
    return t_clean, t_clean.lower()


def match_deterministic_intent(user_text: str, context: ConversationContext) -> Tuple[Optional[str], Dict[str, Any]]:
    """
    Tier 1: High-accuracy, low-latency natural language intent classification.
    Correctly maps conversational questions, system operations, and Windows controls.
    """
    raw = user_text.strip()
    raw_clean, cmd = clean_user_input(raw)

    # 1. Check for Pending Confirmation First
    if context.has_pending_confirmation():
        if re.match(r"^(?:yes|confirm|proceed|do it|haan|ha|sure|yeah|yep|okay|ok)$", cmd):
            return "confirm_action", {"proceed": True}
        if re.match(r"^(?:no|cancel|abort|stop|dont|don't|mat karo|nahi|nah)$", cmd):
            return "confirm_action", {"proceed": False}

    # 2. Complete Assistant Exit
    if re.search(r"\b(?:(?:stop|exit|quit|terminate|band karo)\s+vision|goodbye vision|vision goodbye)\b", raw, re.I):
        return "stop", {}

    # 3. Immediate Speech Interruption & Barge-in
    if re.match(r"^(?:stop(?:\s+speaking|\s+talking|\s+it|\s+now)?|be quiet|shut\s*up|shutup|enough|that'?s enough|cancel|wait|pause|listen|continue|ruk jao|ruko|chup(?:\s+raho|\s+ho\s+jao)?)$", cmd, re.I):
        return "tts_stop", {}

    # 4. Speech Playback Adjustments
    if re.match(r"^(?:repeat that|what did you say|say that again|repeat|phir se bolo)$", cmd, re.I):
        return "tts_repeat", {}

    if re.search(r"\b(?:continue from where we stopped|continue your explanation|continue speaking|keep going|aage batao)\b", cmd, re.I):
        return "tts_continue", {}

    if re.search(r"\b(?:speak slower|talk slower|slow down your voice|slower voice)\b", cmd, re.I):
        return "tts_slower", {}

    if re.search(r"\b(?:speak faster|talk faster|speed up your voice|faster voice)\b", cmd, re.I):
        return "tts_faster", {}

    if re.search(r"\b(?:don't speak|dont speak|silent mode|mute responses|stop voice responses)\b", cmd, re.I):
        return "tts_disable_speech", {}

    if re.search(r"\b(?:enable speech|speak normally|voice on|unmute responses)\b", cmd, re.I):
        return "tts_enable_speech", {}

    # 5. System Awareness & Hardware Performance
    # RAM / Memory
    if re.search(r"\b(?:how much (?:ram|memory)|ram (?:usage|use|status|level|free)|memory (?:usage|use)|check ram)\b", cmd, re.I):
        return "system_ram", {}

    # CPU / Overall Performance
    if re.search(r"\b(?:how much cpu|cpu (?:usage|use|load)|system (?:performance|stats|load)|hardware usage)\b", cmd, re.I):
        return "performance", {}

    # Running Applications
    if re.search(r"\b(?:what (?:apps|applications|programs|windows) are (?:running|open)|list (?:running )?(?:apps|applications|programs)|show (?:running )?(?:apps|applications|processes)|running (?:apps|applications|programs))\b", cmd, re.I):
        return "list_running_apps", {}

    # Battery
    if re.search(r"\b(?:(?:check |what is |how is |show )?(?:my )?battery(?: status| level| percentage)|battery level|battery status|battery percentage|battery kitni hai)\b", cmd, re.I):
        return "battery", {}

    # System Info & Specs
    if re.search(r"\b(?:system info|system information|about this pc|pc specs|computer info)\b", cmd, re.I):
        return "system_info", {}

    # Time & Date
    if re.search(r"\b(?:what time is it|current time|what's the time|tell me the time|time kya hai|samay kya hua)\b", cmd, re.I):
        return "get_time", {}

    if re.search(r"\b(?:what is today's date|today's date|what date is it|what is the date|aaj ki date|aaj ki tarikh)\b", cmd, re.I):
        return "get_date", {}

    # Task Manager & Settings
    if re.search(r"\b(?:open |launch |show )?(?:task manager|taskmgr|system processes)\b", cmd, re.I):
        return "task_manager", {}

    if re.search(r"\b(?:open |launch |show )?(?:windows settings|system settings|pc settings|control panel)\b", cmd, re.I):
        return "settings", {}

    # Lock Screen
    if re.search(r"\b(?:lock (?:my )?(?:pc|computer|windows|screen)|lock screen|workstation lock)\b", cmd, re.I):
        return "lock_workstation", {}

    # Screenshots & Photos
    if re.search(r"\b(?:take (?:a )?screenshot|capture (?:my )?screen|screenshot (?:lo|khencho|le lo))\b", cmd, re.I):
        return "screenshot", {}

    if re.search(r"\b(?:take (?:a )?photo|take (?:a )?picture|capture photo|photo (?:lo|khencho))\b", cmd, re.I):
        return "take_photo", {}

    # Volume and Brightness
    vol_set = re.search(r"\b(?:set volume (?:to )?|volume (?:to )?)(\d{1,3})\b", cmd)
    if vol_set:
        return "volume_set", {"value": int(vol_set.group(1))}

    if re.search(r"\b(?:increase (?:the )?volume|volume up|turn (?:it )?up|sound up|louder|tez karo)\b", cmd, re.I):
        return "volume_up", {}

    if re.search(r"\b(?:decrease (?:the )?volume|lower (?:the )?volume|volume down|turn (?:it )?down|sound down|quieter|dheema karo)\b", cmd, re.I):
        return "volume_down", {}

    if re.search(r"\b(?:mute (?:the )?(?:audio|sound|volume)|sound mute|awaaz band)\b", cmd, re.I):
        return "volume_mute", {}

    if re.search(r"\b(?:unmute (?:the )?(?:audio|sound|volume)|sound unmute|awaaz chalu)\b", cmd, re.I):
        return "volume_unmute", {}

    # Window Management
    if re.search(r"\b(?:minimize (?:this |that |the )?window|minimize screen|window minimize)\b", cmd, re.I):
        return "window_minimize", {}
    if re.search(r"\b(?:maximize (?:this |that |the )?window|maximize screen|full ?screen window)\b", cmd, re.I):
        return "window_maximize", {}
    if re.search(r"\b(?:restore (?:this |that |the )?window|restore window)\b", cmd, re.I):
        return "window_restore", {}

    # Sensitive operations requiring confirmation
    if re.search(r"\b(?:shut ?down|power off|turn off)(?:\s+(?:my|the|this))?\s*(?:pc|computer|laptop|system|machine)\b", cmd, re.I):
        return "shutdown_request", {}
    if re.search(r"\b(?:restart|reboot)(?:\s+(?:my|the|this))?\s*(?:pc|computer|laptop|system|machine)\b", cmd, re.I):
        return "restart_request", {}

    # 6. File & Folder Intelligence
    # Project Folder
    if re.search(r"\b(?:open|show|explore)\s+(?:my\s+)?(?:project|workspace|root|code)(?:\s+folder)?\b", cmd, re.I):
        return "open_folder", {"folder": "project"}

    # Standard User Folders
    folder_match = re.search(r"\b(?:open|show|explore|kholo)\s+(?:my\s+)?(downloads|documents|desktop|pictures|videos|music)(?:\s+folder)?\b", cmd, re.I)
    if folder_match:
        return "open_folder", {"folder": folder_match.group(1)}

    # List Files in Folder
    list_files_match = re.search(r"\b(?:list files|show files|what is in|files in)\s+(?:my\s+)?(downloads|documents|desktop|pictures|videos|music)(?:\s+folder)?\b", cmd, re.I)
    if list_files_match:
        return "list_files", {"folder": list_files_match.group(1)}

    # Find Files / Notes (e.g. 'find my DBMS notes', 'find python notes', 'find report.pdf')
    m_file = re.search(r"\b(?:find|search for|look for|locate|open)\s+(?:my\s+)?([a-z0-9 _\-]+?\s+(?:notes?|files?|docs?|documents?|pdfs?|sheets?|assignments?|code))\b", cmd, re.I)
    if m_file:
        return "find_files", {"query": m_file.group(1).strip()}

    m_ext = re.search(r"\b(?:find|search for|locate|open)\s+(?:my\s+)?([a-z0-9 _\-\.]+\.(?:pdf|txt|docx|doc|xlsx|csv|py|json|md))\b", cmd, re.I)
    if m_ext:
        return "find_files", {"query": m_ext.group(1).strip()}

    # Document Summarization
    m_doc = re.search(r"\b(?:summarise|summarize|read|explain|analyze)\s+(?:this |my |the )?(?:pdf|document|file|notes?)\b", cmd, re.I)
    if m_doc:
        return "summarize_document", {"target": "pdf"}

    # 7. Reminders
    if "remind" in cmd:
        task, delay = parse_reminder_phrase(raw)
        if task and delay:
            return "add_reminder", {"task": task, "delay": delay}
        # Natural reminder without explicit time delay -> default to 15 minutes
        m_gen_rem = re.search(r"\bremind me (?:to|about) (.+?)$", cmd, re.I)
        if m_gen_rem:
            return "add_reminder", {"task": m_gen_rem.group(1).strip(), "delay": 900.0}

    if re.search(r"\b(?:what are my reminders|show (?:my )?reminders|list reminders|reminders dikhao)\b", cmd, re.I):
        return "list_reminders", {}

    if re.search(r"\b(?:cancel (?:all )?reminders|clear reminders|delete reminders)\b", cmd, re.I):
        return "cancel_reminders", {}

    # 8. Personal & Project Memory
    m_proj_note = re.search(r"\bremember (?:this )?(?:for |in )?(?:our |my |the )?(?:current )?project[:\s]*(.*)\b", raw, re.I)
    if m_proj_note:
        note_text = m_proj_note.group(1).strip() or raw_clean
        return "add_project_note", {"note": note_text}

    m_note = re.search(r"\b(?:remember that|save note|add note|yaad rakhna ki)\s+(.+)\b", cmd, re.I)
    if m_note:
        return "add_note", {"note": m_note.group(1).strip()}

    if re.search(r"\b(?:show (?:my )?notes|what are my notes|read (?:my )?notes|notes dikhao)\b", cmd, re.I):
        return "show_notes", {}

    if re.search(r"\b(?:clear (?:my )?notes|delete (?:my )?notes|erase notes)\b", cmd, re.I):
        return "clear_notes", {}

    name_match = re.search(r"\b(?:my name is|call me|mera naam)\s+([a-zA-Z]+)\b", raw, re.I)
    if name_match:
        return "set_name", {"name": name_match.group(1).title()}

    if re.search(r"\b(?:what is my name|who am i|mera naam kya hai)\b", cmd, re.I):
        return "get_name", {}

    # 9. Application and Website Management
    # Contextual Close ('close it', 'close that app')
    if re.search(r"\b(?:close|quit|exit|kill|band karo)\s+(?:it|that|that app|the app|that application)\b", cmd, re.I):
        resolved_app, _ = context.resolve_target("it")
        if resolved_app:
            return "close_app", {"app": resolved_app}

    # Close explicit app
    close_app_match = re.search(r"\b(?:close|quit|exit|kill|band karo)\s+([a-z0-9 _\-]+)\b", cmd, re.I)
    if close_app_match:
        target = close_app_match.group(1).strip()
        if target not in ("vision", "interface", "hologram", "window", "speech", "speaking"):
            norm = normalize_app_name(target)
            if norm in APP_ALIASES or norm in BUILTIN_COMMANDS:
                return "close_app", {"app": norm}

    # Open specific website
    site_match = re.search(r"\b(?:open|launch|kholo)\s+(youtube|chatgpt|google|github|reddit|wikipedia|twitter|gmail|netflix|amazon)\b", cmd, re.I)
    if site_match:
        return "open_site", {"site": site_match.group(1)}

    # Open specific application
    open_app_match = re.search(r"\b(?:open|launch|start|run|kholo|chalao)\s+([a-z0-9 _\-]+)\b", cmd, re.I)
    if open_app_match:
        target = open_app_match.group(1).strip()
        norm = normalize_app_name(target)
        if norm in APP_ALIASES or norm in BUILTIN_COMMANDS:
            return "open_app", {"app": norm}

    # 10. Web Search & Online Research
    if re.search(r"\b(?:search|look up)\b", cmd, re.I):
        plat = "google"
        if "youtube" in cmd:
            plat = "youtube"
        # Clean query: strip search verbs, platforms, and filler words
        q = re.sub(r"^(?:search (?:the internet|the web|google|online)? (?:for )?|find (?:me )?(?:information (?:about|on) )?|look up )", "", cmd, flags=re.I).strip()
        q = re.sub(r"\b(?:on|in)?\s*(?:youtube|google)\b", "", q, flags=re.I).strip()
        q = re.sub(r"^(?:for |about |tutorials on |videos of )", "", q, flags=re.I).strip()
        q = re.sub(r"^(?:the |a |an )", "", q, flags=re.I).strip()
        return "search", {"query": q or cmd, "platform": plat}

    # 11. Sleep, Standby & Dictation Modes
    if re.search(r"\b(?:start dictation|enter dictation|dictation mode|transcribe speech|type what i say)\b", cmd, re.I):
        return "dictation_start", {}

    if re.search(r"\b(?:stop dictation|exit dictation|end dictation)\b", cmd, re.I):
        return "dictation_stop", {}

    if re.search(r"\b(?:go to sleep|sleep mode|sleep now|stop listening|so jao|chup ho jao|take a break|standby|enter standby)\b", cmd, re.I):
        return "sleep", {}

    # 12. Conversational Questions, Explanations, and Follow-ups
    if CONVERSATIONAL_REGEX.search(cmd):
        return "chat", {}

    if FOLLOW_UP_REGEX.search(cmd) and (getattr(context, "turns", None) or getattr(context, "last_action", "") == "chat"):
        return "chat", {}

    # All unhandled requests naturally route to conversational AI
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
        json_match = re.search(r"\{.*\}", raw_content, re.DOTALL)
        if json_match:
            data = json.loads(json_match.group(0))
            intent = data.get("intent")
            target = data.get("target", "")
            query = data.get("query", "")

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
