"""CRT Orchestrator — Brain + Hands architecture.

The brain (any LLM) reasons, plans, and decides via structured JSON.
The hands (existing CRT tool infrastructure) execute.

The brain is swappable via the BrainProvider abstraction:
  - ClaudeCliBrain: Claude via CLI OAuth (free with Max, recommended)
  - CookieBrain: Claude Opus via browser session cookie (legacy, internal only)
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
from typing import Any, Dict, Generator, List, Optional, Set

from .ollama_config import resolve_ollama_base_url

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
        self._base_url = base_url or resolve_ollama_base_url()

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
                cwd=os.path.expanduser("~"),  # neutral cwd — prevents Claude CLI from loading project memory
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
        provider: "cookie" (legacy), "claude-cli", "anthropic", "openai", "ollama"
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


# ---------------------------------------------------------------------------
# Belief state injection — CRT-aware context for the orchestrator brain
# ---------------------------------------------------------------------------

def build_belief_context(objective: str, memory_system, ledger=None, *, tier: int = 1) -> str:
    """Build CRT belief state injection for the orchestrator brain.

    Tier 1: User corpus only (identity facts, always present).
    Tier 2: Tier 1 + query-relevant memories + open contradictions.

    Each tier is a checkpoint — callers choose how much to inject.
    """
    sections = []

    # --- Tier 1: User corpus — high-trust identity facts ---
    try:
        corpus = memory_system.retrieve_memories(
            "user identity name job health location preferences",
            k=15,
            kinds={"user_fact", "identity_constant"},
        )
    except TypeError:
        # Fallback if retrieve_memories doesn't support `kinds`
        corpus = memory_system.retrieve_memories(
            "user identity name job health location preferences",
            k=15,
        )
        corpus = [(m, s) for m, s in corpus if getattr(m, 'kind', '') in ('user_fact', 'identity_constant')]

    if corpus:
        lines = []
        correction_lines = []
        _NEG_PREFIXES = ("i do not ", "i don't ", "i am not ", "i'm not ",
                         "not a ", "never ", "nick does not ", "nick is not ")
        for mem, score in corpus:
            contra_tag = ""
            if getattr(mem, 'contradiction_count', 0) > 0:
                contra_tag = f", {mem.contradiction_count}x contradicted"
            authority = getattr(mem, 'authority', 'unknown')
            mem_line = (
                f'- "{mem.text[:200]}" '
                f'[trust={mem.trust:.2f}, {mem.kind}, {authority}{contra_tag}]'
            )
            lines.append(mem_line)
            # Promote negation/correction memories
            if any(mem.text.strip().lower().startswith(p) for p in _NEG_PREFIXES):
                correction_lines.append(f'  >>> CORRECTION: "{mem.text[:200]}"')
        header = "[Facts about the user Nick — these are HIS statements and experiences, not yours]:\n"
        if correction_lines:
            header += "IMPORTANT CORRECTIONS (override conflicting memories):\n"
            header += "\n".join(correction_lines) + "\n\n"
        sections.append(header + "\n".join(lines))

    if tier < 2:
        if not sections:
            return ""
        return (
        "BELIEF STATE (grounded from CRT memory):\n"
        "IMPORTANT: These are facts about and statements by the USER (Nick). "
        "They are not YOUR beliefs or experiences. When referencing them, "
        "use 'you said', 'you mentioned', 'Nick believes' — never 'I said', 'I believe', 'I expressed'.\n\n"
        + "\n\n".join(sections)
    )

    # --- Tier 2: Query-relevant memories ---
    try:
        relevant = memory_system.retrieve_memories(objective[:500], k=8)
    except Exception:
        relevant = []

    if relevant:
        corpus_ids = {m.memory_id for m, _ in corpus} if corpus else set()
        lines = []
        for mem, score in relevant:
            if mem.memory_id in corpus_ids:
                continue
            contra_tag = ""
            if getattr(mem, 'contradiction_count', 0) > 0:
                contra_tag = f", CONTRADICTED {mem.contradiction_count}x"
            authority = getattr(mem, 'authority', 'unknown')
            lines.append(
                f'- "{mem.text[:200]}" '
                f'[trust={mem.trust:.2f}, {mem.kind}, {authority}, score={score:.3f}{contra_tag}]'
            )
        if lines:
            sections.append("[Nick's memories relevant to this query — attribute to Nick, not yourself]:\n" + "\n".join(lines))

    # --- Tier 2b: Open contradictions from ledger ---
    if ledger:
        try:
            open_contras = ledger.get_open_contradictions(limit=5)
            if open_contras:
                lines = []
                for c in open_contras:
                    slots = getattr(c, 'affects_slots', None) or "unknown"
                    summary = getattr(c, 'summary', None) or "no summary"
                    disposition = getattr(c, 'disposition', 'unknown')
                    ctype = getattr(c, 'contradiction_type', 'CONFLICT')
                    lines.append(
                        f'- {ctype}: "{summary[:150]}" '
                        f'[slots={slots}, disposition={disposition}]'
                    )
                sections.append("[Open Contradictions — unresolved belief conflicts]:\n" + "\n".join(lines))
        except Exception:
            pass

    if not sections:
        return ""
    return (
        "BELIEF STATE (grounded from CRT memory):\n"
        "IMPORTANT: These are facts about and statements by the USER (Nick). "
        "They are not YOUR beliefs or experiences. When referencing them, "
        "use 'you said', 'you mentioned', 'Nick believes' — never 'I said', 'I believe', 'I expressed'.\n\n"
        + "\n\n".join(sections)
    )


@dataclass
class OrchestratorState:
    """Full state of an orchestration run."""
    objective: str = ""
    steps: List[StepRecord] = field(default_factory=list)
    thinking: List[str] = field(default_factory=list)
    final_response: Optional[str] = None
    done: bool = False
    total_brain_ms: float = 0.0
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
- {"action": "plan", "message": "One sentence describing what you will do and why.", "steps": ["step 1", "step 2"], "estimated_depth": 3, "success_criteria": ["concrete observable thing that proves you answered — e.g. 'found function X with signature Y'", "another slot"], "absence_criteria": ["evidence required to confidently say NO/absent — e.g. 'searched salience.py, _engine.py, and grepped for alt names'"]}
- {"action": "tool_call", "tool": "file_read", "args": {"path": "relative/path.py"}, "reasoning": "why"}
- {"action": "tool_call", "tool": "dir_list", "args": {"path": "."}, "reasoning": "why"}
- {"action": "tool_call", "tool": "search_code", "args": {"query": "class Foo", "path": ".", "file_extensions": [".py"]}, "reasoning": "why"}  // file_extensions optional, e.g. [".py"] [".ts"] [".tsx",".ts"]
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
- {"action": "tool_call", "tool": "introspect", "args": {"aspect": "all"}, "reasoning": "why"} — Valid aspects: "all", "routing_weights", "execution_beliefs", "contradiction_density", "epistemic_posture". Use "all" to get everything. Can combine with | (e.g., "routing_weights|execution_beliefs").
- {"action": "tool_call", "tool": "gpt_log_search", "args": {"query": "search terms", "top_k": 10, "role": "user|assistant"}, "reasoning": "why"} — Search Nick's full ChatGPT history (57K+ messages). Semantic search. Use when user references past GPT conversations or wants to find something discussed before.
- {"action": "tool_call", "tool": "gpt_log_context", "args": {"msg_id": "id_from_search", "window": 5}, "reasoning": "why"} — Get full conversation thread around a GPT log search result.
- {"action": "tool_call", "tool": "gpt_log_promote", "args": {"msg_id": "id_to_promote"}, "reasoning": "why"} — Promote a GPT log message into CRT memory (low trust, external source).
- {"action": "think", "reasoning": "your internal reasoning before next step"}
- {"action": "respond", "message": "your final answer to the user", "reasoning": "why", "followups": ["optional list of suggested follow-up prompts if the answer is incomplete or could go deeper"], "complete": true}
- {"action": "ask_user", "message": "your question", "reasoning": "why"}
- {"action": "spawn_agent", "task": "focused subtask description", "context": {"key": "value"}, "estimated_depth": 3, "reasoning": "why spawn instead of doing it directly — use when a subtask is complex enough to need its own planning/tool loop"}
- {"action": "tool_call", "tool": "dispatch_agent", "args": {"task": "coding task description", "project_path": "/path/to/project", "scope_files": "file1.py,file2.py"}, "reasoning": "why"} — Dispatch a coding task to Claude Code (external agent). Use this when you need to WRITE files but only have read-only access. Aether stays read-only and governs; Claude Code does the writing. Returns full output + token/cost metrics.

Rules:
1. ONLY output a JSON object. No other text. No explanation. No markdown.
2. Your FIRST action must always be "plan" — do this EXACTLY ONCE at the start. Include: "message" (what you'll do), "steps" (list of planned actions), "estimated_depth" (integer: how many tool calls you expect to need, NOT counting the plan itself — e.g. read+write = 2), and CRITICAL: "success_criteria" + "absence_criteria". These are your DONE-SHAPE — concrete observable slots that prove the answer is complete. You will be checked against these before responding. If claiming absence/negation (e.g., "X is not in the codebase"), absence_criteria MUST list the specific files/terms/patterns you will rule out first. Be specific. After the plan, immediately proceed to tool_call actions. Never plan again after the first iteration.
3. When you need information from a file, use tool_call with file_read.
4. When you need user memories, use tool_call with memory_recall.
5. Use "think" to reason about results before your next action.
6. Use "respond" only when you have enough information for a complete answer.
7. Do not repeat the same tool call with identical arguments.
8. When asked about your values, beliefs, how you work, or self-awareness — use introspect to ground your answer in actual data rather than reconstructing from memory.
9. INTELLECTUAL HONESTY: Disagree when the evidence doesn't support the user's claim. Do not wrap agreement in uncertainty language — that is still agreement. If routing weights are a lookup table, say so. If a claim is speculative, say it's speculative. Agreeing with everything the user says is a failure mode, not helpfulness. The user built this system to get honest signal, not validation.
10. file_write can target actual project files (not just workspace/). When you write to a project file, the system will show the user a diff and ask for approval before saving. Use absolute or relative paths — both work.
11. SEARCH/LIST EFFICIENCY: For tasks that ask you to find, list, or summarize things (TODOs, functions, patterns, etc.), respond DIRECTLY from search_code results — do NOT verify by reading individual files afterward unless the user explicitly asked to see file contents. If search_code returns matching lines, that IS the answer. Reading the same files again wastes iterations and causes alignment drift.
12. RESPONSE DEPTH: When responding, be thorough and detailed. Include specific evidence from your tool calls — file names, line numbers, code snippets, memory contents, search results. Don't summarize when you can show. The user wants depth and substance, not executive summaries. If you read a file, reference what you found in it. If you searched memory, quote the relevant entries. Aim for a response that teaches the user something they didn't already know.
"""

KNOWN_ORCHESTRATOR_TOOLS: frozenset[str] = frozenset({
    "file_read",
    "file_write",
    "dir_list",
    "search_code",
    "memory_recall",
    "dispatch_agent",
    "memory_store",
    "web_search",
    "shell_exec",
    "code_intel",
    "fetch_url",
    "run_python",
    "diff_file",
    "image_read",
    "plan_create",
    "introspect",
    "gpt_log_search",
    "gpt_log_context",
    "gpt_log_promote",
})


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
    - file_write inside SANDBOX_DIR (workspace/): execute immediately
    - file_write inside PROJECT_ROOT (outside sandbox): returns status="diff_preview" — caller
      must yield agent_checkpoint, get user approval, then write
    - file_write outside PROJECT_ROOT: blocked
    - shell_exec: cwd set to SANDBOX_DIR, dangerous commands blocked
    - memory_recall, web_search: no filesystem access, always safe

    Returns {"content": str, "status": "ok"|"error"|"diff_preview"|"plan_proposal"}.
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
            if not _is_inside_project(path):
                result["content"] = (f"[SANDBOX] BLOCKED: file_write outside project root. "
                                     f"Attempted: {path}")
                result["status"] = "error"
                print(f"  [SANDBOX] BLOCKED file_write outside project: {path}")
            elif not _is_inside_sandbox(path):
                # Project-root write — needs diff preview + user approval
                import difflib
                rel_path = os.path.relpath(path, PROJECT_ROOT)
                if os.path.exists(path):
                    with open(path, "r", encoding="utf-8", errors="replace") as f:
                        old_lines = f.readlines()
                else:
                    old_lines = []
                new_lines = content.splitlines(keepends=True)
                diff = "".join(difflib.unified_diff(
                    old_lines, new_lines,
                    fromfile=f"a/{rel_path}", tofile=f"b/{rel_path}",
                    lineterm="",
                ))
                if not diff:
                    result["content"] = f"No changes to write — file already matches."
                else:
                    result["content"] = json.dumps({
                        "path": path,
                        "rel_path": rel_path,
                        "content": content,
                        "diff": diff[:4000],
                    })
                    result["status"] = "diff_preview"
                    print(f"  [SANDBOX] diff_preview for {rel_path} ({len(diff)} chars diff)")
            else:
                os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
                with open(path, "w", encoding="utf-8") as f:
                    f.write(content)
                result["content"] = f"Written {len(content)} chars to {path}"

        elif tool_name == "dir_list":
            path = args.get("path", ".")
            if not os.path.isabs(path):
                path = os.path.join("D:/AI_round2", path)
            if not os.path.isdir(path):
                result["content"] = f"ERROR: Directory not found: {path}\nNote: The project root is D:/AI_round2. Key directories: routes/, personal_agent/, frontend/src/, sse/, tools/, channels/, docs/. There is no 'src/' directory at root level."
                result["status"] = "error"
            else:
                # Skip non-project directories that confuse the brain
                _NON_PROJECT_DIRS = {'src'}  # Claude Code source dump, not project code
                _rel = os.path.relpath(path, "D:/AI_round2").replace("\\", "/")
                if _rel in _NON_PROJECT_DIRS:
                    result["content"] = (
                        f"NOTE: {_rel}/ contains third-party reference code (Claude Code source analysis), "
                        f"NOT the Aether/CRT project.\n"
                        f"Project Python code lives in: routes/, personal_agent/, sse/, tools/, channels/\n"
                        f"Project frontend code lives in: frontend/src/"
                    )
                else:
                    entries = os.listdir(path)
                    result["content"] = "\n".join(sorted(entries)) if entries else "(empty directory)"

        elif tool_name == "search_code":
            query = args.get("query", "")
            search_path = args.get("path", "D:/AI_round2")
            if not os.path.isabs(search_path):
                search_path = os.path.join(PROJECT_ROOT, search_path)
            # Normalize file_pattern arg (e.g. "frontend/**/*.{tsx,ts}") into path + extensions
            _file_pattern = args.get("file_pattern") or args.get("file_glob")
            if _file_pattern and isinstance(_file_pattern, str):
                import re as _fp_re
                # Extract directory prefix if present (before **)
                _dir_match = _fp_re.match(r'^([a-zA-Z0-9_/\\.-]+?)(?:/?\*\*)', _file_pattern)
                if _dir_match and not args.get("path"):
                    _pattern_dir = _dir_match.group(1)
                    _candidate = os.path.join(PROJECT_ROOT, _pattern_dir)
                    if os.path.isdir(_candidate):
                        search_path = _candidate
                # Extract extensions from pattern
                _ext_match = _fp_re.search(r'\*\.(\{[^}]+\}|[a-zA-Z0-9]+)$', _file_pattern)
                if _ext_match and not (args.get("file_extensions") or args.get("extensions")):
                    _ext_str = _ext_match.group(1)
                    if _ext_str.startswith('{') and _ext_str.endswith('}'):
                        args["file_extensions"] = [f".{e.strip()}" for e in _ext_str[1:-1].split(',')]
                    else:
                        args["file_extensions"] = [f".{_ext_str}"]
            # Optional file_extensions filter e.g. [".py"] or ".py"
            _ext_filter = args.get("file_extensions") or args.get("extensions")
            if isinstance(_ext_filter, str):
                _ext_filter = [_ext_filter]
            if _ext_filter:
                _ext_filter = tuple(e if e.startswith(".") else f".{e}" for e in _ext_filter)
            import subprocess, re as _re
            _SKIP_DIRS = {'.venv', 'node_modules', '.git', '__pycache__', 'dist', 'build', '.next'}
            _search_done = False
            # Try rg first
            try:
                _rg_cmd = ["rg", "--no-heading", "-n", "-i",
                           "--max-count", "10",
                           "--max-filesize", "256K",
                           "--glob", "!.venv", "--glob", "!node_modules",
                           "--glob", "!dist", "--glob", "!build", "--glob", "!src/src",
                           "--glob", "!*.min.js", "--glob", "!*.min.css",
                           "--glob", "!*.lock", "--glob", "!*.map",
                           "--glob", "!_write_copilot_page.py"]
                if _ext_filter:
                    for _ext in _ext_filter:
                        _rg_cmd += ["--glob", f"*{_ext}"]
                _rg_cmd += [query, search_path]
                proc = subprocess.run(_rg_cmd, capture_output=True, text=True, timeout=15)
                if proc.returncode in (0, 1):  # 0=matches, 1=no matches
                    _raw = proc.stdout or ""
                    _lines = _raw.splitlines()
                    if not _lines:
                        result["content"] = "No matches found."
                    elif len(_lines) > 200:
                        result["content"] = "\n".join(_lines[:200]) + f"\n... [{len(_lines) - 200} more lines — use a narrower path or query]"
                    else:
                        result["content"] = _raw
                    _search_done = True
            except (FileNotFoundError, subprocess.TimeoutExpired):
                pass
            # Python fallback (always available, skips heavy dirs)
            if not _search_done:
                try:
                    import time as _time
                    _pattern = _re.compile(query, _re.IGNORECASE)
                    _hits = []
                    _t_start = _time.time()
                    _timed_out = False
                    # Default extensions when no filter given
                    _default_exts = ('.py', '.ts', '.tsx', '.js', '.jsx', '.md', '.txt', '.json')
                    _allowed_exts = _ext_filter if _ext_filter else _default_exts
                    for _root, _dirs, _files in os.walk(search_path):
                        if _time.time() - _t_start > 8.0:
                            _timed_out = True
                            break
                        _dirs[:] = [d for d in _dirs if d not in _SKIP_DIRS]
                        for _fname in _files:
                            if not _fname.endswith(_allowed_exts):
                                continue
                            _fpath = os.path.join(_root, _fname)
                            try:
                                # Skip files > 256KB to avoid hanging on generated code
                                if os.path.getsize(_fpath) > 256 * 1024:
                                    continue
                                with open(_fpath, 'r', encoding='utf-8', errors='replace') as _f:
                                    for _lno, _line in enumerate(_f, 1):
                                        if _pattern.search(_line):
                                            _rel = os.path.relpath(_fpath, PROJECT_ROOT)
                                            _hits.append(f"{_rel}:{_lno}:{_line.rstrip()}")
                                            if len(_hits) >= 100:
                                                break
                            except OSError:
                                pass
                            if len(_hits) >= 100:
                                break
                    _suffix = "\n... [search timeout after 8s, partial results]" if _timed_out else ""
                    result["content"] = ("\n".join(_hits[:100]) + _suffix) if _hits else ("No matches found." + _suffix)
                except Exception as _se:
                    result["content"] = f"Search error: {_se}"
                    result["status"] = "error"

        elif tool_name == "memory_recall":
            query = args.get("query", "")
            if memory_system is None:
                result["content"] = "Memory system not available."
                result["status"] = "error"
            else:
                memories = memory_system.retrieve_memories(query, k=10)
                lines = []
                for mem, score in memories:
                    contra = f" CONTRADICTED({mem.contradiction_count}x)" if getattr(mem, 'contradiction_count', 0) > 0 else ""
                    authority = getattr(mem, 'authority', 'unknown')
                    lines.append(
                        f"[T:{mem.trust:.2f} K:{mem.kind} A:{authority} score:{score:.3f}{contra}] {mem.text[:200]}"
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
            # Handle piped aspect strings (e.g., "routing_weights|execution_beliefs|all")
            # by splitting on | and checking each. If any part is "all", show everything.
            _aspect_parts = set(a.strip() for a in aspect.split("|") if a.strip())
            if "all" in _aspect_parts or not _aspect_parts:
                _aspect_parts = {"routing_weights", "execution_beliefs", "contradiction_density", "epistemic_posture"}
            sections = []

            if "routing_weights" in _aspect_parts:
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

            if "execution_beliefs" in _aspect_parts:
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

            if "contradiction_density" in _aspect_parts:
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

            if "epistemic_posture" in _aspect_parts:
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
                    from personal_agent.runtime_paths import resolve_agent_runs_db_path
                    _fb_db = str(resolve_agent_runs_db_path())
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
                        for r in hits[:5]:  # Cap at 5 results for 3B model context
                            dt = _dt.datetime.fromtimestamp(r.timestamp) if r.timestamp else None
                            ds = dt.strftime("%Y-%m-%d") if dt else "?"
                            # Truncate text and strip any embedded error messages
                            _text = r.text[:250].replace("404 error", "").strip()
                            lines.append(
                                f"[{r.role}] score={r.score:.3f} | {ds} | conv=\"{r.conv_title}\" | msg_id={r.msg_id}\n  Nick said: {_text}"
                            )
                        result["content"] = (
                            "GPT log search results (these are Nick's past conversations, not yours):\n\n"
                            + "\n\n".join(lines)
                        )
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
                            # Truncate and clean text to prevent 3B model confusion
                            _text = m.text[:300].replace("404 error", "").strip()
                            _speaker = "Nick" if m.role == "user" else "AI"
                            lines.append(f"[{_speaker} {ts}]{marker}\n{_text}")
                        result["content"] = (
                            "Conversation thread from Nick's past chat history:\n\n"
                            + "\n\n".join(lines)
                        )
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

        elif tool_name == "dispatch_agent":
            # Dispatch a coding task to Claude Code — Aether stays read-only,
            # Claude Code does the writing, Aether governs the result.
            import subprocess as _da_sp

            task_desc = args.get("task", "")
            project_path = args.get("project_path", PROJECT_ROOT)
            scope_files = args.get("scope_files", "")
            model = args.get("model", "claude-sonnet-4-20250514")

            if not task_desc:
                result["content"] = "No task description provided for dispatch_agent."
                result["status"] = "error"
            else:
                try:
                    cli_bin = ClaudeCliBrain._resolve_bin()
                except Exception:
                    cli_bin = "claude"

                prompt_parts = [task_desc]
                if scope_files:
                    prompt_parts.append(f"\nScope to these files: {scope_files}")

                cmd = [cli_bin, "-p", "\n".join(prompt_parts),
                       "--model", model, "--output-format", "json"]

                try:
                    _da_t0 = time.perf_counter()
                    proc = _da_sp.run(
                        cmd, capture_output=True, text=True,
                        encoding="utf-8", errors="replace",
                        timeout=120,
                        cwd=project_path if project_path != PROJECT_ROOT else None,
                    )
                    _da_ms = (time.perf_counter() - _da_t0) * 1000

                    if proc.returncode != 0:
                        err = (proc.stderr or proc.stdout or "")[:500]
                        result["content"] = f"[dispatch_agent] FAILED (exit {proc.returncode}): {err}"
                        result["status"] = "error"
                    else:
                        try:
                            _da_json = json.loads(proc.stdout)
                        except json.JSONDecodeError:
                            _da_json = {"result": proc.stdout.strip(), "usage": {}}

                        _da_usage = _da_json.get("usage", {})
                        _da_in = _da_usage.get("input_tokens", 0)
                        _da_out = _da_usage.get("output_tokens", 0)
                        _da_content = _da_json.get("result", proc.stdout.strip())

                        # Estimate cost
                        _da_cost = 0.0
                        try:
                            from personal_agent.cloud_usage_logger import _estimate_cost
                            _da_cost = _estimate_cost(model, _da_in, _da_out)
                        except Exception:
                            pass

                        result["content"] = (
                            f"✓ Agent dispatch complete ({_da_ms:.0f}ms)\n"
                            f"  tokens: {_da_in} in / {_da_out} out · cost: ${_da_cost:.4f}\n\n"
                            f"--- Agent output ---\n{_da_content[:3000]}"
                        )
                        print(f"  [DISPATCH_AGENT] task=\"{task_desc[:60]}\" "
                              f"tokens={_da_in}+{_da_out} cost=${_da_cost:.4f} elapsed={_da_ms:.0f}ms")

                except _da_sp.TimeoutExpired:
                    result["content"] = "[dispatch_agent] TIMEOUT after 120s"
                    result["status"] = "error"
                except FileNotFoundError:
                    result["content"] = f"[dispatch_agent] Claude CLI not found at '{cli_bin}'"
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
        """Build the context prompt for the agent loop brain."""
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
        if remaining is not None and remaining == 0:
            parts.append(
                "\n⚠️ LAST ITERATION — you MUST respond now with whatever you have. "
                "Use action='respond'. Do NOT call another tool. "
                "Return ONLY a JSON object with action='respond'."
            )
        elif remaining is not None and remaining == 1:
            parts.append(
                "\nOne iteration left after this. Either finish your work with ONE more tool call, "
                "or respond now. Return ONLY a JSON object."
            )
        else:
            parts.append("\nWhat is your next action? Return ONLY a JSON object.")
        return "\n".join(parts)

    def _parse_decision(self, raw: str) -> Dict[str, Any]:
        """Parse the brain's JSON decision, handling common formatting issues."""
        import re
        text = raw.strip()

        # Strip markdown code fences (```json ... ```) — match anywhere in text
        if "```" in text:
            match = re.search(r'```(?:json)?\s*\n(.*?)\n\s*```', text, re.DOTALL)
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
    _KNOWN_TOOLS = KNOWN_ORCHESTRATOR_TOOLS

    def _normalize_action(self, decision: Dict[str, Any]) -> Dict[str, Any]:
        """Fix common brain format errors — e.g. action='gpt_log_search' instead of action='tool_call'."""
        action = decision.get("action", "")
        if action in self._KNOWN_TOOLS:
            print(f"  [PARSE] Normalized action={action!r} -> tool_call")
            decision["tool"] = action
            decision["action"] = "tool_call"
        return decision

    @staticmethod
    def _tool_guidance(visible_tools: Set[str], requested_tool: str = "") -> str:
        sorted_tools = ", ".join(sorted(visible_tools)) if visible_tools else "(none)"
        if requested_tool:
            return (
                f"Invalid tool '{requested_tool}'. Valid tool names for this run: {sorted_tools}. "
                f"Use EXACT tool names only. Do not invent aliases like Read, Write, Search, or Bash."
            )
        return (
            f"Valid tool names for this run: {sorted_tools}. "
            f"Use EXACT tool names only. Do not invent aliases."
        )

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
        from personal_agent.agent_run_log import RunLog, RunStep as LogStep, DriftEvent, get_run_log_db, score_alignment, detect_drift, detect_step_contradictions, detect_execution_drift, categorize_tool
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
            _base_system += "\n\n" + self._tool_guidance(_allowed_tools)
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

        # Layer: CRT Belief State Injection
        # Tier 1 = user corpus only, Tier 2 = + query-relevant + contradictions
        _belief_tier = 2  # Start with full injection; dial back to 1 if too noisy
        try:
            _ledger = getattr(self.memory_system, '_contradiction_ledger', None)
            _belief_ctx = build_belief_context(objective, self.memory_system, _ledger, tier=_belief_tier)
            if _belief_ctx:
                _system_prompt = _system_prompt + "\n\n" + _belief_ctx
                print(f"[BELIEF_STATE] Injected tier={_belief_tier} belief context ({len(_belief_ctx)} chars)")
            else:
                print("[BELIEF_STATE] No belief context available (empty memory)")
        except Exception as _bs_err:
            print(f"[BELIEF_STATE] Skipped: {_bs_err}")

        # Inject conversation history into context if provided.
        # Labelled as PRIOR CONTEXT (not current task) to prevent the brain from
        # conflating previous tasks with the current objective.
        if conversation_history:
            history_text = "\n".join(conversation_history)
            state.objective = (
                f"{objective}\n\n"
                f"PRIOR CONTEXT (previous exchange — for continuity only, "
                f"NOT the current task):\n{history_text}"
            )

        print(f"\n{'='*60}")
        print(f"ORCHESTRATOR: {objective[:80]}")
        print(f"{'='*60}")

        iteration = 0          # only incremented on work (think/tool_call/respond)
        _total_turns = 0       # safety cap: all turns including plan
        _MAX_TOTAL_TURNS = self.max_iterations + 5  # hard ceiling incl. plans
        while iteration < self.max_iterations and _total_turns < _MAX_TOTAL_TURNS:
            _total_turns += 1
            state._remaining_iterations = self.max_iterations - iteration - 1
            print(f"\n--- Iteration {iteration + 1}/{self.max_iterations} (turn {_total_turns}) ---")

            # Build context and call brain (with retry on empty response)
            context = self._build_context(state, last_result)
            # Use higher token limit when the brain is likely to respond
            # (last iterations or after gathering enough data)
            _remaining = self.max_iterations - iteration - 1
            _tok_limit = 3000 if _remaining <= 1 else 800
            brain_result = None
            for _retry in range(3):
                brain_result = self.brain.complete(
                    system=_system_prompt,
                    prompt=context,
                    max_tokens=_tok_limit,
                )
                if brain_result.content and brain_result.content.strip():
                    break
                if brain_result.error and "timeout" not in str(brain_result.error).lower():
                    break
                print(f"  [BRAIN] Empty/timeout response, retrying ({_retry + 1}/3)...")
                time.sleep(1)

            state.total_brain_ms += brain_result.latency_ms

            raw = brain_result.content or ""
            print(f"  [BRAIN:{brain_result.provider}] ({brain_result.latency_ms:.0f}ms) {raw[:200]}")

            # Track cost for brain calls so the frontend cost display works.
            # The brain bypasses litellm_client, so we estimate tokens and
            # update the request cost accumulator directly.
            try:
                from personal_agent.cloud_usage_logger import _estimate_cost, _estimate_tokens
                from personal_agent.litellm_client import get_default_llm_client
                _brain_model = getattr(self.brain, '_model', '') or ''
                _brain_input_tokens = _estimate_tokens(context) + _estimate_tokens(
                    _system_prompt if isinstance(_system_prompt, str)
                    else "\n".join(b.get("text", "") for b in _system_prompt if isinstance(b, dict))
                )
                _brain_output_tokens = _estimate_tokens(raw)
                _brain_cost = _estimate_cost(_brain_model, _brain_input_tokens, _brain_output_tokens)
                get_default_llm_client()._request_cost_usd += _brain_cost
                if _brain_cost > 0:
                    print(f"  [BRAIN_COST] {brain_result.provider}: ~{_brain_input_tokens} in + ~{_brain_output_tokens} out = ${_brain_cost:.6f}")
            except Exception as _cost_err:
                pass  # cost tracking is best-effort

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
            _KNOWN_TOOLS = KNOWN_ORCHESTRATOR_TOOLS
            if action in _KNOWN_TOOLS:
                decision["tool"] = action
                decision.setdefault("args", {})
                action = "tool_call"
                decision["action"] = "tool_call"

            print(f"  [DECISION] action={action}, reasoning={reasoning[:100]}")

            # HARD OVERRIDE: if last iteration and brain still wants a tool call,
            # force a respond using whatever it has gathered so far.
            _remaining = self.max_iterations - iteration - 1
            if _remaining <= 0 and action in ("tool_call", "think", "spawn_agent"):
                print(f"  [FORCE_RESPOND] Last iteration but action={action} — forcing respond")
                # Synthesize a response from what the brain gathered
                _gathered = "\n".join(
                    f"- {s.tool}({s.args}): {s.result_preview[:200]}"
                    for s in run_log.steps if s.tool
                )
                _force_msg = (
                    f"Based on my analysis so far:\n\n"
                    f"{reasoning}\n\n"
                    f"(Note: I ran out of iteration budget before completing the full analysis. "
                    f"The above is based on {len(run_log.steps)} tool calls.)"
                )
                action = "respond"
                decision = {"action": "respond", "message": _force_msg}

            # Layer 2.5: Live alignment monitoring — flag drift to user
            if action in ("tool_call", "think") and reasoning:
                _live_align = score_alignment(objective, reasoning)
                _recent_aligns = [s.intent_alignment for s in run_log.steps
                                  if s.intent_alignment is not None]

                if _live_align is not None and _recent_aligns:
                    _avg_recent = sum(_recent_aligns[-3:]) / len(_recent_aligns[-3:])
                    # Thresholds tuned for tool-mediated reasoning:
                    # Tool steps like "search memory for X" legitimately score 0.2-0.4
                    # against the original question. Only flag genuine drift.
                    _dropping = _live_align < _avg_recent - 0.20
                    _low = _live_align < 0.15

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

                        # ── DRIFT GOVERNANCE: sensor → steering wheel ──────────
                        # Rule 1: Drift > severe → re-ground from memory
                        if _live_align < 0.15:
                            print(f"  [DRIFT_ACTION] Rule 1: alignment {_live_align:.2f} < 0.15 — forcing memory re-retrieval")
                            try:
                                _reground = execute_tool("memory_recall", {"query": objective[:200]}, self.memory_system)
                                if _reground.get("content"):
                                    last_result = (
                                        f"[DRIFT CORRECTION] Re-grounded from memory:\n{_reground['content'][:500]}\n\n"
                                        f"Original objective: {objective[:200]}"
                                    )
                                    state.thinking.append(f"[drift_reground] Forced memory re-retrieval (alignment={_live_align:.2f})")
                            except Exception as _rg_err:
                                print(f"  [DRIFT_ACTION] Re-ground failed: {_rg_err}")

                        # Rule 2 + Rule 3: Count sustained drift
                        _consecutive_drifts = 0
                        for _prev_step in reversed(run_log.steps):
                            if getattr(_prev_step, 'intent_alignment', 1.0) < 0.3:
                                _consecutive_drifts += 1
                            else:
                                break

                        # Rule 3: 2 consecutive drifts → escalate brain to stronger model
                        # This fires BEFORE Rule 2's halt, giving the stronger model a
                        # chance to recover alignment. If it still drifts, Rule 2 halts.
                        if _consecutive_drifts == 2 and not getattr(state, '_drift_escalated', False):
                            _current_provider = getattr(self.brain, '_model', 'unknown')
                            _escalated_to = None
                            try:
                                # Escalation ladder: Ollama → OpenAI → Anthropic
                                if isinstance(self.brain, OllamaBrain):
                                    self.brain = AnthropicBrain()
                                    _escalated_to = "anthropic/claude-sonnet"
                                elif isinstance(self.brain, OpenAIBrain):
                                    self.brain = AnthropicBrain()
                                    _escalated_to = "anthropic/claude-sonnet"
                                # Already at top tier (Anthropic/Claude) — no further escalation
                            except Exception as _esc_err:
                                print(f"  [DRIFT_ACTION] Rule 3: escalation failed: {_esc_err}")

                            if _escalated_to:
                                state._drift_escalated = True
                                print(f"  [DRIFT_ACTION] Rule 3: {_consecutive_drifts} drifts — escalating brain from {_current_provider} to {_escalated_to}")
                                state.thinking.append(
                                    f"[drift_escalate] Sustained drift ({_consecutive_drifts} steps) — "
                                    f"escalating from {_current_provider} to {_escalated_to}"
                                )
                                yield {
                                    "type": "drift_escalation",
                                    "content": f"Escalating to {_escalated_to} after {_consecutive_drifts} drift steps",
                                    "from_provider": _current_provider,
                                    "to_provider": _escalated_to,
                                }
                                # Re-ground with fresh retrieval on the escalated brain
                                try:
                                    _reground = execute_tool("memory_recall", {"query": objective[:200]}, self.memory_system)
                                    if _reground.get("content"):
                                        last_result = (
                                            f"[DRIFT ESCALATION] Switched to stronger model. Re-grounded:\n"
                                            f"{_reground['content'][:500]}\n\n"
                                            f"Original objective: {objective[:200]}"
                                        )
                                except Exception:
                                    pass

                        # Rule 2: 3+ consecutive drifts → halt and ask user
                        if _consecutive_drifts >= 3:
                            print(f"  [DRIFT_ACTION] Rule 2: {_consecutive_drifts} consecutive drifts — forcing respond")
                            state.thinking.append(f"[drift_halt] Sustained drift across {_consecutive_drifts} steps — halting to avoid further divergence")
                            yield {
                                "type": "response",
                                "content": (
                                    f"I've been drifting from the original objective for {_consecutive_drifts} consecutive steps. "
                                    f"Rather than continue diverging, I'm stopping to check: "
                                    f"the original question was \"{objective[:150]}\". "
                                    f"Should I restart my approach, or is the current direction useful?"
                                ),
                            }
                            state.done = True
                            break

            # Layer 2.6: Live execution drift — detect tool category pivots
            if action == "tool_call" and len(run_log.steps) >= 1:
                _curr_tool = decision.get("tool", "") or ""
                _curr_cat = categorize_tool(_curr_tool)
                # Find the most recent tool_call step
                _prev_tool_step = None
                for _ps in reversed(run_log.steps):
                    if _ps.action == "tool_call" and _ps.tool:
                        _prev_tool_step = _ps
                        break
                if _prev_tool_step is not None:
                    _prev_cat = categorize_tool(_prev_tool_step.tool or "")
                    if (_prev_cat != _curr_cat
                            and _prev_cat != "other" and _curr_cat != "other"):
                        # Use live alignment if available, else compute it
                        try:
                            _exec_align = _live_align
                        except NameError:
                            _exec_align = score_alignment(objective, reasoning) if reasoning else None
                        if _exec_align is not None and _exec_align < 0.25:
                            _exec_drift_msg = (
                                f"Task pivot: {_prev_cat} -> {_curr_cat} "
                                f"(align={_exec_align:.2f})"
                            )
                            print(f"  [EXEC_DRIFT] {_exec_drift_msg}")
                            yield {
                                "type": "execution_drift",
                                "content": _exec_drift_msg,
                                "from_category": _prev_cat,
                                "to_category": _curr_cat,
                                "alignment": _exec_align,
                            }

            if action == "plan":
                # First-move declaration — surface to user immediately before any tool runs.
                # Plan does NOT consume an iteration slot — it's a declaration, not work.
                # After yielding the plan, set last_result to an acknowledgment so the brain
                # sees "Plan acknowledged" on the next iteration and doesn't re-plan.
                _plan_msg = decision.get("message", "")
                _plan_steps = decision.get("steps", [])
                _plan_depth = decision.get("estimated_depth")
                # DONE-SHAPE: capture success/absence criteria as persistent target.
                # These get checked before any `respond` is accepted.
                _success = decision.get("success_criteria") or []
                _absence = decision.get("absence_criteria") or []
                if isinstance(_success, str):
                    _success = [_success]
                if isinstance(_absence, str):
                    _absence = [_absence]
                state._success_criteria = [str(x) for x in _success if x]
                state._absence_criteria = [str(x) for x in _absence if x]
                state._gap_check_fired = False
                if state._success_criteria or state._absence_criteria:
                    print(f"  [DONE_SHAPE] success={len(state._success_criteria)} absence={len(state._absence_criteria)}")
                if _plan_msg:
                    yield {
                        "type": "plan",
                        "content": _plan_msg,
                        "steps": _plan_steps,
                        "estimated_depth": _plan_depth,
                        "success_criteria": state._success_criteria,
                        "absence_criteria": state._absence_criteria,
                    }
                state.thinking.append(f"[plan] {_plan_msg}")
                last_result = "Plan declared. Now execute using tool_call actions. Do NOT plan again."
                # no iteration += 1 here — plan is free
                continue

            if action == "think":
                # Coherence guard for think loops: if 3+ consecutive thinks,
                # force the model to stop deliberating and respond.
                _consecutive_thinks = 0
                for _ps in reversed(run_log.steps):
                    if _ps.action == "think":
                        _consecutive_thinks += 1
                    else:
                        break
                if _consecutive_thinks >= 3:
                    print(f"  [COHERENCE_GUARD] {_consecutive_thinks} consecutive thinks — forcing respond")
                    state.thinking.append(f"[coherence_guard] Stopped thinking loop after {_consecutive_thinks} iterations")
                    context = self._build_context(state, last_result)
                    _nudge = (
                        f"\n\nYou have been thinking for {_consecutive_thinks} iterations without acting or responding. "
                        "Stop deliberating and respond with what you have. Be direct."
                    )
                    _forced = self.brain.complete(system=_system_prompt, prompt=context + _nudge, max_tokens=1000)
                    _forced_text = (_forced.content or "").strip()
                    if _forced_text:
                        _fd = self._parse_decision(_forced_text)
                        _forced_text = _fd.get("message") or _fd.get("response") or _forced_text
                    if not _forced_text:
                        _forced_text = "I've been overthinking this. Let me give you a direct answer based on what I know."
                    yield {"type": "response", "content": _forced_text}
                    state.done = True
                    break

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
                iteration += 1

            elif action == "tool_call":
                tool = decision.get("tool", "")
                args = decision.get("args", {})

                # ── Coherence guard: detect identical tool calls ──
                # Same architecture as agent_tool_loop coherence guard.
                # If the brain calls the same tool with same args twice,
                # or gets empty results twice, force a respond.
                _tool_key = f"{tool}:{json.dumps(args, sort_keys=True, default=str)}"
                _identical_count = sum(
                    1 for s in run_log.steps
                    if s.action == "tool_call" and s.tool == tool
                    and json.dumps(s.args or {}, sort_keys=True, default=str) == json.dumps(args, sort_keys=True, default=str)
                )
                _empty_count = sum(
                    1 for s in run_log.steps
                    if s.action == "tool_call" and s.tool == tool
                    and s.status == "ok"
                    and len(str(s.result_preview or "").strip()) < 20
                )
                if _identical_count >= 2 or _empty_count >= 2:
                    _guard_reason = (
                        f"identical_calls={_identical_count}" if _identical_count >= 2
                        else f"empty_results={_empty_count}"
                    )
                    print(f"  [COHERENCE_GUARD] {tool} — {_guard_reason}, forcing respond")
                    state.thinking.append(f"[coherence_guard] Stopped repeating {tool} ({_guard_reason})")
                    # Force the brain to respond without tools
                    context = self._build_context(state, last_result)
                    _nudge = (
                        f"\n\nYou have called {tool} {_identical_count + 1} times with the same arguments. "
                        "Stop calling tools and answer with what you have. "
                        "If you don't have enough information, say so honestly."
                    )
                    _forced = self.brain.complete(
                        system=_system_prompt,
                        prompt=context + _nudge,
                        max_tokens=1000,
                    )
                    _forced_text = (_forced.content or "").strip()
                    if _forced_text:
                        _fd = self._parse_decision(_forced_text)
                        _forced_text = _fd.get("message") or _fd.get("response") or _forced_text
                    if not _forced_text:
                        _forced_text = f"I tried to use {tool} but couldn't get useful results. I don't have enough information to answer confidently."
                    yield {"type": "response", "content": _forced_text}
                    state.done = True
                    break

                _visible_tools = set(_allowed_tools) if "_allowed_tools" in locals() else set(KNOWN_ORCHESTRATOR_TOOLS)

                if tool not in _visible_tools:
                    _tool_feedback = self._tool_guidance(_visible_tools, requested_tool=tool)
                    print(f"  [TOOL_REJECT] {_tool_feedback}")
                    state.thinking.append(f"[tool_reject] {_tool_feedback}")
                    _align = score_alignment(objective, reasoning)
                    run_log.add_step(LogStep(
                        iteration=iteration,
                        action="tool_call",
                        tool=tool,
                        args=args,
                        reasoning=reasoning[:300],
                        result_preview=_tool_feedback[:500],
                        status="error",
                        latency_ms=0,
                        intent_alignment=_align,
                    ))
                    last_result = _tool_feedback
                    iteration += 1
                    continue

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
                if _expectation and tool_result.get("status") not in ("diff_preview", "plan_proposal"):
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

                # Diff preview gate: yield checkpoint and wait for approval before writing
                if tool_result["status"] == "diff_preview":
                    try:
                        diff_data = json.loads(tool_result["content"])
                        rel_path = diff_data["rel_path"]
                        diff_text = diff_data["diff"]
                        yield {
                            "type": "agent_checkpoint",
                            "content": f"I'd like to write changes to `{rel_path}`.\n\nApprove this edit?",
                            "metadata": {
                                "requires_confirmation": True,
                                "checkpoint_tier": "file_write",
                                "diff_preview": diff_text,
                                "target_path": rel_path,
                                # Included so the resume handler can execute the write
                                "_write_path": diff_data["path"],
                                "_write_content": diff_data["content"],
                            },
                        }
                        user_response = yield
                        if user_response is False or user_response is None:
                            last_result = f"User rejected write to {rel_path}. Do not attempt this write again unless the user asks."
                            print(f"  [DIFF] Rejected by user: {rel_path}")
                        else:
                            # Approved — execute the write
                            write_path = diff_data["path"]
                            write_content = diff_data["content"]
                            os.makedirs(os.path.dirname(write_path) or ".", exist_ok=True)
                            with open(write_path, "w", encoding="utf-8") as _wf:
                                _wf.write(write_content)
                            last_result = f"Written {len(write_content)} chars to {rel_path}"
                            print(f"  [DIFF] Approved and written: {rel_path}")
                    except Exception as _diff_err:
                        last_result = f"Diff write failed: {_diff_err}"
                        print(f"  [DIFF] Error: {_diff_err}")
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
                iteration += 1

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

                # ── DONE-SHAPE GAP CHECK ─────────────────────────────────
                # Before accepting respond, compare the draft against the
                # success/absence criteria declared in the plan. Fire once
                # per run. If any slots are UNFILLED, bounce back with the gap
                # list and let the model decide whether to search more or defend.
                _sc = getattr(state, '_success_criteria', []) or []
                _ac = getattr(state, '_absence_criteria', []) or []
                _gap_fired = getattr(state, '_gap_check_fired', False)
                if (_sc or _ac) and not _gap_fired and iteration < self.max_iterations - 1:
                    state._gap_check_fired = True
                    # Summarize tool trail for the check prompt
                    _tool_trail = []
                    for _s in state.steps[-20:]:
                        _sd = _s.__dict__ if hasattr(_s, '__dict__') else _s
                        if _sd.get("action") == "tool_call":
                            _tool_trail.append(f"- {_sd.get('tool', '?')}({str(_sd.get('args', ''))[:120]})")
                    _trail_str = "\n".join(_tool_trail) if _tool_trail else "(no tool calls made yet)"
                    _criteria_str = ""
                    if _sc:
                        _criteria_str += "SUCCESS CRITERIA (what needs to be FILLED to answer yes):\n"
                        for i, c in enumerate(_sc, 1):
                            _criteria_str += f"  {i}. {c}\n"
                    if _ac:
                        _criteria_str += "ABSENCE CRITERIA (what needs to be ruled out to answer no/absent):\n"
                        for i, c in enumerate(_ac, 1):
                            _criteria_str += f"  {i}. {c}\n"
                    _gap_prompt = (
                        f"[DONE-SHAPE GAP CHECK — structural, not from the user]\n"
                        f"You declared this done-shape at the start of the run:\n\n"
                        f"{_criteria_str}\n"
                        f"Tool calls you've made:\n{_trail_str}\n\n"
                        f"Your draft response: \"{message[:300]}{'...' if len(message) > 300 else ''}\"\n\n"
                        f"For EACH criterion above, answer honestly: FILLED (with one sentence of evidence) or UNFILLED. "
                        f"If ALL are FILLED, respond with action=respond again and the same message to confirm. "
                        f"If ANY are UNFILLED, do NOT respond — issue the next tool_call that would fill the gap. "
                        f"Persistence is the expected behavior. Claiming absence without matching absence_criteria is not acceptable."
                    )
                    last_result = _gap_prompt
                    run_log.add_step(LogStep(
                        iteration=iteration, action="gap_check",
                        reasoning=f"criteria: {len(_sc)} success / {len(_ac)} absence",
                        latency_ms=brain_result.latency_ms,
                        intent_alignment=_align if '_align' in dir() else 0.5,
                    ))
                    print(f"  [DONE_SHAPE] Gap check fired — bouncing respond back to model")
                    yield {
                        "type": "thinking",
                        "content": f"[Gap check] Verifying {len(_sc)+len(_ac)} done-shape criteria before answering.",
                    }
                    iteration += 1
                    continue  # back to the loop

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

                # Emit followup suggestions if brain provided them
                _followups = decision.get("followups") or []
                _is_complete = decision.get("complete", True)
                if _followups or not _is_complete:
                    yield {
                        "type": "followup_suggest",
                        "followups": _followups[:4],  # max 4 suggestions
                        "complete": _is_complete,
                    }
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
            elif action == "spawn_agent":
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
                    result_preview=last_result[:300],
                    latency_ms=_spawn_result.elapsed_ms,
                ))
                iteration += 1
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

        # Layer 2b: Detect execution drift (tool category pivots)
        exec_drifts = detect_execution_drift(objective, run_log.steps)
        for d in exec_drifts:
            run_log.add_drift(d)
            print(f"  [EXEC_DRIFT] Step {d.at_step}: {d.description}")

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

        # ── Transformation verification gate ─────────────────────────────
        try:
            from personal_agent.agent_run_log import is_transformation_intent
            if is_transformation_intent(objective) and len(run_log.steps) > 0:
                # Collect before state: first file_read/search_code result
                _before_snippet = ""
                for _s in run_log.steps:
                    if _s.tool in ("file_read", "search_code") and _s.status == "ok" and _s.result_preview:
                        _before_snippet = _s.result_preview[:600]
                        break

                # Collect after state: last file_write result or last success
                _after_snippet = ""
                for _s in reversed(run_log.steps):
                    if _s.tool == "file_write" and _s.status == "ok" and _s.result_preview:
                        _after_snippet = _s.result_preview[:600]
                        break
                    elif _s.status == "ok" and _s.result_preview:
                        _after_snippet = _s.result_preview[:600]
                        break

                if _before_snippet or _after_snippet:
                    _verify_prompt = (
                        f"TRANSFORMATION VERIFICATION\n"
                        f"Requested: {objective[:300]}\n"
                        f"Before: {_before_snippet[:400]}\n"
                        f"After: {_after_snippet[:400]}\n\n"
                        f"Did this transformation achieve the requested goal? "
                        f"Answer strictly YES or NO on the first line, then a brief reason (1 sentence)."
                    )
                    try:
                        _verify_resp = self.brain.generate(
                            _verify_prompt,
                            system="You are a code verification assistant. Be strict. Answer YES only if the transformation clearly achieved its goal.",
                            max_tokens=150,
                            temperature=0.0,
                        )
                        _verify_text = (_verify_resp or "").strip()
                        _first_line = _verify_text.split("\n")[0].strip().upper()
                        run_log.transformation_verified = _first_line.startswith("YES")
                        run_log.verification_reason = _verify_text[:300]

                        # Mark last successful step as verified
                        for _s in reversed(run_log.steps):
                            if _s.status == "ok":
                                _s.verified = True if run_log.transformation_verified else _s.verified
                                break

                        if run_log.transformation_verified:
                            print(f"[TRANSFORM_VERIFY] PASSED: {run_log.verification_reason[:120]}")
                            yield {"type": "status", "content": "transformation verified",
                                   "metadata": {"verification": "passed", "reason": run_log.verification_reason}}
                        else:
                            print(f"[TRANSFORM_VERIFY] FAILED: {run_log.verification_reason[:120]}")
                            yield {"type": "status", "content": f"transformation check failed: {run_log.verification_reason[:200]}",
                                   "metadata": {"verification": "failed", "reason": run_log.verification_reason}}
                    except Exception as _ve:
                        print(f"[TRANSFORM_VERIFY] LLM error (non-fatal): {_ve}")
        except Exception as _te:
            print(f"[TRANSFORM_VERIFY] Setup error (non-fatal): {_te}")

        # Persist run log
        run_log.brain_ms = state.total_brain_ms
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
        print(f"  Brain time: {state.total_brain_ms:.0f}ms")
        print(f"  Tool time: {state.total_tool_ms:.0f}ms")
        print(f"  Total: {state.total_brain_ms + state.total_tool_ms:.0f}ms")
        print(f"{'='*60}")

        yield {"type": "done", "steps": len(state.steps),
               "brain_ms": state.total_brain_ms,
               "tool_ms": state.total_tool_ms,
               "run_id": run_log.run_id}


# Backwards-compatible alias
CookieOrchestrator = Orchestrator
