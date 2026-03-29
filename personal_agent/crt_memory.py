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

    # Geometric memory (Phase G1)
    sigma: Optional[np.ndarray] = None          # Diagonal covariance (384D), None = uninitialized
    belnap_state: str = "true"                  # true | false | both | neither
    memory_type: str = "observation"            # fact | preference | event | belief | identity

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
            'sigma': self.sigma.tolist() if self.sigma is not None else None,
            'belnap_state': self.belnap_state,
            'memory_type': self.memory_type,
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


# ---------------------------------------------------------------------------
# Geometric memory helpers (Phase G1 + G2)
# ---------------------------------------------------------------------------

_KIND_TO_MEMORY_TYPE = {
    "user_fact": "fact",
    "ops": "fact",
    "preference": "preference",
    "identity_constant": "identity",
    "evolution_observation": "belief",
    "evolution_proposal": "belief",
    "hypothesis": "belief",
    "observation": "observation",
    "narrative_note": "belief",
}

# Per-type sigma multipliers (relative to 1/dim base scale).
# Tight = low uncertainty, wide = high uncertainty.
_SIGMA_MULTIPLIERS = {
    "fact": 0.5,
    "preference": 1.5,
    "event": 0.8,
    "belief": 2.0,
    "identity": 1.2,
    "observation": 1.0,
}

_EMBEDDING_DIM = 384  # all-MiniLM-L6-v2


def _kind_to_memory_type(kind: Optional[str]) -> str:
    """Map existing ``kind`` field to geometric memory_type."""
    return _KIND_TO_MEMORY_TYPE.get(kind or "", "observation")


# Recency weight curves by memory type (age_days → weight).
# Matches temporal_governance.py's recency_weight() but inlined for hot-path perf.
_RECENCY_CURVES: Dict[str, tuple] = {
    #              (lambda_days, floor)
    "fact":        (365.0, 0.8),   # nearly flat — facts stay relevant
    "preference":  (90.0,  0.3),   # moderate decay
    "event":       (3.0,   0.1),   # fast decay — events are ephemeral
    "belief":      (365.0, 0.6),   # slow decay
    "identity":    (1e9,   1.0),   # constant — identity never decays
    "observation": (7.0,   0.4),   # default: 7-day half-life
}


def _temporal_recency(age_days: float, memory_type: str) -> float:
    """Type-dependent recency weight for retrieval scoring."""
    lam, floor = _RECENCY_CURVES.get(memory_type, (7.0, 0.4))
    import math as _m
    return max(floor, _m.exp(-age_days / lam))


def _init_sigma(memory_type: str, dim: int = _EMBEDDING_DIM) -> np.ndarray:
    """Initialize diagonal covariance from memory_type.

    Returns a float32 array of shape ``(dim,)`` with type-appropriate spread.
    """
    base_scale = 1.0 / dim
    mult = _SIGMA_MULTIPLIERS.get(memory_type, 1.0)
    return np.full(dim, base_scale * mult, dtype=np.float32)


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
                source TEXT,
                query_embedding BLOB,
                response_embedding BLOB,
                topic_id INTEGER
            )
        """)

        # Opinion/belief variance tracking
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS opinion_topics (
                topic_id INTEGER PRIMARY KEY AUTOINCREMENT,
                label TEXT,
                centroid_embedding BLOB NOT NULL,
                entry_count INTEGER DEFAULT 0,
                first_seen REAL NOT NULL,
                last_seen REAL NOT NULL,
                last_analyzed REAL,
                metrics_json TEXT
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS variance_snapshots (
                snapshot_id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp REAL NOT NULL,
                num_topics INTEGER,
                avg_drift REAL,
                avg_belief_stability REAL,
                avg_speech_entropy REAL,
                global_flip_rate REAL,
                details_json TEXT
            )
        """)
        # Note: belief_speech indexes are created in _migrate_schema() to handle
        # existing DBs where topic_id column doesn't exist yet.

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

        # Phase G2: trajectory snapshots for covariance evolution tracking
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS trajectory_snapshots (
                snapshot_id INTEGER PRIMARY KEY AUTOINCREMENT,
                memory_id TEXT NOT NULL,
                timestamp REAL NOT NULL,
                mu BLOB,
                sigma BLOB,
                alpha REAL,
                total_uncertainty REAL,
                FOREIGN KEY (memory_id) REFERENCES memories(memory_id)
            )
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_trajectory_memory_ts
            ON trajectory_snapshots(memory_id, timestamp DESC)
        """)

        # Alias protection: route-redundancy embeddings for critical memories.
        # Separate table — aliases aren't memories (no trust/confidence/kind).
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS memory_aliases (
                alias_id TEXT PRIMARY KEY,
                memory_id TEXT NOT NULL,
                vector_json TEXT NOT NULL,
                method TEXT NOT NULL,
                created_at REAL NOT NULL,
                FOREIGN KEY (memory_id) REFERENCES memories(memory_id)
            )
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_aliases_memory
            ON memory_aliases(memory_id)
        """)

        conn.commit()

        # Log DB identity on init
        try:
            active = cursor.execute(
                "SELECT COUNT(*) FROM memories WHERE deprecated = 0"
            ).fetchone()[0]
            alias_ct = cursor.execute(
                "SELECT COUNT(*) FROM memory_aliases"
            ).fetchone()[0]
            print(
                "[MEMORY_DB] Initialized: %s (%d active memories, %d aliases)"
                % (self.db_path, active, alias_ct)
            )
        except Exception:
            print("[MEMORY_DB] Initialized: %s" % self.db_path)

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

        # Geometric memory (Phase G1): sigma (diagonal covariance), belnap_state, memory_type
        if "sigma" not in columns:
            logger.info(f"[MIGRATION] Adding geometric memory columns to {self.db_path}")
            cursor.execute("ALTER TABLE memories ADD COLUMN sigma BLOB")
            cursor.execute("ALTER TABLE memories ADD COLUMN belnap_state TEXT DEFAULT 'true'")
            cursor.execute("ALTER TABLE memories ADD COLUMN memory_type TEXT DEFAULT 'observation'")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_memories_belnap_state ON memories(belnap_state)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_memories_memory_type ON memories(memory_type)")

        # --- belief_speech table migrations ---
        cursor.execute("PRAGMA table_info(belief_speech)")
        bs_columns = [row[1] for row in cursor.fetchall()]

        if "query_embedding" not in bs_columns:
            logger.info(f"[MIGRATION] Adding query_embedding to belief_speech in {self.db_path}")
            cursor.execute("ALTER TABLE belief_speech ADD COLUMN query_embedding BLOB")

        if "response_embedding" not in bs_columns:
            logger.info(f"[MIGRATION] Adding response_embedding to belief_speech in {self.db_path}")
            cursor.execute("ALTER TABLE belief_speech ADD COLUMN response_embedding BLOB")

        if "topic_id" not in bs_columns:
            logger.info(f"[MIGRATION] Adding topic_id to belief_speech in {self.db_path}")
            cursor.execute("ALTER TABLE belief_speech ADD COLUMN topic_id INTEGER")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_belief_speech_topic ON belief_speech(topic_id, timestamp)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_belief_speech_timestamp ON belief_speech(timestamp DESC)")

        # Create opinion_topics and variance_snapshots if missing
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS opinion_topics (
                topic_id INTEGER PRIMARY KEY AUTOINCREMENT,
                label TEXT,
                centroid_embedding BLOB NOT NULL,
                entry_count INTEGER DEFAULT 0,
                first_seen REAL NOT NULL,
                last_seen REAL NOT NULL,
                last_analyzed REAL,
                metrics_json TEXT
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS variance_snapshots (
                snapshot_id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp REAL NOT NULL,
                num_topics INTEGER,
                avg_drift REAL,
                avg_belief_stability REAL,
                avg_speech_entropy REAL,
                global_flip_rate REAL,
                details_json TEXT
            )
        """)

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
            # Phase G2: confirming evidence → tighten covariance
            try:
                self._tighten_sigma(existing_id)
            except Exception:
                pass
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
            memory_type=_kind_to_memory_type(kind),
            sigma=_init_sigma(_kind_to_memory_type(kind), dim=vector.shape[0]),
        )

        # Store in database
        conn = self._get_connection()
        cursor = conn.cursor()

        try:
            cursor.execute("""
                INSERT INTO memories
                (memory_id, vector_json, text, timestamp, confidence, trust, source, sse_mode, context_json, fact_tuples, extraction_method, temporal_status, domain_tags, thread_id, authority, channel, origin, kind, review_after, source_kind, model_id, run_id, user_id, sigma, belnap_state, memory_type)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                memory.sigma.tobytes() if memory.sigma is not None else None,
                memory.belnap_state,
                memory.memory_type,
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
                # Phase G2: contradicting evidence → widen covariance
                try:
                    self._widen_sigma(old_mem.memory_id)
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

        # Auto-alias: generate route-redundancy aliases for high-risk memories
        try:
            self.maybe_alias_memory(memory)
        except Exception as e:
            logger.debug("[ALIAS] Auto-alias failed (non-fatal): %s", e)

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
        belnap_include: Optional[Set[str]] = None,
        belnap_exclude: Optional[Set[str]] = None,
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

        # Phase G3: Belnap-aware filtering
        # By default, include all states. Pass belnap_exclude={'both'} to hide
        # contradicted memories, or belnap_include={'true'} to get only clean ones.
        if belnap_include is not None:
            memories = [m for m in memories if getattr(m, "belnap_state", "true") in belnap_include]
        if belnap_exclude is not None:
            memories = [m for m in memories if getattr(m, "belnap_state", "true") not in belnap_exclude]

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
        from personal_agent.memory_compression import (
            fold_vector, TIER_DIMS, dequantize_vector,
        )

        # Compression tier fidelity penalty: lower-fidelity compressed
        # vectors get a slight discount (MemQuant is much less lossy than fold).
        _TIER_WEIGHT = {0: 0.90, 1: 0.97, 2: 1.0}

        memory_dicts = []
        for m in memories:
            tier = getattr(m, 'compression_tier', 2)
            best_sim = -1.0
            for qvec in expanded_vectors:
                try:
                    if tier < 2 and m.compressed_vector is not None and len(m.compressed_vector) > 0:
                        # Compressed memory — detect format and decompress
                        if isinstance(m.cogni_seed, dict) and m.cogni_seed.get("method") == "memquant":
                            # MemQuant: decompress to full 384D, compare directly
                            effective_vector = dequantize_vector(
                                np.array(m.compressed_vector, dtype=np.uint8),
                                m.cogni_seed,
                            )
                        else:
                            # Legacy fold: fold query down to match compressed dim
                            target_dim = TIER_DIMS.get(tier, 384)
                            folded_query, _ = fold_vector(qvec, target_dim)
                            effective_vector = m.compressed_vector
                            sim = float(np.dot(folded_query, effective_vector) / (
                                np.linalg.norm(folded_query) * np.linalg.norm(effective_vector) + 1e-8
                            ))
                            best_sim = max(best_sim, sim)
                            continue
                        sim = float(np.dot(qvec, effective_vector) / (
                            np.linalg.norm(qvec) * np.linalg.norm(effective_vector) + 1e-8
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

            # CRT scoring: R = sim * recency * belief_weight * tier_weight * kind_boost
            age = t_now - m.timestamp
            # Phase G3: type-dependent recency via temporal governance
            # Facts/identity decay slowly; events decay fast; preferences moderate.
            recency = _temporal_recency(age / 86400.0, getattr(m, "memory_type", "observation"))
            belief = 0.7 * m.trust + 0.3 * m.confidence
            tier_weight = _TIER_WEIGHT.get(tier, 1.0)
            # Kind boost: user facts and preferences outrank generic observations.
            # Without this, conversational noise ("What's on your mind?") drowns
            # out structured facts ("Nick lives in Wisconsin") in retrieval.
            _kind = str(getattr(m, "kind", "") or "").strip().lower()
            _KIND_BOOST = {
                "user_fact": 1.4, "preference": 1.3, "narrative_note": 1.25,
                "identity_constant": 1.5,
            }
            kind_boost = _KIND_BOOST.get(_kind, 1.0)
            score = max(0.0, best_sim) * recency * belief * tier_weight * kind_boost
            memory_dicts.append((m, score))

        # ----- Canonical collapse: score alias vectors, merge best per memory_id -----
        alias_boosted_ids: set = set()
        try:
            alias_map = self.load_all_aliases()  # {memory_id: [vec, ...]}
        except Exception:
            alias_map = {}

        if alias_map:
            # Build lookup for memories we already scored (for metadata reuse)
            mem_by_id: Dict[str, MemoryItem] = {m.memory_id: m for m in memories}
            # Track best score per memory_id from canonical pass
            best_scores: Dict[str, float] = {}
            best_items: Dict[str, MemoryItem] = {}
            for m, sc in memory_dicts:
                if m.memory_id not in best_scores or sc > best_scores[m.memory_id]:
                    best_scores[m.memory_id] = sc
                    best_items[m.memory_id] = m

            # Score alias vectors using parent memory metadata
            for mid, alias_vecs in alias_map.items():
                parent = mem_by_id.get(mid)
                if parent is None:
                    continue  # parent was filtered out
                tier = getattr(parent, 'compression_tier', 2)
                age = t_now - parent.timestamp
                recency = _temporal_recency(age / 86400.0, getattr(parent, "memory_type", "observation"))
                belief = 0.7 * parent.trust + 0.3 * parent.confidence
                tier_w = _TIER_WEIGHT.get(tier, 1.0)
                _kind = str(getattr(parent, "kind", "") or "").strip().lower()
                kind_b = _KIND_BOOST.get(_kind, 1.0)
                canonical_score = best_scores.get(mid, -1.0)

                for av in alias_vecs:
                    alias_best_sim = -1.0
                    for qvec in expanded_vectors:
                        try:
                            sim = float(np.dot(qvec, av) / (
                                np.linalg.norm(qvec) * np.linalg.norm(av) + 1e-8
                            ))
                            alias_best_sim = max(alias_best_sim, sim)
                        except Exception:
                            continue
                    if alias_best_sim < 0:
                        continue
                    alias_score = max(0.0, alias_best_sim) * recency * belief * tier_w * kind_b
                    if alias_score > canonical_score and (mid not in best_scores or alias_score > best_scores[mid]):
                        best_scores[mid] = alias_score
                        best_items[mid] = parent
                        alias_boosted_ids.add(mid)

            # Rebuild memory_dicts from merged best-per-id
            memory_dicts = [(best_items[mid], sc) for mid, sc in best_scores.items()]

            if alias_boosted_ids:
                print(
                    "[ALIAS_COLLAPSE] %d aliased memories checked, %d boosted by alias route"
                    % (len(alias_map), len(alias_boosted_ids))
                )

        # Sort by score descending
        memory_dicts.sort(key=lambda x: x[1], reverse=True)

        # Increment access_count for returned memories
        top_k = memory_dicts[:k]

        # --- Retrieval log ---
        if top_k:
            lines = [
                "[RETRIEVAL] query=\"%s\" k=%d results=%d db=%s"
                % (query[:60], k, len(top_k), self.db_path)
            ]
            for idx, (m, sc) in enumerate(top_k[:5]):
                _k = str(getattr(m, "kind", "") or "").strip().lower()
                boosted = "yes" if m.memory_id in alias_boosted_ids else "no"
                lines.append(
                    "[RETRIEVAL]   #%d score=%.3f kind=%s alias_boost=%s: %s"
                    % (idx + 1, sc, _k, boosted, (m.text or "")[:70])
                )
            print("\n".join(lines))
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
    # Alias Protection (Route Redundancy)
    # ========================================================================

    # Risk weights — ported from compression_lab/four_arm_experiment.py
    _KIND_CRITICALITY = {
        "identity_constant": 1.0, "user_fact": 0.9, "narrative_note": 0.75,
        "preference": 0.7, "hypothesis": 0.3, "observation": 0.15,
        "ops": 0.1, "self_model": 0.05,
    }
    _SOURCE_RISK = {
        "USER": 1.0, "EXTERNAL": 0.8, "SYSTEM": 0.3,
        "FALLBACK": 0.1, "REFLECTION": 0.5,
    }

    def compute_memory_risk(self, m: MemoryItem) -> float:
        """Compute retrieval-loss risk score for a memory. Returns [0, 1]."""
        criticality = self._KIND_CRITICALITY.get(
            str(getattr(m, "kind", "") or "").strip().lower(), 0.15
        )
        trust_w = float(getattr(m, "trust", 0.5))
        access_w = min(1.0, getattr(m, "access_count", 0) / 15.0)
        contradiction_w = min(1.0, getattr(m, "contradiction_count", 0) * 0.5)
        source_w = self._SOURCE_RISK.get(
            str(getattr(m, "source", "SYSTEM")).upper(), 0.3
        )
        stability_discount = min(0.3, getattr(m, "stable_cycles", 0) / 100.0)
        risk = (
            0.30 * criticality
            + 0.25 * trust_w
            + 0.15 * access_w
            + 0.10 * contradiction_w
            + 0.10 * source_w
            - 0.10 * stability_discount
        )
        return max(0.0, min(1.0, risk))

    def get_critical_memories(
        self, threshold_percentile: float = 97, user_id: Optional[str] = None,
    ) -> List[MemoryItem]:
        """Return memories whose risk score is above the given percentile."""
        all_mems = self._load_all_memories(user_id=user_id)
        mems = [m for m in all_mems if not m.deprecated]
        if not mems:
            return []
        risks = np.array([self.compute_memory_risk(m) for m in mems])
        threshold = float(np.percentile(risks, threshold_percentile))
        return [m for m, r in zip(mems, risks) if r >= threshold]

    # --- Alias generation ---------------------------------------------------

    def generate_aliases(
        self, memory: MemoryItem, count: int = 2,
    ) -> List[Dict[str, Any]]:
        """Generate paraphrase alias embeddings for a memory.

        Methods:
          terse   — first sentence only
          question — "What about <key phrase>?"
          perturb — noise + renormalize (fallback)
        """
        from personal_agent.embeddings import encode_text

        text = memory.text or ""
        aliases: List[Dict[str, Any]] = []

        # 1) Terse: first sentence
        first_sentence = text.split(".")[0].strip() + "."
        if len(first_sentence) > 15 and first_sentence != text.strip():
            try:
                v = np.array(encode_text(first_sentence), dtype=np.float32)
                aliases.append({
                    "vector": v, "method": "terse",
                })
            except Exception:
                pass

        # 2) Question form
        words = text.split()
        if len(words) > 3:
            skip_first = words[0].lower() in (
                "nick", "nick's", "the", "a", "an", "i", "my",
            )
            key_phrase = " ".join(words[1:6] if skip_first else words[:5])
            question = f"What about {key_phrase}?"
            try:
                v = np.array(encode_text(question), dtype=np.float32)
                aliases.append({
                    "vector": v, "method": "question",
                })
            except Exception:
                pass

        # 3) Perturb fallback — fill remaining slots
        canonical = memory.vector
        while len(aliases) < count and canonical is not None and len(canonical) > 0:
            rng = np.random.RandomState(
                hash(memory.memory_id) % (2**31) + len(aliases)
            )
            noise = rng.randn(len(canonical)).astype(np.float32) * 0.08
            perturbed = canonical + noise
            perturbed = perturbed / (np.linalg.norm(perturbed) + 1e-8)
            aliases.append({
                "vector": perturbed, "method": "perturb",
            })

        return aliases[:count]

    # --- Alias CRUD ---------------------------------------------------------

    def store_aliases(
        self, memory_id: str, aliases: List[Dict[str, Any]],
    ) -> int:
        """Persist alias embeddings. Returns count stored."""
        conn = self._get_connection()
        now = time.time()
        stored = 0
        for a in aliases:
            alias_id = f"alias_{memory_id}_{a['method']}_{int(now*1000)}"
            try:
                conn.execute(
                    "INSERT OR REPLACE INTO memory_aliases "
                    "(alias_id, memory_id, vector_json, method, created_at) "
                    "VALUES (?, ?, ?, ?, ?)",
                    (
                        alias_id,
                        memory_id,
                        json.dumps(a["vector"].tolist()),
                        a["method"],
                        now,
                    ),
                )
                stored += 1
            except Exception as e:
                logger.debug("[ALIAS] Store error for %s: %s", memory_id, e)
        conn.commit()
        conn.close()
        return stored

    def delete_aliases(self, memory_id: str) -> int:
        """Delete all aliases for a memory. Returns count deleted."""
        conn = self._get_connection()
        cursor = conn.execute(
            "DELETE FROM memory_aliases WHERE memory_id = ?", (memory_id,),
        )
        deleted = cursor.rowcount
        conn.commit()
        conn.close()
        return deleted

    def load_all_aliases(self) -> Dict[str, List[np.ndarray]]:
        """Load all alias vectors grouped by memory_id.

        Returns {memory_id: [vector, ...]}
        """
        conn = self._get_connection()
        rows = conn.execute(
            "SELECT memory_id, vector_json FROM memory_aliases"
        ).fetchall()
        conn.close()
        result: Dict[str, List[np.ndarray]] = {}
        for mid, vjson in rows:
            try:
                v = np.array(json.loads(vjson), dtype=np.float32)
                result.setdefault(mid, []).append(v)
            except Exception:
                continue
        return result

    def get_alias_stats(self) -> Dict[str, Any]:
        """Return alias coverage statistics."""
        conn = self._get_connection()
        total_aliases = conn.execute(
            "SELECT COUNT(*) FROM memory_aliases"
        ).fetchone()[0]
        aliased_memories = conn.execute(
            "SELECT COUNT(DISTINCT memory_id) FROM memory_aliases"
        ).fetchone()[0]
        by_method = {}
        for method, cnt in conn.execute(
            "SELECT method, COUNT(*) FROM memory_aliases GROUP BY method"
        ).fetchall():
            by_method[method] = cnt
        conn.close()
        return {
            "total_aliases": total_aliases,
            "aliased_memories": aliased_memories,
            "by_method": by_method,
        }

    # --- Auto-alias + backfill ----------------------------------------------

    # Kinds that always get aliases on store (high-value, route-mismatch-prone)
    _ALIAS_AUTO_KINDS = {"user_fact", "identity_constant", "preference"}

    def maybe_alias_memory(self, memory: MemoryItem) -> int:
        """Generate aliases if memory kind/risk warrants it. Returns aliases created."""
        kind = str(getattr(memory, "kind", "") or "").strip().lower()
        src = getattr(memory, "source", None)
        src_val = getattr(src, "value", str(src)).lower() if src else ""
        # Auto-alias high-value kinds from user/external source
        if kind not in self._ALIAS_AUTO_KINDS or src_val not in ("user", "external"):
            return 0
        aliases = self.generate_aliases(memory, count=2)
        if not aliases:
            return 0
        stored = self.store_aliases(memory.memory_id, aliases)
        if stored:
            logger.info(
                "[ALIAS] Generated %d aliases for %s (risk=%.2f, kind=%s)",
                stored, memory.memory_id, risk,
                getattr(memory, "kind", "unknown"),
            )
        return stored

    def backfill_aliases(
        self, user_id: Optional[str] = None, threshold_percentile: float = 97,
    ) -> Dict[str, Any]:
        """Generate aliases for all critical memories that don't have them yet."""
        critical = self.get_critical_memories(
            threshold_percentile=threshold_percentile, user_id=user_id,
        )
        # Find which already have aliases
        existing = self.load_all_aliases()
        new_count = 0
        skipped = 0
        for m in critical:
            if m.memory_id in existing:
                skipped += 1
                continue
            aliases = self.generate_aliases(m, count=2)
            stored = self.store_aliases(m.memory_id, aliases)
            new_count += stored
            if stored:
                logger.info(
                    "[ALIAS] Backfill: %d aliases for %s (risk=%.2f)",
                    stored, m.memory_id, self.compute_memory_risk(m),
                )
        return {
            "critical_count": len(critical),
            "new_aliases": new_count,
            "skipped_existing": skipped,
        }

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

    # ------------------------------------------------------------------
    # Phase G2: Sigma (covariance) updates
    # ------------------------------------------------------------------

    def _tighten_sigma(self, memory_id: str, learning_rate: float = 0.1) -> None:
        """Shrink covariance (confirming evidence). Called on dedup reinforcement."""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT sigma FROM memories WHERE memory_id = ?", (memory_id,))
        row = cursor.fetchone()
        if row and row[0] is not None:
            sigma = np.frombuffer(row[0], dtype=np.float32).copy()
            sigma *= (1.0 - learning_rate)
            np.maximum(sigma, 1e-8, out=sigma)
            cursor.execute(
                "UPDATE memories SET sigma = ? WHERE memory_id = ?",
                (sigma.tobytes(), memory_id),
            )
            conn.commit()
        conn.close()

    def _widen_sigma(self, memory_id: str, learning_rate: float = 0.15) -> None:
        """Grow covariance (contradicting evidence). Called on contradiction detection."""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT sigma FROM memories WHERE memory_id = ?", (memory_id,))
        row = cursor.fetchone()
        if row and row[0] is not None:
            sigma = np.frombuffer(row[0], dtype=np.float32).copy()
            sigma *= (1.0 + learning_rate)
            cursor.execute(
                "UPDATE memories SET sigma = ? WHERE memory_id = ?",
                (sigma.tobytes(), memory_id),
            )
            conn.commit()
        conn.close()

    def save_trajectory_snapshot(self, memory_id: str) -> None:
        """Save current (mu, sigma, trust) as a trajectory snapshot.

        Called periodically during compression heartbeat to build covariance
        evolution history for predictive contradiction detection.
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT vector_json, sigma, trust FROM memories WHERE memory_id = ?",
            (memory_id,),
        )
        row = cursor.fetchone()
        if not row:
            conn.close()
            return

        mu_blob = None
        sigma_blob = row[1]
        alpha = row[2] if row[2] is not None else 0.5
        total_uncertainty = 0.0

        if row[0]:
            try:
                mu = np.array(json.loads(row[0]), dtype=np.float32)
                mu_blob = mu.tobytes()
            except Exception:
                pass
        if sigma_blob is not None:
            try:
                sigma = np.frombuffer(sigma_blob, dtype=np.float32)
                total_uncertainty = float(np.sum(sigma))
            except Exception:
                pass

        cursor.execute(
            """INSERT INTO trajectory_snapshots
               (memory_id, timestamp, mu, sigma, alpha, total_uncertainty)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (memory_id, time.time(), mu_blob, sigma_blob, alpha, total_uncertainty),
        )
        conn.commit()
        conn.close()

    def get_trajectory_snapshots(
        self, memory_id: str, limit: int = 20,
    ) -> list:
        """Return recent trajectory snapshots for a memory (newest first)."""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute(
            """SELECT timestamp, mu, sigma, alpha, total_uncertainty
               FROM trajectory_snapshots
               WHERE memory_id = ?
               ORDER BY timestamp DESC LIMIT ?""",
            (memory_id, limit),
        )
        rows = cursor.fetchall()
        conn.close()
        snapshots = []
        for ts, mu_blob, sigma_blob, alpha, total_unc in rows:
            snap = {"timestamp": ts, "alpha": alpha, "total_uncertainty": total_unc}
            if mu_blob:
                snap["mu"] = np.frombuffer(mu_blob, dtype=np.float32)
            if sigma_blob:
                snap["sigma"] = np.frombuffer(sigma_blob, dtype=np.float32)
            snapshots.append(snap)
        return snapshots

    def _update_sigma_with_evidence(
        self,
        memory_id: str,
        new_embedding: np.ndarray,
        weight: float = 0.2,
    ) -> None:
        """Bayesian-style sigma update: shift center, adjust covariance by surprise."""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT vector_json, sigma FROM memories WHERE memory_id = ?",
            (memory_id,),
        )
        row = cursor.fetchone()
        if not row or row[1] is None:
            conn.close()
            return

        import math as _math

        mu = np.array(json.loads(row[0]), dtype=np.float32)
        sigma = np.frombuffer(row[1], dtype=np.float32).copy()
        new_emb = np.asarray(new_embedding, dtype=np.float32)

        diff = new_emb - mu
        dist_sq = float(np.sum(diff ** 2))
        expected_dist = float(np.sum(sigma))

        # Shift center toward new evidence
        mu += weight * diff

        surprise_ratio = dist_sq / max(expected_dist, 1e-8)
        if surprise_ratio < 1.0:
            sigma *= (1.0 - 0.05 * weight)
        else:
            widen_factor = min(0.5, 0.1 * _math.log(surprise_ratio + 1))
            sigma *= (1.0 + widen_factor)

        np.maximum(sigma, 1e-8, out=sigma)

        cursor.execute(
            "UPDATE memories SET vector_json = ?, sigma = ? WHERE memory_id = ?",
            (json.dumps(mu.tolist()), sigma.tobytes(), memory_id),
        )
        conn.commit()
        conn.close()

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
        avg_trust: float,
        query_embedding: Optional[bytes] = None,
        response_embedding: Optional[bytes] = None,
    ) -> int:
        """Record response as belief (high trust). Returns entry_id."""
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            INSERT INTO belief_speech
            (timestamp, query, response, is_belief, memory_ids_json, trust_avg, source,
             query_embedding, response_embedding)
            VALUES (?, ?, ?, 1, ?, ?, 'belief', ?, ?)
        """, (time.time(), query, response, json.dumps(memory_ids), avg_trust,
              query_embedding, response_embedding))

        entry_id = cursor.lastrowid
        conn.commit()
        conn.close()
        return entry_id
    
    def record_speech(
        self,
        query: str,
        response: str,
        source: str = "fallback",
        query_embedding: Optional[bytes] = None,
        response_embedding: Optional[bytes] = None,
    ) -> int:
        """Record response as speech (low trust fallback). Returns entry_id."""
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            INSERT INTO belief_speech
            (timestamp, query, response, is_belief, memory_ids_json, trust_avg, source,
             query_embedding, response_embedding)
            VALUES (?, ?, ?, 0, NULL, NULL, ?, ?, ?)
        """, (time.time(), query, response, source,
              query_embedding, response_embedding))

        entry_id = cursor.lastrowid
        conn.commit()
        conn.close()
        return entry_id
    
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
        if len(row) > 29 and row[29]:
            try:
                memory.cogni_seed = json.loads(row[29])
            except Exception:
                pass
        if len(row) > 28 and row[28]:
            try:
                # Detect format: memquant stores uint8 indices, legacy stores float32
                if isinstance(memory.cogni_seed, dict) and memory.cogni_seed.get("method") == "memquant":
                    memory.compressed_vector = np.array(json.loads(row[28]), dtype=np.uint8)
                else:
                    memory.compressed_vector = np.array(json.loads(row[28]), dtype=np.float32)
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
        # Geometric memory (columns 34-36 — sigma BLOB, belnap_state, memory_type)
        if len(row) > 34 and row[34] is not None:
            try:
                memory.sigma = np.frombuffer(row[34], dtype=np.float32)
            except Exception:
                pass
        if len(row) > 35:
            memory.belnap_state = row[35] if row[35] else "true"
        if len(row) > 36:
            memory.memory_type = row[36] if row[36] else "observation"
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
