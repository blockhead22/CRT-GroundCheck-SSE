"""
CRT Contradiction Ledger - No Silent Overwrites

Implements:
- Contradiction event tracking
- Ledger entries (not deletions)
- Drift measurement and logging
- Resolution status tracking
- No memory replacement, only recorded tension

Philosophy:
- Contradictions are signals, not bugs
- Nothing is deleted or silently replaced
- Tension is preserved until reflection
- History matters more than consistency
"""

import sqlite3
import json
import logging
import numpy as np
from typing import List, Dict, Optional, Tuple, Any
from datetime import datetime
from dataclasses import dataclass
import time

_logger = logging.getLogger(__name__)

from .runtime_paths import resolve_runtime_path
from .crt_core import CRTMath, CRTConfig, MemorySource
from .fact_slots import extract_fact_slots, create_simple_fact
from .two_tier_facts import TwoTierFactSystem, TwoTierExtractionResult
from .crt_semantic_anchor import (
    SemanticAnchor,
    generate_clarification_prompt,
    parse_user_answer,
    is_resolution_grounded,
)

# Import disposition classifier (Phase G1)
_disposition_classifier = None

def _get_disposition_classifier():
    """Lazy-load the disposition classifier."""
    global _disposition_classifier
    if _disposition_classifier is None:
        try:
            from .disposition_classifier import classify_contradiction as _classify_disp
            _disposition_classifier = _classify_disp
        except ImportError:
            _logger.debug("[DISPOSITION] disposition_classifier not available")
    return _disposition_classifier


# Import LLM drift assessor (lazy-loaded to avoid startup cost)
_llm_drift_assessor = None

def _get_drift_assessor():
    """Lazy-load drift assessor."""
    global _llm_drift_assessor
    if _llm_drift_assessor is None:
        try:
            from .llm_drift_assessor import get_drift_assessor
            _llm_drift_assessor = get_drift_assessor()
        except ImportError:
            pass
    return _llm_drift_assessor


# ---------------------------------------------------------------------------
# Tension Type Classification (goal formation layer)
# ---------------------------------------------------------------------------
# Lightweight rule-based classifier matching the lab's TensionClassifier.
# Runs inside record_contradiction() to tag every ledger entry with its
# tension type: state_change, factual_error, staleness, identity_conflict,
# or ambivalence. This feeds the goal formation engine.

_STATE_VERBS = {"owns", "has", "uses", "works", "lives", "prefers", "takes",
                "drives", "runs", "studies", "plays", "exercises",
                "left", "quit", "freelancing", "self-employed"}

_TRANSITION_DELIBERATIVE = {
    "thinking about", "considering", "might", "maybe", "should",
    "contemplating", "wondering if",
}

_TRANSITION_COMPLETED = {
    "sold", "left", "quit", "switched", "moved", "stopped",
    "dropped", "already", "now taking", "now using", "doctor switched",
}

_IDENTITY_NEGATIVE = {
    "don't know if", "not sure i", "doubt", "can't", "not cut out",
    "not good enough", "imposter", "second guess",
}

_IDENTITY_POSITIVE = {
    "capable", "built", "created", "proven", "achieved", "skilled",
}


def _classify_tension_type(
    old_text: str,
    new_text: str,
    contradiction_type: Optional[str] = None,
    drift_mean: float = 0.0,
    confidence_delta: float = 0.0,
) -> Tuple[Optional[str], float]:
    """Classify the tension type between two contradicting texts.

    Returns (tension_type, magnitude) or (None, 0.0).
    """
    old_lower = old_text.lower()
    new_lower = new_text.lower()

    # 1. Identity conflict
    old_neg = any(m in old_lower for m in _IDENTITY_NEGATIVE)
    old_pos = any(m in old_lower for m in _IDENTITY_POSITIVE)
    new_neg = any(m in new_lower for m in _IDENTITY_NEGATIVE)
    new_pos = any(m in new_lower for m in _IDENTITY_POSITIVE)
    if (old_pos and new_neg) or (old_neg and new_pos):
        magnitude = min(1.0, abs(confidence_delta) * 1.2 + 0.3)
        return ("identity_conflict", magnitude)

    # 2. State change
    has_state = any(v in old_lower for v in _STATE_VERBS)
    is_delib = any(t in new_lower for t in _TRANSITION_DELIBERATIVE)
    is_completed = any(t in new_lower for t in _TRANSITION_COMPLETED)
    if has_state and (is_delib or is_completed):
        magnitude = min(1.0, drift_mean * 0.8 + 0.2)
        return ("state_change", magnitude)

    # 3. Check contradiction_type from existing classification
    if contradiction_type == "temporal":
        return ("staleness", min(0.7, drift_mean + 0.2))

    # 4. Factual error (default for CONFLICT type with high drift)
    if contradiction_type == "conflict" and drift_mean > 0.3:
        return ("factual_error", min(1.0, drift_mean))

    # 5. Ambivalence (low drift, similar confidence)
    if drift_mean < 0.2 and abs(confidence_delta) < 0.15:
        return ("ambivalence", 0.3)

    # Fallback: use drift as generic tension
    if drift_mean > 0.2:
        return ("factual_error", min(1.0, drift_mean))

    return (None, 0.0)


class ContradictionStatus:
    """Status of contradiction resolution."""
    OPEN = "open"              # Unresolved tension
    REFLECTING = "reflecting"  # Reflection in progress
    RESOLVED = "resolved"      # Merged via reflection
    ACCEPTED = "accepted"      # Both kept as valid perspectives


class ContradictionType:
    """Type of contradiction based on fact topology."""
    REFINEMENT = "refinement"  # More specific information (Seattle → Bellevue)
    REVISION = "revision"      # Explicit correction ("actually", "I meant", "not X")
    TEMPORAL = "temporal"      # Time-based progression (Senior → Principal)
    CONFLICT = "conflict"      # Mutually exclusive facts (Microsoft vs Amazon)
    DENIAL = "denial"          # User denies a previously stated fact (gaslighting detection)


@dataclass
class ContradictionEntry:
    """
    A contradiction ledger entry.
    
    Records:
    - Old memory (prior belief)
    - New memory (contradicting belief)
    - Drift measurements
    - Resolution status
    - Reflection metadata
    """
    ledger_id: str
    timestamp: float
    old_memory_id: str
    new_memory_id: str
    
    # Drift measurements
    drift_mean: float           # Meaning drift
    drift_reason: Optional[float] = None  # Reasoning drift (optional)
    confidence_delta: float = 0.0
    
    # Status
    status: str = ContradictionStatus.OPEN
    contradiction_type: str = ContradictionType.CONFLICT  # Default to conflict
    
    # Slot tracking - which fact slots does this contradiction affect?
    affects_slots: Optional[str] = None  # Comma-separated slot names (e.g., "employer,location")
    
    # Tension type classification (goal formation layer)
    # state_change | factual_error | staleness | identity_conflict | ambivalence
    tension_type: Optional[str] = None
    tension_magnitude: float = 0.0  # 0.0-1.0, severity of the tension

    # Disposition classification (Phase G1: resolvable/held/evolving/contextual)
    disposition: Optional[str] = None           # resolvable | held | evolving | contextual | unknown
    disposition_confidence: float = 0.0         # classifier confidence 0-1
    disposition_explanation: Optional[str] = None

    # Metadata
    query: Optional[str] = None
    summary: Optional[str] = None
    resolution_timestamp: Optional[float] = None
    resolution_method: Optional[str] = None
    merged_memory_id: Optional[str] = None
    thread_id: Optional[str] = None

    def to_dict(self) -> Dict:
        """Convert to dictionary."""
        return {
            'ledger_id': self.ledger_id,
            'timestamp': self.timestamp,
            'old_memory_id': self.old_memory_id,
            'new_memory_id': self.new_memory_id,
            'drift_mean': self.drift_mean,
            'drift_reason': self.drift_reason,
            'confidence_delta': self.confidence_delta,
            'status': self.status,
            'contradiction_type': self.contradiction_type,
            'affects_slots': self.affects_slots,
            'disposition': self.disposition,
            'disposition_confidence': self.disposition_confidence,
            'disposition_explanation': self.disposition_explanation,
            'query': self.query,
            'summary': self.summary,
            'resolution_timestamp': self.resolution_timestamp,
            'resolution_method': self.resolution_method,
            'merged_memory_id': self.merged_memory_id,
            'thread_id': self.thread_id,
        }


class ContradictionLedger:
    """
    CRT contradiction ledger system.
    
    NO SILENT OVERWRITES.
    
    When beliefs diverge:
    1. Create ledger entry
    2. Preserve both old and new
    3. Log drift measurements
    4. Track resolution status
    5. Trigger reflection if needed
    """
    
    def __init__(
        self,
        db_path: Optional[str] = None,
        config: Optional[CRTConfig] = None
    ):
        """Initialize ledger."""
        self.db_path = db_path or str(resolve_runtime_path("crt_ledger.db"))
        self.config = config or CRTConfig()
        self.crt_math = CRTMath(self.config)
        self.two_tier_system: Optional[TwoTierFactSystem] = None
        self.default_thread_id: Optional[str] = None
        
        self._init_db()
    
    def set_two_tier_system(self, system: Optional[TwoTierFactSystem]) -> None:
        """Set the two-tier fact extraction system for enhanced contradiction detection."""
        self.two_tier_system = system
    
    def _extract_all_facts(self, text: str) -> Dict[str, Any]:
        """
        Extract all facts (hard slots + open tuples) from text.
        
        Uses two-tier system if available, otherwise falls back to regex-only.
        Returns a unified dictionary of all facts.
        """
        if self.two_tier_system is not None:
            try:
                result = self.two_tier_system.extract_facts(text, skip_llm=True)
                # Combine hard facts and open tuples
                all_facts = dict(result.hard_facts)
                # Add open tuples with high confidence
                for tuple_fact in result.open_tuples:
                    if tuple_fact.confidence >= 0.6 and tuple_fact.attribute not in all_facts:
                        # Create a compatible fact object using helper
                        all_facts[tuple_fact.attribute] = create_simple_fact(tuple_fact.value)
                # If two-tier returned results, use them; otherwise fall back
                if all_facts:
                    return all_facts
            except Exception as e:
                # Fall back to regex
                import logging
                logging.warning(f"[TWO_TIER] Failed to extract facts, falling back to regex: {e}")
        
        return extract_fact_slots(text) or {}
    
    def _get_connection(self, timeout: float = 30.0) -> sqlite3.Connection:
        """
        Create a properly configured SQLite connection with:
        - WAL mode for better concurrent access
        - Busy timeout to retry on lock conflicts
        """
        conn = sqlite3.connect(self.db_path, timeout=timeout, check_same_thread=False)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
        conn.execute("PRAGMA busy_timeout=5000")  # 5 second busy timeout (reduced)
        return conn

    def _has_contradiction_thread_column(self) -> bool:
        """Return True when the contradictions table includes thread_id."""
        conn = self._get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("PRAGMA table_info(contradictions)")
            return any(str(row[1] or "") == "thread_id" for row in cursor.fetchall())
        finally:
            conn.close()
    
    def _init_db(self):
        """Initialize database."""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        # Contradiction ledger table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS contradictions (
                ledger_id TEXT PRIMARY KEY,
                timestamp REAL NOT NULL,
                old_memory_id TEXT NOT NULL,
                new_memory_id TEXT NOT NULL,
                drift_mean REAL NOT NULL,
                drift_reason REAL,
                confidence_delta REAL,
                status TEXT NOT NULL,
                contradiction_type TEXT DEFAULT 'conflict',
                affects_slots TEXT,
                query TEXT,
                summary TEXT,
                resolution_timestamp REAL,
                resolution_method TEXT,
                merged_memory_id TEXT,
                metadata TEXT,
                thread_id TEXT
            )
        """)
        
        # Migration: Add metadata column if missing (for existing databases)
        try:
            cursor.execute("ALTER TABLE contradictions ADD COLUMN metadata TEXT")
        except Exception:
            pass  # Column already exists
        try:
            cursor.execute("ALTER TABLE contradictions ADD COLUMN thread_id TEXT")
        except Exception:
            pass  # Column already exists
        try:
            cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_contradictions_thread_status "
                "ON contradictions(thread_id, status, timestamp)"
            )
        except Exception:
            pass
        
        # Reflection queue
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS reflection_queue (
                queue_id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp REAL NOT NULL,
                ledger_id TEXT NOT NULL,
                volatility REAL NOT NULL,
                priority TEXT NOT NULL,
                context_json TEXT,
                processed INTEGER DEFAULT 0,
                FOREIGN KEY (ledger_id) REFERENCES contradictions(ledger_id)
            )
        """)

        # Worklog for "contradictions become goals": record when we asked the user to clarify.
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS contradiction_worklog (
                ledger_id TEXT PRIMARY KEY,
                first_asked_at REAL,
                last_asked_at REAL,
                ask_count INTEGER DEFAULT 0,
                last_user_answer TEXT,
                last_user_answer_at REAL
            )
        """)
        
        # Conflict resolutions table - tracks user-driven resolution decisions
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS conflict_resolutions (
                ledger_id TEXT PRIMARY KEY,
                resolution_method TEXT NOT NULL,
                chosen_memory_id TEXT,
                user_feedback TEXT,
                timestamp REAL NOT NULL,
                FOREIGN KEY (ledger_id) REFERENCES contradictions(ledger_id)
            )
        """)
        
        # Performance indexes to avoid full table scans
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_contradictions_status 
            ON contradictions(status)
        """)
        
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_contradictions_old_memory 
            ON contradictions(old_memory_id)
        """)
        
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_contradictions_new_memory 
            ON contradictions(new_memory_id)
        """)
        
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_reflection_queue_processed 
            ON reflection_queue(processed, priority)
        """)
        
        # =================================================================
        # Schema migrations for Phase 1-3 enhancements
        # =================================================================
        
        # Add fact_tuples column for storing LLM-extracted tuples as JSON
        try:
            cursor.execute("""
                ALTER TABLE contradictions ADD COLUMN fact_tuples TEXT
            """)
        except sqlite3.OperationalError:
            pass  # Column already exists
        
        # Add extraction_method column (regex, llm, or hybrid)
        try:
            cursor.execute("""
                ALTER TABLE contradictions ADD COLUMN extraction_method TEXT DEFAULT 'regex'
            """)
        except sqlite3.OperationalError:
            pass  # Column already exists
        
        # Add lifecycle_state column for contradiction lifecycle tracking
        try:
            cursor.execute("""
                ALTER TABLE contradictions ADD COLUMN lifecycle_state TEXT DEFAULT 'active'
            """)
        except sqlite3.OperationalError:
            pass  # Column already exists
        
        # Add confirmation_count for tracking user confirmations
        try:
            cursor.execute("""
                ALTER TABLE contradictions ADD COLUMN confirmation_count INTEGER DEFAULT 0
            """)
        except sqlite3.OperationalError:
            pass  # Column already exists
        
        # Add disclosure_count for tracking how many times disclosed
        try:
            cursor.execute("""
                ALTER TABLE contradictions ADD COLUMN disclosure_count INTEGER DEFAULT 0
            """)
        except sqlite3.OperationalError:
            pass  # Column already exists
        
        # Add settled_at timestamp for lifecycle tracking
        try:
            cursor.execute("""
                ALTER TABLE contradictions ADD COLUMN settled_at REAL
            """)
        except sqlite3.OperationalError:
            pass  # Column already exists
        
        # Add archived_at timestamp for lifecycle tracking
        try:
            cursor.execute("""
                ALTER TABLE contradictions ADD COLUMN archived_at REAL
            """)
        except sqlite3.OperationalError:
            pass  # Column already exists
        
        # Create contradiction_lifecycle table for detailed state tracking
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS contradiction_lifecycle (
                ledger_id TEXT PRIMARY KEY,
                state TEXT NOT NULL DEFAULT 'active',
                detected_at REAL NOT NULL,
                settled_at REAL,
                archived_at REAL,
                confirmation_count INTEGER DEFAULT 0,
                disclosure_count INTEGER DEFAULT 0,
                last_mentioned REAL,
                old_value TEXT,
                new_value TEXT,
                freshness_window REAL DEFAULT 604800,
                FOREIGN KEY (ledger_id) REFERENCES contradictions(ledger_id)
            )
        """)
        
        # Index on lifecycle state for efficient filtering
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_contradiction_lifecycle_state
            ON contradiction_lifecycle(state)
        """)

        # Phase G1: Disposition classification columns
        try:
            cursor.execute("ALTER TABLE contradictions ADD COLUMN disposition TEXT")
        except sqlite3.OperationalError:
            pass
        try:
            cursor.execute("ALTER TABLE contradictions ADD COLUMN disposition_confidence REAL DEFAULT 0.0")
        except sqlite3.OperationalError:
            pass
        try:
            cursor.execute("ALTER TABLE contradictions ADD COLUMN disposition_explanation TEXT")
        except sqlite3.OperationalError:
            pass
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_contradictions_disposition "
            "ON contradictions(disposition)"
        )

        conn.commit()
        conn.close()

    def mark_contradiction_asked(self, ledger_id: str) -> None:
        """Record that we asked the user to clarify a contradiction."""
        ts = time.time()
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO contradiction_worklog (ledger_id, first_asked_at, last_asked_at, ask_count)
            VALUES (?, ?, ?, 1)
            ON CONFLICT(ledger_id) DO UPDATE SET
                last_asked_at=excluded.last_asked_at,
                ask_count=coalesce(contradiction_worklog.ask_count, 0) + 1
            """,
            (ledger_id, ts, ts),
        )
        conn.commit()
        conn.close()

    def get_contradiction_for_pair(
        self, old_memory_id: str, new_memory_id: str
    ) -> Optional[str]:
        """Check if a contradiction already exists for this memory pair. Returns ledger_id or None."""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT ledger_id FROM contradictions WHERE old_memory_id = ? AND new_memory_id = ? LIMIT 1",
            (old_memory_id, new_memory_id),
        )
        row = cursor.fetchone()
        conn.close()
        return row[0] if row else None

    def record_contradiction_user_answer(self, ledger_id: str, answer: str) -> None:
        """Record a user answer intended to resolve a contradiction (does not auto-resolve)."""
        ts = time.time()
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO contradiction_worklog (ledger_id, last_user_answer, last_user_answer_at)
            VALUES (?, ?, ?)
            ON CONFLICT(ledger_id) DO UPDATE SET
                last_user_answer=excluded.last_user_answer,
                last_user_answer_at=excluded.last_user_answer_at
            """,
            (ledger_id, (answer or "").strip(), ts),
        )
        conn.commit()
        conn.close()

    def get_resolved_contradictions(self, limit: int = 100) -> List[ContradictionEntry]:
        """Get all resolved contradictions for filtering deprecated values."""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT ledger_id, old_memory_id, new_memory_id, similarity, timestamp, 
                   status, contradiction_type, affects_slots, query, summary,
                   resolution_timestamp, resolution_method, merged_memory_id
            FROM contradictions
            WHERE status = 'resolved'
            ORDER BY resolution_timestamp DESC
            LIMIT ?
        """, (limit,))
        
        rows = cursor.fetchall()
        conn.close()
        
        entries = []
        for row in rows:
            entry = ContradictionEntry(
                ledger_id=row[0],
                old_memory_id=row[1],
                new_memory_id=row[2],
                similarity=row[3],
                timestamp=row[4],
                status=ContradictionStatus(row[5]),
                contradiction_type=ContradictionType(row[6]) if row[6] else ContradictionType.CONFLICT,
                affects_slots=row[7],
                query=row[8],
                summary=row[9]
            )
            # Add resolution metadata
            entry.resolution_timestamp = row[10]
            entry.resolution_method = row[11]
            entry.merged_memory_id = row[12]
            entries.append(entry)
        
        return entries
    
    def get_contradiction_worklog(self, ledger_id: str) -> Dict[str, Optional[object]]:
        """Return worklog fields for a contradiction (or defaults if absent)."""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT first_asked_at, last_asked_at, ask_count, last_user_answer, last_user_answer_at
            FROM contradiction_worklog
            WHERE ledger_id = ?
            """,
            (ledger_id,),
        )
        row = cursor.fetchone()
        conn.close()
        if not row:
            return {
                "first_asked_at": None,
                "last_asked_at": None,
                "ask_count": 0,
                "last_user_answer": None,
                "last_user_answer_at": None,
            }
        return {
            "first_asked_at": row[0],
            "last_asked_at": row[1],
            "ask_count": int(row[2] or 0),
            "last_user_answer": row[3],
            "last_user_answer_at": row[4],
        }
    
    # ========================================================================
    # Contradiction Recording
    # ========================================================================
    
    def _classify_contradiction(
        self,
        old_text: str,
        new_text: str,
        drift_mean: float,
        old_vector: Optional[np.ndarray] = None,
        new_vector: Optional[np.ndarray] = None
    ) -> str:
        """
        Classify contradiction type based on fact topology.
        
        Returns:
            REFINEMENT: New info is more specific (Seattle → Bellevue, Seattle metro → Bellevue)
            REVISION: Explicit correction ("actually", "I meant", "not X")
            TEMPORAL: Progression/upgrade (Senior → Principal)
            CONFLICT: Mutually exclusive (Microsoft vs Amazon)
        """
        old_lower = old_text.lower()
        new_lower = new_text.lower()
        
        # Check for revision keywords
        revision_keywords = ["actually", "correction", "i meant", "not ", "wrong", "mistake"]
        if any(kw in new_lower for kw in revision_keywords):
            return ContradictionType.REVISION
        
        # Check for hierarchical refinement (one contains the other)
        if old_text in new_text or new_text in old_text:
            return ContradictionType.REFINEMENT
        
        # Check for geographic refinement (city → specific neighborhood/suburb)
        # This prevents "Seattle metro → Bellevue" from being treated as a conflict
        old_facts = self._extract_all_facts(old_text) or {}
        new_facts = self._extract_all_facts(new_text) or {}
        
        # Check if location slot is being refined
        if "location" in old_facts and "location" in new_facts:
            old_loc = str(getattr(old_facts.get("location"), "value", "")).lower()
            new_loc = str(getattr(new_facts.get("location"), "value", "")).lower()
            
            # Common refinement patterns
            refinement_patterns = [
                ("seattle metro", "bellevue"),
                ("seattle", "bellevue"),
                ("seattle area", "bellevue"),
                ("bay area", "san francisco"),
                ("bay area", "oakland"),
                ("bay area", "palo alto"),
                ("new york", "brooklyn"),
                ("new york", "manhattan"),
                ("los angeles", "santa monica"),
                ("metro", ""),  # Generic metro → specific city is refinement
            ]
            
            for broad, specific in refinement_patterns:
                if broad in old_loc and specific in new_loc:
                    return ContradictionType.REFINEMENT
            
            # If new location contains qualifier words suggesting refinement
            refinement_qualifiers = ["specifically", "actually in", "more precisely", "in the"]
            if any(q in new_lower for q in refinement_qualifiers):
                return ContradictionType.REFINEMENT
        
        # Enhanced temporal detection
        temporal_markers = [
            "now", "currently", "recently", "just", "switched", "changed",
            "moved", "started", "used to", "no longer", "anymore", "these days",
            "at the moment", "as of", "since then", "after that",
            "promoted", "became", "upgraded"
        ]
        seniority_pairs = [("senior", "principal"), ("junior", "senior"), ("mid", "senior")]
        
        # Check for temporal markers in both old and new text (single iteration)
        if any(marker in new_lower or marker in old_lower for marker in temporal_markers):
            return ContradictionType.TEMPORAL
        
        for lower, higher in seniority_pairs:
            if lower in old_lower and higher in new_lower:
                return ContradictionType.TEMPORAL
        
        # Check semantic similarity if vectors available
        if old_vector is not None and new_vector is not None:
            similarity = self.crt_math.similarity(old_vector, new_vector)
            # High similarity but not identical suggests refinement
            if 0.7 <= similarity < 0.9:
                return ContradictionType.REFINEMENT
        
        # =====================================================================
        # LLM-BASED DRIFT ASSESSMENT (when available)
        # Uses lightweight local LLM for semantic understanding of gradual drift
        # =====================================================================
        drift_assessor = _get_drift_assessor()
        if drift_assessor is not None:
            try:
                from .llm_drift_assessor import DriftType
                assessment = drift_assessor.assess_drift(old_text, new_text)
                if assessment is not None:
                    # Map LLM drift types to contradiction types
                    drift_to_contradiction = {
                        DriftType.CONTRADICTION: ContradictionType.CONFLICT,
                        DriftType.EVOLUTION: ContradictionType.TEMPORAL,
                        DriftType.REFINEMENT: ContradictionType.REFINEMENT,
                        DriftType.CORRECTION: ContradictionType.REVISION,
                        DriftType.TEMPORAL: ContradictionType.TEMPORAL,
                        DriftType.PREFERENCE: ContradictionType.TEMPORAL,  # Preferences evolve
                        DriftType.COMPATIBLE: ContradictionType.REFINEMENT,  # Not a real conflict
                    }
                    mapped_type = drift_to_contradiction.get(
                        assessment.drift_type, 
                        ContradictionType.CONFLICT
                    )
                    # Only use LLM result if confident
                    if assessment.confidence >= 0.6:
                        return mapped_type
            except Exception as e:
                # LLM assessment failed, fall through to default
                pass
        
        # Default to conflict for mutually exclusive facts
        return ContradictionType.CONFLICT
    
    def record_contradiction(
        self,
        old_memory_id: str,
        new_memory_id: str,
        drift_mean: float,
        confidence_delta: float,
        query: Optional[str] = None,
        summary: Optional[str] = None,
        drift_reason: Optional[float] = None,
        old_text: Optional[str] = None,
        new_text: Optional[str] = None,
        old_vector: Optional[np.ndarray] = None,
        new_vector: Optional[np.ndarray] = None,
        contradiction_type: Optional[str] = None,
        suggested_policy: Optional[str] = None,
        thread_id: Optional[str] = None,
    ) -> ContradictionEntry:
        """
        Record contradiction event with classification.
        
        NO DELETION. NO REPLACEMENT.
        Just create ledger entry preserving both memories.
        """
        # Classify the contradiction type (use provided or auto-detect)
        # Try belief classifier first (XGBoost, if trained), fall back to rules
        _belief_classifier_used = False
        if contradiction_type is None and old_text and new_text:
            try:
                import sys, os
                _bc_pkg_dir = os.path.join(os.path.dirname(__file__), "..", "packages", "belief_classifier")
                if _bc_pkg_dir not in sys.path:
                    sys.path.insert(0, _bc_pkg_dir)
                from belief_classifier import ContradictionResolver, ContradictionPair as BCPair
                _bc_model_dir = os.path.join(_bc_pkg_dir, "models")
                _bc_belief_path = os.path.join(_bc_model_dir, "belief_model.pkl")
                _bc_policy_path = os.path.join(_bc_model_dir, "policy_model.pkl")
                if os.path.exists(_bc_belief_path) and os.path.exists(_bc_policy_path):
                    _resolver = ContradictionResolver(
                        belief_model_path=_bc_belief_path,
                        policy_model_path=_bc_policy_path,
                    )
                    if _resolver.is_trained:
                        # Build a ContradictionPair for the classifier
                        _sim = 0.5
                        if old_vector is not None and new_vector is not None:
                            _sim = float(self.crt_math.similarity(old_vector, new_vector))
                        # Extract slot info
                        _old_facts = self._extract_all_facts(old_text) or {}
                        _new_facts = self._extract_all_facts(new_text) or {}
                        _shared = set(_old_facts.keys()) & set(_new_facts.keys())
                        _slot = list(_shared)[0] if _shared else None
                        _bc_pair = BCPair(
                            old_text=old_text,
                            new_text=new_text,
                            old_trust=drift_mean,  # approximate
                            new_trust=max(0.5, drift_mean + confidence_delta),
                            old_timestamp=time.time() - 86400,  # approximate
                            new_timestamp=time.time(),
                            slot_name=_slot,
                            is_exclusive_slot=bool(_slot),
                            similarity_score=_sim,
                            thread_id=thread_id,
                        )
                        _belief, _b_conf, _policy, _p_conf = _resolver.resolve(_bc_pair)
                        # Map belief type to contradiction type
                        _type_map = {
                            "refinement": ContradictionType.REFINEMENT,
                            "revision": ContradictionType.REVISION,
                            "temporal": ContradictionType.TEMPORAL,
                            "conflict": ContradictionType.CONFLICT,
                        }
                        contradiction_type = _type_map.get(str(_belief.value), ContradictionType.CONFLICT)
                        suggested_policy = str(_policy.value)
                        _belief_classifier_used = True
                        _logger.info(
                            "[BELIEF_CLASSIFIER] type=%s (%.2f), policy=%s (%.2f)",
                            _belief.value, _b_conf, _policy.value, _p_conf,
                        )
            except ImportError:
                pass  # belief_classifier package not installed
            except Exception as _bc_err:
                _logger.debug("[BELIEF_CLASSIFIER] Failed (non-fatal): %s", _bc_err)

        if contradiction_type is None:
            if old_text and new_text:
                contradiction_type = self._classify_contradiction(
                    old_text, new_text, drift_mean, old_vector, new_vector
                )
            else:
                contradiction_type = ContradictionType.CONFLICT  # Default

        # Extract affected slots from both memories
        affects_slots_set = set()
        if old_text and new_text:
            old_facts = self._extract_all_facts(old_text) or {}
            new_facts = self._extract_all_facts(new_text) or {}
            # Track slots that appear in both (potential conflicts)
            shared_slots = set(old_facts.keys()) & set(new_facts.keys())
            affects_slots_set.update(shared_slots)
        
        affects_slots_str = ",".join(sorted(affects_slots_set)) if affects_slots_set else None
        
        # Phase G1: Run disposition classifier
        _disp_result = None
        if old_text and new_text:
            _classify_disp = _get_disposition_classifier()
            if _classify_disp is not None:
                try:
                    # Compute similarity if vectors available
                    _sim = 0.5
                    if old_vector is not None and new_vector is not None:
                        _sim = float(self.crt_math.similarity(old_vector, new_vector))
                    # Approximate timestamps — use current time and offset by 1 day
                    _ts_new = time.time()
                    _ts_old = _ts_new - 86400  # approximate
                    _disp_result = _classify_disp(
                        text_a=old_text,
                        text_b=new_text,
                        timestamp_a=_ts_old,
                        timestamp_b=_ts_new,
                        similarity=_sim,
                    )
                    _logger.info(
                        "[DISPOSITION] %s (%.2f) — %s",
                        _disp_result.disposition.value,
                        _disp_result.confidence,
                        _disp_result.explanation,
                    )
                except Exception as _disp_err:
                    _logger.debug("[DISPOSITION] Classification failed (non-fatal): %s", _disp_err)

        # --- Tension type classification (goal formation layer) ---
        _tension_type = None
        _tension_magnitude = 0.0
        try:
            _tension_type, _tension_magnitude = _classify_tension_type(
                old_text=old_text or "",
                new_text=new_text or "",
                contradiction_type=contradiction_type,
                drift_mean=drift_mean,
                confidence_delta=confidence_delta,
            )
            if _tension_type:
                _logger.info(
                    "[TENSION_TYPE] %s (magnitude=%.2f) for %s vs %s",
                    _tension_type, _tension_magnitude,
                    (old_text or "")[:40], (new_text or "")[:40],
                )
        except Exception as _tt_err:
            _logger.debug("[TENSION_TYPE] Classification failed (non-fatal): %s", _tt_err)

        entry = ContradictionEntry(
            ledger_id=f"contra_{int(time.time() * 1000)}_{hash(old_memory_id + new_memory_id) % 10000}",
            timestamp=time.time(),
            old_memory_id=old_memory_id,
            new_memory_id=new_memory_id,
            drift_mean=drift_mean,
            drift_reason=drift_reason,
            confidence_delta=confidence_delta,
            status=ContradictionStatus.OPEN,
            contradiction_type=contradiction_type,
            tension_type=_tension_type,
            tension_magnitude=round(_tension_magnitude, 3),
            affects_slots=affects_slots_str,
            disposition=_disp_result.disposition.value if _disp_result else None,
            disposition_confidence=_disp_result.confidence if _disp_result else 0.0,
            disposition_explanation=_disp_result.explanation if _disp_result else None,
            query=query,
            summary=summary or self._generate_summary(drift_mean, confidence_delta, contradiction_type),
            thread_id=thread_id or self.default_thread_id,
        )

        # Store in database
        conn = self._get_connection()
        cursor = conn.cursor()

        # Store suggested policy in metadata if provided
        metadata = {}
        if suggested_policy:
            metadata['suggested_policy'] = suggested_policy
        if _disp_result:
            metadata['disposition_rule_trace'] = _disp_result.rule_trace

        # Include tension_type in metadata for storage
        if _tension_type:
            metadata['tension_type'] = _tension_type
            metadata['tension_magnitude'] = round(_tension_magnitude, 3)

        cursor.execute("""
            INSERT INTO contradictions
            (ledger_id, timestamp, old_memory_id, new_memory_id, drift_mean,
             drift_reason, confidence_delta, status, contradiction_type, affects_slots,
             query, summary, metadata, thread_id,
             disposition, disposition_confidence, disposition_explanation)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            entry.ledger_id,
            entry.timestamp,
            old_memory_id,
            new_memory_id,
            drift_mean,
            drift_reason,
            confidence_delta,
            entry.status,
            entry.contradiction_type,
            entry.affects_slots,
            query,
            entry.summary,
            json.dumps(metadata) if metadata else None,
            entry.thread_id,
            entry.disposition,
            entry.disposition_confidence,
            entry.disposition_explanation,
        ))
        
        conn.commit()
        conn.close()

        # Sprint 6: Notify slot discovery of the new contradiction (non-blocking)
        if affects_slots_set and summary:
            try:
                from personal_agent.slot_discovery import on_contradiction_recorded as _sd_notify
                _resolution = suggested_policy or "ask_user"
                # Parse old/new values from summary if possible (format: "slot: type - old -> new")
                for _affected_slot in affects_slots_set:
                    _old_v = old_text[:60] if old_text else ""
                    _new_v = new_text[:60] if new_text else ""
                    _sd_notify(_affected_slot, _old_v, _new_v, _resolution)
            except Exception as _sd_err:
                logger.debug(f"[SLOT_DISCOVERY] Failed to notify slot discovery: {_sd_err}")

        return entry

    def create_semantic_anchor(
        self,
        entry: ContradictionEntry,
        old_text: str,
        new_text: str,
        turn_number: int,
        slot_name: Optional[str] = None,
        old_value: Optional[str] = None,
        new_value: Optional[str] = None,
        old_vector: Optional[np.ndarray] = None,
        new_vector: Optional[np.ndarray] = None
    ) -> SemanticAnchor:
        """Create a semantic anchor for this contradiction.
        
        The anchor carries the contradiction context forward for follow-up questions.
        """
        # Extract slot values if not provided
        if slot_name is None or old_value is None or new_value is None:
            old_facts = self._extract_all_facts(old_text) or {}
            new_facts = self._extract_all_facts(new_text) or {}
            shared_slots = set(old_facts.keys()) & set(new_facts.keys())
            
            if shared_slots and slot_name is None:
                # Pick the first shared slot as the primary slot
                slot_name = sorted(shared_slots)[0]
                old_fact = old_facts.get(slot_name)
                new_fact = new_facts.get(slot_name)
                if old_fact and new_fact:
                    old_value = str(old_fact.value)
                    new_value = str(new_fact.value)
        
        # Calculate drift vector if embeddings provided
        drift_vector = None
        if old_vector is not None and new_vector is not None:
            drift_vector = new_vector - old_vector
        
        # Generate clarification prompt based on type
        anchor = SemanticAnchor(
            contradiction_id=entry.ledger_id,
            turn_number=turn_number,
            contradiction_type=entry.contradiction_type,
            old_memory_id=entry.old_memory_id,
            new_memory_id=entry.new_memory_id,
            old_text=old_text,
            new_text=new_text,
            slot_name=slot_name,
            old_value=old_value,
            new_value=new_value,
            drift_vector=drift_vector,
            expected_answer_type=self._determine_expected_answer_type(entry.contradiction_type),
        )
        
        # Generate the clarification prompt
        anchor.clarification_prompt = generate_clarification_prompt(anchor)
        
        return anchor
    
    def _determine_expected_answer_type(self, contradiction_type: str) -> str:
        """Determine what kind of answer we expect based on contradiction type."""
        if contradiction_type == ContradictionType.REFINEMENT:
            return "both_true"  # Both might be valid at different levels of specificity
        elif contradiction_type == ContradictionType.REVISION:
            return "choose_one"  # User correcting themselves
        elif contradiction_type == ContradictionType.TEMPORAL:
            return "temporal_order"  # Progression over time
        else:  # CONFLICT
            return "choose_one"  # Mutually exclusive - pick one
    
    def _generate_summary(self, drift: float, conf_delta: float, contradiction_type: str = ContradictionType.CONFLICT) -> str:
        """Generate natural language summary of contradiction."""
        if drift > 0.5:
            intensity = "Strong"
        elif drift > 0.3:
            intensity = "Moderate"
        else:
            intensity = "Mild"
        
        if conf_delta > 0.3:
            conf_desc = "with significant confidence shift"
        elif conf_delta > 0.1:
            conf_desc = "with moderate confidence shift"
        else:
            conf_desc = ""
        
        type_desc = {
            ContradictionType.REFINEMENT: "Refinement",
            ContradictionType.REVISION: "Revision",
            ContradictionType.TEMPORAL: "Temporal progression",
            ContradictionType.CONFLICT: "Conflict"
        }.get(contradiction_type, "Contradiction")
        
        return f"{type_desc}: {intensity} belief divergence (drift={drift:.2f}) {conf_desc}".strip()
    
    # ========================================================================
    # Contradiction Queries
    # ========================================================================
    
    def get_open_contradictions(
        self,
        limit: int = 10,
        thread_id: Optional[str] = None,
    ) -> List[ContradictionEntry]:
        """Get unresolved contradictions."""
        conn = self._get_connection()
        cursor = conn.cursor()
        effective_thread = thread_id if thread_id is not None else self.default_thread_id
        if effective_thread is not None and self._has_contradiction_thread_column():
            cursor.execute("""
                SELECT * FROM contradictions 
                WHERE status = ?
                  AND COALESCE(contradiction_type, '') != 'profile_update'
                  AND COALESCE(thread_id, 'default') = ?
                ORDER BY timestamp DESC
                LIMIT ?
            """, (ContradictionStatus.OPEN, str(effective_thread), limit))
        else:
            cursor.execute("""
                SELECT * FROM contradictions 
                WHERE status = ?
                  AND COALESCE(contradiction_type, '') != 'profile_update'
                ORDER BY timestamp DESC
                LIMIT ?
            """, (ContradictionStatus.OPEN, limit))
        
        rows = cursor.fetchall()
        conn.close()
        
        return [self._row_to_entry(row) for row in rows]

    def get_all_contradictions(
        self,
        limit: int = 100,
        thread_id: Optional[str] = None,
    ) -> List[ContradictionEntry]:
        """Return all contradictions, newest first, optionally scoped to a thread."""
        conn = self._get_connection()
        cursor = conn.cursor()
        effective_thread = thread_id if thread_id is not None else self.default_thread_id
        if effective_thread is not None and self._has_contradiction_thread_column():
            cursor.execute("""
                SELECT * FROM contradictions
                WHERE COALESCE(thread_id, 'default') = ?
                ORDER BY timestamp DESC
                LIMIT ?
            """, (str(effective_thread), int(limit)))
        else:
            cursor.execute("""
                SELECT * FROM contradictions
                ORDER BY timestamp DESC
                LIMIT ?
            """, (int(limit),))
        rows = cursor.fetchall()
        conn.close()
        return [self._row_to_entry(row) for row in rows]
    
    def get_contradiction_by_memory(self, memory_id: str) -> List[ContradictionEntry]:
        """Get all contradictions involving a memory."""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT * FROM contradictions 
            WHERE old_memory_id = ? OR new_memory_id = ?
            ORDER BY timestamp DESC
        """, (memory_id, memory_id))
        
        rows = cursor.fetchall()
        conn.close()
        
        return [self._row_to_entry(row) for row in rows]
    
    def has_open_contradiction(self, memory_id: str) -> bool:
        """Check if memory has any open contradictions."""
        contradictions = self.get_contradiction_by_memory(memory_id)
        return any(c.status == ContradictionStatus.OPEN for c in contradictions)
    
    # ========================================================================
    # Resolution
    # ========================================================================
    
    def resolve_contradiction(
        self,
        ledger_id: str,
        method: str,
        merged_memory_id: Optional[str] = None,
        new_status: str = ContradictionStatus.RESOLVED
    ):
        """
        Mark contradiction as resolved.
        
        Methods:
        - "reflection_merge": Reflected and merged into new belief
        - "accept_both": Both kept as valid perspectives
        - "deprecate_old": Old memory trust degraded, new preferred
        - "deprecate_new": New memory trust degraded, old preferred
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            UPDATE contradictions
            SET status = ?,
                resolution_timestamp = ?,
                resolution_method = ?,
                merged_memory_id = ?
            WHERE ledger_id = ?
        """, (new_status, time.time(), method, merged_memory_id, ledger_id))
        
        conn.commit()
        conn.close()
    
    # ========================================================================
    # Reflection Queue
    # ========================================================================
    
    def queue_reflection(
        self,
        ledger_id: str,
        volatility: float,
        context: Optional[Dict] = None
    ):
        """
        Queue contradiction for reflection.
        
        Priority based on volatility:
        - High (> 0.7): Immediate
        - Medium (0.4-0.7): Soon
        - Low (< 0.4): Eventually
        """
        if volatility >= 0.7:
            priority = "high"
        elif volatility >= 0.4:
            priority = "medium"
        else:
            priority = "low"
        
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT INTO reflection_queue
            (timestamp, ledger_id, volatility, priority, context_json)
            VALUES (?, ?, ?, ?, ?)
        """, (time.time(), ledger_id, volatility, priority, json.dumps(context) if context else None))
        
        conn.commit()
        conn.close()
    
    def get_reflection_queue(self, priority: Optional[str] = None) -> List[Dict]:
        """Get pending reflections, optionally filtered by priority."""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        if priority:
            cursor.execute("""
                SELECT * FROM reflection_queue
                WHERE processed = 0 AND priority = ?
                ORDER BY volatility DESC, timestamp ASC
            """, (priority,))
        else:
            cursor.execute("""
                SELECT * FROM reflection_queue
                WHERE processed = 0
                ORDER BY 
                    CASE priority
                        WHEN 'high' THEN 1
                        WHEN 'medium' THEN 2
                        WHEN 'low' THEN 3
                    END,
                    volatility DESC,
                    timestamp ASC
            """)
        
        rows = cursor.fetchall()
        conn.close()
        
        return [
            {
                'queue_id': row[0],
                'timestamp': row[1],
                'ledger_id': row[2],
                'volatility': row[3],
                'priority': row[4],
                'context': json.loads(row[5]) if row[5] else None
            }
            for row in rows
        ]
    
    def mark_reflection_processed(self, queue_id: int):
        """Mark reflection as processed."""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute(
            "UPDATE reflection_queue SET processed = 1 WHERE queue_id = ?",
            (queue_id,)
        )
        
        conn.commit()
        conn.close()
    
    # ========================================================================
    # Statistics
    # ========================================================================
    
    def get_contradiction_stats(self, days: int = 7, thread_id: Optional[str] = None) -> Dict:
        """Get contradiction statistics."""
        since = time.time() - (days * 86400)
        effective_thread = thread_id if thread_id is not None else self.default_thread_id
        
        conn = self._get_connection()
        cursor = conn.cursor()
        has_thread = effective_thread is not None and self._has_contradiction_thread_column()
        thread_clause = " AND COALESCE(thread_id, 'default') = ?" if has_thread else ""
        thread_params = (str(effective_thread),) if has_thread else ()
        
        # Total contradictions
        cursor.execute(
            f"SELECT COUNT(*) FROM contradictions WHERE timestamp > ?{thread_clause}",
            (since,) + thread_params
        )
        total = cursor.fetchone()[0]
        
        # By status
        cursor.execute(f"""
            SELECT status, COUNT(*) 
            FROM contradictions 
            WHERE timestamp > ?{thread_clause}
            GROUP BY status
        """, (since,) + thread_params)
        
        by_status = dict(cursor.fetchall())
        
        # Average drift
        cursor.execute(
            f"SELECT AVG(drift_mean) FROM contradictions WHERE timestamp > ?{thread_clause}",
            (since,) + thread_params
        )
        avg_drift = cursor.fetchone()[0] or 0.0
        
        # Pending reflections
        cursor.execute(
            "SELECT COUNT(*) FROM reflection_queue WHERE processed = 0"
        )
        pending_reflections = cursor.fetchone()[0]
        
        conn.close()
        
        return {
            'total_contradictions': total,
            'open': by_status.get(ContradictionStatus.OPEN, 0),
            'resolved': by_status.get(ContradictionStatus.RESOLVED, 0),
            'accepted': by_status.get(ContradictionStatus.ACCEPTED, 0),
            'average_drift': avg_drift,
            'pending_reflections': pending_reflections,
            'days': days
        }
    
    # ========================================================================
    # Helpers
    # ========================================================================
    
    def _row_to_entry(self, row) -> ContradictionEntry:
        """Convert database row to ContradictionEntry."""
        entry = ContradictionEntry(
            ledger_id=row[0],
            timestamp=row[1],
            old_memory_id=row[2],
            new_memory_id=row[3],
            drift_mean=row[4],
            drift_reason=row[5],
            confidence_delta=row[6],
            status=row[7],
            contradiction_type=row[8] if len(row) > 8 else ContradictionType.CONFLICT,
            affects_slots=row[9] if len(row) > 9 else None,
            query=row[10] if len(row) > 10 else (row[9] if len(row) > 9 else row[8]),
            summary=row[11] if len(row) > 11 else (row[10] if len(row) > 10 else row[9]),
            resolution_timestamp=row[12] if len(row) > 12 else (row[11] if len(row) > 11 else row[10]),
            resolution_method=row[13] if len(row) > 13 else (row[12] if len(row) > 12 else row[11]),
            merged_memory_id=row[14] if len(row) > 14 else (row[13] if len(row) > 13 else row[12]),
            thread_id=row[16] if len(row) > 16 else None,
        )
        # Phase G1: disposition columns (24, 25, 26 after migration)
        if len(row) > 24:
            entry.disposition = row[24]
        if len(row) > 25:
            entry.disposition_confidence = row[25] if row[25] is not None else 0.0
        if len(row) > 26:
            entry.disposition_explanation = row[26]
        return entry

    # ========================================================================
    # Metadata Management
    # ========================================================================
    
    def update_contradiction_metadata(
        self,
        ledger_id: str,
        metadata_updates: Dict[str, Any]
    ) -> bool:
        """
        Update metadata for a contradiction (merges with existing metadata).
        
        Args:
            ledger_id: Contradiction ID
            metadata_updates: Dict of metadata fields to update/add
            
        Returns:
            True if update succeeded
        """
        import json
        
        conn = self._get_connection()
        cursor = conn.cursor()
        
        try:
            # Get existing metadata
            cursor.execute(
                "SELECT metadata FROM contradictions WHERE ledger_id = ?",
                (ledger_id,)
            )
            row = cursor.fetchone()
            if not row:
                return False
            
            # Parse existing metadata or start with empty dict
            existing = {}
            if row[0]:
                try:
                    existing = json.loads(row[0])
                except json.JSONDecodeError:
                    existing = {}
            
            # Merge updates
            existing.update(metadata_updates)
            
            # Save back
            cursor.execute(
                "UPDATE contradictions SET metadata = ? WHERE ledger_id = ?",
                (json.dumps(existing), ledger_id)
            )
            conn.commit()
            
            _logger.debug(f"[LEDGER] Updated metadata for {ledger_id}: {list(metadata_updates.keys())}")
            return True
        except Exception as e:
            _logger.warning(f"[LEDGER] Failed to update metadata for {ledger_id}: {e}")
            return False
        finally:
            conn.close()

    # ========================================================================
    # Lifecycle State Management (P0 Fix)
    # ========================================================================
    
    def update_lifecycle_state(
        self,
        ledger_id: str,
        new_state: str,
        confirmation_count: Optional[int] = None,
        disclosure_count: Optional[int] = None
    ) -> bool:
        """
        Update lifecycle state for a contradiction.
        
        Args:
            ledger_id: Contradiction ID
            new_state: New lifecycle state ('active', 'settling', 'settled', 'archived')
            confirmation_count: Optional - update confirmation count
            disclosure_count: Optional - update disclosure count
            
        Returns:
            True if update succeeded
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        
        try:
            # Build dynamic update query
            updates = ["lifecycle_state = ?"]
            params = [new_state]
            
            if confirmation_count is not None:
                updates.append("confirmation_count = ?")
                params.append(confirmation_count)
            
            if disclosure_count is not None:
                updates.append("disclosure_count = ?")
                params.append(disclosure_count)
            
            # Set timestamps based on state
            if new_state == "settled":
                updates.append("settled_at = ?")
                params.append(time.time())
            elif new_state == "archived":
                updates.append("archived_at = ?")
                params.append(time.time())
            
            params.append(ledger_id)
            
            cursor.execute(f"""
                UPDATE contradictions
                SET {', '.join(updates)}
                WHERE ledger_id = ?
            """, params)
            
            conn.commit()
            return cursor.rowcount > 0
        finally:
            conn.close()
    
    def increment_confirmation(self, ledger_id: str) -> int:
        """
        Increment confirmation count for a contradiction.
        
        Called when user repeats/confirms the new fact value.
        
        Returns:
            New confirmation count
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        
        try:
            cursor.execute("""
                UPDATE contradictions
                SET confirmation_count = COALESCE(confirmation_count, 0) + 1
                WHERE ledger_id = ?
            """, (ledger_id,))
            conn.commit()
            
            cursor.execute(
                "SELECT confirmation_count FROM contradictions WHERE ledger_id = ?",
                (ledger_id,)
            )
            row = cursor.fetchone()
            return row[0] if row else 0
        finally:
            conn.close()
    
    def get_lifecycle_info(self, ledger_id: str) -> Optional[Dict[str, Any]]:
        """Get lifecycle information for a contradiction."""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        try:
            cursor.execute("""
                SELECT lifecycle_state, confirmation_count, disclosure_count,
                       settled_at, archived_at, timestamp
                FROM contradictions
                WHERE ledger_id = ?
            """, (ledger_id,))
            
            row = cursor.fetchone()
            if not row:
                return None
            
            return {
                "lifecycle_state": row[0] or "active",
                "confirmation_count": row[1] or 0,
                "disclosure_count": row[2] or 0,
                "settled_at": row[3],
                "archived_at": row[4],
                "detected_at": row[5],
            }
        finally:
            conn.close()
    
    def process_lifecycle_transitions(self) -> Dict[str, int]:
        """
        Process all open contradictions and update their lifecycle states.
        
        Called periodically or on query to move contradictions through:
        ACTIVE → SETTLING → SETTLED → ARCHIVED
        
        Returns:
            Dict with counts of transitions made
        """
        from .contradiction_lifecycle import ContradictionLifecycle, ContradictionLifecycleState, ContradictionLifecycleEntry
        
        transitions = {"active_to_settling": 0, "settling_to_settled": 0, "settled_to_archived": 0}
        lifecycle = ContradictionLifecycle()
        
        conn = self._get_connection()
        cursor = conn.cursor()
        
        try:
            # Get all non-archived contradictions
            cursor.execute("""
                SELECT ledger_id, lifecycle_state, confirmation_count, timestamp
                FROM contradictions
                WHERE lifecycle_state IS NULL 
                   OR lifecycle_state NOT IN ('archived')
            """)
            
            rows = cursor.fetchall()
            
            for row in rows:
                ledger_id, current_state, confirmation_count, detected_at = row
                current_state = current_state or "active"
                
                # Create lifecycle entry for evaluation
                entry = ContradictionLifecycleEntry(
                    ledger_id=ledger_id,
                    state=ContradictionLifecycleState(current_state),
                    detected_at=detected_at,
                    confirmation_count=confirmation_count or 0
                )
                
                # Check for state transition
                new_state = lifecycle.update_state(entry)
                
                if new_state.value != current_state:
                    # Transition occurred - update database
                    self.update_lifecycle_state(ledger_id, new_state.value)
                    
                    # Track transition type
                    if current_state == "active" and new_state == ContradictionLifecycleState.SETTLING:
                        transitions["active_to_settling"] += 1
                    elif current_state == "settling" and new_state == ContradictionLifecycleState.SETTLED:
                        transitions["settling_to_settled"] += 1
                    elif current_state == "settled" and new_state == ContradictionLifecycleState.ARCHIVED:
                        transitions["settled_to_archived"] += 1
            
            return transitions
        finally:
            conn.close()
