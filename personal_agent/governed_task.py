"""Governed task lifecycle models for durable agent-loop runtime state."""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class _StringEnum(str, Enum):
    pass


class GovernedTaskStatus(_StringEnum):
    RUNNING = "running"
    AWAITING_USER = "awaiting_user"
    AWAITING_CHECKPOINT = "awaiting_checkpoint"
    AWAITING_SUBTASK = "awaiting_subtask"
    NEEDS_FOLLOWUP = "needs_followup"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    FAILED = "failed"


class GovernedTaskWaitKind(_StringEnum):
    ASK_USER = "ask_user"
    DIFF_WRITE = "diff_write"
    CHECKPOINT = "checkpoint"
    SUBAGENT = "subagent"


@dataclass
class GovernedTaskCheckpoint:
    checkpoint_tier: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class GovernedTaskEvent:
    task_id: str
    thread_id: str
    event_type: str
    content: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: float = field(default_factory=time.time)


@dataclass
class GovernedTask:
    task_id: str
    thread_id: str
    parent_task_id: Optional[str] = None
    source: str = "agent_loop"
    objective: str = ""
    status: GovernedTaskStatus = GovernedTaskStatus.RUNNING
    wait_kind: Optional[GovernedTaskWaitKind] = None
    checkpoint_tier: Optional[str] = None
    current_iteration: int = 0
    max_iterations: int = 0
    remaining_iterations: int = 0
    steps_done: List[Dict[str, Any]] = field(default_factory=list)
    pending_followups: List[str] = field(default_factory=list)
    orch_answer_so_far: str = ""
    question: Optional[str] = None
    result_summary: Optional[str] = None
    error: Optional[str] = None
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    expires_at: float = field(default_factory=lambda: time.time() + 86400.0)
    completed_at: Optional[float] = None
    state_json: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def new(
        cls,
        *,
        thread_id: str,
        objective: str,
        source: str = "agent_loop",
        parent_task_id: Optional[str] = None,
        max_iterations: int = 0,
        current_iteration: int = 0,
        remaining_iterations: Optional[int] = None,
    ) -> "GovernedTask":
        now = time.time()
        return cls(
            task_id=f"gt_{uuid.uuid4().hex}",
            thread_id=thread_id,
            parent_task_id=parent_task_id,
            source=source,
            objective=objective,
            max_iterations=max_iterations,
            current_iteration=current_iteration,
            remaining_iterations=max_iterations if remaining_iterations is None else remaining_iterations,
            created_at=now,
            updated_at=now,
            expires_at=now + 86400.0,
        )

    def to_record(self) -> Dict[str, Any]:
        return {
            "task_id": self.task_id,
            "thread_id": self.thread_id,
            "parent_task_id": self.parent_task_id,
            "source": self.source,
            "objective": self.objective,
            "status": self.status.value,
            "wait_kind": self.wait_kind.value if self.wait_kind else None,
            "checkpoint_tier": self.checkpoint_tier,
            "current_iteration": self.current_iteration,
            "max_iterations": self.max_iterations,
            "remaining_iterations": self.remaining_iterations,
            "steps_done": list(self.steps_done),
            "pending_followups": list(self.pending_followups),
            "orch_answer_so_far": self.orch_answer_so_far,
            "question": self.question,
            "result_summary": self.result_summary,
            "error": self.error,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "expires_at": self.expires_at,
            "completed_at": self.completed_at,
            "state_json": dict(self.state_json),
        }

    @classmethod
    def from_record(cls, row: Dict[str, Any]) -> "GovernedTask":
        return cls(
            task_id=str(row.get("task_id") or ""),
            thread_id=str(row.get("thread_id") or ""),
            parent_task_id=row.get("parent_task_id"),
            source=str(row.get("source") or "agent_loop"),
            objective=str(row.get("objective") or ""),
            status=GovernedTaskStatus(str(row.get("status") or GovernedTaskStatus.RUNNING.value)),
            wait_kind=GovernedTaskWaitKind(str(row["wait_kind"])) if row.get("wait_kind") else None,
            checkpoint_tier=row.get("checkpoint_tier"),
            current_iteration=int(row.get("current_iteration") or 0),
            max_iterations=int(row.get("max_iterations") or 0),
            remaining_iterations=int(row.get("remaining_iterations") or 0),
            steps_done=list(row.get("steps_done") or []),
            pending_followups=list(row.get("pending_followups") or []),
            orch_answer_so_far=str(row.get("orch_answer_so_far") or ""),
            question=row.get("question"),
            result_summary=row.get("result_summary"),
            error=row.get("error"),
            created_at=float(row.get("created_at") or time.time()),
            updated_at=float(row.get("updated_at") or time.time()),
            expires_at=float(row.get("expires_at") or (time.time() + 86400.0)),
            completed_at=float(row["completed_at"]) if row.get("completed_at") is not None else None,
            state_json=dict(row.get("state_json") or {}),
        )

    def apply_update(self, **changes: Any) -> "GovernedTask":
        for key, value in changes.items():
            setattr(self, key, value)
        self.updated_at = time.time()
        return self

    def mark_terminal(self, status: GovernedTaskStatus, *, result_summary: Optional[str] = None, error: Optional[str] = None) -> "GovernedTask":
        now = time.time()
        self.status = status
        self.wait_kind = None
        self.question = None
        self.pending_followups = []
        self.completed_at = now
        self.updated_at = now
        if result_summary is not None:
            self.result_summary = result_summary
        if error is not None:
            self.error = error
        return self
