"""Pipeline status/event helpers and ResponseControlState extracted from routes/chat.py."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from personal_agent.stream_events import normalize_stream_event

from ._constants import (
    _pipeline_status_queue,
    _pipeline_event_queue,
    _CONTRADICTION_CAVEAT_RE,
)


def _safe_print(msg: str) -> None:
    """Print to console, replacing unencodable characters (Windows cp1252 fix)."""
    try:
        print(msg)
    except UnicodeEncodeError:
        print(msg.encode("ascii", errors="replace").decode("ascii"))


def _emit_pipeline_status(status: str) -> None:
    """Push a pipeline status event to the SSE stream (if one is active)."""
    q = _pipeline_status_queue.get(None)
    if q is not None:
        q.put_nowait(status)


def _emit_pipeline_event(event: dict) -> None:
    """Push a structured SSE event dict to the stream queue (if one is active)."""
    q = _pipeline_event_queue.get(None)
    if q is not None:
        q.put_nowait(normalize_stream_event(event))


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
