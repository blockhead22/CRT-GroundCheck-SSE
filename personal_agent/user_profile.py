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
from typing import Dict, Optional, Any, List
from pathlib import Path
from dataclasses import dataclass

from .fact_slots import extract_fact_slots, ExtractedFact


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
        print(f"[DEBUG] GlobalUserProfile init: db_path={self.db_path}")
        self._init_db()
    
    def _init_db(self):
        """Initialize profile database."""
        print(f"[DEBUG] GlobalUserProfile creating DB at: {self.db_path}")
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS user_profile (
                slot TEXT PRIMARY KEY,
                value TEXT NOT NULL,
                normalized TEXT NOT NULL,
                timestamp REAL NOT NULL,
                source_thread TEXT NOT NULL,
                confidence REAL DEFAULT 0.9,
                updated_count INTEGER DEFAULT 1
            )
        """)
        
        # Index for fast lookups
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_timestamp 
            ON user_profile(timestamp DESC)
        """)
        
        conn.commit()
        conn.close()
    
    def update_from_text(self, text: str, thread_id: str = "default") -> Dict[str, str]:
        """
        Extract facts from user text and update profile.
        
        Returns:
            Dictionary of slot -> value for facts that were updated
        """
        print(f"[DEBUG] GlobalUserProfile.update_from_text called: text='{text[:50]}'")
        facts = extract_fact_slots(text)
        print(f"[DEBUG] Extracted {len(facts)} facts: {list(facts.keys())}")
        if not facts:
            return {}
        
        updated = {}
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        for slot, fact in facts.items():
            # Check if slot already exists
            cursor.execute("SELECT value, normalized FROM user_profile WHERE slot = ?", (slot,))
            existing = cursor.fetchone()
            
            if existing:
                old_value, old_norm = existing
                new_norm = fact.normalized if hasattr(fact, 'normalized') else fact.value.lower()
                
                # Only update if value actually changed
                if old_norm != new_norm:
                    cursor.execute("""
                        UPDATE user_profile 
                        SET value = ?, normalized = ?, timestamp = ?, 
                            source_thread = ?, updated_count = updated_count + 1
                        WHERE slot = ?
                    """, (fact.value, new_norm, time.time(), thread_id, slot))
                    updated[slot] = fact.value
            else:
                # Insert new fact
                cursor.execute("""
                    INSERT INTO user_profile 
                    (slot, value, normalized, timestamp, source_thread, confidence)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (
                    slot,
                    fact.value,
                    fact.normalized if hasattr(fact, 'normalized') else fact.value.lower(),
                    time.time(),
                    thread_id,
                    0.9
                ))
                updated[slot] = fact.value
        
        conn.commit()
        conn.close()
        
        return updated
    
    def get_fact(self, slot: str) -> Optional[UserProfileFact]:
        """Get a single fact by slot name."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT slot, value, normalized, timestamp, source_thread, confidence
            FROM user_profile
            WHERE slot = ?
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
    
    def get_all_facts(self) -> Dict[str, UserProfileFact]:
        """Get all stored user profile facts."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT slot, value, normalized, timestamp, source_thread, confidence
            FROM user_profile
            ORDER BY timestamp DESC
        """)
        
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
    
    def get_facts_for_slots(self, slots: List[str]) -> Dict[str, UserProfileFact]:
        """Get facts for specific slots."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        placeholders = ','.join('?' * len(slots))
        cursor.execute(f"""
            SELECT slot, value, normalized, timestamp, source_thread, confidence
            FROM user_profile
            WHERE slot IN ({placeholders})
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
        cursor.execute("DELETE FROM user_profile")
        conn.commit()
        conn.close()
    
    def to_memory_texts(self) -> List[str]:
        """
        Convert profile facts to memory-like text format.
        
        Returns:
            List of "FACT: slot = value" strings suitable for memory retrieval
        """
        facts = self.get_all_facts()
        texts = []
        
        for slot, fact in facts.items():
            # Format as memory text
            slot_label = slot.replace('_', ' ')
            texts.append(f"FACT: {slot_label} = {fact.value}")
        
        return texts
