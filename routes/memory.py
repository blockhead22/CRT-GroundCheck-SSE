"""Memory, profile, facts, dashboard, and docs route module.

Extracted from crt_api.py — all data-access endpoints live here.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query, Request

from personal_agent.crt_rag import CRTEnhancedRAG
from personal_agent.fact_slots import extract_fact_slots, create_simple_fact

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
    MemoryListItem,
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

@router.get("/api/memory/recent", response_model=list[MemoryListItem])
def memory_recent(request: Request, thread_id: str = Query(default="default"), limit: int = Query(default=30, ge=1, le=200)) -> list[MemoryListItem]:
    engine = _get_engine(request, thread_id)
    try:
        items = engine.memory._load_all_memories()
    except Exception:
        items = []

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
) -> list[MemoryListItem]:
    engine = _get_engine(request, thread_id)
    try:
        retrieved = engine.retrieve(q, k=k, min_trust=min_trust)
    except Exception:
        retrieved = []
    out: list[MemoryListItem] = []
    for mem, _score in retrieved:
        out.append(MemoryListItem(**_memory_item_to_dict(mem)))
    return out


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
