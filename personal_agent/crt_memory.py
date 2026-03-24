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

import contextvars
import math
import sqlite3
import json
import logging
import numpy as np
import re
from typing import List, Dict, Optional, Any, Tuple, Set
from datetime import datetime
from dataclasses import dataclass, asdict
import time

# Context variable for propagating the authenticated user_id into engine
# internals without changing every call signature.  Route handlers set this
# before invoking the engine; store_memory reads it as a fallback when no
# explicit user_id argument is provided.
_request_user_id: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar(
    "_request_user_id", default=None,
)

from .db_utils import retry_on_lock, get_db_connection
from .crt_core import (
    CRTMath, CRTConfig, SSEMode, MemorySource,
    encode_vector, extract_emotion_intensity, extract_future_relevance
)
from .policy import validate_external_memory_context
from .engine.anchors import AnchorSystem
from .engine.reconstruction import ReconstructionFidelityEvaluator

logger = logging.getLogger(__name__)


_TRANSCRIPT_GUARD_MARKERS = (
    "[CONTINUITY INSTRUCTION]",
    "[RECENT CONVERSATION CONTEXT]",
)

_TRANSCRIPT_LINE_RE = re.compile(r"(?im)^\s*(user|assistant)\s*:")

# Patterns in system-source response text that would poison user-fact extraction.
# These are Aether's own identity assertions that get stored as system memories and
# then mistakenly re-extracted as "name = Aether" user facts.
_AETHER_IDENTITY_LEAK_RE = re.compile(
    r"\b(?:your|my)\s+name\s+is\s+(?:Aether|GroundCheck|CRT)\b"
    r"|I(?:'m|\s+am)\s+\*{0,2}(?:Aether|the\s+Aether)\b"
    r"|You\s+are\s+\*{0,2}(?:Aether|the\s+Aether)\b"
    r"|\*{0,2}Name\*{0,2}\s*:\s*\*{0,2}Aether\b",
    re.IGNORECASE,
)

_AUTHORITY_RANK = {
    "provisional": 0,
    "confirmed": 1,
    "locked": 2,
}

_SOCIAL_CHANNELS = {"moltbook"}
_INTERNAL_PROVISIONAL_SOURCES = {
    MemorySource.SYSTEM,
    MemorySource.FALLBACK,
    MemorySource.REFLECTION,
    MemorySource.LLM_OUTPUT,
}

_NON_USER_FACT_KINDS = {
    "ops",
    "identity_constant",
    "evolution_observation",
    "evolution_proposal",
    "narrative_note",
    "narrative_summary",
    "self_model",
    "sentiment_contradiction",
    "synthesis",
}

_ALLOWED_MEMORY_KINDS = {
    "user_fact",
    "ops",
    "preference",
    "identity_constant",
    "evolution_observation",
    "evolution_proposal",
    "hypothesis",
    "observation",
    "narrative_note",
}

# Provenance source kinds for model output governance
_VALID_SOURCE_KINDS = {"principal", "tool_receipt", "model_output", "social", "external", "system"}

# review_after defaults in seconds from storage time, keyed by memory kind.
# None means no scheduled review (never expires by staleness).
_REVIEW_AFTER_DEFAULTS: Dict[str, Optional[float]] = {
    "identity_constant":    None,
    "user_fact":            None,
    "preference":           90  * 86_400,   # 90 days
    "permission":           14  * 86_400,   # 14 days
    "ops":                  30  * 86_400,   # 30 days
    "evolution_observation": None,
    "evolution_proposal":   None,
    "hypothesis":           30  * 86_400,   # 30 days
    "observation":          60  * 86_400,   # 60 days
    "narrative_note":       None,           # non-authoritative, no scheduled review
}

# Kinds eligible for quiet model_output→confirmed promotion (no principal needed)
_QUIET_PROMOTION_KINDS = {"ops"}

_USAGE_EVENT_TYPES = (
    "retrieved",
    "prompt_included",
    "slot_selected",
    "guard_blocked",
    "answer_support",
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
    
    Phase 2.0 Updates:
    - temporal_status: past/active/future/potential
    - valid_from/valid_until: Time validity bounds
    - domain_tags: Context domains (print_shop, programming, etc.)
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
    
    # Phase 2.0: Temporal and domain context
    temporal_status: str = "active"             # past | active | future | potential
    valid_from: Optional[float] = None          # Unix timestamp (None = beginning of time)
    valid_until: Optional[float] = None         # Unix timestamp (None = ongoing)
    domain_tags: Optional[List[str]] = None     # e.g., ["print_shop", "freelance"]
    authority: str = "confirmed"                # provisional | confirmed | locked
    channel: str = "unknown"                    # webchat | telegram | moltbook | system | unknown | api | ...
    origin: Optional[str] = None                # URL, message ID, etc.
    kind: str = "observation"                   # user_fact | ops | preference | ...

    # User scoping — primary retrieval key (thread_id kept for audit trail)
    user_id: Optional[str] = None               # Authenticated user ID; None = legacy/anonymous

    # Phase B/C: Model provenance + staleness
    review_after: Optional[float] = None        # Unix ts — if set and passed, memory is stale
    source_kind: str = "principal"              # principal | tool_receipt | model_output | social | external | system
    model_id: Optional[str] = None             # generating model identifier
    run_id: Optional[str] = None               # run/request identifier for traceability

    # Adaptive compression (Phase 1)
    compression_tier: int = 2                   # 0=cold(10D), 1=warm(64D), 2=full(384D)
    compressed_vector: Optional[np.ndarray] = None  # folded vector (None for tier 2)
    cogni_seed: Optional[Dict] = None           # CogniSeed dict for reconstruction
    stable_cycles: int = 0                      # consecutive low-volatility heartbeat cycles
    contradiction_count: int = 0                # times contradicted
    access_count: int = 0                       # retrieval hit count
    
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
            'thread_id': self.thread_id,
            'temporal_status': self.temporal_status,
            'valid_from': self.valid_from,
            'valid_until': self.valid_until,
            'domain_tags': self.domain_tags,
            'authority': self.authority,
            'channel': self.channel,
            'origin': self.origin,
            'kind': self.kind,
            'review_after': self.review_after,
            'source_kind': self.source_kind,
            'model_id': self.model_id,
            'run_id': self.run_id,
            'compression_tier': self.compression_tier,
            'compressed_vector': self.compressed_vector.tolist() if self.compressed_vector is not None else None,
            'cogni_seed': self.cogni_seed,
            'stable_cycles': self.stable_cycles,
            'contradiction_count': self.contradiction_count,
            'access_count': self.access_count,
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
            thread_id=data.get('thread_id'),
            temporal_status=data.get('temporal_status', 'active'),
            valid_from=data.get('valid_from'),
            valid_until=data.get('valid_until'),
            domain_tags=data.get('domain_tags'),
            authority=data.get('authority', 'confirmed'),
            channel=data.get('channel', 'unknown'),
            origin=data.get('origin'),
            kind=data.get('kind', 'observation'),
            review_after=data.get('review_after'),
            source_kind=data.get('source_kind', 'principal'),
            model_id=data.get('model_id'),
            run_id=data.get('run_id'),
            compression_tier=data.get('compression_tier', 2),
            compressed_vector=np.array(data['compressed_vector']) if data.get('compressed_vector') is not None else None,
            cogni_seed=data.get('cogni_seed'),
            stable_cycles=data.get('stable_cycles', 0),
            contradiction_count=data.get('contradiction_count', 0),
            access_count=data.get('access_count', 0),
        )
    
    def get_domains(self) -> List[str]:
        """Get domain tags, with fallback to 'general'."""
        if self.domain_tags:
            return self.domain_tags
        return ["general"]
    
    def is_active(self) -> bool:
        """Check if this memory is currently active (not past/deprecated)."""
        return self.temporal_status == "active" and not self.deprecated

    def is_stale(self, now: Optional[float] = None) -> bool:
        """True if review_after is set and has passed (soft staleness — still retrievable)."""
        if self.review_after is None:
            return False
        return (now if now is not None else time.time()) > self.review_after


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
        self.anchor_system = AnchorSystem()
        self.reconstruction_fidelity = ReconstructionFidelityEvaluator()
        self.fidelity_min_threshold = 0.60

        # Initialize database
        self._init_db()
        try:
            self._consolidate_sync_origin_duplicates()
        except Exception as e:
            logger.debug(f"[MEMORY] Sync duplicate consolidation skipped: {e}")
    
    def _get_connection(self, timeout: float = 30.0) -> sqlite3.Connection:
        """
        Create a properly configured SQLite connection with:
        - WAL mode for better concurrent access
        - Busy timeout to retry on lock conflicts
        """
        conn = sqlite3.connect(self.db_path, timeout=timeout, check_same_thread=False)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
        conn.execute("PRAGMA busy_timeout=10000")  # 10 second busy timeout (reduced from 30)
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

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS memory_events (
                event_id INTEGER PRIMARY KEY AUTOINCREMENT,
                memory_id TEXT NOT NULL,
                timestamp REAL NOT NULL,
                event_type TEXT NOT NULL,
                old_authority TEXT,
                new_authority TEXT,
                actor TEXT,
                reason TEXT,
                metadata_json TEXT,
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
        
        # Reasoning traces - full thinking content for lazy loading
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS reasoning_traces (
                trace_id TEXT PRIMARY KEY,
                thread_id TEXT,
                query TEXT NOT NULL,
                thinking_content TEXT NOT NULL,
                response_summary TEXT,
                model TEXT,
                timestamp REAL NOT NULL,
                char_count INTEGER,
                metadata_json TEXT
            )
        """)
        
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_reasoning_traces_thread
            ON reasoning_traces(thread_id, timestamp DESC)
        """)
        
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_reasoning_traces_timestamp
            ON reasoning_traces(timestamp DESC)
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

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_memory_events_memory
            ON memory_events(memory_id, timestamp DESC)
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_memory_events_type_timestamp
            ON memory_events(event_type, timestamp DESC)
        """)

        # Cached fact slots extracted from memories (avoids re-running regex on every query)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS memory_facts (
                memory_id TEXT NOT NULL,
                slot TEXT NOT NULL,
                value TEXT NOT NULL,
                normalized TEXT,
                UNIQUE(memory_id, slot)
            )
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_memory_facts_slot
            ON memory_facts(slot)
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_memory_facts_memory
            ON memory_facts(memory_id)
        """)

        conn.commit()
        conn.close()

        # Migrate existing databases to add deprecated columns if needed
        # This must run BEFORE creating deprecated column indexes
        self._migrate_schema()
        
        # Create indexes for columns added by migration (safe after migration)
        self._create_post_migration_indexes()
    
    def _create_post_migration_indexes(self):
        """Create indexes for columns that may have been added by migration."""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        # Index for deprecated column (for filtering)
        try:
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_memories_deprecated
                ON memories(deprecated)
            """)
        except Exception as e:
            logger.debug(f"[MEMORY] Could not create deprecated index: {e}")

        for index_name, column_name in (
            ("idx_memories_authority", "authority"),
            ("idx_memories_channel", "channel"),
            ("idx_memories_kind", "kind"),
        ):
            try:
                cursor.execute(
                    f"CREATE INDEX IF NOT EXISTS {index_name} ON memories({column_name})"
                )
            except Exception as e:
                logger.debug(f"[MEMORY] Could not create {index_name}: {e}")

        try:
            cursor.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_memories_thread_origin_active
                ON memories(thread_id, origin, deprecated, timestamp DESC)
                """
            )
        except Exception as e:
            logger.debug(f"[MEMORY] Could not create idx_memories_thread_origin_active: {e}")
        
        conn.commit()
        conn.close()
    
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
        
        # Phase 2.0: Add temporal and domain columns for context-aware memory
        if "temporal_status" not in columns:
            logger.info(f"[MIGRATION] Adding temporal_status column to {self.db_path}")
            cursor.execute("ALTER TABLE memories ADD COLUMN temporal_status TEXT DEFAULT 'active'")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_memories_temporal_status ON memories(temporal_status)")
        
        if "valid_from" not in columns:
            logger.info(f"[MIGRATION] Adding valid_from column to {self.db_path}")
            cursor.execute("ALTER TABLE memories ADD COLUMN valid_from REAL")
        
        if "valid_until" not in columns:
            logger.info(f"[MIGRATION] Adding valid_until column to {self.db_path}")
            cursor.execute("ALTER TABLE memories ADD COLUMN valid_until REAL")
        
        if "domain_tags" not in columns:
            logger.info(f"[MIGRATION] Adding domain_tags column to {self.db_path}")
            cursor.execute("ALTER TABLE memories ADD COLUMN domain_tags TEXT")  # JSON array
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_memories_domain_tags ON memories(domain_tags)")

        if "authority" not in columns:
            logger.info(f"[MIGRATION] Adding authority column to {self.db_path}")
            cursor.execute("ALTER TABLE memories ADD COLUMN authority TEXT DEFAULT 'confirmed'")
            cursor.execute("UPDATE memories SET authority = 'confirmed' WHERE authority IS NULL OR TRIM(authority) = ''")

        if "channel" not in columns:
            logger.info(f"[MIGRATION] Adding channel column to {self.db_path}")
            cursor.execute("ALTER TABLE memories ADD COLUMN channel TEXT DEFAULT 'unknown'")
            cursor.execute("UPDATE memories SET channel = 'unknown' WHERE channel IS NULL OR TRIM(channel) = ''")

        if "origin" not in columns:
            logger.info(f"[MIGRATION] Adding origin column to {self.db_path}")
            cursor.execute("ALTER TABLE memories ADD COLUMN origin TEXT")

        if "kind" not in columns:
            logger.info(f"[MIGRATION] Adding kind column to {self.db_path}")
            cursor.execute("ALTER TABLE memories ADD COLUMN kind TEXT DEFAULT 'observation'")
            cursor.execute("UPDATE memories SET kind = 'observation' WHERE kind IS NULL OR TRIM(kind) = ''")

        if "review_after" not in columns:
            logger.info(f"[MIGRATION] Adding review_after column to {self.db_path}")
            cursor.execute("ALTER TABLE memories ADD COLUMN review_after REAL")

        if "source_kind" not in columns:
            logger.info(f"[MIGRATION] Adding source_kind column to {self.db_path}")
            cursor.execute("ALTER TABLE memories ADD COLUMN source_kind TEXT DEFAULT 'principal'")
            cursor.execute("UPDATE memories SET source_kind = 'principal' WHERE source_kind IS NULL OR TRIM(source_kind) = ''")

        if "model_id" not in columns:
            logger.info(f"[MIGRATION] Adding model_id column to {self.db_path}")
            cursor.execute("ALTER TABLE memories ADD COLUMN model_id TEXT")

        if "run_id" not in columns:
            logger.info(f"[MIGRATION] Adding run_id column to {self.db_path}")
            cursor.execute("ALTER TABLE memories ADD COLUMN run_id TEXT")

        # Adaptive compression (Phase 1)
        if "compression_tier" not in columns:
            logger.info(f"[MIGRATION] Adding compression columns to {self.db_path}")
            cursor.execute("ALTER TABLE memories ADD COLUMN compression_tier INTEGER DEFAULT 2")
            cursor.execute("ALTER TABLE memories ADD COLUMN compressed_vector_json TEXT")
            cursor.execute("ALTER TABLE memories ADD COLUMN cogni_seed_json TEXT")
            cursor.execute("ALTER TABLE memories ADD COLUMN stable_cycles INTEGER DEFAULT 0")
            cursor.execute("ALTER TABLE memories ADD COLUMN contradiction_count INTEGER DEFAULT 0")
            cursor.execute("ALTER TABLE memories ADD COLUMN access_count INTEGER DEFAULT 0")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_memories_compression_tier ON memories(compression_tier)")

        # User-scoped retrieval (user_id replaces thread_id as primary filter).
        # IMPORTANT: this migration MUST run after the compression columns so that
        # user_id is always the last column (index 33) in SELECT * results.
        if "user_id" not in columns:
            logger.info(f"[MIGRATION] Adding user_id column to {self.db_path}")
            cursor.execute("ALTER TABLE memories ADD COLUMN user_id TEXT")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_memories_user_id ON memories(user_id)")

        conn.commit()
        conn.close()

    def _normalize_authority(self, authority: Optional[str]) -> str:
        value = str(authority or "").strip().lower()
        return value if value in _AUTHORITY_RANK else "confirmed"

    def _normalize_channel(self, channel: Optional[str]) -> str:
        value = str(channel or "").strip().lower()
        return value or "unknown"

    def _normalize_kind(
        self,
        kind: Optional[str],
        *,
        source: MemorySource,
        context: Optional[Dict[str, Any]] = None,
    ) -> str:
        value = str(kind or "").strip().lower()
        if value not in _ALLOWED_MEMORY_KINDS:
            ctx_kind = ""
            if isinstance(context, dict):
                ctx_kind = str(context.get("memory_kind") or "").strip().lower()
                if not ctx_kind:
                    raw_kind = str(context.get("kind") or "").strip().lower()
                    if raw_kind in _ALLOWED_MEMORY_KINDS:
                        ctx_kind = raw_kind
            if ctx_kind in _ALLOWED_MEMORY_KINDS:
                value = ctx_kind
        if value not in _ALLOWED_MEMORY_KINDS:
            if source == MemorySource.USER and isinstance(context, dict):
                ctx_type = str(context.get("type") or "").strip().lower()
                ctx_kind = str(context.get("kind") or "").strip().lower()
                if ctx_type == "llm_extracted_fact" or (ctx_type == "user_input" and ctx_kind == "assertion"):
                    return "user_fact"
            return "observation"
        return value

    def _normalize_source_kind(self, source_kind: Optional[str]) -> str:
        value = str(source_kind or "").strip().lower()
        return value if value in _VALID_SOURCE_KINDS else "principal"

    def _compute_review_after(self, kind: str, now: Optional[float] = None) -> Optional[float]:
        """Return a review_after timestamp for the given kind, or None if no review is scheduled."""
        delta = _REVIEW_AFTER_DEFAULTS.get(kind)
        if delta is None:
            return None
        return (now if now is not None else time.time()) + delta

    @staticmethod
    def _normalize_dedupe_text(text: Optional[str]) -> str:
        return re.sub(r"\s+", " ", str(text or "").strip()).lower()

    _DEDUP_SIMILARITY_THRESHOLD = 0.9

    def _find_dedup_match(
        self, vector: np.ndarray, text: str
    ) -> Optional[Tuple[str, float]]:
        """Return (memory_id, trust) of an existing memory that is a semantic
        duplicate of *text* / *vector*, or None if no duplicate is found.

        A match requires:
        1. Cosine similarity >= 0.9 between the embedding vectors.
        2. Normalized-text equality (guards against high-similarity but
           semantically different short phrases).
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute(
                "SELECT memory_id, vector_json, text, trust FROM memories"
            )
            rows = cursor.fetchall()
        finally:
            conn.close()

        if not rows:
            return None

        norm_new = self._normalize_dedupe_text(text)
        best: Optional[Tuple[str, float, float]] = None  # (id, sim, trust)

        for memory_id, vector_json, existing_text, trust in rows:
            try:
                existing_vec = np.array(json.loads(vector_json))
            except Exception:
                continue
            sim = float(self.crt_math.similarity(vector, existing_vec))
            if sim < self._DEDUP_SIMILARITY_THRESHOLD:
                continue
            # High vector similarity — confirm with normalized text match
            if self._normalize_dedupe_text(existing_text) != norm_new:
                continue
            if best is None or sim > best[1]:
                best = (memory_id, sim, float(trust))

        if best is not None:
            return (best[0], best[2])
        return None

    def _is_sync_style_write(
        self,
        *,
        origin: Optional[str],
        context: Optional[Dict[str, Any]] = None,
    ) -> bool:
        origin_value = str(origin or "").strip().lower()
        if origin_value.startswith("user.md:"):
            return True
        if not isinstance(context, dict):
            return False
        ctx_type = str(context.get("type") or "").strip().lower()
        return ctx_type in {"sync_user_md", "user_md_sync"}

    def _get_active_origin_memories(
        self,
        *,
        origin: Optional[str],
        thread_id: Optional[str],
    ) -> List[MemoryItem]:
        origin_value = str(origin or "").strip()
        if not origin_value:
            return []
        thread_key = str(thread_id or "").strip()
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT *
            FROM memories
            WHERE origin = ?
              AND COALESCE(thread_id, '') = ?
              AND COALESCE(deprecated, 0) = 0
            ORDER BY timestamp DESC
            """,
            (origin_value, thread_key),
        )
        rows = cursor.fetchall()
        conn.close()
        return [self._row_to_memory(row) for row in rows]

    def _consolidate_sync_origin_duplicates(self) -> int:
        """Keep only the newest active sync-import memory per thread+origin."""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT COALESCE(thread_id, '') AS thread_key, origin
            FROM memories
            WHERE origin LIKE 'USER.md:%'
              AND COALESCE(deprecated, 0) = 0
            GROUP BY thread_key, origin
            HAVING COUNT(*) > 1
            """
        )
        groups = cursor.fetchall()
        conn.close()

        deprecated_count = 0
        for thread_key, origin in groups:
            active = self._get_active_origin_memories(origin=origin, thread_id=thread_key)
            if len(active) <= 1:
                continue
            keep = active[0]
            for older in active[1:]:
                self.deprecate_memory(
                    older.memory_id,
                    reason=f"sync_replaced:{origin}",
                )
                self.record_memory_event(
                    memory_id=older.memory_id,
                    event_type="sync_replaced",
                    actor="system",
                    reason="historical_sync_consolidation",
                    metadata={
                        "origin": origin,
                        "thread_id": thread_key or None,
                        "replacement_memory_id": keep.memory_id,
                    },
                )
                deprecated_count += 1
        return deprecated_count

    def _resolve_origin(
        self,
        origin: Optional[str],
        context: Optional[Dict[str, Any]] = None,
        *,
        source: Optional[MemorySource] = None,
        channel: Optional[str] = None,
        kind: Optional[str] = None,
    ) -> Optional[str]:
        value = str(origin or "").strip()
        if value:
            return value
        if not isinstance(context, dict):
            context = {}
        for key in ("origin", "message_id", "url"):
            candidate = str(context.get(key) or "").strip()
            if candidate:
                return candidate
        provenance = context.get("provenance")
        if isinstance(provenance, dict):
            for key in ("source", "url", "message_id"):
                candidate = str(provenance.get(key) or "").strip()
                if candidate:
                    return candidate
        if source in _INTERNAL_PROVISIONAL_SOURCES or str(channel or "").strip().lower() == "system":
            detail = (
                str(context.get("kind") or "").strip().lower()
                or str(context.get("type") or "").strip().lower()
                or str(kind or "").strip().lower()
                or (source.value if source is not None else "system")
            )
            detail = re.sub(r"[^a-z0-9._:-]+", "_", detail).strip("_") or "memory"
            return f"system:{detail}"
        return None

    def _resolve_memory_metadata(
        self,
        *,
        authority: Optional[str],
        channel: Optional[str],
        origin: Optional[str],
        kind: Optional[str],
        source: MemorySource,
        context: Optional[Dict[str, Any]] = None,
    ) -> Tuple[str, str, Optional[str], str]:
        raw_channel = channel if channel is not None else (context or {}).get("channel")
        raw_authority = authority if authority is not None else (context or {}).get("authority")

        explicit_channel = bool(str(raw_channel or "").strip())
        explicit_authority = bool(str(raw_authority or "").strip())

        resolved_channel = self._normalize_channel(raw_channel)
        if not explicit_channel and source in _INTERNAL_PROVISIONAL_SOURCES:
            resolved_channel = "system"

        resolved_kind = self._normalize_kind(kind, source=source, context=context)
        resolved_authority = self._normalize_authority(raw_authority)
        if not explicit_authority and source in _INTERNAL_PROVISIONAL_SOURCES:
            resolved_authority = "provisional"
        resolved_origin = self._resolve_origin(
            origin,
            context,
            source=source,
            channel=resolved_channel,
            kind=resolved_kind,
        )

        if resolved_channel in _SOCIAL_CHANNELS:
            resolved_authority = "provisional"
            if resolved_kind not in {"evolution_observation"}:
                resolved_kind = "observation"

        # Narrative notes are always provisional — they are introspective, not authoritative.
        if resolved_kind == "narrative_note":
            resolved_authority = "provisional"

        return resolved_authority, resolved_channel, resolved_origin, resolved_kind

    def is_social_channel(self, channel: Optional[str]) -> bool:
        return self._normalize_channel(channel) in _SOCIAL_CHANNELS

    def is_authoritative_memory(self, memory: Optional[MemoryItem]) -> bool:
        if memory is None:
            return False
        return self._normalize_authority(getattr(memory, "authority", None)) in {"confirmed", "locked"}

    def can_answer_user_fact(self, memory: Optional[MemoryItem]) -> bool:
        if not self.is_authoritative_memory(memory):
            return False
        kind = str(getattr(memory, "kind", "observation") or "observation").strip().lower()
        return kind == "user_fact"

    def can_update_user_profile(self, memory: Optional[MemoryItem]) -> bool:
        return self.can_answer_user_fact(memory)

    def can_affect_contradiction_resolution(self, memory: Optional[MemoryItem]) -> bool:
        return self.is_authoritative_memory(memory)

    def _append_memory_event(
        self,
        *,
        memory_id: str,
        event_type: str,
        old_authority: Optional[str] = None,
        new_authority: Optional[str] = None,
        actor: Optional[str] = None,
        reason: Optional[str] = None,
        timestamp: Optional[float] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO memory_events
            (memory_id, timestamp, event_type, old_authority, new_authority, actor, reason, metadata_json)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                memory_id,
                float(timestamp if timestamp is not None else time.time()),
                str(event_type or "").strip() or "event",
                old_authority,
                new_authority,
                str(actor or "").strip() or None,
                str(reason or "").strip() or None,
                json.dumps(metadata) if metadata else None,
            ),
        )
        conn.commit()
        conn.close()

    def record_memory_event(
        self,
        *,
        memory_id: str,
        event_type: str,
        actor: Optional[str] = None,
        reason: Optional[str] = None,
        timestamp: Optional[float] = None,
        metadata: Optional[Dict[str, Any]] = None,
        old_authority: Optional[str] = None,
        new_authority: Optional[str] = None,
    ) -> None:
        """Public append-only event writer."""
        self._append_memory_event(
            memory_id=memory_id,
            event_type=event_type,
            old_authority=old_authority,
            new_authority=new_authority,
            actor=actor,
            reason=reason,
            timestamp=timestamp,
            metadata=metadata,
        )

    def record_memory_usage(
        self,
        memory_ids: List[str],
        *,
        event_type: str,
        actor: Optional[str] = "system",
        reason: Optional[str] = None,
        timestamp: Optional[float] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> int:
        """Append usage events for one or more memories in a single transaction."""
        unique_ids: List[str] = []
        seen: Set[str] = set()
        for raw_memory_id in memory_ids:
            memory_id = str(raw_memory_id or "").strip()
            if not memory_id or memory_id in seen:
                continue
            unique_ids.append(memory_id)
            seen.add(memory_id)

        if not unique_ids:
            return 0

        when = float(timestamp if timestamp is not None else time.time())
        normalized_event_type = str(event_type or "").strip() or "event"
        base_metadata = dict(metadata or {})

        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.executemany(
            """
            INSERT INTO memory_events
            (memory_id, timestamp, event_type, old_authority, new_authority, actor, reason, metadata_json)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    memory_id,
                    when,
                    normalized_event_type,
                    None,
                    None,
                    str(actor or "").strip() or None,
                    str(reason or "").strip() or None,
                    json.dumps({**base_metadata, "memory_id": memory_id}) if base_metadata else None,
                )
                for memory_id in unique_ids
            ],
        )
        conn.commit()
        conn.close()
        return len(unique_ids)
    
    # ========================================================================
    # Memory Storage
    # ========================================================================

    def _sanitize_transcript_pollution(self, text: str) -> Tuple[str, Optional[str]]:
        """
        Remove continuity/transcript helper blocks before persistence.

        Returns:
            (clean_text, reason) where reason is set if any cleanup occurred.
        """
        raw = str(text or "")
        cleaned = raw.strip()
        if not cleaned:
            return "", None

        reason: Optional[str] = None

        # Remove continuity helper suffix blocks.
        cut_at: Optional[int] = None
        for marker in _TRANSCRIPT_GUARD_MARKERS:
            idx = cleaned.find(marker)
            if idx >= 0 and (cut_at is None or idx < cut_at):
                cut_at = idx
        if cut_at is not None:
            cleaned = cleaned[:cut_at].strip()
            reason = "continuity_block_trimmed"

        # Remove appended transcript sections.
        transcript_match = re.search(r"\n\s*(?:User|Assistant)\s*:", cleaned, flags=re.IGNORECASE)
        if transcript_match:
            cleaned = cleaned[: transcript_match.start()].strip()
            reason = reason or "transcript_block_trimmed"

        # If remaining text still starts with transcript labels, strip one prefix.
        if _TRANSCRIPT_LINE_RE.match(cleaned):
            cleaned = _TRANSCRIPT_LINE_RE.sub("", cleaned, count=1).strip()
            reason = reason or "transcript_prefix_stripped"

        # Strip Aether identity-leak sentences so they can't be re-extracted
        # as user facts.  e.g. "Your name is Aether, a custom-built AI…" stored
        # as a system memory would later yield name="Aether" via fact_slots.
        if _AETHER_IDENTITY_LEAK_RE.search(cleaned):
            # Remove only the offending sentence(s), not the whole memory.
            sentences = re.split(r"(?<=[.!?])\s+", cleaned)
            filtered = [s for s in sentences if not _AETHER_IDENTITY_LEAK_RE.search(s)]
            cleaned = " ".join(filtered).strip()
            reason = reason or "aether_identity_leak_stripped"

        # Defensive: collapse excessive blank lines after trimming.
        cleaned = re.sub(r"\n{3,}", "\n\n", cleaned).strip()

        return cleaned, reason
    
    def store_memory(
        self,
        text: str,
        confidence: float,
        source: MemorySource,
        context: Optional[Dict] = None,
        user_marked_important: bool = False,
        contradiction_signal: float = 0.0,
        thread_id: Optional[str] = None,
        authority: Optional[str] = None,
        channel: Optional[str] = None,
        origin: Optional[str] = None,
        kind: Optional[str] = None,
        source_kind: Optional[str] = None,
        model_id: Optional[str] = None,
        run_id: Optional[str] = None,
        user_id: Optional[str] = None,
    ) -> MemoryItem:
        """
        Store new memory with CRT principles.

        Process:
        1. Encode to vector
        2. Compute significance → select SSE mode
        3. Assign initial trust (based on source)
        4. Store with metadata
        """
        # Write-time guard: strip continuity/transcript contamination from text.
        text_clean, guard_reason = self._sanitize_transcript_pollution(text)
        if guard_reason:
            logger.info("[MEMORY_GUARD] %s", guard_reason)
        if not text_clean:
            logger.warning("[MEMORY_GUARD] Skipping empty memory after sanitation")
            text_clean = "[filtered-empty-memory]"

        text = text_clean

        # Thread affinity: prefer explicit arg, then context thread_id.
        resolved_thread_id = str(thread_id or "").strip() or None
        if not resolved_thread_id and isinstance(context, dict):
            ctx_tid = context.get("thread_id")
            if ctx_tid is not None:
                ctx_tid_str = str(ctx_tid).strip()
                if ctx_tid_str:
                    resolved_thread_id = ctx_tid_str

        authority, channel, origin, kind = self._resolve_memory_metadata(
            authority=authority,
            channel=channel,
            origin=origin,
            kind=kind,
            source=source,
            context=context,
        )

        # Normalize provenance fields.
        resolved_source_kind = self._normalize_source_kind(source_kind)

        # model_output provenance → always provisional (except quiet ops promotion handled separately)
        if resolved_source_kind == "model_output" and authority not in {"locked"}:
            authority = "provisional"

        # Compute soft staleness marker from kind defaults.
        review_after = self._compute_review_after(kind)

        active_origin_memories: List[MemoryItem] = []
        if self._is_sync_style_write(origin=origin, context=context):
            active_origin_memories = self._get_active_origin_memories(
                origin=origin,
                thread_id=resolved_thread_id,
            )
            normalized_new_text = self._normalize_dedupe_text(text)
            for existing in active_origin_memories:
                if self._normalize_dedupe_text(getattr(existing, "text", "")) != normalized_new_text:
                    continue
                self.record_memory_event(
                    memory_id=existing.memory_id,
                    event_type="sync_duplicate_skipped",
                    actor="system",
                    reason="idempotent_origin_match",
                    metadata={
                        "origin": origin,
                        "thread_id": resolved_thread_id,
                    },
                )
                return existing

        # Policy boundary: external/tool memories must be auditable.
        if source == MemorySource.EXTERNAL:
            validate_external_memory_context(context)

        # SPRINT 1: Detect if this is an explicit correction
        correction_phrases = [
            "actually", "not", "correction", "correct", "wrong",
            "i mean", "i meant", "clarify", "to be clear",
            "changed", "no longer", "instead"
        ]
        
        is_correction = any(phrase in text.lower() for phrase in correction_phrases)
        
        # If this is a correction, boost confidence and trust
        if is_correction:
            confidence = max(confidence, 0.95)  # Explicit corrections are high confidence
            logger.info(f"[CORRECTION_DETECTED] Boosting confidence for: {text[:60]}")

        # Encode
        vector = encode_vector(text)

        # --- Dedup check: skip insert if a near-identical memory already exists ---
        dedup_match = self._find_dedup_match(vector, text)
        if dedup_match is not None:
            existing_id, existing_trust = dedup_match
            # Bump trust: reinforce the existing memory (capped at 1.0)
            new_trust = min(float(existing_trust) + 0.05, 1.0)
            now = time.time()
            conn = self._get_connection()
            conn.execute(
                "UPDATE memories SET trust = ?, timestamp = ? WHERE memory_id = ?",
                (new_trust, now, existing_id),
            )
            conn.commit()
            conn.close()
            self.record_memory_event(
                memory_id=existing_id,
                event_type="dedup_reinforced",
                actor="system",
                reason=f"duplicate suppressed (sim>0.9), trust {existing_trust:.3f}->{new_trust:.3f}",
                metadata={"new_text": text[:200], "old_trust": existing_trust, "new_trust": new_trust},
            )
            logger.info(
                "[DEDUP] Reinforced existing memory %s instead of inserting duplicate (trust %.3f->%.3f): %s",
                existing_id, existing_trust, new_trust, text[:80],
            )
            # Return the existing memory item so callers behave normally
            existing_mem = self.get_memory_by_id(existing_id)
            if existing_mem is not None:
                return existing_mem
            # Fallthrough: if the row vanished between check and fetch, insert normally

        # --- Slot-level behavior: handle exclusive/additive/temporal slots dynamically ---
        # Sprint 6: replaced hardcoded EXCLUSIVE_SLOTS with learned slot types.
        # This runs AFTER text-based dedup (which only catches near-identical text)
        # to handle cases like "favorite color is green" vs "favorite color is orange".
        _corrective_phrases = ("not ", "actually", "always has been", "never was")
        _has_corrective_language = any(p in text.lower() for p in _corrective_phrases)
        try:
            from .fact_slots import extract_fact_slots as _efs
            from .slot_discovery import get_slot_type, on_fact_stored, SlotType
            _new_slots = _efs(text)
            _discovery_db = None  # Use default discovery DB path
            for _slot_name, _slot_fact in _new_slots.items():
                _slot_type = get_slot_type(_slot_name, db_path=_discovery_db)
                _new_val_norm = str(getattr(_slot_fact, "normalized", getattr(_slot_fact, "value", _slot_fact))).strip().lower()

                if _slot_type == SlotType.ADDITIVE:
                    # Multiple values coexist — no demotion needed
                    logger.debug(
                        "[SLOT_DISCOVERY] Slot %s is ADDITIVE — keeping all values",
                        _slot_name,
                    )
                    continue

                if _slot_type == SlotType.UNKNOWN:
                    # Not enough data — default to exclusive for safety
                    logger.debug(
                        "[SLOT_DISCOVERY] Slot %s is UNKNOWN — defaulting to exclusive behavior",
                        _slot_name,
                    )

                # EXCLUSIVE, TEMPORAL, HIERARCHICAL, or UNKNOWN → demote old values
                # Query memory_facts for existing entries with same slot but different value
                _conn_ex = self._get_connection()
                _cur_ex = _conn_ex.cursor()
                _cur_ex.execute("""
                    SELECT mf.memory_id, mf.normalized, m.trust
                    FROM memory_facts mf
                    JOIN memories m ON mf.memory_id = m.memory_id
                    WHERE mf.slot = ? AND m.deprecated = 0
                """, (_slot_name,))
                _existing_rows = _cur_ex.fetchall()
                _conn_ex.close()
                for _ex_mem_id, _ex_norm, _ex_trust in _existing_rows:
                    if str(_ex_norm).strip().lower() == _new_val_norm:
                        continue  # Same value — not a conflict

                    if _slot_type == SlotType.TEMPORAL:
                        # Archive: lighter demotion — old value was true in the past
                        _demoted_trust = float(_ex_trust) * 0.6
                    else:
                        # Exclusive/unknown: stronger demotion
                        _demoted_trust = float(_ex_trust) * 0.4

                    self._update_memory_trust(_ex_mem_id, _demoted_trust)
                    self.record_memory_event(
                        memory_id=_ex_mem_id,
                        event_type="slot_exclusivity_demoted",
                        actor="system",
                        reason=f"superseded by new memory: {_slot_name}={_new_val_norm}",
                        metadata={
                            "slot": _slot_name,
                            "slot_type": _slot_type.value,
                            "old_value": str(_ex_norm),
                            "new_value": _new_val_norm,
                            "old_trust": float(_ex_trust),
                            "demoted_trust": _demoted_trust,
                        },
                    )
                    logger.info(
                        "[SLOT_EXCLUSIVITY] Demoted %s for slot %s (%s): %s -> %s (trust %.3f -> %.3f)",
                        _ex_mem_id, _slot_name, _slot_type.value, _ex_norm, _new_val_norm,
                        float(_ex_trust), _demoted_trust,
                    )

                # Notify slot discovery of the new fact (non-blocking)
                try:
                    on_fact_stored(_slot_name, _new_val_norm, confidence, db_path=_discovery_db)
                except Exception:
                    pass
        except Exception as _slot_ex_err:
            logger.debug(f"[SLOT_EXCLUSIVITY] Slot behavior check failed (non-fatal): {_slot_ex_err}")

        # Corrective language trust boost: if user is explicitly correcting a value,
        # start the new memory at 0.90 instead of the default 0.70.
        if _has_corrective_language:
            confidence = max(confidence, 0.90)
            logger.info(f"[SLOT_EXCLUSIVITY] Corrective language detected, boosting confidence to {confidence:.2f}: {text[:60]}")

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
        if source in {MemorySource.FALLBACK, MemorySource.LLM_OUTPUT}:
            trust = min(self.config.tau_base * 0.6, self.config.tau_fallback_cap)
        elif source == MemorySource.REFLECTION:
            trust = self.config.tau_base * 1.2  # Reflection gets higher initial trust
        else:
            trust = self.config.tau_base

        trust = np.clip(trust, 0.0, 1.0)

        # Phase 0.5 DNNT hook: reconstruction fidelity + anchor extraction.
        # The interface is stable so a learned Mirus/Holden module can replace it later.
        hook_context: Dict[str, Any] = dict(context or {})
        hook_meta = hook_context.get("crt_hooks")
        if not isinstance(hook_meta, dict):
            hook_meta = {}
        try:
            fidelity_signal = self.reconstruction_fidelity.evaluate(text=text, sse_mode=sse_mode)
            hook_meta["reconstruction_fidelity"] = round(float(fidelity_signal.fidelity), 6)
            hook_meta["reconstruction_loss"] = round(float(fidelity_signal.loss), 6)
            hook_meta["compressed_preview"] = fidelity_signal.compressed_text[:240]
            hook_meta["reconstructed_preview"] = fidelity_signal.reconstructed_text[:240]

            if fidelity_signal.fidelity < self.fidelity_min_threshold:
                # Low-fidelity memories are less trusted by default.
                delta = (self.fidelity_min_threshold - float(fidelity_signal.fidelity)) * 0.25
                trust = float(max(0.0, trust - delta))
                hook_meta["fidelity_trust_penalty"] = round(delta, 6)
        except Exception as e:
            logger.debug(f"[FIDELITY] Failed to compute reconstruction fidelity: {e}")
            hook_meta["reconstruction_fidelity"] = None
            hook_meta["reconstruction_loss"] = None

        try:
            anchors = self.anchor_system.matched_anchors(text)
            if anchors:
                hook_meta["anchor_matches"] = anchors
        except Exception as e:
            logger.debug(f"[ANCHORS] Failed to compute anchor matches: {e}")

        hook_context["crt_hooks"] = hook_meta
        context = hook_context
        
        # Sprint 1: Extract facts using two-tier system
        fact_tuples_json = None
        extraction_method = 'none'
        
        # Phase 2.0: Extract temporal status and domains
        temporal_status = "active"
        domain_tags = None
        
        try:
            from .two_tier_facts import TwoTierFactSystem
            from .fact_slots import extract_temporal_status, TemporalStatus
            from .domain_detector import detect_domains
            
            # Extract temporal status from text
            temporal_status, _ = extract_temporal_status(text)
            
            # Detect domains from text
            detected_domains = detect_domains(text)
            if detected_domains and detected_domains != ["general"]:
                domain_tags = detected_domains
            
            # Extract facts using two-tier system (local-only, no external API)
            extractor = TwoTierFactSystem(enable_llm=False)
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
            logger.debug(f"[PHASE_2.0] Temporal status: {temporal_status}, domains: {domain_tags}")
        except Exception as e:
            logger.warning(f"[TWO_TIER] Failed to extract facts: {e}")
            extraction_method = 'none'
        
        # Resolve user_id: prefer explicit arg → context dict → context variable.
        resolved_user_id = str(user_id or "").strip() or None
        if not resolved_user_id and isinstance(context, dict):
            ctx_uid = context.get("user_id")
            if ctx_uid is not None:
                ctx_uid_str = str(ctx_uid).strip()
                if ctx_uid_str:
                    resolved_user_id = ctx_uid_str
        if not resolved_user_id:
            resolved_user_id = _request_user_id.get(None)

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
            thread_id=resolved_thread_id,
            user_id=resolved_user_id,
            fact_tuples=fact_tuples_json,
            extraction_method=extraction_method,
            temporal_status=temporal_status,
            domain_tags=domain_tags,
            authority=authority,
            channel=channel,
            origin=origin,
            kind=kind,
            review_after=review_after,
            source_kind=resolved_source_kind,
            model_id=model_id,
            run_id=run_id,
        )

        # Store in database
        conn = self._get_connection()
        cursor = conn.cursor()

        try:
            cursor.execute("""
                INSERT INTO memories
                (memory_id, vector_json, text, timestamp, confidence, trust, source, sse_mode, context_json, fact_tuples, extraction_method, temporal_status, domain_tags, thread_id, authority, channel, origin, kind, review_after, source_kind, model_id, run_id, user_id)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                extraction_method,
                temporal_status,
                json.dumps(domain_tags) if domain_tags else None,
                resolved_thread_id,
                authority,
                channel,
                origin,
                kind,
                review_after,
                resolved_source_kind,
                model_id,
                run_id,
                resolved_user_id,
            ))
        except sqlite3.OperationalError as e:
            # Backward compatibility for old ad-hoc tables that may not include thread_id.
            if "thread_id" not in str(e).lower():
                raise
            cursor.execute("""
                INSERT INTO memories
                (memory_id, vector_json, text, timestamp, confidence, trust, source, sse_mode, context_json, fact_tuples, extraction_method, temporal_status, domain_tags)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                extraction_method,
                temporal_status,
                json.dumps(domain_tags) if domain_tags else None,
            ))

        conn.commit()
        conn.close()

        # Cache extracted hard facts in memory_facts table for fast slot lookups.
        # This avoids re-running regex on all memories at query time.
        # Skip fact extraction for narrative/system kinds to prevent pollution —
        # these contain LLM-generated summaries that re-extract user facts with
        # wrong source attribution.
        if extraction_method in ('regex', 'hybrid') and kind not in _NON_USER_FACT_KINDS:
            try:
                from .fact_slots import extract_fact_slots
                hard_facts = extract_fact_slots(text)
                if hard_facts:
                    self.store_memory_facts(memory.memory_id, hard_facts)
            except Exception as e:
                logger.debug(f"[MEMORY_FACTS] Failed to cache facts for {memory.memory_id}: {e}")

        # SPRINT 1: After storing, if correction was detected, decay contradicted memories.
        # Narrative notes are non-authoritative — they cannot trigger contradiction decay.
        if is_correction and memory.authority != "provisional" and kind != "narrative_note":
            contradicting = self._find_contradicting_memories(text)

            for old_mem in contradicting:
                # Narrative notes must never be decayed by other memories either.
                if getattr(old_mem, "kind", "observation") == "narrative_note":
                    continue
                # Significantly reduce trust of contradicted memory
                old_trust = old_mem.trust
                new_trust = old_trust * 0.4
                self._update_memory_trust(old_mem.memory_id, new_trust)
                # Increment contradiction_count for compression volatility tracking
                try:
                    c = self._get_connection()
                    c.execute(
                        "UPDATE memories SET contradiction_count = COALESCE(contradiction_count, 0) + 1 WHERE memory_id = ?",
                        (old_mem.memory_id,),
                    )
                    c.commit()
                    c.close()
                except Exception:
                    pass
                logger.info(f"[TRUST_DECAY] Reduced trust for contradicted memory: {old_mem.text[:60]} (trust: {old_trust:.2f} -> {new_trust:.2f})")

        # B: Model disagreement detection — when model_output writes slot values that
        # conflict with existing confirmed user_facts, log a disagreement event.
        # _detect_model_disagreement returns early when no facts are extractable.
        if resolved_source_kind == "model_output":
            self._detect_model_disagreement(memory)

        if active_origin_memories:
            for older in active_origin_memories:
                if older.memory_id == memory.memory_id:
                    continue
                self.deprecate_memory(
                    older.memory_id,
                    reason=f"sync_replaced:{origin}",
                )
                self.record_memory_event(
                    memory_id=older.memory_id,
                    event_type="sync_replaced",
                    actor="system",
                    reason="superseded_by_new_sync_value",
                    metadata={
                        "origin": origin,
                        "thread_id": resolved_thread_id,
                        "replacement_memory_id": memory.memory_id,
                    },
                )
            self.record_memory_event(
                memory_id=memory.memory_id,
                event_type="sync_replaced",
                actor="system",
                reason="activated_latest_sync_value",
                metadata={
                    "origin": origin,
                    "thread_id": resolved_thread_id,
                    "replaced_memory_ids": [m.memory_id for m in active_origin_memories if m.memory_id != memory.memory_id],
                },
            )

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
        excluded_ids: Optional[Set[str]] = None,
        authorities: Optional[Set[str]] = None,
        exclude_authorities: Optional[Set[str]] = None,
        kinds: Optional[Set[str]] = None,
        exclude_kinds: Optional[Set[str]] = None,
        user_id: Optional[str] = None,
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

        # Load all memories — scope to user when available (fall back to context var)
        effective_user_id = user_id or _request_user_id.get(None)
        memories = self._load_all_memories(user_id=effective_user_id)
        
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

        if authorities:
            normalized = {self._normalize_authority(a) for a in authorities}
            memories = [m for m in memories if self._normalize_authority(getattr(m, "authority", None)) in normalized]

        if exclude_authorities:
            normalized = {self._normalize_authority(a) for a in exclude_authorities}
            memories = [m for m in memories if self._normalize_authority(getattr(m, "authority", None)) not in normalized]

        if kinds:
            normalized = {str(k or "").strip().lower() for k in kinds if str(k or "").strip()}
            memories = [m for m in memories if str(getattr(m, "kind", "") or "").strip().lower() in normalized]

        if exclude_kinds:
            normalized = {str(k or "").strip().lower() for k in exclude_kinds if str(k or "").strip()}
            memories = [m for m in memories if str(getattr(m, "kind", "") or "").strip().lower() not in normalized]
        
        if not memories:
            return []

        # Query expansion for question patterns like "what is my favorite color"
        # Expand to include slot-style terms so embedding similarity is higher
        expanded_vectors = [query_vector]
        _question_slot_re = re.compile(
            r"\b(?:what(?:'s| is| are)?\s+(?:my|your)\s+)"    # "what is my"
            r"(?:favorite\s+)?(\w[\w\s]{1,30})\b",            # "favorite color"
            re.IGNORECASE,
        )
        _slot_match = _question_slot_re.search(query)
        if _slot_match:
            slot_phrase = _slot_match.group(1).strip()
            # Build expanded query with slot-name style: "favorite_color orange"
            slot_key = slot_phrase.replace(" ", "_")
            expanded_text = f"{slot_key} {slot_phrase}"
            try:
                expanded_vectors.append(encode_vector(expanded_text))
            except Exception:
                pass

        # Compute scores — tier-aware: fold query to each memory's dimensionality
        t_now = time.time()
        from personal_agent.memory_compression import fold_vector, TIER_DIMS

        # Compression tier fidelity penalty: lower-dim vectors lose
        # information, so we discount their similarity scores.
        _TIER_WEIGHT = {0: 0.85, 1: 0.95, 2: 1.0}

        memory_dicts = []
        for m in memories:
            tier = getattr(m, 'compression_tier', 2)
            best_sim = -1.0
            for qvec in expanded_vectors:
                try:
                    if tier < 2 and m.compressed_vector is not None and len(m.compressed_vector) > 0:
                        # Memory is compressed — fold query to its tier for comparison
                        target_dim = TIER_DIMS.get(tier, 384)
                        folded_query, _ = fold_vector(qvec, target_dim)
                        effective_vector = m.compressed_vector
                        sim = float(np.dot(folded_query, effective_vector) / (
                            np.linalg.norm(folded_query) * np.linalg.norm(effective_vector) + 1e-8
                        ))
                    else:
                        # Full vector — compare directly
                        if m.vector is None or len(m.vector) == 0:
                            continue  # skip malformed memories
                        sim = float(np.dot(qvec, m.vector) / (
                            np.linalg.norm(qvec) * np.linalg.norm(m.vector) + 1e-8
                        ))
                    best_sim = max(best_sim, sim)
                except Exception:
                    continue  # skip any vector shape mismatches

            if best_sim < 0:
                continue  # no valid similarity computed

            # CRT scoring: R = sim * recency * belief_weight * tier_weight
            age = t_now - m.timestamp
            # BUG FIX: Previous lambda of 86400 (1 day) was far too aggressive.
            # Stable facts like "favorite color = orange" become unretrievable
            # after 2-3 days. Use 7-day lambda (604800s) so memories remain
            # discoverable for weeks. A 7-day-old memory gets recency ~0.37
            # instead of the old ~0.0006.
            recency = math.exp(-age / 604800.0)  # 7-day lambda
            belief = 0.7 * m.trust + 0.3 * m.confidence
            tier_weight = _TIER_WEIGHT.get(tier, 1.0)
            score = max(0.0, best_sim) * recency * belief * tier_weight
            memory_dicts.append((m, score))

        # Sort by score descending
        memory_dicts.sort(key=lambda x: x[1], reverse=True)

        # Increment access_count for returned memories
        top_k = memory_dicts[:k]
        try:
            conn = self._get_connection()
            for m, _ in top_k:
                conn.execute(
                    "UPDATE memories SET access_count = COALESCE(access_count, 0) + 1 WHERE memory_id = ?",
                    (m.memory_id,),
                )
            conn.commit()
            conn.close()
        except Exception:
            pass

        return [(m, score) for m, score in top_k]
    
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
        import re
        
        # Derive ledger database path from memory database path
        # Handle multiple naming patterns:
        # 1. 'crt_memory' → 'crt_ledger'
        # 2. 'crt_stress_memory' → 'crt_stress_ledger'
        # 3. Any '*_memory*' → '*_ledger*'
        mem_path = str(self.db_path)
        ledger_path = re.sub(r'_memory', '_ledger', mem_path)
        
        # If no change was made (no '_memory' in path), try simple replacement
        if ledger_path == mem_path:
            ledger_path = mem_path.replace('memory', 'ledger')
        
        ledger_db = Path(ledger_path)
        
        if not ledger_db.exists():
            return False
        
        try:
            conn = sqlite3.connect(str(ledger_db), timeout=5.0, check_same_thread=False)
            conn.execute("PRAGMA busy_timeout=5000")
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT ledger_id FROM contradictions 
                WHERE (old_memory_id = ? OR new_memory_id = ?)
                AND status = 'open'
            """, (memory_id, memory_id))
            
            result = cursor.fetchone()
            conn.close()
            
            return result is not None
        except sqlite3.OperationalError:
            # Table doesn't exist yet - no contradictions
            return False
    
    def deprecate_memory(self, memory_id: str, reason: str = ""):
        """Mark a memory as deprecated (soft-delete).

        Uses the same connection management as other memory operations
        to avoid visibility issues from raw sqlite3.connect() calls.
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE memories SET deprecated = 1, deprecation_reason = ? WHERE memory_id = ?",
            (reason, memory_id),
        )
        conn.commit()
        conn.close()
        logger.info(f"[MEMORY] Deprecated memory {memory_id}: {reason[:80]}")

    def store_memory_facts(self, memory_id: str, facts: Dict[str, Any]) -> None:
        """Cache extracted fact slots for a memory (avoids re-running regex at query time).

        Args:
            memory_id: The memory this fact belongs to.
            facts: Dict mapping slot name -> ExtractedFact (or value).
        """
        if not facts:
            return
        conn = self._get_connection()
        cursor = conn.cursor()
        for slot, fact in facts.items():
            value = getattr(fact, "value", fact) if not isinstance(fact, str) else fact
            normalized = getattr(fact, "normalized", str(value).lower())
            try:
                cursor.execute(
                    "INSERT OR REPLACE INTO memory_facts (memory_id, slot, value, normalized) VALUES (?, ?, ?, ?)",
                    (memory_id, slot, str(value), str(normalized)),
                )
            except Exception as e:
                logger.debug(f"[MEMORY_FACTS] Failed to store fact {slot}={value}: {e}")
        conn.commit()
        conn.close()

    def get_facts_for_slot(self, slot: str, include_deprecated: bool = False) -> List[Tuple[str, str, str]]:
        """Look up all stored values for a given fact slot.

        Returns list of (memory_id, value, normalized) tuples, ordered by
        the memory's timestamp descending (newest first).
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        if include_deprecated:
            cursor.execute("""
                SELECT mf.memory_id, mf.value, mf.normalized
                FROM memory_facts mf
                JOIN memories m ON mf.memory_id = m.memory_id
                WHERE mf.slot = ?
                ORDER BY m.timestamp DESC
            """, (slot,))
        else:
            cursor.execute("""
                SELECT mf.memory_id, mf.value, mf.normalized
                FROM memory_facts mf
                JOIN memories m ON mf.memory_id = m.memory_id
                WHERE mf.slot = ? AND m.deprecated = 0
                ORDER BY m.timestamp DESC
            """, (slot,))
        rows = cursor.fetchall()
        conn.close()
        return rows

    def get_all_facts(self, include_deprecated: bool = False) -> Dict[str, List[Tuple[str, str]]]:
        """Return all cached facts grouped by slot.

        Returns dict: slot -> [(memory_id, value), ...] ordered newest first.
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        if include_deprecated:
            cursor.execute("""
                SELECT mf.slot, mf.memory_id, mf.value
                FROM memory_facts mf
                JOIN memories m ON mf.memory_id = m.memory_id
                ORDER BY m.timestamp DESC
            """)
        else:
            cursor.execute("""
                SELECT mf.slot, mf.memory_id, mf.value
                FROM memory_facts mf
                JOIN memories m ON mf.memory_id = m.memory_id
                WHERE m.deprecated = 0
                ORDER BY m.timestamp DESC
            """)
        rows = cursor.fetchall()
        conn.close()
        result: Dict[str, List[Tuple[str, str]]] = {}
        for slot, mem_id, value in rows:
            result.setdefault(slot, []).append((mem_id, value))
        return result

    def count_memories(self, include_deprecated: bool = False) -> int:
        """Return the number of stored memories (fast SQL count, no data loaded)."""
        conn = self._get_connection()
        cursor = conn.cursor()
        if include_deprecated:
            cursor.execute("SELECT COUNT(*) FROM memories")
        else:
            cursor.execute("SELECT COUNT(*) FROM memories WHERE deprecated = 0")
        count = cursor.fetchone()[0]
        conn.close()
        return count

    def update_trust(
        self,
        memory_id: str,
        new_trust: float,
        reason: str,
        drift: Optional[float] = None
    ):
        """Update trust score and log the change."""
        # Validate input: new_trust must not be None
        if new_trust is None:
            logger.error(f"[TRUST] Attempted to update trust to None for memory {memory_id}. Reason: {reason}. Skipping update.")
            return
        
        # Additional validation: new_trust must be a valid float
        try:
            new_trust = float(new_trust)
            # Check for NaN after conversion
            if np.isnan(new_trust):
                logger.error(f"[TRUST] new_trust is NaN for memory {memory_id}. Reason: {reason}. Skipping update.")
                return
        except (TypeError, ValueError) as e:
            logger.error(f"[TRUST] Invalid new_trust value for memory {memory_id}: {new_trust} ({type(new_trust)}). Error: {e}. Skipping update.")
            return
        
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
        
        # Final validation before UPDATE
        if actual_new_trust is None or (isinstance(actual_new_trust, float) and np.isnan(actual_new_trust)):
            logger.error(f"[TRUST] actual_new_trust is None or NaN after processing for memory {memory_id}. Value: {actual_new_trust}. Skipping update.")
            conn.close()
            return
        
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
    
    def _update_memory_trust(self, memory_id: str, new_trust: float):
        """
        Update trust score for a specific memory in database.
        
        Args:
            memory_id: ID of memory to update
            new_trust: New trust value
        """
        # Validate input: new_trust must not be None
        if new_trust is None:
            logger.error(f"[TRUST] Attempted to update trust to None for memory {memory_id} via _update_memory_trust. Skipping update.")
            return
        
        # Additional validation: new_trust must be a valid float
        try:
            new_trust = float(new_trust)
            # Check for NaN after conversion
            if np.isnan(new_trust):
                logger.error(f"[TRUST] new_trust is NaN for memory {memory_id} via _update_memory_trust. Skipping update.")
                return
        except (TypeError, ValueError) as e:
            logger.error(f"[TRUST] Invalid new_trust value for memory {memory_id}: {new_trust} ({type(new_trust)}). Error: {e}. Skipping update.")
            return
        
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute(
            "UPDATE memories SET trust = ? WHERE memory_id = ?",
            (new_trust, memory_id)
        )
        
        conn.commit()
        conn.close()
    
    def _find_contradicting_memories(self, new_text: str) -> List[MemoryItem]:
        """
        Find memories that contradict the new text.
        
        Args:
            new_text: New memory text to check
            
        Returns:
            List of contradicting memory items
        """
        # Use existing fact extraction to get slot
        from .fact_slots import extract_fact_slots
        
        new_facts = extract_fact_slots(new_text)
        if not new_facts:
            return []
        
        contradicting = []
        
        # Load all user memories to check for contradictions
        all_memories = self._load_all_memories()
        user_memories = [m for m in all_memories if m.source == MemorySource.USER]
        
        # new_facts is Dict[str, ExtractedFact] - keys are slot names
        for slot, new_fact in new_facts.items():
            if not slot:
                continue
            
            # Check each existing memory to see if it has the same slot but different value
            for old_mem in user_memories:
                old_facts = extract_fact_slots(old_mem.text)
                # old_facts is also Dict[str, ExtractedFact]
                if slot in old_facts and old_mem.text != new_text:
                    # Different value for same slot = contradiction
                    contradicting.append(old_mem)
        
        return contradicting

    def _detect_model_disagreement(self, new_memory: MemoryItem) -> None:
        """
        Log a model_disagreement_detected event when a model_output memory's slot values
        conflict with existing confirmed user_facts for the same slot.

        Does NOT auto-promote or override — only logs the event for governance.
        """
        try:
            from .fact_slots import extract_fact_slots
            new_facts = extract_fact_slots(new_memory.text)
            if not new_facts:
                return

            confirmed_memories = [
                m for m in self._load_all_memories()
                if self._normalize_authority(getattr(m, "authority", None)) in {"confirmed", "locked"}
                and getattr(m, "kind", "observation") == "user_fact"
                and not getattr(m, "deprecated", False)
                and m.memory_id != new_memory.memory_id
            ]

            for slot in new_facts:
                for conf_mem in confirmed_memories:
                    conf_facts = extract_fact_slots(conf_mem.text)
                    if slot not in conf_facts:
                        continue
                    new_val = str(new_facts[slot].value).strip().lower()
                    conf_val = str(conf_facts[slot].value).strip().lower()
                    if new_val and conf_val and new_val != conf_val:
                        self._append_memory_event(
                            memory_id=new_memory.memory_id,
                            event_type="model_disagreement_detected",
                            actor=getattr(new_memory, "model_id", None) or "model",
                            reason=f"slot={slot} model={new_val!r} confirmed={conf_val!r}",
                            metadata={
                                "slot": slot,
                                "model_value": new_val,
                                "confirmed_value": conf_val,
                                "confirmed_memory_id": conf_mem.memory_id,
                                "model_id": getattr(new_memory, "model_id", None),
                                "run_id": getattr(new_memory, "run_id", None),
                            },
                        )
                        logger.info(
                            "[MODEL_DISAGREEMENT] slot=%s model=%r confirmed=%r new_id=%s conf_id=%s",
                            slot, new_val, conf_val, new_memory.memory_id, conf_mem.memory_id,
                        )
        except Exception as e:
            logger.debug("[MODEL_DISAGREEMENT] Detection failed: %s", e)

    def try_quiet_promote_ops(
        self,
        memory_id: str,
        *,
        reason: str,
        evidence: Optional[Dict[str, Any]] = None,
        model_id: Optional[str] = None,
        run_id: Optional[str] = None,
    ) -> bool:
        """
        Promote an ops memory from provisional → confirmed without requiring a principal.

        This is the ONLY quiet-promotion path. Restricted to kind=ops.
        Caller must supply a non-empty reason and ideally tool-receipt evidence.

        Returns True if promotion happened, False if it was blocked.
        """
        memory = self.get_memory_by_id(memory_id)
        if memory is None:
            logger.warning("[QUIET_OPS] memory not found: %s", memory_id)
            return False

        if getattr(memory, "kind", "observation") not in _QUIET_PROMOTION_KINDS:
            logger.warning("[QUIET_OPS] blocked: kind=%s not in quiet-promotion allowlist", memory.kind)
            return False

        current = self._normalize_authority(getattr(memory, "authority", None))
        if current != "provisional":
            logger.debug("[QUIET_OPS] skipped: already %s", current)
            return False

        if not str(reason or "").strip():
            logger.warning("[QUIET_OPS] blocked: reason is required")
            return False

        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("UPDATE memories SET authority = 'confirmed' WHERE memory_id = ?", (memory_id,))
        conn.commit()
        conn.close()

        self._append_memory_event(
            memory_id=memory_id,
            event_type="authority_promotion",
            old_authority="provisional",
            new_authority="confirmed",
            actor=model_id or "model_auto",
            reason=reason,
            metadata={
                "promotion_path": "quiet_ops",
                "model_id": model_id,
                "run_id": run_id,
                "evidence": evidence or {},
            },
        )
        logger.info("[QUIET_OPS] promoted ops memory %s: %s", memory_id, reason)
        return True

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
        # Defensive check: if memory.trust is None, initialize to default
        if memory.trust is None:
            logger.warning(f"[TRUST] Memory {memory.memory_id} has None trust, initializing to 0.5")
            memory.trust = 0.5
        
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
        # Defensive check: if memory.trust is None, initialize to default
        if memory.trust is None:
            logger.warning(f"[TRUST] Memory {memory.memory_id} has None trust, initializing to 0.5")
            memory.trust = 0.5
        
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
    # Reasoning Trace Storage (Lazy Loading)
    # ========================================================================
    
    def store_reasoning_trace(
        self,
        query: str,
        thinking_content: str,
        thread_id: Optional[str] = None,
        response_summary: Optional[str] = None,
        model: Optional[str] = None,
        metadata: Optional[Dict] = None
    ) -> str:
        """
        Store full reasoning trace for lazy loading.
        
        Returns trace_id for later retrieval.
        """
        trace_id = f"trace_{int(time.time() * 1000)}_{hash(query) % 10000}"
        
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT INTO reasoning_traces 
            (trace_id, thread_id, query, thinking_content, response_summary, model, timestamp, char_count, metadata_json)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            trace_id,
            thread_id,
            query[:500],  # Truncate query for storage
            thinking_content,  # Full thinking content
            response_summary[:500] if response_summary else None,
            model,
            time.time(),
            len(thinking_content),
            json.dumps(metadata) if metadata else None
        ))
        
        conn.commit()
        conn.close()
        
        logger.debug(f"[REASONING] Stored trace {trace_id} ({len(thinking_content)} chars)")
        return trace_id
    
    def get_reasoning_trace(self, trace_id: str) -> Optional[Dict]:
        """
        Retrieve full reasoning trace by ID.
        
        For lazy loading - only fetch full content when needed.
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT trace_id, thread_id, query, thinking_content, response_summary, 
                   model, timestamp, char_count, metadata_json
            FROM reasoning_traces
            WHERE trace_id = ?
        """, (trace_id,))
        
        row = cursor.fetchone()
        conn.close()
        
        if not row:
            return None
        
        return {
            'trace_id': row[0],
            'thread_id': row[1],
            'query': row[2],
            'thinking_content': row[3],
            'response_summary': row[4],
            'model': row[5],
            'timestamp': row[6],
            'char_count': row[7],
            'metadata': json.loads(row[8]) if row[8] else None
        }
    
    def list_reasoning_traces(
        self,
        thread_id: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
        include_content: bool = False
    ) -> List[Dict]:
        """
        List reasoning traces with pagination.
        
        By default excludes full thinking_content for performance.
        Set include_content=True for full content (lazy load on demand).
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        
        if include_content:
            select_cols = "trace_id, thread_id, query, thinking_content, response_summary, model, timestamp, char_count"
        else:
            # Exclude thinking_content for fast listing
            select_cols = "trace_id, thread_id, query, response_summary, model, timestamp, char_count"
        
        query = f"SELECT {select_cols} FROM reasoning_traces"
        params = []
        
        if thread_id:
            query += " WHERE thread_id = ?"
            params.append(thread_id)
        
        query += " ORDER BY timestamp DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])
        
        cursor.execute(query, params)
        rows = cursor.fetchall()
        conn.close()
        
        traces = []
        for row in rows:
            if include_content:
                traces.append({
                    'trace_id': row[0],
                    'thread_id': row[1],
                    'query': row[2],
                    'thinking_content': row[3],
                    'response_summary': row[4],
                    'model': row[5],
                    'timestamp': row[6],
                    'char_count': row[7]
                })
            else:
                traces.append({
                    'trace_id': row[0],
                    'thread_id': row[1],
                    'query': row[2],
                    'response_summary': row[3],
                    'model': row[4],
                    'timestamp': row[5],
                    'char_count': row[6],
                    # Preview only
                    'thinking_preview': None  # Client must fetch full content separately
                })
        
        return traces
    
    def get_reasoning_trace_count(self, thread_id: Optional[str] = None) -> int:
        """Get total count of reasoning traces for pagination."""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        if thread_id:
            cursor.execute("SELECT COUNT(*) FROM reasoning_traces WHERE thread_id = ?", (thread_id,))
        else:
            cursor.execute("SELECT COUNT(*) FROM reasoning_traces")
        
        count = cursor.fetchone()[0]
        conn.close()
        return count
    
    # ========================================================================
    # Helpers
    # ========================================================================

    def _row_to_memory(self, row: Tuple[Any, ...]) -> MemoryItem:
        """Convert a ``SELECT * FROM memories`` row into ``MemoryItem``."""
        memory = MemoryItem(
            memory_id=row[0],
            vector=np.array(json.loads(row[1])),
            text=row[2],
            timestamp=row[3],
            confidence=row[4],
            trust=row[5],
            source=MemorySource(row[6]),
            sse_mode=SSEMode(row[7]),
            context=json.loads(row[8]) if len(row) > 8 and row[8] else None,
            tags=json.loads(row[9]) if len(row) > 9 and row[9] else None,
            thread_id=row[10] if len(row) > 10 else None,
        )
        if len(row) > 11:
            memory.deprecated = row[11] if row[11] is not None else False
        if len(row) > 12:
            memory.deprecation_reason = row[12]
        if len(row) > 13:
            memory.fact_tuples = row[13]
        if len(row) > 14:
            memory.extraction_method = row[14] if row[14] else 'regex'
        if len(row) > 15:
            memory.temporal_status = row[15] if row[15] else 'active'
        if len(row) > 16:
            memory.valid_from = row[16]
        if len(row) > 17:
            memory.valid_until = row[17]
        if len(row) > 18:
            memory.domain_tags = json.loads(row[18]) if row[18] else None
        if len(row) > 19:
            memory.authority = self._normalize_authority(row[19])
        if len(row) > 20:
            memory.channel = self._normalize_channel(row[20])
        if len(row) > 21:
            memory.origin = row[21]
        if len(row) > 22:
            memory.kind = self._normalize_kind(row[22], source=memory.source, context=memory.context)
        if len(row) > 23:
            memory.review_after = row[23]
        if len(row) > 24:
            memory.source_kind = self._normalize_source_kind(row[24])
        if len(row) > 25:
            memory.model_id = row[25]
        if len(row) > 26:
            memory.run_id = row[26]
        # Adaptive compression fields (columns 27-32)
        if len(row) > 27:
            memory.compression_tier = int(row[27]) if row[27] is not None else 2
        if len(row) > 28 and row[28]:
            try:
                memory.compressed_vector = np.array(json.loads(row[28]), dtype=np.float32)
            except Exception:
                pass
        if len(row) > 29 and row[29]:
            try:
                memory.cogni_seed = json.loads(row[29])
            except Exception:
                pass
        if len(row) > 30:
            memory.stable_cycles = int(row[30]) if row[30] is not None else 0
        if len(row) > 31:
            memory.contradiction_count = int(row[31]) if row[31] is not None else 0
        if len(row) > 32:
            memory.access_count = int(row[32]) if row[32] is not None else 0
        # user_id (column 33 — added AFTER compression columns in migration order)
        if len(row) > 33:
            memory.user_id = row[33]
        return memory
    
    def _load_all_memories(self, user_id: Optional[str] = None) -> List[MemoryItem]:
        """Load all memories from database, scoped to user when available.

        Resolution order for user scope:
        1. Explicit ``user_id`` argument
        2. ``_request_user_id`` context variable (set by route handlers)
        3. No filter (legacy / anonymous — returns everything)
        """
        effective_uid = user_id or _request_user_id.get(None)
        conn = self._get_connection()
        cursor = conn.cursor()

        if effective_uid is not None:
            cursor.execute("SELECT * FROM memories WHERE user_id = ?", (effective_uid,))
        else:
            cursor.execute("SELECT * FROM memories")
        rows = cursor.fetchall()
        conn.close()

        return [self._row_to_memory(row) for row in rows]
    
    def _load_memories_filtered(
        self,
        source: Optional[MemorySource] = None,
        thread_id: Optional[str] = None,
        limit: Optional[int] = None,
        user_id: Optional[str] = None,
    ) -> List[MemoryItem]:
        """
        Load memories with SQL-level filtering to avoid loading entire database.

        Performance optimization: Use this instead of _load_all_memories() when
        you need to filter by source, user, or limit results.

        Args:
            source: Filter by memory source (USER, SYSTEM, etc.)
            thread_id: Filter by thread (kept for backward compat / audit queries)
            limit: Maximum number of results
            user_id: Filter by authenticated user (primary retrieval scope)

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

        # user_id is the primary retrieval scope; thread_id is kept for audit
        effective_uid = user_id or _request_user_id.get(None)
        if effective_uid is not None:
            query += " AND user_id = ?"
            params.append(effective_uid)
        elif thread_id is not None:
            # Backward compat: fall back to thread_id when user_id not available
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

        return [self._row_to_memory(row) for row in rows]
    
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

        return self._row_to_memory(row)
    
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

    def promote_memory(
        self,
        memory_id: str,
        new_authority: str,
        promoted_by: str = "user",
        reason: Optional[str] = None,
        timestamp: Optional[float] = None,
    ) -> MemoryItem:
        """Promote a memory authority level via explicit approval only."""
        target = self._normalize_authority(new_authority)
        if target not in {"confirmed", "locked"}:
            raise ValueError("new_authority must be 'confirmed' or 'locked'")

        memory = self.get_memory_by_id(memory_id)
        if memory is None:
            raise ValueError(f"memory not found: {memory_id}")

        current = self._normalize_authority(getattr(memory, "authority", None))
        if _AUTHORITY_RANK[target] <= _AUTHORITY_RANK[current]:
            raise ValueError(f"cannot promote authority from {current} to {target}")

        when = float(timestamp if timestamp is not None else time.time())
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE memories SET authority = ? WHERE memory_id = ?",
            (target, memory_id),
        )
        conn.commit()
        conn.close()

        self._append_memory_event(
            memory_id=memory_id,
            event_type="authority_promotion",
            old_authority=current,
            new_authority=target,
            actor=promoted_by,
            reason=reason,
            timestamp=when,
            metadata={
                "memory_id": memory_id,
                "promoted_by": promoted_by,
            },
        )

        updated = self.get_memory_by_id(memory_id)
        if updated is None:
            raise ValueError(f"memory disappeared after promotion: {memory_id}")
        return updated

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
        try:
            self.promote_memory(
                memory_id,
                "confirmed",
                promoted_by="user",
                reason="promote_to_belief",
            )
        except Exception:
            pass
        
        return True

    def get_memory_events(self, memory_id: str, event_type: Optional[str] = None) -> List[Dict[str, Any]]:
        """Return append-only event records for a memory."""
        conn = self._get_connection()
        cursor = conn.cursor()
        if event_type:
            cursor.execute(
                """
                SELECT timestamp, event_type, old_authority, new_authority, actor, reason, metadata_json
                FROM memory_events
                WHERE memory_id = ? AND event_type = ?
                ORDER BY timestamp DESC, event_id DESC
                """,
                (memory_id, event_type),
            )
        else:
            cursor.execute(
                """
                SELECT timestamp, event_type, old_authority, new_authority, actor, reason, metadata_json
                FROM memory_events
                WHERE memory_id = ?
                ORDER BY timestamp DESC, event_id DESC
                """,
                (memory_id,),
            )
        rows = cursor.fetchall()
        conn.close()
        out: List[Dict[str, Any]] = []
        for row in rows:
            out.append(
                {
                    "timestamp": row[0],
                    "event_type": row[1],
                    "old_authority": row[2],
                    "new_authority": row[3],
                    "actor": row[4],
                    "reason": row[5],
                    "metadata": json.loads(row[6]) if row[6] else None,
                }
            )
        return out

    def get_memory_usage_summary(
        self,
        *,
        thread_id: Optional[str] = None,
        since_timestamp: Optional[float] = None,
        event_types: Optional[List[str]] = None,
        limit: int = 50,
        exclude_deprecated: bool = True,
    ) -> List[Dict[str, Any]]:
        """Aggregate append-only usage events into per-memory hit counts."""
        normalized_event_types = [
            str(event_type or "").strip()
            for event_type in (event_types or list(_USAGE_EVENT_TYPES))
            if str(event_type or "").strip()
        ]
        if not normalized_event_types:
            return []

        placeholders = ", ".join("?" for _ in normalized_event_types)
        sql = f"""
            SELECT
                me.memory_id,
                m.text,
                m.thread_id,
                m.authority,
                m.channel,
                m.origin,
                m.kind,
                m.trust,
                SUM(CASE WHEN me.event_type = 'retrieved' THEN 1 ELSE 0 END) AS retrieved_hits,
                SUM(CASE WHEN me.event_type = 'prompt_included' THEN 1 ELSE 0 END) AS prompt_included_hits,
                SUM(CASE WHEN me.event_type = 'slot_selected' THEN 1 ELSE 0 END) AS slot_selected_hits,
                SUM(CASE WHEN me.event_type = 'guard_blocked' THEN 1 ELSE 0 END) AS guard_blocked_hits,
                SUM(CASE WHEN me.event_type = 'answer_support' THEN 1 ELSE 0 END) AS answer_support_hits,
                COUNT(*) AS total_hits,
                MAX(me.timestamp) AS last_hit_timestamp
            FROM memory_events me
            JOIN memories m ON m.memory_id = me.memory_id
            WHERE me.event_type IN ({placeholders})
        """
        params: List[Any] = list(normalized_event_types)

        if exclude_deprecated:
            sql += " AND COALESCE(m.deprecated, 0) = 0"

        effective_uid = _request_user_id.get(None)
        if effective_uid is not None:
            sql += " AND m.user_id = ?"
            params.append(effective_uid)
        elif thread_id is not None:
            sql += " AND COALESCE(m.thread_id, '') = ?"
            params.append(str(thread_id))

        if since_timestamp is not None:
            sql += " AND me.timestamp >= ?"
            params.append(float(since_timestamp))

        sql += """
            GROUP BY
                me.memory_id,
                m.text,
                m.thread_id,
                m.authority,
                m.channel,
                m.origin,
                m.kind,
                m.trust
            ORDER BY total_hits DESC, last_hit_timestamp DESC
            LIMIT ?
        """
        params.append(int(limit))

        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute(sql, params)
        rows = cursor.fetchall()
        conn.close()

        out: List[Dict[str, Any]] = []
        for row in rows:
            out.append(
                {
                    "memory_id": row[0],
                    "text": row[1],
                    "thread_id": row[2],
                    "authority": row[3] or "confirmed",
                    "channel": row[4] or "unknown",
                    "origin": row[5],
                    "kind": row[6] or "observation",
                    "trust": float(row[7] or 0.0),
                    "retrieved_hits": int(row[8] or 0),
                    "prompt_included_hits": int(row[9] or 0),
                    "slot_selected_hits": int(row[10] or 0),
                    "guard_blocked_hits": int(row[11] or 0),
                    "answer_support_hits": int(row[12] or 0),
                    "total_hits": int(row[13] or 0),
                    "last_hit_timestamp": float(row[14] or 0.0),
                }
            )
        return out
    
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
            SELECT *
            FROM memories
            WHERE memory_id = ?
        """, (memory_id,))
        
        row = cursor.fetchone()
        conn.close()
        
        if not row:
            return None

        return self._row_to_memory(row)
