"""
CRT Memory System - Trust-Weighted Memory with Belief/Speech Separation

Implements:
- Memory items with trust and confidence scores
- Source tracking (user/system/fallback/reflection)
- SSE mode tracking (L/C/H)
- Trust-weighted retrieval
- Belief vs speech separation
- No silent overwrites

Philosophy:
- Confidence: "how certain it sounded at creation"
- Trust: "how stable/validated it has proven over time"
- Fallback can speak, but creates low-trust memories
- Only reflection merges conflicting beliefs
"""

import sqlite3
import json
import numpy as np
from typing import List, Dict, Optional, Any, Tuple
from datetime import datetime
from dataclasses import dataclass, asdict
import time

from .crt_core import (
    CRTMath, CRTConfig, SSEMode, MemorySource,
    encode_vector, extract_emotion_intensity, extract_future_relevance
)


@dataclass
class MemoryItem:
    """
    A single memory item in CRT.
    
    Stores:
    - Semantic vector (meaning signature)
    - Trust score (evolves over time)
    - Confidence score (fixed at creation)
    - Source (user/system/fallback/etc)
    - SSE mode (L/C/H)
    - Metadata
    """
    memory_id: str
    vector: np.ndarray         # Semantic encoding
    text: str                  # Original text (if SSE-L) or summary (if SSE-C/H)
    timestamp: float           # Unix timestamp
    confidence: float          # [0,1] How certain at creation
    trust: float               # [0,1] How validated over time
    source: MemorySource       # Where it came from
    sse_mode: SSEMode          # Compression mode
    
    # Optional metadata
    context: Optional[Dict] = None
    tags: Optional[List[str]] = None
    thread_id: Optional[str] = None
    
    def to_dict(self) -> Dict:
        """Convert to dictionary (for storage)."""
        return {
            'memory_id': self.memory_id,
            'vector': self.vector.tolist(),
            'text': self.text,
            'timestamp': self.timestamp,
            'confidence': self.confidence,
            'trust': self.trust,
            'source': self.source.value,
            'sse_mode': self.sse_mode.value,
            'context': self.context,
            'tags': self.tags,
            'thread_id': self.thread_id
        }
    
    @staticmethod
    def from_dict(data: Dict) -> 'MemoryItem':
        """Load from dictionary."""
        return MemoryItem(
            memory_id=data['memory_id'],
            vector=np.array(data['vector']),
            text=data['text'],
            timestamp=data['timestamp'],
            confidence=data['confidence'],
            trust=data['trust'],
            source=MemorySource(data['source']),
            sse_mode=SSEMode(data['sse_mode']),
            context=data.get('context'),
            tags=data.get('tags'),
            thread_id=data.get('thread_id')
        )


class CRTMemorySystem:
    """
    CRT-compliant memory system.
    
    Features:
    - Trust-weighted storage and retrieval
    - Belief vs speech separation
    - No silent overwrites (contradictions create ledger entries)
    - SSE mode selection based on significance
    - Trust evolution over time
    """
    
    def __init__(
        self,
        db_path: str = "personal_agent/crt_memory.db",
        config: Optional[CRTConfig] = None
    ):
        """Initialize CRT memory system."""
        self.db_path = db_path
        self.config = config or CRTConfig()
        self.crt_math = CRTMath(self.config)
        
        # Initialize database
        self._init_db()
    
    def _init_db(self):
        """Initialize database tables."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Memory items table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS memories (
                memory_id TEXT PRIMARY KEY,
                vector_json TEXT NOT NULL,
                text TEXT NOT NULL,
                timestamp REAL NOT NULL,
                confidence REAL NOT NULL,
                trust REAL NOT NULL,
                source TEXT NOT NULL,
                sse_mode TEXT NOT NULL,
                context_json TEXT,
                tags_json TEXT,
                thread_id TEXT
            )
        """)
        
        # Trust evolution log
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS trust_log (
                log_id INTEGER PRIMARY KEY AUTOINCREMENT,
                memory_id TEXT NOT NULL,
                timestamp REAL NOT NULL,
                old_trust REAL NOT NULL,
                new_trust REAL NOT NULL,
                reason TEXT NOT NULL,
                drift REAL,
                FOREIGN KEY (memory_id) REFERENCES memories(memory_id)
            )
        """)
        
        # Belief vs speech tracking
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS belief_speech (
                entry_id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp REAL NOT NULL,
                query TEXT NOT NULL,
                response TEXT NOT NULL,
                is_belief INTEGER NOT NULL,
                memory_ids_json TEXT,
                trust_avg REAL,
                source TEXT
            )
        """)
        
        conn.commit()
        conn.close()
    
    # ========================================================================
    # Memory Storage
    # ========================================================================
    
    def store_memory(
        self,
        text: str,
        confidence: float,
        source: MemorySource,
        context: Optional[Dict] = None,
        user_marked_important: bool = False,
        contradiction_signal: float = 0.0
    ) -> MemoryItem:
        """
        Store new memory with CRT principles.
        
        Process:
        1. Encode to vector
        2. Compute significance → select SSE mode
        3. Assign initial trust (based on source)
        4. Store with metadata
        """
        # Encode
        vector = encode_vector(text)
        
        # Compute significance for SSE mode selection
        all_vectors = self._get_all_vectors()
        novelty = self.crt_math.novelty(vector, all_vectors)
        emotion = extract_emotion_intensity(text)
        future = extract_future_relevance(text)
        user_mark = 1.0 if user_marked_important else 0.0
        
        significance = self.crt_math.compute_significance(
            emotion_intensity=emotion,
            novelty=novelty,
            user_marked=user_mark,
            contradiction_signal=contradiction_signal,
            future_relevance=future
        )
        
        sse_mode = self.crt_math.select_sse_mode(significance)
        
        # Initial trust (based on source and significance)
        if source == MemorySource.FALLBACK:
            trust = min(self.config.tau_base * 0.6, self.config.tau_fallback_cap)
        elif source == MemorySource.REFLECTION:
            trust = self.config.tau_base * 1.2  # Reflection gets higher initial trust
        else:
            trust = self.config.tau_base
        
        trust = np.clip(trust, 0.0, 1.0)
        
        # Create memory item
        memory = MemoryItem(
            memory_id=f"mem_{int(time.time() * 1000)}_{hash(text) % 10000}",
            vector=vector,
            text=text,
            timestamp=time.time(),
            confidence=confidence,
            trust=trust,
            source=source,
            sse_mode=sse_mode,
            context=context
        )
        
        # Store in database
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT INTO memories 
            (memory_id, vector_json, text, timestamp, confidence, trust, source, sse_mode, context_json)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            memory.memory_id,
            json.dumps(vector.tolist()),
            text,
            memory.timestamp,
            confidence,
            trust,
            source.value,
            sse_mode.value,
            json.dumps(context) if context else None
        ))
        
        conn.commit()
        conn.close()
        
        return memory
    
    # ========================================================================
    # Trust-Weighted Retrieval
    # ========================================================================
    
    def retrieve_memories(
        self,
        query: str,
        k: int = 5,
        min_trust: float = 0.0
    ) -> List[Tuple[MemoryItem, float]]:
        """
        Retrieve memories using trust-weighted scoring.
        
        Scoring: R_i = s_i · ρ_i · w_i
        where:
        - s_i = similarity to query
        - ρ_i = recency weight
        - w_i = belief weight (α·trust + (1-α)·confidence)
        
        Returns list of (memory, score) tuples.
        """
        query_vector = encode_vector(query)
        
        # Load all memories
        memories = self._load_all_memories()
        
        # Filter by minimum trust
        memories = [m for m in memories if m.trust >= min_trust]
        
        if not memories:
            return []
        
        # Compute scores
        t_now = time.time()
        memory_dicts = [
            {
                'vector': m.vector,
                'timestamp': m.timestamp,
                'trust': m.trust,
                'confidence': m.confidence
            }
            for m in memories
        ]
        
        scores = self.crt_math.compute_retrieval_scores(
            query_vector=query_vector,
            memories=memory_dicts,
            t_now=t_now
        )
        
        # Return top k
        top_k = scores[:k]
        return [(memories[idx], score) for idx, score in top_k]
    
    def get_best_prior_belief(self, query: str) -> Optional[MemoryItem]:
        """
        Get the strongest prior belief for a query.
        
        Returns memory with highest retrieval score.
        """
        results = self.retrieve_memories(query, k=1)
        return results[0][0] if results else None
    
    # ========================================================================
    # Trust Evolution
    # ========================================================================
    
    def update_trust(
        self,
        memory_id: str,
        new_trust: float,
        reason: str,
        drift: Optional[float] = None
    ):
        """Update trust score and log the change."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Get current trust
        cursor.execute("SELECT trust FROM memories WHERE memory_id = ?", (memory_id,))
        row = cursor.fetchone()
        if not row:
            conn.close()
            return
        
        old_trust = row[0]
        
        # Update trust
        cursor.execute(
            "UPDATE memories SET trust = ? WHERE memory_id = ?",
            (new_trust, memory_id)
        )
        
        # Log change
        cursor.execute("""
            INSERT INTO trust_log (memory_id, timestamp, old_trust, new_trust, reason, drift)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (memory_id, time.time(), old_trust, new_trust, reason, drift))
        
        conn.commit()
        conn.close()
    
    def evolve_trust_for_alignment(
        self,
        memory: MemoryItem,
        new_output_vector: np.ndarray
    ):
        """
        Evolve trust when new output aligns with memory.
        
        Uses: τ_new = clip(τ + η_pos·(1 - D_mean), 0, 1)
        
        This is called when gates pass, meaning the retrieved memory
        was useful and led to a coherent response. We reward it.
        """
        drift = self.crt_math.drift_meaning(new_output_vector, memory.vector)
        
        # Always evolve trust when this is called (gates already passed)
        # The drift just modulates HOW MUCH we increase trust
        new_trust = self.crt_math.evolve_trust_aligned(memory.trust, drift)
        self.update_trust(
            memory.memory_id,
            new_trust,
            f"Aligned (drift={drift:.3f})",
            drift
        )
    
    def evolve_trust_for_contradiction(
        self,
        memory: MemoryItem,
        new_output_vector: np.ndarray
    ):
        """
        Degrade trust when contradiction detected.
        
        Uses: τ_new = clip(τ · (1 - η_neg·D_mean), 0, 1)
        """
        drift = self.crt_math.drift_meaning(new_output_vector, memory.vector)
        new_trust = self.crt_math.evolve_trust_contradicted(memory.trust, drift)
        
        self.update_trust(
            memory.memory_id,
            new_trust,
            f"Contradicted (drift={drift:.3f})",
            drift
        )
    
    # ========================================================================
    # Belief vs Speech Separation
    # ========================================================================
    
    def record_belief(
        self,
        query: str,
        response: str,
        memory_ids: List[str],
        avg_trust: float
    ):
        """
        Record response as belief (high trust).
        
        Only responses passing reconstruction gates become beliefs.
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT INTO belief_speech 
            (timestamp, query, response, is_belief, memory_ids_json, trust_avg, source)
            VALUES (?, ?, ?, 1, ?, ?, 'belief')
        """, (time.time(), query, response, json.dumps(memory_ids), avg_trust))
        
        conn.commit()
        conn.close()
    
    def record_speech(
        self,
        query: str,
        response: str,
        source: str = "fallback"
    ):
        """
        Record response as speech (low trust fallback).
        
        Speech can be shown to user but doesn't update beliefs.
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT INTO belief_speech 
            (timestamp, query, response, is_belief, memory_ids_json, trust_avg, source)
            VALUES (?, ?, ?, 0, NULL, NULL, ?)
        """, (time.time(), query, response, source))
        
        conn.commit()
        conn.close()
    
    # ========================================================================
    # Helpers
    # ========================================================================
    
    def _load_all_memories(self) -> List[MemoryItem]:
        """Load all memories from database."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("SELECT * FROM memories")
        rows = cursor.fetchall()
        conn.close()
        
        memories = []
        for row in rows:
            memories.append(MemoryItem(
                memory_id=row[0],
                vector=np.array(json.loads(row[1])),
                text=row[2],
                timestamp=row[3],
                confidence=row[4],
                trust=row[5],
                source=MemorySource(row[6]),
                sse_mode=SSEMode(row[7]),
                context=json.loads(row[8]) if row[8] else None,
                tags=json.loads(row[9]) if row[9] else None,
                thread_id=row[10]
            ))
        
        return memories
    
    def _get_all_vectors(self) -> List[np.ndarray]:
        """Get all memory vectors."""
        memories = self._load_all_memories()
        return [m.vector for m in memories]

    def get_memory_by_id(self, memory_id: str) -> Optional[MemoryItem]:
        """Fetch a single memory by ID (or None if missing)."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("SELECT * FROM memories WHERE memory_id = ?", (memory_id,))
        row = cursor.fetchone()
        conn.close()

        if not row:
            return None

        return MemoryItem(
            memory_id=row[0],
            vector=np.array(json.loads(row[1])),
            text=row[2],
            timestamp=row[3],
            confidence=row[4],
            trust=row[5],
            source=MemorySource(row[6]),
            sse_mode=SSEMode(row[7]),
            context=json.loads(row[8]) if row[8] else None,
            tags=json.loads(row[9]) if row[9] else None,
            thread_id=row[10]
        )
    
    def get_trust_history(self, memory_id: str) -> List[Dict]:
        """Get trust evolution history for a memory."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT timestamp, old_trust, new_trust, reason, drift
            FROM trust_log
            WHERE memory_id = ?
            ORDER BY timestamp DESC
        """, (memory_id,))
        
        rows = cursor.fetchall()
        conn.close()
        
        return [
            {
                'timestamp': row[0],
                'old_trust': row[1],
                'new_trust': row[2],
                'reason': row[3],
                'drift': row[4]
            }
            for row in rows
        ]
    
    def get_belief_speech_ratio(self, limit: int = 100) -> Dict[str, float]:
        """Get ratio of belief vs speech responses."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT is_belief, COUNT(*) 
            FROM belief_speech 
            WHERE timestamp > ?
            GROUP BY is_belief
        """, (time.time() - 86400 * 7,))  # Last 7 days
        
        rows = cursor.fetchall()
        conn.close()
        
        belief_count = 0
        speech_count = 0
        
        for is_belief, count in rows:
            if is_belief:
                belief_count = count
            else:
                speech_count = count
        
        total = belief_count + speech_count
        if total == 0:
            return {'belief_ratio': 0.0, 'speech_ratio': 0.0}
        
        return {
            'belief_ratio': belief_count / total,
            'speech_ratio': speech_count / total,
            'belief_count': belief_count,
            'speech_count': speech_count
        }
