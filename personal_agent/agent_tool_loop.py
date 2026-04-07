"""Agentic Tool Loop — LLM-driven ReAct loop for the main chat pipeline.

Replaces the classify-once-execute-blind pattern with a true agentic loop:
  LLM sees tools → calls one or more → sees results → decides next action → repeat

Works with:
  - Local Ollama via chat_with_tools()
  - Cloud OpenAI/Claude via HybridLLMClient.chat_with_tools()

Checkpoint gates (Layer 3+) still fire — file_write, shell_exec, git_exec
require user confirmation before execution.

Sprint 14 / v3.1
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, field
from typing import Any, Dict, Generator, List, Optional

from personal_agent.tool_registry import (
    TOOL_REGISTRY,
    ToolDefinition,
    get_all_llm_schemas,
    get_routing_schemas,
)

try:
    from personal_agent.governance import GovernanceLayer, GovernanceTier
except ImportError:
    GovernanceLayer = None
    GovernanceTier = None

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# System prompt for the agentic loop LLM
# ---------------------------------------------------------------------------

_AGENT_TOOL_RULES = """
You have access to tools including persistent memory (memory_recall), web search, \
file operations, shell commands, and more. Use them to fulfill the user's request.

Rules:
1. Use the appropriate tool(s) for the request. Don't just describe what you'd do.
2. After each tool result, decide: need another tool, or can you respond?
3. For multi-step tasks, execute ALL steps — don't stop after the first.
4. When you have the information, respond with a natural text answer.
5. Be concise. Don't repeat raw tool output — interpret it.
6. Put ALL internal reasoning in <think> tags. Everything outside is shown verbatim.
7. Do NOT call the same tool more than 2 times with similar queries. If it returns \
no useful results twice, answer with what you have or say you don't know.
8. PREFER shell_exec for file operations (copy, move, rename, delete).
9. If a memory_recall returns facts about the user, use SECOND PERSON: \
"Your name is Nick", not "I'm Nick". User facts use "you/your".

IMPORTANT: You must ONLY use the tools provided. Do not invent tool names."""


def _get_agent_system_prompt() -> str:
    """Build agent system prompt using the shared static prefix + tool rules."""
    try:
        from .prompt_prefix import build_system_prompt
        return build_system_prompt(dynamic_parts=[_AGENT_TOOL_RULES])
    except ImportError:
        # Fallback if prompt_prefix not available
        from .prompt_prefix import get_static_prefix
        return get_static_prefix() + "\n" + _AGENT_TOOL_RULES


# ---------------------------------------------------------------------------
# Checkpoint / safety layer
# ---------------------------------------------------------------------------

# Tools at access_layer 3+ require user confirmation before execution
_CHECKPOINT_TOOLS = frozenset()  # Populated at module load from registry


def _get_checkpoint_tools() -> frozenset:
    """Return set of tool names that require checkpoint confirmation."""
    return frozenset(
        name for name, td in TOOL_REGISTRY.items()
        if td.checkpoint_tier != "none"
    )


def _needs_checkpoint(tool_name: str) -> bool:
    """Check if a tool call requires user confirmation."""
    td = TOOL_REGISTRY.get(tool_name)
    if not td:
        return True  # Unknown tools always need confirmation
    return td.checkpoint_tier != "none"


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class LoopStep:
    """One iteration of the agent loop."""
    iteration: int
    tool_name: str
    tool_args: Dict[str, Any]
    status: str = "pending"  # pending | executing | ok | error | checkpoint
    result_content: str = ""
    result_metadata: Dict[str, Any] = field(default_factory=dict)
    duration_ms: float = 0.0


@dataclass
class LoopResult:
    """Final result from the agent loop."""
    answer: str
    iterations: int
    steps: List[LoopStep]
    tools_used: List[str]
    total_duration_ms: float
    hit_max_iterations: bool = False


# ---------------------------------------------------------------------------
# Tool execution bridge
# ---------------------------------------------------------------------------

def _execute_tool(tool_name: str, tool_args: Dict[str, Any], thread_id: str,
                   engine=None) -> Dict[str, Any]:
    """Execute a registered tool and return the result.

    Returns dict with keys: content (str), status (str), metadata (dict).
    Reuses the same execution functions as CRTTaskAgent._run_* methods.

    Args:
        engine: Optional CRTEnhancedRAG instance for memory access.
    """
    try:
        if tool_name == "file_read":
            from personal_agent.file_tools import read_file, format_file_result
            result = read_file(tool_args.get("path", ""))
            text = format_file_result(result)
            has_error = "error" in result
            return {
                "content": text,
                "status": "error" if has_error else "ok",
                "metadata": {"tool_name": tool_name, "error": result.get("error") if has_error else None},
            }

        elif tool_name == "file_write":
            from personal_agent.file_tools import write_file
            from personal_agent.action_receipts import create_receipt, log_receipt
            path = tool_args.get("path", "")
            content = tool_args.get("content", "")
            result = write_file(path, content)
            has_error = "error" in result
            if not has_error:
                written = result.get("written_bytes", 0)
                created = result.get("created", False)
                diff_preview = result.get("diff_preview", "")
                action_desc = f"{'created' if created else 'wrote'} {written} bytes to {path}"
                receipt = create_receipt(
                    tool_name="file_write", action=action_desc, target=path,
                    result="success", reversible=not created and result.get("previous_content") is not None,
                    reverse_action="restore from previous content" if not created else None,
                    details={"written_bytes": written, "created": created, "diff_preview": diff_preview},
                )
                log_receipt(receipt, thread_id)
                return {"content": f"✓ {action_desc}", "status": "ok",
                        "metadata": {"tool_name": tool_name, "written_bytes": written, "created": created,
                                     "diff_preview": diff_preview, "receipt_id": receipt.receipt_id}}
            return {"content": f"✗ file write failed: {result.get('error')}",
                    "status": "error", "metadata": {"tool_name": tool_name, "error": result.get("error")}}

        elif tool_name == "dir_list":
            from personal_agent.file_tools import list_directory, format_dir_result
            result = list_directory(tool_args.get("path", ""))
            text = format_dir_result(result)
            has_error = "error" in result
            return {"content": text, "status": "error" if has_error else "ok",
                    "metadata": {"tool_name": tool_name, "error": result.get("error") if has_error else None}}

        elif tool_name == "project_scan":
            from personal_agent.file_tools import scan_project, format_project_result
            result = scan_project(tool_args.get("path", ""))
            text = format_project_result(result)
            has_error = "error" in result
            return {"content": text, "status": "error" if has_error else "ok",
                    "metadata": {"tool_name": tool_name, "error": result.get("error") if has_error else None}}

        elif tool_name == "search_code":
            import re as _re_search
            from pathlib import Path as _Path_search
            pattern = tool_args.get("pattern", "")
            search_path = _Path_search(tool_args.get("path", "D:/AI_round2"))
            glob_filter = tool_args.get("glob", "*.py")
            max_results = int(tool_args.get("max_results", 30))

            if not pattern:
                return {"content": "Error: pattern is required", "status": "error",
                        "metadata": {"tool_name": tool_name}}

            try:
                compiled = _re_search.compile(pattern, _re_search.IGNORECASE)
            except _re_search.error:
                compiled = None  # fall back to literal match

            matches = []
            skip_dirs = {".git", "__pycache__", "node_modules", ".venv", "venv", ".mypy_cache", "dist", "build"}
            try:
                for fpath in search_path.rglob(glob_filter):
                    if any(skip in fpath.parts for skip in skip_dirs):
                        continue
                    if not fpath.is_file() or fpath.stat().st_size > 500_000:
                        continue
                    try:
                        text = fpath.read_text(encoding="utf-8", errors="ignore")
                        for i, line in enumerate(text.splitlines(), 1):
                            hit = (compiled.search(line) if compiled else pattern.lower() in line.lower())
                            if hit:
                                rel = fpath.relative_to(search_path)
                                matches.append(f"{rel}:{i}: {line.strip()[:120]}")
                                if len(matches) >= max_results:
                                    break
                    except Exception:
                        continue
                    if len(matches) >= max_results:
                        break
            except Exception as e:
                return {"content": f"Search failed: {e}", "status": "error",
                        "metadata": {"tool_name": tool_name}}

            output = "\n".join(matches) if matches else f"No matches found for '{pattern}'"
            return {"content": output, "status": "ok",
                    "metadata": {"tool_name": tool_name, "matches": len(matches)}}

        elif tool_name == "shell_exec":
            from personal_agent.shell_tools import execute_command
            from personal_agent.action_receipts import create_receipt, log_receipt
            command = tool_args.get("command", "")
            cwd = tool_args.get("cwd", "D:/AI_round2")
            timeout = tool_args.get("timeout", 30)
            result = execute_command(command, cwd=cwd, timeout=timeout)
            has_error = "error" in result
            if not has_error:
                exit_code = result.get("exit_code", -1)
                stdout = result.get("stdout", "")
                stderr = result.get("stderr", "")
                duration_ms = result.get("duration_ms", 0)
                stdout_lines = stdout.splitlines()
                preview = "\n".join(stdout_lines[:50])
                if len(stdout_lines) > 50:
                    preview += f"\n... ({len(stdout_lines) - 50} more lines)"
                receipt = create_receipt(
                    tool_name="shell_exec", action=f"ran `{command}` — exit code {exit_code}",
                    target=command, result="success" if exit_code == 0 else "error",
                    reversible=False,
                    details={"exit_code": exit_code, "stdout": stdout[:2000], "stderr": stderr[:1000]},
                )
                log_receipt(receipt, thread_id)
                output_text = f"✓ exit={exit_code}  {duration_ms}ms\n{preview}" if exit_code == 0 else f"✗ exit={exit_code}\n{preview}"
                return {"content": output_text, "status": "ok",
                        "metadata": {"tool_name": tool_name, "exit_code": exit_code,
                                     "duration_ms": duration_ms, "receipt_id": receipt.receipt_id}}
            return {"content": f"✗ command failed: {result.get('error')}",
                    "status": "error", "metadata": {"tool_name": tool_name, "error": result.get("error")}}

        elif tool_name == "git_exec":
            from personal_agent.shell_tools import execute_git
            from personal_agent.action_receipts import create_receipt, log_receipt
            args = tool_args.get("args", [])
            cwd = tool_args.get("cwd", "D:/AI_round2")
            result = execute_git(args, cwd=cwd)
            has_error = "error" in result
            if not has_error:
                exit_code = result.get("exit_code", -1)
                stdout = result.get("stdout", "")
                stderr = result.get("stderr", "")
                duration_ms = result.get("duration_ms", 0)
                command = result.get("command", f"git {' '.join(args)}")
                output = stdout or stderr
                receipt = create_receipt(
                    tool_name="git", action=f"executed `{command}` — exit code {exit_code}",
                    target=command, result="success" if exit_code == 0 else "error",
                    reversible=args[0] in ("commit", "add", "stash", "checkout", "branch") if args else False,
                    details={"exit_code": exit_code, "stdout": stdout[:2000], "stderr": stderr[:1000]},
                )
                log_receipt(receipt, thread_id)
                return {"content": f"✓ {command} — exit={exit_code}\n{output[:1000]}",
                        "status": "ok", "metadata": {"tool_name": tool_name, "exit_code": exit_code,
                                                      "duration_ms": duration_ms, "receipt_id": receipt.receipt_id}}
            return {"content": f"✗ git failed: {result.get('error')}",
                    "status": "error", "metadata": {"tool_name": tool_name, "error": result.get("error")}}

        elif tool_name == "web_search":
            from personal_agent.web_search import WebSearchTool
            query = tool_args.get("query", "")
            searcher = WebSearchTool()
            response = searcher.search(query)
            results_text = response.to_context_string()
            if response.results:
                return {"content": results_text[:3000], "status": "ok",
                        "metadata": {"tool_name": tool_name, "result_count": len(response.results)}}
            return {"content": f"✗ web search returned no results for: {query}",
                    "status": "error", "metadata": {"tool_name": tool_name, "error": "no results"}}

        elif tool_name == "system_info":
            import platform, psutil, shutil
            cpu_pct = psutil.cpu_percent(interval=0.5)
            mem = psutil.virtual_memory()
            disk = shutil.disk_usage("/")
            gpu_info = "N/A"
            try:
                import subprocess as _sp
                _nv = _sp.run(["nvidia-smi", "--query-gpu=name,utilization.gpu,memory.used,memory.total",
                               "--format=csv,noheader,nounits"], capture_output=True, text=True, timeout=5)
                if _nv.returncode == 0 and _nv.stdout.strip():
                    gpu_info = _nv.stdout.strip()
            except Exception:
                pass
            formatted = (
                f"OS: {platform.system()} {platform.release()} ({platform.machine()})\n"
                f"CPU: {cpu_pct}% ({psutil.cpu_count()} cores)\n"
                f"RAM: {mem.used // (1024**3)}GB / {mem.total // (1024**3)}GB ({mem.percent}%)\n"
                f"Disk: {disk.used // (1024**3)}GB / {disk.total // (1024**3)}GB ({100 * disk.used // disk.total}%)\n"
                f"GPU: {gpu_info}"
            )
            return {"content": formatted, "status": "ok",
                    "metadata": {"tool_name": tool_name}}

        elif tool_name == "fetch_url":
            import urllib.request
            url = tool_args.get("url", "")
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (CRT-Aether/1.0)"})
            with urllib.request.urlopen(req, timeout=15) as resp:
                text = resp.read().decode("utf-8", errors="replace")
            return {"content": text[:5000], "status": "ok",
                    "metadata": {"tool_name": tool_name, "byte_count": len(text)}}

        elif tool_name == "memory_recall":
            query = tool_args.get("query", "").strip()
            if not query:
                return {"content": "(no query provided)", "status": "error",
                        "metadata": {"tool_name": tool_name}}
            if engine is not None and hasattr(engine, "memory"):
                results = engine.memory.retrieve_memories(query, k=5)
                if results:
                    lines = []
                    for mem, score in results:
                        text = getattr(mem, "text", str(mem))
                        trust = getattr(mem, "trust", None)
                        trust_tag = f" [trust={trust:.2f}]" if trust is not None else ""
                        lines.append(f"- {text}{trust_tag} (score={score:.3f})")
                    return {"content": "\n".join(lines), "status": "ok",
                            "metadata": {"tool_name": tool_name, "result_count": len(results)}}
                return {"content": "(no matching memories found)", "status": "ok",
                        "metadata": {"tool_name": tool_name, "result_count": 0}}
            return {"content": "(memory system not available)", "status": "error",
                    "metadata": {"tool_name": tool_name}}

        elif tool_name == "gpt_log_search":
            query = tool_args.get("query", "").strip()
            if not query:
                return {"content": "(no query provided)", "status": "error",
                        "metadata": {"tool_name": tool_name}}
            try:
                from personal_agent.gpt_log_store import get_gpt_log_store
                store = get_gpt_log_store()
                top_k = tool_args.get("top_k", 10)
                role = tool_args.get("role")
                results = store.search(query, top_k=top_k, role_filter=role)
                if results:
                    import datetime
                    lines = []
                    for r in results:
                        dt = datetime.datetime.fromtimestamp(r.timestamp) if r.timestamp else None
                        date_str = dt.strftime("%Y-%m-%d") if dt else "?"
                        lines.append(
                            f"- [{r.role}] (score={r.score:.3f}, {date_str}, conv=\"{r.conv_title}\", msg_id={r.msg_id})\n  {r.text[:400]}"
                        )
                    return {"content": "\n".join(lines), "status": "ok",
                            "metadata": {"tool_name": tool_name, "result_count": len(results)}}
                return {"content": "(no matching GPT log messages found)", "status": "ok",
                        "metadata": {"tool_name": tool_name, "result_count": 0}}
            except Exception as e:
                return {"content": f"(GPT log search failed: {e})", "status": "error",
                        "metadata": {"tool_name": tool_name}}

        elif tool_name == "gpt_log_context":
            msg_id = tool_args.get("msg_id", "").strip()
            if not msg_id:
                return {"content": "(no msg_id provided)", "status": "error",
                        "metadata": {"tool_name": tool_name}}
            try:
                from personal_agent.gpt_log_store import get_gpt_log_store
                import datetime
                store = get_gpt_log_store()
                window = tool_args.get("window", 5)
                messages = store.get_message_context(msg_id, window=window)
                if messages:
                    lines = []
                    for m in messages:
                        dt = datetime.datetime.fromtimestamp(m.timestamp) if m.timestamp else None
                        ts = dt.strftime("%H:%M:%S") if dt else "?"
                        marker = " <<<" if m.msg_id == msg_id else ""
                        lines.append(f"[{m.role} {ts}]{marker}\n{m.text[:600]}")
                    return {"content": "\n\n".join(lines), "status": "ok",
                            "metadata": {"tool_name": tool_name, "message_count": len(messages)}}
                return {"content": "(message not found)", "status": "error",
                        "metadata": {"tool_name": tool_name}}
            except Exception as e:
                return {"content": f"(GPT log context failed: {e})", "status": "error",
                        "metadata": {"tool_name": tool_name}}

        elif tool_name == "gpt_log_promote":
            msg_id = tool_args.get("msg_id", "").strip()
            if not msg_id:
                return {"content": "(no msg_id provided)", "status": "error",
                        "metadata": {"tool_name": tool_name}}
            try:
                from personal_agent.gpt_log_store import get_gpt_log_store
                store = get_gpt_log_store()
                memory_id = store.promote_to_crt(msg_id, engine)
                if memory_id:
                    return {"content": f"Promoted to CRT memory: {memory_id}", "status": "ok",
                            "metadata": {"tool_name": tool_name, "memory_id": memory_id}}
                return {"content": "(message not found in GPT logs)", "status": "error",
                        "metadata": {"tool_name": tool_name}}
            except Exception as e:
                return {"content": f"(GPT log promote failed: {e})", "status": "error",
                        "metadata": {"tool_name": tool_name}}

        elif tool_name == "inquiry_queue":
            # Phase G4: Active inference — show what the agent is uncertain about
            try:
                from personal_agent.heartbeat_system import HeartbeatScheduler
                queue = HeartbeatScheduler.get_inquiry_queue()
                if queue:
                    lines = []
                    for inq in queue[:10]:
                        lines.append(
                            f"- [{inq.urgency.value.upper()}] {inq.question} "
                            f"(type={inq.uncertainty_type.value}, gain={inq.expected_info_gain:.2f})"
                        )
                    return {"content": "\n".join(lines), "status": "ok",
                            "metadata": {"tool_name": tool_name, "count": len(queue)}}
                return {"content": "(no open inquiries — belief state is stable)", "status": "ok",
                        "metadata": {"tool_name": tool_name, "count": 0}}
            except Exception as e:
                return {"content": f"(inquiry queue unavailable: {e})", "status": "error",
                        "metadata": {"tool_name": tool_name}}

        elif tool_name == "generate_content":
            # Content generation is handled by the LLM itself in loop mode
            return {"content": "(use your own generation capability to produce the content, then call file_write to save it)",
                    "status": "ok", "metadata": {"tool_name": tool_name}}

        elif tool_name == "create_commitment":
            intent_text = tool_args.get("intent", "")
            description = tool_args.get("description", intent_text)
            # If there's a deadline, treat as a scheduled reminder
            deadline = tool_args.get("deadline")
            if deadline and engine is None:
                # No engine — try scheduled tasks
                try:
                    from personal_agent.scheduled_tasks import create_scheduled_task
                    from datetime import datetime
                    task_id = f"reminder_{thread_id}_{int(time.time() * 1000)}"
                    create_scheduled_task(task_id, thread_id, intent_text, datetime.fromisoformat(deadline))
                    return {"content": f"✓ Reminder set: {intent_text}", "status": "ok",
                            "metadata": {"tool_name": tool_name}}
                except Exception as e:
                    return {"content": f"✗ Failed to create reminder: {e}", "status": "error",
                            "metadata": {"tool_name": tool_name, "error": str(e)}}
            # No deadline — store as a memory fact
            if engine is not None and hasattr(engine, "memory"):
                try:
                    from personal_agent.crt_core import MemorySource
                    fact_text = description or intent_text
                    engine.memory.store_memory(
                        fact_text,
                        confidence=0.9,
                        source=MemorySource.USER,
                        context={"origin": "agent_loop", "thread_id": thread_id},
                    )
                    return {"content": f"✓ Stored: {fact_text}", "status": "ok",
                            "metadata": {"tool_name": tool_name}}
                except Exception as e:
                    return {"content": f"✗ Failed to store: {e}", "status": "error",
                            "metadata": {"tool_name": tool_name, "error": str(e)}}
            return {"content": f"✓ Noted: {intent_text} (not persisted — no memory system)",
                    "status": "ok", "metadata": {"tool_name": tool_name}}

        elif tool_name == "list_commitments":
            from personal_agent.scheduled_tasks import list_reminders
            reminders = list_reminders(thread_id=thread_id)
            if not reminders:
                return {"content": "No active reminders.", "status": "ok",
                        "metadata": {"tool_name": tool_name}}
            lines = [f"- {r.get('intent', '?')} (due: {r.get('deadline', 'unset')})" for r in reminders]
            return {"content": "\n".join(lines), "status": "ok",
                    "metadata": {"tool_name": tool_name, "count": len(reminders)}}

        elif tool_name == "cancel_commitment":
            from personal_agent.scheduled_tasks import cancel_reminder
            search = tool_args.get("commitment_id", "")
            result = cancel_reminder(search_term=search, thread_id=thread_id)
            return {"content": f"✓ Cancelled: {search}", "status": "ok",
                    "metadata": {"tool_name": tool_name}}

        else:
            return {"content": f"Tool '{tool_name}' is not yet supported in the agentic loop.",
                    "status": "error", "metadata": {"tool_name": tool_name, "error": "unsupported_tool"}}

    except Exception as e:
        logger.error("[AGENT_LOOP] Tool %s execution error: %s", tool_name, e, exc_info=True)
        return {"content": f"✗ {tool_name} failed: {e}",
                "status": "error", "metadata": {"tool_name": tool_name, "error": str(e)}}


# ---------------------------------------------------------------------------
# AgentToolLoop — the core class
# ---------------------------------------------------------------------------

class AgentToolLoop:
    """LLM-driven agentic tool loop.

    Sends conversation + tool definitions to the LLM. The LLM decides which
    tools to call. After each tool execution, results are appended to the
    conversation and the LLM decides again. Repeats until the LLM responds
    with text (no tool calls) or max_iterations is reached.

    Yields SSE-compatible event dicts throughout for real-time UI updates.
    """

    def __init__(
        self,
        llm_client,
        *,
        session_db=None,
        max_iterations: int = 10,
        show_thinking: bool = True,
        engine=None,
        intent_hint: Optional[str] = None,
        retrieval_count: int = 0,
        retrieval_avg_trust: float = 0.0,
    ):
        self.llm_client = llm_client
        self.session_db = session_db
        self.max_iterations = max_iterations
        self.show_thinking = show_thinking
        self.engine = engine
        self.intent_hint = intent_hint
        self.retrieval_count = retrieval_count
        self.retrieval_avg_trust = retrieval_avg_trust

        # Governance layer — immune agents watching response boundary
        try:
            self._governance = GovernanceLayer() if GovernanceLayer else None
        except Exception:
            self._governance = None

    def run(
        self,
        message: str,
        thread_id: str,
        *,
        conversation_history: Optional[List[Dict[str, str]]] = None,
        tool_filter: Optional[List[str]] = None,
    ) -> Generator[Dict[str, Any], Optional[bool], None]:
        """Execute the agentic loop. Yields SSE event dicts.

        The generator can receive checkpoint confirmation via .send(True/False).
        When a checkpoint is hit, the generator yields a checkpoint event and
        pauses. The caller sends True to confirm or False to deny.

        Args:
            message: User's message
            thread_id: Session thread ID
            conversation_history: Recent conversation for context
            tool_filter: Optional list of tool names to include (None = all)

        Yields:
            SSE event dicts with types: agent_step, agent_result, agent_thinking,
            agent_checkpoint, agent_complete, tool_start, tool_result, task_done, token
        """
        start_time = time.time()
        steps: List[LoopStep] = []
        tools_used: List[str] = []

        # Build tool schemas for the LLM
        tool_schemas = self._build_tool_schemas(tool_filter)

        # Build conversation messages
        messages = self._build_messages(message, conversation_history, thread_id=thread_id)

        # Inject intent context so the LLM knows what to do on iteration 1
        if self.intent_hint and messages and messages[0].get("role") == "system":
            messages[0]["content"] += (
                f"\n\nINTENT CONTEXT: {self.intent_hint}\n"
                "Use the most relevant tool once — if it returns no useful results, "
                "answer with what you know. Do not retry the same tool."
            )

        yield {
            "type": "agent_loop_start",
            "content": "Starting agentic tool loop",
            "metadata": {
                "max_iterations": self.max_iterations,
                "tools_available": [s["function"]["name"] for s in tool_schemas],
            },
        }

        _loop_generation_source = ""  # Tracks actual generation source across iterations

        for iteration in range(self.max_iterations):
            logger.info("[AGENT_LOOP] Iteration %d/%d", iteration + 1, self.max_iterations)
            _total_msg_chars = sum(len(str(m.get("content", ""))) for m in messages)
            print(f"[AGENT_LOOP_DEBUG] Iteration {iteration+1}: {len(messages)} messages, ~{_total_msg_chars} chars total")

            # ── 1. Call LLM with tools ─────────────────────────────────────
            try:
                llm_response = self.llm_client.chat_with_tools(
                    messages,
                    tools=tool_schemas,
                    max_tokens=2000,
                    temperature=0.1,
                )
            except Exception as e:
                print(f"[AGENT_LOOP_DEBUG] LLM call FAILED: {e}")
                logger.error("[AGENT_LOOP] LLM call failed: %s", e)
                yield {
                    "type": "token",
                    "content": f"I encountered an error while thinking: {e}",
                }
                break

            # ── 2. Check if LLM returned text (no tool calls) ─────────────
            _resp_gen_source = llm_response.get("generation_source", "")
            if _resp_gen_source:
                # Track the last known generation source for the completion event
                _loop_generation_source = _resp_gen_source
            print(f"[AGENT_LOOP_DEBUG] Raw LLM response keys={list(llm_response.keys())} used_tools={llm_response.get('used_tools')}")
            tool_calls = llm_response.get("tool_calls", [])
            text_content = (llm_response.get("content") or "").strip()

            print(f"[AGENT_LOOP_DEBUG] iter={iteration+1}  tool_calls={len(tool_calls)}  text_len={len(text_content)}  text_preview={text_content[:200] if text_content else '(empty)'}")
            if tool_calls:
                for _tc_dbg in tool_calls:
                    print(f"[AGENT_LOOP_DEBUG]   tool: {_tc_dbg.get('name')}  args_keys={list(_tc_dbg.get('arguments', {}).keys()) if isinstance(_tc_dbg.get('arguments'), dict) else 'raw'}")

            if not tool_calls:
                # LLM is done — emit final answer
                if text_content:
                    # Strip <think> tags for display
                    from personal_agent.text_utils import strip_thinking_tags, extract_think_content
                    think_content = extract_think_content(text_content)
                    clean_text = strip_thinking_tags(text_content)

                    # Unwrap JSON-wrapped responses from models like gemma3
                    # that sometimes return {"response": "actual text"} instead of plain text
                    if clean_text.strip().startswith('{"response"'):
                        try:
                            import json as _json_unwrap
                            _parsed = _json_unwrap.loads(clean_text.strip())
                            if isinstance(_parsed, dict) and "response" in _parsed:
                                clean_text = str(_parsed["response"])
                                print("[AGENT_LOOP_DEBUG] Unwrapped JSON-wrapped response from model")
                        except Exception:
                            pass  # Not valid JSON, keep original

                    if think_content and self.show_thinking:
                        yield {
                            "type": "agent_thinking_token",
                            "content": think_content,
                            "metadata": {"step": "final_reasoning"},
                        }

                    # --- Governance gate ---
                    if self._governance:
                        # Compute belief confidence from what actually happened:
                        # - Did memory tools run and return results? → grounded
                        # - Was this a cookie fallback with no tools? → ungrounded
                        # - More successful tool steps → higher confidence
                        _memory_steps = [s for s in steps if s.tool_name == "memory_recall" and s.status == "ok"]
                        _any_tools_succeeded = any(s.status == "ok" for s in steps)
                        _was_fallback = not _any_tools_succeeded and iteration == 0

                        if _memory_steps:
                            _belief_conf = min(0.8, 0.4 + 0.1 * len(_memory_steps))
                        elif self.retrieval_count > 0:
                            # Memories were retrieved pre-loop (context assembly).
                            # Scale belief by retrieval count and average trust.
                            _belief_conf = min(0.75, 0.3 + 0.05 * self.retrieval_count)
                            if self.retrieval_avg_trust > 0.7:
                                _belief_conf = min(0.8, _belief_conf + 0.1)
                        elif self.engine is not None and _was_fallback:
                            # Cookie fallback with no tool steps, but engine has context.
                            # Check system prompt for memory injection and count them.
                            try:
                                _sys_msg = next((m.get("content", "") for m in messages if m.get("role") == "system"), "")
                                # Count how many memory entries appear in the system prompt
                                _mem_cite_count = _sys_msg.count("trust:") + _sys_msg.count("T:0.") + _sys_msg.count("T:1.")
                                _has_memories = "memories cited" in _sys_msg.lower() or _mem_cite_count > 0
                                if _has_memories:
                                    # Scale by memory count: more grounding = higher belief
                                    # but cookie fallback caps at 0.55 (unverified synthesis)
                                    _belief_conf = min(0.55, 0.25 + 0.04 * min(_mem_cite_count, 8))
                                else:
                                    _belief_conf = 0.15
                            except Exception:
                                _belief_conf = 0.15
                        elif _any_tools_succeeded:
                            _belief_conf = 0.4  # tools ran but no memory grounding
                        elif _was_fallback:
                            _belief_conf = 0.15  # cookie/cloud fallback, no tools, no grounding
                        else:
                            _belief_conf = 0.3  # multiple iterations but no memory

                        # Adjust based on response assertiveness vs hedging
                        # Assertive claims about the user need higher grounding to be credible
                        _text_lower = clean_text.lower()
                        _assertive_markers = ["you are ", "you always ", "you never ", "you definitely ",
                                              "you clearly ", "you obviously ", "you have always"]
                        _hedge_markers = ["i think", "i believe", "might be", "may be", "possibly",
                                          "perhaps", "it seems", "i'm not certain", "i'm not sure",
                                          "could be", "i'd guess"]
                        _assertive_count = sum(1 for m in _assertive_markers if m in _text_lower)
                        _hedge_count = sum(1 for m in _hedge_markers if m in _text_lower)
                        # Assertive claims without strong grounding → lower belief
                        if _assertive_count >= 2 and _belief_conf < 0.6:
                            _belief_conf = max(0.10, _belief_conf - 0.08 * min(_assertive_count, 3))
                        # Explicit hedging is honest → small boost
                        if _hedge_count >= 2:
                            _belief_conf = min(0.75, _belief_conf + 0.04)

                        _gov = self._governance.govern_response(
                            text=clean_text,
                            belief_confidence=_belief_conf,
                        )
                        print(f"[GOVERNANCE] tier={_gov.tier.value}, belief={_belief_conf:.2f}, annotations={len(_gov.annotations)}, block={_gov.should_block}")
                        if _gov.annotations:
                            for _ann in _gov.annotations:
                                print(f"[GOVERNANCE]   {_ann.agent}: {_ann.finding[:120]}")
                        if _gov.should_block:
                            _findings = "; ".join(a.finding for a in _gov.annotations)
                            clean_text = (
                                f"[GOVERNANCE ESCALATION: {_findings}]\n\n"
                                f"The following response has been flagged by the immune system. "
                                f"Review the findings above before relying on this answer.\n\n"
                                f"{clean_text}"
                            )

                    print(f"[AGENT_LOOP_DEBUG] Emitting final token, len={len(clean_text)}, preview={clean_text[:200]}")
                    yield {"type": "token", "content": clean_text}
                else:
                    if iteration == 0:
                        # First iteration empty — retry once with a nudge
                        print("[AGENT_LOOP_DEBUG] Empty response on iter 0, retrying with nudge")
                        messages.append({
                            "role": "user",
                            "content": "You returned an empty response. Please either call a tool or provide a text answer to my question.",
                        })
                        continue
                    print("[AGENT_LOOP_DEBUG] No tool_calls AND empty text — emitting fallback")
                    _fallback = "I wasn't able to process that request. Could you try rephrasing?"
                    yield {"type": "token", "content": _fallback}
                break

            # ── 2b. Repetition guard — stop if same tool called 3+ times ──
            _tool_name_this = tool_calls[0].get("name", "") if tool_calls else ""
            _same_tool_count = sum(
                1 for s in steps if s.tool_name == _tool_name_this
            )
            if _same_tool_count >= 3:
                print(f"[AGENT_LOOP_DEBUG] Repetition guard: {_tool_name_this} called {_same_tool_count} times, forcing answer")
                # Inject a nudge message and let the LLM answer without tools
                messages.append({
                    "role": "user",
                    "content": (
                        f"You have already called {_tool_name_this} {_same_tool_count} times. "
                        "Stop calling tools and answer with what you have. "
                        "If you don't have the information, say so."
                    ),
                })
                # Re-call LLM without tools to force a text answer
                try:
                    _forced = self.llm_client.chat_with_tools(
                        messages, tools=[], max_tokens=1000, temperature=0.1,
                    )
                    _forced_text = (_forced.get("content") or "").strip()
                    if _forced_text:
                        from personal_agent.text_utils import strip_thinking_tags
                        _forced_text = strip_thinking_tags(_forced_text)
                        # Unwrap JSON-wrapped responses
                        if _forced_text.startswith('{"response"'):
                            try:
                                import json as _json_f
                                _pf = _json_f.loads(_forced_text)
                                if isinstance(_pf, dict) and "response" in _pf:
                                    _forced_text = str(_pf["response"])
                            except Exception:
                                pass
                        print(f"[AGENT_LOOP_DEBUG] Forced answer: {_forced_text[:200]}")
                        yield {"type": "token", "content": _forced_text}
                    else:
                        yield {"type": "token", "content": "I couldn't find that information in my memory."}
                except Exception as _fe:
                    print(f"[AGENT_LOOP_DEBUG] Forced answer failed: {_fe}")
                    yield {"type": "token", "content": "I couldn't find that information in my memory."}
                break

            # ── 3. Process each tool call ──────────────────────────────────
            for tc in tool_calls:
                tool_name = tc.get("name", "")
                tool_args = tc.get("arguments", {})
                if isinstance(tool_args, str):
                    try:
                        tool_args = json.loads(tool_args)
                    except (json.JSONDecodeError, TypeError):
                        tool_args = {}

                step = LoopStep(
                    iteration=iteration,
                    tool_name=tool_name,
                    tool_args=tool_args,
                )
                steps.append(step)

                # ── 3a. Emit thinking/reasoning if present ─────────────
                if text_content and self.show_thinking:
                    from personal_agent.text_utils import strip_thinking_tags, extract_think_content
                    think_content = extract_think_content(text_content)
                    reasoning = strip_thinking_tags(text_content).strip()

                    if think_content:
                        yield {
                            "type": "agent_thinking_token",
                            "content": think_content,
                            "metadata": {"step": f"iteration_{iteration}"},
                        }
                    if reasoning:
                        yield {
                            "type": "agent_thinking_token",
                            "content": reasoning,
                            "metadata": {"step": f"reasoning_{iteration}"},
                        }
                    text_content = ""  # Only emit once per iteration

                # ── 3b. Checkpoint gate for Layer 3+ tools ─────────────
                print(f"[AGENT_LOOP_DEBUG] Tool={tool_name} needs_checkpoint={_needs_checkpoint(tool_name)}")
                if _needs_checkpoint(tool_name):
                    td = TOOL_REGISTRY.get(tool_name)
                    tier = td.checkpoint_tier if td else "high"

                    # Build human-readable description
                    action_desc = _describe_tool_action(tool_name, tool_args)

                    yield {
                        "type": "agent_checkpoint",
                        "content": f"Before I do that, I need your go-ahead to {action_desc}.",
                        "metadata": {
                            "requires_confirmation": True,
                            "checkpoint_tier": tier,
                            "tool_name": tool_name,
                            "tool_args": tool_args,
                            "iteration": iteration,
                            "intent": tool_name,
                            "confidence": 0.95,
                            "slots": tool_args,
                        },
                    }

                    # Pause for confirmation — caller sends True/False via .send()
                    confirmation = yield

                    if confirmation is False or confirmation is None:
                        # User denied — tell the LLM and continue the loop
                        step.status = "denied"
                        step.result_content = "User denied this action."

                        _deny_tc_id = f"call_{iteration}_{tool_name}_denied"
                        messages.append({
                            "role": "assistant",
                            "content": "",
                            "tool_calls": [{"id": _deny_tc_id, "type": "function",
                                            "function": {"name": tool_name,
                                                        "arguments": tool_args}}],
                        })
                        messages.append({
                            "role": "tool",
                            "tool_call_id": _deny_tc_id,
                            "name": tool_name,
                            "content": "User denied this action. Adapt your approach or ask the user what they'd like instead.",
                        })

                        yield {
                            "type": "tool_result",
                            "content": "Action denied by user.",
                            "metadata": {"tool_name": tool_name, "status": "denied",
                                        "step_index": len(steps) - 1},
                        }
                        continue  # Next tool call or next iteration

                # ── 3c. Execute the tool ───────────────────────────────
                step.status = "executing"
                yield {
                    "type": "tool_start",
                    "content": f"▷ {tool_name}",
                    "metadata": {"tool_name": tool_name, "input": tool_args,
                                "step_index": len(steps) - 1},
                }

                # Extract expectation before execution
                _atl_expectation = None
                try:
                    from personal_agent.tool_verification import (
                        extract_expectation as _atl_extract,
                        verify_tool_result as _atl_verify,
                        get_session_stats as _atl_stats,
                    )
                    # Use tool name + args as reasoning proxy (no think text in tool-calling mode)
                    _atl_reasoning = f"calling {tool_name} with {json.dumps(tool_args)[:200]}"
                    _atl_expectation = _atl_extract(tool_name, tool_args, _atl_reasoning)
                except ImportError:
                    pass

                t0 = time.time()
                result = _execute_tool(tool_name, tool_args, thread_id, engine=self.engine)
                elapsed_ms = (time.time() - t0) * 1000

                # Verify result against expectation
                _atl_result = None
                if _atl_expectation:
                    try:
                        _atl_result = _atl_verify(
                            _atl_expectation,
                            result_content=result.get("content", "") or "",
                            result_status=result.get("status", "ok"),
                        )
                        _atl_stats().record(_atl_result)
                        if _atl_result.surprise != "none":
                            print(f"  [VERIFY] {_atl_result.surprise}: {tool_name}")
                    except Exception:
                        pass

                # Persist verification + model attribution to the receipt
                _receipt_id = (result.get("metadata") or {}).get("receipt_id")
                if _receipt_id:
                    try:
                        from personal_agent.action_receipts import update_receipt_verification
                        _model_attr = getattr(self.llm_client, "model", None) or "unknown"
                        _step_id = f"step_{iteration}_{tool_name}"
                        if _atl_result:
                            update_receipt_verification(
                                receipt_id=_receipt_id,
                                verification_passed=_atl_result.status_match and _atl_result.surprise == "none",
                                verification_reason=_atl_result.details,
                                expectation_keywords=_atl_expectation.expected_content if _atl_expectation else None,
                                run_step_id=_step_id,
                                model_attribution=_model_attr,
                            )
                        else:
                            # No verification available, still record model attribution
                            update_receipt_verification(
                                receipt_id=_receipt_id,
                                verification_passed=True,  # no verification = assumed pass
                                verification_reason="no expectation extracted",
                                run_step_id=_step_id,
                                model_attribution=_model_attr,
                            )
                    except Exception:
                        pass

                step.status = result["status"]
                step.result_content = result["content"]
                step.result_metadata = result.get("metadata", {})
                step.duration_ms = elapsed_ms

                if tool_name not in tools_used:
                    tools_used.append(tool_name)

                yield {
                    "type": "tool_result",
                    "content": result["content"][:500],  # Truncate for SSE
                    "metadata": {
                        **result.get("metadata", {}),
                        "status": result["status"],
                        "step_index": len(steps) - 1,
                        "duration_ms": round(elapsed_ms),
                    },
                }

                # ── 3d. Append tool call + result to messages ──────────
                # Include synthetic tool_call_id so OpenAI message history stays consistent.
                _tc_id = f"call_{iteration}_{tool_name}"
                messages.append({
                    "role": "assistant",
                    "content": "",
                    "tool_calls": [{"id": _tc_id, "type": "function",
                                    "function": {"name": tool_name,
                                                "arguments": tool_args}}],
                })
                messages.append({
                    "role": "tool",
                    "tool_call_id": _tc_id,
                    "name": tool_name,
                    "content": result["content"][:4000],  # Keep context manageable
                })

        else:
            # Hit max iterations
            logger.warning("[AGENT_LOOP] Hit max iterations (%d)", self.max_iterations)
            yield {
                "type": "token",
                "content": f"I've completed {self.max_iterations} steps. Here's what I've done so far based on the results above.",
            }

        # ── Transformation verification gate ─────────────────────────────
        _transformation_verified = None
        _verification_reason = None
        try:
            from personal_agent.agent_run_log import is_transformation_intent
            if is_transformation_intent(message) and len(steps) > 0:
                # Collect before state: first file_read or search_code result
                _before_snippet = ""
                for _s in steps:
                    if _s.tool_name in ("file_read", "search_code") and _s.status == "ok" and _s.result_content:
                        _before_snippet = _s.result_content[:600]
                        break

                # Collect after state: last file_write result, or last successful result
                _after_snippet = ""
                for _s in reversed(steps):
                    if _s.tool_name == "file_write" and _s.status == "ok" and _s.result_content:
                        _after_snippet = _s.result_content[:600]
                        break
                    elif _s.status == "ok" and _s.result_content:
                        _after_snippet = _s.result_content[:600]
                        break

                # Only verify if we have at least some state to check
                if _before_snippet or _after_snippet:
                    _verify_prompt = (
                        f"TRANSFORMATION VERIFICATION\n"
                        f"Requested: {message[:300]}\n"
                        f"Before: {_before_snippet[:400]}\n"
                        f"After: {_after_snippet[:400]}\n\n"
                        f"Did this transformation achieve the requested goal? "
                        f"Answer strictly YES or NO on the first line, then a brief reason (1 sentence)."
                    )
                    _verify_messages = [
                        {"role": "system", "content": "You are a code verification assistant. Be strict. Answer YES only if the transformation clearly achieved its goal."},
                        {"role": "user", "content": _verify_prompt},
                    ]
                    try:
                        _verify_resp = self.llm_client.chat_with_tools(
                            _verify_messages, tools=[], max_tokens=150, temperature=0.0,
                        )
                        _verify_text = (_verify_resp.get("content") or "").strip()
                        # Strip thinking tags if present
                        from personal_agent.text_utils import strip_thinking_tags
                        _verify_text = strip_thinking_tags(_verify_text).strip()

                        _first_line = _verify_text.split("\n")[0].strip().upper()
                        _transformation_verified = _first_line.startswith("YES")
                        _verification_reason = _verify_text[:300]

                        # Mark the last tool step as verified
                        for _s in reversed(steps):
                            if _s.status == "ok":
                                _s.status = "verified" if _transformation_verified else _s.status
                                break

                        if _transformation_verified:
                            print(f"[TRANSFORM_VERIFY] PASSED: {_verification_reason[:120]}")
                            yield {
                                "type": "status",
                                "content": "transformation verified",
                                "metadata": {"verification": "passed", "reason": _verification_reason},
                            }
                        else:
                            print(f"[TRANSFORM_VERIFY] FAILED: {_verification_reason[:120]}")
                            yield {
                                "type": "status",
                                "content": f"transformation check failed: {_verification_reason[:200]}",
                                "metadata": {"verification": "failed", "reason": _verification_reason},
                            }
                    except Exception as _ve:
                        print(f"[TRANSFORM_VERIFY] Error during verification: {_ve}")
                        # Non-fatal — don't block the loop completion
        except Exception as _te:
            print(f"[TRANSFORM_VERIFY] Setup error: {_te}")

        # ── Emit completion event ──────────────────────────────────────────
        total_ms = (time.time() - start_time) * 1000
        _final_gen_source = _loop_generation_source or ("local" if len(steps) > 0 else "unknown")
        print(f"[GEN_SOURCE] Loop complete — generation_source={_final_gen_source}, tools_executed={len(steps)}")
        yield {
            "type": "agent_loop_complete",
            "content": f"Loop finished: {len(steps)} tool call(s) in {len(tools_used)} unique tool(s)",
            "metadata": {
                "iterations": min(len(steps), self.max_iterations),
                "tools_used": tools_used,
                "total_duration_ms": round(total_ms),
                "generation_source": _final_gen_source,
                "transformation_verified": _transformation_verified,
                "verification_reason": _verification_reason,
                "steps": [
                    {
                        "tool_name": s.tool_name,
                        "status": s.status,
                        "duration_ms": round(s.duration_ms),
                    }
                    for s in steps
                ],
            },
        }

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _build_tool_schemas(self, tool_filter: Optional[List[str]] = None) -> List[Dict[str, Any]]:
        """Build OpenAI-compatible tool schemas from the registry."""
        if tool_filter:
            return [
                td.to_llm_schema()
                for name, td in TOOL_REGISTRY.items()
                if name in tool_filter
            ]
        # Exclude internal tools not suitable for direct LLM routing
        return get_routing_schemas()

    def _build_messages(
        self,
        message: str,
        history: Optional[List[Dict[str, str]]],
        *,
        thread_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Build the message list for the LLM."""
        system_content = _get_agent_system_prompt()

        # Inject context-aware summary from CRT memories
        # Use belief-aware compaction when history is long
        if thread_id and self.engine:
            try:
                _mem_db = getattr(self.engine, "memory", None)
                _db_path = getattr(_mem_db, "db_path", None) if _mem_db else None
                if _db_path:
                    _hist_tokens = sum(len(str(t.get("content", ""))) // 4 for t in (history or [])[-4:])
                    if _hist_tokens > 1500:
                        from personal_agent.context_feed import build_compacted_context
                        _ctx = build_compacted_context(
                            thread_id=thread_id,
                            memory_db_path=_db_path,
                            token_budget=max(1500, 3000 - _hist_tokens),
                            trigger="token_overflow",
                        )
                    else:
                        from personal_agent.context_feed import build_context_summary
                        _ctx = build_context_summary(thread_id=thread_id, memory_db_path=_db_path)
                    if _ctx:
                        system_content += _ctx
            except Exception:
                pass

        msgs: List[Dict[str, Any]] = [
            {"role": "system", "content": system_content},
        ]

        # Add conversation history for context (last 4 turns max)
        if history:
            for turn in history[-4:]:
                msgs.append({
                    "role": turn.get("role", "user"),
                    "content": turn.get("content", ""),
                })

        msgs.append({"role": "user", "content": message})
        return msgs


# ---------------------------------------------------------------------------
# Helper: human-readable tool action description
# ---------------------------------------------------------------------------

def _describe_tool_action(tool_name: str, tool_args: Dict[str, Any]) -> str:
    """Generate a human-readable description of a tool call for checkpoints."""
    if tool_name == "file_write":
        path = tool_args.get("path", "a file")
        content = tool_args.get("content", "")
        preview = content[:80] + "..." if len(content) > 80 else content
        return f"write to {path} ({len(content)} chars)"
    elif tool_name == "shell_exec":
        cmd = tool_args.get("command", "a command")
        return f"run command: `{cmd}`"
    elif tool_name == "git_exec":
        args = tool_args.get("args", [])
        return f"execute: git {' '.join(args)}"
    elif tool_name == "file_read":
        return f"read file {tool_args.get('path', '?')}"
    elif tool_name == "web_browse":
        return f"browse: {tool_args.get('task', tool_args.get('url', '?'))}"
    elif tool_name == "desktop_action":
        return f"control desktop: {tool_args.get('task', '?')}"
    elif tool_name == "cancel_commitment":
        return f"cancel reminder: {tool_args.get('commitment_id', '?')}"
    else:
        td = TOOL_REGISTRY.get(tool_name)
        desc = td.description[:60] if td else tool_name
        return f"{tool_name}: {desc}"


# ---------------------------------------------------------------------------
# Convenience function for integration
# ---------------------------------------------------------------------------

def run_agent_tool_loop(
    message: str,
    thread_id: str,
    llm_client,
    *,
    session_db=None,
    conversation_history: Optional[List[Dict[str, str]]] = None,
    max_iterations: int = 10,
    show_thinking: bool = True,
    engine=None,
) -> Generator[Dict[str, Any], Optional[bool], None]:
    """Convenience wrapper to create and run an AgentToolLoop.

    Usage:
        gen = run_agent_tool_loop(message, thread_id, llm_client)
        for event in gen:
            if event["type"] == "agent_checkpoint":
                # Ask user, then gen.send(True/False)
                pass
            else:
                yield_to_sse(event)
    """
    loop = AgentToolLoop(
        llm_client,
        session_db=session_db,
        max_iterations=max_iterations,
        show_thinking=show_thinking,
        engine=engine,
    )
    yield from loop.run(
        message,
        thread_id,
        conversation_history=conversation_history,
    )
