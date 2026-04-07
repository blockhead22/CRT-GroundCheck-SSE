"""Memory, profile, facts, dashboard, and docs route module.

Extracted from crt_api.py — all data-access endpoints live here.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Header, HTTPException, Query, Request
from pydantic import BaseModel

import re as _re

from personal_agent.crt_core import MemorySource
from personal_agent.crt_rag import CRTEnhancedRAG
from personal_agent.fact_slots import (
    create_simple_fact,
    extract_fact_slots,
    is_explicit_name_declaration_text,
    names_look_equivalent,
)
from personal_agent.judgment_audit_log import get_judgment_log, CONTRADICTION_STORE
from personal_agent.db_utils import get_db_connection

from routes.deps import sanitize_thread_id, resolve_user_id
from routes.models import (
    ChatSendRequest,
    ChatSendResponse,
    DashboardOverviewResponse,
    DocGetResponse,
    DocListItem,
    EffectiveFactItem,
    ExtractedFactItem,
    FactExtractionRequest,
    FactExtractionResponse,
    FactHistoryResponse,
    MemoryEventItem,
    MemoryListItem,
    MemoryStoreRequest,
    MemoryStoreResponse,
    MemoryUsageSummaryItem,
    ModelRoutingInfo,
    ProfileResponse,
    StructuredFactsResponse,
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
        "user_id": getattr(mem, "user_id", None),
        "authority": str(getattr(mem, "authority", "confirmed") or "confirmed"),
        "channel": str(getattr(mem, "channel", "unknown") or "unknown"),
        "origin": getattr(mem, "origin", None),
        "kind": str(getattr(mem, "kind", "observation") or "observation"),
        "review_after": getattr(mem, "review_after", None),
        "source_kind": str(getattr(mem, "source_kind", "principal") or "principal"),
        "model_id": getattr(mem, "model_id", None),
        "run_id": getattr(mem, "run_id", None),
    }


def _recent_scope_items(engine: CRTEnhancedRAG, tid: str, user_id: Optional[str] = None) -> list:
    """Return the same raw memory scope used by /api/memory/recent.

    When *user_id* is provided the scope is all memories owned by that user
    (regardless of thread).  Otherwise falls back to thread-based scoping for
    backward compatibility.
    """
    try:
        if user_id:
            return list(engine.memory._load_all_memories(user_id=user_id))
        if tid == "default":
            all_items = engine.memory._load_all_memories()
            return [
                m for m in all_items
                if not getattr(m, "thread_id", None)
                or str(m.thread_id).lower() in ("default", "")
            ]
        return list(engine.memory._load_memories_filtered(thread_id=tid))
    except Exception:
        return []


def _extract_latest_profile_slots(engine: CRTEnhancedRAG) -> Dict[str, str]:
    """Best-effort extraction of latest fact slots from user memories.

    We treat structured facts like "FACT: name = Nick" as authoritative signals.
    Uses two-tier extraction to capture both hard slots and open tuples.
    """
    try:
        items = engine.memory._load_all_memories()
    except Exception:
        items = []

    best_by_slot: Dict[str, Dict[str, Any]] = {}
    for mem in items:
        src = getattr(getattr(mem, "source", None), "value", None) or str(getattr(mem, "source", ""))
        if str(src).lower() != "user":
            continue
        if hasattr(engine, "memory") and not engine.memory.can_answer_user_fact(mem):
            continue
        text = str(getattr(mem, "text", "") or "")

        # Use two-tier extraction if available, otherwise fall back to regex
        if hasattr(engine, 'two_tier_system') and engine.two_tier_system is not None:
            try:
                two_tier_result = engine.two_tier_system.extract_facts(text, skip_llm=True)
                facts = two_tier_result.hard_facts
                # Also include open tuples as additional slots
                for tuple_fact in two_tier_result.open_tuples:
                    if tuple_fact.attribute not in facts and tuple_fact.confidence >= 0.6:
                        facts[tuple_fact.attribute] = create_simple_fact(tuple_fact.value)
            except Exception:
                facts = extract_fact_slots(text)
        else:
            facts = extract_fact_slots(text)

        if not facts:
            continue
        ts = float(getattr(mem, "timestamp", 0.0) or 0.0)
        for slot, extracted in facts.items():
            prev = best_by_slot.get(slot)
            if prev is None or ts >= float(prev.get("timestamp") or 0.0):
                best_by_slot[slot] = {"value": str(extracted.value), "timestamp": ts}

    out: Dict[str, str] = {}
    for slot, d in best_by_slot.items():
        v = str(d.get("value") or "").strip()
        if v:
            out[str(slot)] = v
    return out


# ========================================================================
# Docs
# ========================================================================

@router.get("/api/docs", response_model=list[DocListItem])
def list_docs(request: Request) -> list[DocListItem]:
    doc_map = request.app.state.doc_map
    items: list[DocListItem] = []
    for doc_id, meta in doc_map.items():
        path: Path = meta["path"]
        if not path.exists() or not path.is_file():
            continue
        items.append(DocListItem(id=doc_id, title=str(meta.get("title") or doc_id), kind=str(meta.get("kind") or "docs")))
    # Stable ordering: preserve doc_map insertion order within each kind, kinds alphabetical
    kind_order = {k: i for i, k in enumerate(dict.fromkeys(meta.get("kind", "") for meta in doc_map.values()))}
    doc_order = {doc_id: i for i, doc_id in enumerate(doc_map.keys())}
    items.sort(key=lambda x: (kind_order.get(x.kind, 99), doc_order.get(x.id, 99)))
    return items


@router.get("/api/docs/{doc_id}", response_model=DocGetResponse)
def get_doc(doc_id: str, request: Request) -> DocGetResponse:
    doc_map = request.app.state.doc_map
    meta = doc_map.get(doc_id)
    if not meta:
        return DocGetResponse(id=doc_id, title="Not found", kind="error", markdown=f"# Not found\n\nUnknown doc id: `{doc_id}`")

    path: Path = meta["path"]
    try:
        markdown = path.read_text(encoding="utf-8")
    except Exception as e:
        markdown = f"# Missing document\n\nCould not read: `{path}`\n\nError: {e}"

    return DocGetResponse(
        id=doc_id,
        title=str(meta.get("title") or doc_id),
        kind=str(meta.get("kind") or "docs"),
        markdown=markdown,
    )


# ========================================================================
# Profile
# ========================================================================

@router.get("/api/profile", response_model=ProfileResponse)
def get_profile(request: Request, thread_id: str = Query(default="default"), authorization: Optional[str] = Header(None)) -> ProfileResponse:
    engine = _get_engine(request, thread_id)
    tid = sanitize_thread_id(thread_id)
    uid = resolve_user_id(authorization)
    slots = {
        str(slot): str((fact or {}).get("value") or "")
        for slot, fact in (engine.get_effective_user_facts(thread_id=tid) or {}).items()
        if str((fact or {}).get("value") or "").strip()
    }
    # Canonical name: auth display_name > memory-extracted name slot
    name = None
    if uid:
        try:
            import auth as _auth_profile
            _user = _auth_profile.get_user_by_id(int(uid))
            name = (_user or {}).get("display_name") or None
        except Exception:
            pass
    if not name:
        name = slots.get("name")
    # Don't expose stale name slot in profile if auth has a display_name
    if name and slots.get("name") and name != slots.get("name"):
        slots["name"] = name  # Sync slot to match auth
    return ProfileResponse(thread_id=tid, name=name, slots=slots)


@router.post("/api/profile/consolidate")
def consolidate_profile(request: Request):
    """
    Fix single-value slots that have multiple values.

    For slots like 'name' that should only have one value,
    this keeps the most recent and deactivates older values.

    Use this to clean up after the multi-value bug is fixed.
    """
    engine = _get_engine(request, "default")
    try:
        result = engine.user_profile.consolidate_single_value_slots()
        return {
            "status": "success",
            "consolidated": result,
            "message": f"Consolidated {len(result)} slots"
        }
    except Exception as e:
        logger.error(f"[PROFILE] Failed to consolidate: {e}")
        return {"status": "error", "error": str(e)}


@router.post("/api/profile/set_name")
def set_profile_name(req: ChatSendRequest, request: Request):
    """Set profile name by storing it as a FACT memory."""
    engine = _get_engine(request, req.thread_id or "default")
    try:
        text = req.message.strip() if req.message else ""
        if not text:
            return {"ok": False, "error": "No name provided"}
        # Strip FACT wrapper if frontend already wrapped it (backward compat)
        if text.upper().startswith("FACT:"):
            _match = _re.match(r"(?i)FACT:\s*name\s*=\s*(.+)", text)
            if _match:
                text = _match.group(1).strip()
        name_value = text
        engine.memory.store_memory(
            text=f"FACT: name = {name_value}",
            confidence=1.0,
            source=MemorySource.USER,
            context={"thread_id": req.thread_id or "default", "kind": "identity"},
        )
        # Also update global user profile so name propagates across threads
        try:
            from personal_agent.user_profile import GlobalUserProfile
            profile = GlobalUserProfile()
            profile.update_from_text(
                f"My name is {name_value}",
                thread_id=req.thread_id or "default",
            )
            print(f"[PROFILE] Global profile updated with name: {name_value}")
        except Exception as profile_err:
            print(f"[PROFILE] Failed to update global profile: {profile_err}")
        return {"ok": True, "name": name_value}
    except Exception as e:
        logger.error(f"[PROFILE] Failed to set name: {e}")
        return {"ok": False, "error": str(e)}


class _SetFactsRequest(BaseModel):
    thread_id: str = "default"
    facts: Dict[str, str] = {}


@router.post("/api/profile/set_facts")
def set_profile_facts(req: _SetFactsRequest, request: Request):
    """Batch-set profile facts via CRT memory system."""
    if not req.facts:
        return {"ok": True, "stored": 0}

    engine = _get_engine(request, req.thread_id or "default")

    if not hasattr(engine, "fact_store") or engine.fact_store is None:
        logger.warning("[PROFILE] No fact_store available on engine")
        return {"ok": False, "error": "fact_store not available"}

    stored = 0
    for slot, value in req.facts.items():
        if not isinstance(value, str) or not value.strip():
            continue
        try:
            engine.fact_store.process_input(
                f"FACT: {slot} = {value.strip()}",
                thread_id=req.thread_id or "default",
            )
            stored += 1
        except Exception as e:
            logger.warning("[PROFILE] Failed to store fact %s: %s", slot, e)

    return {"ok": True, "stored": stored}


# ========================================================================
# Fact extraction
# ========================================================================

@router.post("/api/facts/extract", response_model=FactExtractionResponse)
def extract_facts_endpoint(req: FactExtractionRequest, request: Request) -> FactExtractionResponse:
    """
    Extract facts from text using the two-tier fact extraction system.

    Returns both hard slots (regex-based) and open tuples (LLM-based) if available.
    """
    engine = _get_engine(request, "default")

    if not hasattr(engine, 'two_tier_system') or engine.two_tier_system is None:
        # Fall back to regex-only extraction
        facts = extract_fact_slots(req.text) or {}

        hard_facts_dict: Dict[str, ExtractedFactItem] = {}
        for slot, fact in facts.items():
            hard_facts_dict[slot] = ExtractedFactItem(
                slot=slot,
                value=str(fact.value),
                normalized=str(fact.normalized),
                tier="hard",
                source="regex",
                confidence=1.0
            )

        return FactExtractionResponse(
            text=req.text,
            hard_facts=hard_facts_dict,
            open_tuples=[],
            extraction_time=0.0,
            methods_used=["regex_fallback"]
        )

    # Use two-tier system
    try:
        result = engine.two_tier_system.extract_facts(req.text, skip_llm=req.skip_llm)

        # Convert hard facts
        hard_facts_dict = {}
        for slot, fact in result.hard_facts.items():
            hard_facts_dict[slot] = ExtractedFactItem(
                slot=slot,
                value=str(fact.value),
                normalized=str(fact.normalized),
                tier="hard",
                source="regex",
                confidence=1.0
            )

        # Convert open tuples
        open_tuples_list: list[ExtractedFactItem] = []
        for tuple_fact in result.open_tuples:
            open_tuples_list.append(ExtractedFactItem(
                slot=tuple_fact.attribute,
                value=str(tuple_fact.value),
                normalized=str(tuple_fact.normalized_value),
                tier="open",
                source="llm",
                confidence=tuple_fact.confidence
            ))

        return FactExtractionResponse(
            text=req.text,
            hard_facts=hard_facts_dict,
            open_tuples=open_tuples_list,
            extraction_time=result.extraction_time,
            methods_used=result.methods_used
        )
    except Exception as e:
        logger.error(f"[FACT_EXTRACTION] Error extracting facts: {e}")
        return FactExtractionResponse(
            text=req.text,
            hard_facts={},
            open_tuples=[],
            extraction_time=0.0,
            methods_used=["error"]
        )


@router.get("/api/facts/structured")
def get_structured_facts(
    request: Request,
    thread_id: str = Query(default="default"),
    scope: str = Query(default="thread"),
) -> StructuredFactsResponse:
    """Get structured facts from the requested fact surface."""
    tid = sanitize_thread_id(thread_id)
    engine = _get_engine(request, tid)

    facts = engine.get_structured_facts(thread_id=tid, scope=scope)

    return StructuredFactsResponse(
        thread_id=tid,
        facts=facts,
        count=len(facts)
    )


@router.get("/api/facts/search", response_model=list[EffectiveFactItem])
def search_structured_facts(
    request: Request,
    thread_id: str = Query(default="default"),
    q: str = Query(min_length=1),
    scope: str = Query(default="effective"),
    limit: int = Query(default=10, ge=1, le=50),
) -> list[EffectiveFactItem]:
    tid = sanitize_thread_id(thread_id)
    engine = _get_engine(request, tid)

    scope_key = str(scope or "effective").strip().lower()
    if scope_key == "effective":
        results = engine.search_effective_user_facts(q, thread_id=tid, limit=limit)
    else:
        facts = engine.get_structured_facts(thread_id=tid, scope=scope_key)
        query_lower = str(q or "").strip().lower()
        results = []
        for slot, fact in (facts or {}).items():
            value = str((fact or {}).get("value") or "")
            haystack = f"{slot} {value}".lower()
            if query_lower and query_lower not in haystack:
                continue
            results.append(
                {
                    "slot": str(slot),
                    "value": value,
                    "source_surface": scope_key,
                    "source_thread": (fact or {}).get("thread_id") or (fact or {}).get("source_thread") or tid,
                    "authority": str((fact or {}).get("authority") or "confirmed"),
                    "origin": (fact or {}).get("origin"),
                    "confidence": (fact or {}).get("confidence"),
                    "trust": (fact or {}).get("trust"),
                    "timestamp": (fact or {}).get("timestamp"),
                    "memory_id": (fact or {}).get("memory_id"),
                }
            )
        results = results[:limit]

    return [EffectiveFactItem(**item) for item in results]


@router.get("/api/facts/history/{slot}")
def get_fact_history(
    slot: str,
    request: Request,
    thread_id: str = Query(default="default"),
) -> FactHistoryResponse:
    """Get history for a specific fact slot."""
    tid = sanitize_thread_id(thread_id)
    engine = _get_engine(request, tid)

    history: List[Dict[str, Any]] = []
    if hasattr(engine, 'fact_store') and engine.fact_store:
        # Normalize slot name
        if not slot.startswith("user."):
            slot = f"user.{slot}"
        history = engine.fact_store.get_history(slot, thread_id=tid)

    return FactHistoryResponse(
        thread_id=tid,
        slot=slot,
        history=history
    )


# ========================================================================
# Dashboard
# ========================================================================

@router.get("/api/dashboard/overview", response_model=DashboardOverviewResponse)
def dashboard_overview(request: Request, thread_id: str = Query(default="default"), authorization: Optional[str] = Header(None)) -> DashboardOverviewResponse:
    engine = _get_engine(request, thread_id)
    tid = sanitize_thread_id(thread_id)
    uid = resolve_user_id(authorization)

    try:
        global_memories_total = len(engine.memory._load_all_memories(user_id=uid))
    except Exception:
        global_memories_total = 0

    memories_total = len(_recent_scope_items(engine, tid, user_id=uid))

    try:
        effective_facts_total = len(engine.get_structured_facts(thread_id=tid, scope="effective"))
    except Exception:
        effective_facts_total = 0

    try:
        open_contradictions = len(engine.ledger.get_open_contradictions(limit=10_000, thread_id=tid))
    except Exception:
        try:
            open_contradictions = len(engine.ledger.get_open_contradictions(limit=10_000))
        except Exception:
            open_contradictions = 0

    try:
        ratio = engine.memory.get_belief_speech_ratio(limit=100)
    except Exception:
        ratio = {"belief_ratio": 0.0, "speech_ratio": 0.0, "belief_count": 0, "speech_count": 0}

    model_routing: Optional[ModelRoutingInfo] = None
    try:
        router_obj = getattr(request.app.state, "model_router", None)
        if router_obj is not None and hasattr(router_obj, "models"):
            m = router_obj.models
            model_routing = ModelRoutingInfo(
                default=m.get("default"),
                fast=m.get("fast"),
                reasoning=m.get("reasoning"),
                code=m.get("code"),
                research=m.get("research"),
            )
    except Exception:
        pass

    return DashboardOverviewResponse(
        thread_id=tid,
        session_id=getattr(engine, "session_id", None),
        memories_total=memories_total,
        global_memories_total=global_memories_total,
        effective_facts_total=effective_facts_total,
        open_contradictions=open_contradictions,
        belief_ratio=float(ratio.get("belief_ratio") or 0.0),
        speech_ratio=float(ratio.get("speech_ratio") or 0.0),
        belief_count=int(ratio.get("belief_count") or 0),
        speech_count=int(ratio.get("speech_count") or 0),
        memory_scope="thread",
        contradiction_scope="thread",
        belief_speech_scope="global_7d",
        model_routing=model_routing,
    )


# ========================================================================
# Memory
# ========================================================================

# Exclusive slots: any two different non-empty values for these slots = contradiction.
# Mirrors GroundCheck.KNOWN_EXCLUSIVE_SLOTS.
_EXCLUSIVE_SLOTS = {
    "employer", "location", "name", "title", "occupation",
    "coffee", "favorite_color", "favorite_food", "pet", "school",
    "undergrad_school", "masters_school", "graduation_year", "project",
    "age", "birthday", "birth_year", "height", "weight", "diet",
    "relationship", "salary", "budget", "database", "os", "editor",
    "framework", "cloud", "api_url", "programming_language",
    "programming_years",
    # assistant_name intentionally excluded — it's a system config, not a user fact,
    # and LLMs hallucinate it from sentences like "I'm happy that you are starting to work"
}

# Patterns that catch "My X is Y" and similar natural-language slot declarations
# that extract_fact_slots misses. Yields (slot, value) pairs.
_GENERIC_SLOT_RE = [
    # "My X is Y" / "my X is Y" — most natural form
    (
        "generic_my",
        _re.compile(
            r"\bmy\s+(?:favorite\s+)?(?:current\s+)?([a-zA-Z][a-zA-Z _]{1,40}?)\s+is\s+([^\.,;!?\n]{1,60})",
            _re.IGNORECASE,
        ),
    ),
    # "I prefer X" / "I like X best"
    (
        "generic_prefer",
        _re.compile(
            r"\bi\s+(?:prefer|like|use|love|enjoy)\s+([a-zA-Z][a-zA-Z0-9+#._-]{1,40})\b",
            _re.IGNORECASE,
        ),
    ),
]


def _extract_slots_broad(text: str, engine) -> Dict[str, str]:
    """
    Extract slot→value pairs using all available methods.

    Order of precedence:
    1. Tier-A regex (extract_fact_slots)
    2. Two-tier LLM extraction if engine has it
    3. Generic "My X is Y" regex fallback
    """
    results: Dict[str, str] = {}

    # Tier A
    try:
        tier_a = extract_fact_slots(text) or {}
        for slot, fact in tier_a.items():
            results[slot.lower()] = str(fact.value).strip()
    except Exception:
        pass

    # Tier B (LLM open tuples) — skip_llm=True to stay fast and sync
    try:
        two_tier = getattr(engine, "two_tier_system", None)
        if two_tier is not None:
            result = two_tier.extract_facts(text, skip_llm=True)
            for t in result.open_tuples:
                if t.confidence >= 0.5:
                    results[t.attribute.lower()] = str(t.value).strip()
    except Exception:
        pass

    # Generic fallback: "My X is Y"
    try:
        for _name, pat in _GENERIC_SLOT_RE:
            for m in pat.finditer(text):
                grps = m.groups()
                if len(grps) == 2:
                    slot_raw = grps[0].strip().lower().replace(" ", "_").replace("-", "_")
                    # Strip leading "favorite_" so "favorite_programming_language" and
                    # "programming_language" resolve to the same slot key.
                    slot_key = slot_raw.removeprefix("favorite_")
                    val_raw = grps[1].strip().rstrip(".,;!?")
                    if slot_key and val_raw and slot_key not in results:
                        results[slot_key] = val_raw
                elif len(grps) == 1:
                    # prefer/use pattern — value only, slot inferred from context
                    val_raw = grps[0].strip()
                    if val_raw:
                        results.setdefault("_inferred", val_raw)
    except Exception:
        pass

    return results


def _check_inline_contradiction(
    engine,
    new_text: str,
    new_memory_id: str,
    thread_id: str,
    *,
    new_origin: Optional[str] = None,
) -> tuple:
    """
    Returns (contradiction_detected: bool, contradiction_info: str | None).

    Strategy:
    1. Extract slots from new text (broad extraction).
    2. For each existing memory, extract its slots.
    3. If the same slot appears with a different value AND the slot is exclusive → contradiction.
    4. Fallback: run heuristic_contradiction on the raw texts for non-slot cases.
    """
    from sse.contradictions import heuristic_contradiction

    new_slots = _extract_slots_broad(new_text, engine)

    try:
        existing_memories = engine._load_thread_user_memories(
            thread_id=thread_id,
            exclude_memory_id=new_memory_id,
        )
    except Exception:
        return False, None

    # Only check user-sourced memories; cap scan to avoid O(n²) on large stores
    user_mems = [
        m
        for m in existing_memories
        if engine.memory.can_update_user_profile(m) and not bool(getattr(m, "deprecated", False))
    ][:200]

    for existing_mem in user_mems:
        eid = str(getattr(existing_mem, "memory_id", "") or "")
        if eid == new_memory_id:
            continue
        existing_text = str(getattr(existing_mem, "text", "") or "").strip()
        if not existing_text:
            continue
        if new_origin and str(getattr(existing_mem, "origin", "") or "").strip() == str(new_origin).strip():
            continue

        # Slot-based comparison (fast path for exclusive slots)
        if new_slots:
            existing_slots = _extract_slots_broad(existing_text, engine)
            for slot, new_val in new_slots.items():
                if not new_val or slot not in existing_slots:
                    continue
                if slot == "name" and not is_explicit_name_declaration_text(existing_text):
                    continue
                old_val = existing_slots[slot]
                if not old_val or new_val.lower() == old_val.lower():
                    continue
                if slot == "name" and names_look_equivalent(old_val, new_val):
                    continue
                # For exclusive slots: different value = contradiction, no NLP needed
                # Sprint 6: dynamic slot type lookup with fallback to legacy list
                try:
                    from personal_agent.slot_discovery import get_slot_type, SlotType as _SlotType
                    _dyn_type = get_slot_type(slot)
                    is_exclusive = _dyn_type == _SlotType.EXCLUSIVE or (_dyn_type == _SlotType.UNKNOWN and (slot in _EXCLUSIVE_SLOTS or slot.startswith("favorite_")))
                except Exception:
                    is_exclusive = slot in _EXCLUSIVE_SLOTS or slot.startswith("favorite_")
                if is_exclusive:
                    info = (
                        f"slot={slot!r} old={old_val!r} new={new_val!r} "
                        f"(memory {eid})"
                    )
                    get_judgment_log().log(
                        CONTRADICTION_STORE,
                        f"Exclusive slot conflict on store: {slot!r} {old_val!r} → {new_val!r}",
                        slot=slot,
                        old_value=old_val,
                        new_value=new_val,
                        memory_id=new_memory_id,
                        thread_id=thread_id,
                    )
                    return True, info

    # Heuristic fallback is audit-only; do not expose it as a public contradiction flag.
    if not new_slots:
        for existing_mem in user_mems:
            eid = str(getattr(existing_mem, "memory_id", "") or "")
            if eid == new_memory_id:
                continue
            existing_text = str(getattr(existing_mem, "text", "") or "").strip()
            if not existing_text:
                continue
            try:
                label = heuristic_contradiction(new_text, existing_text)
                if label == "contradiction":
                    get_judgment_log().log(
                        CONTRADICTION_STORE,
                        "Heuristic contradiction detected on store",
                        old_value=existing_text[:120],
                        new_value=new_text[:120],
                        memory_id=new_memory_id,
                        thread_id=thread_id,
                    )
                    if hasattr(engine, "memory"):
                        engine.memory.record_memory_event(
                            memory_id=new_memory_id,
                            event_type="heuristic_conflict_observed",
                            actor="system",
                            reason="inline_store_heuristic_conflict",
                            metadata={
                                "thread_id": thread_id,
                                "conflicting_memory_id": eid,
                            },
                        )
                    return False, None
            except Exception:
                pass

    return False, None


@router.post("/api/memory/store", response_model=MemoryStoreResponse)
def memory_store(req: MemoryStoreRequest, request: Request, authorization: Optional[str] = Header(None)) -> MemoryStoreResponse:
    tid = sanitize_thread_id(req.thread_id)
    engine = _get_engine(request, tid)
    uid = resolve_user_id(authorization)

    try:
        source = MemorySource(str(req.source or "user").strip().lower())
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid memory source: {req.source}") from e

    context = dict(req.context or {})
    context.setdefault("thread_id", tid)

    ingest_result = engine.ingest_memory_write(
        text=req.text,
        confidence=float(req.confidence),
        source=source,
        context=context,
        user_marked_important=bool(req.user_marked_important),
        contradiction_signal=float(req.contradiction_signal or 0.0),
        thread_id=tid,
        authority=req.authority,
        channel=req.channel,
        origin=req.origin,
        kind=req.kind,
        source_kind=req.source_kind,
        model_id=req.model_id,
        run_id=req.run_id,
        user_id=uid,
    )
    mem = ingest_result["memory"]
    fact_store_updated = bool(ingest_result.get("fact_store_updated"))

    # --- Inline synchronous contradiction check ---
    contradiction_detected = False
    contradiction_info: Optional[str] = None
    try:
        if hasattr(engine, "memory") and engine.memory.can_update_user_profile(mem):
            contradiction_detected, contradiction_info = _check_inline_contradiction(
                engine=engine,
                new_text=req.text,
                new_memory_id=str(getattr(mem, "memory_id", "") or ""),
                thread_id=tid,
                new_origin=getattr(mem, "origin", None),
            )
    except Exception as e:
        logger.warning(f"[MEMORY_STORE] Inline contradiction check failed for thread {tid}: {e}")

    return MemoryStoreResponse(
        stored=True,
        memory=MemoryListItem(**_memory_item_to_dict(mem)),
        fact_store_updated=fact_store_updated,
        contradiction_detected=contradiction_detected,
        contradiction_info=contradiction_info,
    )

@router.get("/api/memory/recent", response_model=list[MemoryListItem])
def memory_recent(request: Request, thread_id: str = Query(default="default"), limit: int = Query(default=30, ge=1, le=200), authorization: Optional[str] = Header(None)) -> list[MemoryListItem]:
    tid = sanitize_thread_id(thread_id)
    engine = _get_engine(request, tid)
    uid = resolve_user_id(authorization)
    items = _recent_scope_items(engine, tid, user_id=uid)
    items.sort(key=lambda m: float(getattr(m, "timestamp", 0.0) or 0.0), reverse=True)

    out: list[MemoryListItem] = []
    for mem in items[:limit]:
        out.append(MemoryListItem(**_memory_item_to_dict(mem)))
    return out


@router.get("/api/memory/search", response_model=list[MemoryListItem])
def memory_search(
    request: Request,
    thread_id: str = Query(default="default"),
    q: str = Query(min_length=1),
    k: int = Query(default=10, ge=1, le=50),
    min_trust: float = Query(default=0.0, ge=0.0, le=1.0),
    authorization: Optional[str] = Header(None),
) -> list[MemoryListItem]:
    tid = sanitize_thread_id(thread_id)
    engine = _get_engine(request, tid)
    uid = resolve_user_id(authorization)
    try:
        retrieved = engine.retrieve(
            q,
            k=k,
            min_trust=min_trust,
            thread_id=tid,
            usage_reason="api_memory_search",
            usage_metadata={"endpoint": "/api/memory/search"},
        )
    except Exception:
        retrieved = []

    def _matches_scope(mem) -> bool:
        """When user_id is available, match by user; else fall back to thread."""
        if uid:
            return str(getattr(mem, "user_id", "") or "") == uid
        mt = str(getattr(mem, "thread_id", "") or "")
        if tid == "default":
            return not mt or mt.lower() in ("default", "")
        return mt == tid

    inferred_slots = []
    try:
        inferred_slots = list(engine._infer_slots_from_query(q))
    except Exception:
        inferred_slots = []

    def _supports_inferred_slot(mem) -> bool:
        if not inferred_slots:
            return True
        try:
            facts = extract_fact_slots(str(getattr(mem, "text", "") or "")) or {}
        except Exception:
            facts = {}
        fact_slots = {str(slot or "").strip().lower() for slot in facts.keys()}
        return any(str(slot or "").strip().lower() in fact_slots for slot in inferred_slots)

    out: list[MemoryListItem] = []
    for mem, _score in retrieved:
        if not _matches_scope(mem):
            continue
        if not _supports_inferred_slot(mem):
            continue
        out.append(MemoryListItem(**_memory_item_to_dict(mem)))
    return out


@router.get("/api/memory/usage/summary", response_model=list[MemoryUsageSummaryItem])
def memory_usage_summary(
    request: Request,
    thread_id: str = Query(default="default"),
    limit: int = Query(default=25, ge=1, le=200),
    since_timestamp: Optional[float] = Query(default=None),
) -> list[MemoryUsageSummaryItem]:
    tid = sanitize_thread_id(thread_id)
    engine = _get_engine(request, tid)
    try:
        summary = engine.memory.get_memory_usage_summary(
            thread_id=tid,
            since_timestamp=since_timestamp,
            limit=limit,
        )
    except Exception:
        summary = []
    return [MemoryUsageSummaryItem(**item) for item in summary]


@router.get("/api/memory/trust-delta")
def memory_trust_delta(
    request: Request,
    thread_id: str = Query(default="default"),
    since_ts: float = Query(default=0.0, description="Unix timestamp; return trust movements after this point"),
    limit: int = Query(default=30, ge=1, le=200),
) -> list[dict]:
    """Return recent trust movements for the TrustDeltaStrip UI component.

    Joins trust_log against memories to include a text preview so the UI can
    display which claim shifted without a second round-trip.
    """
    tid = sanitize_thread_id(thread_id)
    engine = _get_engine(request, tid)
    try:
        db_path = str(getattr(engine.memory, "db_path", ""))
        if not db_path:
            return []
        with get_db_connection(db_path) as conn:
            rows = conn.execute(
                """
                SELECT
                    tl.memory_id,
                    COALESCE(tl.old_trust, 0.5) AS old_trust,
                    COALESCE(tl.new_trust, 0.5) AS new_trust,
                    tl.timestamp,
                    tl.reason,
                    COALESCE(substr(m.text, 1, 100), '') AS text_preview
                FROM trust_log tl
                LEFT JOIN memories m ON m.memory_id = tl.memory_id
                WHERE tl.timestamp > ?
                ORDER BY tl.timestamp DESC
                LIMIT ?
                """,
                (since_ts, limit),
            ).fetchall()
        return [
            {
                "memory_id": r[0],
                "old_trust": round(float(r[1]), 3),
                "new_trust": round(float(r[2]), 3),
                "delta": round(float(r[2]) - float(r[1]), 3),
                "timestamp": float(r[3]),
                "reason": r[4] or "",
                "text_preview": r[5] or "",
            }
            for r in rows
        ]
    except Exception as exc:
        logger.warning("[trust-delta] query failed: %s", exc)
        return []


@router.get("/api/memory/{memory_id}/events", response_model=list[MemoryEventItem])
def memory_events(
    memory_id: str,
    request: Request,
    thread_id: str = Query(default="default"),
    event_type: Optional[str] = Query(default=None),
) -> list[MemoryEventItem]:
    tid = sanitize_thread_id(thread_id)
    engine = _get_engine(request, tid)
    try:
        events = engine.memory.get_memory_events(memory_id, event_type=event_type)
    except Exception:
        events = []
    return [MemoryEventItem(**event) for event in events]


@router.get("/api/memory/{memory_id}", response_model=MemoryListItem)
def memory_get(memory_id: str, request: Request, thread_id: str = Query(default="default")) -> MemoryListItem:
    engine = _get_engine(request, thread_id)
    mem = engine.memory.get_memory_by_id(memory_id)
    if mem is None:
        return MemoryListItem(
            memory_id=memory_id,
            text="",
            timestamp=0.0,
            confidence=0.0,
            trust=0.0,
            source="",
            sse_mode="",
            thread_id=None,
        )
    return MemoryListItem(**_memory_item_to_dict(mem))


@router.get("/api/memory/{memory_id}/trust", response_model=list[dict])
def memory_trust_history(memory_id: str, request: Request, thread_id: str = Query(default="default")) -> list[dict]:
    engine = _get_engine(request, thread_id)
    try:
        return engine.memory.get_trust_history(memory_id)
    except Exception:
        return []


@router.get("/api/memory/{memory_id}/provenance")
def memory_provenance(
    memory_id: str,
    request: Request,
    thread_id: str = Query(default="default"),
) -> Dict[str, Any]:
    """
    Isnad chain for a memory: who said it, on what channel, under what
    authority, trust trajectory, and any contradiction events it was involved in.

    Returns a structured provenance chain — each link has a type and timestamp
    so callers can reconstruct the epistemic history of this fact.
    """
    engine = _get_engine(request, thread_id)
    mem = engine.memory.get_memory_by_id(memory_id)
    if mem is None:
        return {"memory_id": memory_id, "found": False, "chain": []}

    chain: List[Dict[str, Any]] = []

    # Link 0 — creation
    chain.append({
        "link": "created",
        "timestamp": float(getattr(mem, "timestamp", 0.0) or 0.0),
        "source": getattr(getattr(mem, "source", None), "value", None) or str(getattr(mem, "source", "")),
        "source_kind": str(getattr(mem, "source_kind", "principal") or "principal"),
        "channel": str(getattr(mem, "channel", "unknown") or "unknown"),
        "origin": getattr(mem, "origin", None),
        "authority": str(getattr(mem, "authority", "confirmed") or "confirmed"),
        "model_id": getattr(mem, "model_id", None),
        "run_id": getattr(mem, "run_id", None),
        "initial_trust": float(getattr(mem, "trust", 0.0) or 0.0),
        "confidence": float(getattr(mem, "confidence", 0.0) or 0.0),
    })

    # Trust history links
    try:
        trust_history = engine.memory.get_trust_history(memory_id) or []
        for th in trust_history:
            chain.append({
                "link": "trust_update",
                "timestamp": float(th.get("timestamp") or 0.0),
                "trust_before": th.get("trust_before"),
                "trust_after": th.get("trust_after"),
                "reason": th.get("reason"),
            })
    except Exception:
        pass

    # Contradiction links — this memory as old or new side
    try:
        all_contradictions = engine.ledger.get_all_contradictions(limit=5000)
        for entry in all_contradictions:
            old_id = str(getattr(entry, "old_memory_id", "") or "")
            new_id = str(getattr(entry, "new_memory_id", "") or "")
            if memory_id not in (old_id, new_id):
                continue
            role = "superseded_by" if memory_id == old_id else "supersedes"
            other_id = new_id if memory_id == old_id else old_id
            chain.append({
                "link": "contradiction",
                "timestamp": float(getattr(entry, "timestamp", 0.0) or 0.0),
                "role": role,
                "other_memory_id": other_id,
                "ledger_id": str(getattr(entry, "ledger_id", "") or ""),
                "contradiction_type": str(getattr(entry, "contradiction_type", "") or ""),
                "status": str(getattr(entry, "status", "") or ""),
                "drift_mean": float(getattr(entry, "drift_mean", 0.0) or 0.0),
            })
    except Exception:
        pass

    # Memory usage events
    try:
        usage_events = engine.memory.get_memory_events(memory_id) or []
        for ev in usage_events:
            chain.append({
                "link": "usage",
                "timestamp": float(ev.get("timestamp") or 0.0),
                "event_type": ev.get("event_type"),
                "actor": ev.get("actor"),
                "reason": ev.get("reason"),
            })
    except Exception:
        pass

    # Sort chain chronologically
    chain.sort(key=lambda x: float(x.get("timestamp") or 0.0))

    return {
        "memory_id": memory_id,
        "found": True,
        "text": str(getattr(mem, "text", "") or ""),
        "kind": str(getattr(mem, "kind", "observation") or "observation"),
        "current_trust": float(getattr(mem, "trust", 0.0) or 0.0),
        "chain": chain,
        "chain_length": len(chain),
    }


# ========================================================================
# Audit
# ========================================================================

@router.get("/api/audit/judgments")
def audit_judgments(
    request: Request,
    limit: int = Query(default=100, ge=1, le=500),
    event_type: Optional[str] = Query(default=None, description="Filter by event_type"),
) -> List[Dict[str, Any]]:
    """
    Silent judgment log — every gate decision that changed what was stored
    or said: DisclosurePolicy REJECT/CLARIFY, inline contradiction on store,
    CRT-as-Critic blocks.

    Returns most-recent entries first (today's log file).
    """
    try:
        return get_judgment_log().recent(limit=limit, event_type=event_type)
    except Exception as e:
        logger.warning(f"[AUDIT] Failed to read judgment log: {e}")
        return []


# ============================================================================
# Sprint 9: Belief Synthesis API
# ============================================================================

class SynthesisRequest(BaseModel):
    query: str
    thread_id: str = "default"


@router.post("/api/synthesis")
def run_synthesis(
    body: SynthesisRequest,
    request: Request,
) -> Dict[str, Any]:
    """Run belief synthesis: thematic, trajectory, or contradiction-aware.

    Answers worldview questions from compressed belief trajectories.
    """
    from personal_agent.belief_synthesis import synthesize, classify_synthesis_query
    from personal_agent.cloud_features import get_cloud_feature_service
    from personal_agent.local_only_policy import is_strict_local_only_mode

    engine: CRTEnhancedRAG = request.app.state.engine

    synthesis_type = classify_synthesis_query(body.query)
    if synthesis_type is None:
        return {"error": "Not a synthesis query", "query": body.query}

    # Load all user memories
    try:
        all_mems = [
            m for m in engine.memory._load_all_memories()
            if getattr(m, "source", None) in (MemorySource.USER, MemorySource.EXTERNAL)
            and not getattr(m, "deprecated", False)
        ]
    except Exception as e:
        logger.warning("[SYNTHESIS_API] Failed to load memories: %s", e)
        all_mems = []

    cloud = None if is_strict_local_only_mode(uid=1) else get_cloud_feature_service()
    result = synthesize(
        query=body.query,
        memories=all_mems,
        ledger=engine.ledger,
        cloud_service=cloud,
        thread_id=body.thread_id,
    )
    return result.to_dict()


@router.get("/api/belief-trajectory/{slot}")
def get_belief_trajectory(
    slot: str,
    request: Request,
    thread_id: str = Query(default="default"),
    min_trust: float = Query(default=0.0, ge=0.0, le=1.0),
) -> Dict[str, Any]:
    """Get temporal belief trajectory for a specific slot."""
    from personal_agent.belief_synthesis import build_belief_trajectory

    engine: CRTEnhancedRAG = request.app.state.engine

    try:
        all_mems = [
            m for m in engine.memory._load_all_memories()
            if getattr(m, "source", None) in (MemorySource.USER, MemorySource.EXTERNAL)
            and not getattr(m, "deprecated", False)
            and getattr(m, "trust", 0) >= min_trust
        ]
    except Exception:
        all_mems = []

    traj = build_belief_trajectory(all_mems, slot)
    if traj is None:
        return {"slot": slot, "trajectory": None, "message": "Not enough data points"}
    return {"slot": slot, "trajectory": traj.to_dict()}


# ============================================================================
# Sprint 10: Volatility Context API
# ============================================================================

@router.get("/api/context-budget")
def get_context_budget(
    request: Request,
    query: str = Query(description="Query to compute budget for"),
    thread_id: str = Query(default="default"),
    total_budget: int = Query(default=6000, ge=1000, le=20000),
) -> Dict[str, Any]:
    """Compute and return context budget allocation for a query (debugging/introspection)."""
    from personal_agent.volatility_context import allocate_context_budget

    engine: CRTEnhancedRAG = request.app.state.engine

    # Run retrieval
    try:
        retrieved = engine.retrieve(query, k=10, thread_id=thread_id)
    except Exception:
        retrieved = []

    budget = allocate_context_budget(
        query=query,
        retrieved=retrieved,
        total_budget=total_budget,
        ledger=engine.ledger,
        memory_system=engine.memory,
    )
    return budget.to_dict()


@router.get("/api/memory/{memory_id}/volatility")
def get_memory_volatility(
    memory_id: str,
    request: Request,
) -> Dict[str, Any]:
    """Get volatility profile for a single memory."""
    from personal_agent.volatility_context import get_volatility_profile

    engine: CRTEnhancedRAG = request.app.state.engine

    mem = engine.memory.get_memory_by_id(memory_id)
    if mem is None:
        raise HTTPException(status_code=404, detail="Memory not found")

    profile = get_volatility_profile(mem, engine.ledger, engine.memory)
    return profile.to_dict()


@router.get("/api/volatile-memories")
def list_volatile_memories(
    request: Request,
    thread_id: str = Query(default="default"),
    limit: int = Query(default=10, ge=1, le=50),
    min_volatility: float = Query(default=0.4, ge=0.0, le=1.0),
) -> List[Dict[str, Any]]:
    """List memories with high volatility (V(t) above threshold)."""
    from personal_agent.volatility_context import compute_memory_volatility

    engine: CRTEnhancedRAG = request.app.state.engine

    try:
        all_mems = [
            m for m in engine.memory._load_all_memories()
            if not getattr(m, "deprecated", False)
        ]
    except Exception:
        return []

    volatile = []
    for mem in all_mems:
        vol = compute_memory_volatility(mem, engine.ledger, engine.memory)
        if vol >= min_volatility:
            volatile.append({
                "memory_id": mem.memory_id,
                "text": mem.text[:200],
                "trust": mem.trust,
                "volatility": round(vol, 3),
                "source": mem.source.value if hasattr(mem.source, "value") else str(mem.source),
                "contradiction_count": getattr(mem, "contradiction_count", 0),
            })

    # Sort by volatility descending
    volatile.sort(key=lambda x: x["volatility"], reverse=True)
    return volatile[:limit]


# ========================================================================
# Variance Tracker — opinion/belief drift over time
# ========================================================================


@router.get("/api/variance/topics")
def variance_topics(
    request: Request,
    thread_id: str = Query(default="default"),
    min_entries: int = Query(default=3),
):
    """List discovered topics with per-topic variance metrics."""
    engine = _get_engine(request, thread_id)
    try:
        from personal_agent.variance_tracker import VarianceTracker
        tracker = VarianceTracker(db_path=engine.memory.db_path)
        topics = tracker.get_all_topics_summary(min_entries=min_entries)
        snapshot = tracker.get_global_snapshot()
        return {"topics": topics, "snapshot": snapshot}
    except Exception as e:
        logger.warning(f"[VARIANCE] topics error: {e}")
        return {"topics": [], "snapshot": None, "error": str(e)}


@router.get("/api/variance/topic/{topic_id}")
def variance_topic_detail(
    topic_id: int,
    request: Request,
    thread_id: str = Query(default="default"),
):
    """Detailed per-topic variance data with per-entry drift series."""
    engine = _get_engine(request, thread_id)
    try:
        from personal_agent.variance_tracker import VarianceTracker
        tracker = VarianceTracker(db_path=engine.memory.db_path)
        detail = tracker.get_topic_detail(topic_id)
        if not detail:
            raise HTTPException(status_code=404, detail=f"Topic {topic_id} not found")
        return detail
    except HTTPException:
        raise
    except Exception as e:
        logger.warning(f"[VARIANCE] topic detail error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/api/variance/analyze")
def variance_analyze(
    request: Request,
    thread_id: str = Query(default="default"),
):
    """Trigger on-demand variance analysis."""
    engine = _get_engine(request, thread_id)
    try:
        from personal_agent.variance_tracker import VarianceTracker
        from personal_agent.governance_bridge import GovernanceBridge
        tracker = VarianceTracker(db_path=engine.memory.db_path)
        bridge = GovernanceBridge(memory_system=engine.memory, variance_tracker=tracker)
        tracker.set_governance_bridge(bridge)
        result = tracker.run_analysis(force=True)
        return result
    except Exception as e:
        logger.warning(f"[VARIANCE] analyze error: {e}")
        return {"error": str(e)}


@router.get("/api/variance/embedding-map")
def variance_embedding_map(
    request: Request,
    thread_id: str = Query(default="default"),
    dimensions: int = Query(default=2, ge=2, le=3),
):
    """PCA-projected coordinates for belief map visualization (2D or 3D)."""
    engine = _get_engine(request, thread_id)
    try:
        from personal_agent.variance_tracker import VarianceTracker
        tracker = VarianceTracker(db_path=engine.memory.db_path)
        return tracker.get_embedding_map(dimensions=dimensions)
    except Exception as e:
        logger.warning(f"[VARIANCE] embedding-map error: {e}")
        return {"points": [], "contradictions": [], "topics": [], "error": str(e)}


@router.get("/api/variance/snapshots")
def variance_snapshots(
    request: Request,
    thread_id: str = Query(default="default"),
    limit: int = Query(default=20),
):
    """Historical variance snapshots for trending."""
    engine = _get_engine(request, thread_id)
    try:
        from personal_agent.variance_tracker import VarianceTracker
        tracker = VarianceTracker(db_path=engine.memory.db_path)
        return tracker.get_snapshots(limit=limit)
    except Exception as e:
        logger.warning(f"[VARIANCE] snapshots error: {e}")
        return []


# ── Alias Protection ────────────────────────────────────────────────────


@router.get("/api/memory/alias-stats")
async def alias_stats(request: Request, thread_id: str = Query(default="")):
    """Return alias protection coverage statistics."""
    engine = _get_engine(request, thread_id)
    try:
        stats = engine.memory.get_alias_stats()
        return stats
    except Exception as e:
        logger.warning("[ALIAS] stats error: %s", e)
        return {"total_aliases": 0, "aliased_memories": 0, "by_method": {}}


@router.get("/api/memory/aliases")
async def list_aliases(
    request: Request,
    memory_id: str = Query(...),
    thread_id: str = Query(default=""),
):
    """List alias embeddings for a specific memory."""
    engine = _get_engine(request, thread_id)
    conn = engine.memory._get_connection()
    rows = conn.execute(
        "SELECT alias_id, method, created_at FROM memory_aliases WHERE memory_id = ?",
        (memory_id,),
    ).fetchall()
    conn.close()
    return [
        {"alias_id": r[0], "method": r[1], "created_at": r[2]}
        for r in rows
    ]


@router.post("/api/memory/aliases/backfill")
async def backfill_aliases(
    request: Request,
    thread_id: str = Query(default=""),
    threshold_percentile: float = Query(default=97),
):
    """Generate aliases for all critical memories that don't have them yet."""
    engine = _get_engine(request, thread_id)
    user_id = resolve_user_id(request)
    result = engine.memory.backfill_aliases(
        user_id=user_id,
        threshold_percentile=threshold_percentile,
    )
    return result


# ---------------------------------------------------------------------------
# Inspectable Memory Index — Belief State per Memory
# ---------------------------------------------------------------------------

@router.get("/api/memory/index")
def memory_index(
    request: Request,
    thread_id: str = Query(default="default"),
    limit: int = Query(default=100, ge=1, le=500),
    min_trust: float = Query(default=0.0, ge=0.0, le=1.0),
    sort_by: str = Query(default="trust", pattern="^(trust|timestamp|compaction_count)$"),
    format: str = Query(default="json", pattern="^(json|text)$"),
    authorization: Optional[str] = Header(None),
):
    """Inspectable memory index with full belief state per memory.

    Each entry shows:
    - Memory text + trust score + authority
    - Contradiction status (open contradictions involving this memory)
    - Compaction history (how many times compacted, observation type)
    - Last confirmed/accessed timestamps
    - Whether it's held, resolved, or evolving

    This is not just what Aether knows — it's how much Aether trusts what it knows.
    """
    import time as _time
    tid = sanitize_thread_id(thread_id)
    engine = _get_engine(request, tid)
    uid = resolve_user_id(authorization)

    # Load all active memories
    items = _recent_scope_items(engine, tid, user_id=uid)
    items = [m for m in items if getattr(m, "trust", 0) >= min_trust]

    # Sort
    if sort_by == "trust":
        items.sort(key=lambda m: float(getattr(m, "trust", 0)), reverse=True)
    elif sort_by == "timestamp":
        items.sort(key=lambda m: float(getattr(m, "timestamp", 0)), reverse=True)
    elif sort_by == "compaction_count":
        items.sort(key=lambda m: int(getattr(m, "compaction_count", 0) or 0), reverse=True)

    items = items[:limit]

    # Load contradiction status for these memories
    contradiction_map: Dict[str, list] = {}
    try:
        led_path = engine.memory.db_path.replace("crt_memory", "crt_ledger")
        if Path(led_path).exists():
            with get_db_connection(led_path) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT ledger_id, old_memory_id, new_memory_id, status,
                           disposition, drift_mean, contradiction_type
                    FROM contradictions
                    WHERE status IN ('open', 'reflecting')
                """)
                for row in cursor.fetchall():
                    for mid in (row[1], row[2]):
                        if mid:
                            contradiction_map.setdefault(mid, []).append({
                                "ledger_id": row[0],
                                "other_memory_id": row[2] if mid == row[1] else row[1],
                                "status": row[3],
                                "disposition": row[4],
                                "drift": round(row[5], 3) if row[5] else None,
                                "type": row[6],
                            })
    except Exception:
        pass

    # Build index entries
    entries = []
    for mem in items:
        mid = getattr(mem, "memory_id", "")
        trust = round(float(getattr(mem, "trust", 0)), 3)
        confidence = round(float(getattr(mem, "confidence", 0)), 3)
        authority = getattr(mem, "authority", "confirmed")
        source_kind = getattr(mem, "source_kind", "principal")
        kind = getattr(mem, "kind", "observation")
        text = getattr(mem, "text", "")
        ts = getattr(mem, "timestamp", 0)
        obs_type = getattr(mem, "observation_type", "direct") or "direct"
        comp_count = int(getattr(mem, "compaction_count", 0) or 0)
        last_compacted = getattr(mem, "last_compacted", None)
        last_accessed = getattr(mem, "last_accessed", None)
        belnap = getattr(mem, "belnap_state", "true")
        temporal = getattr(mem, "temporal_status", "active")
        contras = contradiction_map.get(mid, [])

        entry = {
            "memory_id": mid,
            "text": text[:300],
            "trust": trust,
            "confidence": confidence,
            "authority": authority,
            "source_kind": source_kind,
            "kind": kind,
            "timestamp": ts,
            "observation_type": obs_type,
            "compaction_count": comp_count,
            "last_compacted": last_compacted,
            "last_accessed": last_accessed,
            "belnap_state": belnap,
            "temporal_status": temporal,
            "contradictions": contras,
            "contradiction_count": len(contras),
        }
        entries.append(entry)

    if format == "text":
        return _render_text_index(entries)

    return {
        "thread_id": tid,
        "total": len(entries),
        "min_trust": min_trust,
        "sort_by": sort_by,
        "generated_at": _time.time(),
        "entries": entries,
    }


def _render_text_index(entries: list) -> dict:
    """Render the memory index as human-readable text.

    Format:
    Nick prefers concise communication (T:0.92, confirmed, direct, no contradictions)
    Nick works at Aeteros (T:0.85, confirmed, survived 2 compactions, 1 open contradiction)
    """
    lines = [f"# Memory Index ({len(entries)} entries)\n"]

    # Group by authority
    locked = [e for e in entries if e["authority"] == "locked"]
    confirmed = [e for e in entries if e["authority"] == "confirmed"]
    provisional = [e for e in entries if e["authority"] == "provisional"]

    if locked:
        lines.append("## Locked (immutable)")
        for e in locked:
            lines.append(_format_index_line(e))
        lines.append("")

    if confirmed:
        lines.append("## Confirmed")
        for e in confirmed:
            lines.append(_format_index_line(e))
        lines.append("")

    if provisional:
        lines.append("## Provisional")
        for e in provisional:
            lines.append(_format_index_line(e))

    return {"text": "\n".join(lines), "total": len(entries)}


def _format_index_line(entry: dict) -> str:
    """Format a single memory index entry."""
    text = entry["text"][:120]
    trust = entry["trust"]
    auth = entry["authority"]
    obs = entry["observation_type"]
    comp = entry["compaction_count"]
    contras = entry["contradiction_count"]
    belnap = entry["belnap_state"]

    parts = [f"T:{trust:.2f}"]
    parts.append(auth)

    if obs == "survived_compaction":
        parts.append(f"survived {comp} compaction{'s' if comp != 1 else ''}")
    elif obs == "direct":
        parts.append("direct")

    if contras > 0:
        parts.append(f"{contras} contradiction{'s' if contras != 1 else ''}")
    else:
        parts.append("no contradictions")

    if belnap == "both":
        parts.append("HELD")
    elif belnap == "neither":
        parts.append("UNCERTAIN")

    return f"- {text} ({', '.join(parts)})"


# ---------------------------------------------------------------------------
# User Beliefs endpoint — the epistemic mirror
# ---------------------------------------------------------------------------

@router.get("/api/beliefs")
def list_user_beliefs(
    request: Request,
    thread_id: str = Query(default="default"),
    min_trust: float = Query(default=0.0, ge=0.0, le=1.0),
    limit: int = Query(default=50, ge=1, le=200),
    authorization: Optional[str] = Header(None),
):
    """List the user's tracked beliefs/positions with trust scores and contradiction status.

    Returns user_belief memories: positions, stances, opinions — not flat facts.
    Each belief includes trust score, temporal trajectory, and active contradictions.
    This is the epistemic mirror — showing the user the shape of their own convictions.
    """
    import time as _time

    tid = sanitize_thread_id(thread_id)
    engine = _get_engine(request, tid)
    uid = resolve_user_id(authorization)

    # Load all active user_belief AND user_fact memories — GLOBAL across all threads.
    # Beliefs are persistent user convictions, not thread-local context.
    # Using thread-scoped loading caused beliefs to "disappear" when a new
    # thread was created (each restart generates a new UUID thread).
    # NOTE: The belief classifier defaults to "user_fact" for most assertions;
    # only strong opinion markers get "user_belief". Including both kinds
    # ensures the page actually shows data instead of being perpetually empty.
    _BELIEF_KINDS = {"user_belief", "user_fact"}
    all_items = engine.memory._load_all_memories(user_id=uid) if uid else engine.memory._load_all_memories()
    beliefs = [
        m for m in all_items
        if getattr(m, "kind", "") in _BELIEF_KINDS
        and not getattr(m, "deprecated", False)
        and float(getattr(m, "trust", 0)) >= min_trust
    ]

    # Sort by trust descending (strongest convictions first)
    beliefs.sort(key=lambda m: float(getattr(m, "trust", 0)), reverse=True)
    beliefs = beliefs[:limit]

    # Load contradiction map
    contradiction_map: Dict[str, list] = {}
    try:
        led_path = engine.memory.db_path.replace("crt_memory", "crt_ledger")
        if Path(led_path).exists():
            with get_db_connection(led_path) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT ledger_id, old_memory_id, new_memory_id, status,
                           disposition, drift_mean
                    FROM contradictions
                    WHERE status IN ('open', 'reflecting')
                """)
                for row in cursor.fetchall():
                    for mid in (row[1], row[2]):
                        if mid:
                            contradiction_map.setdefault(mid, []).append({
                                "ledger_id": row[0],
                                "other_memory_id": row[2] if mid == row[1] else row[1],
                                "status": row[3],
                                "disposition": row[4],
                                "drift": round(row[5], 3) if row[5] else None,
                            })
    except Exception:
        pass

    # Build response
    entries = []
    for mem in beliefs:
        mid = getattr(mem, "memory_id", "")
        contras = contradiction_map.get(mid, [])

        # Load trust trajectory (last 5 changes)
        trust_history = []
        try:
            conn = engine.memory._get_connection()
            cursor = conn.cursor()
            cursor.execute(
                "SELECT old_trust, new_trust, reason, timestamp FROM trust_log "
                "WHERE memory_id = ? ORDER BY timestamp DESC LIMIT 5",
                (mid,),
            )
            for row in cursor.fetchall():
                trust_history.append({
                    "from": round(row[0], 3),
                    "to": round(row[1], 3),
                    "reason": row[2],
                    "timestamp": row[3],
                })
            conn.close()
        except Exception:
            pass

        entries.append({
            "memory_id": mid,
            "text": getattr(mem, "text", ""),
            "kind": getattr(mem, "kind", "user_fact"),
            "trust": round(float(getattr(mem, "trust", 0)), 3),
            "confidence": round(float(getattr(mem, "confidence", 0)), 3),
            "authority": getattr(mem, "authority", "confirmed"),
            "belnap_state": getattr(mem, "belnap_state", "true"),
            "temporal_status": getattr(mem, "temporal_status", "active"),
            "created_at": getattr(mem, "timestamp", 0),
            "domain_tags": getattr(mem, "domain_tags", None),
            "contradictions": contras,
            "contradiction_count": len(contras),
            "trust_trajectory": trust_history,
        })

    # Summary stats
    total = len(entries)
    avg_trust = round(sum(e["trust"] for e in entries) / total, 3) if total else 0
    contested = sum(1 for e in entries if e["contradiction_count"] > 0)
    held = sum(1 for e in entries if e["belnap_state"] == "both")

    return {
        "thread_id": tid,
        "total_beliefs": total,
        "average_trust": avg_trust,
        "contested": contested,
        "held_contradictions": held,
        "generated_at": _time.time(),
        "beliefs": entries,
    }


# ------------------------------------------------------------------
# Cloud budget / gradient limiter endpoint
# ------------------------------------------------------------------

@router.get("/api/cloud/budget")
def cloud_budget() -> Dict[str, Any]:
    """Return current cloud spend, gradient multiplier, and per-feature limits."""
    from personal_agent.cloud_features import get_cloud_feature_service
    svc = get_cloud_feature_service()
    if svc is None:
        return {
            "daily_cost_usd": 0.0,
            "budget_ceiling": 10.0,
            "gradient_multiplier": 1.0,
            "features": {},
            "error": "CloudFeatureService not initialized",
        }
    svc._reset_daily_if_needed()
    gradient = svc._gradient_limit("cloud_generation")
    features: Dict[str, Any] = {}
    for feature in svc.daily_limits:
        base_limit = svc.daily_limits.get(feature, 0)
        effective = svc._effective_limit(feature)
        used = svc._daily_counts.get(feature, 0)
        status = "blocked" if effective == 0 else ("throttled" if used >= effective else "ok")
        features[feature] = {
            "base_limit": base_limit,
            "effective_limit": effective,
            "used": used,
            "status": status,
        }
    return {
        "daily_cost_usd": round(svc._daily_cost_usd, 4),
        "budget_ceiling": 10.0,
        "gradient_multiplier": round(gradient, 4),
        "features": features,
    }
