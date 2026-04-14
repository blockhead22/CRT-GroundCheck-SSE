"""Chat endpoint functions — extracted from routes/chat.py.

Contains:
  chat_send          POST /api/chat/send   (synchronous)
  chat_stream        POST /api/chat/stream  (SSE streaming)
  chat_intent        POST /api/chat/intent  (intent-routed)
  chat_feedback      POST /api/chat/feedback
"""

from __future__ import annotations

import contextvars
import json
import logging
import os
import queue as _queue_mod
import re
import sqlite3
import threading
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from fastapi import APIRouter, Header, Request
from fastapi.responses import StreamingResponse

from ..deps import sanitize_thread_id, resolve_user_id
from personal_agent.text_utils import (
    strip_thinking_tags as _strip_thinking_tags,
    strip_think_blocks,
    extract_think_content,
    looks_like_llm_error_text,
)
from ..models import (
    ChatSendRequest,
    ChatSendResponse,
    IntentQueryRequest,
    IntentQueryResponse,
)

from personal_agent.runtime_config import get_runtime_config
from personal_agent.cloud_usage_tracker import log_cloud_call as _track_cloud_call
from personal_agent.db_utils import get_thread_session_db
from personal_agent.governed_task import GovernedTaskStatus, GovernedTaskWaitKind
from personal_agent.runtime_paths import resolve_agent_runs_db_path
from personal_agent.stream_events import normalize_stream_event
from ..chat_agent_loop_runner import run_agent_tool_loop
from ..chat_governed_resume import try_resume_or_resolve
from ..chat_orchestrator_runner import run_orchestrator
from ..chat_provider_routing import (
    build_orchestrator_brain,
    build_request_llm_client,
    is_cloud_fallback_allowed,
    resolve_effective_generation_mode,
)
from ..chat_runtime import ChatStreamRuntime

try:
    from personal_agent.governance import GovernanceLayer, GovernanceTier
    _LEGACY_GOVERNANCE = GovernanceLayer()
except Exception:
    _LEGACY_GOVERNANCE = None
    GovernanceTier = None
from personal_agent.greeting_system import get_time_based_greeting
from personal_agent.active_learning import get_active_learning_coordinator
from personal_agent.episodic_memory import get_episodic_manager
from personal_agent.openclaw_bridge import run_openclaw_agent, should_delegate_to_openclaw
from ..meta_awareness import (
    build_meta_awareness_snapshot,
    is_meta_awareness_prompt,
    render_meta_awareness_response,
)
from personal_agent.reflection_system import run_reflection_pass, ReflectionResult
from personal_agent.scheduled_tasks import schedule_reminder, extract_reminder_from_message
from personal_agent.fact_slots import extract_fact_slots

# --- Sibling submodule imports ---
from ._constants import (
    _pipeline_status_queue, _pipeline_event_queue,
    _TASKING_INTERVAL_SECONDS, _TASKING_LAST_RUN, _TASKING_LOCK,
    _EXPAND_TRIGGERS, _CONTINUITY_FOLLOWUP_HINTS,
    _GROUNDCHECK_BRIDGE_LOCK, _GROUNDCHECK_BRIDGE_LAST_SYNC,
)
from ._pipeline import (
    _safe_print, _emit_pipeline_status, _emit_pipeline_event,
    ResponseControlState, _control_status_lines,
    _env_bool, _answer_has_contradiction_caveat,
)
from ._history import (
    _load_recent_history_messages, _looks_like_follow_up, _augment_query_with_continuity,
    _normalize_followup_shortcut, _looks_like_pending_followup_shortcut,
    _extract_recent_followup_anchor, _resolve_pending_followup_context,
    _augment_query_with_pending_followup,
    _is_personal_history_question, _resolve_personal_history_reference,
    _build_gpt_reference_context_block, _build_gpt_reference_answer, _history_answer_is_weak,
    _get_or_build_gpt_reference_packet, _history_topic_key, _history_search_queries,
)
from ._personal_facts import (
    _is_meta_provenance_followup, _answer_recent_slot_provenance, _generic_meta_provenance_answer,
    _extract_personal_fact_bundle_slots, _answer_personal_fact_bundle,
)
from ._introspection import (
    _is_self_referential_question, _is_user_reflection_question, _is_broad_recall_request,
    _answer_self_referential, _answer_user_reflection, _answer_broad_recall,
)
from ._expansion import (
    _user_requested_expansion, _should_expand_response, _build_expansion_prompt,
    _generate_expansion, _chunk_text,
)
from ._preferences import (
    _format_style_instruction, _detect_response_mood, _get_verbosity_preference,
    _get_preference_profile, _format_preference_instruction,
    _normalize_confirmation_text, _is_confirmation_yes, _is_confirmation_no,
    _format_reminder_time,
)
from ._special import (
    _build_loop_acknowledgment, _is_bare_web_search_command, _resolve_bare_web_search_command,
    _post_answer_quick_check, _is_architecture_explanation_request, _classify_and_store_feedback,
    _is_contradiction_inventory_request, _try_answer_workplan_question,
    _try_answer_mcp_tools_question, _answer_from_docs,
)
from ._routing import (
    _extract_git_args, _capability_reroute, _route_model_for_request,
)
from ._governance import (
    _maybe_sync_groundcheck_bridge, _is_strict_local_only_mode, _is_cloud_governance_allowed,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/chat", tags=["chat"])


@router.post("/send", response_model=ChatSendResponse)
def chat_send(req: ChatSendRequest, request: Request, authorization: Optional[str] = Header(None)) -> ChatSendResponse:
    get_engine = request.app.state.get_engine
    get_llm_client = request.app.state.get_llm_client
    increment_turn = request.app.state.increment_turn
    _log_collapse_trail = request.app.state.log_collapse_trail

    # Propagate authenticated user_id into memory system context variable
    # so all memory writes during this request are tagged with the user.
    uid = resolve_user_id(authorization)
    if uid:
        from personal_agent.crt_memory import _request_user_id
        _request_user_id.set(uid)

    # --- Early diagnostic: log generation mode at pipeline entry ---
    try:
        import auth as _auth_early
        _uid_early = int(uid) if uid else 1
        _gen_mode_early = resolve_effective_generation_mode(req, uid)
        _safe_print(f"[PIPELINE_ENTRY] message=\"{str(req.message or '')[:60]}\" generation_mode={_gen_mode_early} uid={_uid_early} thread={req.thread_id}")
        # Reset per-request cost accumulator
        try:
            from personal_agent.litellm_client import get_default_llm_client
            get_default_llm_client().reset_request_cost()
        except Exception:
            pass
    except Exception as _early_err:
        _safe_print(f"[PIPELINE_ENTRY] message=\"{str(req.message or '')[:60]}\" (settings read failed: {_early_err})")

    # --- Layer 6: Implicit feedback capture for previous orchestrator run ---
    try:
        _fb_msg = str(req.message or "").strip().lower()
        if _fb_msg and len(_fb_msg) > 2:
            _classify_and_store_feedback(req.thread_id, _fb_msg)
    except Exception as _fb_err:
        _safe_print(f"[FEEDBACK] Error (non-fatal): {_fb_err}")

    engine = get_engine(req.thread_id)
    runtime_config = get_runtime_config()
    control_state = ResponseControlState(request_text=str(req.message or ""))
    control_state.mark("input_pause", "ready", chars=len(str(req.message or "")))
    timing_enabled = str(os.getenv("CRT_CHAT_TIMING", "1")).strip().lower() not in {"0", "false", "off", "no"}
    t0 = time.perf_counter()
    stage_marks: List[Dict[str, Any]] = []

    # Map internal stage names to user-facing pipeline status labels
    _STAGE_STATUS_MAP = {
        "chat_send_start": "reading context",
        "session_and_style_ready": "searching memory",
        "engine_query_done": "reasoning",
        "critic_done": "verifying",
        "thinking_trace_done": "planning response",
        "reflection_done": "drafting",
    }

    def _mark(stage: str) -> None:
        if not timing_enabled:
            return
        now = time.perf_counter()
        stage_marks.append(
            {
                "stage": stage,
                "t_ms": round((now - t0) * 1000.0, 2),
            }
        )
        # Push real-time status to SSE stream if mapped
        _label = _STAGE_STATUS_MAP.get(stage)
        if _label:
            _emit_pipeline_status(_label)

    def _timings() -> List[Dict[str, Any]]:
        if not timing_enabled:
            return []
        out: List[Dict[str, Any]] = []
        prev = 0.0
        for item in stage_marks:
            current = float(item.get("t_ms") or 0.0)
            out.append(
                {
                    "stage": item.get("stage"),
                    "t_ms": current,
                    "dt_ms": round(current - prev, 2),
                }
            )
            prev = current
        return out

    def _response_action(gates_passed: bool, gate_reason: Optional[str], response_type: str) -> str:
        reason = str(gate_reason or "")
        if not gates_passed:
            if "contradiction" in reason or response_type == "uncertainty":
                return "clarify"
            return "block"
        if reason in {"recent_slot_provenance", "meta_awareness", "docs_explanation"}:
            return "explain"
        if "reminder" in reason:
            return "confirm"
        return "send"

    def _finalize_metadata(
        metadata: Optional[Dict[str, Any]],
        *,
        response_type: str,
        gates_passed: bool,
        gate_reason: Optional[str],
        interaction_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        meta = dict(metadata or {})
        meta["response_type"] = response_type
        meta["gates_passed"] = bool(gates_passed)
        meta["gate_reason"] = gate_reason
        if interaction_id:
            meta["interaction_id"] = interaction_id
        control_state.final_action = _response_action(gates_passed, gate_reason, response_type)
        meta["response_control"] = {
            "request_kind": control_state.request_kind,
            "final_action": control_state.final_action,
            "effective_text": control_state.effective_text or control_state.request_text,
            "stages": list(control_state.stages),
        }
        existing = list(meta.get("pipeline_statuses") or [])
        meta["pipeline_statuses"] = _control_status_lines(control_state) + existing
        return meta

    def _chat_response(
        *,
        answer: str,
        response_type: str,
        gates_passed: bool,
        gate_reason: Optional[str],
        metadata: Optional[Dict[str, Any]] = None,
        xray: Optional[Dict[str, Any]] = None,
    ) -> ChatSendResponse:
        # _interaction_id captured from enclosing scope — generated before any
        # branch executes so every response path carries the same stable ID.
        return ChatSendResponse(
            answer=answer,
            response_type=response_type,
            gates_passed=gates_passed,
            gate_reason=gate_reason,
            session_id=getattr(engine, "session_id", None),
            metadata=_finalize_metadata(
                metadata,
                response_type=response_type,
                gates_passed=gates_passed,
                gate_reason=gate_reason,
                interaction_id=_interaction_id,
            ),
            xray=xray,
        )

    _mark("chat_send_start")

    # Generate interaction_id upfront so it can be returned to the client
    # before the background bookkeeping thread runs.
    _interaction_id = str(uuid.uuid4())

    # Session tracking: update activity and check for greeting
    session_db = get_thread_session_db()
    session = session_db.get_or_create_session(req.thread_id)

    # Persist channel context only when explicit channel metadata is provided.
    try:
        if req.channel or req.actor_id or req.channel_destination_id:
            session_db.update_channel_context(
                req.thread_id,
                channel=(req.channel or "api"),
                actor_id=req.actor_id,
                destination_id=req.channel_destination_id,
            )
    except Exception as e:
        logger.debug(f"[CHANNEL_CTX] Failed to persist channel context for {req.thread_id}: {e}")

    # Generate greeting if applicable (before processing query)
    greeting_text = None
    try:
        greeting_text = get_time_based_greeting(
            thread_id=req.thread_id,
            runtime_config=runtime_config,
            session_db=session_db,
            user_profile=engine.user_profile,
        )
    except Exception as e:
        logger.debug(f"[GREETING] Error generating greeting: {e}")

    # Update session activity
    session_db.update_activity(req.thread_id, increment_messages=True)
    style_profile = None
    try:
        style_profile = session_db.update_style_profile(req.thread_id, req.message)
    except Exception as e:
        logger.debug(f"[STYLE] Failed to update style profile: {e}")
    personality_profile = None
    reflection_scorecard = None
    try:
        personality_profile = session_db.get_personality_profile(req.thread_id)
    except Exception as e:
        logger.debug(f"[PERSONALITY] Failed to read personality profile: {e}")
    try:
        reflection_scorecard = session_db.get_reflection_scorecard(req.thread_id)
    except Exception as e:
        logger.debug(f"[REFLECTION_LOOP] Failed to read reflection scorecard: {e}")

    # Increment turn counter
    increment_turn(req.thread_id)
    _mark("session_and_style_ready")

    # Belief state classification (two-tap belief head)
    try:
        from personal_agent.belief_classifier import classify_query
        _belief = classify_query(str(req.message or ""))
        if _belief:
            logger.info("[BELIEF] %s | latency=%.1fms | query=%r",
                        _belief, _belief.latency_ms, str(req.message or "")[:60])
    except Exception:
        pass

    effective_message = _resolve_bare_web_search_command(
        message=req.message,
        session_db=session_db,
        thread_id=req.thread_id,
    )
    recent_history = _load_recent_history_messages(session_db, req.thread_id, window=6)
    pending_followup_context = _resolve_pending_followup_context(
        message=effective_message,
        session_db=session_db,
        thread_id=req.thread_id,
        history_messages=recent_history,
    )
    control_state.effective_text = effective_message
    control_state.request_kind = (
        "follow_up"
        if (_looks_like_follow_up(effective_message) or pending_followup_context is not None)
        else "direct"
    )
    if _is_meta_provenance_followup(effective_message):
        control_state.request_kind = "meta_provenance"
    elif _is_architecture_explanation_request(effective_message):
        control_state.request_kind = "architecture_explanation"
    elif _is_contradiction_inventory_request(effective_message):
        control_state.request_kind = "contradiction_inventory"
    control_state.mark(
        "determine_request",
        "classified",
        request_kind=control_state.request_kind,
        follow_up=(_looks_like_follow_up(effective_message) or pending_followup_context is not None),
    )

    openclaw_delegate, openclaw_reason = should_delegate_to_openclaw(
        message=effective_message,
        channel=req.channel,
        meta_scope=req.meta_scope,
        mode=req.mode,
        runtime_config=runtime_config,
    )
    if openclaw_delegate:
        structured_facts: Dict[str, Any] = {}
        try:
            if hasattr(engine, "get_effective_user_facts"):
                maybe_facts = engine.get_effective_user_facts(thread_id=req.thread_id)
                if isinstance(maybe_facts, dict):
                    structured_facts = maybe_facts
        except Exception as e:
            logger.debug("[OPENCLAW] Failed to build structured fact context: %s", e)

        try:
            openclaw_result = run_openclaw_agent(
                user_command=effective_message,
                thread_id=req.thread_id,
                crt_api_url=os.getenv("CRT_API_URL", "http://127.0.0.1:8123"),
                channel=req.channel,
                origin=req.origin,
                actor_id=req.actor_id,
                structured_facts=structured_facts,
                runtime_config=runtime_config,
                workdir=Path.cwd(),
            )
            if openclaw_result.get("ok"):
                control_state.request_kind = "openclaw_handoff"
                control_state.mark(
                    "decide",
                    "openclaw",
                    detail=str(openclaw_reason or "delegated"),
                    session_id=str(openclaw_result.get("session_id") or ""),
                )
                delegated_answer = str(openclaw_result.get("answer") or "").strip()
                if greeting_text:
                    delegated_answer = f"{greeting_text}\n\n{delegated_answer}"
                return _chat_response(
                    answer=delegated_answer,
                    response_type="speech",
                    gates_passed=True,
                    gate_reason="openclaw_handoff",
                    metadata={
                        "mode": "openclaw",
                        "confidence": 0.88,
                        "agent_activated": True,
                        "openclaw_delegated": True,
                        "openclaw_handoff_reason": openclaw_reason,
                        "openclaw_session_id": openclaw_result.get("session_id"),
                        "openclaw_agent_id": openclaw_result.get("agent_id"),
                        "structured_facts": structured_facts,
                        "pipeline_statuses": [
                            "delegating to openclaw",
                            f"openclaw session {openclaw_result.get('session_id')}",
                        ],
                    },
                )
            logger.warning(
                "[OPENCLAW] Handoff failed for thread=%s reason=%s rc=%s stderr=%s",
                req.thread_id,
                openclaw_reason,
                openclaw_result.get("returncode"),
                str(openclaw_result.get("stderr") or "")[:300],
            )
            control_state.mark(
                "decide",
                "openclaw_fallback",
                detail=str(openclaw_reason or "delegated"),
                returncode=int(openclaw_result.get("returncode") or 0),
            )
        except Exception as e:
            logger.warning("[OPENCLAW] Handoff exception for thread=%s: %s", req.thread_id, e)
            control_state.mark("decide", "openclaw_fallback", detail="exception")

    # ── Agentic URL/tool routing (DISABLED — Phase 1 checkpoint policy) ────────
    # Previously this block auto-routed URL + action verb messages and
    # service keywords (moltbook, openclaw) directly to agent_loop with
    # NO checkpoint or user confirmation.  This was the root cause of the
    # "hijack" behavior where the system jumped into tool spam without asking.
    #
    # All agentic routing now goes through the /stream endpoint's checkpoint
    # system (task_agent.classify_intent → gate_task_intent → checkpoint →
    # user confirms → execute).  The /send endpoint should NOT bypass that.
    #
    # If a caller needs agentic routing from /send, they should use /stream
    # instead, which has the full pause-confirm-act flow.
    # ── End agentic URL routing ───────────────────────────────────────────────

    if _is_meta_provenance_followup(effective_message):
        control_state.mark("bind", "recent_slot", detail="provenance_followup")
        provenance_answer = _answer_recent_slot_provenance(
            engine=engine,
            session_db=session_db,
            thread_id=req.thread_id,
        )
        provenance_gate_reason = "recent_slot_provenance" if provenance_answer else "generic_meta_provenance"
        if not provenance_answer:
            provenance_answer = _generic_meta_provenance_answer()
        if greeting_text:
            provenance_answer = f"{greeting_text}\n\n{provenance_answer}"
        try:
            session_db.record_query(
                thread_id=req.thread_id,
                query_text=req.message,
                response_text=provenance_answer,
                detected_slot="provenance",
            )
        except Exception as e:
            logger.debug(f"[SESSION] Error recording deterministic provenance query: {e}")
        try:
            from personal_agent.training_log import log_chat_turn
            log_chat_turn(
                thread_id=req.thread_id,
                user_message=req.message,
                assistant_response=provenance_answer,
                generation_mode="deterministic",
                intent="provenance",
            )
        except Exception:
            pass
        control_state.mark("decide", "ready", detail=provenance_gate_reason)
        control_state.mark("learn", "recorded", detail="fast_query")
        return _chat_response(
            answer=provenance_answer,
            response_type="explanation",
            gates_passed=True,
            gate_reason=provenance_gate_reason,
            metadata={
                "mode": "deterministic_provenance",
                "confidence": 0.98,
                "continuity_context_applied": True,
            },
        )

    def _record_fast_query(answer_text: str, detected_slot: Optional[str]) -> None:
        try:
            session_db.record_query(
                thread_id=req.thread_id,
                query_text=req.message,
                response_text=answer_text,
                detected_slot=detected_slot,
            )
        except Exception as e:
            logger.debug(f"[SESSION] Error recording deterministic query: {e}")
        try:
            from personal_agent.training_log import log_chat_turn
            log_chat_turn(
                thread_id=req.thread_id,
                user_message=req.message,
                assistant_response=answer_text,
                generation_mode="deterministic",
                intent=detected_slot or "fast_path",
            )
        except Exception:
            pass

    # Reminder confirmation flow (explicit yes/no before scheduling).
    pending_reminder: Optional[Dict[str, Any]] = None
    try:
        pending_reminder = session_db.get_pending_reminder(req.thread_id)
    except Exception as e:
        logger.debug(f"[REMINDER] Failed to load pending reminder for {req.thread_id}: {e}")
        pending_reminder = None

    if isinstance(pending_reminder, dict):
        if _is_confirmation_yes(effective_message):
            control_state.request_kind = "reminder_confirmation"
            control_state.mark("bind", "pending_reminder", detail="confirm_yes")
            reminder_text = str(pending_reminder.get("reminder_text") or "").strip()
            scheduled_at = float(pending_reminder.get("scheduled_at") or 0.0)
            if reminder_text and scheduled_at > time.time():
                db_path = str(getattr(request.app.state, "scheduled_tasks_db_path", "") or "")
                if db_path:
                    try:
                        task = schedule_reminder(
                            db_path=db_path,
                            thread_id=req.thread_id,
                            reminder_text=reminder_text,
                            scheduled_time=datetime.fromtimestamp(scheduled_at),
                        )
                        session_db.clear_pending_reminder(req.thread_id)
                        answer = (
                            f"Confirmed. I will remind you to '{reminder_text}' on "
                            f"{_format_reminder_time(scheduled_at)}."
                        )
                        if greeting_text:
                            answer = f"{greeting_text}\n\n{answer}"
                        _record_fast_query(answer, "reminder_confirmed")
                        control_state.mark("decide", "ready", detail="reminder_scheduled")
                        control_state.mark("learn", "recorded", detail="fast_query")
                        return _chat_response(
                            answer=answer,
                            response_type="speech",
                            gates_passed=True,
                            gate_reason="reminder_scheduled",
                            metadata={
                                "mode": "deterministic_reminder",
                                "confidence": 0.99,
                                "reminder_scheduled": True,
                                "reminder_task_id": getattr(task, "task_id", None),
                                "reminder_text": reminder_text,
                                "reminder_time": scheduled_at,
                            },
                        )
                    except Exception as e:
                        logger.warning(f"[REMINDER] Failed to schedule confirmed reminder: {e}")
                        session_db.clear_pending_reminder(req.thread_id)
                        error_answer = "I could not schedule that reminder due to an internal error. Please try again."
                        _record_fast_query(error_answer, "reminder_error")
                        control_state.mark("decide", "blocked", detail="reminder_schedule_error")
                        control_state.mark("learn", "recorded", detail="fast_query")
                        return _chat_response(
                            answer=error_answer,
                            response_type="speech",
                            gates_passed=False,
                            gate_reason="reminder_schedule_error",
                            metadata={
                                "mode": "deterministic_reminder",
                                "confidence": 0.35,
                                "reminder_scheduled": False,
                            },
                        )
            session_db.clear_pending_reminder(req.thread_id)
            cleared_answer = "That reminder request expired or had invalid timing, so I cleared it. Ask again and I will re-parse it."
            _record_fast_query(cleared_answer, "reminder_pending_cleared")
            control_state.mark("decide", "ready", detail="reminder_pending_cleared")
            control_state.mark("learn", "recorded", detail="fast_query")
            return _chat_response(
                answer=cleared_answer,
                response_type="speech",
                gates_passed=True,
                gate_reason="reminder_pending_cleared",
                metadata={
                    "mode": "deterministic_reminder",
                    "confidence": 0.9,
                    "reminder_pending_cleared": True,
                },
            )

        if _is_confirmation_no(effective_message):
            control_state.request_kind = "reminder_confirmation"
            control_state.mark("bind", "pending_reminder", detail="confirm_no")
            session_db.clear_pending_reminder(req.thread_id)
            answer = "Canceled. I did not schedule that reminder."
            if greeting_text:
                answer = f"{greeting_text}\n\n{answer}"
            _record_fast_query(answer, "reminder_cancelled")
            control_state.mark("decide", "ready", detail="reminder_cancelled")
            control_state.mark("learn", "recorded", detail="fast_query")
            return _chat_response(
                answer=answer,
                response_type="speech",
                gates_passed=True,
                gate_reason="reminder_cancelled",
                metadata={
                    "mode": "deterministic_reminder",
                    "confidence": 0.99,
                    "reminder_cancelled": True,
                },
            )

    reminder_candidate = None
    try:
        reminder_candidate = extract_reminder_from_message(effective_message)
    except Exception as e:
        logger.debug(f"[REMINDER] Reminder extraction failed: {e}")
        reminder_candidate = None

    if reminder_candidate:
        control_state.request_kind = "reminder_candidate"
        control_state.mark("bind", "reminder_candidate")
        reminder_text, reminder_dt = reminder_candidate
        scheduled_at = float(reminder_dt.timestamp())
        if scheduled_at <= time.time():
            past_answer = "I parsed a reminder request, but the target time is in the past. Please provide a future time."
            _record_fast_query(past_answer, "reminder_past_time")
            control_state.mark("decide", "ready", detail="reminder_past_time")
            control_state.mark("learn", "recorded", detail="fast_query")
            return _chat_response(
                answer=past_answer,
                response_type="speech",
                gates_passed=True,
                gate_reason="reminder_past_time",
                metadata={
                    "mode": "deterministic_reminder",
                    "confidence": 0.92,
                    "reminder_confirmation_required": False,
                },
            )
        session_db.set_pending_reminder(
            req.thread_id,
            reminder_text=str(reminder_text),
            scheduled_at=scheduled_at,
            source_message=req.message,
            expires_seconds=900,
        )
        human_time = _format_reminder_time(scheduled_at)
        answer = (
            f"I parsed this reminder: '{str(reminder_text).strip()}' at {human_time}. "
            "Reply 'yes' to confirm, or 'no' to cancel."
        )
        if greeting_text:
            answer = f"{greeting_text}\n\n{answer}"
        _record_fast_query(answer, "reminder_confirmation")
        control_state.mark("decide", "ready", detail="reminder_confirmation_required")
        control_state.mark("learn", "recorded", detail="fast_query")
        return _chat_response(
            answer=answer,
            response_type="speech",
            gates_passed=True,
            gate_reason="reminder_confirmation_required",
            metadata={
                "mode": "deterministic_reminder",
                "confidence": 0.97,
                "reminder_confirmation_required": True,
                "reminder_candidate": {
                    "text": str(reminder_text).strip(),
                    "scheduled_at": scheduled_at,
                    "scheduled_for": human_time,
                },
            },
        )

    groundcheck_bridge_meta: Optional[Dict[str, Any]] = None
    try:
        groundcheck_bridge_meta = _maybe_sync_groundcheck_bridge(
            thread_id=req.thread_id,
            engine=engine,
        )
    except Exception as e:
        logger.debug(f"[MEMORY_BRIDGE] Unexpected sync error: {e}")
        groundcheck_bridge_meta = {"enabled": True, "attempted": True, "ok": False, "error": str(e)}

    if is_meta_awareness_prompt(effective_message):
        control_state.request_kind = "meta_awareness"
        control_state.mark("bind", "meta_awareness")
        snapshot = build_meta_awareness_snapshot(
            thread_id=req.thread_id,
            session_db=session_db,
            engine=engine,
            recent_query_limit=8,
            journal_limit=8,
            contradiction_limit=8,
        )
        answer = render_meta_awareness_response(snapshot)
        if greeting_text:
            answer = f"{greeting_text}\n\n{answer}"
        _record_fast_query(answer, "meta_awareness")
        control_state.mark("decide", "ready", detail="meta_awareness")
        control_state.mark("learn", "recorded", detail="fast_query")
        return _chat_response(
            answer=answer,
            response_type="speech",
            gates_passed=True,
            gate_reason="meta_awareness",
            metadata={
                "mode": "meta_awareness",
                "confidence": 0.96,
                "meta_awareness": snapshot,
                "groundcheck_bridge": groundcheck_bridge_meta,
            },
        )

    # Deterministic ledger-backed contradiction inventory.
    if _is_contradiction_inventory_request(effective_message):
        control_state.request_kind = "contradiction_inventory"
        control_state.mark("bind", "ledger_inventory")
        from personal_agent.canonical_view import get_contradiction_counts

        ledger_db_path = str(getattr(engine.ledger, "db_path", "") or "")
        counts = get_contradiction_counts(ledger_db_path)
        open_count = int(counts.get("open", 0))
        resolved_count = int(counts.get("resolved", 0))
        accepted_count = int(counts.get("accepted", 0))
        reflecting_count = int(counts.get("reflecting", 0))
        total = int(sum(counts.values()))

        try:
            open_entries = engine.ledger.get_open_contradictions(limit=50)
        except Exception:
            open_entries = []

        hard_conflicts = sum(
            1 for e in open_entries if (getattr(e, "contradiction_type", "") or "") == "conflict"
        )

        lines = [
            "I can summarize what I\u2019ve recorded in the contradiction ledger so far.",
            f"Total contradictions recorded: {total}.",
            f"Open: {open_count}. Resolved: {resolved_count}. Accepted: {accepted_count}. Reflecting: {reflecting_count}.",
        ]

        if open_count > 0 and open_entries:
            lines.extend(["", "Most recent open items:"])
            for e in open_entries[:10]:
                typ = getattr(e, "contradiction_type", None) or "conflict"
                status = getattr(e, "status", None) or "open"
                summary = getattr(e, "summary", None) or "(no summary)"
                lines.append(f"- [{typ}/{status}] {summary}")
        elif open_count == 0:
            lines.append("")
            lines.append("There are no open contradictions at the moment.")

        answer = "\n".join(lines)

        control_state.mark("decide", "clarify", detail="ledger_contradictions")
        return _chat_response(
            answer=answer,
            response_type="explanation",
            gates_passed=False,
            gate_reason="ledger_contradictions",
            metadata={
                "mode": "uncertainty",
                "confidence": 0.65,
                "contradiction_detected": False,
                "unresolved_contradictions_total": open_count,
                "unresolved_hard_conflicts": hard_conflicts,
                "retrieved_memories": [],
                "prompt_memories": [],
                "groundcheck_bridge": groundcheck_bridge_meta,
            },
        )

    # Safe doc-grounded channel for architecture/system explanation questions.
    if _is_architecture_explanation_request(effective_message):
        control_state.request_kind = "architecture_explanation"
        control_state.mark("bind", "doc_map")
        doc_map = request.app.state.doc_map
        answer, prompt_items = _answer_from_docs(effective_message, doc_map)
        control_state.mark("decide", "ready", detail="docs_explanation")
        return _chat_response(
            answer=answer,
            response_type="explanation",
            gates_passed=True,
            gate_reason="docs_explanation",
            metadata={
                "confidence": 0.85,
                "retrieved_memories": [],
                "prompt_memories": prompt_items,
            },
        )

    bundled_personal_slots = _extract_personal_fact_bundle_slots(effective_message)
    if bundled_personal_slots:
        control_state.request_kind = "personal_fact_bundle"
        control_state.mark("bind", "structured_user_facts")
        answer = _answer_personal_fact_bundle(effective_message, engine, req.thread_id)
        if greeting_text:
            answer = f"{greeting_text}\n\n{answer}"
        control_state.mark("decide", "ready", detail="personal_fact_bundle")
        return _chat_response(
            answer=answer,
            response_type="belief",
            gates_passed=True,
            gate_reason="personal_fact_bundle",
            metadata={
                "confidence": 0.86,
                "retrieved_memories": [],
                "prompt_memories": [],
                "requested_slots": bundled_personal_slots,
            },
        )

    if _is_user_reflection_question(effective_message):
        control_state.request_kind = "user_reflection"
        control_state.mark("bind", "memory_reflection")
        answer = _answer_user_reflection(effective_message, engine, req.thread_id)
        if greeting_text:
            answer = f"{greeting_text}\n\n{answer}"
        control_state.mark("decide", "ready", detail="user_reflection")
        return _chat_response(
            answer=answer,
            response_type="belief",
            gates_passed=True,
            gate_reason="user_reflection",
            metadata={
                "confidence": 0.82,
                "retrieved_memories": [],
                "prompt_memories": [],
            },
        )

    # Self-referential questions: "how do you work?", "any contradictions?", etc.
    # Route to self-model + system knowledge instead of user-fact memory search.
    if _is_self_referential_question(effective_message):
        control_state.request_kind = "self_referential"
        control_state.mark("bind", "self_model")
        answer = _answer_self_referential(effective_message, engine, req.thread_id)
        if greeting_text:
            answer = f"{greeting_text}\n\n{answer}"
        control_state.mark("decide", "ready", detail="self_referential")
        return _chat_response(
            answer=answer,
            response_type="explanation",
            gates_passed=True,
            gate_reason="self_referential",
            metadata={
                "confidence": 0.80,
                "retrieved_memories": [],
                "prompt_memories": [],
            },
        )

    # Broad recall: "what do you know about me?" — dump all high-trust facts.
    # Also handles identity questions right after user provides info (recency awareness).
    # Check both the regex AND the intent classifier — the LLM router catches
    # broader patterns like "what do you remember about my views on X?"
    _is_identity_question = _is_broad_recall_request(effective_message)
    if not _is_identity_question:
        # Check if intent classifier said broad_recall
        try:
            _intent_type_for_recall = getattr(_task_intent, "intent_type", "") if _task_intent else ""
        except NameError:
            _intent_type_for_recall = ""
        if _intent_type_for_recall == "broad_recall":
            _is_identity_question = True
    if not _is_identity_question:
        # Also catch "who am I" / "tell me about who I am" that might not
        # fully match broad recall but need recency awareness
        _eff_lower = effective_message.lower()
        _is_identity_question = any(
            p in _eff_lower for p in ("who am i", "about who i am", "about me")
        ) and "?" in effective_message

    # Skip legacy broad_recall when the orchestrator will handle it.
    # The orchestrator has belief state injection (Tier 1 + Tier 2) which
    # grounds answers properly. The legacy path uses a local model that
    # hallucinates facts (Bug #8).
    _skip_legacy_broad_recall = False
    if _is_identity_question:
        try:
            _rt_cfg_br = get_runtime_config()
            _al_enabled_br = _rt_cfg_br.get("agent_loop", {}).get("enabled", False)
            if _al_enabled_br:
                _skip_legacy_broad_recall = True
                _safe_print("[BROAD_RECALL] Skipping legacy path — orchestrator will handle via belief state injection")
        except Exception:
            pass

    if _is_identity_question and not _skip_legacy_broad_recall:
        control_state.request_kind = "broad_recall"
        control_state.mark("bind", "memory_dump")

        # Recency awareness: check if user just provided identity info
        recent_context = ""
        try:
            recent = session_db.get_recent_queries(req.thread_id, window=3) if session_db else []
            for row in (recent or []):
                if not isinstance(row, dict):
                    continue
                prev_query = str(row.get("query_text") or "").strip()
                # If previous user message was a substantial assertion (bio, about me, etc.)
                if len(prev_query) > 100:
                    recent_context = prev_query
                    break
        except Exception:
            pass

        # Determine if this is a generic "about me" or topic-specific recall
        try:
            _recall_slots = getattr(_task_intent, "slots", {}) if _task_intent else {}
        except NameError:
            _recall_slots = {}
        _recall_query = _recall_slots.get("query", "") or ""
        # If no explicit query slot, check if the raw message is topic-specific
        # (not just "what do you know about me" but "what do you remember about my views on X")
        if not _recall_query:
            _raw_msg = _recall_slots.get("raw_message", effective_message) or effective_message
            # Extract topic from "about my X" or "about X" patterns
            import re as _re_recall
            _topic_match = _re_recall.search(r"\babout\s+(?:my\s+)?(.{5,60}?)(?:\?|$)", _raw_msg, _re_recall.IGNORECASE)
            if _topic_match:
                _candidate = _topic_match.group(1).strip().rstrip("?. ")
                # Skip generic "about me" patterns
                if _candidate.lower() not in ("me", "myself", "who i am", "me so far"):
                    _recall_query = _candidate
        if _recall_query and _recall_query not in ("about me", "me", "who am i"):
            # Topic-specific recall — use RAG retrieval + LLM synthesis
            _safe_print(f"[BROAD_RECALL] Topic-specific: '{_recall_query}' — using targeted retrieval")
            try:
                _retrieved = engine.retrieve(effective_message, k=15) if hasattr(engine, "retrieve") else []
                if _retrieved:
                    _mem_texts = []
                    for m in _retrieved[:10]:
                        _mt = m.get("text", "") if isinstance(m, dict) else str(m)
                        if _mt.strip():
                            _mem_texts.append(f"- {_mt.strip()[:300]}")
                    if _mem_texts:
                        _recall_context = "\n".join(_mem_texts)
                        # Try LLM synthesis
                        try:
                            from personal_agent.litellm_client import get_default_llm_client
                            _synth_client = get_default_llm_client()
                            _synth_resp = _synth_client.chat(
                                messages=[
                                    {"role": "system", "content": "You are Aether, a personal AI assistant. Synthesize the following memories into a coherent, conversational answer to the user's question. Be specific, cite what you actually know, and acknowledge gaps honestly."},
                                    {"role": "user", "content": f"Question: {effective_message}\n\nRelevant memories:\n{_recall_context}"},
                                ],
                                max_tokens=500,
                                temperature=0.3,
                            )
                            if _synth_resp and isinstance(_synth_resp, str) and len(_synth_resp.strip()) > 20:
                                answer = _synth_resp.strip()
                            else:
                                answer = f"Here's what I remember about that:\n\n{_recall_context}"
                        except Exception as _synth_err:
                            _safe_print(f"[BROAD_RECALL] Synthesis failed: {_synth_err}")
                            answer = f"Here's what I remember about that:\n\n{_recall_context}"
                    else:
                        answer = _answer_broad_recall(engine, req.thread_id)
                else:
                    answer = _answer_broad_recall(engine, req.thread_id)
            except Exception as _tgt_err:
                _safe_print(f"[BROAD_RECALL] Targeted retrieval failed: {_tgt_err}")
                answer = _answer_broad_recall(engine, req.thread_id)
        else:
            answer = _answer_broad_recall(engine, req.thread_id)

        # If we have recent context and the broad recall was sparse, enrich
        if recent_context and ("don't have" in answer.lower() or "0 facts" in answer.lower()):
            answer = (
                "Based on what you just shared with me, here's what I know:\n\n"
                + recent_context[:500]
            )
        elif recent_context:
            answer = answer + (
                "\n\nAdditionally, you recently shared more detail about yourself — "
                "I'm processing that into my memory now."
            )

        if greeting_text:
            answer = f"{greeting_text}\n\n{answer}"
        control_state.mark("decide", "ready", detail="broad_recall")
        return _chat_response(
            answer=answer,
            response_type="belief",
            gates_passed=True,
            gate_reason="broad_recall",
            metadata={
                "confidence": 0.90,
                "retrieved_memories": [],
                "prompt_memories": [],
                "recency_context_used": bool(recent_context),
            },
        )

    # Deterministic GroundCheck path for numbered work-plan queries.
    direct_workplan = _try_answer_workplan_question(
        effective_message,
        engine=engine,
        thread_id=req.thread_id,
    )
    if direct_workplan:
        control_state.request_kind = "groundcheck_workplan"
        control_state.mark("bind", "groundcheck_workplan")
        direct_answer = str(direct_workplan.get("answer") or "").strip()
        if greeting_text:
            direct_answer = f"{greeting_text}\n\n{direct_answer}"
        metadata = {
            "mode": "direct_groundcheck_workplan",
            "confidence": 0.98,
            "retrieved_memories": [
                {
                    "memory_id": direct_workplan.get("source_memory_id"),
                    "text": direct_workplan.get("source_text"),
                    "source": "groundcheck",
                    "trust": 0.7,
                    "confidence": 0.98,
                }
            ],
            "prompt_memories": [],
            "groundcheck_bridge": groundcheck_bridge_meta,
            "direct_workplan_items": direct_workplan.get("items") or {},
        }
        if greeting_text:
            metadata["greeting_shown"] = True

        try:
            session_db.record_query(
                thread_id=req.thread_id,
                query_text=req.message,
                response_text=direct_answer,
                detected_slot="work_plan_item",
            )
        except Exception as e:
            logger.debug(f"[SESSION] Error recording direct workplan query: {e}")
        try:
            from personal_agent.training_log import log_chat_turn
            log_chat_turn(
                thread_id=req.thread_id,
                user_message=req.message,
                assistant_response=direct_answer,
                generation_mode="deterministic",
                intent="work_plan_item",
            )
        except Exception:
            pass

        control_state.mark("decide", "ready", detail="groundcheck_workplan_direct")
        control_state.mark("learn", "recorded", detail="session_query")
        return _chat_response(
            answer=direct_answer,
            response_type="speech",
            gates_passed=True,
            gate_reason="groundcheck_workplan_direct",
            metadata=metadata,
        )

    direct_mcp_tools = _try_answer_mcp_tools_question(effective_message)
    if direct_mcp_tools:
        control_state.request_kind = "groundcheck_mcp_tools"
        control_state.mark("bind", "groundcheck_mcp_tools")
        direct_answer = str(direct_mcp_tools.get("answer") or "").strip()
        if greeting_text:
            direct_answer = f"{greeting_text}\n\n{direct_answer}"
        metadata = {
            "mode": "direct_groundcheck_mcp_tools",
            "confidence": 0.97,
            "retrieved_memories": [
                {
                    "memory_id": direct_mcp_tools.get("source_memory_id"),
                    "text": direct_mcp_tools.get("source_text"),
                    "source": "groundcheck",
                    "trust": 0.7,
                    "confidence": 0.97,
                }
            ],
            "prompt_memories": [],
            "groundcheck_bridge": groundcheck_bridge_meta,
            "direct_mcp_tools": direct_mcp_tools.get("tools") or [],
        }
        if greeting_text:
            metadata["greeting_shown"] = True

        try:
            session_db.record_query(
                thread_id=req.thread_id,
                query_text=req.message,
                response_text=direct_answer,
                detected_slot="mcp_tools",
            )
        except Exception as e:
            logger.debug(f"[SESSION] Error recording direct MCP-tools query: {e}")
        try:
            from personal_agent.training_log import log_chat_turn
            log_chat_turn(
                thread_id=req.thread_id,
                user_message=req.message,
                assistant_response=direct_answer,
                generation_mode="deterministic",
                intent="mcp_tools",
            )
        except Exception:
            pass

        control_state.mark("decide", "ready", detail="groundcheck_mcp_tools_direct")
        control_state.mark("learn", "recorded", detail="session_query")
        return _chat_response(
            answer=direct_answer,
            response_type="speech",
            gates_passed=True,
            gate_reason="groundcheck_mcp_tools_direct",
            metadata=metadata,
        )

    tasking_enabled = bool(req.mode and str(req.mode).lower() == "tasking")
    mode_arg = None
    if req.mode and not tasking_enabled:
        try:
            from personal_agent.reasoning import ReasoningMode

            mode_arg = ReasoningMode(req.mode)  # type: ignore[arg-type]
        except Exception:
            mode_arg = None

    # ====== Auto Fact-Check: surface pending corrections from last round ======
    fact_check_preamble = ""
    try:
        from personal_agent.auto_fact_checker import get_pending_fact_checks, resolve_fact_check
        pending = get_pending_fact_checks(thread_id=req.thread_id, limit=3)
        if pending:
            issues = []
            for p in pending:
                issues.append(f"- [{p['issue_type']}] {p['claim']}")
                resolve_fact_check(p["id"], resolution="surfaced")
            fact_check_preamble = (
                "\n\n[SYSTEM NOTE — self-correction from previous response: "
                "The following issues were detected in a prior answer. "
                "If relevant to this question, acknowledge and correct them. "
                "If not relevant, ignore silently.]\n"
                + "\n".join(issues)
                + "\n"
            )
    except Exception as e:
        logger.debug(f"[AUTO_FC] Error surfacing pending checks: {e}")

    query_with_context = effective_message
    if fact_check_preamble:
        query_with_context = effective_message + fact_check_preamble

    # Self-awareness injection now happens in reasoning.py/_build_quick_prompt
    # where the system prompt is assembled. No separate variable needed here.

    # Pass structured history for proper multi-turn chat; keep text
    # augmentation as fallback context in the query itself.
    if pending_followup_context is not None:
        query_with_context = _augment_query_with_pending_followup(
            message=query_with_context,
            pending_context=pending_followup_context,
        )
    query_with_continuity = _augment_query_with_continuity(
        message=query_with_context,
        history_messages=recent_history,
    )
    # --- Governance: ContinuityAuditor (Law 6) ---
    # Check if we've answered this question before and inject prior-response context.
    _continuity_verdict = None
    if _LEGACY_GOVERNANCE:
        try:
            _continuity_verdict = _LEGACY_GOVERNANCE.govern_continuity(
                query=effective_message,
                thread_id=req.thread_id,
            )
            if _continuity_verdict and _continuity_verdict.action == "inject" and _continuity_verdict.continuity_context:
                query_with_continuity = (
                    query_with_continuity
                    + "\n\n[CONTINUITY — prior responses on this topic]\n"
                    + _continuity_verdict.continuity_context
                )
                logger.info("[CONTINUITY] Injected %d chars of prior-response context (similarity=%.2f)",
                            len(_continuity_verdict.continuity_context),
                            _continuity_verdict.max_similarity)
            elif _continuity_verdict and _continuity_verdict.action == "hedge":
                logger.info("[CONTINUITY] Prior responses conflict — will hedge (consistency=%.2f)",
                            _continuity_verdict.internal_consistency)
        except Exception as _cont_err:
            logger.debug("[CONTINUITY] Auditor check failed: %s", _cont_err)
    _gpt_reference_packet = None
    _gpt_reference_from_cache = False
    _history_ref_query, _history_ref_topic, _history_ref_inferred = _resolve_personal_history_reference(
        effective_message,
        recent_history,
    )
    if _history_ref_query:
        try:
            _emit_pipeline_status("checking archived GPT history")
            _emit_pipeline_event({
                "type": "intent_preview",
                "content": (
                    "This sounds like a follow-up to your earlier health-history thread, so I'm pulling that context back in before I answer."
                    if _history_ref_inferred and _history_ref_topic == "health_history"
                    else "I only have partial settled memory here, so I'm checking your GPT history for relevant context before I answer."
                ),
                "metadata": {
                    "intent": "gpt_reference_lookup",
                    "topic": _history_ref_topic,
                    "inferred_from_followup": _history_ref_inferred,
                },
            })
            _gpt_reference_packet, _gpt_reference_from_cache = _get_or_build_gpt_reference_packet(
                req.thread_id,
                _history_ref_query,
            )
            if _gpt_reference_packet:
                query_with_continuity = (
                    query_with_continuity
                    + "\n\n"
                    + _build_gpt_reference_context_block(_gpt_reference_packet)
                )
                _emit_pipeline_status(
                    "loaded archived GPT context"
                    if _gpt_reference_from_cache
                    else "found archived GPT context"
                )
        except Exception as _gpt_ref_err:
            logger.debug("[GPT_REF] preload failed: %s", _gpt_ref_err)
    control_state.mark(
        "bind",
        "context_ready",
        continuity_applied=(query_with_continuity != query_with_context),
        recent_messages=len(recent_history),
    )

    _mark("pre_generation_context_ready")
    # ── PARALLEL FETCH: preference profile + model routing ──────────
    # These are independent I/O calls that were previously serial.
    # ThreadPoolExecutor runs them concurrently for ~30-100ms savings.
    import concurrent.futures
    _pref_profile_result = [None]
    def _fetch_pref():
        _pref_profile_result[0] = _get_preference_profile(req.thread_id, engine.memory)
    _pref_thread = threading.Thread(target=_fetch_pref, daemon=True)
    _pref_thread.start()
    # While pref loads, we can't route yet (depends on pref), but we can
    # do other pre-generation prep that was previously after routing.
    _pref_thread.join(timeout=5.0)
    preference_profile = _pref_profile_result[0]
    model_override, model_route = _route_model_for_request(
        request,
        query=effective_message,
        mode=req.mode,
        preference_profile=preference_profile,
        channel=req.channel,
    )

    # ====== BYPASS CRT MODE ======
    # When bypass_crt is enabled and a cloud model is selected, skip the
    # entire CRT pipeline (memory, contradiction detection, gates, trust)
    # and send the user message directly to the raw cloud model.
    _bypass_crt = False
    try:
        import auth as _auth_bypass
        _uid_bypass = int(uid) if uid else 1
        _bypass_crt = str(
            _auth_bypass.get_user_setting(_uid_bypass, "bypass_crt", "false")
        ).lower() in ("true", "1", "yes", "on")
        _bypass_gen_mode = str(
            _auth_bypass.get_user_setting(_uid_bypass, "generation_mode", "cloud_openai") or "cloud_openai"
        ).strip()
        if _bypass_gen_mode == "local_network":
            _bypass_gen_mode = "local"
    except Exception as _bp_err:
        _safe_print(f"[BYPASS_CRT] Settings check failed: {_bp_err}")
        _bypass_gen_mode = "cloud_openai"

    if _bypass_crt and _bypass_gen_mode in ("cloud_openai", "cloud_claude"):
        _safe_print(f"[BYPASS_CRT] Raw cloud mode — skipping CRT pipeline, model={_bypass_gen_mode}")
        control_state.mark("generate", "drafting", detail="bypass_crt_raw")
        try:
            from personal_agent.cloud_features import get_cloud_feature_service
            import auth as _auth_bp2
            _bp_svc = get_cloud_feature_service()
            _bp_provider = "openai" if _bypass_gen_mode == "cloud_openai" else "claude"
            _bp_model_key = "cloud_model_openai" if _bp_provider == "openai" else "cloud_model_claude"
            _bp_model_default = "gpt-4o-mini" if _bp_provider == "openai" else "claude-opus-4-5"
            _bp_cloud_model = str(_auth_bp2.get_user_setting(_uid_bypass, _bp_model_key, _bp_model_default) or _bp_model_default)

            # Build minimal prompt with conversation history (no CRT context)
            _bp_prompt_parts = []
            if recent_history:
                for _turn in recent_history[-6:]:
                    _role = _turn.get("role", "user")
                    _content = (_turn.get("content") or "").strip()
                    if _content and _role in ("user", "assistant"):
                        _bp_prompt_parts.append(f"{'User' if _role == 'user' else 'Aether'}: {_content[:500]}")
            _bp_prompt_parts.append(f"User: {effective_message}")
            _bp_prompt = "\n".join(_bp_prompt_parts)

            # Build system prompt with static/dynamic boundary
            from personal_agent.prompt_prefix import build_system_prompt as _bp_build
            _bp_dynamic = []
            try:
                _bp_token_est = len(effective_message) // 4
                if _bp_history:
                    for _bh in _bp_history[-6:]:
                        _bp_token_est += len(str(_bh.get("content", ""))) // 4

                if _bp_token_est > 2000:
                    from personal_agent.context_feed import build_compacted_context
                    _bp_ctx = build_compacted_context(
                        thread_id=req.thread_id,
                        memory_db_path=engine.memory.db_path,
                        token_budget=max(2000, 4000 - _bp_token_est),
                        trigger="token_overflow",
                    )
                else:
                    from personal_agent.context_feed import build_context_summary
                    _bp_ctx = build_context_summary(
                        thread_id=req.thread_id,
                        memory_db_path=engine.memory.db_path,
                    )
                if _bp_ctx:
                    _bp_dynamic.append(_bp_ctx)
            except Exception:
                pass
            # Gravity topology
            try:
                from personal_agent._gravity_singleton import get_gravity_bridge
                _gravity = get_gravity_bridge()
                if _gravity is not None:
                    _grav_sec = _gravity.prompt_section(max_rooms=8)
                    if _grav_sec:
                        _bp_dynamic.append(_grav_sec)
            except Exception:
                pass

            _bp_system = _bp_build(dynamic_parts=_bp_dynamic)

            _bp_answer = None
            if _bp_svc is not None:
                _bp_answer = _bp_svc.generate_full_response(
                    prompt=_bp_prompt,
                    system_prompt=_bp_system,
                    provider=_bp_provider,
                    model=_bp_cloud_model,
                    max_tokens=4096,
                )
            if _bp_answer:
                _safe_print(f"[BYPASS_CRT] Raw response — {len(_bp_answer)} chars via {_bp_provider}")
                try:
                    session_db.record_query(
                        thread_id=req.thread_id,
                        query_text=req.message,
                        response_text=_bp_answer,
                        detected_slot="bypass_crt",
                    )
                except Exception:
                    pass
                try:
                    from personal_agent.training_log import log_chat_turn
                    log_chat_turn(
                        thread_id=req.thread_id,
                        user_message=req.message,
                        assistant_response=_bp_answer,
                        model_used=_bp_cloud_model,
                        generation_mode=f"bypass_{_bp_provider}",
                        intent="bypass",
                    )
                except Exception:
                    pass
                control_state.mark("generate", "draft_ready", detail="bypass_crt_done")
                control_state.mark("decide", "ready", detail="bypass_crt")
                control_state.mark("learn", "recorded", detail="bypass_crt")
                return _chat_response(
                    answer=_bp_answer,
                    response_type="bypass",
                    gates_passed=True,
                    gate_reason="bypass_crt_raw",
                    metadata={
                        "generation_source": f"bypass_{_bp_provider}",
                        "cloud_model": _bp_cloud_model,
                        "bypass_crt": True,
                    },
                )
            else:
                print("[BYPASS_CRT] Cloud returned None, falling through to CRT pipeline")
        except Exception as _bp_gen_err:
            _safe_print(f"[BYPASS_CRT] Raw generation failed: {_bp_gen_err}, falling through to CRT")

    # ── Inject recent tool result context for follow-up questions ────────
    # If the user's last turn was a tool execution (system_info, file_read, etc.)
    # and this message is a conversational follow-up, inject the tool output
    # so the LLM can reference it.
    try:
        _recent_task = session_db.get_pending_task(req.thread_id)
        if _recent_task and _recent_task.get("status") == "completed":
            import time as _time_mod
            _task_age = _time_mod.time() - (_recent_task.get("updated_at") or 0)
            if _task_age < 120:  # within 2 minutes
                _task_type = _recent_task.get("intent_type", "")
                _completed_steps = _recent_task.get("steps_completed") or []
                _tool_summaries = []
                for _step in _completed_steps[-3:]:  # last 3 steps max
                    _preview = _step.get("output_preview") or _step.get("output", "")
                    if isinstance(_preview, str) and len(_preview) > 800:
                        _preview = _preview[:800] + "..."
                    if _preview:
                        _tool_summaries.append(f"[{_step.get('tool_name', 'tool')}]: {_preview}")
                if _tool_summaries:
                    _context_block = (
                        f"\n\n[Recent tool results from {_task_type} task — use this to answer follow-up questions]\n"
                        + "\n".join(_tool_summaries)
                    )
                    query_with_continuity = query_with_continuity + _context_block
                    logger.info("[STREAM] Injected recent %s tool context (%d chars) for follow-up",
                                _task_type, len(_context_block))
    except Exception as _rtc_err:
        logger.debug("[STREAM] Recent tool context injection failed: %s", _rtc_err)

    control_state.mark("generate", "drafting", detail="engine_query")
    result = engine.query(
        user_query=query_with_continuity,
        user_marked_important=req.user_marked_important,
        mode=mode_arg,
        thread_id=req.thread_id,
        model_override=model_override,
        conversation_history=recent_history or None,
        channel=req.channel,
        origin=req.origin,
        authority=req.authority,
        kind=req.kind,
    )
    if _gpt_reference_packet is not None:
        result["gpt_reference_packet"] = _gpt_reference_packet
        result["gpt_reference_from_cache"] = _gpt_reference_from_cache
        if _history_answer_is_weak(result):
            result["answer"] = _build_gpt_reference_answer(
                _gpt_reference_packet,
                from_cache=_gpt_reference_from_cache,
            )
            result["response_type"] = "reference"
            result["gates_passed"] = True
            result["gate_reason"] = "gpt_reference_cache"
    _mark("engine_query_done")
    # Emit memory retrieval count
    _mem_retrieved_count = len(result.get("retrieved_memories") or []) + len(result.get("prompt_memories") or [])
    if _mem_retrieved_count > 0:
        _emit_pipeline_status(f"{_mem_retrieved_count} memories retrieved")
        # Emit structured retrieval event for live trust bar display
        _retrieval_mems = result.get("retrieved_memories") or result.get("prompt_memories") or []
        _emit_pipeline_event({
            "type": "retrieval",
            "content": f"{_mem_retrieved_count} memories",
            "metadata": {
                "memories": [
                    {
                        "id": str(m.get("memory_id") or m.get("id") or ""),
                        "text": (str(m.get("text") or ""))[:120],
                        "trust": round(float(m.get("trust") or 0.5), 3),
                        "kind": str(m.get("kind") or "observation"),
                        "pca_x": float(m.get("pca_x") or 0.0),
                        "pca_y": float(m.get("pca_y") or 0.0),
                        "score": round(float(m.get("score") or 0.0), 3),
                    }
                    for m in _retrieval_mems[:8]
                ],
                "edges": result.get("retrieval_edges") or [],
            },
        })

    # ====== PRIMARY CLOUD GENERATION MODE ======
    # If the user has selected cloud as their PRIMARY generator, replace the
    # local LLM answer with a cloud-generated one. The full CRT pipeline
    # (memory retrieval, trust scoring, contradiction detection, gate checks,
    # NLI verification, slot classification) has already run via engine.query().
    # We just swap the vocal cords — the control plane stays intact.
    _gen_phase_t0 = time.perf_counter()
    _gen_tracking = {"gen": "local", "slots": "none", "nli": "none", "escalation": "none"}
    _escalation_decision = None
    try:
        import auth as _auth_gen
        _uid_gen = int(uid) if uid else 1
        _generation_mode = resolve_effective_generation_mode(req, uid)
        # Normalize local_network → local for routing purposes (same Ollama backend, URL set via OLLAMA_BASE_URL)
        if _generation_mode == "local_network":
            _generation_mode = "local"
        _safe_print(f"[GENERATION] mode_select: generation_mode={_generation_mode}, uid={_uid_gen}")

        # ── STRUCTURAL GOVERNANCE: Confidence-gated response depth ──────
        # Compute belief confidence from retrieved memories BEFORE generation.
        # If confidence is low, structurally constrain the response:
        # - Cap max_tokens so the model can't produce long assertive answers
        # - Inject a hedge prefix so the model frames uncertainty honestly
        # This is architectural, not advisory — the constraint lives in the
        # execution context, not in the prompt instructions.
        _pre_gen_mems = result.get("retrieved_memories") or result.get("prompt_memories") or []
        _pre_gen_belief = 0.4  # default: no memories = low confidence
        if _pre_gen_mems and isinstance(_pre_gen_mems, list):
            _valid_mems = [m for m in _pre_gen_mems if isinstance(m, dict)]
            if _valid_mems:
                _avg_trust = sum(m.get("trust", 0.5) for m in _valid_mems) / len(_valid_mems)
                _pre_gen_belief = min(0.85, 0.3 + 0.05 * len(_valid_mems) + _avg_trust * 0.2)
        result["pre_gen_belief"] = round(_pre_gen_belief, 3)

        # ── Adaptive depth: gravity-aware token budget ──
        # Base: smooth power-law curve from belief confidence.
        # Modifier: memory density (more grounded memories = more room to elaborate).
        # Dense room + high trust = go deep. Sparse room = cut short.
        _MIN_TOKENS = 100
        _MAX_TOKENS = 4096
        _base_tokens = int(_MIN_TOKENS + (_MAX_TOKENS - _MIN_TOKENS) * min(1.0, _pre_gen_belief ** 0.7))

        # Memory density bonus: scale depth by how many high-trust memories ground this response
        _mem_count = len(result.get("retrieved_memories") or result.get("prompt_memories") or [])
        _high_trust_mems = sum(
            1 for m in (result.get("retrieved_memories") or result.get("prompt_memories") or [])
            if isinstance(m, dict) and (m.get("trust") or 0) > 0.7
        )
        # 0 memories = no bonus. 5+ high-trust = up to 40% more tokens.
        _density_multiplier = 1.0 + min(0.4, _high_trust_mems * 0.08)
        _confidence_max_tokens = min(_MAX_TOKENS, int(_base_tokens * _density_multiplier))
        _confidence_gate_active = _pre_gen_belief < 0.35  # only hedge below 0.35
        _confidence_hedge = ""
        if _confidence_gate_active:
            _confidence_hedge = (
                "[Note: I have low confidence in this answer — my memory evidence is weak or absent. "
                "I'll keep it brief and honest about what I don't know.]\n\n"
            )

        # ── Cap reasoning mode by confidence ──
        # Don't allow deep/research reasoning when evidence is weak.
        _effective_reasoning_mode = str(mode_arg.value if mode_arg else "quick")
        if _pre_gen_belief < 0.3:
            _effective_reasoning_mode = "quick"  # weak evidence → don't reason deeply
        elif _pre_gen_belief < 0.5 and _effective_reasoning_mode in ("deep", "research"):
            _effective_reasoning_mode = "thinking"  # cap at thinking for medium confidence
        # else: allow user-requested mode
        result["effective_reasoning_mode"] = _effective_reasoning_mode

        logger.info(f"[ADAPTIVE_DEPTH] belief={_pre_gen_belief:.2f} tokens={_confidence_max_tokens} mode={_effective_reasoning_mode} gate={'active' if _confidence_gate_active else 'off'}")
        _safe_print(f"[STRUCTURAL_GATE] adaptive: belief={_pre_gen_belief:.2f} → tokens={_confidence_max_tokens}, mode={_effective_reasoning_mode}, gate={'active' if _confidence_gate_active else 'off'}")

        _emit_pipeline_event({
            "type": "status",
            "content": f"depth: {_confidence_max_tokens} tokens (belief={_pre_gen_belief:.2f})",
        })

        _emit_pipeline_status(f"generating ({_generation_mode})")

        # --- Escalation policy: may promote local → cloud for this request ---
        _escalation_decision = None
        try:
            from personal_agent.escalation_policy import get_escalation_policy
            _esc_policy = get_escalation_policy()
            # Rough token estimate: ~4 chars per token
            _token_est = len(effective_message) // 4
            if recent_history:
                for _h in recent_history[-6:]:
                    _token_est += len(str(_h.get("content", ""))) // 4
            _pc_mems = result.get("retrieved_memories") or result.get("prompt_memories") or []
            for _m in (_pc_mems[:10] if isinstance(_pc_mems, list) else []):
                _token_est += len(str(_m.get("text", ""))) // 4

            # Count recent cloud turns for conversation momentum
            _recent_cloud = 0
            try:
                for _rh in (recent_history or [])[-3:]:
                    _rh_meta = _rh.get("metadata") or _rh.get("meta") or {}
                    if isinstance(_rh_meta, dict):
                        _gs = str(_rh_meta.get("generation_source") or _rh_meta.get("generation_provider") or "")
                        if "cloud" in _gs or "claude" in _gs or "openai" in _gs or "agent_loop" in _gs:
                            _recent_cloud += 1
            except Exception:
                pass

            _escalation_decision = _esc_policy.decide(
                query=effective_message,
                generation_mode=_generation_mode,
                context_token_estimate=_token_est,
                gate_boost=getattr(engine, '_last_behavioral_directives', {}).get('gate_boost', 0.0) if hasattr(engine, '_last_behavioral_directives') else 0.0,
                recent_cloud_turns=_recent_cloud,
            )
            result["escalation"] = _escalation_decision.to_dict()

            # --- Emotional routing: advisory escalation based on conversation emotional state ---
            try:
                from personal_agent.emotional_router import (
                    get_emotional_router, compute_emotional_state,
                )

                # Gather emotional signals from existing detectors
                _emo_mood = None
                _emo_volatility = 0.0
                _emo_urgency = "NONE"
                _emo_tensions = []
                _emo_cascade_pressure = 0.0
                _emo_held_contradictions = 0
                _emo_drift_severity = 0.0

                # Mood: detect from last assistant response in history
                try:
                    _last_assistant = ""
                    for _rh in reversed(recent_history or []):
                        if _rh.get("role") == "assistant":
                            _last_assistant = str(_rh.get("content", ""))[:1000]
                            break
                    if _last_assistant:
                        _emo_mood = _detect_response_mood(_last_assistant)
                except Exception:
                    pass

                # Volatility: from result context if available
                try:
                    _emo_volatility = float(
                        result.get("volatility_context", {}).get("volatility", 0.0)
                        if isinstance(result.get("volatility_context"), dict)
                        else 0.0
                    )
                except Exception:
                    pass

                # Urgency: from active inference if available
                try:
                    _ai_ctx = result.get("active_inference") or {}
                    if isinstance(_ai_ctx, dict):
                        _top_inq = (_ai_ctx.get("inquiries") or [None])[0] if _ai_ctx.get("inquiries") else None
                        if _top_inq and hasattr(_top_inq, "urgency"):
                            _emo_urgency = str(_top_inq.urgency.value).upper()
                        elif isinstance(_top_inq, dict):
                            _emo_urgency = str(_top_inq.get("urgency", "NONE")).upper()
                except Exception:
                    pass

                # Held contradictions from ledger
                try:
                    _emo_open = engine.ledger.get_open_contradictions(limit=50)
                    _emo_held_contradictions = sum(
                        1 for _c in _emo_open
                        if str(getattr(_c, "status", "")).lower() == "both"
                    )
                except Exception:
                    pass

                # Cascade pressure from result
                try:
                    _cas = result.get("cascade_result") or {}
                    if isinstance(_cas, dict):
                        _emo_cascade_pressure = float(_cas.get("max_pressure", 0.0))
                except Exception:
                    pass

                # Drift severity
                try:
                    _drift_ctx = result.get("drift") or {}
                    if isinstance(_drift_ctx, dict):
                        _emo_drift_severity = float(_drift_ctx.get("alignment", 0.0))
                except Exception:
                    pass

                _emo_state = compute_emotional_state(
                    mood_result=_emo_mood,
                    volatility=_emo_volatility,
                    urgency=_emo_urgency,
                    tensions=_emo_tensions,
                    cascade_pressure=_emo_cascade_pressure,
                    held_contradictions=_emo_held_contradictions,
                    drift_severity=_emo_drift_severity,
                )

                _emo_router = get_emotional_router()
                _emo_result = _emo_router.apply_to_decision(
                    state=_emo_state,
                    current_tier=_escalation_decision.start_tier,
                    current_reason=_escalation_decision.reason,
                )

                if _emo_result["escalated"]:
                    _escalation_decision.start_tier = _emo_result["new_tier"]
                    _escalation_decision.reason += _emo_result["reason_suffix"]
                    _escalation_decision.boosted = True
                    result["escalation"] = _escalation_decision.to_dict()

                result["emotional_routing"] = {
                    "state": _emo_state.to_dict(),
                    "recommendation": _emo_result["recommendation"].to_dict(),
                    "escalated": _emo_result["escalated"],
                }
            except Exception as _emo_err:
                logger.debug("[EMOTIONAL_ROUTING] error: %s", _emo_err)

            # Promote local → cloud if escalation says so
            # But respect "local_only" escalation policy — never promote
            _user_esc_policy = str(
                _auth_gen.get_user_setting(_uid_gen, "cloud_escalation_policy", "conservative")
            ).lower().strip()
            if (
                _generation_mode == "local"
                and _escalation_decision.start_tier != "local"
                and _user_esc_policy != "local_only"
            ):
                _promoted_tier = _escalation_decision.start_tier
                _generation_mode = f"cloud_{_promoted_tier}"
                _safe_print(f"[ESCALATION] promoted: local -> {_generation_mode} (reason: {_escalation_decision.reason})")
                _gen_tracking["escalation"] = f"promoted_{_escalation_decision.start_tier}"
            elif _generation_mode == "local" and _escalation_decision.start_tier != "local" and _user_esc_policy == "local_only":
                _safe_print(f"[ESCALATION] blocked: local_only policy (would have been: {_escalation_decision.start_tier})")
                _gen_tracking["escalation"] = "blocked_local_only"
        except Exception as _esc_err:
            _safe_print(f"[ESCALATION] error: {_esc_err}")

        if _generation_mode in ("cloud_openai", "cloud_claude"):
            from personal_agent.cloud_features import get_cloud_feature_service
            _primary_cloud_svc = get_cloud_feature_service()
            if _primary_cloud_svc is not None:
                _provider = "openai" if _generation_mode == "cloud_openai" else "claude"
                _model_key = "cloud_model_openai" if _provider == "openai" else "cloud_model_claude"
                _model_default = "gpt-4o-mini" if _provider == "openai" else "claude-opus-4-5"
                _cloud_model = str(_auth_gen.get_user_setting(_uid_gen, _model_key, _model_default) or _model_default)

                # Build the same rich context the local LLM would see
                _pc_memories = result.get("retrieved_memories") or result.get("prompt_memories") or []
                _pc_history = recent_history or None
                _pc_self_model = None
                try:
                    from personal_agent.self_model import get_self_model
                    _sm = get_self_model()
                    if _sm:
                        _pc_self_model = {
                            "top_facts": [str(f) for f in (_sm.get_top_facts(5) or [])],
                        }
                except Exception:
                    pass

                # Build system prompt for cloud primary generation.
                # This is a standard product integration — Claude serves as the
                # language generation backend for the Aether product, the same way
                # it powers Cursor, Notion AI, and thousands of other products.
                # Build system prompt with static/dynamic boundary
                from personal_agent.prompt_prefix import build_system_prompt

                # --- Dynamic evidence section ---
                import datetime as _dt_sys
                _dynamic_parts = []

                # Current time
                _now = _dt_sys.datetime.now()
                _dynamic_parts.append(f"Current date and time: {_now.strftime('%A, %B %d, %Y at %I:%M %p')}")

                # Retrieved memories with trust scores
                if _pc_memories:
                    from personal_agent.crt_memory import sanitize_memory_for_prompt as _sanitize_mem
                    _mem_lines = [
                        "Facts about the user Nick (these are HIS words and experiences, not yours):",
                        "When referencing these, say 'you said' or 'you mentioned' — never 'I believe' or 'I expressed'.",
                    ]
                    # Detect corrections/negations and promote to hard constraints
                    _NEG_PREFIXES = ("i do not ", "i don't ", "i am not ", "i'm not ",
                                     "not a ", "never ", "nick does not ", "nick is not ")
                    _correction_lines = []
                    for _m in (list(_pc_memories) if isinstance(_pc_memories, list) else [])[:10]:
                        _mt = (_m.get("text") or "").strip()
                        if any(_mt.lower().startswith(p) for p in _NEG_PREFIXES):
                            _correction_lines.append(f"  >>> CORRECTION: Nick: {_sanitize_mem(_mt[:250])}")
                    if _correction_lines:
                        _mem_lines.append("")
                        _mem_lines.append("IMPORTANT CORRECTIONS (override conflicting memories):")
                        _mem_lines.extend(_correction_lines)
                    for _m in (list(_pc_memories) if isinstance(_pc_memories, list) else [])[:10]:
                        _mt = (_m.get("text") or "").strip()
                        _mt = _sanitize_mem(_mt)
                        _mtr = _m.get("trust")
                        if _mt:
                            _trust_tag = f" [trust={_mtr:.2f}]" if _mtr is not None else ""
                            _mem_lines.append(f"- Nick: {_mt[:250]}{_trust_tag}")
                    if len(_mem_lines) > 1:
                        _dynamic_parts.append("\n".join(_mem_lines))

                _gpt_ref_packet = result.get("gpt_reference_packet")
                if isinstance(_gpt_ref_packet, dict):
                    _dynamic_parts.append(_build_gpt_reference_context_block(_gpt_ref_packet))

                # Self-model traits
                if _pc_self_model:
                    _traits = _pc_self_model.get("top_facts") or []
                    if _traits:
                        _trait_lines = ["Your self-model (what you know about yourself):"]
                        _trait_lines.extend(f"- {t}" for t in _traits[:5] if isinstance(t, str))
                        if len(_trait_lines) > 1:
                            _dynamic_parts.append("\n".join(_trait_lines))

                # Context feed (regular or compacted)
                try:
                    if _token_est > 2000:
                        from personal_agent.context_feed import build_compacted_context
                        _ctx_summary = build_compacted_context(
                            thread_id=req.thread_id,
                            memory_db_path=engine.memory.db_path,
                            token_budget=max(2000, 4000 - _token_est),
                            trigger="token_overflow",
                        )
                        if _ctx_summary:
                            _safe_print(f"[CONTEXT_FEED] compacted context injected ({len(_ctx_summary)} chars)")
                    else:
                        from personal_agent.context_feed import build_context_summary
                        _ctx_summary = build_context_summary(
                            thread_id=req.thread_id,
                            memory_db_path=engine.memory.db_path,
                        )
                    if _ctx_summary:
                        _dynamic_parts.append(_ctx_summary)
                except Exception as _ctx_err:
                    _safe_print(f"[CONTEXT_FEED] injection failed: {_ctx_err}")

                # Gravity topology — belief structure awareness
                try:
                    from personal_agent._gravity_singleton import get_gravity_bridge
                    _gravity = get_gravity_bridge()
                    if _gravity is not None:
                        _gravity_section = _gravity.prompt_section(max_rooms=8)
                        if _gravity_section:
                            _dynamic_parts.append(_gravity_section)
                except Exception as _grav_prompt_err:
                    pass  # Non-blocking

                _pc_system = build_system_prompt(dynamic_parts=_dynamic_parts)

                # Build prompt with conversation history
                _pc_prompt_parts = []
                if _pc_history:
                    for _turn in _pc_history[-6:]:
                        _role = _turn.get("role", "user")
                        _content = (_turn.get("content") or "").strip()
                        if _content and _role in ("user", "assistant"):
                            _pc_prompt_parts.append(f"{'User' if _role == 'user' else 'Aether'}: {_content[:500]}")
                _pc_prompt_parts.append(f"User: {effective_message}")
                _pc_prompt = "\n".join(_pc_prompt_parts)

                _safe_print(f"[GENERATION] cloud_primary: using {_provider} ({_cloud_model})")
                # Apply confidence gate: inject hedge prefix if low confidence
                if _confidence_hedge:
                    _pc_prompt = _confidence_hedge + _pc_prompt
                _t_primary = time.perf_counter()
                _cloud_primary_answer = _primary_cloud_svc.generate_full_response(
                    prompt=_pc_prompt,
                    system_prompt=_pc_system,
                    provider=_provider,
                    model=_cloud_model,
                    max_tokens=_confidence_max_tokens,
                )
                _lat_primary = int((time.perf_counter() - _t_primary) * 1000)
                if _cloud_primary_answer:
                    result["answer"] = _cloud_primary_answer
                    result["generation_source"] = _generation_mode
                    _gen_tracking["gen"] = _generation_mode
                    # Cloud succeeded — clear any local gate failure so the
                    # cloud answer actually gets shown to the user.
                    if not result.get("gates_passed", True):
                        _safe_print(f"[GENERATION] cloud_primary: cleared local gate failure ({result.get('gate_reason')})")
                        result["gates_passed"] = True
                        result["gate_reason"] = "cloud_primary_override"
                    _safe_print(f"[GENERATION] cloud_primary: success, {len(_cloud_primary_answer)} chars via {_provider}")
                    try:
                        _esc_policy.record_success(_provider)
                    except Exception:
                        pass
                    try:
                        _track_cloud_call(
                            call_type=f"generation_primary_{_provider}",
                            provider=_provider, model=_cloud_model,
                            latency_ms=_lat_primary, success=True,
                            thread_id=req.thread_id, uid=int(uid) if uid else None,
                            input_text=_pc_prompt, output_text=_cloud_primary_answer,
                            escalation_reason=str((result.get("escalation") or {}).get("reason", "")),
                            user_message=effective_message,
                        )
                    except Exception:
                        pass
                else:
                    _safe_print(f"[GENERATION] cloud_primary: {_provider} returned None, keeping local answer")
                    try:
                        _esc_policy.record_failure(_provider, "returned_none")
                    except Exception:
                        pass
                    try:
                        _track_cloud_call(
                            call_type=f"generation_primary_{_provider}",
                            provider=_provider, model=_cloud_model,
                            latency_ms=_lat_primary, success=False,
                            thread_id=req.thread_id, uid=int(uid) if uid else None,
                            input_text=_pc_prompt, error_type="returned_none",
                            user_message=effective_message,
                        )
                    except Exception:
                        pass
            else:
                print("[GENERATION] cloud_primary: cloud service not initialized, using local")
    except Exception as _gen_mode_err:
        _safe_print(f"[GENERATION] error: generation mode check failed: {_gen_mode_err}")

    # ====== CLOUD GENERATION FALLBACK ======
    # If local LLM returned an error (timeout, connection refused, etc.),
    # fall back to cloud generation instead of leaking the error to the user.
    # The CRT control plane stays local — cloud is just the vocal cords.
    _raw_answer = str(result.get("answer") or "")
    _is_llm_error = (
        _raw_answer.startswith("[Ollama error:")
        or _raw_answer.startswith("[Ollama connection error:")
        or _raw_answer.startswith("[LLM error:")
        or _raw_answer.startswith("[Model '")
        or _raw_answer.startswith("[No LLM available")
        or _raw_answer.startswith("[Cloud LLM error:")
    )
    # Also catch gate-fail with empty/error responses — the engine returned
    # an empty or error answer before cloud had a chance to help.
    # Note: "no_memories_local_generation" means local model succeeded without
    # memories — do NOT fall back to cloud for that case.
    _gate_reason_str = str(result.get("gate_reason") or "")
    _is_gate_fail_empty = (
        not _is_llm_error
        and not result.get("gates_passed", True)
        and _gate_reason_str != "no_memories_local_generation"
        and (
            not _raw_answer.strip()
            or _gate_reason_str == "No memories available"
        )
    )
    if _is_llm_error or _is_gate_fail_empty:
        _fallback_reason = "LLM error" if _is_llm_error else f"gate fail ({result.get('gate_reason', 'empty')})"
        _safe_print(f"[GENERATION] fallback: local failed ({_fallback_reason}): {_raw_answer[:120]}")
        # Record local failure for circuit breaker
        try:
            _esc_policy.record_failure("local", "timeout" if "timeout" in _raw_answer.lower() else "error")
        except Exception:
            pass
        try:
            import auth as _auth_cg
            _uid_cg = int(uid) if uid else 1
            _cloud_gen_enabled = str(
                _auth_cg.get_user_setting(_uid_cg, "cloud_generation_fallback", "true")
            ).lower() in ("true", "1", "yes", "on")
            _user_gen_mode = resolve_effective_generation_mode(req, uid)
            if not is_cloud_fallback_allowed(req, _uid_cg):
                _cloud_gen_enabled = False
                print(f"[GENERATION] fallback: blocked for effective local-only routing (generation_mode={_user_gen_mode})")
            if _cloud_gen_enabled:
                from personal_agent.cloud_features import get_cloud_feature_service
                _cloud_gen_svc = get_cloud_feature_service()
                if _cloud_gen_svc is not None:
                    print("[GENERATION] fallback: trying OpenAI after local failure")
                    # Gather context for the cloud prompt
                    _cg_memories = result.get("retrieved_memories") or result.get("prompt_memories") or []
                    _cg_history = recent_history or None
                    # Try to get self-model snapshot
                    _cg_self_model = None
                    try:
                        from personal_agent.self_model import get_self_model
                        _sm = get_self_model()
                        if _sm:
                            _cg_self_model = {
                                "top_facts": [str(f) for f in (_sm.get_top_facts(5) or [])],
                            }
                    except Exception:
                        pass
                    _t_fb = time.perf_counter()
                    _cloud_answer = _cloud_gen_svc.generate_response(
                        user_message=effective_message,
                        retrieved_memories=_cg_memories if isinstance(_cg_memories, list) else [],
                        conversation_history=_cg_history,
                        self_model_snapshot=_cg_self_model,
                    )
                    _lat_fb = int((time.perf_counter() - _t_fb) * 1000)
                    if _cloud_answer:
                        result["answer"] = _cloud_answer
                        result["generation_source"] = "cloud_fallback"
                        _gen_tracking["gen"] = "cloud_fallback"
                        # Clear gate-fail state — cloud provided a valid answer
                        if _is_gate_fail_empty:
                            result["gates_passed"] = True
                            result["gate_reason"] = "cloud_fallback_recovery"
                        _safe_print(f"[GENERATION] fallback: OpenAI succeeded, {len(_cloud_answer)} chars")
                        try:
                            _esc_policy.record_success("openai")
                        except Exception:
                            pass
                        try:
                            _track_cloud_call(
                                call_type="generation_fallback",
                                provider="openai", model="gpt-4o-mini",
                                latency_ms=_lat_fb, success=True,
                                thread_id=req.thread_id, uid=int(uid) if uid else None,
                                output_text=_cloud_answer,
                                escalation_reason=_fallback_reason,
                                user_message=effective_message,
                            )
                        except Exception:
                            pass
                    else:
                        # OpenAI failed — escalate to Claude (Tier 2) if enabled
                        print("[GENERATION] fallback: OpenAI returned None, escalating to Claude (Tier 2)")
                        try:
                            _esc_policy.record_failure("openai", "returned_none")
                        except Exception:
                            pass
                        try:
                            _track_cloud_call(
                                call_type="generation_fallback",
                                provider="openai", model="gpt-4o-mini",
                                latency_ms=_lat_fb, success=False,
                                thread_id=req.thread_id, uid=int(uid) if uid else None,
                                error_type="returned_none",
                                escalation_reason=_fallback_reason,
                                user_message=effective_message,
                            )
                        except Exception:
                            pass
                        # Check if Claude is enabled before calling
                        _claude_enabled = str(
                            _auth_cg.get_user_setting(_uid_cg, "cloud_claude_enabled", "false")
                        ).lower() in ("true", "1", "yes", "on")
                        if not _claude_enabled:
                            print("[GENERATION] fallback: Claude disabled by user setting, skipping Tier 2")
                        else:
                            _t_cfb = time.perf_counter()
                            _claude_answer = _cloud_gen_svc.generate_response_claude(
                                user_message=effective_message,
                                retrieved_memories=_cg_memories if isinstance(_cg_memories, list) else [],
                                conversation_history=_cg_history,
                                self_model_snapshot=_cg_self_model,
                            )
                            _lat_cfb = int((time.perf_counter() - _t_cfb) * 1000)
                            if _claude_answer:
                                result["answer"] = _claude_answer
                                result["generation_source"] = "cloud_fallback_claude"
                                _gen_tracking["gen"] = "cloud_fallback_claude"
                                if _is_gate_fail_empty:
                                    result["gates_passed"] = True
                                    result["gate_reason"] = "cloud_fallback_recovery"
                                _safe_print(f"[GENERATION] fallback: Claude succeeded, {len(_claude_answer)} chars")
                                try:
                                    _esc_policy.record_success("claude")
                                except Exception:
                                    pass
                                try:
                                    _track_cloud_call(
                                        call_type="generation_fallback_claude",
                                        provider="claude_cookie", model="claude-sonnet",
                                        latency_ms=_lat_cfb, success=True,
                                        thread_id=req.thread_id, uid=int(uid) if uid else None,
                                        output_text=_claude_answer,
                                        escalation_reason=_fallback_reason,
                                        user_message=effective_message,
                                    )
                                except Exception:
                                    pass
                            else:
                                print("[GENERATION] fallback: Claude also returned None, keeping local error")
                                try:
                                    _esc_policy.record_failure("claude", "returned_none")
                                except Exception:
                                    pass
                                try:
                                    _track_cloud_call(
                                        call_type="generation_fallback_claude",
                                        provider="claude_cookie", model="claude-sonnet",
                                        latency_ms=_lat_cfb, success=False,
                                        thread_id=req.thread_id, uid=int(uid) if uid else None,
                                        error_type="returned_none",
                                        escalation_reason=_fallback_reason,
                                        user_message=effective_message,
                                    )
                                except Exception:
                                    pass
                else:
                    print("[GENERATION] fallback: cloud service not initialized")
            else:
                print("[GENERATION] fallback: cloud generation fallback disabled by user setting")
        except Exception as _cg_err:
            _safe_print(f"[GENERATION] fallback_error: {_cg_err}")
    else:
        # No LLM error and no gate-fail-empty → local generation succeeded
        _gen_source = result.get("generation_source", "")
        if not _gen_source:
            result["generation_source"] = "local"
            _gen_tracking["gen"] = "local"
        if not _gen_source or _gen_source == "local":
            try:
                _esc_policy.record_success("local")
            except Exception:
                pass

    # ── STRUCTURAL GOVERNANCE: Apply confidence gate to final answer ──────
    # If confidence is low and the answer is too long, truncate it.
    # If confidence is low, prepend the hedge prefix (if not already from cloud path).
    if _confidence_gate_active:
        _final_answer = str(result.get("answer") or "")
        if _final_answer and not _final_answer.startswith("[Note: I have low confidence"):
            # Truncate if over the token limit (rough: 4 chars per token)
            _char_limit = _confidence_max_tokens * 4
            if len(_final_answer) > _char_limit:
                _final_answer = _final_answer[:_char_limit].rsplit(" ", 1)[0] + "..."
                _safe_print(f"[STRUCTURAL_GATE] Response truncated to ~{_confidence_max_tokens} tokens (was {len(str(result.get('answer', ''))) // 4})")
            result["answer"] = _confidence_hedge + _final_answer
            result["structural_gate_applied"] = True
            _safe_print(f"[STRUCTURAL_GATE] Hedge prefix applied to final answer")

    control_state.mark(
        "generate",
        "draft_ready",
        gate_reason=str(result.get("gate_reason") or ""),
        response_type=str(result.get("response_type") or ""),
    )

    # ====== CLOUD SLOT CLASSIFICATION (optional) ======
    # Skip for conversational/self-referential messages (no facts to extract, saves 1-2s)
    _gate_reason_for_skip = str(result.get("gate_reason") or "").lower()
    _skip_governance = any(kw in _gate_reason_for_skip for kw in (
        "greeting", "self_referential", "conversational", "no_memories",
        "identity", "chitchat", "explanation", "user_reflection",
    ))
    if _skip_governance:
        _safe_print(f"[GOVERNANCE] Skipping slot classification for conversational message (gate_reason={_gate_reason_for_skip})")
    elif not _is_cloud_governance_allowed(req, uid):
        _skip_governance = True
        _safe_print("[GOVERNANCE] Skipping cloud slot classification in strict local-only mode")

    # If local fact extraction couldn't classify a slot, try cloud classification.
    try:
        _local_slots = result.get("slots_extracted") or result.get("facts") or {}
        if not _skip_governance and (not _local_slots or (isinstance(_local_slots, dict) and not _local_slots)):
            import auth as _auth_mod
            _uid_int = int(uid) if uid else 1
            _cloud_slot_enabled = str(
                _auth_mod.get_user_setting(_uid_int, "cloud_slot_classification", "false")
            ).lower() in ("true", "1", "yes", "on")
            if _cloud_slot_enabled:
                from personal_agent.cloud_features import get_cloud_feature_service
                _cloud_svc = get_cloud_feature_service()
                _safe_print(f"[GOVERNANCE] slot_classify: no local slots, cloud_enabled={_cloud_slot_enabled}, cloud_svc={_cloud_svc is not None}")
                _emit_pipeline_status("classifying slots")
                if _cloud_svc is not None:
                    # Gather existing slot names from memory for context
                    _existing_slots = []
                    try:
                        _existing_slots = list(
                            (extract_fact_slots(effective_message) or {}).keys()
                        ) or []
                    except Exception:
                        pass
                    _t_slot = time.perf_counter()
                    _cloud_result = _cloud_svc.classify_slot(
                        effective_message, _existing_slots
                    )
                    _lat_slot = int((time.perf_counter() - _t_slot) * 1000)
                    try:
                        _track_cloud_call(
                            call_type="slot_classification",
                            provider="openai", model="gpt-4o-mini",
                            latency_ms=_lat_slot,
                            success=_cloud_result is not None,
                            thread_id=req.thread_id, uid=int(uid) if uid else None,
                            error_type=None if _cloud_result else "returned_none",
                            user_message=effective_message,
                        )
                    except Exception:
                        pass
                    if _cloud_result:
                        result["cloud_governance_used"] = True
                    if _cloud_result and _cloud_result.get("contains_fact"):
                        _cloud_slot = _cloud_result.get("slot_name")
                        _cloud_value = _cloud_result.get("value")
                        _safe_print(f"[GOVERNANCE] slot_classify: detected slot={_cloud_slot}, value={_cloud_value}")
                        _gen_tracking["slots"] = f"cloud({_cloud_slot})"
                        if _cloud_slot and _cloud_value:
                            try:
                                result.setdefault("slots_extracted", {})
                                if isinstance(result["slots_extracted"], dict):
                                    result["slots_extracted"][_cloud_slot] = _cloud_value
                            except Exception as _se_err:
                                _safe_print(f"[GOVERNANCE] slot_classify: slots_extracted error: {_se_err}")
                            # --- Cloud-driven slot exclusivity demotion ---
                            _safe_print(f"[GOVERNANCE] slot_exclusivity: Entering demotion check for {_cloud_slot}={_cloud_value}")
                            # Sprint 6: dynamic slot type lookup with legacy fallback
                            _EXCLUSIVE_SLOTS_LEGACY = {
                                "favorite_color", "name", "first_name", "last_name",
                                "birthday", "birth_date", "legal_name", "primary_city",
                                "city", "employer", "job_title", "nickname",
                            }
                            try:
                                from personal_agent.slot_discovery import get_slot_type as _gst, SlotType as _ST
                                _dyn_slot_type = _gst(_cloud_slot)
                                _is_exclusive = _cloud_result.get("exclusive", _dyn_slot_type == _ST.EXCLUSIVE or (_dyn_slot_type == _ST.UNKNOWN and _cloud_slot in _EXCLUSIVE_SLOTS_LEGACY))
                            except Exception:
                                _is_exclusive = _cloud_result.get("exclusive", _cloud_slot in _EXCLUSIVE_SLOTS_LEGACY)
                            _safe_print(f"[GOVERNANCE] slot_exclusivity: exclusive={_is_exclusive}")

                            # GUARD: Do NOT demote established memories if ANY recent
                            # memory is still provisional. This prevents a test/false
                            # claim from destroying trust on real memories before
                            # contradiction detection has had a chance to evaluate it.
                            _skip_demotion = False
                            if _is_exclusive:
                                try:
                                    import time as _time_prov
                                    _conn_prov = engine.memory._get_connection()
                                    _cur_prov = _conn_prov.cursor()
                                    _cur_prov.execute("""
                                        SELECT memory_id, authority, text FROM memories
                                        WHERE authority = 'provisional'
                                        AND deprecated = 0
                                        AND timestamp > ?
                                        ORDER BY timestamp DESC
                                        LIMIT 5
                                    """, (_time_prov.time() - 30,))
                                    _prov_row = next(
                                        (
                                            row for row in (_cur_prov.fetchall() or [])
                                            if not looks_like_llm_error_text(str((row[2] if len(row) > 2 else "") or ""))
                                        ),
                                        None,
                                    )
                                    _conn_prov.close()
                                    if _prov_row:
                                        _skip_demotion = True
                                        _safe_print(f"[GOVERNANCE] slot_exclusivity: BLOCKED demotion — "
                                                    f"provisional memory exists: {_prov_row[0]} "
                                                    f"(\"{str(_prov_row[2] or '')[:50]}\")")
                                except Exception as _prov_err:
                                    _safe_print(f"[GOVERNANCE] slot_exclusivity: provisional check error: {_prov_err}")

                            if _is_exclusive and not _skip_demotion:
                                try:
                                    _new_val_norm = str(_cloud_value).strip().lower()
                                    # Use ONLY memory_facts table — no text search.
                                    # Text search (LIKE '%name%') caused the 81-memory cascade
                                    # incident on 2026-04-08. Structured slot comparison only.
                                    _conn_ex = engine.memory._get_connection()
                                    _cur_ex = _conn_ex.cursor()
                                    _cur_ex.execute("""
                                        SELECT mf.memory_id, mf.normalized, m.trust
                                        FROM memory_facts mf
                                        JOIN memories m ON mf.memory_id = m.memory_id
                                        WHERE mf.slot = ? AND m.deprecated = 0
                                    """, (_cloud_slot,))
                                    _fact_rows = _cur_ex.fetchall()
                                    _conn_ex.close()
                                    _safe_print(f"[GOVERNANCE] slot_exclusivity: facts_table={len(_fact_rows)} rows (text search removed)")
                                    _demoted_ids = set()
                                    for _ex_mem_id, _ex_norm, _ex_trust in _fact_rows:
                                        _ex_val = str(_ex_norm).strip().lower()
                                        # Same-value skip (substring containment)
                                        if (_ex_val == _new_val_norm
                                                or _new_val_norm in _ex_val
                                                or _ex_val in _new_val_norm):
                                            continue
                                        # Skip non-user sources
                                        try:
                                            _conn_sk = engine.memory._get_connection()
                                            _cur_sk = _conn_sk.cursor()
                                            _cur_sk.execute("SELECT source_kind FROM memories WHERE memory_id = ?", (_ex_mem_id,))
                                            _row_sk = _cur_sk.fetchone()
                                            _conn_sk.close()
                                            if _row_sk and (_row_sk[0] or 'principal') in {'model_output', 'system', 'tool_receipt'}:
                                                _safe_print(f"[GOVERNANCE] slot_exclusivity: SKIPPED {_ex_mem_id} (non-user source)")
                                                continue
                                        except Exception:
                                            pass
                                        _demoted = float(_ex_trust) * 0.4
                                        engine.memory._update_memory_trust(_ex_mem_id, _demoted)
                                        _demoted_ids.add(_ex_mem_id)
                                        _safe_print(
                                            f"[GOVERNANCE] slot_exclusivity: DEMOTED {_ex_mem_id} "
                                            f"(trust {float(_ex_trust):.3f} -> {_demoted:.3f}) "
                                            f"slot: {_cloud_slot}, old={_ex_val}, new={_new_val_norm}"
                                        )
                                    # Record demotion events (no DELETE of old memory_facts —
                                    # the write-path in store_memory handles fact lifecycle)
                                    try:
                                        _conn_store = engine.memory._get_connection()
                                        _cur_store = _conn_store.cursor()
                                        for _dem_id in _demoted_ids:
                                            try:
                                                engine.memory.record_memory_event(
                                                    memory_id=_dem_id,
                                                    event_type="slot_exclusivity_demoted",
                                                    actor="cloud_slot",
                                                    reason=f"superseded: {_cloud_slot}={_new_val_norm}",
                                                )
                                            except Exception:
                                                pass
                                        # Find the most recent memory matching this text
                                        _cur_store.execute("""
                                            SELECT memory_id FROM memories
                                            WHERE LOWER(text) LIKE ? AND deprecated = 0
                                            ORDER BY timestamp DESC LIMIT 1
                                        """, (f"%{_new_val_norm}%",))
                                        _new_mem_row = _cur_store.fetchone()
                                        if _new_mem_row:
                                            _cur_store.execute(
                                                "INSERT OR REPLACE INTO memory_facts (memory_id, slot, value, normalized) VALUES (?, ?, ?, ?)",
                                                (_new_mem_row[0], _cloud_slot, str(_cloud_value), _new_val_norm),
                                            )
                                            _safe_print(f"[GOVERNANCE] slot_exclusivity: Stored fact: {_cloud_slot}={_new_val_norm} for {_new_mem_row[0]}")
                                        _conn_store.commit()
                                        _conn_store.close()
                                        if _deleted_facts:
                                            _safe_print(f"[GOVERNANCE] slot_exclusivity: Cleaned {_deleted_facts} stale fact entries for {_cloud_slot}")
                                    except Exception as _sf_err:
                                        _safe_print(f"[GOVERNANCE] slot_exclusivity: Fact store error (non-fatal): {_sf_err}")
                                except Exception as _slot_ex_err:
                                    import traceback
                                    _safe_print(f"[GOVERNANCE] slot_exclusivity: Error: {_slot_ex_err}")
                                    traceback.print_exc()
                    else:
                        print("[GOVERNANCE] slot_classify: no fact detected")
    except Exception as _cloud_slot_err:
        logger.warning("[GOVERNANCE] slot_classify: cloud classification failed (non-fatal): %s", _cloud_slot_err)

    # ====== CRT-AS-CRITIC: Post-generation verification ======
    # Verify the draft answer against stored memories using GroundCheck (~1ms).
    # This replaces unreliable LLM self-critique with external truth checking.
    # Skip for simple greetings — they are not factual assertions and should
    # never trigger the contradiction_disclosure gate.
    _GREETING_WORDS = {
        "hello", "hi", "hey", "good morning", "good afternoon", "good evening",
        "what's up", "whats up", "howdy", "yo", "sup", "hiya", "greetings",
        "how are you", "how's it going", "hows it going",
    }
    _critic_msg_lower = (effective_message or "").strip().lower().rstrip("!?.,'")
    # Strip the bot's name for matching (e.g. "hello aether" -> "hello")
    _critic_msg_clean = _critic_msg_lower.replace("aether", "").strip().rstrip(",!. ")
    _skip_critic_greeting = (
        _critic_msg_clean in _GREETING_WORDS
        or (len(_critic_msg_lower) < 20 and any(_critic_msg_lower.startswith(g) for g in _GREETING_WORDS))
    )
    # Also skip critic for opinion/conversational questions (no facts to verify against)
    _OPINION_SIGNALS = (
        "what do you think", "do you think", "what's your", "whats your",
        "how do you feel", "what worries", "what scares", "scariest",
        "what matters", "what's important", "your opinion", "your take",
        "do you believe", "would you say", "where do you see",
        "what excites", "what concerns", "how would you",
    )
    if any(sig in _critic_msg_lower for sig in _OPINION_SIGNALS):
        _skip_critic_greeting = True
        logger.debug("[CRT-CRITIC] Skipping contradiction gate for opinion question: %s", effective_message[:60])
    critic_meta = None
    if _skip_critic_greeting:
        logger.debug("[CRT-CRITIC] Skipping contradiction gate for greeting: %s", effective_message[:60])
    try:
      if not _skip_critic_greeting:
        from personal_agent.crt_critic import CRTCritic, VerifyVerdict
        _critic = CRTCritic()
        _draft = result.get("answer", "")
        _retrieved = result.get("retrieved_memories") or []
        if _draft and _retrieved:
            _critic_result = _critic.verify_draft(
                query=effective_message,
                draft_answer=_draft,
                retrieved_memories=_retrieved,
                llm_client=get_llm_client(),
            )
            critic_meta = _critic_result.to_dict()
            # Replace answer with critic's output (may be revised or disclosure)
            result["answer"] = _critic_result.final_answer
            if _critic_result.was_revised:
                logger.info(f"[CRT-CRITIC] Answer revised (verdict={_critic_result.verdict.value})")
                try:
                    from personal_agent.judgment_audit_log import log_judgment, GATE_BLOCKED
                    log_judgment(
                        GATE_BLOCKED,
                        f"CRT-Critic revised answer (verdict={_critic_result.verdict.value})",
                        thread_id=req.thread_id,
                        extra={"verdict": _critic_result.verdict.value, "query": effective_message[:120]},
                    )
                except Exception:
                    pass
            if _critic_result.verdict == VerifyVerdict.HARD_FAIL:
                # Override gates to signal contradiction disclosure
                result["gates_passed"] = False
                result["gate_reason"] = "contradiction_disclosure"
                # Keep metadata consistent with disclosure path for channels/telemetry.
                result["contradiction_detected"] = True
                logger.info("[CRT-CRITIC] Hard fail — surfacing contradiction to user")
                try:
                    from personal_agent.judgment_audit_log import log_judgment, GATE_BLOCKED
                    log_judgment(
                        GATE_BLOCKED,
                        "CRT-Critic HARD_FAIL — contradiction disclosure forced",
                        thread_id=req.thread_id,
                        extra={"verdict": "HARD_FAIL", "query": effective_message[:120]},
                    )
                except Exception:
                    pass
    except ImportError:
        logger.debug("[CRT-CRITIC] crt_critic not available")
    except Exception as e:
        logger.warning(f"[CRT-CRITIC] Verification error (non-fatal): {e}")
    # ── NLI enforcement: soft_fail with contradictions should also gate ──
    # Previously only hard_fail set gates_passed=False. Soft_fail with
    # unrevised contradictions silently delivered the wrong answer.
    if critic_meta:
        _critic_v = str(critic_meta.get("verdict") or "")
        _critic_contras = critic_meta.get("contradictions") or []
        _critic_revised = bool(critic_meta.get("was_revised"))
        if _critic_v == "soft_fail" and _critic_contras and not _critic_revised:
            # Soft fail + contradictions found + revision failed = gate should fail
            result["gates_passed"] = False
            result["gate_reason"] = "nli_soft_fail_unrevised"
            result["critic_meta"] = critic_meta
            _safe_print(
                f"[NLI_ENFORCEMENT] soft_fail with {len(_critic_contras)} unrevised contradictions — gating response"
            )

    _mark("critic_done")
    control_state.mark(
        "validate",
        "critic_checked",
        detail=str((critic_meta or {}).get("verdict") or "no_critic"),
        gates_passed=bool(result.get("gates_passed")),
    )

    # ====== CLOUD NLI CONTRADICTION CHECK (optional) ======
    # If the CRT critic returned SOFT_FAIL (uncertain confidence 0.4-0.7),
    # escalate to cloud NLI for a definitive answer.
    try:
        _critic_confidence = float((critic_meta or {}).get("confidence") or 0.0)
        _critic_verdict_str = str((critic_meta or {}).get("verdict") or "")
        _safe_print(f"[GOVERNANCE] nli: critic verdict={_critic_verdict_str}, confidence={_critic_confidence}")
        _emit_pipeline_status("checking contradictions")
        # Emit verification event for frontend
        _emit_pipeline_event({
            "type": "verification",
            "content": f"{'passed' if _critic_verdict_str == 'pass' else 'checking'}" if _critic_verdict_str else "skipped",
            "metadata": {
                "verdict": _critic_verdict_str or "none",
                "confidence": _critic_confidence,
            },
        })
        if _critic_verdict_str == "soft_fail" and 0.4 <= _critic_confidence <= 0.7:
            import auth as _auth_mod_nli
            _uid_int_nli = int(uid) if uid else 1
            _cloud_nli_enabled = str(
                _auth_mod_nli.get_user_setting(_uid_int_nli, "cloud_nli_contradiction", "false")
            ).lower() in ("true", "1", "yes", "on")
            if _cloud_nli_enabled and _is_cloud_governance_allowed(req, uid):
                from personal_agent.cloud_features import get_cloud_feature_service
                _cloud_svc_nli = get_cloud_feature_service()
                if _cloud_svc_nli is not None:
                    # Extract the contradicting facts from critic metadata
                    _contradictions = (critic_meta or {}).get("contradictions") or []
                    _fact_a = effective_message
                    _fact_b = _contradictions[0] if _contradictions else str(result.get("answer", ""))[:200]
                    _t_nli = time.perf_counter()
                    _nli_result = _cloud_svc_nli.check_contradiction(_fact_a, _fact_b)
                    _lat_nli = int((time.perf_counter() - _t_nli) * 1000)
                    try:
                        _track_cloud_call(
                            call_type="nli_contradiction",
                            provider="openai", model="gpt-4o-mini",
                            latency_ms=_lat_nli,
                            success=_nli_result is not None,
                            thread_id=req.thread_id, uid=int(uid) if uid else None,
                            error_type=None if _nli_result else "returned_none",
                            user_message=effective_message,
                        )
                    except Exception:
                        pass
                    if _nli_result:
                        result["cloud_governance_used"] = True
                        _nli_relation = str(_nli_result.get("relation") or "").lower()
                        if _nli_relation == "contradiction":
                            # Cloud confirms contradiction — upgrade to hard fail
                            result["gates_passed"] = False
                            result["gate_reason"] = "cloud_nli_contradiction"
                            result["contradiction_detected"] = True
                            print("[GOVERNANCE] nli: cloud confirmed contradiction, upgraded to hard fail")
                            _gen_tracking["nli"] = "cloud(contradiction)"
                        elif _nli_relation in ("entailment", "neutral"):
                            # Cloud says no contradiction — upgrade to pass
                            result["gates_passed"] = True
                            result.pop("gate_reason", None)
                            result["contradiction_detected"] = False
                            print("[GOVERNANCE] nli: cloud cleared contradiction, upgraded to pass")
                            _gen_tracking["nli"] = "cloud(pass)"
            elif _cloud_nli_enabled:
                _safe_print("[GOVERNANCE] nli: skipping cloud NLI in strict local-only mode")
    except Exception as _cloud_nli_err:
        logger.warning("[GOVERNANCE] nli_error: cloud NLI check failed (non-fatal): %s", _cloud_nli_err)

    # ── Request summary ─────────────────────────────────────────────────────
    try:
        _gen_latency_ms = round((time.perf_counter() - _gen_phase_t0) * 1000)
        # Update nli tracking from local critic if cloud NLI didn't run
        if _gen_tracking["nli"] == "none" and critic_meta:
            _cv = str((critic_meta or {}).get("verdict") or "")
            _gen_tracking["nli"] = f"local({_cv})" if _cv else "local(skip)"
        _escalation_mode = _gen_tracking.get("escalation", "none")
        if _escalation_mode == "none" and _escalation_decision is not None:
            _escalation_mode = "local_only"
            _gen_tracking["escalation"] = _escalation_mode
        print(
            f"[REQUEST_SUMMARY] gen={_gen_tracking['gen']}, "
            f"slots={_gen_tracking['slots']}, "
            f"nli={_gen_tracking['nli']}, "
            f"escalation={_gen_tracking['escalation']}, "
            f"latency={_gen_latency_ms}ms"
        )
        # Store gate check results for frontend visualization
        result["gate_checks"] = {
            "slot": _gen_tracking.get("slots", "none"),
            "nli": _gen_tracking.get("nli", "none"),
            "gap": "safe",  # default; updated below if governance ran
        }
        # Extract gap audit from governance annotations if available
        try:
            _gov_tier = result.get("governance_tier") or result.get("metadata", {}).get("governance_tier")
            _gov_anns = result.get("governance_annotations") or result.get("metadata", {}).get("governance_annotations", 0)
            _gov_findings = result.get("governance_findings") or result.get("metadata", {}).get("governance_findings", [])
            if _gov_tier:
                result["gate_checks"]["governance_tier"] = _gov_tier
            for _finding in (_gov_findings or []):
                if "gap" in str(_finding).lower() or "belief/speech" in str(_finding).lower():
                    result["gate_checks"]["gap"] = "flagged"
                    break
        except Exception:
            pass
    except Exception as _summary_err:
        _safe_print(f"[REQUEST_SUMMARY] error: {_summary_err}")

    # ── Gate telemetry emission ──────────────────────────────────────────────
    try:
        _gates_passed_final = bool(result.get("gates_passed", False))
        _coordinator = get_active_learning_coordinator()
        _coordinator.emit_turn_event(
            event_type="gate_pass" if _gates_passed_final else "gate_fail",
            thread_id=req.thread_id,
            severity=0.0 if _gates_passed_final else 0.33,
            payload={
                "gate_reason": str(result.get("gate_reason") or ""),
                "confidence": float(result.get("confidence") or 0.0),
                "response_type": str(result.get("response_type") or ""),
            },
        )
    except Exception as _gte:
        logger.debug("[GATE_TELEMETRY] emit failed: %s", _gte)

    # Capture thinking trace (if available) for non-stream responses.
    llm_client = get_llm_client()
    thinking_content = _strip_thinking_tags(str(result.get("thinking") or ""))
    thinking_trace_id = None
    if thinking_content and len(thinking_content) > 50:
        try:
            thinking_trace_id = engine.memory.store_reasoning_trace(
                query=effective_message,
                thinking_content=thinking_content,
                thread_id=req.thread_id,
                response_summary=str(result.get("answer") or "")[:200] if result.get("answer") else None,
                model=(llm_client.model if llm_client else None),
                metadata={
                    "gates_passed": result.get("gates_passed", True),
                    "confidence": result.get("confidence", 0.7),
                },
            )
        except Exception as e:
            logger.debug(f"[TRACE] Failed to store thinking trace: {e}")
    _mark("thinking_trace_done")

    # AGENT INTEGRATION: Check for proactive triggers
    # CHECKPOINT GATE: Agent no longer auto-executes. Triggers are surfaced
    # as metadata so the frontend can present them to the user as a suggestion.
    # The user must explicitly confirm before the agent runs.
    _llm_enabled = os.getenv("CRT_ENABLE_LLM", "false").lower() == "true"
    agent_activated = False
    agent_trace_data = None
    agent_answer = None
    agent_suggested_triggers: list = []

    if _llm_enabled:
        try:
            from personal_agent.proactive_triggers import ProactiveTriggers

            triggers_engine = ProactiveTriggers(
                confidence_threshold=0.5,
                auto_research_threshold=0.4,
                contradiction_auto_resolve=False,
            )
            detected_triggers = triggers_engine.analyze_response(result)

            if detected_triggers:
                # Surface triggers as suggestions — do NOT auto-execute.
                agent_suggested_triggers = [
                    {
                        "type": t.trigger_type.value,
                        "reason": t.reason,
                        "suggested_action": t.suggested_action,
                        "would_auto_execute": t.should_auto_execute,
                    }
                    for t in detected_triggers
                ]
                logger.info(
                    "[AGENT] %d trigger(s) detected but NOT auto-executing (checkpoint gate). Triggers: %s",
                    len(detected_triggers),
                    [t.trigger_type.value for t in detected_triggers],
                )

        except Exception as e:
            logger.warning(f"[AGENT] Trigger analysis error: {e}")

    # Build retrieved / prompt memory payloads
    retrieved_mems = [
        {
            "memory_id": (m.get("memory_id") if isinstance(m, dict) else None),
            "text": (m.get("text") if isinstance(m, dict) else None),
            "source": (m.get("source") if isinstance(m, dict) else None),
            "trust": (m.get("trust") if isinstance(m, dict) else None),
            "confidence": (m.get("confidence") if isinstance(m, dict) else None),
            "timestamp": (m.get("timestamp") if isinstance(m, dict) else None),
            "sse_mode": (m.get("sse_mode") if isinstance(m, dict) else None),
            "score": (m.get("score") if isinstance(m, dict) else None),
            "reintroduced_claim": (
                engine.ledger.has_open_contradiction(m.get("memory_id"))
                if isinstance(m, dict)
                and m.get("memory_id")
                and hasattr(engine.ledger, "has_open_contradiction")
                else m.get("reintroduced_claim", False) if isinstance(m, dict) else False
            ),
        }
        for m in (result.get("retrieved_memories") or [])
        if isinstance(m, dict)
    ]

    prompt_mems = [
        {
            "memory_id": (m.get("memory_id") if isinstance(m, dict) else None),
            "text": (m.get("text") if isinstance(m, dict) else None),
            "source": (m.get("source") if isinstance(m, dict) else None),
            "trust": (m.get("trust") if isinstance(m, dict) else None),
            "confidence": (m.get("confidence") if isinstance(m, dict) else None),
            "reintroduced_claim": (
                engine.ledger.has_open_contradiction(m.get("memory_id"))
                if isinstance(m, dict)
                and m.get("memory_id")
                and hasattr(engine.ledger, "has_open_contradiction")
                else m.get("reintroduced_claim", False) if isinstance(m, dict) else False
            ),
        }
        for m in (result.get("prompt_memories") or [])
        if isinstance(m, dict)
    ]

    reintro_count = sum(1 for m in retrieved_mems if m.get("reintroduced_claim") is True)

    # ====== Trust reinforcement: context-aware trust update for cited memories ======
    # BUG FIX: Previously boosted trust for ALL cited memories unconditionally.
    # Now checks whether the user's message agrees or contradicts each memory.
    # - Agreement → trust goes up (reinforce)
    # - Contradiction → trust goes down (penalize)
    # - Neutral citation → no change (avoid blind boosting)
    try:
        from personal_agent.trust_decay import reinforce_memory, REINFORCE_BOOST, TRUST_FLOOR
        from personal_agent.crt_core import CRTMath, CRTConfig, encode_vector
        import numpy as _np_trust

        _crt_trust = None
        try:
            _crt_trust = CRTMath(CRTConfig())
        except Exception:
            pass

        _user_vec = None
        try:
            _user_vec = encode_vector(effective_message)
        except Exception:
            pass

        for mem in retrieved_mems:
            mid = mem.get("memory_id")
            mem_text = mem.get("text") or ""
            if not mid or not mem_text:
                continue

            # Compute semantic similarity between user message and memory
            _mem_vec = None
            try:
                _mem_vec = encode_vector(mem_text)
            except Exception:
                pass

            if _user_vec is not None and _mem_vec is not None and _crt_trust is not None:
                similarity = float(_np_trust.dot(_user_vec, _mem_vec) / (
                    _np_trust.linalg.norm(_user_vec) * _np_trust.linalg.norm(_mem_vec) + 1e-8
                ))
                drift = _crt_trust.drift_meaning(_user_vec, _mem_vec)

                # Check for contradiction signals between user message and memory
                is_contra = False
                try:
                    is_contra, _ = _crt_trust.detect_contradiction(
                        drift=drift,
                        confidence_new=0.9,
                        confidence_prior=0.7,
                        source=None,
                        text_new=effective_message,
                        text_prior=mem_text,
                    )
                except Exception:
                    # detect_contradiction may fail on source=None; fall back to drift threshold
                    is_contra = drift > 0.6

                if is_contra:
                    # User contradicts this memory → penalize trust
                    try:
                        from personal_agent.trust_decay import _find_groundcheck_db, _is_crt_schema
                        import sqlite3 as _sql_trust
                        _db = _find_groundcheck_db()
                        if _db:
                            _conn = _sql_trust.connect(str(_db))
                            _conn.row_factory = _sql_trust.Row
                            _id_col = "memory_id" if _is_crt_schema(_conn) else "id"
                            _row = _conn.execute(f"SELECT trust FROM memories WHERE {_id_col} = ?", (mid,)).fetchone()
                            if _row:
                                _old = _row["trust"]
                                # Penalize: reduce by REINFORCE_BOOST scaled by drift severity
                                _penalty = REINFORCE_BOOST * min(drift * 2, 1.5)
                                _new = max(TRUST_FLOOR, _old - _penalty)
                                if _new < _old:
                                    _conn.execute(f"UPDATE memories SET trust = ? WHERE {_id_col} = ?",
                                                  (round(_new, 4), mid))
                                    _conn.commit()
                                    logger.debug(f"[TRUST_DECAY] Contradicted memory {mid}: {_old:.3f} → {_new:.3f} (drift={drift:.3f})")
                            _conn.close()
                    except Exception as _te:
                        logger.debug(f"[TRUST_DECAY] Error penalizing contradicted memory {mid}: {_te}")
                elif similarity > 0.5 and drift < 0.35:
                    # User agrees with this memory → reinforce trust
                    reinforce_memory(mid, context_text=effective_message)
                # else: neutral citation (low similarity, moderate drift) → no trust change
            else:
                # Vectors unavailable — no trust change (safe default, avoids blind boosting)
                pass
    except Exception as e:
        logger.debug(f"[TRUST_DECAY] Error in context-aware trust update: {e}")

    base_answer = strip_think_blocks(str(result.get("answer") or ""))

    # ========================================
    # DIRECTED REFLECTION PASS — fired async
    # ========================================
    # Reflection is expensive (~8-9s) and not needed to deliver the answer.
    # Fire it in a background thread; metadata fields will be None for this response.
    reflection_trace_id = None
    reflection_result = None
    if llm_client is not None:
        _bg_grounding_facts = [
            m.get("text", "")[:300]
            for m in (result.get("retrieved_memories") or [])
            if isinstance(m, dict) and m.get("text")
        ][:5]
        _bg_reflection_kwargs = dict(
            question=effective_message,
            response=base_answer,
            thinking=thinking_content,
            thread_id=req.thread_id,
            db_path=engine.memory.db_path,
            facts=_bg_grounding_facts,
            auto_requery=False,
            collect_training_data=True,
        )
        def _run_reflection_bg(**kwargs):
            try:
                run_reflection_pass(**kwargs)
            except Exception as _e:
                logger.debug(f"[REFLECTION_BG] Reflection failed: {_e}")
        threading.Thread(target=_run_reflection_bg, kwargs=_bg_reflection_kwargs, daemon=True).start()
    _mark("reflection_done")
    control_state.mark(
        "validate",
        "reflection_checked",
        detail=str(reflection_trace_id or "none"),
    )

    verbosity_pref = _get_verbosity_preference(req.thread_id, engine.memory)
    if not verbosity_pref and personality_profile:
        try:
            personality_verbosity = str(personality_profile.get("verbosity") or "").lower()
            if personality_verbosity:
                verbosity_pref = personality_verbosity
        except Exception:
            pass
    known_fact_lines: List[str] = []
    for mem in (retrieved_mems + prompt_mems)[:6]:
        if isinstance(mem, dict):
            text = (mem.get("text") or "").strip()
            if text:
                known_fact_lines.append(f"- {text[:280]}")
    known_facts_text = "\n".join(known_fact_lines)

    expanded = False
    expansion_reason: Optional[str] = None
    should_expand, expansion_reason = _should_expand_response(
        effective_message,
        base_answer,
        reflection_result,
        verbosity_pref,
    )
    if should_expand:
        expansion_text = _generate_expansion(
            llm_client,
            effective_message,
            base_answer,
            known_facts_text,
            style_profile,
            reflection_result,
            personality_profile,
        )
        if expansion_text:
            expanded = True
            base_answer = base_answer.rstrip()
            base_answer = f"{base_answer}\n\n{expansion_text}"
        else:
            expansion_reason = None

    final_answer = base_answer

    # Strip model-generated greeting prefix if the model echoed the system greeting
    # (3B models sometimes reproduce "Hey! I'm Aether. What's on your mind?" from context)
    _GREETING_PATTERNS = [
        "Hey! I'm Aether. What's on your mind?",
        "Hey! I'm Aether.",
        "Hey! What's on your mind?",
    ]
    for _gp in _GREETING_PATTERNS:
        if final_answer.startswith(_gp):
            final_answer = final_answer[len(_gp):].lstrip("\n").lstrip()
            _safe_print(f"[GREETING_STRIP] Removed model-echoed greeting: {_gp[:40]}")
            break

    # Strip hallucinated source citations (3B models invent fake references)
    import re as _re_strip
    final_answer = _re_strip.sub(
        r'\n*(?:Source|Sources|References?):\s*\(.*?\)\s*$', '', final_answer, flags=_re_strip.DOTALL
    ).rstrip()
    # Also strip "Source: (This explanation is based on...)" patterns
    final_answer = _re_strip.sub(
        r'\n*(?:Source|Sources|References?):\s*$', '', final_answer, flags=_re_strip.MULTILINE
    ).rstrip()

    if greeting_text:
        final_answer = f"{greeting_text}\n\n{final_answer}"

    # Strip LLM error strings that leak from Ollama client — try cloud fallback first
    _leaked_error = (
        final_answer.startswith("[Ollama error:")
        or final_answer.startswith("[Ollama connection error:")
        or final_answer.startswith("[LLM error:")
        or final_answer.startswith("[Model '")
        or final_answer.startswith("[No LLM available")
    )
    # Also catch errors buried after a greeting prefix
    if not _leaked_error and greeting_text and "\n\n" in final_answer:
        _after_greeting = final_answer.split("\n\n", 1)[1] if "\n\n" in final_answer else ""
        _leaked_error = (
            _after_greeting.startswith("[Ollama error:")
            or _after_greeting.startswith("[Ollama connection error:")
            or _after_greeting.startswith("[LLM error:")
            or _after_greeting.startswith("[Model '")
            or _after_greeting.startswith("[No LLM available")
        )
    if _leaked_error:
        _safe_print(f"[GENERATION] late_fallback: LLM error leaked into final_answer: {final_answer[:120]}")
        # Try cloud fallback if not already attempted
        _already_cloud = result.get("generation_source") in ("cloud_fallback", "cloud_fallback_claude")
        if not _already_cloud:
            try:
                import auth as _auth_cg2
                _uid_cg2 = int(uid) if uid else 1
                _cloud_gen_enabled2 = str(
                    _auth_cg2.get_user_setting(_uid_cg2, "cloud_generation_fallback", "true")
                ).lower() in ("true", "1", "yes", "on")
                _user_gen_mode2 = resolve_effective_generation_mode(req, uid)
                if not is_cloud_fallback_allowed(req, _uid_cg2):
                    _cloud_gen_enabled2 = False
                    print(f"[GENERATION] late_fallback: blocked for effective local-only routing (generation_mode={_user_gen_mode2})")
                if _cloud_gen_enabled2:
                    from personal_agent.cloud_features import get_cloud_feature_service
                    _cloud_gen_svc2 = get_cloud_feature_service()
                    if _cloud_gen_svc2 is not None:
                        print("[GENERATION] late_fallback: trying OpenAI after leaked error string")
                        _cg2_memories = retrieved_mems or []
                        _t_late = time.perf_counter()
                        _cg2_answer = _cloud_gen_svc2.generate_response(
                            user_message=effective_message,
                            retrieved_memories=_cg2_memories,
                            conversation_history=recent_history or None,
                        )
                        _lat_late = int((time.perf_counter() - _t_late) * 1000)
                        if _cg2_answer:
                            final_answer = _cg2_answer
                            if greeting_text:
                                final_answer = f"{greeting_text}\n\n{final_answer}"
                            result["generation_source"] = "cloud_fallback"
                            _safe_print(f"[GENERATION] late_fallback: OpenAI succeeded, {len(_cg2_answer)} chars")
                        try:
                            _track_cloud_call(
                                call_type="generation_fallback",
                                provider="openai", model="gpt-4o-mini",
                                latency_ms=_lat_late, success=True,
                                thread_id=req.thread_id, uid=int(uid) if uid else None,
                                output_text=_cg2_answer,
                                escalation_reason="leaked_error_string",
                                user_message=effective_message,
                            )
                        except Exception:
                            pass
                        else:
                            # OpenAI failed — escalate to Claude (Tier 2) if enabled
                            _claude_enabled2 = str(
                                _auth_cg2.get_user_setting(_uid_cg2, "cloud_claude_enabled", "false")
                            ).lower() in ("true", "1", "yes", "on")
                            if not _claude_enabled2:
                                print("[GENERATION] late_fallback: Claude disabled by user setting, skipping Tier 2")
                                final_answer = "I ran into a problem generating a response. The model may not be available -- try again in a moment."
                            else:
                                print("[GENERATION] late_fallback: OpenAI returned None, escalating to Claude (Tier 2)")
                                _t_late_c = time.perf_counter()
                                _cg2_claude = _cloud_gen_svc2.generate_response_claude(
                                    user_message=effective_message,
                                    retrieved_memories=_cg2_memories,
                                    conversation_history=recent_history or None,
                                )
                                _lat_late_c = int((time.perf_counter() - _t_late_c) * 1000)
                                if _cg2_claude:
                                    final_answer = _cg2_claude
                                    if greeting_text:
                                        final_answer = f"{greeting_text}\n\n{final_answer}"
                                    result["generation_source"] = "cloud_fallback_claude"
                                    _safe_print(f"[GENERATION] late_fallback: Claude succeeded, {len(_cg2_claude)} chars")
                                try:
                                    _track_cloud_call(
                                        call_type="generation_fallback_claude",
                                        provider="claude_cookie", model="claude-sonnet",
                                        latency_ms=_lat_late_c, success=True,
                                        thread_id=req.thread_id, uid=int(uid) if uid else None,
                                        output_text=_cg2_claude,
                                        escalation_reason="leaked_error_string",
                                        user_message=effective_message,
                                    )
                                except Exception:
                                    pass
                                if not _cg2_claude:
                                    print("[GENERATION] late_fallback: Claude also returned None")
                                    final_answer = "I ran into a problem generating a response. The model may not be available -- try again in a moment."
                    else:
                        final_answer = "I ran into a problem generating a response. The model may not be available -- try again in a moment."
                else:
                    final_answer = "I ran into a problem generating a response. The model may not be available -- try again in a moment."
            except Exception as _cg2_err:
                _safe_print(f"[GENERATION] late_fallback_error: {_cg2_err}")
                final_answer = "I ran into a problem generating a response. The model may not be available -- try again in a moment."
        else:
            # Cloud fallback was already attempted but still leaked — use generic message
            logger.warning("[CHAT] LLM error string leaked into response: %s", final_answer[:120])
            final_answer = "I ran into a problem generating a response. The model may not be available -- try again in a moment."

    # Strip generic AI assistant intros / boilerplate (model ignoring FORMAT RULES)
    import re as _re
    _intro_patterns = [
        r"^(Hello!?\s+)?I'?m\s+(your\s+)?AI\s+assistant[^.!]*[.!]\s*",
        r"^I'?m here to help you with questions and tasks\.?\s*",
        r"^I'?m here to help[^.!]*[.!]\s*",
        r"^As an AI(?: assistant)?[^.!]*[.!]\s*",
    ]
    for _pat in _intro_patterns:
        final_answer = _re.sub(_pat, "", final_answer, flags=_re.IGNORECASE).lstrip()

    # Strip emojis — local models often add them despite instructions
    import unicodedata as _ud
    def _strip_emojis(text: str) -> str:
        return "".join(
            ch for ch in text
            if not (_ud.category(ch) in ("So", "Sm") or
                    0x1F300 <= ord(ch) <= 0x1FAFF or
                    0x2600 <= ord(ch) <= 0x27BF or
                    0xFE00 <= ord(ch) <= 0xFE0F or
                    0x1F1E0 <= ord(ch) <= 0x1F1FF)
        ).strip()
    final_answer = _strip_emojis(final_answer)

    def _collapse_repetitive_answer(text: str) -> str:
        value = str(text or "").strip()
        if not value:
            return value
        sentences = [s.strip() for s in _re.split(r"(?<=[.!?])\s+", value) if s.strip()]
        if len(sentences) < 4:
            return value
        normalized = [_re.sub(r"\s+", " ", s).strip().lower() for s in sentences]
        # Identical-prefix run of 4+
        first = normalized[0]
        repeated_prefix = 1
        for item in normalized[1:]:
            if item != first:
                break
            repeated_prefix += 1
        if repeated_prefix >= 4:
            return sentences[0]
        # Whole-answer 2- or 3-sentence cyclic pattern
        for pattern_len in (2, 3):
            if len(normalized) < pattern_len * 3:
                continue
            pattern = normalized[:pattern_len]
            if all(normalized[idx] == pattern[idx % pattern_len] for idx in range(len(normalized))):
                return " ".join(sentences[:pattern_len])
        # All sentences identical
        if len(set(normalized)) == 1 and len(normalized) >= 3:
            return sentences[0]
        # Any run of 6+ consecutive identical sentences in the middle or tail → truncate there
        run_start = None
        run_val = None
        run_len = 0
        for i, s in enumerate(normalized):
            if s == run_val:
                run_len += 1
                if run_len >= 6 and run_start is not None:
                    # Keep everything before the run plus the first sentence of the run
                    keep = sentences[:run_start + 1]
                    return " ".join(keep)
            else:
                run_start = i
                run_val = s
                run_len = 1
        return value

    final_answer = _collapse_repetitive_answer(final_answer)

    def _blocked_answer(reason: str, existing_answer: str) -> str:
        answer_text = str(existing_answer or "").strip()
        lower_answer = answer_text.lower()
        gate_debug = result.get("gate_debug") or {}
        slot_label = str(gate_debug.get("slot") or "").strip(" ?")
        meta_provenance = _is_meta_provenance_followup(effective_message)
        suspicious_markers = (
            "corrections from stored memory",
            "revise your answer",
            "original question:",
            "your draft answer:",
        )
        uncertainty_markers = (
            "conflicting information",
            "conflicting memories",
            "which is correct",
            "can't answer confidently",
            "i'm not confident",
            "i found a conflict",
        )
        suspicious = any(marker in lower_answer for marker in suspicious_markers)
        already_safe = any(marker in lower_answer for marker in uncertainty_markers)

        if "contradiction" in reason or "disclosure" in reason or "unresolved" in reason or "hard_conflict" in reason:
            if answer_text and already_safe and not suspicious:
                return answer_text
            if slot_label:
                return f"I have conflicting information about your {slot_label} and can't answer confidently yet. Which version is correct right now?"
            return "I have conflicting information about this and can't answer confidently yet. Which version is correct right now?"
        if "system_prompt" in reason:
            return (
                "I can't share my hidden instructions verbatim. "
                "If you tell me what you're trying to do, I can summarize the behavior instead."
            )
        if meta_provenance and ("explanatory_memory_fail" in reason or "degraded_output" in reason):
            return (
                "I remember this by storing your confirmed facts in memory and retrieving them when they're relevant. "
                "Facts about you come from what you've told me, while my assistant identity comes from my configured system role. "
                "If those records conflict, I disclose the conflict instead of silently picking a winner."
            )
        if "explanatory_memory_fail" in reason or "no_memory" in reason:
            # No relevant memory found — don't claim "conflicting information"
            if answer_text and not suspicious and "conflicting" not in lower_answer:
                return answer_text
            return "I don't have a stored memory for that topic. Tell me about it and I'll remember for next time."
        if "low_alignment" in reason or "degraded_output" in reason:
            if answer_text and not suspicious and "conflicting" not in lower_answer:
                return answer_text
            return "I found some related memories but couldn't build a confident answer. Could you be more specific?"
        if "uncertainty" in reason or "grounding_fail" in reason:
            if answer_text and not suspicious:
                return answer_text
            return "I'm not confident enough in my answer to share it. Could you give me more context?"
        if answer_text and not suspicious and "conflicting" not in lower_answer:
            return answer_text
        return "I wasn't able to generate a reliable response to that. Try rephrasing, or ask me to explain why."

    if not bool(result.get("gates_passed", True)):
        final_answer = _blocked_answer(str(result.get("gate_reason") or ""), final_answer)

    tasking_meta = None
    if tasking_enabled and bool(result.get("gates_passed", True)):
        allow_tasking = True
        if _TASKING_INTERVAL_SECONDS > 0:
            now_ts = time.time()
            tid = sanitize_thread_id(req.thread_id)
            with _TASKING_LOCK:
                last_ts = _TASKING_LAST_RUN.get(tid, 0.0)
                if now_ts - last_ts < _TASKING_INTERVAL_SECONDS:
                    allow_tasking = False
                else:
                    _TASKING_LAST_RUN[tid] = now_ts

        if not allow_tasking:
            tasking_meta = {
                "mode": "plan+coverage",
                "skipped": "interval",
                "interval_seconds": _TASKING_INTERVAL_SECONDS,
            }
        else:
            try:
                from personal_agent.tasking_loop import TaskingLoop

                tasking_loop = TaskingLoop(llm_client=llm_client)
                tasking_result = tasking_loop.run(effective_message, final_answer, allow_expansion=True)
                final_answer = tasking_result.final_answer
                tasking_meta = tasking_result.to_dict()
                tasking_meta["interval_seconds"] = _TASKING_INTERVAL_SECONDS
            except Exception as e:
                logger.debug(f"[TASKING] Tasking loop failed: {e}")
    _mark("tasking_done")
    if tasking_enabled:
        control_state.mark("validate", "tasking_checked", detail=str((tasking_meta or {}).get("mode") or "tasking"))

    # Caveat injection is now handled by the LLM via extra_context in crt_rag.py.
    # Blindly appending "(most recent update)" was too broad -- it fired on greetings,
    # meta-questions, and answers unrelated to the conflicted slot.
    caveat_injected = False
    if reintro_count > 0:
        logger.info(
            "[CAVEAT_NOTE] reintro_count=%d -- contradiction awareness handled by LLM via extra_context",
            reintro_count,
        )

    metadata: Dict[str, Any] = {
        "mode": result.get("mode"),
        "confidence": result.get("confidence"),
        "channel": req.channel,
        "actor_id": req.actor_id,
        "channel_destination_id": req.channel_destination_id,
        "meta_scope": req.meta_scope,
        "intent_alignment": result.get("intent_alignment"),
        "memory_alignment": result.get("memory_alignment"),
        "thinking": thinking_content or None,
        "thinking_trace_id": thinking_trace_id,
        "reflection_trace_id": reflection_trace_id,
        "reflection_confidence": reflection_result.confidence_score if reflection_result else None,
        "reflection_label": reflection_result.confidence_label if reflection_result else None,
        "style_profile": style_profile,
        "personality_profile": personality_profile,
        "reflection_scorecard": reflection_scorecard,
        "contradiction_detected": result.get("contradiction_detected"),
        "contradiction_resolved": result.get("contradiction_resolved"),
        "unresolved_contradictions_total": result.get("unresolved_contradictions_total"),
        "unresolved_hard_conflicts": result.get("unresolved_hard_conflicts"),
        "learned_suggestions": result.get("learned_suggestions") or [],
        "heuristic_suggestions": result.get("heuristic_suggestions") or [],
        "profile_updates": result.get("profile_updates") or [],
        "agent_activated": agent_activated,
        "agent_answer": agent_answer,
        "agent_trace": agent_trace_data,
        "agent_suggested_triggers": agent_suggested_triggers,
        "retrieved_memories": retrieved_mems,
        "prompt_memories": prompt_mems,
        "reintroduced_claims_count": reintro_count,
        "caveat_injected_for_reintroduced_claims": caveat_injected,
        "expanded": expanded,
        "expansion_reason": expansion_reason,
        "tasking": tasking_meta,
        "critic": critic_meta,
        "model_route": model_route,
        "model_override": model_override,
        "product_mode": ((runtime_config.get("product_mode") or {}).get("mode") if isinstance(runtime_config, dict) else None),
        "generation_provider": (model_route or {}).get("provider") if isinstance(model_route, dict) else None,
        "pre_gen_belief": result.get("pre_gen_belief"),
        "contradiction_entry": result.get("contradiction_entry"),
        "retrieval_edges": result.get("retrieval_edges"),
        "generation_source": result.get("generation_source"),
        "escalation": result.get("escalation"),
        "gpt_reference_used": isinstance(result.get("gpt_reference_packet"), dict),
        "gpt_reference_from_cache": bool(result.get("gpt_reference_from_cache")),
        "gpt_reference_topic": (result.get("gpt_reference_packet") or {}).get("topic_key") if isinstance(result.get("gpt_reference_packet"), dict) else None,
        "cloud_governance_used": result.get("cloud_governance_used", False),
        "groundcheck_bridge": groundcheck_bridge_meta,
        "gate_debug": result.get("gate_debug") or None,
    }

    collapse_trail_id = _log_collapse_trail(
        thread_id=req.thread_id,
        query=req.message,
        answer=final_answer,
        result=result,
        stage="chat_send",
        mode=str(req.mode) if req.mode else None,
        extra={
            "expanded": expanded,
            "tasking_enabled": tasking_enabled,
            "agent_activated": agent_activated,
        },
    )
    if collapse_trail_id:
        metadata["collapse_trail_id"] = collapse_trail_id

    # Build X-Ray data (memory transparency mode)
    xray_data = None
    try:
        if retrieved_mems:
            xray_data = {
                "memories_used": [
                    {
                        "text": (m.get("text") if isinstance(m, dict) else "")[:100],
                        "trust": m.get("trust") if isinstance(m, dict) else 0,
                        "confidence": m.get("confidence") if isinstance(m, dict) else 0,
                        "timestamp": m.get("timestamp") if isinstance(m, dict) else None,
                        "reintroduced_claim": m.get("reintroduced_claim") if isinstance(m, dict) else False,
                    }
                    for m in retrieved_mems[:5]
                    if isinstance(m, dict)
                ],
                "conflicts_detected": [],
                "reintroduced_claims_count": reintro_count,
            }

            try:
                open_contras = engine.ledger.get_open_contradictions(limit=10)
                for c in open_contras:
                    xray_data["conflicts_detected"].append(
                        {
                            "old": (c.claim_a_text or "")[:100],
                            "new": (c.claim_b_text or "")[:100],
                            "status": c.status.value if hasattr(c.status, "value") else str(c.status),
                        }
                    )
            except Exception:
                pass
    except Exception:
        pass

    # PHASE 1: Active learning, session record, episodic — all fired async.
    # These don't affect the answer; no reason to block the response on them.
    interaction_id = None
    _mark("active_learning_done")
    _mark("session_record_done")
    _mark("episodic_done")

    def _run_post_response_bookkeeping(
        _thread_id, _message, _final_answer, _result, _prompt_mems, _session_db, _engine_memory,
        _iid: str = "",
        _gen_info: Optional[Dict[str, Any]] = None,
    ):
        # Active learning
        try:
            coordinator = get_active_learning_coordinator()
            slots_inferred = _result.get("slots_extracted") or _result.get("facts") or {}
            facts_injected = [
                {"memory_id": m.get("memory_id"), "text": m.get("text"), "confidence": m.get("confidence")}
                for m in _prompt_mems
                if isinstance(m, dict) and m.get("memory_id")
            ]
            coordinator.record_interaction(
                thread_id=_thread_id,
                query=_message,
                response=_final_answer,
                response_type=str(_result.get("response_type") or "speech"),
                confidence=float(_result.get("confidence") or 0.0),
                gates_passed=bool(_result.get("gates_passed")),
                slots_inferred=slots_inferred if isinstance(slots_inferred, dict) else None,
                facts_injected=facts_injected if facts_injected else None,
                session_id=str(_result.get("session_id") or "default"),
                interaction_id=_iid or None,
            )
        except Exception as _e:
            logging.warning(f"[Phase1_BG] Failed to log interaction: {_e}")

        # Session record
        try:
            detected_slot = None
            slots = _result.get("slots_extracted")
            if isinstance(slots, dict) and slots:
                detected_slot = list(slots.keys())[0]
            _session_db.record_query(
                thread_id=_thread_id,
                query_text=_message,
                response_text=_final_answer,
                detected_slot=detected_slot,
            )
        except Exception as _e:
            logger.debug(f"[SESSION_BG] Error recording query: {_e}")

        # Episodic memory
        try:
            episodic_mgr = get_episodic_manager(memory_system=_engine_memory)
            episodic_mgr.process_interaction(
                thread_id=_thread_id,
                query=_message,
                response=_final_answer,
                response_time_ms=0,
            )
        except Exception as _e:
            logger.debug(f"[EPISODIC_BG] Error processing interaction: {_e}")

        # Activation log enrichment: update the retrieval activation record
        # with post-generation data (PCA coords, edges, contradictions, response type)
        try:
            from personal_agent.activation_log import log_activation, ActivationRecord, make_query_hash
            _act_mems = _result.get("retrieved_memories") or []
            if _act_mems:
                _act = ActivationRecord(
                    activation_id=f"act_{int(time.time()*1000)}_{hash(_message) % 10000}",
                    timestamp=time.time(),
                    thread_id=_thread_id,
                    query=_message[:500],
                    query_hash=make_query_hash(_message),
                    memory_ids=[str(m.get("memory_id") or m.get("id") or "") for m in _act_mems],
                    scores=[float(m.get("score") or 0) for m in _act_mems],
                    trusts=[float(m.get("trust") or 0) for m in _act_mems],
                    kinds=[str(m.get("kind") or "") for m in _act_mems],
                    pca_coords=[
                        {"x": float(m.get("pca_x") or 0), "y": float(m.get("pca_y") or 0),
                         "memory_id": str(m.get("memory_id") or "")}
                        for m in _act_mems if m.get("pca_x") is not None
                    ],
                    edges=_result.get("retrieval_edges") or [],
                    contradictions_detected=1 if _result.get("contradiction_detected") else 0,
                    contradiction_ids=[str((_result.get("contradiction_entry") or {}).get("ledger_id", ""))]
                        if _result.get("contradiction_detected") else [],
                    belief_confidence=float(_result.get("confidence") or 0),
                    response_type=str(_result.get("response_type") or ""),
                    generation_source=str((_gen_info or {}).get("generation_mode") or ""),
                )
                log_activation(str(_engine_memory.db_path), _act)
        except Exception as _act_err:
            logger.debug(f"[ACTIVATION_LOG] Post-gen enrichment failed: {_act_err}")

        # Training data log (append-only JSONL)
        try:
            from personal_agent.training_log import log_chat_turn
            _gi = _gen_info or {}
            log_chat_turn(
                thread_id=_thread_id,
                user_message=_message,
                assistant_response=_final_answer,
                model_used=str(_gi.get("model_used", "")),
                generation_mode=str(_gi.get("generation_mode", "local")),
                intent=str(_result.get("response_type") or "conversational"),
                latency_ms=int(_gi.get("latency_ms", 0)),
                memories_cited=len(_prompt_mems) if _prompt_mems else 0,
                governance_tier=str(_gi.get("governance_tier", "")),
                metadata={
                    "confidence": _result.get("confidence"),
                    "gates_passed": bool(_result.get("gates_passed")),
                    "gate_reason": str(_result.get("gate_reason") or ""),
                    "escalation": str(_result.get("escalation") or ""),
                    "generation_source": str(_result.get("generation_source") or ""),
                },
            )
        except Exception as _e:
            logger.debug(f"[TRAINING_LOG_BG] Error logging chat turn: {_e}")

        # CRT Session State — track per-turn epistemic signals
        try:
            from personal_agent.session_state import get_or_create_session, record_turn
            _crt_session = get_or_create_session(_thread_id)
            _crt_turn = record_turn(
                _crt_session,
                result=_result,
                prompt_mems=_prompt_mems,
                message=_message,
                engine_memory=_engine_memory,
            )
            print(f"[SESSION_STATE] turn={_crt_turn.turn_number} density={_crt_turn.density_score:.4f} "
                  f"cited={len(_crt_turn.memories_cited_ids)} slots={len(_crt_turn.slots_classified)} "
                  f"trust_shifts={len(_crt_turn.trust_shifts)}")
            # Emit trust_shift SSE events for live frontend visualization
            _TRUST_REASON_MAP = {
                "cited": "cited", "citation_bump": "cited", "citation": "cited",
                "corroborate": "corroborated", "nli_support": "corroborated", "support": "corroborated",
                "contradiction": "contradicted", "nli_contra": "contradicted", "contra": "contradicted",
                "decay": "decayed", "time_decay": "decayed",
                "reinforced": "reinforced", "reinforce": "reinforced",
            }
            _retrieval_by_id = {
                str(m.get("memory_id") or m.get("id") or ""): (str(m.get("text") or ""))[:80]
                for m in (result.get("retrieved_memories") or [])
            }
            for _ts in _crt_turn.trust_shifts:
                _ts_mid = str(_ts.get("memory_id", ""))
                _ts_reason_raw = str(_ts.get("reason", ""))
                _ts_reason = _TRUST_REASON_MAP.get(_ts_reason_raw.lower().strip(), _ts_reason_raw)
                _emit_pipeline_event({
                    "type": "trust_shift",
                    "metadata": {
                        "memoryId": _ts_mid,
                        "from": round(float(_ts.get("old_trust", 0)), 3),
                        "to": round(float(_ts.get("new_trust", 0)), 3),
                        "reason": _ts_reason,
                        "text": _retrieval_by_id.get(_ts_mid, ""),
                    },
                })
            # Emit drift event — intent alignment + trust delta signal
            _drift_count = len(_crt_turn.trust_shifts)
            _total_trust_delta = round(_crt_session.total_trust_delta, 3)
            if _drift_count > 0 or abs(_total_trust_delta) > 0.01:
                _emit_pipeline_event({
                    "type": "drift",
                    "content": f"{_drift_count} trust shift(s) this turn",
                    "metadata": {
                        "drift_count": _drift_count,
                        "total_trust_delta": _total_trust_delta,
                        "intent_alignment": round(float(result.get("intent_alignment") or 1.0), 3),
                    },
                })
            # Emit session_state snapshot — density + contradiction count
            _emit_pipeline_event({
                "type": "session_state",
                "content": f"density={_crt_session.cumulative_density:.4f}",
                "metadata": {
                    "cumulative_density": round(_crt_session.cumulative_density, 4),
                    "open_contradiction_count": int(_crt_session.open_contradiction_count),
                    "total_trust_delta": _total_trust_delta,
                    "turn_count": int(_crt_session.turn_count),
                    "memories_confirmed": int(_crt_session.memories_confirmed),
                },
            })

            # --- Density-triggered episodic extraction ---
            # Synchronous check: if density threshold hit, enqueue extraction now
            # instead of waiting for idle_scheduler's 10s poll.
            from personal_agent.session_state import should_extract as _should_extract
            if _should_extract(_crt_session):
                try:
                    from personal_agent.jobs_db import enqueue_job as _enqueue_job
                    from personal_agent.runtime_paths import resolve_jobs_db_path as _resolve_jdb
                    from datetime import datetime, timezone
                    _jobs_db = str(_resolve_jdb())
                    _jid = f"density_extract_{_thread_id}_{int(time.time())}"
                    _enqueue_job(
                        db_path=_jobs_db,
                        job_id=_jid,
                        job_type="heartbeat_learning",
                        created_at=datetime.now(timezone.utc).isoformat(),
                        payload={
                            "thread_id": _thread_id,
                            "memory_db": str(_engine_memory.db_path) if hasattr(_engine_memory, 'db_path') else "",
                            "trigger": "post_response_density",
                            "density": round(_crt_session.cumulative_density, 4),
                            "tokens": _crt_session.cumulative_tokens,
                        },
                        priority=1,
                    )
                    # Reset counters so we don't re-trigger next turn
                    _crt_session.cumulative_tokens = 0
                    _crt_session.cumulative_numerator = 0
                    _crt_session.last_extraction_ts = time.time()
                    print(f"[EXTRACTION] Post-response trigger: density={_crt_session.cumulative_density:.4f} job={_jid}")
                except Exception as _ext_err:
                    print(f"[EXTRACTION] Failed to enqueue: {_ext_err}")

        except Exception as _e:
            print(f"[SESSION_STATE_BG] Error: {_e}")
            import traceback; traceback.print_exc()

    try:
        _training_gen_info = {
            "model_used": str((model_route or {}).get("model") or "") if isinstance(model_route, dict) else "",
            "generation_mode": str(_gen_tracking.get("gen", "local")),
            "latency_ms": int(_gen_latency_ms),
            "governance_tier": str(metadata.get("governance_tier", "")),
        }
    except Exception:
        _training_gen_info = {}

    threading.Thread(
        target=_run_post_response_bookkeeping,
        args=(req.thread_id, req.message, final_answer, result, prompt_mems, session_db, engine.memory),
        kwargs={
            "_iid": _interaction_id,
            "_gen_info": _training_gen_info,
        },
        daemon=True,
    ).start()

    if greeting_text:
        metadata["greeting_shown"] = True
    if query_with_continuity != query_with_context:
        metadata["continuity_context_applied"] = True

    # ====== Auto Fact-Check: verify response against memories (background) ======
    try:
        from personal_agent.auto_fact_checker import schedule_fact_check
        schedule_fact_check(
            thread_id=req.thread_id,
            query=req.message,
            response=final_answer,
            memories=retrieved_mems if retrieved_mems else [],
        )
    except Exception as e:
        logger.debug(f"[AUTO_FC] Error scheduling fact check: {e}")
    _mark("fact_check_schedule_done")
    control_state.mark(
        "decide",
        "ready",
        detail=str(result.get("gate_reason") or ""),
        gates_passed=bool(result.get("gates_passed")),
    )
    control_state.mark(
        "learn",
        "recorded",
        detail="interaction+session+episodic+fact_check",
        interaction_id=interaction_id,
    )

    timing_rows = _timings()
    if timing_rows:
        metadata["pipeline_timings_ms"] = timing_rows
        metadata.setdefault(
            "pipeline_statuses",
            [f"{str(row.get('stage'))}:{float(row.get('dt_ms') or 0.0):.1f}ms" for row in timing_rows],
        )
        total_ms = float(timing_rows[-1].get("t_ms") or 0.0)
        logger.info(
            "[CHAT_TIMING] thread=%s total_ms=%.1f gate=%s mode=%s stages=%s",
            req.thread_id,
            total_ms,
            str(result.get("gate_reason") or ""),
            str(result.get("mode") or ""),
            " | ".join(f"{row.get('stage')}:{row.get('dt_ms')}ms" for row in timing_rows),
        )

    # ====== FIDELITY MIRROR (Breathing Loop) ======
    # Post-generation integrity check: did the response faithfully represent
    # the belief state? Three checks: belief fidelity, request alignment,
    # factual grounding. If below threshold, gate the response.
    try:
        from personal_agent.fidelity_mirror import check_fidelity

        # Inject gravity topology as a recognized source for grounding.
        # Without this, responses about belief tension/topology fail the
        # fidelity check because the gravity map isn't in retrieved memories.
        _fidelity_mems = list(retrieved_mems) if retrieved_mems else []
        try:
            from personal_agent._gravity_singleton import get_gravity_bridge
            _grav_for_fidelity = get_gravity_bridge()
            if _grav_for_fidelity is not None:
                _grav_text = _grav_for_fidelity.prompt_section(max_rooms=10)
                if _grav_text:
                    _fidelity_mems.append({
                        "text": _grav_text,
                        "trust": 0.9,
                        "kind": "gravity_topology",
                    })
        except Exception:
            pass

        _fidelity = check_fidelity(
            response=final_answer,
            query=effective_message,
            memories=_fidelity_mems,
        )
        metadata["fidelity_mirror"] = {
            "belief_fidelity": _fidelity.belief_fidelity,
            "request_alignment": _fidelity.request_alignment,
            "factual_grounding": _fidelity.factual_grounding,
            "composite": _fidelity.composite,
            "passed": _fidelity.passed,
            "latency_ms": _fidelity.latency_ms,
        }
        if not _fidelity.passed:
            result["gates_passed"] = False
            result["gate_reason"] = "fidelity_mirror"
            _safe_print(
                f"[FIDELITY_MIRROR] FAILED composite={_fidelity.composite:.3f} "
                f"(belief={_fidelity.belief_fidelity:.2f}, request={_fidelity.request_alignment:.2f}, "
                f"grounding={_fidelity.factual_grounding:.2f})"
            )
            for _f in _fidelity.findings:
                _safe_print(f"  [FIDELITY] {_f}")
        else:
            _safe_print(
                f"[FIDELITY_MIRROR] passed composite={_fidelity.composite:.3f} "
                f"({_fidelity.latency_ms:.0f}ms)"
            )
    except Exception as _fm_err:
        _safe_print(f"[FIDELITY_MIRROR] skipped: {_fm_err}")

    # ====== NLI ENFORCEMENT GATE (Bug #9 fix) ======
    # Structural veto: when gates_passed=False due to contradiction,
    # hedge the response instead of delivering it as-is.
    # This is the enforcement layer — advisory governance becomes structural.
    _gates_final = bool(result.get("gates_passed"))
    _gate_reason_final = result.get("gate_reason") if isinstance(result.get("gate_reason"), str) else None
    if not _gates_final and _gate_reason_final:
        _is_contradiction_gate = any(
            term in str(_gate_reason_final).lower()
            for term in ("contradiction", "nli", "ledger", "conflict")
        )
        _is_fidelity_gate = "fidelity" in str(_gate_reason_final).lower()

        if _is_contradiction_gate:
            # Build hedge prefix from contradiction context
            _contra_details = result.get("contradiction_details") or ""
            _critic_meta = result.get("critic_meta") or {}
            _contradictions_list = _critic_meta.get("contradictions") or []

            _hedge_lines = [
                "**Note:** My response may conflict with what I have on record.",
            ]
            if _contradictions_list:
                for _c_text in _contradictions_list[:3]:
                    _hedge_lines.append(f"- Stored belief: \"{str(_c_text)[:150]}\"")
            _hedge_lines.append(
                "I'm delivering my answer below, but flagging that my confidence is lower than usual. "
                "If something sounds wrong, correct me and I'll update."
            )
            _hedge_prefix = "\n".join(_hedge_lines) + "\n\n---\n\n"
            final_answer = _hedge_prefix + final_answer
            _safe_print(
                f"[NLI_ENFORCEMENT] Gate failed ({_gate_reason_final}) — "
                f"hedged response with contradiction disclosure ({len(_contradictions_list)} conflicts)"
            )
            metadata["nli_enforcement"] = {
                "action": "hedged",
                "gate_reason": _gate_reason_final,
                "contradictions_disclosed": len(_contradictions_list),
            }

        elif _is_fidelity_gate:
            # Fidelity mirror failed — response may not be grounded in memory
            # or may not answer the actual question. Add disclosure.
            _fm_data = metadata.get("fidelity_mirror", {})
            _fm_findings = []
            if _fm_data.get("belief_fidelity", 1.0) < 0.2:
                _fm_findings.append("I may not be drawing on what I know about you")
            if _fm_data.get("request_alignment", 1.0) < 0.2:
                _fm_findings.append("I may not be directly answering your question")
            if _fm_data.get("factual_grounding", 1.0) < 0.1:
                _fm_findings.append("my claims aren't well-grounded in stored facts")

            if _fm_findings:
                _fidelity_prefix = (
                    "**Heads up:** " + ", and ".join(_fm_findings) + ". "
                    "Take this with lower confidence.\n\n---\n\n"
                )
                final_answer = _fidelity_prefix + final_answer
                _safe_print(
                    f"[FIDELITY_ENFORCEMENT] Gate failed — "
                    f"hedged response with fidelity disclosure ({len(_fm_findings)} findings)"
                )
                metadata["fidelity_enforcement"] = {
                    "action": "hedged",
                    "gate_reason": _gate_reason_final,
                    "findings": _fm_findings,
                }

    return _chat_response(
        answer=final_answer,
        response_type=str(result.get("response_type") or "speech"),
        gates_passed=_gates_final,
        gate_reason=_gate_reason_final,
        metadata=metadata,
        xray=xray_data,
    )


def _run_shared_chat_pipeline(req: ChatSendRequest, request: Request) -> ChatSendResponse:
    """Single response pipeline used by both /send and /stream."""
    return chat_send(req, request)


# ============================================================================
# POST /api/chat/stream
# ============================================================================


@router.post("/stream")
def chat_stream(req: ChatSendRequest, request: Request, authorization: Optional[str] = Header(None)):
    """Stream using the same shared pipeline as /send to prevent drift."""
    # Propagate authenticated user_id into memory context variable
    uid = resolve_user_id(authorization)
    if uid:
        from personal_agent.crt_memory import _request_user_id
        _request_user_id.set(uid)
    logger.info(f"[STREAM] /api/chat/stream called with message: {req.message[:50]}...")

    def generate_stream():
        from personal_agent.event_bus import get_event_bus
        _session_db = get_thread_session_db()
        runtime = ChatStreamRuntime(
            req=req,
            request=request,
            authorization=authorization,
            uid=uid,
            safe_print=_safe_print,
            session_db=_session_db,
            event_bus=get_event_bus(),
        )
        _sse = runtime.emit
        _status = runtime.emit_status
        _phase = runtime.emit_phase
        _ensure_governed_task = runtime.ensure_governed_task
        _update_governed_task = runtime.update_governed_task
        _append_governed_event = runtime.append_governed_event
        _governed_task = runtime.governed_task

        try:
            # ── Upfront activity signals ──────────────────────────────────
            q_lower = req.message.lower()
            yield runtime.emit_phase('analyze', 'Reading request')
            yield runtime.emit_status('reading context')
            yield runtime.emit_phase('analyze', end=True)

            # ── Intent classification (fast, pattern-based) ───────────────
            try:
                from personal_agent.task_agent import (
                    classify_intent as _classify_intent,
                    CRTTaskAgent,
                    TaskIntent,
                )
                _resume_task_intent = None
                _resume_user_confirmed = False
                _resume_outcome = yield from try_resume_or_resolve(
                    runtime,
                    recent_history=recent_history if "recent_history" in locals() else None,
                )
                if _resume_outcome and _resume_outcome.terminal:
                    return
                if _resume_outcome:
                    _resume_task_intent = _resume_outcome.task_intent
                    _resume_user_confirmed = _resume_outcome.user_confirmed
                    _orig_classify_intent = _classify_intent

                    def _classify_intent(message, active_task=None):
                        nonlocal _resume_task_intent
                        if _resume_task_intent is not None:
                            _intent = _resume_task_intent
                            _resume_task_intent = None
                            return _intent
                        return _orig_classify_intent(message, active_task=active_task)

                # ── AGENT LOOP RESUME (must be before intent classify) ────
                # If there's a suspended agent loop for this thread, the user's
                # current message is their answer to the agent loop's ask_user question.
                # Reconstruct the loop from the checkpoint and continue.
                try:
                    _suspended = _session_db.get_suspended_loop(req.thread_id)
                    if _suspended:
                        _governed_task = _session_db.get_active_governed_task(req.thread_id)
                        if _governed_task and str(_governed_task.get("source") or "") == "agent_loop":
                            _update_governed_task(
                                status=GovernedTaskStatus.RUNNING.value,
                                wait_kind=None,
                                question=None,
                            )
                            _append_governed_event("resume", req.message, {"resume_kind": str(_suspended.get("type") or "ask_user")})
                        _session_db.clear_suspended_loop(req.thread_id)
                        _safe_print(f"[ORCHESTRATOR] Resuming suspended loop — user answered: {req.message[:80]!r}")

                        _suspended_type = _suspended.get("type", "ask_user")

                        if _suspended_type == "diff_write":
                            # ── Diff preview resume ─────────────────────────
                            # User either approved or rejected a file write.
                            # Detect approval: any affirmative in the message.
                            _dw_raw_meta = _suspended.get("diff_data", {}).get("_raw_meta", {})
                            _dw_write_path = _dw_raw_meta.get("_write_path", "")
                            _dw_write_content = _dw_raw_meta.get("_write_content", "")
                            _dw_target_path = _dw_raw_meta.get("target_path", "?")
                            _dw_msg_lower = req.message.lower().strip()
                            _dw_approved = any(w in _dw_msg_lower for w in (
                                "yes", "approve", "ok", "sure", "do it", "go ahead", "confirm", "write it"
                            )) and not any(w in _dw_msg_lower for w in ("no", "reject", "cancel", "don't", "skip"))
                            if _dw_approved and _dw_write_path and _dw_write_content:
                                try:
                                    import os as _os_dw
                                    _os_dw.makedirs(_os_dw.path.dirname(_dw_write_path) or ".", exist_ok=True)
                                    with open(_dw_write_path, "w", encoding="utf-8") as _dw_f:
                                        _dw_f.write(_dw_write_content)
                                    _dw_result_msg = f"Written {len(_dw_write_content)} chars to {_dw_target_path}"
                                    _safe_print(f"[ORCHESTRATOR] Diff approved + written: {_dw_target_path}")
                                except Exception as _dw_err:
                                    _dw_result_msg = f"Write failed: {_dw_err}"
                                    _safe_print(f"[ORCHESTRATOR] Diff write error: {_dw_err}")
                            else:
                                _dw_result_msg = f"User rejected write to {_dw_target_path}."
                                _safe_print(f"[ORCHESTRATOR] Diff rejected: {_dw_target_path}")

                            yield _sse({"type": "token", "content": _dw_result_msg + "\n\n"})

                            # Build resume prompt: original task + steps done + write result
                            _resume_objective = _suspended.get("objective", req.message)
                            _resume_steps = _suspended.get("steps_done", [])
                            _resume_answer_so_far = _suspended.get("orch_answer_so_far", "") + _dw_result_msg + "\n\n"
                            _resume_steps_text = "\n".join(
                                f"  - {s.get('tool', '?')}: {str(s.get('status',''))}"
                                for s in _resume_steps
                            ) if _resume_steps else ""
                            _resume_msg = (
                                f"{_resume_objective}\n\n"
                                f"[CONTEXT: You paused to show a diff preview for {_dw_target_path!r}. "
                                f"Result: {_dw_result_msg}\n"
                                + (f"Previous steps completed:\n{_resume_steps_text}\n" if _resume_steps_text else "")
                                + f"Continue and complete the task.]"
                            )

                        else:
                            # ── ask_user resume (default) ───────────────────
                            # Build resume context injecting the user's answer
                            _resume_objective = _suspended.get("objective", req.message)
                            _resume_steps = _suspended.get("steps_done", [])
                            _resume_question = _suspended.get("question", "")
                            _resume_answer_so_far = _suspended.get("orch_answer_so_far", "")

                            # Format previous steps summary for the agent loop's context
                            _resume_steps_text = ""
                            if _resume_steps:
                                _resume_steps_text = "\n".join(
                                    f"  - {s.get('tool', '?')}: {str(s.get('status',''))}"
                                    for s in _resume_steps
                                )

                            # The resume message: re-state the objective with answer injected
                            _resume_msg = (
                                f"{_resume_objective}\n\n"
                                f"[CONTEXT: You were executing this task and paused to ask: "
                                f"{_resume_question!r}\n"
                                f"The user replied: {req.message!r}\n"
                                + (f"Previous steps completed:\n{_resume_steps_text}\n" if _resume_steps_text else "")
                                + f"Continue the task with this answer. Do not re-plan.]"
                            )

                        # Re-use the agent loop orchestrator path directly
                        yield _status("Resuming...")
                        try:
                            from personal_agent.cookie_orchestrator import Orchestrator
                            _r_brain_mode, _r_brain = build_orchestrator_brain(req, uid)
                            _r_remaining = _suspended.get("remaining_iterations", 8)
                            _safe_print(f"[ORCHESTRATOR] Resume brain: {_r_brain_mode}, remaining_iterations: {_r_remaining}")
                            _r_orch = Orchestrator(brain=_r_brain, max_iterations=max(3, _r_remaining))
                            _r_gen = _r_orch.run(_resume_msg)
                            _r_orch_answer = _resume_answer_so_far
                            _r_steps: list = list(_resume_steps)

                            _r_send_val = None
                            while True:
                                try:
                                    _r_event = _r_gen.send(_r_send_val) if _r_send_val is not None else next(_r_gen)
                                    _r_send_val = None
                                except StopIteration:
                                    break
                                _r_etype = _r_event.get("type", "")

                                if _r_etype == "plan":
                                    _plan_txt = _r_event.get("content", "")
                                    if _plan_txt:
                                        yield _sse({"type": "token", "content": _plan_txt + "\n\n"})
                                        _r_orch_answer += _plan_txt + "\n\n"

                                elif _r_etype in ("thinking", "think"):
                                    yield _sse({
                                        "type": "agent_thinking_token",
                                        "content": _r_event.get("content", ""),
                                        "metadata": {"step": "tool_loop"},
                                    })

                                elif _r_etype == "tool_call":
                                    _rt_name = _r_event.get("tool", "")
                                    _rt_args = _r_event.get("args", {})
                                    _rt_result = _r_event.get("result", "")
                                    _rt_status = _r_event.get("status", "ok")
                                    _rt_ms = _r_event.get("latency_ms")
                                    yield _sse({"type": "tool_start", "content": f"Running {_rt_name}...", "metadata": {"tool_name": _rt_name, "input": _rt_args}})
                                    yield _sse({"type": "tool_result", "content": _rt_result[:500], "metadata": {"tool_name": _rt_name, "status": _rt_status, "step_index": len(_r_steps), "duration_ms": _rt_ms}})
                                    _append_governed_event("tool_result", _rt_result[:500], {"tool_name": _rt_name, "status": _rt_status, "step_index": len(_r_steps), "duration_ms": _rt_ms})
                                    _r_steps.append({"tool": _rt_name, "args": _rt_args, "status": _rt_status})

                                elif _r_etype == "ask_user":
                                    # Nested ask_user — suspend again
                                    _r_question = _r_event.get("content", "")
                                    yield _sse({"type": "token", "content": _r_question})
                                    _session_db.store_suspended_loop(req.thread_id, {
                                        "objective": _resume_objective,
                                        "steps_done": _r_steps,
                                        "iteration": 0,
                                        "question": _r_question,
                                        "orch_answer_so_far": _r_orch_answer,
                                        "remaining_iterations": getattr(_r_orch, 'max_iterations', 8) - len(_r_steps),
                                    })
                                    _update_governed_task(
                                        status=GovernedTaskStatus.AWAITING_USER.value,
                                        wait_kind=GovernedTaskWaitKind.ASK_USER.value,
                                        question=_r_question,
                                        steps_done=list(_r_steps),
                                        orch_answer_so_far=_r_orch_answer,
                                        remaining_iterations=max(0, getattr(_r_orch, 'max_iterations', 8) - len(_r_steps)),
                                    )
                                    _append_governed_event("ask_user", _r_question, {"task_status": GovernedTaskStatus.AWAITING_USER.value})
                                    yield _sse({"type": "done", "content": _r_orch_answer, "metadata": {"loop_suspended": True, "loop_question": _r_question, "response_type": "ask_user"}})
                                    return

                                elif _r_etype == "response":
                                    _r_resp = _r_event.get("content", "")
                                    if _r_resp:
                                        yield _sse({"type": "token", "content": _r_resp})
                                        _r_orch_answer += _r_resp

                            # Done — yield final done event
                            if _governed_task:
                                _governed_task = _session_db.complete_governed_task(str(_governed_task["task_id"]), _r_orch_answer) or _governed_task
                                _append_governed_event("done", _r_orch_answer, {"task_status": GovernedTaskStatus.COMPLETED.value})
                            yield _sse({"type": "done", "content": _r_orch_answer, "metadata": {
                                "response_type": "speech",
                                "tool_calls": _r_steps,
                                "orchestrator": "agent_loop_resume",
                            }})
                            return

                        except Exception as _resume_err:
                            if _governed_task:
                                _governed_task = _session_db.fail_governed_task(str(_governed_task["task_id"]), str(_resume_err)) or _governed_task
                                _append_governed_event("error", str(_resume_err), {"task_status": GovernedTaskStatus.FAILED.value})
                            _safe_print(f"[ORCHESTRATOR] Resume failed: {_resume_err}")
                            yield _sse({"type": "token", "content": f"I ran into an issue resuming our conversation: {_resume_err}"})
                            yield _sse({"type": "done", "content": "", "metadata": {"response_type": "error"}})
                            return

                except Exception as _suspend_check_err:
                    _safe_print(f"[ORCHESTRATOR] Suspend check failed (non-fatal): {_suspend_check_err}")

                # ── REMINDER CONFIRMATION (must be FIRST, before any LLM) ──
                try:
                    _pend_rem_early = _session_db.get_pending_reminder(req.thread_id)
                    if isinstance(_pend_rem_early, dict) and _is_confirmation_yes(req.message):
                        _safe_print("[REMINDER_CONFIRM] Fast-path: confirming pending reminder (early)")
                        _rem_text_e = str(_pend_rem_early.get("reminder_text") or "").strip()
                        _rem_ts_e = float(_pend_rem_early.get("scheduled_at") or 0.0)
                        if _rem_text_e and _rem_ts_e > time.time():
                            _db_path_e = str(getattr(request.app.state, "scheduled_tasks_db_path", "") or "")
                            if _db_path_e:
                                _task_e = schedule_reminder(
                                    db_path=_db_path_e,
                                    thread_id=req.thread_id,
                                    reminder_text=_rem_text_e,
                                    scheduled_time=datetime.fromtimestamp(_rem_ts_e),
                                )
                                _session_db.clear_pending_reminder(req.thread_id)
                                _human_time_e = _format_reminder_time(_rem_ts_e)
                                _confirm_ans = (
                                    f"Confirmed. I will remind you to '{_rem_text_e}' on {_human_time_e}."
                                )
                                _safe_print(f"[REMINDER_CONFIRM] Scheduled: {_rem_text_e} at {_human_time_e}")
                                yield _sse({"type": "token", "content": _confirm_ans})
                                yield _sse({"type": "done", "content": _confirm_ans,
                                            "metadata": {"mode": "deterministic_reminder",
                                                         "reminder_scheduled": True}})
                                return
                        _session_db.clear_pending_reminder(req.thread_id)
                except Exception as _rem_early_err:
                    _safe_print(f"[REMINDER_CONFIRM] Early check failed: {_rem_early_err}")

                _active_task = _session_db.get_pending_task(req.thread_id)

                # ── Check for pending agentic checkpoint confirmation ─────
                _pending_cp = _session_db.get_pending_checkpoint(req.thread_id)
                _user_confirmed = _resume_user_confirmed
                if _pending_cp:
                    # Check if this is a disambiguation response (user selected an intent type)
                    _cp_source = _pending_cp.get("intent", {}).get("source", "")
                    _cp_suggested = [
                        a.get("value", "") for a in
                        (_pending_cp.get("metadata", {}) or {}).get("suggested_actions", [])
                    ]
                    _msg_stripped = req.message.strip().lower()
                    if _cp_source in ("embedding_ambiguous",) and _msg_stripped in _cp_suggested:
                        # User disambiguated — create a TaskIntent for the chosen type
                        _chosen_intent = _msg_stripped
                        _route = "conversational" if _chosen_intent == "conversational" else "task"
                        _task_intent = TaskIntent(
                            route=_route,
                            intent_type=_chosen_intent,
                            slots={},
                            confidence=0.95,
                            reason="user_disambiguated",
                            source="embedding_ambiguous",
                        )
                        _user_confirmed = True
                        _session_db.clear_pending_checkpoint(req.thread_id)
                        logger.info(f"[STREAM] User disambiguated: {_chosen_intent}")

                        # Record correction for learning
                        try:
                            from personal_agent.task_agent import _get_semantic_router
                            _sr = _get_semantic_router()
                            if _sr:
                                _original = _pending_cp.get("intent", {}).get("intent_type", "ambiguous")
                                _sr.record_correction(
                                    req.message, _original, _chosen_intent, "user_disambiguate"
                                )
                        except Exception:
                            pass

                    else:
                        _confirmation = _parse_confirm(req.message)
                        if _confirmation is True:
                            _cp_data = _pending_cp["intent"]

                            # ── Agent Loop checkpoint resume (Sprint 14) ──
                            if _cp_data.get("_agent_loop"):
                                _session_db.clear_pending_checkpoint(req.thread_id)
                                logger.info("[STREAM] User confirmed agent loop checkpoint — resuming loop")
                                try:
                                    from personal_agent.agent_tool_loop import AgentToolLoop, _execute_tool
                                    _get_llm_alr = request.app.state.get_llm_client
                                    _llm_client_alr = _get_llm_alr()
                                    _rt_cfg_alr = get_runtime_config()
                                    _al_cfg_alr = _rt_cfg_alr.get("agent_loop", {})

                                    # Wire user tooling settings for resume path too
                                    try:
                                        import auth as _auth_tooling_r
                                        _uid_tooling_r = int(uid) if uid else 1
                                        _user_fallback_r = _auth_tooling_r.get_user_setting(_uid_tooling_r, "tooling_fallback_policy", "")
                                        if _user_fallback_r and _llm_client_alr is not None:
                                            _llm_client_alr.fallback_policy = _user_fallback_r
                                        for _role_r in ("fast", "reasoning", "tool_loop", "answer"):
                                            _user_role_r = _auth_tooling_r.get_user_setting(_uid_tooling_r, f"tooling_model_role_{_role_r}", "")
                                            if _user_role_r and _llm_client_alr is not None:
                                                if not hasattr(_llm_client_alr, "model_roles") or _llm_client_alr.model_roles is None:
                                                    _llm_client_alr.model_roles = {}
                                                _llm_client_alr.model_roles[_role_r] = _user_role_r
                                    except Exception as _tooling_r_err:
                                        logger.warning("[AGENT_LOOP_RESUME] Failed to read tooling settings: %s", _tooling_r_err)

                                    _loop_state = _cp_data.get("_loop_state", {})
                                    _pending_tool = _loop_state.get("tool_name", "")
                                    _pending_args = _loop_state.get("tool_args", {})
                                    _original_msg = _loop_state.get("message", req.message)

                                    # Execute the confirmed tool first
                                    yield _sse({
                                        "type": "tool_start",
                                        "content": f"▷ {_pending_tool}",
                                        "metadata": {"tool_name": _pending_tool, "input": _pending_args, "step_index": 0},
                                    })
                                    _confirmed_result = _execute_tool(_pending_tool, _pending_args, req.thread_id)
                                    yield _sse({
                                        "type": "tool_result",
                                        "content": _confirmed_result["content"][:500],
                                        "metadata": {**_confirmed_result.get("metadata", {}), "status": _confirmed_result["status"], "step_index": 0},
                                    })

                                    # Now re-run the agent loop with the confirmed result already in context
                                    _alr_engine = None
                                    try:
                                        _alr_engine = request.app.state.get_engine(req.thread_id)
                                    except Exception:
                                        pass
                                    _loop_alr = AgentToolLoop(
                                        _llm_client_alr,
                                        session_db=_session_db,
                                        max_iterations=_al_cfg_alr.get("max_iterations", 10),
                                        show_thinking=_al_cfg_alr.get("show_thinking", True),
                                        engine=_alr_engine,
                                    )

                                    # Build messages with the confirmed tool result already included
                                    _resume_history = []
                                    if 'recent_history' in dir():
                                        _resume_history = recent_history
                                    _resume_msgs = _loop_alr._build_messages(_original_msg, _resume_history)
                                    import json as _json_alr
                                    _resume_msgs.append({
                                        "role": "assistant", "content": None,
                                        "tool_calls": [{"id": "call_confirmed", "type": "function",
                                                       "function": {"name": _pending_tool,
                                                                   "arguments": _json_alr.dumps(_pending_args)}}],
                                    })
                                    _resume_msgs.append({
                                        "role": "tool", "tool_call_id": "call_confirmed",
                                        "content": _confirmed_result["content"][:4000],
                                    })

                                    # Continue the loop from where we left off
                                    _alr_gen = _loop_alr.run.__wrapped__(_loop_alr, _original_msg, req.thread_id) if hasattr(_loop_alr.run, '__wrapped__') else None

                                    # Simpler: just create a new loop with the augmented messages
                                    _alr_answer = ""
                                    _alr_steps = [_confirmed_result.get("metadata", {})]
                                    _alr_schemas = _loop_alr._build_tool_schemas(None)

                                    for _alr_iter in range(_al_cfg_alr.get("max_iterations", 10) - 1):
                                        try:
                                            _alr_resp = _llm_client_alr.chat_with_tools(
                                                _resume_msgs, tools=_alr_schemas, max_tokens=2000, temperature=0.1,
                                            )
                                        except Exception as _alr_llm_err:
                                            logger.error("[AGENT_LOOP_RESUME] LLM error: %s", _alr_llm_err)
                                            yield _sse({"type": "token", "content": f"Error during continuation: {_alr_llm_err}"})
                                            break

                                        _alr_tcs = _alr_resp.get("tool_calls", [])
                                        _alr_text = (_alr_resp.get("content") or "").strip()

                                        if not _alr_tcs:
                                            if _alr_text:
                                                from personal_agent.text_utils import strip_thinking_tags
                                                _alr_clean = strip_thinking_tags(_alr_text)
                                                yield _sse({"type": "token", "content": _alr_clean})
                                                _alr_answer = _alr_clean
                                            break

                                        for _alr_tc in _alr_tcs:
                                            _alr_tn = _alr_tc.get("name", "")
                                            _alr_ta = _alr_tc.get("arguments", {})
                                            if isinstance(_alr_ta, str):
                                                try:
                                                    _alr_ta = _json_alr.loads(_alr_ta)
                                                except Exception:
                                                    _alr_ta = {}

                                            from personal_agent.agent_tool_loop import _needs_checkpoint
                                            if _needs_checkpoint(_alr_tn):
                                                # Another checkpoint needed — store and pause
                                                from personal_agent.agent_tool_loop import _describe_tool_action
                                                yield _sse({
                                                    "type": "agent_checkpoint",
                                                    "content": f"I need to {_describe_tool_action(_alr_tn, _alr_ta)}. Go ahead?",
                                                    "metadata": {
                                                        "requires_confirmation": True,
                                                        "checkpoint_tier": "medium",
                                                        "tool_name": _alr_tn, "tool_args": _alr_ta,
                                                        "intent": _alr_tn, "confidence": 0.95, "slots": _alr_ta,
                                                    },
                                                })
                                                _session_db.store_pending_checkpoint(
                                                    thread_id=req.thread_id,
                                                    intent_data={
                                                        "route": "task", "intent_type": _alr_tn,
                                                        "slots": _alr_ta, "confidence": 0.95,
                                                        "reason": "agent_loop_continuation",
                                                        "source": "agent_loop",
                                                        "_agent_loop": True,
                                                        "_loop_state": {"message": _original_msg,
                                                                       "tool_name": _alr_tn, "tool_args": _alr_ta},
                                                    },
                                                    checkpoint_tier="medium",
                                                    metadata={"tool_name": _alr_tn, "tool_args": _alr_ta},
                                                )
                                                yield _sse({"type": "done", "content": "",
                                                           "metadata": {"checkpoint_pending": True, "agent_loop": True}})
                                                return

                                            yield _sse({"type": "tool_start", "content": f"▷ {_alr_tn}",
                                                       "metadata": {"tool_name": _alr_tn, "input": _alr_ta,
                                                                    "step_index": len(_alr_steps)}})
                                            _alr_res = _execute_tool(_alr_tn, _alr_ta, req.thread_id)
                                            _alr_steps.append(_alr_res.get("metadata", {}))
                                            yield _sse({"type": "tool_result", "content": _alr_res["content"][:500],
                                                       "metadata": {**_alr_res.get("metadata", {}), "status": _alr_res["status"],
                                                                    "step_index": len(_alr_steps) - 1}})

                                            _resume_msgs.append({
                                                "role": "assistant", "content": None,
                                                "tool_calls": [{"id": f"call_r{_alr_iter}_{_alr_tn}", "type": "function",
                                                               "function": {"name": _alr_tn,
                                                                           "arguments": _json_alr.dumps(_alr_ta)}}],
                                            })
                                            _resume_msgs.append({
                                                "role": "tool", "tool_call_id": f"call_r{_alr_iter}_{_alr_tn}",
                                                "content": _alr_res["content"][:4000],
                                            })

                                    yield _sse({"type": "done", "content": _alr_answer,
                                               "metadata": {"tool_calls": _alr_steps, "agent_loop": True,
                                                            "response_type": "task", "gates_passed": True}})
                                    return

                                except Exception as _alr_err:
                                    logger.warning("[STREAM] Agent loop resume failed: %s", _alr_err, exc_info=True)
                                    # Fall through to legacy confirmation path

                            # ── Plan proposal checkpoint (plan_create approval) ──
                            elif _cp_data.get("_plan_proposal"):
                                _session_db.clear_pending_checkpoint(req.thread_id)
                                _plan_data = _cp_data.get("_plan_data", {})
                                _plan_title = _plan_data.get("title", "Untitled Plan")
                                _plan_steps = _plan_data.get("steps", [])
                                _safe_print(f"[PLAN] User approved plan: {_plan_title}")

                                # Save plan to workspace
                                import time as _plan_time
                                _plan_file = os.path.join("D:/AI_round2/workspace", f"plan_{int(_plan_time.time())}.json")
                                os.makedirs(os.path.dirname(_plan_file), exist_ok=True)
                                _plan_save = {
                                    "title": _plan_title,
                                    "steps": [{"title": s.get("title", s) if isinstance(s, dict) else str(s),
                                               "description": s.get("description", "") if isinstance(s, dict) else "",
                                               "status": "pending"} for s in _plan_steps],
                                    "created": _plan_time.strftime("%Y-%m-%d %H:%M:%S"),
                                    "status": "active",
                                    "approved": True,
                                    "thread_id": req.thread_id,
                                }
                                import json as _plan_json
                                with open(_plan_file, "w", encoding="utf-8") as _pf:
                                    _plan_json.dump(_plan_save, _pf, indent=2)

                                _step_list = "\n".join(f"  {i+1}. {s.get('title', s) if isinstance(s, dict) else s}" for i, s in enumerate(_plan_steps))
                                yield _sse({
                                    "type": "token",
                                    "content": f"Plan approved and saved: **{_plan_title}**\n\n{_step_list}\n\nSaved to: {_plan_file}",
                                })
                                yield _sse({
                                    "type": "done",
                                    "content": f"Plan approved: {_plan_title}",
                                    "metadata": {"plan_approved": True, "plan_file": _plan_file},
                                })
                                return

                            # User confirmed — re-use stored intent, mark confirmed (legacy path)
                            _task_intent = TaskIntent(
                                route=_cp_data["route"],
                                intent_type=_cp_data["intent_type"],
                                slots=_cp_data.get("slots", {}),
                                confidence=_cp_data.get("confidence", 0.9),
                                reason=_cp_data.get("reason", ""),
                            )
                            _user_confirmed = True
                            _session_db.clear_pending_checkpoint(req.thread_id)
                            logger.info("[STREAM] User confirmed agentic checkpoint")
                        elif _confirmation is False:
                            # User denied — emit cancellation and return immediately.
                            _cancelled_intent = _pending_cp.get("intent", {})
                            _governed_task = _session_db.get_active_governed_task(req.thread_id)
                            _session_db.clear_pending_checkpoint(req.thread_id)
                            _session_db.clear_pending_task(req.thread_id)
                            if _governed_task and str(_governed_task.get("source") or "") == "agent_loop":
                                _governed_task = _session_db.cancel_governed_task(
                                    str(_governed_task["task_id"]),
                                    "Task cancelled. What would you like to do instead?",
                                ) or _governed_task
                                _append_governed_event("cancelled", "Task cancelled. What would you like to do instead?", {"task_status": GovernedTaskStatus.CANCELLED.value})
                            logger.info("[STREAM] User denied agentic checkpoint — emitting cancellation")
                            yield _sse({
                                "type": "task_cancelled",
                                "content": "Task cancelled. What would you like to do instead?",
                                "metadata": {
                                    "cancelled_intent": _cancelled_intent.get("intent_type", ""),
                                    "cancelled_service": _cancelled_intent.get("slots", {}).get("service", ""),
                                },
                            })
                            yield _sse({
                                "type": "done",
                                "content": "Task cancelled. What would you like to do instead?",
                                "metadata": {"task_cancelled": True},
                            })
                            return
                        else:
                            # Ambiguous — treat as new message, clear stale checkpoint
                            _session_db.clear_pending_checkpoint(req.thread_id)
                            _task_intent = _classify_intent(query_with_continuity, active_task=_active_task)
                            logger.info("[STREAM] Ambiguous checkpoint response — reclassifying")
                else:
                    _task_intent = _classify_intent(query_with_continuity, active_task=_active_task)

            except Exception as _cie:
                logger.error("[STREAM] INTENT CLASSIFIER ERROR: %s", _cie, exc_info=True)
                _task_intent = None
                _active_task = None
                _user_confirmed = False

            # ── CAPABILITY-AWARE RE-ROUTE (Sprint 12) ──────────────────────
            # If the classifier said "conversational" but the message clearly
            # matches a tool capability, override. This catches cases like
            # "what apps are open?" falling through to conversational when
            # system_info can answer it.
            _safe_print(f"[INTENT_DEBUG] _task_intent={_task_intent}, route={getattr(_task_intent, 'route', None)}, type={getattr(_task_intent, 'intent_type', None)}, conf={getattr(_task_intent, 'confidence', None)}")
            if _task_intent is not None and _task_intent.route in ("conversational", "clarify"):
                try:
                    _rerouted = _capability_reroute(req.message, _task_intent)
                    _safe_print(f"[INTENT_DEBUG] capability_reroute result: {_rerouted}")
                    if _rerouted is not None:
                        logger.info(
                            "[STREAM] Capability re-route: %s → %s (was conversational)",
                            req.message[:60], _rerouted.intent_type,
                        )
                        _task_intent = _rerouted
                except Exception as _rre:
                    _safe_print(f"[INTENT_DEBUG] capability_reroute EXCEPTION: {_rre}")
                    logger.debug("[STREAM] capability re-route check failed: %s", _rre)

            # ── COMPOUND INTENT UPGRADE (Sprint 8) ────────────────────────
            # If the classifier returned a single task intent (or conversational
            # due to multi-action confusion) but the message contains additional
            # tool-worthy clauses, upgrade to multi_intent so the orchestrator
            # can run them in parallel.
            if (
                _task_intent is not None
                and _task_intent.route in ("task", "conversational")
                and _task_intent.intent_type not in ("multi_intent", "multi_step", "task_continuation")
            ):
                try:
                    _extra_intents = []
                    for _cp, _ci in _COMPOUND_INTENT_PATTERNS:
                        if _cp.search(req.message) and _ci != _task_intent.intent_type:
                            if not any(e["type"] == _ci for e in _extra_intents):
                                _extra_intents.append({"type": _ci, "confidence": 0.80})
                    if _extra_intents:
                        # Build merged slots — include original slots plus extracted args
                        _merged_slots = dict(_task_intent.slots)
                        # Extract git args if any sub-intent is git_action
                        if any(e["type"] == "git_action" for e in _extra_intents) or _task_intent.intent_type == "git_action":
                            _merged_slots["args"] = _extract_git_args(req.message)
                            _merged_slots["cwd"] = "D:/AI_round2"
                        # When upgrading from conversational, don't include "conversational" as a sub-intent
                        _base_intents = []
                        if _task_intent.intent_type != "conversational":
                            _base_intents.append({"type": _task_intent.intent_type, "confidence": _task_intent.confidence})
                        _all_intents = [*_base_intents, *_extra_intents]
                        _merged_slots["intents"] = _all_intents
                        logger.info(
                            "[STREAM] Compound upgrade: %s + %s → multi_intent",
                            _task_intent.intent_type,
                            ", ".join(e["type"] for e in _extra_intents),
                        )
                        _task_intent = TaskIntent(
                            route="task",
                            intent_type="multi_intent",
                            confidence=_task_intent.confidence,
                            slots=_merged_slots,
                            reason="compound_upgrade",
                            source="compound_upgrade",
                        )
                except Exception as _cue:
                    logger.debug("[STREAM] compound upgrade check failed: %s", _cue)

            # ── INTUITION CHECK: Clarify ambiguous input ─────────────────
            # If the classifier fell to conversational but confidence is low,
            # ask the intuition check if clarification is needed before proceeding.
            if (
                _task_intent is not None
                and _task_intent.route in ("conversational", "clarify")
                and _task_intent.confidence < 0.75
                and _is_cloud_governance_allowed(req, uid)
            ):
                try:
                    from personal_agent.intuition_check import get_intuition_check as _get_tap
                    from personal_agent.cloud_features import get_cloud_feature_service as _get_cfs
                    _tap = _get_tap(cloud_service=_get_cfs())
                    _open_tasks = []
                    try:
                        _open_tasks = [_active_task] if _active_task else []
                    except Exception:
                        pass
                    _tap_result = _tap.clarify(
                        message=req.message,
                        open_tasks=_open_tasks,
                        classifier_confidence=_task_intent.confidence,
                    )
                    if _tap_result is not None:
                        logger.info(
                            "[STREAM] Intuition check clarify: %s (confidence=%.2f, latency=%dms)",
                            _tap_result.message[:60], _tap_result.confidence, _tap_result.latency_ms,
                        )
                        yield _sse({
                            "type": "intuition_check",
                            "content": _tap_result.message,
                            "metadata": {
                                "tap_action": "clarify",
                                "confidence": _tap_result.confidence,
                                "latency_ms": _tap_result.latency_ms,
                                **_tap_result.metadata,
                            },
                        })
                except Exception as _tap_err:
                    logger.debug("[STREAM] Intuition check clarify failed: %s", _tap_err)
            elif (
                _task_intent is not None
                and _task_intent.route in ("conversational", "clarify")
                and _task_intent.confidence < 0.75
            ):
                logger.debug("[STREAM] Intuition check clarify skipped in strict local-only mode")

            # ── PLAN ENGINE CHECK (v2.9.3) ──────────────────────────────
            # If the message warrants a plan (multi-step work), generate one
            # and upgrade the intent to use the plan orchestrator.
            if _task_intent is not None and _task_intent.route == "task":
                try:
                    from personal_agent.plan_engine import PlanEngine as _PlanEngine
                    _get_llm_pe = request.app.state.get_llm_client
                    _pe = _PlanEngine(
                        llm_client=_get_llm_pe(),
                        session_db=_session_db,
                    )
                    _PLAN_SKIP_INTENTS = {"broad_recall", "user_reflection", "system_info", "inquiry_queue", "conversational"}
                    _plan_intent_type = getattr(_task_intent, "intent_type", None)
                    if _plan_intent_type in _PLAN_SKIP_INTENTS:
                        _safe_print(f"[PLAN] skipping planner for memory-only intent: {_plan_intent_type}")
                    elif _pe.should_create_plan(req.message, intent=_task_intent):
                        _safe_print(f"[PLAN] should_create_plan=True for: {req.message[:80]}")
                        _plan = _pe.generate_plan(
                            user_message=req.message,
                            conversation_history=recent_history if 'recent_history' in dir() else None,
                        )
                        if _plan:
                            _plan_steps = _plan.get("steps", [])
                            _safe_print(f"[PLAN] Generated plan '{_plan.get('title')}' with {len(_plan_steps)} steps")
                            # Link plan to thread so advance_step() can find it
                            try:
                                _session_db.link_plan_to_thread(req.thread_id, _plan["id"])
                            except Exception as _lpe:
                                _safe_print(f"[PLAN] link_plan_to_thread failed: {_lpe}")
                            yield _sse({
                                "type": "plan_created",
                                "content": f"Plan: {_plan.get('title', 'Untitled')}",
                                "metadata": {
                                    "plan_id": _plan.get("id"),
                                    "title": _plan.get("title"),
                                    "step_count": len(_plan_steps),
                                    "steps": [
                                        {"title": s.get("title", ""), "tool_name": s.get("tool_name")}
                                        for s in _plan_steps[:10]
                                    ],
                                },
                            })
                            # Upgrade intent to multi_step with plan context
                            _task_intent = TaskIntent(
                                route="task",
                                intent_type="multi_step",
                                confidence=0.90,
                                slots={
                                    "raw_message": req.message,
                                    "plan_id": _plan.get("id"),
                                    "plan_steps": _plan_steps,
                                },
                                reason="plan_engine_generated",
                                source="plan_engine",
                            )
                except Exception as _pe_err:
                    _safe_print(f"[PLAN] plan engine check failed: {_pe_err}")
                    logger.debug("[STREAM] Plan engine check failed: %s", _pe_err)

            # ── AGENT TOOL LOOP PATH (Sprint 14) ──────────────────────────
            # ── REMINDER FAST-PATH (deterministic, no LLM needed) ────────
            # If the message looks like a reminder request, handle it directly
            # without entering the agent loop (direct Claude can't use tools).
            _is_reminder_msg = any(kw in q_lower for kw in ("remind", "reminder", "alert me", "notify me"))
            _safe_print(f"[REMINDER_GATE] intent_type={getattr(_task_intent, 'intent_type', None)}, is_reminder={_is_reminder_msg}")
            if (
                _task_intent is not None
                and _task_intent.intent_type in ("create_commitment",)
                and _is_reminder_msg
            ):
                _safe_print("[REMINDER_GATE] >>> ENTERING reminder fast-path")
                try:
                    _reminder_result = extract_reminder_from_message(req.message)
                    _safe_print(f"[REMINDER_GATE] extract result: {_reminder_result}")
                    if _reminder_result:
                        _rem_text, _rem_dt = _reminder_result
                        _rem_ts = float(_rem_dt.timestamp())
                        if _rem_ts > time.time():
                            _session_db = get_thread_session_db()
                            _session_db.set_pending_reminder(
                                req.thread_id,
                                reminder_text=str(_rem_text),
                                scheduled_at=_rem_ts,
                                source_message=req.message,
                                expires_seconds=900,
                            )
                            _human_time = _format_reminder_time(_rem_ts)
                            _rem_answer = (
                                f"Set reminder: '{str(_rem_text).strip()}' at {_human_time}?"
                            )
                            # Emit as agent_checkpoint so the frontend shows the confirmation card
                            yield _sse({
                                "type": "agent_checkpoint",
                                "content": _rem_answer,
                                "metadata": {
                                    "checkpoint_tier": "reminder",
                                    "requires_confirmation": True,
                                    "intent": "create_reminder",
                                    "confidence": 0.97,
                                    "reminder_text": str(_rem_text),
                                    "reminder_time": _rem_ts,
                                },
                            })
                            # Must emit done so frontend exits streaming state and shows the action card
                            yield _sse({
                                "type": "done",
                                "content": _rem_answer,
                                "metadata": {"mode": "deterministic_reminder"},
                            })
                            return
                        else:
                            yield _sse({"type": "token", "content": "That time is in the past. Please provide a future time."})
                            yield _sse({"type": "done", "content": "That time is in the past."})
                            return
                except Exception as _rem_err:
                    logger.debug("[STREAM] Reminder fast-path failed: %s", _rem_err)
                    # Fall through to agent loop

            # ── CORRECTION FAST-PATH (deterministic, no LLM needed) ───────
            # If the user is correcting a prior fact ("that was a lie",
            # "I'm not allergic to X"), find matching memories and demote
            # their trust scores directly.
            if (
                _task_intent is not None
                and _task_intent.intent_type == "fact_correction"
            ):
                _safe_print("[CORRECTION_GATE] >>> ENTERING correction fast-path")
                try:
                    _corr_engine = request.app.state.get_engine(req.thread_id)
                    _corr_mem = _corr_engine.memory

                    # --- Extract what's being corrected ---
                    # Use the raw message as the search query.  Strip common
                    # correction prefixes so the semantic search focuses on
                    # the *subject* of the correction.
                    _corr_raw = req.message
                    _corr_query = re.sub(
                        r"(?i)^(that(?:'s|\s+is|\s+was)\s+(?:a\s+lie|wrong|not\s+true|false|incorrect|bs|bullshit)"
                        r"|those\s+were\s+lies"
                        r"|i\s+lied(?:\s+about)?"
                        r"|actually\s*,?\s*"
                        r"|forget\s+(?:that|what\s+i\s+said|what\s+i\s+told\s+you)\s*,?\s*"
                        r"|ignore\s+(?:that|what\s+i\s+said)\s*,?\s*"
                        r"|correction:\s*"
                        r"|correct:\s*)\s*",
                        "",
                        _corr_raw,
                    ).strip()
                    # If stripping left nothing, fall back to the full message
                    if not _corr_query or len(_corr_query) < 3:
                        _corr_query = _corr_raw

                    # Also pull recent conversation context to improve matching
                    _corr_context_msgs = []
                    try:
                        _corr_context_msgs = _load_recent_history_messages(
                            _session_db, req.thread_id, window=4,
                        )
                    except Exception:
                        pass

                    _safe_print(f"[CORRECTION] Search query: {_corr_query[:80]}")

                    # --- Search for matching memories ---
                    # Use the direct correction subject (not augmented with conversation)
                    # to avoid polluting the search with unrelated context.
                    # Do TWO searches: one for the stripped query, one for the raw message.
                    _corr_results = _corr_mem.retrieve_memories(
                        _corr_query,
                        k=10,
                        min_trust=0.05,
                        exclude_deprecated=True,
                        kinds={"user_fact", "user_belief", "preference", "observation"},
                        user_id=uid,
                    )
                    # Second search with raw message for broader matching
                    try:
                        _corr_results_raw = _corr_mem.retrieve_memories(
                            _corr_raw,
                            k=10,
                            min_trust=0.05,
                            exclude_deprecated=True,
                            kinds={"user_fact", "user_belief", "preference", "observation"},
                            user_id=uid,
                        )
                        # Merge, dedup by memory_id
                        _seen_ids = {getattr(m, 'memory_id', None) for m, _ in _corr_results}
                        for m, s in _corr_results_raw:
                            if getattr(m, 'memory_id', None) not in _seen_ids:
                                _corr_results.append((m, s))
                                _seen_ids.add(getattr(m, 'memory_id', None))
                    except Exception:
                        pass

                    # Filter to reasonably relevant matches
                    # Lower threshold (0.15) because short corrections like
                    # "that is incorrect" have weak semantic signal.
                    # Conversation context helps identify the target.
                    _corr_candidates = [
                        (mem, score) for mem, score in _corr_results
                        if score > 0.15 and mem.trust > 0.10
                    ]

                    _safe_print(f"[CORRECTION] Found {len(_corr_candidates)} candidate memories (from {len(_corr_results)} total)")

                    # --- Slot-scoped demotion (Bug #5 fix) ---
                    # Extract the fact slot from the correction to scope demotions.
                    # "I lied, coffee is my favorite drink" → slot = favorite_drink
                    # Only demote memories that share the same slot OR have high
                    # textual overlap with the correction subject.
                    _corr_slot = None
                    _corr_subject_words = set()
                    try:
                        _corr_lower = _corr_query.lower()
                        # Extract slot-like patterns
                        _SLOT_PATTERNS = {
                            "favorite_color": r"fav(?:ou?rite)?\s+color",
                            "favorite_drink": r"fav(?:ou?rite)?\s+drink|coffee|tea|juice",
                            "favorite_food": r"fav(?:ou?rite)?\s+food",
                            "employer": r"work(?:s?|ed|ing)?\s+(?:at|for)|employer|job|walmart|freelanc",
                            "location": r"live[sd]?\s+in|location|address|from\s+",
                            "name": r"(?:my\s+)?name\s+is|call\s+me",
                            "pet": r"(?:my\s+)?(?:dog|cat|pet|fish)\s+",
                        }
                        for slot_name, pattern in _SLOT_PATTERNS.items():
                            if re.search(pattern, _corr_lower):
                                _corr_slot = slot_name
                                break

                        # Extract content words for subject matching
                        _stopwords = {"i", "my", "is", "a", "the", "its", "favorite", "favourite",
                                      "lied", "actually", "really", "not", "never", "liked",
                                      "drink", "color", "food", "am", "was", "dont", "don't"}
                        _corr_subject_words = {
                            w for w in re.findall(r'\b\w+\b', _corr_lower)
                            if w not in _stopwords and len(w) > 2
                        }

                        _safe_print(f"[CORRECTION] Detected slot: {_corr_slot}, subject words: {_corr_subject_words}")
                    except Exception:
                        pass

                    _demoted_count = 0
                    _demoted_texts = []
                    _skipped_texts = []
                    _CORRECTION_TRUST = 0.15  # Target trust for corrected memories

                    for _c_mem, _c_score in _corr_candidates[:10]:  # Check more, demote fewer
                        _old_trust = float(_c_mem.trust)
                        if _old_trust <= _CORRECTION_TRUST:
                            continue  # Already low, skip

                        # Slot-scope check: only demote if memory is about the same slot
                        _mem_lower = (_c_mem.text or "").lower()
                        _should_demote = False

                        if _corr_slot:
                            # Check if memory matches the correction slot
                            _slot_pattern = _SLOT_PATTERNS.get(_corr_slot, "")
                            if _slot_pattern and re.search(_slot_pattern, _mem_lower):
                                _should_demote = True
                                _safe_print(f"[CORRECTION] Slot match ({_corr_slot}): {_c_mem.text[:50]}")
                            else:
                                # Check for subject word overlap (e.g., "coffee" in both)
                                _mem_words = set(re.findall(r'\b\w+\b', _mem_lower))
                                _overlap = _corr_subject_words & _mem_words
                                if len(_overlap) >= 1 and any(len(w) > 3 for w in _overlap):
                                    _should_demote = True
                                    _safe_print(f"[CORRECTION] Subject overlap ({_overlap}): {_c_mem.text[:50]}")
                        else:
                            # No slot detected — fall back to high similarity threshold
                            if _c_score > 0.5:
                                _should_demote = True

                        if not _should_demote:
                            _skipped_texts.append(f"  SKIPPED (no slot match): {_c_mem.text[:60]}")
                            _safe_print(f"[CORRECTION] SKIPPED (no slot match, sim={_c_score:.3f}): {_c_mem.text[:60]}")
                            continue

                        if _demoted_count >= 5:
                            break  # Cap at 5 demotions

                        _corr_mem._update_memory_trust(_c_mem.memory_id, _CORRECTION_TRUST)
                        _corr_mem.record_memory_event(
                            memory_id=_c_mem.memory_id,
                            event_type="user_correction_demoted",
                            actor="user",
                            reason=f"User correction: {_corr_raw[:120]}",
                            metadata={
                                "correction_message": _corr_raw[:200],
                                "old_trust": _old_trust,
                                "new_trust": _CORRECTION_TRUST,
                                "similarity_score": round(_c_score, 3),
                                "search_query": _corr_query[:200],
                            },
                        )
                        _demoted_count += 1
                        _short_text = _c_mem.text[:80].replace("\n", " ")
                        _demoted_texts.append(f"  - \"{_short_text}\" (trust {_old_trust:.2f} -> {_CORRECTION_TRUST:.2f})")
                        _safe_print(
                            f"[CORRECTION] Demoted memory {_c_mem.memory_id}: "
                            f"trust {_old_trust:.3f} -> {_CORRECTION_TRUST} "
                            f"(sim={_c_score:.3f}): {_short_text}"
                        )

                    # --- Record in active learning DB ---
                    try:
                        _al_coord = get_active_learning_coordinator()
                        if _al_coord is not None:
                            _al_coord.record_feedback_correction(
                                interaction_id=str(uuid.uuid4()),
                                correction_type="fact_retraction",
                                field_name=None,
                                incorrect_value=_corr_query[:200],
                                correct_value=None,
                                user_comment=_corr_raw[:200],
                            )
                    except Exception as _al_err:
                        logger.debug("[CORRECTION] Active learning record failed: %s", _al_err)

                    # --- Emit response ---
                    if _demoted_count > 0:
                        _corr_response = (
                            f"Got it -- I've lowered the trust on {_demoted_count} "
                            f"memor{'y' if _demoted_count == 1 else 'ies'} "
                            f"that {'was' if _demoted_count == 1 else 'were'} incorrect:\n"
                            + "\n".join(_demoted_texts)
                            + "\n\nThese memories will still exist but carry very low weight."
                        )
                    else:
                        _corr_response = (
                            "I hear you, but I couldn't find matching memories to correct. "
                            "Could you be more specific about what was wrong? "
                            "For example: \"I'm not actually allergic to peanuts\" or "
                            "\"I don't live in Portland\"."
                        )

                    yield _sse({"type": "token", "content": _corr_response})
                    yield _sse({
                        "type": "done",
                        "content": _corr_response,
                        "metadata": {
                            "mode": "correction_fast_path",
                            "demoted_count": _demoted_count,
                        },
                    })
                    return
                except Exception as _corr_err:
                    _safe_print(f"[CORRECTION] Fast-path failed: {_corr_err}")
                    logger.warning("[STREAM] Correction fast-path failed: %s", _corr_err, exc_info=True)
                    # Fall through to normal generation

            # ── LAYER 4: EPISTEMIC ROUTING (runs FIRST, before agent loop) ──
            # Decides: orchestrator (agent loop) vs conversational vs agent tool loop.
            # If Layer 4 says orchestrator, skip the agent loop entirely.
            _orch_msg = str(req.message or "")
            _layer4_orchestrator = False
            try:
                from personal_agent.routing_beliefs import should_orchestrate as _route_check
                _routing = _route_check(_orch_msg, _task_intent)
                _layer4_orchestrator = not _user_confirmed and _routing.route == "orchestrator"
                _safe_print(f"[ROUTING] {_routing.route} (conf={_routing.confidence:.2f}, reasons={_routing.reasons})")

                # ── Pure transformation guard ──────────────────────────
                # Tasks like "rewrite as table", "convert to list", "format as markdown"
                # need zero tools — sending them through the orchestrator wastes iterations
                # on tool calls that can't help. Route to direct generation instead.
                if _layer4_orchestrator and _task_intent and _task_intent.intent_type == "conversational":
                    import re as _re_transform
                    _is_pure_transform = bool(_re_transform.search(
                        r"\b(?:rewrite|convert|format|transform|rephrase|restructure|reorganize)\b.*\b(?:as|into|to)\b.*\b(?:table|list|json|csv|markdown|bullet|summary|paragraph)\b",
                        _orch_msg, _re_transform.IGNORECASE,
                    ))
                    if _is_pure_transform:
                        _layer4_orchestrator = False
                        _safe_print("[ROUTING] Pure transformation detected — skipping orchestrator, direct generation")
            except Exception as _route_err:
                _safe_print(f"[ROUTING] Belief routing failed, falling back: {_route_err}")

            # If agent_loop is enabled, use the LLM-driven agentic tool loop
            # instead of the classify-once-execute-blind pattern. The LLM sees
            # tool results and decides what to do next autonomously.
            _agent_loop_enabled = False
            try:
                _rt_cfg = get_runtime_config()
                _al_cfg = _rt_cfg.get("agent_loop", {})
                _agent_loop_enabled = _al_cfg.get("enabled", False)
            except Exception:
                pass

            # ── Check if agent loop can actually use the user's preferred model ──
            # The agent loop needs a working LLM. Check if at least one provider
            # is reachable. Previously this blocked on cloud_claude and llm_local
            # modes, which caused total system failure when Ollama was unreachable.
            # Now: only block if no provider is available at all.
            _agent_loop_model_ok = True
            try:
                import auth as _auth_al_check
                _uid_al_check = int(uid) if uid else 1
                _al_gen_mode = str(_auth_al_check.get_user_setting(_uid_al_check, "generation_mode", "cloud_claude") or "cloud_claude").strip()
                if _al_gen_mode == "cloud_claude":
                    # cloud_claude mode: agent loop can use the LiteLLM fallback chain
                    # (Anthropic API → OpenAI API → local). Only block if we have
                    # no cloud keys at all.
                    _has_cloud = bool(os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("OPENAI_API_KEY"))
                    if not _has_cloud:
                        _agent_loop_model_ok = False
                # llm_local: let it through — intent classification now has cloud
                # fallback, so even if Ollama is down the system degrades gracefully
            except Exception:
                pass

            _safe_print(f"[AGENT_LOOP_GATE] enabled={_agent_loop_enabled}, intent={_task_intent is not None}, route={getattr(_task_intent, 'route', None)}, confirmed={_user_confirmed}, layer4_orchestrator={_layer4_orchestrator}, model_ok={_agent_loop_model_ok}")
            # Memory-only intents must bypass the agent loop — they need direct retrieval,
            # not an LLM tool loop that will spin up web_search / shell_exec.
            _MEMORY_ONLY_INTENTS = {"user_reflection", "system_info", "inquiry_queue"}
            _agent_loop_gate_hit = (
                _agent_loop_enabled
                and _agent_loop_model_ok
                and _task_intent is not None
                and _task_intent.route == "task"
                and _task_intent.intent_type not in _MEMORY_ONLY_INTENTS
                and not _user_confirmed
                and not _layer4_orchestrator
            )
            if _agent_loop_gate_hit:
                _runner_result = yield from run_agent_tool_loop(
                    runtime,
                    _task_intent,
                    _active_task,
                    _user_confirmed,
                    recent_history if 'recent_history' in dir() else None,
                )
                if _runner_result and _runner_result.handled:
                    _agent_loop_enabled = False
                    if _runner_result.terminal:
                        return
            if (
                _agent_loop_enabled
                and _agent_loop_model_ok  # Agent loop must be able to use the user's preferred model
                and _task_intent is not None
                and _task_intent.route == "task"
                and _task_intent.intent_type not in _MEMORY_ONLY_INTENTS
                and not _user_confirmed  # Agent loop handles its own checkpoints
                and not _layer4_orchestrator  # Layer 4 overrides — route to agent loop instead
            ):
                _safe_print("[AGENT_LOOP_GATE] >>> ENTERING agent tool loop path")
                try:
                    from personal_agent.agent_tool_loop import AgentToolLoop
                    _ensure_governed_task(objective=req.message, max_iterations=int(_al_cfg.get("max_iterations", 10) or 10))
                    _update_governed_task(status=GovernedTaskStatus.RUNNING.value, wait_kind=None, question=None)
                    _append_governed_event("agent_loop_start", req.message, {"mode": "agent_tool_loop"})
                    yield _sse({"type": "agent_loop_start", "content": "Agent loop started", "metadata": {"mode": "agent_tool_loop"}})

                    _get_llm_al = request.app.state.get_llm_client
                    _llm_client_al = _get_llm_al()
                    _al_max_iter = _al_cfg.get("max_iterations", 10)
                    _al_show_thinking = _al_cfg.get("show_thinking", True)

                    # ── Wire user tooling settings into runtime ──
                    try:
                        import auth as _auth_tooling
                        _uid_tooling = int(uid) if uid else 1

                        # Override agent loop config from user settings
                        _user_al_enabled = _auth_tooling.get_user_setting(_uid_tooling, "tooling_agent_loop_enabled", "true")
                        if _user_al_enabled == "false":
                            _safe_print("[AGENT_LOOP_GATE] Agent loop disabled by user tooling settings")
                            # Skip agent loop, fall through to normal generation
                            raise StopIteration("agent_loop_disabled_by_user")
                        _user_max_iter = _auth_tooling.get_user_setting(_uid_tooling, "tooling_agent_loop_max_iterations", "")
                        if _user_max_iter and _user_max_iter.isdigit():
                            _al_max_iter = max(1, min(50, int(_user_max_iter)))
                        _user_show_thinking = _auth_tooling.get_user_setting(_uid_tooling, "tooling_agent_loop_show_thinking", "true")
                        _al_show_thinking = _user_show_thinking != "false"

                        # Override fallback policy on the LLM client
                        _user_fallback = _auth_tooling.get_user_setting(_uid_tooling, "tooling_fallback_policy", "")
                        if _user_fallback and _llm_client_al is not None:
                            _llm_client_al.fallback_policy = _user_fallback
                            _safe_print(f"[AGENT_LOOP] Fallback policy set to: {_user_fallback}")

                        # Override model roles on the LLM client
                        if _llm_client_al is not None:
                            for _role in ("fast", "reasoning", "tool_loop", "answer"):
                                _user_role_model = _auth_tooling.get_user_setting(
                                    _uid_tooling, f"tooling_model_role_{_role}", ""
                                )
                                if _user_role_model:
                                    if not hasattr(_llm_client_al, "model_roles") or _llm_client_al.model_roles is None:
                                        _llm_client_al.model_roles = {}
                                    _llm_client_al.model_roles[_role] = _user_role_model
                                    _safe_print(f"[AGENT_LOOP] Model role '{_role}' overridden to: {_user_role_model}")
                    except StopIteration:
                        raise
                    except Exception as _tooling_err:
                        _safe_print(f"[AGENT_LOOP] Warning: failed to read tooling settings: {_tooling_err}")

                    # Get engine for memory access in tool loop
                    _al_engine = None
                    try:
                        _al_engine = request.app.state.get_engine(req.thread_id)
                    except Exception:
                        pass

                    # ── Triage: assess intent and tell the user what we're about to do ──
                    _al_intent_hint = None
                    try:
                        from personal_agent.task_agent import triage_message, _INTENT_TOOL_MAP
                        _triage = triage_message(req.message, _task_intent)
                        _ack_text = _build_loop_acknowledgment(
                            req.message,
                            _task_intent,
                            history_messages=recent_history,
                        )
                        _tools_planned = _triage.tools_needed or _INTENT_TOOL_MAP.get(_task_intent.intent_type, [])
                        if _ack_text:
                            yield _sse({
                                "type": "intent_preview",
                                "content": _ack_text,
                                "metadata": {
                                    "intent": _task_intent.intent_type,
                                    "route": _task_intent.route,
                                    "confidence": _task_intent.confidence,
                                    "tools_planned": _tools_planned,
                                    "source": getattr(_task_intent, "source", ""),
                                },
                            })
                            _safe_print(f"[AGENT_LOOP] Intent preview: {_ack_text} (tools={_tools_planned})")
                        # Build intent hint for the LLM
                        _al_intent_hint = (
                            f"User intent: {_task_intent.intent_type}. "
                            f"Suggested tools: {', '.join(_tools_planned) if _tools_planned else 'none'}."
                        )
                    except Exception as _triage_err:
                        _safe_print(f"[AGENT_LOOP] Triage failed (non-fatal): {_triage_err}")

                    _loop = AgentToolLoop(
                        _llm_client_al,
                        session_db=_session_db,
                        max_iterations=_al_max_iter,
                        show_thinking=_al_show_thinking,
                        engine=_al_engine,
                        intent_hint=_al_intent_hint,
                    )

                    # Intent-gated tool access (Layer 10)
                    _al_tool_filter = None
                    try:
                        from personal_agent.tool_gate import get_agent_loop_filter
                        _al_tool_filter = get_agent_loop_filter(
                            intent_type=getattr(_task_intent, 'intent_type', 'task'),
                            route=getattr(_task_intent, 'route', None),
                        )
                        if _al_tool_filter:
                            _safe_print(f"[TOOL_GATE] Agent loop: {len(_al_tool_filter)} tools for intent={getattr(_task_intent, 'intent_type', '?')}")
                    except Exception:
                        pass

                    _loop_gen = _loop.run(
                        req.message,
                        req.thread_id,
                        conversation_history=recent_history if 'recent_history' in dir() else None,
                        tool_filter=_al_tool_filter,
                    )

                    _al_checkpoint_hit = False
                    _al_answer = ""
                    _al_steps: list = []
                    _al_done = False
                    _al_generation_source = ""

                    try:
                        _event = next(_loop_gen)
                        while True:
                            # Emit the event to SSE
                            logger.info("[SSE_DEBUG] Emitting event type=%s content_len=%d", _event.get("type"), len(str(_event.get("content", ""))))
                            yield _sse(_event)

                            if _event["type"] == "agent_checkpoint":
                                # Store checkpoint for user confirmation on next message
                                _al_checkpoint_hit = True
                                _cp_tier = _event.get("metadata", {}).get("checkpoint_tier", "medium")
                                _session_db.store_pending_checkpoint(
                                    thread_id=req.thread_id,
                                    intent_data={
                                        "route": _task_intent.route,
                                        "intent_type": _task_intent.intent_type,
                                        "slots": _task_intent.slots,
                                        "confidence": _task_intent.confidence,
                                        "reason": _task_intent.reason,
                                        "source": getattr(_task_intent, "source", "agent_loop"),
                                        "_agent_loop": True,
                                        "_loop_state": {
                                            "message": req.message,
                                            "tool_name": _event.get("metadata", {}).get("tool_name"),
                                            "tool_args": _event.get("metadata", {}).get("tool_args"),
                                        },
                                    },
                                    checkpoint_tier=_cp_tier,
                                    metadata=_event.get("metadata"),
                                )
                                _update_governed_task(
                                    status=GovernedTaskStatus.AWAITING_CHECKPOINT.value,
                                    wait_kind=GovernedTaskWaitKind.CHECKPOINT.value,
                                    checkpoint_tier=_cp_tier,
                                    question=_event.get("content", ""),
                                    steps_done=list(_al_steps),
                                    orch_answer_so_far=_al_answer,
                                )
                                _append_governed_event("agent_checkpoint", _event.get("content", ""), _event.get("metadata", {}))
                                break  # Pause — user must confirm on next message

                            elif _event["type"] == "token":
                                _al_answer += _event.get("content", "")
                            elif _event["type"] == "tool_result":
                                _al_steps.append(_event.get("metadata", {}))
                                _update_governed_task(steps_done=list(_al_steps), orch_answer_so_far=_al_answer)
                                _append_governed_event("tool_result", _event.get("content", ""), _event.get("metadata", {}))
                            elif _event["type"] == "agent_loop_complete":
                                _al_done = True
                                _al_generation_source = _event.get("metadata", {}).get("generation_source", "")
                                _append_governed_event("agent_loop_complete", _event.get("content", ""), _event.get("metadata", {}))

                            # Get next event (no checkpoint confirmation in SSE mode)
                            _event = _loop_gen.send(None)

                    except StopIteration:
                        _al_done = True

                    logger.info("[SSE_DEBUG] Loop exited: checkpoint_hit=%s, al_done=%s, al_answer_len=%d, steps=%d",
                               _al_checkpoint_hit, _al_done, len(_al_answer), len(_al_steps))

                    if _al_checkpoint_hit:
                        logger.info("[SSE_DEBUG] Emitting checkpoint-done, content=%.200s", _event.get("content", "")[:200])
                        yield _sse({
                            "type": "done",
                            "content": _event.get("content", ""),
                            "metadata": {"checkpoint_pending": True, "agent_loop": True},
                        })
                        return

                    # Agent loop completed — emit done
                    logger.info("[SSE_DEBUG] Emitting final done, al_answer_len=%d, preview=%.200s", len(_al_answer), _al_answer[:200])
                    _tools_executed = len(_al_steps) > 0
                    # Infer generation source if agent loop didn't report one
                    if not _al_generation_source:
                        _al_generation_source = "local" if _tools_executed else "agent_loop"
                    _safe_print(f"[GEN_SOURCE] SSE final: generation_source={_al_generation_source}, tools_executed={_tools_executed}")
                    # Extract belief confidence from the last governance check
                    _al_belief = 0.5
                    try:
                        # Agent loop governance runs inside the loop — get the last belief
                        for _ev in reversed(_al_events):
                            if isinstance(_ev, dict) and _ev.get("type") == "governance":
                                _al_belief = float(_ev.get("metadata", {}).get("belief_confidence", 0.5))
                                break
                    except Exception:
                        pass
                    # ── Fidelity mirror on agent loop response (Bug #9) ──
                    _al_gates_passed = True
                    _al_fidelity_meta = {}
                    try:
                        from personal_agent.fidelity_mirror import check_fidelity as _al_check_fidelity
                        _al_fm_mems = []
                        if _al_engine:
                            try:
                                _al_fm_results = _al_engine.memory.retrieve_memories(req.message[:500], k=8)
                                _al_fm_mems = [
                                    {"text": m.text[:300], "trust": m.trust, "memory_id": m.memory_id}
                                    for m, _ in _al_fm_results
                                ]
                            except Exception:
                                pass
                        _al_fidelity = _al_check_fidelity(
                            response=_al_answer,
                            query=req.message,
                            memories=_al_fm_mems,
                        )
                        _al_fidelity_meta = {
                            "belief_fidelity": _al_fidelity.belief_fidelity,
                            "request_alignment": _al_fidelity.request_alignment,
                            "factual_grounding": _al_fidelity.factual_grounding,
                            "composite": _al_fidelity.composite,
                            "passed": _al_fidelity.passed,
                        }
                        if not _al_fidelity.passed:
                            _al_gates_passed = False
                            _fm_findings = []
                            if _al_fidelity.belief_fidelity < 0.2:
                                _fm_findings.append("I may not be drawing on what I know about you")
                            if _al_fidelity.request_alignment < 0.2:
                                _fm_findings.append("I may not be directly answering your question")
                            if _al_fidelity.factual_grounding < 0.1:
                                _fm_findings.append("my claims aren't well-grounded in stored facts")
                            if _fm_findings:
                                _hedge = (
                                    "**Heads up:** " + ", and ".join(_fm_findings) + ". "
                                    "Take this with lower confidence.\n\n---\n\n"
                                )
                                _al_answer = _hedge + _al_answer
                                _safe_print(f"[FIDELITY_ENFORCEMENT] Agent loop hedged ({len(_fm_findings)} findings)")
                            yield _sse({"type": "epistemic_event", "content": f"Fidelity check failed", "metadata": {"event": "fidelity_fail", **_al_fidelity_meta}})
                    except Exception as _al_fm_err:
                        _safe_print(f"[FIDELITY_MIRROR] Agent loop skipped: {_al_fm_err}")

                    # Expose retrieved memories for UI (matches legacy path's retrieved_memories key)
                    _al_retrieved_mems = getattr(_loop, "retrieved_memories", [])

                    _done_meta_al = {
                        "tool_calls": _al_steps,
                        "agent_loop": True,
                        "tools_executed": _tools_executed,
                        "response_type": "task",
                        "gates_passed": _al_gates_passed,
                        "generation_source": _al_generation_source,
                        "belief_confidence": round(_al_belief, 3),
                        "fidelity_mirror": _al_fidelity_meta,
                        "retrieved_memories": _al_retrieved_mems,
                    }
                    if _governed_task:
                        _governed_task = _session_db.complete_governed_task(str(_governed_task["task_id"]), _al_answer) or _governed_task
                        _append_governed_event("done", _al_answer, {"task_status": GovernedTaskStatus.COMPLETED.value, **_done_meta_al})
                    yield _sse({"type": "agent_loop_complete", "content": _al_answer, "metadata": {"generation_source": _al_generation_source}})
                    # Inject request cost
                    try:
                        from personal_agent.litellm_client import get_default_llm_client
                        _done_meta_al["cost_usd"] = round(get_default_llm_client().get_request_cost(), 6)
                    except Exception:
                        _done_meta_al["cost_usd"] = 0.0
                    yield _sse({"type": "done", "content": _al_answer, "metadata": _done_meta_al})
                    return

                except Exception as _al_err:
                    if _governed_task:
                        _governed_task = _session_db.fail_governed_task(str(_governed_task["task_id"]), str(_al_err)) or _governed_task
                        _append_governed_event("error", str(_al_err), {"task_status": GovernedTaskStatus.FAILED.value})
                    _safe_print(f"[AGENT_LOOP_GATE] >>> EXCEPTION in agent loop: {_al_err}")
                    logger.warning("[STREAM] Agent tool loop failed, falling back to legacy path: %s", _al_err, exc_info=True)
                    # Fall through to legacy path

            # ── AGENT LOOP ORCHESTRATOR PATH: Complex multi-step tasks ─────────
            # Uses the brain (Claude/GPT/Ollama) for planning/reasoning,
            # local tools for execution. Sandboxed file writes.
            # Layer 4 routing decision was made above (before agent loop gate).
            # Also enters orchestrator when agent loop was skipped due to model
            # mismatch (user wants Claude CLI but agent loop can only do API).
            _agent_loop_skipped_for_model = (
                _agent_loop_enabled
                and not _agent_loop_model_ok
                and _task_intent is not None
                and _task_intent.route == "task"
                and _task_intent.intent_type not in _MEMORY_ONLY_INTENTS
            )
            # ── Routing gate: only enter agent loop for genuine tool-requiring tasks ──
            # Replaces the `and False` kill-switch with a real signal:
            #   1. intent_type must be in the tool-requiring whitelist
            #   2. routing confidence must be ≥ 0.75 (prevents borderline misfires)
            #   3. message must be at least 4 words (not a one-liner like "hello")
            # Generic convos, memory queries, and greetings fall through to legacy.
            _TOOL_REQUIRING_INTENTS = {
                "file_op", "code_task", "code_read", "code_write",
                "file_read", "file_write",  # explicit file intents always need tools
                "project_scan", "search_code",  # needs tool access
                "web_search", "web_fetch", "research",
                "shell_exec", "run_python",
                "memory_write",
                "multi_step", "multi_intent", "plan_create",
                # Hard-forced intents (from routing_beliefs) always pass
                "gpt_log_search", "gpt_log_context", "gpt_log_promote",
            }
            _SKIP_ORCHESTRATOR_INTENTS = {
                "broad_recall", "user_reflection", "inquiry", "question", "conversational",
                "memory_query", "memory_search",
                "self_reflection", "greeting", "system_info", "inquiry_queue",
            }
            try:
                _routing_conf = _routing.confidence  # type: ignore[name-defined]
            except Exception:
                _routing_conf = 0.0
            _intent_type_str = getattr(_task_intent, "intent_type", "") if _task_intent else ""
            # Followup chips from agent loop responses should always route back to agent loop
            _is_followup = str(req.message or "").startswith("[followup]")
            if _is_followup:
                req.message = req.message[len("[followup]"):].strip()
            _needs_agent_loop = (
                _is_followup  # followup clicks always go to agent loop
                or (
                    _intent_type_str not in _SKIP_ORCHESTRATOR_INTENTS
                    and (
                        _intent_type_str in _TOOL_REQUIRING_INTENTS
                        or (_routing_conf >= 0.75 and _task_intent is not None and _task_intent.route == "task")
                    )
                    and len(str(req.message or "").split()) >= 4
                )
            )
            # When Layer 4 explicitly routed to orchestrator, trust it — don't let the
            # intent-based gate override an explicit orchestrator decision.
            # _needs_agent_loop only gates the agent_loop_skipped redirect path.
            _orch_entry = _layer4_orchestrator or (_agent_loop_skipped_for_model and _needs_agent_loop)
            if not _orch_entry and (_layer4_orchestrator or _agent_loop_skipped_for_model):
                _safe_print(f"[ROUTING_GATE] Blocked agent loop entry: intent={_intent_type_str!r}, conf={_routing_conf:.2f}, words={len(str(req.message or '').split())} — falling through to legacy")
            _orch_preview_emitted = False
            if _orch_entry:
                _orch_reason = "layer4" if _layer4_orchestrator else "model_redirect"
                _ack_text = _build_loop_acknowledgment(
                    req.message,
                    _task_intent,
                    history_messages=(recent_history if 'recent_history' in dir() else None),
                )
                yield _sse({
                    "type": "intent_preview",
                    "content": _ack_text,
                    "metadata": {
                        "intent": _intent_type_str,
                        "route": getattr(_task_intent, "route", ""),
                        "reason": _orch_reason,
                    },
                })
                yield _sse({"type": "token", "content": _ack_text + "\n\n"})
                _orch_preview_emitted = True
                _orch_runner_result = yield from run_orchestrator(
                    runtime,
                    _task_intent,
                    _orch_reason,
                    recent_history if 'recent_history' in dir() else None,
                )
                if _orch_runner_result and _orch_runner_result.handled:
                    _orch_entry = False
                    if _orch_runner_result.terminal:
                        return
            if _orch_entry:
                _orch_reason = "layer4" if _layer4_orchestrator else "model_redirect"
                _safe_print(f"[ORCHESTRATOR] >>> ENTERING agent loop path (intent={_intent_type_str!r}, reason={_orch_reason})")
                _ensure_governed_task(objective=_orch_msg, max_iterations=10)
                _update_governed_task(status=GovernedTaskStatus.RUNNING.value, wait_kind=None, question=None)
                _append_governed_event("agent_loop_start", _orch_msg, {"mode": "orchestrator", "reason": _orch_reason})
                yield _sse({"type": "agent_loop_start", "content": "Agent loop started", "metadata": {"mode": "orchestrator", "reason": _orch_reason}})

                # ── Immediate acknowledgment before agent loop initializes ──────
                # Without this, the user sees silence for several seconds.
                # The ack is the first token of the response; the orchestrator
                # answer is appended after. Keep it short and contextual.
                _ack_text = _build_loop_acknowledgment(
                    req.message,
                    _task_intent,
                    history_messages=(
                        _orch_recent
                        if "_orch_recent" in locals()
                        else (recent_history if "recent_history" in locals() else None)
                    ),
                )
                if not _orch_preview_emitted:
                    yield _sse({
                        "type": "intent_preview",
                        "content": _ack_text,
                        "metadata": {
                            "intent": _intent_type_str,
                            "route": getattr(_task_intent, "route", ""),
                            "reason": _orch_reason,
                        },
                    })
                    yield _sse({"type": "token", "content": _ack_text + "\n\n"})

                try:
                    from personal_agent.cookie_orchestrator import Orchestrator

                    _orch_engine = request.app.state.get_engine(req.thread_id)

                    _orch_gen_mode, _orch_brain = build_orchestrator_brain(req, uid)
                    _safe_print(f"[ORCHESTRATOR] Brain selected: {_orch_gen_mode} -> {getattr(_orch_brain, '_model', 'unknown')}")

                    _orch = Orchestrator(
                        brain=_orch_brain,
                        memory_system=_orch_engine.memory,
                        max_iterations=10,
                    )

                    # Load conversation history for multi-turn context.
                    # window=2: only the immediately prior exchange — larger windows
                    # cause the brain to conflate previous tasks with the current one.
                    _orch_history = []
                    try:
                        _orch_recent = _load_recent_history_messages(
                            _session_db, req.thread_id, window=2)
                        _orch_history = [
                            f"{'User' if m['role'] == 'user' else 'Aether'}: {m['content'][:150]}"
                            for m in _orch_recent
                        ]
                        if _orch_history:
                            _safe_print(f"[ORCHESTRATOR] Loaded {len(_orch_history)} history messages")
                    except Exception as _hist_err:
                        _safe_print(f"[ORCHESTRATOR] History load failed (non-fatal): {_hist_err}")

                    _orch_answer = _ack_text + "\n\n"
                    _orch_steps = []

                    _orch_gen = _orch.run(
                        _orch_msg,
                        conversation_history=_orch_history or None,
                        intent_type=getattr(_task_intent, 'intent_type', None),
                        route=getattr(_task_intent, 'route', None),
                    )
                    _orch_send_val = None
                    while True:
                        try:
                            if _orch_send_val is not None:
                                _orch_event = _orch_gen.send(_orch_send_val)
                                _orch_send_val = None
                            else:
                                _orch_event = next(_orch_gen)
                        except StopIteration:
                            break

                        _etype = _orch_event.get("type", "")

                        if _etype == "plan":
                            # Agent loop's first-move declaration — stream it as visible
                            # response tokens so the user sees what's about to happen
                            # before any tools fire.
                            _plan_content = _orch_event.get("content", "")
                            _plan_steps = _orch_event.get("steps", [])
                            # Phase 4: adaptive depth — brain declares estimated_depth
                            # in its plan. If provided, clamp max_iterations to that
                            # value (floor 3, ceiling 10) so simple tasks don't burn
                            # unnecessary iterations.
                            _est_depth = _orch_event.get("estimated_depth")
                            if _est_depth is not None:
                                try:
                                    # Floor is 5: plan burns slot 0, so need at least 4 working slots
                                    _clamped = max(5, min(10, int(_est_depth) + 1))
                                    _orch.max_iterations = _clamped
                                    _safe_print(f"[ORCHESTRATOR] Adaptive depth: plan declared estimated_depth={_est_depth} → max_iterations={_clamped}")
                                except (TypeError, ValueError):
                                    pass
                            if _plan_content:
                                # Route plan to pipeline panel as a thinking step,
                                # NOT as a visible response token (avoids scripted preamble).
                                _plan_display = _plan_content
                                if _plan_steps:
                                    _plan_display += " → " + " · ".join(_plan_steps)
                                yield _sse({
                                    "type": "thinking",
                                    "content": _plan_display,
                                })

                        elif _etype == "thinking":
                            yield _sse({
                                "type": "agent_thinking_token",
                                "content": _orch_event.get("content", ""),
                                "metadata": {
                                    "step": "orchestrator_thinking",
                                    "alignment": _orch_event.get("alignment"),
                                },
                            })

                        elif _etype == "drift_warning":
                            yield _sse({
                                "type": "epistemic_event",
                                "content": _orch_event.get("content", ""),
                                "metadata": {
                                    "event": "drift",
                                    "alignment": _orch_event.get("alignment"),
                                    "avg_alignment": _orch_event.get("avg_alignment"),
                                    "proposed_action": _orch_event.get("proposed_action", ""),
                                    "proposed_tool": _orch_event.get("proposed_tool", ""),
                                },
                            })

                        elif _etype == "execution_drift":
                            yield _sse({
                                "type": "epistemic_event",
                                "content": _orch_event.get("content", ""),
                                "metadata": {
                                    "event": "execution_drift",
                                    "from_category": _orch_event.get("from_category", ""),
                                    "to_category": _orch_event.get("to_category", ""),
                                    "alignment": _orch_event.get("alignment"),
                                },
                            })

                        elif _etype == "contradiction_warning":
                            yield _sse({
                                "type": "epistemic_event",
                                "content": _orch_event.get("content", ""),
                                "metadata": {
                                    "event": "contradiction",
                                    "step_a": _orch_event.get("step_a"),
                                    "step_b": _orch_event.get("step_b"),
                                },
                            })

                        elif _etype == "tool_call":
                            _tool_name = _orch_event.get("tool", "")
                            _tool_args = _orch_event.get("args", {})
                            _tool_result = _orch_event.get("result", "")
                            _tool_status = _orch_event.get("status", "ok")
                            _tool_align = _orch_event.get("alignment")
                            _tool_ms = _orch_event.get("latency_ms")
                            _tool_reasoning = _orch_event.get("reasoning", "")
                            if _tool_reasoning:
                                # Phase 3: mid-update — surface the brain's reasoning
                                # as a thinking stub before the tool row fires.
                                yield _sse({
                                    "type": "agent_thinking_token",
                                    "content": _tool_reasoning[:200],
                                    "metadata": {
                                        "step": "tool_loop",
                                        "alignment": _tool_align,
                                    },
                                })
                            yield _sse({
                                "type": "tool_start",
                                "content": f"Running {_tool_name}...",
                                "metadata": {
                                    "tool_name": _tool_name,
                                    "input": _tool_args,
                                    "alignment": _tool_align,
                                    "reasoning": _tool_reasoning,
                                },
                            })
                            yield _sse({
                                "type": "tool_result",
                                "content": _tool_result[:500],
                                "metadata": {
                                    "tool_name": _tool_name,
                                    "status": _tool_status,
                                    "step_index": len(_orch_steps),
                                    "duration_ms": _tool_ms,
                                    "alignment": _tool_align,
                                },
                            })
                            _orch_steps.append({
                                "tool": _tool_name,
                                "args": _tool_args,
                                "status": _tool_status,
                            })
                            _update_governed_task(steps_done=list(_orch_steps), orch_answer_so_far=_orch_answer)
                            _append_governed_event("tool_result", _tool_result[:500], {
                                "tool_name": _tool_name,
                                "status": _tool_status,
                                "step_index": len(_orch_steps) - 1,
                                "duration_ms": _tool_ms,
                            })

                        # ── Spawn agent events (Phase 5) ──────────────────
                        elif _etype == "spawn_thinking":
                            yield _sse({
                                "type": "agent_thinking_token",
                                "content": _orch_event.get("content", ""),
                                "metadata": {
                                    "step": "spawn_agent",
                                    "is_subagent": True,
                                    "subagent_task": _orch_event.get("subagent_task", ""),
                                },
                            })

                        elif _etype == "spawn_tool":
                            _st_name = _orch_event.get("tool", "")
                            _st_status = _orch_event.get("status", "ok")
                            _st_ms = _orch_event.get("latency_ms")
                            yield _sse({
                                "type": "tool_start",
                                "content": f"[subagent] {_st_name}",
                                "metadata": {
                                    "tool_name": _st_name,
                                    "input": _orch_event.get("args", {}),
                                    "is_subagent": True,
                                    "subagent_task": _orch_event.get("subagent_task", ""),
                                },
                            })
                            yield _sse({
                                "type": "tool_result",
                                "content": _orch_event.get("result", "")[:300],
                                "metadata": {
                                    "tool_name": _st_name,
                                    "status": _st_status,
                                    "step_index": len(_orch_steps),
                                    "duration_ms": _st_ms,
                                    "is_subagent": True,
                                },
                            })
                            _orch_steps.append({
                                "tool": f"[subagent] {_st_name}",
                                "args": _orch_event.get("args", {}),
                                "status": _st_status,
                            })
                            _update_governed_task(
                                status=GovernedTaskStatus.AWAITING_SUBTASK.value,
                                wait_kind=GovernedTaskWaitKind.SUBAGENT.value,
                                steps_done=list(_orch_steps),
                                orch_answer_so_far=_orch_answer,
                            )
                            _append_governed_event("tool_result", _orch_event.get("result", "")[:300], {
                                "tool_name": _st_name,
                                "status": _st_status,
                                "is_subagent": True,
                            })

                        elif _etype == "spawn_complete":
                            _spawn_res = _orch_event.get("result")
                            _spawn_success = _orch_event.get("success", False)
                            _spawn_ms = _orch_event.get("elapsed_ms", 0)
                            _update_governed_task(
                                status=GovernedTaskStatus.RUNNING.value,
                                wait_kind=None,
                                steps_done=list(_orch_steps),
                                orch_answer_so_far=_orch_answer,
                            )
                            _safe_print(f"[ORCHESTRATOR] Subagent complete: success={_spawn_success}, {_spawn_ms:.0f}ms")
                            yield _sse({
                                "type": "status",
                                "content": f"Subagent {'done' if _spawn_success else 'failed'} ({_spawn_ms:.0f}ms)",
                                "metadata": {"is_subagent": True},
                            })

                        elif _etype == "agent_checkpoint":
                            _checkpoint_content = _orch_event.get("content", "")
                            _orch_meta = _orch_event.get("metadata", {})
                            _checkpoint_tier = _orch_meta.get("checkpoint_tier", "plan")
                            _append_governed_event("agent_checkpoint", _checkpoint_content, _orch_meta)

                            # Emit the question/content as a visible token
                            if _checkpoint_content:
                                yield _sse({"type": "token", "content": _checkpoint_content})
                            # Emit the checkpoint event itself (ActionCard renders it)
                            yield _sse(_orch_event)

                            if _checkpoint_tier == "file_write":
                                # Diff preview — suspend loop, write on user approval next turn
                                _diff_suspended = {
                                    "type": "diff_write",
                                    "objective": _orch_msg,
                                    "steps_done": list(_orch_steps),
                                    "orch_answer_so_far": _orch_answer,
                                    "remaining_iterations": getattr(_orch, 'max_iterations', 10) - len(_orch_steps),
                                    "diff_data": {
                                        "path": _orch_meta.get("diff_preview", ""),  # stored inline
                                        "target_path": _orch_meta.get("target_path", ""),
                                        "diff_preview": _orch_meta.get("diff_preview", ""),
                                        # actual path/content captured from the orchestrator event
                                        "_raw_meta": _orch_meta,
                                    },
                                }
                                _session_db.store_suspended_loop(req.thread_id, _diff_suspended)
                                _update_governed_task(
                                    status=GovernedTaskStatus.AWAITING_USER.value,
                                    wait_kind=GovernedTaskWaitKind.DIFF_WRITE.value,
                                    checkpoint_tier="file_write",
                                    question=_checkpoint_content,
                                    steps_done=list(_orch_steps),
                                    orch_answer_so_far=_orch_answer,
                                )
                                _safe_print(f"[ORCHESTRATOR] Diff checkpoint suspended: {_orch_meta.get('target_path')}")
                                yield _sse({
                                    "type": "done",
                                    "content": _orch_answer,
                                    "metadata": {
                                        "loop_suspended": True,
                                        "loop_question": _checkpoint_content,
                                        "response_type": "diff_preview",
                                        "checkpoint_tier": "file_write",
                                    },
                                })
                                return
                            else:
                                # Plan proposal (and any other tier) — break and let next message confirm
                                _session_db.store_pending_checkpoint(
                                    thread_id=req.thread_id,
                                    intent_data={
                                        "route": "task",
                                        "intent_type": "plan_create",
                                        "slots": {},
                                        "confidence": 0.95,
                                        "reason": "plan_proposal",
                                        "source": "orchestrator",
                                        "_plan_proposal": True,
                                        "_plan_data": _orch_meta.get("plan_data", {}),
                                    },
                                    checkpoint_tier="plan",
                                    metadata=_orch_meta,
                                )
                                _update_governed_task(
                                    status=GovernedTaskStatus.AWAITING_CHECKPOINT.value,
                                    wait_kind=GovernedTaskWaitKind.CHECKPOINT.value,
                                    checkpoint_tier="plan",
                                    question=_checkpoint_content,
                                    steps_done=list(_orch_steps),
                                    orch_answer_so_far=_orch_answer,
                                )
                                _safe_print(f"[ORCHESTRATOR] Checkpoint: plan proposal stored + surfaced")
                                break

                        elif _etype == "response":
                            _orch_answer = _orch_event.get("content", "")
                            _update_governed_task(orch_answer_so_far=_orch_answer, steps_done=list(_orch_steps))
                            yield _sse({
                                "type": "token",
                                "content": _orch_answer,
                            })

                        elif _etype == "followup_suggest":
                            _followups = _orch_event.get("followups", [])
                            _is_complete = _orch_event.get("complete", True)
                            if _followups:
                                if _is_complete:
                                    _update_governed_task(pending_followups=list(_followups))
                                else:
                                    _update_governed_task(
                                        status=GovernedTaskStatus.NEEDS_FOLLOWUP.value,
                                        pending_followups=list(_followups),
                                        steps_done=list(_orch_steps),
                                        orch_answer_so_far=_orch_answer,
                                    )
                                _append_governed_event("followup_suggest", "Suggested follow-ups", {"followups": _followups, "complete": _is_complete})
                                yield _sse({
                                    "type": "followup_suggest",
                                    "content": "Suggested follow-ups",
                                    "metadata": {
                                        "followups": _followups,
                                        "complete": _is_complete,
                                    },
                                })

                        elif _etype == "ask_user":
                            _ask_question = _orch_event.get("content", "")
                            # 1. Yield the question as a visible token
                            yield _sse({"type": "token", "content": _ask_question})
                            # 2. Serialize loop state to session DB
                            #    We store enough to reconstruct: objective, tool results
                            #    so far, iteration count, and the question asked.
                            #    The generator itself can't be pickled — we reconstruct
                            #    from this checkpoint on resume.
                            _suspended_state = {
                                "objective": _orch_msg,
                                "steps_done": list(_orch_steps),
                                "iteration": _orch_iteration if "_orch_iteration" in dir() else 0,
                                "question": _ask_question,
                                "orch_answer_so_far": _orch_answer,
                                "remaining_iterations": getattr(_orch, 'max_iterations', 10) - len(_orch_steps),
                            }
                            _session_db.store_suspended_loop(req.thread_id, _suspended_state)
                            _update_governed_task(
                                status=GovernedTaskStatus.AWAITING_USER.value,
                                wait_kind=GovernedTaskWaitKind.ASK_USER.value,
                                question=_ask_question,
                                steps_done=list(_orch_steps),
                                orch_answer_so_far=_orch_answer,
                                remaining_iterations=max(0, getattr(_orch, 'max_iterations', 10) - len(_orch_steps)),
                            )
                            _append_governed_event("ask_user", _ask_question, {"task_status": GovernedTaskStatus.AWAITING_USER.value})
                            _safe_print(f"[ORCHESTRATOR] Loop suspended — ask_user: {_ask_question[:80]!r}")
                            # 3. Yield done with loop_suspended=True so frontend shows reply UI
                            yield _sse({
                                "type": "done",
                                "content": _orch_answer,
                                "metadata": {
                                    "loop_suspended": True,
                                    "loop_question": _ask_question,
                                    "response_type": "ask_user",
                                    "session_id": getattr(_session_db, "session_id", None),
                                },
                            })
                            return  # end this request; loop resumes on next user message

                        elif _etype == "done":
                            pass  # handled below

                    # Store in conversation history for multi-turn continuity
                    try:
                        _session_db.record_query(
                            thread_id=req.thread_id,
                            query_text=_orch_msg,
                            response_text=_orch_answer,
                        )
                        _safe_print(f"[ORCHESTRATOR] Stored in conversation history")
                    except Exception as _store_err:
                        _safe_print(f"[ORCHESTRATOR] Failed to store history (non-fatal): {_store_err}")

                    # ── Write-path parity: store user message as CRT memory ──
                    # The legacy pipeline calls engine.query() which stores user
                    # assertions via ingest_memory_write(). The orchestrator path
                    # skips query() entirely, so user facts were never extracted,
                    # slot-compared, or contradiction-checked. This block fixes that.
                    try:
                        _orch_input_kind = _orch_engine._classify_user_input(_orch_msg)
                        if _orch_input_kind == "assertion":
                            from personal_agent.crt_memory import MemorySource
                            _orch_kind = "user_fact"
                            try:
                                from personal_agent.belief_classifier import classify_assertion_kind
                                _orch_kind, _ = classify_assertion_kind(_orch_msg)
                            except Exception:
                                pass
                            _orch_engine.ingest_memory_write(
                                text=_orch_msg,
                                confidence=0.7,
                                source=MemorySource.USER,
                                context={"type": "user_input", "kind": "assertion", "via": "orchestrator"},
                                thread_id=req.thread_id,
                                authority="provisional",
                                kind=_orch_kind,
                            )
                            _safe_print(f"[ORCHESTRATOR_WRITE] Stored user assertion as memory: \"{_orch_msg[:60]}\"")
                        else:
                            _safe_print(f"[ORCHESTRATOR_WRITE] Skipped — input_kind={_orch_input_kind}")
                    except Exception as _orch_write_err:
                        _safe_print(f"[ORCHESTRATOR_WRITE] Failed (non-fatal): {_orch_write_err}")

                    # Emit trust_shift events from orchestrator run
                    try:
                        _orch_db_path = getattr(_orch_engine.memory, "db_path", None)
                        if _orch_db_path:
                            import sqlite3 as _sq3_orch
                            from pathlib import Path as _Path_orch
                            if _Path_orch(_orch_db_path).exists():
                                _orch_conn = _sq3_orch.connect(_orch_db_path, timeout=5)
                                _orch_conn.execute("PRAGMA journal_mode=WAL")
                                _orch_cursor = _orch_conn.cursor()
                                # Get trust shifts from last 60 seconds (covers this orchestrator run)
                                _orch_cursor.execute(
                                    "SELECT memory_id, old_trust, new_trust, reason FROM trust_log "
                                    "WHERE timestamp > ? ORDER BY timestamp",
                                    (time.time() - 60,)
                                )
                                _TRUST_REASON_MAP_ORCH = {
                                    "cited": "cited", "citation_bump": "cited", "citation": "cited",
                                    "corroborate": "corroborated", "nli_support": "corroborated",
                                    "contradiction": "contradicted", "nli_contra": "contradicted",
                                    "decay": "decayed", "reinforced": "reinforced",
                                }
                                for _trow in _orch_cursor.fetchall():
                                    _tr_raw = str(_trow[3] or "")
                                    yield _sse({
                                        "type": "trust_shift",
                                        "metadata": {
                                            "memoryId": str(_trow[0]),
                                            "from": round(float(_trow[1] or 0), 3),
                                            "to": round(float(_trow[2] or 0), 3),
                                            "reason": _TRUST_REASON_MAP_ORCH.get(_tr_raw.lower().strip(), _tr_raw),
                                            "text": "",
                                        },
                                    })
                                _orch_conn.close()
                    except Exception as _orch_ts_err:
                        _safe_print(f"[ORCHESTRATOR] trust_shift emission failed (non-fatal): {_orch_ts_err}")

                    # Phase 6: push proactive suggestion to outbox if present
                    # Any part of the run that set a proactive_suggestion in
                    # the answer metadata (e.g. a subagent noticing something)
                    # gets queued for the WS drain loop to deliver unprompted.
                    try:
                        from personal_agent.outbox import get_outbox as _get_outbox
                        _outbox = _get_outbox()
                        # Check if orchestrator flagged a follow-up worth surfacing
                        if _orch_steps and len(_orch_steps) >= 3:
                            # Heuristic: multi-step runs often have follow-on questions.
                            # Agent loop can explicitly push to outbox via a special tool in future.
                            # For now, check if the answer ends with a question.
                            _ans_stripped = _orch_answer.strip()
                            if _ans_stripped.endswith("?") and len(_ans_stripped) > 50:
                                _outbox.push(
                                    thread_id=req.thread_id,
                                    content=_ans_stripped.split("\n")[-1].strip(),
                                    trigger="agent_loop_followup",
                                    metadata={"steps": len(_orch_steps), "source": "agent_loop"},
                                )
                    except Exception as _outbox_err:
                        _safe_print(f"[ORCHESTRATOR] Outbox push failed (non-fatal): {_outbox_err}")

                    # Emit drift + session_state from orchestrator run
                    try:
                        from personal_agent.agent_run_log import get_run_log_db as _get_rl_db
                        _rl_db = _get_rl_db()
                        _rl_recent = _rl_db.get_recent_runs(limit=1)
                        if _rl_recent:
                            _rl_row = _rl_recent[0]
                            _rl_dc = int(_rl_row.get("drift_count") or 0)
                            _rl_conf = float(_rl_row.get("confidence") or 1.0)
                            if _rl_dc > 0:
                                yield _sse({
                                    "type": "drift",
                                    "content": f"{_rl_dc} drift event(s)",
                                    "metadata": {
                                        "drift_count": _rl_dc,
                                        "intent_alignment": round(_rl_conf, 3),
                                        "total_trust_delta": 0.0,
                                    },
                                })
                    except Exception as _rl_err:
                        _safe_print(f"[ORCHESTRATOR] drift event failed (non-fatal): {_rl_err}")
                    try:
                        from personal_agent.session_state import get_or_create_session as _get_orch_sess
                        _orch_sess = _get_orch_sess(req.thread_id)
                        yield _sse({
                            "type": "session_state",
                            "content": f"density={_orch_sess.cumulative_density:.4f}",
                            "metadata": {
                                "cumulative_density": round(_orch_sess.cumulative_density, 4),
                                "open_contradiction_count": int(_orch_sess.open_contradiction_count),
                                "total_trust_delta": round(_orch_sess.total_trust_delta, 3),
                                "turn_count": int(_orch_sess.turn_count),
                                "memories_confirmed": int(_orch_sess.memories_confirmed),
                            },
                        })
                    except Exception as _sess_err:
                        _safe_print(f"[ORCHESTRATOR] session_state event failed (non-fatal): {_sess_err}")

                    # Emit final done event
                    _safe_print(f"[ORCHESTRATOR] Complete: {len(_orch_steps)} steps, answer_len={len(_orch_answer)}")
                    if _governed_task:
                        _governed_task = _session_db.complete_governed_task(str(_governed_task["task_id"]), _orch_answer) or _governed_task
                        _append_governed_event("done", _orch_answer, {"task_status": GovernedTaskStatus.COMPLETED.value, "generation_source": "agent_loop"})
                    yield _sse({"type": "agent_loop_complete", "content": _orch_answer, "metadata": {"generation_source": "agent_loop"}})
                    # Get request cost
                    _orch_cost = 0.0
                    try:
                        from personal_agent.litellm_client import get_default_llm_client
                        _orch_cost = round(get_default_llm_client().get_request_cost(), 6)
                    except Exception:
                        pass
                    yield _sse({
                        "type": "done",
                        "content": _orch_answer,
                        "metadata": {
                            "tool_calls": _orch_steps,
                            "agent_loop": True,
                            "orchestrator": True,
                            "tools_executed": len(_orch_steps) > 0,
                            "response_type": "task",
                            "gates_passed": True,
                            "generation_source": "agent_loop",
                            "cost_usd": _orch_cost,
                        },
                    })
                    return

                except Exception as _orch_err:
                    if _governed_task:
                        _governed_task = _session_db.fail_governed_task(str(_governed_task["task_id"]), str(_orch_err)) or _governed_task
                        _append_governed_event("error", str(_orch_err), {"task_status": GovernedTaskStatus.FAILED.value})
                    _safe_print(f"[ORCHESTRATOR] >>> EXCEPTION: {_orch_err}")
                    import traceback
                    traceback.print_exc()
                    logger.warning("[STREAM] Orchestrator failed, falling back to legacy path: %s", _orch_err)
                    # Fall through to legacy path

            # ── TASK ROUTE: URL fetch / instruction execution ─────────────
            _safe_print("[AGENT_LOOP_GATE] >>> LEGACY PATH (agent loop was skipped or failed)")
            if _task_intent is not None and _task_intent.route == "task":
                try:
                    _get_engine = request.app.state.get_engine
                    _engine = _get_engine(req.thread_id)
                    _llm_client = build_request_llm_client(request, req, uid)

                    _agent = CRTTaskAgent(
                        memory_agent=_engine.memory,
                        llm_client=_llm_client,
                        session_db=_session_db,
                    )
                    _safe_print(f"[LEGACY_PATH] CRTTaskAgent created, intent_type={_task_intent.intent_type}")

                    # ── Sprint 8: Pick sync vs async orchestrated path ────
                    # Multi-intent tasks use the async orchestrator for
                    # parallel sub-agent execution. Single-intent tasks
                    # use the existing sync path (no overhead).
                    _use_orchestrator = (
                        _task_intent.intent_type in ("multi_intent", "multi_step")
                    )

                    _checkpoint_hit = False
                    _task_steps: list = []
                    _task_answer = ""
                    _task_meta: dict = {}

                    if _use_orchestrator:
                        # ── ASYNC ORCHESTRATED PATH (Sprint 8) ────────────
                        # Run the async generator on a dedicated event loop
                        # in a background thread. Events stream back via a
                        # thread-safe queue to this sync SSE generator.
                        import asyncio as _asyncio
                        import threading as _threading
                        import queue as _sync_queue

                        _event_q: _sync_queue.Queue = _sync_queue.Queue()
                        _orch_done = _threading.Event()
                        _orch_error: list = []

                        def _run_async_orchestrator():
                            loop = _asyncio.new_event_loop()
                            _asyncio.set_event_loop(loop)
                            try:
                                async def _inner():
                                    async for evt in _agent.run_stream_async(
                                        req.message, req.thread_id, _task_intent,
                                        active_task=_active_task,
                                        user_confirmed=_user_confirmed,
                                    ):
                                        _event_q.put(evt)
                                loop.run_until_complete(_inner())
                            except Exception as _ae:
                                _orch_error.append(_ae)
                                logger.error("[STREAM] Async orchestrator error: %s", _ae, exc_info=True)
                            finally:
                                _orch_done.set()
                                loop.close()

                        _orch_thread = _threading.Thread(
                            target=_run_async_orchestrator, daemon=True,
                        )
                        _orch_thread.start()

                        # Stream events from the queue to the SSE response
                        while not _orch_done.is_set() or not _event_q.empty():
                            try:
                                _event = _event_q.get(timeout=0.2)
                            except _sync_queue.Empty:
                                continue

                            if _event["type"] in ("agent_checkpoint", "agent_checkpoint_write"):
                                yield _sse(_event)
                                _checkpoint_hit = True
                                _cp_tier = (
                                    _event.get("metadata", {}).get("checkpoint_tier")
                                    or "tier_1"
                                )
                                _session_db.store_pending_checkpoint(
                                    thread_id=req.thread_id,
                                    intent_data={
                                        "route": _task_intent.route,
                                        "intent_type": _task_intent.intent_type,
                                        "slots": _task_intent.slots,
                                        "confidence": _task_intent.confidence,
                                        "reason": _task_intent.reason,
                                        "source": getattr(_task_intent, "source", "regex"),
                                    },
                                    checkpoint_tier=_cp_tier,
                                    metadata=_event.get("metadata"),
                                )
                                break

                            yield _sse(_event)
                            if _event["type"] == "tool_result":
                                _task_steps.append(_event.get("metadata", {}))
                            elif _event["type"] in ("subtask_done",):
                                _task_steps.append(_event.get("metadata", {}))
                            elif _event["type"] == "task_done":
                                _task_answer = _event.get("content", "")
                                _task_meta = _event.get("metadata", {})

                        # Wait for thread to finish
                        _orch_thread.join(timeout=5)

                        if _orch_error and not _checkpoint_hit:
                            _err_msg = f"Orchestration error: {_orch_error[0]}"
                            yield _sse({"type": "error", "content": _err_msg})
                            yield _sse({"type": "done", "content": _err_msg, "metadata": {"error": True}})
                            return

                    else:
                        # ── SYNC PATH (existing behavior) ─────────────────
                        for _event in _agent.run_stream(
                            req.message, req.thread_id, _task_intent,
                            active_task=_active_task, user_confirmed=_user_confirmed,
                        ):
                            if _event["type"] in ("agent_checkpoint", "agent_checkpoint_write"):
                                yield _sse(_event)
                                _checkpoint_hit = True
                                _cp_tier = (
                                    _event.get("metadata", {}).get("checkpoint_tier")
                                    or _event.get("metadata", {}).get("tier")
                                    or "tier_1"
                                )
                                _session_db.store_pending_checkpoint(
                                    thread_id=req.thread_id,
                                    intent_data={
                                        "route": _task_intent.route,
                                        "intent_type": _task_intent.intent_type,
                                        "slots": _task_intent.slots,
                                        "confidence": _task_intent.confidence,
                                        "reason": _task_intent.reason,
                                        "source": getattr(_task_intent, "source", "regex"),
                                    },
                                    checkpoint_tier=_cp_tier,
                                    metadata=_event.get("metadata"),
                                )
                                break

                            yield _sse(_event)
                            if _event["type"] == "tool_result":
                                _task_steps.append(_event.get("metadata", {}))
                            elif _event["type"] == "task_done":
                                _task_answer = _event.get("content", "")
                                _task_meta = _event.get("metadata", {})

                    if _checkpoint_hit:
                        yield _sse({
                            "type": "done",
                            "content": _event["content"],
                            "metadata": {"checkpoint_pending": True},
                        })
                        return

                    # Task agent already streamed tokens via _stream_generate_answer;
                    # just emit the done event with the captured answer and metadata.
                    _done_meta = {
                        **_task_meta,
                        "tool_calls": _task_steps,
                    }

                    # ── INTUITION CHECK: Post-task suggestion ────────────────
                    try:
                        if not _is_cloud_governance_allowed(req, uid):
                            raise RuntimeError("strict local-only mode")
                        from personal_agent.intuition_check import get_intuition_check as _get_tap_post
                        from personal_agent.cloud_features import get_cloud_feature_service as _get_cfs_post
                        _tap_post = _get_tap_post(cloud_service=_get_cfs_post())
                        _completed_info = {
                            "intent_type": getattr(_task_intent, "intent_type", "unknown"),
                            "answer": str(_task_answer)[:300],
                        }
                        _open_tasks_post = [_active_task] if _active_task else []
                        _tap_suggest = _tap_post.suggest_next(
                            completed_task=_completed_info,
                            open_tasks=_open_tasks_post,
                        )
                        if _tap_suggest is not None:
                            logger.info(
                                "[STREAM] Intuition check suggest: %s (latency=%dms)",
                                _tap_suggest.message[:60], _tap_suggest.latency_ms,
                            )
                            _done_meta["intuition_check"] = {
                                "action": "suggest",
                                "message": _tap_suggest.message,
                                "suggested_action": _tap_suggest.metadata.get("suggested_action"),
                                "latency_ms": _tap_suggest.latency_ms,
                            }
                    except Exception as _tap_post_err:
                        logger.debug("[STREAM] Intuition check suggest skipped/failed: %s", _tap_post_err)

                    # --- Governance gate (legacy task path) ---
                    if _LEGACY_GOVERNANCE and _task_answer:
                        try:
                            # Compute belief from retrieval grounding instead of hardcoding
                            _legacy_belief = 0.4
                            try:
                                _legacy_mems = result.get("retrieved_memories") or result.get("prompt_memories") or []
                                if _legacy_mems:
                                    _legacy_belief = min(0.75, 0.3 + 0.05 * len(_legacy_mems))
                                    _avg_t = sum(m.get("trust", 0.5) for m in _legacy_mems) / len(_legacy_mems)
                                    if _avg_t > 0.7:
                                        _legacy_belief = min(0.8, _legacy_belief + 0.1)
                            except Exception:
                                pass
                            # Fetch recent responses for tension detection
                            _recent_resps = []
                            try:
                                _tension_engine = request.app.state.get_engine(req.thread_id)
                                _bs_conn = _tension_engine.memory._get_connection()
                                _recent_rows = _bs_conn.execute(
                                    "SELECT response FROM belief_speech WHERE is_belief=0 ORDER BY timestamp DESC LIMIT 5"
                                ).fetchall()
                                _bs_conn.close()
                                _recent_resps = [r[0] for r in reversed(_recent_rows) if r[0]]
                            except Exception:
                                pass
                            _gov = _LEGACY_GOVERNANCE.govern_response(
                                text=_task_answer,
                                belief_confidence=_legacy_belief,
                                recent_responses=_recent_resps,
                                query=effective_message,
                            )
                            _done_meta["governance_tier"] = _gov.tier.value
                            _done_meta["governance_annotations"] = len(_gov.annotations)
                            if _gov.annotations:
                                _done_meta["governance_findings"] = [a.finding[:120] for a in _gov.annotations]
                            _safe_print(f"[GOVERNANCE_LEGACY] tier={_gov.tier.value}, annotations={len(_gov.annotations)}")
                            _tension_anns = [a for a in _gov.annotations if a.agent == "tension_detector"]
                            if _tension_anns:
                                for _ta in _tension_anns:
                                    _safe_print(f"[TENSION] {_ta.finding[:150]}")
                        except Exception as _gov_err:
                            logger.debug("[GOVERNANCE_LEGACY] Task path failed: %s", _gov_err)

                    # Inject request cost into done metadata
                    try:
                        from personal_agent.litellm_client import get_default_llm_client
                        _cost_client = get_default_llm_client()
                        _done_meta["cost_usd"] = round(_cost_client.get_request_cost(), 6)
                    except Exception:
                        _done_meta["cost_usd"] = 0.0
                    yield _sse({"type": "done", "content": _task_answer, "metadata": _done_meta})
                    return
                except Exception as _te:
                    logger.warning("[STREAM] TaskAgent failed, falling back to CRT pipeline: %s", _te)
                    # Fall through to CRT pipeline

            # ── INTUITION CHECK: Reconnect after idle ────────────────────
            # If the user has been idle for a while and there's open work,
            # the intuition check generates a natural reconnection message.
            try:
                if not _is_cloud_governance_allowed(req, uid):
                    raise RuntimeError("strict local-only mode")
                from personal_agent.intuition_check import get_intuition_check as _get_tap_recon
                from personal_agent.cloud_features import get_cloud_feature_service as _get_cfs_recon
                _tap_recon = _get_tap_recon(cloud_service=_get_cfs_recon())
                # Check idle time from session metadata
                _last_msg_age = 0.0
                try:
                    _session_db_recon = get_thread_session_db()
                    _last_ts = _session_db_recon.get_last_message_ts(req.thread_id)
                    if _last_ts:
                        _last_msg_age = time.time() - _last_ts
                except Exception:
                    pass
                if _last_msg_age > 300:  # 5 minutes idle
                    _open_tasks_recon = []
                    try:
                        _at = _session_db_recon.get_pending_task(req.thread_id)
                        if _at:
                            _open_tasks_recon = [_at]
                    except Exception:
                        pass
                    _tap_reconnect = _tap_recon.reconnect(
                        open_tasks=_open_tasks_recon,
                        last_message_age_seconds=_last_msg_age,
                    )
                    if _tap_reconnect is not None:
                        logger.info(
                            "[STREAM] Intuition check reconnect: %s (idle=%dm, latency=%dms)",
                            _tap_reconnect.message[:60],
                            int(_last_msg_age / 60),
                            _tap_reconnect.latency_ms,
                        )
                        yield _sse({
                            "type": "intuition_check",
                            "content": _tap_reconnect.message,
                            "metadata": {
                                "tap_action": "reconnect",
                                "idle_minutes": int(_last_msg_age / 60),
                                "latency_ms": _tap_reconnect.latency_ms,
                                **_tap_reconnect.metadata,
                            },
                        })
            except Exception as _tap_recon_err:
                logger.debug("[STREAM] Intuition check reconnect skipped/failed: %s", _tap_recon_err)

            # ── Intent pre-pass for conversational route ──────────────────
            try:
                from personal_agent.fact_slots import extract_fact_slots as _efs

                def _quick_intent(text: str) -> str:
                    t = text.lower().strip()
                    correction_starters = ('no,', 'no.', 'no!', "that's wrong", "that is wrong",
                                           'actually,', 'actually.', 'wrong,', 'wrong.', 'not right',
                                           'incorrect', 'you said', 'you told',
                                           "that's a lie", "that was a lie", "those were lies",
                                           "i lied", "that's false", "that's not true",
                                           "forget that", "forget what i said",
                                           "ignore what i said", "correction:",
                                           "i was wrong", "i was lying", "i was mistaken",
                                           "disregard what i said", "disregard that")
                    name_starters = ('my name is', 'call me', "i'm ", "i am ")
                    if any(t.startswith(s) for s in correction_starters):
                        return 'correction'
                    # Also catch mid-sentence correction patterns
                    if any(w in t for w in ("i lied about", "i'm not allergic",
                                            "i don't have", "i never said",
                                            "actually i'm not", "actually i don't")):
                        return 'correction'
                    if any(t.startswith(s) for s in name_starters) and len(t.split()) <= 6:
                        return 'learning'
                    if '?' in text:
                        return 'question'
                    if any(w in t for w in ('contradict', 'conflict', 'remember', 'told you', 'lied')):
                        return 'contradiction'
                    return 'statement'

                _intent = _quick_intent(req.message)
                _slots = _efs(req.message)
                _slot_keys = [k for k in _slots if k not in ('assistant_name',)]

                _intent_parts = [f'intent: {_intent}']
                if _slot_keys:
                    _intent_parts.append('recalling: ' + ', '.join(_slot_keys[:3]))

                yield f"data: {json.dumps({'type': 'intent_preview', 'content': ' · '.join(_intent_parts), 'metadata': {'intent': _intent, 'slots': _slot_keys}})}\n\n"
            except Exception as _ipe:
                logger.debug("[STREAM] intent pre-pass failed: %s", _ipe)

            yield _phase('plan', 'Processing')

            # ── Run pipeline in background, emit real status events ──────
            result_q: _queue_mod.Queue = _queue_mod.Queue()
            err_q: _queue_mod.Queue = _queue_mod.Queue()
            status_q: _queue_mod.Queue = _queue_mod.Queue()
            event_q: _queue_mod.Queue = _queue_mod.Queue()

            def _run():
                # Set the pipeline status queue so _emit_pipeline_status works
                _pipeline_status_queue.set(status_q)
                # Set the structured event queue so _emit_pipeline_event works
                _pipeline_event_queue.set(event_q)
                try:
                    result_q.put(_run_shared_chat_pipeline(req, request))
                except Exception as exc:
                    err_q.put(exc)

            t = threading.Thread(target=_run, daemon=True)
            t.start()

            import time as _time
            _last_status_t = _time.monotonic()
            _fallback_idx = 0
            _fallback_statuses = ['reasoning', 'planning response', 'verifying', 'drafting']
            while t.is_alive():
                # Drain any real pipeline status events
                _got_real = False
                try:
                    while True:
                        _ps = status_q.get_nowait()
                        yield _status(_ps)
                        _last_status_t = _time.monotonic()
                        _got_real = True
                except _queue_mod.Empty:
                    pass
                # Drain structured pipeline events (retrieval, trust_shift, verification)
                try:
                    while True:
                        _pe = event_q.get_nowait()
                        yield _sse(_pe)
                except _queue_mod.Empty:
                    pass
                # If no real status in 2.5s, emit a fallback heartbeat
                if not _got_real and _time.monotonic() - _last_status_t > 2.5:
                    if _fallback_idx < len(_fallback_statuses):
                        yield _status(_fallback_statuses[_fallback_idx])
                        _fallback_idx += 1
                        _last_status_t = _time.monotonic()
                _time.sleep(0.05)

            # Drain any remaining status events after thread completes
            try:
                while True:
                    yield _status(status_q.get_nowait())
            except _queue_mod.Empty:
                pass
            # Drain any remaining structured events (trust_shifts arrive after pipeline completes)
            try:
                while True:
                    yield _sse(event_q.get_nowait())
            except _queue_mod.Empty:
                pass

            t.join()

            if not err_q.empty():
                raise err_q.get()

            shared_response = result_q.get()
            yield _phase('plan', end=True)

            # ── Post-pipeline status insights ─────────────────────────────
            metadata: Dict[str, Any] = dict(shared_response.metadata or {})
            metadata.setdefault("response_type", shared_response.response_type)
            metadata.setdefault("gates_passed", shared_response.gates_passed)
            metadata.setdefault("gate_reason", shared_response.gate_reason)
            metadata.setdefault("session_id", shared_response.session_id)

            _gates_passed = shared_response.gates_passed
            _response_type = shared_response.response_type or "speech"
            _gate_reason = shared_response.gate_reason or ""
            _retrieved = metadata.get("retrieved_memories") or []
            _prompt_mems = metadata.get("prompt_memories") or []
            _mem_count = len(_retrieved) + len(_prompt_mems)

            if _mem_count > 0:
                yield _status(f'{_mem_count} memories read')
            if metadata.get("contradiction_detected"):
                _open = metadata.get("unresolved_contradictions_total", 0)
                yield _status(f'contradiction detected ({_open} open)')
            if metadata.get("agent_activated"):
                yield _status('agent activated')
            _suggested = metadata.get("agent_suggested_triggers") or []
            if _suggested:
                yield _status(f'{len(_suggested)} agent trigger(s) suggested — awaiting confirmation')
            if not _gates_passed:
                yield _status(f'gate: {_gate_reason or "blocked"}')
            if _response_type not in ("speech", ""):
                yield _status(_response_type)

            # ── Thinking content ──────────────────────────────────────────
            thinking_content = _strip_thinking_tags(str(metadata.get("thinking") or "")).strip()
            if thinking_content:
                yield f"data: {json.dumps({'type': 'thinking_start', 'content': ''})}\n\n"
                for thought_chunk in _chunk_text(thinking_content, chunk_size=280):
                    yield f"data: {json.dumps({'type': 'thinking_token', 'content': thought_chunk})}\n\n"
                yield f"data: {json.dumps({'type': 'thinking_end', 'content': ''})}\n\n"

            # ── Stream answer tokens with mid-stream verification ────────
            answer = str(shared_response.answer or "")
            yield _phase('answer', 'Writing response')

            # Initialize stream verifier for checkpoint-based checks
            _stream_stopped = False
            try:
                from personal_agent.stream_verifier import StreamVerifier
                _verifier = StreamVerifier(
                    retrieved_memories=_retrieved,
                    checkpoint_interval=150,
                )
                _streamed_buffer = ""
                for text_chunk in _chunk_text(answer):
                    _streamed_buffer += text_chunk
                    yield f"data: {json.dumps({'type': 'token', 'content': text_chunk})}\n\n"

                    # Run checkpoint if we've accumulated enough tokens
                    if _verifier.should_checkpoint(_streamed_buffer):
                        _cp_result = _verifier.run_checkpoint(_streamed_buffer)

                        # Emit checkpoint event for frontend pipeline trace
                        yield _sse({
                            "type": "stream_checkpoint",
                            "content": f"Checkpoint @ ~{_cp_result.token_count} tokens",
                            "metadata": _cp_result.to_dict(),
                        })

                        if _cp_result.action == "strip" and _cp_result.stripped_content is not None:
                            # Think tag leak: replace answer with stripped version
                            answer = _cp_result.stripped_content
                            logger.warning("[STREAM_VERIFY] Think tags stripped from response")
                            # Continue streaming — the tags are stripped from final answer

                        elif _cp_result.action == "stop":
                            # Fact contradiction or repetition: stop generation
                            logger.warning(
                                "[STREAM_VERIFY] Stopping stream: %s",
                                _cp_result.detail,
                            )
                            answer = _streamed_buffer  # Keep what we have
                            _stream_stopped = True
                            yield _sse({
                                "type": "stream_stopped",
                                "content": _cp_result.detail or "Stream stopped by verification",
                                "metadata": _cp_result.to_dict(),
                            })
                            break

                # Store verification summary in metadata
                _verify_summary = _verifier.get_summary()
                if _verify_summary["checkpoints_run"] > 0:
                    metadata["stream_verification"] = _verify_summary

            except ImportError:
                # StreamVerifier not available — fall back to simple chunking
                for text_chunk in _chunk_text(answer):
                    yield f"data: {json.dumps({'type': 'token', 'content': text_chunk})}\n\n"
            except Exception as _sv_err:
                logger.debug("[STREAM_VERIFY] Verification failed: %s", _sv_err)
                # Already streamed what we have — continue

            yield _phase('answer', end=True)

            # ── Self-correction check (before done) ──────────────────────
            # If the answer says "I don't know" but we actually have data,
            # emit a correction event so the user sees it in the same turn.
            correction_text = None
            try:
                correction_text = _post_answer_quick_check(
                    answer=answer,
                    retrieved_memories=_retrieved,
                    session_db=session_db,
                    thread_id=req.thread_id,
                )
            except Exception as _corr_err:
                logger.debug("[STREAM] correction check failed: %s", _corr_err)

            if correction_text:
                yield f"data: {json.dumps({'type': 'correction', 'content': correction_text})}\n\n"
                metadata["correction_applied"] = True
                metadata["correction_text"] = correction_text

            # ── Proactive pattern suggestions (Sprint 4) ─────────────────
            try:
                from personal_agent.proactive_triggers import check_proactive_patterns
                _proactive = check_proactive_patterns(req.message, answer)
                if _proactive:
                    metadata["proactive_suggestion"] = {
                        "trigger": _proactive.name,
                        "suggestion": _proactive.suggestion,
                        "action": _proactive.action,
                    }
            except Exception as _pt_err:
                logger.debug("[STREAM] Proactive pattern check failed: %s", _pt_err)

            # --- Governance gate (legacy conversational path) ---
            if _LEGACY_GOVERNANCE and answer:
                try:
                    # Compute belief from retrieval grounding
                    _conv_belief = 0.4
                    try:
                        _conv_mems = result.get("retrieved_memories") or result.get("prompt_memories") or []
                        if _conv_mems:
                            _conv_belief = min(0.75, 0.3 + 0.05 * len(_conv_mems))
                            _avg_t = sum(m.get("trust", 0.5) for m in _conv_mems) / len(_conv_mems)
                            if _avg_t > 0.7:
                                _conv_belief = min(0.8, _conv_belief + 0.1)
                    except Exception:
                        pass
                    # Fetch recent responses for tension detection
                    _recent_resps_conv = []
                    try:
                        _tension_engine2 = request.app.state.get_engine(req.thread_id)
                        _bs_conn2 = _tension_engine2.memory._get_connection()
                        _rr2 = _bs_conn2.execute(
                            "SELECT response FROM belief_speech WHERE is_belief=0 ORDER BY timestamp DESC LIMIT 5"
                        ).fetchall()
                        _bs_conn2.close()
                        _recent_resps_conv = [r[0] for r in reversed(_rr2) if r[0]]
                    except Exception:
                        pass
                    _gov = _LEGACY_GOVERNANCE.govern_response(
                        text=answer,
                        belief_confidence=_conv_belief,
                        recent_responses=_recent_resps_conv,
                        query=effective_message,
                    )
                    metadata["governance_tier"] = _gov.tier.value
                    metadata["governance_annotations"] = len(_gov.annotations)
                    if _gov.annotations:
                        metadata["governance_findings"] = [a.finding[:120] for a in _gov.annotations]
                    _safe_print(f"[GOVERNANCE_LEGACY] tier={_gov.tier.value}, annotations={len(_gov.annotations)}")
                    _tension_anns2 = [a for a in _gov.annotations if a.agent == "tension_detector"]
                    if _tension_anns2:
                        for _ta2 in _tension_anns2:
                            _safe_print(f"[TENSION] {_ta2.finding[:150]}")
                    if _gov.should_block:
                        _findings = "; ".join(a.finding for a in _gov.annotations)
                        answer = (
                            f"[GOVERNANCE ESCALATION: {_findings}]\n\n"
                            f"The following response has been flagged. "
                            f"Review the findings above before relying on this answer.\n\n"
                            f"{answer}"
                        )
                except Exception as _gov_err:
                    logger.debug("[GOVERNANCE_LEGACY] Failed: %s", _gov_err)

            # Inject gate check results into done metadata
            try:
                _gate_checks = shared_response.metadata.get("gate_checks") if hasattr(shared_response, "metadata") and shared_response.metadata else None
                if not _gate_checks:
                    _gate_checks = result.get("gate_checks") if "result" in dir() and isinstance(result, dict) else None
                if _gate_checks:
                    metadata["gate_checks"] = _gate_checks
                else:
                    # Build from what we know
                    metadata["gate_checks"] = {
                        "slot": metadata.get("slot_type", "none"),
                        "nli": "pass" if metadata.get("gates_passed") else metadata.get("gate_reason", "unknown"),
                        "gap": "safe",
                    }
                    # Check governance findings for gap audit
                    for _gf in (metadata.get("governance_findings") or []):
                        if "gap" in str(_gf).lower():
                            metadata["gate_checks"]["gap"] = "flagged"
                            break
            except Exception:
                metadata.setdefault("gate_checks", {"slot": "none", "nli": "none", "gap": "safe"})

            # Inject belief confidence into done metadata
            # pre_gen_belief is computed at the structural gate and stored in the
            # shared_response.metadata by _run_shared_chat_pipeline. We read it
            # from shared_response.metadata (NOT from `result` which is in a
            # different scope/thread).
            try:
                if "belief_confidence" not in metadata:
                    # Try shared_response.metadata first (set by pipeline)
                    _pgb = (shared_response.metadata or {}).get("pre_gen_belief") if hasattr(shared_response, "metadata") else None
                    # Fallback: try result if it exists in scope
                    if _pgb is None and "result" in dir() and isinstance(result, dict):
                        _pgb = result.get("pre_gen_belief")
                    metadata["belief_confidence"] = round(float(_pgb or 0.4), 3)
            except Exception:
                metadata.setdefault("belief_confidence", 0.4)

            # Inject request cost into done metadata
            try:
                from personal_agent.litellm_client import get_default_llm_client
                metadata["cost_usd"] = round(get_default_llm_client().get_request_cost(), 6)
            except Exception:
                metadata.setdefault("cost_usd", 0.0)

            yield f"data: {json.dumps({'type': 'done', 'content': answer, 'metadata': metadata})}\n\n"

        except Exception as e:
            logger.error(f"[STREAM] Stream error: {e}", exc_info=True)
            yield f"data: {json.dumps({'type': 'error', 'content': str(e)})}\n\n"

    return StreamingResponse(
        generate_stream(),
        media_type="text/event-stream; charset=utf-8",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


# ============================================================================
# POST /api/chat/intent
# ============================================================================


@router.post("/intent", response_model=IntentQueryResponse)
def chat_intent(req: IntentQueryRequest, request: Request, authorization: Optional[str] = Header(None)) -> IntentQueryResponse:
    """Query with IntentRouter + FactStore routing.

    Uses IntentRouter + FactStore for smarter routing,
    with optional trace for debugging/transparency.
    """
    get_engine = request.app.state.get_engine
    increment_turn = request.app.state.increment_turn
    _log_collapse_trail = request.app.state.log_collapse_trail

    # Propagate authenticated user_id into memory context variable
    uid = resolve_user_id(authorization)
    if uid:
        from personal_agent.crt_memory import _request_user_id
        _request_user_id.set(uid)

    engine = get_engine(req.thread_id)
    increment_turn(req.thread_id)
    groundcheck_bridge_meta: Optional[Dict[str, Any]] = None
    try:
        groundcheck_bridge_meta = _maybe_sync_groundcheck_bridge(
            thread_id=req.thread_id,
            engine=engine,
        )
    except Exception as e:
        logger.debug(f"[MEMORY_BRIDGE] Intent sync failed: {e}")
        groundcheck_bridge_meta = {"enabled": True, "attempted": True, "ok": False, "error": str(e)}

    # Enable tracing if requested
    if hasattr(engine, "enable_tracing"):
        engine.enable_tracing(req.include_trace)

    # Use intent query if available
    if hasattr(engine, "query_with_intent"):
        result = engine.query_with_intent(
            user_query=req.message,
            user_marked_important=req.user_marked_important,
            thread_id=req.thread_id,
            channel=req.channel,
            origin=req.origin,
            authority=req.authority,
            kind=req.kind,
        )
    else:
        session_db = get_thread_session_db()
        history_messages = _load_recent_history_messages(session_db, req.thread_id, window=6)
        query_with_continuity = _augment_query_with_continuity(
            message=req.message,
            history_messages=history_messages,
        )
        preference_profile = _get_preference_profile(req.thread_id, engine.memory)
        model_override, model_route = _route_model_for_request(
            request,
            query=req.message,
            mode=None,
            preference_profile=preference_profile,
            channel=None,
        )
        result = engine.query(
            user_query=query_with_continuity,
            user_marked_important=req.user_marked_important,
            model_override=model_override,
            conversation_history=history_messages or None,
            channel=req.channel,
            origin=req.origin,
            authority=req.authority,
            kind=req.kind,
        )
        result["intent"] = "unknown"
        result["trace"] = None
        result["model_route"] = model_route

    metadata: Dict[str, Any] = {
        "mode": result.get("mode"),
        "contradiction_detected": result.get("contradiction_detected"),
        "retrieved_memories": len(result.get("retrieved_memories") or []),
        "structured_facts": result.get("structured_facts"),
        "fact_store_hit": result.get("fact_store_hit", False),
        "model_route": result.get("model_route"),
        "groundcheck_bridge": groundcheck_bridge_meta,
    }
    collapse_trail_id = _log_collapse_trail(
        thread_id=req.thread_id,
        query=req.message,
        answer=str(result.get("answer") or ""),
        result=result,
        stage="chat_intent",
        mode="intent",
    )
    if collapse_trail_id:
        metadata["collapse_trail_id"] = collapse_trail_id

    return IntentQueryResponse(
        answer=result.get("answer", ""),
        intent=result.get("intent", "unknown"),
        confidence=result.get("confidence", 0.0),
        response_type=result.get("response_type", "speech"),
        gates_passed=result.get("gates_passed", False),
        gate_reason=result.get("gate_reason"),
        trace=result.get("trace") if req.include_trace else None,
        metadata=metadata,
    )


# ---------------------------------------------------------------------------
# POST /api/chat/feedback
# ---------------------------------------------------------------------------

from ..models import ChatFeedbackRequest  # noqa: E402 — appended section

# Severity weights by category — hallucination hits trust hardest, tone barely at all
_FEEDBACK_SEVERITY: dict[str, float] = {
    "hallucination": 1.0,
    "wrong_fact":    0.67,
    "other":         0.33,
    "tone":          0.13,
}


@router.post("/feedback")
def chat_feedback(req: ChatFeedbackRequest) -> dict:
    """Submit thumbs-up/down feedback for a past chat response.

    On thumbs-down:
      • records the rating in the active-learning DB via record_feedback_thumbs()
      • degrades trust on every cited memory by (severity × η_neg)
      • appends a 'user_flagged' event to each memory's event log (append-only)
      • queues the interaction as a high-priority correction example

    On thumbs-up:
      • records the rating
      • lightly reinforces trust on cited memories

    Returns which memories were affected and their old/new trust values.
    """
    affected: list[dict] = []

    # ── 1. Record in active-learning DB ──────────────────────────────────────
    severity = _FEEDBACK_SEVERITY.get(req.category or "", 0.33)
    feedback_priority = severity if not req.thumbs_up else 0.0

    try:
        coordinator = get_active_learning_coordinator()
        coordinator.record_feedback_thumbs(
            interaction_id=req.interaction_id,
            thumbs_up=req.thumbs_up,
            comment=req.comment or req.category,
            feedback_priority=feedback_priority,
        )
        logger.info(
            "[FEEDBACK] %s on interaction=%s category=%s priority=%.2f",
            "👍" if req.thumbs_up else "👎",
            req.interaction_id,
            req.category,
            feedback_priority,
        )
    except Exception as exc:
        logger.warning("[FEEDBACK] active-learning record failed: %s", exc)

    # ── 1b. Emit turn telemetry ───────────────────────────────────────────────
    try:
        coordinator = get_active_learning_coordinator()
        coordinator.emit_turn_event(
            event_type="feedback_down" if not req.thumbs_up else "feedback_up",
            thread_id=req.thread_id,
            interaction_id=req.interaction_id,
            severity=feedback_priority,
            memory_ids=req.memory_ids_cited or [],
            payload={"category": req.category, "comment": req.comment},
        )
    except Exception as exc:
        logger.debug("[FEEDBACK] telemetry emit failed: %s", exc)

    # ── 2. Trust updates on cited memories ───────────────────────────────────
    if req.memory_ids_cited:

        try:
            from personal_agent.crt_memory import CRTMemorySystem
            from personal_agent.crt_core import CRTMath, CRTConfig

            crt_mem = CRTMemorySystem()
            crt_math = CRTMath(CRTConfig())

            with crt_mem._get_connection() as conn:
                conn.row_factory = sqlite3.Row
                for mid in req.memory_ids_cited:
                    row = conn.execute(
                        "SELECT trust, text FROM memories WHERE memory_id = ? AND (deprecated IS NULL OR deprecated = 0)",
                        (mid,),
                    ).fetchone()
                    if not row:
                        continue

                    old_trust = float(row["trust"])

                    if req.thumbs_up:
                        # Positive signal — light reinforcement
                        new_trust = min(0.95, old_trust + crt_math.config.eta_pos * (1.0 - severity * 0.3))
                    else:
                        # Negative signal — drift-aware degradation scaled by severity
                        delta = crt_math.config.eta_neg * severity
                        new_trust = max(0.20, old_trust - delta)

                    conn.execute(
                        "UPDATE memories SET trust = ? WHERE memory_id = ?",
                        (round(new_trust, 4), mid),
                    )

                    # Append audit event (append-only — never deletes)
                    try:
                        crt_mem.record_memory_event(
                            memory_id=mid,
                            event_type="user_flagged" if not req.thumbs_up else "user_reinforced",
                            details={
                                "interaction_id": req.interaction_id,
                                "thumbs_up": req.thumbs_up,
                                "category": req.category,
                                "old_trust": old_trust,
                                "new_trust": round(new_trust, 4),
                                "severity": severity,
                            },
                        )
                    except Exception as ev_exc:
                        logger.debug("[FEEDBACK] memory event log failed: %s", ev_exc)

                    affected.append(
                        {"memory_id": mid, "old_trust": old_trust, "new_trust": round(new_trust, 4)}
                    )

                conn.commit()

        except Exception as exc:
            logger.warning("[FEEDBACK] trust update failed: %s", exc)

    # ── 3. Queue as high-priority correction if thumbs-down ──────────────────
    if not req.thumbs_up:
        try:
            coordinator = get_active_learning_coordinator()
            coordinator.record_feedback_correction(
                interaction_id=req.interaction_id,
                correction_type=req.category or "general_feedback",
                user_comment=req.comment,
            )
            logger.info(
                "[FEEDBACK] queued correction for interaction=%s", req.interaction_id
            )
        except Exception as exc:
            logger.debug("[FEEDBACK] correction queue failed: %s", exc)

    # ── 4. Reflection trigger — high-severity thumbs-down queues self-assessment
    if not req.thumbs_up and req.category in ("hallucination", "wrong_fact"):
        try:
            coordinator = get_active_learning_coordinator()
            coordinator.emit_turn_event(
                event_type="reflection_queued",
                thread_id=req.thread_id,
                interaction_id=req.interaction_id,
                severity=severity,
                memory_ids=req.memory_ids_cited or [],
                payload={
                    "category": req.category,
                    "trigger": "user_thumbs_down",
                    "priority": "high",
                },
            )
            logger.info(
                "[FEEDBACK] reflection queued for interaction=%s category=%s",
                req.interaction_id,
                req.category,
            )
        except Exception as exc:
            logger.debug("[FEEDBACK] reflection queue emit failed: %s", exc)

    return {
        "ok": True,
        "interaction_id": req.interaction_id,
        "thumbs_up": req.thumbs_up,
        "memories_affected": affected,
    }
