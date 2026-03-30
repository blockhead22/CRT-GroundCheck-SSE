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

CRITICAL — NEVER use a tool for these message types (respond with text only):
- Questions asking for opinions, reflections, or analysis: "what do you think...", \
"why do you think...", "how do you feel...", "do you think..."
- Gratitude or acknowledgment: "thank you", "that was great", "I appreciate..."
- Agreement or disagreement statements: "I think you're right", "I disagree because..."
- Philosophical or conceptual discussion about the system itself
- Follow-up to a conversation that doesn't require new information (e.g. "keep going", \
"that's interesting", "tell me more about that")
- Emotional or personal sharing that needs a thoughtful reply, not a tool

CRITICAL — use memory_recall (NOT web_search or desktop_action) when:
- User asks what you know about them: "what do you know about me", "tell me about me"
- User asks about your relationship: "what have we talked about", "do you remember"
- User asks for a fact about themselves: "what's my job", "where do I live"

CRITICAL — use web_search or web_browse ONLY when:
- User explicitly says "search for", "look up", "find online", "google this"
- User asks for current events, news, or external information not in memory

CRITICAL — desktop_action is ONLY for literal computer control tasks:
- Opening apps, clicking, typing, taking screenshots, controlling the screen
- NEVER use for questions, opinions, memory recall, or reflective conversations

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

    # ------------------------------------------------------------------
    # Conversational pre-filter — intercepts before the LLM sees the message
    # ------------------------------------------------------------------

    _CONVERSATIONAL_EXACT: frozenset = frozenset({
        "hello", "hello!", "hello?", "hello aether", "hello aether!", "hello aether?",
        "hi", "hi!", "hey", "hey!", "hey aether", "hey aether!", "heya",
        "how are you", "how are you?", "how are you doing", "how are you doing?",
        "how's it going", "how's it going?", "what's up", "what's up?",
        "good morning", "good afternoon", "good evening", "good night",
        "thanks", "thank you", "thank you!", "thanks!", "ty", "ty!",
        "ok", "okay", "ok.", "okay.", "ok!", "okay!", "got it", "got it.",
        "yes", "no", "sure", "alright", "sounds good", "perfect", "great",
        "nice", "cool", "awesome", "interesting", "hmm", "hm", "lol",
        "i see", "i understand", "makes sense", "that makes sense",
        "that's interesting", "thats interesting", "wow",
    })

    _CONVERSATIONAL_PREFIXES: tuple = (
        "hello ",  # "hello how are you", "hello there", etc.
        "what do you think",
        "what's your opinion",
        "what is your opinion",
        "how do you feel",
        "do you think",
        "why do you think",
        "what do you believe",
        "what would you say",
        "what is your take",
        "what's your take",
        "what is your view",
        "do you agree",
        "do you believe",
        "i think you",
        "i appreciate",
        "i agree",
        "i disagree",
        "that was",
        "that's really",
        "thats really",
        "that is all ",
        "now, that is",
        "now that is",
        "we are still",
        "we're still",
        "you are right",
        "you're right",
        "you were right",
        "this is amazing",
        "this is great",
        "this discussion",
        "this has been",
        "keep going",
        "tell me more",
        "go on",
        "interesting thought",
        "what does that mean to you",
        "what is your purpose",
        "what is aether",
        "who are you",
        "why do you exist",
        "why should",
        "why does",
        "what is the point",
        "what is the meaning",
        "what is important to you",
        "what is important",
        "what matters to you",
        "what do you care about",
        "what are you uncertain",
        "what don't you know",
        "what should i clarify",
        "what do you value",
        "how does that make you",
        "do you have feelings",
        "do you have emotions",
        "are you conscious",
        "are you sentient",
        "can you feel",
        "do you enjoy",
        "i'm not ignoring",
        "im not ignoring",
        "what else",
        "continue",
        "go ahead",
        "sounds good",
        # Memory-state questions — asking about stored knowledge, not web search
        "what do you know about me",
        "what do you remember about me",
        "what do you know about",
        "tell me what you know",
        "what have you learned about me",
        "what have we talked about",
        "do you remember",
        "what's my ",
        "what is my ",
        "who am i",
        "who do you think i am",
        "what kind of person",
        "based on what you know",
        # Casual fact updates / corrections — memory store, not desktop action
        "i sold ",
        "i bought ",
        "i got rid of ",
        "i no longer ",
        "i don't have ",
        "i don't own ",
        "btw ",
        "by the way ",
        "just to let you know",
        "just so you know",
        "fyi ",
        "update: ",
        "small update",
        "quick update",
        "also, i ",
        "also i ",
        "oh and ",
        "oh also ",
    )

    _AGENT_NAME_PREFIXES: tuple = (
        "aether, ", "aether - ", "hey aether, ", "hi aether, ",
        "hello aether, ", "ok aether, ", "okay aether, ",
    )

    def _is_conversational(self, message: str) -> bool:
        """Return True if the message is clearly conversational (no tool needed)."""
        # Ignore messages with file attachments — they likely need file_read
        if "[file:" in message or "[folder:" in message:
            return False
        # Ignore very long messages — might contain real task instructions
        stripped = message.strip().rstrip("?!. ")
        if len(stripped) > 150:
            return False
        normalized = stripped.lower()
        # Strip agent name prefix ("Aether, what do you think..." → "what do you think...")
        for agent_pfx in self._AGENT_NAME_PREFIXES:
            if normalized.startswith(agent_pfx):
                normalized = normalized[len(agent_pfx):].strip()
                break
        if normalized in self._CONVERSATIONAL_EXACT:
            return True
        for prefix in self._CONVERSATIONAL_PREFIXES:
            if normalized.startswith(prefix):
                return True
        return False

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

        # Pre-filter: intercept obviously conversational messages before LLM routing.
        # llama3.2 reliably misclassifies greetings/opinions as desktop_action/web_search.
        if not attached_paths and self._is_conversational(message):
            logger.info("[LLM_ROUTER] Conversational pre-filter → no tool (msg=%r)", message[:60])
            return TaskIntent(
                route="conversational",
                intent_type="conversational",
                slots={"raw_message": message},
                confidence=0.99,
                reason="Conversational pre-filter: no tool needed",
                source="pre_filter",
            )

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
    """Create an LLM router using a local Ollama model.

    Uses CRT_INTENT_MODEL if set (e.g. llama3.2:latest for fast routing),
    otherwise falls back to CRT_OLLAMA_MODEL (the main generation model).
    """
    if ollama_client is None:
        try:
            from personal_agent.litellm_client import get_default_llm_client
            intent_model = os.getenv("CRT_INTENT_MODEL")
            model = intent_model or os.getenv("CRT_OLLAMA_MODEL", "qwen3:14b")
            if intent_model:
                print("[LLM_ROUTER] Using dedicated intent model: %s" % intent_model)
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
