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
import logging
import numpy as np
from typing import List, Dict, Optional, Any, Tuple, Set
from datetime import datetime
from dataclasses import dataclass, asdict
import time

from .crt_core import (
    CRTMath, CRTConfig, SSEMode, MemorySource,
    encode_vector, extract_emotion_intensity, extract_future_relevance
)
from .policy import validate_external_memory_context

logger = logging.getLogger(__name__)


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
    deprecated: bool = False
    deprecation_reason: Optional[str] = None
    
    # Two-tier fact extraction (Sprint 1)
    fact_tuples: Optional[str] = None  # JSON-serialized list of FactTuple objects
    extraction_method: Optional[str] = 'regex'  # 'regex', 'llm', or 'none'
    
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
    
    # Contested memory trust cap multiplier (90% reduction)
    CONTESTED_TRUST_MULTIPLIER = 0.1
    
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
        """Initialize database tables."""
        conn = self._get_connection()
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
                thread_id TEXT,
                deprecated INTEGER DEFAULT 0,
                deprecation_reason TEXT
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
        
        # Performance indexes - avoid full table scans
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_memories_source 
            ON memories(source)
        """)
        
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_memories_timestamp 
            ON memories(timestamp DESC)
        """)
        
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_memories_thread 
            ON memories(thread_id)
        """)
        
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_trust_log_memory 
            ON trust_log(memory_id, timestamp)
        """)
        
        # Index for deprecated column (for filtering)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_memories_deprecated
            ON memories(deprecated)
        """)
        
        conn.commit()
        conn.close()
        
        # Migrate existing databases to add deprecated columns if needed
        self._migrate_schema()
    
    def _migrate_schema(self):
        """
        Add deprecated columns to existing memory databases.
        This migration is safe to run multiple times.
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        
        # Check if columns exist
        cursor.execute("PRAGMA table_info(memories)")
        columns = [row[1] for row in cursor.fetchall()]
        
        if "deprecated" not in columns:
            logger.info(f"[MIGRATION] Adding deprecated column to {self.db_path}")
            cursor.execute("ALTER TABLE memories ADD COLUMN deprecated INTEGER DEFAULT 0")
        
        if "deprecation_reason" not in columns:
            logger.info(f"[MIGRATION] Adding deprecation_reason column to {self.db_path}")
            cursor.execute("ALTER TABLE memories ADD COLUMN deprecation_reason TEXT")
        
        # Sprint 1: Add two-tier fact extraction columns
        if "fact_tuples" not in columns:
            logger.info(f"[MIGRATION] Adding fact_tuples column to {self.db_path}")
            cursor.execute("ALTER TABLE memories ADD COLUMN fact_tuples TEXT")
        
        if "extraction_method" not in columns:
            logger.info(f"[MIGRATION] Adding extraction_method column to {self.db_path}")
            cursor.execute("ALTER TABLE memories ADD COLUMN extraction_method TEXT DEFAULT 'regex'")
            # Add index for performance
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_memories_extraction_method ON memories(extraction_method)")
        
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
        # Policy boundary: external/tool memories must be auditable.
        if source == MemorySource.EXTERNAL:
            validate_external_memory_context(context)

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
        
        # Sprint 1: Extract facts using two-tier system
        fact_tuples_json = None
        extraction_method = 'none'
        
        try:
            from .two_tier_facts import TwoTierFactSystem
            
            # Extract facts using two-tier system
            extractor = TwoTierFactSystem()
            fact_data = extractor.extract_facts(text)
            
            # Determine extraction method based on what was used
            # Note: Hard facts are already extracted and stored separately in the ledger/fact system
            # We store open_tuples here because they represent flexible, LLM-extracted facts
            # that complement the deterministic hard slots
            if fact_data.hard_facts and fact_data.open_tuples:
                extraction_method = 'hybrid'  # Both methods used
            elif fact_data.hard_facts:
                extraction_method = 'regex'
            elif fact_data.open_tuples:
                extraction_method = 'llm'
            
            # Serialize open tuples to JSON
            # Hard facts are handled by the existing fact_slots system and ledger
            if fact_data.open_tuples:
                fact_tuples_json = json.dumps([t.to_dict() for t in fact_data.open_tuples])
                
            logger.debug(f"[TWO_TIER] Extracted facts: method={extraction_method}, "
                        f"hard_facts={len(fact_data.hard_facts)}, open_tuples={len(fact_data.open_tuples)}")
        except Exception as e:
            logger.warning(f"[TWO_TIER] Failed to extract facts: {e}")
            extraction_method = 'none'
        
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
            context=context,
            fact_tuples=fact_tuples_json,
            extraction_method=extraction_method
        )
        
        # Store in database
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT INTO memories 
            (memory_id, vector_json, text, timestamp, confidence, trust, source, sse_mode, context_json, fact_tuples, extraction_method)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            memory.memory_id,
            json.dumps(vector.tolist()),
            text,
            memory.timestamp,
            confidence,
            trust,
            source.value,
            sse_mode.value,
            json.dumps(context) if context else None,
            fact_tuples_json,
            extraction_method
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
        min_trust: float = 0.0,
        exclude_deprecated: bool = True,
        ledger = None,
        excluded_ids: Optional[Set[str]] = None
    ) -> List[Tuple[MemoryItem, float]]:
        """
        Retrieve memories using trust-weighted scoring.
        
        Scoring: R_i = s_i · ρ_i · w_i
        where:
        - s_i = similarity to query
        - ρ_i = recency weight
        - w_i = belief weight (α·trust + (1-α)·confidence)
        
        Args:
            exclude_deprecated: If True, filter out memories that are old values from resolved contradictions
            ledger: CRT ledger instance for checking resolved contradictions
            excluded_ids: Additional memory IDs to exclude from retrieval
        
        Returns list of (memory, score) tuples.
        """
        query_vector = encode_vector(query)
        
        # Load all memories
        memories = self._load_all_memories()
        
        # Build set of IDs to exclude
        deprecated_ids = set()
        
        # Filter memories marked as deprecated in the database
        if exclude_deprecated:
            memories = [m for m in memories if not getattr(m, 'deprecated', False)]
        
        # Filter deprecated contradiction sources (SSE invariant: no truth reintroduction)
        if exclude_deprecated and ledger is not None:
            try:
                from .crt_ledger import ContradictionStatus
                resolved = ledger.get_resolved_contradictions(limit=500)
                # Collect old_memory_ids from resolved contradictions that were "replaced"
                for contra in resolved:
                    # Only exclude if resolution method indicates replacement
                    method = getattr(contra, 'resolution_method', None)
                    if method and (('clarif' in method.lower()) or ('replace' in method.lower())):
                        deprecated_ids.add(contra.old_memory_id)
            except Exception:
                # Graceful degradation if ledger unavailable
                pass
        
        # Add any additional excluded IDs
        if excluded_ids:
            deprecated_ids.update(excluded_ids)
        
        # Filter out deprecated and excluded memories
        if deprecated_ids:
            memories = [m for m in memories if m.memory_id not in deprecated_ids]
        
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
    
    def is_memory_contested(self, memory_id: str) -> bool:
        """
        Check if a memory is referenced in an open contradiction.
        
        Args:
            memory_id: Memory ID to check
            
        Returns:
            bool: True if memory is in an open contradiction
        """
        # Import here to avoid circular dependency
        from pathlib import Path
        
        # Derive ledger database path from memory database path
        # Replace 'crt_memory' with 'crt_ledger' to get corresponding ledger DB
        ledger_db = Path(self.db_path.replace('crt_memory', 'crt_ledger'))
        
        if not ledger_db.exists():
            return False
        
        conn = sqlite3.connect(str(ledger_db), timeout=30.0)
        conn.execute("PRAGMA busy_timeout=30000")
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT ledger_id FROM contradictions 
            WHERE (old_memory_id = ? OR new_memory_id = ?)
            AND status = 'open'
        """, (memory_id, memory_id))
        
        result = cursor.fetchone()
        conn.close()
        
        return result is not None
    
    def update_trust(
        self,
        memory_id: str,
        new_trust: float,
        reason: str,
        drift: Optional[float] = None
    ):
        """Update trust score and log the change."""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        # Get current trust
        cursor.execute("SELECT trust FROM memories WHERE memory_id = ?", (memory_id,))
        row = cursor.fetchone()
        if not row:
            conn.close()
            return
        
        old_trust = row[0]
        
        # Check if memory is contested (in open contradiction)
        # If so, apply contested multiplier to cap trust updates
        is_contested = self.is_memory_contested(memory_id)
        actual_new_trust = new_trust
        
        if is_contested:
            # Calculate the delta from current trust
            delta = new_trust - old_trust
            
            # Apply contested multiplier (reduce updates by 90%)
            capped_delta = delta * self.CONTESTED_TRUST_MULTIPLIER
            actual_new_trust = old_trust + capped_delta
            
            # Ensure within bounds
            actual_new_trust = max(0.0, min(1.0, actual_new_trust))
            
            logger.info(f"[CONTESTED] Memory {memory_id} is in open contradiction")
            logger.info(f"[CONTESTED] Trust update capped: Δ{delta:.3f} → Δ{capped_delta:.3f}")
            
            # Log contested event
            cursor.execute("""
                INSERT INTO trust_log (memory_id, timestamp, old_trust, new_trust, reason, drift)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                memory_id, 
                time.time(), 
                old_trust, 
                actual_new_trust, 
                f"contested_cap_applied: {reason}", 
                drift
            ))
        
        # Update trust
        cursor.execute(
            "UPDATE memories SET trust = ? WHERE memory_id = ?",
            (actual_new_trust, memory_id)
        )
        
        # Log change (if not already logged above for contested case)
        if not is_contested:
            cursor.execute("""
                INSERT INTO trust_log (memory_id, timestamp, old_trust, new_trust, reason, drift)
            VALUES (?, ?, ?, ?, ?, ?)
            """, (memory_id, time.time(), old_trust, actual_new_trust, reason, drift))
        
        conn.commit()
        conn.close()
        
        logger.info(f"[TRUST] Memory {memory_id}: {old_trust:.3f} → {actual_new_trust:.3f}")
    
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
        conn = self._get_connection()
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
        conn = self._get_connection()
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
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute("SELECT * FROM memories")
        rows = cursor.fetchall()
        conn.close()
        
        memories = []
        for row in rows:
            # Handle both old and new schema (with/without deprecated columns)
            memory = MemoryItem(
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
            # Add deprecated fields if they exist
            if len(row) > 11:
                memory.deprecated = row[11] if row[11] is not None else False
            if len(row) > 12:
                memory.deprecation_reason = row[12]
            # Add two-tier extraction fields if they exist (Sprint 1)
            if len(row) > 13:
                memory.fact_tuples = row[13]
            if len(row) > 14:
                memory.extraction_method = row[14] if row[14] else 'regex'
            
            memories.append(memory)
        
        return memories
    
    def _load_memories_filtered(
        self,
        source: Optional[MemorySource] = None,
        thread_id: Optional[str] = None,
        limit: Optional[int] = None
    ) -> List[MemoryItem]:
        """
        Load memories with SQL-level filtering to avoid loading entire database.
        
        Performance optimization: Use this instead of _load_all_memories() when
        you need to filter by source, thread, or limit results.
        
        Args:
            source: Filter by memory source (USER, SYSTEM, etc.)
            thread_id: Filter by thread
            limit: Maximum number of results
            
        Returns:
            Filtered list of MemoryItem objects
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        
        # Build query with filters
        query = "SELECT * FROM memories WHERE 1=1"
        params = []
        
        if source is not None:
            query += " AND source = ?"
            params.append(source.value)
            
        if thread_id is not None:
            query += " AND thread_id = ?"
            params.append(thread_id)
            
        # Order by timestamp descending for latest-first behavior
        query += " ORDER BY timestamp DESC"
        
        if limit is not None:
            query += " LIMIT ?"
            params.append(limit)
        
        cursor.execute(query, params)
        rows = cursor.fetchall()
        conn.close()
        
        memories = []
        for row in rows:
            memory = MemoryItem(
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
            # Add additional fields if they exist
            if len(row) > 11:
                memory.deprecated = row[11] if row[11] is not None else False
            if len(row) > 12:
                memory.deprecation_reason = row[12]
            if len(row) > 13:
                memory.fact_tuples = row[13]
            if len(row) > 14:
                memory.extraction_method = row[14] if row[14] else 'regex'
            
            memories.append(memory)
        
        return memories
    
    def _get_all_vectors(self) -> List[np.ndarray]:
        """
        Get all memory vectors efficiently.
        
        Optimized to load only vector data without deserializing other fields.
        
        Note: For very large databases (>50k memories), consider using
        paginated/streamed loading to prevent OOM errors. This loads all
        vectors into memory at once.
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        
        # Check count first to warn about large loads
        cursor.execute("SELECT COUNT(*) FROM memories")
        count = cursor.fetchone()[0]
        
        if count > 50_000:
            logger.warning(
                f"Loading {count} vectors into memory. Consider pagination for large datasets."
            )
        
        # Only fetch vectors, skip other columns
        cursor.execute("SELECT vector_json FROM memories")
        rows = cursor.fetchall()
        conn.close()
        
        # Deserialize only the vectors
        vectors = [np.array(json.loads(row[0])) for row in rows]
        return vectors

    def get_memory_by_id(self, memory_id: str) -> Optional[MemoryItem]:
        """Fetch a single memory by ID (or None if missing)."""
        conn = self._get_connection()
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
        conn = self._get_connection()
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
        conn = self._get_connection()
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
    
    # ========================================================================
    # M3: Research Storage with Evidence Packets
    # ========================================================================
    
    def store_research_result(
        self,
        query: str,
        evidence_packet: 'EvidencePacket',  # type: ignore
    ) -> str:
        """
        Store research result in notes lane with full provenance.
        
        Design:
        - Always goes to notes lane (quarantined, never belief)
        - Trust fixed at 0.4 for TOOL sources
        - Provenance stored in context with citations
        - Can only be promoted to belief lane by user
        
        Args:
            query: Original research query
            evidence_packet: EvidencePacket with summary and citations
        
        Returns:
            memory_id of stored research result
        """
        # Build provenance context (must match policy.py requirements)
        provenance_context = {
            "type": "research_note",
            "packet_id": evidence_packet.packet_id,
            "query": query,
            "provenance": {
                "tool": "research_engine",
                "retrieved_at": evidence_packet.created_at.isoformat(),
                "source": f"local_search:{query}",
                "citations": [c.to_dict() for c in evidence_packet.citations],
                "citation_count": evidence_packet.citation_count(),
                "source_urls": evidence_packet.get_source_urls(),
            }
        }
        
        # Store as EXTERNAL source (requires provenance)
        memory = self.store_memory(
            text=evidence_packet.summary,
            confidence=0.6,  # Medium confidence for research
            source=MemorySource.EXTERNAL,
            context=provenance_context,
            user_marked_important=False,
            contradiction_signal=0.0
        )
        
        # Override trust to match evidence packet (should be 0.4)
        self._update_memory_trust(memory.memory_id, evidence_packet.trust)
        
        return memory.memory_id
    
    def _update_memory_trust(self, memory_id: str, new_trust: float) -> None:
        """Update trust score for a memory (internal use)."""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            UPDATE memories 
            SET trust = ?
            WHERE memory_id = ?
        """, (new_trust, memory_id))
        
        conn.commit()
        conn.close()
    
    def promote_to_belief(self, memory_id: str, user_confirmed: bool = True) -> bool:
        """
        Promote a research note to belief lane.
        
        Args:
            memory_id: Memory to promote
            user_confirmed: Must be True (user must explicitly confirm)
        
        Returns:
            True if promoted successfully
        """
        if not user_confirmed:
            return False
        
        # Increase trust to belief threshold (0.7+)
        self._update_memory_trust(memory_id, 0.8)
        
        return True
    
    def get_research_citations(self, memory_id: str) -> List[Dict]:
        """
        Get citations for a research memory.
        
        Args:
            memory_id: Memory ID
        
        Returns:
            List of citation dicts
        """
        memory = self.retrieve_by_id(memory_id)
        if not memory or not memory.context:
            return []
        
        # Citations are stored in context.provenance.citations
        provenance = memory.context.get("provenance", {})
        return provenance.get("citations", [])
    
    def retrieve_by_id(self, memory_id: str) -> Optional[MemoryItem]:
        """Retrieve a specific memory by ID."""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT memory_id, vector_json, text, timestamp, confidence, trust, source, sse_mode, context_json
            FROM memories
            WHERE memory_id = ?
        """, (memory_id,))
        
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
            context=json.loads(row[8]) if row[8] else None
        )
