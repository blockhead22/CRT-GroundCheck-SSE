"""
MySQL Authentication module for CRT.
Session-based auth with MySQL storage on nickblockdesigns.com.
"""

import pymysql
import hashlib
import secrets
import time
import json
import os
import re
import bcrypt
import threading
from collections import defaultdict
from typing import Optional, Dict, Any, List
from dataclasses import dataclass, asdict
from contextlib import contextmanager
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Rate limiting: track failed login attempts per username
_login_attempts: Dict[str, list] = defaultdict(list)
_login_lock = threading.Lock()
_RATE_LIMIT_WINDOW = 300     # 5 minute window
_RATE_LIMIT_MAX_ATTEMPTS = 5  # max failures per window

# MySQL Configuration
MYSQL_CONFIG = {
    'host': os.getenv('MYSQL_HOST', 'nickblockdesigns.com'),
    'user': os.getenv('MYSQL_USER', 'crt_api'),
    'password': os.getenv('MYSQL_PASSWORD', ''),
    'database': os.getenv('MYSQL_DATABASE', 'crt_users'),
    'port': int(os.getenv('MYSQL_PORT', 3306)),
    'charset': 'utf8mb4',
    'cursorclass': pymysql.cursors.DictCursor,
    'autocommit': False
}


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
    """Hash password with bcrypt (salt parameter kept for interface compatibility)."""
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')


def _verify_password(password: str, stored_hash: str) -> bool:
    """Verify password against stored bcrypt hash."""
    try:
        return bcrypt.checkpw(password.encode('utf-8'), stored_hash.encode('utf-8'))
    except (ValueError, TypeError):
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
    """Check if login attempts are rate-limited. Returns True if blocked."""
    now = time.time()
    with _login_lock:
        attempts = _login_attempts[username]
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
    conn = None
    try:
        conn = pymysql.connect(**MYSQL_CONFIG)
        yield conn
    except pymysql.Error as e:
        print(f"MySQL connection error: {e}")
        if conn:
            conn.rollback()
        raise
    finally:
        if conn:
            conn.close()


def init_auth_db():
    """Initialize the authentication database tables."""
    try:
        with get_db() as conn:
            cursor = conn.cursor()
            
            # Users table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    username VARCHAR(255) UNIQUE NOT NULL,
                    password_hash VARCHAR(64) NOT NULL,
                    password_salt VARCHAR(32) NOT NULL,
                    display_name VARCHAR(255) NOT NULL,
                    email VARCHAR(255),
                    created_at BIGINT NOT NULL,
                    updated_at BIGINT NOT NULL,
                    INDEX idx_username (username)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
            """)
            
            # Sessions table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS sessions (
                    token VARCHAR(64) PRIMARY KEY,
                    user_id INT NOT NULL,
                    created_at BIGINT NOT NULL,
                    expires_at BIGINT NOT NULL,
                    user_agent TEXT,
                    ip_address VARCHAR(45),
                    INDEX idx_user_id (user_id),
                    INDEX idx_expires_at (expires_at),
                    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
            """)
            
            # User chat threads table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS user_chat_threads (
                    id VARCHAR(255) PRIMARY KEY,
                    user_id INT NOT NULL,
                    title VARCHAR(500) NOT NULL,
                    messages LONGTEXT NOT NULL DEFAULT '[]',
                    created_at BIGINT NOT NULL,
                    updated_at BIGINT NOT NULL,
                    INDEX idx_user_id (user_id),
                    INDEX idx_updated_at (updated_at),
                    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
            """)
            
            conn.commit()
            print(f"MySQL auth database initialized at {MYSQL_CONFIG['host']}/{MYSQL_CONFIG['database']}")
    except Exception as e:
        print(f"Error initializing auth database: {e}")
        raise


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
                VALUES (%s, %s, %s, %s, %s, %s, %s)
            """, (username, password_hash, salt, display_name, email, now, now))
            conn.commit()
            
            user_id = cursor.lastrowid
            return User(id=user_id, username=username, display_name=display_name, created_at=now)
        except pymysql.IntegrityError:
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
            FROM users WHERE username = %s
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

        # Fallback: check legacy SHA-256 hash and migrate to bcrypt
        legacy_hash = _hash_password_legacy(password, salt)
        if legacy_hash == stored_hash:
            new_hash = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
            cursor.execute("UPDATE users SET password_hash = %s WHERE id = %s", (new_hash, row['id']))
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
            VALUES (%s, %s, %s, %s, %s, %s)
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
            WHERE s.token = %s AND s.expires_at > %s
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
        cursor.execute("DELETE FROM sessions WHERE token = %s", (token,))
        conn.commit()
        return cursor.rowcount > 0


def cleanup_expired_sessions():
    """Remove expired sessions from the database."""
    now = int(time.time() * 1000)
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM sessions WHERE expires_at < %s", (now,))
        conn.commit()
        return cursor.rowcount


# Chat history functions

def save_user_threads(user_id: int, threads: List[Dict[str, Any]]) -> bool:
    """Save all chat threads for a user (full sync)."""
    now = int(time.time() * 1000)
    
    with get_db() as conn:
        cursor = conn.cursor()
        
        # Get existing thread IDs
        cursor.execute("SELECT id FROM user_chat_threads WHERE user_id = %s", (user_id,))
        existing_ids = {row['id'] for row in cursor.fetchall()}
        
        incoming_ids = {t['id'] for t in threads}
        
        # Delete threads that no longer exist
        to_delete = existing_ids - incoming_ids
        if to_delete:
            for tid in to_delete:
                cursor.execute(
                    "DELETE FROM user_chat_threads WHERE id = %s AND user_id = %s",
                    (tid, user_id)
                )
        
        # Upsert threads
        for thread in threads:
            messages_json = json.dumps(thread.get('messages', []))
            
            # Check if thread exists
            cursor.execute("SELECT id FROM user_chat_threads WHERE id = %s", (thread['id'],))
            exists = cursor.fetchone()
            
            if exists:
                cursor.execute("""
                    UPDATE user_chat_threads 
                    SET title = %s, messages = %s, updated_at = %s
                    WHERE id = %s
                """, (
                    thread.get('title', 'Untitled'),
                    messages_json,
                    thread.get('updatedAt', now),
                    thread['id']
                ))
            else:
                cursor.execute("""
                    INSERT INTO user_chat_threads (id, user_id, title, messages, created_at, updated_at)
                    VALUES (%s, %s, %s, %s, %s, %s)
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
            WHERE user_id = %s
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
            FROM users WHERE id = %s
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
            UPDATE users SET display_name = %s, updated_at = %s
            WHERE id = %s
        """, (display_name, now, user_id))
        conn.commit()
        return cursor.rowcount > 0


# Lazy initialization — call explicitly at app startup, not on import
_db_initialized = False

def ensure_db_initialized():
    """Initialize MySQL auth DB if not already done."""
    global _db_initialized
    if not _db_initialized:
        try:
            init_auth_db()
            _db_initialized = True
        except Exception as e:
            print(f"Warning: Could not initialize MySQL auth database: {e}")

