"""Response Synthesis Layer for CRT.

After tools execute, this layer runs an LLM pass that interprets results
in the context of the user's original intent, producing natural responses
instead of raw data dumps.

Sprint 13 / v2.9.1
"""

from __future__ import annotations

import json
import logging
import os
import re
import time
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Synthesis intent signals — phrases that imply the user wants interpretation
# ---------------------------------------------------------------------------

_INTERPRETATION_SIGNALS = (
    "tell me about",
    "what is",
    "what does",
    "what's in",
    "explain",
    "summarize",
    "summary",
    "describe",
    "overview",
    "break down",
    "walk me through",
    "what do you think",
    "analyse",
    "analyze",
    "how does",
    "why does",
    "what happened",
    "what's going on",
    "what's wrong",
    "what's the status",
    "how's",
    "how is",
)

_RAW_OUTPUT_SIGNALS = (
    "show me the file",
    "show me the contents",
    "show the output",
    "print the file",
    "cat ",
    "raw output",
    "show raw",
    "just show",
    "just list",
    "just read",
)


# ---------------------------------------------------------------------------
# Synthesis system prompt
# ---------------------------------------------------------------------------

_SYNTHESIS_SYSTEM_PROMPT = """\
You are a personal AI assistant, responding to a user after executing a tool on their behalf.

The user asked: "{user_message}"

The tool "{tool_name}" was executed and returned results (provided below as JSON).

Your job: Respond naturally to what the user actually needs.

Rules:
- ONLY reference information present in the tool results below. Never invent data.
- If the user asked you to "tell me about" or "summarize" something, give a \
thoughtful interpretation — highlight what matters, explain structure, note key points.
- If the results are simple, keep the response concise. Don't pad.
- If the results are complex (large file, scan), focus on what's important.
- If the tool returned an error, explain what went wrong clearly.
- Match the user's energy — casual question gets casual answer, detailed question gets depth.
- If relevant, suggest what the user might want to do next (briefly, 1 sentence max).
- Start with the answer immediately. No "Based on the results..." or "The tool returned...".
- Put ALL internal reasoning in <think> tags. Everything outside <think> is shown verbatim.
- Keep responses to 2-6 sentences for simple results, more for complex analysis requests."""


# ---------------------------------------------------------------------------
# ResponseSynthesizer
# ---------------------------------------------------------------------------

class ResponseSynthesizer:
    """Takes tool results + user intent and generates a thoughtful response."""

    def __init__(self, llm_client, *, mode: str = "local"):
        """
        Args:
            llm_client: OllamaClient or HybridLLMClient instance
            mode: "local" | "cloud" | "hybrid" — matches routing_mode setting
        """
        self.llm_client = llm_client
        self.mode = mode

    def should_synthesize(
        self,
        tool_name: str,
        user_message: str,
        tool_result: Any,
    ) -> bool:
        """Decide whether to run synthesis based on tool's synthesis_mode and user intent."""
        from personal_agent.tool_registry import get_synthesis_mode

        synthesis_mode = get_synthesis_mode(tool_name)

        if synthesis_mode == "never":
            return False
        if synthesis_mode == "always":
            return True

        msg_lower = user_message.lower()

        if synthesis_mode == "on_request":
            return any(sig in msg_lower for sig in _INTERPRETATION_SIGNALS)

        # synthesis_mode == "smart" — decide based on context
        # If user explicitly wants raw output, skip synthesis
        if any(sig in msg_lower for sig in _RAW_OUTPUT_SIGNALS):
            return False

        # If user asks for interpretation, synthesize
        if any(sig in msg_lower for sig in _INTERPRETATION_SIGNALS):
            return True

        # If tool result is an error, synthesize to explain it
        if isinstance(tool_result, dict) and "error" in tool_result:
            return True

        # For file_read with large content, synthesize to summarize
        if tool_name == "file_read" and isinstance(tool_result, dict):
            content = tool_result.get("content", "")
            lines = content.count("\n") + 1
            if lines > 30:
                return True

        # Default: don't synthesize for "smart" mode — keep it fast
        return False

    def synthesize(
        self,
        user_message: str,
        tool_name: str,
        tool_results: List[Dict[str, Any]],
        *,
        conversation_history: Optional[List[Dict[str, str]]] = None,
        max_tokens: int = 600,
    ) -> Optional[str]:
        """
        Run the synthesis LLM pass.

        Args:
            user_message: Original user message
            tool_name: Primary tool that was executed
            tool_results: List of step results from tool execution
            conversation_history: Optional recent conversation
            max_tokens: Max tokens for synthesis response

        Returns:
            Synthesized response text, or None on failure
        """
        t0 = time.time()

        # Build the tool results summary for the LLM
        results_json = self._format_tool_results(tool_results)

        # Build the system prompt
        system_prompt = _SYNTHESIS_SYSTEM_PROMPT.format(
            user_message=user_message[:500],
            tool_name=tool_name,
        )

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"Tool results:\n```json\n{results_json}\n```"},
        ]

        try:
            response = self._call_llm(messages, max_tokens=max_tokens)
            elapsed_ms = (time.time() - t0) * 1000

            if response:
                # Strip any <think> tags from the response
                response = self._strip_thinking(response)
                logger.info(
                    "[SYNTHESIS] %s → %d chars in %.0fms",
                    tool_name, len(response), elapsed_ms,
                )
                return response
        except Exception as e:
            logger.warning("[SYNTHESIS] Failed for %s: %s", tool_name, e)

        return None

    def _call_llm(self, messages: List[Dict[str, str]], max_tokens: int = 600) -> str:
        """Call the LLM client. Supports OllamaClient and HybridLLMClient."""
        client = self.llm_client

        # Determine which model/client to use based on mode
        fast_model = os.getenv("CRT_MODEL_FAST") or "role:fast"

        if hasattr(client, "chat"):
            return client.chat(
                messages=messages,
                max_tokens=max_tokens,
                temperature=0.3,
                model=fast_model if hasattr(client, "local_client") else None,
            )

        return ""

    def _format_tool_results(self, results: List[Dict[str, Any]]) -> str:
        """Format tool results as a compact JSON string for the LLM."""
        formatted = []
        for r in results:
            entry: Dict[str, Any] = {
                "tool": r.get("tool_name", "unknown"),
                "status": r.get("status", "unknown"),
            }

            output = r.get("output")
            if isinstance(output, dict):
                # For file_read, include the content but truncate if huge
                content = output.get("content", "")
                if content and len(content) > 4000:
                    output = {**output, "content": content[:4000] + f"\n... [truncated, {len(content)} chars total]"}
                entry["result"] = output
            elif isinstance(output, str):
                entry["result"] = output[:4000] if len(output) > 4000 else output
            else:
                entry["result"] = r.get("output_preview", "no output")

            if r.get("error"):
                entry["error"] = r["error"]

            formatted.append(entry)

        return json.dumps(formatted, indent=2, default=str)

    @staticmethod
    def _strip_thinking(text: str) -> str:
        """Remove <think>...</think> blocks from LLM output."""
        cleaned = re.sub(r'<think>.*?</think>', '', text, flags=re.DOTALL)
        return cleaned.strip()


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------

_global_synthesizer: Optional[ResponseSynthesizer] = None


def get_response_synthesizer(llm_client=None, mode: str = "local") -> Optional[ResponseSynthesizer]:
    """Get or create the global ResponseSynthesizer."""
    global _global_synthesizer

    if llm_client is not None:
        _global_synthesizer = ResponseSynthesizer(llm_client, mode=mode)
        return _global_synthesizer

    if _global_synthesizer is not None:
        return _global_synthesizer

    # Try to create with default client
    try:
        from personal_agent.litellm_client import get_default_llm_client as get_ollama_client
        model = os.getenv("CRT_OLLAMA_MODEL", "qwen3:14b")
        client = get_ollama_client(model)
        _global_synthesizer = ResponseSynthesizer(client, mode=mode)
        return _global_synthesizer
    except Exception as e:
        logger.debug("[SYNTHESIS] Could not create synthesizer: %s", e)
        return None
