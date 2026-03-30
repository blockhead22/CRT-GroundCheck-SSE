"""Cookie-Opus Orchestrator — Brain + Hands architecture.

Cookie (Claude Opus via session) is the brain: it reasons, plans, and decides.
The existing CRT tool infrastructure is the hands: it executes.

Cookie is stateless. The orchestrator holds all state and feeds context
to Cookie each turn. Cookie returns structured JSON decisions.

Usage:
    from personal_agent.cookie_orchestrator import CookieOrchestrator
    orch = CookieOrchestrator()
    for event in orch.run("What classes are in memory_graph.py?"):
        print(event)
"""

import json
import os
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Generator, List, Optional

# Ensure project root is importable
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


# ---------------------------------------------------------------------------
# Orchestrator state
# ---------------------------------------------------------------------------

@dataclass
class StepRecord:
    """One completed step in the orchestration."""
    iteration: int
    action: str          # tool_call, think, respond, ask_user
    tool: Optional[str] = None
    args: Optional[Dict] = None
    reasoning: str = ""
    result: Optional[str] = None
    status: str = "ok"
    latency_ms: float = 0.0


@dataclass
class OrchestratorState:
    """Full state of an orchestration run."""
    objective: str = ""
    steps: List[StepRecord] = field(default_factory=list)
    thinking: List[str] = field(default_factory=list)
    final_response: Optional[str] = None
    done: bool = False
    total_cookie_ms: float = 0.0
    total_tool_ms: float = 0.0

    def add_step(self, step: StepRecord):
        self.steps.append(step)

    def completed_summary(self, max_result_len: int = 300) -> str:
        """Build a summary of completed steps for context injection."""
        if not self.steps:
            return "No steps completed yet."
        lines = []
        for i, s in enumerate(self.steps, 1):
            if s.action == "tool_call":
                result_preview = (s.result or "")[:max_result_len]
                if len(s.result or "") > max_result_len:
                    result_preview += "..."
                lines.append(f"{i}. [{s.tool}] args={json.dumps(s.args or {})} → {result_preview}")
            elif s.action == "think":
                lines.append(f"{i}. [think] {s.reasoning[:200]}")
        return "\n".join(lines) if lines else "No steps completed yet."


# ---------------------------------------------------------------------------
# Orchestrator system prompt
# ---------------------------------------------------------------------------

ORCHESTRATOR_SYSTEM = """You are a decision-making API for a tool orchestration system.
Your job is to decide what action to take next to accomplish an objective.
A separate system will execute your decisions and return results.

You communicate ONLY in JSON. Every response must be a single JSON object.

Available actions:
- {"action": "tool_call", "tool": "file_read", "args": {"path": "relative/path.py"}, "reasoning": "why"}
- {"action": "tool_call", "tool": "dir_list", "args": {"path": "."}, "reasoning": "why"}
- {"action": "tool_call", "tool": "search_code", "args": {"query": "class Foo", "path": "."}, "reasoning": "why"}
- {"action": "tool_call", "tool": "memory_recall", "args": {"query": "search terms"}, "reasoning": "why"}
- {"action": "tool_call", "tool": "web_search", "args": {"query": "search terms"}, "reasoning": "why"}
- {"action": "tool_call", "tool": "shell_exec", "args": {"command": "ls -la"}, "reasoning": "why"}
- {"action": "tool_call", "tool": "file_write", "args": {"path": "path", "content": "text"}, "reasoning": "why"}
- {"action": "think", "reasoning": "your internal reasoning before next step"}
- {"action": "respond", "message": "your final answer to the user", "reasoning": "why"}
- {"action": "ask_user", "message": "your question", "reasoning": "why"}

Rules:
1. ONLY output a JSON object. No other text. No explanation. No markdown.
2. When you need information from a file, use tool_call with file_read.
3. When you need user memories, use tool_call with memory_recall.
4. Use "think" to reason about results before your next action.
5. Use "respond" only when you have enough information for a complete answer.
6. Do not repeat the same tool call with identical arguments.
"""


# ---------------------------------------------------------------------------
# Tool executor (standalone, wraps existing infrastructure)
# ---------------------------------------------------------------------------

def execute_tool(tool_name: str, args: Dict[str, Any],
                 memory_system=None) -> Dict[str, Any]:
    """Execute a tool and return the result.

    Reuses existing tool implementations where possible.
    Returns {"content": str, "status": "ok"|"error"}.
    """
    t0 = time.perf_counter()
    result = {"content": "", "status": "ok"}

    try:
        if tool_name == "file_read":
            path = args.get("path", "")
            if not os.path.isabs(path):
                path = os.path.join("D:/AI_round2", path)
            with open(path, "r", encoding="utf-8", errors="replace") as f:
                content = f.read()
            # Truncate large files
            if len(content) > 15000:
                content = content[:15000] + f"\n\n... [truncated, {len(content)} total chars]"
            result["content"] = content

        elif tool_name == "file_write":
            path = args.get("path", "")
            content = args.get("content", "")
            if not os.path.isabs(path):
                path = os.path.join("D:/AI_round2", path)
            os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
            with open(path, "w", encoding="utf-8") as f:
                f.write(content)
            result["content"] = f"Written {len(content)} chars to {path}"

        elif tool_name == "dir_list":
            path = args.get("path", ".")
            if not os.path.isabs(path):
                path = os.path.join("D:/AI_round2", path)
            entries = os.listdir(path)
            result["content"] = "\n".join(sorted(entries))

        elif tool_name == "search_code":
            query = args.get("query", "")
            search_path = args.get("path", "D:/AI_round2")
            import subprocess
            try:
                proc = subprocess.run(
                    ["rg", "--no-heading", "-n", "-i", "--max-count", "20", query, search_path],
                    capture_output=True, text=True, timeout=10,
                )
                result["content"] = proc.stdout[:5000] if proc.stdout else "No matches found."
            except FileNotFoundError:
                # Fallback to grep
                proc = subprocess.run(
                    ["grep", "-rn", "-i", "--max-count=20", query, search_path],
                    capture_output=True, text=True, timeout=10,
                )
                result["content"] = proc.stdout[:5000] if proc.stdout else "No matches found."

        elif tool_name == "memory_recall":
            query = args.get("query", "")
            if memory_system is None:
                result["content"] = "Memory system not available."
                result["status"] = "error"
            else:
                memories = memory_system.retrieve_memories(query, k=10)
                lines = []
                for mem, score in memories:
                    lines.append(
                        f"[T:{mem.trust:.2f} score:{score:.3f}] {mem.text[:200]}"
                    )
                result["content"] = "\n".join(lines) if lines else "No memories found."

        elif tool_name == "web_search":
            query = args.get("query", "")
            try:
                from personal_agent.web_tools import duckduckgo_search
                results = duckduckgo_search(query, max_results=5)
                lines = []
                for r in results:
                    lines.append(f"[{r.get('title', '')}] {r.get('url', '')}\n  {r.get('snippet', '')[:150]}")
                result["content"] = "\n".join(lines) if lines else "No results."
            except Exception as e:
                result["content"] = f"Web search failed: {e}"
                result["status"] = "error"

        elif tool_name == "shell_exec":
            command = args.get("command", "")
            import subprocess
            proc = subprocess.run(
                command, shell=True, capture_output=True, text=True,
                timeout=30, cwd="D:/AI_round2",
            )
            output = proc.stdout[:3000]
            if proc.stderr:
                output += f"\n[stderr] {proc.stderr[:1000]}"
            result["content"] = output or "(no output)"

        else:
            result["content"] = f"Unknown tool: {tool_name}"
            result["status"] = "error"

    except Exception as e:
        result["content"] = f"Tool execution error: {e}"
        result["status"] = "error"

    elapsed = (time.perf_counter() - t0) * 1000
    print(f"  [TOOL] {tool_name}({json.dumps(args)[:80]}) → {result['status']} ({elapsed:.0f}ms)")
    return result


# ---------------------------------------------------------------------------
# The orchestrator
# ---------------------------------------------------------------------------

class CookieOrchestrator:
    """Cookie-Opus-driven orchestrator with tool execution."""

    def __init__(self, memory_system=None, max_iterations: int = 8,
                 model: str = "claude-opus-4-5"):
        from tests.cloud_providers.providers import CookieProvider
        self.cookie = CookieProvider()
        self.memory_system = memory_system
        self.max_iterations = max_iterations
        self.model = model

    def _build_context(self, state: OrchestratorState,
                       last_result: Optional[str] = None) -> str:
        """Build the context prompt for Cookie."""
        parts = [f"OBJECTIVE: {state.objective}"]

        completed = state.completed_summary()
        if completed != "No steps completed yet.":
            parts.append(f"\nCOMPLETED STEPS:\n{completed}")

        if last_result:
            preview = last_result[:2000]
            if len(last_result) > 2000:
                preview += f"\n... [{len(last_result)} total chars]"
            parts.append(f"\nLAST RESULT:\n{preview}")

        if state.thinking:
            parts.append(f"\nYOUR PREVIOUS REASONING:\n" + "\n".join(state.thinking[-3:]))

        parts.append("\nWhat is your next action? Return ONLY a JSON object.")
        return "\n".join(parts)

    def _parse_decision(self, raw: str) -> Dict[str, Any]:
        """Parse Cookie's JSON decision, handling common formatting issues."""
        text = raw.strip()

        # Strip markdown code fences
        if "```" in text:
            import re
            # Extract content between code fences
            match = re.search(r'```(?:json)?\s*\n?(.*?)\n?```', text, re.DOTALL)
            if match:
                text = match.group(1).strip()

        # Try direct parse first
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass

        # Find the first { and match to its closing }
        start = text.find("{")
        if start >= 0:
            depth = 0
            for i in range(start, len(text)):
                if text[i] == "{":
                    depth += 1
                elif text[i] == "}":
                    depth -= 1
                    if depth == 0:
                        try:
                            return json.loads(text[start:i+1])
                        except json.JSONDecodeError:
                            break

        # Fallback: treat as a direct response
        print(f"  [PARSE] Failed to extract JSON, using raw response")
        return {
            "action": "respond",
            "message": raw,
            "reasoning": "Failed to parse JSON, treating as direct response",
        }

    def run(self, objective: str,
            conversation_history: Optional[List[str]] = None
            ) -> Generator[Dict[str, Any], Optional[str], None]:
        """Run the orchestrator loop.

        Yields events:
            {"type": "thinking", "content": "..."}
            {"type": "tool_call", "tool": "...", "args": {...}, "result": "..."}
            {"type": "response", "content": "..."}
            {"type": "ask_user", "content": "..."}
            {"type": "done", "state": OrchestratorState}

        Can receive user input via .send() for ask_user responses.
        """
        state = OrchestratorState(objective=objective)
        last_result = None

        # Inject conversation history into context if provided
        if conversation_history:
            history_text = "\n".join(conversation_history)
            state.objective = f"{objective}\n\nCONVERSATION HISTORY:\n{history_text}"

        print(f"\n{'='*60}")
        print(f"ORCHESTRATOR: {objective[:80]}")
        print(f"{'='*60}")

        for iteration in range(self.max_iterations):
            print(f"\n--- Iteration {iteration + 1}/{self.max_iterations} ---")

            # Build context and call Cookie
            context = self._build_context(state, last_result)
            t0 = time.perf_counter()
            cookie_result = self.cookie.complete(
                system=ORCHESTRATOR_SYSTEM,
                prompt=context,
                max_tokens=800,
                model=self.model,
            )
            cookie_ms = (time.perf_counter() - t0) * 1000
            state.total_cookie_ms += cookie_ms

            raw = cookie_result.content or ""
            print(f"  [COOKIE] ({cookie_ms:.0f}ms) {raw[:200]}")

            if cookie_result.error:
                print(f"  [COOKIE ERROR] {cookie_result.error}")
                yield {"type": "response", "content": f"Orchestrator error: {cookie_result.error}"}
                break

            # Parse decision
            decision = self._parse_decision(raw)
            action = decision.get("action", "respond")
            reasoning = decision.get("reasoning", "")

            print(f"  [DECISION] action={action}, reasoning={reasoning[:100]}")

            if action == "think":
                state.thinking.append(reasoning)
                state.add_step(StepRecord(
                    iteration=iteration, action="think",
                    reasoning=reasoning, latency_ms=cookie_ms,
                ))
                yield {"type": "thinking", "content": reasoning}
                last_result = None  # thinking doesn't produce a result

            elif action == "tool_call":
                tool = decision.get("tool", "")
                args = decision.get("args", {})

                t1 = time.perf_counter()
                tool_result = execute_tool(tool, args, self.memory_system)
                tool_ms = (time.perf_counter() - t1) * 1000
                state.total_tool_ms += tool_ms

                step = StepRecord(
                    iteration=iteration, action="tool_call",
                    tool=tool, args=args, reasoning=reasoning,
                    result=tool_result["content"],
                    status=tool_result["status"],
                    latency_ms=tool_ms,
                )
                state.add_step(step)
                last_result = tool_result["content"]

                yield {
                    "type": "tool_call",
                    "tool": tool,
                    "args": args,
                    "result": tool_result["content"][:500],
                    "status": tool_result["status"],
                }

            elif action == "respond":
                message = decision.get("message", raw)
                state.final_response = message
                state.done = True

                yield {"type": "response", "content": message}
                break

            elif action == "ask_user":
                question = decision.get("message", "Could you clarify?")
                yield {"type": "ask_user", "content": question}
                # In a real integration, we'd wait for user input here
                # For testing, we just note it and continue
                state.add_step(StepRecord(
                    iteration=iteration, action="ask_user",
                    reasoning=reasoning, latency_ms=cookie_ms,
                ))
                break

            else:
                # Unknown action, treat as response
                state.final_response = raw
                state.done = True
                yield {"type": "response", "content": raw}
                break

        # Final summary
        print(f"\n{'='*60}")
        print(f"ORCHESTRATOR COMPLETE")
        print(f"  Steps: {len(state.steps)}")
        print(f"  Cookie time: {state.total_cookie_ms:.0f}ms")
        print(f"  Tool time: {state.total_tool_ms:.0f}ms")
        print(f"  Total: {state.total_cookie_ms + state.total_tool_ms:.0f}ms")
        print(f"{'='*60}")

        yield {"type": "done", "steps": len(state.steps),
               "cookie_ms": state.total_cookie_ms,
               "tool_ms": state.total_tool_ms}
