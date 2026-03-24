"""Slot discovery API routes — view and manage learned slot profiles."""

from __future__ import annotations

import time
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Body, HTTPException, Path, Query

router = APIRouter(prefix="/api/slots", tags=["slot-discovery"])


@router.get("/profiles")
def list_slot_profiles(
    thread_id: Optional[str] = Query(None, description="Thread ID (for DB path resolution)"),
) -> List[Dict[str, Any]]:
    """Return all learned slot profiles with types and confidence."""
    from personal_agent.slot_discovery import load_all_profiles, _get_db_path

    db = _resolve_discovery_db(thread_id)
    profiles = load_all_profiles(db_path=db)
    return [_profile_to_dict(p) for p in profiles]


@router.get("/profiles/{slot_name}")
def get_slot_profile(
    slot_name: str = Path(..., description="Slot name"),
    thread_id: Optional[str] = Query(None, description="Thread ID"),
) -> Dict[str, Any]:
    """Return specific slot profile."""
    from personal_agent.slot_discovery import load_slot_profile

    db = _resolve_discovery_db(thread_id)
    profile = load_slot_profile(slot_name.strip().lower(), db_path=db)
    if not profile:
        raise HTTPException(status_code=404, detail=f"No profile found for slot '{slot_name}'")
    return _profile_to_dict(profile)


@router.post("/analyze")
def trigger_analysis(
    thread_id: Optional[str] = Query(None, description="Thread ID"),
) -> Dict[str, Any]:
    """Trigger a discovery pass manually, returns results."""
    from personal_agent.slot_discovery import run_discovery_pass

    memory_db, ledger_db = _resolve_memory_and_ledger_db(thread_id)
    discovery_db = _resolve_discovery_db(thread_id)

    result = run_discovery_pass(
        memory_db_path=memory_db,
        ledger_db_path=ledger_db,
        discovery_db_path=discovery_db,
    )
    return result


@router.put("/profiles/{slot_name}/override")
def override_slot_type(
    slot_name: str = Path(..., description="Slot name"),
    body: Dict[str, Any] = Body(...),
    thread_id: Optional[str] = Query(None, description="Thread ID"),
) -> Dict[str, Any]:
    """Manually override a slot type."""
    from personal_agent.slot_discovery import (
        SlotType, SlotProfile, load_slot_profile, save_slot_profile,
        _get_db_path, _ensure_tables, _log_reclassification,
    )

    new_type_str = body.get("type", "").strip().lower()
    try:
        new_type = SlotType(new_type_str)
    except ValueError:
        valid = [t.value for t in SlotType]
        raise HTTPException(status_code=400, detail=f"Invalid type '{new_type_str}'. Valid: {valid}")

    norm = slot_name.strip().lower().replace(" ", "_")
    db = _resolve_discovery_db(thread_id)
    _ensure_tables(db)

    profile = load_slot_profile(norm, db_path=db) or SlotProfile(
        slot_name=norm,
        discovered_type=new_type,
        last_updated=time.time(),
    )

    old_type = profile.discovered_type
    profile.discovered_type = new_type
    profile.confidence = 1.0  # Manual override = full confidence
    profile.last_updated = time.time()
    profile.metadata["manual_override"] = True
    profile.metadata["override_timestamp"] = time.time()

    save_slot_profile(profile, db_path=db)

    if old_type != new_type:
        _log_reclassification(
            norm, old_type, new_type, 1.0,
            trigger="user_override",
            evidence_summary={"reason": "manual API override"},
            db_path=db,
        )

    return _profile_to_dict(profile)


@router.get("/stats")
def slot_stats(
    thread_id: Optional[str] = Query(None, description="Thread ID"),
) -> Dict[str, Any]:
    """Summary: total slots, typed/untyped breakdown, confidence distribution."""
    from personal_agent.slot_discovery import get_slot_stats

    db = _resolve_discovery_db(thread_id)
    return get_slot_stats(db_path=db)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _resolve_discovery_db(thread_id: Optional[str]) -> str:
    """Resolve discovery DB path from thread_id."""
    from personal_agent.slot_discovery import _get_db_path

    if thread_id:
        memory_db, _ = _resolve_memory_and_ledger_db(thread_id)
        if memory_db:
            return _get_db_path(memory_db)
    return _get_db_path()


def _resolve_memory_and_ledger_db(thread_id: Optional[str] = None):
    """Resolve memory and ledger DB paths for a thread."""
    import os
    from pathlib import Path as _Path

    pa_dir = _Path(__file__).resolve().parent.parent / "personal_agent"
    tid = thread_id or "default"

    # Try shared memory first, then per-thread
    shared = os.getenv("CRT_SHARED_MEMORY", "false").lower() == "true"
    if shared:
        mem_candidates = [pa_dir / "crt_memory.db"]
    else:
        mem_candidates = [
            pa_dir / f"crt_memory_{tid}.db",
            pa_dir / "crt_memory.db",
        ]

    memory_db = None
    for c in mem_candidates:
        if c.exists():
            memory_db = str(c)
            break

    # Ledger DB follows same pattern
    if shared:
        ledger_candidates = [pa_dir / "crt_ledger.db"]
    else:
        ledger_candidates = [
            pa_dir / f"crt_ledger_{tid}.db",
            pa_dir / "crt_ledger.db",
        ]

    ledger_db = None
    for c in ledger_candidates:
        if c.exists():
            ledger_db = str(c)
            break

    return memory_db, ledger_db


def _profile_to_dict(profile) -> Dict[str, Any]:
    """Convert SlotProfile to JSON-serializable dict."""
    return {
        "slot_name": profile.slot_name,
        "discovered_type": profile.discovered_type.value,
        "confidence": profile.confidence,
        "evidence_count": profile.evidence_count,
        "resolution_pattern": profile.resolution_pattern,
        "unique_values_seen": profile.unique_values_seen,
        "contradiction_count": profile.contradiction_count,
        "avg_resolution_time": profile.avg_resolution_time,
        "last_updated": profile.last_updated,
        "metadata": profile.metadata,
    }
