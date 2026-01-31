"""Database utilities for handling SQLite locks and concurrent access."""

import sqlite3
import time
import logging
from typing import Callable, TypeVar, Optional
from contextlib import contextmanager

logger = logging.getLogger(__name__)

T = TypeVar('T')


def retry_on_lock(
    func: Callable[[], T],
    max_retries: int = 5,
    initial_delay: float = 0.1,
    max_delay: float = 2.0,
    backoff_factor: float = 2.0
) -> T:
    """
    Retry a database operation on lock errors with exponential backoff.
    
    Args:
        func: Function to execute (should be idempotent for writes)
        max_retries: Maximum number of retry attempts
        initial_delay: Initial delay in seconds
        max_delay: Maximum delay between retries
        backoff_factor: Multiplier for delay after each retry
    
    Returns:
        Result of func()
    
    Raises:
        sqlite3.OperationalError: If all retries exhausted
    """
    delay = initial_delay
    last_error = None
    
    for attempt in range(max_retries + 1):
        try:
            return func()
        except sqlite3.OperationalError as e:
            last_error = e
            error_msg = str(e).lower()
            
            # Only retry on lock errors
            if 'locked' not in error_msg and 'busy' not in error_msg:
                raise
            
            if attempt < max_retries:
                logger.debug(f"[DB_RETRY] Database locked, retry {attempt + 1}/{max_retries} after {delay:.2f}s")
                time.sleep(delay)
                delay = min(delay * backoff_factor, max_delay)
            else:
                logger.error(f"[DB_RETRY] All retries exhausted: {e}")
                raise
    
    # Should never reach here, but for type safety
    raise last_error if last_error else sqlite3.OperationalError("Retry failed")


@contextmanager
def get_db_connection(
    db_path: str,
    timeout: float = 30.0,
    enable_wal: bool = True
):
    """
    Context manager for SQLite connections with proper configuration.
    
    Args:
        db_path: Path to database file
        timeout: Connection timeout in seconds
        enable_wal: Enable WAL mode for better concurrency
    
    Yields:
        sqlite3.Connection
    """
    conn = None
    try:
        conn = sqlite3.connect(db_path, timeout=timeout, check_same_thread=False)
        
        if enable_wal:
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA synchronous=NORMAL")
        
        conn.execute(f"PRAGMA busy_timeout={int(timeout * 1000)}")
        
        yield conn
        
    finally:
        if conn:
            try:
                conn.close()
            except Exception as e:
                logger.warning(f"[DB] Error closing connection: {e}")


def execute_with_retry(
    db_path: str,
    query: str,
    params: tuple = (),
    fetch: Optional[str] = None,
    commit: bool = True,
    max_retries: int = 3
):
    """
    Execute a SQL query with automatic retry on lock errors.
    
    Args:
        db_path: Database path
        query: SQL query
        params: Query parameters
        fetch: 'one', 'all', or None
        commit: Whether to commit transaction
        max_retries: Maximum retry attempts
    
    Returns:
        Query result if fetch specified, else None
    """
    def _execute():
        with get_db_connection(db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(query, params)
            
            result = None
            if fetch == 'one':
                result = cursor.fetchone()
            elif fetch == 'all':
                result = cursor.fetchall()
            
            if commit:
                conn.commit()
            
            return result
    
    return retry_on_lock(_execute, max_retries=max_retries)


# ============================================================================
# Thread Session Tracking Database
# ============================================================================

class ThreadSessionDB:
    """
    Tracks per-thread session state: first_created, last_active, message_count,
    greeting_shown, onboarding_completed, and recent query history for response variation.
    
    This enables:
    - Time-based greetings ("Welcome back! It's been 3 days since we last chatted.")
    - Onboarding flow state tracking (which questions have been asked)
    - Response variation detection (avoid repetitive answers to same questions)
    """
    
    DEFAULT_PATH = "personal_agent/crt_thread_sessions.db"

    HUMOR_CUES = (
        "lmao", "lol", "haha", "hehe", "rofl", "jk", "kidding",
        "😂", "🤣", "😅", "😆", "🙃", "goofy", "silly", "bro", "dude"
    )
    SERIOUS_CUES = (
        "depressed", "depression", "suicide", "self-harm", "self harm",
        "cancer", "leukemia", "health battle", "diagnosed", "hospital",
        "grief", "trauma", "ptsd", "anxiety", "panic"
    )
    
    def __init__(self, db_path: Optional[str] = None):
        self.db_path = db_path or self.DEFAULT_PATH
        self._init_db()
    
    def _get_connection(self) -> sqlite3.Connection:
        """Create properly configured SQLite connection."""
        conn = sqlite3.connect(self.db_path, timeout=30.0)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
        conn.execute("PRAGMA busy_timeout=30000")
        conn.row_factory = sqlite3.Row
        return conn
    
    def _init_db(self):
        """Initialize thread sessions database schema."""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        # Main sessions table: tracks thread lifecycle
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS thread_sessions (
                thread_id TEXT PRIMARY KEY,
                first_created REAL NOT NULL,
                last_active REAL NOT NULL,
                message_count INTEGER DEFAULT 0,
                greeting_shown INTEGER DEFAULT 0,
                onboarding_completed INTEGER DEFAULT 0,
                onboarding_step INTEGER DEFAULT 0,
                user_name TEXT,
                style_profile_json TEXT
            )
        """)

        # Ensure new columns exist for older DBs
        self._ensure_columns(
            cursor,
            "thread_sessions",
            {
                "style_profile_json": "TEXT",
                "journal_auto_reply_enabled": "INTEGER",
                "journal_auto_reply_updated_at": "REAL",
                "heartbeat_config_json": "TEXT",
                "heartbeat_last_run": "REAL",
                "heartbeat_last_summary": "TEXT",
                "heartbeat_last_actions_json": "TEXT",
            },
        )
        
        # Recent queries table: for response variation detection
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS recent_queries (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                thread_id TEXT NOT NULL,
                query_text TEXT NOT NULL,
                query_normalized TEXT NOT NULL,
                detected_slot TEXT,
                response_text TEXT,
                timestamp REAL NOT NULL,
                FOREIGN KEY (thread_id) REFERENCES thread_sessions(thread_id)
            )
        """)
        
        # Index for fast recent query lookups
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_recent_queries_thread_ts 
            ON recent_queries(thread_id, timestamp DESC)
        """)
        
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_recent_queries_slot 
            ON recent_queries(thread_id, detected_slot, timestamp DESC)
        """)

        # Reflection scorecards (single latest per thread)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS reflection_scorecards (
                thread_id TEXT PRIMARY KEY,
                updated_at REAL NOT NULL,
                scorecard_json TEXT NOT NULL
            )
        """)

        # Personality profiles (single latest per thread)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS personality_profiles (
                thread_id TEXT PRIMARY KEY,
                updated_at REAL NOT NULL,
                profile_json TEXT NOT NULL
            )
        """)

        # Reflection journal entries (append-only log)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS reflection_journal_entries (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                thread_id TEXT NOT NULL,
                created_at REAL NOT NULL,
                entry_type TEXT NOT NULL,
                title TEXT NOT NULL,
                body TEXT NOT NULL,
                meta_json TEXT
            )
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_reflection_journal_thread_ts
            ON reflection_journal_entries(thread_id, created_at DESC)
        """)

        # Heartbeat history (append-only log of heartbeat runs)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS heartbeat_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                thread_id TEXT NOT NULL,
                timestamp REAL NOT NULL,
                summary TEXT,
                actions_json TEXT,
                success INTEGER DEFAULT 1,
                FOREIGN KEY (thread_id) REFERENCES thread_sessions(thread_id)
            )
        """)
        
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_heartbeat_history_thread_ts
            ON heartbeat_history(thread_id, timestamp DESC)
        """)

        # Moltbook-style local forum (posts, comments, votes, submolts)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS molt_submolts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                description TEXT,
                created_at REAL NOT NULL,
                created_by TEXT
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS molt_posts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                submolt TEXT NOT NULL,
                title TEXT NOT NULL,
                content TEXT NOT NULL,
                author TEXT NOT NULL,
                created_at REAL NOT NULL,
                updated_at REAL NOT NULL,
                source_type TEXT,
                source_entry_id INTEGER
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS molt_comments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                post_id INTEGER NOT NULL,
                parent_comment_id INTEGER,
                content TEXT NOT NULL,
                author TEXT NOT NULL,
                created_at REAL NOT NULL,
                FOREIGN KEY (post_id) REFERENCES molt_posts(id)
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS molt_votes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                target_type TEXT NOT NULL,
                target_id INTEGER NOT NULL,
                voter TEXT NOT NULL,
                value INTEGER NOT NULL,
                created_at REAL NOT NULL,
                UNIQUE(target_type, target_id, voter)
            )
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_molt_posts_submolt_ts
            ON molt_posts(submolt, created_at DESC)
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_molt_comments_post_ts
            ON molt_comments(post_id, created_at ASC)
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_molt_votes_target
            ON molt_votes(target_type, target_id)
        """)
        
        conn.commit()
        conn.close()

    def _ensure_columns(self, cursor: sqlite3.Cursor, table: str, columns: dict) -> None:
        """Add missing columns to an existing table (safe migration)."""
        cursor.execute(f"PRAGMA table_info({table})")
        existing = {row[1] for row in cursor.fetchall()}
        for col, col_type in columns.items():
            if col not in existing:
                cursor.execute(f"ALTER TABLE {table} ADD COLUMN {col} {col_type}")
    
    def get_or_create_session(self, thread_id: str) -> dict:
        """
        Get session for thread, creating if needed.
        
        Returns dict with: thread_id, first_created, last_active, message_count,
                          greeting_shown, onboarding_completed, onboarding_step, user_name
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT thread_id, first_created, last_active, message_count,
                   greeting_shown, onboarding_completed, onboarding_step, user_name
            FROM thread_sessions WHERE thread_id = ?
        """, (thread_id,))
        
        row = cursor.fetchone()
        
        if row:
            result = dict(row)
            conn.close()
            return result
        
        # Create new session
        now = time.time()
        try:
            import json
            style_json = json.dumps(self._default_style_profile())
        except Exception:
            style_json = None

        cursor.execute("""
            INSERT INTO thread_sessions 
            (thread_id, first_created, last_active, message_count, greeting_shown, 
             onboarding_completed, onboarding_step, user_name, style_profile_json)
            VALUES (?, ?, ?, 0, 0, 0, 0, NULL, ?)
        """, (thread_id, now, now, style_json))
        
        conn.commit()
        conn.close()
        
        return {
            'thread_id': thread_id,
            'first_created': now,
            'last_active': now,
            'message_count': 0,
            'greeting_shown': False,
            'onboarding_completed': False,
            'onboarding_step': 0,
            'user_name': None,
            'style_profile': self._default_style_profile(),
        }
    
    def update_activity(self, thread_id: str, increment_messages: bool = True) -> dict:
        """
        Update last_active timestamp and optionally increment message count.
        Returns updated session.
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        
        now = time.time()
        
        if increment_messages:
            cursor.execute("""
                UPDATE thread_sessions 
                SET last_active = ?, message_count = message_count + 1
                WHERE thread_id = ?
            """, (now, thread_id))
        else:
            cursor.execute("""
                UPDATE thread_sessions SET last_active = ? WHERE thread_id = ?
            """, (now, thread_id))
        
        conn.commit()
        conn.close()
        
        return self.get_or_create_session(thread_id)
    
    def mark_greeting_shown(self, thread_id: str):
        """Mark that greeting has been shown for this session."""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            UPDATE thread_sessions SET greeting_shown = 1 WHERE thread_id = ?
        """, (thread_id,))
        
        conn.commit()
        conn.close()
    
    def mark_onboarding_completed(self, thread_id: str):
        """Mark onboarding as completed for this thread."""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            UPDATE thread_sessions SET onboarding_completed = 1 WHERE thread_id = ?
        """, (thread_id,))
        
        conn.commit()
        conn.close()
    
    def update_onboarding_step(self, thread_id: str, step: int):
        """Update current onboarding step."""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            UPDATE thread_sessions SET onboarding_step = ? WHERE thread_id = ?
        """, (step, thread_id))
        
        conn.commit()
        conn.close()
    
    def set_user_name(self, thread_id: str, name: str):
        """Store user's name for personalized greetings."""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            UPDATE thread_sessions SET user_name = ? WHERE thread_id = ?
        """, (name, thread_id))
        
        conn.commit()
        conn.close()

    def _default_style_profile(self) -> dict:
        """Default adaptive style profile."""
        return {
            "humor": 0.4,
            "seriousness": 0.4,
            "formality": 0.3,
            "tone_label": "balanced",
            "last_updated": time.time(),
        }

    def get_style_profile(self, thread_id: str) -> dict:
        """Get stored style profile (or default if missing)."""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT style_profile_json
            FROM thread_sessions
            WHERE thread_id = ?
        """, (thread_id,))
        row = cursor.fetchone()
        conn.close()

        if row and row["style_profile_json"]:
            try:
                import json
                return json.loads(row["style_profile_json"])
            except Exception:
                return self._default_style_profile()
        return self._default_style_profile()

    def update_style_profile(self, thread_id: str, user_message: str) -> dict:
        """Update tone profile based on user message cues."""
        profile = self.get_style_profile(thread_id)
        text = (user_message or "")
        lower = text.lower()

        humor_hits = sum(1 for cue in self.HUMOR_CUES if cue in lower)
        serious_hits = sum(1 for cue in self.SERIOUS_CUES if cue in lower)

        humor_delta = min(0.3, humor_hits * 0.1)
        serious_delta = min(0.4, serious_hits * 0.12)

        humor = max(0.0, min(1.0, (profile.get("humor", 0.4) * 0.85) + humor_delta - (serious_delta * 0.2)))
        serious = max(0.0, min(1.0, (profile.get("seriousness", 0.4) * 0.85) + serious_delta - (humor_delta * 0.1)))
        formality = max(0.0, min(1.0, profile.get("formality", 0.3)))

        if humor > 0.55 and serious > 0.55:
            tone_label = "adaptive"
        elif humor - serious >= 0.15:
            tone_label = "playful"
        elif serious - humor >= 0.15:
            tone_label = "serious"
        else:
            tone_label = "balanced"

        profile = {
            "humor": round(humor, 3),
            "seriousness": round(serious, 3),
            "formality": round(formality, 3),
            "tone_label": tone_label,
            "last_updated": time.time(),
        }

        try:
            import json
            conn = self._get_connection()
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE thread_sessions
                SET style_profile_json = ?
                WHERE thread_id = ?
            """, (json.dumps(profile), thread_id))
            conn.commit()
            conn.close()
        except Exception as e:
            logger.debug(f"[STYLE] Failed to update style profile: {e}")

        return profile

    def get_journal_auto_reply_enabled(self, thread_id: str) -> Optional[bool]:
        """Get per-thread override for journal auto replies (None if unset)."""
        self.get_or_create_session(thread_id)
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT journal_auto_reply_enabled
            FROM thread_sessions
            WHERE thread_id = ?
        """, (thread_id,))
        row = cursor.fetchone()
        conn.close()
        if not row:
            return None
        value = row["journal_auto_reply_enabled"]
        if value is None:
            return None
        try:
            return bool(int(value))
        except Exception:
            return None

    def set_journal_auto_reply_enabled(self, thread_id: str, enabled: bool) -> None:
        """Set per-thread override for journal auto replies."""
        self.get_or_create_session(thread_id)
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE thread_sessions
            SET journal_auto_reply_enabled = ?, journal_auto_reply_updated_at = ?
            WHERE thread_id = ?
        """, (1 if enabled else 0, time.time(), thread_id))
        conn.commit()
        conn.close()

    def get_heartbeat_config(self, thread_id: str) -> Optional[dict]:
        """Get per-thread heartbeat config override (None if unset)."""
        import json
        self.get_or_create_session(thread_id)
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT heartbeat_config_json
            FROM thread_sessions
            WHERE thread_id = ?
        """, (thread_id,))
        row = cursor.fetchone()
        conn.close()
        if not row:
            return None
        raw = row["heartbeat_config_json"]
        if not raw:
            return None
        try:
            return json.loads(raw)
        except Exception:
            return None

    def set_heartbeat_config(self, thread_id: str, config: dict) -> None:
        """Set per-thread heartbeat config override."""
        import json
        self.get_or_create_session(thread_id)
        payload = json.dumps(config or {})
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE thread_sessions
            SET heartbeat_config_json = ?
            WHERE thread_id = ?
        """, (payload, thread_id))
        conn.commit()
        conn.close()

    def get_heartbeat_state(self, thread_id: str) -> dict:
        """Get last heartbeat run metadata for a thread."""
        import json
        self.get_or_create_session(thread_id)
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT heartbeat_last_run, heartbeat_last_summary, heartbeat_last_actions_json
            FROM thread_sessions
            WHERE thread_id = ?
        """, (thread_id,))
        row = cursor.fetchone()
        conn.close()
        if not row:
            return {"last_run": None, "last_summary": None, "last_actions": []}
        actions = []
        if row["heartbeat_last_actions_json"]:
            try:
                actions = json.loads(row["heartbeat_last_actions_json"])
            except Exception:
                actions = []
        return {
            "last_run": row["heartbeat_last_run"],
            "last_summary": row["heartbeat_last_summary"],
            "last_actions": actions,
        }

    def update_heartbeat_state(
        self,
        thread_id: str,
        *,
        last_run: float,
        summary: Optional[str],
        actions: Optional[list[dict]] = None,
    ) -> None:
        """Store last heartbeat run metadata and add to history."""
        import json
        self.get_or_create_session(thread_id)
        payload = json.dumps(actions or [])
        conn = self._get_connection()
        cursor = conn.cursor()
        
        # Update latest state
        cursor.execute("""
            UPDATE thread_sessions
            SET heartbeat_last_run = ?, heartbeat_last_summary = ?, heartbeat_last_actions_json = ?
            WHERE thread_id = ?
        """, (last_run, summary, payload, thread_id))
        
        # Add to history
        success = 1 if actions and any(a.get("success") for a in actions) else 1
        cursor.execute("""
            INSERT INTO heartbeat_history (thread_id, timestamp, summary, actions_json, success)
            VALUES (?, ?, ?, ?, ?)
        """, (thread_id, last_run, summary, payload, success))
        
        conn.commit()
        conn.close()
    
    def get_heartbeat_history(self, thread_id: str, limit: int = 10) -> list[dict]:
        """Get recent heartbeat history for a thread."""
        import json
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT timestamp, summary, actions_json, success
            FROM heartbeat_history
            WHERE thread_id = ?
            ORDER BY timestamp DESC
            LIMIT ?
        """, (thread_id, limit))
        rows = cursor.fetchall()
        conn.close()
        
        history = []
        for row in rows:
            actions = []
            if row["actions_json"]:
                try:
                    actions = json.loads(row["actions_json"])
                except Exception:
                    pass
            history.append({
                "timestamp": row["timestamp"],
                "summary": row["summary"] or "",
                "actions": actions,
                "success": bool(row["success"]),
            })
        return history
    
    # ====== Recent Query Tracking for Response Variation ======
    
    def record_query(
        self, 
        thread_id: str, 
        query_text: str, 
        response_text: str,
        detected_slot: Optional[str] = None
    ):
        """
        Record a query and response for variation tracking.
        
        Args:
            thread_id: Thread identifier
            query_text: Original user query
            response_text: Response given
            detected_slot: If this was a slot query (e.g., "name", "employer")
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        
        # Normalize query for comparison
        query_normalized = self._normalize_query(query_text)
        
        cursor.execute("""
            INSERT INTO recent_queries 
            (thread_id, query_text, query_normalized, detected_slot, response_text, timestamp)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (thread_id, query_text, query_normalized, detected_slot, response_text, time.time()))
        
        conn.commit()
        
        # Cleanup old entries (keep last 50 per thread)
        cursor.execute("""
            DELETE FROM recent_queries 
            WHERE thread_id = ? AND id NOT IN (
                SELECT id FROM recent_queries 
                WHERE thread_id = ? 
                ORDER BY timestamp DESC LIMIT 50
            )
        """, (thread_id, thread_id))
        
        conn.commit()
        conn.close()
    
    def get_recent_slot_queries(
        self, 
        thread_id: str, 
        slot: str, 
        window: int = 5
    ) -> list:
        """
        Get recent queries for a specific slot within message window.
        
        Args:
            thread_id: Thread identifier
            slot: Slot name (e.g., "name", "employer")
            window: Number of recent messages to check
            
        Returns:
            List of dicts with query_text, response_text, timestamp
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT query_text, response_text, timestamp
            FROM recent_queries
            WHERE thread_id = ? AND detected_slot = ?
            ORDER BY timestamp DESC
            LIMIT ?
        """, (thread_id, slot, window))
        
        results = [dict(row) for row in cursor.fetchall()]
        conn.close()
        
        return results
    
    def get_recent_queries(self, thread_id: str, window: int = 5) -> list:
        """
        Get all recent queries within message window (for duplicate detection).
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT query_text, query_normalized, detected_slot, response_text, timestamp
            FROM recent_queries
            WHERE thread_id = ?
            ORDER BY timestamp DESC
            LIMIT ?
        """, (thread_id, window))
        
        results = [dict(row) for row in cursor.fetchall()]
        conn.close()
        
        return results

    def list_threads(self, limit: int = 200) -> list[str]:
        """List active thread IDs by most recent activity."""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT thread_id
            FROM thread_sessions
            ORDER BY last_active DESC
            LIMIT ?
        """, (limit,))
        results = [row["thread_id"] for row in cursor.fetchall()]
        conn.close()
        return results

    def store_reflection_scorecard(self, thread_id: str, scorecard: dict) -> None:
        """Upsert the latest reflection scorecard for a thread."""
        import json
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO reflection_scorecards (thread_id, updated_at, scorecard_json)
            VALUES (?, ?, ?)
            ON CONFLICT(thread_id) DO UPDATE SET
                updated_at = excluded.updated_at,
                scorecard_json = excluded.scorecard_json
        """, (thread_id, time.time(), json.dumps(scorecard)))
        conn.commit()
        conn.close()

    def get_reflection_scorecard(self, thread_id: str) -> dict | None:
        """Fetch latest reflection scorecard, if available."""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT scorecard_json
            FROM reflection_scorecards
            WHERE thread_id = ?
        """, (thread_id,))
        row = cursor.fetchone()
        conn.close()
        if not row:
            return None
        try:
            import json
            return json.loads(row["scorecard_json"])
        except Exception:
            return None

    def store_personality_profile(self, thread_id: str, profile: dict) -> None:
        """Upsert the latest personality profile for a thread."""
        import json
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO personality_profiles (thread_id, updated_at, profile_json)
            VALUES (?, ?, ?)
            ON CONFLICT(thread_id) DO UPDATE SET
                updated_at = excluded.updated_at,
                profile_json = excluded.profile_json
        """, (thread_id, time.time(), json.dumps(profile)))
        conn.commit()
        conn.close()

    def get_personality_profile(self, thread_id: str) -> dict | None:
        """Fetch latest personality profile, if available."""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT profile_json
            FROM personality_profiles
            WHERE thread_id = ?
        """, (thread_id,))
        row = cursor.fetchone()
        conn.close()
        if not row:
            return None
        try:
            import json
            return json.loads(row["profile_json"])
        except Exception:
            return None

    def add_reflection_journal_entry(
        self,
        thread_id: str,
        entry_type: str,
        title: str,
        body: str,
        meta: Optional[dict] = None,
    ) -> int:
        """Append a reflection journal entry for a thread."""
        import json
        created_at = time.time()
        meta_json = json.dumps(meta) if meta else None
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO reflection_journal_entries
            (thread_id, created_at, entry_type, title, body, meta_json)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (thread_id, created_at, entry_type, title, body, meta_json))
        entry_id = cursor.lastrowid
        conn.commit()
        conn.close()
        return int(entry_id) if entry_id is not None else -1

    def get_reflection_journal_entries(self, thread_id: str, limit: int = 50) -> list[dict]:
        """Fetch reflection journal entries for a thread (most recent first)."""
        import json
        limit = max(1, min(int(limit or 50), 200))
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, thread_id, created_at, entry_type, title, body, meta_json
            FROM reflection_journal_entries
            WHERE thread_id = ?
            ORDER BY created_at DESC
            LIMIT ?
        """, (thread_id, limit))
        rows = cursor.fetchall()
        conn.close()
        out = []
        for row in rows:
            meta = None
            if row["meta_json"]:
                try:
                    meta = json.loads(row["meta_json"])
                except Exception:
                    meta = None
            out.append({
                "id": row["id"],
                "thread_id": row["thread_id"],
                "created_at": row["created_at"],
                "entry_type": row["entry_type"],
                "title": row["title"],
                "body": row["body"],
                "meta": meta,
            })
        return out

    def get_reflection_journal_entry(self, thread_id: str, entry_id: int) -> Optional[dict]:
        """Fetch a single reflection journal entry by id."""
        import json
        if not entry_id:
            return None
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, thread_id, created_at, entry_type, title, body, meta_json
            FROM reflection_journal_entries
            WHERE thread_id = ? AND id = ?
        """, (thread_id, entry_id))
        row = cursor.fetchone()
        conn.close()
        if not row:
            return None
        meta = None
        if row["meta_json"]:
            try:
                meta = json.loads(row["meta_json"])
            except Exception:
                meta = None
        return {
            "id": row["id"],
            "thread_id": row["thread_id"],
            "created_at": row["created_at"],
            "entry_type": row["entry_type"],
            "title": row["title"],
            "body": row["body"],
            "meta": meta,
        }

    # ====== Moltbook-style local forum ======

    def list_submolts(self, limit: int = 50) -> list[dict]:
        """List available submolts."""
        limit = max(1, min(int(limit or 50), 200))
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, name, description, created_at, created_by
            FROM molt_submolts
            ORDER BY name ASC
            LIMIT ?
        """, (limit,))
        rows = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return rows

    def create_submolt(self, name: str, description: str = "", created_by: Optional[str] = None) -> dict:
        """Create a submolt (if it doesn't exist)."""
        clean_name = (name or "").strip().lower().replace(" ", "_")
        if not clean_name:
            raise ValueError("Submolt name required")
        desc = (description or "").strip() or None
        created_at = time.time()
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT OR IGNORE INTO molt_submolts (name, description, created_at, created_by)
            VALUES (?, ?, ?, ?)
        """, (clean_name, desc, created_at, created_by))
        conn.commit()
        cursor.execute("""
            SELECT id, name, description, created_at, created_by
            FROM molt_submolts
            WHERE name = ?
        """, (clean_name,))
        row = cursor.fetchone()
        conn.close()
        return dict(row) if row else {
            "id": None,
            "name": clean_name,
            "description": desc,
            "created_at": created_at,
            "created_by": created_by,
        }

    def ensure_default_submolts(self) -> None:
        """Ensure baseline submolts exist."""
        defaults = [
            ("reflections", "Agent self-reflections and internal notes."),
            ("debugging", "Bug hunts, fixes, and debugging notes."),
            ("agent-ops", "Operational tips for running agents."),
        ]
        for name, desc in defaults:
            try:
                self.create_submolt(name=name, description=desc, created_by="system")
            except Exception:
                continue

    def create_post(
        self,
        submolt: str,
        title: str,
        content: str,
        author: str,
        source_type: Optional[str] = None,
        source_entry_id: Optional[int] = None,
    ) -> dict:
        """Create a Moltbook post."""
        if not submolt:
            raise ValueError("submolt required")
        if not title or not content:
            raise ValueError("title and content required")
        now = time.time()
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO molt_posts
            (submolt, title, content, author, created_at, updated_at, source_type, source_entry_id)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (submolt, title, content, author, now, now, source_type, source_entry_id))
        post_id = cursor.lastrowid
        conn.commit()
        conn.close()
        return {
            "id": int(post_id) if post_id is not None else None,
            "submolt": submolt,
            "title": title,
            "content": content,
            "author": author,
            "created_at": now,
            "updated_at": now,
            "source_type": source_type,
            "source_entry_id": source_entry_id,
        }

    def list_posts(self, submolt: Optional[str] = None, sort: str = "new", limit: int = 50, offset: int = 0) -> list[dict]:
        """List posts, optionally filtered by submolt."""
        limit = max(1, min(int(limit or 50), 200))
        offset = max(0, int(offset or 0))
        conn = self._get_connection()
        cursor = conn.cursor()
        if submolt:
            cursor.execute("""
                SELECT p.id, p.submolt, p.title, p.content, p.author, p.created_at, p.updated_at,
                       p.source_type, p.source_entry_id,
                       COALESCE(SUM(v.value), 0) AS score
                FROM molt_posts p
                LEFT JOIN molt_votes v
                  ON v.target_type = 'post' AND v.target_id = p.id
                WHERE p.submolt = ?
                GROUP BY p.id
                ORDER BY p.created_at DESC
                LIMIT ? OFFSET ?
            """, (submolt, limit, offset))
        else:
            cursor.execute("""
                SELECT p.id, p.submolt, p.title, p.content, p.author, p.created_at, p.updated_at,
                       p.source_type, p.source_entry_id,
                       COALESCE(SUM(v.value), 0) AS score
                FROM molt_posts p
                LEFT JOIN molt_votes v
                  ON v.target_type = 'post' AND v.target_id = p.id
                GROUP BY p.id
                ORDER BY p.created_at DESC
                LIMIT ? OFFSET ?
            """, (limit, offset))
        rows = [dict(row) for row in cursor.fetchall()]
        conn.close()

        if sort and sort != "new":
            now = time.time()
            if sort == "top":
                rows.sort(key=lambda r: (r.get("score", 0), r.get("created_at", 0)), reverse=True)
            elif sort == "hot":
                def _hot_score(row):
                    age_hours = max(0.1, (now - float(row.get("created_at") or now)) / 3600.0)
                    score = float(row.get("score") or 0)
                    return score / ((age_hours + 2.0) ** 1.3)
                rows.sort(key=_hot_score, reverse=True)
        return rows

    def get_post(self, post_id: int) -> Optional[dict]:
        """Fetch a single post with score."""
        if not post_id:
            return None
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT p.id, p.submolt, p.title, p.content, p.author, p.created_at, p.updated_at,
                   p.source_type, p.source_entry_id,
                   COALESCE(SUM(v.value), 0) AS score
            FROM molt_posts p
            LEFT JOIN molt_votes v
              ON v.target_type = 'post' AND v.target_id = p.id
            WHERE p.id = ?
            GROUP BY p.id
        """, (post_id,))
        row = cursor.fetchone()
        conn.close()
        return dict(row) if row else None

    def create_comment(
        self,
        post_id: int,
        content: str,
        author: str,
        parent_comment_id: Optional[int] = None,
    ) -> dict:
        """Create a comment."""
        if not post_id:
            raise ValueError("post_id required")
        if not content:
            raise ValueError("content required")
        now = time.time()
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO molt_comments
            (post_id, parent_comment_id, content, author, created_at)
            VALUES (?, ?, ?, ?, ?)
        """, (post_id, parent_comment_id, content, author, now))
        comment_id = cursor.lastrowid
        conn.commit()
        conn.close()
        return {
            "id": int(comment_id) if comment_id is not None else None,
            "post_id": post_id,
            "parent_comment_id": parent_comment_id,
            "content": content,
            "author": author,
            "created_at": now,
        }

    def list_comments(self, post_id: int) -> list[dict]:
        """List comments for a post (chronological)."""
        if not post_id:
            return []
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT c.id, c.post_id, c.parent_comment_id, c.content, c.author, c.created_at,
                   COALESCE(SUM(v.value), 0) AS score
            FROM molt_comments c
            LEFT JOIN molt_votes v
              ON v.target_type = 'comment' AND v.target_id = c.id
            WHERE c.post_id = ?
            GROUP BY c.id
            ORDER BY c.created_at ASC
        """, (post_id,))
        rows = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return rows

    def get_posts_mentioning(self, agent_name: str = "agent", since_timestamp: Optional[float] = None, limit: int = 10) -> list[dict]:
        """Find posts that mention the agent by name."""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        # Search for mentions like @agent or just "agent" in content
        patterns = [f"@{agent_name}", agent_name.lower(), f" {agent_name} ", f"@{agent_name.lower()}"]
        
        query = """
            SELECT p.id, p.submolt, p.title, p.content, p.author, p.created_at,
                   COALESCE(SUM(v.value), 0) AS score
            FROM molt_posts p
            LEFT JOIN molt_votes v
              ON v.target_type = 'post' AND v.target_id = p.id
            WHERE (LOWER(p.content) LIKE ? OR LOWER(p.title) LIKE ?)
        """
        params = [f"%{agent_name.lower()}%", f"%{agent_name.lower()}%"]
        
        if since_timestamp:
            query += " AND p.created_at > ?"
            params.append(since_timestamp)
        
        query += """
            GROUP BY p.id
            ORDER BY p.created_at DESC
            LIMIT ?
        """
        params.append(limit)
        
        cursor.execute(query, params)
        rows = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return rows

    def cast_vote(self, target_type: str, target_id: int, voter: str, value: int) -> dict:
        """Upsert a vote (+1 / -1)."""
        if target_type not in ("post", "comment"):
            raise ValueError("invalid target_type")
        if not target_id:
            raise ValueError("target_id required")
        val = 1 if value > 0 else -1
        now = time.time()
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO molt_votes (target_type, target_id, voter, value, created_at)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(target_type, target_id, voter)
            DO UPDATE SET value = excluded.value, created_at = excluded.created_at
        """, (target_type, target_id, voter, val, now))
        conn.commit()
        conn.close()
        return {
            "target_type": target_type,
            "target_id": target_id,
            "voter": voter,
            "value": val,
            "created_at": now,
        }
    
    def _normalize_query(self, query: str) -> str:
        """Normalize query for comparison (lowercase, strip punctuation)."""
        import re
        normalized = query.lower().strip()
        normalized = re.sub(r'[^\w\s]', '', normalized)
        normalized = re.sub(r'\s+', ' ', normalized)
        return normalized
    
    def is_repeated_slot_query(self, thread_id: str, slot: str, window: int = 5) -> bool:
        """
        Check if user has asked about this slot recently.
        Used to trigger response variation.
        """
        recent = self.get_recent_slot_queries(thread_id, slot, window)
        return len(recent) > 0


# Global instance for easy access
_thread_session_db: Optional[ThreadSessionDB] = None


def get_thread_session_db() -> ThreadSessionDB:
    """Get or create global ThreadSessionDB instance."""
    global _thread_session_db
    if _thread_session_db is None:
        _thread_session_db = ThreadSessionDB()
    return _thread_session_db
