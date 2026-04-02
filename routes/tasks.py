"""Governed task status routes."""

from __future__ import annotations

from fastapi import APIRouter, Query

from .deps import sanitize_thread_id
from .models import ActiveGovernedTaskItem, ActiveGovernedTaskResponse
from personal_agent.db_utils import get_thread_session_db


router = APIRouter(prefix="/api/tasks", tags=["tasks"])


@router.get("/active", response_model=ActiveGovernedTaskResponse)
def get_active_task(thread_id: str = Query(default="default")) -> ActiveGovernedTaskResponse:
    thread_id = sanitize_thread_id(thread_id)
    session_db = get_thread_session_db()
    task = session_db.get_active_governed_task(thread_id)
    if not task:
        return ActiveGovernedTaskResponse(task=None)
    return ActiveGovernedTaskResponse(
        task=ActiveGovernedTaskItem(
            task_id=str(task.get("task_id") or ""),
            thread_id=str(task.get("thread_id") or thread_id),
            source=str(task.get("source") or "agent_loop"),
            objective=str(task.get("objective") or ""),
            status=str(task.get("status") or ""),
            wait_kind=task.get("wait_kind"),
            checkpoint_tier=task.get("checkpoint_tier"),
            current_iteration=int(task.get("current_iteration") or 0),
            max_iterations=int(task.get("max_iterations") or 0),
            remaining_iterations=int(task.get("remaining_iterations") or 0),
            question=task.get("question"),
            pending_followups=list(task.get("pending_followups") or []),
            updated_at=float(task.get("updated_at") or 0.0),
        )
    )
