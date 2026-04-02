"""Agent tool loop runner for chat stream."""

from __future__ import annotations

import logging
from typing import Any, Generator, Optional

from personal_agent.governed_task import GovernedTaskStatus, GovernedTaskWaitKind
from personal_agent.runtime_config import get_runtime_config

from .chat_runtime import ChatStreamRuntime, StreamTerminalResult


logger = logging.getLogger(__name__)


def run_agent_tool_loop(
    runtime: ChatStreamRuntime,
    task_intent: Any,
    active_task: Any,
    user_confirmed: bool,
    recent_history: Optional[list],
) -> Generator[str, None, StreamTerminalResult]:
    req = runtime.req
    request = runtime.request
    session_db = runtime.session_db
    rt_cfg = get_runtime_config()
    al_cfg = rt_cfg.get("agent_loop", {})

    try:
        from personal_agent.agent_tool_loop import AgentToolLoop

        runtime.ensure_governed_task(objective=req.message, max_iterations=int(al_cfg.get("max_iterations", 10) or 10))
        runtime.update_governed_task(status=GovernedTaskStatus.RUNNING.value, wait_kind=None, question=None)
        runtime.append_governed_event("agent_loop_start", req.message, {"mode": "agent_tool_loop"})
        yield runtime.emit({"type": "agent_loop_start", "content": "Agent loop started", "metadata": {"mode": "agent_tool_loop"}})

        get_llm = request.app.state.get_llm_client
        llm_client = get_llm()
        al_max_iter = al_cfg.get("max_iterations", 10)
        al_show_thinking = al_cfg.get("show_thinking", True)

        try:
            import auth as _auth_tooling

            uid_tooling = int(runtime.uid) if runtime.uid else 1
            user_al_enabled = _auth_tooling.get_user_setting(uid_tooling, "tooling_agent_loop_enabled", "true")
            if user_al_enabled == "false":
                runtime.safe_print("[AGENT_LOOP_GATE] Agent loop disabled by user tooling settings")
                raise StopIteration("agent_loop_disabled_by_user")
            user_max_iter = _auth_tooling.get_user_setting(uid_tooling, "tooling_agent_loop_max_iterations", "")
            if user_max_iter and user_max_iter.isdigit():
                al_max_iter = max(1, min(50, int(user_max_iter)))
            user_show_thinking = _auth_tooling.get_user_setting(uid_tooling, "tooling_agent_loop_show_thinking", "true")
            al_show_thinking = user_show_thinking != "false"

            user_fallback = _auth_tooling.get_user_setting(uid_tooling, "tooling_fallback_policy", "")
            if user_fallback and llm_client is not None:
                llm_client.fallback_policy = user_fallback
                runtime.safe_print(f"[AGENT_LOOP] Fallback policy set to: {user_fallback}")

            if llm_client is not None:
                for role in ("fast", "reasoning", "tool_loop", "answer"):
                    user_role_model = _auth_tooling.get_user_setting(uid_tooling, f"tooling_model_role_{role}", "")
                    if user_role_model:
                        if not hasattr(llm_client, "model_roles") or llm_client.model_roles is None:
                            llm_client.model_roles = {}
                        llm_client.model_roles[role] = user_role_model
                        runtime.safe_print(f"[AGENT_LOOP] Model role '{role}' overridden to: {user_role_model}")
        except StopIteration:
            raise
        except Exception as tooling_err:
            runtime.safe_print(f"[AGENT_LOOP] Warning: failed to read tooling settings: {tooling_err}")

        al_engine = None
        try:
            al_engine = request.app.state.get_engine(req.thread_id)
        except Exception:
            pass

        al_intent_hint = None
        try:
            from personal_agent.task_agent import triage_message, _INTENT_TOOL_MAP

            triage = triage_message(req.message, task_intent)
            ack_text = triage.acknowledgment
            tools_planned = triage.tools_needed or _INTENT_TOOL_MAP.get(task_intent.intent_type, [])
            if ack_text:
                yield runtime.emit(
                    {
                        "type": "intent_preview",
                        "content": ack_text,
                        "metadata": {
                            "intent": task_intent.intent_type,
                            "route": task_intent.route,
                            "confidence": task_intent.confidence,
                            "tools_planned": tools_planned,
                            "source": getattr(task_intent, "source", ""),
                        },
                    }
                )
                runtime.safe_print(f"[AGENT_LOOP] Intent preview: {ack_text} (tools={tools_planned})")
            al_intent_hint = f"User intent: {task_intent.intent_type}. Suggested tools: {', '.join(tools_planned) if tools_planned else 'none'}."
        except Exception as triage_err:
            runtime.safe_print(f"[AGENT_LOOP] Triage failed (non-fatal): {triage_err}")

        loop = AgentToolLoop(
            llm_client,
            session_db=session_db,
            max_iterations=al_max_iter,
            show_thinking=al_show_thinking,
            engine=al_engine,
            intent_hint=al_intent_hint,
        )

        al_tool_filter = None
        try:
            from personal_agent.tool_gate import get_agent_loop_filter

            al_tool_filter = get_agent_loop_filter(
                intent_type=getattr(task_intent, "intent_type", "task"),
                route=getattr(task_intent, "route", None),
            )
            if al_tool_filter:
                runtime.safe_print(f"[TOOL_GATE] Agent loop: {len(al_tool_filter)} tools for intent={getattr(task_intent, 'intent_type', '?')}")
        except Exception:
            pass

        loop_gen = loop.run(
            req.message,
            req.thread_id,
            conversation_history=recent_history or None,
            tool_filter=al_tool_filter,
        )

        checkpoint_hit = False
        answer = ""
        steps: list = []
        generation_source = ""

        try:
            event = next(loop_gen)
            while True:
                logger.info("[SSE_DEBUG] Emitting event type=%s content_len=%d", event.get("type"), len(str(event.get("content", ""))))
                yield runtime.emit(event)

                if event["type"] == "agent_checkpoint":
                    checkpoint_hit = True
                    cp_tier = event.get("metadata", {}).get("checkpoint_tier", "medium")
                    session_db.store_pending_checkpoint(
                        thread_id=req.thread_id,
                        intent_data={
                            "route": task_intent.route,
                            "intent_type": task_intent.intent_type,
                            "slots": task_intent.slots,
                            "confidence": task_intent.confidence,
                            "reason": task_intent.reason,
                            "source": getattr(task_intent, "source", "agent_loop"),
                            "_agent_loop": True,
                            "_loop_state": {
                                "message": req.message,
                                "tool_name": event.get("metadata", {}).get("tool_name"),
                                "tool_args": event.get("metadata", {}).get("tool_args"),
                            },
                        },
                        checkpoint_tier=cp_tier,
                        metadata=event.get("metadata"),
                    )
                    runtime.update_governed_task(
                        status=GovernedTaskStatus.AWAITING_CHECKPOINT.value,
                        wait_kind=GovernedTaskWaitKind.CHECKPOINT.value,
                        checkpoint_tier=cp_tier,
                        question=event.get("content", ""),
                        steps_done=list(steps),
                        orch_answer_so_far=answer,
                    )
                    runtime.append_governed_event("agent_checkpoint", event.get("content", ""), event.get("metadata", {}))
                    break
                if event["type"] == "token":
                    answer += event.get("content", "")
                elif event["type"] == "tool_result":
                    steps.append(event.get("metadata", {}))
                    runtime.update_governed_task(steps_done=list(steps), orch_answer_so_far=answer)
                    runtime.append_governed_event("tool_result", event.get("content", ""), event.get("metadata", {}))
                elif event["type"] == "agent_loop_complete":
                    generation_source = event.get("metadata", {}).get("generation_source", "")
                    runtime.append_governed_event("agent_loop_complete", event.get("content", ""), event.get("metadata", {}))

                event = loop_gen.send(None)
        except StopIteration:
            pass

        logger.info(
            "[SSE_DEBUG] Loop exited: checkpoint_hit=%s, al_answer_len=%d, steps=%d",
            checkpoint_hit,
            len(answer),
            len(steps),
        )

        if checkpoint_hit:
            yield runtime.emit({"type": "done", "content": event.get("content", ""), "metadata": {"checkpoint_pending": True, "agent_loop": True}})
            return StreamTerminalResult(terminal=True, handled=True, metadata={"checkpoint_pending": True})

        tools_executed = len(steps) > 0
        if not generation_source:
            generation_source = "local" if tools_executed else "agent_loop"
        runtime.safe_print(f"[GEN_SOURCE] SSE final: generation_source={generation_source}, tools_executed={tools_executed}")
        done_meta = {
            "tool_calls": steps,
            "agent_loop": True,
            "tools_executed": tools_executed,
            "response_type": "task",
            "gates_passed": True,
            "generation_source": generation_source,
        }
        if runtime.governed_task:
            runtime.governed_task = session_db.complete_governed_task(str(runtime.governed_task["task_id"]), answer) or runtime.governed_task
            runtime.append_governed_event("done", answer, {"task_status": GovernedTaskStatus.COMPLETED.value, **done_meta})
        yield runtime.emit({"type": "agent_loop_complete", "content": answer, "metadata": {"generation_source": generation_source}})
        yield runtime.emit({"type": "done", "content": answer, "metadata": done_meta})
        return StreamTerminalResult(terminal=True, handled=True, metadata=done_meta)
    except Exception as err:
        if runtime.governed_task:
            runtime.governed_task = session_db.fail_governed_task(str(runtime.governed_task["task_id"]), str(err)) or runtime.governed_task
            runtime.append_governed_event("error", str(err), {"task_status": GovernedTaskStatus.FAILED.value})
        runtime.safe_print(f"[AGENT_LOOP_GATE] >>> EXCEPTION in agent loop: {err}")
        logger.warning("[STREAM] Agent tool loop failed, falling back to legacy path: %s", err, exc_info=True)
        return StreamTerminalResult(terminal=False, handled=False)
