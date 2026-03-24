"""Task Orchestrator — Sprint 8.

Decomposes multi-step requests into a dependency graph of SubTasks,
dispatches them to specialized SubAgents, and runs independent subtasks
in parallel via asyncio. Trust propagation follows CRT's weakest-link
model: the merged result inherits the minimum trust across all branches.

Usage from the task agent:

    orchestrator = TaskOrchestrator(build_agent_registry(llm_client))
    subtasks = orchestrator.decompose(message, triage_result)
    result = await orchestrator.execute(subtasks, ctx)
"""

from __future__ import annotations

import asyncio
import logging
import time
import uuid
from typing import Any, Dict, List, Optional

from personal_agent.sub_agents import (
    SubAgent,
    SubTask,
    SubTaskResult,
    OrchestrationContext,
    OrchestratorResult,
    build_agent_registry,
)

logger = logging.getLogger(__name__)


class TaskOrchestrator:
    """Decomposes and executes multi-step tasks with parallel sub-agents."""

    def __init__(self, agents: Optional[Dict[str, SubAgent]] = None):
        self._agents = agents or build_agent_registry()

    # ------------------------------------------------------------------
    # Decomposition
    # ------------------------------------------------------------------

    def decompose(
        self,
        message: str,
        triage_result: Any,  # TriageResult from task_agent
    ) -> List[SubTask]:
        """Break a request into subtasks with dependency edges."""
        intent = triage_result.intent

        # Single intent — one subtask
        if intent.intent_type != "multi_intent":
            return [SubTask(
                task_id="t0",
                intent_type=intent.intent_type,
                message=message,
                slots=dict(intent.slots),
            )]

        # Multi-intent — one subtask per sub-intent
        sub_intents = intent.slots.get("intents", [])
        if not sub_intents:
            return [SubTask(
                task_id="t0",
                intent_type=intent.intent_type,
                message=message,
                slots=dict(intent.slots),
            )]

        tasks = []
        for i, si in enumerate(sub_intents):
            tasks.append(SubTask(
                task_id=f"t{i}",
                intent_type=si.get("type", "conversational"),
                message=message,
                slots=dict(intent.slots),
            ))

        # Detect dependencies between subtasks
        tasks = self._detect_dependencies(tasks, message)
        return tasks

    def _detect_dependencies(self, tasks: List[SubTask], message: str) -> List[SubTask]:
        """Infer sequential dependencies from intent types and message structure.

        Rules:
        1. Sequential language markers ("then", "after that") → chain all tasks
        2. Structural: generate_content → file_write (content piped)
        3. Structural: url_fetch → llm_respond / service_action (fetched data piped)
        4. Otherwise: tasks are independent (can run in parallel)
        """
        msg_lower = message.lower()

        # Check for sequential language
        sequential_markers = [
            " then ", " after that", " and then ", " once that",
            " when done", " after you", " next ", " followed by",
        ]
        has_sequential = any(m in msg_lower for m in sequential_markers)

        if has_sequential and len(tasks) > 1:
            for i in range(1, len(tasks)):
                tasks[i].depends_on = [tasks[i - 1].task_id]

        # Structural: generate_content → file_write
        gen_task = next((t for t in tasks if t.intent_type == "generate_content"), None)
        write_task = next((t for t in tasks if t.intent_type == "file_write"), None)
        if gen_task and write_task and gen_task.task_id not in write_task.depends_on:
            write_task.depends_on.append(gen_task.task_id)
            write_task.input_from["content"] = gen_task.task_id

        # Structural: url_fetch → service_action / llm_respond
        fetch_task = next((t for t in tasks if t.intent_type == "url_fetch"), None)
        consume_task = next(
            (t for t in tasks if t.intent_type in ("llm_respond", "service_action") and t != fetch_task),
            None,
        )
        if fetch_task and consume_task and fetch_task.task_id not in consume_task.depends_on:
            consume_task.depends_on.append(fetch_task.task_id)
            consume_task.input_from["fetched_content"] = fetch_task.task_id

        return tasks

    # ------------------------------------------------------------------
    # Execution
    # ------------------------------------------------------------------

    async def execute(
        self,
        subtasks: List[SubTask],
        ctx: OrchestrationContext,
    ) -> OrchestratorResult:
        """Execute subtasks respecting dependency graph.

        Independent tasks run concurrently via asyncio.gather().
        Returns an OrchestratorResult with merged trust.
        """
        orchestration_id = str(uuid.uuid4())
        t0 = time.monotonic()

        pending = {t.task_id: t for t in subtasks}
        completed: Dict[str, SubTaskResult] = {}
        failed: Dict[str, SubTaskResult] = {}
        max_parallel = 0

        # Emit orchestration start
        await self._emit(ctx, {
            "type": "orchestration_start",
            "content": f"Orchestrating {len(subtasks)} subtask(s)",
            "metadata": {
                "orchestration_id": orchestration_id,
                "subtask_count": len(subtasks),
                "subtasks": [
                    {
                        "task_id": t.task_id,
                        "intent_type": t.intent_type,
                        "agent_name": self._agent_for(t.intent_type),
                        "depends_on": t.depends_on,
                    }
                    for t in subtasks
                ],
            },
        })

        while pending:
            # Find tasks whose dependencies are all satisfied
            ready = [
                t for t in pending.values()
                if all(dep in completed for dep in t.depends_on)
                and not any(dep in failed for dep in t.depends_on)
            ]

            # Also check for tasks blocked by failed dependencies
            blocked_by_failure = [
                t for t in pending.values()
                if any(dep in failed for dep in t.depends_on)
            ]
            for task in blocked_by_failure:
                del pending[task.task_id]
                failed[task.task_id] = SubTaskResult(
                    task_id=task.task_id,
                    agent_name="none",
                    status="error",
                    output=None,
                    output_preview=f"Blocked: dependency failed",
                    confidence=0, source_trust=0, propagated_trust=0,
                    duration_ms=0, receipt_id="",
                )

            if not ready:
                if pending:
                    # Remaining tasks have unsatisfied dependencies (deadlock or failure cascade)
                    for task in list(pending.values()):
                        failed[task.task_id] = SubTaskResult(
                            task_id=task.task_id,
                            agent_name="none",
                            status="error",
                            output=None,
                            output_preview="Deadlock: dependencies unsatisfied",
                            confidence=0, source_trust=0, propagated_trust=0,
                            duration_ms=0, receipt_id="",
                        )
                    pending.clear()
                break

            # Resolve input_from: pipe output from completed tasks into slots
            for task in ready:
                for param, source_id in task.input_from.items():
                    if source_id in completed:
                        source_result = completed[source_id]
                        task.slots[param] = source_result.output
                        # Propagate trust from dependency
                        task.slots["_source_trust"] = source_result.propagated_trust

            # Build async tasks for all ready subtasks
            agent_tasks = []
            for task in ready:
                agent = self._agents.get(task.intent_type)
                if agent is None:
                    logger.warning("[ORCHESTRATOR] No agent for intent: %s", task.intent_type)
                    del pending[task.task_id]
                    failed[task.task_id] = SubTaskResult(
                        task_id=task.task_id, agent_name="none", status="error",
                        output=None, output_preview=f"No agent for {task.intent_type}",
                        confidence=0, source_trust=0, propagated_trust=0,
                        duration_ms=0, receipt_id="",
                    )
                    continue
                agent_tasks.append((task, agent))

            max_parallel = max(max_parallel, len(agent_tasks))

            if not agent_tasks:
                continue

            # Update context with completed results
            ctx.results = completed

            # Execute concurrently
            logger.info(
                "[ORCHESTRATOR] Launching %d subtask(s) in parallel: %s",
                len(agent_tasks),
                ", ".join(f"{t.task_id}:{a.name}" for t, a in agent_tasks),
            )

            results = await asyncio.gather(*[
                agent.execute(task, ctx) for task, agent in agent_tasks
            ], return_exceptions=True)

            for (task, agent), result in zip(agent_tasks, results):
                del pending[task.task_id]
                if isinstance(result, BaseException):
                    logger.error("[ORCHESTRATOR] Agent %s raised: %s", agent.name, result)
                    failed[task.task_id] = SubTaskResult(
                        task_id=task.task_id, agent_name=agent.name,
                        status="error", output=None,
                        output_preview=str(result)[:200],
                        confidence=0, source_trust=0, propagated_trust=0,
                        duration_ms=0, receipt_id="",
                    )
                else:
                    if result.status == "ok":
                        completed[task.task_id] = result
                    else:
                        failed[task.task_id] = result

        # ── Compute merged trust (weakest link) ──────────────────────────
        all_results = list(completed.values()) + list(failed.values())
        if completed:
            merged_trust = min(r.propagated_trust for r in completed.values())
        else:
            merged_trust = 0.0

        total_duration = (time.monotonic() - t0) * 1000

        # Log orchestration receipt
        try:
            from personal_agent.action_receipts import log_orchestration_receipt
            log_orchestration_receipt(
                orchestration_id=orchestration_id,
                thread_id=ctx.thread_id,
                subtask_count=len(subtasks),
                parallel_count=max_parallel,
                total_duration_ms=total_duration,
                merged_trust=merged_trust,
                all_ok=len(failed) == 0,
            )
        except Exception as e:
            logger.warning("[ORCHESTRATOR] Failed to log orchestration receipt: %s", e)

        orch_result = OrchestratorResult(
            results=all_results,
            merged_trust=merged_trust,
            all_ok=len(failed) == 0,
            orchestration_id=orchestration_id,
            total_duration_ms=total_duration,
            parallel_count=max_parallel,
        )

        # Emit orchestration done
        await self._emit(ctx, {
            "type": "orchestration_done",
            "content": f"Orchestration {'complete' if orch_result.all_ok else 'partial failure'} — trust: {merged_trust:.2f}",
            "metadata": {
                "orchestration_id": orchestration_id,
                "merged_trust": merged_trust,
                "all_ok": orch_result.all_ok,
                "total_duration_ms": total_duration,
                "subtask_count": len(subtasks),
                "parallel_count": max_parallel,
                "completed": len(completed),
                "failed": len(failed),
            },
        })

        return orch_result

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _agent_for(self, intent_type: str) -> str:
        """Get agent name for an intent type, or 'none'."""
        agent = self._agents.get(intent_type)
        return agent.name if agent else "none"

    async def _emit(self, ctx: OrchestrationContext, event: Dict[str, Any]) -> None:
        """Push an event to the orchestration event queue."""
        if ctx.event_queue is not None:
            await ctx.event_queue.put(event)
