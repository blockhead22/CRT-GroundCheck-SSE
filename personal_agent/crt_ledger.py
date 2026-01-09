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


class ContradictionStatus:
    """Status of contradiction resolution."""
    OPEN = "open"              # Unresolved tension
    REFLECTING = "reflecting"  # Reflection in progress
    RESOLVED = "resolved"      # Merged via reflection
    ACCEPTED = "accepted"      # Both kept as valid perspectives


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
    
    def _init_db(self):
        """Initialize database."""
        conn = sqlite3.connect(self.db_path)
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
                query TEXT,
                summary TEXT,
                resolution_timestamp REAL,
                resolution_method TEXT,
                merged_memory_id TEXT
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
        
        conn.commit()
        conn.close()
    
    # ========================================================================
    # Contradiction Recording
    # ========================================================================
    
    def record_contradiction(
        self,
        old_memory_id: str,
        new_memory_id: str,
        drift_mean: float,
        confidence_delta: float,
        query: Optional[str] = None,
        summary: Optional[str] = None,
        drift_reason: Optional[float] = None
    ) -> ContradictionEntry:
        """
        Record contradiction event.
        
        NO DELETION. NO REPLACEMENT.
        Just create ledger entry preserving both memories.
        """
        entry = ContradictionEntry(
            ledger_id=f"contra_{int(time.time() * 1000)}_{hash(old_memory_id + new_memory_id) % 10000}",
            timestamp=time.time(),
            old_memory_id=old_memory_id,
            new_memory_id=new_memory_id,
            drift_mean=drift_mean,
            drift_reason=drift_reason,
            confidence_delta=confidence_delta,
            status=ContradictionStatus.OPEN,
            query=query,
            summary=summary or self._generate_summary(drift_mean, confidence_delta)
        )
        
        # Store in database
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT INTO contradictions
            (ledger_id, timestamp, old_memory_id, new_memory_id, drift_mean, 
             drift_reason, confidence_delta, status, query, summary)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            entry.ledger_id,
            entry.timestamp,
            old_memory_id,
            new_memory_id,
            drift_mean,
            drift_reason,
            confidence_delta,
            entry.status,
            query,
            entry.summary
        ))
        
        conn.commit()
        conn.close()
        
        return entry
    
    def _generate_summary(self, drift: float, conf_delta: float) -> str:
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
        
        return f"{intensity} belief divergence (drift={drift:.2f}) {conf_desc}".strip()
    
    # ========================================================================
    # Contradiction Queries
    # ========================================================================
    
    def get_open_contradictions(self, limit: int = 10) -> List[ContradictionEntry]:
        """Get unresolved contradictions."""
        conn = sqlite3.connect(self.db_path)
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
        conn = sqlite3.connect(self.db_path)
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
        conn = sqlite3.connect(self.db_path)
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
        
        conn = sqlite3.connect(self.db_path)
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
        conn = sqlite3.connect(self.db_path)
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
        conn = sqlite3.connect(self.db_path)
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
        
        conn = sqlite3.connect(self.db_path)
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
            query=row[8],
            summary=row[9],
            resolution_timestamp=row[10],
            resolution_method=row[11],
            merged_memory_id=row[12]
        )
