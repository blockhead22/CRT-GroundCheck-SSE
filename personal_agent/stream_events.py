"""Canonical chat stream and WebSocket event contract helpers."""

from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Any, Dict, Final

CHAT_STREAM_EVENT_TYPES: Final[frozenset[str]] = frozenset(
    {
        "status",
        "intent_preview",
        "intent_classified",
        "plan_ready",
        "tool_start",
        "tool_result",
        "validate_result",
        "task_done",
        "task_acknowledged",
        "orchestration_start",
        "subtask_start",
        "subtask_done",
        "orchestration_done",
        "agent_checkpoint",
        "task_cancelled",
        "agent_thinking_token",
        "thinking_start",
        "thinking_token",
        "thinking",
        "thinking_end",
        "phase_start",
        "phase_end",
        "token",
        "correction",
        "stream_checkpoint",
        "stream_stopped",
        "plan_proposal",
        "plan_update",
        "plan_complete",
        "agent_loop_start",
        "agent_loop_complete",
        "retrieval",
        "trust_shift",
        "verification",
        "epistemic_event",
        "drift",
        "session_state",
        "followup_suggest",
        "done",
        "error",
    }
)

WS_SERVER_EVENT_TYPES: Final[frozenset[str]] = CHAT_STREAM_EVENT_TYPES | frozenset(
    {
        "connected",
        "subscribed",
        "pong",
        "notification",
        "proactive_turn",
    }
)


def _coerce_metadata(metadata: Any) -> Dict[str, Any] | None:
    if metadata is None:
        return None
    if not isinstance(metadata, Mapping):
        raise TypeError("stream event metadata must be a mapping or None")
    return dict(metadata)


def normalize_stream_event(
    event: Mapping[str, Any],
    *,
    allow_ws: bool = False,
) -> Dict[str, Any]:
    event_type = str(event.get("type") or "").strip()
    allowed = WS_SERVER_EVENT_TYPES if allow_ws else CHAT_STREAM_EVENT_TYPES
    if event_type not in allowed:
        raise ValueError(f"unsupported stream event type: {event_type!r}")

    normalized: Dict[str, Any] = {"type": event_type, "content": str(event.get("content") or "")}

    phase = event.get("phase")
    if phase is not None:
        normalized["phase"] = str(phase)

    metadata = _coerce_metadata(event.get("metadata"))
    if metadata is not None:
        normalized["metadata"] = metadata

    for key, value in event.items():
        if key in {"type", "content", "phase", "metadata"}:
            continue
        normalized[key] = value

    return normalized


def make_stream_event(
    event_type: str,
    content: str = "",
    *,
    metadata: Mapping[str, Any] | None = None,
    phase: str | None = None,
    allow_ws: bool = False,
    **extra: Any,
) -> Dict[str, Any]:
    raw: Dict[str, Any] = {"type": event_type, "content": content, **extra}
    if metadata is not None:
        raw["metadata"] = dict(metadata)
    if phase is not None:
        raw["phase"] = phase
    return normalize_stream_event(raw, allow_ws=allow_ws)


def encode_sse_event(event: Mapping[str, Any]) -> str:
    normalized = normalize_stream_event(event)
    return f"data: {json.dumps(normalized)}\n\n"
