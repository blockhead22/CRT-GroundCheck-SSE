"""
Authentication module for CRT.
Simple session-based auth with SQLite storage.
"""

import sqlite3
import hashlib
import secrets
import time
import json
from pathlib import Path
from typing import Optional, Dict, Any, List
from dataclasses import dataclass, asdict
from contextlib import contextmanager

AUTH_DB_PATH = Path(__file__).parent / "data" / "auth.db"


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
    """Hash password with salt using SHA-256."""
    return hashlib.sha256((password + salt).encode()).hexdigest()


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
        
        # Create indexes
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_sessions_user ON sessions(user_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_sessions_expires ON sessions(expires_at)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_threads_user ON user_chat_threads(user_id)")
        
        conn.commit()
        print(f"Auth database initialized at {AUTH_DB_PATH}")


def register_user(username: str, password: str, display_name: Optional[str] = None, email: Optional[str] = None) -> Optional[User]:
    """Register a new user. Returns User on success, None if username taken."""
    username = username.lower().strip()
    display_name = display_name or username
    
    if len(username) < 3:
        raise ValueError("Username must be at least 3 characters")
    if len(password) < 4:
        raise ValueError("Password must be at least 4 characters")
    
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
    
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, username, password_hash, password_salt, display_name, created_at
            FROM users WHERE username = ?
        """, (username,))
        row = cursor.fetchone()
        
        if not row:
            return None
        
        expected_hash = _hash_password(password, row['password_salt'])
        if expected_hash != row['password_hash']:
            return None
        
        return User(
            id=row['id'],
            username=row['username'],
            display_name=row['display_name'],
            created_at=row['created_at']
        )


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


def cleanup_expired_sessions():
    """Remove expired sessions from the database."""
    now = int(time.time() * 1000)
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM sessions WHERE expires_at < ?", (now,))
        conn.commit()
        return cursor.rowcount


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


# Initialize on import
init_auth_db()
