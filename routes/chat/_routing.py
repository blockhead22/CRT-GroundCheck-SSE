"""Routing helpers extracted from routes/chat.py."""

from __future__ import annotations

import logging
import re as _re_mod
from typing import Any, Dict, Optional, Tuple

from fastapi import Request

logger = logging.getLogger(__name__)


def _safe_print(msg: str) -> None:
    """Print to console, replacing unencodable characters (Windows cp1252 fix)."""
    try:
        print(msg)
    except UnicodeEncodeError:
        print(msg.encode("ascii", errors="replace").decode("ascii"))


# ── Capability-aware re-route (Sprint 12) ──────────────────────────────
# Patterns that should route to tools but the classifier missed.
# These are checked ONLY when the classifier said "conversational".

_CAPABILITY_REROUTE_PATTERNS = [
    # System info queries
    (
        _re_mod.compile(
            r"(?:what(?:'s| is| are)?\s+(?:\w+\s+)*(?:apps?|programs?|processes?|windows?)\s+(?:are\s+)?(?:\w+\s+)?(?:open|running|active))"
            r"|(?:which\s+(?:apps?|programs?|windows?)\s+(?:are\s+)?(?:\w+\s+)?(?:open|running|active))"
            r"|(?:(?:show|list|check)\s+(?:me\s+)?(?:what\s+)?(?:processes?|apps?|programs?)\s+(?:are\s+)?(?:\w+\s+)?(?:running|open|active))"
            r"|(?:(?:show|list|check)\s+(?:me\s+)?(?:the\s+)?(?:running|active|open)\s+(?:processes?|apps?|programs?))"
            r"|(?:(?:apps?|programs?|windows?)\s+(?:are\s+)?(?:\w+\s+)?(?:open|running|active)\??)"
            r"|(?:how(?:'s| is)?\s+my\s+(?:system|computer|pc|machine|cpu|ram|gpu|memory|disk))"
            r"|(?:(?:check|show|what(?:'s)?)\s+(?:my\s+)?(?:system|cpu|ram|gpu|memory|disk)\s*(?:status|usage|info)?)"
            r"|(?:top\s+processes|task\s+manager|resource\s+monitor)"
            r"|(?:(?:anything|something|what(?:'s)?)\s+(?:\w+\s+)?(?:unusual|wrong|off|weird|strange)\s+(?:\w+\s+)?(?:my\s+)?(?:system|computer|pc|machine))"
            r"|(?:(?:is|are)\s+(?:my\s+)?(?:system|computer|pc|machine)\s+(?:\w+\s+)?(?:ok|fine|healthy|normal|overloaded|slow))"
            r"|(?:(?:my\s+)?(?:system|computer|pc)\s+(?:status|health|performance|diagnostics))",
            _re_mod.IGNORECASE,
        ),
        "system_info",
        {},
    ),
    # Desktop action queries that look like questions
    (
        _re_mod.compile(
            r"\b(?:can you\s+)?(?:take|grab|capture)\s+(?:a\s+)?screenshot",
            _re_mod.IGNORECASE,
        ),
        "desktop_action",
        lambda msg: {"task_description": msg},
    ),
    # Debugging / inspection / auditing queries that should enter agent loop
    (
        _re_mod.compile(
            r"\b(?:check|inspect|debug|audit|verify|test|examine|look at|review)"
            r"\s+(?:your\s+|the\s+|my\s+)?"
            r"(?:self[- ]?model|auditor|memory|memories|contradiction|ledger|trust|"
            r"governance|pipeline|heartbeat|belief|system|logs?|config|status|state)\b"
            r"|(?:what(?:'s| is| has)?\s+(?:changed|different|new|updated|broken|wrong))"
            r"|(?:run\s+(?:the\s+)?(?:audit|check|test|diagnostic))"
            r"|(?:show\s+(?:me\s+)?(?:the\s+)?(?:audit|self[- ]?model|contradiction|trust)\s+(?:results?|data|log|state))",
            _re_mod.IGNORECASE,
        ),
        "system_info",
        {},
    ),
]


# Additional patterns for multi-intent compound detection
_COMPOUND_INTENT_PATTERNS = [
    # ── Git ──
    (_re_mod.compile(r"\bgit\s+(status|diff|log|branch|commit|push|pull|stash)", _re_mod.IGNORECASE), "git_action"),
    (_re_mod.compile(r"\b(?:uncommitted|modified|staged)\s+(?:git\s+)?(?:changes?|files?)", _re_mod.IGNORECASE), "git_action"),
    (_re_mod.compile(r"\bgit\s+(?:changes?|uncommitted|modified|staged)", _re_mod.IGNORECASE), "git_action"),
    # ── Directory listing ──
    (_re_mod.compile(r"\b(?:list|show|check)\s+(?:the\s+)?(?:files?|directory|folder|dir)\b", _re_mod.IGNORECASE), "dir_list"),
    # ── File read (including [file:...] tags and named files) ──
    (_re_mod.compile(r"\b(?:read|open|show\s+me)\s+(?:the\s+)?(?:file|contents?\s+of)\b", _re_mod.IGNORECASE), "file_read"),
    (_re_mod.compile(r"\[file:\s*\S+\]", _re_mod.IGNORECASE), "file_read"),
    (_re_mod.compile(r"\b(?:read|open|show|cat)\s+\S+\.(?:md|py|txt|json|yaml|yml|toml|cfg|ini|log|csv|ts|tsx|js|jsx)\b", _re_mod.IGNORECASE), "file_read"),
    (_re_mod.compile(r"\b(?:summarize|explain|describe|tell\s+me\s+about)\s+\S+\.(?:md|py|txt|json)\b", _re_mod.IGNORECASE), "file_read"),
    # ── File operations (copy/move/delete) ──
    (_re_mod.compile(r"\b(?:copy|move|rename|delete)\s+.*\.(?:md|py|txt|json|ts|tsx|js|jsx|csv)\b", _re_mod.IGNORECASE), "shell_exec"),
    # ── File write/create ──
    (_re_mod.compile(r"\b(?:write|create|make)\s+(?:a\s+)?(?:new\s+)?(?:file|document)\b", _re_mod.IGNORECASE), "file_write"),
    (_re_mod.compile(r"\b(?:save|write)\s+.*\s+to\s+", _re_mod.IGNORECASE), "file_write"),
    # ── Web search/browse ──
    (_re_mod.compile(r"\b(?:search|look\s*up|find|google|browse)\s+(?:for|on|the\s+web|online)\b", _re_mod.IGNORECASE), "web_search"),
    (_re_mod.compile(r"\b(?:search|look\s*up|check|find)\s+(?:on\s+)?\S+\.(?:com|org|net|io)\b", _re_mod.IGNORECASE), "web_search"),
    (_re_mod.compile(r"\b(?:go\s+to|open|visit|navigate\s+to)\s+\S+\.(?:com|org|net|io)\b", _re_mod.IGNORECASE), "web_browse"),
    (_re_mod.compile(r"\b(?:latest|recent|current|today'?s?)\s+(?:news|headlines|updates|weather)\b", _re_mod.IGNORECASE), "web_search"),
    (_re_mod.compile(r"\b(?:can you|please)?\s*(?:check|search|look\s*up|find)\s+(?:the\s+)?(?:latest|recent|current)\b", _re_mod.IGNORECASE), "web_search"),
    # ── Project scaffold ──
    (_re_mod.compile(r"\b(?:set\s*up|scaffold|initialize|init|bootstrap)\s+(?:a\s+)?(?:new\s+)?project\b", _re_mod.IGNORECASE), "shell_exec"),
    # ── GPT log search ──
    (_re_mod.compile(r"\b(?:gpt|chatgpt)\s+(?:logs?|history|conversations?|export)\b", _re_mod.IGNORECASE), "gpt_log_search"),
    (_re_mod.compile(r"\b(?:search|check|find|look\s*(?:up|through)|dig\s+into|query)\s+(?:my\s+|the\s+)?(?:gpt|chatgpt)\b", _re_mod.IGNORECASE), "gpt_log_search"),
    (_re_mod.compile(r"\bwhat\s+(?:did\s+)?(?:I|we|nick)\s+(?:ask|discuss|talk|say|said)\s+(?:with\s+|to\s+)?(?:gpt|chatgpt)\b", _re_mod.IGNORECASE), "gpt_log_search"),
    (_re_mod.compile(r"\bwhat\s+(?:did\s+|has\s+)?(?:gpt|chatgpt)\s+(?:say|said|respond|think|suggest)\b", _re_mod.IGNORECASE), "gpt_log_search"),
    (_re_mod.compile(r"\b(?:trace|find|search)\s+(?:how\s+)?(?:ideas?|concepts?|things?)\s+(?:evolved|changed|developed)\b", _re_mod.IGNORECASE), "gpt_log_search"),
    (_re_mod.compile(r"\b(?:old|past|previous|prior|earlier)\s+(?:gpt\s+)?(?:conversations?|discussions?|chats?)\b", _re_mod.IGNORECASE), "gpt_log_search"),
]


# ---------------------------------------------------------------------------
# _extract_git_args
# ---------------------------------------------------------------------------

def _extract_git_args(message: str) -> list:
    """Extract git args from a natural language message."""
    m = _re_mod.search(r"\bgit\s+(status|diff|log|branch|commit|push|pull|stash)\b", message, _re_mod.IGNORECASE)
    if m:
        return [m.group(1).lower()]
    # "uncommitted changes" -> git status
    if _re_mod.search(r"\b(uncommitted|modified|staged)\s+(changes?|files?)", message, _re_mod.IGNORECASE):
        return ["status"]
    if _re_mod.search(r"\bgit\s+changes?", message, _re_mod.IGNORECASE):
        return ["status"]
    return ["status"]  # default to status for safety


# ---------------------------------------------------------------------------
# _capability_reroute
# ---------------------------------------------------------------------------

def _capability_reroute(message: str, current_intent) -> "Optional[TaskIntent]":
    """Check if a conversational message should actually route to a tool.

    Returns a new TaskIntent if re-routing is needed, None otherwise.
    Also detects multi-intent compound messages (e.g. "show processes and check git status").
    """
    from personal_agent.task_agent import TaskIntent

    msg = message.strip()
    _total_patterns = len(_CAPABILITY_REROUTE_PATTERNS) + len(_COMPOUND_INTENT_PATTERNS)
    _safe_print(f"[REROUTE] checking {_total_patterns} patterns against: {msg[:80]}")

    # First pass: collect all matching intents (primary + compound)
    matched_intents = []
    for pattern, intent_type, slots_fn in _CAPABILITY_REROUTE_PATTERNS:
        if pattern.search(msg):
            _slots = slots_fn(msg) if callable(slots_fn) else dict(slots_fn)
            matched_intents.append({"type": intent_type, "confidence": 0.85, "slots": _slots})

    # Check compound patterns too
    for pattern, intent_type in _COMPOUND_INTENT_PATTERNS:
        if pattern.search(msg):
            # Don't duplicate if already matched from primary patterns
            if not any(m["type"] == intent_type for m in matched_intents):
                matched_intents.append({"type": intent_type, "confidence": 0.80})

    if not matched_intents:
        _safe_print(f"[REROUTE] no pattern matched")
        return None

    _safe_print(f"[REROUTE] matched: {[m['type'] for m in matched_intents]}")
    # Single match -- return as single intent
    if len(matched_intents) == 1:
        m = matched_intents[0]
        return TaskIntent(
            route="task",
            intent_type=m["type"],
            confidence=m["confidence"],
            slots=m.get("slots", {}),
            reason="capability_reroute",
            source="capability_reroute",
        )

    # Multiple matches -- return as multi_intent for orchestration
    return TaskIntent(
        route="task",
        intent_type="multi_intent",
        confidence=matched_intents[0]["confidence"],
        slots={
            "intents": [{"type": m["type"], "confidence": m["confidence"]} for m in matched_intents],
        },
        reason="capability_reroute_multi",
        source="capability_reroute",
    )


# ---------------------------------------------------------------------------
# _route_model_for_request
# ---------------------------------------------------------------------------

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
