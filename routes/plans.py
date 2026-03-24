"""Plans REST API — CRUD for multi-step task plans (v2.9.2)."""

from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from .models import (
    CreatePlanRequest,
    CreateStepRequest,
    PlanResponse,
    ReorderStepsRequest,
    StepResponse,
    UpdatePlanRequest,
    UpdateStepRequest,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/plans", tags=["plans"])


def _get_db():
    """Lazy import to avoid circular deps."""
    from personal_agent.db_utils import get_thread_session_db
    return get_thread_session_db()


def _plan_to_response(plan: dict) -> dict:
    """Normalise a DB plan dict into PlanResponse-compatible shape."""
    steps = []
    for s in plan.get("steps", []):
        steps.append({
            "id": s["id"],
            "plan_id": s["plan_id"],
            "step_number": s["step_number"],
            "title": s["title"],
            "description": s.get("description"),
            "status": s["status"],
            "tool_name": s.get("tool_name"),
            "input_json": s.get("input_json"),
            "output_json": s.get("output_json"),
            "needs_user_input": s.get("needs_user_input"),
            "user_input": s.get("user_input"),
            "started_at": s.get("started_at"),
            "completed_at": s.get("completed_at"),
        })
    return {
        "id": plan["id"],
        "title": plan["title"],
        "description": plan.get("description"),
        "status": plan["status"],
        "created_by": plan.get("created_by", "user"),
        "created_at": plan["created_at"],
        "updated_at": plan["updated_at"],
        "completed_at": plan.get("completed_at"),
        "metadata": plan.get("metadata"),
        "steps": steps,
        "current_step_id": plan.get("current_step_id"),
        "thread_id": plan.get("thread_id"),
    }


# ── Thread-Plan lookup (must be before /{plan_id} to avoid conflict) ───


@router.get("/thread/{thread_id}")
def get_thread_plan(thread_id: str):
    """Get the plan linked to a thread (if any)."""
    db = _get_db()
    plan = db.get_thread_plan(thread_id)
    if not plan:
        return None
    return _plan_to_response(plan)


# ── Plan CRUD ──────────────────────────────────────────────────────────


@router.get("")
def list_plans(status: Optional[str] = Query(None), limit: int = Query(50)):
    """List all plans, optionally filtered by status."""
    db = _get_db()
    plans = db.list_plans(status=status, limit=limit)
    # Attach steps to each plan
    result = []
    for p in plans:
        full = db.get_plan(p["id"])
        if full:
            result.append(_plan_to_response(full))
    return result


@router.post("")
def create_plan(req: CreatePlanRequest):
    """Create a new plan with optional steps."""
    db = _get_db()
    steps_data = [
        {
            "title": s.title,
            "description": s.description,
            "tool_name": s.tool_name,
            "needs_user_input": s.needs_user_input,
        }
        for s in req.steps
    ]
    plan = db.create_plan(
        title=req.title,
        description=req.description,
        created_by="user",
        steps=steps_data,
    )
    return _plan_to_response(plan)


@router.get("/{plan_id}")
def get_plan(plan_id: str):
    """Get a plan with all its steps."""
    db = _get_db()
    plan = db.get_plan(plan_id)
    if not plan:
        raise HTTPException(status_code=404, detail="Plan not found")
    return _plan_to_response(plan)


@router.put("/{plan_id}")
def update_plan(plan_id: str, req: UpdatePlanRequest):
    """Update plan title, description, or status."""
    db = _get_db()
    existing = db.get_plan(plan_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Plan not found")
    kwargs = {}
    if req.title is not None:
        kwargs["title"] = req.title
    if req.description is not None:
        kwargs["description"] = req.description
    if req.status is not None:
        kwargs["status"] = req.status
    if kwargs:
        db.update_plan(plan_id, **kwargs)
    return _plan_to_response(db.get_plan(plan_id))


@router.delete("/{plan_id}")
def delete_plan(plan_id: str):
    """Delete a plan and all its steps."""
    db = _get_db()
    existing = db.get_plan(plan_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Plan not found")
    db.delete_plan(plan_id)
    return {"ok": True}


# ── Step CRUD ──────────────────────────────────────────────────────────


@router.post("/{plan_id}/steps")
def add_step(plan_id: str, req: CreateStepRequest):
    """Add a step to a plan."""
    db = _get_db()
    existing = db.get_plan(plan_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Plan not found")
    step = db.add_plan_step(
        plan_id=plan_id,
        title=req.title,
        description=req.description,
        tool_name=req.tool_name,
    )
    return step


@router.put("/{plan_id}/steps/{step_id}")
def update_step(plan_id: str, step_id: str, req: UpdateStepRequest):
    """Update a step's status, output, user_input, etc."""
    db = _get_db()
    kwargs = {}
    if req.title is not None:
        kwargs["title"] = req.title
    if req.description is not None:
        kwargs["description"] = req.description
    if req.status is not None:
        kwargs["status"] = req.status
    if req.output_json is not None:
        kwargs["output_json"] = req.output_json
    if req.user_input is not None:
        kwargs["user_input"] = req.user_input
    if req.tool_name is not None:
        kwargs["tool_name"] = req.tool_name
    if kwargs:
        db.update_step(step_id, **kwargs)
    # Return updated plan
    plan = db.get_plan(plan_id)
    if not plan:
        raise HTTPException(status_code=404, detail="Plan not found")
    return _plan_to_response(plan)


@router.delete("/{plan_id}/steps/{step_id}")
def delete_step(plan_id: str, step_id: str):
    """Remove a step from a plan."""
    db = _get_db()
    db.delete_step(step_id)
    return {"ok": True}


@router.post("/{plan_id}/reorder")
def reorder_steps(plan_id: str, req: ReorderStepsRequest):
    """Reorder steps by providing an ordered list of step IDs."""
    db = _get_db()
    db.reorder_steps(plan_id, req.step_ids)
    plan = db.get_plan(plan_id)
    if not plan:
        raise HTTPException(status_code=404, detail="Plan not found")
    return _plan_to_response(plan)


# ── Thread-Plan linking ────────────────────────────────────────────────


@router.post("/{plan_id}/link/{thread_id}")
def link_plan_to_thread(plan_id: str, thread_id: str):
    """Link a plan to a thread."""
    db = _get_db()
    existing = db.get_plan(plan_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Plan not found")
    db.link_plan_to_thread(thread_id, plan_id)
    return {"ok": True, "plan_id": plan_id, "thread_id": thread_id}


@router.delete("/{plan_id}/link/{thread_id}")
def unlink_plan_from_thread(plan_id: str, thread_id: str):
    """Unlink a plan from a thread."""
    db = _get_db()
    db.unlink_plan_from_thread(thread_id)
    return {"ok": True}
