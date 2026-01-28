"""
Episodic Memory System - Conversation Summaries, Patterns, and Concept Linking

This module provides higher-order memory capabilities beyond discrete facts:

1. **Session Summaries**: End-of-session narrative summaries
2. **Preference Learning**: Explicit + inferred user preferences  
3. **Pattern Detection**: Behavioral patterns from interaction history
4. **Concept Linking**: Entity resolution and knowledge graph building

Design Principles:
- Lightweight: Consumer hardware friendly
- Async-capable: Heavy processing in background
- Incremental: No full re-indexing required
- Storage-first: Save everything, process lazily

SSE Modes Used:
- P (Preference): User preferences (explicit and inferred)
- B (Belief): Internal observations, patterns, reasoning traces
- C (Compressed): Session summaries
"""

import sqlite3
import json
import time
import logging
import hashlib
from typing import Dict, Optional, Any, List, Tuple, Set
from dataclasses import dataclass, asdict, field
from pathlib import Path
from collections import Counter, defaultdict

logger = logging.getLogger(__name__)


# ============================================================================
# Data Classes
# ============================================================================

@dataclass
class SessionSummary:
    """A narrative summary of a conversation session."""
    summary_id: str
    thread_id: str
    session_start: float
    session_end: float
    message_count: int
    summary_text: str  # Natural language summary
    topics: List[str]  # Key topics discussed
    entities_mentioned: List[str]  # Names, projects, etc.
    facts_learned: List[str]  # New facts extracted this session
    unresolved_items: List[str]  # Questions/tasks left open
    timestamp: float = field(default_factory=time.time)
    
    def to_dict(self) -> Dict:
        return asdict(self)
    
    @staticmethod
    def from_dict(d: Dict) -> 'SessionSummary':
        return SessionSummary(**d)


@dataclass 
class UserPreference:
    """A learned or stated user preference."""
    pref_id: str
    category: str  # response_style, verbosity, format, behavior, topic
    key: str       # e.g., "emoji_usage", "response_length", "code_style"
    value: str     # e.g., "minimal", "verbose", "python"
    confidence: float  # 0-1, how sure we are
    source: str    # "explicit" (user stated) or "inferred" (observed pattern)
    evidence: List[str]  # Supporting observations
    timestamp: float = field(default_factory=time.time)
    active: bool = True
    
    def to_dict(self) -> Dict:
        return asdict(self)
    
    @staticmethod
    def from_dict(d: Dict) -> 'UserPreference':
        return UserPreference(**d)


@dataclass
class InteractionPattern:
    """A detected behavioral pattern."""
    pattern_id: str
    pattern_type: str  # topic_frequency, question_style, session_timing, feedback_signal
    description: str   # Natural language description
    evidence_count: int  # How many times observed
    confidence: float
    first_seen: float
    last_seen: float
    metadata: Dict = field(default_factory=dict)
    
    def to_dict(self) -> Dict:
        return asdict(self)
    
    @staticmethod
    def from_dict(d: Dict) -> 'InteractionPattern':
        return InteractionPattern(**d)


@dataclass
class ConceptNode:
    """A linked concept/entity in the knowledge graph."""
    concept_id: str
    canonical_name: str  # Primary name
    aliases: List[str]   # Alternative names/references
    concept_type: str    # person, project, topic, organization, location
    related_memory_ids: List[str]  # Links to memories mentioning this
    attributes: Dict[str, str]  # Known attributes
    first_mentioned: float
    last_mentioned: float
    mention_count: int = 1
    
    def to_dict(self) -> Dict:
        return asdict(self)
    
    @staticmethod
    def from_dict(d: Dict) -> 'ConceptNode':
        return ConceptNode(**d)


# ============================================================================
# Episodic Memory Database
# ============================================================================

class EpisodicMemoryDB:
    """
    SQLite-backed storage for episodic memories, preferences, patterns, and concepts.
    
    Designed for:
    - Fast writes (store everything immediately)
    - Lazy reads (query only when needed)
    - Incremental updates (no full re-indexing)
    - Consumer hardware (minimal memory footprint)
    """
    
    DEFAULT_PATH = "personal_agent/crt_episodic.db"
    
    def __init__(self, db_path: Optional[str] = None):
        self.db_path = db_path or self.DEFAULT_PATH
        self._init_db()
    
    def _get_conn(self) -> sqlite3.Connection:
        """Create optimized SQLite connection."""
        conn = sqlite3.connect(self.db_path, timeout=30.0)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
        conn.execute("PRAGMA busy_timeout=30000")
        conn.execute("PRAGMA cache_size=-8000")  # 8MB cache
        conn.row_factory = sqlite3.Row
        return conn
    
    def _init_db(self):
        """Initialize all episodic memory tables."""
        conn = self._get_conn()
        c = conn.cursor()
        
        # ========== Session Summaries ==========
        c.execute("""
            CREATE TABLE IF NOT EXISTS session_summaries (
                summary_id TEXT PRIMARY KEY,
                thread_id TEXT NOT NULL,
                session_start REAL NOT NULL,
                session_end REAL NOT NULL,
                message_count INTEGER,
                summary_text TEXT NOT NULL,
                topics TEXT,  -- JSON array
                entities_mentioned TEXT,  -- JSON array
                facts_learned TEXT,  -- JSON array
                unresolved_items TEXT,  -- JSON array
                timestamp REAL NOT NULL
            )
        """)
        c.execute("CREATE INDEX IF NOT EXISTS idx_summaries_thread ON session_summaries(thread_id, timestamp DESC)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_summaries_time ON session_summaries(session_end DESC)")
        
        # ========== User Preferences ==========
        c.execute("""
            CREATE TABLE IF NOT EXISTS user_preferences (
                pref_id TEXT PRIMARY KEY,
                category TEXT NOT NULL,
                key TEXT NOT NULL,
                value TEXT NOT NULL,
                confidence REAL DEFAULT 0.5,
                source TEXT DEFAULT 'inferred',
                evidence TEXT,  -- JSON array
                timestamp REAL NOT NULL,
                active INTEGER DEFAULT 1,
                UNIQUE(category, key, value)
            )
        """)
        c.execute("CREATE INDEX IF NOT EXISTS idx_prefs_category ON user_preferences(category, active)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_prefs_key ON user_preferences(key, active)")
        
        # ========== Interaction Patterns ==========
        c.execute("""
            CREATE TABLE IF NOT EXISTS interaction_patterns (
                pattern_id TEXT PRIMARY KEY,
                pattern_type TEXT NOT NULL,
                description TEXT NOT NULL,
                evidence_count INTEGER DEFAULT 1,
                confidence REAL DEFAULT 0.3,
                first_seen REAL NOT NULL,
                last_seen REAL NOT NULL,
                metadata TEXT  -- JSON object
            )
        """)
        c.execute("CREATE INDEX IF NOT EXISTS idx_patterns_type ON interaction_patterns(pattern_type, confidence DESC)")
        
        # ========== Concept Nodes (Knowledge Graph) ==========
        c.execute("""
            CREATE TABLE IF NOT EXISTS concept_nodes (
                concept_id TEXT PRIMARY KEY,
                canonical_name TEXT NOT NULL,
                aliases TEXT,  -- JSON array
                concept_type TEXT NOT NULL,
                related_memory_ids TEXT,  -- JSON array
                attributes TEXT,  -- JSON object
                first_mentioned REAL NOT NULL,
                last_mentioned REAL NOT NULL,
                mention_count INTEGER DEFAULT 1
            )
        """)
        c.execute("CREATE INDEX IF NOT EXISTS idx_concepts_name ON concept_nodes(canonical_name)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_concepts_type ON concept_nodes(concept_type)")
        
        # ========== Concept Aliases (for fast lookup) ==========
        c.execute("""
            CREATE TABLE IF NOT EXISTS concept_aliases (
                alias TEXT PRIMARY KEY,
                concept_id TEXT NOT NULL,
                FOREIGN KEY (concept_id) REFERENCES concept_nodes(concept_id)
            )
        """)
        
        # ========== Interaction Log (lightweight) ==========
        # Stores minimal data for pattern detection
        c.execute("""
            CREATE TABLE IF NOT EXISTS interaction_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                thread_id TEXT NOT NULL,
                timestamp REAL NOT NULL,
                query_length INTEGER,
                response_length INTEGER,
                query_type TEXT,  -- question, statement, command, etc.
                topic_keywords TEXT,  -- JSON array of extracted keywords
                sentiment TEXT,  -- positive, negative, neutral
                has_code INTEGER DEFAULT 0,
                has_emoji INTEGER DEFAULT 0,
                response_time_ms INTEGER
            )
        """)
        c.execute("CREATE INDEX IF NOT EXISTS idx_interactions_thread ON interaction_log(thread_id, timestamp DESC)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_interactions_time ON interaction_log(timestamp DESC)")
        
        # Keep only recent interactions (auto-cleanup trigger)
        c.execute("""
            CREATE TRIGGER IF NOT EXISTS cleanup_old_interactions
            AFTER INSERT ON interaction_log
            BEGIN
                DELETE FROM interaction_log 
                WHERE id NOT IN (
                    SELECT id FROM interaction_log ORDER BY timestamp DESC LIMIT 1000
                );
            END
        """)
        
        conn.commit()
        conn.close()
        logger.debug(f"EpisodicMemoryDB initialized at {self.db_path}")
    
    # ========== Session Summaries ==========
    
    def save_session_summary(self, summary: SessionSummary):
        """Save a session summary."""
        conn = self._get_conn()
        c = conn.cursor()
        
        c.execute("""
            INSERT OR REPLACE INTO session_summaries
            (summary_id, thread_id, session_start, session_end, message_count,
             summary_text, topics, entities_mentioned, facts_learned, 
             unresolved_items, timestamp)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            summary.summary_id,
            summary.thread_id,
            summary.session_start,
            summary.session_end,
            summary.message_count,
            summary.summary_text,
            json.dumps(summary.topics),
            json.dumps(summary.entities_mentioned),
            json.dumps(summary.facts_learned),
            json.dumps(summary.unresolved_items),
            summary.timestamp
        ))
        
        conn.commit()
        conn.close()
    
    def get_recent_summaries(self, thread_id: Optional[str] = None, limit: int = 5) -> List[SessionSummary]:
        """Get recent session summaries, optionally filtered by thread."""
        conn = self._get_conn()
        c = conn.cursor()
        
        if thread_id:
            c.execute("""
                SELECT * FROM session_summaries 
                WHERE thread_id = ? 
                ORDER BY session_end DESC LIMIT ?
            """, (thread_id, limit))
        else:
            c.execute("""
                SELECT * FROM session_summaries 
                ORDER BY session_end DESC LIMIT ?
            """, (limit,))
        
        summaries = []
        for row in c.fetchall():
            summaries.append(SessionSummary(
                summary_id=row['summary_id'],
                thread_id=row['thread_id'],
                session_start=row['session_start'],
                session_end=row['session_end'],
                message_count=row['message_count'],
                summary_text=row['summary_text'],
                topics=json.loads(row['topics'] or '[]'),
                entities_mentioned=json.loads(row['entities_mentioned'] or '[]'),
                facts_learned=json.loads(row['facts_learned'] or '[]'),
                unresolved_items=json.loads(row['unresolved_items'] or '[]'),
                timestamp=row['timestamp']
            ))
        
        conn.close()
        return summaries
    
    def search_summaries_by_topic(self, topic: str, limit: int = 10) -> List[SessionSummary]:
        """Search summaries that mention a topic."""
        conn = self._get_conn()
        c = conn.cursor()
        
        # Simple LIKE search - fast enough for small datasets
        c.execute("""
            SELECT * FROM session_summaries 
            WHERE topics LIKE ? OR summary_text LIKE ? OR entities_mentioned LIKE ?
            ORDER BY session_end DESC LIMIT ?
        """, (f'%{topic}%', f'%{topic}%', f'%{topic}%', limit))
        
        summaries = []
        for row in c.fetchall():
            summaries.append(SessionSummary(
                summary_id=row['summary_id'],
                thread_id=row['thread_id'],
                session_start=row['session_start'],
                session_end=row['session_end'],
                message_count=row['message_count'],
                summary_text=row['summary_text'],
                topics=json.loads(row['topics'] or '[]'),
                entities_mentioned=json.loads(row['entities_mentioned'] or '[]'),
                facts_learned=json.loads(row['facts_learned'] or '[]'),
                unresolved_items=json.loads(row['unresolved_items'] or '[]'),
                timestamp=row['timestamp']
            ))
        
        conn.close()
        return summaries
    
    # ========== User Preferences ==========
    
    def save_preference(self, pref: UserPreference):
        """Save or update a user preference."""
        conn = self._get_conn()
        c = conn.cursor()
        
        c.execute("""
            INSERT INTO user_preferences
            (pref_id, category, key, value, confidence, source, evidence, timestamp, active)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(category, key, value) DO UPDATE SET
                confidence = MAX(confidence, excluded.confidence),
                evidence = excluded.evidence,
                timestamp = excluded.timestamp,
                active = 1
        """, (
            pref.pref_id,
            pref.category,
            pref.key,
            pref.value,
            pref.confidence,
            pref.source,
            json.dumps(pref.evidence),
            pref.timestamp,
            1 if pref.active else 0
        ))
        
        conn.commit()
        conn.close()
    
    def get_preferences(self, category: Optional[str] = None) -> List[UserPreference]:
        """Get active preferences, optionally filtered by category."""
        conn = self._get_conn()
        c = conn.cursor()
        
        if category:
            c.execute("""
                SELECT * FROM user_preferences 
                WHERE category = ? AND active = 1
                ORDER BY confidence DESC
            """, (category,))
        else:
            c.execute("""
                SELECT * FROM user_preferences 
                WHERE active = 1
                ORDER BY category, confidence DESC
            """)
        
        prefs = []
        for row in c.fetchall():
            prefs.append(UserPreference(
                pref_id=row['pref_id'],
                category=row['category'],
                key=row['key'],
                value=row['value'],
                confidence=row['confidence'],
                source=row['source'],
                evidence=json.loads(row['evidence'] or '[]'),
                timestamp=row['timestamp'],
                active=bool(row['active'])
            ))
        
        conn.close()
        return prefs
    
    def get_preference_value(self, category: str, key: str) -> Optional[str]:
        """Get the highest-confidence value for a preference key."""
        conn = self._get_conn()
        c = conn.cursor()
        
        c.execute("""
            SELECT value FROM user_preferences 
            WHERE category = ? AND key = ? AND active = 1
            ORDER BY confidence DESC LIMIT 1
        """, (category, key))
        
        row = c.fetchone()
        conn.close()
        
        return row['value'] if row else None
    
    # ========== Interaction Patterns ==========
    
    def save_pattern(self, pattern: InteractionPattern):
        """Save or update an interaction pattern."""
        conn = self._get_conn()
        c = conn.cursor()
        
        c.execute("""
            INSERT OR REPLACE INTO interaction_patterns
            (pattern_id, pattern_type, description, evidence_count, confidence,
             first_seen, last_seen, metadata)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            pattern.pattern_id,
            pattern.pattern_type,
            pattern.description,
            pattern.evidence_count,
            pattern.confidence,
            pattern.first_seen,
            pattern.last_seen,
            json.dumps(pattern.metadata)
        ))
        
        conn.commit()
        conn.close()
    
    def get_patterns(self, pattern_type: Optional[str] = None, min_confidence: float = 0.3) -> List[InteractionPattern]:
        """Get patterns above confidence threshold."""
        conn = self._get_conn()
        c = conn.cursor()
        
        if pattern_type:
            c.execute("""
                SELECT * FROM interaction_patterns 
                WHERE pattern_type = ? AND confidence >= ?
                ORDER BY confidence DESC
            """, (pattern_type, min_confidence))
        else:
            c.execute("""
                SELECT * FROM interaction_patterns 
                WHERE confidence >= ?
                ORDER BY confidence DESC
            """, (min_confidence,))
        
        patterns = []
        for row in c.fetchall():
            patterns.append(InteractionPattern(
                pattern_id=row['pattern_id'],
                pattern_type=row['pattern_type'],
                description=row['description'],
                evidence_count=row['evidence_count'],
                confidence=row['confidence'],
                first_seen=row['first_seen'],
                last_seen=row['last_seen'],
                metadata=json.loads(row['metadata'] or '{}')
            ))
        
        conn.close()
        return patterns
    
    def increment_pattern(self, pattern_id: str) -> Optional[InteractionPattern]:
        """Increment evidence count and update last_seen for a pattern."""
        conn = self._get_conn()
        c = conn.cursor()
        
        now = time.time()
        
        c.execute("""
            UPDATE interaction_patterns 
            SET evidence_count = evidence_count + 1,
                last_seen = ?,
                confidence = MIN(0.95, confidence + 0.05)
            WHERE pattern_id = ?
        """, (now, pattern_id))
        
        conn.commit()
        
        # Return updated pattern
        c.execute("SELECT * FROM interaction_patterns WHERE pattern_id = ?", (pattern_id,))
        row = c.fetchone()
        conn.close()
        
        if row:
            return InteractionPattern(
                pattern_id=row['pattern_id'],
                pattern_type=row['pattern_type'],
                description=row['description'],
                evidence_count=row['evidence_count'],
                confidence=row['confidence'],
                first_seen=row['first_seen'],
                last_seen=row['last_seen'],
                metadata=json.loads(row['metadata'] or '{}')
            )
        return None
    
    # ========== Concept Nodes (Knowledge Graph) ==========
    
    def save_concept(self, concept: ConceptNode):
        """Save or update a concept node."""
        conn = self._get_conn()
        c = conn.cursor()
        
        c.execute("""
            INSERT OR REPLACE INTO concept_nodes
            (concept_id, canonical_name, aliases, concept_type, related_memory_ids,
             attributes, first_mentioned, last_mentioned, mention_count)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            concept.concept_id,
            concept.canonical_name,
            json.dumps(concept.aliases),
            concept.concept_type,
            json.dumps(concept.related_memory_ids),
            json.dumps(concept.attributes),
            concept.first_mentioned,
            concept.last_mentioned,
            concept.mention_count
        ))
        
        # Update alias lookup table
        for alias in [concept.canonical_name.lower()] + [a.lower() for a in concept.aliases]:
            c.execute("""
                INSERT OR REPLACE INTO concept_aliases (alias, concept_id)
                VALUES (?, ?)
            """, (alias, concept.concept_id))
        
        conn.commit()
        conn.close()
    
    def find_concept_by_name(self, name: str) -> Optional[ConceptNode]:
        """Find a concept by name or alias."""
        conn = self._get_conn()
        c = conn.cursor()
        
        # First check alias table (fast)
        c.execute("""
            SELECT concept_id FROM concept_aliases WHERE alias = ?
        """, (name.lower(),))
        
        row = c.fetchone()
        if row:
            concept_id = row['concept_id']
            c.execute("SELECT * FROM concept_nodes WHERE concept_id = ?", (concept_id,))
            crow = c.fetchone()
            conn.close()
            
            if crow:
                return ConceptNode(
                    concept_id=crow['concept_id'],
                    canonical_name=crow['canonical_name'],
                    aliases=json.loads(crow['aliases'] or '[]'),
                    concept_type=crow['concept_type'],
                    related_memory_ids=json.loads(crow['related_memory_ids'] or '[]'),
                    attributes=json.loads(crow['attributes'] or '{}'),
                    first_mentioned=crow['first_mentioned'],
                    last_mentioned=crow['last_mentioned'],
                    mention_count=crow['mention_count']
                )
        
        conn.close()
        return None
    
    def update_concept_mention(self, concept_id: str, memory_id: str):
        """Update concept with new memory reference."""
        conn = self._get_conn()
        c = conn.cursor()
        
        now = time.time()
        
        # Get current memory IDs
        c.execute("SELECT related_memory_ids FROM concept_nodes WHERE concept_id = ?", (concept_id,))
        row = c.fetchone()
        
        if row:
            memory_ids = json.loads(row['related_memory_ids'] or '[]')
            if memory_id not in memory_ids:
                memory_ids.append(memory_id)
                # Keep only last 100 references
                memory_ids = memory_ids[-100:]
            
            c.execute("""
                UPDATE concept_nodes 
                SET related_memory_ids = ?,
                    last_mentioned = ?,
                    mention_count = mention_count + 1
                WHERE concept_id = ?
            """, (json.dumps(memory_ids), now, concept_id))
            
            conn.commit()
        
        conn.close()
    
    def get_concepts_by_type(self, concept_type: str) -> List[ConceptNode]:
        """Get all concepts of a given type."""
        conn = self._get_conn()
        c = conn.cursor()
        
        c.execute("""
            SELECT * FROM concept_nodes 
            WHERE concept_type = ?
            ORDER BY mention_count DESC
        """, (concept_type,))
        
        concepts = []
        for row in c.fetchall():
            concepts.append(ConceptNode(
                concept_id=row['concept_id'],
                canonical_name=row['canonical_name'],
                aliases=json.loads(row['aliases'] or '[]'),
                concept_type=row['concept_type'],
                related_memory_ids=json.loads(row['related_memory_ids'] or '[]'),
                attributes=json.loads(row['attributes'] or '{}'),
                first_mentioned=row['first_mentioned'],
                last_mentioned=row['last_mentioned'],
                mention_count=row['mention_count']
            ))
        
        conn.close()
        return concepts
    
    # ========== Interaction Logging ==========
    
    def log_interaction(
        self,
        thread_id: str,
        query_length: int,
        response_length: int,
        query_type: str = 'unknown',
        topic_keywords: List[str] = None,
        sentiment: str = 'neutral',
        has_code: bool = False,
        has_emoji: bool = False,
        response_time_ms: int = 0
    ):
        """Log minimal interaction data for pattern detection."""
        conn = self._get_conn()
        c = conn.cursor()
        
        c.execute("""
            INSERT INTO interaction_log
            (thread_id, timestamp, query_length, response_length, query_type,
             topic_keywords, sentiment, has_code, has_emoji, response_time_ms)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            thread_id,
            time.time(),
            query_length,
            response_length,
            query_type,
            json.dumps(topic_keywords or []),
            sentiment,
            1 if has_code else 0,
            1 if has_emoji else 0,
            response_time_ms
        ))
        
        conn.commit()
        conn.close()
    
    def get_interaction_stats(self, thread_id: Optional[str] = None, window_hours: int = 24) -> Dict:
        """Get interaction statistics for pattern detection."""
        conn = self._get_conn()
        c = conn.cursor()
        
        cutoff = time.time() - (window_hours * 3600)
        
        if thread_id:
            c.execute("""
                SELECT 
                    COUNT(*) as total,
                    AVG(query_length) as avg_query_len,
                    AVG(response_length) as avg_response_len,
                    SUM(has_code) as code_count,
                    SUM(has_emoji) as emoji_count
                FROM interaction_log
                WHERE thread_id = ? AND timestamp > ?
            """, (thread_id, cutoff))
        else:
            c.execute("""
                SELECT 
                    COUNT(*) as total,
                    AVG(query_length) as avg_query_len,
                    AVG(response_length) as avg_response_len,
                    SUM(has_code) as code_count,
                    SUM(has_emoji) as emoji_count
                FROM interaction_log
                WHERE timestamp > ?
            """, (cutoff,))
        
        row = c.fetchone()
        conn.close()
        
        return {
            'total_interactions': row['total'] or 0,
            'avg_query_length': row['avg_query_len'] or 0,
            'avg_response_length': row['avg_response_len'] or 0,
            'code_interactions': row['code_count'] or 0,
            'emoji_interactions': row['emoji_count'] or 0
        }


# ============================================================================
# Preference Extraction
# ============================================================================

class PreferenceExtractor:
    """
    Extracts user preferences from explicit statements and infers from patterns.
    
    Explicit extraction patterns:
    - "I prefer verbose responses"
    - "Don't use emojis"
    - "I like Python code examples"
    - "Less formal please"
    
    Inferred patterns:
    - User always asks for more detail -> prefers verbose
    - User never uses emojis -> probably prefers no emojis
    - User asks about Python frequently -> Python preference
    """
    
    EXPLICIT_PATTERNS = [
        # Verbosity preferences
        (r'\b(i\s+)?(prefer|like|want)\s+(more\s+)?(verbose|detailed|thorough)\b', 
         'response_style', 'verbosity', 'verbose'),
        (r'\b(i\s+)?(prefer|like|want)\s+(more\s+)?(brief|concise|short)\b', 
         'response_style', 'verbosity', 'concise'),
        (r'\bmore\s+detail\s*please\b', 'response_style', 'verbosity', 'verbose'),
        (r'\bkeep\s+it\s+(short|brief)\b', 'response_style', 'verbosity', 'concise'),
        
        # Emoji preferences
        (r'\b(don\'?t|no|stop|avoid)\s+(use\s+)?emojis?\b', 
         'response_style', 'emoji_usage', 'none'),
        (r'\b(less|fewer)\s+emojis?\b', 'response_style', 'emoji_usage', 'minimal'),
        (r'\b(more|use)\s+emojis?\b', 'response_style', 'emoji_usage', 'frequent'),
        
        # Formality preferences  
        (r'\b(more\s+)?(casual|informal)\b.*\b(please|tone)\b', 
         'response_style', 'formality', 'casual'),
        (r'\b(more\s+)?(formal|professional)\b.*\b(please|tone)\b', 
         'response_style', 'formality', 'formal'),
        
        # Code style preferences
        (r'\bi\s+(use|prefer|like)\s+(python|javascript|typescript|rust|go)\b', 
         'code_style', 'language', None),  # Value extracted dynamically
        (r'\b(show|include)\s+code\s+examples?\b', 
         'response_style', 'code_examples', 'yes'),
        (r'\b(no|skip)\s+code\b', 'response_style', 'code_examples', 'no'),
    ]
    
    def __init__(self, db: EpisodicMemoryDB):
        self.db = db
        import re
        self._compiled_patterns = [
            (re.compile(p, re.IGNORECASE), cat, key, val) 
            for p, cat, key, val in self.EXPLICIT_PATTERNS
        ]
    
    def extract_explicit_preferences(self, text: str) -> List[UserPreference]:
        """Extract explicitly stated preferences from text."""
        found = []
        text_lower = text.lower()
        
        for pattern, category, key, value in self._compiled_patterns:
            match = pattern.search(text_lower)
            if match:
                # Dynamic value extraction for language preference
                if value is None and key == 'language':
                    for lang in ['python', 'javascript', 'typescript', 'rust', 'go', 'java', 'c#']:
                        if lang in text_lower:
                            value = lang
                            break
                
                if value:
                    pref_id = hashlib.md5(f"{category}:{key}:{value}".encode()).hexdigest()[:12]
                    pref = UserPreference(
                        pref_id=pref_id,
                        category=category,
                        key=key,
                        value=value,
                        confidence=0.9,  # Explicit statements are high confidence
                        source='explicit',
                        evidence=[f"User said: '{text[:100]}'"]
                    )
                    found.append(pref)
                    self.db.save_preference(pref)
        
        return found
    
    def infer_from_interaction(
        self, 
        query: str, 
        response: str, 
        user_feedback: Optional[str] = None
    ) -> List[UserPreference]:
        """Infer preferences from interaction patterns."""
        inferred = []
        
        # Check for implicit signals
        query_lower = query.lower()
        
        # User asking for more detail might indicate verbosity preference
        if any(phrase in query_lower for phrase in [
            'can you explain more', 'more detail', 'elaborate', 'expand on'
        ]):
            pref = self._create_inferred_pref(
                'response_style', 'verbosity', 'verbose', 0.4,
                f"User asked for elaboration: '{query[:50]}'"
            )
            inferred.append(pref)
        
        # User asking to shorten indicates concise preference
        if any(phrase in query_lower for phrase in [
            'too long', 'shorter', 'summarize', 'tldr', 'tl;dr'
        ]):
            pref = self._create_inferred_pref(
                'response_style', 'verbosity', 'concise', 0.5,
                f"User asked for brevity: '{query[:50]}'"
            )
            inferred.append(pref)
        
        # Check response for emoji usage to track what user sees
        has_emoji_response = any(ord(c) > 0x1F300 for c in response)
        
        # If user has negative feedback about emojis
        if user_feedback and any(word in user_feedback.lower() for word in ['emoji', 'emojis']):
            if any(neg in user_feedback.lower() for neg in ['no', 'stop', 'don\'t', 'hate']):
                pref = self._create_inferred_pref(
                    'response_style', 'emoji_usage', 'none', 0.7,
                    f"Negative feedback about emojis: '{user_feedback[:50]}'"
                )
                inferred.append(pref)
        
        return inferred
    
    def _create_inferred_pref(
        self, category: str, key: str, value: str, 
        confidence: float, evidence: str
    ) -> UserPreference:
        """Create an inferred preference and save it."""
        pref_id = hashlib.md5(f"{category}:{key}:{value}".encode()).hexdigest()[:12]
        
        # Check if this preference already exists
        existing = self.db.get_preferences(category)
        for ep in existing:
            if ep.key == key and ep.value == value:
                # Update existing with new evidence
                ep.evidence.append(evidence)
                ep.confidence = min(0.9, ep.confidence + 0.1)  # Increase confidence
                self.db.save_preference(ep)
                return ep
        
        pref = UserPreference(
            pref_id=pref_id,
            category=category,
            key=key,
            value=value,
            confidence=confidence,
            source='inferred',
            evidence=[evidence]
        )
        self.db.save_preference(pref)
        return pref


# ============================================================================
# Pattern Detector
# ============================================================================

class PatternDetector:
    """
    Detects behavioral patterns from interaction history.
    
    Pattern types:
    - topic_frequency: What topics does user discuss most?
    - session_timing: When does user typically chat?
    - question_style: How does user ask questions?
    - code_frequency: How often is code involved?
    """
    
    def __init__(self, db: EpisodicMemoryDB):
        self.db = db
    
    def analyze_topic_frequency(self, thread_id: Optional[str] = None) -> List[InteractionPattern]:
        """Analyze what topics user discusses most frequently."""
        conn = self.db._get_conn()
        c = conn.cursor()
        
        # Get recent topic keywords
        if thread_id:
            c.execute("""
                SELECT topic_keywords FROM interaction_log 
                WHERE thread_id = ? AND topic_keywords IS NOT NULL
                ORDER BY timestamp DESC LIMIT 100
            """, (thread_id,))
        else:
            c.execute("""
                SELECT topic_keywords FROM interaction_log 
                WHERE topic_keywords IS NOT NULL
                ORDER BY timestamp DESC LIMIT 100
            """)
        
        # Count topic frequency
        topic_counts = Counter()
        for row in c.fetchall():
            keywords = json.loads(row['topic_keywords'] or '[]')
            topic_counts.update(keywords)
        
        conn.close()
        
        # Create patterns for frequent topics
        patterns = []
        total = sum(topic_counts.values()) or 1
        
        for topic, count in topic_counts.most_common(10):
            if count >= 3:  # Minimum threshold
                frequency = count / total
                confidence = min(0.9, 0.3 + (frequency * 2))
                
                pattern_id = hashlib.md5(f"topic_freq:{topic}".encode()).hexdigest()[:12]
                pattern = InteractionPattern(
                    pattern_id=pattern_id,
                    pattern_type='topic_frequency',
                    description=f"User frequently discusses '{topic}' ({count} times)",
                    evidence_count=count,
                    confidence=confidence,
                    first_seen=time.time(),
                    last_seen=time.time(),
                    metadata={'topic': topic, 'count': count, 'frequency': frequency}
                )
                patterns.append(pattern)
                self.db.save_pattern(pattern)
        
        return patterns
    
    def analyze_response_preferences(self, thread_id: Optional[str] = None) -> List[InteractionPattern]:
        """Analyze user's response preferences from interaction data."""
        stats = self.db.get_interaction_stats(thread_id)
        
        patterns = []
        
        # Code preference
        if stats['total_interactions'] >= 5:
            code_ratio = stats['code_interactions'] / stats['total_interactions']
            if code_ratio > 0.5:
                pattern = InteractionPattern(
                    pattern_id=hashlib.md5(b"code_frequent").hexdigest()[:12],
                    pattern_type='code_preference',
                    description=f"User frequently involves code ({int(code_ratio*100)}% of interactions)",
                    evidence_count=stats['code_interactions'],
                    confidence=min(0.8, 0.3 + code_ratio),
                    first_seen=time.time(),
                    last_seen=time.time(),
                    metadata={'code_ratio': code_ratio}
                )
                patterns.append(pattern)
                self.db.save_pattern(pattern)
        
        # Query length preference (verbose vs concise user)
        if stats['avg_query_length'] and stats['total_interactions'] >= 5:
            avg_len = stats['avg_query_length']
            if avg_len > 100:
                pattern = InteractionPattern(
                    pattern_id=hashlib.md5(b"verbose_user").hexdigest()[:12],
                    pattern_type='communication_style',
                    description=f"User writes detailed messages (avg {int(avg_len)} chars)",
                    evidence_count=stats['total_interactions'],
                    confidence=0.5,
                    first_seen=time.time(),
                    last_seen=time.time(),
                    metadata={'avg_query_length': avg_len}
                )
                patterns.append(pattern)
                self.db.save_pattern(pattern)
            elif avg_len < 30:
                pattern = InteractionPattern(
                    pattern_id=hashlib.md5(b"concise_user").hexdigest()[:12],
                    pattern_type='communication_style',
                    description=f"User writes brief messages (avg {int(avg_len)} chars)",
                    evidence_count=stats['total_interactions'],
                    confidence=0.5,
                    first_seen=time.time(),
                    last_seen=time.time(),
                    metadata={'avg_query_length': avg_len}
                )
                patterns.append(pattern)
                self.db.save_pattern(pattern)
        
        return patterns


# ============================================================================
# Session Summarizer
# ============================================================================

class SessionSummarizer:
    """
    Creates narrative summaries of conversation sessions.
    
    Triggers:
    - End of session (inactivity timeout)
    - Explicit "summarize this chat" request
    - Periodic background summarization
    """
    
    def __init__(self, db: EpisodicMemoryDB, memory_system=None):
        self.db = db
        self.memory_system = memory_system  # CRTMemorySystem for storing as memory
    
    def summarize_session(
        self,
        thread_id: str,
        messages: List[Dict],  # List of {role, text, timestamp}
        llm_client=None  # Optional LLM for better summaries
    ) -> SessionSummary:
        """
        Create a summary of a conversation session.
        
        If LLM available, uses it for natural summary.
        Otherwise, uses heuristic extraction.
        """
        if not messages:
            return None
        
        session_start = messages[0].get('timestamp', time.time())
        session_end = messages[-1].get('timestamp', time.time())
        
        # Extract topics and entities using simple heuristics
        topics = self._extract_topics(messages)
        entities = self._extract_entities(messages)
        facts = self._extract_facts_mentioned(messages)
        unresolved = self._extract_unresolved(messages)
        
        # Generate summary text
        if llm_client:
            summary_text = self._llm_summarize(messages, llm_client)
        else:
            summary_text = self._heuristic_summarize(messages, topics, entities)
        
        summary_id = hashlib.md5(f"{thread_id}:{session_start}:{session_end}".encode()).hexdigest()[:16]
        
        summary = SessionSummary(
            summary_id=summary_id,
            thread_id=thread_id,
            session_start=session_start,
            session_end=session_end,
            message_count=len(messages),
            summary_text=summary_text,
            topics=topics,
            entities_mentioned=entities,
            facts_learned=facts,
            unresolved_items=unresolved
        )
        
        # Save to database
        self.db.save_session_summary(summary)
        
        # Optionally store as a compressed memory for RAG retrieval
        if self.memory_system:
            try:
                self.memory_system.add(
                    text=f"[SESSION SUMMARY] {summary_text}",
                    source="session_summary",
                    sse_mode="C",  # Compressed
                    confidence=0.7,
                    trust=0.6,
                )
            except Exception as e:
                logger.warning(f"Failed to store session summary as memory: {e}")
        
        return summary
    
    def _extract_topics(self, messages: List[Dict]) -> List[str]:
        """Extract main topics from messages using keyword frequency."""
        import re
        
        # Combine all text
        all_text = ' '.join(m.get('text', '') for m in messages).lower()
        
        # Remove common words
        stopwords = {
            'the', 'a', 'an', 'is', 'are', 'was', 'were', 'be', 'been',
            'i', 'you', 'we', 'they', 'it', 'this', 'that', 'what', 'how',
            'can', 'could', 'would', 'should', 'will', 'do', 'does', 'did',
            'to', 'of', 'in', 'for', 'on', 'with', 'at', 'by', 'from',
            'and', 'or', 'but', 'if', 'then', 'so', 'as', 'just', 'like',
            'my', 'your', 'his', 'her', 'its', 'our', 'their',
            'have', 'has', 'had', 'get', 'got', 'make', 'made',
            'about', 'also', 'more', 'some', 'any', 'all', 'most',
            'please', 'thanks', 'thank', 'okay', 'ok', 'yes', 'no',
            'want', 'need', 'help', 'know', 'think', 'see', 'look',
        }
        
        # Extract words
        words = re.findall(r'\b[a-z]{4,}\b', all_text)
        words = [w for w in words if w not in stopwords]
        
        # Count frequency
        counter = Counter(words)
        
        # Return top topics
        return [word for word, count in counter.most_common(5) if count >= 2]
    
    def _extract_entities(self, messages: List[Dict]) -> List[str]:
        """Extract named entities (capitalized words/phrases)."""
        import re
        
        entities = set()
        
        for msg in messages:
            text = msg.get('text', '')
            
            # Find capitalized words/phrases (likely names, projects, etc.)
            # Pattern: Capital letter followed by lowercase, possibly with more words
            matches = re.findall(r'\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\b', text)
            
            for match in matches:
                # Filter out common sentence starters
                if match.lower() not in {'the', 'this', 'that', 'what', 'how', 'why', 'when', 'where', 'i', 'you'}:
                    entities.add(match)
        
        return list(entities)[:10]  # Limit to 10
    
    def _extract_facts_mentioned(self, messages: List[Dict]) -> List[str]:
        """Extract facts that were discussed/learned."""
        facts = []
        
        # Look for "is/are" statements from user
        import re
        for msg in messages:
            if msg.get('role') == 'user':
                text = msg.get('text', '')
                # Simple fact patterns
                matches = re.findall(
                    r'(?:my|i)\s+(?:am|work|live|have|like|prefer)\s+[^.!?]{3,50}',
                    text, re.IGNORECASE
                )
                facts.extend(matches[:3])
        
        return facts[:5]
    
    def _extract_unresolved(self, messages: List[Dict]) -> List[str]:
        """Extract questions/tasks that weren't clearly resolved."""
        unresolved = []
        
        # Look for question patterns in recent messages
        for msg in messages[-5:]:
            text = msg.get('text', '')
            if '?' in text and msg.get('role') == 'user':
                # Check if next message (if any) seems to answer it
                unresolved.append(text[:100])
        
        return unresolved[:3]
    
    def _heuristic_summarize(
        self, 
        messages: List[Dict], 
        topics: List[str], 
        entities: List[str]
    ) -> str:
        """Generate summary without LLM."""
        msg_count = len(messages)
        user_msgs = [m for m in messages if m.get('role') == 'user']
        
        # Build summary
        parts = [f"Conversation with {msg_count} messages."]
        
        if topics:
            parts.append(f"Main topics: {', '.join(topics)}.")
        
        if entities:
            parts.append(f"Mentioned: {', '.join(entities[:5])}.")
        
        # First and last user message context
        if user_msgs:
            first_q = user_msgs[0].get('text', '')[:50]
            parts.append(f"Started with: '{first_q}...'")
            
            if len(user_msgs) > 1:
                last_q = user_msgs[-1].get('text', '')[:50]
                parts.append(f"Ended with: '{last_q}...'")
        
        return ' '.join(parts)
    
    def _llm_summarize(self, messages: List[Dict], llm_client) -> str:
        """Generate summary using LLM."""
        # Build conversation text (limited to avoid token overflow)
        conv_text = []
        for msg in messages[-20:]:  # Last 20 messages
            role = msg.get('role', 'user')
            text = msg.get('text', '')[:200]
            conv_text.append(f"{role}: {text}")
        
        prompt = f"""Summarize this conversation in 2-3 sentences. Focus on:
- Main topics discussed
- Key facts learned about the user
- Any unresolved questions or tasks

Conversation:
{chr(10).join(conv_text)}

Summary:"""
        
        try:
            response = llm_client.generate(prompt, max_tokens=150)
            return response.strip()
        except Exception as e:
            logger.warning(f"LLM summary failed: {e}")
            return self._heuristic_summarize(messages, [], [])


# ============================================================================
# Concept Linker
# ============================================================================

class ConceptLinker:
    """
    Links mentions of entities/concepts across conversations.
    
    Resolves:
    - "the project" -> "Project Alpha"
    - "my boss" -> "Sarah (boss at Acme Corp)"
    - Typos and variations
    """
    
    def __init__(self, db: EpisodicMemoryDB):
        self.db = db
    
    def link_or_create(
        self,
        name: str,
        concept_type: str,
        memory_id: Optional[str] = None,
        attributes: Dict[str, str] = None
    ) -> ConceptNode:
        """
        Find existing concept or create new one.
        Links memory_id if provided.
        """
        # Try to find existing concept
        existing = self.db.find_concept_by_name(name)
        
        if existing:
            # Update with new mention
            if memory_id:
                self.db.update_concept_mention(existing.concept_id, memory_id)
            
            # Merge attributes
            if attributes:
                existing.attributes.update(attributes)
                self.db.save_concept(existing)
            
            return existing
        
        # Create new concept
        concept_id = hashlib.md5(f"{concept_type}:{name.lower()}".encode()).hexdigest()[:16]
        
        concept = ConceptNode(
            concept_id=concept_id,
            canonical_name=name,
            aliases=[],
            concept_type=concept_type,
            related_memory_ids=[memory_id] if memory_id else [],
            attributes=attributes or {},
            first_mentioned=time.time(),
            last_mentioned=time.time(),
            mention_count=1
        )
        
        self.db.save_concept(concept)
        return concept
    
    def add_alias(self, concept_id: str, alias: str):
        """Add an alias to an existing concept."""
        conn = self.db._get_conn()
        c = conn.cursor()
        
        # Get current concept
        c.execute("SELECT aliases FROM concept_nodes WHERE concept_id = ?", (concept_id,))
        row = c.fetchone()
        
        if row:
            aliases = json.loads(row['aliases'] or '[]')
            if alias.lower() not in [a.lower() for a in aliases]:
                aliases.append(alias)
                c.execute("""
                    UPDATE concept_nodes SET aliases = ? WHERE concept_id = ?
                """, (json.dumps(aliases), concept_id))
                
                # Add to alias lookup
                c.execute("""
                    INSERT OR REPLACE INTO concept_aliases (alias, concept_id)
                    VALUES (?, ?)
                """, (alias.lower(), concept_id))
                
                conn.commit()
        
        conn.close()
    
    def extract_and_link_from_text(
        self,
        text: str,
        memory_id: Optional[str] = None
    ) -> List[ConceptNode]:
        """
        Extract entities from text and link to concepts.
        Uses simple NER patterns (no ML required).
        """
        import re
        
        linked = []
        
        # Pattern: "my [relation] [Name]" -> person concept
        relation_pattern = r'my\s+(boss|manager|friend|colleague|partner|wife|husband|brother|sister|mom|dad|mother|father)\s+([A-Z][a-z]+)'
        for match in re.finditer(relation_pattern, text, re.IGNORECASE):
            relation = match.group(1).lower()
            name = match.group(2)
            
            concept = self.link_or_create(
                name=name,
                concept_type='person',
                memory_id=memory_id,
                attributes={'relation': relation}
            )
            linked.append(concept)
        
        # Pattern: "Project [Name]" or "[Name] project"
        project_pattern = r'(?:project\s+([A-Z][a-z]+)|([A-Z][a-z]+)\s+project)'
        for match in re.finditer(project_pattern, text, re.IGNORECASE):
            name = match.group(1) or match.group(2)
            if name:
                concept = self.link_or_create(
                    name=f"Project {name}",
                    concept_type='project',
                    memory_id=memory_id
                )
                linked.append(concept)
        
        # Pattern: "[Company] (where I work)" or "I work at [Company]"
        company_pattern = r'(?:work\s+(?:at|for)\s+([A-Z][a-zA-Z]+)|([A-Z][a-zA-Z]+)(?:\s+where\s+I\s+work))'
        for match in re.finditer(company_pattern, text, re.IGNORECASE):
            name = match.group(1) or match.group(2)
            if name and name.lower() not in {'the', 'a', 'my'}:
                concept = self.link_or_create(
                    name=name,
                    concept_type='organization',
                    memory_id=memory_id,
                    attributes={'relationship': 'employer'}
                )
                linked.append(concept)
        
        return linked


# ============================================================================
# Unified Episodic Memory Manager
# ============================================================================

class EpisodicMemoryManager:
    """
    Unified interface for all episodic memory capabilities.
    
    Usage:
        manager = EpisodicMemoryManager()
        
        # On each interaction
        manager.process_interaction(thread_id, query, response)
        
        # At session end
        manager.finalize_session(thread_id, messages)
        
        # Query context for prompts
        context = manager.get_user_context()
    """
    
    def __init__(self, db_path: Optional[str] = None, memory_system=None):
        self.db = EpisodicMemoryDB(db_path)
        self.preference_extractor = PreferenceExtractor(self.db)
        self.pattern_detector = PatternDetector(self.db)
        self.summarizer = SessionSummarizer(self.db, memory_system)
        self.linker = ConceptLinker(self.db)
        self.memory_system = memory_system
        
        # Lightweight keyword extraction (no heavy NLP)
        self._topic_keywords_cache = set()
    
    def process_interaction(
        self,
        thread_id: str,
        query: str,
        response: str,
        response_time_ms: int = 0,
        llm_client=None
    ):
        """
        Process a single interaction for patterns, preferences, and concepts.
        
        Designed to be FAST - no heavy processing on critical path.
        """
        now = time.time()
        
        # 1. Extract explicit preferences (fast regex)
        self.preference_extractor.extract_explicit_preferences(query)
        
        # 2. Log interaction (fast DB insert)
        topic_keywords = self._extract_keywords_fast(query)
        has_code = '```' in query or '```' in response
        has_emoji = any(ord(c) > 0x1F300 for c in response)
        
        query_type = self._classify_query_fast(query)
        
        self.db.log_interaction(
            thread_id=thread_id,
            query_length=len(query),
            response_length=len(response),
            query_type=query_type,
            topic_keywords=topic_keywords,
            has_code=has_code,
            has_emoji=has_emoji,
            response_time_ms=response_time_ms
        )
        
        # 3. Link concepts mentioned (fast pattern matching)
        self.linker.extract_and_link_from_text(query)
        
        # 4. Infer preferences from interaction (lightweight)
        self.preference_extractor.infer_from_interaction(query, response)
    
    def _extract_keywords_fast(self, text: str) -> List[str]:
        """Fast keyword extraction without heavy NLP."""
        import re
        
        # Extract notable words (4+ chars, not common)
        words = re.findall(r'\b[a-zA-Z]{4,}\b', text.lower())
        
        common = {
            'that', 'this', 'what', 'have', 'with', 'your', 'about',
            'would', 'there', 'their', 'could', 'which', 'these',
            'them', 'been', 'were', 'being', 'some', 'when', 'just',
            'also', 'into', 'more', 'will', 'from', 'like', 'than',
            'very', 'should', 'because', 'please', 'thanks', 'want',
            'need', 'help', 'know', 'think'
        }
        
        keywords = [w for w in words if w not in common]
        
        # Return unique keywords, preserving order
        seen = set()
        result = []
        for kw in keywords:
            if kw not in seen:
                seen.add(kw)
                result.append(kw)
        
        return result[:10]
    
    def _classify_query_fast(self, query: str) -> str:
        """Fast query type classification."""
        q = query.lower().strip()
        
        if q.endswith('?') or q.startswith(('what', 'how', 'why', 'when', 'where', 'who', 'can you', 'could you')):
            return 'question'
        elif q.startswith(('do', 'make', 'create', 'build', 'write', 'fix', 'update', 'add', 'remove')):
            return 'command'
        elif any(w in q for w in ['my name is', 'i am', 'i work', 'i live']):
            return 'statement'
        else:
            return 'other'
    
    def finalize_session(
        self,
        thread_id: str,
        messages: List[Dict],
        llm_client=None
    ) -> Optional[SessionSummary]:
        """
        Finalize a session - create summary and run pattern analysis.
        
        Call this when:
        - User explicitly ends session
        - Inactivity timeout
        - Application shutdown
        """
        if not messages or len(messages) < 3:
            return None
        
        # Create session summary
        summary = self.summarizer.summarize_session(thread_id, messages, llm_client)
        
        # Run pattern analysis (can be async in production)
        self.pattern_detector.analyze_topic_frequency(thread_id)
        self.pattern_detector.analyze_response_preferences(thread_id)
        
        return summary
    
    def get_user_context(self, include_summaries: int = 3) -> Dict:
        """
        Get comprehensive user context for prompt building.
        
        Returns dict with:
        - preferences: Active user preferences
        - patterns: Detected behavioral patterns
        - recent_summaries: Recent session summaries
        - concepts: Key concepts/entities
        """
        context = {
            'preferences': {},
            'patterns': [],
            'recent_summaries': [],
            'concepts': []
        }
        
        # Get preferences grouped by category
        prefs = self.db.get_preferences()
        for pref in prefs:
            if pref.category not in context['preferences']:
                context['preferences'][pref.category] = {}
            context['preferences'][pref.category][pref.key] = {
                'value': pref.value,
                'confidence': pref.confidence,
                'source': pref.source
            }
        
        # Get high-confidence patterns
        patterns = self.db.get_patterns(min_confidence=0.5)
        context['patterns'] = [
            {'type': p.pattern_type, 'description': p.description, 'confidence': p.confidence}
            for p in patterns[:5]
        ]
        
        # Get recent summaries
        summaries = self.db.get_recent_summaries(limit=include_summaries)
        context['recent_summaries'] = [
            {'summary': s.summary_text, 'topics': s.topics, 'timestamp': s.timestamp}
            for s in summaries
        ]
        
        # Get key concepts (most mentioned)
        for ctype in ['person', 'project', 'organization']:
            concepts = self.db.get_concepts_by_type(ctype)
            for c in concepts[:3]:
                context['concepts'].append({
                    'name': c.canonical_name,
                    'type': c.concept_type,
                    'mentions': c.mention_count,
                    'attributes': c.attributes
                })
        
        return context
    
    def build_context_prompt(self) -> str:
        """
        Build a context section for LLM prompts based on learned info.
        
        Returns a string suitable for inclusion in system prompts.
        """
        ctx = self.get_user_context()
        
        parts = []
        
        # Preferences
        if ctx['preferences']:
            pref_lines = []
            for category, prefs in ctx['preferences'].items():
                for key, data in prefs.items():
                    if data['confidence'] >= 0.5:
                        pref_lines.append(f"- {category}/{key}: {data['value']}")
            
            if pref_lines:
                parts.append("User preferences:\n" + "\n".join(pref_lines))
        
        # Patterns
        if ctx['patterns']:
            pattern_lines = [f"- {p['description']}" for p in ctx['patterns']]
            parts.append("Observed patterns:\n" + "\n".join(pattern_lines))
        
        # Recent context
        if ctx['recent_summaries']:
            recent = ctx['recent_summaries'][0]
            parts.append(f"Recent conversation: {recent['summary']}")
        
        # Key entities
        if ctx['concepts']:
            concept_lines = [
                f"- {c['name']} ({c['type']})" + (f": {c['attributes']}" if c['attributes'] else "")
                for c in ctx['concepts'][:5]
            ]
            parts.append("Known entities:\n" + "\n".join(concept_lines))
        
        return "\n\n".join(parts) if parts else ""


# ============================================================================
# Global Instance
# ============================================================================

_episodic_manager: Optional[EpisodicMemoryManager] = None


def get_episodic_manager(db_path: Optional[str] = None, memory_system=None) -> EpisodicMemoryManager:
    """Get or create global episodic memory manager."""
    global _episodic_manager
    if _episodic_manager is None:
        _episodic_manager = EpisodicMemoryManager(db_path, memory_system)
    return _episodic_manager
