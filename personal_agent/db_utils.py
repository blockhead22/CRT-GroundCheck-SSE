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
                user_name TEXT
            )
        """)
        
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
        
        conn.commit()
        conn.close()
    
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
        cursor.execute("""
            INSERT INTO thread_sessions 
            (thread_id, first_created, last_active, message_count, greeting_shown, 
             onboarding_completed, onboarding_step, user_name)
            VALUES (?, ?, ?, 0, 0, 0, 0, NULL)
        """, (thread_id, now, now))
        
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
