"""API routes for commitment governance (Sprint 4)."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

router = APIRouter(prefix="/api/commitments", tags=["commitments"])


# ---------------------------------------------------------------------------
# Request / response models
# ---------------------------------------------------------------------------

class CreateCommitmentRequest(BaseModel):
    thread_id: str = "default"
    intent: str
    description: str
    deadline: Optional[float] = None
    deadline_text: Optional[str] = None  # natural language, e.g. "tomorrow at 3pm"
    recurrence: Optional[str] = None
    priority: str = "medium"
    consequence: Optional[str] = None
    origin: str = "user_requested"
    metadata: Dict[str, Any] = Field(default_factory=dict)


class UpdateStatusRequest(BaseModel):
    status: str


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post("")
def create_commitment_endpoint(req: CreateCommitmentRequest):
    """Create a new commitment / reminder."""
    from personal_agent.commitments import create_commitment, format_timestamp

    deadline = req.deadline
    recurrence = req.recurrence

    # Parse natural language time if provided
    if req.deadline_text and not deadline:
        from personal_agent.time_parser import parse_time_expression
        parsed = parse_time_expression(req.deadline_text)
        if parsed["deadline"]:
            deadline = parsed["deadline"]
        if parsed["recurrence"]:
            recurrence = parsed["recurrence"]

    if not deadline:
        raise HTTPException(status_code=400, detail="No deadline provided or parseable from deadline_text")

    commitment = create_commitment(
        thread_id=req.thread_id,
        intent=req.intent,
        description=req.description,
        deadline=deadline,
        recurrence=recurrence,
        priority=req.priority,
        consequence=req.consequence,
        origin=req.origin,
        metadata=req.metadata,
    )

    return {
        "commitment": commitment.to_dict(),
        "message": f"Reminder set: {commitment.description}. "
                   f"Next fire: {format_timestamp(commitment.next_fire_at) if commitment.next_fire_at else 'none'}. "
                   f"Recurrence: {commitment.recurrence or 'one-time'}.",
    }


@router.get("")
def list_commitments_endpoint(
    thread_id: Optional[str] = Query(default=None),
    status: Optional[str] = Query(default=None),
):
    """List commitments, optionally filtered."""
    from personal_agent.commitments import get_all_commitments
    commitments = get_all_commitments(thread_id=thread_id, status=status)
    return {
        "commitments": [c.to_dict() for c in commitments],
        "count": len(commitments),
    }


@router.get("/due")
def due_commitments_endpoint(
    minutes: int = Query(default=5, ge=1, le=1440),
):
    """Get commitments due in the next N minutes."""
    import time
    from personal_agent.commitments import get_pending_commitments
    before = time.time() + (minutes * 60)
    commitments = get_pending_commitments(before_timestamp=before)
    return {
        "commitments": [c.to_dict() for c in commitments],
        "count": len(commitments),
    }


@router.put("/{commitment_id}/status")
def update_status_endpoint(commitment_id: str, req: UpdateStatusRequest):
    """Update the status of a commitment."""
    from personal_agent.commitments import update_commitment_status
    result = update_commitment_status(commitment_id, req.status)
    if not result:
        raise HTTPException(status_code=404, detail="Commitment not found")
    return {"commitment": result.to_dict()}


@router.delete("/{commitment_id}")
def cancel_commitment_endpoint(commitment_id: str):
    """Cancel a commitment."""
    from personal_agent.commitments import cancel_commitment
    result = cancel_commitment(commitment_id)
    if not result:
        raise HTTPException(status_code=404, detail="Commitment not found")
    return {
        "commitment": result.to_dict(),
        "message": f"Cancelled reminder: {result.description}",
    }
