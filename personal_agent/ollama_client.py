"""Ollama LLM client for CRT.

This integration is optional. The rest of the repo (tests, heuristic tooling)
should remain usable even when the `ollama` Python package isn't installed.
"""

import os
from typing import Generator, Optional, Dict, List, Any, Tuple

from .text_utils import extract_think_content

try:
    import ollama  # type: ignore
except ModuleNotFoundError:  # pragma: no cover
    ollama = None  # type: ignore[assignment]


class OllamaClient:
    """Client for Ollama local LLM."""
    
    def __init__(self, model: Optional[str] = None):
        """
        Initialize Ollama client.
        
        Popular models:
        - llama3.2:latest (3B): Fast and efficient
        - mistral:latest: Good for chat
        - deepseek-r1:8b: Reasoning-focused
        - codellama: Good for code
        """
        # Prefer explicit model, then CRT_OLLAMA_MODEL, else fallback.
        self.model = model or os.getenv("CRT_OLLAMA_MODEL") or "qwen2.5-coder:14b"

        if ollama is None:
            raise ModuleNotFoundError(
                "Optional dependency 'ollama' is not installed. Install with: pip install ollama"
            )

        # Default request timeout so the UI/test harness can't hang forever.
        # Can be overridden via env var OLLAMA_TIMEOUT_SECONDS.
        timeout_s = None
        try:
            env = os.getenv("OLLAMA_TIMEOUT_SECONDS", "")
            timeout_s = float(env) if env else 300.0
        except Exception:
            timeout_s = 300.0

        # Use a dedicated client instance so we can pass timeout/settings.
        # The underlying ollama Python client forwards kwargs to httpx.Client.
        try:
            self._client = ollama.Client(timeout=timeout_s)  # type: ignore[union-attr]
        except Exception:
            self._client = None
        self._verify_model()
    
    def _verify_model(self):
        """Check if model is available."""
        try:
            # Try to list models - don't fail if this doesn't work
            if self._client is not None and hasattr(self._client, "list"):
                self._client.list()
            else:
                ollama.list()  # type: ignore[union-attr]
            # If we get here, Ollama is running
        except:
            # Silently continue - we'll find out when we try to generate
            pass
    
    def generate(
        self,
        prompt: str,
        system: Optional[str] = None,
        max_tokens: int = 500,
        temperature: float = 0.7,
        stream: bool = False,
        model: Optional[str] = None,
    ) -> str:
        """
        Generate text from prompt.
        
        Args:
            prompt: User prompt
            system: System prompt (optional)
            max_tokens: Max tokens to generate
            temperature: Sampling temperature (0-1)
            stream: Whether to stream response
        
        Returns:
            Generated text
        """
        messages = []
        
        if system:
            messages.append({
                'role': 'system',
                'content': system
            })
        
        messages.append({
            'role': 'user',
            'content': prompt
        })
        
        try:
            selected_model = model or self.model
            chat_fn = self._client.chat if (self._client is not None and hasattr(self._client, "chat")) else ollama.chat  # type: ignore[union-attr]

            response = chat_fn(
                model=selected_model,
                messages=messages,
                options={
                    'num_predict': max_tokens,
                    'temperature': temperature,
                    'repeat_penalty': 1.15,
                },
                stream=stream
            )
            
            if stream:
                # Return generator for streaming
                return response
            else:
                # Handle both dict-style and pydantic responses
                if hasattr(response, 'message'):
                    # Pydantic model (newer ollama)
                    msg = response.message
                    content = msg.content if msg.content else ""
                    thinking = getattr(msg, 'thinking', None) or ""
                    return self._resolve_visible_text(content, thinking)
                else:
                    # Dict-style response (older ollama)
                    return response['message']['content']
        
        except Exception as e:
            error_msg = str(e)
            if "connection" in error_msg.lower():
                return f"[Ollama connection error: Is Ollama running? Try: ollama serve]"
            elif "not found" in error_msg.lower():
                target = model or self.model
                return f"[Model '{target}' not found. Try: ollama pull {target}]"
            else:
                return f"[Ollama error: {e}]"
    
    def chat(
        self,
        messages: List[Dict[str, str]],
        max_tokens: int = 500,
        temperature: float = 0.7,
        model: Optional[str] = None,
    ) -> str:
        """
        Chat with message history.
        
        Args:
            messages: List of {'role': 'user'|'assistant', 'content': str}
            max_tokens: Max tokens to generate
            temperature: Sampling temperature
        
        Returns:
            Generated response
        """
        try:
            selected_model = model or self.model
            chat_fn = self._client.chat if (self._client is not None and hasattr(self._client, "chat")) else ollama.chat  # type: ignore[union-attr]

            response = chat_fn(
                model=selected_model,
                messages=messages,
                options={
                    'num_predict': max_tokens,
                    'temperature': temperature,
                    'repeat_penalty': 1.15,
                }
            )

            # Handle both dict-style and pydantic responses
            if hasattr(response, 'message'):
                msg = response.message
                content = msg.content if msg.content else ""
                thinking = getattr(msg, 'thinking', None) or ""
                return self._resolve_visible_text(content, thinking)
            else:
                return response['message']['content']
        except Exception as e:
            return f"[Ollama error: {e}]"

    def _resolve_visible_text(self, content: str, thinking: str) -> str:
        """Return safe user-visible text, never raw chain-of-thought.

        Handles three response formats:
        1. Native thinking field: thinking="reasoning...", content="answer"
           → Return content (the answer).
        2. Inline <think> tags: content="<think>reasoning</think>answer"
           → Extract and return the answer portion.
        3. Mixed/legacy: thinking contains <think> tags with visible text
           after the closing tag → extract the visible portion.

        The thinking field itself is NEVER returned as visible text.
        """
        visible = str(content or "").strip()
        if visible:
            # Strip any dangling/inline think tags from content.
            _, visible = extract_think_content(visible)
            visible = str(visible or "").strip()
            if visible:
                return visible

        # Content is empty. If thinking has content, the model used
        # the native thinking field — the reasoning IS the thinking,
        # not visible text. Only extract if there are actual <think>
        # tags (legacy format where both thinking and answer ended up
        # in the same field).
        thinking_text = str(thinking or "").strip()
        if not thinking_text:
            return ""

        # Check for <think> tags — only then might there be visible
        # text outside the tags in this field.
        if "<think>" in thinking_text.lower():
            _, extracted_visible = extract_think_content(thinking_text)
            extracted_visible = str(extracted_visible or "").strip()
            if extracted_visible:
                return extracted_visible

        # Native thinking field with no content = model reasoned but
        # produced no answer. Do not leak the reasoning.
        return "[Model returned internal reasoning without a final answer. Please retry.]"
    
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

        Handles two formats:
          - Native thinking field: chunk.message.thinking (Ollama native)
          - Inline <think> tags in content stream (Qwen3 default format)
        """
        selected_model = model or self.model
        chat_fn = (
            self._client.chat
            if (self._client is not None and hasattr(self._client, "chat"))
            else ollama.chat  # type: ignore[union-attr]
        )
        try:
            stream = chat_fn(
                model=selected_model,
                messages=messages,
                options={
                    "num_predict": max_tokens,
                    "temperature": temperature,
                    "repeat_penalty": 1.15,
                },
                stream=True,
            )

            in_think = False
            buf = ""

            for chunk in stream:
                msg = (
                    chunk.message
                    if hasattr(chunk, "message")
                    else (chunk.get("message", {}) if isinstance(chunk, dict) else {})
                )

                # Native thinking field (some Ollama builds surface this separately)
                thinking_tok = (
                    (msg.thinking if hasattr(msg, "thinking") else None)
                    or (msg.get("thinking") if isinstance(msg, dict) else None)
                    or ""
                )
                content_tok = (
                    (msg.content if hasattr(msg, "content") else None)
                    or (msg.get("content") if isinstance(msg, dict) else None)
                    or ""
                )

                if thinking_tok:
                    yield ("thinking", thinking_tok)

                # Parse inline <think>...</think> tags from content stream
                if content_tok:
                    buf += content_tok
                    while buf:
                        if not in_think:
                            start = buf.find("<think>")
                            if start == -1:
                                yield ("content", buf)
                                buf = ""
                                break
                            if start > 0:
                                yield ("content", buf[:start])
                            buf = buf[start + 7:]
                            in_think = True
                        else:
                            end = buf.find("</think>")
                            if end == -1:
                                yield ("thinking", buf)
                                buf = ""
                                break
                            if end > 0:
                                yield ("thinking", buf[:end])
                            buf = buf[end + 8:]
                            in_think = False

            if buf:
                yield ("thinking" if in_think else "content", buf)

        except Exception as e:
            yield ("content", f"[stream error: {e}]")

    def chat_with_tools(
        self,
        messages: List[Dict[str, Any]],
        tools: List[Dict[str, Any]],
        max_tokens: int = 1000,
        temperature: float = 0.3,
        model: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Chat with native Ollama function/tool calling.

        Args:
            messages: Conversation messages
            tools: Ollama tool schema list (OpenAI-compatible type/function format)
            max_tokens: Max tokens to generate
            temperature: Sampling temperature (lower = more precise tool selection)
            model: Override model

        Returns:
            {
                "tool_calls": list of {"name": str, "arguments": dict},
                "content": str,
                "used_tools": bool,
            }
        """
        try:
            selected_model = model or self.model
            chat_fn = (
                self._client.chat
                if (self._client is not None and hasattr(self._client, "chat"))
                else ollama.chat  # type: ignore[union-attr]
            )
            response = chat_fn(
                model=selected_model,
                messages=messages,
                tools=tools,
                options={
                    "num_predict": max_tokens,
                    "temperature": temperature,
                    "repeat_penalty": 1.15,
                },
            )

            msg = (
                response.message
                if hasattr(response, "message")
                else response.get("message", {})
            )

            # Extract tool calls (pydantic or dict)
            raw_tool_calls = []
            if hasattr(msg, "tool_calls") and msg.tool_calls:
                raw_tool_calls = msg.tool_calls
            elif isinstance(msg, dict) and msg.get("tool_calls"):
                raw_tool_calls = msg["tool_calls"]

            parsed_calls = []
            for tc in raw_tool_calls:
                if hasattr(tc, "function"):
                    args = tc.function.arguments
                    parsed_calls.append({
                        "name": tc.function.name,
                        "arguments": args if isinstance(args, dict) else {},
                    })
                elif isinstance(tc, dict) and "function" in tc:
                    fn = tc["function"]
                    parsed_calls.append({
                        "name": fn.get("name", ""),
                        "arguments": fn.get("arguments", {}),
                    })

            content = ""
            if hasattr(msg, "content"):
                content = msg.content or ""
            elif isinstance(msg, dict):
                content = msg.get("content", "") or ""

            return {
                "tool_calls": parsed_calls,
                "content": content,
                "used_tools": len(parsed_calls) > 0,
            }

        except Exception as e:
            return {
                "tool_calls": [],
                "content": f"[tool_calling_error: {e}]",
                "used_tools": False,
                "error": str(e),
            }

    def extract_intent(self, query: str) -> Dict[str, Any]:
        """
        Extract user intent from query.
        
        Returns:
            {
                'intent': str,
                'entities': List[str],
                'importance': float (0-1)
            }
        """
        prompt = f"""Analyze this user query and extract:
1. The main intent (what they want)
2. Any important entities or facts
3. Importance score (0-1, how important to remember this)

Query: "{query}"

Respond in this format:
Intent: <intent>
Entities: <comma-separated entities>
Importance: <0.0-1.0>"""
        
        response = self.generate(prompt, max_tokens=200, temperature=0.3)
        
        # Parse response
        intent_data = {
            'intent': 'unknown',
            'entities': [],
            'importance': 0.5
        }
        
        try:
            for line in response.split('\n'):
                if line.startswith('Intent:'):
                    intent_data['intent'] = line.replace('Intent:', '').strip()
                elif line.startswith('Entities:'):
                    entities_str = line.replace('Entities:', '').strip()
                    intent_data['entities'] = [e.strip() for e in entities_str.split(',') if e.strip()]
                elif line.startswith('Importance:'):
                    importance_str = line.replace('Importance:', '').strip()
                    try:
                        intent_data['importance'] = float(importance_str)
                    except:
                        pass
        except:
            pass
        
        return intent_data


# Global instance
_global_client: Optional[OllamaClient] = None


def get_ollama_client(model: str = "qwen2.5-coder:14b") -> OllamaClient:
    """Get or create global Ollama client."""
    global _global_client
    if ollama is None:
        raise ModuleNotFoundError(
            "Optional dependency 'ollama' is not installed. Install with: pip install ollama"
        )
    if _global_client is None or _global_client.model != model:
        _global_client = OllamaClient(model)
    return _global_client
