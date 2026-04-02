"""Shared runtime context for /api/chat/stream handlers."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, Optional

from fastapi import Request

from personal_agent.governed_task import GovernedTask
from personal_agent.stream_events import encode_sse_event, make_stream_event, normalize_stream_event

from .models import ChatSendRequest


@dataclass
class StreamTerminalResult:
    terminal: bool = False
    handled: bool = False
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ChatStreamRuntime:
    req: ChatSendRequest
    request: Request
    authorization: Optional[str]
    uid: Optional[int]
    safe_print: Callable[[str], None]
    session_db: Any
    event_bus: Any
    governed_task: Optional[dict] = None
    task_tag_types: set[str] = field(default_factory=lambda: {
        "agent_loop_start",
        "agent_loop_complete",
        "agent_checkpoint",
        "followup_suggest",
        "done",
        "error",
        "tool_start",
        "tool_result",
    })

    @property
    def ws_thread_id(self) -> Optional[str]:
        return getattr(self.req, "thread_id", None)

    def bus_emit(self, event: dict) -> None:
        self.event_bus.emit_sync(event.get("type", "unknown"), event, thread_id=self.ws_thread_id)

    def emit_status(self, status: str) -> str:
        event = make_stream_event("status", status)
        self.bus_emit(event)
        return encode_sse_event(event)

    def emit_phase(self, phase: str, content: str = "", end: bool = False) -> str:
        event_type = "phase_end" if end else "phase_start"
        event = make_stream_event(event_type, content, phase=phase)
        self.bus_emit(event)
        return encode_sse_event(event)

    def task_meta(self, extra: Optional[dict] = None) -> dict:
        meta = dict(extra or {})
        if self.governed_task:
            meta.setdefault("task_id", self.governed_task.get("task_id"))
            meta.setdefault("task_status", self.governed_task.get("status"))
            if self.governed_task.get("wait_kind"):
                meta.setdefault("wait_kind", self.governed_task.get("wait_kind"))
            if self.governed_task.get("checkpoint_tier"):
                meta.setdefault("checkpoint_tier", self.governed_task.get("checkpoint_tier"))
            if self.governed_task.get("parent_task_id"):
                meta.setdefault("parent_task_id", self.governed_task.get("parent_task_id"))
        return meta

    def emit(self, event: dict) -> str:
        if self.governed_task and event.get("type") in self.task_tag_types:
            event = dict(event)
            event["metadata"] = self.task_meta(event.get("metadata"))
        normalized = normalize_stream_event(event)
        self.bus_emit(normalized)
        return encode_sse_event(normalized)

    def ensure_governed_task(
        self,
        *,
        objective: str,
        max_iterations: int = 0,
        current_iteration: int = 0,
        remaining_iterations: Optional[int] = None,
        parent_task_id: Optional[str] = None,
    ) -> dict:
        if self.governed_task:
            return self.governed_task
        existing = self.session_db.get_active_governed_task(self.req.thread_id)
        if existing and str(existing.get("source") or "") == "agent_loop":
            self.governed_task = existing
            return self.governed_task
        task = GovernedTask.new(
            thread_id=self.req.thread_id,
            objective=objective,
            source="agent_loop",
            parent_task_id=parent_task_id,
            max_iterations=max_iterations,
            current_iteration=current_iteration,
            remaining_iterations=remaining_iterations,
        )
        self.governed_task = self.session_db.create_governed_task(task)
        return self.governed_task

    def update_governed_task(self, **changes: Any) -> Optional[dict]:
        if not self.governed_task:
            return None
        self.governed_task = self.session_db.update_governed_task(str(self.governed_task["task_id"]), **changes) or self.governed_task
        return self.governed_task

    def append_governed_event(self, event_type: str, content: str = "", metadata: Optional[dict] = None) -> None:
        if not self.governed_task:
            return
        self.session_db.append_governed_task_event(
            str(self.governed_task["task_id"]),
            self.req.thread_id,
            event_type,
            content=content,
            metadata=metadata or {},
        )
