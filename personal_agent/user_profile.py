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
    
    def _init_db(self):
        """Initialize profile database."""
        logger.debug(f"GlobalUserProfile creating DB at: {self.db_path}")
        conn = sqlite3.connect(self.db_path)
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
        
        Returns:
            Dictionary of slot -> value for facts that were updated/added
        """
        logger.debug(f"GlobalUserProfile.update_from_text called: text='{text[:50]}'")
        facts = extract_fact_slots(text)
        logger.debug(f"Extracted {len(facts)} facts: {list(facts.keys())}")
        if not facts:
            return {}
        
        updated = {}
        conn = sqlite3.connect(self.db_path)
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
    
    def get_fact(self, slot: str) -> Optional[UserProfileFact]:
        """
        Get the most recent fact for a slot.
        
        Note: If there are multiple values for a slot (e.g., multiple employers),
        this returns only the most recent one. Use get_all_facts_for_slot() to get all.
        """
        conn = sqlite3.connect(self.db_path)
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
        conn = sqlite3.connect(self.db_path)
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
        conn = sqlite3.connect(self.db_path)
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
        conn = sqlite3.connect(self.db_path)
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
        conn = sqlite3.connect(self.db_path)
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
        conn = sqlite3.connect(self.db_path)
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
