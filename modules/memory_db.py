"""
VISION AI - Permanent Personal Memory Subsystem (SQLite)
Provides persistent, structured, cross-session personal memory for user preferences,
personal info, project notes, and important facts with USB portability, WAL mode,
conflict resolution, and zero storage of passwords or private tokens.
"""

import os
import re
import sqlite3
import threading
import time
from datetime import datetime
from typing import Dict, List, Optional, Tuple, Any

# Resolve absolute path to data directory
SCRIPT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(SCRIPT_DIR, "data")
os.makedirs(DATA_DIR, exist_ok=True)
DB_PATH = os.path.join(DATA_DIR, "vision_memory.db")

_db_lock = threading.Lock()

# Sensitive keywords that must never be stored in persistent memory
SENSITIVE_KEYWORDS = {
    "password", "passwd", "pwd", "pin", "api_key", "apikey", "secret_key",
    "token", "auth_token", "bearer", "private_key", "credentials", "credit_card", "cvv"
}

# Patterns for sensitive data that should NEVER be stored in memory
SENSITIVE_PATTERNS = [
    re.compile(r"(?:password|passwd|pwd|pin)\s*[:=]\s*\S+", re.IGNORECASE),
    re.compile(r"(?:api[_-]?key|secret[_-]?key|token)\s*[:=]\s*\S+", re.IGNORECASE),
    re.compile(r"\b[A-Za-z0-9+/]{32,}={0,2}\b"),  # Base64 tokens / hashes
    re.compile(r"\b(?:bearer\s+[a-zA-Z0-9_\-\.]+)\b", re.IGNORECASE),
    re.compile(r"\b\d{4}[ -]?\d{4}[ -]?\d{4}[ -]?\d{4}\b"),  # Credit cards
]


def _get_connection() -> sqlite3.Connection:
    """Create a SQLite connection with WAL mode and timeout for concurrency."""
    conn = sqlite3.connect(DB_PATH, timeout=10.0, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    try:
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA synchronous=NORMAL;")
    except Exception:
        pass
    return conn


def init_memory_db():
    """Initialize memory and conversation history tables."""
    with _db_lock:
        conn = _get_connection()
        try:
            with conn:
                # 1. Permanent Structured Memory
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS memories (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        category TEXT NOT NULL,
                        key TEXT NOT NULL,
                        value TEXT NOT NULL,
                        details TEXT DEFAULT '',
                        confidence REAL DEFAULT 1.0,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        UNIQUE(category, key)
                    );
                """)
                conn.execute("CREATE INDEX IF NOT EXISTS idx_memories_cat_key ON memories(category, key);")

                # 2. Short-term and Long-term Conversation History
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS conversation_turns (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        session_id TEXT DEFAULT 'default',
                        role TEXT NOT NULL,
                        content TEXT NOT NULL,
                        input_method TEXT DEFAULT 'voice',
                        intent TEXT DEFAULT '',
                        timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    );
                """)
                conn.execute("CREATE INDEX IF NOT EXISTS idx_turns_time ON conversation_turns(timestamp);")
        finally:
            conn.close()


def is_sensitive(text: str) -> bool:
    """Check if text contains passwords, private API tokens, or secrets."""
    if not text:
        return False
    lower_text = text.lower()
    for kw in SENSITIVE_KEYWORDS:
        if kw in lower_text:
            return True
    for pattern in SENSITIVE_PATTERNS:
        if pattern.search(text):
            return True
    return False


def save_memory(category: str, key: str, value: str, details: str = "") -> bool:
    """
    Save or update a structured permanent memory record.
    Returns True if successfully persisted, False otherwise.
    """
    if not key or not value:
        return False

    # Block sensitive information
    if is_sensitive(key) or is_sensitive(value) or is_sensitive(details):
        print("[Memory] Blocked attempt to persist sensitive credentials or tokens.")
        return False

    category = category.strip().lower()
    key = key.strip().lower()
    value = value.strip()
    details = details.strip()

    with _db_lock:
        conn = _get_connection()
        try:
            with conn:
                now_str = datetime.now().isoformat()
                conn.execute("""
                    INSERT INTO memories (category, key, value, details, updated_at)
                    VALUES (?, ?, ?, ?, ?)
                    ON CONFLICT(category, key) DO UPDATE SET
                        value = excluded.value,
                        details = excluded.details,
                        updated_at = excluded.updated_at;
                """, (category, key, value, details, now_str))
            return True
        except Exception as e:
            print(f"[Memory] Failed to save memory ({category}/{key}): {e}")
            return False
        finally:
            conn.close()


def get_memory(key: str, category: Optional[str] = None) -> Optional[str]:
    """Retrieve the value of a specific memory record by key."""
    key = key.strip().lower()
    with _db_lock:
        conn = _get_connection()
        try:
            if category:
                cursor = conn.execute(
                    "SELECT value FROM memories WHERE key = ? AND category = ? LIMIT 1;",
                    (key, category.strip().lower())
                )
            else:
                cursor = conn.execute("SELECT value FROM memories WHERE key = ? LIMIT 1;", (key,))
            row = cursor.fetchone()
            return row["value"] if row else None
        except Exception as e:
            print(f"[Memory] Error querying memory: {e}")
            return None
        finally:
            conn.close()


def search_memories(query: str) -> List[Dict[str, Any]]:
    """Search stored memories by keyword across category, key, value, and details."""
    query = f"%{query.strip().lower()}%"
    with _db_lock:
        conn = _get_connection()
        try:
            cursor = conn.execute("""
                SELECT category, key, value, details, updated_at
                FROM memories
                WHERE lower(category) LIKE ? OR lower(key) LIKE ? OR lower(value) LIKE ? OR lower(details) LIKE ?
                ORDER BY updated_at DESC;
            """, (query, query, query, query))
            return [dict(row) for row in cursor.fetchall()]
        except Exception as e:
            print(f"[Memory] Search error: {e}")
            return []
        finally:
            conn.close()


def list_all_memories(category: Optional[str] = None) -> List[Dict[str, Any]]:
    """List all stored memories, optionally filtered by category."""
    with _db_lock:
        conn = _get_connection()
        try:
            if category:
                cursor = conn.execute(
                    "SELECT category, key, value, details, updated_at FROM memories WHERE category = ? ORDER BY key ASC;",
                    (category.strip().lower(),)
                )
            else:
                cursor = conn.execute(
                    "SELECT category, key, value, details, updated_at FROM memories ORDER BY category ASC, key ASC;"
                )
            return [dict(row) for row in cursor.fetchall()]
        except Exception as e:
            print(f"[Memory] List error: {e}")
            return []
        finally:
            conn.close()


def delete_memory(key: str, category: Optional[str] = None) -> bool:
    """Delete a memory record by key or key+category."""
    key = key.strip().lower()
    with _db_lock:
        conn = _get_connection()
        try:
            with conn:
                if category:
                    cursor = conn.execute(
                        "DELETE FROM memories WHERE key = ? AND category = ?;",
                        (key, category.strip().lower())
                    )
                else:
                    cursor = conn.execute("DELETE FROM memories WHERE key = ?;", (key,))
                return cursor.rowcount > 0
        except Exception as e:
            print(f"[Memory] Delete error: {e}")
            return False
        finally:
            conn.close()


def append_conversation_turn(role: str, content: str, input_method: str = "voice", intent: str = ""):
    """Record a user query or assistant reply into SQLite conversation history."""
    if not content:
        return
    with _db_lock:
        conn = _get_connection()
        try:
            with conn:
                conn.execute("""
                    INSERT INTO conversation_turns (role, content, input_method, intent)
                    VALUES (?, ?, ?, ?);
                """, (role, content.strip(), input_method, intent))
        except Exception as e:
            print(f"[Memory] Failed to record conversation turn: {e}")
        finally:
            conn.close()


def get_recent_turns(limit: int = 8) -> List[Dict[str, Any]]:
    """Retrieve the last N turns for short-term contextual continuity."""
    with _db_lock:
        conn = _get_connection()
        try:
            cursor = conn.execute("""
                SELECT role, content, input_method, intent, timestamp
                FROM conversation_turns
                ORDER BY id DESC
                LIMIT ?;
            """, (limit,))
            rows = cursor.fetchall()
            return [dict(r) for r in reversed(rows)]
        except Exception as e:
            print(f"[Memory] History query error: {e}")
            return []
        finally:
            conn.close()


def build_memory_context_prompt() -> str:
    """
    Format all permanent user memories into a concise, high-priority context block
    for system prompt injection so the AI naturally knows user identity and preferences.
    """
    memories = list_all_memories()
    if not memories:
        return ""

    lines = ["\n[PERMANENT USER KNOWLEDGE & PREFERENCES]"]
    for m in memories:
        cat = m["category"].capitalize()
        k = m["key"].replace("_", " ")
        v = m["value"]
        lines.append(f"- {cat} ({k}): {v}")
    lines.append("[END PERMANENT KNOWLEDGE]\n")
    return "\n".join(lines)


# Ensure DB tables exist on import
init_memory_db()
