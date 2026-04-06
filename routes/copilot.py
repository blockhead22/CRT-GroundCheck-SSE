"""Copilot Interactions route — serves GroundCheck MCP memory data.

Reads the GroundCheck SQLite database directly (read-only for queries,
write for teach/delete/correct) to expose memories, stats, and namespaces
to the frontend Copilot Interactions page.
"""

from __future__ import annotations

import logging
import math
import os
import sqlite3
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Active Learning bridge (lazy import to avoid circular deps)
# ---------------------------------------------------------------------------

def _notify_active_learning_correction(
    memory_id: str, old_text: str, new_text: str
) -> None:
    """Forward a memory correction to the ActiveLearningCoordinator."""
    try:
        from personal_agent.active_learning import get_active_learning_coordinator
        coordinator = get_active_learning_coordinator()
        coordinator.record_conflict_resolution(
            thread_id="copilot",
            old_fact=old_text,
            new_fact=new_text,
            user_action="corrected",
            ledger_id=memory_id,
            context="copilot_ui_correction",
            auto_resolved=False,
        )
        logger.info("[COPILOT] Forwarded correction to active learning: %s", memory_id)
    except Exception as e:
        logger.warning("[COPILOT] Could not notify active learning of correction: %s", e)


def _notify_active_learning_deletion(memory_id: str, deleted_text: str) -> None:
    """Forward a memory deletion to the ActiveLearningCoordinator."""
    try:
        from personal_agent.active_learning import get_active_learning_coordinator
        coordinator = get_active_learning_coordinator()
        coordinator.record_conflict_resolution(
            thread_id="copilot",
            old_fact=deleted_text,
            new_fact="",
            user_action="deleted",
            ledger_id=memory_id,
            context="copilot_ui_deletion",
            auto_resolved=False,
        )
        logger.info("[COPILOT] Forwarded deletion to active learning: %s", memory_id)
    except Exception as e:
        logger.warning("[COPILOT] Could not notify active learning of deletion: %s", e)

router = APIRouter(prefix="/api/copilot", tags=["copilot"])

# ---------------------------------------------------------------------------
# DB path resolution
# ---------------------------------------------------------------------------

# Mirror the engine's shared-memory logic: when CRT_SHARED_MEMORY=true all
# threads use crt_memory_shared.db; otherwise fall back to crt_memory.db.
_ENV_DB = os.environ.get("GROUNDCHECK_DB", "")
_SHARED_MEMORY = os.environ.get("CRT_SHARED_MEMORY", "false").lower() == "true"


def _candidate_paths() -> list:
    """Return ordered DB candidates, respecting CRT_SHARED_MEMORY."""
    candidates = []
    if _ENV_DB:
        candidates.append(Path(_ENV_DB))
    if _SHARED_MEMORY:
        candidates.append(Path("personal_agent/crt_memory_shared.db"))
    candidates += [
        Path("personal_agent/crt_memory_shared.db"),  # prefer shared if it has data
        Path("personal_agent/crt_memory.db"),
        Path("data/crt_memory.db"),
        Path("../personal_agent/crt_memory.db"),
        # GroundCheck MCP DB (fallback)
        Path("D:/groundcheck/.groundcheck/memory.db"),
        Path("../.groundcheck/memory.db"),
        Path(".groundcheck/memory.db"),
    ]
    return candidates


def _find_db() -> Optional[Path]:
    """Return the first existing memory DB path."""
    for p in _candidate_paths():
        try:
            if p.is_file() and p.stat().st_size > 0:
                return p
        except (OSError, TypeError):
            continue
    return None


def _engine_db_path(thread_id: str = "default") -> str:
    """Return the DB path the engine would use for this thread_id."""
    if _SHARED_MEMORY:
        return "personal_agent/crt_memory_shared.db"
    from personal_agent.text_utils import sanitize_thread_id
    tid = sanitize_thread_id(thread_id)
    return f"personal_agent/crt_memory_{tid}.db"


def _has_column(conn: sqlite3.Connection, table: str, column: str) -> bool:
    """Check if a column exists in a table (handles schema differences)."""
    cols = [r[1] for r in conn.execute(f"PRAGMA table_info({table})").fetchall()]
    return column in cols


def _is_crt_schema(conn: sqlite3.Connection) -> bool:
    """Return True if the DB uses CRT memory schema (memory_id PK instead of id)."""
    return _has_column(conn, "memories", "memory_id")


class _DBAdapter:
    """Thin schema-normalisation wrapper so query code stays readable."""

    def __init__(self, conn: sqlite3.Connection) -> None:
        self.conn = conn
        self.crt = _is_crt_schema(conn)
        # Primary key column name
        self.id_col = "memory_id" if self.crt else "id"
        # Namespace substitute: CRT uses 'kind', GroundCheck has 'namespace'
        self.has_ns = _has_column(conn, "memories", "namespace")
        self.has_kind = _has_column(conn, "memories", "kind")
        # Alive-rows clause (CRT has deprecated flag)
        self.alive = "AND (deprecated IS NULL OR deprecated = 0)" if self.crt else ""

    def ns_select_expr(self) -> str:
        """SQL expression that returns a namespace-like value."""
        if self.has_ns:
            return "namespace"
        if self.has_kind:
            return "COALESCE(kind, 'default') AS namespace"
        return "'default' AS namespace"

    def ts_expr(self) -> str:
        """SQL expression for timestamp as integer seconds."""
        if self.crt:
            return "CAST(timestamp AS INTEGER) AS timestamp"
        return "timestamp"

    def created_at_expr(self) -> str:
        if _has_column(self.conn, "memories", "created_at"):
            return "created_at"
        if self.crt:
            return "datetime(timestamp, 'unixepoch') AS created_at"
        return "NULL AS created_at"


def _open_readonly() -> sqlite3.Connection:
    """Open a read-only connection to the memory DB."""
    db_path = _find_db()
    if not db_path:
        raise HTTPException(
            status_code=503,
            detail="Memory database not found. Start the CRT backend or configure GROUNDCHECK_DB.",
        )
    # CRT DB needs write access for WAL; open read-only only for GroundCheck DB
    try:
        uri = f"file:{db_path}?mode=ro"
        conn = sqlite3.connect(uri, uri=True)
        conn.row_factory = sqlite3.Row
        return conn
    except sqlite3.OperationalError:
        # Fall back to read-write if read-only mode fails (e.g. WAL without -shm)
        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row
        return conn


def _open_readwrite() -> sqlite3.Connection:
    """Open a read-write connection to the memory DB."""
    db_path = _find_db()
    if not db_path:
        raise HTTPException(
            status_code=503,
            detail="Memory database not found.",
        )
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    return conn


# ---------------------------------------------------------------------------
# Response models
# ---------------------------------------------------------------------------

class CopilotMemory(BaseModel):
    id: str
    thread_id: str
    text: str
    trust: float
    source: str
    namespace: str
    timestamp: int
    created_at: Optional[str] = None


class CopilotStats(BaseModel):
    total_memories: int = 0
    namespaces: List[str] = Field(default_factory=list)
    source_counts: Dict[str, int] = Field(default_factory=dict)
    trust_distribution: Dict[str, int] = Field(default_factory=dict)
    auto_learned_count: int = 0
    explicit_count: int = 0
    newest_timestamp: Optional[int] = None
    oldest_timestamp: Optional[int] = None


class CopilotMemoriesResponse(BaseModel):
    memories: List[CopilotMemory]
    total: int
    stats: CopilotStats


class TeachRequest(BaseModel):
    text: str = Field(min_length=1, description="The fact to teach Copilot")
    source: str = Field(default="user", description="Source label")
    namespace: str = Field(default="default")
    thread_id: str = Field(default="default")


class CorrectRequest(BaseModel):
    memory_id: str = Field(description="ID of memory to correct")
    corrected_text: str = Field(min_length=1, description="The corrected fact text")


class CopilotProfile(BaseModel):
    """Synthesized profile from all memories."""
    name: Optional[str] = None
    role: Optional[str] = None
    employer: Optional[str] = None
    languages: List[str] = Field(default_factory=list)
    preferences: Dict[str, str] = Field(default_factory=dict)
    all_facts: List[str] = Field(default_factory=list)


class AccuracyStats(BaseModel):
    total_memories: int = 0
    corrections_made: int = 0
    deletions_made: int = 0
    auto_learned: int = 0
    explicit: int = 0
    accuracy_rate: float = 1.0  # 1.0 = perfect, lower = more corrections
    trust_avg: float = 0.0
    memories_per_day: float = 0.0
    learning_velocity: List[Dict[str, Any]] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.get("/memories", response_model=CopilotMemoriesResponse)
def get_copilot_memories(
    namespace: Optional[str] = Query(None, description="Filter by namespace"),
    source: Optional[str] = Query(None, description="Filter by source (user/inferred/document/code)"),
    search: Optional[str] = Query(None, description="Text search filter"),
    min_trust: float = Query(0.0, ge=0.0, le=1.0, description="Minimum trust threshold"),
    limit: int = Query(200, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    sort: str = Query("newest", description="Sort order: newest, oldest, trust_high, trust_low"),
) -> CopilotMemoriesResponse:
    """Return all CRT/GroundCheck memories with optional filtering."""
    conn = _open_readonly()
    try:
        db = _DBAdapter(conn)

        # Build WHERE clauses
        where_clauses = [f"trust >= ?"]
        params: list = [min_trust]
        if db.alive:
            where_clauses.append(db.alive.lstrip("AND ").strip())

        if namespace:
            if db.has_ns:
                where_clauses.append("namespace = ?")
                params.append(namespace)
            elif db.has_kind:
                where_clauses.append("kind = ?")
                params.append(namespace)
        if source:
            where_clauses.append("source = ?")
            params.append(source)
        if search:
            where_clauses.append("text LIKE ?")
            params.append(f"%{search}%")

        where_sql = " AND ".join(where_clauses)

        order_map = {
            "newest": "timestamp DESC",
            "oldest": "timestamp ASC",
            "trust_high": "trust DESC, timestamp DESC",
            "trust_low": "trust ASC, timestamp DESC",
        }
        order_sql = order_map.get(sort, "timestamp DESC")

        # Count total matching
        total = conn.execute(f"SELECT COUNT(*) FROM memories WHERE {where_sql}", params).fetchone()[0]

        # Fetch page
        ns_expr = db.ns_select_expr()
        ts_expr = db.ts_expr()
        ca_expr = db.created_at_expr()
        id_col = db.id_col
        data_sql = f"""
            SELECT {id_col} AS id, COALESCE(thread_id, 'default') AS thread_id,
                   text, trust, COALESCE(source, 'unknown') AS source,
                   {ns_expr}, {ts_expr}, {ca_expr}
            FROM memories
            WHERE {where_sql}
            ORDER BY {order_sql}
            LIMIT ? OFFSET ?
        """
        rows = conn.execute(data_sql, params + [limit, offset]).fetchall()

        memories = [
            CopilotMemory(
                id=r["id"],
                thread_id=r["thread_id"] or "default",
                text=r["text"],
                trust=float(r["trust"]),
                source=r["source"] or "unknown",
                namespace=r["namespace"] if "namespace" in r.keys() else "default",
                timestamp=int(r["timestamp"]),
                created_at=r["created_at"],
            )
            for r in rows
        ]

        stats = _compute_stats(conn, db)

        return CopilotMemoriesResponse(memories=memories, total=total, stats=stats)

    finally:
        conn.close()


@router.get("/stats", response_model=CopilotStats)
def get_copilot_stats() -> CopilotStats:
    """Return aggregate statistics about CRT memories."""
    conn = _open_readonly()
    try:
        return _compute_stats(conn, _DBAdapter(conn))
    finally:
        conn.close()


@router.get("/namespaces")
def get_copilot_namespaces() -> List[str]:
    """Return all distinct namespaces / kinds in the memory DB."""
    conn = _open_readonly()
    try:
        db = _DBAdapter(conn)
        alive = db.alive
        if db.has_ns:
            rows = conn.execute(f"SELECT DISTINCT namespace FROM memories WHERE 1=1 {alive} ORDER BY namespace").fetchall()
            return [r["namespace"] or "default" for r in rows]
        if db.has_kind:
            rows = conn.execute(f"SELECT DISTINCT kind FROM memories WHERE 1=1 {alive} ORDER BY kind").fetchall()
            return [r["kind"] or "default" for r in rows]
        return ["default"]
    finally:
        conn.close()


@router.post("/teach")
def teach_copilot(req: TeachRequest) -> Dict[str, Any]:
    """Store a new fact directly from the UI — 'Teach Copilot' feature.

    For the CRT native DB, delegates to CRTMemorySystem so embeddings and
    metadata are stored correctly.  Falls back to raw SQL for the GroundCheck DB.
    """
    # Try CRT system first (preferred path)
    try:
        from personal_agent.crt_memory import CRTMemorySystem, MemorySource
        from personal_agent.crt_core import encode_vector

        db_path = _engine_db_path(req.thread_id)
        crt = CRTMemorySystem(db_path)
        source_map = {
            "user": MemorySource.USER,
            "inferred": MemorySource.INFERENCE,
            "document": MemorySource.DOCUMENT,
        }
        src = source_map.get(req.source, MemorySource.USER)
        vector = encode_vector(req.text)
        mem_id = crt.store_memory(
            text=req.text,
            vector=vector,
            source=src,
            confidence=0.85,
            trust=0.70,
            thread_id=req.thread_id,
            kind="user_fact",
            authority="confirmed",
            channel="webchat",
        )
        logger.info("[COPILOT] Stored fact via CRTMemorySystem: %s", mem_id)
        return {"ok": True, "memory_id": mem_id, "text": req.text, "trust": 0.70, "via": "crt"}
    except Exception as crt_exc:
        logger.debug("[COPILOT] CRTMemorySystem teach failed (%s) — falling back to raw SQL", crt_exc)

    # Raw SQL fallback (GroundCheck schema)
    conn = _open_readwrite()
    try:
        db = _DBAdapter(conn)
        now_ts = time.time()
        now_int = int(now_ts)
        mem_id = f"mem_{req.thread_id}_{now_int}_{hash(req.text) % 10000:04d}"
        created = time.strftime("%Y-%m-%d %H:%M:%S")

        if db.crt:
            conn.execute(
                """INSERT INTO memories
                   (memory_id, thread_id, text, trust, confidence, source, timestamp,
                    vector_json, sse_mode, kind, authority)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (mem_id, req.thread_id, req.text, 0.70, 0.85, req.source, now_ts,
                 "[]", "H", req.namespace or "user_fact", "confirmed"),
            )
        elif db.has_ns:
            conn.execute(
                """INSERT INTO memories
                   (id, thread_id, text, trust, source, timestamp, metadata, namespace, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (mem_id, req.thread_id, req.text, 0.70, req.source, now_int, "{}", req.namespace, created),
            )
        else:
            conn.execute(
                """INSERT INTO memories
                   (id, thread_id, text, trust, source, timestamp, metadata, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (mem_id, req.thread_id, req.text, 0.70, req.source, now_int, "{}", created),
            )
        conn.commit()
        return {"ok": True, "memory_id": mem_id, "text": req.text, "trust": 0.70, "via": "raw_sql"}
    finally:
        conn.close()


@router.delete("/memory/{memory_id}")
def delete_copilot_memory(memory_id: str) -> Dict[str, Any]:
    """Delete (or soft-deprecate) a specific memory by ID."""
    conn = _open_readwrite()
    try:
        db = _DBAdapter(conn)
        row = conn.execute(
            f"SELECT text FROM memories WHERE {db.id_col} = ?", (memory_id,)
        ).fetchone()
        deleted_text = row["text"] if row else ""

        _track_event(conn, "deletion", memory_id)

        if db.crt:
            # CRT is append-only — soft-delete via deprecated flag
            cur = conn.execute(
                "UPDATE memories SET deprecated = 1, deprecation_reason = 'user_deleted' WHERE memory_id = ?",
                (memory_id,),
            )
        else:
            cur = conn.execute("DELETE FROM memories WHERE id = ?", (memory_id,))

        conn.commit()
        if cur.rowcount == 0:
            raise HTTPException(status_code=404, detail="Memory not found")

        _notify_active_learning_deletion(memory_id, deleted_text)
        return {"ok": True, "deleted": memory_id}
    finally:
        conn.close()


@router.post("/correct")
def correct_copilot_memory(req: CorrectRequest) -> Dict[str, Any]:
    """Correct an existing memory — CRT drift-aware trust evolution + fact classification."""
    conn = _open_readwrite()
    try:
        db = _DBAdapter(conn)
        row = conn.execute(
            f"SELECT * FROM memories WHERE {db.id_col} = ?", (req.memory_id,)
        ).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Memory not found")

        old_text = row["text"]
        conn.execute(
            f"UPDATE memories SET text = ?, source = 'user' WHERE {db.id_col} = ?",
            (req.corrected_text, req.memory_id),
        )
        _track_event(conn, "correction", req.memory_id, old_text=old_text, new_text=req.corrected_text)
        conn.commit()

        # Forward to active learning (non-blocking)
        _notify_active_learning_correction(req.memory_id, old_text, req.corrected_text)

        # CRT drift-aware trust boost + fact classification
        change_type = "unknown"
        crt_used = False
        try:
            from personal_agent.crt_core import CRTMath, CRTConfig, MemorySource, encode_vector
            crt = CRTMath(CRTConfig())

            # Classify the type of change
            change_type = crt.classify_fact_change(
                slot="",
                value_new=req.corrected_text,
                value_prior=old_text,
                text_new=req.corrected_text,
                text_prior=old_text,
            )

            # Check if this memory is safe to train on after correction
            current_trust = float(row["trust"] if row["trust"] is not None else 0.7)
            trainable, train_reason = crt.can_train_on_memory(
                trust=current_trust,
                has_open_contradiction=False,
                source=MemorySource.USER,
            )

            # Drift-aware reinforcement
            from personal_agent.trust_decay import reinforce_memory
            reinforce_memory(
                req.memory_id,
                context_text=req.corrected_text,
                is_correction=True,
            )
            crt_used = True
        except Exception as exc:
            import logging
            logging.getLogger(__name__).warning("[COPILOT] CRT correction failed: %s", exc, exc_info=True)
            # Flat fallback
            try:
                from personal_agent.trust_decay import reinforce_memory, CORRECTION_BOOST
                reinforce_memory(req.memory_id, boost=CORRECTION_BOOST)
            except Exception:
                pass

        return {
            "ok": True,
            "memory_id": req.memory_id,
            "old_text": old_text,
            "new_text": req.corrected_text,
            "change_type": change_type,
            "crt_drift_aware": crt_used,
        }
    finally:
        conn.close()


@router.get("/profile", response_model=CopilotProfile)
def get_copilot_profile() -> CopilotProfile:
    """Synthesize a user profile from all stored memories."""
    conn = _open_readonly()
    try:
        db = _DBAdapter(conn)
        alive = db.alive
        # Only extract profile from user_fact/preference memories — not observations,
        # model_output, or self_model entries which contain LLM-generated text that
        # pollutes the profile with hallucinated values.
        rows = conn.execute(
            f"""SELECT text, trust FROM memories
                WHERE 1=1 {alive}
                AND COALESCE(kind, 'observation') IN ('user_fact', 'preference', 'identity_constant')
                AND text NOT LIKE '%[SYSTEM NOTE%'
                ORDER BY trust DESC, timestamp DESC"""
        ).fetchall()
        texts = [r["text"] for r in rows]

        profile = CopilotProfile(all_facts=texts)

        for text in texts:
            tl = text.lower()
            # Name extraction
            if profile.name is None:
                for pattern in ["user's name is ", "name is ", "my name is "]:
                    if pattern in tl:
                        profile.name = text[tl.index(pattern) + len(pattern):].strip().rstrip(".")
                        break

            # Role / employer
            if "freelancer" in tl or "freelance" in tl:
                profile.role = "Freelancer"
            if profile.employer is None:
                for pattern in ["works at ", "work at ", "employed at ", "employer is "]:
                    if pattern in tl:
                        profile.employer = text[tl.index(pattern) + len(pattern):].strip().rstrip(".")
                        break

            # Languages
            for pattern in ["programming language is ", "code in ", "codes in ", "writes in "]:
                if pattern in tl:
                    langs_raw = text[tl.index(pattern) + len(pattern):].strip().rstrip(".")
                    for lang in langs_raw.replace(" and ", ", ").split(", "):
                        lang = lang.strip()
                        if lang and lang not in profile.languages:
                            profile.languages.append(lang)

            # Preferences (favorite_*)
            if "favorite" in tl:
                parts = tl.split("favorite", 1)
                if len(parts) == 2:
                    rest = parts[1].strip()
                    if " is " in rest:
                        slot, val = rest.split(" is ", 1)
                        slot = slot.strip()
                        val_orig = text[text.lower().index(" is " + val) + 4:].strip().rstrip(".")
                        profile.preferences[f"favorite_{slot}"] = val_orig

            # Likes
            for pattern in ["likes ", "loves ", "enjoys "]:
                if tl.startswith(pattern) or f"user {pattern}" in tl or f"nick {pattern}" in tl:
                    idx = tl.index(pattern) + len(pattern)
                    val = text[idx:].strip().rstrip(".")
                    if val:
                        profile.preferences[f"likes"] = val

        return profile
    finally:
        conn.close()


@router.get("/accuracy", response_model=AccuracyStats)
def get_accuracy_stats() -> AccuracyStats:
    """Return accuracy and learning velocity stats."""
    conn = _open_readonly()
    try:
        db = _DBAdapter(conn)
        alive = db.alive
        total = conn.execute(f"SELECT COUNT(*) FROM memories WHERE 1=1 {alive}").fetchone()[0]
        if total == 0:
            return AccuracyStats()

        # Source counts
        src_rows = conn.execute(
            f"SELECT COALESCE(source, 'unknown') as src, COUNT(*) as cnt FROM memories WHERE 1=1 {alive} GROUP BY src"
        ).fetchall()
        source_counts = {r["src"]: r["cnt"] for r in src_rows}
        auto = source_counts.get("inferred", 0)
        explicit = total - auto

        # Trust average
        avg_row = conn.execute("SELECT AVG(trust) as avg_trust FROM memories").fetchone()
        trust_avg = round(avg_row["avg_trust"] or 0, 3)

        # Event tracking
        corrections = 0
        deletions = 0
        has_events = _has_table(conn, "copilot_events")
        if has_events:
            ev_rows = conn.execute(
                "SELECT event_type, COUNT(*) as cnt FROM copilot_events GROUP BY event_type"
            ).fetchall()
            for r in ev_rows:
                if r["event_type"] == "correction":
                    corrections = r["cnt"]
                elif r["event_type"] == "deletion":
                    deletions = r["cnt"]

        # Accuracy: total facts ever created vs corrections+deletions
        total_ever = total + deletions
        accuracy = round(1.0 - ((corrections + deletions) / max(total_ever, 1)), 3)

        # Time range and velocity
        time_row = conn.execute(
            f"SELECT MIN(timestamp) as oldest, MAX(timestamp) as newest FROM memories WHERE 1=1 {alive}"
        ).fetchone()
        oldest = float(time_row["oldest"] or time.time())
        newest = float(time_row["newest"] or time.time())
        days_span = max((newest - oldest) / 86400, 1)
        memories_per_day = round(total / days_span, 2)

        # Learning velocity — memories per hour bucketed
        velocity: List[Dict[str, Any]] = []
        hour_rows = conn.execute(
            f"""SELECT (CAST(timestamp AS INTEGER) / 3600) * 3600 as hour_bucket,
                      COUNT(*) as cnt,
                      SUM(CASE WHEN source = 'inferred' THEN 1 ELSE 0 END) as auto_cnt
               FROM memories
               WHERE 1=1 {alive}
               GROUP BY hour_bucket
               ORDER BY hour_bucket"""
        ).fetchall()
        for r in hour_rows:
            velocity.append({
                "timestamp": r["hour_bucket"],
                "count": r["cnt"],
                "auto_learned": r["auto_cnt"],
                "label": time.strftime("%b %d %H:%M", time.localtime(r["hour_bucket"])),
            })

        return AccuracyStats(
            total_memories=total,
            corrections_made=corrections,
            deletions_made=deletions,
            auto_learned=auto,
            explicit=explicit,
            accuracy_rate=accuracy,
            trust_avg=trust_avg,
            memories_per_day=memories_per_day,
            learning_velocity=velocity,
        )
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Pending fact-checks endpoint
# ---------------------------------------------------------------------------

@router.get("/fact-checks")
def get_fact_checks(
    thread_id: Optional[str] = Query(None),
    limit: int = Query(10, ge=1, le=50),
) -> List[Dict[str, Any]]:
    """Return pending fact-check findings from auto verification."""
    try:
        from personal_agent.auto_fact_checker import get_pending_fact_checks
        return get_pending_fact_checks(thread_id=thread_id, limit=limit)
    except ImportError:
        return []
    except Exception as e:
        logger.warning("[COPILOT] Error fetching fact checks: %s", e)
        return []


@router.post("/fact-checks/{check_id}/resolve")
def resolve_fact_check_endpoint(check_id: str) -> Dict[str, Any]:
    """Mark a pending fact-check as resolved."""
    try:
        from personal_agent.auto_fact_checker import resolve_fact_check
        ok = resolve_fact_check(check_id, resolution="user_resolved")
        if not ok:
            raise HTTPException(status_code=404, detail="Fact check not found")
        return {"ok": True, "resolved": check_id}
    except ImportError:
        raise HTTPException(status_code=501, detail="Auto fact-checker not available")
    except HTTPException:
        raise
    except Exception as e:
        logger.warning("[COPILOT] Error resolving fact check: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _compute_stats(conn: sqlite3.Connection, db: Optional["_DBAdapter"] = None) -> CopilotStats:
    """Compute aggregate stats from the memories table."""
    if db is None:
        db = _DBAdapter(conn)
    alive = db.alive

    total = conn.execute(f"SELECT COUNT(*) FROM memories WHERE 1=1 {alive}").fetchone()[0]

    # Namespaces / kinds
    if db.has_ns:
        ns_rows = conn.execute(f"SELECT DISTINCT namespace FROM memories WHERE 1=1 {alive} ORDER BY namespace").fetchall()
        namespaces = [r["namespace"] or "default" for r in ns_rows]
    elif db.has_kind:
        ns_rows = conn.execute(f"SELECT DISTINCT kind FROM memories WHERE 1=1 {alive} ORDER BY kind").fetchall()
        namespaces = [r["kind"] or "default" for r in ns_rows]
    else:
        namespaces = ["default"]

    # Source counts
    src_rows = conn.execute(
        f"SELECT COALESCE(source, 'unknown') as src, COUNT(*) as cnt FROM memories WHERE 1=1 {alive} GROUP BY src"
    ).fetchall()
    source_counts = {r["src"]: r["cnt"] for r in src_rows}

    # Trust distribution buckets
    trust_buckets = {"low (0-0.3)": 0, "medium (0.3-0.6)": 0, "high (0.6-0.8)": 0, "very_high (0.8-1.0)": 0}
    trust_rows = conn.execute(
        f"""SELECT
             SUM(CASE WHEN trust < 0.3 THEN 1 ELSE 0 END) as low,
             SUM(CASE WHEN trust >= 0.3 AND trust < 0.6 THEN 1 ELSE 0 END) as med,
             SUM(CASE WHEN trust >= 0.6 AND trust < 0.8 THEN 1 ELSE 0 END) as high,
             SUM(CASE WHEN trust >= 0.8 THEN 1 ELSE 0 END) as vhigh
           FROM memories WHERE 1=1 {alive}"""
    ).fetchone()
    trust_buckets["low (0-0.3)"] = trust_rows["low"] or 0
    trust_buckets["medium (0.3-0.6)"] = trust_rows["med"] or 0
    trust_buckets["high (0.6-0.8)"] = trust_rows["high"] or 0
    trust_buckets["very_high (0.8-1.0)"] = trust_rows["vhigh"] or 0

    # Auto-learned vs explicit
    auto = source_counts.get("inferred", 0)
    explicit = total - auto

    # Time range
    time_row = conn.execute(
        f"SELECT MIN(timestamp) as oldest, MAX(timestamp) as newest FROM memories WHERE 1=1 {alive}"
    ).fetchone()

    return CopilotStats(
        total_memories=total,
        namespaces=namespaces,
        source_counts=source_counts,
        trust_distribution=trust_buckets,
        auto_learned_count=auto,
        explicit_count=explicit,
        newest_timestamp=int(time_row["newest"]) if time_row["newest"] else None,
        oldest_timestamp=int(time_row["oldest"]) if time_row["oldest"] else None,
    )


def _has_table(conn: sqlite3.Connection, table: str) -> bool:
    """Check if a table exists."""
    row = conn.execute(
        "SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name=?", (table,)
    ).fetchone()
    return row[0] > 0


def _track_event(
    conn: sqlite3.Connection,
    event_type: str,
    memory_id: str,
    old_text: str = "",
    new_text: str = "",
) -> None:
    """Log a correction/deletion event for accuracy tracking."""
    conn.execute(
        """CREATE TABLE IF NOT EXISTS copilot_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            event_type TEXT NOT NULL,
            memory_id TEXT NOT NULL,
            old_text TEXT DEFAULT '',
            new_text TEXT DEFAULT '',
            timestamp INTEGER NOT NULL
        )"""
    )
    conn.execute(
        "INSERT INTO copilot_events (event_type, memory_id, old_text, new_text, timestamp) VALUES (?, ?, ?, ?, ?)",
        (event_type, memory_id, old_text, new_text, int(time.time())),
    )


# ===========================================================================
# Active Learning endpoints
# ===========================================================================

@router.get("/learning/stats")
def get_learning_stats() -> Dict[str, Any]:
    """Return active learning system statistics."""
    try:
        from personal_agent.active_learning import get_active_learning_coordinator
        coordinator = get_active_learning_coordinator()
        stats = coordinator.get_stats(force_refresh=True)
        return stats.to_dict()
    except ImportError:
        raise HTTPException(status_code=501, detail="Active learning module not available")
    except Exception as e:
        logger.warning("[COPILOT] Error fetching learning stats: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/learning/corrections")
def get_learning_corrections(
    limit: int = Query(10, ge=1, le=100),
) -> List[Dict[str, Any]]:
    """Return recent user corrections for dashboard display."""
    try:
        from personal_agent.active_learning import get_active_learning_coordinator
        coordinator = get_active_learning_coordinator()
        return coordinator.get_recent_corrections(limit=limit)
    except ImportError:
        return []
    except Exception as e:
        logger.warning("[COPILOT] Error fetching corrections: %s", e)
        return []


@router.get("/learning/events")
def get_learning_events(
    limit: int = Query(50, ge=1, le=200),
) -> List[Dict[str, Any]]:
    """Return gate events that haven't been corrected yet (for labeling UI)."""
    try:
        from personal_agent.active_learning import get_active_learning_coordinator
        coordinator = get_active_learning_coordinator()
        return coordinator.get_events_needing_correction(limit=limit)
    except ImportError:
        return []
    except Exception as e:
        logger.warning("[COPILOT] Error fetching events: %s", e)
        return []


class FeedbackThumbsRequest(BaseModel):
    interaction_id: str
    thumbs_up: bool
    comment: Optional[str] = None


@router.post("/learning/feedback")
def submit_learning_feedback(req: FeedbackThumbsRequest) -> Dict[str, Any]:
    """Submit thumbs up/down feedback for an interaction."""
    try:
        from personal_agent.active_learning import get_active_learning_coordinator
        coordinator = get_active_learning_coordinator()
        ok = coordinator.record_feedback_thumbs(
            interaction_id=req.interaction_id,
            thumbs_up=req.thumbs_up,
            comment=req.comment,
        )
        return {"ok": ok}
    except ImportError:
        raise HTTPException(status_code=501, detail="Active learning module not available")
    except Exception as e:
        logger.warning("[COPILOT] Error submitting feedback: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


class FeedbackCorrectionRequest(BaseModel):
    interaction_id: str
    correction_type: str
    field_name: Optional[str] = None
    incorrect_value: Optional[str] = None
    correct_value: Optional[str] = None
    user_comment: Optional[str] = None


@router.post("/learning/correct")
def submit_learning_correction(req: FeedbackCorrectionRequest) -> Dict[str, Any]:
    """Submit a correction for an interaction."""
    try:
        from personal_agent.active_learning import get_active_learning_coordinator
        coordinator = get_active_learning_coordinator()
        correction_id = coordinator.record_feedback_correction(
            interaction_id=req.interaction_id,
            correction_type=req.correction_type,
            field_name=req.field_name,
            incorrect_value=req.incorrect_value,
            correct_value=req.correct_value,
            user_comment=req.user_comment,
        )
        return {"ok": True, "correction_id": correction_id}
    except ImportError:
        raise HTTPException(status_code=501, detail="Active learning module not available")
    except Exception as e:
        logger.warning("[COPILOT] Error submitting correction: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/learning/interaction-stats")
def get_interaction_stats(
    hours: int = Query(24, ge=1, le=720),
) -> Dict[str, Any]:
    """Return interaction statistics for the last N hours."""
    try:
        from personal_agent.active_learning import get_active_learning_coordinator
        coordinator = get_active_learning_coordinator()
        return coordinator.get_interaction_stats(hours=hours)
    except ImportError:
        return {"total_interactions": 0, "period_hours": hours}
    except Exception as e:
        logger.warning("[COPILOT] Error fetching interaction stats: %s", e)
        return {"total_interactions": 0, "period_hours": hours}


@router.post("/learning/retrain")
def trigger_retrain() -> Dict[str, Any]:
    """Manually trigger model retraining."""
    try:
        from personal_agent.active_learning import get_active_learning_coordinator
        coordinator = get_active_learning_coordinator()
        coordinator._trigger_training()
        return {"ok": True, "message": "Retraining triggered"}
    except ImportError:
        raise HTTPException(status_code=501, detail="Active learning module not available")
    except Exception as e:
        logger.warning("[COPILOT] Error triggering retrain: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


# ===========================================================================
# Episodic Memory endpoints
# ===========================================================================

@router.get("/preferences")
def get_preferences(
    category: Optional[str] = Query(None),
) -> List[Dict[str, Any]]:
    """Return learned user preferences from episodic memory."""
    try:
        from personal_agent.episodic_memory import get_episodic_manager
        manager = get_episodic_manager()
        prefs = manager.db.get_preferences(category=category)
        return [p.to_dict() for p in prefs]
    except ImportError:
        return []
    except Exception as e:
        logger.warning("[COPILOT] Error fetching preferences: %s", e)
        return []


@router.get("/sessions")
def get_session_summaries(
    thread_id: Optional[str] = Query(None),
    limit: int = Query(10, ge=1, le=100),
) -> List[Dict[str, Any]]:
    """Return recent session summaries from episodic memory."""
    try:
        from personal_agent.episodic_memory import get_episodic_manager
        manager = get_episodic_manager()
        summaries = manager.db.get_recent_summaries(thread_id=thread_id, limit=limit)
        return [s.to_dict() for s in summaries]
    except ImportError:
        return []
    except Exception as e:
        logger.warning("[COPILOT] Error fetching sessions: %s", e)
        return []


@router.get("/sessions/search")
def search_sessions(
    topic: str = Query(..., min_length=1),
    limit: int = Query(10, ge=1, le=100),
) -> List[Dict[str, Any]]:
    """Search session summaries by topic keyword."""
    try:
        from personal_agent.episodic_memory import get_episodic_manager
        manager = get_episodic_manager()
        summaries = manager.db.search_summaries_by_topic(topic, limit=limit)
        return [s.to_dict() for s in summaries]
    except ImportError:
        return []
    except Exception as e:
        logger.warning("[COPILOT] Error searching sessions: %s", e)
        return []


@router.get("/patterns")
def get_interaction_patterns(
    pattern_type: Optional[str] = Query(None),
    min_confidence: float = Query(0.3, ge=0.0, le=1.0),
) -> List[Dict[str, Any]]:
    """Return detected behavioral patterns from episodic memory."""
    try:
        from personal_agent.episodic_memory import get_episodic_manager
        manager = get_episodic_manager()
        patterns = manager.db.get_patterns(pattern_type=pattern_type, min_confidence=min_confidence)
        return [p.to_dict() for p in patterns]
    except ImportError:
        return []
    except Exception as e:
        logger.warning("[COPILOT] Error fetching patterns: %s", e)
        return []


@router.get("/concepts")
def get_concepts(
    concept_type: Optional[str] = Query(None, description="Filter by type: person, project, organization, topic, location"),
) -> List[Dict[str, Any]]:
    """Return known entities/concepts from the knowledge graph."""
    try:
        from personal_agent.episodic_memory import get_episodic_manager
        manager = get_episodic_manager()
        if concept_type:
            concepts = manager.db.get_concepts_by_type(concept_type)
        else:
            # Return all types
            all_concepts = []
            for ct in ["person", "project", "organization", "topic", "location"]:
                all_concepts.extend(manager.db.get_concepts_by_type(ct))
            concepts = sorted(all_concepts, key=lambda c: c.mention_count, reverse=True)
        return [c.to_dict() for c in concepts]
    except ImportError:
        return []
    except Exception as e:
        logger.warning("[COPILOT] Error fetching concepts: %s", e)
        return []


@router.get("/concepts/search")
def search_concept(
    name: str = Query(..., min_length=1),
) -> Optional[Dict[str, Any]]:
    """Search for a specific concept/entity by name or alias."""
    try:
        from personal_agent.episodic_memory import get_episodic_manager
        manager = get_episodic_manager()
        concept = manager.db.find_concept_by_name(name)
        if concept:
            return concept.to_dict()
        return None
    except ImportError:
        return None
    except Exception as e:
        logger.warning("[COPILOT] Error searching concept: %s", e)
        return None


@router.get("/user-context")
def get_user_context(
    include_summaries: int = Query(3, ge=0, le=20),
) -> Dict[str, Any]:
    """Return comprehensive user context from episodic memory.

    Includes preferences, patterns, session summaries, concepts,
    and the pre-built context prompt string.
    """
    try:
        from personal_agent.episodic_memory import get_episodic_manager
        manager = get_episodic_manager()
        context = manager.get_user_context(include_summaries=include_summaries)
        context["context_prompt"] = manager.build_context_prompt()
        return context
    except ImportError:
        return {"preferences": {}, "patterns": [], "recent_summaries": [], "concepts": [], "context_prompt": ""}
    except Exception as e:
        logger.warning("[COPILOT] Error fetching user context: %s", e)
        return {"preferences": {}, "patterns": [], "recent_summaries": [], "concepts": [], "context_prompt": ""}


# ===========================================================================
# Trust Decay & Scheduler endpoints
# ===========================================================================

@router.get("/trust-decay/config")
def get_trust_decay_config() -> Dict[str, Any]:
    """Return trust decay tuning parameters."""
    try:
        from personal_agent.trust_decay import (
            DECAY_RATE, REINFORCE_BOOST, CORRECTION_BOOST,
            TRUST_FLOOR, TRUST_CEILING, GRACE_PERIOD_DAYS,
            MIN_PASS_INTERVAL_SECS,
        )
        return {
            "decay_rate": DECAY_RATE,
            "reinforce_boost": REINFORCE_BOOST,
            "correction_boost": CORRECTION_BOOST,
            "trust_floor": TRUST_FLOOR,
            "trust_ceiling": TRUST_CEILING,
            "grace_period_days": GRACE_PERIOD_DAYS,
            "min_pass_interval_secs": MIN_PASS_INTERVAL_SECS,
        }
    except ImportError:
        raise HTTPException(status_code=501, detail="Trust decay module not available")


@router.post("/trust-decay/run")
def run_trust_decay() -> Dict[str, Any]:
    """Manually trigger a trust decay pass."""
    try:
        from personal_agent.trust_decay import run_trust_decay_pass
        return run_trust_decay_pass()
    except ImportError:
        raise HTTPException(status_code=501, detail="Trust decay module not available")
    except Exception as e:
        logger.warning("[COPILOT] Error running trust decay: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/memory/{memory_id}/reinforce")
def reinforce_memory_endpoint(memory_id: str) -> Dict[str, Any]:
    """Manually boost a memory's trust score (reinforcement)."""
    try:
        from personal_agent.trust_decay import reinforce_memory, REINFORCE_BOOST
        # trust_decay.reinforce_memory now auto-detects CRT vs GroundCheck schema
        ok = reinforce_memory(memory_id, boost=REINFORCE_BOOST)
        if not ok:
            raise HTTPException(status_code=404, detail="Memory not found")
        return {"ok": True, "memory_id": memory_id, "boost": REINFORCE_BOOST}
    except ImportError:
        raise HTTPException(status_code=501, detail="Trust decay module not available")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/memory/{memory_id}/trust-history")
def get_memory_trust_history(memory_id: str, limit: int = 40) -> Dict[str, Any]:
    """Return trust evolution history for a single memory (for sparkline rendering)."""
    try:
        crt = CRTMemorySystem(_engine_db_path())
        rows = crt.get_trust_history(memory_id)
        # Oldest-first for sparkline (ascending time)
        rows = list(reversed(rows))[-limit:]
        return {"memory_id": memory_id, "history": rows}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/self-audit")
def get_self_audit() -> Dict[str, Any]:
    """Run verified self-audit and return comprehensive health report."""
    try:
        from personal_agent.verified_self_audit import run_verified_self_audit
        report = run_verified_self_audit()
        return report.to_dict()
    except Exception as e:
        logger.warning("[COPILOT] Self-audit failed: %s", e)
        return {"error": str(e), "overall_health": 0.0}


@router.get("/scheduler/status")
def get_scheduler_status() -> Dict[str, Any]:
    """Return idle scheduler status and configuration."""
    try:
        import json as _json
        from pathlib import Path as _Path
        config_path = _Path("crt_runtime_config.json")
        if config_path.exists():
            with open(config_path, encoding='utf-8') as f:
                config = _json.load(f)
            bg = config.get("background_jobs", {})
            return {
                "enabled": bg.get("idle_scheduler_enabled", False),
                "auto_learning_enabled": bg.get("auto_learning_enabled", False),
                "auto_resolve_contradictions": bg.get("auto_resolve_idle_contradictions", False),
                "idle_seconds": bg.get("idle_scheduler_idle_seconds", 120),
                "interval_seconds": bg.get("idle_scheduler_interval_seconds", 10),
            }
        return {"enabled": False, "note": "Config file not found"}
    except Exception as e:
        logger.warning("[COPILOT] Error fetching scheduler status: %s", e)
        return {"enabled": False, "error": str(e)}


@router.post("/scheduler/tick")
def force_scheduler_tick() -> Dict[str, Any]:
    """Force a single scheduler tick (admin/debug)."""
    try:
        # The scheduler is wired into the background worker, so we run
        # the relevant pieces directly
        results: Dict[str, Any] = {"triggered": []}

        # Trust decay
        try:
            from personal_agent.trust_decay import run_trust_decay_pass
            import personal_agent.trust_decay as td
            td._last_decay_ts = 0.0  # Force run
            decay_result = run_trust_decay_pass()
            results["trust_decay"] = decay_result
            results["triggered"].append("trust_decay")
        except ImportError:
            results["trust_decay"] = "not_available"

        return results
    except Exception as e:
        logger.warning("[COPILOT] Error in scheduler tick: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


# ===========================================================================
# Reflection & Training Data endpoints
# ===========================================================================

@router.get("/reflections/{thread_id}")
def get_reflections(
    thread_id: str,
    limit: int = Query(50, ge=1, le=200),
) -> List[Dict[str, Any]]:
    """Return reflection traces for a thread."""
    try:
        from personal_agent.reflection_system import ReflectionDB
        db = ReflectionDB("data/reflection_traces.db")
        return db.get_thread_reflections(thread_id, limit=limit)
    except ImportError:
        return []
    except Exception as e:
        logger.warning("[COPILOT] Error fetching reflections: %s", e)
        return []


@router.get("/training-data/stats")
def get_training_data_stats() -> Dict[str, Any]:
    """Return training data collection statistics."""
    try:
        from personal_agent.reflection_system import TrainingDataCollector
        collector = TrainingDataCollector()
        return collector.get_stats()
    except ImportError:
        return {"total_reflections": 0, "total_requeries": 0, "total_preferences": 0}
    except Exception as e:
        logger.warning("[COPILOT] Error fetching training stats: %s", e)
        return {"total_reflections": 0, "total_requeries": 0, "total_preferences": 0}


@router.get("/training-data/export")
def export_training_data(
    format: str = Query("jsonl", description="Export format: jsonl or json"),
) -> Dict[str, Any]:
    """Export collected training data for fine-tuning."""
    try:
        from personal_agent.reflection_system import TrainingDataCollector
        collector = TrainingDataCollector()
        data = collector.export_for_training(format=format)
        return {"format": format, "data": data}
    except ImportError:
        raise HTTPException(status_code=501, detail="Reflection system not available")
    except Exception as e:
        logger.warning("[COPILOT] Error exporting training data: %s", e)
        raise HTTPException(status_code=500, detail=str(e))
