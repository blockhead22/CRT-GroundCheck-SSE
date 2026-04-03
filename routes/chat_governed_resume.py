"""Governed resume/checkpoint handling for chat stream."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Generator, Optional

from personal_agent.governed_task import GovernedTaskStatus, GovernedTaskWaitKind
from personal_agent.runtime_config import get_runtime_config

from .chat_provider_routing import build_request_llm_client, resolve_effective_generation_mode
from .chat_runtime import ChatStreamRuntime


logger = logging.getLogger(__name__)


@dataclass
class ResumeOutcome:
    handled: bool = False
    terminal: bool = False
    task_intent: Optional[Any] = None
    user_confirmed: bool = False


def try_resume_or_resolve(
    runtime: ChatStreamRuntime,
    *,
    recent_history: Optional[list] = None,
) -> Generator[str, None, ResumeOutcome | None]:
    from personal_agent.task_agent import TaskIntent, parse_checkpoint_confirmation as _parse_confirm

    req = runtime.req
    request = runtime.request
    session_db = runtime.session_db

    try:
        suspended = session_db.get_suspended_loop(req.thread_id)
        if suspended:
            runtime.governed_task = session_db.get_active_governed_task(req.thread_id)
            if runtime.governed_task and str(runtime.governed_task.get("source") or "") == "agent_loop":
                runtime.update_governed_task(
                    status=GovernedTaskStatus.RUNNING.value,
                    wait_kind=None,
                    question=None,
                )
                runtime.append_governed_event("resume", req.message, {"resume_kind": str(suspended.get("type") or "ask_user")})
            session_db.clear_suspended_loop(req.thread_id)
            runtime.safe_print(f"[ORCHESTRATOR] Resuming suspended loop — user answered: {req.message[:80]!r}")
            yield from _resume_suspended_loop(runtime, suspended)
            return ResumeOutcome(handled=True, terminal=True)
    except Exception as err:
        runtime.safe_print(f"[ORCHESTRATOR] Suspend check failed (non-fatal): {err}")

    pending_cp = session_db.get_pending_checkpoint(req.thread_id)
    if not pending_cp:
        return None

    cp_source = pending_cp.get("intent", {}).get("source", "")
    cp_suggested = [
        action.get("value", "")
        for action in (pending_cp.get("metadata", {}) or {}).get("suggested_actions", [])
    ]
    msg_stripped = req.message.strip().lower()

    if cp_source in ("embedding_ambiguous",) and msg_stripped in cp_suggested:
        chosen_intent = msg_stripped
        route = "conversational" if chosen_intent == "conversational" else "task"
        task_intent = TaskIntent(
            route=route,
            intent_type=chosen_intent,
            slots={},
            confidence=0.95,
            reason="user_disambiguated",
            source="embedding_ambiguous",
        )
        session_db.clear_pending_checkpoint(req.thread_id)
        logger.info("[STREAM] User disambiguated: %s", chosen_intent)
        try:
            from personal_agent.task_agent import _get_semantic_router

            sr = _get_semantic_router()
            if sr:
                original = pending_cp.get("intent", {}).get("intent_type", "ambiguous")
                sr.record_correction(req.message, original, chosen_intent, "user_disambiguate")
        except Exception:
            pass
        return ResumeOutcome(handled=True, terminal=False, task_intent=task_intent, user_confirmed=True)

    confirmation = _parse_confirm(req.message)
    if confirmation is True:
        cp_data = pending_cp["intent"]

        if cp_data.get("_agent_loop"):
            session_db.clear_pending_checkpoint(req.thread_id)
            logger.info("[STREAM] User confirmed agent loop checkpoint — resuming loop")
            yield from _resume_agent_loop_checkpoint(runtime, cp_data, recent_history=recent_history)
            return ResumeOutcome(handled=True, terminal=True, user_confirmed=True)

        if cp_data.get("_plan_proposal"):
            session_db.clear_pending_checkpoint(req.thread_id)
            yield from _approve_plan_proposal(runtime, cp_data)
            return ResumeOutcome(handled=True, terminal=True, user_confirmed=True)

        task_intent = TaskIntent(
            route=cp_data["route"],
            intent_type=cp_data["intent_type"],
            slots=cp_data.get("slots", {}),
            confidence=cp_data.get("confidence", 0.9),
            reason=cp_data.get("reason", ""),
        )
        session_db.clear_pending_checkpoint(req.thread_id)
        logger.info("[STREAM] User confirmed agentic checkpoint")
        return ResumeOutcome(handled=True, terminal=False, task_intent=task_intent, user_confirmed=True)

    if confirmation is False:
        cancelled_intent = pending_cp.get("intent", {})
        runtime.governed_task = session_db.get_active_governed_task(req.thread_id)
        session_db.clear_pending_checkpoint(req.thread_id)
        session_db.clear_pending_task(req.thread_id)
        if runtime.governed_task and str(runtime.governed_task.get("source") or "") == "agent_loop":
            runtime.governed_task = session_db.cancel_governed_task(
                str(runtime.governed_task["task_id"]),
                "Task cancelled. What would you like to do instead?",
            ) or runtime.governed_task
            runtime.append_governed_event(
                "cancelled",
                "Task cancelled. What would you like to do instead?",
                {"task_status": GovernedTaskStatus.CANCELLED.value},
            )
        logger.info("[STREAM] User denied agentic checkpoint — emitting cancellation")
        yield runtime.emit(
            {
                "type": "task_cancelled",
                "content": "Task cancelled. What would you like to do instead?",
                "metadata": {
                    "cancelled_intent": cancelled_intent.get("intent_type", ""),
                    "cancelled_service": cancelled_intent.get("slots", {}).get("service", ""),
                },
            }
        )
        yield runtime.emit(
            {
                "type": "done",
                "content": "Task cancelled. What would you like to do instead?",
                "metadata": {"task_cancelled": True},
            }
        )
        return ResumeOutcome(handled=True, terminal=True)

    session_db.clear_pending_checkpoint(req.thread_id)
    logger.info("[STREAM] Ambiguous checkpoint response — reclassifying")
    return ResumeOutcome(handled=False, terminal=False)


def _resume_suspended_loop(
    runtime: ChatStreamRuntime,
    suspended: dict,
) -> Generator[str, None, None]:
    req = runtime.req
    session_db = runtime.session_db

    suspended_type = suspended.get("type", "ask_user")
    if suspended_type == "diff_write":
        dw_raw_meta = suspended.get("diff_data", {}).get("_raw_meta", {})
        dw_write_path = dw_raw_meta.get("_write_path", "")
        dw_write_content = dw_raw_meta.get("_write_content", "")
        dw_target_path = dw_raw_meta.get("target_path", "?")
        dw_msg_lower = req.message.lower().strip()
        dw_approved = any(
            word in dw_msg_lower for word in ("yes", "approve", "ok", "sure", "do it", "go ahead", "confirm", "write it")
        ) and not any(word in dw_msg_lower for word in ("no", "reject", "cancel", "don't", "skip"))
        if dw_approved and dw_write_path and dw_write_content:
            try:
                import os as _os_dw

                _os_dw.makedirs(_os_dw.path.dirname(dw_write_path) or ".", exist_ok=True)
                with open(dw_write_path, "w", encoding="utf-8") as handle:
                    handle.write(dw_write_content)
                dw_result_msg = f"Written {len(dw_write_content)} chars to {dw_target_path}"
                runtime.safe_print(f"[ORCHESTRATOR] Diff approved + written: {dw_target_path}")
            except Exception as err:
                dw_result_msg = f"Write failed: {err}"
                runtime.safe_print(f"[ORCHESTRATOR] Diff write error: {err}")
        else:
            dw_result_msg = f"User rejected write to {dw_target_path}."
            runtime.safe_print(f"[ORCHESTRATOR] Diff rejected: {dw_target_path}")

        yield runtime.emit({"type": "token", "content": dw_result_msg + "\n\n"})
        resume_objective = suspended.get("objective", req.message)
        resume_steps = suspended.get("steps_done", [])
        resume_answer_so_far = suspended.get("orch_answer_so_far", "") + dw_result_msg + "\n\n"
        resume_steps_text = "\n".join(
            f"  - {step.get('tool', '?')}: {str(step.get('status', ''))}" for step in resume_steps
        ) if resume_steps else ""
        resume_msg = (
            f"{resume_objective}\n\n"
            f"[CONTEXT: You paused to show a diff preview for {dw_target_path!r}. Result: {dw_result_msg}\n"
            + (f"Previous steps completed:\n{resume_steps_text}\n" if resume_steps_text else "")
            + "Continue and complete the task.]"
        )
    else:
        resume_objective = suspended.get("objective", req.message)
        resume_steps = suspended.get("steps_done", [])
        resume_question = suspended.get("question", "")
        resume_answer_so_far = suspended.get("orch_answer_so_far", "")
        resume_steps_text = "\n".join(
            f"  - {step.get('tool', '?')}: {str(step.get('status', ''))}" for step in resume_steps
        ) if resume_steps else ""
        resume_msg = (
            f"{resume_objective}\n\n"
            f"[CONTEXT: You were executing this task and paused to ask: {resume_question!r}\n"
            f"The user replied: {req.message!r}\n"
            + (f"Previous steps completed:\n{resume_steps_text}\n" if resume_steps_text else "")
            + "Continue the task with this answer. Do not re-plan.]"
        )

    yield runtime.emit_status("Resuming...")
    try:
        from personal_agent.cookie_orchestrator import Orchestrator, get_brain

        r_brain_mode = resolve_effective_generation_mode(req, runtime.uid)
        r_brain = get_brain("claude-cli" if r_brain_mode == "cloud_claude" else "claude-cli")
        r_remaining = suspended.get("remaining_iterations", 8)
        runtime.safe_print(f"[ORCHESTRATOR] Resume brain: {r_brain_mode}, remaining_iterations: {r_remaining}")
        r_orch = Orchestrator(brain=r_brain, max_iterations=max(3, r_remaining))
        r_gen = r_orch.run(resume_msg)
        r_orch_answer = resume_answer_so_far
        r_steps: list = list(resume_steps)
        r_send_val = None
        while True:
            try:
                r_event = r_gen.send(r_send_val) if r_send_val is not None else next(r_gen)
                r_send_val = None
            except StopIteration:
                break
            r_etype = r_event.get("type", "")

            if r_etype == "plan":
                plan_txt = r_event.get("content", "")
                if plan_txt:
                    yield runtime.emit({"type": "token", "content": plan_txt + "\n\n"})
                    r_orch_answer += plan_txt + "\n\n"
            elif r_etype in ("thinking", "think"):
                yield runtime.emit(
                    {
                        "type": "agent_thinking_token",
                        "content": r_event.get("content", ""),
                        "metadata": {"step": "tool_loop"},
                    }
                )
            elif r_etype == "tool_call":
                rt_name = r_event.get("tool", "")
                rt_args = r_event.get("args", {})
                rt_result = r_event.get("result", "")
                rt_status = r_event.get("status", "ok")
                rt_ms = r_event.get("latency_ms")
                yield runtime.emit({"type": "tool_start", "content": f"Running {rt_name}...", "metadata": {"tool_name": rt_name, "input": rt_args}})
                yield runtime.emit({"type": "tool_result", "content": rt_result[:500], "metadata": {"tool_name": rt_name, "status": rt_status, "step_index": len(r_steps), "duration_ms": rt_ms}})
                runtime.append_governed_event("tool_result", rt_result[:500], {"tool_name": rt_name, "status": rt_status, "step_index": len(r_steps), "duration_ms": rt_ms})
                r_steps.append({"tool": rt_name, "args": rt_args, "status": rt_status})
            elif r_etype == "ask_user":
                r_question = r_event.get("content", "")
                yield runtime.emit({"type": "token", "content": r_question})
                session_db.store_suspended_loop(
                    req.thread_id,
                    {
                        "objective": resume_objective,
                        "steps_done": r_steps,
                        "iteration": 0,
                        "question": r_question,
                        "orch_answer_so_far": r_orch_answer,
                        "remaining_iterations": getattr(r_orch, "max_iterations", 8) - len(r_steps),
                    },
                )
                runtime.update_governed_task(
                    status=GovernedTaskStatus.AWAITING_USER.value,
                    wait_kind=GovernedTaskWaitKind.ASK_USER.value,
                    question=r_question,
                    steps_done=list(r_steps),
                    orch_answer_so_far=r_orch_answer,
                    remaining_iterations=max(0, getattr(r_orch, "max_iterations", 8) - len(r_steps)),
                )
                runtime.append_governed_event("ask_user", r_question, {"task_status": GovernedTaskStatus.AWAITING_USER.value})
                yield runtime.emit({"type": "done", "content": r_orch_answer, "metadata": {"loop_suspended": True, "loop_question": r_question, "response_type": "ask_user"}})
                return
            elif r_etype == "response":
                r_resp = r_event.get("content", "")
                if r_resp:
                    yield runtime.emit({"type": "token", "content": r_resp})
                    r_orch_answer += r_resp

        if runtime.governed_task:
            runtime.governed_task = session_db.complete_governed_task(str(runtime.governed_task["task_id"]), r_orch_answer) or runtime.governed_task
            runtime.append_governed_event("done", r_orch_answer, {"task_status": GovernedTaskStatus.COMPLETED.value})
        yield runtime.emit({"type": "done", "content": r_orch_answer, "metadata": {"response_type": "speech", "tool_calls": r_steps, "orchestrator": "agent_loop_resume"}})
    except Exception as resume_err:
        if runtime.governed_task:
            runtime.governed_task = session_db.fail_governed_task(str(runtime.governed_task["task_id"]), str(resume_err)) or runtime.governed_task
            runtime.append_governed_event("error", str(resume_err), {"task_status": GovernedTaskStatus.FAILED.value})
        runtime.safe_print(f"[ORCHESTRATOR] Resume failed: {resume_err}")
        yield runtime.emit({"type": "token", "content": f"I ran into an issue resuming our conversation: {resume_err}"})
        yield runtime.emit({"type": "done", "content": "", "metadata": {"response_type": "error"}})


def _resume_agent_loop_checkpoint(
    runtime: ChatStreamRuntime,
    cp_data: dict,
    *,
    recent_history: Optional[list] = None,
) -> Generator[str, None, None]:
    req = runtime.req
    request = runtime.request
    session_db = runtime.session_db
    try:
        from personal_agent.agent_tool_loop import AgentToolLoop, _execute_tool, _needs_checkpoint, _describe_tool_action

        llm_client_alr = build_request_llm_client(request, req, runtime.uid)
        rt_cfg_alr = get_runtime_config()
        al_cfg_alr = rt_cfg_alr.get("agent_loop", {})

        try:
            import auth as _auth_tooling_r

            uid_tooling_r = int(runtime.uid) if runtime.uid else 1
            user_fallback_r = _auth_tooling_r.get_user_setting(uid_tooling_r, "tooling_fallback_policy", "")
            if user_fallback_r and llm_client_alr is not None:
                llm_client_alr.fallback_policy = user_fallback_r
            for role in ("fast", "reasoning", "tool_loop", "answer"):
                user_role_r = _auth_tooling_r.get_user_setting(uid_tooling_r, f"tooling_model_role_{role}", "")
                if user_role_r and llm_client_alr is not None:
                    if not hasattr(llm_client_alr, "model_roles") or llm_client_alr.model_roles is None:
                        llm_client_alr.model_roles = {}
                    llm_client_alr.model_roles[role] = user_role_r
        except Exception as tooling_err:
            logger.warning("[AGENT_LOOP_RESUME] Failed to read tooling settings: %s", tooling_err)

        loop_state = cp_data.get("_loop_state", {})
        pending_tool = loop_state.get("tool_name", "")
        pending_args = loop_state.get("tool_args", {})
        original_msg = loop_state.get("message", req.message)

        yield runtime.emit({"type": "tool_start", "content": f"▷ {pending_tool}", "metadata": {"tool_name": pending_tool, "input": pending_args, "step_index": 0}})
        confirmed_result = _execute_tool(pending_tool, pending_args, req.thread_id)
        yield runtime.emit({"type": "tool_result", "content": confirmed_result["content"][:500], "metadata": {**confirmed_result.get("metadata", {}), "status": confirmed_result["status"], "step_index": 0}})

        alr_engine = None
        try:
            alr_engine = request.app.state.get_engine(req.thread_id)
        except Exception:
            pass
        loop_alr = AgentToolLoop(
            llm_client_alr,
            session_db=session_db,
            max_iterations=al_cfg_alr.get("max_iterations", 10),
            show_thinking=al_cfg_alr.get("show_thinking", True),
            engine=alr_engine,
        )

        resume_msgs = loop_alr._build_messages(original_msg, recent_history or [])
        import json as _json_alr

        resume_msgs.append(
            {
                "role": "assistant",
                "content": None,
                "tool_calls": [{"id": "call_confirmed", "type": "function", "function": {"name": pending_tool, "arguments": _json_alr.dumps(pending_args)}}],
            }
        )
        resume_msgs.append({"role": "tool", "tool_call_id": "call_confirmed", "content": confirmed_result["content"][:4000]})

        alr_answer = ""
        alr_steps = [confirmed_result.get("metadata", {})]
        alr_schemas = loop_alr._build_tool_schemas(None)

        for alr_iter in range(al_cfg_alr.get("max_iterations", 10) - 1):
            try:
                alr_resp = llm_client_alr.chat_with_tools(resume_msgs, tools=alr_schemas, max_tokens=2000, temperature=0.1)
            except Exception as llm_err:
                logger.error("[AGENT_LOOP_RESUME] LLM error: %s", llm_err)
                yield runtime.emit({"type": "token", "content": f"Error during continuation: {llm_err}"})
                break

            alr_tcs = alr_resp.get("tool_calls", [])
            alr_text = (alr_resp.get("content") or "").strip()
            if not alr_tcs:
                if alr_text:
                    from personal_agent.text_utils import strip_thinking_tags

                    alr_clean = strip_thinking_tags(alr_text)
                    yield runtime.emit({"type": "token", "content": alr_clean})
                    alr_answer = alr_clean
                break

            for alr_tc in alr_tcs:
                alr_tn = alr_tc.get("name", "")
                alr_ta = alr_tc.get("arguments", {})
                if isinstance(alr_ta, str):
                    try:
                        alr_ta = _json_alr.loads(alr_ta)
                    except Exception:
                        alr_ta = {}
                if _needs_checkpoint(alr_tn):
                    yield runtime.emit(
                        {
                            "type": "agent_checkpoint",
                            "content": f"I need to {_describe_tool_action(alr_tn, alr_ta)}. Go ahead?",
                            "metadata": {
                                "requires_confirmation": True,
                                "checkpoint_tier": "medium",
                                "tool_name": alr_tn,
                                "tool_args": alr_ta,
                                "intent": alr_tn,
                                "confidence": 0.95,
                                "slots": alr_ta,
                            },
                        }
                    )
                    session_db.store_pending_checkpoint(
                        thread_id=req.thread_id,
                        intent_data={
                            "route": "task",
                            "intent_type": alr_tn,
                            "slots": alr_ta,
                            "confidence": 0.95,
                            "reason": "agent_loop_continuation",
                            "source": "agent_loop",
                            "_agent_loop": True,
                            "_loop_state": {"message": original_msg, "tool_name": alr_tn, "tool_args": alr_ta},
                        },
                        checkpoint_tier="medium",
                        metadata={"tool_name": alr_tn, "tool_args": alr_ta},
                    )
                    yield runtime.emit({"type": "done", "content": "", "metadata": {"checkpoint_pending": True, "agent_loop": True}})
                    return

                yield runtime.emit({"type": "tool_start", "content": f"▷ {alr_tn}", "metadata": {"tool_name": alr_tn, "input": alr_ta, "step_index": len(alr_steps)}})
                alr_res = _execute_tool(alr_tn, alr_ta, req.thread_id)
                alr_steps.append(alr_res.get("metadata", {}))
                yield runtime.emit({"type": "tool_result", "content": alr_res["content"][:500], "metadata": {**alr_res.get("metadata", {}), "status": alr_res["status"], "step_index": len(alr_steps) - 1}})

                resume_msgs.append(
                    {
                        "role": "assistant",
                        "content": None,
                        "tool_calls": [{"id": f"call_r{alr_iter}_{alr_tn}", "type": "function", "function": {"name": alr_tn, "arguments": _json_alr.dumps(alr_ta)}}],
                    }
                )
                resume_msgs.append({"role": "tool", "tool_call_id": f"call_r{alr_iter}_{alr_tn}", "content": alr_res["content"][:4000]})

        yield runtime.emit({"type": "done", "content": alr_answer, "metadata": {"tool_calls": alr_steps, "agent_loop": True, "response_type": "task", "gates_passed": True}})
    except Exception as alr_err:
        logger.warning("[STREAM] Agent loop resume failed: %s", alr_err, exc_info=True)


def _approve_plan_proposal(runtime: ChatStreamRuntime, cp_data: dict) -> Generator[str, None, None]:
    req = runtime.req
    plan_data = cp_data.get("_plan_data", {})
    plan_title = plan_data.get("title", "Untitled Plan")
    plan_steps = plan_data.get("steps", [])
    runtime.safe_print(f"[PLAN] User approved plan: {plan_title}")

    import json as _plan_json
    import os
    import time as _plan_time

    plan_file = os.path.join("D:/AI_round2/workspace", f"plan_{int(_plan_time.time())}.json")
    os.makedirs(os.path.dirname(plan_file), exist_ok=True)
    plan_save = {
        "title": plan_title,
        "steps": [
            {
                "title": step.get("title", step) if isinstance(step, dict) else str(step),
                "description": step.get("description", "") if isinstance(step, dict) else "",
                "status": "pending",
            }
            for step in plan_steps
        ],
        "created": _plan_time.strftime("%Y-%m-%d %H:%M:%S"),
        "status": "active",
        "approved": True,
        "thread_id": req.thread_id,
    }
    with open(plan_file, "w", encoding="utf-8") as handle:
        _plan_json.dump(plan_save, handle, indent=2)

    step_list = "\n".join(f"  {i + 1}. {step.get('title', step) if isinstance(step, dict) else step}" for i, step in enumerate(plan_steps))
    yield runtime.emit({"type": "token", "content": f"Plan approved and saved: **{plan_title}**\n\n{step_list}\n\nSaved to: {plan_file}"})
    yield runtime.emit({"type": "done", "content": f"Plan approved: {plan_title}", "metadata": {"plan_approved": True, "plan_file": plan_file}})
