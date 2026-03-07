"""Contradictions route module.

Extracted from crt_api.py — all contradiction lifecycle endpoints live here.
Covers both ``/api/ledger/`` and ``/api/contradictions/`` namespaces.
"""

from __future__ import annotations

import json
import logging
import time
from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException, Query, Request

from personal_agent.crt_rag import CRTEnhancedRAG
from personal_agent.db_utils import get_db_connection

from routes.deps import sanitize_thread_id
from routes.models import (
    ContradictionAskedRequest,
    ContradictionListItem,
    ContradictionNextResponse,
    ContradictionRespondRequest,
    ContradictionRespondResponse,
    ContradictionWorkItem,
    ResolveContradictionPolicyRequest,
    ResolveContradictionPolicyResponse,
    ResolveContradictionRequest,
)

logger = logging.getLogger(__name__)

# Constants for resolution policies
RESOLUTION_TRUST_BOOST = 0.1  # Trust boost for chosen memory in OVERRIDE resolution

router = APIRouter()


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _get_engine(request: Request, thread_id: str) -> CRTEnhancedRAG:
    return request.app.state.get_engine(thread_id)


def _get_turn_number(request: Request, thread_id: str) -> int:
    return request.app.state.get_turn_number(thread_id)


def _suggest_contradiction_question(engine: CRTEnhancedRAG, entry: Any) -> str:
    """Deterministic, low-risk clarifying question for a ledger entry."""
    try:
        old_id = getattr(entry, "old_memory_id", None)
        new_id = getattr(entry, "new_memory_id", None)
        old_mem = engine.memory.get_memory_by_id(old_id) if old_id else None
        new_mem = engine.memory.get_memory_by_id(new_id) if new_id else None
        old_text = (getattr(old_mem, "text", "") or "").strip()
        new_text = (getattr(new_mem, "text", "") or "").strip()
    except Exception:
        old_text, new_text = "", ""

    if old_text and new_text:
        q = (
            "I have two conflicting statements recorded:\n"
            f"1) {old_text}\n"
            f"2) {new_text}\n\n"
            "Which is correct right now? If both can be true, tell me how."
        )
    else:
        q = "I have a potential contradiction recorded. Can you clarify which version is correct?"

    ctype = (getattr(entry, "contradiction_type", None) or "conflict").strip().lower()
    if ctype == "refinement":
        return q + " (If it's a refinement, please specify the more precise version.)"
    if ctype == "temporal":
        return q + " (If this changed over time, tell me the current value and when it changed.)"
    return q


def _work_item_for_entry(
    request: Request, engine: CRTEnhancedRAG, thread_id: str, entry: Any
) -> ContradictionWorkItem:
    ledger_id = str(getattr(entry, "ledger_id", "") or "")
    status = str(getattr(entry, "status", "") or "open")
    ctype = str(getattr(entry, "contradiction_type", "") or "conflict")
    drift = float(getattr(entry, "drift_mean", 0.0) or 0.0)
    summary = getattr(entry, "summary", None)

    try:
        wl = engine.ledger.get_contradiction_worklog(ledger_id)
    except Exception:
        wl = {"ask_count": 0, "last_asked_at": None}

    # M2 heuristic: open conflicts/revisions should ask user; refinements ask for precision; temporal asks for timeline.
    next_action = "ask_user"

    # Create semantic anchor for this contradiction
    semantic_anchor_dict = None
    suggested = None
    try:
        # Retrieve the memory texts
        old_mem_id = str(getattr(entry, "old_memory_id", ""))
        new_mem_id = str(getattr(entry, "new_memory_id", ""))

        old_mem = engine.memory.get_memory_by_id(old_mem_id) if old_mem_id else None
        new_mem = engine.memory.get_memory_by_id(new_mem_id) if new_mem_id else None

        if old_mem and new_mem:
            old_text = old_mem.text
            new_text = new_mem.text

            # Get current turn number for this thread
            turn_num = _get_turn_number(request, thread_id)

            # Create the semantic anchor
            anchor = engine.ledger.create_semantic_anchor(
                entry=entry,
                old_text=old_text,
                new_text=new_text,
                turn_number=turn_num,
            )
            semantic_anchor_dict = anchor.to_dict()
            # Use the anchor's type-aware clarification prompt
            suggested = anchor.clarification_prompt
    except Exception:
        # If anchor creation fails, fall back to no anchor (degraded mode)
        pass

    # Fall back to old generic question if anchor creation failed
    if not suggested:
        suggested = _suggest_contradiction_question(engine, entry)

    return ContradictionWorkItem(
        thread_id=sanitize_thread_id(thread_id),
        ledger_id=ledger_id,
        status=status,
        contradiction_type=ctype,
        drift_mean=drift,
        summary=summary,
        ask_count=int(wl.get("ask_count") or 0),
        last_asked_at=(wl.get("last_asked_at") if wl else None),
        next_action=next_action,
        suggested_question=suggested,
        semantic_anchor=semantic_anchor_dict,
    )


def _priority_key(item: ContradictionWorkItem) -> tuple:
    # Higher drift first, then fewer asks first, then most recently created (best-effort via ledger_id timestamp).
    return (
        -float(item.drift_mean or 0.0),
        int(item.ask_count or 0),
        item.ledger_id,
    )


# ---------------------------------------------------------------------------
# GET endpoints
# ---------------------------------------------------------------------------

@router.get("/api/ledger/open", response_model=list[ContradictionListItem])
def ledger_open(
    request: Request,
    thread_id: str = Query(default="default"),
    limit: int = Query(default=50, ge=1, le=500),
) -> list[ContradictionListItem]:
    engine = _get_engine(request, thread_id)
    try:
        entries = engine.ledger.get_open_contradictions(limit=limit)
    except Exception:
        entries = []

    def _get_memory_details(memory_id: str) -> tuple[str, float]:
        """Helper to fetch memory text and trust score."""
        try:
            mem = engine.memory.get_memory(memory_id)
            if mem:
                return mem.get('text', memory_id), mem.get('trust', 0.0)
        except (KeyError, AttributeError, ValueError) as e:
            logging.warning(f"Failed to fetch memory {memory_id}: {e}")
        return memory_id, 0.0

    # Enhance entries with memory details for UI
    result = []
    for e in entries:
        data = e.to_dict()
        # Add aliases for frontend compatibility
        data['contradiction_id'] = data['ledger_id']
        data['detected_at'] = data['timestamp']

        # Fetch memory details for old and new memories
        data['old_value'], data['old_trust'] = _get_memory_details(data['old_memory_id'])
        data['new_value'], data['new_trust'] = _get_memory_details(data['new_memory_id'])

        # Extract slot from affects_slots field (first slot if multiple)
        if data.get('affects_slots'):
            slots = str(data['affects_slots']).split(',')
            data['slot'] = slots[0].strip() if slots else 'unknown'
        else:
            data['slot'] = 'unknown'

        # Set policy from contradiction_type
        data['policy'] = data.get('contradiction_type', 'conflict')

        result.append(ContradictionListItem(**data))

    return result


@router.get("/api/contradictions/work-items", response_model=list[ContradictionWorkItem])
def contradiction_work_items(
    request: Request,
    thread_id: str = Query(default="default"),
    limit: int = Query(default=20, ge=1, le=200),
) -> list[ContradictionWorkItem]:
    engine = _get_engine(request, thread_id)
    try:
        entries = engine.ledger.get_open_contradictions(limit=500)
    except Exception:
        entries = []

    items = [_work_item_for_entry(request, engine, thread_id, e) for e in entries]
    items.sort(key=_priority_key)
    return items[: int(limit)]


@router.get("/api/contradictions/next", response_model=ContradictionNextResponse)
def contradiction_next(
    request: Request,
    thread_id: str = Query(default="default"),
) -> ContradictionNextResponse:
    engine = _get_engine(request, thread_id)
    try:
        entries = engine.ledger.get_open_contradictions(limit=500)
    except Exception:
        entries = []
    if not entries:
        return ContradictionNextResponse(thread_id=sanitize_thread_id(thread_id), has_item=False, item=None)

    items = [_work_item_for_entry(request, engine, thread_id, e) for e in entries]
    items.sort(key=_priority_key)
    return ContradictionNextResponse(thread_id=sanitize_thread_id(thread_id), has_item=True, item=items[0])


@router.get("/api/contradictions")
def get_contradictions(
    request: Request,
    thread_id: str = Query(default="default"),
) -> Dict[str, Any]:
    """Get all contradictions for a thread (for stress testing)"""
    tid = sanitize_thread_id(thread_id)
    ledger_db = f"personal_agent/crt_ledger_{tid}.db"

    try:
        with get_db_connection(ledger_db) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM contradictions")
            rows = cursor.fetchall()

            # Get column names
            columns = [desc[0] for desc in cursor.description]

            # Convert to dicts
            contradictions = []
            for row in rows:
                contradictions.append(dict(zip(columns, row)))

        return {
            "contradictions": contradictions,
            "count": len(contradictions),
        }
    except Exception as e:
        return {"contradictions": [], "count": 0, "error": str(e)}


# ---------------------------------------------------------------------------
# POST endpoints
# ---------------------------------------------------------------------------

@router.post("/api/contradictions/asked")
def contradiction_mark_asked(
    request: Request,
    req: ContradictionAskedRequest,
) -> Dict[str, Any]:
    engine = _get_engine(request, req.thread_id)
    try:
        engine.ledger.mark_contradiction_asked(req.ledger_id)
    except Exception:
        return {"ok": False}
    return {"ok": True}


@router.post("/api/contradictions/respond", response_model=ContradictionRespondResponse)
def contradiction_respond(
    request: Request,
    req: ContradictionRespondRequest,
) -> ContradictionRespondResponse:
    engine = _get_engine(request, req.thread_id)

    recorded = False
    resolved = False
    parse_result = None

    try:
        engine.ledger.record_contradiction_user_answer(req.ledger_id, req.answer)
        recorded = True
    except Exception:
        recorded = False

    if bool(req.resolve):
        # Try to use semantic anchor for intelligent parsing
        try:
            # Get the contradiction entry to build anchor
            entries = [e for e in engine.ledger.get_all_contradictions(limit=1000)
                      if getattr(e, 'ledger_id', '') == req.ledger_id]

            if entries:
                entry = entries[0]
                old_mem_id = str(getattr(entry, "old_memory_id", ""))
                new_mem_id = str(getattr(entry, "new_memory_id", ""))

                # Retrieve memory texts
                old_mem = engine.memory.get_memory_by_id(old_mem_id) if old_mem_id else None
                new_mem = engine.memory.get_memory_by_id(new_mem_id) if new_mem_id else None

                if old_mem and new_mem:
                    # Create semantic anchor
                    from personal_agent.crt_semantic_anchor import (
                        parse_user_answer,
                        is_resolution_grounded,
                    )

                    anchor = engine.ledger.create_semantic_anchor(
                        entry=entry,
                        old_text=old_mem.text,
                        new_text=new_mem.text,
                        turn_number=_get_turn_number(request, req.thread_id),
                    )

                    # Parse the user's answer using semantic anchor
                    parse_result = parse_user_answer(anchor, req.answer)

                    # Validate grounding
                    if is_resolution_grounded(anchor, parse_result):
                        # Use parsed resolution instead of raw request
                        resolution_method = parse_result.get("resolution_method", req.resolution_method)
                        chosen_memory_id = parse_result.get("chosen_memory_id", req.merged_memory_id)
                        new_status = parse_result.get("new_status", req.new_status)
                    else:
                        # Grounding check failed - fall back to request params
                        resolution_method = req.resolution_method
                        chosen_memory_id = req.merged_memory_id
                        new_status = req.new_status
                else:
                    # No memories found - use request params
                    resolution_method = req.resolution_method
                    chosen_memory_id = req.merged_memory_id
                    new_status = req.new_status
            else:
                # No entry found - use request params
                resolution_method = req.resolution_method
                chosen_memory_id = req.merged_memory_id
                new_status = req.new_status

        except Exception:
            # Parsing failed - fall back to request params
            resolution_method = req.resolution_method
            chosen_memory_id = req.merged_memory_id
            new_status = req.new_status

        try:
            engine.ledger.resolve_contradiction(
                ledger_id=req.ledger_id,
                method=str(resolution_method or "user_clarified"),
                merged_memory_id=chosen_memory_id,
                new_status=str(new_status or "resolved"),
            )
            # Verify the write actually moved status; if not, force a direct update.
            resolved = False
            try:
                current = next(
                    (e for e in engine.ledger.get_all_contradictions(limit=2000) if getattr(e, "ledger_id", "") == req.ledger_id),
                    None,
                )
                if current is not None and str(getattr(current, "status", "")).lower() == str(new_status or "resolved").lower():
                    resolved = True
                else:
                    conn = engine.ledger._get_connection()
                    cur = conn.cursor()
                    cur.execute(
                        """
                        UPDATE contradictions
                        SET status = ?, resolution_timestamp = ?, resolution_method = ?, merged_memory_id = ?
                        WHERE ledger_id = ?
                        """,
                        (str(new_status or "resolved"), time.time(), str(resolution_method or "user_clarified"), chosen_memory_id, req.ledger_id),
                    )
                    conn.commit()
                    resolved = cur.rowcount > 0
                    conn.close()
            except Exception:
                resolved = True
        except Exception:
            resolved = False

    # Return the next work item for convenience (M2 loop).
    try:
        nxt = contradiction_next(request=request, thread_id=req.thread_id)
    except Exception:
        nxt = ContradictionNextResponse(thread_id=sanitize_thread_id(req.thread_id), has_item=False, item=None)

    return ContradictionRespondResponse(
        ok=bool(recorded),
        thread_id=sanitize_thread_id(req.thread_id),
        ledger_id=str(req.ledger_id),
        recorded=bool(recorded),
        resolved=bool(resolved),
        next=nxt,
    )


@router.post("/api/ledger/resolve")
def ledger_resolve(
    request: Request,
    req: ResolveContradictionRequest,
) -> Dict[str, Any]:
    engine = _get_engine(request, req.thread_id)
    engine.ledger.resolve_contradiction(
        ledger_id=req.ledger_id,
        method=req.method,
        merged_memory_id=req.merged_memory_id,
        new_status=req.new_status,
    )
    return {"ok": True}


@router.post("/api/resolve_contradiction", response_model=ResolveContradictionPolicyResponse)
def resolve_contradiction_policy(
    request: Request,
    req: ResolveContradictionPolicyRequest,
) -> ResolveContradictionPolicyResponse:
    """
    Resolve an open contradiction with user feedback using policy-driven approach.

    Policies:
    - OVERRIDE: Deprecate old memory, keep chosen memory
    - PRESERVE: Keep both memories as valid
    - ASK_USER: Defer decision, keep contradiction open
    """
    engine = _get_engine(request, req.thread_id)
    ledger_id = req.ledger_id
    resolution = req.resolution
    chosen_memory_id = req.chosen_memory_id
    user_confirmation = req.user_confirmation

    logger.info(f"\n[RESOLUTION] Starting resolution for {ledger_id}")
    logger.info(f"[RESOLUTION] Policy: {resolution}")
    logger.info(f"[RESOLUTION] User says: {user_confirmation}")

    # Load contradiction from ledger
    ledger_db = str(engine.ledger.db_path)
    with get_db_connection(ledger_db) as conn:
        cursor = conn.cursor()

        cursor.execute("""
            SELECT old_memory_id, new_memory_id, contradiction_type, status
            FROM contradictions
            WHERE ledger_id = ?
        """, (ledger_id,))

        result = cursor.fetchone()
        if not result:
            raise HTTPException(status_code=404, detail="Contradiction not found")

        old_memory_id, new_memory_id, contra_type, status = result

        if status != 'open':
            raise HTTPException(status_code=400, detail="Contradiction already resolved")

    deprecated_id = None
    active_id = None
    message = None

    # Apply resolution policy
    if resolution == "OVERRIDE":
        if not chosen_memory_id:
            raise HTTPException(status_code=400, detail="chosen_memory_id required for OVERRIDE")

        # Deprecate the non-chosen memory, keep the chosen one
        deprecated_id = old_memory_id if chosen_memory_id == new_memory_id else new_memory_id
        active_id = chosen_memory_id

        # Update memory database
        mem_db = str(engine.memory.db_path)
        with get_db_connection(mem_db) as mem_conn:
            mem_cursor = mem_conn.cursor()

            # Deprecate old memory
            mem_cursor.execute("""
                UPDATE memories 
                SET deprecated = 1, deprecation_reason = ?
                WHERE memory_id = ?
            """, (f"Overridden by {active_id} - user confirmed", deprecated_id))

            # Boost trust of chosen memory (SQLite doesn't have LEAST, use MIN instead)
            mem_cursor.execute("""
                UPDATE memories 
                SET trust = MIN(trust + ?, 1.0)
                WHERE memory_id = ?
            """, (RESOLUTION_TRUST_BOOST, active_id,))

            mem_conn.commit()

        logger.info(f"[OVERRIDE] Deprecated {deprecated_id}, kept {active_id}")

    elif resolution == "PRESERVE":
        # Keep both memories, mark as complementary
        mem_db = str(engine.memory.db_path)
        with get_db_connection(mem_db) as mem_conn:
            mem_cursor = mem_conn.cursor()

            # Tag both as "resolved_both_valid"
            for mem_id in [old_memory_id, new_memory_id]:
                # Get current tags
                mem_cursor.execute("SELECT tags_json FROM memories WHERE memory_id = ?", (mem_id,))
                row = mem_cursor.fetchone()
                if row:
                    tags_json = row[0] or '[]'
                    tags = json.loads(tags_json)
                    if 'resolved_both_valid' not in tags:
                        tags.append('resolved_both_valid')
                    mem_cursor.execute("""
                        UPDATE memories 
                        SET tags_json = ?
                        WHERE memory_id = ?
                    """, (json.dumps(tags), mem_id))

            mem_conn.commit()

        logger.info(f"[PRESERVE] Both memories marked as valid")
        message = "Both memories preserved as valid"

    elif resolution == "ASK_USER":
        # User deferred decision, keep contradiction open but note user was asked
        with get_db_connection(ledger_db) as conn:
            cursor = conn.cursor()

            cursor.execute("""
                SELECT metadata FROM contradictions WHERE ledger_id = ?
            """, (ledger_id,))
            row = cursor.fetchone()
            metadata = {}
            if row and row[0]:
                metadata = json.loads(row[0]) if isinstance(row[0], str) else row[0]

            metadata['user_deferred'] = 'true'

            cursor.execute("""
                UPDATE contradictions
                SET metadata = ?
                WHERE ledger_id = ?
            """, (json.dumps(metadata), ledger_id))
            conn.commit()

        logger.info(f"[ASK_USER] User deferred resolution for {ledger_id}")

        return ResolveContradictionPolicyResponse(
            status="deferred",
            ledger_id=ledger_id,
            resolution=resolution,
            message="User deferred resolution. Contradiction remains open.",
        )
    else:
        raise HTTPException(status_code=400, detail=f"Unknown resolution policy: {resolution}")

    # Update ledger to mark resolved (for OVERRIDE and PRESERVE)
    with get_db_connection(ledger_db) as conn:
        cursor = conn.cursor()

        cursor.execute("""
            UPDATE contradictions
            SET 
                status = 'resolved',
                resolution_method = ?,
                resolution_timestamp = ?
            WHERE ledger_id = ?
        """, (resolution, time.time(), ledger_id))

        # Log to conflict_resolutions table
        cursor.execute("""
            INSERT INTO conflict_resolutions 
            (ledger_id, resolution_method, chosen_memory_id, user_feedback, timestamp)
            VALUES (?, ?, ?, ?, ?)
        """, (ledger_id, resolution, chosen_memory_id, user_confirmation, time.time()))

        conn.commit()

    logger.info(f"[RESOLUTION] Completed: {ledger_id} → {resolution}")

    return ResolveContradictionPolicyResponse(
        status="resolved",
        ledger_id=ledger_id,
        resolution=resolution,
        deprecated_memory=deprecated_id,
        active_memory=active_id,
        message=message,
    )
