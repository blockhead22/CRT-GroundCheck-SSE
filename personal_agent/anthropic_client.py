"""
AnthropicClient — Claude API integration for CRT/Aether.

Implements the same duck-typed interface as OllamaClient:
  - generate(prompt, system, max_tokens, temperature, stream, model) -> str
  - chat(messages, max_tokens, temperature, model) -> str
  - chat_stream(messages, max_tokens, temperature, model) -> Generator[(token_type, text)]
  - chat_with_tools(messages, tools, max_tokens, temperature, model) -> dict

Uses the official `anthropic` Python SDK.
"""

from __future__ import annotations

import json
import logging
import os
import time
from typing import Any, Dict, Generator, List, Optional, Tuple

logger = logging.getLogger(__name__)

try:
    import anthropic
    HAS_ANTHROPIC = True
except ImportError:
    HAS_ANTHROPIC = False
    anthropic = None  # type: ignore


class AnthropicClient:
    """Claude API client matching the OllamaClient interface."""

    def __init__(
        self,
        model: Optional[str] = None,
        api_key_env: str = "ANTHROPIC_API_KEY",
        timeout_seconds: float = 120.0,
        max_retries: int = 2,
    ) -> None:
        if not HAS_ANTHROPIC:
            raise ImportError(
                "anthropic package not installed. Run: pip install anthropic"
            )

        self.model = str(
            model
            or os.getenv("CRT_ANTHROPIC_MODEL")
            or "claude-sonnet-4-6"
        )
        self.api_key_env = api_key_env
        self.timeout_seconds = timeout_seconds

        api_key = os.getenv(api_key_env)
        if not api_key:
            raise ValueError(
                f"Environment variable {api_key_env} is not set. "
                "Get an API key from https://console.anthropic.com/"
            )

        self._client = anthropic.Anthropic(
            api_key=api_key,
            timeout=timeout_seconds,
            max_retries=max_retries,
        )
        self._total_input_tokens = 0
        self._total_output_tokens = 0

        logger.info(
            "[ANTHROPIC] Initialized client: model=%s timeout=%ss",
            self.model, timeout_seconds,
        )

    @property
    def is_available(self) -> bool:
        return bool(os.getenv(self.api_key_env))

    @property
    def usage_stats(self) -> Dict[str, int]:
        return {
            "total_input_tokens": self._total_input_tokens,
            "total_output_tokens": self._total_output_tokens,
        }

    # ── Message format conversion ──────────────────────────────────────────

    @staticmethod
    def _convert_messages(
        messages: List[Dict[str, Any]],
    ) -> Tuple[Optional[str], List[Dict[str, Any]]]:
        """
        Convert from CRT internal format to Claude API format.
        Extracts system message (Claude takes it as top-level param).
        Returns (system_prompt, messages).
        """
        system_prompt: Optional[str] = None
        converted: List[Dict[str, Any]] = []

        for msg in messages:
            role = msg.get("role", "user")
            content = msg.get("content", "")

            if role == "system":
                system_prompt = str(content)
                continue

            # Claude requires content to be str or list of content blocks
            if isinstance(content, str):
                converted.append({"role": role, "content": content})
            elif isinstance(content, list):
                # Already in block format — pass through
                converted.append({"role": role, "content": content})
            else:
                converted.append({"role": role, "content": str(content)})

        # Claude requires first message to be 'user'
        if converted and converted[0]["role"] != "user":
            converted.insert(0, {"role": "user", "content": "Continue."})

        # Claude requires alternating user/assistant
        deduped: List[Dict[str, Any]] = []
        for msg in converted:
            if deduped and deduped[-1]["role"] == msg["role"]:
                # Merge consecutive same-role messages
                prev = deduped[-1]["content"]
                curr = msg["content"]
                if isinstance(prev, str) and isinstance(curr, str):
                    deduped[-1]["content"] = prev + "\n" + curr
                else:
                    deduped[-1]["content"] = str(prev) + "\n" + str(curr)
            else:
                deduped.append(msg)

        return system_prompt, deduped

    @staticmethod
    def _convert_tools_to_anthropic(
        tools: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """
        Convert from CRT/Ollama tool format to Claude API tool format.

        CRT format:
          {"type": "function", "function": {"name": ..., "description": ..., "parameters": ...}}

        Claude format:
          {"name": ..., "description": ..., "input_schema": ...}
        """
        converted = []
        for tool in tools:
            if "function" in tool:
                func = tool["function"]
                converted.append({
                    "name": func.get("name", ""),
                    "description": func.get("description", ""),
                    "input_schema": func.get("parameters", {"type": "object", "properties": {}}),
                })
            elif "name" in tool and "input_schema" in tool:
                # Already in Claude format
                converted.append(tool)
            else:
                # Best-effort pass-through
                converted.append({
                    "name": tool.get("name", "unknown"),
                    "description": tool.get("description", ""),
                    "input_schema": tool.get("parameters") or tool.get("input_schema") or {"type": "object", "properties": {}},
                })
        return converted

    @staticmethod
    def _extract_text(response) -> str:
        """Extract text content from a Claude API response."""
        parts = []
        for block in response.content:
            if block.type == "text":
                parts.append(block.text)
        return "\n".join(parts).strip()

    @staticmethod
    def _extract_thinking(response) -> str:
        """Extract thinking content from a Claude API response."""
        parts = []
        for block in response.content:
            if block.type == "thinking":
                parts.append(block.thinking)
        return "\n".join(parts).strip()

    # ── generate() ─────────────────────────────────────────────────────────

    def generate(
        self,
        prompt: str,
        system: Optional[str] = None,
        max_tokens: int = 500,
        temperature: float = 0.7,
        stream: bool = False,
        model: Optional[str] = None,
    ) -> str:
        """Generate text from a prompt."""
        messages = [{"role": "user", "content": prompt}]
        if system:
            messages.insert(0, {"role": "system", "content": system})
        return self.chat(messages, max_tokens=max_tokens, temperature=temperature, model=model)

    # ── chat() ─────────────────────────────────────────────────────────────

    def chat(
        self,
        messages: List[Dict[str, str]],
        max_tokens: int = 500,
        temperature: float = 0.7,
        model: Optional[str] = None,
    ) -> str:
        """Chat with message history. Returns text response."""
        selected_model = model or self.model
        system_prompt, converted = self._convert_messages(messages)

        kwargs: Dict[str, Any] = {
            "model": selected_model,
            "max_tokens": max(max_tokens, 1024),
            "temperature": temperature,
            "messages": converted,
        }
        if system_prompt:
            kwargs["system"] = system_prompt

        # Use adaptive thinking for capable models
        if self._supports_adaptive_thinking(selected_model):
            kwargs["thinking"] = {"type": "adaptive"}

        try:
            t0 = time.time()
            response = self._client.messages.create(**kwargs)
            elapsed = time.time() - t0

            self._total_input_tokens += response.usage.input_tokens
            self._total_output_tokens += response.usage.output_tokens

            text = self._extract_text(response)
            logger.debug(
                "[ANTHROPIC] chat: model=%s tokens=%d/%d elapsed=%.1fs",
                selected_model,
                response.usage.input_tokens,
                response.usage.output_tokens,
                elapsed,
            )
            return text or "[No response from Claude]"

        except Exception as e:
            logger.warning("[ANTHROPIC] chat failed: %s", e)
            return f"[Claude API error: {e}]"

    # ── chat_stream() ──────────────────────────────────────────────────────

    def chat_stream(
        self,
        messages: List[Dict[str, str]],
        max_tokens: int = 500,
        temperature: float = 0.7,
        model: Optional[str] = None,
    ) -> Generator[Tuple[str, str], None, None]:
        """
        Stream chat response as (token_type, text) tuples.
        token_type: "thinking" | "content"
        """
        selected_model = model or self.model
        system_prompt, converted = self._convert_messages(messages)

        kwargs: Dict[str, Any] = {
            "model": selected_model,
            "max_tokens": max(max_tokens, 1024),
            "temperature": temperature,
            "messages": converted,
        }
        if system_prompt:
            kwargs["system"] = system_prompt

        if self._supports_adaptive_thinking(selected_model):
            kwargs["thinking"] = {"type": "adaptive"}

        try:
            current_block_type: Optional[str] = None

            with self._client.messages.stream(**kwargs) as stream:
                for event in stream:
                    if event.type == "content_block_start":
                        block = event.content_block
                        current_block_type = block.type

                    elif event.type == "content_block_delta":
                        if event.delta.type == "thinking_delta":
                            yield ("thinking", event.delta.thinking)
                        elif event.delta.type == "text_delta":
                            yield ("content", event.delta.text)

                    elif event.type == "content_block_stop":
                        current_block_type = None

                # Record usage from final message
                final = stream.get_final_message()
                self._total_input_tokens += final.usage.input_tokens
                self._total_output_tokens += final.usage.output_tokens

        except Exception as e:
            logger.warning("[ANTHROPIC] chat_stream failed: %s", e)
            yield ("content", f"[Claude API error: {e}]")

    # ── chat_with_tools() ──────────────────────────────────────────────────

    def chat_with_tools(
        self,
        messages: List[Dict[str, Any]],
        tools: List[Dict[str, Any]],
        max_tokens: int = 1000,
        temperature: float = 0.3,
        model: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Chat with function/tool calling support.

        Returns dict matching the CRT internal format:
        {
            "tool_calls": [{"name": str, "arguments": dict}, ...],
            "content": str,  # reasoning/text content
            "used_tools": bool,
        }
        """
        selected_model = model or self.model
        system_prompt, converted = self._convert_messages(messages)
        claude_tools = self._convert_tools_to_anthropic(tools)

        kwargs: Dict[str, Any] = {
            "model": selected_model,
            "max_tokens": max(max_tokens, 1024),
            "temperature": temperature,
            "messages": converted,
            "tools": claude_tools,
        }
        if system_prompt:
            kwargs["system"] = system_prompt

        if self._supports_adaptive_thinking(selected_model):
            kwargs["thinking"] = {"type": "adaptive"}

        try:
            t0 = time.time()
            response = self._client.messages.create(**kwargs)
            elapsed = time.time() - t0

            self._total_input_tokens += response.usage.input_tokens
            self._total_output_tokens += response.usage.output_tokens

            # Extract text content (reasoning) and tool calls
            text_parts = []
            thinking_parts = []
            tool_calls = []

            for block in response.content:
                if block.type == "text":
                    text_parts.append(block.text)
                elif block.type == "thinking":
                    thinking_parts.append(block.thinking)
                elif block.type == "tool_use":
                    tool_calls.append({
                        "name": block.name,
                        "arguments": block.input if isinstance(block.input, dict) else {},
                    })

            content = "\n".join(text_parts).strip()
            # Include thinking in content if no visible text
            if not content and thinking_parts:
                content = "\n".join(thinking_parts).strip()

            logger.debug(
                "[ANTHROPIC] chat_with_tools: model=%s tools=%d calls=%d tokens=%d/%d elapsed=%.1fs",
                selected_model,
                len(claude_tools),
                len(tool_calls),
                response.usage.input_tokens,
                response.usage.output_tokens,
                elapsed,
            )

            return {
                "tool_calls": tool_calls,
                "content": content,
                "used_tools": len(tool_calls) > 0,
            }

        except Exception as e:
            logger.warning("[ANTHROPIC] chat_with_tools failed: %s", e)
            return {"tool_calls": [], "content": f"[Claude API error: {e}]", "used_tools": False}

    # ── chat_with_image() ─────────────────────────────────────────────────

    def chat_with_image(
        self,
        prompt: str,
        image_b64: str,
        image_media_type: str = "image/jpeg",
        max_tokens: int = 1000,
        temperature: float = 0.1,
        model: Optional[str] = None,
    ) -> str:
        """Send a prompt with an image to Claude. Returns text response."""
        selected_model = model or self.model

        kwargs: Dict[str, Any] = {
            "model": selected_model,
            "max_tokens": max(max_tokens, 1024),
            "temperature": temperature,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": image_media_type,
                                "data": image_b64,
                            },
                        },
                        {
                            "type": "text",
                            "text": prompt,
                        },
                    ],
                }
            ],
        }

        try:
            t0 = time.time()
            response = self._client.messages.create(**kwargs)
            elapsed = time.time() - t0

            self._total_input_tokens += response.usage.input_tokens
            self._total_output_tokens += response.usage.output_tokens

            text = self._extract_text(response)
            logger.debug(
                "[ANTHROPIC] chat_with_image: model=%s tokens=%d/%d elapsed=%.1fs",
                selected_model,
                response.usage.input_tokens,
                response.usage.output_tokens,
                elapsed,
            )
            return text or "[No response from Claude]"

        except Exception as e:
            logger.warning("[ANTHROPIC] chat_with_image failed: %s", e)
            return f"[Claude API error: {e}]"

    # ── Helpers ────────────────────────────────────────────────────────────

    @staticmethod
    def _supports_adaptive_thinking(model: str) -> bool:
        """Check if a model supports adaptive thinking (Opus 4.6, Sonnet 4.6)."""
        m = model.lower()
        return any(tag in m for tag in ("opus-4-6", "sonnet-4-6", "opus-4-5", "sonnet-4-5"))
