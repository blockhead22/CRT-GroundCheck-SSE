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

# Governance layer — immune agents guard resolution endpoints
try:
    from personal_agent.governance import GovernanceLayer
    from personal_agent.immune_agents import (
        Contradiction as ImmuneContradiction,
        Disposition as ImmuneDisposition,
        ResolutionAction as ImmuneResolutionAction,
    )
    _GOVERNANCE = GovernanceLayer()
    logger.info("[CONTRADICTIONS] GovernanceLayer loaded — PrematureResolutionGuard active")
except Exception as _gov_err:
    _GOVERNANCE = None
    logger.warning(f"[CONTRADICTIONS] GovernanceLayer not available: {_gov_err}")

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


def _salience_sort(items: list[ContradictionWorkItem], temperature: float = 1.0) -> list[ContradictionWorkItem]:
    """Sort work items by salience score using softmax with temperature.

    No resolution performed — ranking only.
    """
    if not items:
        return items
    try:
        import numpy as np
        from personal_agent.salience import compute_contradiction_salience, softmax

        t_now = time.time()

        # Count open contradictions per slot for volatility signal
        slot_counts: dict[str, int] = {}
        for item in items:
            slot = (item.summary or "").split(":")[0].strip().lower() if item.summary else "unknown"
            slot_counts[slot] = slot_counts.get(slot, 0) + 1

        # Compute salience scores
        scores = []
        for item in items:
            slot = (item.summary or "").split(":")[0].strip().lower() if item.summary else "unknown"
            # Extract timestamp from ledger_id (format: contra_<timestamp>_<random>)
            try:
                ts = float(item.ledger_id.split("_")[1]) / 1000.0
            except (IndexError, ValueError):
                ts = t_now
            s = compute_contradiction_salience(
                drift_mean=item.drift_mean or 0.0,
                slot=slot,
                slot_open_count=slot_counts.get(slot, 1),
                timestamp=ts,
                t_now=t_now,
            )
            item.salience_score = round(s, 4)
            scores.append(s)

        # Apply softmax for final ranking
        score_array = np.array(scores)
        priorities = softmax(score_array, temperature=temperature)
        ranked = sorted(zip(items, priorities), key=lambda x: x[1], reverse=True)
        top_slot = None
        if ranked:
            _s = (ranked[0][0].summary or "").split(":")[0].strip().lower() if ranked[0][0].summary else "?"
            top_slot = _s
        print(
            "[SALIENCE] contradiction rerank n=%d T=%.2f top_slot=%s top_priority=%.4f"
            % (len(items), temperature, top_slot, float(ranked[0][1]) if ranked else 0.0)
        )
        return [item for item, _ in ranked]
    except Exception as e:
        logger.warning("[SALIENCE] Fallback to drift sort: %s", e)
        items.sort(key=_priority_key)
        return items


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
        entries = engine.ledger.get_open_contradictions(limit=limit, thread_id=sanitize_thread_id(thread_id))
    except Exception:
        entries = []

    def _get_memory_details(memory_id: str) -> tuple[str, float]:
        """Helper to fetch memory text and trust score."""
        try:
            mem = engine.memory.get_memory_by_id(memory_id)
            if mem:
                text = mem.text if hasattr(mem, 'text') else mem.get('text', memory_id)
                trust = mem.trust if hasattr(mem, 'trust') else mem.get('trust', 0.0)
                return text, trust
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

        # Compute salience score if gate is enabled (Lab 11)
        try:
            import auth as _auth_sal
            _uid_sal = int(getattr(request.state, "user_id", 1))
            if _auth_sal.get_user_setting(_uid_sal, "salience_gate_enabled", "true") == "true":
                from personal_agent.salience import compute_contradiction_salience
                _slot = data.get('slot', 'unknown')
                _slot_count = sum(1 for _e in entries if _slot in str(getattr(_e, 'affects_slots', '') or ''))
                data['salience_score'] = round(compute_contradiction_salience(
                    drift_mean=data.get('drift_mean', 0.0),
                    slot=_slot,
                    slot_open_count=max(1, _slot_count),
                    timestamp=data.get('timestamp', 0.0),
                ), 4)
        except Exception:
            pass

        result.append(ContradictionListItem(**data))

    # Sort by salience if scores were computed
    if result and result[0].salience_score is not None:
        result.sort(key=lambda x: x.salience_score or 0.0, reverse=True)

    return result


@router.get("/api/contradictions/work-items", response_model=list[ContradictionWorkItem])
def contradiction_work_items(
    request: Request,
    thread_id: str = Query(default="default"),
    limit: int = Query(default=20, ge=1, le=200),
) -> list[ContradictionWorkItem]:
    engine = _get_engine(request, thread_id)
    try:
        entries = engine.ledger.get_open_contradictions(limit=500, thread_id=sanitize_thread_id(thread_id))
    except Exception:
        entries = []

    items = [_work_item_for_entry(request, engine, thread_id, e) for e in entries]

    # Salience-gated re-ranking (Lab 11)
    try:
        import auth as _auth_salience
        _uid = int(getattr(request.state, "user_id", 1))
        _salience_on = _auth_salience.get_user_setting(_uid, "salience_gate_enabled", "true") == "true"
    except Exception:
        _salience_on = False

    if _salience_on:
        try:
            _temp = float(_auth_salience.get_user_setting(_uid, "salience_temperature", "1.0"))
        except (ValueError, NameError):
            _temp = 1.0
        items = _salience_sort(items, temperature=_temp)
    else:
        items.sort(key=_priority_key)

    return items[: int(limit)]


@router.get("/api/contradictions/next", response_model=ContradictionNextResponse)
def contradiction_next(
    request: Request,
    thread_id: str = Query(default="default"),
) -> ContradictionNextResponse:
    engine = _get_engine(request, thread_id)
    try:
        entries = engine.ledger.get_open_contradictions(limit=500, thread_id=sanitize_thread_id(thread_id))
    except Exception:
        entries = []
    if not entries:
        return ContradictionNextResponse(thread_id=sanitize_thread_id(thread_id), has_item=False, item=None)

    items = [_work_item_for_entry(request, engine, thread_id, e) for e in entries]

    # Salience-gated re-ranking (Lab 11)
    try:
        import auth as _auth_salience
        _uid = int(getattr(request.state, "user_id", 1))
        _salience_on = _auth_salience.get_user_setting(_uid, "salience_gate_enabled", "true") == "true"
    except Exception:
        _salience_on = False

    if _salience_on:
        try:
            _temp = float(_auth_salience.get_user_setting(_uid, "salience_temperature", "1.0"))
        except (ValueError, NameError):
            _temp = 1.0
        items = _salience_sort(items, temperature=_temp)
    else:
        items.sort(key=_priority_key)

    return ContradictionNextResponse(thread_id=sanitize_thread_id(thread_id), has_item=True, item=items[0])


@router.get("/api/contradictions")
def get_contradictions(
    request: Request,
    thread_id: str = Query(default="default"),
) -> Dict[str, Any]:
    """Get all contradictions for a thread (for stress testing)"""
    tid = sanitize_thread_id(thread_id)
    engine = _get_engine(request, tid)
    ledger_db = str(getattr(getattr(engine, "ledger", None), "db_path", "") or "")
    if not ledger_db:
        thread_db_paths = getattr(request.app.state, "thread_db_paths", None)
        if callable(thread_db_paths):
            try:
                _, ledger_db = thread_db_paths(tid)
            except Exception:
                ledger_db = ""
    if not ledger_db:
        return {"contradictions": [], "count": 0, "error": "ledger db unavailable"}

    try:
        with get_db_connection(ledger_db) as conn:
            cursor = conn.cursor()
            cursor.execute("PRAGMA table_info(contradictions)")
            columns_info = cursor.fetchall()
            has_thread_id = any(str(col[1] or "") == "thread_id" for col in columns_info)
            if has_thread_id:
                cursor.execute(
                    "SELECT * FROM contradictions WHERE COALESCE(thread_id, 'default') = ? ORDER BY timestamp DESC",
                    (tid,),
                )
            else:
                cursor.execute("SELECT * FROM contradictions ORDER BY timestamp DESC")
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
            entries = [e for e in engine.ledger.get_all_contradictions(limit=1000, thread_id=sanitize_thread_id(req.thread_id))
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

        # --- Governance: PrematureResolutionGuard ---
        if _GOVERNANCE and entry:
            try:
                _gov_result = _GOVERNANCE.govern_resolution(
                    contradiction=ImmuneContradiction(
                        id=req.ledger_id,
                        claim_a=getattr(old_mem, "text", "") or "" if old_mem else "",
                        claim_b=getattr(new_mem, "text", "") or "" if new_mem else "",
                        disposition=getattr(entry, "disposition", "unknown") or "unknown",
                        trust_a=float(getattr(old_mem, "trust", 0.5) or 0.5) if old_mem else 0.5,
                        trust_b=float(getattr(new_mem, "trust", 0.5) or 0.5) if new_mem else 0.5,
                    ),
                    proposed_action=ImmuneResolutionAction.RESOLVE_A,
                )
                if _gov_result.should_block:
                    _reason = _gov_result.annotations[0].finding if _gov_result.annotations else "blocked"
                    logger.warning(f"[GOVERNANCE] Respond-resolution blocked: {_reason}")
                    return ContradictionRespondResponse(
                        ok=False, thread_id=sanitize_thread_id(req.thread_id),
                        ledger_id=str(req.ledger_id), recorded=recorded,
                        resolved=False, next=None,
                    )
            except Exception as _ge:
                logger.debug(f"[GOVERNANCE] Respond guard failed (proceeding): {_ge}")

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

    # --- Governance: PrematureResolutionGuard ---
    if _GOVERNANCE:
        try:
            _entry = next(
                (e for e in engine.ledger.get_all_contradictions(limit=2000)
                 if getattr(e, "ledger_id", "") == req.ledger_id),
                None,
            )
            if _entry:
                _gov_result = _GOVERNANCE.govern_resolution(
                    contradiction=ImmuneContradiction(
                        id=req.ledger_id,
                        claim_a=getattr(_entry, "old_text", "") or "",
                        claim_b=getattr(_entry, "new_text", "") or "",
                        disposition=getattr(_entry, "disposition", "unknown") or "unknown",
                        trust_a=float(getattr(_entry, "old_trust", 0.5) or 0.5),
                        trust_b=float(getattr(_entry, "new_trust", 0.5) or 0.5),
                    ),
                    proposed_action=ImmuneResolutionAction.RESOLVE_A,
                )
                if _gov_result.should_block:
                    _reason = _gov_result.annotations[0].finding if _gov_result.annotations else "governance blocked"
                    logger.warning(f"[GOVERNANCE] Resolution blocked for {req.ledger_id}: {_reason}")
                    raise HTTPException(status_code=403, detail=f"Governance blocked: {_reason}")
        except HTTPException:
            raise
        except Exception as _ge:
            logger.debug(f"[GOVERNANCE] Resolution guard check failed (proceeding): {_ge}")

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

    # --- Governance: PrematureResolutionGuard + MemoryCorruptionGuard ---
    if _GOVERNANCE:
        try:
            _gov_result = _GOVERNANCE.govern_resolution(
                contradiction=ImmuneContradiction(
                    id=ledger_id,
                    claim_a="",  # We don't have texts here but disposition matters
                    claim_b="",
                    disposition=str(contra_type or "unknown"),
                    trust_a=0.5,
                    trust_b=0.5,
                ),
                proposed_action=ImmuneResolutionAction.RESOLVE_A,
            )
            if _gov_result.should_block:
                _reason = _gov_result.annotations[0].finding if _gov_result.annotations else "governance blocked"
                logger.warning(f"[GOVERNANCE] Policy resolution blocked for {ledger_id}: {_reason}")
                raise HTTPException(status_code=403, detail=f"Governance blocked: {_reason}")
        except HTTPException:
            raise
        except Exception as _ge:
            logger.debug(f"[GOVERNANCE] Policy resolution guard failed (proceeding): {_ge}")

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
