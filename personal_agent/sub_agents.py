"""Sub-Agent Interface — Sprint 8.

Defines the SubAgent protocol and concrete agent implementations that wrap
existing tool functions. Each agent handles one or more intent types and
produces structured SubTaskResults with trust propagation metadata.

Agents are consumed by the TaskOrchestrator which runs independent subtasks
in parallel and chains dependent ones sequentially.
"""

from __future__ import annotations

import asyncio
import logging
import time
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, Generator, List, Literal, Optional

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class SubTask:
    """A single unit of work within an orchestration."""
    task_id: str
    intent_type: str
    message: str                           # original user message or sub-message
    slots: Dict[str, Any]                  # intent slots for this subtask
    depends_on: List[str] = field(default_factory=list)   # task_ids to wait for
    input_from: Dict[str, str] = field(default_factory=dict)  # param → source task_id


@dataclass
class SubTaskResult:
    """Structured result from a sub-agent execution."""
    task_id: str
    agent_name: str
    status: Literal["ok", "error"]
    output: Any                            # tool-specific output
    output_preview: str                    # human-readable summary (≤200 chars)
    confidence: float                      # agent's self-assessed confidence
    source_trust: float                    # trust of input data feeding this task
    propagated_trust: float                # min(confidence, source_trust)
    duration_ms: float
    receipt_id: str                        # links to action_receipts table
    steps: List[Any] = field(default_factory=list)  # AgentStep list for multi-step agents
    events: List[Dict[str, Any]] = field(default_factory=list)  # SSE events emitted during execution


@dataclass
class OrchestrationContext:
    """Shared context passed to every sub-agent during orchestration."""
    thread_id: str
    memory: Any                            # CRTMemorySystem
    llm_client: Any                        # for content generation
    session_db: Any                        # for task persistence
    results: Dict[str, SubTaskResult] = field(default_factory=dict)  # completed results
    event_queue: Optional[asyncio.Queue] = None  # for streaming events to caller


@dataclass
class OrchestratorResult:
    """Combined output from a full orchestration run."""
    results: List[SubTaskResult]
    merged_trust: float
    all_ok: bool
    orchestration_id: str
    total_duration_ms: float = 0.0
    parallel_count: int = 0                # max concurrent subtasks observed


# ---------------------------------------------------------------------------
# Trust constants per agent type
# ---------------------------------------------------------------------------

AGENT_CONFIDENCE = {
    "SystemInfoAgent": 0.95,       # ground truth from OS
    "FileAgent_read": 0.95,        # reading real files
    "FileAgent_write": 0.90,       # write succeeded but content may be generated
    "ShellAgent": 0.85,            # command ran, output interpretation varies
    "GitAgent": 0.85,              # git operations are deterministic
    "DesktopToolAgent": 0.80,      # vision model may misread screen
    "WebFetchAgent": 0.70,         # external data, may be stale
    "GenerationAgent": 0.60,       # LLM-generated, lowest trust
    "CommitmentAgent": 0.90,       # local DB write, reliable
}


def _compute_trust(agent_name: str, source_trust: float, confidence_key: Optional[str] = None) -> float:
    """Compute propagated trust = min(agent_confidence, source_trust)."""
    key = confidence_key or agent_name
    confidence = AGENT_CONFIDENCE.get(key, 0.70)
    return min(confidence, source_trust)


# ---------------------------------------------------------------------------
# SubAgent ABC
# ---------------------------------------------------------------------------

class SubAgent(ABC):
    """Abstract base class for all sub-agents."""

    name: str = "SubAgent"
    capabilities: List[str] = []

    def can_handle(self, intent_type: str) -> bool:
        return intent_type in self.capabilities

    @abstractmethod
    async def execute(self, task: SubTask, ctx: OrchestrationContext) -> SubTaskResult:
        """Execute a subtask. Called from the async orchestrator."""
        ...

    async def _emit(self, ctx: OrchestrationContext, event: Dict[str, Any]) -> None:
        """Push an SSE event to the orchestration event queue."""
        if ctx.event_queue is not None:
            await ctx.event_queue.put(event)

    def _make_receipt(
        self,
        task: SubTask,
        status: str,
        target: str,
        action: str,
        duration_ms: float,
        details: Optional[Dict[str, Any]] = None,
        orchestration_id: str = "",
    ) -> str:
        """Log an action receipt and return its ID."""
        try:
            from personal_agent.action_receipts import log_receipt, ActionReceipt
            receipt = ActionReceipt(
                receipt_id=str(uuid.uuid4()),
                timestamp=time.time(),
                tool_name=task.intent_type,
                action=action,
                target=target,
                result=status,
                reversible=False,
                details={
                    **(details or {}),
                    "agent_name": self.name,
                    "orchestration_id": orchestration_id,
                    "task_id": task.task_id,
                    "duration_ms": duration_ms,
                },
            )
            log_receipt(receipt, thread_id=task.slots.get("_thread_id", ""))
            return receipt.receipt_id
        except Exception as e:
            logger.warning("[SUB_AGENT] Receipt logging failed: %s", e)
            return ""


# ---------------------------------------------------------------------------
# Concrete Agents
# ---------------------------------------------------------------------------


class SystemInfoAgent(SubAgent):
    """Checks system status: running processes, active window, CPU/RAM/GPU."""

    name = "SystemInfoAgent"
    capabilities = ["system_info"]

    async def execute(self, task: SubTask, ctx: OrchestrationContext) -> SubTaskResult:
        await self._emit(ctx, {
            "type": "subtask_start",
            "content": f"{self.name}: checking system status",
            "metadata": {"task_id": task.task_id, "agent_name": self.name, "intent_type": task.intent_type},
        })
        t0 = time.monotonic()
        try:
            from personal_agent.system_info import get_system_snapshot, format_snapshot_text
            snapshot = await asyncio.to_thread(get_system_snapshot)
            text = await asyncio.to_thread(format_snapshot_text, snapshot)
            duration = (time.monotonic() - t0) * 1000

            source_trust = 1.0  # system data is ground truth
            propagated = _compute_trust(self.name, source_trust)
            receipt_id = self._make_receipt(task, "ok", "system", f"system snapshot ({len(text)} chars)", duration)

            result = SubTaskResult(
                task_id=task.task_id, agent_name=self.name, status="ok",
                output=snapshot, output_preview=text[:200],
                confidence=AGENT_CONFIDENCE[self.name], source_trust=source_trust,
                propagated_trust=propagated, duration_ms=duration,
                receipt_id=receipt_id,
            )
        except Exception as e:
            duration = (time.monotonic() - t0) * 1000
            result = SubTaskResult(
                task_id=task.task_id, agent_name=self.name, status="error",
                output=None, output_preview=f"system info failed: {e}",
                confidence=0, source_trust=0, propagated_trust=0,
                duration_ms=duration, receipt_id="",
            )

        await self._emit(ctx, {
            "type": "subtask_done",
            "content": f"{self.name}: {result.status}",
            "metadata": {"task_id": task.task_id, "agent_name": self.name, "status": result.status, "duration_ms": result.duration_ms},
        })
        return result


class FileAgent(SubAgent):
    """Reads/writes files, lists directories, scans projects."""

    name = "FileAgent"
    capabilities = ["file_read", "file_write", "dir_list", "project_scan"]

    async def execute(self, task: SubTask, ctx: OrchestrationContext) -> SubTaskResult:
        await self._emit(ctx, {
            "type": "subtask_start",
            "content": f"{self.name}: {task.intent_type}",
            "metadata": {"task_id": task.task_id, "agent_name": self.name, "intent_type": task.intent_type},
        })
        t0 = time.monotonic()
        try:
            if task.intent_type == "file_read":
                result = await self._file_read(task)
            elif task.intent_type == "file_write":
                result = await self._file_write(task, ctx)
            elif task.intent_type == "dir_list":
                result = await self._dir_list(task)
            elif task.intent_type == "project_scan":
                result = await self._project_scan(task)
            else:
                raise ValueError(f"Unknown file intent: {task.intent_type}")

            duration = (time.monotonic() - t0) * 1000
            is_write = task.intent_type in ("file_write",)
            confidence_key = "FileAgent_write" if is_write else "FileAgent_read"
            source_trust = task.slots.get("_source_trust", 1.0)
            propagated = _compute_trust(self.name, source_trust, confidence_key)
            path = task.slots.get("path", "?")
            receipt_id = self._make_receipt(task, "ok", path, f"{task.intent_type}: {path}", duration)

            out = SubTaskResult(
                task_id=task.task_id, agent_name=self.name, status="ok",
                output=result, output_preview=str(result)[:200],
                confidence=AGENT_CONFIDENCE.get(confidence_key, 0.90),
                source_trust=source_trust, propagated_trust=propagated,
                duration_ms=duration, receipt_id=receipt_id,
            )
        except Exception as e:
            duration = (time.monotonic() - t0) * 1000
            out = SubTaskResult(
                task_id=task.task_id, agent_name=self.name, status="error",
                output=None, output_preview=f"{task.intent_type} failed: {e}",
                confidence=0, source_trust=0, propagated_trust=0,
                duration_ms=duration, receipt_id="",
            )

        await self._emit(ctx, {
            "type": "subtask_done",
            "content": f"{self.name}: {out.status}",
            "metadata": {"task_id": task.task_id, "agent_name": self.name, "status": out.status, "duration_ms": out.duration_ms},
        })
        return out

    async def _file_read(self, task: SubTask) -> Dict[str, Any]:
        from personal_agent.file_tools import read_file
        return await asyncio.to_thread(read_file, task.slots.get("path", ""))

    async def _file_write(self, task: SubTask, ctx: OrchestrationContext) -> Dict[str, Any]:
        from personal_agent.file_tools import write_file
        path = task.slots.get("path", "")
        content = task.slots.get("content", "")
        return await asyncio.to_thread(write_file, path, content)

    async def _dir_list(self, task: SubTask) -> Dict[str, Any]:
        from personal_agent.file_tools import list_directory
        return await asyncio.to_thread(list_directory, task.slots.get("path", "D:/AI_round2"))

    async def _project_scan(self, task: SubTask) -> Dict[str, Any]:
        from personal_agent.file_tools import scan_project
        return await asyncio.to_thread(scan_project, task.slots.get("path", "D:/AI_round2"))


class ShellAgent(SubAgent):
    """Executes shell commands."""

    name = "ShellAgent"
    capabilities = ["shell_exec"]

    async def execute(self, task: SubTask, ctx: OrchestrationContext) -> SubTaskResult:
        await self._emit(ctx, {
            "type": "subtask_start",
            "content": f"{self.name}: running command",
            "metadata": {"task_id": task.task_id, "agent_name": self.name, "intent_type": task.intent_type},
        })
        t0 = time.monotonic()
        try:
            from personal_agent.shell_tools import execute_command
            command = task.slots.get("command", "")
            cwd = task.slots.get("cwd", "D:/AI_round2")
            result = await asyncio.to_thread(execute_command, command, cwd)
            duration = (time.monotonic() - t0) * 1000

            source_trust = 1.0
            propagated = _compute_trust(self.name, source_trust)
            receipt_id = self._make_receipt(task, "ok", command, f"shell: {command[:60]}", duration)

            out = SubTaskResult(
                task_id=task.task_id, agent_name=self.name, status="ok",
                output=result, output_preview=str(result)[:200],
                confidence=AGENT_CONFIDENCE[self.name], source_trust=source_trust,
                propagated_trust=propagated, duration_ms=duration,
                receipt_id=receipt_id,
            )
        except Exception as e:
            duration = (time.monotonic() - t0) * 1000
            out = SubTaskResult(
                task_id=task.task_id, agent_name=self.name, status="error",
                output=None, output_preview=f"shell failed: {e}",
                confidence=0, source_trust=0, propagated_trust=0,
                duration_ms=duration, receipt_id="",
            )

        await self._emit(ctx, {
            "type": "subtask_done",
            "content": f"{self.name}: {out.status}",
            "metadata": {"task_id": task.task_id, "agent_name": self.name, "status": out.status, "duration_ms": out.duration_ms},
        })
        return out


class GitAgent(SubAgent):
    """Executes git operations."""

    name = "GitAgent"
    capabilities = ["git_action"]

    async def execute(self, task: SubTask, ctx: OrchestrationContext) -> SubTaskResult:
        await self._emit(ctx, {
            "type": "subtask_start",
            "content": f"{self.name}: git operation",
            "metadata": {"task_id": task.task_id, "agent_name": self.name, "intent_type": task.intent_type},
        })
        t0 = time.monotonic()
        try:
            from personal_agent.shell_tools import execute_git
            args = task.slots.get("args", [])
            if isinstance(args, str):
                args = args.split()
            if not args:
                # Try to extract git subcommand from the message
                import re as _re
                _m = _re.search(r"\bgit\s+(status|diff|log|branch|show|commit|push|pull|stash)\b", task.message, _re.IGNORECASE)
                if _m:
                    args = [_m.group(1).lower()]
                elif _re.search(r"\b(uncommitted|modified|staged|changes)\b", task.message, _re.IGNORECASE):
                    args = ["status"]
                else:
                    args = ["status"]  # safe default
            cwd = task.slots.get("cwd", "D:/AI_round2")
            result = await asyncio.to_thread(execute_git, args, cwd)
            duration = (time.monotonic() - t0) * 1000

            source_trust = 1.0
            propagated = _compute_trust(self.name, source_trust)
            cmd_str = f"git {' '.join(args)}" if isinstance(args, list) else f"git {args}"
            receipt_id = self._make_receipt(task, "ok", cmd_str, f"git: {cmd_str[:60]}", duration)

            out = SubTaskResult(
                task_id=task.task_id, agent_name=self.name, status="ok",
                output=result, output_preview=str(result)[:200],
                confidence=AGENT_CONFIDENCE[self.name], source_trust=source_trust,
                propagated_trust=propagated, duration_ms=duration,
                receipt_id=receipt_id,
            )
        except Exception as e:
            duration = (time.monotonic() - t0) * 1000
            out = SubTaskResult(
                task_id=task.task_id, agent_name=self.name, status="error",
                output=None, output_preview=f"git failed: {e}",
                confidence=0, source_trust=0, propagated_trust=0,
                duration_ms=duration, receipt_id="",
            )

        await self._emit(ctx, {
            "type": "subtask_done",
            "content": f"{self.name}: {out.status}",
            "metadata": {"task_id": task.task_id, "agent_name": self.name, "status": out.status, "duration_ms": out.duration_ms},
        })
        return out


class WebFetchAgent(SubAgent):
    """Fetches URLs and interacts with web services."""

    name = "WebFetchAgent"
    capabilities = ["url_fetch", "service_action"]

    async def execute(self, task: SubTask, ctx: OrchestrationContext) -> SubTaskResult:
        await self._emit(ctx, {
            "type": "subtask_start",
            "content": f"{self.name}: fetching URL",
            "metadata": {"task_id": task.task_id, "agent_name": self.name, "intent_type": task.intent_type},
        })
        t0 = time.monotonic()
        try:
            url = task.slots.get("url", "")
            if not url:
                raise ValueError("No URL provided")

            # Use the simple HTTP GET from task_agent
            from personal_agent.task_agent import _http_get
            status_code, body, byte_count, req_duration = await asyncio.to_thread(
                _http_get, url
            )
            duration = (time.monotonic() - t0) * 1000

            ok = 200 <= status_code < 400
            source_trust = 0.70  # external data
            propagated = _compute_trust(self.name, source_trust)
            receipt_id = self._make_receipt(
                task, "ok" if ok else "error", url,
                f"fetch {url[:60]} → {status_code} ({byte_count}B)", duration,
            )

            out = SubTaskResult(
                task_id=task.task_id, agent_name=self.name,
                status="ok" if ok else "error",
                output={"status_code": status_code, "body": body, "byte_count": byte_count},
                output_preview=f"HTTP {status_code}, {byte_count} bytes",
                confidence=AGENT_CONFIDENCE[self.name], source_trust=source_trust,
                propagated_trust=propagated, duration_ms=duration,
                receipt_id=receipt_id,
            )
        except Exception as e:
            duration = (time.monotonic() - t0) * 1000
            out = SubTaskResult(
                task_id=task.task_id, agent_name=self.name, status="error",
                output=None, output_preview=f"fetch failed: {e}",
                confidence=0, source_trust=0, propagated_trust=0,
                duration_ms=duration, receipt_id="",
            )

        await self._emit(ctx, {
            "type": "subtask_done",
            "content": f"{self.name}: {out.status}",
            "metadata": {"task_id": task.task_id, "agent_name": self.name, "status": out.status, "duration_ms": out.duration_ms},
        })
        return out


class DesktopToolAgent(SubAgent):
    """Controls the desktop via screenshot-vision-action loop."""

    name = "DesktopToolAgent"
    capabilities = ["desktop_action"]

    async def execute(self, task: SubTask, ctx: OrchestrationContext) -> SubTaskResult:
        await self._emit(ctx, {
            "type": "subtask_start",
            "content": f"{self.name}: controlling desktop",
            "metadata": {"task_id": task.task_id, "agent_name": self.name, "intent_type": task.intent_type},
        })
        t0 = time.monotonic()
        try:
            # The desktop agent uses a ReAct loop internally.
            # We run the whole thing on a thread since it's long-running and sync.
            task_description = task.slots.get("task_description", task.message)
            result = await asyncio.to_thread(self._run_desktop_sync, task_description, ctx)
            duration = (time.monotonic() - t0) * 1000

            source_trust = 1.0
            propagated = _compute_trust(self.name, source_trust)
            receipt_id = self._make_receipt(
                task, "ok", task_description[:80],
                f"desktop: {task_description[:60]}", duration,
            )

            out = SubTaskResult(
                task_id=task.task_id, agent_name=self.name, status="ok",
                output=result.get("summary", ""),
                output_preview=result.get("summary", "")[:200],
                confidence=AGENT_CONFIDENCE[self.name], source_trust=source_trust,
                propagated_trust=propagated, duration_ms=duration,
                receipt_id=receipt_id,
                steps=result.get("steps", []),
            )
        except Exception as e:
            duration = (time.monotonic() - t0) * 1000
            out = SubTaskResult(
                task_id=task.task_id, agent_name=self.name, status="error",
                output=None, output_preview=f"desktop action failed: {e}",
                confidence=0, source_trust=0, propagated_trust=0,
                duration_ms=duration, receipt_id="",
            )

        await self._emit(ctx, {
            "type": "subtask_done",
            "content": f"{self.name}: {out.status}",
            "metadata": {"task_id": task.task_id, "agent_name": self.name, "status": out.status, "duration_ms": out.duration_ms},
        })
        return out

    def _run_desktop_sync(self, task_description: str, ctx: OrchestrationContext) -> Dict[str, Any]:
        """Run the DesktopAgent ReAct loop synchronously."""
        try:
            from personal_agent.desktop_agent import DesktopAgent
            from personal_agent.cloud_features import CloudFeatureService

            cloud_svc = CloudFeatureService()
            agent = DesktopAgent(cloud_service=cloud_svc, memory_agent=ctx.memory)

            steps_log = []
            def on_step(step_data):
                steps_log.append(step_data)

            success = agent.run(task_description, on_step_callback=on_step)

            return {
                "success": success,
                "summary": f"Desktop task {'completed' if success else 'failed'} in {len(steps_log)} steps",
                "steps": steps_log,
            }
        except Exception as e:
            return {"success": False, "summary": str(e), "steps": []}


class GenerationAgent(SubAgent):
    """Generates content using LLM (files, text, code)."""

    name = "GenerationAgent"
    capabilities = ["generate_content", "llm_respond"]

    def __init__(self, llm_client=None):
        self._llm = llm_client

    async def execute(self, task: SubTask, ctx: OrchestrationContext) -> SubTaskResult:
        await self._emit(ctx, {
            "type": "subtask_start",
            "content": f"{self.name}: generating content",
            "metadata": {"task_id": task.task_id, "agent_name": self.name, "intent_type": task.intent_type},
        })
        t0 = time.monotonic()
        try:
            llm = self._llm or ctx.llm_client
            if llm is None:
                raise RuntimeError("No LLM client available for content generation")

            description = task.slots.get("description", task.message)
            path = task.slots.get("path", "")

            # Use the LLM to generate content
            result = await asyncio.to_thread(
                self._generate_sync, llm, description, path
            )
            duration = (time.monotonic() - t0) * 1000

            source_trust = task.slots.get("_source_trust", 1.0)
            propagated = _compute_trust(self.name, source_trust)
            receipt_id = self._make_receipt(
                task, "ok", path or "content",
                f"generated {len(result.get('content', ''))} chars", duration,
            )

            out = SubTaskResult(
                task_id=task.task_id, agent_name=self.name, status="ok",
                output=result, output_preview=result.get("content", "")[:200],
                confidence=AGENT_CONFIDENCE[self.name],
                source_trust=source_trust, propagated_trust=propagated,
                duration_ms=duration, receipt_id=receipt_id,
            )
        except Exception as e:
            duration = (time.monotonic() - t0) * 1000
            out = SubTaskResult(
                task_id=task.task_id, agent_name=self.name, status="error",
                output=None, output_preview=f"generation failed: {e}",
                confidence=0, source_trust=0, propagated_trust=0,
                duration_ms=duration, receipt_id="",
            )

        await self._emit(ctx, {
            "type": "subtask_done",
            "content": f"{self.name}: {out.status}",
            "metadata": {"task_id": task.task_id, "agent_name": self.name, "status": out.status, "duration_ms": out.duration_ms},
        })
        return out

    def _generate_sync(self, llm, description: str, path: str) -> Dict[str, Any]:
        """Generate content using the LLM client synchronously."""
        prompt = f"Generate the content for: {description}"
        if path:
            ext = path.rsplit(".", 1)[-1] if "." in path else ""
            prompt += f"\nTarget file: {path} (format: {ext})"
        prompt += "\nReturn ONLY the file content, no explanation."

        try:
            response = llm.chat(prompt)
            content = response if isinstance(response, str) else str(response)
            return {"content": content, "path": path}
        except Exception as e:
            raise RuntimeError(f"LLM generation failed: {e}") from e


class CommitmentAgent(SubAgent):
    """Creates, lists, and cancels reminders/commitments."""

    name = "CommitmentAgent"
    capabilities = ["create_commitment", "list_commitments", "cancel_commitment"]

    async def execute(self, task: SubTask, ctx: OrchestrationContext) -> SubTaskResult:
        await self._emit(ctx, {
            "type": "subtask_start",
            "content": f"{self.name}: {task.intent_type}",
            "metadata": {"task_id": task.task_id, "agent_name": self.name, "intent_type": task.intent_type},
        })
        t0 = time.monotonic()
        try:
            from personal_agent.commitments import (
                create_commitment, list_commitments, cancel_commitment,
            )

            if task.intent_type == "create_commitment":
                result = await asyncio.to_thread(
                    create_commitment,
                    intent=task.slots.get("intent", task.message),
                    description=task.slots.get("description", ""),
                    deadline=task.slots.get("deadline"),
                    recurrence=task.slots.get("recurrence"),
                    priority=task.slots.get("priority", "medium"),
                    consequence=task.slots.get("consequence"),
                )
            elif task.intent_type == "list_commitments":
                result = await asyncio.to_thread(list_commitments)
            elif task.intent_type == "cancel_commitment":
                result = await asyncio.to_thread(
                    cancel_commitment,
                    search_term=task.slots.get("search_term", ""),
                )
            else:
                raise ValueError(f"Unknown commitment intent: {task.intent_type}")

            duration = (time.monotonic() - t0) * 1000
            source_trust = 1.0
            propagated = _compute_trust(self.name, source_trust, "CommitmentAgent")
            receipt_id = self._make_receipt(task, "ok", task.intent_type, f"commitment: {task.intent_type}", duration)

            out = SubTaskResult(
                task_id=task.task_id, agent_name=self.name, status="ok",
                output=result, output_preview=str(result)[:200],
                confidence=AGENT_CONFIDENCE.get("CommitmentAgent", 0.90),
                source_trust=source_trust, propagated_trust=propagated,
                duration_ms=duration, receipt_id=receipt_id,
            )
        except Exception as e:
            duration = (time.monotonic() - t0) * 1000
            out = SubTaskResult(
                task_id=task.task_id, agent_name=self.name, status="error",
                output=None, output_preview=f"commitment failed: {e}",
                confidence=0, source_trust=0, propagated_trust=0,
                duration_ms=duration, receipt_id="",
            )

        await self._emit(ctx, {
            "type": "subtask_done",
            "content": f"{self.name}: {out.status}",
            "metadata": {"task_id": task.task_id, "agent_name": self.name, "status": out.status, "duration_ms": out.duration_ms},
        })
        return out


# ---------------------------------------------------------------------------
# Agent registry builder
# ---------------------------------------------------------------------------

def build_agent_registry(llm_client=None) -> Dict[str, SubAgent]:
    """Build the default agent registry mapping capability names to agents."""
    agents = [
        SystemInfoAgent(),
        FileAgent(),
        ShellAgent(),
        GitAgent(),
        WebFetchAgent(),
        DesktopToolAgent(),
        GenerationAgent(llm_client=llm_client),
        CommitmentAgent(),
    ]
    registry: Dict[str, SubAgent] = {}
    for agent in agents:
        for cap in agent.capabilities:
            registry[cap] = agent
    return registry
