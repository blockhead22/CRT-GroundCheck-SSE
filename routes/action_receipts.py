"""Action receipts route — read action history for a thread."""

from __future__ import annotations

from typing import Any, Dict, List

from fastapi import APIRouter, Query

router = APIRouter(prefix="/api", tags=["action-receipts"])


@router.get("/action-receipts")
def list_action_receipts(
    thread_id: str = Query(..., description="Thread ID"),
    limit: int = Query(20, ge=1, le=100, description="Max receipts to return"),
) -> List[Dict[str, Any]]:
    """Return recent action receipts for a thread."""
    from personal_agent.action_receipts import get_receipts

    return get_receipts(thread_id, limit=limit)
