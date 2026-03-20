"""Chat route module – extracted from crt_api.py.

Contains:
  POST /api/chat/send   – synchronous chat
  POST /api/chat/stream  – SSE streaming chat
  POST /api/chat/intent  – intent-routed chat
"""

from __future__ import annotations

import json
import logging
import os
import re
import sqlite3
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse

from .deps import sanitize_thread_id
from personal_agent.text_utils import (
    strip_thinking_tags as _strip_thinking_tags,
    strip_think_blocks,
    extract_think_content,
)
from .models import (
    ChatSendRequest,
    ChatSendResponse,
    IntentQueryRequest,
    IntentQueryResponse,
)

from personal_agent.runtime_config import get_runtime_config
from personal_agent.db_utils import get_thread_session_db
from personal_agent.greeting_system import get_time_based_greeting
from personal_agent.active_learning import get_active_learning_coordinator
from personal_agent.episodic_memory import get_episodic_manager
from personal_agent.openclaw_bridge import run_openclaw_agent, should_delegate_to_openclaw
from .meta_awareness import (
    build_meta_awareness_snapshot,
    is_meta_awareness_prompt,
    render_meta_awareness_response,
)
from personal_agent.reflection_system import run_reflection_pass, ReflectionResult
from personal_agent.scheduled_tasks import schedule_reminder, extract_reminder_from_message
from personal_agent.fact_slots import extract_fact_slots

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/chat", tags=["chat"])

# ---------------------------------------------------------------------------
# Module-level constants (mirrors crt_api module-level vars)
# ---------------------------------------------------------------------------

try:
    _TASKING_INTERVAL_SECONDS = float(os.getenv("CRT_TASKING_INTERVAL_SECONDS", "0") or 0)
except Exception:
    _TASKING_INTERVAL_SECONDS = 0.0

_TASKING_LAST_RUN: Dict[str, float] = {}
_TASKING_LOCK = threading.Lock()

_EXPAND_TRIGGERS = (
    "expand",
    "expand more",
    "explain more",
    "tell me more",
    "go deeper",
    "more detail",
    "more details",
    "elaborate",
    "continue",
)

_CONTINUITY_FOLLOWUP_HINTS = (
    "tell me more",
    "continue",
    "and then",
    "what about",
    "how about",
    "what else",
    "how do you know",
    "how are you sure",
    "how did you know",
    "the highlights",
    "highlights",
    "summarize",
    "summary",
    "give me details",
    "details about that",
    "more about that",
    "elaborate",
    "expand on",
    "about that",
    "about this",
    "about it",
    "go on",
    "keep going",
    "go deeper",
    "explain that",
    "explain it",
    "why is that",
    "interesting fact",
)

_GROUNDCHECK_BRIDGE_LOCK = threading.Lock()
_GROUNDCHECK_BRIDGE_LAST_SYNC: Dict[str, float] = {}
_CONTRADICTION_CAVEAT_RE = re.compile(
    r"("
    r"\b(most recent|latest|conflicting|however|according to)\b|"
    r"\b(updat(e|ed|ing)|correct(ed|ing|ion)?|clarif(y|ied|ying))\b|"
    r"\b(earlier|previously|before|prior|former)\b|"
    r"\b(chang(e|ed|ing)|revis(e|ed|ing)|adjust(ed|ing)?|modif(y|ied|ying))\b|"
    r"\(changed from|\(most recent|\(updated|"
    r"\b(versus|vs|compared to)\b|"
    r"\bno longer\b|"
    r"\bas of\b"
    r")",
    flags=re.IGNORECASE,
)


@dataclass
class ResponseControlState:
    request_text: str
    effective_text: str = ""
    request_kind: str = "unknown"
    final_action: str = "pending"
    stages: List[Dict[str, Any]] = field(default_factory=list)

    def mark(self, stage: str, status: str, detail: Optional[str] = None, **extra: Any) -> None:
        item: Dict[str, Any] = {"stage": stage, "status": status}
        if detail:
            item["detail"] = detail
        for key, value in extra.items():
            if value is not None:
                item[key] = value
        self.stages.append(item)


def _control_status_lines(state: ResponseControlState) -> List[str]:
    out: List[str] = []
    for item in state.stages:
        stage = str(item.get("stage") or "")
        status = str(item.get("status") or "")
        detail = str(item.get("detail") or "").strip()
        line = f"ctrl:{stage}:{status}"
        if detail:
            line += f":{detail}"
        out.append(line)
    return out


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


def _env_bool(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return str(raw).strip().lower() in {"1", "true", "yes", "y", "on"}


def _answer_has_contradiction_caveat(answer: str) -> bool:
    text = str(answer or "").strip()
    if not text:
        return False
    return bool(_CONTRADICTION_CAVEAT_RE.search(text))


def _maybe_sync_groundcheck_bridge(
    *,
    thread_id: str,
    engine: Any,
) -> Dict[str, Any]:
    """Best-effort GroundCheck -> CRT sync for retrieval parity across channels."""
    enabled = _env_bool("CRT_GROUNDCHECK_BRIDGE_ENABLED", True)
    if not enabled:
        return {"enabled": False, "attempted": False, "reason": "disabled"}

    tid = sanitize_thread_id(thread_id)
    try:
        interval = float(os.getenv("CRT_GROUNDCHECK_BRIDGE_INTERVAL_SECONDS", "120") or 120.0)
    except Exception:
        interval = 120.0
    interval = max(5.0, interval)

    now = time.time()
    with _GROUNDCHECK_BRIDGE_LOCK:
        last = float(_GROUNDCHECK_BRIDGE_LAST_SYNC.get(tid, 0.0) or 0.0)
        if now - last < interval:
            return {
                "enabled": True,
                "attempted": False,
                "reason": "interval",
                "next_sync_in_seconds": round(interval - (now - last), 3),
            }
        _GROUNDCHECK_BRIDGE_LAST_SYNC[tid] = now

    try:
        from personal_agent.memory_bridge import sync_groundcheck_to_memory

        try:
            min_trust = float(os.getenv("CRT_GROUNDCHECK_BRIDGE_MIN_TRUST", "0.2") or 0.2)
        except Exception:
            min_trust = 0.2
        try:
            raw_limit = int(os.getenv("CRT_GROUNDCHECK_BRIDGE_RAW_LIMIT", "400") or 400)
        except Exception:
            raw_limit = 400
        try:
            narrative_limit = int(os.getenv("CRT_GROUNDCHECK_BRIDGE_NARRATIVE_LIMIT", "120") or 120)
        except Exception:
            narrative_limit = 120

        allowed_sources_raw = str(os.getenv("CRT_GROUNDCHECK_BRIDGE_SOURCES", "user,inferred") or "").strip()
        allowed_sources = [s.strip() for s in allowed_sources_raw.split(",") if s.strip()] if allowed_sources_raw else None

        result = sync_groundcheck_to_memory(
            memory_system=engine.memory,
            thread_id=tid,
            min_trust=min_trust,
            raw_limit=max(1, raw_limit),
            narrative_limit=max(0, narrative_limit),
            allowed_sources=allowed_sources,
        )
        result["enabled"] = True
        result["attempted"] = True
        return result
    except Exception as e:
        logger.debug(f"[MEMORY_BRIDGE] Sync failed for {tid}: {e}")
        return {"enabled": True, "attempted": True, "ok": False, "error": str(e)}


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


def _is_bare_web_search_command(text: str) -> bool:
    """True for generic search commands without a concrete topic/query."""
    t = re.sub(r"\s+", " ", str(text or "").strip().lower())
    if not t:
        return False

    command_markers = (
        "use duckduckgo",
        "use duck duck go",
        "duckduckgo and web search",
        "duck duck go and web search",
        "use web search",
        "web search",
        "search the web",
        "search online",
    )
    if not any(m in t for m in command_markers):
        return False

    # If the user already specified a topical query, this is not a bare command.
    # Examples to keep as non-bare:
    # - "search the web for dji mic 2 lav input"
    # - "can you check X using duckduckgo"
    if any(m in t for m in ("search for ", "for ", "about ", "on ", "regarding ", "using duckduckgo")):
        # still bare if the whole message is essentially just a command phrase
        trimmed = t
        for m in command_markers:
            trimmed = trimmed.replace(m, " ")
        trimmed = re.sub(r"[^a-z0-9\s]", " ", trimmed)
        words = [w for w in trimmed.split() if w and w not in {"use", "and", "please", "can", "you"}]
        return len(words) <= 2

    return True


def _resolve_bare_web_search_command(
    *,
    message: str,
    session_db: Any,
    thread_id: str,
) -> str:
    """Map bare 'use web search' commands to the last substantive user question."""
    q = str(message or "").strip()
    if not q or not _is_bare_web_search_command(q):
        return q
    if session_db is None:
        return q

    try:
        recent = session_db.get_recent_queries(thread_id, window=12)
    except Exception:
        recent = []

    # get_recent_queries() already returns newest-first; pick the latest
    # substantive user query that is not another bare search command.
    for row in recent:
        prev_q = str((row or {}).get("query_text") or "").strip()
        if not prev_q:
            continue
        if prev_q.lower() == q.lower():
            continue
        if _is_bare_web_search_command(prev_q):
            continue
        prev_l = prev_q.lower()
        if re.match(r"^(search (the web|online|duckduckgo|ddg) for|web search for)\b", prev_l):
            return prev_q
        return f"search the web for {prev_q}"

    return q


def _is_meta_provenance_followup(message: str) -> bool:
    text = str(message or "").strip().lower()
    if not text:
        return False
    return any(
        phrase in text
        for phrase in (
            "how do you know",
            "how are you sure",
            "how did you know",
            "how do you remember",
            "how did you learn",
            "where did you learn",
            "where did you learn that",
            "how does your memory",
            "how does that work",
            "explain your process",
            "why are you sure",
        )
    )


def _answer_recent_slot_provenance(*, engine: Any, session_db: Any, thread_id: str) -> Optional[str]:
    if session_db is None:
        return None
    try:
        recent = session_db.get_recent_queries(thread_id, window=6)
    except Exception:
        recent = []
    if not recent:
        return None

    target_slot = None
    for row in recent:
        slot = str((row or {}).get("detected_slot") or "").strip()
        if slot:
            target_slot = slot
            break
    if not target_slot:
        return None

    try:
        memories = engine.memory._load_all_memories()
    except Exception:
        return None

    candidates: List[Tuple[Any, Any]] = []
    for mem in memories:
        if getattr(mem, "source", None) is None:
            continue
        if bool(getattr(mem, "deprecated", False)):
            continue
        try:
            facts = extract_fact_slots(str(getattr(mem, "text", "") or ""))
        except Exception:
            continue
        if target_slot in facts:
            candidates.append((mem, facts[target_slot]))

    if not candidates:
        return None

    best_mem, best_fact = max(
        candidates,
        key=lambda item: (
            float(getattr(item[0], "timestamp", 0.0) or 0.0),
            float(getattr(item[0], "trust", 0.0) or 0.0),
        ),
    )
    slot_label = target_slot.replace("_", " ")
    fact_value = str(getattr(best_fact, "value", "") or "").strip()
    fact_text = str(getattr(best_mem, "text", "") or "").strip()
    trust = float(getattr(best_mem, "trust", 0.0) or 0.0)

    if not fact_value or not fact_text:
        return None
    return (
        f"I know that because you told me your {slot_label} is {fact_value}. "
        f"I have that stored from: \"{fact_text}\" (trust: {trust:.2f})."
    )


def _generic_meta_provenance_answer() -> str:
    return (
        "I remember this by storing your confirmed facts in memory and retrieving them when they're relevant. "
        "Facts about you come from what you've told me, while my assistant identity comes from my configured system role. "
        "If those records conflict, I disclose the conflict instead of silently picking a winner."
    )


# ---------------------------------------------------------------------------
# Copied helper functions (originally module-level in crt_api.py)
# ---------------------------------------------------------------------------


# _strip_thinking_tags imported from personal_agent.text_utils


def _format_style_instruction(
    style_profile: Optional[Dict[str, Any]],
    personality_profile: Optional[Dict[str, Any]] = None,
) -> str:
    if not style_profile:
        return ""
    label = str(style_profile.get("tone_label") or "balanced").lower()
    personality_profile = personality_profile or {}
    verbosity_pref = str(personality_profile.get("verbosity") or "").lower()
    emoji_pref = str(personality_profile.get("emoji") or "").lower()
    format_pref = str(personality_profile.get("format") or "").lower()
    if label == "playful":
        base = (
            "Tone: playful and witty when appropriate; mirror the user's humor. "
            "Shift to serious and grounded when the topic is serious. Keep language natural and not overly formal."
        )
    elif label == "serious":
        base = (
            "Tone: calm, direct, and empathetic. Avoid jokes unless the user cues humor. "
            "Keep language natural and not overly formal."
        )
    elif label == "adaptive":
        base = (
            "Tone: adaptive; light when the user is playful, grounded when the user is serious. "
            "Keep a warm, consistent voice. Keep language natural and not overly formal."
        )
    else:
        base = (
            "Tone: friendly and flexible; lightly playful when the user is playful, "
            "and serious when they are serious. Keep language natural and not overly formal."
        )

    verbosity_line = ""
    if verbosity_pref == "concise":
        verbosity_line = "Prefer concise responses unless detail is explicitly requested."
    elif verbosity_pref == "verbose":
        verbosity_line = "Prefer detailed responses with concrete steps and examples."

    emoji_line = ""
    if emoji_pref == "off":
        emoji_line = "Avoid emojis unless the user uses them first."
    elif emoji_pref == "on":
        emoji_line = "Emojis are welcome if they match the tone."

    format_line = ""
    if format_pref == "structured":
        format_line = "Prefer structured formatting (short sections or bullets) when it helps clarity."
    elif format_pref == "freeform":
        format_line = "Prefer natural paragraphs over heavy bulleting unless requested."

    extras = " ".join([s for s in [verbosity_line, emoji_line, format_line] if s])
    return f"{base} {extras}".strip()


def _detect_response_mood(
    response: str,
    thinking: str = "",
    confidence: float = 0.7,
    contradiction_detected: bool = False,
) -> Dict[str, Any]:
    """Detect the mood/tone of a response for UI visualization."""
    response_lower = response.lower()
    thinking_lower = thinking.lower() if thinking else ""

    triggers: List[str] = []
    mood = "calm"
    intensity = 0.3
    thinking_depth = min(1.0, len(thinking) / 2000) if thinking else 0.0

    warm_words = [
        "happy", "glad", "great", "wonderful", "love", "enjoy", "excited",
        "welcome", "pleasure", "delighted", "awesome", "fantastic", "😊", "🎉",
    ]
    warm_count = sum(1 for w in warm_words if w in response_lower)

    playful_words = [
        "haha", "lol", "funny", "joke", "silly", "😄", "😂", "🤣",
        "quirky", "whimsical", "amusing", "teasing",
    ]
    playful_count = sum(1 for w in playful_words if w in response_lower)

    intense_words = [
        "important", "critical", "crucial", "significant", "challenge",
        "complex", "difficult", "serious", "careful", "warning", "consider",
        "however", "but", "actually", "contradiction", "conflict",
    ]
    intense_count = sum(1 for w in intense_words if w in response_lower or w in thinking_lower)

    curious_words = [
        "interesting", "wonder", "curious", "fascinating", "intriguing",
        "hmm", "perhaps", "maybe", "what if", "🤔",
    ]
    curious_count = sum(1 for w in curious_words if w in response_lower or w in thinking_lower)

    uncertain_words = [
        "unsure", "uncertain", "don't know", "not sure", "might be",
        "possibly", "i think", "seems like", "could be",
    ]
    uncertain_count = sum(1 for w in uncertain_words if w in response_lower)

    deep_thinking_words = [
        "analyzing", "considering", "evaluating", "weighing",
        "multiple", "factors", "implications", "reasoning",
        "therefore", "because", "evidence", "conclusion",
    ]
    deep_count = sum(1 for w in deep_thinking_words if w in thinking_lower)

    counts = {
        "warm": warm_count,
        "playful": playful_count,
        "intense": intense_count + (2 if contradiction_detected else 0),
        "curious": curious_count,
        "uncertain": uncertain_count,
    }

    max_mood = max(counts, key=counts.get)  # type: ignore[arg-type]
    max_count = counts[max_mood]

    if max_count >= 2:
        mood = max_mood
        triggers.append(f"{mood}_keywords")

    if contradiction_detected:
        intensity = max(intensity, 0.7)
        triggers.append("contradiction")

    if thinking_depth > 0.5:
        intensity = max(intensity, 0.5 + thinking_depth * 0.3)
        triggers.append("deep_thinking")

    if deep_count >= 3:
        intensity = max(intensity, 0.6)
        mood = "intense"
        triggers.append("complex_reasoning")

    if confidence < 0.5:
        mood = "uncertain"
        intensity = 0.4
        triggers.append("low_confidence")

    if playful_count >= 2:
        mood = "playful"
        intensity = min(0.6, intensity)

    if warm_count >= 3:
        mood = "warm"
        intensity = max(0.4, min(0.7, intensity))

    return {
        "mood": mood,
        "intensity": round(min(1.0, intensity), 2),
        "thinking_depth": round(thinking_depth, 2),
        "triggers": triggers,
    }


def _user_requested_expansion(text: str) -> bool:
    t = (text or "").strip().lower()
    if not t:
        return False
    return any(t == trigger or t.startswith(trigger + " ") for trigger in _EXPAND_TRIGGERS)


def _get_verbosity_preference(thread_id: str, memory_system) -> Optional[str]:
    try:
        episodic_mgr = get_episodic_manager(memory_system=memory_system)
        ctx = episodic_mgr.get_user_context()
        prefs = ctx.get("preferences", {}) if isinstance(ctx, dict) else {}
        response_style = prefs.get("response_style", {}) if isinstance(prefs, dict) else {}
        verbosity = response_style.get("verbosity", {}) if isinstance(response_style, dict) else {}
        value = verbosity.get("value")
        if isinstance(value, str) and value.strip():
            return value.strip().lower()
    except Exception as e:
        logger.debug(f"[PREF] Failed to read verbosity preference for {thread_id}: {e}")
        return None


def _get_preference_profile(thread_id: str, memory_system) -> Dict[str, Any]:
    """Load episodic preferences payload for routing/prompt adaptation."""
    try:
        episodic_mgr = get_episodic_manager(memory_system=memory_system)
        ctx = episodic_mgr.get_user_context()
        prefs = ctx.get("preferences", {}) if isinstance(ctx, dict) else {}
        if isinstance(prefs, dict):
            return prefs
    except Exception as e:
        logger.debug(f"[PREF] Failed to load preference profile for {thread_id}: {e}")
    return {}


def _format_preference_instruction(preference_profile: Optional[Dict[str, Any]]) -> str:
    """Create concise, high-confidence preference constraints for stream prompts."""
    if not isinstance(preference_profile, dict):
        return ""

    response_style = preference_profile.get("response_style")
    if not isinstance(response_style, dict):
        response_style = preference_profile
    code_style = preference_profile.get("code_style")
    if not isinstance(code_style, dict):
        code_style = {}

    def _pref_value(pref_map: Dict[str, Any], key: str) -> tuple[str, float]:
        raw = pref_map.get(key)
        if isinstance(raw, dict):
            val = str(raw.get("value") or "").strip().lower()
            try:
                conf = float(raw.get("confidence") or 0.0)
            except Exception:
                conf = 0.0
            return val, conf
        if raw is None:
            return "", 0.0
        return str(raw).strip().lower(), 0.5

    lines: List[str] = []

    verbosity, verbosity_conf = _pref_value(response_style, "verbosity")
    if verbosity_conf >= 0.6:
        if verbosity == "concise":
            lines.append("Keep responses concise unless the user asks for detail.")
        elif verbosity == "verbose":
            lines.append("Provide detailed responses with context by default.")

    fmt, fmt_conf = _pref_value(response_style, "format")
    if fmt_conf >= 0.6:
        if fmt == "structured":
            lines.append("Prefer structured formatting (sections/lists) when helpful.")
        elif fmt == "freeform":
            lines.append("Prefer natural prose over list-heavy formatting.")

    emoji, emoji_conf = _pref_value(response_style, "emoji_usage")
    if emoji_conf >= 0.6:
        if emoji == "none":
            lines.append("Do not use emoji.")
        elif emoji == "minimal":
            lines.append("Use emoji sparingly.")

    citation, citation_conf = _pref_value(response_style, "citation_style")
    if citation_conf >= 0.6 and citation == "required":
        lines.append("When providing factual claims, include sources where possible.")

    language, language_conf = _pref_value(code_style, "language")
    if language_conf >= 0.6 and language:
        lines.append(f"For code examples, prefer {language} unless user asks otherwise.")

    if not lines:
        return ""
    return "LEARNED USER PREFERENCES:\n" + "\n".join(f"- {line}" for line in lines)


def _route_model_for_request(
    request: Request,
    *,
    query: str,
    mode: Optional[str] = None,
    preference_profile: Optional[Dict[str, Any]] = None,
    channel: Optional[str] = None,
) -> Tuple[Optional[str], Optional[Dict[str, Any]]]:
    """Select a model for this request using app-level model router."""
    router_obj = getattr(request.app.state, "model_router", None)
    if router_obj is None:
        return None, None
    try:
        routed = router_obj.route(
            query=query,
            requested_mode=mode,
            preference_profile=preference_profile,
            channel=channel,
        )
        if routed is None:
            return None, None
        model = getattr(routed, "model", None)
        route_dict = routed.to_dict() if hasattr(routed, "to_dict") else {
            "route": str(getattr(routed, "route", "")),
            "model": str(model or ""),
            "reason": str(getattr(routed, "reason", "")),
        }
        return (str(model).strip() if model else None), route_dict
    except Exception as e:
        logger.debug(f"[MODEL_ROUTER] Failed to route model: {e}")
        return None, None


def _should_expand_response(
    question: str,
    response: str,
    reflection_result: Optional[ReflectionResult],
    verbosity_pref: Optional[str],
) -> Tuple[bool, Optional[str]]:
    if not response:
        return False, None
    if verbosity_pref == "concise":
        return False, None
    if _user_requested_expansion(question):
        return True, "user_requested"
    if reflection_result and reflection_result.suggested_action in ("refine", "re-query"):
        return True, f"reflection_{reflection_result.suggested_action}"
    if verbosity_pref == "verbose" and len(response) < 1400:
        return True, "preference_verbose"
    return False, None


def _build_expansion_prompt(
    question: str,
    response: str,
    known_facts: str,
    reflection_result: Optional[ReflectionResult],
) -> str:
    parts = [
        "You are expanding a draft answer after a self-check.",
        "Rules:",
        "- Do not repeat the original answer verbatim.",
        "- Add missing details, examples, or concrete steps when useful.",
        "- If you are unsure, say what is uncertain instead of guessing.",
        "",
        f"Question:\n{question}",
        "",
        f"Draft answer:\n{response}",
    ]
    if known_facts:
        parts.append("")
        parts.append(f"Known facts:\n{known_facts}")
    if reflection_result:
        parts.append("")
        parts.append(
            f"Self-assessment: confidence={reflection_result.confidence_label}, "
            f"suggested_action={reflection_result.suggested_action}"
        )
    parts.append("")
    parts.append("Provide an expanded answer:")
    return "\n".join(parts)


def _generate_expansion(
    llm_client: Any,
    question: str,
    response: str,
    known_facts: str,
    style_profile: Optional[Dict[str, Any]],
    reflection_result: Optional[ReflectionResult],
    personality_profile: Optional[Dict[str, Any]] = None,
) -> Optional[str]:
    if not llm_client:
        return None
    style_instruction = _format_style_instruction(style_profile, personality_profile)
    system_lines = [
        "You are a careful assistant expanding a response after a self-check.",
        "Keep additions grounded in known facts. Avoid speculation.",
    ]
    if style_instruction:
        system_lines.append(style_instruction)
    system_prompt = " ".join(system_lines)
    prompt = _build_expansion_prompt(question, response, known_facts, reflection_result)
    expansion = llm_client.generate(prompt, system=system_prompt, max_tokens=420, temperature=0.4)
    if not isinstance(expansion, str):
        return None
    expansion = _strip_thinking_tags(expansion).strip()
    if not expansion or expansion.startswith("[Ollama error") or expansion.startswith("[Ollama connection error"):
        return None
    # Strip model meta-preamble that leaks from instruction-following models
    expansion = re.sub(
        r"^(Okay[,.]?\s+)?(here'?s?\s+)?(an?\s+)?(expanded|expanded version|expansion)[^:\n]*[:\n]+\s*",
        "",
        expansion,
        flags=re.IGNORECASE,
    ).lstrip()
    expansion = re.sub(
        r"^(Okay[,.]?\s+)(I'?ll|let me|the user|based on)[^\n]*\n+",
        "",
        expansion,
        flags=re.IGNORECASE,
    ).lstrip()
    if not expansion:
        return None
    return expansion


def _chunk_text(text: str, chunk_size: int = 320) -> List[str]:
    if not text:
        return []
    return [text[i : i + chunk_size] for i in range(0, len(text), chunk_size)]


def _normalize_confirmation_text(text: str) -> str:
    return re.sub(r"\s+", " ", str(text or "").strip().lower())


def _is_confirmation_yes(text: str) -> bool:
    normalized = _normalize_confirmation_text(text)
    if not normalized:
        return False
    direct = {
        "yes",
        "y",
        "yeah",
        "yep",
        "sure",
        "ok",
        "okay",
        "do it",
        "confirm",
        "confirmed",
        "please do",
        "set it",
        "schedule it",
    }
    if normalized in direct:
        return True
    return bool(
        re.search(
            r"\b(confirm|go ahead|sounds good|that works|please schedule|yes please)\b",
            normalized,
        )
    )


def _is_confirmation_no(text: str) -> bool:
    normalized = _normalize_confirmation_text(text)
    if not normalized:
        return False
    direct = {
        "no",
        "n",
        "nope",
        "nah",
        "cancel",
        "stop",
        "nevermind",
        "never mind",
        "dont",
        "don't",
        "do not",
    }
    if normalized in direct:
        return True
    return bool(re.search(r"\b(cancel|don't schedule|do not schedule|skip it)\b", normalized))


def _format_reminder_time(ts: Optional[float]) -> str:
    try:
        value = float(ts or 0.0)
    except Exception:
        value = 0.0
    if value <= 0:
        return "the requested time"
    try:
        return datetime.fromtimestamp(value).strftime("%A, %B %d at %I:%M %p")
    except Exception:
        return "the requested time"


# ---------------------------------------------------------------------------
# Closure-scoped helpers (originally inside create_app) -- copied here
# ---------------------------------------------------------------------------


def _is_architecture_explanation_request(text: str) -> bool:
    t = (text or "").strip().lower()
    if not t:
        return False
    if len(t) > 1000:
        return False
    # Do not hijack explicit profile/memory submissions into the doc-grounded lane.
    # Example: "Here is an about me ... I'm building CRT ..."
    profile_markers = (
        "here is an about me",
        "here's an about me",
        "question: here is an about me",
        "about me:",
        "here is my bio",
        "here's my bio",
        "my bio:",
        "remember this about me",
        "store this about me",
        "save this about me",
        "for your memory",
    )
    if any(m in t for m in profile_markers):
        return False
    # Also avoid doc-lane hijack when the user is giving profile-like content.
    if "about me" in t and any(
        m in t
        for m in (
            "my name is",
            "i'm ",
            "i am ",
            "i work",
            "i build",
            "i value",
            "focused on",
        )
    ):
        return False
    # Only route to doc-grounded answers for very specific technical terms.
    # General questions like "how do you work" or "who are you" should go through
    # the LLM path where the self-aware system prompt can answer naturally.
    needles = (
        "crt architecture",
        "system architecture",
        "reconstruction gate",
        "reconstruction gates",
        "trust-weighted memories",
        "trust weighted memories",
        "contradiction preservation",
        "contradiction ledger",
        "coherence priority",
        "cognitive-reflective transformer",
        "cognitive reflective transformer",
        "crt whitepaper",
        "crt spec",
        "functional spec",
    )
    return any(n in t for n in needles)


def _is_contradiction_inventory_request(text: str) -> bool:
    """Detect user requests asking about contradictions/conflicts."""
    t = (text or "").strip().lower()
    if not t:
        return False
    if not any(k in t for k in ("contradict", "inconsisten", "conflict")):
        return False
    needles = (
        "what contradictions",
        "which contradictions",
        "any contradictions",
        "are there contradictions",
        "do you have contradictions",
        "contradictions have you",
        "contradictions did you",
        "contradictions detected",
        "contradictions found",
        "what conflicts",
        "any conflicts",
        "in our conversation",
        "in our chat",
    )
    return any(n in t for n in needles)


def _extract_workplan_items(text: str) -> Dict[int, str]:
    """Parse 'Items N (label)' pairs from a stored work-plan sentence."""
    out: Dict[int, str] = {}
    for num_s, label in re.findall(r"(\d+)\s*\(([^)]+)\)", str(text or "")):
        try:
            num = int(num_s)
        except Exception:
            continue
        clean = " ".join(str(label).strip().split())
        if clean:
            out[num] = clean
    return out


def _load_latest_workplan_from_groundcheck() -> Optional[Tuple[str, str, Dict[int, str]]]:
    """Return (memory_id, text, parsed_items) for the latest GroundCheck work-plan row."""
    try:
        from personal_agent.memory_bridge import find_groundcheck_db

        db_path = find_groundcheck_db()
    except Exception:
        return None
    if not db_path:
        return None

    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(
            """
            SELECT id, text, timestamp
            FROM memories
            WHERE lower(text) LIKE '%work plan%'
               OR lower(text) LIKE '%plan for aether%'
               OR lower(text) LIKE '%item %(%'
               OR lower(text) LIKE '%items %(%'
            ORDER BY timestamp DESC
            LIMIT 20
            """
        ).fetchall()
        for row in rows:
            text = str(row["text"] or "").strip()
            parsed = _extract_workplan_items(text)
            if parsed:
                return str(row["id"]), text, parsed
    except Exception:
        return None
    finally:
        conn.close()
    return None


def _load_latest_workplan_from_crt_memory(
    engine: Any,
    *,
    thread_id: Optional[str] = None,
) -> Optional[Tuple[str, str, Dict[int, str]]]:
    """Fallback work-plan loader from CRT memory when GroundCheck lookup misses."""
    if engine is None:
        return None
    mem = getattr(engine, "memory", None)
    if mem is None:
        return None
    try:
        all_mems = mem._load_all_memories()  # internal helper; best-effort fallback path
    except Exception:
        return None
    if not all_mems:
        return None

    tid = sanitize_thread_id(str(thread_id or "default")) if thread_id else None
    scoped = []
    for m in all_mems:
        m_tid = str(getattr(m, "thread_id", "") or "").strip()
        if tid and m_tid and m_tid != tid:
            continue
        scoped.append(m)

    scoped.sort(key=lambda m: float(getattr(m, "timestamp", 0.0) or 0.0), reverse=True)
    for m in scoped[:120]:
        text = str(getattr(m, "text", "") or "").strip()
        if not text:
            continue
        tl = text.lower()
        if "work plan" not in tl and "item" not in tl:
            continue
        parsed = _extract_workplan_items(text)
        if not parsed:
            continue
        mem_id = str(getattr(m, "memory_id", "") or getattr(m, "id", "") or "")
        if mem_id:
            return mem_id, text, parsed
    return None


def _load_latest_groundcheck_memory_by_phrase(
    phrases: Tuple[str, ...],
    *,
    limit: int = 8,
) -> Optional[Tuple[str, str]]:
    """Return latest (memory_id, text) matching any lowercase phrase."""
    try:
        from personal_agent.memory_bridge import find_groundcheck_db

        db_path = find_groundcheck_db()
    except Exception:
        return None
    if not db_path:
        return None

    lowered = [str(p or "").strip().lower() for p in phrases if str(p or "").strip()]
    if not lowered:
        return None

    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    try:
        where = " OR ".join("lower(text) LIKE ?" for _ in lowered)
        params = [f"%{p}%" for p in lowered] + [max(1, int(limit))]
        rows = conn.execute(
            f"""
            SELECT id, text, timestamp
            FROM memories
            WHERE {where}
            ORDER BY timestamp DESC
            LIMIT ?
            """,
            params,
        ).fetchall()
        for row in rows:
            text = str(row["text"] or "").strip()
            if text:
                return str(row["id"]), text
    except Exception:
        return None
    finally:
        conn.close()
    return None


def _try_answer_workplan_question(
    message: str,
    *,
    engine: Any = None,
    thread_id: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """Deterministic answer path for numbered work-plan item questions."""
    q = str(message or "").strip()
    if not q:
        return None
    ql = q.lower()
    if not any(k in ql for k in ("work plan", "plan item", "plan items", " item ", "items ", "number ")):
        return None

    loaded = _load_latest_workplan_from_groundcheck()
    if not loaded and engine is not None:
        loaded = _load_latest_workplan_from_crt_memory(engine, thread_id=thread_id)
    if not loaded:
        return None
    source_id, source_text, items = loaded
    if not items:
        return None

    explicit_targets = [int(n) for n in re.findall(r"(?:item|number)\s*(\d+)", ql)]
    numeric_targets = []
    for n in re.findall(r"\b\d+\b", ql):
        try:
            iv = int(n)
        except Exception:
            continue
        if iv in items:
            numeric_targets.append(iv)

    requested = [n for n in explicit_targets if n in items]
    if not requested:
        requested = numeric_targets
    requested = list(dict.fromkeys(requested))  # preserve order, dedupe

    if "next" in ql and requested:
        pivot = requested[-1]
        higher = sorted([n for n in items.keys() if n > pivot])
        if higher:
            nxt = higher[0]
            return {
                "answer": f"Item {nxt}: {items[nxt]}.",
                "source_memory_id": source_id,
                "source_text": source_text,
                "items": {str(k): v for k, v in sorted(items.items())},
            }

    summary_like = (
        "summarize" in ql
        or "summary" in ql
        or ("plan items" in ql and len(requested) >= 2)
        or ("all" in ql and "item" in ql)
    )

    if not requested and summary_like:
        requested = sorted(items.keys())
    if not requested:
        return None

    if "just the label" in ql and len(requested) == 1:
        answer = items[requested[0]]
    elif len(requested) == 1:
        n = requested[0]
        answer = f"Item {n}: {items[n]}."
    else:
        parts = [f"Item {n}: {items[n]}" for n in requested if n in items]
        answer = "; ".join(parts) + "."

    return {
        "answer": answer,
        "source_memory_id": source_id,
        "source_text": source_text,
        "items": {str(k): v for k, v in sorted(items.items())},
    }


def _try_answer_mcp_tools_question(message: str) -> Optional[Dict[str, Any]]:
    """Deterministic answer path for MCP tools expansion memory queries."""
    q = str(message or "").strip()
    if not q:
        return None
    ql = q.lower()
    if not ("mcp" in ql and "tool" in ql):
        return None

    loaded = _load_latest_groundcheck_memory_by_phrase(
        ("mcp tools expansion ideas", "new tools to build"),
        limit=8,
    )
    if not loaded:
        return None
    source_id, source_text = loaded

    tools = re.findall(r"\b(?:cogniforge|crt)_[a-z0-9_]+\b", source_text.lower())
    tool_list: List[str] = []
    for t in tools:
        if t not in tool_list:
            tool_list.append(t)

    if not tool_list:
        return None

    picked: Optional[str] = None
    if any(k in ql for k in ("topic", "rising", "fading", "drift")) and "crt_topic_drift" in tool_list:
        picked = "crt_topic_drift"
    elif "code context" in ql and "crt_search_code_context" in tool_list:
        picked = "crt_search_code_context"
    elif "project memory" in ql and "crt_project_memory" in tool_list:
        picked = "crt_project_memory"

    if picked is None:
        picked = tool_list[0]

    if any(k in ql for k in ("one tool", "name one", "just one", "single")):
        answer = picked
    else:
        answer = ", ".join(tool_list)

    return {
        "answer": answer,
        "source_memory_id": source_id,
        "source_text": source_text,
        "tools": tool_list,
    }


def _load_doc_text(doc_map: Dict[str, Any], doc_id: str) -> str:
    info = doc_map.get(doc_id)
    if not info:
        return ""
    path = info.get("path")
    try:
        return Path(path).read_text(encoding="utf-8", errors="ignore")  # type: ignore[arg-type]
    except Exception:
        return ""


def _score_snippet(snippet: str, q_words: List[str]) -> float:
    s = snippet.lower()
    score = 0.0
    for w in q_words:
        if not w:
            continue
        if w in s:
            score += 1.0
    score *= 1.0 / max(1.0, (len(snippet) / 800.0))
    return score


def _answer_from_docs(
    query: str,
    doc_map: Dict[str, Any],
) -> Tuple[str, List[Dict[str, Any]]]:
    q = (query or "").strip()
    ql = q.lower()
    q_words = [w for w in re.split(r"[^a-z0-9_]+", ql) if len(w) >= 3]

    doc_ids = [
        "how_it_works",
        "crt_whitepaper",
        "crt_quick_reference",
        "project_summary",
        "crt_dashboard_guide",
        "architecture",
        "functional_spec",
    ]

    candidates: List[Tuple[float, str, str]] = []
    for did in doc_ids:
        txt = _load_doc_text(doc_map, did)
        if not txt:
            continue
        parts = [p.strip() for p in re.split(r"\n\s*\n", txt) if p.strip()]
        for p in parts:
            if len(p) < 60:
                continue
            if len(p) > 1600:
                p = p[:1600] + "\u2026"
            sc = _score_snippet(p, q_words)
            if sc <= 0:
                continue
            candidates.append((sc, did, p))

    candidates.sort(key=lambda x: x[0], reverse=True)
    top = candidates[:6]

    lines: List[str] = []
    lines.append("This is a design/spec explanation (doc-grounded), not a personal memory claim.")
    lines.append("")
    lines.append(f"Question: {q}")
    lines.append("")

    if not top:
        lines.append("I could not find a relevant section in the local docs set.")
        lines.append(
            'Try asking about a specific component (e.g., "reconstruction gates", '
            '"contradiction ledger", "trust-weighted memories").'
        )
        return "\n".join(lines), []

    prompt_items: List[Dict[str, Any]] = []
    for i, (_sc, did, snippet) in enumerate(top, start=1):
        title = str((doc_map.get(did) or {}).get("title") or did)
        lines.append(f"{i}. From {title}:")
        lines.append(snippet)
        lines.append("")
        prompt_items.append(
            {
                "memory_id": f"doc:{did}",
                "text": f"DOC[{did}]: {snippet}",
                "source": "docs",
                "trust": None,
                "confidence": None,
            }
        )

    lines.append(
        "If you want, tell me which part to go deeper on "
        "(gates, memory, ledger, coherence), and I\u2019ll expand that section."
    )
    return "\n".join(lines).strip(), prompt_items


# ============================================================================
# POST /api/chat/send
# ============================================================================


@router.post("/send", response_model=ChatSendResponse)
def chat_send(req: ChatSendRequest, request: Request) -> ChatSendResponse:
    get_engine = request.app.state.get_engine
    get_llm_client = request.app.state.get_llm_client
    increment_turn = request.app.state.increment_turn
    _log_collapse_trail = request.app.state.log_collapse_trail

    engine = get_engine(req.thread_id)
    runtime_config = get_runtime_config()
    control_state = ResponseControlState(request_text=str(req.message or ""))
    control_state.mark("input_pause", "ready", chars=len(str(req.message or "")))
    timing_enabled = str(os.getenv("CRT_CHAT_TIMING", "1")).strip().lower() not in {"0", "false", "off", "no"}
    t0 = time.perf_counter()
    stage_marks: List[Dict[str, Any]] = []

    def _mark(stage: str) -> None:
        if not timing_enabled:
            return
        now = time.perf_counter()
        stage_marks.append(
            {
                "stage": stage,
                "t_ms": round((now - t0) * 1000.0, 2),
            }
        )

    def _timings() -> List[Dict[str, Any]]:
        if not timing_enabled:
            return []
        out: List[Dict[str, Any]] = []
        prev = 0.0
        for item in stage_marks:
            current = float(item.get("t_ms") or 0.0)
            out.append(
                {
                    "stage": item.get("stage"),
                    "t_ms": current,
                    "dt_ms": round(current - prev, 2),
                }
            )
            prev = current
        return out

    def _response_action(gates_passed: bool, gate_reason: Optional[str], response_type: str) -> str:
        reason = str(gate_reason or "")
        if not gates_passed:
            if "contradiction" in reason or response_type == "uncertainty":
                return "clarify"
            return "block"
        if reason in {"recent_slot_provenance", "meta_awareness", "docs_explanation"}:
            return "explain"
        if "reminder" in reason:
            return "confirm"
        return "send"

    def _finalize_metadata(
        metadata: Optional[Dict[str, Any]],
        *,
        response_type: str,
        gates_passed: bool,
        gate_reason: Optional[str],
    ) -> Dict[str, Any]:
        meta = dict(metadata or {})
        meta["response_type"] = response_type
        meta["gates_passed"] = bool(gates_passed)
        meta["gate_reason"] = gate_reason
        control_state.final_action = _response_action(gates_passed, gate_reason, response_type)
        meta["response_control"] = {
            "request_kind": control_state.request_kind,
            "final_action": control_state.final_action,
            "effective_text": control_state.effective_text or control_state.request_text,
            "stages": list(control_state.stages),
        }
        existing = list(meta.get("pipeline_statuses") or [])
        meta["pipeline_statuses"] = _control_status_lines(control_state) + existing
        return meta

    def _chat_response(
        *,
        answer: str,
        response_type: str,
        gates_passed: bool,
        gate_reason: Optional[str],
        metadata: Optional[Dict[str, Any]] = None,
        xray: Optional[Dict[str, Any]] = None,
    ) -> ChatSendResponse:
        return ChatSendResponse(
            answer=answer,
            response_type=response_type,
            gates_passed=gates_passed,
            gate_reason=gate_reason,
            session_id=getattr(engine, "session_id", None),
            metadata=_finalize_metadata(
                metadata,
                response_type=response_type,
                gates_passed=gates_passed,
                gate_reason=gate_reason,
            ),
            xray=xray,
        )

    _mark("chat_send_start")

    # Session tracking: update activity and check for greeting
    session_db = get_thread_session_db()
    session = session_db.get_or_create_session(req.thread_id)

    # Persist channel context only when explicit channel metadata is provided.
    try:
        if req.channel or req.actor_id or req.channel_destination_id:
            session_db.update_channel_context(
                req.thread_id,
                channel=(req.channel or "api"),
                actor_id=req.actor_id,
                destination_id=req.channel_destination_id,
            )
    except Exception as e:
        logger.debug(f"[CHANNEL_CTX] Failed to persist channel context for {req.thread_id}: {e}")

    # Generate greeting if applicable (before processing query)
    greeting_text = None
    try:
        greeting_text = get_time_based_greeting(
            thread_id=req.thread_id,
            runtime_config=runtime_config,
            session_db=session_db,
            user_profile=engine.user_profile,
        )
    except Exception as e:
        logger.debug(f"[GREETING] Error generating greeting: {e}")

    # Update session activity
    session_db.update_activity(req.thread_id, increment_messages=True)
    style_profile = None
    try:
        style_profile = session_db.update_style_profile(req.thread_id, req.message)
    except Exception as e:
        logger.debug(f"[STYLE] Failed to update style profile: {e}")
    personality_profile = None
    reflection_scorecard = None
    try:
        personality_profile = session_db.get_personality_profile(req.thread_id)
    except Exception as e:
        logger.debug(f"[PERSONALITY] Failed to read personality profile: {e}")
    try:
        reflection_scorecard = session_db.get_reflection_scorecard(req.thread_id)
    except Exception as e:
        logger.debug(f"[REFLECTION_LOOP] Failed to read reflection scorecard: {e}")

    # Increment turn counter
    increment_turn(req.thread_id)
    _mark("session_and_style_ready")

    effective_message = _resolve_bare_web_search_command(
        message=req.message,
        session_db=session_db,
        thread_id=req.thread_id,
    )
    control_state.effective_text = effective_message
    control_state.request_kind = "follow_up" if _looks_like_follow_up(effective_message) else "direct"
    if _is_meta_provenance_followup(effective_message):
        control_state.request_kind = "meta_provenance"
    elif _is_architecture_explanation_request(effective_message):
        control_state.request_kind = "architecture_explanation"
    elif _is_contradiction_inventory_request(effective_message):
        control_state.request_kind = "contradiction_inventory"
    control_state.mark(
        "determine_request",
        "classified",
        request_kind=control_state.request_kind,
        follow_up=_looks_like_follow_up(effective_message),
    )

    openclaw_delegate, openclaw_reason = should_delegate_to_openclaw(
        message=effective_message,
        channel=req.channel,
        meta_scope=req.meta_scope,
        mode=req.mode,
        runtime_config=runtime_config,
    )
    if openclaw_delegate:
        structured_facts: Dict[str, Any] = {}
        try:
            if hasattr(engine, "get_effective_user_facts"):
                maybe_facts = engine.get_effective_user_facts(thread_id=req.thread_id)
                if isinstance(maybe_facts, dict):
                    structured_facts = maybe_facts
        except Exception as e:
            logger.debug("[OPENCLAW] Failed to build structured fact context: %s", e)

        try:
            openclaw_result = run_openclaw_agent(
                user_command=effective_message,
                thread_id=req.thread_id,
                crt_api_url=os.getenv("CRT_API_URL", "http://127.0.0.1:8123"),
                channel=req.channel,
                origin=req.origin,
                actor_id=req.actor_id,
                structured_facts=structured_facts,
                runtime_config=runtime_config,
                workdir=Path.cwd(),
            )
            if openclaw_result.get("ok"):
                control_state.request_kind = "openclaw_handoff"
                control_state.mark(
                    "decide",
                    "openclaw",
                    detail=str(openclaw_reason or "delegated"),
                    session_id=str(openclaw_result.get("session_id") or ""),
                )
                delegated_answer = str(openclaw_result.get("answer") or "").strip()
                if greeting_text:
                    delegated_answer = f"{greeting_text}\n\n{delegated_answer}"
                return _chat_response(
                    answer=delegated_answer,
                    response_type="speech",
                    gates_passed=True,
                    gate_reason="openclaw_handoff",
                    metadata={
                        "mode": "openclaw",
                        "confidence": 0.88,
                        "agent_activated": True,
                        "openclaw_delegated": True,
                        "openclaw_handoff_reason": openclaw_reason,
                        "openclaw_session_id": openclaw_result.get("session_id"),
                        "openclaw_agent_id": openclaw_result.get("agent_id"),
                        "structured_facts": structured_facts,
                        "pipeline_statuses": [
                            "delegating to openclaw",
                            f"openclaw session {openclaw_result.get('session_id')}",
                        ],
                    },
                )
            logger.warning(
                "[OPENCLAW] Handoff failed for thread=%s reason=%s rc=%s stderr=%s",
                req.thread_id,
                openclaw_reason,
                openclaw_result.get("returncode"),
                str(openclaw_result.get("stderr") or "")[:300],
            )
            control_state.mark(
                "decide",
                "openclaw_fallback",
                detail=str(openclaw_reason or "delegated"),
                returncode=int(openclaw_result.get("returncode") or 0),
            )
        except Exception as e:
            logger.warning("[OPENCLAW] Handoff exception for thread=%s: %s", req.thread_id, e)
            control_state.mark("decide", "openclaw_fallback", detail="exception")

    # ── Agentic URL/tool routing ──────────────────────────────────────────────
    # If the message contains a URL with an action verb (read, fetch, visit, check,
    # open, go to, follow), route straight to the agent so it can FETCH_URL and act.
    _url_action_re = re.compile(
        r"\b(read|fetch|visit|check|open|go to|follow|access|look at|get|load)\b.{0,60}https?://\S+",
        re.IGNORECASE,
    )
    _bare_url_re = re.compile(r"^https?://\S+$")
    _tool_keyword_re = re.compile(
        r"\b(moltbook|openclaw)\b",
        re.IGNORECASE,
    )
    if _url_action_re.search(effective_message) or _bare_url_re.match(effective_message.strip()) or _tool_keyword_re.search(effective_message):
        try:
            from personal_agent.agent_loop import create_agent
            _ag = create_agent(
                memory_engine=engine.memory,
                workspace_root=Path.cwd(),
                max_steps=12,
            )
            control_state.mark("decide", "agent_url", detail="url_action_detected")
            _trace = _ag.run(effective_message)
            _url_answer = (_trace.final_answer or "").strip()
            if _url_answer:
                return _chat_response(
                    answer=_url_answer,
                    response_type="speech",
                    gates_passed=True,
                    gate_reason="agent_url_fetch",
                    metadata={
                        "mode": "agent",
                        "confidence": 0.85,
                        "agent_activated": True,
                        "agent_trace": _trace.to_dict(),
                        "pipeline_statuses": ["accessing tools", "running agent", f"agent activated"],
                    },
                )
        except Exception as _e:
            logger.warning("[AGENT_URL] Failed to route URL fetch to agent: %s", _e)
    # ── End agentic URL routing ───────────────────────────────────────────────

    if _is_meta_provenance_followup(effective_message):
        control_state.mark("bind", "recent_slot", detail="provenance_followup")
        provenance_answer = _answer_recent_slot_provenance(
            engine=engine,
            session_db=session_db,
            thread_id=req.thread_id,
        )
        provenance_gate_reason = "recent_slot_provenance" if provenance_answer else "generic_meta_provenance"
        if not provenance_answer:
            provenance_answer = _generic_meta_provenance_answer()
        if greeting_text:
            provenance_answer = f"{greeting_text}\n\n{provenance_answer}"
        try:
            session_db.record_query(
                thread_id=req.thread_id,
                query_text=req.message,
                response_text=provenance_answer,
                detected_slot="provenance",
            )
        except Exception as e:
            logger.debug(f"[SESSION] Error recording deterministic provenance query: {e}")
        control_state.mark("decide", "ready", detail=provenance_gate_reason)
        control_state.mark("learn", "recorded", detail="fast_query")
        return _chat_response(
            answer=provenance_answer,
            response_type="explanation",
            gates_passed=True,
            gate_reason=provenance_gate_reason,
            metadata={
                "mode": "deterministic_provenance",
                "confidence": 0.98,
                "continuity_context_applied": True,
            },
        )

    def _record_fast_query(answer_text: str, detected_slot: Optional[str]) -> None:
        try:
            session_db.record_query(
                thread_id=req.thread_id,
                query_text=req.message,
                response_text=answer_text,
                detected_slot=detected_slot,
            )
        except Exception as e:
            logger.debug(f"[SESSION] Error recording deterministic query: {e}")

    # Reminder confirmation flow (explicit yes/no before scheduling).
    pending_reminder: Optional[Dict[str, Any]] = None
    try:
        pending_reminder = session_db.get_pending_reminder(req.thread_id)
    except Exception as e:
        logger.debug(f"[REMINDER] Failed to load pending reminder for {req.thread_id}: {e}")
        pending_reminder = None

    if isinstance(pending_reminder, dict):
        if _is_confirmation_yes(effective_message):
            control_state.request_kind = "reminder_confirmation"
            control_state.mark("bind", "pending_reminder", detail="confirm_yes")
            reminder_text = str(pending_reminder.get("reminder_text") or "").strip()
            scheduled_at = float(pending_reminder.get("scheduled_at") or 0.0)
            if reminder_text and scheduled_at > time.time():
                db_path = str(getattr(request.app.state, "scheduled_tasks_db_path", "") or "")
                if db_path:
                    try:
                        task = schedule_reminder(
                            db_path=db_path,
                            thread_id=req.thread_id,
                            reminder_text=reminder_text,
                            scheduled_time=datetime.fromtimestamp(scheduled_at),
                        )
                        session_db.clear_pending_reminder(req.thread_id)
                        answer = (
                            f"Confirmed. I will remind you to '{reminder_text}' on "
                            f"{_format_reminder_time(scheduled_at)}."
                        )
                        if greeting_text:
                            answer = f"{greeting_text}\n\n{answer}"
                        _record_fast_query(answer, "reminder_confirmed")
                        control_state.mark("decide", "ready", detail="reminder_scheduled")
                        control_state.mark("learn", "recorded", detail="fast_query")
                        return _chat_response(
                            answer=answer,
                            response_type="speech",
                            gates_passed=True,
                            gate_reason="reminder_scheduled",
                            metadata={
                                "mode": "deterministic_reminder",
                                "confidence": 0.99,
                                "reminder_scheduled": True,
                                "reminder_task_id": getattr(task, "task_id", None),
                                "reminder_text": reminder_text,
                                "reminder_time": scheduled_at,
                            },
                        )
                    except Exception as e:
                        logger.warning(f"[REMINDER] Failed to schedule confirmed reminder: {e}")
                        session_db.clear_pending_reminder(req.thread_id)
                        error_answer = "I could not schedule that reminder due to an internal error. Please try again."
                        _record_fast_query(error_answer, "reminder_error")
                        control_state.mark("decide", "blocked", detail="reminder_schedule_error")
                        control_state.mark("learn", "recorded", detail="fast_query")
                        return _chat_response(
                            answer=error_answer,
                            response_type="speech",
                            gates_passed=False,
                            gate_reason="reminder_schedule_error",
                            metadata={
                                "mode": "deterministic_reminder",
                                "confidence": 0.35,
                                "reminder_scheduled": False,
                            },
                        )
            session_db.clear_pending_reminder(req.thread_id)
            cleared_answer = "That reminder request expired or had invalid timing, so I cleared it. Ask again and I will re-parse it."
            _record_fast_query(cleared_answer, "reminder_pending_cleared")
            control_state.mark("decide", "ready", detail="reminder_pending_cleared")
            control_state.mark("learn", "recorded", detail="fast_query")
            return _chat_response(
                answer=cleared_answer,
                response_type="speech",
                gates_passed=True,
                gate_reason="reminder_pending_cleared",
                metadata={
                    "mode": "deterministic_reminder",
                    "confidence": 0.9,
                    "reminder_pending_cleared": True,
                },
            )

        if _is_confirmation_no(effective_message):
            control_state.request_kind = "reminder_confirmation"
            control_state.mark("bind", "pending_reminder", detail="confirm_no")
            session_db.clear_pending_reminder(req.thread_id)
            answer = "Canceled. I did not schedule that reminder."
            if greeting_text:
                answer = f"{greeting_text}\n\n{answer}"
            _record_fast_query(answer, "reminder_cancelled")
            control_state.mark("decide", "ready", detail="reminder_cancelled")
            control_state.mark("learn", "recorded", detail="fast_query")
            return _chat_response(
                answer=answer,
                response_type="speech",
                gates_passed=True,
                gate_reason="reminder_cancelled",
                metadata={
                    "mode": "deterministic_reminder",
                    "confidence": 0.99,
                    "reminder_cancelled": True,
                },
            )

    reminder_candidate = None
    try:
        reminder_candidate = extract_reminder_from_message(effective_message)
    except Exception as e:
        logger.debug(f"[REMINDER] Reminder extraction failed: {e}")
        reminder_candidate = None

    if reminder_candidate:
        control_state.request_kind = "reminder_candidate"
        control_state.mark("bind", "reminder_candidate")
        reminder_text, reminder_dt = reminder_candidate
        scheduled_at = float(reminder_dt.timestamp())
        if scheduled_at <= time.time():
            past_answer = "I parsed a reminder request, but the target time is in the past. Please provide a future time."
            _record_fast_query(past_answer, "reminder_past_time")
            control_state.mark("decide", "ready", detail="reminder_past_time")
            control_state.mark("learn", "recorded", detail="fast_query")
            return _chat_response(
                answer=past_answer,
                response_type="speech",
                gates_passed=True,
                gate_reason="reminder_past_time",
                metadata={
                    "mode": "deterministic_reminder",
                    "confidence": 0.92,
                    "reminder_confirmation_required": False,
                },
            )
        session_db.set_pending_reminder(
            req.thread_id,
            reminder_text=str(reminder_text),
            scheduled_at=scheduled_at,
            source_message=req.message,
            expires_seconds=900,
        )
        human_time = _format_reminder_time(scheduled_at)
        answer = (
            f"I parsed this reminder: '{str(reminder_text).strip()}' at {human_time}. "
            "Reply 'yes' to confirm, or 'no' to cancel."
        )
        if greeting_text:
            answer = f"{greeting_text}\n\n{answer}"
        _record_fast_query(answer, "reminder_confirmation")
        control_state.mark("decide", "ready", detail="reminder_confirmation_required")
        control_state.mark("learn", "recorded", detail="fast_query")
        return _chat_response(
            answer=answer,
            response_type="speech",
            gates_passed=True,
            gate_reason="reminder_confirmation_required",
            metadata={
                "mode": "deterministic_reminder",
                "confidence": 0.97,
                "reminder_confirmation_required": True,
                "reminder_candidate": {
                    "text": str(reminder_text).strip(),
                    "scheduled_at": scheduled_at,
                    "scheduled_for": human_time,
                },
            },
        )

    groundcheck_bridge_meta: Optional[Dict[str, Any]] = None
    try:
        groundcheck_bridge_meta = _maybe_sync_groundcheck_bridge(
            thread_id=req.thread_id,
            engine=engine,
        )
    except Exception as e:
        logger.debug(f"[MEMORY_BRIDGE] Unexpected sync error: {e}")
        groundcheck_bridge_meta = {"enabled": True, "attempted": True, "ok": False, "error": str(e)}

    if is_meta_awareness_prompt(effective_message):
        control_state.request_kind = "meta_awareness"
        control_state.mark("bind", "meta_awareness")
        snapshot = build_meta_awareness_snapshot(
            thread_id=req.thread_id,
            session_db=session_db,
            engine=engine,
            recent_query_limit=8,
            journal_limit=8,
            contradiction_limit=8,
        )
        answer = render_meta_awareness_response(snapshot)
        if greeting_text:
            answer = f"{greeting_text}\n\n{answer}"
        _record_fast_query(answer, "meta_awareness")
        control_state.mark("decide", "ready", detail="meta_awareness")
        control_state.mark("learn", "recorded", detail="fast_query")
        return _chat_response(
            answer=answer,
            response_type="speech",
            gates_passed=True,
            gate_reason="meta_awareness",
            metadata={
                "mode": "meta_awareness",
                "confidence": 0.96,
                "meta_awareness": snapshot,
                "groundcheck_bridge": groundcheck_bridge_meta,
            },
        )

    # Deterministic ledger-backed contradiction inventory.
    if _is_contradiction_inventory_request(effective_message):
        control_state.request_kind = "contradiction_inventory"
        control_state.mark("bind", "ledger_inventory")
        from personal_agent.canonical_view import get_contradiction_counts

        ledger_db_path = str(getattr(engine.ledger, "db_path", "") or "")
        counts = get_contradiction_counts(ledger_db_path)
        open_count = int(counts.get("open", 0))
        resolved_count = int(counts.get("resolved", 0))
        accepted_count = int(counts.get("accepted", 0))
        reflecting_count = int(counts.get("reflecting", 0))
        total = int(sum(counts.values()))

        try:
            open_entries = engine.ledger.get_open_contradictions(limit=50)
        except Exception:
            open_entries = []

        hard_conflicts = sum(
            1 for e in open_entries if (getattr(e, "contradiction_type", "") or "") == "conflict"
        )

        lines = [
            "I can summarize what I\u2019ve recorded in the contradiction ledger so far.",
            f"Total contradictions recorded: {total}.",
            f"Open: {open_count}. Resolved: {resolved_count}. Accepted: {accepted_count}. Reflecting: {reflecting_count}.",
        ]

        if open_count > 0 and open_entries:
            lines.extend(["", "Most recent open items:"])
            for e in open_entries[:10]:
                typ = getattr(e, "contradiction_type", None) or "conflict"
                status = getattr(e, "status", None) or "open"
                summary = getattr(e, "summary", None) or "(no summary)"
                lines.append(f"- [{typ}/{status}] {summary}")
        elif open_count == 0:
            lines.append("")
            lines.append("There are no open contradictions at the moment.")

        answer = "\n".join(lines)

        control_state.mark("decide", "clarify", detail="ledger_contradictions")
        return _chat_response(
            answer=answer,
            response_type="explanation",
            gates_passed=False,
            gate_reason="ledger_contradictions",
            metadata={
                "mode": "uncertainty",
                "confidence": 0.65,
                "contradiction_detected": False,
                "unresolved_contradictions_total": open_count,
                "unresolved_hard_conflicts": hard_conflicts,
                "retrieved_memories": [],
                "prompt_memories": [],
                "groundcheck_bridge": groundcheck_bridge_meta,
            },
        )

    # Safe doc-grounded channel for architecture/system explanation questions.
    if _is_architecture_explanation_request(effective_message):
        control_state.request_kind = "architecture_explanation"
        control_state.mark("bind", "doc_map")
        doc_map = request.app.state.doc_map
        answer, prompt_items = _answer_from_docs(effective_message, doc_map)
        control_state.mark("decide", "ready", detail="docs_explanation")
        return _chat_response(
            answer=answer,
            response_type="explanation",
            gates_passed=True,
            gate_reason="docs_explanation",
            metadata={
                "confidence": 0.85,
                "retrieved_memories": [],
                "prompt_memories": prompt_items,
            },
        )

    # Deterministic GroundCheck path for numbered work-plan queries.
    direct_workplan = _try_answer_workplan_question(
        effective_message,
        engine=engine,
        thread_id=req.thread_id,
    )
    if direct_workplan:
        control_state.request_kind = "groundcheck_workplan"
        control_state.mark("bind", "groundcheck_workplan")
        direct_answer = str(direct_workplan.get("answer") or "").strip()
        if greeting_text:
            direct_answer = f"{greeting_text}\n\n{direct_answer}"
        metadata = {
            "mode": "direct_groundcheck_workplan",
            "confidence": 0.98,
            "retrieved_memories": [
                {
                    "memory_id": direct_workplan.get("source_memory_id"),
                    "text": direct_workplan.get("source_text"),
                    "source": "groundcheck",
                    "trust": 0.7,
                    "confidence": 0.98,
                }
            ],
            "prompt_memories": [],
            "groundcheck_bridge": groundcheck_bridge_meta,
            "direct_workplan_items": direct_workplan.get("items") or {},
        }
        if greeting_text:
            metadata["greeting_shown"] = True

        try:
            session_db.record_query(
                thread_id=req.thread_id,
                query_text=req.message,
                response_text=direct_answer,
                detected_slot="work_plan_item",
            )
        except Exception as e:
            logger.debug(f"[SESSION] Error recording direct workplan query: {e}")

        control_state.mark("decide", "ready", detail="groundcheck_workplan_direct")
        control_state.mark("learn", "recorded", detail="session_query")
        return _chat_response(
            answer=direct_answer,
            response_type="speech",
            gates_passed=True,
            gate_reason="groundcheck_workplan_direct",
            metadata=metadata,
        )

    direct_mcp_tools = _try_answer_mcp_tools_question(effective_message)
    if direct_mcp_tools:
        control_state.request_kind = "groundcheck_mcp_tools"
        control_state.mark("bind", "groundcheck_mcp_tools")
        direct_answer = str(direct_mcp_tools.get("answer") or "").strip()
        if greeting_text:
            direct_answer = f"{greeting_text}\n\n{direct_answer}"
        metadata = {
            "mode": "direct_groundcheck_mcp_tools",
            "confidence": 0.97,
            "retrieved_memories": [
                {
                    "memory_id": direct_mcp_tools.get("source_memory_id"),
                    "text": direct_mcp_tools.get("source_text"),
                    "source": "groundcheck",
                    "trust": 0.7,
                    "confidence": 0.97,
                }
            ],
            "prompt_memories": [],
            "groundcheck_bridge": groundcheck_bridge_meta,
            "direct_mcp_tools": direct_mcp_tools.get("tools") or [],
        }
        if greeting_text:
            metadata["greeting_shown"] = True

        try:
            session_db.record_query(
                thread_id=req.thread_id,
                query_text=req.message,
                response_text=direct_answer,
                detected_slot="mcp_tools",
            )
        except Exception as e:
            logger.debug(f"[SESSION] Error recording direct MCP-tools query: {e}")

        control_state.mark("decide", "ready", detail="groundcheck_mcp_tools_direct")
        control_state.mark("learn", "recorded", detail="session_query")
        return _chat_response(
            answer=direct_answer,
            response_type="speech",
            gates_passed=True,
            gate_reason="groundcheck_mcp_tools_direct",
            metadata=metadata,
        )

    tasking_enabled = bool(req.mode and str(req.mode).lower() == "tasking")
    mode_arg = None
    if req.mode and not tasking_enabled:
        try:
            from personal_agent.reasoning import ReasoningMode

            mode_arg = ReasoningMode(req.mode)  # type: ignore[arg-type]
        except Exception:
            mode_arg = None

    # ====== Auto Fact-Check: surface pending corrections from last round ======
    fact_check_preamble = ""
    try:
        from personal_agent.auto_fact_checker import get_pending_fact_checks, resolve_fact_check
        pending = get_pending_fact_checks(thread_id=req.thread_id, limit=3)
        if pending:
            issues = []
            for p in pending:
                issues.append(f"- [{p['issue_type']}] {p['claim']}")
                resolve_fact_check(p["id"], resolution="surfaced")
            fact_check_preamble = (
                "\n\n[SYSTEM NOTE — self-correction from previous response: "
                "The following issues were detected in a prior answer. "
                "If relevant to this question, acknowledge and correct them. "
                "If not relevant, ignore silently.]\n"
                + "\n".join(issues)
                + "\n"
            )
    except Exception as e:
        logger.debug(f"[AUTO_FC] Error surfacing pending checks: {e}")

    query_with_context = effective_message
    if fact_check_preamble:
        query_with_context = effective_message + fact_check_preamble

    recent_history = _load_recent_history_messages(session_db, req.thread_id, window=6)
    # Pass structured history for proper multi-turn chat; keep text
    # augmentation as fallback context in the query itself.
    query_with_continuity = _augment_query_with_continuity(
        message=query_with_context,
        history_messages=recent_history,
    )
    control_state.mark(
        "bind",
        "context_ready",
        continuity_applied=(query_with_continuity != query_with_context),
        recent_messages=len(recent_history),
    )

    preference_profile = _get_preference_profile(req.thread_id, engine.memory)
    model_override, model_route = _route_model_for_request(
        request,
        query=effective_message,
        mode=req.mode,
        preference_profile=preference_profile,
        channel=req.channel,
    )

    control_state.mark("generate", "drafting", detail="engine_query")
    result = engine.query(
        user_query=query_with_continuity,
        user_marked_important=req.user_marked_important,
        mode=mode_arg,
        thread_id=req.thread_id,
        model_override=model_override,
        conversation_history=recent_history or None,
        channel=req.channel,
        origin=req.origin,
        authority=req.authority,
        kind=req.kind,
    )
    _mark("engine_query_done")
    control_state.mark(
        "generate",
        "draft_ready",
        gate_reason=str(result.get("gate_reason") or ""),
        response_type=str(result.get("response_type") or ""),
    )

    # ====== CRT-AS-CRITIC: Post-generation verification ======
    # Verify the draft answer against stored memories using GroundCheck (~1ms).
    # This replaces unreliable LLM self-critique with external truth checking.
    critic_meta = None
    try:
        from personal_agent.crt_critic import CRTCritic, VerifyVerdict
        _critic = CRTCritic()
        _draft = result.get("answer", "")
        _retrieved = result.get("retrieved_memories") or []
        if _draft and _retrieved:
            _critic_result = _critic.verify_draft(
                query=effective_message,
                draft_answer=_draft,
                retrieved_memories=_retrieved,
                llm_client=get_llm_client(),
            )
            critic_meta = _critic_result.to_dict()
            # Replace answer with critic's output (may be revised or disclosure)
            result["answer"] = _critic_result.final_answer
            if _critic_result.was_revised:
                logger.info(f"[CRT-CRITIC] Answer revised (verdict={_critic_result.verdict.value})")
                try:
                    from personal_agent.judgment_audit_log import log_judgment, GATE_BLOCKED
                    log_judgment(
                        GATE_BLOCKED,
                        f"CRT-Critic revised answer (verdict={_critic_result.verdict.value})",
                        thread_id=req.thread_id,
                        extra={"verdict": _critic_result.verdict.value, "query": effective_message[:120]},
                    )
                except Exception:
                    pass
            if _critic_result.verdict == VerifyVerdict.HARD_FAIL:
                # Override gates to signal contradiction disclosure
                result["gates_passed"] = False
                result["gate_reason"] = "contradiction_disclosure"
                # Keep metadata consistent with disclosure path for channels/telemetry.
                result["contradiction_detected"] = True
                logger.info("[CRT-CRITIC] Hard fail — surfacing contradiction to user")
                try:
                    from personal_agent.judgment_audit_log import log_judgment, GATE_BLOCKED
                    log_judgment(
                        GATE_BLOCKED,
                        "CRT-Critic HARD_FAIL — contradiction disclosure forced",
                        thread_id=req.thread_id,
                        extra={"verdict": "HARD_FAIL", "query": effective_message[:120]},
                    )
                except Exception:
                    pass
    except ImportError:
        logger.debug("[CRT-CRITIC] crt_critic not available")
    except Exception as e:
        logger.warning(f"[CRT-CRITIC] Verification error (non-fatal): {e}")
    _mark("critic_done")
    control_state.mark(
        "validate",
        "critic_checked",
        detail=str((critic_meta or {}).get("verdict") or "no_critic"),
        gates_passed=bool(result.get("gates_passed")),
    )

    # Capture thinking trace (if available) for non-stream responses.
    llm_client = get_llm_client()
    thinking_content = _strip_thinking_tags(str(result.get("thinking") or ""))
    thinking_trace_id = None
    if thinking_content and len(thinking_content) > 50:
        try:
            thinking_trace_id = engine.memory.store_reasoning_trace(
                query=effective_message,
                thinking_content=thinking_content,
                thread_id=req.thread_id,
                response_summary=str(result.get("answer") or "")[:200] if result.get("answer") else None,
                model=(llm_client.model if llm_client else None),
                metadata={
                    "gates_passed": result.get("gates_passed", True),
                    "confidence": result.get("confidence", 0.7),
                },
            )
        except Exception as e:
            logger.debug(f"[TRACE] Failed to store thinking trace: {e}")
    _mark("thinking_trace_done")

    # AGENT INTEGRATION: Check for proactive triggers
    _llm_enabled = os.getenv("CRT_ENABLE_LLM", "false").lower() == "true"
    agent_activated = False
    agent_trace_data = None
    agent_answer = None

    if _llm_enabled:
        try:
            from personal_agent.proactive_triggers import ProactiveTriggers
            from personal_agent.agent_loop import create_agent

            triggers_engine = ProactiveTriggers(
                confidence_threshold=0.5,
                auto_research_threshold=0.4,
                contradiction_auto_resolve=False,
            )
            detected_triggers = triggers_engine.analyze_response(result)

            if triggers_engine.should_activate_agent(detected_triggers):
                research_engine = None
                try:
                    from personal_agent.research_engine import ResearchEngine

                    research_engine = ResearchEngine()
                except Exception:
                    pass

                agent = create_agent(
                    memory_engine=engine.memory,
                    research_engine=research_engine,
                    workspace_root=Path.cwd(),
                    max_steps=8,
                )

                task = triggers_engine.get_agent_task(detected_triggers, effective_message)
                trace = agent.run(task)

                agent_activated = True
                agent_answer = trace.final_answer
                agent_trace_data = trace.to_dict()

        except Exception as e:
            logger.warning(f"[AGENT] Execution error: {e}")

    # Build retrieved / prompt memory payloads
    retrieved_mems = [
        {
            "memory_id": (m.get("memory_id") if isinstance(m, dict) else None),
            "text": (m.get("text") if isinstance(m, dict) else None),
            "source": (m.get("source") if isinstance(m, dict) else None),
            "trust": (m.get("trust") if isinstance(m, dict) else None),
            "confidence": (m.get("confidence") if isinstance(m, dict) else None),
            "timestamp": (m.get("timestamp") if isinstance(m, dict) else None),
            "sse_mode": (m.get("sse_mode") if isinstance(m, dict) else None),
            "score": (m.get("score") if isinstance(m, dict) else None),
            "reintroduced_claim": (
                engine.ledger.has_open_contradiction(m.get("memory_id"))
                if isinstance(m, dict)
                and m.get("memory_id")
                and hasattr(engine.ledger, "has_open_contradiction")
                else m.get("reintroduced_claim", False) if isinstance(m, dict) else False
            ),
        }
        for m in (result.get("retrieved_memories") or [])
        if isinstance(m, dict)
    ]

    prompt_mems = [
        {
            "memory_id": (m.get("memory_id") if isinstance(m, dict) else None),
            "text": (m.get("text") if isinstance(m, dict) else None),
            "source": (m.get("source") if isinstance(m, dict) else None),
            "trust": (m.get("trust") if isinstance(m, dict) else None),
            "confidence": (m.get("confidence") if isinstance(m, dict) else None),
            "reintroduced_claim": (
                engine.ledger.has_open_contradiction(m.get("memory_id"))
                if isinstance(m, dict)
                and m.get("memory_id")
                and hasattr(engine.ledger, "has_open_contradiction")
                else m.get("reintroduced_claim", False) if isinstance(m, dict) else False
            ),
        }
        for m in (result.get("prompt_memories") or [])
        if isinstance(m, dict)
    ]

    reintro_count = sum(1 for m in retrieved_mems if m.get("reintroduced_claim") is True)

    # ====== Trust reinforcement: boost trust for memories actually used ======
    try:
        from personal_agent.trust_decay import reinforce_memory
        for mem in retrieved_mems:
            mid = mem.get("memory_id")
            if mid:
                reinforce_memory(mid)
    except Exception as e:
        logger.debug(f"[TRUST_DECAY] Error reinforcing memories: {e}")

    base_answer = strip_think_blocks(str(result.get("answer") or ""))

    # ========================================
    # DIRECTED REFLECTION PASS — fired async
    # ========================================
    # Reflection is expensive (~8-9s) and not needed to deliver the answer.
    # Fire it in a background thread; metadata fields will be None for this response.
    reflection_trace_id = None
    reflection_result = None
    if llm_client is not None:
        _bg_grounding_facts = [
            m.get("text", "")[:300]
            for m in (result.get("retrieved_memories") or [])
            if isinstance(m, dict) and m.get("text")
        ][:5]
        _bg_reflection_kwargs = dict(
            question=effective_message,
            response=base_answer,
            thinking=thinking_content,
            thread_id=req.thread_id,
            db_path=engine.memory.db_path,
            facts=_bg_grounding_facts,
            auto_requery=False,
            collect_training_data=True,
        )
        def _run_reflection_bg(**kwargs):
            try:
                run_reflection_pass(**kwargs)
            except Exception as _e:
                logger.debug(f"[REFLECTION_BG] Reflection failed: {_e}")
        threading.Thread(target=_run_reflection_bg, kwargs=_bg_reflection_kwargs, daemon=True).start()
    _mark("reflection_done")
    control_state.mark(
        "validate",
        "reflection_checked",
        detail=str(reflection_trace_id or "none"),
    )

    verbosity_pref = _get_verbosity_preference(req.thread_id, engine.memory)
    if not verbosity_pref and personality_profile:
        try:
            personality_verbosity = str(personality_profile.get("verbosity") or "").lower()
            if personality_verbosity:
                verbosity_pref = personality_verbosity
        except Exception:
            pass
    known_fact_lines: List[str] = []
    for mem in (retrieved_mems + prompt_mems)[:6]:
        if isinstance(mem, dict):
            text = (mem.get("text") or "").strip()
            if text:
                known_fact_lines.append(f"- {text[:280]}")
    known_facts_text = "\n".join(known_fact_lines)

    expanded = False
    expansion_reason: Optional[str] = None
    should_expand, expansion_reason = _should_expand_response(
        effective_message,
        base_answer,
        reflection_result,
        verbosity_pref,
    )
    if should_expand:
        expansion_text = _generate_expansion(
            llm_client,
            effective_message,
            base_answer,
            known_facts_text,
            style_profile,
            reflection_result,
            personality_profile,
        )
        if expansion_text:
            expanded = True
            base_answer = base_answer.rstrip()
            base_answer = f"{base_answer}\n\n{expansion_text}"
        else:
            expansion_reason = None

    final_answer = base_answer
    if greeting_text:
        final_answer = f"{greeting_text}\n\n{final_answer}"

    # Strip LLM error strings that leak from Ollama client
    if final_answer.startswith("[Ollama error:") or final_answer.startswith("[LLM error:") or final_answer.startswith("[Model '"):
        logger.warning("[CHAT] LLM error string leaked into response: %s", final_answer[:120])
        final_answer = "I ran into a problem generating a response. The model may not be available — try again in a moment."

    # Strip generic AI assistant intros / boilerplate (model ignoring FORMAT RULES)
    import re as _re
    _intro_patterns = [
        r"^(Hello!?\s+)?I'?m\s+(your\s+)?AI\s+assistant[^.!]*[.!]\s*",
        r"^I'?m here to help you with questions and tasks\.?\s*",
        r"^I'?m here to help[^.!]*[.!]\s*",
        r"^As an AI(?: assistant)?[^.!]*[.!]\s*",
    ]
    for _pat in _intro_patterns:
        final_answer = _re.sub(_pat, "", final_answer, flags=_re.IGNORECASE).lstrip()

    # Strip emojis — local models often add them despite instructions
    import unicodedata as _ud
    def _strip_emojis(text: str) -> str:
        return "".join(
            ch for ch in text
            if not (_ud.category(ch) in ("So", "Sm") or
                    0x1F300 <= ord(ch) <= 0x1FAFF or
                    0x2600 <= ord(ch) <= 0x27BF or
                    0xFE00 <= ord(ch) <= 0xFE0F or
                    0x1F1E0 <= ord(ch) <= 0x1F1FF)
        ).strip()
    final_answer = _strip_emojis(final_answer)

    def _collapse_repetitive_answer(text: str) -> str:
        value = str(text or "").strip()
        if not value:
            return value
        sentences = [s.strip() for s in _re.split(r"(?<=[.!?])\s+", value) if s.strip()]
        if len(sentences) < 4:
            return value
        normalized = [_re.sub(r"\s+", " ", s).strip().lower() for s in sentences]
        first = normalized[0]
        repeated_prefix = 1
        for item in normalized[1:]:
            if item != first:
                break
            repeated_prefix += 1
        if repeated_prefix >= 4:
            return sentences[0]
        for pattern_len in (2, 3):
            if len(normalized) < pattern_len * 3:
                continue
            pattern = normalized[:pattern_len]
            if all(normalized[idx] == pattern[idx % pattern_len] for idx in range(len(normalized))):
                return " ".join(sentences[:pattern_len])
        if len(set(normalized)) == 1 and len(normalized) >= 3:
            return sentences[0]
        return value

    final_answer = _collapse_repetitive_answer(final_answer)

    def _blocked_answer(reason: str, existing_answer: str) -> str:
        answer_text = str(existing_answer or "").strip()
        lower_answer = answer_text.lower()
        gate_debug = result.get("gate_debug") or {}
        slot_label = str(gate_debug.get("slot") or "").strip(" ?")
        meta_provenance = _is_meta_provenance_followup(effective_message)
        suspicious_markers = (
            "corrections from stored memory",
            "revise your answer",
            "original question:",
            "your draft answer:",
        )
        uncertainty_markers = (
            "conflicting information",
            "conflicting memories",
            "which is correct",
            "can't answer confidently",
            "i'm not confident",
            "i found a conflict",
        )
        suspicious = any(marker in lower_answer for marker in suspicious_markers)
        already_safe = any(marker in lower_answer for marker in uncertainty_markers)

        if "contradiction" in reason or "disclosure" in reason or "unresolved" in reason or "hard_conflict" in reason:
            if answer_text and already_safe and not suspicious:
                return answer_text
            if slot_label:
                return f"I have conflicting information about your {slot_label} and can't answer confidently yet. Which version is correct right now?"
            return "I have conflicting information about this and can't answer confidently yet. Which version is correct right now?"
        if "system_prompt" in reason:
            return (
                "I can't share my hidden instructions verbatim. "
                "If you tell me what you're trying to do, I can summarize the behavior instead."
            )
        if meta_provenance and ("explanatory_memory_fail" in reason or "degraded_output" in reason):
            return (
                "I remember this by storing your confirmed facts in memory and retrieving them when they're relevant. "
                "Facts about you come from what you've told me, while my assistant identity comes from my configured system role. "
                "If those records conflict, I disclose the conflict instead of silently picking a winner."
            )
        if "uncertainty" in reason or "grounding_fail" in reason:
            if answer_text and not suspicious:
                return answer_text
            return "I'm not confident enough in my answer to share it. Could you give me more context?"
        if answer_text and not suspicious:
            return answer_text
        return "I wasn't able to generate a reliable response to that. Try rephrasing, or ask me to explain why."

    if not bool(result.get("gates_passed", True)):
        final_answer = _blocked_answer(str(result.get("gate_reason") or ""), final_answer)

    tasking_meta = None
    if tasking_enabled and bool(result.get("gates_passed", True)):
        allow_tasking = True
        if _TASKING_INTERVAL_SECONDS > 0:
            now_ts = time.time()
            tid = sanitize_thread_id(req.thread_id)
            with _TASKING_LOCK:
                last_ts = _TASKING_LAST_RUN.get(tid, 0.0)
                if now_ts - last_ts < _TASKING_INTERVAL_SECONDS:
                    allow_tasking = False
                else:
                    _TASKING_LAST_RUN[tid] = now_ts

        if not allow_tasking:
            tasking_meta = {
                "mode": "plan+coverage",
                "skipped": "interval",
                "interval_seconds": _TASKING_INTERVAL_SECONDS,
            }
        else:
            try:
                from personal_agent.tasking_loop import TaskingLoop

                tasking_loop = TaskingLoop(llm_client=llm_client)
                tasking_result = tasking_loop.run(effective_message, final_answer, allow_expansion=True)
                final_answer = tasking_result.final_answer
                tasking_meta = tasking_result.to_dict()
                tasking_meta["interval_seconds"] = _TASKING_INTERVAL_SECONDS
            except Exception as e:
                logger.debug(f"[TASKING] Tasking loop failed: {e}")
    _mark("tasking_done")
    if tasking_enabled:
        control_state.mark("validate", "tasking_checked", detail=str((tasking_meta or {}).get("mode") or "tasking"))

    # Caveat injection is now handled by the LLM via extra_context in crt_rag.py.
    # Blindly appending "(most recent update)" was too broad -- it fired on greetings,
    # meta-questions, and answers unrelated to the conflicted slot.
    caveat_injected = False
    if reintro_count > 0:
        logger.info(
            "[CAVEAT_NOTE] reintro_count=%d -- contradiction awareness handled by LLM via extra_context",
            reintro_count,
        )

    metadata: Dict[str, Any] = {
        "mode": result.get("mode"),
        "confidence": result.get("confidence"),
        "channel": req.channel,
        "actor_id": req.actor_id,
        "channel_destination_id": req.channel_destination_id,
        "meta_scope": req.meta_scope,
        "intent_alignment": result.get("intent_alignment"),
        "memory_alignment": result.get("memory_alignment"),
        "thinking": thinking_content or None,
        "thinking_trace_id": thinking_trace_id,
        "reflection_trace_id": reflection_trace_id,
        "reflection_confidence": reflection_result.confidence_score if reflection_result else None,
        "reflection_label": reflection_result.confidence_label if reflection_result else None,
        "style_profile": style_profile,
        "personality_profile": personality_profile,
        "reflection_scorecard": reflection_scorecard,
        "contradiction_detected": result.get("contradiction_detected"),
        "contradiction_resolved": result.get("contradiction_resolved"),
        "unresolved_contradictions_total": result.get("unresolved_contradictions_total"),
        "unresolved_hard_conflicts": result.get("unresolved_hard_conflicts"),
        "learned_suggestions": result.get("learned_suggestions") or [],
        "heuristic_suggestions": result.get("heuristic_suggestions") or [],
        "profile_updates": result.get("profile_updates") or [],
        "agent_activated": agent_activated,
        "agent_answer": agent_answer,
        "agent_trace": agent_trace_data,
        "retrieved_memories": retrieved_mems,
        "prompt_memories": prompt_mems,
        "reintroduced_claims_count": reintro_count,
        "caveat_injected_for_reintroduced_claims": caveat_injected,
        "expanded": expanded,
        "expansion_reason": expansion_reason,
        "tasking": tasking_meta,
        "critic": critic_meta,
        "model_route": model_route,
        "model_override": model_override,
        "product_mode": ((runtime_config.get("product_mode") or {}).get("mode") if isinstance(runtime_config, dict) else None),
        "generation_provider": (model_route or {}).get("provider") if isinstance(model_route, dict) else None,
        "groundcheck_bridge": groundcheck_bridge_meta,
        "gate_debug": result.get("gate_debug") or None,
    }

    collapse_trail_id = _log_collapse_trail(
        thread_id=req.thread_id,
        query=req.message,
        answer=final_answer,
        result=result,
        stage="chat_send",
        mode=str(req.mode) if req.mode else None,
        extra={
            "expanded": expanded,
            "tasking_enabled": tasking_enabled,
            "agent_activated": agent_activated,
        },
    )
    if collapse_trail_id:
        metadata["collapse_trail_id"] = collapse_trail_id

    # Build X-Ray data (memory transparency mode)
    xray_data = None
    try:
        if retrieved_mems:
            xray_data = {
                "memories_used": [
                    {
                        "text": (m.get("text") if isinstance(m, dict) else "")[:100],
                        "trust": m.get("trust") if isinstance(m, dict) else 0,
                        "confidence": m.get("confidence") if isinstance(m, dict) else 0,
                        "timestamp": m.get("timestamp") if isinstance(m, dict) else None,
                        "reintroduced_claim": m.get("reintroduced_claim") if isinstance(m, dict) else False,
                    }
                    for m in retrieved_mems[:5]
                    if isinstance(m, dict)
                ],
                "conflicts_detected": [],
                "reintroduced_claims_count": reintro_count,
            }

            try:
                open_contras = engine.ledger.get_open_contradictions(limit=10)
                for c in open_contras:
                    xray_data["conflicts_detected"].append(
                        {
                            "old": (c.claim_a_text or "")[:100],
                            "new": (c.claim_b_text or "")[:100],
                            "status": c.status.value if hasattr(c.status, "value") else str(c.status),
                        }
                    )
            except Exception:
                pass
    except Exception:
        pass

    # PHASE 1: Active learning, session record, episodic — all fired async.
    # These don't affect the answer; no reason to block the response on them.
    interaction_id = None
    _mark("active_learning_done")
    _mark("session_record_done")
    _mark("episodic_done")

    def _run_post_response_bookkeeping(
        _thread_id, _message, _final_answer, _result, _prompt_mems, _session_db, _engine_memory
    ):
        # Active learning
        try:
            coordinator = get_active_learning_coordinator()
            slots_inferred = _result.get("slots_extracted") or _result.get("facts") or {}
            facts_injected = [
                {"memory_id": m.get("memory_id"), "text": m.get("text"), "confidence": m.get("confidence")}
                for m in _prompt_mems
                if isinstance(m, dict) and m.get("memory_id")
            ]
            coordinator.record_interaction(
                thread_id=_thread_id,
                query=_message,
                response=_final_answer,
                response_type=str(_result.get("response_type") or "speech"),
                confidence=float(_result.get("confidence") or 0.0),
                gates_passed=bool(_result.get("gates_passed")),
                slots_inferred=slots_inferred if isinstance(slots_inferred, dict) else None,
                facts_injected=facts_injected if facts_injected else None,
                session_id=str(_result.get("session_id") or "default"),
            )
        except Exception as _e:
            logging.warning(f"[Phase1_BG] Failed to log interaction: {_e}")

        # Session record
        try:
            detected_slot = None
            slots = _result.get("slots_extracted")
            if isinstance(slots, dict) and slots:
                detected_slot = list(slots.keys())[0]
            _session_db.record_query(
                thread_id=_thread_id,
                query_text=_message,
                response_text=_final_answer,
                detected_slot=detected_slot,
            )
        except Exception as _e:
            logger.debug(f"[SESSION_BG] Error recording query: {_e}")

        # Episodic memory
        try:
            episodic_mgr = get_episodic_manager(memory_system=_engine_memory)
            episodic_mgr.process_interaction(
                thread_id=_thread_id,
                query=_message,
                response=_final_answer,
                response_time_ms=0,
            )
        except Exception as _e:
            logger.debug(f"[EPISODIC_BG] Error processing interaction: {_e}")

    threading.Thread(
        target=_run_post_response_bookkeeping,
        args=(req.thread_id, req.message, final_answer, result, prompt_mems, session_db, engine.memory),
        daemon=True,
    ).start()

    if greeting_text:
        metadata["greeting_shown"] = True
    if query_with_continuity != query_with_context:
        metadata["continuity_context_applied"] = True

    # ====== Auto Fact-Check: verify response against memories (background) ======
    try:
        from personal_agent.auto_fact_checker import schedule_fact_check
        schedule_fact_check(
            thread_id=req.thread_id,
            query=req.message,
            response=final_answer,
            memories=retrieved_mems if retrieved_mems else [],
        )
    except Exception as e:
        logger.debug(f"[AUTO_FC] Error scheduling fact check: {e}")
    _mark("fact_check_schedule_done")
    control_state.mark(
        "decide",
        "ready",
        detail=str(result.get("gate_reason") or ""),
        gates_passed=bool(result.get("gates_passed")),
    )
    control_state.mark(
        "learn",
        "recorded",
        detail="interaction+session+episodic+fact_check",
        interaction_id=interaction_id,
    )

    timing_rows = _timings()
    if timing_rows:
        metadata["pipeline_timings_ms"] = timing_rows
        metadata.setdefault(
            "pipeline_statuses",
            [f"{str(row.get('stage'))}:{float(row.get('dt_ms') or 0.0):.1f}ms" for row in timing_rows],
        )
        total_ms = float(timing_rows[-1].get("t_ms") or 0.0)
        logger.info(
            "[CHAT_TIMING] thread=%s total_ms=%.1f gate=%s mode=%s stages=%s",
            req.thread_id,
            total_ms,
            str(result.get("gate_reason") or ""),
            str(result.get("mode") or ""),
            " | ".join(f"{row.get('stage')}:{row.get('dt_ms')}ms" for row in timing_rows),
        )

    return _chat_response(
        answer=final_answer,
        response_type=str(result.get("response_type") or "speech"),
        gates_passed=bool(result.get("gates_passed")),
        gate_reason=(result.get("gate_reason") if isinstance(result.get("gate_reason"), str) else None),
        metadata=metadata,
        xray=xray_data,
    )


def _run_shared_chat_pipeline(req: ChatSendRequest, request: Request) -> ChatSendResponse:
    """Single response pipeline used by both /send and /stream."""
    return chat_send(req, request)


# ============================================================================
# POST /api/chat/stream
# ============================================================================


@router.post("/stream")
def chat_stream(req: ChatSendRequest, request: Request):
    """Stream using the same shared pipeline as /send to prevent drift."""
    logger.info(f"[STREAM] /api/chat/stream called with message: {req.message[:50]}...")

    def generate_stream():
        import threading, queue as _queue, time as _time

        def _status(s: str) -> str:
            return f"data: {json.dumps({'type': 'status', 'content': s})}\n\n"

        def _phase(phase: str, content: str = '', end: bool = False) -> str:
            t = 'phase_end' if end else 'phase_start'
            return f"data: {json.dumps({'type': t, 'phase': phase, 'content': content})}\n\n"

        try:
            # ── Upfront activity signals ──────────────────────────────────
            q_lower = req.message.lower()
            yield _phase('analyze', 'Reading request')
            yield _status('reading context')
            yield _phase('analyze', end=True)

            yield _phase('plan', 'Retrieving memory')
            yield _status('searching memory')

            # Hint at what type of processing will happen
            if any(w in q_lower for w in ('contradict', 'conflict', 'remember', 'told you', 'said')):
                yield _status('checking contradictions')
            elif any(w in q_lower for w in ('code', 'python', 'function', 'script', 'write', 'build')):
                yield _status('accessing tools')
            elif any(w in q_lower for w in ('research', 'search', 'find', 'look up')):
                yield _status('running agent')
            else:
                yield _status('analyzing query')

            # ── Run pipeline in background, emit heartbeats while waiting ─
            result_q: _queue.Queue = _queue.Queue()
            err_q: _queue.Queue = _queue.Queue()

            def _run():
                try:
                    result_q.put(_run_shared_chat_pipeline(req, request))
                except Exception as exc:
                    err_q.put(exc)

            t = threading.Thread(target=_run, daemon=True)
            t.start()

            _heartbeats = ['reasoning', 'planning response', 'verifying', 'drafting']
            _hb_idx = 0
            _last_hb = _time.monotonic()
            _hb_max = len(_heartbeats) * 2  # cap at 2 full cycles
            while t.is_alive():
                _time.sleep(0.05)
                if _time.monotonic() - _last_hb > 1.4 and _hb_idx < _hb_max:
                    yield _status(_heartbeats[_hb_idx % len(_heartbeats)])
                    _hb_idx += 1
                    _last_hb = _time.monotonic()

            t.join()

            if not err_q.empty():
                raise err_q.get()

            shared_response = result_q.get()
            yield _phase('plan', end=True)

            # ── Post-pipeline status insights ─────────────────────────────
            metadata: Dict[str, Any] = dict(shared_response.metadata or {})
            metadata.setdefault("response_type", shared_response.response_type)
            metadata.setdefault("gates_passed", shared_response.gates_passed)
            metadata.setdefault("gate_reason", shared_response.gate_reason)
            metadata.setdefault("session_id", shared_response.session_id)

            _gates_passed = shared_response.gates_passed
            _response_type = shared_response.response_type or "speech"
            _gate_reason = shared_response.gate_reason or ""
            _retrieved = metadata.get("retrieved_memories") or []
            _prompt_mems = metadata.get("prompt_memories") or []
            _mem_count = len(_retrieved) + len(_prompt_mems)

            if _mem_count > 0:
                yield _status(f'{_mem_count} memories read')
            if metadata.get("contradiction_detected"):
                _open = metadata.get("unresolved_contradictions_total", 0)
                yield _status(f'contradiction detected ({_open} open)')
            if metadata.get("agent_activated"):
                yield _status('agent activated')
            if not _gates_passed:
                yield _status(f'gate: {_gate_reason or "blocked"}')
            if _response_type not in ("speech", ""):
                yield _status(_response_type)

            # ── Thinking content ──────────────────────────────────────────
            thinking_content = _strip_thinking_tags(str(metadata.get("thinking") or "")).strip()
            if thinking_content:
                yield f"data: {json.dumps({'type': 'thinking_start', 'content': ''})}\n\n"
                for thought_chunk in _chunk_text(thinking_content, chunk_size=280):
                    yield f"data: {json.dumps({'type': 'thinking_token', 'content': thought_chunk})}\n\n"
                yield f"data: {json.dumps({'type': 'thinking_end', 'content': ''})}\n\n"

            # ── Stream answer tokens ──────────────────────────────────────
            answer = str(shared_response.answer or "")
            yield _phase('answer', 'Writing response')
            for text_chunk in _chunk_text(answer):
                yield f"data: {json.dumps({'type': 'token', 'content': text_chunk})}\n\n"
            yield _phase('answer', end=True)

            yield f"data: {json.dumps({'type': 'done', 'content': answer, 'metadata': metadata})}\n\n"

        except Exception as e:
            logger.error(f"[STREAM] Stream error: {e}", exc_info=True)
            yield f"data: {json.dumps({'type': 'error', 'content': str(e)})}\n\n"

    return StreamingResponse(
        generate_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


# ============================================================================
# POST /api/chat/intent
# ============================================================================


@router.post("/intent", response_model=IntentQueryResponse)
def chat_intent(req: IntentQueryRequest, request: Request) -> IntentQueryResponse:
    """Query with IntentRouter + FactStore routing.

    Uses IntentRouter + FactStore for smarter routing,
    with optional trace for debugging/transparency.
    """
    get_engine = request.app.state.get_engine
    increment_turn = request.app.state.increment_turn
    _log_collapse_trail = request.app.state.log_collapse_trail

    engine = get_engine(req.thread_id)
    increment_turn(req.thread_id)
    groundcheck_bridge_meta: Optional[Dict[str, Any]] = None
    try:
        groundcheck_bridge_meta = _maybe_sync_groundcheck_bridge(
            thread_id=req.thread_id,
            engine=engine,
        )
    except Exception as e:
        logger.debug(f"[MEMORY_BRIDGE] Intent sync failed: {e}")
        groundcheck_bridge_meta = {"enabled": True, "attempted": True, "ok": False, "error": str(e)}

    # Enable tracing if requested
    if hasattr(engine, "enable_tracing"):
        engine.enable_tracing(req.include_trace)

    # Use intent query if available
    if hasattr(engine, "query_with_intent"):
        result = engine.query_with_intent(
            user_query=req.message,
            user_marked_important=req.user_marked_important,
            thread_id=req.thread_id,
            channel=req.channel,
            origin=req.origin,
            authority=req.authority,
            kind=req.kind,
        )
    else:
        session_db = get_thread_session_db()
        history_messages = _load_recent_history_messages(session_db, req.thread_id, window=6)
        query_with_continuity = _augment_query_with_continuity(
            message=req.message,
            history_messages=history_messages,
        )
        preference_profile = _get_preference_profile(req.thread_id, engine.memory)
        model_override, model_route = _route_model_for_request(
            request,
            query=req.message,
            mode=None,
            preference_profile=preference_profile,
            channel=None,
        )
        result = engine.query(
            user_query=query_with_continuity,
            user_marked_important=req.user_marked_important,
            model_override=model_override,
            conversation_history=history_messages or None,
            channel=req.channel,
            origin=req.origin,
            authority=req.authority,
            kind=req.kind,
        )
        result["intent"] = "unknown"
        result["trace"] = None
        result["model_route"] = model_route

    metadata: Dict[str, Any] = {
        "mode": result.get("mode"),
        "contradiction_detected": result.get("contradiction_detected"),
        "retrieved_memories": len(result.get("retrieved_memories") or []),
        "structured_facts": result.get("structured_facts"),
        "fact_store_hit": result.get("fact_store_hit", False),
        "model_route": result.get("model_route"),
        "groundcheck_bridge": groundcheck_bridge_meta,
    }
    collapse_trail_id = _log_collapse_trail(
        thread_id=req.thread_id,
        query=req.message,
        answer=str(result.get("answer") or ""),
        result=result,
        stage="chat_intent",
        mode="intent",
    )
    if collapse_trail_id:
        metadata["collapse_trail_id"] = collapse_trail_id

    return IntentQueryResponse(
        answer=result.get("answer", ""),
        intent=result.get("intent", "unknown"),
        confidence=result.get("confidence", 0.0),
        response_type=result.get("response_type", "speech"),
        gates_passed=result.get("gates_passed", False),
        gate_reason=result.get("gate_reason"),
        trace=result.get("trace") if req.include_trace else None,
        metadata=metadata,
    )
