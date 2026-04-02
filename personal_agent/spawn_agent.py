"""spawn_agent — Phase 5 of the agentic pipeline.

A child agent loop run that executes a focused subtask and returns
its result to the parent loop. Uses the same suspend/resume primitive as
ask_user: the parent yields, child runs fully, parent resumes with result.

Architecture
------------
Parent loop hits action="spawn_agent" →
    SpawnAgent.run(task, context) →
        child Orchestrator runs to completion →
    returns SpawnResult →
parent receives result as last_result, continues.

The child has:
  - Its own max_iterations (capped at parent's remaining budget)
  - Its own tool set (can be narrowed via allowed_tools)
  - Full access to the same memory/tool infrastructure
  - Its own run log (stored separately, linked by parent_run_id)

This is NOT wired into chat.py yet. Wire-in is Phase 5 integration.
To enable: import handle_spawn_agent from this module and call it
from the orchestrator action handler in cookie_orchestrator.py.

Usage (from orchestrator, when wired):
    result = yield from handle_spawn_agent(event, brain, memory_system)
    last_result = result.summary()
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Dict, Generator, List, Optional

# ── Data types ────────────────────────────────────────────────────────────────

@dataclass
class SpawnResult:
    """Result returned to the parent loop after a child agent completes."""
    task: str
    success: bool
    answer: str                          # Final respond content from child
    steps: List[Dict[str, Any]] = field(default_factory=list)  # tool calls
    iterations: int = 0
    elapsed_ms: float = 0.0
    error: Optional[str] = None

    def summary(self) -> str:
        """Compact summary injected as last_result in the parent loop."""
        status = "completed" if self.success else "failed"
        tool_summary = ""
        if self.steps:
            names = [s.get("tool", "?") for s in self.steps]
            tool_summary = f" (used: {', '.join(names)})"
        return (
            f"[SUBAGENT {status}{tool_summary}]\n"
            f"Task: {self.task}\n"
            f"Result: {self.answer[:1000]}"
            + (f"\nError: {self.error}" if self.error else "")
        )


# ── Runner ────────────────────────────────────────────────────────────────────

def run_subagent(
    task: str,
    context: Optional[Dict[str, Any]] = None,
    brain=None,
    memory_system=None,
    max_iterations: int = 6,
    allowed_tools: Optional[List[str]] = None,
    parent_run_id: Optional[str] = None,
) -> Generator[Dict[str, Any], None, SpawnResult]:
    """Run a child agent loop for a focused subtask.

    This is a generator — yield events to the caller (pipeline panel updates),
    then return the SpawnResult when done.

    Yields:
        {"type": "spawn_thinking",  "content": "...", "subagent_task": task}
        {"type": "spawn_tool",      "tool": "...", "args": {...}, "status": "...", "subagent_task": task}
        {"type": "spawn_complete",  "result": SpawnResult, "subagent_task": task}

    Returns:
        SpawnResult (via StopIteration.value — use `yield from` or `send()`).
    """
    from personal_agent.cookie_orchestrator import Orchestrator, get_brain

    _brain = brain or get_brain("claude-cli")
    _start = time.time()
    _steps: List[Dict[str, Any]] = []
    _answer = ""

    # Build the child objective — inject context if provided
    _ctx_block = ""
    if context:
        _ctx_lines = "\n".join(f"  {k}: {v}" for k, v in context.items())
        _ctx_block = f"\n\nContext from parent:\n{_ctx_lines}"

    _child_objective = f"{task}{_ctx_block}"

    try:
        child = Orchestrator(
            brain=_brain,
            memory_system=memory_system,
            max_iterations=max_iterations,
        )

        gen = child.run(_child_objective)

        while True:
            try:
                event = next(gen)
            except StopIteration:
                break

            etype = event.get("type", "")

            if etype == "plan":
                # Surface plan as a thinking stub
                yield {
                    "type": "spawn_thinking",
                    "content": f"[subagent] {event.get('content', '')}",
                    "subagent_task": task,
                }

            elif etype in ("thinking", "think"):
                yield {
                    "type": "spawn_thinking",
                    "content": event.get("content", ""),
                    "subagent_task": task,
                }

            elif etype == "tool_call":
                tool_name = event.get("tool", "")
                # Gate on allowed_tools if provided
                if allowed_tools and tool_name not in allowed_tools:
                    print(f"  [SPAWN] Tool {tool_name!r} blocked by allowed_tools filter")
                    continue
                _steps.append({
                    "tool": tool_name,
                    "args": event.get("args", {}),
                    "status": event.get("status", "ok"),
                    "latency_ms": event.get("latency_ms"),
                })
                yield {
                    "type": "spawn_tool",
                    "tool": tool_name,
                    "args": event.get("args", {}),
                    "result": event.get("result", "")[:300],
                    "status": event.get("status", "ok"),
                    "latency_ms": event.get("latency_ms"),
                    "subagent_task": task,
                }

            elif etype == "response":
                _answer += event.get("content", "")

            elif etype == "ask_user":
                # Child asked a question we can't answer — treat as failure
                # In Phase 6 we can route this back up to the parent/user
                print(f"  [SPAWN] Child asked user mid-task (unsupported): {event.get('content', '')[:80]}")
                _answer += f"\n[Subagent paused: {event.get('content', '')}]"
                break

        elapsed = (time.time() - _start) * 1000
        result = SpawnResult(
            task=task,
            success=bool(_answer),
            answer=_answer or "(no response)",
            steps=_steps,
            iterations=len(_steps),
            elapsed_ms=elapsed,
        )

    except Exception as err:
        elapsed = (time.time() - _start) * 1000
        result = SpawnResult(
            task=task,
            success=False,
            answer="",
            steps=_steps,
            iterations=len(_steps),
            elapsed_ms=elapsed,
            error=str(err),
        )
        print(f"  [SPAWN] Child agent failed: {err}")

    yield {
        "type": "spawn_complete",
        "result": result,
        "subagent_task": task,
        "success": result.success,
        "elapsed_ms": result.elapsed_ms,
    }

    return result


# ── Handler (called from orchestrator when wired) ─────────────────────────────

def handle_spawn_agent(
    event: Dict[str, Any],
    brain=None,
    memory_system=None,
    parent_remaining_iterations: int = 8,
) -> Generator[Dict[str, Any], None, SpawnResult]:
    """Drop-in handler for action="spawn_agent" in the orchestrator.

    NOT yet wired — import and call from the orchestrator action handler.

    Wire-in (one block in the orchestrator run() loop):

        elif action == "spawn_agent":
            from personal_agent.spawn_agent import handle_spawn_agent
            _spawn_result = yield from handle_spawn_agent(
                decision, brain=self.brain,
                memory_system=self.memory_system,
                parent_remaining_iterations=self.max_iterations - iteration,
            )
            last_result = _spawn_result.summary()
            continue
    """
    task = event.get("task", event.get("message", ""))
    context = event.get("context", {})
    allowed_tools = event.get("allowed_tools")  # optional whitelist
    # Child gets at most half the parent's remaining budget, floor 3
    child_max = max(3, min(6, parent_remaining_iterations // 2))

    print(f"  [SPAWN] Spawning child agent: {task[:80]!r} (max_iter={child_max})")

    result = yield from run_subagent(
        task=task,
        context=context,
        brain=brain,
        memory_system=memory_system,
        max_iterations=child_max,
        allowed_tools=allowed_tools,
    )
    return result


# ── Standalone test ───────────────────────────────────────────────────────────

if __name__ == "__main__":
    import sys

    task = " ".join(sys.argv[1:]) or "List the files in the current directory and summarize what kind of project this is."
    print(f"Running subagent test: {task!r}\n")

    gen = run_subagent(task=task, max_iterations=4)
    result = None
    while True:
        try:
            ev = next(gen)
            etype = ev.get("type", "")
            if etype == "spawn_thinking":
                print(f"  [THINK] {ev['content'][:100]}")
            elif etype == "spawn_tool":
                print(f"  [TOOL]  {ev['tool']} → {ev['status']} ({ev.get('latency_ms', 0):.0f}ms)")
            elif etype == "spawn_complete":
                result = ev["result"]
        except StopIteration as e:
            result = e.value
            break

    if result:
        print(f"\n{'='*60}")
        print(f"Success: {result.success}")
        print(f"Steps:   {result.iterations}")
        print(f"Time:    {result.elapsed_ms:.0f}ms")
        print(f"\nAnswer:\n{result.answer}")
        print(f"\nSummary (what parent sees):\n{result.summary()}")
