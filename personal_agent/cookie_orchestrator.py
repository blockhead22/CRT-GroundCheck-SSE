"""CRT Orchestrator — Brain + Hands architecture.

The brain (any LLM) reasons, plans, and decides via structured JSON.
The hands (existing CRT tool infrastructure) execute.

The brain is swappable via the BrainProvider abstraction:
  - CookieBrain: Claude Opus via browser session (free, best quality)
  - AnthropicBrain: Official Anthropic API (paid, production-grade)
  - OpenAIBrain: OpenAI API (paid, fast)
  - OllamaBrain: Local Ollama models (free, your hardware)

Usage:
    from personal_agent.cookie_orchestrator import Orchestrator, CookieBrain
    brain = CookieBrain()  # or AnthropicBrain(api_key=...), etc.
    orch = Orchestrator(brain=brain)
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
# Brain provider abstraction — swap LLMs without changing orchestrator logic
# ---------------------------------------------------------------------------

@dataclass
class BrainResult:
    """Standardized result from any brain provider."""
    content: str = ""
    error: Optional[str] = None
    latency_ms: float = 0.0
    provider: str = "unknown"


class BrainProvider:
    """Abstract base for orchestrator brain providers."""

    def complete(self, system: str, prompt: str, max_tokens: int = 800) -> BrainResult:
        raise NotImplementedError


class CookieBrain(BrainProvider):
    """Claude Opus via browser session cookie. Free, best quality."""

    def __init__(self, model: str = "claude-opus-4-5"):
        from tests.cloud_providers.providers import CookieProvider
        self._cookie = CookieProvider()
        self._model = model

    def complete(self, system: str, prompt: str, max_tokens: int = 800) -> BrainResult:
        t0 = time.perf_counter()
        result = self._cookie.complete(
            system=system, prompt=prompt,
            max_tokens=max_tokens, model=self._model,
        )
        elapsed = (time.perf_counter() - t0) * 1000
        return BrainResult(
            content=result.content or "",
            error=result.error,
            latency_ms=elapsed,
            provider=f"cookie/{self._model}",
        )


class AnthropicBrain(BrainProvider):
    """Official Anthropic Messages API. Paid, production-grade."""

    def __init__(self, api_key: Optional[str] = None,
                 model: str = "claude-sonnet-4-20250514"):
        import anthropic
        self._client = anthropic.Anthropic(
            api_key=api_key or os.environ.get("ANTHROPIC_API_KEY"),
        )
        self._model = model

    def complete(self, system: str, prompt: str, max_tokens: int = 800) -> BrainResult:
        t0 = time.perf_counter()
        try:
            response = self._client.messages.create(
                model=self._model,
                max_tokens=max_tokens,
                system=system,
                messages=[{"role": "user", "content": prompt}],
            )
            content = response.content[0].text if response.content else ""
            elapsed = (time.perf_counter() - t0) * 1000
            return BrainResult(content=content, latency_ms=elapsed,
                               provider=f"anthropic/{self._model}")
        except Exception as e:
            elapsed = (time.perf_counter() - t0) * 1000
            return BrainResult(error=str(e), latency_ms=elapsed,
                               provider=f"anthropic/{self._model}")


class OpenAIBrain(BrainProvider):
    """OpenAI API (GPT-4o, etc). Paid, fast."""

    def __init__(self, api_key: Optional[str] = None,
                 model: str = "gpt-4o"):
        from openai import OpenAI
        self._client = OpenAI(
            api_key=api_key or os.environ.get("OPENAI_API_KEY"),
        )
        self._model = model

    def complete(self, system: str, prompt: str, max_tokens: int = 800) -> BrainResult:
        t0 = time.perf_counter()
        try:
            response = self._client.chat.completions.create(
                model=self._model,
                max_tokens=max_tokens,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": prompt},
                ],
            )
            content = response.choices[0].message.content or ""
            elapsed = (time.perf_counter() - t0) * 1000
            return BrainResult(content=content, latency_ms=elapsed,
                               provider=f"openai/{self._model}")
        except Exception as e:
            elapsed = (time.perf_counter() - t0) * 1000
            return BrainResult(error=str(e), latency_ms=elapsed,
                               provider=f"openai/{self._model}")


class OllamaBrain(BrainProvider):
    """Local Ollama model. Free, your hardware."""

    def __init__(self, model: str = "llama3.2",
                 base_url: Optional[str] = None):
        self._model = model
        self._base_url = base_url or os.environ.get(
            "OLLAMA_BASE_URL", "http://localhost:11434")

    def complete(self, system: str, prompt: str, max_tokens: int = 800) -> BrainResult:
        import requests
        t0 = time.perf_counter()
        try:
            response = requests.post(
                f"{self._base_url}/api/chat",
                json={
                    "model": self._model,
                    "messages": [
                        {"role": "system", "content": system},
                        {"role": "user", "content": prompt},
                    ],
                    "stream": False,
                    "options": {"num_predict": max_tokens},
                },
                timeout=60,
            )
            data = response.json()
            content = data.get("message", {}).get("content", "")
            elapsed = (time.perf_counter() - t0) * 1000
            return BrainResult(content=content, latency_ms=elapsed,
                               provider=f"ollama/{self._model}")
        except Exception as e:
            elapsed = (time.perf_counter() - t0) * 1000
            return BrainResult(error=str(e), latency_ms=elapsed,
                               provider=f"ollama/{self._model}")


def get_brain(provider: str = "cookie", **kwargs) -> BrainProvider:
    """Factory function to get a brain provider by name.

    Args:
        provider: "cookie", "anthropic", "openai", "ollama"
        **kwargs: passed to the provider constructor

    Returns:
        BrainProvider instance
    """
    providers = {
        "cookie": CookieBrain,
        "anthropic": AnthropicBrain,
        "openai": OpenAIBrain,
        "ollama": OllamaBrain,
    }
    cls = providers.get(provider)
    if cls is None:
        raise ValueError(f"Unknown brain provider: {provider}. Available: {list(providers.keys())}")
    return cls(**kwargs)


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

PROJECT_ROOT = "D:/AI_round2"
SANDBOX_DIR = os.path.join(PROJECT_ROOT, "workspace")
os.makedirs(SANDBOX_DIR, exist_ok=True)

# Dangerous shell patterns to block
_BLOCKED_COMMANDS = ["rm -rf", "del /s", "format ", "rmdir /s", "rd /s",
                     "shutdown", "reboot", "> /dev/", "mkfs", "dd if="]


def _is_inside_sandbox(path: str) -> bool:
    """Check if a path resolves inside the sandbox directory."""
    resolved = os.path.realpath(os.path.abspath(path))
    sandbox_resolved = os.path.realpath(os.path.abspath(SANDBOX_DIR))
    return resolved.startswith(sandbox_resolved)


def _is_inside_project(path: str) -> bool:
    """Check if a path resolves inside the project root (for reads)."""
    resolved = os.path.realpath(os.path.abspath(path))
    root_resolved = os.path.realpath(os.path.abspath(PROJECT_ROOT))
    return resolved.startswith(root_resolved)


def execute_tool(tool_name: str, args: Dict[str, Any],
                 memory_system=None) -> Dict[str, Any]:
    """Execute a tool and return the result.

    SANDBOX RULES:
    - file_read, dir_list, search_code: allowed anywhere inside PROJECT_ROOT
    - file_write: ONLY inside SANDBOX_DIR (workspace/)
    - shell_exec: cwd set to SANDBOX_DIR, dangerous commands blocked
    - memory_recall, web_search: no filesystem access, always safe

    Returns {"content": str, "status": "ok"|"error"}.
    """
    t0 = time.perf_counter()
    result = {"content": "", "status": "ok"}

    try:
        if tool_name == "file_read":
            path = args.get("path", "")
            if not os.path.isabs(path):
                path = os.path.join(PROJECT_ROOT, path)
            if not _is_inside_project(path):
                result["content"] = f"[SANDBOX] BLOCKED: file_read outside project root: {path}"
                result["status"] = "error"
                print(f"  [SANDBOX] BLOCKED file_read: {path}")
            else:
                with open(path, "r", encoding="utf-8", errors="replace") as f:
                    content = f.read()
                if len(content) > 30000:
                    content = content[:30000] + f"\n\n... [truncated, {len(content)} total chars]"
                result["content"] = content

        elif tool_name == "file_write":
            path = args.get("path", "")
            content = args.get("content", "")
            if not os.path.isabs(path):
                path = os.path.join(PROJECT_ROOT, path)
            if not _is_inside_sandbox(path):
                result["content"] = (f"[SANDBOX] BLOCKED: file_write only allowed inside {SANDBOX_DIR}. "
                                     f"Attempted: {path}")
                result["status"] = "error"
                print(f"  [SANDBOX] BLOCKED file_write: {path}")
            else:
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
            cmd_lower = command.lower()
            # Block dangerous commands
            blocked_hit = False
            for blocked in _BLOCKED_COMMANDS:
                if blocked in cmd_lower:
                    result["content"] = f"[SANDBOX] BLOCKED dangerous command: {command}"
                    result["status"] = "error"
                    print(f"  [SANDBOX] BLOCKED shell_exec: {command}")
                    blocked_hit = True
                    break
            if not blocked_hit:
                import subprocess
                # Read-only commands run from project root; write commands from sandbox
                _read_only_prefixes = ("cat ", "head ", "tail ", "wc ", "grep ", "rg ",
                                       "find ", "ls ", "dir ", "type ", "findstr ",
                                       "sed -n", "awk ", "python -c")
                _is_read_only = any(cmd_lower.strip().startswith(p) for p in _read_only_prefixes)
                _cwd = PROJECT_ROOT if _is_read_only else SANDBOX_DIR
                proc = subprocess.run(
                    command, shell=True, capture_output=True, text=True,
                    timeout=30, cwd=_cwd,
                )
                output = proc.stdout[:5000]
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

class Orchestrator:
    """Brain-agnostic orchestrator with tool execution.

    The brain (any BrainProvider) makes decisions.
    The hands (tool executor) carry them out.
    Swap brains without changing any logic.
    """

    def __init__(self, brain: Optional[BrainProvider] = None,
                 memory_system=None, max_iterations: int = 8):
        self.brain = brain or CookieBrain()
        self.memory_system = memory_system
        self.max_iterations = max_iterations

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

        # Time pressure hint near end of iterations
        remaining = getattr(state, '_remaining_iterations', None)
        if remaining is not None and remaining <= 2:
            parts.append(f"\nWARNING: Only {remaining} iteration(s) remaining. You MUST respond now with action=respond. Summarize what you know.")
        else:
            parts.append("\nWhat is your next action? Return ONLY a JSON object.")
        return "\n".join(parts)

    def _parse_decision(self, raw: str) -> Dict[str, Any]:
        """Parse Cookie's JSON decision, handling common formatting issues."""
        text = raw.strip()

        # Strip markdown code fences ONLY if they wrap the entire response
        # (not if backticks appear inside JSON string values like markdown code blocks)
        if text.startswith("```"):
            import re
            match = re.search(r'^```(?:json)?\s*\n(.*)\n```\s*$', text, re.DOTALL)
            if match:
                text = match.group(1).strip()

        # Fix literal control characters in JSON
        # Cookie sometimes returns actual newlines/tabs instead of escape sequences
        # Replace them with proper JSON escapes using explicit char codes
        text_fixed = text.replace(chr(13), chr(92) + chr(110))  # \r -> \n
        text_fixed = text_fixed.replace(chr(10), chr(92) + chr(110))  # actual newline -> \n
        text_fixed = text_fixed.replace(chr(9), chr(92) + chr(116))  # tab -> \t

        # Try direct parse first
        try:
            return json.loads(text_fixed)
        except json.JSONDecodeError as _jde:
            print(f"  [PARSE_DEBUG] Direct parse failed: {_jde}")
            print(f"  [PARSE_DEBUG] text_fixed has newline: {chr(10) in text_fixed}, len={len(text_fixed)}")
            print(f"  [PARSE_DEBUG] text_fixed[:80] hex: {text_fixed[:80].encode('utf-8').hex()}")
            pass

        # Try extracting JSON by finding first { and trying every } from the end
        start = text_fixed.find("{")
        if start >= 0:
            for end in range(len(text_fixed) - 1, start, -1):
                if text_fixed[end] == "}":
                    try:
                        result = json.loads(text_fixed[start:end + 1])
                        if isinstance(result, dict) and "action" in result:
                            return result
                    except json.JSONDecodeError:
                        continue

        # Fallback: treat as a direct response
        # Debug: show hex of first failing area
        _fail_start = text_fixed.find("{")
        if _fail_start >= 0:
            _sample = text_fixed[_fail_start:_fail_start+200]
            print(f"  [PARSE] Failed. text_fixed hex sample: {_sample.encode('utf-8').hex()[:200]}")
        print(f"  [PARSE] Failed to extract JSON ({len(raw)} chars), first 100: {repr(raw[:100])}")
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

        # Initialize run log (Layer 1: observation, Layer 2: alignment scoring)
        from personal_agent.agent_run_log import RunLog, RunStep as LogStep, DriftEvent, get_run_log_db, score_alignment, detect_drift, detect_step_contradictions
        run_log = RunLog(
            intent=objective[:500],
            thread_id="",  # filled by caller if available
            brain_provider=getattr(self.brain, '_model', 'unknown'),
        )

        # Inject conversation history into context if provided
        if conversation_history:
            history_text = "\n".join(conversation_history)
            state.objective = f"{objective}\n\nCONVERSATION HISTORY:\n{history_text}"

        print(f"\n{'='*60}")
        print(f"ORCHESTRATOR: {objective[:80]}")
        print(f"{'='*60}")

        for iteration in range(self.max_iterations):
            state._remaining_iterations = self.max_iterations - iteration - 1
            print(f"\n--- Iteration {iteration + 1}/{self.max_iterations} ---")

            # Build context and call brain (with retry on empty response)
            context = self._build_context(state, last_result)
            brain_result = None
            for _retry in range(3):
                brain_result = self.brain.complete(
                    system=ORCHESTRATOR_SYSTEM,
                    prompt=context,
                    max_tokens=800,
                )
                if brain_result.content and brain_result.content.strip():
                    break
                if brain_result.error and "timeout" not in str(brain_result.error).lower():
                    break
                print(f"  [BRAIN] Empty/timeout response, retrying ({_retry + 1}/3)...")
                time.sleep(1)

            state.total_cookie_ms += brain_result.latency_ms

            raw = brain_result.content or ""
            print(f"  [BRAIN:{brain_result.provider}] ({brain_result.latency_ms:.0f}ms) {raw[:200]}")

            if brain_result.error and not raw:
                print(f"  [BRAIN ERROR] {brain_result.error}")
                yield {"type": "response", "content": f"Orchestrator error: {brain_result.error}"}
                break

            # Parse decision
            decision = self._parse_decision(raw)
            action = decision.get("action", "respond")
            reasoning = decision.get("reasoning", "")

            print(f"  [DECISION] action={action}, reasoning={reasoning[:100]}")

            # Layer 2.5: Live alignment monitoring — flag drift to user
            if action in ("tool_call", "think") and reasoning:
                _live_align = score_alignment(objective, reasoning)
                _recent_aligns = [s.intent_alignment for s in run_log.steps
                                  if s.intent_alignment is not None]

                if _live_align is not None and _recent_aligns:
                    _avg_recent = sum(_recent_aligns[-3:]) / len(_recent_aligns[-3:])
                    _dropping = _live_align < _avg_recent - 0.15
                    _low = _live_align < 0.25

                    if _dropping or _low:
                        _drift_msg = (
                            f"I may be drifting from your objective. "
                            f"Alignment: {_live_align:.2f} (was averaging {_avg_recent:.2f}). "
                            f"I was about to: {reasoning[:150]}"
                        )
                        print(f"  [DRIFT_FLAG] {_drift_msg}")
                        yield {
                            "type": "drift_warning",
                            "content": _drift_msg,
                            "alignment": _live_align,
                            "avg_alignment": _avg_recent,
                            "proposed_action": action,
                            "proposed_tool": decision.get("tool", ""),
                        }

            if action == "think":
                state.thinking.append(reasoning)
                state.add_step(StepRecord(
                    iteration=iteration, action="think",
                    reasoning=reasoning, latency_ms=brain_result.latency_ms,
                ))
                _align = score_alignment(objective, reasoning)
                run_log.add_step(LogStep(
                    iteration=iteration, action="think",
                    reasoning=reasoning[:300], latency_ms=brain_result.latency_ms,
                    intent_alignment=_align,
                ))
                if _align is not None:
                    print(f"  [ALIGNMENT] think: {_align:.3f}")
                yield {"type": "thinking", "content": reasoning}
                last_result = None

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

                # Log step: detect if this is a verification step
                _is_verify = False
                # Pattern 1: Running code to test it
                if tool == "shell_exec":
                    _cmd = str(args.get("command", "")).lower()
                    _is_verify = any(kw in _cmd for kw in [
                        "python ", "pytest", "node ", "npm test", "cargo test",
                        "go test", "ruby ", "bash ", "sh ",
                    ])
                # Pattern 2: Reading back a file we previously wrote
                if tool == "file_read":
                    _read_path = str(args.get("path", ""))
                    _prior_writes = [
                        s.tool for s in run_log.steps
                        if s.action == "tool_call" and s.tool == "file_write"
                        and str((s.args or {}).get("path", "")) == _read_path
                    ]
                    if _prior_writes:
                        _is_verify = True
                # Pattern 3: Searching code after writing (checking integration)
                if tool == "search_code" and any(
                    s.tool == "file_write" for s in run_log.steps
                    if s.action == "tool_call"
                ):
                    _is_verify = True
                # Pattern 4: dir_list after file_write (checking file exists)
                if tool == "dir_list" and any(
                    s.tool == "file_write" for s in run_log.steps
                    if s.action == "tool_call"
                ):
                    _is_verify = True
                _align = score_alignment(objective, reasoning)
                run_log.add_step(LogStep(
                    iteration=iteration, action="tool_call",
                    tool=tool, args=args, reasoning=reasoning[:300],
                    result_preview=(tool_result["content"] or "")[:500],
                    status=tool_result["status"],
                    latency_ms=tool_ms,
                    verified=_is_verify,
                    intent_alignment=_align,
                ))
                if _align is not None:
                    print(f"  [ALIGNMENT] {tool}: {_align:.3f}")

                # Layer 3: Live contradiction check against prior steps
                _current_step = run_log.steps[-1] if run_log.steps else None
                if _current_step and len(run_log.steps) >= 2:
                    _prior = run_log.steps[:-1]
                    # Check: same file written twice
                    if tool == "file_write":
                        _write_path = str(args.get("path", ""))
                        for ps in _prior:
                            if (ps.action == "tool_call" and ps.tool == "file_write"
                                    and str((ps.args or {}).get("path", "")) == _write_path):
                                _contra_msg = (f"Writing to '{_write_path}' again — "
                                               f"previously written at step {ps.iteration}")
                                print(f"  [CONTRADICTION] {_contra_msg}")
                                yield {
                                    "type": "contradiction_warning",
                                    "content": _contra_msg,
                                    "step_a": ps.iteration,
                                    "step_b": iteration,
                                }
                    # Check: same tool+args but different outcome from prior
                    if tool_result["status"] == "error":
                        for ps in _prior:
                            if (ps.action == "tool_call" and ps.tool == tool
                                    and ps.status == "ok"
                                    and str(ps.args) == str(args)):
                                _contra_msg = (f"{tool} previously succeeded with same args "
                                               f"but now failed at step {iteration}")
                                print(f"  [CONTRADICTION] {_contra_msg}")
                                yield {
                                    "type": "contradiction_warning",
                                    "content": _contra_msg,
                                    "step_a": ps.iteration,
                                    "step_b": iteration,
                                }

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

                _align = score_alignment(objective, message)
                run_log.add_step(LogStep(
                    iteration=iteration, action="respond",
                    reasoning=reasoning[:300],
                    result_preview=message[:500],
                    latency_ms=brain_result.latency_ms,
                    intent_alignment=_align,
                ))
                if _align is not None:
                    print(f"  [ALIGNMENT] response: {_align:.3f}")

                yield {"type": "response", "content": message}
                break

            elif action == "ask_user":
                question = decision.get("message", "Could you clarify?")
                yield {"type": "ask_user", "content": question}
                state.add_step(StepRecord(
                    iteration=iteration, action="ask_user",
                    reasoning=reasoning, latency_ms=brain_result.latency_ms,
                ))
                run_log.add_step(LogStep(
                    iteration=iteration, action="ask_user",
                    reasoning=reasoning[:300], latency_ms=brain_result.latency_ms,
                ))
                break

            else:
                state.final_response = raw
                state.done = True
                run_log.add_step(LogStep(
                    iteration=iteration, action="unknown",
                    reasoning=f"Unknown action: {action}",
                    latency_ms=brain_result.latency_ms,
                ))
                yield {"type": "response", "content": raw}
                break

        # Layer 2: Detect drift from alignment scores
        drifts = detect_drift(objective, run_log.steps)
        for d in drifts:
            run_log.add_drift(d)
            print(f"  [DRIFT] Step {d.at_step}: {d.description}")

        # Layer 3: Detect step-to-step contradictions
        contradictions = detect_step_contradictions(run_log.steps)
        for step_i, step_j, desc in contradictions:
            print(f"  [CONTRADICTION] Steps {step_i}↔{step_j}: {desc}")
            run_log.add_drift(DriftEvent(
                at_step=step_j,
                description=f"Contradiction: {desc}",
                from_belief=f"Step {step_i} outcome",
                to_belief=f"Step {step_j} outcome",
                had_reasoning=True,
            ))

        # Persist run log
        run_log.brain_ms = state.total_cookie_ms
        run_log.tool_ms = state.total_tool_ms
        run_log.hit_iteration_limit = not state.done
        run_log.complete(
            success=state.done and state.final_response is not None,
            confidence=0.5 if not state.done else 0.8,  # basic heuristic for now
            response_length=len(state.final_response or ""),
        )
        # Count unverified claims: tool_call steps that wrote something but never ran/verified
        _write_tools = {"file_write", "shell_exec"}
        _wrote = any(s.tool in _write_tools for s in run_log.steps if s.action == "tool_call")
        _verified = any(s.verified for s in run_log.steps)
        if _wrote and not _verified:
            run_log.unverified_claims = 1

        try:
            db = get_run_log_db()
            db.store_run(run_log)
        except Exception as _log_err:
            print(f"[RUN_LOG] Failed to store (non-fatal): {_log_err}")

        # Final summary
        print(f"\n{'='*60}")
        print(f"ORCHESTRATOR COMPLETE")
        print(f"  Steps: {len(state.steps)}")
        print(f"  Brain time: {state.total_cookie_ms:.0f}ms")
        print(f"  Tool time: {state.total_tool_ms:.0f}ms")
        print(f"  Total: {state.total_cookie_ms + state.total_tool_ms:.0f}ms")
        print(f"{'='*60}")

        yield {"type": "done", "steps": len(state.steps),
               "brain_ms": state.total_cookie_ms,
               "tool_ms": state.total_tool_ms,
               "run_id": run_log.run_id}


# Backwards-compatible alias
CookieOrchestrator = Orchestrator
