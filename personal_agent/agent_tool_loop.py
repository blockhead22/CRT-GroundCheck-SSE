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

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# System prompt for the agentic loop LLM
# ---------------------------------------------------------------------------

_AGENT_SYSTEM_PROMPT = """\
You are Aether, a personal AI agent with access to tools. Use tools to fulfill \
the user's request. You may call multiple tools in sequence — after each tool \
result, decide whether you need more tools or can provide a final answer.

Available tools are provided as function definitions. Call them by name with \
the correct parameters extracted from the user's message and prior tool results.

Rules:
1. If the user's request requires action (reading files, searching, running \
commands), use the appropriate tool(s). Don't just describe what you would do.
2. After each tool result, decide: do you need another tool, or can you respond?
3. For multi-step tasks (e.g., "read this file and copy it to X"), execute ALL \
steps — don't stop after the first one.
4. When writing files, use the content from prior tool results (e.g., file_read \
output) as the content parameter.
5. If a tool fails, try to recover or explain what went wrong.
6. When you have all the information needed, respond with a natural text answer.
7. For file paths, preserve the exact paths from the user's message.
8. For shell commands, put the full command in the command parameter.
9. For git commands, extract subcommand + args into the args array.
10. Be concise in your final answers. Don't repeat raw tool output — interpret it.
11. Put ALL internal reasoning in <think> tags. Everything outside <think> is shown verbatim.

IMPORTANT: You must ONLY use the tools provided. Do not invent tool names."""


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

def _execute_tool(tool_name: str, tool_args: Dict[str, Any], thread_id: str) -> Dict[str, Any]:
    """Execute a registered tool and return the result.

    Returns dict with keys: content (str), status (str), metadata (dict).
    Reuses the same execution functions as CRTTaskAgent._run_* methods.
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
            from personal_agent.web_tools import web_search
            query = tool_args.get("query", "")
            result = web_search(query)
            has_error = "error" in result
            if not has_error:
                results_text = result.get("formatted", json.dumps(result.get("results", []), indent=2))
                return {"content": results_text[:3000], "status": "ok",
                        "metadata": {"tool_name": tool_name, "result_count": result.get("result_count", 0)}}
            return {"content": f"✗ web search failed: {result.get('error')}",
                    "status": "error", "metadata": {"tool_name": tool_name, "error": result.get("error")}}

        elif tool_name == "system_info":
            from personal_agent.system_tools import get_system_info
            result = get_system_info()
            formatted = result.get("formatted", json.dumps(result, indent=2))
            return {"content": formatted[:3000], "status": "ok",
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
            # Attempt memory recall if memory system is available
            return {"content": "(memory recall not available in loop mode)", "status": "ok",
                    "metadata": {"tool_name": tool_name}}

        elif tool_name == "generate_content":
            # Content generation is handled by the LLM itself in loop mode
            return {"content": "(use your own generation capability to produce the content, then call file_write to save it)",
                    "status": "ok", "metadata": {"tool_name": tool_name}}

        elif tool_name == "create_commitment":
            from personal_agent.scheduled_tasks import schedule_reminder
            intent_text = tool_args.get("intent", "")
            deadline = tool_args.get("deadline")
            recurrence = tool_args.get("recurrence")
            priority = tool_args.get("priority", "medium")
            result = schedule_reminder(
                intent=intent_text, description=tool_args.get("description", intent_text),
                deadline=deadline, recurrence=recurrence, priority=priority, thread_id=thread_id,
            )
            return {"content": f"✓ Reminder set: {intent_text}", "status": "ok",
                    "metadata": {"tool_name": tool_name, "reminder_id": result.get("id", "")}}

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
    ):
        self.llm_client = llm_client
        self.session_db = session_db
        self.max_iterations = max_iterations
        self.show_thinking = show_thinking

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
        messages = self._build_messages(message, conversation_history)

        yield {
            "type": "agent_loop_start",
            "content": "Starting agentic tool loop",
            "metadata": {
                "max_iterations": self.max_iterations,
                "tools_available": [s["function"]["name"] for s in tool_schemas],
            },
        }

        for iteration in range(self.max_iterations):
            logger.info("[AGENT_LOOP] Iteration %d/%d", iteration + 1, self.max_iterations)

            # ── 1. Call LLM with tools ─────────────────────────────────────
            try:
                llm_response = self.llm_client.chat_with_tools(
                    messages,
                    tools=tool_schemas,
                    max_tokens=2000,
                    temperature=0.1,
                )
            except Exception as e:
                logger.error("[AGENT_LOOP] LLM call failed: %s", e)
                yield {
                    "type": "token",
                    "content": f"I encountered an error while thinking: {e}",
                }
                break

            # ── 2. Check if LLM returned text (no tool calls) ─────────────
            tool_calls = llm_response.get("tool_calls", [])
            text_content = (llm_response.get("content") or "").strip()

            if not tool_calls:
                # LLM is done — emit final answer
                if text_content:
                    # Strip <think> tags for display
                    from personal_agent.text_utils import strip_thinking_tags, extract_think_content
                    think_content = extract_think_content(text_content)
                    clean_text = strip_thinking_tags(text_content)

                    if think_content and self.show_thinking:
                        yield {
                            "type": "agent_thinking_token",
                            "content": think_content,
                            "metadata": {"step": "final_reasoning"},
                        }

                    yield {"type": "token", "content": clean_text}
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
                if _needs_checkpoint(tool_name):
                    td = TOOL_REGISTRY.get(tool_name)
                    tier = td.checkpoint_tier if td else "high"

                    # Build human-readable description
                    action_desc = _describe_tool_action(tool_name, tool_args)

                    yield {
                        "type": "agent_checkpoint",
                        "content": f"I need to {action_desc}. Go ahead?",
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

                        messages.append({
                            "role": "assistant",
                            "content": None,
                            "tool_calls": [{"id": f"call_{iteration}_{tool_name}",
                                           "type": "function",
                                           "function": {"name": tool_name,
                                                       "arguments": json.dumps(tool_args)}}],
                        })
                        messages.append({
                            "role": "tool",
                            "tool_call_id": f"call_{iteration}_{tool_name}",
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

                t0 = time.time()
                result = _execute_tool(tool_name, tool_args, thread_id)
                elapsed_ms = (time.time() - t0) * 1000

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
                # Use the format expected by the LLM for tool results
                messages.append({
                    "role": "assistant",
                    "content": None,
                    "tool_calls": [{"id": f"call_{iteration}_{tool_name}",
                                   "type": "function",
                                   "function": {"name": tool_name,
                                               "arguments": json.dumps(tool_args)}}],
                })
                messages.append({
                    "role": "tool",
                    "tool_call_id": f"call_{iteration}_{tool_name}",
                    "content": result["content"][:4000],  # Keep context manageable
                })

        else:
            # Hit max iterations
            logger.warning("[AGENT_LOOP] Hit max iterations (%d)", self.max_iterations)
            yield {
                "type": "token",
                "content": f"I've completed {self.max_iterations} steps. Here's what I've done so far based on the results above.",
            }

        # ── Emit completion event ──────────────────────────────────────────
        total_ms = (time.time() - start_time) * 1000
        yield {
            "type": "agent_loop_complete",
            "content": f"Loop finished: {len(steps)} tool call(s) in {len(tools_used)} unique tool(s)",
            "metadata": {
                "iterations": min(len(steps), self.max_iterations),
                "tools_used": tools_used,
                "total_duration_ms": round(total_ms),
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
    ) -> List[Dict[str, Any]]:
        """Build the message list for the LLM."""
        msgs: List[Dict[str, Any]] = [
            {"role": "system", "content": _AGENT_SYSTEM_PROMPT},
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
    )
    yield from loop.run(
        message,
        thread_id,
        conversation_history=conversation_history,
    )
