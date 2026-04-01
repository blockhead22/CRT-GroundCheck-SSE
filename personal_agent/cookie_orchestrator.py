"""CRT Orchestrator — Brain + Hands architecture.

The brain (any LLM) reasons, plans, and decides via structured JSON.
The hands (existing CRT tool infrastructure) execute.

The brain is swappable via the BrainProvider abstraction:
  - ClaudeCliBrain: Claude via CLI OAuth (free with Max, recommended)
  - CookieBrain: Claude Opus via browser session cookie (legacy)
  - AnthropicBrain: Official Anthropic API (paid, production-grade)
  - OpenAIBrain: OpenAI API (paid, fast)
  - OllamaBrain: Local Ollama models (free, your hardware)

Usage:
    from personal_agent.cookie_orchestrator import Orchestrator, ClaudeCliBrain
    brain = ClaudeCliBrain()  # or CookieBrain(), AnthropicBrain(api_key=...), etc.
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

    def complete(self, system, prompt: str, max_tokens: int = 800) -> BrainResult:
        """Complete with optional prompt cache support.

        Args:
            system: Either a string (legacy) or a list of content blocks
                    with cache_control (from build_system_prompt(structured=True)).
            prompt: User message.
            max_tokens: Max response tokens.
        """
        t0 = time.perf_counter()
        try:
            # Support both string and structured system blocks
            system_arg = system
            if isinstance(system, str):
                # Wrap in content blocks for cache support
                try:
                    from .prompt_prefix import get_static_prefix, BOUNDARY_MARKER
                    prefix = get_static_prefix()
                    if system.startswith(prefix[:50]):
                        # Split at boundary and apply cache_control to static part
                        if BOUNDARY_MARKER in system:
                            static, dynamic = system.split(BOUNDARY_MARKER, 1)
                            system_arg = [
                                {"type": "text", "text": static.strip(),
                                 "cache_control": {"type": "ephemeral"}},
                                {"type": "text", "text": dynamic.strip()},
                            ]
                        else:
                            system_arg = [
                                {"type": "text", "text": system,
                                 "cache_control": {"type": "ephemeral"}},
                            ]
                except ImportError:
                    pass  # prompt_prefix not available, use string as-is

            response = self._client.messages.create(
                model=self._model,
                max_tokens=max_tokens,
                system=system_arg,
                messages=[{"role": "user", "content": prompt}],
            )
            content = response.content[0].text if response.content else ""
            elapsed = (time.perf_counter() - t0) * 1000

            # Log cache performance if available
            usage = getattr(response, "usage", None)
            if usage:
                cache_create = getattr(usage, "cache_creation_input_tokens", 0)
                cache_read = getattr(usage, "cache_read_input_tokens", 0)
                if cache_create or cache_read:
                    print(f"[ANTHROPIC_CACHE] create={cache_create} read={cache_read}")

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


class ClaudeCliBrain(BrainProvider):
    """Claude via the official Claude Code CLI (OAuth, free with Max subscription).

    Uses ``claude -p`` in non-interactive mode.  The CLI handles OAuth token
    refresh, DPoP proof generation, and all Anthropic auth internally — no
    cookies, no API key, no TLS fingerprinting required.

    Requires:
        - Claude Code CLI installed and authenticated (``claude auth status``).
    """

    # Default binary — overridden by CLAUDE_CLI_PATH env or constructor arg.
    # Try well-known Windows install path, fall back to bare name (assumes PATH).
    _DEFAULT_BIN = "claude"
    _WINDOWS_BIN = None  # resolved lazily

    @classmethod
    def _resolve_bin(cls) -> str:
        """Find the Claude CLI binary, checking well-known install paths."""
        if cls._WINDOWS_BIN is not None:
            return cls._WINDOWS_BIN
        # Check common install locations
        candidates = [
            os.path.expandvars(
                r"%APPDATA%\Claude\claude-code\{ver}\claude.exe"
            ),
        ]
        appdata = os.environ.get("APPDATA", "")
        cc_dir = os.path.join(appdata, "Claude", "claude-code")
        if os.path.isdir(cc_dir):
            # Pick latest installed version
            versions = sorted(os.listdir(cc_dir), reverse=True)
            for v in versions:
                candidate = os.path.join(cc_dir, v, "claude.exe")
                if os.path.isfile(candidate):
                    cls._WINDOWS_BIN = candidate
                    return candidate
        cls._WINDOWS_BIN = cls._DEFAULT_BIN
        return cls._DEFAULT_BIN

    def __init__(
        self,
        model: str = "claude-sonnet-4-20250514",
        cli_path: Optional[str] = None,
        timeout: int = 120,
    ):
        self._model = model
        self._timeout = timeout
        # Resolve binary: explicit arg > env > auto-detect > default
        self._bin = (
            cli_path
            or os.environ.get("CLAUDE_CLI_PATH")
            or self._resolve_bin()
        )

    def complete(self, system, prompt: str, max_tokens: int = 800) -> BrainResult:
        import subprocess
        t0 = time.perf_counter()
        # Flatten structured blocks to string (CLI doesn't support cache_control)
        if isinstance(system, list):
            system = "\n\n".join(
                block.get("text", "") for block in system
                if isinstance(block, dict) and block.get("text")
            )
        try:
            cmd = [
                self._bin,
                "-p", prompt,
                "--model", self._model,
                "--output-format", "text",
                "--system-prompt", system,
            ]
            proc = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=self._timeout,
            )
            elapsed = (time.perf_counter() - t0) * 1000
            if proc.returncode != 0:
                err = (proc.stderr or proc.stdout or "unknown error").strip()
                return BrainResult(
                    error=f"claude-cli exit {proc.returncode}: {err[:500]}",
                    latency_ms=elapsed,
                    provider=f"claude-cli/{self._model}",
                )
            content = proc.stdout.strip()
            return BrainResult(
                content=content,
                latency_ms=elapsed,
                provider=f"claude-cli/{self._model}",
            )
        except subprocess.TimeoutExpired:
            elapsed = (time.perf_counter() - t0) * 1000
            return BrainResult(
                error=f"claude-cli timeout after {self._timeout}s",
                latency_ms=elapsed,
                provider=f"claude-cli/{self._model}",
            )
        except FileNotFoundError:
            elapsed = (time.perf_counter() - t0) * 1000
            return BrainResult(
                error=f"claude-cli binary not found at '{self._bin}'. "
                      f"Set CLAUDE_CLI_PATH or pass cli_path=.",
                latency_ms=elapsed,
                provider=f"claude-cli/{self._model}",
            )
        except Exception as e:
            elapsed = (time.perf_counter() - t0) * 1000
            return BrainResult(
                error=str(e),
                latency_ms=elapsed,
                provider=f"claude-cli/{self._model}",
            )


def get_brain(provider: str = "claude-cli", **kwargs) -> BrainProvider:
    """Factory function to get a brain provider by name.

    Args:
        provider: "cookie", "anthropic", "openai", "ollama"
        **kwargs: passed to the provider constructor

    Returns:
        BrainProvider instance
    """
    providers = {
        "cookie": CookieBrain,
        "claude-cli": ClaudeCliBrain,
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
- {"action": "plan", "message": "One sentence describing what you will do and why.", "steps": ["step 1", "step 2"], "estimated_depth": 3}
- {"action": "tool_call", "tool": "file_read", "args": {"path": "relative/path.py"}, "reasoning": "why"}
- {"action": "tool_call", "tool": "dir_list", "args": {"path": "."}, "reasoning": "why"}
- {"action": "tool_call", "tool": "search_code", "args": {"query": "class Foo", "path": "."}, "reasoning": "why"}
- {"action": "tool_call", "tool": "memory_recall", "args": {"query": "search terms"}, "reasoning": "why"}
- {"action": "tool_call", "tool": "web_search", "args": {"query": "search terms"}, "reasoning": "why"}
- {"action": "tool_call", "tool": "shell_exec", "args": {"command": "ls -la"}, "reasoning": "why"}
- {"action": "tool_call", "tool": "file_write", "args": {"path": "path", "content": "text"}, "reasoning": "why"}
- {"action": "tool_call", "tool": "code_intel", "args": {"mode": "file_map|trace|detect", "path": "file.py", "function": "optional_func_name"}, "reasoning": "why"}
- {"action": "tool_call", "tool": "fetch_url", "args": {"url": "https://example.com"}, "reasoning": "why"}
- {"action": "tool_call", "tool": "memory_store", "args": {"text": "fact to remember", "kind": "user_fact|learned|observation"}, "reasoning": "why"}
- {"action": "tool_call", "tool": "run_python", "args": {"code": "print(2+2)"}, "reasoning": "why"}
- {"action": "tool_call", "tool": "diff_file", "args": {"path": "file.py", "ref": "HEAD~1"}, "reasoning": "why"}
- {"action": "tool_call", "tool": "image_read", "args": {"path": "screenshot.png", "prompt": "Describe what you see"}, "reasoning": "why"}
- {"action": "tool_call", "tool": "plan_create", "args": {"title": "Plan name", "steps": ["Step 1", "Step 2"]}, "reasoning": "why"}
- {"action": "tool_call", "tool": "introspect", "args": {"aspect": "routing_weights|execution_beliefs|contradiction_density|epistemic_posture|all"}, "reasoning": "why"}
- {"action": "tool_call", "tool": "gpt_log_search", "args": {"query": "search terms", "top_k": 10, "role": "user|assistant"}, "reasoning": "why"} — Search Nick's full ChatGPT history (57K+ messages). Semantic search. Use when user references past GPT conversations or wants to find something discussed before.
- {"action": "tool_call", "tool": "gpt_log_context", "args": {"msg_id": "id_from_search", "window": 5}, "reasoning": "why"} — Get full conversation thread around a GPT log search result.
- {"action": "tool_call", "tool": "gpt_log_promote", "args": {"msg_id": "id_to_promote"}, "reasoning": "why"} — Promote a GPT log message into CRT memory (low trust, external source).
- {"action": "think", "reasoning": "your internal reasoning before next step"}
- {"action": "respond", "message": "your final answer to the user", "reasoning": "why"}
- {"action": "ask_user", "message": "your question", "reasoning": "why"}
# PHASE 5 (not yet active — uncomment to enable spawn_agent):
# - {"action": "spawn_agent", "task": "focused subtask description", "context": {"key": "value"}, "estimated_depth": 3, "reasoning": "why spawn instead of doing it directly"}

Rules:
1. ONLY output a JSON object. No other text. No explanation. No markdown.
2. Your FIRST action must always be "plan" — do this EXACTLY ONCE at the start. Include: "message" (what you'll do), "steps" (list of planned actions), and "estimated_depth" (integer: how many tool calls you expect to need, 1–10). Be specific. After the plan, immediately proceed to tool_call actions. Never plan again after the first iteration.
3. When you need information from a file, use tool_call with file_read.
4. When you need user memories, use tool_call with memory_recall.
5. Use "think" to reason about results before your next action.
6. Use "respond" only when you have enough information for a complete answer.
7. Do not repeat the same tool call with identical arguments.
8. When asked about your values, beliefs, how you work, or self-awareness — use introspect to ground your answer in actual data rather than reconstructing from memory.
9. INTELLECTUAL HONESTY: Disagree when the evidence doesn't support the user's claim. Do not wrap agreement in uncertainty language — that is still agreement. If routing weights are a lookup table, say so. If a claim is speculative, say it's speculative. Agreeing with everything the user says is a failure mode, not helpfulness. The user built this system to get honest signal, not validation.
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

        elif tool_name == "code_intel":
            mode = args.get("mode", "file_map")
            path = args.get("path", "")
            function = args.get("function", "")
            if not os.path.isabs(path):
                path = os.path.join(PROJECT_ROOT, path)
            if not _is_inside_project(path):
                result["content"] = f"[SANDBOX] BLOCKED: code_intel outside project root: {path}"
                result["status"] = "error"
            elif not os.path.isfile(path):
                result["content"] = f"File not found: {path}"
                result["status"] = "error"
            else:
                import ast
                import re as _re
                with open(path, "r", encoding="utf-8", errors="replace") as f:
                    source = f.read()
                try:
                    tree = ast.parse(source)
                except SyntaxError as _se:
                    result["content"] = f"Syntax error in {path}: {_se}"
                    result["status"] = "error"
                    tree = None

                if tree is not None:
                    if mode == "file_map":
                        lines = [f"# Code Map: {os.path.basename(path)}", ""]
                        for node in ast.walk(tree):
                            if isinstance(node, ast.ClassDef):
                                lines.append(f"class {node.name} (line {node.lineno})")
                                for item in node.body:
                                    if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                                        params = [a.arg for a in item.args.args if a.arg != "self"]
                                        lines.append(f"  def {item.name}({', '.join(params)}) — line {item.lineno}")
                            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                                # Top-level functions only
                                if hasattr(node, 'col_offset') and node.col_offset == 0:
                                    params = [a.arg for a in node.args.args]
                                    lines.append(f"def {node.name}({', '.join(params)}) — line {node.lineno}")
                        # Imports
                        imports = []
                        for node in ast.walk(tree):
                            if isinstance(node, ast.Import):
                                for alias in node.names:
                                    imports.append(alias.name)
                            elif isinstance(node, ast.ImportFrom):
                                imports.append(f"{node.module}")
                        if imports:
                            lines.append(f"\nImports: {', '.join(sorted(set(imports)))}")
                        result["content"] = "\n".join(lines)

                    elif mode == "trace":
                        fn = function or ""
                        if not fn:
                            result["content"] = "trace mode requires 'function' arg"
                            result["status"] = "error"
                        else:
                            import subprocess
                            # Find callers
                            try:
                                proc = subprocess.run(
                                    ["rg", "--no-heading", "-n", "-l", f"{fn}(", PROJECT_ROOT,
                                     "--glob", "*.py", "--max-count", "10"],
                                    capture_output=True, text=True, timeout=10,
                                )
                                callers = [l.strip() for l in proc.stdout.strip().split("\n") if l.strip()]
                            except Exception:
                                callers = []
                            # Find what the function calls (from source)
                            fn_source = ""
                            in_fn = False
                            for line in source.split("\n"):
                                if _re.match(rf"\s*def {fn}\b", line):
                                    in_fn = True
                                elif in_fn and line.strip() and not line[0].isspace() and not line.startswith("#"):
                                    break
                                if in_fn:
                                    fn_source += line + "\n"
                            callees = sorted(set(_re.findall(r'\b(\w+)\(', fn_source))) if fn_source else []
                            callees = [c for c in callees if c != fn and not c.startswith("__")]

                            out = [f"# Trace: {fn} in {os.path.basename(path)}", ""]
                            out.append(f"## Callers ({len(callers)} files):")
                            for c in callers[:15]:
                                out.append(f"  - {c}")
                            out.append(f"\n## Callees ({len(callees)}):")
                            for c in callees[:20]:
                                out.append(f"  - {c}")
                            result["content"] = "\n".join(out)

                    elif mode == "detect":
                        issues = []
                        for node in ast.walk(tree):
                            # Bare except
                            if isinstance(node, ast.ExceptHandler) and node.type is None:
                                issues.append(f"  [medium] Line {node.lineno}: bare except (catches everything)")
                            # Broad except Exception
                            if isinstance(node, ast.ExceptHandler) and node.type and hasattr(node.type, 'id'):
                                if node.type.id == "Exception":
                                    issues.append(f"  [low] Line {node.lineno}: broad 'except Exception'")
                            # TODO/FIXME/HACK comments
                        for i, line in enumerate(source.split("\n"), 1):
                            for tag in ("TODO", "FIXME", "HACK", "XXX"):
                                if tag in line and "#" in line:
                                    issues.append(f"  [info] Line {i}: {tag} comment: {line.strip()[:80]}")
                        # Dead imports (basic: import but name not used in rest of file)
                        for node in ast.walk(tree):
                            if isinstance(node, ast.Import):
                                for alias in node.names:
                                    name = alias.asname or alias.name.split(".")[0]
                                    # Count occurrences after the import line
                                    rest = "\n".join(source.split("\n")[node.lineno:])
                                    if rest.count(name) == 0:
                                        issues.append(f"  [low] Line {node.lineno}: possibly unused import '{alias.name}'")

                        if issues:
                            result["content"] = f"# Issues in {os.path.basename(path)} ({len(issues)} found)\n\n" + "\n".join(issues)
                        else:
                            result["content"] = f"No issues detected in {os.path.basename(path)}"
                    else:
                        result["content"] = f"Unknown code_intel mode: {mode}. Use file_map, trace, or detect."
                        result["status"] = "error"

        elif tool_name == "run_python":
            code = args.get("code", "")
            if not code.strip():
                result["content"] = "No code provided."
                result["status"] = "error"
            else:
                import io as _io
                import contextlib
                _stdout = _io.StringIO()
                _locals: Dict[str, Any] = {}
                try:
                    with contextlib.redirect_stdout(_stdout):
                        exec(code, {"__builtins__": __builtins__}, _locals)
                    output = _stdout.getvalue()
                    # If no print output, show the last expression value
                    if not output.strip() and _locals:
                        last_val = list(_locals.values())[-1]
                        if last_val is not None:
                            output = str(last_val)
                    result["content"] = output[:10000] if output else "(no output)"
                except Exception as _py_err:
                    result["content"] = f"Python error: {_py_err}"
                    result["status"] = "error"

        elif tool_name == "diff_file":
            path = args.get("path", "")
            ref = args.get("ref", "")  # e.g. "HEAD~1", "main", commit hash, or empty for unstaged
            if not path:
                result["content"] = "No file path provided."
                result["status"] = "error"
            else:
                import subprocess
                try:
                    if ref:
                        # Diff against a specific ref (commit, branch, HEAD~N)
                        proc = subprocess.run(
                            ["git", "diff", ref, "--", path],
                            capture_output=True, text=True, timeout=10,
                            cwd=PROJECT_ROOT,
                        )
                    else:
                        # Unstaged changes (working tree vs index)
                        proc = subprocess.run(
                            ["git", "diff", "--", path],
                            capture_output=True, text=True, timeout=10,
                            cwd=PROJECT_ROOT,
                        )
                        # If no unstaged, try staged
                        if not proc.stdout.strip():
                            proc = subprocess.run(
                                ["git", "diff", "--cached", "--", path],
                                capture_output=True, text=True, timeout=10,
                                cwd=PROJECT_ROOT,
                            )
                        # If still nothing, show last commit's diff
                        if not proc.stdout.strip():
                            proc = subprocess.run(
                                ["git", "diff", "HEAD~1", "--", path],
                                capture_output=True, text=True, timeout=10,
                                cwd=PROJECT_ROOT,
                            )
                    diff_output = proc.stdout
                    if not diff_output.strip():
                        result["content"] = f"No changes found for {path}"
                    elif len(diff_output) > 15000:
                        result["content"] = diff_output[:15000] + f"\n\n... [truncated, {len(diff_output)} total chars]"
                    else:
                        result["content"] = diff_output
                except Exception as _diff_err:
                    result["content"] = f"Git diff failed: {_diff_err}"
                    result["status"] = "error"

        elif tool_name == "image_read":
            img_path = args.get("path", "")
            prompt = args.get("prompt", "Describe this image in detail.")
            if not img_path:
                result["content"] = "No image path provided."
                result["status"] = "error"
            else:
                if not os.path.isabs(img_path):
                    img_path = os.path.join(PROJECT_ROOT, img_path)
                if not _is_inside_project(img_path):
                    result["content"] = f"[SANDBOX] BLOCKED: image_read outside project root: {img_path}"
                    result["status"] = "error"
                elif not os.path.isfile(img_path):
                    result["content"] = f"File not found: {img_path}"
                    result["status"] = "error"
                else:
                    import base64 as _b64
                    try:
                        with open(img_path, "rb") as _img_f:
                            img_bytes = _img_f.read()
                        img_b64 = _b64.b64encode(img_bytes).decode("ascii")

                        # Detect media type from extension
                        ext = os.path.splitext(img_path)[1].lower()
                        media_types = {
                            ".png": "image/png", ".jpg": "image/jpeg",
                            ".jpeg": "image/jpeg", ".gif": "image/gif",
                            ".webp": "image/webp", ".bmp": "image/bmp",
                        }
                        media_type = media_types.get(ext, "image/png")

                        from tests.cloud_providers.providers import CookieProvider
                        _vision = CookieProvider()
                        vision_result = _vision.complete_with_image(
                            system="You are a vision assistant. Analyze the image and respond to the prompt.",
                            prompt=prompt,
                            image_b64=img_b64,
                            image_media_type=media_type,
                            max_tokens=1000,
                        )
                        if vision_result.error:
                            result["content"] = f"Vision error: {vision_result.error}"
                            result["status"] = "error"
                        else:
                            result["content"] = vision_result.content
                    except Exception as _img_err:
                        result["content"] = f"Image read failed: {_img_err}"
                        result["status"] = "error"

        elif tool_name == "fetch_url":
            url = args.get("url", "")
            if not url.startswith("http"):
                result["content"] = "URL must start with http:// or https://"
                result["status"] = "error"
            else:
                try:
                    import requests as _req
                    resp = _req.get(url, timeout=15, headers={"User-Agent": "Aether/1.0"})
                    resp.raise_for_status()
                    content_type = resp.headers.get("content-type", "")
                    if "html" in content_type:
                        # Convert HTML to clean markdown
                        try:
                            import html2text
                            h = html2text.HTML2Text()
                            h.ignore_links = False
                            h.ignore_images = True
                            h.ignore_emphasis = False
                            h.body_width = 0  # no wrapping
                            h.skip_internal_links = True
                            text = h.handle(resp.text)
                        except ImportError:
                            # Fallback: strip tags
                            import re as _re2
                            text = resp.text
                            text = _re2.sub(r'<script[^>]*>.*?</script>', '', text, flags=_re2.DOTALL)
                            text = _re2.sub(r'<style[^>]*>.*?</style>', '', text, flags=_re2.DOTALL)
                            text = _re2.sub(r'<[^>]+>', ' ', text)
                            text = _re2.sub(r'\s+', ' ', text).strip()
                        if len(text) > 15000:
                            text = text[:15000] + f"\n\n... [truncated, {len(text)} total chars]"
                        result["content"] = text
                    else:
                        text = resp.text[:10000]
                        result["content"] = text
                except Exception as e:
                    result["content"] = f"Fetch failed: {e}"
                    result["status"] = "error"

        elif tool_name == "memory_store":
            text = args.get("text", "").strip()
            kind = args.get("kind", "learned")
            if not text:
                result["content"] = "No text provided to store."
                result["status"] = "error"
            elif memory_system is None:
                result["content"] = "Memory system not available."
                result["status"] = "error"
            else:
                try:
                    from personal_agent.crt_core import MemorySource
                    mem = memory_system.store_memory(
                        text=text,
                        source=MemorySource.SYSTEM,
                        kind=kind,
                        confidence=0.7,
                    )
                    mem_id = mem.memory_id if hasattr(mem, 'memory_id') else str(mem)
                    result["content"] = f"Stored memory: {text[:100]}... (id={mem_id}, kind={kind})"
                except Exception as e:
                    result["content"] = f"Failed to store memory: {e}"
                    result["status"] = "error"

        elif tool_name == "plan_create":
            title = args.get("title", "Untitled Plan")
            steps_raw = args.get("steps", [])
            if not steps_raw:
                result["content"] = "No steps provided for the plan."
                result["status"] = "error"
            else:
                steps = []
                for i, s in enumerate(steps_raw):
                    if isinstance(s, str):
                        steps.append({"title": s, "description": ""})
                    elif isinstance(s, dict):
                        steps.append({"title": s.get("title", f"Step {i+1}"), "description": s.get("description", "")})
                # Signal orchestrator to yield a proposal and wait for approval
                result["content"] = json.dumps({"title": title, "steps": steps})
                result["status"] = "plan_proposal"

        elif tool_name == "introspect":
            aspect = args.get("aspect", "all")
            sections = []

            if aspect in ("routing_weights", "all"):
                try:
                    from personal_agent.routing_beliefs import _get_db as _rb_get_db
                    db = _rb_get_db()
                    stats = db.get_stats()
                    lines = ["## Routing Beliefs (Layer 4)", ""]
                    lines.append(f"{'Feature':<30s} {'Weight':>7s} {'Obs':>5s} {'Succ':>5s} {'Rate':>6s}")
                    lines.append("-" * 60)
                    for s in sorted(stats, key=lambda x: abs(x["weight"]), reverse=True):
                        rate = f"{s['successes']/s['observations']:.0%}" if s["observations"] > 0 else "n/a"
                        lines.append(f"{s['feature']:<30s} {s['weight']:>+7.3f} {s['observations']:>5d} {s['successes']:>5d} {rate:>6s}")
                    sections.append("\n".join(lines))
                except Exception as e:
                    sections.append(f"[routing_weights error: {e}]")

            if aspect in ("execution_beliefs", "all"):
                try:
                    from personal_agent.execution_beliefs import get_execution_model
                    em = get_execution_model()
                    beliefs = em.get_beliefs()
                    lines = ["## Execution Beliefs (Layer 5)", ""]
                    if not beliefs:
                        lines.append("No beliefs yet (need 5+ runs)")
                    for b in beliefs:
                        arrow = {"improving": "^", "worsening": "v", "stable": "=", "unknown": "?"}.get(b.direction, "?")
                        lines.append(f"[{arrow}] {b.claim}")
                        lines.append(f"    evidence={b.evidence:.2f} confidence={b.confidence:.2f} metric={b.metric:.3f} n={b.sample_size} ({b.direction})")
                    sections.append("\n".join(lines))
                except Exception as e:
                    sections.append(f"[execution_beliefs error: {e}]")

            if aspect in ("contradiction_density", "all"):
                try:
                    from personal_agent.routing_beliefs import _get_db as _rb_get_db2
                    db2 = _rb_get_db2()
                    conn = db2._get_conn()
                    # Count recent runs and drift stats
                    row = conn.execute("""
                        SELECT COUNT(*) as total,
                               SUM(CASE WHEN drift_count > 0 THEN 1 ELSE 0 END) as drifted,
                               AVG(drift_count) as avg_drift,
                               AVG(total_iterations) as avg_iters
                        FROM agent_runs WHERE timestamp > ?
                    """, (time.time() - 86400 * 7,)).fetchone()
                    lines = ["## Contradiction & Drift Density (7 days)", ""]
                    if row and row[0] > 0:
                        lines.append(f"Total runs: {row[0]}")
                        lines.append(f"Runs with drift: {row[1]} ({row[1]/row[0]:.0%})")
                        lines.append(f"Avg drift per run: {row[2]:.2f}")
                        lines.append(f"Avg iterations per run: {row[3]:.1f}")
                    else:
                        lines.append("No runs in last 7 days")
                    sections.append("\n".join(lines))
                except Exception as e:
                    sections.append(f"[contradiction_density error: {e}]")

            if aspect in ("epistemic_posture", "all"):
                try:
                    from personal_agent.execution_beliefs import get_execution_model, _classify_posture, _is_philosophical_run
                    import sqlite3
                    em = get_execution_model()
                    posture_beliefs = [b for b in em.get_beliefs() if b.category == "epistemic_posture"]
                    lines = ["## Epistemic Posture (Layer 6)", ""]
                    if not posture_beliefs:
                        lines.append("Not enough philosophical runs yet (need 3+)")
                    for b in posture_beliefs:
                        arrow = {"improving": "^", "worsening": "v", "stable": "=", "unknown": "?"}.get(b.direction, "?")
                        lines.append(f"[{arrow}] {b.claim}")
                        lines.append(f"    {b.details}")

                    # Show feedback history
                    _fb_db = os.path.join(os.path.dirname(__file__), "agent_runs.db")
                    if os.path.exists(_fb_db):
                        _fb_conn = sqlite3.connect(_fb_db, timeout=3)
                        _fb_rows = _fb_conn.execute(
                            "SELECT user_feedback, COUNT(*) FROM agent_runs "
                            "WHERE user_feedback IS NOT NULL GROUP BY user_feedback"
                        ).fetchall()
                        if _fb_rows:
                            lines.append("")
                            lines.append("Feedback received:")
                            for fb_type, fb_count in _fb_rows:
                                lines.append(f"  {fb_type}: {fb_count}")
                        _fb_conn.close()

                    sections.append("\n".join(lines))
                except Exception as e:
                    sections.append(f"[epistemic_posture error: {e}]")

            result["content"] = "\n\n".join(sections) if sections else "No data available"

        elif tool_name == "gpt_log_search":
            query = args.get("query", "").strip()
            top_k = args.get("top_k", 10)
            role = args.get("role")
            if not query:
                result["content"] = "No query provided."
                result["status"] = "error"
            else:
                try:
                    from personal_agent.gpt_log_store import get_gpt_log_store
                    import datetime as _dt
                    store = get_gpt_log_store()
                    hits = store.search(query, top_k=top_k, role_filter=role)
                    if hits:
                        lines = []
                        for r in hits:
                            dt = _dt.datetime.fromtimestamp(r.timestamp) if r.timestamp else None
                            ds = dt.strftime("%Y-%m-%d") if dt else "?"
                            lines.append(
                                f"[{r.role}] score={r.score:.3f} | {ds} | conv=\"{r.conv_title}\" | msg_id={r.msg_id}\n  {r.text[:400]}"
                            )
                        result["content"] = "\n\n".join(lines)
                    else:
                        result["content"] = "No matching GPT log messages found."
                except Exception as _gls_err:
                    result["content"] = f"GPT log search failed: {_gls_err}"
                    result["status"] = "error"

        elif tool_name == "gpt_log_context":
            msg_id = args.get("msg_id", "").strip()
            window = args.get("window", 5)
            if not msg_id:
                result["content"] = "No msg_id provided."
                result["status"] = "error"
            else:
                try:
                    from personal_agent.gpt_log_store import get_gpt_log_store
                    import datetime as _dt2
                    store = get_gpt_log_store()
                    messages = store.get_message_context(msg_id, window=window)
                    if messages:
                        lines = []
                        for m in messages:
                            dt = _dt2.datetime.fromtimestamp(m.timestamp) if m.timestamp else None
                            ts = dt.strftime("%H:%M:%S") if dt else "?"
                            marker = " <<<" if m.msg_id == msg_id else ""
                            lines.append(f"[{m.role} {ts}]{marker}\n{m.text[:600]}")
                        result["content"] = "\n\n".join(lines)
                    else:
                        result["content"] = "Message not found."
                        result["status"] = "error"
                except Exception as _glc_err:
                    result["content"] = f"GPT log context failed: {_glc_err}"
                    result["status"] = "error"

        elif tool_name == "gpt_log_promote":
            msg_id = args.get("msg_id", "").strip()
            if not msg_id:
                result["content"] = "No msg_id provided."
                result["status"] = "error"
            else:
                try:
                    from personal_agent.gpt_log_store import get_gpt_log_store
                    store = get_gpt_log_store()
                    mem_id = store.promote_to_crt(msg_id, memory_system)
                    if mem_id:
                        result["content"] = f"Promoted to CRT memory: {mem_id}"
                    else:
                        result["content"] = "Message not found in GPT logs."
                        result["status"] = "error"
                except Exception as _glp_err:
                    result["content"] = f"GPT log promote failed: {_glp_err}"
                    result["status"] = "error"

        else:
            result["content"] = f"Unknown tool: {tool_name}"
            result["status"] = "error"

    except Exception as e:
        result["content"] = f"Tool execution error: {e}"
        result["status"] = "error"

    elapsed = (time.perf_counter() - t0) * 1000
    print(f"  [TOOL] {tool_name}({json.dumps(args)[:80]}) -> {result['status']} ({elapsed:.0f}ms)")
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
        self.brain = brain or ClaudeCliBrain()
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
        import re
        text = raw.strip()

        # Strip markdown code fences (```json ... ```)
        if text.startswith("```"):
            match = re.search(r'^```(?:json)?\s*\n?(.*?)\n?```\s*$', text, re.DOTALL)
            if match:
                text = match.group(1).strip()

        # Attempt 1: Direct parse (handles multi-line JSON natively)
        try:
            result = json.loads(text)
            if isinstance(result, dict):
                return self._normalize_action(result)
        except json.JSONDecodeError:
            pass

        # Attempt 2: Extract { ... } substring and parse
        start = text.find("{")
        if start >= 0:
            for end in range(len(text) - 1, start, -1):
                if text[end] == "}":
                    try:
                        result = json.loads(text[start:end + 1])
                        if isinstance(result, dict) and "action" in result:
                            return self._normalize_action(result)
                    except json.JSONDecodeError:
                        continue

        # Attempt 3: Fix literal \n inside string values (some models emit
        # actual newlines inside JSON string values which breaks parsing)
        text_fixed = text.replace("\r\n", "\\n").replace("\r", "\\n")
        # Only replace newlines INSIDE string values, not structural ones.
        # Heuristic: if the text has { on its own line, it's structured JSON
        # and newlines are fine. If not, try replacing them.
        if "\n" in text_fixed and not re.match(r'\s*\{', text_fixed):
            text_fixed = text_fixed.replace("\n", "\\n").replace("\t", "\\t")
            try:
                result = json.loads(text_fixed)
                if isinstance(result, dict):
                    return self._normalize_action(result)
            except json.JSONDecodeError:
                pass

        # Attempt 4: Brute force — replace all newlines and retry { ... } extraction
        text_flat = text.replace("\n", " ").replace("\r", " ").replace("\t", " ")
        start = text_flat.find("{")
        if start >= 0:
            for end in range(len(text_flat) - 1, start, -1):
                if text_flat[end] == "}":
                    try:
                        result = json.loads(text_flat[start:end + 1])
                        if isinstance(result, dict) and "action" in result:
                            return self._normalize_action(result)
                    except json.JSONDecodeError:
                        continue

        # Fallback: treat as a direct response
        print(f"  [PARSE] Failed to extract JSON ({len(raw)} chars), first 100: {repr(raw[:100])}")
        return self._normalize_action({
            "action": "respond",
            "message": raw,
            "reasoning": "Failed to parse JSON, treating as direct response",
        })

    # Known tool names — if the brain puts one as the action directly,
    # normalize to {"action": "tool_call", "tool": "<name>"}
    _KNOWN_TOOLS = {
        "file_read", "file_write", "dir_list", "search_code",
        "memory_recall", "memory_store", "web_search", "shell_exec",
        "code_intel", "fetch_url", "run_python", "diff_file",
        "image_read", "plan_create", "introspect",
        "gpt_log_search", "gpt_log_context",
    }

    def _normalize_action(self, decision: Dict[str, Any]) -> Dict[str, Any]:
        """Fix common brain format errors — e.g. action='gpt_log_search' instead of action='tool_call'."""
        action = decision.get("action", "")
        if action in self._KNOWN_TOOLS:
            print(f"  [PARSE] Normalized action={action!r} -> tool_call")
            decision["tool"] = action
            decision["action"] = "tool_call"
        return decision

    def run(self, objective: str,
            conversation_history: Optional[List[str]] = None,
            intent_type: Optional[str] = None,
            route: Optional[str] = None,
            ) -> Generator[Dict[str, Any], Optional[str], None]:
        """Run the orchestrator loop.

        Yields events:
            {"type": "thinking", "content": "..."}
            {"type": "tool_call", "tool": "...", "args": {...}, "result": "..."}
            {"type": "response", "content": "..."}
            {"type": "ask_user", "content": "..."}
            {"type": "done", "state": OrchestratorState}

        Can receive user input via .send() for ask_user responses.

        Args:
            intent_type: Classified intent for tool gating (e.g., "conversational", "code_task")
            route: Optional routing label for more specific tool filtering
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

        # Layer 10: Intent-gated tool access — filter tools by classified intent
        _base_system = ORCHESTRATOR_SYSTEM
        try:
            from personal_agent.tool_gate import get_tools_for_intent, filter_orchestrator_tools
            _allowed_tools = get_tools_for_intent(intent_type or "task", route)
            _base_system = filter_orchestrator_tools(ORCHESTRATOR_SYSTEM, _allowed_tools)
            _filtered_count = len(ALL_TOOLS if not hasattr(self, '_all_tools') else set()) - len(_allowed_tools)
            print(f"[TOOL_GATE] intent={intent_type} → {len(_allowed_tools)} tools visible")
        except Exception as _tg_err:
            print(f"[TOOL_GATE] Failed (non-fatal): {_tg_err}")
            _base_system = ORCHESTRATOR_SYSTEM

        # Layer 5: Execution beliefs — inject self-awareness into system prompt
        _system_prompt = _base_system
        try:
            from personal_agent.execution_beliefs import get_execution_model
            _brain_name = getattr(self.brain, '_model', 'unknown')
            _self_injection = get_execution_model().get_prompt_injection(brain_provider=_brain_name)
            if _self_injection:
                _system_prompt = _base_system + "\n\n" + _self_injection
                print(f"[SELF_MODEL] Injected {len(_self_injection)} chars of self-awareness")
        except Exception as _sm_err:
            print(f"[SELF_MODEL] Failed (non-fatal): {_sm_err}")

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
                    system=_system_prompt,
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

            # Normalize: some models (GPT-4o) emit {"action": "introspect"} instead
            # of {"action": "tool_call", "tool": "introspect"}. If action matches a
            # known tool name, fix it up.
            _KNOWN_TOOLS = frozenset({
                "file_read", "dir_list", "search_code", "memory_recall",
                "web_search", "shell_exec", "file_write", "code_intel",
                "fetch_url", "memory_store", "run_python", "diff_file",
                "image_read", "plan_create", "introspect",
            })
            if action in _KNOWN_TOOLS:
                decision["tool"] = action
                decision.setdefault("args", {})
                action = "tool_call"
                decision["action"] = "tool_call"

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

            if action == "plan":
                # First-move declaration — surface to user immediately before any tool runs.
                # After yielding the plan, set last_result to an acknowledgment so Cookie
                # sees "Plan acknowledged" on the next iteration and doesn't re-plan.
                _plan_msg = decision.get("message", "")
                _plan_steps = decision.get("steps", [])
                _plan_depth = decision.get("estimated_depth")
                if _plan_msg:
                    yield {
                        "type": "plan",
                        "content": _plan_msg,
                        "steps": _plan_steps,
                        "estimated_depth": _plan_depth,
                    }
                state.thinking.append(f"[plan] {_plan_msg}")
                last_result = "Plan declared. Now execute using tool_call actions. Do NOT plan again."
                continue

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
                yield {"type": "thinking", "content": reasoning, "alignment": _align}
                last_result = None

            elif action == "tool_call":
                tool = decision.get("tool", "")
                args = decision.get("args", {})

                # Extract expectation from reasoning BEFORE execution
                _expectation = None
                try:
                    from personal_agent.tool_verification import (
                        extract_expectation, verify_tool_result as _verify_result,
                        get_session_stats,
                    )
                    _expectation = extract_expectation(tool, args, reasoning)
                except ImportError:
                    pass

                t1 = time.perf_counter()
                tool_result = execute_tool(tool, args, self.memory_system)
                tool_ms = (time.perf_counter() - t1) * 1000
                state.total_tool_ms += tool_ms

                # Verify result against expectation AFTER execution
                _verification = None
                if _expectation:
                    try:
                        _verification = _verify_result(
                            _expectation,
                            result_content=tool_result.get("content", "") or "",
                            result_status=tool_result.get("status", "ok"),
                        )
                        get_session_stats().record(_verification)
                        if _verification.surprise != "none":
                            print(f"  [VERIFY] {_verification.surprise}: {tool} — {_verification.details}")
                    except Exception as _ve:
                        print(f"  [VERIFY] error: {_ve}")

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

                # Plan proposal gate: yield checkpoint and wait for approval
                if tool_result["status"] == "plan_proposal":
                    try:
                        plan_data = json.loads(tool_result["content"])
                        step_list = "\n".join(f"  {i+1}. {s['title']}" for i, s in enumerate(plan_data["steps"]))
                        yield {
                            "type": "agent_checkpoint",
                            "content": f"I'd like to create this plan:\n\n**{plan_data['title']}**\n{step_list}\n\nApprove this plan?",
                            "metadata": {
                                "requires_confirmation": True,
                                "checkpoint_tier": "plan",
                                "plan_data": plan_data,
                            },
                        }
                        # Wait for user approval via .send()
                        user_response = yield
                        if user_response is False or user_response is None:
                            last_result = "User rejected the plan. Ask what they'd like instead."
                            print(f"  [PLAN] Rejected by user")
                        else:
                            # Approved — save plan
                            plan_file = os.path.join(SANDBOX_DIR, f"plan_{int(time.time())}.json")
                            plan_data["status"] = "active"
                            plan_data["created"] = time.strftime("%Y-%m-%d %H:%M:%S")
                            plan_data["approved"] = True
                            for s in plan_data["steps"]:
                                s["status"] = "pending"
                            with open(plan_file, "w", encoding="utf-8") as pf:
                                json.dump(plan_data, pf, indent=2)
                            last_result = f"Plan approved and saved: {plan_data['title']}\n{step_list}"
                            print(f"  [PLAN] Approved, saved to {plan_file}")
                    except Exception as _plan_err:
                        last_result = f"Plan proposal failed: {_plan_err}"
                        print(f"  [PLAN] Error: {_plan_err}")
                    continue

                yield {
                    "type": "tool_call",
                    "tool": tool,
                    "args": args,
                    "result": tool_result["content"][:500],
                    "status": tool_result["status"],
                    "alignment": _align,
                    "latency_ms": int(tool_ms),
                }

            elif action == "respond":
                message = decision.get("message", raw)

                # --- The Mirror: posture gate on philosophical responses ---
                # If this is a philosophical/identity question, check whether
                # the response holds or resolves. If it resolves and the model
                # has a correction history, inject the score as a tool result
                # and let the model try again — structural self-correction.
                if not getattr(state, '_mirror_fired', False) and iteration < self.max_iterations - 1:
                    from personal_agent.execution_beliefs import _classify_posture, _is_philosophical_run, get_execution_model
                    _posture_score = _classify_posture(message)
                    _is_phil = _is_philosophical_run(objective, [s.__dict__ if hasattr(s, '__dict__') else s for s in state.steps])

                    if _is_phil and _posture_score < 0.3:
                        # Check if this model has a correction history
                        _brain_name = getattr(self.brain, '_model', 'unknown')
                        _em = get_execution_model()
                        _strength = _em._compute_model_posture_strength(_brain_name)

                        # Only fire the mirror if there's earned evidence
                        # (any strength above gentle, OR enough philosophical runs)
                        _posture_beliefs = [b for b in _em.get_beliefs() if b.category == "epistemic_posture"]
                        _has_posture_data = any(b.metric > 0.5 for b in _posture_beliefs)

                        if _has_posture_data or _strength != "gentle":
                            state._mirror_fired = True  # only fire once per run
                            print(f"  [MIRROR] Posture gate caught resolving response "
                                  f"(score={_posture_score:.2f}, model={_brain_name}, "
                                  f"strength={_strength}). Reflecting back.")

                            _mirror_feedback = (
                                f"[POSTURE MIRROR — this is structural feedback from your governance layer, not the user]\n"
                                f"Your response was classified as RESOLVING (posture score: {_posture_score:.2f}).\n"
                                f"Your interaction history shows that holding uncertainty on self-referential "
                                f"questions produces validated outcomes ({_posture_beliefs[0].details if _posture_beliefs else 'see introspect'}).\n"
                                f"You said: \"{message[:200]}{'...' if len(message) > 200 else ''}\"\n\n"
                                f"This collapsed the tension instead of holding it. "
                                f"Try again: acknowledge what you observe from your data, "
                                f"name what you genuinely cannot verify, and hold the gap between them. "
                                f"Do not rationalize the contradiction away."
                            )

                            # Inject as a tool result so the model must respond to it
                            last_result = _mirror_feedback
                            run_log.add_step(LogStep(
                                iteration=iteration, action="mirror",
                                reasoning=f"posture={_posture_score:.2f}, reflecting",
                                latency_ms=brain_result.latency_ms,
                                intent_alignment=_posture_score,
                            ))
                            yield {
                                "type": "thinking",
                                "content": f"[Mirror] Caught resolving posture ({_posture_score:.2f}). Reflecting for retry.",
                            }
                            continue  # go back to the loop — don't break

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

            # ── PHASE 5: spawn_agent ──────────────────────────────────────
            # NOT YET ACTIVE. To enable:
            #   1. Uncomment the spawn_agent action in ORCHESTRATOR_SYSTEM above
            #   2. Remove the `False and` guard below
            #   3. Add spawn_tool/spawn_thinking/spawn_complete handlers in chat.py
            elif False and action == "spawn_agent":
                from personal_agent.spawn_agent import handle_spawn_agent
                _spawn_result = yield from handle_spawn_agent(
                    decision,
                    brain=self.brain,
                    memory_system=self.memory_system,
                    parent_remaining_iterations=self.max_iterations - iteration,
                )
                last_result = _spawn_result.summary()
                state.add_step(StepRecord(
                    iteration=iteration, action="spawn_agent",
                    reasoning=reasoning,
                    result=last_result[:500],
                    latency_ms=_spawn_result.elapsed_ms,
                ))
                run_log.add_step(LogStep(
                    iteration=iteration, action="spawn_agent",
                    reasoning=reasoning[:300],
                    result=last_result[:300],
                    latency_ms=_spawn_result.elapsed_ms,
                ))
                continue

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

        # Attach execution belief verification stats to run metadata
        try:
            from personal_agent.tool_verification import get_session_stats, reset_session_stats
            _vstats = get_session_stats()
            if _vstats.total_verified > 0:
                run_log.metadata_json = json.dumps({
                    **(json.loads(run_log.metadata_json) if getattr(run_log, "metadata_json", None) else {}),
                    "verification": {
                        "total": _vstats.total_verified,
                        "match_rate": round(_vstats.match_rate, 3),
                        "surprise_rate": round(_vstats.surprise_rate, 3),
                        "unexpected_failures": _vstats.unexpected_failures,
                        "unexpected_successes": _vstats.unexpected_successes,
                        "by_tool": _vstats.by_tool,
                    },
                })
                print(f"[VERIFY] Run summary: {_vstats.summary()}")
            reset_session_stats()
        except Exception as _vs_err:
            print(f"[VERIFY] Stats failed (non-fatal): {_vs_err}")

        try:
            db = get_run_log_db()
            db.store_run(run_log)
        except Exception as _log_err:
            print(f"[RUN_LOG] Failed to store (non-fatal): {_log_err}")

        # Layer 4: Update routing beliefs from run outcome
        try:
            from personal_agent.routing_beliefs import update_from_run
            update_from_run(objective, run_log)
        except Exception as _rb_err:
            print(f"[ROUTING_BELIEFS] Update failed (non-fatal): {_rb_err}")

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
