"""
Authentication module for CRT.
Simple session-based auth with SQLite storage.
"""

import logging
import sqlite3
import hashlib
import secrets
import time
import json
import re
import bcrypt
import threading
from collections import defaultdict
from pathlib import Path
from typing import Optional, Dict, Any, List
from dataclasses import dataclass, asdict
from contextlib import contextmanager

logger = logging.getLogger(__name__)

AUTH_DB_PATH = Path(__file__).parent / "data" / "auth.db"

# Rate limiting: track failed login attempts per username
_login_attempts: Dict[str, list] = defaultdict(list)
_login_lock = threading.Lock()
_RATE_LIMIT_WINDOW = 300     # 5 minute window
_RATE_LIMIT_MAX_ATTEMPTS = 5  # max failures per window


@dataclass
class User:
    id: int
    username: str
    display_name: str
    created_at: int
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class Session:
    token: str
    user_id: int
    created_at: int
    expires_at: int


@dataclass
class ChatThread:
    id: str
    user_id: int
    title: str
    messages: List[Dict[str, Any]]
    created_at: int
    updated_at: int


def _hash_password(password: str, salt: str) -> str:
    """Hash password with bcrypt (salt parameter kept for interface compatibility, bcrypt generates its own)."""
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')


def _verify_password(password: str, stored_hash: str) -> bool:
    """Verify password against stored bcrypt hash. Falls back to legacy SHA-256 for migration."""
    try:
        # Try bcrypt first (new format)
        return bcrypt.checkpw(password.encode('utf-8'), stored_hash.encode('utf-8'))
    except (ValueError, TypeError):
        # Legacy SHA-256 hash — will match during migration period
        return False


def _hash_password_legacy(password: str, salt: str) -> str:
    """Legacy SHA-256 hash for migration verification only."""
    return hashlib.sha256((password + salt).encode()).hexdigest()


def _check_password_complexity(password: str) -> Optional[str]:
    """Validate password meets complexity requirements. Returns error message or None."""
    if len(password) < 8:
        return "Password must be at least 8 characters"
    if not re.search(r'[A-Z]', password):
        return "Password must contain at least one uppercase letter"
    if not re.search(r'[a-z]', password):
        return "Password must contain at least one lowercase letter"
    if not re.search(r'[0-9]', password):
        return "Password must contain at least one digit"
    return None


def _check_rate_limit(username: str) -> bool:
    """Check if login attempts are rate-limited. Returns True if request should be blocked."""
    now = time.time()
    with _login_lock:
        attempts = _login_attempts[username]
        # Prune old attempts outside the window
        _login_attempts[username] = [t for t in attempts if now - t < _RATE_LIMIT_WINDOW]
        return len(_login_attempts[username]) >= _RATE_LIMIT_MAX_ATTEMPTS


def _record_failed_login(username: str) -> None:
    """Record a failed login attempt for rate limiting."""
    with _login_lock:
        _login_attempts[username].append(time.time())


def _generate_token() -> str:
    """Generate a secure random session token."""
    return secrets.token_urlsafe(32)


def _generate_salt() -> str:
    """Generate a random salt for password hashing."""
    return secrets.token_hex(16)


@contextmanager
def get_db():
    """Get database connection with context manager."""
    AUTH_DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(AUTH_DB_PATH), check_same_thread=False)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=5000")
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()


def init_auth_db():
    """Initialize the authentication database tables."""
    with get_db() as conn:
        cursor = conn.cursor()
        
        # Users table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                password_salt TEXT NOT NULL,
                display_name TEXT NOT NULL,
                email TEXT,
                created_at INTEGER NOT NULL,
                updated_at INTEGER NOT NULL
            )
        """)
        
        # Sessions table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS sessions (
                token TEXT PRIMARY KEY,
                user_id INTEGER NOT NULL,
                created_at INTEGER NOT NULL,
                expires_at INTEGER NOT NULL,
                user_agent TEXT,
                ip_address TEXT,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            )
        """)
        
        # User chat threads table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS user_chat_threads (
                id TEXT PRIMARY KEY,
                user_id INTEGER NOT NULL,
                title TEXT NOT NULL,
                messages TEXT NOT NULL DEFAULT '[]',
                created_at INTEGER NOT NULL,
                updated_at INTEGER NOT NULL,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            )
        """)
        
        # User settings table (key-value per user)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS user_settings (
                user_id INTEGER NOT NULL,
                key TEXT NOT NULL,
                value TEXT NOT NULL,
                UNIQUE(user_id, key),
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            )
        """)

        # Create indexes
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_sessions_user ON sessions(user_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_sessions_expires ON sessions(expires_at)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_threads_user ON user_chat_threads(user_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_settings_user ON user_settings(user_id)")

        conn.commit()
        print(f"Auth database initialized at {AUTH_DB_PATH}")


def register_user(username: str, password: str, display_name: Optional[str] = None, email: Optional[str] = None) -> Optional[User]:
    """Register a new user. Returns User on success, None if username taken."""
    username = username.lower().strip()
    display_name = display_name or username
    
    if len(username) < 3:
        raise ValueError("Username must be at least 3 characters")
    complexity_error = _check_password_complexity(password)
    if complexity_error:
        raise ValueError(complexity_error)
    
    salt = _generate_salt()
    password_hash = _hash_password(password, salt)
    now = int(time.time() * 1000)
    
    with get_db() as conn:
        cursor = conn.cursor()
        try:
            cursor.execute("""
                INSERT INTO users (username, password_hash, password_salt, display_name, email, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (username, password_hash, salt, display_name, email, now, now))
            conn.commit()
            
            user_id = cursor.lastrowid
            return User(id=user_id, username=username, display_name=display_name, created_at=now)
        except sqlite3.IntegrityError:
            return None  # Username already exists


def authenticate_user(username: str, password: str) -> Optional[User]:
    """Authenticate user with username and password. Returns User on success."""
    username = username.lower().strip()

    # Rate limiting check
    if _check_rate_limit(username):
        raise ValueError("Too many login attempts. Please wait before trying again.")

    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, username, password_hash, password_salt, display_name, created_at
            FROM users WHERE username = ?
        """, (username,))
        row = cursor.fetchone()
        
        if not row:
            _record_failed_login(username)
            return None

        stored_hash = row['password_hash']
        salt = row['password_salt']

        # Try bcrypt verification first
        if _verify_password(password, stored_hash):
            return User(
                id=row['id'],
                username=row['username'],
                display_name=row['display_name'],
                created_at=row['created_at']
            )

        # Fallback: check legacy SHA-256 hash and migrate to bcrypt if valid
        # SECURITY: SHA-256 without key stretching is fast to brute-force.
        # This path auto-migrates on login. Remove once all accounts are migrated.
        legacy_hash = _hash_password_legacy(password, salt)
        if legacy_hash == stored_hash:
            logger.warning(f"[AUTH] Migrating user '{username}' from legacy SHA-256 to bcrypt")
            # Migrate to bcrypt on successful legacy login
            new_hash = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
            cursor.execute("UPDATE users SET password_hash = ? WHERE id = ?", (new_hash, row['id']))
            conn.commit()
            return User(
                id=row['id'],
                username=row['username'],
                display_name=row['display_name'],
                created_at=row['created_at']
            )

        _record_failed_login(username)
        return None


def create_session(user_id: int, duration_hours: int = 24 * 7, user_agent: str = None, ip_address: str = None) -> Session:
    """Create a new session for a user. Default duration is 7 days."""
    token = _generate_token()
    now = int(time.time() * 1000)
    expires_at = now + (duration_hours * 60 * 60 * 1000)
    
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO sessions (token, user_id, created_at, expires_at, user_agent, ip_address)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (token, user_id, now, expires_at, user_agent, ip_address))
        conn.commit()
    
    return Session(token=token, user_id=user_id, created_at=now, expires_at=expires_at)


def validate_session(token: str) -> Optional[User]:
    """Validate a session token. Returns User if valid, None otherwise."""
    if not token:
        return None
    
    now = int(time.time() * 1000)
    
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT u.id, u.username, u.display_name, u.created_at
            FROM sessions s
            JOIN users u ON s.user_id = u.id
            WHERE s.token = ? AND s.expires_at > ?
        """, (token, now))
        row = cursor.fetchone()
        
        if not row:
            return None
        
        return User(
            id=row['id'],
            username=row['username'],
            display_name=row['display_name'],
            created_at=row['created_at']
        )


def delete_session(token: str) -> bool:
    """Delete a session (logout). Returns True if session existed."""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM sessions WHERE token = ?", (token,))
        conn.commit()
        return cursor.rowcount > 0


def cleanup_expired_sessions() -> int:
    """Delete expired sessions. Returns count of removed sessions."""
    now = int(time.time() * 1000)
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM sessions WHERE expires_at < ?", (now,))
        count = cursor.rowcount
        conn.commit()
    return count


# Chat history functions

def save_user_threads(user_id: int, threads: List[Dict[str, Any]]) -> bool:
    """Save all chat threads for a user (full sync)."""
    now = int(time.time() * 1000)
    
    with get_db() as conn:
        cursor = conn.cursor()
        
        # Get existing thread IDs
        cursor.execute("SELECT id FROM user_chat_threads WHERE user_id = ?", (user_id,))
        existing_ids = {row['id'] for row in cursor.fetchall()}
        
        incoming_ids = {t['id'] for t in threads}
        
        # Delete threads that no longer exist
        to_delete = existing_ids - incoming_ids
        if to_delete:
            cursor.executemany(
                "DELETE FROM user_chat_threads WHERE id = ? AND user_id = ?",
                [(tid, user_id) for tid in to_delete]
            )
        
        # Upsert threads
        for thread in threads:
            messages_json = json.dumps(thread.get('messages', []))
            cursor.execute("""
                INSERT INTO user_chat_threads (id, user_id, title, messages, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    title = excluded.title,
                    messages = excluded.messages,
                    updated_at = excluded.updated_at
            """, (
                thread['id'],
                user_id,
                thread.get('title', 'Untitled'),
                messages_json,
                thread.get('createdAt', now),
                thread.get('updatedAt', now)
            ))
        
        conn.commit()
        return True


def load_user_threads(user_id: int) -> List[Dict[str, Any]]:
    """Load all chat threads for a user."""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, title, messages, created_at, updated_at
            FROM user_chat_threads
            WHERE user_id = ?
            ORDER BY updated_at DESC
        """, (user_id,))
        
        threads = []
        for row in cursor.fetchall():
            try:
                messages = json.loads(row['messages'])
            except json.JSONDecodeError:
                messages = []
            
            threads.append({
                'id': row['id'],
                'title': row['title'],
                'messages': messages,
                'createdAt': row['created_at'],
                'updatedAt': row['updated_at']
            })
        
        return threads


def get_user_by_id(user_id: int) -> Optional[User]:
    """Get user by ID."""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, username, display_name, created_at
            FROM users WHERE id = ?
        """, (user_id,))
        row = cursor.fetchone()
        
        if not row:
            return None
        
        return User(
            id=row['id'],
            username=row['username'],
            display_name=row['display_name'],
            created_at=row['created_at']
        )


def update_user_display_name(user_id: int, display_name: str) -> bool:
    """Update user's display name."""
    now = int(time.time() * 1000)
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE users SET display_name = ?, updated_at = ?
            WHERE id = ?
        """, (display_name, now, user_id))
        conn.commit()
        return cursor.rowcount > 0


# ---------------------------------------------------------------------------
# User settings (key-value store per user)
# ---------------------------------------------------------------------------

# Default cloud settings
CLOUD_SETTING_DEFAULTS: Dict[str, str] = {
    "cloud_slot_classification": "off",
    "cloud_nli_contradiction": "off",
    "cloud_reflection_validation": "off",
    "cloud_escalation_policy": "conservative",
    "cloud_confidence_threshold": "0.8",
    "cloud_daily_limit_multiplier": "1.0",
    # Claude (Tier 2/3) settings
    "cloud_claude_enabled": "false",
    "cloud_claude_generation": "true",
    "cloud_claude_reflection": "true",
    "cloud_claude_daily_limit": "20",
    "cloud_claude_max_tokens": "4096",
    # Primary generation mode: "local" | "cloud_openai" | "cloud_claude"
    "generation_mode": "local",
    "network_ollama_model": "",
    "cloud_model_openai": "gpt-4o-mini",
    "cloud_model_claude": "claude-sonnet-4-20250514",
    # Intuition Check (Sprint 8+)
    "intuition_check_enabled": "true",
    "intuition_check_clarify": "true",
    "intuition_check_suggest": "true",
    "intuition_check_reconnect": "true",
    "intuition_check_model": "gpt-4o-mini",
    "intuition_check_escalation": "cloud_first",
    # Advanced settings
    "bypass_crt": "false",
    "enable_tooling": "false",
    # Profile — explicit user-controlled identity fields
    "preferred_nickname": "",
    "agent_name": "Aether",
    # Desktop control (Sprint 11)
    "desktop_control_enabled": "false",
    "desktop_max_actions_per_session": "50",
    "desktop_max_steps_per_task": "15",
    "desktop_heartbeat_idle_control": "false",
    "desktop_idle_task": "",
    "desktop_require_confirmation": "dangerous_only",
    "desktop_vision_provider": "cookie",
    # Intent routing (Sprint 13 / v2.9)
    "routing_mode": "local_only",
    "routing_llm_model": "",
    # Response synthesis (v2.9.1)
    "synthesis_enabled": "true",
    # Heartbeat & proactivity
    "heartbeat_enabled": "true",
    "heartbeat_interval_seconds": "1800",
    "heartbeat_active_hours_start": "",
    "heartbeat_active_hours_end": "",
    "heartbeat_news_monitoring": "false",
    "heartbeat_news_topics": "",
    "heartbeat_curiosity_enabled": "true",
    # Behavior
    "greeting_enabled": "true",
    "greeting_style": "time_based",
    "conflict_warning_enabled": "true",
    "provenance_enabled": "true",
    "provenance_world_check": "false",
    # Background jobs
    "background_jobs_enabled": "false",
    "background_auto_resolve": "false",
    "background_auto_research": "false",
    "background_auto_learning": "false",
    # Web search
    "web_search_max_results": "8",
    "web_search_region": "us-en",
    # Tooling (v3.1.1) — model roles
    "tooling_model_role_fast": "",
    "tooling_model_role_reasoning": "",
    "tooling_model_role_tool_loop": "",
    "tooling_model_role_answer": "",
    # Tooling — fallback policy
    "tooling_fallback_policy": "local_only",
    # Tooling — agent loop
    "tooling_agent_loop_enabled": "true",
    "tooling_agent_loop_max_iterations": "10",
    "tooling_agent_loop_show_thinking": "true",
    # Tooling — per-tool enable/disable (all on by default)
    "tooling_tool_enabled_system_info": "true",
    "tooling_tool_enabled_file_read": "true",
    "tooling_tool_enabled_file_write": "true",
    "tooling_tool_enabled_dir_list": "true",
    "tooling_tool_enabled_project_scan": "true",
    "tooling_tool_enabled_shell_exec": "true",
    "tooling_tool_enabled_git_exec": "true",
    "tooling_tool_enabled_fetch_url": "true",
    "tooling_tool_enabled_desktop_action": "true",
    "tooling_tool_enabled_create_commitment": "true",
    "tooling_tool_enabled_list_commitments": "true",
    "tooling_tool_enabled_cancel_commitment": "true",
    "tooling_tool_enabled_generate_content": "true",
    "tooling_tool_enabled_memory_recall": "true",
    "tooling_tool_enabled_http_post": "true",
    "tooling_tool_enabled_http_get_json": "true",
    "tooling_tool_enabled_store_credential": "true",
    "tooling_tool_enabled_web_browse": "true",
    "tooling_tool_enabled_web_search": "true",
}


def get_user_settings(user_id: int) -> Dict[str, str]:
    """Get all settings for a user, merged with defaults."""
    result = dict(CLOUD_SETTING_DEFAULTS)
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT key, value FROM user_settings WHERE user_id = ?", (user_id,))
        for row in cursor.fetchall():
            result[row["key"]] = row["value"]
    return result


def get_user_setting(user_id: int, key: str, default: Optional[str] = None) -> Optional[str]:
    """Get a single setting for a user."""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT value FROM user_settings WHERE user_id = ? AND key = ?",
            (user_id, key),
        )
        row = cursor.fetchone()
        if row:
            return row["value"]
    # Fall back to built-in defaults, then caller default
    return CLOUD_SETTING_DEFAULTS.get(key, default)


def set_user_setting(user_id: int, key: str, value: str) -> None:
    """Set (upsert) a single setting for a user."""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """INSERT INTO user_settings (user_id, key, value) VALUES (?, ?, ?)
               ON CONFLICT(user_id, key) DO UPDATE SET value = excluded.value""",
            (user_id, key, value),
        )
        conn.commit()


# Lazy initialization — call init_auth_db() explicitly at app startup, not on import
_db_initialized = False

def ensure_db_initialized():
    """Initialize auth DB if not already done. Call at app startup."""
    global _db_initialized
    if not _db_initialized:
        init_auth_db()
        _db_initialized = True

