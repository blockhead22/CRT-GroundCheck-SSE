"""
Global User Profile System - Cross-Thread Memory

Problem: Thread-specific databases isolate memories. When user starts a new chat,
their name, occupation, location, etc. are not available.

Solution: Global profile database that stores user identity facts separately from
thread-specific conversation memories.

Architecture:
- Thread DBs: Conversation-specific memories (still isolated)
- Profile DB: User identity facts (shared across all threads)
- Auto-sync: When user introduces themselves, store in both locations
"""

import sqlite3
import json
import time
import logging
from typing import Dict, Optional, Any, List
from pathlib import Path
from dataclasses import dataclass

from .fact_slots import extract_fact_slots, ExtractedFact

logger = logging.getLogger(__name__)


@dataclass
class UserProfileFact:
    """A single user profile fact (name, employer, location, etc.)"""
    slot: str  # e.g., "name", "employer", "location"
    value: str  # e.g., "Nick Block", "Microsoft", "Seattle"
    normalized: str  # Lowercase normalized version
    timestamp: float  # When last updated
    source_thread: str  # Which thread this came from
    confidence: float = 0.9  # How confident we are


class GlobalUserProfile:
    """
    Stores user identity facts globally across all threads.
    
    Facts stored:
    - name, employer, location, occupation, title
    - first_language, programming_years, team_size
    - masters_school, undergrad_school, graduation_year
    - siblings, languages_spoken
    
    NOT stored globally:
    - Conversation context
    - Thread-specific preferences
    - Temporal statements ("I'm working on X today")
    """
    
    def __init__(self, db_path: str = "personal_agent/crt_user_profile.db"):
        self.db_path = db_path
        logger.debug(f"GlobalUserProfile init: db_path={self.db_path}")
        self._init_db()
    
    def _get_connection(self, timeout: float = 30.0) -> sqlite3.Connection:
        """
        Create a properly configured SQLite connection with:
        - WAL mode for better concurrent access
        - Busy timeout to retry on lock conflicts
        """
        conn = sqlite3.connect(self.db_path, timeout=timeout)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
        conn.execute("PRAGMA busy_timeout=30000")  # 30 second busy timeout
        return conn
    
    def _init_db(self):
        """Initialize profile database."""
        logger.debug(f"GlobalUserProfile creating DB at: {self.db_path}")
        conn = self._get_connection()
        cursor = conn.cursor()
        
        # New multi-value table: allows multiple values per slot (e.g., multiple employers)
        # Uses composite key (slot, normalized) to prevent exact duplicates
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS user_profile_multi (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                slot TEXT NOT NULL,
                value TEXT NOT NULL,
                normalized TEXT NOT NULL,
                timestamp REAL NOT NULL,
                source_thread TEXT NOT NULL,
                confidence REAL DEFAULT 0.9,
                active INTEGER DEFAULT 1,
                UNIQUE(slot, normalized)
            )
        """)
        
        # Indexes for fast lookups
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_multi_slot 
            ON user_profile_multi(slot, active, timestamp DESC)
        """)
        
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_multi_timestamp 
            ON user_profile_multi(timestamp DESC)
        """)
        
        # Migrate old single-value table if it exists (one-time migration)
        # Check if migration has already been done by looking for a marker
        cursor.execute("""
            SELECT name FROM sqlite_master 
            WHERE type='table' AND name='user_profile'
        """)
        if cursor.fetchone():
            # Check if we already migrated (look for data in multi table)
            cursor.execute("SELECT COUNT(*) FROM user_profile_multi")
            already_migrated = cursor.fetchone()[0] > 0
            
            if not already_migrated:
                # Migrate existing data to multi table
                cursor.execute("""
                    INSERT OR IGNORE INTO user_profile_multi 
                    (slot, value, normalized, timestamp, source_thread, confidence)
                    SELECT slot, value, normalized, timestamp, source_thread, confidence
                    FROM user_profile
                """)
                logger.info(f"Migrated {cursor.rowcount} facts from old user_profile table")
        
        conn.commit()
        conn.close()
    
    def update_from_text(self, text: str, thread_id: str = "default") -> Dict[str, str]:
        """
        Extract facts from user text and update profile.
        
        Now supports multiple values per slot (e.g., multiple employers).
        Uses UNIQUE(slot, normalized) to prevent exact duplicates.
        
        Filters out temporal/temporary statements to avoid storing:
        - "I'm working on homework tonight" (temporary activity)
        - "I'm currently reviewing code" (temporary state)
        
        Only stores durable identity facts like:
        - "I work at Walmart" (permanent employer)
        - "I'm a freelance web developer" (occupation)
        
        Returns:
            Dictionary of slot -> value for facts that were updated/added
        """
        logger.debug(f"GlobalUserProfile.update_from_text called: text='{text[:50]}'")
        
        # Guard rail: Skip temporal/temporary statements
        if self.is_temporal_statement(text):
            logger.debug(f"Skipping temporal statement: {text[:50]}")
            return {}
        
        facts = extract_fact_slots(text)
        logger.debug(f"Extracted {len(facts)} facts: {list(facts.keys())}")
        if not facts:
            return {}
        
        updated = {}
        conn = self._get_connection()
        cursor = conn.cursor()
        
        for slot, fact in facts.items():
            new_norm = fact.normalized if hasattr(fact, 'normalized') else fact.value.lower()
            
            # Check if this exact value already exists (using normalized form)
            cursor.execute("""
                SELECT id, value FROM user_profile_multi 
                WHERE slot = ? AND normalized = ? AND active = 1
            """, (slot, new_norm))
            existing = cursor.fetchone()
            
            if existing:
                # Update timestamp to show this value was recently mentioned
                cursor.execute("""
                    UPDATE user_profile_multi 
                    SET timestamp = ?, source_thread = ?
                    WHERE id = ?
                """, (time.time(), thread_id, existing[0]))
                logger.debug(f"Updated existing fact: {slot} = {existing[1]}")
            else:
                # Insert new value (allows multiple values per slot)
                try:
                    cursor.execute("""
                        INSERT INTO user_profile_multi 
                        (slot, value, normalized, timestamp, source_thread, confidence)
                        VALUES (?, ?, ?, ?, ?, ?)
                    """, (
                        slot,
                        fact.value,
                        new_norm,
                        time.time(),
                        thread_id,
                        0.9
                    ))
                    updated[slot] = fact.value
                    logger.debug(f"Added new fact: {slot} = {fact.value}")
                except sqlite3.IntegrityError:
                    # Duplicate entry (shouldn't happen due to check above, but handle gracefully)
                    logger.debug(f"Duplicate fact skipped: {slot} = {fact.value}")
        
        conn.commit()
        conn.close()
        
        return updated
    
    def is_temporal_statement(self, text: str) -> bool:
        """
        Detect temporal/temporary statements that shouldn't be stored as permanent facts.
        
        Public method to allow testing and external validation of temporal filtering.
        
        Examples of what this catches:
        - "I'm working on homework tonight"
        - "I'm currently reviewing code"
        - "I'm studying for exams this week"
        - "I'm doing some freelance work today"
        - "I'm learning about Python recently"
        
        Examples of what this allows:
        - "I work at Walmart" (permanent employer)
        - "I'm a freelance web developer" (occupation/identity)
        - "I graduated from MIT" (historical fact)
        
        Returns:
            True if the statement appears temporal/temporary, False otherwise
        """
        text_lower = text.lower()
        
        # Temporal markers indicating temporary activity
        temporal_markers = [
            'tonight', 'today', 'this week', 'this month', 'this year',
            'right now', 'at the moment', 'currently',
            'this morning', 'this afternoon', 'this evening',
            'these days', 'lately', 'recently',
        ]
        
        # Check for temporal markers
        has_temporal = any(marker in text_lower for marker in temporal_markers)
        
        # Activity verbs that indicate temporary actions (not identity)
        # when combined with temporal markers
        temporary_activities = [
            'working on', 'studying', 'reviewing', 'reading about',
            'learning about', 'practicing', 'preparing for',
            'doing some', 'helping with', 'finishing up',
        ]
        
        has_temporary_activity = any(activity in text_lower for activity in temporary_activities)
        
        # If both temporal marker AND temporary activity, it's likely temporary
        if has_temporal and has_temporary_activity:
            return True
        
        # "working on" without "work at/for" is usually temporary
        if 'working on' in text_lower and not ('work at' in text_lower or 'work for' in text_lower):
            return True
        
        return False
    
    def get_fact(self, slot: str) -> Optional[UserProfileFact]:
        """
        Get the most recent fact for a slot.
        
        Note: If there are multiple values for a slot (e.g., multiple employers),
        this returns only the most recent one. Use get_all_facts_for_slot() to get all.
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT slot, value, normalized, timestamp, source_thread, confidence
            FROM user_profile_multi
            WHERE slot = ? AND active = 1
            ORDER BY timestamp DESC
            LIMIT 1
        """, (slot,))
        
        row = cursor.fetchone()
        conn.close()
        
        if not row:
            return None
        
        return UserProfileFact(
            slot=row[0],
            value=row[1],
            normalized=row[2],
            timestamp=row[3],
            source_thread=row[4],
            confidence=row[5]
        )
    
    def get_all_facts_for_slot(self, slot: str) -> List[UserProfileFact]:
        """
        Get ALL facts for a specific slot (e.g., all employers).
        
        Returns list sorted by timestamp (most recent first).
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT slot, value, normalized, timestamp, source_thread, confidence
            FROM user_profile_multi
            WHERE slot = ? AND active = 1
            ORDER BY timestamp DESC
        """, (slot,))
        
        facts = []
        for row in cursor.fetchall():
            facts.append(UserProfileFact(
                slot=row[0],
                value=row[1],
                normalized=row[2],
                timestamp=row[3],
                source_thread=row[4],
                confidence=row[5]
            ))
        
        conn.close()
        return facts
    
    def get_all_facts(self) -> Dict[str, UserProfileFact]:
        """
        Get all stored user profile facts.
        
        Note: If a slot has multiple values (e.g., multiple employers), 
        this returns only the most recent one per slot.
        For all values, iterate through slots and call get_all_facts_for_slot().
        
        Returns dict of slot -> most recent fact
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        
        # Get most recent fact per slot using subquery
        cursor.execute("""
            SELECT upf.slot, upf.value, upf.normalized, upf.timestamp, upf.source_thread, upf.confidence
            FROM user_profile_multi upf
            INNER JOIN (
                SELECT slot, MAX(timestamp) as max_ts
                FROM user_profile_multi
                WHERE active = 1
                GROUP BY slot
            ) latest ON upf.slot = latest.slot AND upf.timestamp = latest.max_ts
            WHERE upf.active = 1
            ORDER BY upf.timestamp DESC
        """)
        
        facts = {}
        for row in cursor.fetchall():
            # Only keep first (most recent) entry per slot
            if row[0] not in facts:
                facts[row[0]] = UserProfileFact(
                    slot=row[0],
                    value=row[1],
                    normalized=row[2],
                    timestamp=row[3],
                    source_thread=row[4],
                    confidence=row[5]
                )
        
        conn.close()
        return facts
    
    def get_all_facts_expanded(self) -> Dict[str, List[UserProfileFact]]:
        """
        Get ALL stored facts including multiple values per slot.
        
        Returns dict of slot -> list of facts (newest first)
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT slot, value, normalized, timestamp, source_thread, confidence
            FROM user_profile_multi
            WHERE active = 1
            ORDER BY slot, timestamp DESC
        """)
        
        facts: Dict[str, List[UserProfileFact]] = {}
        for row in cursor.fetchall():
            fact = UserProfileFact(
                slot=row[0],
                value=row[1],
                normalized=row[2],
                timestamp=row[3],
                source_thread=row[4],
                confidence=row[5]
            )
            facts.setdefault(row[0], []).append(fact)
        
        conn.close()
        return facts
    
    def get_facts_for_slots(self, slots: List[str]) -> Dict[str, UserProfileFact]:
        """
        Get facts for specific slots (most recent value per slot).
        
        For slots with multiple values, use get_all_facts_for_slot() instead.
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        
        placeholders = ','.join('?' * len(slots))
        cursor.execute(f"""
            SELECT upf.slot, upf.value, upf.normalized, upf.timestamp, upf.source_thread, upf.confidence
            FROM user_profile_multi upf
            INNER JOIN (
                SELECT slot, MAX(timestamp) as max_ts
                FROM user_profile_multi
                WHERE slot IN ({placeholders}) AND active = 1
                GROUP BY slot
            ) latest ON upf.slot = latest.slot AND upf.timestamp = latest.max_ts
            WHERE upf.active = 1
        """, slots)
        
        facts = {}
        for row in cursor.fetchall():
            facts[row[0]] = UserProfileFact(
                slot=row[0],
                value=row[1],
                normalized=row[2],
                timestamp=row[3],
                source_thread=row[4],
                confidence=row[5]
            )
        
        conn.close()
        return facts
    
    def clear(self):
        """Clear all profile data (for testing)."""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM user_profile_multi")
        conn.commit()
        conn.close()
    
    def to_memory_texts(self) -> List[str]:
        """
        Convert profile facts to memory-like text format.
        
        Includes ALL values for multi-value slots (e.g., all employers).
        
        Returns:
            List of "FACT: slot = value" strings suitable for memory retrieval
        """
        all_facts = self.get_all_facts_expanded()
        texts = []
        
        for slot, fact_list in all_facts.items():
            slot_label = slot.replace('_', ' ')
            for fact in fact_list:
                texts.append(f"FACT: {slot_label} = {fact.value}")
        
        return texts


# =============================================================================
# User Transparency Preferences
# =============================================================================

class TransparencyLevel:
    """User preference for transparency/disclosure level."""
    MINIMAL = "minimal"      # Only disclose critical contradictions
    BALANCED = "balanced"    # Default: reasonable disclosure
    AUDIT_HEAVY = "audit_heavy"  # Disclose everything


class MemoryStyle:
    """User preference for how memories are handled."""
    STICKY = "sticky"        # Memories persist longer, harder to override
    NORMAL = "normal"        # Default behavior
    FORGETFUL = "forgetful"  # Memories fade faster, easier to override


@dataclass
class UserTransparencyPrefs:
    """
    User preferences for transparency and disclosure.
    
    These preferences control how aggressively contradictions are
    disclosed and how memories are managed.
    
    Attributes:
        transparency_level: How much detail to disclose about contradictions
        memory_style: How sticky memories should be
        always_disclose_domains: Domains that always get full disclosure
        never_nag_domains: Domains where we don't repeat disclosures
        max_disclosures_per_session: Limit nagging per conversation
    """
    transparency_level: str = TransparencyLevel.BALANCED
    memory_style: str = MemoryStyle.NORMAL
    always_disclose_domains: List[str] = None
    never_nag_domains: List[str] = None
    max_disclosures_per_session: int = 3
    
    def __post_init__(self):
        """Set default values for mutable fields."""
        if self.always_disclose_domains is None:
            self.always_disclose_domains = ["medical", "financial", "legal"]
        if self.never_nag_domains is None:
            self.never_nag_domains = []
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for storage."""
        return {
            "transparency_level": self.transparency_level,
            "memory_style": self.memory_style,
            "always_disclose_domains": self.always_disclose_domains,
            "never_nag_domains": self.never_nag_domains,
            "max_disclosures_per_session": self.max_disclosures_per_session,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'UserTransparencyPrefs':
        """Create from dictionary."""
        return cls(
            transparency_level=data.get("transparency_level", TransparencyLevel.BALANCED),
            memory_style=data.get("memory_style", MemoryStyle.NORMAL),
            always_disclose_domains=data.get("always_disclose_domains", ["medical", "financial", "legal"]),
            never_nag_domains=data.get("never_nag_domains", []),
            max_disclosures_per_session=data.get("max_disclosures_per_session", 3),
        )
