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
    """Return recent action receipts for a thread, including verification data."""
    from personal_agent.action_receipts import get_receipts

    return get_receipts(thread_id, limit=limit)


@router.get("/action-receipts/summary")
def receipt_summary(
    thread_id: str = Query("default", description="Thread ID"),
) -> Dict[str, Any]:
    """Return aggregate receipt stats: total actions, pass rate, tools used, models."""
    from personal_agent.action_receipts import get_receipt_summary

    return get_receipt_summary(thread_id)
