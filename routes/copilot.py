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

router = APIRouter(prefix="/api/copilot", tags=["copilot"])

# ---------------------------------------------------------------------------
# DB path resolution
# ---------------------------------------------------------------------------

# Try common locations for the GroundCheck memory DB
_ENV_DB = os.environ.get("GROUNDCHECK_DB", "")
_CANDIDATE_PATHS = [
    *([] if not _ENV_DB else [Path(_ENV_DB)]),
    Path("D:/groundcheck/.groundcheck/memory.db"),
    Path("../.groundcheck/memory.db"),
    Path(".groundcheck/memory.db"),
]


def _find_db() -> Optional[Path]:
    """Return the first existing GroundCheck DB path."""
    for p in _CANDIDATE_PATHS:
        try:
            if p.is_file() and p.stat().st_size > 0:
                return p
        except (OSError, TypeError):
            continue
    return None


def _open_readonly() -> sqlite3.Connection:
    """Open a read-only connection to the GroundCheck DB."""
    db_path = _find_db()
    if not db_path:
        raise HTTPException(
            status_code=503,
            detail="GroundCheck memory database not found. Ensure groundcheck-mcp is configured.",
        )
    uri = f"file:{db_path}?mode=ro"
    conn = sqlite3.connect(uri, uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def _has_column(conn: sqlite3.Connection, table: str, column: str) -> bool:
    """Check if a column exists in a table (handles schema differences)."""
    cols = [r[1] for r in conn.execute(f"PRAGMA table_info({table})").fetchall()]
    return column in cols


def _open_readwrite() -> sqlite3.Connection:
    """Open a read-write connection to the GroundCheck DB."""
    db_path = _find_db()
    if not db_path:
        raise HTTPException(
            status_code=503,
            detail="GroundCheck memory database not found.",
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
    """Return all GroundCheck memories with optional filtering."""
    conn = _open_readonly()
    try:
        has_ns = _has_column(conn, "memories", "namespace")
        ns_col = "namespace" if has_ns else "'default' as namespace"

        # Build query
        where_clauses = ["trust >= ?"]
        params: list = [min_trust]

        if namespace and has_ns:
            where_clauses.append("namespace = ?")
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
        count_sql = f"SELECT COUNT(*) FROM memories WHERE {where_sql}"
        total = conn.execute(count_sql, params).fetchone()[0]

        # Fetch page
        data_sql = f"""
            SELECT id, thread_id, text, trust, source, {ns_col}, timestamp, created_at
            FROM memories
            WHERE {where_sql}
            ORDER BY {order_sql}
            LIMIT ? OFFSET ?
        """
        rows = conn.execute(data_sql, params + [limit, offset]).fetchall()

        memories = [
            CopilotMemory(
                id=r["id"],
                thread_id=r["thread_id"],
                text=r["text"],
                trust=r["trust"],
                source=r["source"] or "unknown",
                namespace=r["namespace"] if has_ns else "default",
                timestamp=r["timestamp"],
                created_at=r["created_at"],
            )
            for r in rows
        ]

        stats = _compute_stats(conn, has_ns)

        return CopilotMemoriesResponse(memories=memories, total=total, stats=stats)

    finally:
        conn.close()


@router.get("/stats", response_model=CopilotStats)
def get_copilot_stats() -> CopilotStats:
    """Return aggregate statistics about GroundCheck memories."""
    conn = _open_readonly()
    try:
        return _compute_stats(conn)
    finally:
        conn.close()


@router.get("/namespaces")
def get_copilot_namespaces() -> List[str]:
    """Return all distinct namespaces in the GroundCheck DB."""
    conn = _open_readonly()
    try:
        if not _has_column(conn, "memories", "namespace"):
            return ["default"]
        rows = conn.execute("SELECT DISTINCT namespace FROM memories ORDER BY namespace").fetchall()
        return [r["namespace"] or "default" for r in rows]
    finally:
        conn.close()


@router.post("/teach")
def teach_copilot(req: TeachRequest) -> Dict[str, Any]:
    """Store a new fact directly from the UI — 'Teach Copilot' feature."""
    conn = _open_readwrite()
    try:
        has_ns = _has_column(conn, "memories", "namespace")
        now = int(time.time())
        mem_id = f"mem_{req.thread_id}_{now}_{hash(req.text) % 10000:04d}"
        created = time.strftime("%Y-%m-%d %H:%M:%S")

        if has_ns:
            conn.execute(
                """INSERT INTO memories (id, thread_id, text, trust, source, timestamp, metadata, namespace, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (mem_id, req.thread_id, req.text, 0.70, req.source, now, "{}", req.namespace, created),
            )
        else:
            conn.execute(
                """INSERT INTO memories (id, thread_id, text, trust, source, timestamp, metadata, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (mem_id, req.thread_id, req.text, 0.70, req.source, now, "{}", created),
            )
        conn.commit()
        return {"ok": True, "memory_id": mem_id, "text": req.text, "trust": 0.70}
    finally:
        conn.close()


@router.delete("/memory/{memory_id}")
def delete_copilot_memory(memory_id: str) -> Dict[str, Any]:
    """Delete a specific memory by ID."""
    conn = _open_readwrite()
    try:
        # Track deletion for accuracy stats
        _track_event(conn, "deletion", memory_id)
        cur = conn.execute("DELETE FROM memories WHERE id = ?", (memory_id,))
        conn.commit()
        if cur.rowcount == 0:
            raise HTTPException(status_code=404, detail="Memory not found")
        return {"ok": True, "deleted": memory_id}
    finally:
        conn.close()


@router.post("/correct")
def correct_copilot_memory(req: CorrectRequest) -> Dict[str, Any]:
    """Correct an existing memory — keeps the old trust, updates text, logs correction."""
    conn = _open_readwrite()
    try:
        row = conn.execute("SELECT * FROM memories WHERE id = ?", (req.memory_id,)).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Memory not found")

        old_text = row["text"]
        conn.execute(
            "UPDATE memories SET text = ?, source = 'user' WHERE id = ?",
            (req.corrected_text, req.memory_id),
        )
        _track_event(conn, "correction", req.memory_id, old_text=old_text, new_text=req.corrected_text)
        conn.commit()
        return {"ok": True, "memory_id": req.memory_id, "old_text": old_text, "new_text": req.corrected_text}
    finally:
        conn.close()


@router.get("/profile", response_model=CopilotProfile)
def get_copilot_profile() -> CopilotProfile:
    """Synthesize a user profile from all stored memories."""
    conn = _open_readonly()
    try:
        rows = conn.execute("SELECT text, trust FROM memories ORDER BY trust DESC, timestamp DESC").fetchall()
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
        total = conn.execute("SELECT COUNT(*) FROM memories").fetchone()[0]
        if total == 0:
            return AccuracyStats()

        # Source counts
        src_rows = conn.execute(
            "SELECT COALESCE(source, 'unknown') as src, COUNT(*) as cnt FROM memories GROUP BY src"
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
        time_row = conn.execute("SELECT MIN(timestamp) as oldest, MAX(timestamp) as newest FROM memories").fetchone()
        oldest = time_row["oldest"] or int(time.time())
        newest = time_row["newest"] or int(time.time())
        days_span = max((newest - oldest) / 86400, 1)
        memories_per_day = round(total / days_span, 2)

        # Learning velocity — memories per hour bucketed
        velocity: List[Dict[str, Any]] = []
        hour_rows = conn.execute(
            """SELECT (timestamp / 3600) * 3600 as hour_bucket, COUNT(*) as cnt,
                      SUM(CASE WHEN source = 'inferred' THEN 1 ELSE 0 END) as auto_cnt
               FROM memories
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
# Internal helpers
# ---------------------------------------------------------------------------

def _compute_stats(conn: sqlite3.Connection, has_ns: Optional[bool] = None) -> CopilotStats:
    """Compute aggregate stats from the full memories table."""
    if has_ns is None:
        has_ns = _has_column(conn, "memories", "namespace")

    total = conn.execute("SELECT COUNT(*) FROM memories").fetchone()[0]

    # Namespaces
    if has_ns:
        ns_rows = conn.execute("SELECT DISTINCT namespace FROM memories ORDER BY namespace").fetchall()
        namespaces = [r["namespace"] or "default" for r in ns_rows]
    else:
        namespaces = ["default"]

    # Source counts
    src_rows = conn.execute(
        "SELECT COALESCE(source, 'unknown') as src, COUNT(*) as cnt FROM memories GROUP BY src"
    ).fetchall()
    source_counts = {r["src"]: r["cnt"] for r in src_rows}

    # Trust distribution buckets
    trust_buckets = {"low (0-0.3)": 0, "medium (0.3-0.6)": 0, "high (0.6-0.8)": 0, "very_high (0.8-1.0)": 0}
    trust_rows = conn.execute(
        """SELECT
             SUM(CASE WHEN trust < 0.3 THEN 1 ELSE 0 END) as low,
             SUM(CASE WHEN trust >= 0.3 AND trust < 0.6 THEN 1 ELSE 0 END) as med,
             SUM(CASE WHEN trust >= 0.6 AND trust < 0.8 THEN 1 ELSE 0 END) as high,
             SUM(CASE WHEN trust >= 0.8 THEN 1 ELSE 0 END) as vhigh
           FROM memories"""
    ).fetchone()
    trust_buckets["low (0-0.3)"] = trust_rows["low"] or 0
    trust_buckets["medium (0.3-0.6)"] = trust_rows["med"] or 0
    trust_buckets["high (0.6-0.8)"] = trust_rows["high"] or 0
    trust_buckets["very_high (0.8-1.0)"] = trust_rows["vhigh"] or 0

    # Auto-learned vs explicit
    auto = source_counts.get("inferred", 0)
    explicit = total - auto

    # Time range
    time_row = conn.execute("SELECT MIN(timestamp) as oldest, MAX(timestamp) as newest FROM memories").fetchone()

    return CopilotStats(
        total_memories=total,
        namespaces=namespaces,
        source_counts=source_counts,
        trust_distribution=trust_buckets,
        auto_learned_count=auto,
        explicit_count=explicit,
        newest_timestamp=time_row["newest"],
        oldest_timestamp=time_row["oldest"],
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
