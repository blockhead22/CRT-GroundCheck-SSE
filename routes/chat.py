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
import threading
import time
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

from personal_agent.ollama_client import OllamaClient
from personal_agent.runtime_config import get_runtime_config
from personal_agent.db_utils import get_thread_session_db
from personal_agent.greeting_system import get_time_based_greeting
from personal_agent.active_learning import get_active_learning_coordinator
from personal_agent.episodic_memory import get_episodic_manager
from personal_agent.reflection_system import run_reflection_pass, ReflectionResult
from personal_agent.scheduled_tasks import schedule_reminder, extract_reminder_from_message

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
    "the highlights",
    "highlights",
    "summarize",
    "summary",
)

_GROUNDCHECK_BRIDGE_LOCK = threading.Lock()
_GROUNDCHECK_BRIDGE_LAST_SYNC: Dict[str, float] = {}


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
            narrative_limit = int(os.getenv("CRT_GROUNDCHECK_BRIDGE_NARRATIVE_LIMIT", "30") or 30)
        except Exception:
            narrative_limit = 30

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
) -> Tuple[Optional[str], Optional[Dict[str, str]]]:
    """Select a model for this request using app-level model router."""
    router_obj = getattr(request.app.state, "model_router", None)
    if router_obj is None:
        return None, None
    try:
        routed = router_obj.route(
            query=query,
            requested_mode=mode,
            preference_profile=preference_profile,
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
    if len(response) < 360 and len(question or "") > 80:
        return True, "short_answer"
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
    llm_client: OllamaClient,
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
    return expansion


def _chunk_text(text: str, chunk_size: int = 320) -> List[str]:
    if not text:
        return []
    return [text[i : i + chunk_size] for i in range(0, len(text), chunk_size)]


# ---------------------------------------------------------------------------
# Closure-scoped helpers (originally inside create_app) -- copied here
# ---------------------------------------------------------------------------


def _is_architecture_explanation_request(text: str) -> bool:
    t = (text or "").strip().lower()
    if not t:
        return False
    if len(t) > 1000:
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

    # Session tracking: update activity and check for greeting
    session_db = get_thread_session_db()
    session = session_db.get_or_create_session(req.thread_id)

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

    groundcheck_bridge_meta: Optional[Dict[str, Any]] = None
    try:
        groundcheck_bridge_meta = _maybe_sync_groundcheck_bridge(
            thread_id=req.thread_id,
            engine=engine,
        )
    except Exception as e:
        logger.debug(f"[MEMORY_BRIDGE] Unexpected sync error: {e}")
        groundcheck_bridge_meta = {"enabled": True, "attempted": True, "ok": False, "error": str(e)}

    # Deterministic ledger-backed contradiction inventory.
    if _is_contradiction_inventory_request(req.message):
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

        return ChatSendResponse(
            answer=answer,
            response_type="explanation",
            gates_passed=False,
            gate_reason="ledger_contradictions",
            session_id=getattr(engine, "session_id", None),
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
    if _is_architecture_explanation_request(req.message):
        doc_map = request.app.state.doc_map
        answer, prompt_items = _answer_from_docs(req.message, doc_map)
        return ChatSendResponse(
            answer=answer,
            response_type="explanation",
            gates_passed=True,
            gate_reason="docs_explanation",
            session_id=getattr(engine, "session_id", None),
            metadata={
                "confidence": 0.85,
                "retrieved_memories": [],
                "prompt_memories": prompt_items,
            },
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

    query_with_context = req.message
    if fact_check_preamble:
        query_with_context = req.message + fact_check_preamble

    recent_history = _load_recent_history_messages(session_db, req.thread_id, window=6)
    query_with_continuity = _augment_query_with_continuity(
        message=query_with_context,
        history_messages=recent_history,
    )

    preference_profile = _get_preference_profile(req.thread_id, engine.memory)
    model_override, model_route = _route_model_for_request(
        request,
        query=req.message,
        mode=req.mode,
        preference_profile=preference_profile,
    )

    result = engine.query(
        user_query=query_with_continuity,
        user_marked_important=req.user_marked_important,
        mode=mode_arg,
        thread_id=req.thread_id,
        model_override=model_override,
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
                query=req.message,
                draft_answer=_draft,
                retrieved_memories=_retrieved,
                llm_client=get_llm_client(),
            )
            critic_meta = _critic_result.to_dict()
            # Replace answer with critic's output (may be revised or disclosure)
            result["answer"] = _critic_result.final_answer
            if _critic_result.was_revised:
                logger.info(f"[CRT-CRITIC] Answer revised (verdict={_critic_result.verdict.value})")
            if _critic_result.verdict == VerifyVerdict.HARD_FAIL:
                # Override gates to signal contradiction disclosure
                result["gates_passed"] = False
                result["gate_reason"] = "contradiction_disclosure"
                logger.info("[CRT-CRITIC] Hard fail — surfacing contradiction to user")
    except ImportError:
        logger.debug("[CRT-CRITIC] crt_critic not available")
    except Exception as e:
        logger.warning(f"[CRT-CRITIC] Verification error (non-fatal): {e}")

    # Capture thinking trace (if available) for non-stream responses.
    llm_client = get_llm_client()
    thinking_content = _strip_thinking_tags(str(result.get("thinking") or ""))
    thinking_trace_id = None
    if thinking_content and len(thinking_content) > 50:
        try:
            thinking_trace_id = engine.memory.store_reasoning_trace(
                query=req.message,
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

                task = triggers_engine.get_agent_task(detected_triggers, req.message)
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

    base_answer = str(result.get("answer") or "")

    # ========================================
    # DIRECTED REFLECTION PASS (non-stream)
    # ========================================
    reflection_trace_id = None
    reflection_result = None
    if llm_client is not None:
        try:
            grounding_facts = [
                m.get("text", "")[:300]
                for m in (result.get("retrieved_memories") or [])
                if isinstance(m, dict) and m.get("text")
            ][:5]
            reflection_result, _requery_response, _requery_thinking = run_reflection_pass(
                question=req.message,
                response=base_answer,
                thinking=thinking_content,
                thread_id=req.thread_id,
                db_path=engine.memory.db_path,
                facts=grounding_facts,
                auto_requery=False,
                collect_training_data=True,
            )
            reflection_trace_id = reflection_result.trace_id
        except Exception as e:
            logger.debug(f"[REFLECTION] Reflection failed (non-stream): {e}")

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
        req.message,
        base_answer,
        reflection_result,
        verbosity_pref,
    )
    if should_expand:
        expansion_text = _generate_expansion(
            llm_client,
            req.message,
            base_answer,
            known_facts_text,
            style_profile,
            reflection_result,
            personality_profile,
        )
        if expansion_text:
            expanded = True
            base_answer = base_answer.rstrip()
            base_answer = f"{base_answer}\n\nMore detail:\n{expansion_text}"
        else:
            expansion_reason = None

    final_answer = base_answer
    if greeting_text:
        final_answer = f"{greeting_text}\n\n{final_answer}"

    tasking_meta = None
    if tasking_enabled:
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
                tasking_result = tasking_loop.run(req.message, final_answer, allow_expansion=True)
                final_answer = tasking_result.final_answer
                tasking_meta = tasking_result.to_dict()
                tasking_meta["interval_seconds"] = _TASKING_INTERVAL_SECONDS
            except Exception as e:
                logger.debug(f"[TASKING] Tasking loop failed: {e}")

    metadata: Dict[str, Any] = {
        "mode": result.get("mode"),
        "confidence": result.get("confidence"),
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
        "expanded": expanded,
        "expansion_reason": expansion_reason,
        "tasking": tasking_meta,
        "critic": critic_meta,
        "model_route": model_route,
        "model_override": model_override,
        "groundcheck_bridge": groundcheck_bridge_meta,
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

    # PHASE 1: Log complete interaction for active learning
    interaction_id = None
    try:
        coordinator = get_active_learning_coordinator()

        slots_inferred = result.get("slots_extracted") or result.get("facts") or {}

        facts_injected = [
            {
                "memory_id": m.get("memory_id"),
                "text": m.get("text"),
                "confidence": m.get("confidence"),
            }
            for m in prompt_mems
            if isinstance(m, dict) and m.get("memory_id")
        ]

        interaction_id = coordinator.record_interaction(
            thread_id=req.thread_id,
            query=req.message,
            response=final_answer,
            response_type=str(result.get("response_type") or "speech"),
            confidence=float(result.get("confidence") or 0.0),
            gates_passed=bool(result.get("gates_passed")),
            slots_inferred=slots_inferred if isinstance(slots_inferred, dict) else None,
            facts_injected=facts_injected if facts_injected else None,
            session_id=str(result.get("session_id") or "default"),
        )
    except Exception as e:
        logging.warning(f"[Phase1] Failed to log interaction: {e}")

    if interaction_id:
        metadata["interaction_id"] = interaction_id

    if greeting_text:
        metadata["greeting_shown"] = True
    if query_with_continuity != query_with_context:
        metadata["continuity_context_applied"] = True

    # Record query in session DB for response variation tracking
    try:
        detected_slot = None
        if result.get("slots_extracted"):
            slots = result.get("slots_extracted")
            if isinstance(slots, dict) and slots:
                detected_slot = list(slots.keys())[0]

        session_db.record_query(
            thread_id=req.thread_id,
            query_text=req.message,
            response_text=final_answer,
            detected_slot=detected_slot,
        )
    except Exception as e:
        logger.debug(f"[SESSION] Error recording query: {e}")

    # ====== Episodic Memory: Process interaction for patterns/preferences ======
    try:
        episodic_mgr = get_episodic_manager(memory_system=engine.memory)
        start_time = time.time()
        episodic_mgr.process_interaction(
            thread_id=req.thread_id,
            query=req.message,
            response=final_answer,
            response_time_ms=int((time.time() - start_time) * 1000),
        )
    except Exception as e:
        logger.debug(f"[EPISODIC] Error processing interaction: {e}")

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

    return ChatSendResponse(
        answer=final_answer,
        response_type=str(result.get("response_type") or "speech"),
        gates_passed=bool(result.get("gates_passed")),
        gate_reason=(result.get("gate_reason") if isinstance(result.get("gate_reason"), str) else None),
        session_id=(result.get("session_id") if isinstance(result.get("session_id"), str) else None),
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
        try:
            phase_enabled = bool(req.phase_mode)
            if phase_enabled:
                yield f"data: {json.dumps({'type': 'phase_start', 'phase': 'analyze', 'content': 'Analyzing request'})}\n\n"
                yield f"data: {json.dumps({'type': 'phase_end', 'phase': 'analyze', 'content': ''})}\n\n"
                yield f"data: {json.dumps({'type': 'phase_start', 'phase': 'plan', 'content': 'Planning response'})}\n\n"
                yield f"data: {json.dumps({'type': 'phase_end', 'phase': 'plan', 'content': ''})}\n\n"

            yield f"data: {json.dumps({'type': 'status', 'content': 'Processing message...'})}\n\n"

            shared_response = _run_shared_chat_pipeline(req, request)
            metadata: Dict[str, Any] = dict(shared_response.metadata or {})
            metadata.setdefault("response_type", shared_response.response_type)
            metadata.setdefault("gates_passed", shared_response.gates_passed)
            metadata.setdefault("gate_reason", shared_response.gate_reason)
            metadata.setdefault("session_id", shared_response.session_id)

            thinking_content = _strip_thinking_tags(str(metadata.get("thinking") or "")).strip()
            if thinking_content:
                yield f"data: {json.dumps({'type': 'thinking_start', 'content': ''})}\n\n"
                for thought_chunk in _chunk_text(thinking_content, chunk_size=280):
                    yield f"data: {json.dumps({'type': 'thinking_token', 'content': thought_chunk})}\n\n"
                yield f"data: {json.dumps({'type': 'thinking_end', 'content': ''})}\n\n"

            answer = str(shared_response.answer or "")
            if phase_enabled:
                yield f"data: {json.dumps({'type': 'phase_start', 'phase': 'answer', 'content': 'Drafting response'})}\n\n"
            for text_chunk in _chunk_text(answer):
                yield f"data: {json.dumps({'type': 'token', 'content': text_chunk})}\n\n"
            if phase_enabled:
                yield f"data: {json.dumps({'type': 'phase_end', 'phase': 'answer', 'content': ''})}\n\n"

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
        )
        result = engine.query(
            user_query=query_with_continuity,
            user_marked_important=req.user_marked_important,
            model_override=model_override,
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
