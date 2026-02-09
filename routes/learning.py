"""Learning & feedback route module.

Extracted from crt_api.py — contains:
  /api/learn/*       – training-loop status & trigger
  /api/learning/*    – active-learning stats, events, corrections
  /api/feedback/*    – thumbs, corrections, reports, stats
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict, List

from fastapi import APIRouter, BackgroundTasks, HTTPException, Query, Request

from personal_agent.active_learning import (
    LearningStats,
    get_active_learning_coordinator,
)
from routes.models import (
    CorrectionItem,
    CorrectionRequest,
    FeedbackCorrectionRequest,
    FeedbackReportRequest,
    FeedbackThumbsRequest,
    LearnRunRequest,
    LearnStatusResponse,
    LearningStatsResponse,
)

router = APIRouter()


# ========================================================================
# TRAINING-LOOP ENDPOINTS  (/api/learn/*)
# ========================================================================


@router.get("/api/learn/status", response_model=LearnStatusResponse)
def learn_status(request: Request) -> LearnStatusResponse:
    training_loop = request.app.state.training_loop
    st = training_loop.status().to_dict()
    model_path = os.environ.get("CRT_LEARNED_MODEL_PATH")
    exists = bool(model_path and Path(model_path).exists())
    return LearnStatusResponse(
        enabled=bool(st.get("enabled")),
        running=bool(st.get("running")),
        last_started_at=st.get("last_started_at"),
        last_finished_at=st.get("last_finished_at"),
        last_ok=st.get("last_ok"),
        last_decision=st.get("last_decision"),
        last_reason=st.get("last_reason"),
        last_report_path=st.get("last_report_path"),
        last_error=st.get("last_error"),
        model_path=model_path,
        model_file_exists=exists,
    )


@router.post("/api/learn/run")
def learn_run(
    req: LearnRunRequest, background: BackgroundTasks, request: Request
) -> Dict[str, Any]:
    training_loop = request.app.state.training_loop
    if not bool(req.confirm):
        return {"ok": False, "error": "confirm must be true"}
    if not training_loop.enabled():
        return {"ok": False, "error": "training loop disabled"}

    kicked = training_loop.trigger_async()
    return {"ok": bool(kicked), "running": training_loop.status().running}


# ========================================================================
# ACTIVE LEARNING ENDPOINTS  (/api/learning/*)
# ========================================================================


@router.get("/api/learning/stats", response_model=LearningStatsResponse)
def learning_stats() -> LearningStatsResponse:
    """Get active learning statistics."""
    try:
        coordinator = get_active_learning_coordinator()
        stats: LearningStats = coordinator.get_stats()

        return LearningStatsResponse(
            total_events=stats.total_gate_events,
            total_corrections=stats.total_corrections,
            model_loaded=(stats.current_model_version != "none"),
            model_version=int(stats.current_model_version)
            if stats.current_model_version.isdigit()
            else None,
            model_accuracy=stats.current_model_accuracy,
            pending_training=(
                stats.pending_corrections >= stats.next_training_threshold
            ),
            recent_gate_pass_rate=None,  # TODO: Calculate from recent events
            recent_events_24h=0,  # TODO: Calculate from timestamp
        )
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to get learning stats: {e}"
        )


@router.get("/api/learning/events")
def learning_events_needing_correction(
    limit: int = Query(default=50, ge=1, le=100),
) -> List[Dict[str, Any]]:
    """Get recent gate events that need user correction."""
    try:
        coordinator = get_active_learning_coordinator()
        return coordinator.get_events_needing_correction(limit=limit)
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to get events: {e}"
        )


@router.get("/api/learning/corrections", response_model=list[CorrectionItem])
def learning_corrections(
    limit: int = Query(default=10, ge=1, le=100),
) -> list[CorrectionItem]:
    """Get recent user corrections."""
    try:
        coordinator = get_active_learning_coordinator()
        corrections = coordinator.get_recent_corrections(limit=limit)

        return [
            CorrectionItem(
                event_id=c["event_id"],
                question=c["question"],
                predicted_type=c["predicted_type"],
                corrected_type=c["corrected_type"],
                timestamp=c["timestamp"],
            )
            for c in corrections
        ]
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to get corrections: {e}"
        )


@router.post("/api/learning/correct/{event_id}")
def learning_correct(event_id: int, req: CorrectionRequest) -> Dict[str, Any]:
    """Submit user correction for a gate event."""
    try:
        coordinator = get_active_learning_coordinator()
        coordinator.record_user_correction(
            event_id=event_id,
            corrected_type=req.corrected_type,
        )

        stats = coordinator.get_stats()
        return {
            "ok": True,
            "pending_training": stats.pending_training,
            "total_corrections": stats.total_corrections,
        }
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to record correction: {e}"
        )


# ========================================================================
# FEEDBACK ENDPOINTS  (/api/feedback/*)
# ========================================================================


@router.post("/api/feedback/thumbs")
def feedback_thumbs(req: FeedbackThumbsRequest) -> Dict[str, Any]:
    """Submit thumbs up/down feedback for an interaction."""
    try:
        coordinator = get_active_learning_coordinator()
        success = coordinator.record_feedback_thumbs(
            interaction_id=req.interaction_id,
            thumbs_up=req.thumbs_up,
            comment=req.comment,
        )

        return {
            "ok": success,
            "interaction_id": req.interaction_id,
            "feedback": "thumbs_up" if req.thumbs_up else "thumbs_down",
        }
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to record feedback: {e}"
        )


@router.post("/api/feedback/correction")
def feedback_correction(req: FeedbackCorrectionRequest) -> Dict[str, Any]:
    """Submit a correction for an interaction (e.g., 'Actually, my name is Alice')."""
    try:
        coordinator = get_active_learning_coordinator()
        correction_id = coordinator.record_feedback_correction(
            interaction_id=req.interaction_id,
            correction_type=req.correction_type,
            field_name=req.field_name,
            incorrect_value=req.incorrect_value,
            correct_value=req.correct_value,
            user_comment=req.comment,
        )

        return {
            "ok": True,
            "correction_id": correction_id,
            "interaction_id": req.interaction_id,
        }
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to record correction: {e}"
        )


@router.post("/api/feedback/report")
def feedback_report(req: FeedbackReportRequest) -> Dict[str, Any]:
    """Report an issue with an interaction."""
    try:
        coordinator = get_active_learning_coordinator()
        success = coordinator.record_feedback_report(
            interaction_id=req.interaction_id,
            issue_type=req.issue_type,
            description=req.description,
        )

        return {
            "ok": success,
            "interaction_id": req.interaction_id,
            "reported": True,
        }
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to record report: {e}"
        )


@router.get("/api/feedback/stats")
def feedback_stats(
    hours: int = Query(default=24, ge=1, le=168),
) -> Dict[str, Any]:
    """Get feedback statistics for the last N hours."""
    try:
        coordinator = get_active_learning_coordinator()
        stats = coordinator.get_interaction_stats(hours=hours)
        return stats
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to get stats: {e}"
        )

