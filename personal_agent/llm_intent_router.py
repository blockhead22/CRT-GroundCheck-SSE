"""LLM-based Intent Router for CRT.

Tier 2/3 of the hybrid routing system.  Sends the user message plus tool
definitions to a local or cloud LLM and gets back structured tool calls.

Works with:
  - Local (Ollama) via OllamaClient.chat_with_tools()
  - Cloud (OpenAI-compatible) via HybridLLMClient

Sprint 13 / v2.9
"""

from __future__ import annotations

import json
import logging
import os
import re
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# Lazy imports to avoid circular dependencies
_TaskIntent = None  # Will hold the TaskIntent class


def _get_task_intent_cls():
    """Lazy-import TaskIntent to avoid circular imports with task_agent."""
    global _TaskIntent
    if _TaskIntent is None:
        from personal_agent.task_agent import TaskIntent
        _TaskIntent = TaskIntent
    return _TaskIntent


# ---------------------------------------------------------------------------
# System prompt for the router LLM
# ---------------------------------------------------------------------------

_ROUTER_SYSTEM_PROMPT = """\
You are a tool-routing assistant. Your ONLY job is to decide which tool(s) to call \
based on the user's message.

Rules:
1. If the user is asking to perform an action that matches one of the available \
tools, call that tool with the correct parameters.
2. If the user message contains a file path or [file: <path>] attachment, and they \
want to read/view/summarize it, use file_read with that path.
3. If no tool is appropriate (casual conversation, opinions, general questions), \
respond with a short text message — do NOT call any tool.
4. If the user wants MULTIPLE actions in sequence (e.g. "copy this file then \
summarize it", "read the file and tell me what it says"), call the FIRST tool \
that should execute. Also include a JSON block in your text response describing \
the full sequence:
{"multi_step": true, "steps": [{"tool": "tool_name", "params": {...}}, ...]}
5. Extract parameters carefully from the user message — file paths, URLs, commands, etc.
6. For git commands, extract the git subcommand and args into the args parameter as a list.
7. For shell commands, put the full command string in the command parameter.

IMPORTANT: You must ONLY use the tools provided. Do not invent tool names."""


# ---------------------------------------------------------------------------
# LLMIntentRouter
# ---------------------------------------------------------------------------

class LLMIntentRouter:
    """Routes user messages to tools using LLM function-calling."""

    def __init__(
        self,
        llm_client,
        tool_schemas: List[Dict[str, Any]],
        *,
        source_label: str = "llm_local",
        max_tokens: int = 300,
        temperature: float = 0.0,
    ):
        """
        Args:
            llm_client: OllamaClient or HybridLLMClient instance
            tool_schemas: List of OpenAI-compatible function schemas
            source_label: Label for logging/tracking ("llm_local" or "llm_cloud")
            max_tokens: Max tokens for the routing LLM call
            temperature: Low temperature for deterministic routing
        """
        self.llm_client = llm_client
        self.tool_schemas = tool_schemas
        self.source_label = source_label
        self.max_tokens = max_tokens
        self.temperature = 0.0  # Force deterministic routing (classification task)

    def classify(
        self,
        message: str,
        *,
        conversation_history: Optional[List[Dict[str, str]]] = None,
        attached_paths: Optional[List[str]] = None,
    ) -> "TaskIntent":
        """
        Send message + tool schemas to LLM, parse the response into TaskIntent.

        Args:
            message: User's raw message text
            conversation_history: Optional recent conversation for context
            attached_paths: File paths attached to the message (e.g. [file: X])

        Returns:
            TaskIntent with route, intent_type, slots, confidence, source
        """
        TaskIntent = _get_task_intent_cls()
        t0 = time.time()

        # Build the messages payload
        messages = self._build_messages(message, conversation_history, attached_paths)

        # Call the LLM with tool schemas
        result = self._call_llm(messages)

        elapsed_ms = (time.time() - t0) * 1000
        logger.info(
            "[LLM_ROUTER:%s] classify took %.0fms | used_tools=%s",
            self.source_label, elapsed_ms, result.get("used_tools", False),
        )

        # Parse the LLM response into a TaskIntent
        return self._parse_result(result, message, attached_paths)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _build_messages(
        self,
        message: str,
        history: Optional[List[Dict[str, str]]],
        attached_paths: Optional[List[str]],
    ) -> List[Dict[str, str]]:
        """Build the message list for the LLM call."""
        msgs: List[Dict[str, str]] = [
            {"role": "system", "content": _ROUTER_SYSTEM_PROMPT},
        ]

        # Add conversation history for context (last 4 turns max)
        if history:
            for turn in history[-4:]:
                msgs.append({
                    "role": turn.get("role", "user"),
                    "content": turn.get("content", ""),
                })

        # Build the user message with attachment context
        user_content = message
        if attached_paths:
            paths_str = ", ".join(attached_paths)
            user_content = f"[Attached files: {paths_str}]\n{message}"

        msgs.append({"role": "user", "content": user_content})
        return msgs

    def _call_llm(self, messages: List[Dict[str, str]]) -> Dict[str, Any]:
        """Call the LLM with tool schemas. Works with both Ollama and Hybrid clients."""
        client = self.llm_client

        # OllamaClient has chat_with_tools() directly
        if hasattr(client, "chat_with_tools"):
            return client.chat_with_tools(
                messages=messages,
                tools=self.tool_schemas,
                max_tokens=self.max_tokens,
                temperature=self.temperature,
            )

        # HybridLLMClient — use its local_client's chat_with_tools
        if hasattr(client, "local_client") and client.local_client is not None:
            return client.local_client.chat_with_tools(
                messages=messages,
                tools=self.tool_schemas,
                max_tokens=self.max_tokens,
                temperature=self.temperature,
            )

        # Fallback: try chat() and parse JSON manually
        if hasattr(client, "chat"):
            try:
                raw = client.chat(
                    messages=messages,
                    max_tokens=self.max_tokens,
                    temperature=self.temperature,
                )
                return self._parse_json_fallback(raw)
            except Exception as e:
                logger.warning("[LLM_ROUTER] chat() fallback failed: %s", e)

        return {"tool_calls": [], "content": "", "used_tools": False, "error": "no_compatible_client"}

    def _parse_json_fallback(self, raw_text: str) -> Dict[str, Any]:
        """Try to parse a JSON tool call from raw LLM text output."""
        # Look for JSON in the response
        try:
            # Try to find JSON object in the text
            match = re.search(r'\{[^{}]*"tool"[^{}]*\}', raw_text, re.DOTALL)
            if match:
                data = json.loads(match.group())
                tool_name = data.get("tool") or data.get("name", "")
                params = data.get("params") or data.get("parameters") or data.get("arguments", {})
                if tool_name:
                    return {
                        "tool_calls": [{"name": tool_name, "arguments": params}],
                        "content": "",
                        "used_tools": True,
                    }
        except (json.JSONDecodeError, AttributeError):
            pass

        return {"tool_calls": [], "content": raw_text, "used_tools": False}

    def _parse_result(
        self,
        result: Dict[str, Any],
        original_message: str,
        attached_paths: Optional[List[str]],
    ) -> "TaskIntent":
        """Convert LLM tool-call response into a TaskIntent."""
        TaskIntent = _get_task_intent_cls()

        # Check for errors
        if result.get("error"):
            logger.warning("[LLM_ROUTER] Error from LLM: %s", result["error"])
            return TaskIntent(
                route="conversational",
                intent_type="conversational",
                slots={"raw_message": original_message},
                confidence=0.3,
                reason=f"LLM router error: {result['error']}",
                source=self.source_label,
            )

        tool_calls = result.get("tool_calls", [])
        content = result.get("content", "")

        # Check for multi_step JSON in the content (LLM described a sequence)
        _multi_step_match = re.search(
            r'\{[^{}]*"multi_step"\s*:\s*true[^{}]*"steps"\s*:\s*\[',
            content, re.DOTALL,
        )
        if _multi_step_match:
            try:
                # Find the full JSON object
                _json_start = content.find("{", _multi_step_match.start())
                _brace_depth = 0
                _json_end = _json_start
                for _ci, _ch in enumerate(content[_json_start:], _json_start):
                    if _ch == "{":
                        _brace_depth += 1
                    elif _ch == "}":
                        _brace_depth -= 1
                        if _brace_depth == 0:
                            _json_end = _ci + 1
                            break
                _multi_data = json.loads(content[_json_start:_json_end])
                _steps = _multi_data.get("steps", [])
                if _steps and len(_steps) >= 2:
                    logger.info(
                        "[LLM_ROUTER:%s] → multi_step with %d steps",
                        self.source_label, len(_steps),
                    )
                    return TaskIntent(
                        route="task",
                        intent_type="multi_step",
                        slots={
                            "raw_message": original_message,
                            "steps": _steps,
                        },
                        confidence=0.85,
                        reason=f"LLM router detected multi-step ({len(_steps)} steps)",
                        source=self.source_label,
                    )
            except (json.JSONDecodeError, ValueError) as e:
                logger.debug("[LLM_ROUTER] Failed to parse multi_step JSON: %s", e)

        # No tool calls → conversational
        if not tool_calls:
            return TaskIntent(
                route="conversational",
                intent_type="conversational",
                slots={"raw_message": original_message, "llm_response": content},
                confidence=0.75,
                reason="LLM chose no tool — conversational response",
                source=self.source_label,
            )

        # Multiple tool calls → multi_step
        if len(tool_calls) >= 2:
            _steps = [
                {"tool": tc.get("name", ""), "params": tc.get("arguments", {})}
                for tc in tool_calls
            ]
            logger.info(
                "[LLM_ROUTER:%s] → multi_step from %d native tool_calls",
                self.source_label, len(tool_calls),
            )
            return TaskIntent(
                route="task",
                intent_type="multi_step",
                slots={
                    "raw_message": original_message,
                    "steps": _steps,
                },
                confidence=0.88,
                reason=f"LLM router returned {len(tool_calls)} tool calls",
                source=self.source_label,
            )

        # Single tool call → map to TaskIntent
        tc = tool_calls[0]
        tool_name = tc.get("name", "")
        arguments = tc.get("arguments", {})

        # Map tool_name back to intent_type via registry
        intent_type = self._tool_to_intent(tool_name)

        # Build slots from the tool arguments
        slots = self._build_slots(tool_name, arguments, original_message, attached_paths)

        # Confidence: high if the LLM chose a tool decisively
        confidence = 0.85

        logger.info(
            "[LLM_ROUTER:%s] → tool=%s intent=%s conf=%.2f slots=%s",
            self.source_label, tool_name, intent_type, confidence,
            {k: (v[:50] + "..." if isinstance(v, str) and len(v) > 50 else v)
             for k, v in slots.items() if k != "raw_message"},
        )

        return TaskIntent(
            route="task",
            intent_type=intent_type,
            slots=slots,
            confidence=confidence,
            reason=f"LLM router selected tool '{tool_name}'",
            source=self.source_label,
        )

    def _tool_to_intent(self, tool_name: str) -> str:
        """Map a tool name back to the intent_type used by _build_plan()."""
        # Most tools map directly; some need translation
        _TOOL_INTENT_MAP = {
            "system_info": "system_info",
            "file_read": "file_read",
            "file_write": "file_write",
            "dir_list": "dir_list",
            "project_scan": "project_scan",
            "shell_exec": "shell_exec",
            "git_exec": "git_action",
            "fetch_url": "url_fetch",
            "desktop_action": "desktop_action",
            "create_commitment": "create_commitment",
            "list_commitments": "list_commitments",
            "cancel_commitment": "cancel_commitment",
            "generate_content": "file_write",  # content generation goes through file_write path
            "memory_recall": "broad_recall",
        }
        return _TOOL_INTENT_MAP.get(tool_name, tool_name)

    def _build_slots(
        self,
        tool_name: str,
        arguments: Dict[str, Any],
        original_message: str,
        attached_paths: Optional[List[str]],
    ) -> Dict[str, Any]:
        """Build the slots dict that _build_plan() expects."""
        slots: Dict[str, Any] = {"raw_message": original_message}

        # Always include raw arguments for reference
        slots.update(arguments)

        # Tool-specific slot normalization
        if tool_name == "file_read":
            path = arguments.get("path", "")
            # If no path from args but we have attached paths, use first one
            if not path and attached_paths:
                path = attached_paths[0]
            # Also try to extract from [file: X] pattern in message
            if not path:
                path = self._extract_file_path(original_message)
            slots["path"] = path

        elif tool_name == "file_write":
            slots.setdefault("path", arguments.get("path", ""))
            slots.setdefault("content", arguments.get("content", ""))

        elif tool_name == "dir_list":
            slots.setdefault("path", arguments.get("path", ""))

        elif tool_name == "project_scan":
            slots.setdefault("path", arguments.get("path", ""))

        elif tool_name == "shell_exec":
            slots.setdefault("command", arguments.get("command", ""))
            slots.setdefault("cwd", arguments.get("cwd", ""))

        elif tool_name == "git_exec":
            args_list = arguments.get("args", [])
            if isinstance(args_list, str):
                args_list = args_list.split()
            slots["args"] = args_list
            slots.setdefault("cwd", arguments.get("cwd", ""))

        elif tool_name == "fetch_url":
            url = arguments.get("url", "")
            if not url:
                url = self._extract_url(original_message)
            slots["url"] = url

        elif tool_name == "desktop_action":
            slots["task_description"] = arguments.get("task", original_message)

        elif tool_name == "create_commitment":
            slots.setdefault("intent", arguments.get("intent", ""))
            slots.setdefault("description", arguments.get("description", ""))
            slots.setdefault("deadline", arguments.get("deadline", ""))

        elif tool_name == "memory_recall":
            slots.setdefault("query", arguments.get("query", original_message))

        return slots

    @staticmethod
    def _extract_file_path(message: str) -> str:
        """Extract file path from [file: X] pattern or quoted paths."""
        # [file: path/to/file]
        m = re.search(r'\[file:\s*([^\]]+)\]', message)
        if m:
            return m.group(1).strip()
        # Quoted path
        m = re.search(r'["\']([^"\']+\.[a-zA-Z0-9]+)["\']', message)
        if m:
            return m.group(1).strip()
        # Bare path-like token
        m = re.search(r'(\S+\.[a-zA-Z0-9]{1,10})\b', message)
        if m:
            candidate = m.group(1)
            # Filter out common non-file patterns
            if candidate not in ("e.g.", "i.e.", "etc.", "vs."):
                return candidate
        return ""

    @staticmethod
    def _extract_url(message: str) -> str:
        """Extract URL from message text."""
        m = re.search(r'(https?://\S+)', message)
        return m.group(1).rstrip(".,;)") if m else ""


# ---------------------------------------------------------------------------
# Factory functions
# ---------------------------------------------------------------------------

def create_local_router(
    ollama_client=None,
    tool_schemas: Optional[List[Dict[str, Any]]] = None,
) -> Optional[LLMIntentRouter]:
    """Create an LLM router using the local Ollama model."""
    if ollama_client is None:
        try:
            from personal_agent.litellm_client import get_default_llm_client
            model = os.getenv("CRT_OLLAMA_MODEL", "qwen3:14b")
            ollama_client = get_default_llm_client(model)
        except Exception as e:
            logger.warning("[LLM_ROUTER] Could not create local router: %s", e)
            return None

    if tool_schemas is None:
        from personal_agent.tool_registry import get_routing_schemas
        tool_schemas = get_routing_schemas()

    return LLMIntentRouter(
        llm_client=ollama_client,
        tool_schemas=tool_schemas,
        source_label="llm_local",
    )


def create_cloud_router(
    hybrid_client=None,
    tool_schemas: Optional[List[Dict[str, Any]]] = None,
) -> Optional[LLMIntentRouter]:
    """Create an LLM router using the cloud model."""
    if hybrid_client is None:
        logger.warning("[LLM_ROUTER] No hybrid client provided for cloud router")
        return None

    if tool_schemas is None:
        from personal_agent.tool_registry import get_routing_schemas
        tool_schemas = get_routing_schemas()

    return LLMIntentRouter(
        llm_client=hybrid_client,
        tool_schemas=tool_schemas,
        source_label="llm_cloud",
        max_tokens=400,  # Cloud can handle more
    )
