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
import numpy as np
from typing import List, Dict, Optional, Tuple
from datetime import datetime
from dataclasses import dataclass
import time

from .crt_core import CRTMath, CRTConfig, MemorySource
from .fact_slots import extract_fact_slots
from .crt_semantic_anchor import (
    SemanticAnchor,
    generate_clarification_prompt,
    parse_user_answer,
    is_resolution_grounded,
)


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
    
    # Metadata
    query: Optional[str] = None
    summary: Optional[str] = None
    resolution_timestamp: Optional[float] = None
    resolution_method: Optional[str] = None
    merged_memory_id: Optional[str] = None
    
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
            'query': self.query,
            'summary': self.summary,
            'resolution_timestamp': self.resolution_timestamp,
            'resolution_method': self.resolution_method,
            'merged_memory_id': self.merged_memory_id
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
        db_path: str = "personal_agent/crt_ledger.db",
        config: Optional[CRTConfig] = None
    ):
        """Initialize ledger."""
        self.db_path = db_path
        self.config = config or CRTConfig()
        self.crt_math = CRTMath(self.config)
        
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
                metadata TEXT
            )
        """)
        
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
        old_facts = extract_fact_slots(old_text) or {}
        new_facts = extract_fact_slots(new_text) or {}
        
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
        
        # Check for temporal progression keywords
        temporal_keywords = ["now", "currently", "promoted", "became", "upgraded"]
        seniority_pairs = [("senior", "principal"), ("junior", "senior"), ("mid", "senior")]
        
        if any(kw in new_lower for kw in temporal_keywords):
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
        suggested_policy: Optional[str] = None
    ) -> ContradictionEntry:
        """
        Record contradiction event with classification.
        
        NO DELETION. NO REPLACEMENT.
        Just create ledger entry preserving both memories.
        """
        # Classify the contradiction type (use provided or auto-detect)
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
            old_facts = extract_fact_slots(old_text) or {}
            new_facts = extract_fact_slots(new_text) or {}
            # Track slots that appear in both (potential conflicts)
            shared_slots = set(old_facts.keys()) & set(new_facts.keys())
            affects_slots_set.update(shared_slots)
        
        affects_slots_str = ",".join(sorted(affects_slots_set)) if affects_slots_set else None
        
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
            affects_slots=affects_slots_str,
            query=query,
            summary=summary or self._generate_summary(drift_mean, confidence_delta, contradiction_type)
        )
        
        # Store in database
        conn = self._get_connection()
        cursor = conn.cursor()
        
        # Store suggested policy in metadata if provided
        metadata = {}
        if suggested_policy:
            metadata['suggested_policy'] = suggested_policy
        
        cursor.execute("""
            INSERT INTO contradictions
            (ledger_id, timestamp, old_memory_id, new_memory_id, drift_mean, 
             drift_reason, confidence_delta, status, contradiction_type, affects_slots, query, summary, metadata)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
            json.dumps(metadata) if metadata else None
        ))
        
        conn.commit()
        conn.close()
        
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
            old_facts = extract_fact_slots(old_text) or {}
            new_facts = extract_fact_slots(new_text) or {}
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
    
    def get_open_contradictions(self, limit: int = 10) -> List[ContradictionEntry]:
        """Get unresolved contradictions."""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT * FROM contradictions 
            WHERE status = ?
            ORDER BY timestamp DESC
            LIMIT ?
        """, (ContradictionStatus.OPEN, limit))
        
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
    
    def get_contradiction_stats(self, days: int = 7) -> Dict:
        """Get contradiction statistics."""
        since = time.time() - (days * 86400)
        
        conn = self._get_connection()
        cursor = conn.cursor()
        
        # Total contradictions
        cursor.execute(
            "SELECT COUNT(*) FROM contradictions WHERE timestamp > ?",
            (since,)
        )
        total = cursor.fetchone()[0]
        
        # By status
        cursor.execute("""
            SELECT status, COUNT(*) 
            FROM contradictions 
            WHERE timestamp > ?
            GROUP BY status
        """, (since,))
        
        by_status = dict(cursor.fetchall())
        
        # Average drift
        cursor.execute(
            "SELECT AVG(drift_mean) FROM contradictions WHERE timestamp > ?",
            (since,)
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
        return ContradictionEntry(
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
            merged_memory_id=row[14] if len(row) > 14 else (row[13] if len(row) > 13 else row[12])
        )
