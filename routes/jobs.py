"""Jobs route module – extracted from crt_api.py."""

from __future__ import annotations

import time
import uuid
from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException, Query, Request

from personal_agent.artifact_store import now_iso_utc
from personal_agent.jobs_db import (
    enqueue_job,
    get_job,
    list_job_artifacts,
    list_job_events,
    list_jobs,
)
from routes.deps import sanitize_thread_id, thread_db_paths
from routes.models import (
    EnqueueJobRequest,
    EnqueueJobResponse,
    JobDetailResponse,
    JobListItem,
    JobsListResponse,
    JobsStatusResponse,
)

router = APIRouter(prefix="/api/jobs", tags=["jobs"])


# ── GET /api/jobs/status ──────────────────────────────────────────────────

@router.get("/status", response_model=JobsStatusResponse)
def jobs_status(request: Request) -> JobsStatusResponse:
    st = (
        request.app.state.jobs_worker.status().to_dict()
        if getattr(request.app.state, "jobs_worker", None)
        else {}
    )
    return JobsStatusResponse(
        enabled=bool(getattr(request.app.state.jobs_worker, "enabled", False)),
        worker=st,
        idle_scheduler_enabled=bool(
            getattr(request.app.state.idle_scheduler, "enabled", False)
        ),
        jobs_db_path=str(getattr(request.app.state, "jobs_db_path", "")),
    )


# ── GET /api/jobs ─────────────────────────────────────────────────────────

@router.get("", response_model=JobsListResponse)
def jobs_list(
    request: Request,
    status: Optional[str] = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> JobsListResponse:
    rows = list_jobs(
        request.app.state.jobs_db_path,
        status=status,
        limit=limit,
        offset=offset,
    )
    return JobsListResponse(
        jobs=[
            JobListItem(
                id=r.id,
                type=r.type,
                status=r.status,
                priority=r.priority,
                created_at=r.created_at,
                started_at=r.started_at,
                finished_at=r.finished_at,
                payload=r.payload,
                error=r.error,
            )
            for r in rows
        ]
    )


# ── GET /api/jobs/{job_id} ────────────────────────────────────────────────

@router.get("/{job_id}", response_model=JobDetailResponse)
def job_get(job_id: str, request: Request) -> JobDetailResponse:
    row = get_job(request.app.state.jobs_db_path, job_id)
    if row is None:
        raise HTTPException(status_code=404, detail=f"Job not found: {job_id}")

    return JobDetailResponse(
        job=JobListItem(
            id=row.id,
            type=row.type,
            status=row.status,
            priority=row.priority,
            created_at=row.created_at,
            started_at=row.started_at,
            finished_at=row.finished_at,
            payload=row.payload,
            error=row.error,
        ),
        events=list_job_events(request.app.state.jobs_db_path, job_id),
        artifacts=list_job_artifacts(request.app.state.jobs_db_path, job_id),
    )


# ── POST /api/jobs ────────────────────────────────────────────────────────

@router.post("", response_model=EnqueueJobResponse)
def jobs_enqueue(req: EnqueueJobRequest, request: Request) -> EnqueueJobResponse:
    jid = (req.job_id or "").strip() or f"job_{int(time.time())}_{uuid.uuid4().hex[:8]}"

    payload: Dict[str, Any] = dict(req.payload or {})
    thread_id = str(payload.get("thread_id") or payload.get("thread") or "").strip() or None
    if thread_id:
        mem_db, led_db = thread_db_paths(request, thread_id)

        # Convenience: infer DB paths when absent.
        if req.type in {"propose_promotions"}:
            payload.setdefault("memory_db", mem_db)
        if req.type in {"auto_resolve_contradictions"}:
            payload.setdefault("memory_db", mem_db)
            payload.setdefault("ledger_db", led_db)

        # Research jobs optionally store EXTERNAL memory; if requested, infer memory_db.
        if req.type in {"research_fetch", "research_summarize"}:
            if bool(payload.get("store_as_external_memory")):
                payload.setdefault("memory_db", mem_db)

    enqueue_job(
        db_path=request.app.state.jobs_db_path,
        job_id=jid,
        job_type=req.type,
        created_at=now_iso_utc(),
        payload=payload,
        priority=int(req.priority or 0),
    )
    return EnqueueJobResponse(job_id=jid)

