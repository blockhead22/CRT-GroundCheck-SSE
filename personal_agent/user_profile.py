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

# Conditional import for LLM extraction (optional feature)
try:
    from .llm_extractor import LLMFactExtractor, LLMConfig, create_regex_fallback
    from .fact_tuples import FactAction
    HAS_LLM_SUPPORT = True
except ImportError as e:
    HAS_LLM_SUPPORT = False
    LLMFactExtractor = None
    LLMConfig = None
    FactAction = None
    create_regex_fallback = None

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


# Slots that should only have ONE value at a time (replace on conflict)
SINGLE_VALUE_SLOTS = {
    'name',           # User has one name
    'assistant_name', # Assistant has one name
    'location',       # User lives in one place at a time
    'favorite_color', # One favorite color
    'email',          # One primary email
    'phone',          # One primary phone
    'age',            # One age
    'birthday',       # One birthday
}

# Slots that can have MULTIPLE values (accumulate, but detect contradictions)
MULTI_VALUE_SLOTS = {
    'employer',       # User might have multiple jobs
    'occupation',     # Multiple roles
    'title',          # Multiple titles
    'skill',          # Multiple skills
    'language',       # Multiple programming languages
    'school',         # Multiple schools attended
}


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
    
    def __init__(self, db_path: str = "personal_agent/crt_user_profile.db", use_llm_extraction: bool = True):
        self.db_path = db_path
        self.use_llm_extraction = use_llm_extraction and HAS_LLM_SUPPORT
        logger.debug(f"GlobalUserProfile init: db_path={self.db_path}, use_llm={self.use_llm_extraction}")
        
        # Initialize LLM extractor with regex fallback
        self.llm_extractor = None
        if self.use_llm_extraction:
            try:
                self.llm_extractor = LLMFactExtractor(config=LLMConfig(model="gpt-4o-mini"))
                self.llm_extractor.set_fallback_extractor(create_regex_fallback())
                logger.info("LLM-based fact extraction enabled")
            except Exception as e:
                logger.warning(f"LLM extraction unavailable: {e}. Falling back to regex-only.")
        elif use_llm_extraction and not HAS_LLM_SUPPORT:
            logger.info("LLM extraction requested but dependencies not available. Using regex-only.")
        
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
        
        # Multi-value table: allows multiple values per slot with rich context
        # - Multiple favorite colors: "blue" AND "green"
        # - Multiple pets: "healthy dog" AND "sick cat"
        # - Multiple jobs: "Google full-time" AND "consulting part-time"
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
                evidence_span TEXT,
                action TEXT DEFAULT 'add',
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
    
    def update_from_text(self, text: str, thread_id: str = "default") -> Dict[str, Any]:
        """
        Extract facts from user text and update profile using LLM or regex extraction.
        
        NEW BEHAVIOR (LLM-based):
        - Uses LLM to extract open-world facts with context
        - Supports multiple values for ANY slot (e.g., multiple favorite colors, multiple pets)
        - Captures rich context: "sick dog" vs "healthy dog", "part-time job" vs "full-time job"
        - Handles contradictions: "used to work at X" (deprecate) vs "now work at Y" (add)
        - Falls back to regex patterns when LLM unavailable
        
        Examples LLM can handle that regex cannot:
        - "I have two pets: a healthy dog and a really sick cat" → 2 pet facts with health context
        - "My favorite colors are blue and green" → 2 favorite_color facts
        - "I work full-time at Google and part-time as a consultant" → 2 employer facts with employment type
        - "I used to love woodworking but now I prefer pottery" → deprecate woodworking, add pottery
        
        Filters out temporal/temporary statements:
        - "I'm working on homework tonight" (temporary activity)
        - "I'm currently reviewing code" (temporary state)
        
        Returns:
            Dictionary with:
            - 'updated': {slot: value} for facts that were updated/added
            - 'replaced': {slot: {'old': old_value, 'new': new_value}} for contradictions
        """
        logger.debug(f"GlobalUserProfile.update_from_text called: text='{text[:50]}'")
        
        # Guard rail: Skip temporal/temporary statements
        if self.is_temporal_statement(text):
            logger.debug(f"Skipping temporal statement: {text[:50]}")
            return {'updated': {}, 'replaced': {}}
        
        # Try LLM extraction first, fall back to regex
        if self.llm_extractor:
            return self._update_from_llm_tuples(text, thread_id)
        else:
            return self._update_from_regex_facts(text, thread_id)
    
    def _update_from_llm_tuples(self, text: str, thread_id: str) -> Dict[str, Any]:
        """
        Update profile using LLM-extracted fact tuples.
        
        Supports:
        - Multiple values per attribute (multiple pets, colors, jobs)
        - Rich context ("sick dog", "part-time job at Google")
        - Explicit actions: add, update, deprecate, deny
        - Confidence scores from LLM
        """
        try:
            tuples = self.llm_extractor.extract_tuples(text)
            logger.info(f"[LLM_PROFILE_UPDATE] Extracted {len(tuples)} tuples from '{text[:60]}'")
        except Exception as e:
            logger.warning(f"LLM extraction failed: {e}. Falling back to regex.")
            return self._update_from_regex_facts(text, thread_id)
        
        if not tuples:
            logger.info("[LLM_PROFILE_UPDATE] No facts extracted")
            return {'updated': {}, 'replaced': {}}
        
        updated = {}
        replaced = {}
        deprecated = {}
        conn = self._get_connection()
        cursor = conn.cursor()
        
        for tuple_obj in tuples:
            slot = tuple_obj.attribute
            value = tuple_obj.value
            normalized = value.lower().strip()
            action = tuple_obj.action
            evidence = tuple_obj.evidence_span or text[:100]
            confidence = tuple_obj.confidence
            
            logger.info(f"[LLM_PROFILE_UPDATE] Processing: {slot}={value} (action={action.value}, conf={confidence:.2f})")
            
            # Check for existing fact with same normalized value
            cursor.execute("""
                SELECT id, value, active FROM user_profile_multi 
                WHERE slot = ? AND normalized = ?
            """, (slot, normalized))
            exact_match = cursor.fetchone()
            
            if exact_match:
                match_id, match_value, is_active = exact_match
                
                if action == FactAction.DEPRECATE or action == FactAction.DENY:
                    # Mark as inactive
                    cursor.execute("""
                        UPDATE user_profile_multi 
                        SET active = 0, timestamp = ?, action = ?
                        WHERE id = ?
                    """, (time.time(), action.value, match_id))
                    deprecated[slot] = value
                    logger.info(f"[LLM_PROFILE_UPDATE] Deprecated: {slot} = {value}")
                    continue
                    
                elif is_active:
                    # Update timestamp and evidence
                    cursor.execute("""
                        UPDATE user_profile_multi 
                        SET timestamp = ?, source_thread = ?, evidence_span = ?, confidence = ?
                        WHERE id = ?
                    """, (time.time(), thread_id, evidence, confidence, match_id))
                    logger.info(f"[LLM_PROFILE_UPDATE] Refreshed: {slot} = {value}")
                    continue
                else:
                    # Delete inactive duplicate before re-inserting
                    cursor.execute("DELETE FROM user_profile_multi WHERE id = ?", (match_id,))
                    logger.info(f"[LLM_PROFILE_UPDATE] Deleted inactive duplicate for re-insert: {slot} = {value}")
            
            # INSERT new fact
            try:
                cursor.execute("""
                    INSERT INTO user_profile_multi 
                    (slot, value, normalized, timestamp, source_thread, confidence, active, evidence_span, action)
                    VALUES (?, ?, ?, ?, ?, ?, 1, ?, ?)
                """, (slot, value, normalized, time.time(), thread_id, confidence, evidence, action.value))
                updated[slot] = value
                logger.info(f"[LLM_PROFILE_UPDATE] ✅ INSERTED: {slot} = {value}")
            except sqlite3.IntegrityError as e:
                logger.error(f"[LLM_PROFILE_UPDATE] ❌ IntegrityError: {slot} = {value}: {e}")
                continue
        
        conn.commit()
        logger.info(f"[LLM_PROFILE_UPDATE] Committed. Updated: {updated}, Deprecated: {deprecated}")
        conn.close()
        
        return {'updated': updated, 'replaced': replaced, 'deprecated': deprecated}
    
    def _update_from_regex_facts(self, text: str, thread_id: str) -> Dict[str, Any]:
        """
        Legacy regex-based fact extraction (fallback).
        
        Uses predefined patterns from fact_slots.py
        """
        facts = extract_fact_slots(text)
        logger.info(f"[REGEX_PROFILE_UPDATE] Extracted {len(facts)} facts from '{text[:60]}': {list(facts.keys())}")
        
        if not facts:
            logger.info("[REGEX_PROFILE_UPDATE] No facts extracted")
            return {'updated': {}, 'replaced': {}}
        
        updated = {}
        replaced = {}
        conn = self._get_connection()
        cursor = conn.cursor()
        
        for slot, fact in facts.items():
            logger.info(f"[REGEX_PROFILE_UPDATE] Processing slot='{slot}', value='{fact.value}'")
            new_norm = fact.normalized if hasattr(fact, 'normalized') else fact.value.lower()
            
            # Check if exact value exists
            cursor.execute("""
                SELECT id, value, active FROM user_profile_multi 
                WHERE slot = ? AND normalized = ?
            """, (slot, new_norm))
            exact_match = cursor.fetchone()
            
            if exact_match:
                match_id, match_value, is_active = exact_match
                if is_active:
                    # Update timestamp
                    cursor.execute("""
                        UPDATE user_profile_multi 
                        SET timestamp = ?, source_thread = ?
                        WHERE id = ?
                    """, (time.time(), thread_id, match_id))
                    logger.info(f"[REGEX_PROFILE_UPDATE] Updated timestamp: {slot} = {match_value}")
                    continue
                else:
                    # Delete inactive duplicate
                    cursor.execute("DELETE FROM user_profile_multi WHERE id = ?", (match_id,))
                    logger.info(f"[REGEX_PROFILE_UPDATE] Deleted inactive duplicate: {slot} = {match_value}")
            
            # For slots marked as SINGLE_VALUE, replace old values
            is_single_value = slot in SINGLE_VALUE_SLOTS
            if is_single_value:
                cursor.execute("""
                    SELECT id, value FROM user_profile_multi 
                    WHERE slot = ? AND active = 1
                """, (slot,))
                existing = cursor.fetchall()
                
                if existing:
                    for row in existing:
                        cursor.execute("""
                            UPDATE user_profile_multi 
                            SET active = 0, timestamp = ?
                            WHERE id = ?
                        """, (time.time(), row[0]))
                    replaced[slot] = {'old': existing[0][1], 'new': fact.value}
                    logger.info(f"[REGEX_PROFILE_UPDATE] Replaced: {slot} '{existing[0][1]}' -> '{fact.value}'")
            
            # INSERT new fact
            try:
                cursor.execute("""
                    INSERT INTO user_profile_multi 
                    (slot, value, normalized, timestamp, source_thread, confidence, active, evidence_span, action)
                    VALUES (?, ?, ?, ?, ?, ?, 1, ?, 'add')
                """, (slot, fact.value, new_norm, time.time(), thread_id, 0.9, text[:100]))
                updated[slot] = fact.value
                logger.info(f"[REGEX_PROFILE_UPDATE] ✅ INSERTED: {slot} = {fact.value}")
            except sqlite3.IntegrityError as e:
                logger.error(f"[REGEX_PROFILE_UPDATE] ❌ IntegrityError: {slot} = {fact.value}: {e}")
        
        conn.commit()
        logger.info(f"[REGEX_PROFILE_UPDATE] Committed. Updated: {updated}, Replaced: {replaced}")
        conn.close()
        
        return {'updated': updated, 'replaced': replaced}
    
    def is_temporal_statement(self, text: str) -> bool:
        """
        Detect temporal/temporary statements that shouldn't be stored as permanent facts.
        
        Public method to allow testing and external validation of temporal filtering.
        
        Examples of what this catches:
        - "I'm working on homework tonight"
        - "I'm currently reviewing code"
        - "I'm debugging the React component"
        - "I need to refactor the API layer"
        - "I'm studying for exams this week"
        - "I'm doing some freelance work today"
        
        Examples of what this allows:
        - "I work at Walmart" (permanent employer)
        - "I'm a freelance web developer" (occupation/identity)
        - "I graduated from MIT" (historical fact)
        - "I prefer TypeScript over JavaScript" (permanent preference)
        
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
        temporary_activities = [
            'working on', 'studying', 'reviewing', 'reading about',
            'learning about', 'practicing', 'preparing for',
            'doing some', 'helping with', 'finishing up',
            'debugging', 'refactoring', 'implementing', 'fixing',
            'trying to', 'planning to', 'need to', 'going to',
            'building', 'creating', 'developing', 'writing',
        ]
        
        has_temporary_activity = any(activity in text_lower for activity in temporary_activities)
        
        # Technical/code discussion indicators
        code_discussion_markers = [
            'function', 'class', 'component', 'api', 'endpoint',
            'bug', 'error', 'issue', 'pull request', 'commit',
            'repository', 'branch', 'merge', 'deploy',
            'test', 'lint', 'compile', 'build', 'returns',
            'undefined', 'null', 'throws', 'fails',
        ]
        
        # Check if this is a technical discussion (multiple code markers)
        code_marker_count = sum(1 for marker in code_discussion_markers if marker in text_lower)
        is_code_discussion = code_marker_count >= 2
        
        # Phrases that indicate implementation work (temporary)
        implementation_phrases = [
            'implementing', 'using graphql', 'using react', 'using typescript',
            'with graphql', 'with react', 'with typescript'
        ]
        has_implementation = any(phrase in text_lower for phrase in implementation_phrases)
        
        # If both temporal marker AND temporary activity, it's likely temporary
        if has_temporal and has_temporary_activity:
            return True
        
        # "working on" without "work at/for" is usually temporary
        if 'working on' in text_lower and not ('work at' in text_lower or 'work for' in text_lower):
            return True
        
        # Technical discussion with temporary activities is usually temporary
        if is_code_discussion and has_temporary_activity:
            return True
        
        # Pure technical description (no "I" statements) is usually discussion, not identity
        has_first_person = any(word in text_lower for word in [' i ', "i'm", "i am", "my ", "i've"])
        if is_code_discussion and not has_first_person:
            return True
        
        # Implementation work phrases are usually temporary
        if has_implementation and "i'm" in text_lower:
            return True
        
        # Questions about code/projects are usually temporary
        if any(q in text_lower for q in ['how do i', 'can you help', 'what should i']) and code_marker_count > 0:
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
    
    def consolidate_single_value_slots(self) -> Dict[str, Dict]:
        """
        Fix existing data: For single-value slots with multiple values,
        keep only the most recent one and mark others as inactive.
        
        Returns:
            Dictionary of {slot: {'kept': value, 'deactivated': [values]}} for slots that were consolidated
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        
        consolidated = {}
        
        for slot in SINGLE_VALUE_SLOTS:
            # Get all active values for this slot
            cursor.execute("""
                SELECT id, value FROM user_profile_multi 
                WHERE slot = ? AND active = 1
                ORDER BY timestamp DESC
            """, (slot,))
            rows = cursor.fetchall()
            
            if len(rows) > 1:
                # Keep the most recent, deactivate the rest
                kept_id, kept_value = rows[0]
                deactivated_values = []
                
                for row_id, value in rows[1:]:
                    cursor.execute("""
                        UPDATE user_profile_multi 
                        SET active = 0
                        WHERE id = ?
                    """, (row_id,))
                    deactivated_values.append(value)
                
                consolidated[slot] = {
                    'kept': kept_value,
                    'deactivated': deactivated_values
                }
                logger.info(f"[PROFILE_CONSOLIDATE] {slot}: kept '{kept_value}', deactivated {deactivated_values}")
        
        conn.commit()
        conn.close()
        
        return consolidated
    
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
