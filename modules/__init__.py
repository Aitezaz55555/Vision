"""
VISION AI - Core Modules Package
High-performance lazy-loading modular architecture for Windows Application Control,
System Control, Browser Automation, File Navigation, Contextual Memory,
Hybrid Intent Routing, Streaming Conversational AI, and Instant Barge-In Speech Synthesis.
"""

import importlib
from typing import Any

__all__ = [
    "ConversationContext", "launch_application", "close_application", "normalize_app_name",
    "find_application_path", "control_window",
    "control_volume", "get_volume_level", "adjust_brightness", "lock_workstation",
    "execute_shutdown", "get_battery_info", "get_performance_info", "get_ram_info",
    "get_running_apps", "get_system_summary", "capture_screenshot", "open_website",
    "search_web", "sanitize_url", "open_folder", "list_files_in_folder",
    "search_and_open_file", "find_files_matching", "summarize_local_document",
    "match_deterministic_intent", "parse_intent_with_ollama", "ClapDetector",
    "acquire_instance_lock", "release_instance_lock", "enable_startup",
    "disable_startup", "is_startup_enabled", "get_startup_status",
    "play_activation_chime", "play_interrupt_cue", "add_reminder", "list_reminders",
    "cancel_all_reminders", "start_reminder_scheduler", "StreamingTTSManager",
    "split_stream_into_sentences", "clean_text_for_speech", "BARGE_IN_KEYWORDS",
    "detect_conversation_mode", "build_system_prompt", "prepare_chat_messages",
    "stream_ollama_tokens", "HandTracker", "TrackingTelemetry", "SingleHandInfo",
    "ParticleSystem", "RippleWave"
]

_MODULE_MAP = {
    "ConversationContext": "modules.context",
    "launch_application": "modules.apps",
    "close_application": "modules.apps",
    "normalize_app_name": "modules.apps",
    "find_application_path": "modules.apps",
    "control_window": "modules.apps",
    "control_volume": "modules.system",
    "get_volume_level": "modules.system",
    "adjust_brightness": "modules.system",
    "lock_workstation": "modules.system",
    "execute_shutdown": "modules.system",
    "get_battery_info": "modules.system",
    "get_performance_info": "modules.system",
    "get_ram_info": "modules.system",
    "get_running_apps": "modules.system",
    "get_system_summary": "modules.system",
    "capture_screenshot": "modules.system",
    "open_website": "modules.browser",
    "search_web": "modules.browser",
    "sanitize_url": "modules.browser",
    "open_folder": "modules.files",
    "list_files_in_folder": "modules.files",
    "search_and_open_file": "modules.files",
    "find_files_matching": "modules.files",
    "summarize_local_document": "modules.files",
    "match_deterministic_intent": "modules.router",
    "parse_intent_with_ollama": "modules.router",
    "ClapDetector": "modules.clap",
    "acquire_instance_lock": "modules.instance_lock",
    "release_instance_lock": "modules.instance_lock",
    "enable_startup": "modules.startup",
    "disable_startup": "modules.startup",
    "is_startup_enabled": "modules.startup",
    "get_startup_status": "modules.startup",
    "play_activation_chime": "modules.sound",
    "play_interrupt_cue": "modules.sound",
    "add_reminder": "modules.reminders",
    "list_reminders": "modules.reminders",
    "cancel_all_reminders": "modules.reminders",
    "start_reminder_scheduler": "modules.reminders",
    "StreamingTTSManager": "modules.tts_stream",
    "split_stream_into_sentences": "modules.tts_stream",
    "clean_text_for_speech": "modules.tts_stream",
    "BARGE_IN_KEYWORDS": "modules.tts_stream",
    "detect_conversation_mode": "modules.chat",
    "build_system_prompt": "modules.chat",
    "prepare_chat_messages": "modules.chat",
    "stream_ollama_tokens": "modules.chat",
    "HandTracker": "modules.hand_tracking",
    "TrackingTelemetry": "modules.hand_tracking",
    "SingleHandInfo": "modules.hand_tracking",
    "ParticleSystem": "modules.particles",
    "RippleWave": "modules.particles",
}

def __getattr__(name: str) -> Any:
    if name in _MODULE_MAP:
        mod = importlib.import_module(_MODULE_MAP[name])
        return getattr(mod, name)
    raise AttributeError(f"module 'modules' has no attribute '{name}'")
