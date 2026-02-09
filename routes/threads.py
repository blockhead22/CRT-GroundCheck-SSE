"""Threads route module.

Extracted from crt_api.py — thread export, reset, purge, and CRUD endpoints.
Covers both ``/api/thread/`` and ``/api/threads/`` namespaces.
"""

from __future__ import annotations

import logging
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query, Request

from personal_agent.crt_rag import CRTEnhancedRAG
from personal_agent.db_utils import get_db_connection
from personal_agent.user_profile import GlobalUserProfile

from routes.deps import sanitize_thread_id
from routes.models import (
    ContradictionListItem,
    MemoryListItem,
    ThreadCreateRequest,
    ThreadExportResponse,
    ThreadListItem,
    ThreadPurgeMemoriesRequest,
    ThreadPurgeMemoriesResponse,
    ThreadResetRequest,
    ThreadResetResponse,
    ThreadUpdateRequest,
)

logger = logging.getLogger(__name__)

router = APIRouter()


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _get_engine(request: Request, thread_id: str) -> CRTEnhancedRAG:
    return request.app.state.get_engine(thread_id)


def _memory_item_to_dict(mem) -> Dict[str, Any]:
    return {
        "memory_id": getattr(mem, "memory_id", ""),
        "text": getattr(mem, "text", ""),
        "timestamp": float(getattr(mem, "timestamp", 0.0) or 0.0),
        "confidence": float(getattr(mem, "confidence", 0.0) or 0.0),
        "trust": float(getattr(mem, "trust", 0.0) or 0.0),
        "source": getattr(getattr(mem, "source", None), "value", None) or str(getattr(mem, "source", "")),
        "sse_mode": getattr(getattr(mem, "sse_mode", None), "value", None) or str(getattr(mem, "sse_mode", "")),
        "thread_id": getattr(mem, "thread_id", None),
    }


def _list_contradictions(
    engine: CRTEnhancedRAG,
    *,
    include_resolved: bool,
    limit: int,
) -> list[ContradictionListItem]:
    if not include_resolved:
        try:
            entries = engine.ledger.get_open_contradictions(limit=limit)
        except Exception:
            entries = []
        return [ContradictionListItem(**e.to_dict()) for e in entries]

    # Best-effort: read the ledger DB directly to include resolved/accepted.
    db_path = getattr(engine.ledger, "db_path", None)
    if not db_path:
        return []

    try:
        with get_db_connection(str(db_path)) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT ledger_id, timestamp, status, contradiction_type, drift_mean, confidence_delta,
                       summary, query, old_memory_id, new_memory_id
                FROM contradictions
                ORDER BY timestamp DESC
                LIMIT ?
                """,
                (int(limit),),
            )
            rows = cursor.fetchall()
    except Exception:
        return []

    out: list[ContradictionListItem] = []
    for r in rows:
        out.append(
            ContradictionListItem(
                ledger_id=str(r[0]),
                timestamp=float(r[1] or 0.0),
                status=str(r[2] or ""),
                contradiction_type=str(r[3] or ""),
                drift_mean=float(r[4] or 0.0),
                confidence_delta=float(r[5] or 0.0),
                summary=(str(r[6]) if r[6] is not None else None),
                query=(str(r[7]) if r[7] is not None else None),
                old_memory_id=str(r[8] or ""),
                new_memory_id=str(r[9] or ""),
            )
        )
    return out


def _thread_db_paths_map(tid: str) -> Dict[str, Path]:
    root = Path(__file__).resolve().parent.parent
    return {
        "memory": (root / f"personal_agent/crt_memory_{tid}.db"),
        "ledger": (root / f"personal_agent/crt_ledger_{tid}.db"),
    }


def _purge_memory_sources(db_path: Path, sources: list[str]) -> tuple[int, int]:
    """Returns: (deleted_memories, deleted_trust_log)"""
    if not sources:
        return (0, 0)
    norm_sources = [str(s).strip().lower() for s in sources if str(s).strip()]
    norm_sources = [s for s in norm_sources if s]
    if not norm_sources:
        return (0, 0)

    if not db_path.exists() or not db_path.is_file():
        return (0, 0)

    placeholders = ",".join(["?"] * len(norm_sources))
    deleted_memories = 0
    deleted_trust_log = 0

    try:
        with get_db_connection(str(db_path)) as conn:
            cur = conn.cursor()

            # Collect ids to clean up trust_log.
            cur.execute(
                f"SELECT memory_id FROM memories WHERE lower(source) IN ({placeholders})",
                tuple(norm_sources),
            )
            ids = [str(r[0]) for r in cur.fetchall() if r and r[0]]

            if ids:
                id_placeholders = ",".join(["?"] * len(ids))
                cur.execute(
                    f"DELETE FROM trust_log WHERE memory_id IN ({id_placeholders})",
                    tuple(ids),
                )
                deleted_trust_log = int(cur.rowcount or 0)

            cur.execute(
                f"DELETE FROM memories WHERE lower(source) IN ({placeholders})",
                tuple(norm_sources),
            )
            deleted_memories = int(cur.rowcount or 0)

            conn.commit()
    except Exception:
        return (0, 0)

    return (deleted_memories, deleted_trust_log)


# ========================================================================
# Thread Export
# ========================================================================

@router.get("/api/thread/export", response_model=ThreadExportResponse)
def thread_export(
    request: Request,
    thread_id: str = Query(default="default"),
    include_resolved: bool = Query(default=True),
    memories_limit: int = Query(default=2000, ge=1, le=20000),
    contradictions_limit: int = Query(default=2000, ge=1, le=20000),
) -> ThreadExportResponse:
    tid = sanitize_thread_id(thread_id)
    engine = _get_engine(request, tid)

    try:
        mems = engine.memory._load_all_memories()
    except Exception:
        mems = []
    mems.sort(key=lambda m: float(getattr(m, "timestamp", 0.0) or 0.0), reverse=True)
    memories = [MemoryListItem(**_memory_item_to_dict(m)) for m in mems[: int(memories_limit)]]

    contradictions = _list_contradictions(engine, include_resolved=bool(include_resolved), limit=int(contradictions_limit))

    return ThreadExportResponse(
        thread_id=tid,
        generated_at=time.time(),
        memories=memories,
        contradictions=contradictions,
        memories_total=len(mems),
        contradictions_total=len(contradictions),
    )


# ========================================================================
# Tracing
# ========================================================================

@router.post("/api/tracing/enable")
def enable_tracing(
    request: Request,
    thread_id: str = Query(default="default"),
    enabled: bool = Query(default=True),
) -> dict:
    """Enable or disable step tracing for debugging."""
    tid = sanitize_thread_id(thread_id)
    engine = _get_engine(request, tid)

    if hasattr(engine, "enable_tracing"):
        engine.enable_tracing(enabled)
        return {"thread_id": tid, "tracing_enabled": enabled}

    return {"thread_id": tid, "error": "Tracing not available"}


# ========================================================================
# Thread Reset
# ========================================================================

@router.post("/api/thread/reset", response_model=ThreadResetResponse)
def thread_reset(request: Request, req: ThreadResetRequest) -> ThreadResetResponse:
    tid = sanitize_thread_id(req.thread_id)

    # Drop cached engine first to avoid holding references.
    engines = request.app.state.engines
    engines.pop(tid, None)

    target = (req.target or "all").strip().lower()
    if target not in {"memory", "ledger", "all"}:
        target = "all"

    paths = _thread_db_paths_map(tid)
    deleted: Dict[str, bool] = {}

    def _delete_path(name: str) -> None:
        p = paths[name]
        try:
            if p.exists() and p.is_file():
                p.unlink()
                deleted[name] = True
            else:
                deleted[name] = False
        except Exception:
            deleted[name] = False

    if target in {"memory", "all"}:
        _delete_path("memory")
        # Also purge this thread's entries from the GLOBAL user profile
        # to prevent phantom data from bleeding into new sessions.
        try:
            profile = GlobalUserProfile()
            profile_deleted = profile.clear_thread_data(tid)
            deleted["profile_entries"] = profile_deleted > 0
        except Exception as e:
            logger.warning(f"[THREAD_RESET] Failed to clear profile for thread {tid}: {e}")
            deleted["profile_entries"] = False
    if target in {"ledger", "all"}:
        _delete_path("ledger")

    return ThreadResetResponse(thread_id=tid, target=target, deleted=deleted, ok=True)


# ========================================================================
# Thread Purge Memories
# ========================================================================

@router.post("/api/thread/purge_memories", response_model=ThreadPurgeMemoriesResponse)
def thread_purge_memories(request: Request, req: ThreadPurgeMemoriesRequest) -> ThreadPurgeMemoriesResponse:
    tid = sanitize_thread_id(req.thread_id)

    # Require explicit confirmation.
    if not bool(req.confirm):
        return ThreadPurgeMemoriesResponse(
            thread_id=tid,
            sources=list(req.sources or []),
            confirm=False,
            deleted_memories=0,
            deleted_trust_log=0,
            ok=False,
        )

    # Drop cached engine first to avoid holding references and to ensure re-open.
    engines = request.app.state.engines
    engines.pop(tid, None)

    sources = [str(s) for s in (req.sources or [])]
    paths = _thread_db_paths_map(tid)
    deleted_memories, deleted_trust_log = _purge_memory_sources(paths["memory"], sources)

    return ThreadPurgeMemoriesResponse(
        thread_id=tid,
        sources=sources,
        confirm=True,
        deleted_memories=deleted_memories,
        deleted_trust_log=deleted_trust_log,
        ok=True,
    )


# ========================================================================
# Thread Management (CRUD)
# ========================================================================

@router.get("/api/threads", response_model=list[ThreadListItem])
def list_threads(request: Request) -> list[ThreadListItem]:
    """List all threads with basic metadata."""
    engines = request.app.state.engines
    result = []
    for tid in engines.keys():
        result.append(ThreadListItem(
            id=tid,
            title=tid.replace("_", " ").title(),
            updated_at=time.time(),
            message_count=0,
        ))
    # Always include 'default' if not present
    if not any(t.id == "default" for t in result):
        result.insert(0, ThreadListItem(
            id="default",
            title="Default Thread",
            updated_at=time.time(),
            message_count=0,
        ))
    return result


@router.post("/api/threads", response_model=ThreadListItem)
def create_thread(request: Request, req: ThreadCreateRequest) -> ThreadListItem:
    """Create a new thread."""
    thread_id = str(uuid.uuid4())[:8]
    tid = sanitize_thread_id(thread_id)

    # Initialize engine for this thread (creates DBs)
    _get_engine(request, tid)

    return ThreadListItem(
        id=tid,
        title=req.title,
        updated_at=time.time(),
        message_count=0,
    )


@router.put("/api/threads/{thread_id}", response_model=ThreadListItem)
def update_thread(request: Request, thread_id: str, req: ThreadUpdateRequest) -> ThreadListItem:
    """Update thread metadata (e.g., title)."""
    tid = sanitize_thread_id(thread_id)

    # Ensure thread exists
    _get_engine(request, tid)

    return ThreadListItem(
        id=tid,
        title=req.title,
        updated_at=time.time(),
        message_count=0,
    )


@router.delete("/api/threads/{thread_id}")
def delete_thread(request: Request, thread_id: str) -> dict:
    """Delete a thread and its associated data."""
    tid = sanitize_thread_id(thread_id)

    if tid == "default":
        raise HTTPException(status_code=400, detail="Cannot delete default thread")

    # Remove from engines cache
    engines = request.app.state.engines
    turn_counters = request.app.state.turn_counters
    if tid in engines:
        del engines[tid]
    if tid in turn_counters:
        del turn_counters[tid]

    # Delete the DB files
    memory_db, ledger_db = request.app.state.thread_db_paths(tid)
    try:
        if Path(memory_db).exists():
            Path(memory_db).unlink()
        if Path(ledger_db).exists():
            Path(ledger_db).unlink()
    except Exception:
        # Log but don't fail on DB deletion errors
        pass

    return {"ok": True, "thread_id": tid, "deleted": True}
