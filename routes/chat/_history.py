"""History / continuity helpers extracted from routes.chat.

Provides follow-up detection, pending-followup resolution,
personal-history question handling, and GPT-reference retrieval.
"""

from __future__ import annotations

import logging
import re
import time
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from ._constants import _CONTINUITY_FOLLOWUP_HINTS, _PENDING_FOLLOWUP_SHORTCUTS

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_PERSONAL_HISTORY_PATTERNS = (
    re.compile(r"\b(?:health|medical)\s+history\b", re.IGNORECASE),
    re.compile(r"\bwhat\s+do\s+you\s+know\s+about\s+my\b", re.IGNORECASE),
    re.compile(r"\b(?:my|the)\s+past\b", re.IGNORECASE),
    re.compile(r"\bnight\s+in\s+the\s+icu\b", re.IGNORECASE),
    re.compile(r"\bthree\s+promises\b", re.IGNORECASE),
    re.compile(r"\blife\s+matters\s+more\s+to\s+me\s+now\b", re.IGNORECASE),
)

_WEAK_HISTORY_ANSWER_MARKERS = (
    "i have fragments",
    "not the full picture",
    "i'm not seeing specifics",
    "details didn't make it through",
    "i don't have specific details",
    "you'd need to tell me again",
    "i don't have that one in front of me",
    "i know there is",
    "i know it exists",
    "i can't tell you what it is",
    "from what i remember",
    "you've mentioned",
    "health history is important to you",
    "if you'd like to share more",
    "i can help you keep track of it",
    "if there are specific areas you want to discuss",
)

# ---------------------------------------------------------------------------
# History loading
# ---------------------------------------------------------------------------


def _load_recent_history_messages(
    session_db,
    thread_id: str,
    *,
    window: int = 6,
) -> List[Dict[str, str]]:
    """Load recent user/assistant messages from session DB."""
    history_messages: List[Dict[str, str]] = []
    try:
        recent = session_db.get_recent_queries(thread_id, window=window)
        for item in reversed(recent):
            q = str((item or {}).get("query_text") or "").strip()
            r = str((item or {}).get("response_text") or "").strip()
            if q:
                history_messages.append({"role": "user", "content": q})
            if r:
                history_messages.append({"role": "assistant", "content": r})
    except Exception as e:
        logger.debug(f"[CONTINUITY] Failed to load history for {thread_id}: {e}")
    return history_messages


# ---------------------------------------------------------------------------
# Follow-up detection & continuity augmentation
# ---------------------------------------------------------------------------


def _looks_like_follow_up(message: str) -> bool:
    """Heuristic for short referential prompts that need carry-forward context."""
    text = str(message or "").strip().lower()
    if not text:
        return False
    # Avoid attaching history to explicit new-profile assertions.
    if re.search(r"\b(i am|i'm|my name|call me|i work|i live|my favorite|i prefer)\b", text):
        return False
    words = re.findall(r"\w+", text)
    if len(words) <= 8:
        # Only carry context for short prompts with explicit follow-up phrasing.
        # This avoids polluting independent requests (e.g., greetings, jokes, time).
        return any(hint in text for hint in _CONTINUITY_FOLLOWUP_HINTS)
    return any(hint in text for hint in _CONTINUITY_FOLLOWUP_HINTS)


def _augment_query_with_continuity(
    *,
    message: str,
    history_messages: List[Dict[str, str]],
    max_history_lines: int = 10,
    max_chars: int = 2200,
) -> str:
    """
    Add compact prior-turn context for follow-up prompts.

    This keeps /send aligned with /stream behavior without changing engine internals.
    """
    if not history_messages:
        return message
    if not _looks_like_follow_up(message):
        return message

    # Keep the newest lines first when fitting into budget so follow-up cues remain relevant.
    instruction = (
        "[CONTINUITY INSTRUCTION] Treat this as a follow-up to the recent conversation. "
        "Resolve references like 'it', 'that', or 'the highlights' using context below."
    )
    context_header = "[RECENT CONVERSATION CONTEXT]"
    fixed_cost = len(instruction) + len(context_header) + 8
    budget = max(240, max_chars - fixed_cost)

    lines_rev: List[str] = []
    used = 0
    for item in reversed(history_messages):
        role = str(item.get("role") or "user").strip().lower()
        content = re.sub(r"\s+", " ", str(item.get("content") or "")).strip()
        if not content:
            continue
        role_label = "User" if role == "user" else "Assistant"
        per_line_cap = 260 if role == "user" else 420
        if len(content) > per_line_cap:
            content = content[: per_line_cap - 3].rstrip() + "..."
        line = f"{role_label}: {content}"
        line_len = len(line) + 1

        if used + line_len > budget and lines_rev:
            continue
        if used + line_len > budget:
            keep = max(32, budget - used - len(role_label) - 6)
            line = f"{role_label}: {content[:keep].rstrip()}..."
            line_len = len(line) + 1

        lines_rev.append(line)
        used += line_len
        if len(lines_rev) >= max_history_lines:
            break

    if not lines_rev:
        return message

    lines = list(reversed(lines_rev))
    context_block = f"{instruction}\n{context_header}\n" + "\n".join(lines)
    return f"{message}\n\n{context_block}"


# ---------------------------------------------------------------------------
# Pending follow-up shortcuts
# ---------------------------------------------------------------------------


def _normalize_followup_shortcut(message: str) -> str:
    return re.sub(r"\s+", " ", str(message or "").strip().lower())


def _looks_like_pending_followup_shortcut(message: str) -> bool:
    return _normalize_followup_shortcut(message) in _PENDING_FOLLOWUP_SHORTCUTS


def _extract_recent_followup_anchor(history_messages: List[Dict[str, str]]) -> Optional[Dict[str, str]]:
    last_assistant = ""
    for item in reversed(history_messages or []):
        role = str((item or {}).get("role") or "").strip().lower()
        content = str((item or {}).get("content") or "").strip()
        if not content:
            continue
        if role == "assistant" and not last_assistant:
            last_assistant = content
            continue
        if role != "user":
            continue
        user_text = content
        if user_text.startswith("[followup]"):
            user_text = user_text[len("[followup]"):].strip()
        user_lower = user_text.lower()
        if not user_text:
            continue
        if "?" in user_text or user_lower.startswith(
            ("what ", "how ", "why ", "which ", "can you ", "do you ", "tell me ")
        ):
            return {
                "question": user_text,
                "last_assistant": last_assistant,
                "source": "recent_history",
            }
    return None


def _resolve_pending_followup_context(
    *,
    message: str,
    session_db: Any,
    thread_id: str,
    history_messages: List[Dict[str, str]],
) -> Optional[Dict[str, str]]:
    if not _looks_like_pending_followup_shortcut(message):
        return None

    try:
        active = session_db.get_active_governed_task(thread_id) if session_db is not None else None
    except Exception:
        active = None

    if isinstance(active, dict):
        question = str(active.get("question") or "").strip()
        if question:
            return {
                "question": question,
                "objective": str(active.get("objective") or "").strip(),
                "last_answer": str(active.get("orch_answer_so_far") or "").strip(),
                "source": "governed_question",
            }
        pending_followups = [str(item or "").strip() for item in (active.get("pending_followups") or []) if str(item or "").strip()]
        if pending_followups:
            return {
                "question": pending_followups[0],
                "objective": str(active.get("objective") or "").strip(),
                "last_answer": str(active.get("orch_answer_so_far") or "").strip(),
                "source": "governed_followup",
            }

    recent_anchor = _extract_recent_followup_anchor(history_messages)
    if recent_anchor:
        return {
            "question": str(recent_anchor.get("question") or "").strip(),
            "objective": "",
            "last_answer": str(recent_anchor.get("last_assistant") or "").strip(),
            "source": str(recent_anchor.get("source") or "recent_history"),
        }
    return None


def _augment_query_with_pending_followup(
    *,
    message: str,
    pending_context: Optional[Dict[str, str]],
) -> str:
    if not pending_context:
        return message
    question = str(pending_context.get("question") or "").strip()
    if not question:
        return message

    parts = [
        str(message or "").strip(),
        "",
        "[CONTINUITY INSTRUCTION] Treat this as a direct continuation of the pending question below.",
        "[PENDING FOLLOW-UP QUESTION]",
        question,
    ]
    objective = str(pending_context.get("objective") or "").strip()
    if objective:
        parts.extend(["[TASK OBJECTIVE]", objective])
    last_answer = str(pending_context.get("last_answer") or "").strip()
    if last_answer:
        if len(last_answer) > 500:
            last_answer = last_answer[:500].rstrip() + "..."
        parts.extend(["[MOST RECENT ANSWER]", last_answer])
    return "\n".join(part for part in parts if part != "")


# ---------------------------------------------------------------------------
# Personal-history question handling
# ---------------------------------------------------------------------------


def _is_personal_history_question(text: str) -> bool:
    raw = str(text or "").strip()
    if not raw:
        return False
    if any(p.search(raw) for p in _PERSONAL_HISTORY_PATTERNS):
        return True
    raw_lower = raw.lower()
    return "history" in raw_lower and any(term in raw_lower for term in ("my", "health", "medical", "past"))


def _infer_personal_history_topic(history_messages: List[Dict[str, str]]) -> Optional[str]:
    for item in reversed(history_messages or []):
        content = str((item or {}).get("content") or "").strip()
        if not content:
            continue
        if _is_personal_history_question(content):
            return _history_topic_key(content)
        content_lower = content.lower()
        if any(
            term in content_lower
            for term in (
                "medical history",
                "health history",
                "night in the icu",
                "three promises",
                "life matters more",
                "leukemia",
                "cancer",
                "transplant",
                "gvhd",
                "diagnosis",
                "prognosis",
                "hospital",
                "icu",
            )
        ):
            return "health_history"
        if any(term in content_lower for term in ("personal history", "my past", "the past")):
            return "personal_history"
    return None


def _resolve_personal_history_reference(
    text: str,
    history_messages: List[Dict[str, str]],
) -> Tuple[Optional[str], Optional[str], bool]:
    raw = str(text or "").strip()
    if not raw:
        return None, None, False
    if _is_personal_history_question(raw):
        return raw, _history_topic_key(raw), False
    if not _looks_like_follow_up(raw):
        return None, None, False
    inferred_topic = _infer_personal_history_topic(history_messages)
    if not inferred_topic:
        return None, None, False
    if inferred_topic == "health_history":
        return "medical history", inferred_topic, True
    return "personal history", inferred_topic, True


def _history_topic_key(text: str) -> str:
    raw_lower = str(text or "").lower()
    if any(term in raw_lower for term in ("health", "medical", "icu", "hospital", "three promises", "life matters more")):
        return "health_history"
    return "personal_history"


def _history_search_queries(text: str) -> List[str]:
    raw = str(text or "").strip()
    queries: List[str] = [raw]
    raw_lower = raw.lower()
    if any(term in raw_lower for term in ("health", "medical", "icu", "hospital", "three promises", "life matters more")):
        queries.extend([
            "medical history",
            "health history",
            "night in the ICU",
            "three promises",
            "why life matters more to me now",
        ])
    deduped: List[str] = []
    seen = set()
    for item in queries:
        cleaned = str(item or "").strip()
        if not cleaned:
            continue
        key = cleaned.lower()
        if key in seen:
            continue
        seen.add(key)
        deduped.append(cleaned)
    return deduped


# ---------------------------------------------------------------------------
# GPT reference retrieval
# ---------------------------------------------------------------------------


def _build_gpt_reference_summary(excerpts: List[Dict[str, Any]]) -> str:
    lines = ["Temporary GPT archive references for this thread:"]
    for item in excerpts[:4]:
        role = str(item.get("role") or "?")
        date = str(item.get("date") or "?")
        title = str(item.get("conv_title") or "Untitled")
        snippet = str(item.get("text") or "").strip().replace("\n", " ")
        if len(snippet) > 260:
            snippet = snippet[:260].rstrip() + "..."
        lines.append(f"- [{role}] {date} | {title}: {snippet}")
    return "\n".join(lines)


def _get_or_build_gpt_reference_packet(
    thread_id: str,
    query_text: str,
    *,
    ttl_seconds: int = 86400,
) -> Tuple[Optional[Dict[str, Any]], bool]:
    topic_key = _history_topic_key(query_text)
    try:
        from personal_agent.gpt_reference_cache import get_packet, put_packet
        cached = get_packet(thread_id, topic_key)
        if cached:
            return cached, True
    except Exception:
        put_packet = None

    try:
        from personal_agent.gpt_log_store import get_gpt_log_store
        store = get_gpt_log_store()
    except Exception as exc:
        logger.debug("[GPT_REF] store unavailable: %s", exc)
        return None, False

    merged: Dict[str, Dict[str, Any]] = {}
    for search_query in _history_search_queries(query_text):
        try:
            for result in store.search(search_query, top_k=6):
                existing = merged.get(result.msg_id)
                if existing and float(existing.get("score") or 0.0) >= float(result.score or 0.0):
                    continue
                _dt = datetime.fromtimestamp(result.timestamp) if result.timestamp else None
                merged[result.msg_id] = {
                    "msg_id": result.msg_id,
                    "conv_id": result.conv_id,
                    "conv_title": result.conv_title,
                    "role": result.role,
                    "text": result.text,
                    "timestamp": float(result.timestamp or 0.0),
                    "date": _dt.strftime("%Y-%m-%d") if _dt else "?",
                    "score": round(float(result.score or 0.0), 4),
                }
        except Exception as exc:
            logger.debug("[GPT_REF] search failed for %r: %s", search_query, exc)

    if not merged:
        return None, False

    excerpts = sorted(
        merged.values(),
        key=lambda item: (float(item.get("score") or 0.0), float(item.get("timestamp") or 0.0)),
        reverse=True,
    )[:5]
    packet = {
        "thread_id": thread_id,
        "topic_key": topic_key,
        "query_text": query_text,
        "created_at": time.time(),
        "summary": _build_gpt_reference_summary(excerpts),
        "excerpts": excerpts,
    }
    try:
        if put_packet is not None:
            put_packet(
                thread_id=thread_id,
                topic_key=topic_key,
                query_text=query_text,
                summary=packet["summary"],
                excerpts=excerpts,
                ttl_seconds=ttl_seconds,
            )
    except Exception as exc:
        logger.debug("[GPT_REF] cache write failed: %s", exc)
    return packet, False


def _build_gpt_reference_context_block(packet: Dict[str, Any]) -> str:
    excerpts = packet.get("excerpts") or []
    lines = [
        "[Temporary GPT archive context - reference only, not settled memory]",
        str(packet.get("summary") or "").strip(),
    ]
    for item in excerpts[:3]:
        snippet = str(item.get("text") or "").strip().replace("\n", " ")
        if len(snippet) > 320:
            snippet = snippet[:320].rstrip() + "..."
        lines.append(f"- [{item.get('role')}] {item.get('date')} | {item.get('conv_title')}: {snippet}")
    return "\n".join(part for part in lines if part)


def _history_answer_is_weak(result: Dict[str, Any]) -> bool:
    answer = str(result.get("answer") or "").strip().lower()
    if not answer:
        return True
    if any(marker in answer for marker in _WEAK_HISTORY_ANSWER_MARKERS):
        return True
    if len(result.get("retrieved_memories") or []) == 0 and len(result.get("prompt_memories") or []) == 0:
        return True
    return False


def _build_gpt_reference_answer(packet: Dict[str, Any], *, from_cache: bool) -> str:
    excerpts = packet.get("excerpts") or []
    opener = (
        "I checked the temporary GPT-history references already loaded for this thread."
        if from_cache
        else "I checked your GPT archive for relevant past context."
    )
    lines = [opener, ""]
    if excerpts:
        lines.append("The clearest references I found:")
        for item in excerpts[:3]:
            snippet = str(item.get("text") or "").strip().replace("\n", " ")
            if len(snippet) > 240:
                snippet = snippet[:240].rstrip() + "..."
            lines.append(f"- [{item.get('role')}] {item.get('date')} | {item.get('conv_title')}: {snippet}")
        lines.append("")
    lines.append("I'm treating this as temporary reference context, not settled memory, unless you want me to promote specific details.")
    return "\n".join(lines)
