"""Meta-awareness snapshot + conversational rendering helpers."""

from __future__ import annotations

import time
from datetime import datetime
from typing import Any, Dict, List, Optional


_META_AWARENESS_PHRASES = (
    "what are you thinking",
    "what are you thinking about",
    "what's on your mind",
    "whats on your mind",
    "what did you learn",
    "what have you learned",
    "how are you adapting",
    "reflect on",
    "self reflect",
    "self-reflect",
    "meta awareness",
    "meta-awareness",
    "introspection",
    "show your thoughts",
)


def is_meta_awareness_prompt(message: str) -> bool:
    text = " ".join(str(message or "").strip().lower().split())
    if not text:
        return False
    return any(phrase in text for phrase in _META_AWARENESS_PHRASES)


def _to_topic_items(raw_topics: Any, limit: int = 8) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    if not isinstance(raw_topics, list):
        return out
    for item in raw_topics[: max(1, int(limit or 8))]:
        if isinstance(item, dict):
            topic = str(item.get("topic") or "").strip()
            if not topic:
                continue
            try:
                weight = float(item.get("weight") or 0.0)
            except Exception:
                weight = 0.0
            out.append({"topic": topic, "weight": round(weight, 4)})
        else:
            topic = str(item).strip()
            if topic:
                out.append({"topic": topic, "weight": 0.0})
    return out


def _extract_topic_trends(reflection: Dict[str, Any]) -> Dict[str, List[str]]:
    trends = reflection.get("topic_trends")
    if not isinstance(trends, dict):
        return {"rising": [], "fading": []}

    def _norm(items: Any) -> List[str]:
        vals: List[str] = []
        if not isinstance(items, list):
            return vals
        for item in items:
            if isinstance(item, dict):
                topic = str(item.get("topic") or "").strip()
            else:
                topic = str(item or "").strip()
            if topic:
                vals.append(topic)
        return vals

    return {
        "rising": _norm(trends.get("rising"))[:5],
        "fading": _norm(trends.get("fading"))[:5],
    }


def _extract_open_questions(reflection: Dict[str, Any], limit: int = 5) -> List[str]:
    raw = reflection.get("open_questions")
    if not isinstance(raw, list):
        return []
    out: List[str] = []
    for item in raw[: max(1, int(limit or 5))]:
        if isinstance(item, dict):
            question = str(item.get("question") or "").strip()
        else:
            question = str(item or "").strip()
        if question:
            out.append(question)
    return out


def _safe_recent_journal_items(entries: Any, limit: int = 5) -> List[Dict[str, Any]]:
    if not isinstance(entries, list):
        return []
    out: List[Dict[str, Any]] = []
    for entry in entries[: max(1, int(limit or 5))]:
        if not isinstance(entry, dict):
            continue
        out.append(
            {
                "id": entry.get("id"),
                "entry_type": entry.get("entry_type"),
                "title": entry.get("title"),
                "body": entry.get("body"),
                "created_at": entry.get("created_at"),
            }
        )
    return out


def _iso_timestamp(ts: Optional[float]) -> Optional[str]:
    if ts is None:
        return None
    try:
        value = float(ts)
    except Exception:
        return None
    if value <= 0:
        return None
    try:
        return datetime.fromtimestamp(value).isoformat()
    except Exception:
        return None


def build_meta_awareness_snapshot(
    *,
    thread_id: str,
    session_db: Any,
    engine: Optional[Any] = None,
    recent_query_limit: int = 8,
    journal_limit: int = 8,
    contradiction_limit: int = 8,
) -> Dict[str, Any]:
    reflection = session_db.get_reflection_scorecard(thread_id) or {}
    if not isinstance(reflection, dict):
        reflection = {}
    personality = session_db.get_personality_profile(thread_id) or {}
    if not isinstance(personality, dict):
        personality = {}
    style_profile = session_db.get_style_profile(thread_id) or {}
    if not isinstance(style_profile, dict):
        style_profile = {}
    recent_queries = session_db.get_recent_queries(thread_id, window=max(2, int(recent_query_limit or 8))) or []
    if not isinstance(recent_queries, list):
        recent_queries = []
    journal_entries = session_db.get_reflection_journal_entries(thread_id, limit=max(2, int(journal_limit or 8))) or []
    if not isinstance(journal_entries, list):
        journal_entries = []

    topic_items = _to_topic_items(reflection.get("top_topics"), limit=8)
    topic_trends = _extract_topic_trends(reflection)
    open_questions = _extract_open_questions(reflection, limit=5)
    manual_prompt = str(reflection.get("manual_prompt") or "").strip() or None

    channel_ctx = session_db.get_channel_context(thread_id) or {}
    if not isinstance(channel_ctx, dict):
        channel_ctx = {}
    pending_reminder = session_db.get_pending_reminder(thread_id)
    if pending_reminder and not isinstance(pending_reminder, dict):
        pending_reminder = None

    contradictions: List[Dict[str, Any]] = []
    open_total = 0
    if engine is not None:
        try:
            items = engine.ledger.get_open_contradictions(limit=max(1, int(contradiction_limit or 8)))
            open_total = len(items or [])
            for item in items or []:
                contradictions.append(
                    {
                        "ledger_id": getattr(item, "ledger_id", None),
                        "status": str(getattr(item, "status", "") or ""),
                        "type": str(getattr(item, "contradiction_type", "") or ""),
                        "summary": str(getattr(item, "summary", "") or ""),
                    }
                )
        except Exception:
            contradictions = []
            open_total = 0

    learned_slots: List[str] = []
    for row in recent_queries:
        if not isinstance(row, dict):
            continue
        slot = str(row.get("detected_slot") or "").strip()
        if slot and slot not in learned_slots:
            learned_slots.append(slot)

    now = time.time()
    snapshot: Dict[str, Any] = {
        "thread_id": thread_id,
        "generated_at": now,
        "generated_at_iso": _iso_timestamp(now),
        "last_reflection_at": reflection.get("updated_at"),
        "last_reflection_at_iso": _iso_timestamp(reflection.get("updated_at")),
        "topics_on_mind": topic_items,
        "topic_trends": topic_trends,
        "open_questions": open_questions,
        "notes_to_self": manual_prompt,
        "personality_mode": {
            "verbosity": personality.get("verbosity", "balanced"),
            "emoji": personality.get("emoji", "moderate"),
            "format": personality.get("format", "mixed"),
            "state": personality.get("state", "balanced_companion"),
            "state_confidence": personality.get("state_confidence"),
            "state_reason": personality.get("state_reason"),
            "state_transitioned": personality.get("state_transitioned", False),
        },
        "style_profile": style_profile,
        "recent_queries": recent_queries[: max(1, int(recent_query_limit or 8))],
        "recent_journal_entries": _safe_recent_journal_items(journal_entries, limit=5),
        "learned_slots_recent": learned_slots,
        "channel_context": {
            "channel": channel_ctx.get("channel"),
            "actor_id": channel_ctx.get("actor_id"),
            "destination_id": channel_ctx.get("destination_id"),
            "updated_at": channel_ctx.get("updated_at"),
            "updated_at_iso": _iso_timestamp(channel_ctx.get("updated_at")),
        },
        "pending_reminder": pending_reminder,
        "contradictions": {
            "open_total": open_total,
            "items": contradictions,
        },
    }
    return snapshot


def render_meta_awareness_response(snapshot: Dict[str, Any]) -> str:
    topics = snapshot.get("topics_on_mind") or []
    open_questions = snapshot.get("open_questions") or []
    trends = snapshot.get("topic_trends") or {}
    personality = snapshot.get("personality_mode") or {}
    journal_entries = snapshot.get("recent_journal_entries") or []
    pending_reminder = snapshot.get("pending_reminder")
    contradictions = snapshot.get("contradictions") or {}
    learned_slots = snapshot.get("learned_slots_recent") or []

    lines: List[str] = []

    topic_names = [str(t.get("topic") or "").strip() for t in topics if isinstance(t, dict)]
    topic_names = [t for t in topic_names if t]
    if topic_names:
        lines.append(f"I am currently tracking {', '.join(topic_names[:4])} as the strongest themes.")
    else:
        lines.append("I do not have strong topic momentum yet, so I am still building context.")

    rising = trends.get("rising") if isinstance(trends, dict) else []
    if isinstance(rising, list) and rising:
        lines.append(f"My attention is rising on {', '.join([str(x) for x in rising[:3]])}.")

    if open_questions:
        lines.append(f"The main open question in my reflection loop is: {str(open_questions[0])}")

    state = str(personality.get("state") or "balanced_companion")
    state_reason = str(personality.get("state_reason") or "").strip()
    if state_reason:
        lines.append(f"Response mode is {state} because {state_reason}.")
    else:
        lines.append(f"Response mode is currently {state}.")

    if learned_slots:
        lines.append(f"Recent fact-learning activity touched: {', '.join([str(s) for s in learned_slots[:5]])}.")

    if journal_entries:
        latest = journal_entries[0]
        title = str(latest.get("title") or "").strip()
        body = str(latest.get("body") or "").strip()
        if title:
            lines.append(f"Latest journal note: {title}.")
        if body:
            snippet = body[:140].strip()
            if len(body) > 140:
                snippet = snippet.rstrip() + "..."
            lines.append(f"Self-review note: {snippet}")

    open_total = int(contradictions.get("open_total") or 0)
    if open_total > 0:
        lines.append(f"I still have {open_total} open contradiction items under review.")

    if isinstance(pending_reminder, dict):
        reminder_text = str(pending_reminder.get("reminder_text") or "").strip()
        reminder_at = _iso_timestamp(pending_reminder.get("scheduled_at"))
        if reminder_text:
            if reminder_at:
                lines.append(f"I also have a pending reminder candidate: '{reminder_text}' for {reminder_at}.")
            else:
                lines.append(f"I also have a pending reminder candidate: '{reminder_text}'.")

    return " ".join([line for line in lines if line]).strip()

