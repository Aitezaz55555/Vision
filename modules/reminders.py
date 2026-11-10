"""
VISION AI - Voice Reminders and Notification Scheduler
Schedules, tracks, and triggers voice reminders with audio notifications.
"""

import json
import os
import re
import threading
import time
from datetime import datetime
from typing import List, Dict, Tuple, Optional, Callable

REMINDERS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data", "reminders.json")
_reminders_lock = threading.Lock()
_scheduler_running = False
_notify_callback: Optional[Callable[[str], None]] = None


def load_reminders() -> List[Dict]:
    """Loads active reminders from disk."""
    if not os.path.isfile(REMINDERS_FILE):
        return []
    try:
        with open(REMINDERS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []


def save_reminders(reminders: List[Dict]):
    """Persists reminders list to disk."""
    try:
        os.makedirs(os.path.dirname(REMINDERS_FILE), exist_ok=True)
        with open(REMINDERS_FILE, "w", encoding="utf-8") as f:
            json.dump(reminders, f, indent=2)
    except Exception as e:
        print(f"[Reminders] Save error: {e}")


def parse_reminder_phrase(phrase: str) -> Tuple[Optional[str], Optional[float]]:
    """
    Parses natural phrases such as:
    - 'remind me to call John in 10 minutes'
    - 'remind me to check email in 30 seconds'
    - 'remind me to drink water in 1 hour'
    Returns (task_text, delay_seconds).
    """
    cmd = phrase.lower().strip()
    match = re.search(r"\b(?:remind me(?: to)?|set a reminder(?: to)?|reminder to)\s+(.+?)\s+in\s+(\d+)\s*(seconds?|secs?|minutes?|mins?|hours?|hrs?)\b", cmd)
    if not match:
        return None, None

    task = match.group(1).strip()
    num = int(match.group(2))
    unit = match.group(3).lower()

    mult = 1
    if "min" in unit:
        mult = 60
    elif "hour" in unit or "hr" in unit:
        mult = 3600

    delay = float(num * mult)
    return task, delay


def add_reminder(task: str, delay_seconds: float) -> Tuple[bool, str]:
    """Adds a new reminder to the active queue."""
    if delay_seconds <= 0 or not task:
        return False, "Invalid reminder parameters."

    trigger_time = time.time() + delay_seconds
    formatted_time = datetime.fromtimestamp(trigger_time).strftime("%I:%M %p")

    with _reminders_lock:
        reminders = load_reminders()
        reminders.append({
            "task": task,
            "trigger_time": trigger_time,
            "created_at": time.time(),
            "formatted_time": formatted_time
        })
        save_reminders(reminders)

    minutes = int(round(delay_seconds / 60))
    if delay_seconds < 60:
        time_str = f"{int(delay_seconds)} seconds"
    elif minutes == 1:
        time_str = "1 minute"
    elif minutes < 60:
        time_str = f"{minutes} minutes"
    else:
        hours = round(delay_seconds / 3600, 1)
        time_str = f"{hours} hours"

    return True, f"I have set a reminder to {task} in {time_str}, at {formatted_time}."


def list_reminders() -> Tuple[bool, str, List[Dict]]:
    """Lists upcoming scheduled reminders."""
    with _reminders_lock:
        reminders = load_reminders()

    now = time.time()
    upcoming = [r for r in reminders if r.get("trigger_time", 0) > now]

    if not upcoming:
        return True, "You have no active reminders scheduled Sir.", []

    descriptions = []
    for idx, r in enumerate(upcoming, 1):
        remaining = int(r["trigger_time"] - now)
        mins = remaining // 60
        secs = remaining % 60
        time_rem = f"{mins}m {secs}s" if mins > 0 else f"{secs}s"
        descriptions.append(f"{idx}. {r['task']} (in {time_rem} at {r.get('formatted_time', '')})")

    spoken = f"You have {len(upcoming)} active reminder{'s' if len(upcoming) > 1 else ''}. " + "; ".join(descriptions)
    return True, spoken, upcoming


def cancel_all_reminders() -> Tuple[bool, str]:
    """Cancels and clears all active reminders."""
    with _reminders_lock:
        reminders = load_reminders()
        count = len(reminders)
        save_reminders([])

    if count > 0:
        return True, f"Cleared {count} reminder{'s' if count > 1 else ''}."
    return True, "There were no active reminders to cancel Sir."


def start_reminder_scheduler(notify_callback: Callable[[str], None]):
    """Starts the background scheduler thread to fire matured reminders."""
    global _scheduler_running, _notify_callback
    _notify_callback = notify_callback

    if _scheduler_running:
        return

    _scheduler_running = True

    def _loop():
        while _scheduler_running:
            time.sleep(1.0)
            now = time.time()
            to_fire = []

            with _reminders_lock:
                reminders = load_reminders()
                remaining = []
                for r in reminders:
                    if r.get("trigger_time", 0) <= now:
                        to_fire.append(r)
                    else:
                        remaining.append(r)
                if to_fire:
                    save_reminders(remaining)

            for item in to_fire:
                task = item.get("task", "Reminder")
                msg = f"Sir, reminder: {task}."
                if _notify_callback:
                    try:
                        _notify_callback(msg)
                    except Exception as e:
                        print(f"[Reminders] Notify error: {e}")

    threading.Thread(target=_loop, daemon=True).start()
