"""Memory, profile, facts, dashboard, and docs route module.

Extracted from crt_api.py — all data-access endpoints live here.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query, Request

import re as _re

from personal_agent.crt_core import MemorySource
from personal_agent.crt_rag import CRTEnhancedRAG
from personal_agent.fact_slots import extract_fact_slots, create_simple_fact
from personal_agent.judgment_audit_log import get_judgment_log, CONTRADICTION_STORE

from routes.deps import sanitize_thread_id
from routes.models import (
    ChatSendRequest,
    ChatSendResponse,
    DashboardOverviewResponse,
    DocGetResponse,
    DocListItem,
    ExtractedFactItem,
    FactExtractionRequest,
    FactExtractionResponse,
    FactHistoryResponse,
    MemoryEventItem,
    MemoryListItem,
    MemoryStoreRequest,
    MemoryStoreResponse,
    MemoryUsageSummaryItem,
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
        "authority": str(getattr(mem, "authority", "confirmed") or "confirmed"),
        "channel": str(getattr(mem, "channel", "unknown") or "unknown"),
        "origin": getattr(mem, "origin", None),
        "kind": str(getattr(mem, "kind", "observation") or "observation"),
        "review_after": getattr(mem, "review_after", None),
        "source_kind": str(getattr(mem, "source_kind", "principal") or "principal"),
        "model_id": getattr(mem, "model_id", None),
        "run_id": getattr(mem, "run_id", None),
    }


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
    # Stable ordering: docs first, then reference
    items.sort(key=lambda x: (0 if x.kind == "docs" else 1, x.title.lower()))
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
def get_profile(request: Request, thread_id: str = Query(default="default")) -> ProfileResponse:
    engine = _get_engine(request, thread_id)
    tid = sanitize_thread_id(thread_id)
    slots = _extract_latest_profile_slots(engine)
    name = slots.get("name")
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
def set_profile_name(req: ChatSendRequest, request: Request) -> ChatSendResponse:
    """Set profile name by sending a FACT message through CRT.

    Delegates to the main chat endpoint on the app — this ensures proper
    CRT processing.
    """
    from crt_api import chat_send
    return chat_send(req)


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
def get_structured_facts(request: Request, thread_id: str = Query(default="default")) -> StructuredFactsResponse:
    """Get all structured facts from FactStore."""
    tid = sanitize_thread_id(thread_id)
    engine = _get_engine(request, tid)

    facts: Dict[str, Any] = {}
    if hasattr(engine, 'fact_store') and engine.fact_store:
        facts = engine.fact_store.get_all_facts()

    return StructuredFactsResponse(
        thread_id=tid,
        facts=facts,
        count=len(facts)
    )


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
        history = engine.fact_store.get_history(slot)

    return FactHistoryResponse(
        thread_id=tid,
        slot=slot,
        history=history
    )


# ========================================================================
# Dashboard
# ========================================================================

@router.get("/api/dashboard/overview", response_model=DashboardOverviewResponse)
def dashboard_overview(request: Request, thread_id: str = Query(default="default")) -> DashboardOverviewResponse:
    engine = _get_engine(request, thread_id)
    tid = sanitize_thread_id(thread_id)

    try:
        memories_total = len(engine.memory._load_all_memories())
    except Exception:
        memories_total = 0

    try:
        open_contradictions = len(engine.ledger.get_open_contradictions(limit=10_000))
    except Exception:
        open_contradictions = 0

    try:
        ratio = engine.memory.get_belief_speech_ratio(limit=100)
    except Exception:
        ratio = {"belief_ratio": 0.0, "speech_ratio": 0.0, "belief_count": 0, "speech_count": 0}

    return DashboardOverviewResponse(
        thread_id=tid,
        session_id=getattr(engine, "session_id", None),
        memories_total=memories_total,
        open_contradictions=open_contradictions,
        belief_ratio=float(ratio.get("belief_ratio") or 0.0),
        speech_ratio=float(ratio.get("speech_ratio") or 0.0),
        belief_count=int(ratio.get("belief_count") or 0),
        speech_count=int(ratio.get("speech_count") or 0),
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
    "programming_years", "assistant_name",
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
    engine, new_text: str, new_memory_id: str, thread_id: str
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
        existing_memories = engine.memory._load_all_memories()
    except Exception:
        return False, None

    # Only check user-sourced memories; cap scan to avoid O(n²) on large stores
    user_mems = [
        m for m in existing_memories
        if str(getattr(getattr(m, "source", None), "value", "") or "").lower() == "user"
    ][:200]

    for existing_mem in user_mems:
        eid = str(getattr(existing_mem, "memory_id", "") or "")
        if eid == new_memory_id:
            continue
        existing_text = str(getattr(existing_mem, "text", "") or "").strip()
        if not existing_text:
            continue

        # Slot-based comparison (fast path for exclusive slots)
        if new_slots:
            existing_slots = _extract_slots_broad(existing_text, engine)
            for slot, new_val in new_slots.items():
                if not new_val or slot not in existing_slots:
                    continue
                old_val = existing_slots[slot]
                if not old_val or new_val.lower() == old_val.lower():
                    continue
                # For exclusive slots: different value = contradiction, no NLP needed
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

    # Heuristic fallback: only when slot extraction found nothing at all
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
                    info = f"heuristic conflict with memory {eid}"
                    get_judgment_log().log(
                        CONTRADICTION_STORE,
                        "Heuristic contradiction detected on store",
                        old_value=existing_text[:120],
                        new_value=new_text[:120],
                        memory_id=new_memory_id,
                        thread_id=thread_id,
                    )
                    return True, info
            except Exception:
                pass

    return False, None


@router.post("/api/memory/store", response_model=MemoryStoreResponse)
def memory_store(req: MemoryStoreRequest, request: Request) -> MemoryStoreResponse:
    tid = sanitize_thread_id(req.thread_id)
    engine = _get_engine(request, tid)

    try:
        source = MemorySource(str(req.source or "user").strip().lower())
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid memory source: {req.source}") from e

    context = dict(req.context or {})
    context.setdefault("thread_id", tid)

    mem = engine.memory.store_memory(
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
    )

    fact_store_updated = False
    try:
        if hasattr(engine, "memory") and engine.memory.can_update_user_profile(mem):
            fact_store = getattr(engine, "fact_store", None)
            if fact_store is not None:
                fact_result = fact_store.process_input(req.text)
                fact_store_updated = bool(
                    (fact_result or {}).get("extracted") or (fact_result or {}).get("updated")
                )
    except Exception as e:
        logger.debug(f"[MEMORY_STORE] FactStore update failed for thread {tid}: {e}")

    # --- Inline synchronous contradiction check ---
    contradiction_detected = False
    contradiction_info: Optional[str] = None
    try:
        contradiction_detected, contradiction_info = _check_inline_contradiction(
            engine=engine,
            new_text=req.text,
            new_memory_id=str(getattr(mem, "memory_id", "") or ""),
            thread_id=tid,
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
def memory_recent(request: Request, thread_id: str = Query(default="default"), limit: int = Query(default=30, ge=1, le=200)) -> list[MemoryListItem]:
    tid = sanitize_thread_id(thread_id)
    engine = _get_engine(request, tid)
    try:
        if tid == "default":
            # Default thread: include memories with NULL thread_id or explicit "default"
            all_items = engine.memory._load_all_memories()
            items: list = [
                m for m in all_items
                if not getattr(m, "thread_id", None)
                or str(m.thread_id).lower() in ("default", "")
            ]
        else:
            items = engine.memory._load_memories_filtered(thread_id=tid)
        items.sort(key=lambda m: float(getattr(m, "timestamp", 0.0) or 0.0), reverse=True)
    except Exception:
        items = []

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
) -> list[MemoryListItem]:
    tid = sanitize_thread_id(thread_id)
    engine = _get_engine(request, tid)
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

    def _matches_thread(mem) -> bool:
        mt = str(getattr(mem, "thread_id", "") or "")
        if tid == "default":
            return not mt or mt.lower() in ("default", "")
        return mt == tid

    out: list[MemoryListItem] = []
    for mem, _score in retrieved:
        if not _matches_thread(mem):
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
