"""Orchestrator runner for chat stream."""

from __future__ import annotations

import logging
import time
from typing import Any, Dict, Generator, List, Optional

from personal_agent.governed_task import GovernedTaskStatus, GovernedTaskWaitKind

from .chat_provider_routing import build_orchestrator_brain
from .chat_runtime import ChatStreamRuntime, StreamTerminalResult


logger = logging.getLogger(__name__)

_MAX_AUTO_CONTINUATIONS = 3


def _load_recent_history_messages(session_db, thread_id: str, *, window: int = 6) -> List[Dict[str, str]]:
    history_messages: List[Dict[str, str]] = []
    try:
        recent = session_db.get_recent_queries(thread_id, window=window)
        for item in reversed(recent):
            q = str((item or {}).get("query_text") or "").strip()
            r = str((item or {}).get("response_text") or "").strip()
            if q:
                history_messages.append({"role": "user", "content": q})
            if r:
                history_messages.append({"role": "assistant", "content": r})
    except Exception as err:
        logger.debug("[CONTINUITY] Failed to load history for %s: %s", thread_id, err)
    return history_messages


def _select_ack_text(message: str) -> str:
    msg_lower = message.lower().strip()
    if any(word in msg_lower for word in ("read", "open", "look at", "check", "show", "what", "find")):
        return "Looking at that..."
    if any(word in msg_lower for word in ("write", "edit", "update", "change", "fix", "patch")):
        return "On it."
    if any(word in msg_lower for word in ("search", "research", "fetch", "web")):
        return "On it, looking that up..."
    if any(word in msg_lower for word in ("run", "execute", "build", "test")):
        return "Running that..."
    return "On it."


def run_orchestrator(
    runtime: ChatStreamRuntime,
    task_intent: Any,
    routing_reason: str,
    recent_history: Optional[list],
) -> Generator[str, None, StreamTerminalResult]:
    req = runtime.req
    request = runtime.request
    session_db = runtime.session_db
    original_msg = str(req.message or "")

    runtime.safe_print(
        f"[ORCHESTRATOR] >>> ENTERING agent loop path "
        f"(intent={getattr(task_intent, 'intent_type', '')!r}, reason={routing_reason})"
    )
    runtime.ensure_governed_task(objective=original_msg, max_iterations=10)

    accumulated_answer = ""
    accumulated_steps: list = []
    continuation_count = 0
    current_msg = original_msg

    try:
        from personal_agent.cookie_orchestrator import Orchestrator

        orch_engine = request.app.state.get_engine(req.thread_id)

        orch_gen_mode, orch_brain = build_orchestrator_brain(req, runtime.uid)
        runtime.safe_print(
            f"[ORCHESTRATOR] Brain selected: {orch_gen_mode} -> {getattr(orch_brain, '_model', 'unknown')}"
        )

        while True:
            runtime.update_governed_task(
                status=GovernedTaskStatus.RUNNING.value,
                wait_kind=None,
                checkpoint_tier=None,
                question=None,
            )
            runtime.append_governed_event(
                "agent_loop_start",
                current_msg,
                {
                    "mode": "orchestrator",
                    "reason": routing_reason,
                    "continuation_index": continuation_count,
                },
            )
            yield runtime.emit(
                {
                    "type": "agent_loop_start",
                    "content": "Agent loop started",
                    "metadata": {
                        "mode": "orchestrator",
                        "reason": routing_reason,
                        "continuation_index": continuation_count,
                    },
                }
            )

            ack_text = _select_ack_text(current_msg)
            yield runtime.emit({"type": "token", "content": ack_text + "\n\n"})

            # Ensure contradiction ledger is accessible from memory system for belief injection
            if hasattr(orch_engine, 'ledger') and hasattr(orch_engine.memory, 'set_contradiction_ledger'):
                try:
                    orch_engine.memory.set_contradiction_ledger(orch_engine.ledger)
                except Exception:
                    pass

            orch = Orchestrator(brain=orch_brain, memory_system=orch_engine.memory, max_iterations=10)

            orch_history = []
            try:
                orch_recent = _load_recent_history_messages(session_db, req.thread_id, window=2)
                orch_history = [
                    f"{'User' if msg['role'] == 'user' else 'Aether'}: {msg['content'][:150]}"
                    for msg in orch_recent
                ]
                if orch_history:
                    runtime.safe_print(f"[ORCHESTRATOR] Loaded {len(orch_history)} history messages")
            except Exception as hist_err:
                runtime.safe_print(f"[ORCHESTRATOR] History load failed (non-fatal): {hist_err}")

            orch_answer = ack_text + "\n\n"
            orch_steps: list = []
            pending_followups: list[str] = []
            phase_complete = True
            orch_gen = orch.run(
                current_msg,
                conversation_history=orch_history or recent_history or None,
                intent_type=getattr(task_intent, "intent_type", None),
                route=getattr(task_intent, "route", None),
            )
            orch_send_val = None

            while True:
                try:
                    if orch_send_val is not None:
                        orch_event = orch_gen.send(orch_send_val)
                        orch_send_val = None
                    else:
                        orch_event = next(orch_gen)
                except StopIteration:
                    break

                etype = orch_event.get("type", "")
                if etype == "plan":
                    plan_content = orch_event.get("content", "")
                    plan_steps = orch_event.get("steps", [])
                    est_depth = orch_event.get("estimated_depth")
                    if est_depth is not None:
                        try:
                            clamped = max(5, min(10, int(est_depth) + 1))
                            orch.max_iterations = clamped
                            runtime.safe_print(
                                f"[ORCHESTRATOR] Adaptive depth: plan declared estimated_depth={est_depth} -> "
                                f"max_iterations={clamped}"
                            )
                        except (TypeError, ValueError):
                            pass
                    if plan_content:
                        plan_display = plan_content
                        if plan_steps:
                            plan_display += " -> " + " · ".join(plan_steps)
                        yield runtime.emit({"type": "thinking", "content": plan_display})
                elif etype == "thinking":
                    yield runtime.emit(
                        {
                            "type": "agent_thinking_token",
                            "content": orch_event.get("content", ""),
                            "metadata": {
                                "step": "orchestrator_thinking",
                                "alignment": orch_event.get("alignment"),
                            },
                        }
                    )
                elif etype == "drift_warning":
                    yield runtime.emit(
                        {
                            "type": "epistemic_event",
                            "content": orch_event.get("content", ""),
                            "metadata": {
                                "event": "drift",
                                "alignment": orch_event.get("alignment"),
                                "avg_alignment": orch_event.get("avg_alignment"),
                                "proposed_action": orch_event.get("proposed_action", ""),
                                "proposed_tool": orch_event.get("proposed_tool", ""),
                            },
                        }
                    )
                elif etype == "execution_drift":
                    yield runtime.emit(
                        {
                            "type": "epistemic_event",
                            "content": orch_event.get("content", ""),
                            "metadata": {
                                "event": "execution_drift",
                                "from_category": orch_event.get("from_category", ""),
                                "to_category": orch_event.get("to_category", ""),
                                "alignment": orch_event.get("alignment"),
                            },
                        }
                    )
                elif etype == "contradiction_warning":
                    yield runtime.emit(
                        {
                            "type": "epistemic_event",
                            "content": orch_event.get("content", ""),
                            "metadata": {
                                "event": "contradiction",
                                "step_a": orch_event.get("step_a"),
                                "step_b": orch_event.get("step_b"),
                            },
                        }
                    )
                elif etype == "tool_call":
                    tool_name = orch_event.get("tool", "")
                    tool_args = orch_event.get("args", {})
                    tool_result = orch_event.get("result", "")
                    tool_status = orch_event.get("status", "ok")
                    tool_align = orch_event.get("alignment")
                    tool_ms = orch_event.get("latency_ms")
                    tool_reasoning = orch_event.get("reasoning", "")
                    if tool_reasoning:
                        yield runtime.emit(
                            {
                                "type": "agent_thinking_token",
                                "content": tool_reasoning[:200],
                                "metadata": {"step": "tool_loop", "alignment": tool_align},
                            }
                        )
                    yield runtime.emit(
                        {
                            "type": "tool_start",
                            "content": f"Running {tool_name}...",
                            "metadata": {
                                "tool_name": tool_name,
                                "input": tool_args,
                                "alignment": tool_align,
                                "reasoning": tool_reasoning,
                            },
                        }
                    )
                    yield runtime.emit(
                        {
                            "type": "tool_result",
                            "content": tool_result[:500],
                            "metadata": {
                                "tool_name": tool_name,
                                "status": tool_status,
                                "step_index": len(orch_steps),
                                "duration_ms": tool_ms,
                                "alignment": tool_align,
                            },
                        }
                    )
                    orch_steps.append({"tool": tool_name, "args": tool_args, "status": tool_status})
                    runtime.update_governed_task(
                        steps_done=list(accumulated_steps + orch_steps),
                        orch_answer_so_far=accumulated_answer + orch_answer,
                    )
                    runtime.append_governed_event(
                        "tool_result",
                        tool_result[:500],
                        {
                            "tool_name": tool_name,
                            "status": tool_status,
                            "step_index": len(accumulated_steps) + len(orch_steps) - 1,
                            "duration_ms": tool_ms,
                        },
                    )
                elif etype == "spawn_thinking":
                    yield runtime.emit(
                        {
                            "type": "agent_thinking_token",
                            "content": orch_event.get("content", ""),
                            "metadata": {
                                "step": "spawn_agent",
                                "subagent_task": orch_event.get("subagent_task", ""),
                            },
                        }
                    )
                elif etype == "spawn_tool":
                    st_name = orch_event.get("tool", "")
                    st_status = orch_event.get("status", "ok")
                    st_ms = orch_event.get("latency_ms")
                    yield runtime.emit(
                        {
                            "type": "tool_start",
                            "content": f"[subagent] {st_name}",
                            "metadata": {
                                "tool_name": st_name,
                                "input": orch_event.get("args", {}),
                                "is_subagent": True,
                                "subagent_task": orch_event.get("subagent_task", ""),
                            },
                        }
                    )
                    yield runtime.emit(
                        {
                            "type": "tool_result",
                            "content": orch_event.get("result", "")[:300],
                            "metadata": {
                                "tool_name": st_name,
                                "status": st_status,
                                "step_index": len(orch_steps),
                                "duration_ms": st_ms,
                                "is_subagent": True,
                            },
                        }
                    )
                    orch_steps.append(
                        {
                            "tool": f"[subagent] {st_name}",
                            "args": orch_event.get("args", {}),
                            "status": st_status,
                        }
                    )
                    runtime.update_governed_task(
                        status=GovernedTaskStatus.AWAITING_SUBTASK.value,
                        wait_kind=GovernedTaskWaitKind.SUBAGENT.value,
                        steps_done=list(accumulated_steps + orch_steps),
                        orch_answer_so_far=accumulated_answer + orch_answer,
                    )
                    runtime.append_governed_event(
                        "tool_result",
                        orch_event.get("result", "")[:300],
                        {"tool_name": st_name, "status": st_status, "is_subagent": True},
                    )
                elif etype == "spawn_complete":
                    spawn_success = orch_event.get("success", False)
                    spawn_ms = orch_event.get("elapsed_ms", 0)
                    runtime.update_governed_task(
                        status=GovernedTaskStatus.RUNNING.value,
                        wait_kind=None,
                        steps_done=list(accumulated_steps + orch_steps),
                        orch_answer_so_far=accumulated_answer + orch_answer,
                    )
                    runtime.safe_print(
                        f"[ORCHESTRATOR] Subagent complete: success={spawn_success}, {spawn_ms:.0f}ms"
                    )
                    yield runtime.emit(
                        {
                            "type": "status",
                            "content": f"Subagent {'done' if spawn_success else 'failed'} ({spawn_ms:.0f}ms)",
                            "metadata": {"is_subagent": True},
                        }
                    )
                elif etype == "agent_checkpoint":
                    checkpoint_content = orch_event.get("content", "")
                    orch_meta = orch_event.get("metadata", {})
                    checkpoint_tier = orch_meta.get("checkpoint_tier", "plan")
                    runtime.append_governed_event("agent_checkpoint", checkpoint_content, orch_meta)
                    if checkpoint_content:
                        yield runtime.emit({"type": "token", "content": checkpoint_content})
                    yield runtime.emit(orch_event)
                    if checkpoint_tier == "file_write":
                        diff_suspended = {
                            "type": "diff_write",
                            "objective": current_msg,
                            "steps_done": list(accumulated_steps + orch_steps),
                            "orch_answer_so_far": accumulated_answer + orch_answer,
                            "remaining_iterations": getattr(orch, "max_iterations", 10) - len(orch_steps),
                            "diff_data": {
                                "path": orch_meta.get("diff_preview", ""),
                                "target_path": orch_meta.get("target_path", ""),
                                "diff_preview": orch_meta.get("diff_preview", ""),
                                "_raw_meta": orch_meta,
                            },
                        }
                        session_db.store_suspended_loop(req.thread_id, diff_suspended)
                        runtime.update_governed_task(
                            status=GovernedTaskStatus.AWAITING_USER.value,
                            wait_kind=GovernedTaskWaitKind.DIFF_WRITE.value,
                            checkpoint_tier="file_write",
                            question=checkpoint_content,
                            steps_done=list(accumulated_steps + orch_steps),
                            orch_answer_so_far=accumulated_answer + orch_answer,
                        )
                        runtime.safe_print(
                            f"[ORCHESTRATOR] Diff checkpoint suspended: {orch_meta.get('target_path')}"
                        )
                        yield runtime.emit(
                            {
                                "type": "done",
                                "content": accumulated_answer + orch_answer,
                                "metadata": {
                                    "loop_suspended": True,
                                    "loop_question": checkpoint_content,
                                    "response_type": "diff_preview",
                                    "checkpoint_tier": "file_write",
                                },
                            }
                        )
                        return StreamTerminalResult(terminal=True, handled=True, metadata={"loop_suspended": True})
                    session_db.store_pending_checkpoint(
                        thread_id=req.thread_id,
                        intent_data={
                            "route": "task",
                            "intent_type": "plan_create",
                            "slots": {},
                            "confidence": 0.95,
                            "reason": "plan_proposal",
                            "source": "orchestrator",
                            "_plan_proposal": True,
                            "_plan_data": orch_meta.get("plan_data", {}),
                        },
                        checkpoint_tier="plan",
                        metadata=orch_meta,
                    )
                    runtime.update_governed_task(
                        status=GovernedTaskStatus.AWAITING_CHECKPOINT.value,
                        wait_kind=GovernedTaskWaitKind.CHECKPOINT.value,
                        checkpoint_tier="plan",
                        question=checkpoint_content,
                        steps_done=list(accumulated_steps + orch_steps),
                        orch_answer_so_far=accumulated_answer + orch_answer,
                    )
                    runtime.safe_print("[ORCHESTRATOR] Checkpoint: plan proposal stored + surfaced")
                    break
                elif etype == "response":
                    orch_answer = orch_event.get("content", "")
                    runtime.update_governed_task(
                        orch_answer_so_far=accumulated_answer + orch_answer,
                        steps_done=list(accumulated_steps + orch_steps),
                    )
                    yield runtime.emit({"type": "token", "content": orch_answer})
                elif etype == "followup_suggest":
                    pending_followups = [
                        str(item).strip()
                        for item in (orch_event.get("followups", []) or [])
                        if str(item).strip()
                    ]
                    phase_complete = bool(orch_event.get("complete", True))
                    runtime.safe_print(
                        f"[ORCHESTRATOR] followup_suggest received: complete={phase_complete} "
                        f"count={len(pending_followups)} followups={pending_followups!r}"
                    )
                    if pending_followups:
                        if phase_complete:
                            runtime.update_governed_task(pending_followups=list(pending_followups))
                        else:
                            runtime.safe_print(
                                f"[ORCHESTRATOR] complete=false detected; "
                                f"evaluating auto-continuation with {len(pending_followups)} follow-up(s)"
                            )
                            runtime.update_governed_task(
                                status=GovernedTaskStatus.NEEDS_FOLLOWUP.value,
                                pending_followups=list(pending_followups),
                                steps_done=list(accumulated_steps + orch_steps),
                                orch_answer_so_far=accumulated_answer + orch_answer,
                            )
                        runtime.append_governed_event(
                            "followup_suggest",
                            "Suggested follow-ups",
                            {"followups": pending_followups, "complete": phase_complete},
                        )
                        if not phase_complete:
                            yield runtime.emit_status(
                                f"Phase incomplete; received {len(pending_followups)} follow-up option(s)"
                            )
                        yield runtime.emit(
                            {
                                "type": "followup_suggest",
                                "content": "Suggested follow-ups",
                                "metadata": {
                                    "followups": pending_followups,
                                    "complete": phase_complete,
                                },
                            }
                        )
                elif etype == "ask_user":
                    ask_question = orch_event.get("content", "")
                    yield runtime.emit({"type": "token", "content": ask_question})
                    suspended_state = {
                        "objective": current_msg,
                        "steps_done": list(accumulated_steps + orch_steps),
                        "iteration": 0,
                        "question": ask_question,
                        "orch_answer_so_far": accumulated_answer + orch_answer,
                        "remaining_iterations": getattr(orch, "max_iterations", 10) - len(orch_steps),
                    }
                    session_db.store_suspended_loop(req.thread_id, suspended_state)
                    runtime.update_governed_task(
                        status=GovernedTaskStatus.AWAITING_USER.value,
                        wait_kind=GovernedTaskWaitKind.ASK_USER.value,
                        question=ask_question,
                        steps_done=list(accumulated_steps + orch_steps),
                        orch_answer_so_far=accumulated_answer + orch_answer,
                        remaining_iterations=max(0, getattr(orch, "max_iterations", 10) - len(orch_steps)),
                    )
                    runtime.append_governed_event(
                        "ask_user",
                        ask_question,
                        {"task_status": GovernedTaskStatus.AWAITING_USER.value},
                    )
                    runtime.safe_print(f"[ORCHESTRATOR] Loop suspended - ask_user: {ask_question[:80]!r}")
                    yield runtime.emit(
                        {
                            "type": "done",
                            "content": accumulated_answer + orch_answer,
                            "metadata": {
                                "loop_suspended": True,
                                "loop_question": ask_question,
                                "response_type": "ask_user",
                                "session_id": getattr(session_db, "session_id", None),
                            },
                        }
                    )
                    return StreamTerminalResult(terminal=True, handled=True, metadata={"loop_suspended": True})
                elif etype == "done":
                    pass

            try:
                session_db.record_query(
                    thread_id=req.thread_id,
                    query_text=current_msg,
                    response_text=orch_answer,
                )
                runtime.safe_print("[ORCHESTRATOR] Stored in conversation history")
            except Exception as store_err:
                runtime.safe_print(f"[ORCHESTRATOR] Failed to store history (non-fatal): {store_err}")

            try:
                orch_db_path = getattr(orch_engine.memory, "db_path", None)
                if orch_db_path:
                    import sqlite3 as _sq3_orch
                    from pathlib import Path as _Path_orch

                    if _Path_orch(orch_db_path).exists():
                        orch_conn = _sq3_orch.connect(orch_db_path, timeout=5)
                        orch_conn.execute("PRAGMA journal_mode=WAL")
                        orch_cursor = orch_conn.cursor()
                        orch_cursor.execute(
                            "SELECT memory_id, old_trust, new_trust, reason FROM trust_log WHERE timestamp > ? ORDER BY timestamp",
                            (time.time() - 60,),
                        )
                        trust_reason_map = {
                            "cited": "cited",
                            "citation_bump": "cited",
                            "citation": "cited",
                            "corroborate": "corroborated",
                            "nli_support": "corroborated",
                            "contradiction": "contradicted",
                            "nli_contra": "contradicted",
                            "decay": "decayed",
                            "reinforced": "reinforced",
                        }
                        for row in orch_cursor.fetchall():
                            tr_raw = str(row[3] or "")
                            yield runtime.emit(
                                {
                                    "type": "trust_shift",
                                    "metadata": {
                                        "memoryId": str(row[0]),
                                        "from": round(float(row[1] or 0), 3),
                                        "to": round(float(row[2] or 0), 3),
                                        "reason": trust_reason_map.get(tr_raw.lower().strip(), tr_raw),
                                        "text": "",
                                    },
                                }
                            )
                        orch_conn.close()
            except Exception as orch_ts_err:
                runtime.safe_print(f"[ORCHESTRATOR] trust_shift emission failed (non-fatal): {orch_ts_err}")

            try:
                from personal_agent.outbox import get_outbox as _get_outbox

                outbox = _get_outbox()
                if orch_steps and len(orch_steps) >= 3:
                    ans_stripped = orch_answer.strip()
                    if ans_stripped.endswith("?") and len(ans_stripped) > 50:
                        outbox.push(
                            thread_id=req.thread_id,
                            content=ans_stripped.split("\n")[-1].strip(),
                            trigger="agent_loop_followup",
                            metadata={"steps": len(orch_steps), "source": "agent_loop"},
                        )
            except Exception as outbox_err:
                runtime.safe_print(f"[ORCHESTRATOR] Outbox push failed (non-fatal): {outbox_err}")

            try:
                from personal_agent.agent_run_log import get_run_log_db as _get_rl_db

                rl_db = _get_rl_db()
                rl_recent = rl_db.get_recent_runs(limit=1)
                if rl_recent:
                    rl_row = rl_recent[0]
                    rl_dc = int(rl_row.get("drift_count") or 0)
                    rl_conf = float(rl_row.get("confidence") or 1.0)
                    if rl_dc > 0:
                        yield runtime.emit(
                            {
                                "type": "drift",
                                "content": f"{rl_dc} drift event(s)",
                                "metadata": {
                                    "drift_count": rl_dc,
                                    "intent_alignment": round(rl_conf, 3),
                                    "total_trust_delta": 0.0,
                                },
                            }
                        )
            except Exception as rl_err:
                runtime.safe_print(f"[ORCHESTRATOR] drift event failed (non-fatal): {rl_err}")

            try:
                from personal_agent.session_state import get_or_create_session as _get_orch_sess

                orch_sess = _get_orch_sess(req.thread_id)
                yield runtime.emit(
                    {
                        "type": "session_state",
                        "content": f"density={orch_sess.cumulative_density:.4f}",
                        "metadata": {
                            "cumulative_density": round(orch_sess.cumulative_density, 4),
                            "open_contradiction_count": int(orch_sess.open_contradiction_count),
                            "total_trust_delta": round(orch_sess.total_trust_delta, 3),
                            "turn_count": int(orch_sess.turn_count),
                            "memories_confirmed": int(orch_sess.memories_confirmed),
                        },
                    }
                )
            except Exception as sess_err:
                runtime.safe_print(f"[ORCHESTRATOR] session_state event failed (non-fatal): {sess_err}")

            runtime.safe_print(
                f"[ORCHESTRATOR] Complete: {len(orch_steps)} steps, answer_len={len(orch_answer)}"
            )
            accumulated_answer += orch_answer
            accumulated_steps.extend(orch_steps)

            auto_followup = None
            if pending_followups and not phase_complete and continuation_count < _MAX_AUTO_CONTINUATIONS:
                # Drift gate: only auto-continue if the last run wasn't drifting.
                # If alignment dropped or the run had drift events, stop pulling.
                # First sign of drift = stop. Don't compound incoherence.
                _should_continue = True
                try:
                    # Check last run's drift count and alignment
                    _last_run_drift = 0
                    _last_run_alignment = 1.0
                    try:
                        _rl_conn2 = __import__("sqlite3").connect(
                            str(_rl_db_path) if '_rl_db_path' in dir() else "personal_agent/agent_run_log.db",
                            timeout=5.0,
                        )
                        _rl_row2 = _rl_conn2.execute(
                            "SELECT drift_count, confidence FROM agent_runs ORDER BY timestamp DESC LIMIT 1"
                        ).fetchone()
                        _rl_conn2.close()
                        if _rl_row2:
                            _last_run_drift = int(_rl_row2[0] or 0)
                            _last_run_alignment = float(_rl_row2[1] or 1.0)
                    except Exception:
                        pass

                    if _last_run_drift > 0:
                        _should_continue = False
                        runtime.safe_print(
                            f"[ORCHESTRATOR] Drift gate: {_last_run_drift} drift events in last run — "
                            f"suppressing auto-continuation"
                        )
                    elif _last_run_alignment < 0.4:
                        _should_continue = False
                        runtime.safe_print(
                            f"[ORCHESTRATOR] Alignment gate: {_last_run_alignment:.2f} < 0.4 — "
                            f"suppressing auto-continuation"
                        )
                except Exception as _dg_err:
                    runtime.safe_print(f"[ORCHESTRATOR] Drift gate check failed (non-fatal): {_dg_err}")

                if _should_continue:
                    auto_followup = pending_followups[0]

            if auto_followup:
                continuation_count += 1
                remaining_followups = pending_followups[1:]
                runtime.update_governed_task(
                    status=GovernedTaskStatus.RUNNING.value,
                    wait_kind=None,
                    pending_followups=list(remaining_followups),
                    steps_done=list(accumulated_steps),
                    orch_answer_so_far=accumulated_answer,
                    question=None,
                )
                runtime.append_governed_event(
                    "auto_continue",
                    auto_followup,
                    {
                        "continuation_index": continuation_count,
                        "remaining_followups": remaining_followups,
                    },
                )
                runtime.safe_print(
                    f"[ORCHESTRATOR] Auto-continuing ({continuation_count}/{_MAX_AUTO_CONTINUATIONS}) "
                    f"with: {auto_followup!r}"
                )
                yield runtime.emit_status(f"Continuing with: {auto_followup}")
                current_msg = auto_followup
                continue

            if pending_followups and not phase_complete:
                runtime.update_governed_task(
                    status=GovernedTaskStatus.NEEDS_FOLLOWUP.value,
                    pending_followups=list(pending_followups),
                    steps_done=list(accumulated_steps),
                    orch_answer_so_far=accumulated_answer,
                )
                if continuation_count >= _MAX_AUTO_CONTINUATIONS:
                    runtime.safe_print(
                        f"[ORCHESTRATOR] Auto-continuation limit reached with "
                        f"{len(pending_followups)} pending follow-up(s)"
                    )
                    yield runtime.emit_status("Auto-continuation limit reached")
                    yield runtime.emit(
                        {
                            "type": "followup_suggest",
                            "content": "Suggested follow-ups",
                            "metadata": {
                                "followups": pending_followups,
                                "complete": True,
                                "auto_continuation_limit_reached": True,
                            },
                        }
                    )
                done_meta = {
                    "tool_calls": accumulated_steps,
                    "agent_loop": True,
                    "orchestrator": True,
                    "tools_executed": len(accumulated_steps) > 0,
                    "response_type": "task",
                    "gates_passed": True,
                    "generation_source": "agent_loop",
                    "continuations": continuation_count,
                    "last_phase_complete": phase_complete,
                    "pending_followup_count": len(pending_followups),
                    "auto_continuation_limit_reached": continuation_count >= _MAX_AUTO_CONTINUATIONS,
                }
                yield runtime.emit({"type": "done", "content": accumulated_answer, "metadata": done_meta})
                return StreamTerminalResult(terminal=True, handled=True, metadata=done_meta)

            if runtime.governed_task:
                runtime.governed_task = (
                    session_db.complete_governed_task(str(runtime.governed_task["task_id"]), accumulated_answer)
                    or runtime.governed_task
                )
                runtime.append_governed_event(
                    "done",
                    accumulated_answer,
                    {
                        "task_status": GovernedTaskStatus.COMPLETED.value,
                        "generation_source": "agent_loop",
                        "continuations": continuation_count,
                    },
                )
            yield runtime.emit(
                {
                    "type": "agent_loop_complete",
                    "content": accumulated_answer,
                    "metadata": {
                        "generation_source": "agent_loop",
                        "continuations": continuation_count,
                    },
                }
            )
            # ── Fidelity Mirror (breathing loop) ──
            # Check if the orchestrator's response faithfully represents beliefs.
            _fidelity_meta = {}
            try:
                from personal_agent.fidelity_mirror import check_fidelity
                # Build memory list from belief context retrieval
                _fm_memories = []
                try:
                    _fm_results = orch_engine.memory.retrieve_memories(original_msg[:500], k=8)
                    _fm_memories = [
                        {"text": m.text[:300], "trust": m.trust, "memory_id": m.memory_id}
                        for m, _ in _fm_results
                    ]
                except Exception:
                    pass
                _fidelity = check_fidelity(
                    response=accumulated_answer,
                    query=original_msg,
                    memories=_fm_memories,
                )
                _fidelity_meta = {
                    "belief_fidelity": _fidelity.belief_fidelity,
                    "request_alignment": _fidelity.request_alignment,
                    "factual_grounding": _fidelity.factual_grounding,
                    "composite": _fidelity.composite,
                    "passed": _fidelity.passed,
                    "latency_ms": _fidelity.latency_ms,
                }
                if not _fidelity.passed:
                    runtime.safe_print(
                        f"[FIDELITY_MIRROR] FAILED composite={_fidelity.composite:.3f}"
                    )
                    # Enforcement: hedge the response with disclosure (Bug #9 fix)
                    _fm_findings = []
                    if _fidelity.belief_fidelity < 0.2:
                        _fm_findings.append("I may not be drawing on what I know about you")
                    if _fidelity.request_alignment < 0.2:
                        _fm_findings.append("I may not be directly answering your question")
                    if _fidelity.factual_grounding < 0.1:
                        _fm_findings.append("my claims aren't well-grounded in stored facts")
                    if _fm_findings:
                        _hedge = (
                            "**Heads up:** " + ", and ".join(_fm_findings) + ". "
                            "Take this with lower confidence.\n\n---\n\n"
                        )
                        accumulated_answer = _hedge + accumulated_answer
                        runtime.safe_print(
                            f"[FIDELITY_ENFORCEMENT] Hedged response ({len(_fm_findings)} findings)"
                        )
                    # Emit a fidelity warning event for the frontend
                    yield runtime.emit({
                        "type": "epistemic_event",
                        "content": f"Fidelity check failed (score={_fidelity.composite:.2f})",
                        "metadata": {"event": "fidelity_fail", **_fidelity_meta},
                    })
                else:
                    runtime.safe_print(
                        f"[FIDELITY_MIRROR] passed composite={_fidelity.composite:.3f} "
                        f"({_fidelity.latency_ms:.0f}ms)"
                    )
            except Exception as _fm_err:
                runtime.safe_print(f"[FIDELITY_MIRROR] skipped: {_fm_err}")

            done_meta = {
                "tool_calls": accumulated_steps,
                "agent_loop": True,
                "orchestrator": True,
                "tools_executed": len(accumulated_steps) > 0,
                "response_type": "task",
                "gates_passed": _fidelity_meta.get("passed", True),
                "generation_source": "agent_loop",
                "continuations": continuation_count,
                "last_phase_complete": phase_complete,
                "pending_followup_count": len(pending_followups),
                "fidelity_mirror": _fidelity_meta,
            }
            yield runtime.emit({"type": "done", "content": accumulated_answer, "metadata": done_meta})
            return StreamTerminalResult(terminal=True, handled=True, metadata=done_meta)
    except Exception as orch_err:
        if runtime.governed_task:
            runtime.governed_task = (
                session_db.fail_governed_task(str(runtime.governed_task["task_id"]), str(orch_err))
                or runtime.governed_task
            )
            runtime.append_governed_event(
                "error",
                str(orch_err),
                {"task_status": GovernedTaskStatus.FAILED.value},
            )
        runtime.safe_print(f"[ORCHESTRATOR] >>> EXCEPTION: {orch_err}")
        import traceback

        traceback.print_exc()
        logger.warning("[STREAM] Orchestrator failed, falling back to legacy path: %s", orch_err)
        return StreamTerminalResult(terminal=False, handled=False)
