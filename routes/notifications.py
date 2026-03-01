"""Outbound notifications API routes."""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Query

from .deps import sanitize_thread_id
from .models import NotificationClaimRequest, NotificationEnqueueRequest, NotificationFailRequest
from personal_agent.db_utils import get_thread_session_db


router = APIRouter(prefix="/api/notifications", tags=["notifications"])


@router.get("")
def list_notifications(
    thread_id: Optional[str] = Query(default=None),
    status: Optional[str] = Query(default=None),
    channel: Optional[str] = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
):
    session_db = get_thread_session_db()
    tid = sanitize_thread_id(thread_id) if thread_id else None
    items = session_db.list_notifications(
        thread_id=tid,
        status=status,
        channel=channel,
        limit=limit,
    )
    return {"items": items, "count": len(items)}


@router.post("/enqueue")
def enqueue_notification(req: NotificationEnqueueRequest):
    session_db = get_thread_session_db()
    tid = sanitize_thread_id(req.thread_id)
    result = session_db.enqueue_notification(
        thread_id=tid,
        channel=req.channel,
        destination_id=req.destination_id,
        content=req.content,
        category=req.category,
        priority=req.priority,
        payload=req.payload,
        dedupe_key=req.dedupe_key,
        source_kind=req.source_kind,
        source_id=req.source_id,
        max_attempts=req.max_attempts,
    )
    return {"ok": True, **result}


@router.post("/claim")
def claim_notifications(req: NotificationClaimRequest):
    session_db = get_thread_session_db()
    items = session_db.claim_notifications(
        worker_id=req.worker_id,
        channel=req.channel,
        limit=req.limit,
    )
    return {"items": items, "count": len(items)}


@router.post("/{notification_id}/ack")
def ack_notification(notification_id: str):
    session_db = get_thread_session_db()
    ok = session_db.ack_notification(notification_id)
    return {"ok": ok, "notification_id": notification_id}


@router.post("/{notification_id}/fail")
def fail_notification(notification_id: str, req: NotificationFailRequest):
    session_db = get_thread_session_db()
    result = session_db.fail_notification(
        notification_id=notification_id,
        error=req.error,
        retry_in_seconds=req.retry_in_seconds,
    )
    return {"notification_id": notification_id, **result}

