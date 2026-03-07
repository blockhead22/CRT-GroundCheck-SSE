"""Miscellaneous API routes: health, reasoning, reflection, journal, training,
introspection, loops, episodic, research, and heartbeat endpoints."""

from __future__ import annotations

import json
import logging
import os
import time
import traceback
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import StreamingResponse

from .deps import sanitize_thread_id
from .models import (
    CitationModel,
    EmailDigestRequest,
    EmailDigestResponse,
    HealthResponse,
    JournalReplyRequest,
    JournalReplyResponse,
    JournalSettingsRequest,
    JournalSettingsResponse,
    LoopRunRequest,
    LoopRunResponse,
    ResearchCitationsResponse,
    ResearchPromoteRequest,
    ResearchPromoteResponse,
    ResearchSearchRequest,
    ResearchSearchResponse,
)
from .meta_awareness import build_meta_awareness_snapshot, render_meta_awareness_response

logger = logging.getLogger(__name__)

router = APIRouter()

# ---------------------------------------------------------------------------
# Helpers (mirrors crt_api helpers)
# ---------------------------------------------------------------------------


def _env_bool(name: str, default: bool = True) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return str(raw).strip().lower() in {"1", "true", "yes", "y", "on"}


def _env_float(name: str, default: float) -> float:
    raw = os.getenv(name)
    if raw is None:
        return default
    try:
        return float(raw)
    except Exception:
        return default


def _journal_defaults() -> Dict[str, Any]:
    chance = max(0.0, min(1.0, _env_float("CRT_JOURNAL_SELF_REPLY_CHANCE", 0.25)))
    min_seconds = int(max(0, _env_float("CRT_JOURNAL_SELF_REPLY_MIN_SECONDS", 1800)))
    interval_seconds = int(max(60, _env_float("CRT_JOURNAL_SELF_REPLY_LOOP_SECONDS", 1800)))
    enabled = _env_bool("CRT_JOURNAL_SELF_REPLY_ENABLED", True)
    return {
        "auto_reply_enabled": enabled,
        "auto_reply_chance": chance,
        "auto_reply_min_seconds": min_seconds,
        "auto_reply_interval_seconds": interval_seconds,
    }


def _get_engine(request: Request, thread_id: str):
    return request.app.state.get_engine(thread_id)


def _get_session_db():
    from personal_agent.db_utils import get_thread_session_db
    return get_thread_session_db()


def _get_llm_client(request: Request):
    return request.app.state.get_llm_client()


def _memory_preview_item(mem: Any) -> Dict[str, Any]:
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


def _contradiction_preview_item(entry: Any) -> Dict[str, Any]:
    if hasattr(entry, "to_dict"):
        try:
            data = dict(entry.to_dict())
        except Exception:
            data = {}
    elif isinstance(entry, dict):
        data = dict(entry)
    else:
        data = {}

    def _field(name: str, default: Any = None) -> Any:
        if name in data:
            return data.get(name)
        return getattr(entry, name, default)

    return {
        "ledger_id": str(_field("ledger_id", "") or ""),
        "timestamp": float(_field("timestamp", 0.0) or 0.0),
        "status": str(_field("status", "open") or "open"),
        "contradiction_type": str(_field("contradiction_type", "conflict") or "conflict"),
        "drift_mean": float(_field("drift_mean", 0.0) or 0.0),
        "confidence_delta": float(_field("confidence_delta", 0.0) or 0.0),
        "summary": _field("summary"),
        "query": _field("query"),
        "old_memory_id": str(_field("old_memory_id", "") or ""),
        "new_memory_id": str(_field("new_memory_id", "") or ""),
    }


def _derive_self_model_mood(personality: Dict[str, Any], reflection: Dict[str, Any]) -> Dict[str, Any]:
    state = str(personality.get("state") or "balanced_companion")
    urgency = str(personality.get("urgency") or "normal")
    try:
        state_conf = float(personality.get("state_confidence") or 0.45)
    except Exception:
        state_conf = 0.45
    try:
        pref_conf = float(reflection.get("preference_confidence") or 0.0)
    except Exception:
        pref_conf = 0.0
    open_questions = reflection.get("open_questions") or []

    mood = "calm"
    reason = "steady baseline"
    if urgency == "high":
        mood = "intense"
        reason = "urgent user cadence detected"
    elif state == "technical_guide":
        mood = "curious"
        reason = "technical topic density is high"
    elif state == "reflective_partner":
        mood = "warm"
        reason = "reflection loop is emphasizing open questions"
    elif state == "structured_coach":
        mood = "curious"
        reason = "structured, question-led interactions"

    if pref_conf < 0.2:
        mood = "uncertain"
        reason = "low preference confidence in recent window"
    elif open_questions and mood == "calm":
        mood = "curious"
        reason = "open questions are still unresolved"

    intensity = max(0.2, min(0.95, 0.25 + (state_conf * 0.55)))
    return {
        "mood": mood,
        "intensity": round(float(intensity), 3),
        "reason": reason,
    }


def _compute_profile_changes(
    current: Dict[str, Any],
    previous: Optional[Dict[str, Any]],
    *,
    categorical_keys: List[str],
    numeric_keys: List[str],
) -> Dict[str, Dict[str, Any]]:
    if not previous:
        return {}

    changes: Dict[str, Dict[str, Any]] = {}
    for key in categorical_keys:
        new_v = current.get(key)
        old_v = previous.get(key)
        if new_v != old_v:
            changes[key] = {"from": old_v, "to": new_v}

    for key in numeric_keys:
        if key not in current or key not in previous:
            continue
        try:
            new_v = float(current.get(key) or 0.0)
            old_v = float(previous.get(key) or 0.0)
        except Exception:
            continue
        delta = new_v - old_v
        if abs(delta) >= 0.01:
            changes[key] = {
                "from": round(old_v, 4),
                "to": round(new_v, 4),
                "delta": round(delta, 4),
            }
    return changes


# ============================================================================
# Health
# ============================================================================


@router.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(status="ok")


# ============================================================================
# Reasoning Traces – Lazy Loading Endpoints
# ============================================================================


@router.get("/api/reasoning/traces")
def list_reasoning_traces(
    request: Request,
    thread_id: Optional[str] = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
):
    """List reasoning traces with pagination.

    Returns metadata only (no full thinking content).
    Use /api/reasoning/traces/{trace_id} to fetch full content.
    """
    engine = _get_engine(request, thread_id or "default")
    try:
        traces = engine.memory.list_reasoning_traces(
            thread_id=thread_id,
            limit=limit,
            offset=offset,
            include_content=False,
        )
        total = engine.memory.get_reasoning_trace_count(thread_id)
        return {
            "traces": traces,
            "total": total,
            "limit": limit,
            "offset": offset,
            "has_more": offset + len(traces) < total,
        }
    except Exception as e:
        logger.error(f"[REASONING] Failed to list traces: {e}")
        return {"traces": [], "total": 0, "limit": limit, "offset": offset, "has_more": False}


@router.get("/api/reasoning/traces/{trace_id}")
def get_reasoning_trace(
    request: Request,
    trace_id: str,
    thread_id: str = Query(default="default"),
):
    """Get full reasoning trace content by ID.

    This is the lazy-load endpoint – call this when user wants to see full thinking.
    """
    engine = _get_engine(request, thread_id)
    try:
        trace = engine.memory.get_reasoning_trace(trace_id)
        if trace:
            return trace
        return {"error": "Trace not found", "trace_id": trace_id}
    except Exception as e:
        logger.error(f"[REASONING] Failed to get trace {trace_id}: {e}")
        return {"error": str(e), "trace_id": trace_id}


@router.get("/api/reasoning/recent")
def get_recent_reasoning(
    request: Request,
    thread_id: str = Query(default="default"),
    limit: int = Query(default=5, ge=1, le=20),
):
    """Get most recent reasoning traces for a thread (with full content).

    Useful for showing recent thinking in UI without pagination.
    """
    engine = _get_engine(request, thread_id)
    try:
        traces = engine.memory.list_reasoning_traces(
            thread_id=thread_id,
            limit=limit,
            offset=0,
            include_content=True,
        )
        return {"traces": traces}
    except Exception as e:
        logger.error(f"[REASONING] Failed to get recent traces: {e}")
        return {"traces": []}


# ============================================================================
# Reflection API Endpoints
# ============================================================================


@router.get("/api/reflection/traces/{trace_id}")
def get_reflection_trace(
    request: Request,
    trace_id: str,
    thread_id: str = Query(default="default"),
):
    """Get full reflection trace content by ID.

    Returns confidence assessment, fact checks, and hallucination risk.
    """
    from personal_agent.reflection_system import ReflectionDB

    engine = _get_engine(request, thread_id)
    try:
        db = ReflectionDB(engine.memory.db_path)
        trace = db.get_reflection(trace_id)
        if trace:
            return trace
        return {"error": "Reflection trace not found", "trace_id": trace_id}
    except Exception as e:
        logger.error(f"[REFLECTION] Failed to get trace {trace_id}: {e}")
        return {"error": str(e), "trace_id": trace_id}


@router.get("/api/reflection/thread/{thread_id}")
def get_thread_reflections(
    request: Request,
    thread_id: str,
    limit: int = Query(default=20, ge=1, le=100),
):
    """Get all reflection traces for a thread.

    Useful for showing reflection history and confidence trends.
    """
    from personal_agent.reflection_system import ReflectionDB

    engine = _get_engine(request, thread_id)
    try:
        db = ReflectionDB(engine.memory.db_path)
        traces = db.get_thread_reflections(thread_id, limit=limit)
        return {"traces": traces, "count": len(traces)}
    except Exception as e:
        logger.error(f"[REFLECTION] Failed to get thread reflections: {e}")
        return {"traces": [], "count": 0, "error": str(e)}


# ============================================================================
# Journal Endpoints
# ============================================================================


@router.get("/api/reflection/journal/{thread_id}")
def get_reflection_journal(
    thread_id: str,
    limit: int = Query(default=50, ge=1, le=200),
):
    """Get reflection loop journal entries for a thread.

    These are lightweight, append-only summaries from the background reflection loop.
    """
    try:
        session_db = _get_session_db()
        entries = session_db.get_reflection_journal_entries(thread_id, limit=limit)
        return {"entries": entries, "count": len(entries)}
    except Exception as e:
        logger.error(f"[REFLECTION] Failed to get reflection journal: {e}")
        return {"entries": [], "count": 0, "error": str(e)}


@router.get("/api/journal/settings", response_model=JournalSettingsResponse)
def get_journal_settings(thread_id: str = Query(default="default")) -> JournalSettingsResponse:
    tid = sanitize_thread_id(thread_id)
    defaults = _journal_defaults()
    try:
        session_db = _get_session_db()
        override = session_db.get_journal_auto_reply_enabled(tid)
        enabled = override if override is not None else defaults["auto_reply_enabled"]
        return JournalSettingsResponse(
            thread_id=tid,
            auto_reply_enabled=bool(enabled),
            auto_reply_enabled_override=override,
            auto_reply_chance=defaults["auto_reply_chance"],
            auto_reply_min_seconds=defaults["auto_reply_min_seconds"],
            auto_reply_interval_seconds=defaults["auto_reply_interval_seconds"],
        )
    except Exception as e:
        logger.error(f"[JOURNAL] Failed to get settings: {e}")
        return JournalSettingsResponse(
            thread_id=tid,
            auto_reply_enabled=bool(defaults["auto_reply_enabled"]),
            auto_reply_enabled_override=None,
            auto_reply_chance=defaults["auto_reply_chance"],
            auto_reply_min_seconds=defaults["auto_reply_min_seconds"],
            auto_reply_interval_seconds=defaults["auto_reply_interval_seconds"],
        )


@router.post("/api/journal/settings", response_model=JournalSettingsResponse)
def set_journal_settings(req: JournalSettingsRequest) -> JournalSettingsResponse:
    tid = sanitize_thread_id(req.thread_id or "default")
    defaults = _journal_defaults()
    try:
        session_db = _get_session_db()
        session_db.set_journal_auto_reply_enabled(tid, bool(req.auto_reply_enabled))
        override = session_db.get_journal_auto_reply_enabled(tid)
        enabled = override if override is not None else defaults["auto_reply_enabled"]
        return JournalSettingsResponse(
            thread_id=tid,
            auto_reply_enabled=bool(enabled),
            auto_reply_enabled_override=override,
            auto_reply_chance=defaults["auto_reply_chance"],
            auto_reply_min_seconds=defaults["auto_reply_min_seconds"],
            auto_reply_interval_seconds=defaults["auto_reply_interval_seconds"],
        )
    except Exception as e:
        logger.error(f"[JOURNAL] Failed to set settings: {e}")
        return JournalSettingsResponse(
            thread_id=tid,
            auto_reply_enabled=bool(defaults["auto_reply_enabled"]),
            auto_reply_enabled_override=None,
            auto_reply_chance=defaults["auto_reply_chance"],
            auto_reply_min_seconds=defaults["auto_reply_min_seconds"],
            auto_reply_interval_seconds=defaults["auto_reply_interval_seconds"],
        )


@router.post("/api/reflection/journal/reply", response_model=JournalReplyResponse)
def create_reflection_journal_reply(req: JournalReplyRequest) -> JournalReplyResponse:
    from personal_agent.continuous_loops import maybe_reply_to_journal_entry

    tid = sanitize_thread_id(req.thread_id or "default")
    session_db = _get_session_db()
    parent = session_db.get_reflection_journal_entry(tid, req.reply_to)
    if not parent:
        raise HTTPException(status_code=404, detail="Journal entry not found")

    root_id = req.reply_to
    cursor_id = req.reply_to
    for _ in range(6):
        entry = session_db.get_reflection_journal_entry(tid, cursor_id)
        if not entry:
            break
        meta = entry.get("meta") or {}
        reply_to = meta.get("reply_to") if isinstance(meta, dict) else None
        if not reply_to:
            root_id = cursor_id
            break
        try:
            cursor_id = int(reply_to)
        except Exception:
            break

    author = (req.author or "user").strip() or "user"
    title = (req.title or "Comment").strip() or "Comment"
    body = (req.body or "").strip()
    if not body:
        raise HTTPException(status_code=400, detail="Empty comment")

    meta = {
        "reply_to": req.reply_to,
        "root_id": root_id,
        "author": author,
        "source_entry_type": parent.get("entry_type"),
    }
    entry_id = session_db.add_reflection_journal_entry(
        thread_id=tid,
        entry_type="comment",
        title=title,
        body=body,
        meta=meta,
    )
    entry = session_db.get_reflection_journal_entry(tid, entry_id) or {
        "id": entry_id,
        "thread_id": tid,
        "created_at": time.time(),
        "entry_type": "comment",
        "title": title,
        "body": body,
        "meta": meta,
    }
    auto_reply_created = False
    try:
        auto_reply_created = bool(
            maybe_reply_to_journal_entry(
                session_db=session_db,
                thread_id=tid,
                source_entry_id=entry_id,
                source_type="comment",
                source_body=body,
            )
        )
    except Exception as e:
        logger.debug(f"[JOURNAL] Auto-reply failed: {e}")

    return JournalReplyResponse(ok=True, entry=entry, auto_reply_created=auto_reply_created)


# ============================================================================
# Training Endpoints
# ============================================================================


@router.get("/api/training/stats")
def get_training_stats():
    """Get training data collection statistics.

    Shows how much data has been collected for future model training.
    """
    try:
        from personal_agent.reflection_system import TrainingDataCollector

        collector = TrainingDataCollector()
        stats = collector.get_stats()
        return stats
    except Exception as e:
        logger.error(f"[TRAINING] Failed to get stats: {e}")
        return {"error": str(e)}


@router.get("/api/training/export")
def export_training_data(format: str = Query(default="jsonl")):
    """Export collected training data.

    Formats:
    - jsonl: One JSON object per line (for fine-tuning)
    - json: Full JSON object
    """
    try:
        from personal_agent.reflection_system import TrainingDataCollector

        collector = TrainingDataCollector()
        data = collector.export_for_training(format=format)
        return {"format": format, "data": data}
    except Exception as e:
        logger.error(f"[TRAINING] Failed to export data: {e}")
        return {"error": str(e)}


# ============================================================================
# Introspection
# ============================================================================


@router.get("/api/introspection")
def get_introspection(request: Request, thread_id: str = Query("default")):
    """Get CRT's current inner state in machine + conversational formats."""
    tid = sanitize_thread_id(thread_id)
    session_db = _get_session_db()
    engine = _get_engine(request, tid)
    result: Dict[str, Any] = {
        "thread_id": tid,
        "current_thoughts": [],
        "topics_on_mind": [],
        "rising_interests": [],
        "fading_interests": [],
        "open_questions": [],
        "notes_to_self": None,
        "personality_mode": None,
        "last_reflection_at": None,
        "reply": "",
        "meta_awareness": {},
    }

    try:
        snapshot = build_meta_awareness_snapshot(
            thread_id=tid,
            session_db=session_db,
            engine=engine,
            recent_query_limit=8,
            journal_limit=8,
            contradiction_limit=8,
        )
        reply = render_meta_awareness_response(snapshot)

        topics = snapshot.get("topics_on_mind") or []
        trends = snapshot.get("topic_trends") or {}
        rising = trends.get("rising") if isinstance(trends, dict) else []
        fading = trends.get("fading") if isinstance(trends, dict) else []
        open_q = snapshot.get("open_questions") or []
        notes = snapshot.get("notes_to_self")

        thoughts: List[str] = []
        topic_names = [str(t.get("topic") or "").strip() for t in topics if isinstance(t, dict)]
        topic_names = [t for t in topic_names if t]
        if topic_names:
            thoughts.append(f"I've been thinking about: {', '.join(topic_names[:5])}")
        if isinstance(rising, list) and rising:
            thoughts.append(f"My interest in {', '.join([str(x) for x in rising[:3]])} is growing")
        if isinstance(open_q, list) and open_q:
            thoughts.append(f"I'm pondering: {str(open_q[0])}")
        if isinstance(notes, str) and notes.strip():
            thoughts.append(f"Note to self: {notes[:120]}")
        if not thoughts and reply:
            thoughts = [reply]

        result.update(
            {
                "current_thoughts": thoughts,
                "topics_on_mind": topics,
                "rising_interests": rising if isinstance(rising, list) else [],
                "fading_interests": fading if isinstance(fading, list) else [],
                "open_questions": open_q if isinstance(open_q, list) else [],
                "notes_to_self": notes if isinstance(notes, str) else None,
                "personality_mode": snapshot.get("personality_mode"),
                "last_reflection_at": snapshot.get("last_reflection_at"),
                "reply": reply,
                "meta_awareness": snapshot,
            }
        )
    except Exception as e:
        logger.debug(f"[INTROSPECTION] Error: {e}")

    return result


# ============================================================================
# Memory bridge controls (GroundCheck -> CRT)
# ============================================================================


@router.post("/api/memory/bridge/sync/{thread_id}")
def sync_groundcheck_bridge(
    request: Request,
    thread_id: str,
    min_trust: float = Query(default=0.2, ge=0.0, le=1.0),
    raw_limit: int = Query(default=400, ge=1, le=5000),
    narrative_limit: int = Query(default=30, ge=0, le=500),
):
    tid = sanitize_thread_id(thread_id)
    engine = _get_engine(request, tid)

    from personal_agent.memory_bridge import sync_groundcheck_to_memory

    allowed_sources_raw = str(os.getenv("CRT_GROUNDCHECK_BRIDGE_SOURCES", "user,inferred") or "").strip()
    allowed_sources = [s.strip() for s in allowed_sources_raw.split(",") if s.strip()] if allowed_sources_raw else None

    return sync_groundcheck_to_memory(
        memory_system=engine.memory,
        thread_id=tid,
        min_trust=min_trust,
        raw_limit=raw_limit,
        narrative_limit=narrative_limit,
        allowed_sources=allowed_sources,
    )


# ============================================================================
# Unified self-model snapshot (reflection + personality + memory/ledger surface)
# ============================================================================


@router.get("/api/self-model/{thread_id}")
def get_self_model(
    request: Request,
    thread_id: str,
    history_limit: int = Query(default=20, ge=1, le=200),
    journal_limit: int = Query(default=20, ge=1, le=200),
    memory_limit: int = Query(default=12, ge=1, le=100),
    contradiction_limit: int = Query(default=12, ge=1, le=100),
):
    tid = sanitize_thread_id(thread_id)
    session_db = _get_session_db()
    engine = _get_engine(request, tid)

    reflection = session_db.get_reflection_scorecard(tid) or {}
    personality = session_db.get_personality_profile(tid) or {}
    style_profile = session_db.get_style_profile(tid) or {}
    reflection_history = session_db.get_reflection_scorecard_history(tid, limit=history_limit)
    personality_history = session_db.get_personality_profile_history(tid, limit=history_limit)
    journal_entries = session_db.get_reflection_journal_entries(tid, limit=journal_limit)

    prev_reflection = None
    if len(reflection_history) > 1:
        prev_reflection = reflection_history[1].get("scorecard")

    prev_personality = None
    if len(personality_history) > 1:
        prev_personality = personality_history[1].get("profile")

    reflection_changes = _compute_profile_changes(
        reflection,
        prev_reflection if isinstance(prev_reflection, dict) else None,
        categorical_keys=["message_window"],
        numeric_keys=["preference_confidence"],
    )
    personality_changes = _compute_profile_changes(
        personality,
        prev_personality if isinstance(prev_personality, dict) else None,
        categorical_keys=[
            "verbosity",
            "emoji",
            "format",
            "state",
            "interaction_style",
            "tone_preference",
            "urgency",
        ],
        numeric_keys=["state_confidence", "avg_message_length", "question_ratio", "tech_ratio"],
    )

    # Add compact topic-change signal.
    try:
        cur_topics = [
            str(t.get("topic") or "")
            for t in (reflection.get("top_topics") or [])
            if isinstance(t, dict) and t.get("topic")
        ]
        prev_topics = [
            str(t.get("topic") or "")
            for t in ((prev_reflection or {}).get("top_topics") or [])
            if isinstance(t, dict) and t.get("topic")
        ]
        if cur_topics != prev_topics:
            reflection_changes["top_topics"] = {
                "from": prev_topics[:5],
                "to": cur_topics[:5],
            }
    except Exception:
        pass

    memories_total = 0
    recent_memories: List[Dict[str, Any]] = []
    try:
        memories = engine.memory._load_all_memories()
        memories.sort(key=lambda m: float(getattr(m, "timestamp", 0.0) or 0.0), reverse=True)
        memories_total = len(memories)
        recent_memories = [_memory_preview_item(m) for m in memories[:memory_limit]]
    except Exception as e:
        logger.debug(f"[SELF_MODEL] Failed to load memories for {tid}: {e}")

    open_entries: List[Any] = []
    contradiction_items: List[Dict[str, Any]] = []
    try:
        open_entries = engine.ledger.get_open_contradictions(limit=10_000)
        contradiction_items = [_contradiction_preview_item(item) for item in open_entries[:contradiction_limit]]
    except Exception as e:
        logger.debug(f"[SELF_MODEL] Failed to load contradictions for {tid}: {e}")

    journal_counts: Dict[str, int] = {}
    for entry in journal_entries:
        key = str(entry.get("entry_type") or "unknown")
        journal_counts[key] = journal_counts.get(key, 0) + 1

    mood = _derive_self_model_mood(personality, reflection)
    traits = {
        "verbosity": personality.get("verbosity"),
        "emoji": personality.get("emoji"),
        "format": personality.get("format"),
        "state": personality.get("state"),
        "state_confidence": personality.get("state_confidence"),
        "interaction_style": personality.get("interaction_style"),
        "tone_preference": personality.get("tone_preference"),
        "urgency": personality.get("urgency"),
        "humor": style_profile.get("humor"),
        "seriousness": style_profile.get("seriousness"),
        "formality": style_profile.get("formality"),
        "tone_label": style_profile.get("tone_label"),
    }

    return {
        "thread_id": tid,
        "generated_at": time.time(),
        "mood": mood,
        "traits": traits,
        "reflection": reflection,
        "personality": personality,
        "style_profile": style_profile,
        "adaptation": {
            "personality_changes": personality_changes,
            "reflection_changes": reflection_changes,
            "history_points": {
                "personality": len(personality_history),
                "reflection": len(reflection_history),
            },
        },
        "history": {
            "personality": personality_history,
            "reflection": reflection_history,
        },
        "journal": {
            "entries": journal_entries,
            "counts": journal_counts,
        },
        "memory": {
            "total": memories_total,
            "recent": recent_memories,
        },
        "contradictions": {
            "open_total": len(open_entries),
            "items": contradiction_items,
        },
    }


# ============================================================================
# Loops – Streaming & Manual Trigger
# ============================================================================


@router.get("/api/loops/stream")
def loops_stream(
    request: Request,
    thread_id: str = Query("default"),
    interval_seconds: float = Query(2.5, ge=0.5, le=60.0),
):
    """Stream background runtime updates for observability."""

    def generate():
        session_db = _get_session_db()
        last_reflection_ts = 0.0
        last_personality_ts = 0.0
        last_heartbeat = 0.0
        last_heartbeat_state_sig = ""
        last_news_sig = ""
        last_jobs_sig = ""
        last_tasks_sig = ""

        while True:
            try:
                now = time.time()
                scorecard = session_db.get_reflection_scorecard(thread_id)
                if isinstance(scorecard, dict):
                    updated_at = float(scorecard.get("updated_at") or 0)
                    if updated_at > last_reflection_ts:
                        last_reflection_ts = updated_at
                        payload = {
                            "type": "reflection_scorecard",
                            "thread_id": thread_id,
                            "scorecard": scorecard,
                        }
                        yield f"data: {json.dumps(payload)}\n\n"

                profile = session_db.get_personality_profile(thread_id)
                if isinstance(profile, dict):
                    updated_at = float(profile.get("updated_at") or 0)
                    if updated_at > last_personality_ts:
                        last_personality_ts = updated_at
                        payload = {
                            "type": "personality_profile",
                            "thread_id": thread_id,
                            "profile": profile,
                        }
                        yield f"data: {json.dumps(payload)}\n\n"

                if now - last_heartbeat >= interval_seconds:
                    last_heartbeat = now
                    yield f"data: {json.dumps({'type': 'heartbeat', 'thread_id': thread_id, 'ts': now})}\n\n"

                # Heartbeat state + latest actions
                try:
                    hb_state = session_db.get_heartbeat_state(thread_id)
                    hb_sig = json.dumps(hb_state or {}, sort_keys=True, default=str)
                    if hb_sig != last_heartbeat_state_sig:
                        last_heartbeat_state_sig = hb_sig
                        yield f"data: {json.dumps({'type': 'heartbeat_state', 'thread_id': thread_id, 'state': hb_state})}\n\n"
                except Exception as e:
                    logger.debug(f"[LOOPS] heartbeat_state stream error: {e}")

                # Heartbeat news monitor cache
                try:
                    news_rows = session_db.list_heartbeat_news_cache(thread_id, limit=8)
                    news_sig = json.dumps(news_rows or [], sort_keys=True, default=str)
                    if news_sig != last_news_sig:
                        last_news_sig = news_sig
                        payload = {
                            "type": "heartbeat_news",
                            "thread_id": thread_id,
                            "items": news_rows,
                        }
                        yield f"data: {json.dumps(payload)}\n\n"
                except Exception as e:
                    logger.debug(f"[LOOPS] heartbeat_news stream error: {e}")

                # Background jobs worker status
                try:
                    jobs_worker = getattr(request.app.state, "jobs_worker", None)
                    jobs_status = jobs_worker.status().to_dict() if jobs_worker else {"enabled": False, "running": False}
                    jobs_sig = json.dumps(jobs_status or {}, sort_keys=True, default=str)
                    if jobs_sig != last_jobs_sig:
                        last_jobs_sig = jobs_sig
                        payload = {
                            "type": "jobs_worker_status",
                            "status": jobs_status,
                        }
                        yield f"data: {json.dumps(payload)}\n\n"
                except Exception as e:
                    logger.debug(f"[LOOPS] jobs status stream error: {e}")

                # Scheduled tasks status
                try:
                    from personal_agent.scheduled_tasks import get_due_tasks, get_pending_scheduled_tasks

                    scheduled_db = str(getattr(request.app.state, "scheduled_tasks_db_path", "") or "")
                    tasks_status: Dict[str, Any] = {"pending_count": 0, "due_count": 0, "next_due_at": None}
                    if scheduled_db:
                        pending = get_pending_scheduled_tasks(scheduled_db, thread_id=thread_id)
                        due = [t for t in pending if float(t.scheduled_at) <= now]
                        next_due = min((float(t.scheduled_at) for t in pending), default=None)
                        # Global due queue can include non-thread tasks; useful for portal awareness.
                        global_due = get_due_tasks(scheduled_db)
                        tasks_status = {
                            "pending_count": len(pending),
                            "due_count": len(due),
                            "global_due_count": len(global_due),
                            "next_due_at": next_due,
                        }
                    tasks_sig = json.dumps(tasks_status, sort_keys=True, default=str)
                    if tasks_sig != last_tasks_sig:
                        last_tasks_sig = tasks_sig
                        payload = {"type": "scheduled_tasks_status", "status": tasks_status}
                        yield f"data: {json.dumps(payload)}\n\n"
                except Exception as e:
                    logger.debug(f"[LOOPS] scheduled tasks stream error: {e}")

                time.sleep(interval_seconds)
            except GeneratorExit:
                break
            except Exception as e:
                yield f"data: {json.dumps({'type': 'error', 'thread_id': thread_id, 'error': str(e)})}\n\n"
                time.sleep(interval_seconds)

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/api/telegram/live/stream")
def telegram_live_stream(
    request: Request,
    max_initial_lines: int = Query(200, ge=0, le=2000),
    poll_interval: float = Query(1.0, ge=0.2, le=10.0),
):
    """SSE tail for Telegram inbound/outbound runtime events."""
    log_path = os.getenv("TELEGRAM_LIVE_LOG_PATH", "ai_logs/telegram_live.jsonl")
    p = Path(log_path)
    if not p.is_absolute():
        p = (Path.cwd() / p).resolve()

    def _read_last_lines(path: Path, count: int) -> List[str]:
        if count <= 0 or not path.exists():
            return []
        try:
            with path.open("r", encoding="utf-8", errors="ignore") as f:
                lines = f.readlines()
            if count >= len(lines):
                return [ln.rstrip("\n") for ln in lines]
            return [ln.rstrip("\n") for ln in lines[-count:]]
        except Exception:
            return []

    def generate():
        # Initial tail
        for line in _read_last_lines(p, max_initial_lines):
            if not line.strip():
                continue
            try:
                payload = json.loads(line)
            except Exception:
                payload = {"event_type": "raw", "text": line, "ts": time.time()}
            yield f"data: {json.dumps(payload)}\n\n"

        # Follow new lines
        last_size = p.stat().st_size if p.exists() else 0
        while True:
            try:
                if p.exists():
                    size_now = p.stat().st_size
                    if size_now < last_size:
                        # rotated/truncated
                        last_size = 0
                    if size_now > last_size:
                        with p.open("r", encoding="utf-8", errors="ignore") as f:
                            f.seek(last_size)
                            chunk = f.read()
                        last_size = size_now
                        for raw in chunk.splitlines():
                            if not raw.strip():
                                continue
                            try:
                                payload = json.loads(raw)
                            except Exception:
                                payload = {"event_type": "raw", "text": raw, "ts": time.time()}
                            yield f"data: {json.dumps(payload)}\n\n"
                # heartbeat to keep proxies/clients alive
                yield f"data: {json.dumps({'event_type': 'heartbeat', 'ts': time.time()})}\n\n"
                time.sleep(poll_interval)
            except GeneratorExit:
                break
            except Exception as e:
                yield f"data: {json.dumps({'event_type': 'error', 'error': str(e), 'ts': time.time()})}\n\n"
                time.sleep(poll_interval)

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/api/loops/run", response_model=LoopRunResponse)
def loops_run(request: Request, req: LoopRunRequest) -> LoopRunResponse:
    thread_id = req.thread_id or "default"
    mode = (req.mode or "both").strip().lower()
    prompt = (req.prompt or "").strip() or None

    run_reflection = mode in ("reflection", "reflect", "both", "")
    run_personality = mode in ("personality", "person", "both", "")
    if not run_reflection and not run_personality:
        run_reflection = True
        run_personality = True

    reflection_scorecard = None
    personality_profile = None
    ran: List[str] = []

    try:
        if run_reflection and hasattr(request.app.state, "reflection_loop"):
            reflection_scorecard = request.app.state.reflection_loop.run_for_thread(thread_id, prompt=prompt)
            ran.append("reflection")
    except Exception as e:
        logger.warning(f"[LOOPS] Reflection run failed: {e}")

    try:
        if run_personality and hasattr(request.app.state, "personality_loop"):
            personality_profile = request.app.state.personality_loop.run_for_thread(thread_id, prompt=prompt)
            ran.append("personality")
    except Exception as e:
        logger.warning(f"[LOOPS] Personality run failed: {e}")

    open_contradictions = None
    try:
        engine = _get_engine(request, thread_id)
        open_contradictions = len(engine.ledger.get_open_contradictions(limit=200))
    except Exception:
        pass

    return LoopRunResponse(
        ok=True,
        thread_id=thread_id,
        ran=ran,
        reflection_scorecard=reflection_scorecard,
        personality_profile=personality_profile,
        open_contradictions=open_contradictions,
    )


# ============================================================================
# Episodic Memory API Endpoints
# ============================================================================


@router.get("/api/episodic/context")
def get_episodic_context(thread_id: str = Query(default="default")):
    """Get learned user context: preferences, patterns, concepts, recent summaries.

    Useful for:
    - Building personalized prompts
    - Showing user what the system has learned
    - Debugging preference/pattern detection
    """
    try:
        from personal_agent.episodic_memory import get_episodic_manager

        episodic_mgr = get_episodic_manager()
        context = episodic_mgr.get_user_context()
        prompt_context = episodic_mgr.build_context_prompt()

        return {
            "preferences": context.get("preferences", {}),
            "patterns": context.get("patterns", []),
            "recent_summaries": context.get("recent_summaries", []),
            "concepts": context.get("concepts", []),
            "prompt_context": prompt_context,
        }
    except Exception as e:
        logger.error(f"[EPISODIC] Error getting context: {e}")
        return {"error": str(e)}


@router.post("/api/episodic/finalize-session")
def finalize_episodic_session(request: Request, thread_id: str = Query(default="default")):
    """Finalize current session – create summary and run pattern analysis.

    Call this when:
    - User explicitly ends session
    - Application shutdown
    - Long inactivity detected
    """
    try:
        from personal_agent.episodic_memory import get_episodic_manager

        engine = _get_engine(request, thread_id)
        episodic_mgr = get_episodic_manager(memory_system=engine.memory)

        # Get recent messages from session DB
        session_db = _get_session_db()
        recent = session_db.get_recent_queries(thread_id, window=50)

        # Convert to message format
        messages: List[Dict[str, Any]] = []
        for q in reversed(recent):  # Oldest first
            messages.append(
                {
                    "role": "user",
                    "text": q.get("query_text", ""),
                    "timestamp": q.get("timestamp", time.time()),
                }
            )
            if q.get("response_text"):
                messages.append(
                    {
                        "role": "assistant",
                        "text": q.get("response_text", ""),
                        "timestamp": q.get("timestamp", time.time()),
                    }
                )

        if len(messages) < 4:
            return {"status": "skipped", "reason": "Not enough messages for summary"}

        # Get LLM client if available
        llm = _get_llm_client(request)

        summary = episodic_mgr.finalize_session(thread_id, messages, llm)

        return {
            "status": "success",
            "summary_id": summary.summary_id if summary else None,
            "summary_text": summary.summary_text if summary else None,
            "topics": summary.topics if summary else [],
            "message_count": summary.message_count if summary else 0,
        }
    except Exception as e:
        logger.error(f"[EPISODIC] Error finalizing session: {e}")
        return {"status": "error", "error": str(e)}


@router.get("/api/episodic/preferences")
def get_user_preferences(category: Optional[str] = Query(default=None)):
    """Get learned user preferences, optionally filtered by category."""
    try:
        from personal_agent.episodic_memory import get_episodic_manager

        episodic_mgr = get_episodic_manager()
        prefs = episodic_mgr.db.get_preferences(category)

        return {
            "preferences": [
                {
                    "category": p.category,
                    "key": p.key,
                    "value": p.value,
                    "confidence": p.confidence,
                    "source": p.source,
                    "evidence": p.evidence,
                }
                for p in prefs
            ]
        }
    except Exception as e:
        return {"error": str(e)}


@router.get("/api/episodic/patterns")
def get_interaction_patterns(min_confidence: float = Query(default=0.3)):
    """Get detected interaction patterns above confidence threshold."""
    try:
        from personal_agent.episodic_memory import get_episodic_manager

        episodic_mgr = get_episodic_manager()
        patterns = episodic_mgr.db.get_patterns(min_confidence=min_confidence)

        return {
            "patterns": [
                {
                    "type": p.pattern_type,
                    "description": p.description,
                    "evidence_count": p.evidence_count,
                    "confidence": p.confidence,
                    "metadata": p.metadata,
                }
                for p in patterns
            ]
        }
    except Exception as e:
        return {"error": str(e)}


@router.get("/api/episodic/concepts")
def get_concepts(concept_type: Optional[str] = Query(default=None)):
    """Get linked concepts/entities from the knowledge graph."""
    try:
        from personal_agent.episodic_memory import get_episodic_manager

        episodic_mgr = get_episodic_manager()

        if concept_type:
            concepts = episodic_mgr.db.get_concepts_by_type(concept_type)
        else:
            # Get all types
            concepts = []
            for ctype in ["person", "project", "organization", "topic"]:
                concepts.extend(episodic_mgr.db.get_concepts_by_type(ctype))

        return {
            "concepts": [
                {
                    "id": c.concept_id,
                    "name": c.canonical_name,
                    "type": c.concept_type,
                    "aliases": c.aliases,
                    "attributes": c.attributes,
                    "mention_count": c.mention_count,
                }
                for c in concepts
            ]
        }
    except Exception as e:
        return {"error": str(e)}


@router.get("/api/episodic/summaries")
def get_session_summaries(
    thread_id: Optional[str] = Query(default=None),
    limit: int = Query(default=5),
):
    """Get recent session summaries."""
    try:
        from personal_agent.episodic_memory import get_episodic_manager

        episodic_mgr = get_episodic_manager()
        summaries = episodic_mgr.db.get_recent_summaries(thread_id, limit)

        return {
            "summaries": [
                {
                    "id": s.summary_id,
                    "thread_id": s.thread_id,
                    "summary": s.summary_text,
                    "topics": s.topics,
                    "entities": s.entities_mentioned,
                    "facts_learned": s.facts_learned,
                    "message_count": s.message_count,
                    "timestamp": s.timestamp,
                }
                for s in summaries
            ]
        }
    except Exception as e:
        return {"error": str(e)}


# ============================================================================
# Research API Endpoints
# ============================================================================


@router.post("/api/research/search", response_model=ResearchSearchResponse)
def research_search(request: Request, req: ResearchSearchRequest) -> ResearchSearchResponse:
    """Execute research query and return evidence packet with citations.

    Design:
    - Searches local workspace documents (Phase 1)
    - Stores result in notes lane (quarantined, trust=0.4)
    - Returns citations with full provenance
    - Never auto-promotes to belief lane
    """
    from personal_agent.research_engine import ResearchEngine

    tid = sanitize_thread_id(req.thread_id)
    engine = _get_engine(request, tid)

    # Get workspace root for local document search
    workspace_root = str(Path.cwd())

    # Execute research query
    research_engine = ResearchEngine(workspace_root=workspace_root)
    packet = research_engine.research(
        query=req.query,
        max_sources=req.max_sources,
        search_local=True,
        search_web=False,  # M3.5
    )

    # Store in memory with provenance
    memory_id = engine.memory.store_research_result(
        query=req.query,
        evidence_packet=packet,
    )

    # Convert citations to response model
    citations = [
        CitationModel(
            quote_text=c.quote_text,
            source_url=c.source_url,
            char_offset=[c.char_offset[0], c.char_offset[1]],
            fetched_at=c.fetched_at.isoformat(),
            confidence=c.confidence,
        )
        for c in packet.citations
    ]

    return ResearchSearchResponse(
        packet_id=packet.packet_id,
        query=req.query,
        summary=packet.summary,
        citations=citations,
        memory_id=memory_id,
        citation_count=packet.citation_count(),
    )


@router.get("/api/research/citations/{memory_id}", response_model=ResearchCitationsResponse)
def get_citations(
    request: Request,
    memory_id: str,
    thread_id: str = Query(default="default"),
) -> ResearchCitationsResponse:
    """Get citations for a research memory."""
    tid = sanitize_thread_id(thread_id)
    engine = _get_engine(request, tid)

    # Get citations from memory context
    citations_data = engine.memory.get_research_citations(memory_id)

    citations = [
        CitationModel(
            quote_text=c["quote_text"],
            source_url=c["source_url"],
            char_offset=c["char_offset"],
            fetched_at=c["fetched_at"],
            confidence=c.get("confidence", 0.8),
        )
        for c in citations_data
    ]

    return ResearchCitationsResponse(
        memory_id=memory_id,
        citations=citations,
    )


@router.post("/api/research/promote", response_model=ResearchPromoteResponse)
def promote_research(request: Request, req: ResearchPromoteRequest) -> ResearchPromoteResponse:
    """Promote research note to belief lane.

    Requires explicit user confirmation (user_confirmed=True).
    Increases trust from 0.4 -> 0.8 (belief threshold).
    """
    tid = sanitize_thread_id(req.thread_id)
    engine = _get_engine(request, tid)

    if not req.user_confirmed:
        return ResearchPromoteResponse(
            ok=False,
            memory_id=req.memory_id,
            promoted=False,
        )

    # Promote to belief lane
    promoted = engine.memory.promote_to_belief(
        memory_id=req.memory_id,
        user_confirmed=True,
    )

    return ResearchPromoteResponse(
        ok=True,
        memory_id=req.memory_id,
        promoted=promoted,
    )


# ============================================================================
# Heartbeat System API (OpenClaw-style 24/7 proactive engagement)
# ============================================================================


@router.get("/api/heartbeat/status")
def get_heartbeat_status(request: Request) -> dict:
    """Get heartbeat loop status."""
    loop = request.app.state.heartbeat_loop
    return {
        "enabled": loop.enabled,
        "running": loop._thread is not None and loop._thread.is_alive(),
        "interval_seconds": loop.interval_seconds,
    }


@router.post("/api/heartbeat/start")
def start_heartbeat_loop(request: Request) -> dict:
    """Start the heartbeat loop."""
    loop = request.app.state.heartbeat_loop
    loop.start()
    return {"ok": True, "message": "Heartbeat loop started"}


@router.post("/api/heartbeat/stop")
def stop_heartbeat_loop(request: Request) -> dict:
    """Stop the heartbeat loop."""
    loop = request.app.state.heartbeat_loop
    loop.stop()
    return {"ok": True, "message": "Heartbeat loop stopped"}


@router.get("/api/threads/{thread_id}/heartbeat/config")
def get_heartbeat_config(request: Request, thread_id: str):
    """Get heartbeat config for a thread."""
    from personal_agent.heartbeat_system import HeartbeatConfig
    from personal_agent.heartbeat_api import HeartbeatConfigResponse

    tid = sanitize_thread_id(thread_id)
    session_db = _get_session_db()

    # Get config from DB
    config_dict = session_db.get_heartbeat_config(tid)
    config = HeartbeatConfig.from_dict(config_dict) if config_dict else HeartbeatConfig()

    # Get last run info
    state = session_db.get_heartbeat_state(tid)

    return HeartbeatConfigResponse(
        thread_id=tid,
        config=config.to_dict(),
        last_run=state.get("last_run") if state else None,
        last_summary=state.get("last_summary") if state else None,
    )


@router.post("/api/threads/{thread_id}/heartbeat/config")
def set_heartbeat_config(request: Request, thread_id: str, req: "HeartbeatConfigRequest"):
    """Update heartbeat config for a thread."""
    from personal_agent.heartbeat_system import HeartbeatConfig
    from personal_agent.heartbeat_api import HeartbeatConfigRequest as _HCR, HeartbeatConfigResponse

    tid = sanitize_thread_id(thread_id)
    session_db = _get_session_db()

    # Create config from request
    config = HeartbeatConfig(
        enabled=req.enabled,
        every_seconds=req.every,
        target=req.target,
        active_hours_start=req.active_hours_start,
        active_hours_end=req.active_hours_end,
        timezone=req.timezone,
        model=req.model,
        max_tokens=req.max_tokens,
        temperature=req.temperature,
        dry_run=req.dry_run,
        news_monitoring_enabled=req.news_monitoring_enabled,
        news_topics=list(req.news_topics or []),
        news_query_suffix=req.news_query_suffix,
        news_max_results=req.news_max_results,
        news_cooldown_seconds=req.news_cooldown_seconds,
        news_post_submolt=req.news_post_submolt,
        curiosity_enabled=req.curiosity_enabled,
        curiosity_threshold=req.curiosity_threshold,
        curiosity_cooldown_seconds=req.curiosity_cooldown_seconds,
        curiosity_post_enabled=req.curiosity_post_enabled,
        curiosity_post_submolt=req.curiosity_post_submolt,
    )

    # Store in DB
    try:
        session_db.set_heartbeat_config(tid, config.to_dict())
    except Exception as e:
        logger.error(f"Failed to set heartbeat config: {e}")
        raise HTTPException(status_code=500, detail=str(e))

    return HeartbeatConfigResponse(
        thread_id=tid,
        config=config.to_dict(),
    )


@router.post("/api/threads/{thread_id}/heartbeat/run-now")
def run_heartbeat_now(request: Request, thread_id: str):
    """Manually trigger a heartbeat for a thread."""
    from personal_agent.heartbeat_api import HeartbeatRunResponse

    tid = sanitize_thread_id(thread_id)
    loop = request.app.state.heartbeat_loop

    try:
        result = loop.run_for_thread(tid)
        session_db = _get_session_db()
        state = session_db.get_heartbeat_state(tid)

        return HeartbeatRunResponse(
            thread_id=tid,
            ran_successfully=bool(result),
            timestamp=state.get("last_run") if state else time.time(),
            decision_summary=state.get("last_summary", "") if state else "",
            actions=[],
            execution_time_seconds=0.0,
            error=None if result else "Failed to run heartbeat",
        )
    except Exception as e:
        logger.error(f"Failed to run heartbeat: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/api/threads/{thread_id}/heartbeat/history")
def get_heartbeat_history(request: Request, thread_id: str, limit: int = 10):
    """Get heartbeat run history for a thread."""
    from personal_agent.heartbeat_api import HeartbeatHistoryResponse, HeartbeatHistoryItem

    tid = sanitize_thread_id(thread_id)

    activities: List[HeartbeatHistoryItem] = []
    try:
        session_db = _get_session_db()
        history_data = session_db.get_heartbeat_history(tid, limit=limit)

        for item in history_data:
            activities.append(
                HeartbeatHistoryItem(
                    timestamp=item["timestamp"],
                    summary=item["summary"],
                    actions=item.get("actions", []),
                    success=item["success"],
                )
            )
    except Exception as e:
        logger.debug(f"Error getting heartbeat history: {e}")

    return HeartbeatHistoryResponse(
        activities=activities,
        total_runs=len(activities),
    )


@router.get("/api/heartbeat/heartbeat.md")
def get_heartbeat_md():
    """Get current HEARTBEAT.md content."""
    from personal_agent.heartbeat_system import HeartbeatMDParser
    from personal_agent.heartbeat_api import HeartbeatMDResponse

    workspace = Path(__file__).resolve().parent.parent

    content = HeartbeatMDParser.read_heartbeat_md(workspace)

    hb_path = workspace / "HEARTBEAT.md"
    last_modified = None
    if hb_path.exists():
        last_modified = hb_path.stat().st_mtime

    return HeartbeatMDResponse(
        content=content,
        last_modified=last_modified,
        path="HEARTBEAT.md",
    )


@router.post("/api/heartbeat/heartbeat.md")
def set_heartbeat_md(req: "HeartbeatMDRequest"):
    """Update HEARTBEAT.md."""
    from personal_agent.heartbeat_api import HeartbeatMDResponse, HeartbeatMDRequest as _HMR

    workspace = Path(__file__).resolve().parent.parent
    hb_path = workspace / "HEARTBEAT.md"

    try:
        hb_path.write_text(req.content, encoding="utf-8")
        last_modified = hb_path.stat().st_mtime

        return HeartbeatMDResponse(
            content=req.content,
            last_modified=last_modified,
            path="HEARTBEAT.md",
        )
    except Exception as e:
        logger.error(f"Failed to write HEARTBEAT.md: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# Email digest endpoints
# ============================================================================


@router.get("/api/email/status")
def get_email_status() -> dict:
    """Get email digest configuration status."""
    from personal_agent.email_digest import EmailDigestService

    service = EmailDigestService()
    return service.status()


@router.post("/api/email/send-digest", response_model=EmailDigestResponse)
def send_email_digest(req: EmailDigestRequest) -> EmailDigestResponse:
    """Build and send a digest email for a thread."""
    from personal_agent.email_digest import EmailDigestService

    session_db = _get_session_db()
    service = EmailDigestService()
    if not service.is_configured():
        raise HTTPException(status_code=400, detail="Email is not configured/enabled")

    result = service.send_thread_digest(
        thread_id=sanitize_thread_id(req.thread_id),
        to_email=req.to,
        session_db=session_db,
        subject_override=req.subject,
    )
    if not result.get("ok"):
        raise HTTPException(status_code=500, detail=str(result.get("error") or "email_send_failed"))

    return EmailDigestResponse(
        ok=True,
        to=req.to,
        subject=str(result.get("subject") or req.subject or "CRT Digest"),
        error=None,
    )

