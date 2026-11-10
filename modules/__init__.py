"""
VISION AI - Core Modules Package
Modular architecture for Windows Application Control, System Control,
Browser Automation, File Navigation, Contextual Memory, Hybrid Intent Routing,
Streaming Conversational AI, and Instant Barge-In Speech Synthesis.
"""

from modules.context import ConversationContext
from modules.apps import launch_application, close_application, normalize_app_name, find_application_path, control_window
from modules.system import (
    control_volume, get_volume_level, adjust_brightness,
    lock_workstation, execute_shutdown, get_battery_info,
    get_performance_info, get_system_summary, capture_screenshot
)
from modules.browser import open_website, search_web, sanitize_url
from modules.files import open_folder, list_files_in_folder, search_and_open_file
from modules.router import match_deterministic_intent, parse_intent_with_ollama
from modules.clap import ClapDetector
from modules.instance_lock import acquire_instance_lock, release_instance_lock
from modules.startup import enable_startup, disable_startup, is_startup_enabled, get_startup_status
from modules.sound import play_activation_chime, play_interrupt_cue
from modules.reminders import add_reminder, list_reminders, cancel_all_reminders, start_reminder_scheduler
from modules.tts_stream import (
    StreamingTTSManager, split_stream_into_sentences, clean_text_for_speech, BARGE_IN_KEYWORDS
)
from modules.chat import (
    detect_conversation_mode, build_system_prompt, prepare_chat_messages, stream_ollama_tokens
)
