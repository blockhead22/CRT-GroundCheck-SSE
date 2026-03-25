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
        # Last thinking content from chat()/generate() — available for callers
        # that need the reasoning trace without changing the return type.
        self.last_thinking: str = ""

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
    
    # Models known to use a separate thinking/reasoning pass that consumes
    # part of the num_predict budget.  When one of these is selected we
    # inflate num_predict so the *visible* answer is not truncated.
    _THINKING_MODELS = {"qwen3", "deepseek-r1", "qwq"}

    def _is_thinking_model(self, model_name: str) -> bool:
        """Return True if *model_name* is known to spend tokens on internal thinking."""
        name = (model_name or "").lower()
        return any(t in name for t in self._THINKING_MODELS)

    def _effective_num_predict(self, max_tokens: int, model_name: str) -> int:
        """Return inflated num_predict for thinking models.

        Thinking models (qwen3, deepseek-r1, etc.) use part of the token
        budget for internal chain-of-thought.  Without inflation the visible
        answer is often truncated mid-sentence.  We give 4x headroom
        (capped at 8192) so the model has room for both reasoning *and*
        a complete response.
        """
        if self._is_thinking_model(model_name):
            return min(max_tokens * 2, 4096)
        return max_tokens

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
                    'num_predict': self._effective_num_predict(max_tokens, selected_model),
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
                    'num_predict': self._effective_num_predict(max_tokens, selected_model),
                    'temperature': temperature,
                    'repeat_penalty': 1.15,
                }
            )

            # Handle both dict-style and pydantic responses
            if hasattr(response, 'message'):
                msg = response.message
                content = msg.content if msg.content else ""
                thinking = getattr(msg, 'thinking', None) or ""
            else:
                content = response['message'].get('content', '')
                thinking = response['message'].get('thinking', '')
            self.last_thinking = str(thinking or "")
            return self._resolve_visible_text(content, thinking)
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
        # produced no answer. Try to extract a conclusion from the last
        # sentence(s) of the thinking — often the model's final answer
        # is the last line of its reasoning.
        lines = [ln.strip() for ln in thinking_text.splitlines() if ln.strip()]
        if lines:
            # Take the last non-empty line as a best-effort answer.
            last = lines[-1]
            # Skip lines that are clearly meta-reasoning, not answers.
            _meta_prefixes = ("so ", "wait", "hmm", "let me", "i think", "i need",
                              "but ", "however", "actually", "okay")
            if not last.lower().startswith(_meta_prefixes) and len(last) > 5:
                return last
            # Try second-to-last
            if len(lines) >= 2:
                second_last = lines[-2]
                if not second_last.lower().startswith(_meta_prefixes) and len(second_last) > 5:
                    return second_last

        # Genuine failure — no extractable answer.
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
                    "num_predict": self._effective_num_predict(max_tokens, selected_model),
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
            # When tools are provided, use raw httpx to avoid Ollama's Pydantic
            # model rejecting string arguments in tool_calls (ollama v0.6.x bug).
            # For non-tool calls, use the native client as normal.
            if tools:
                import httpx
                _base = "http://localhost:11434"

                # Sanitize messages for Ollama's strict JSON parser:
                # - Replace null content with empty string
                # - Convert string tool_call arguments to dicts
                _clean_msgs = []
                for _m in messages:
                    _cm = dict(_m)
                    if _cm.get("content") is None:
                        _cm["content"] = ""
                    # Ollama chokes on tool_calls with string arguments
                    if "tool_calls" in _cm and _cm["tool_calls"]:
                        _fixed_tcs = []
                        for _tc in _cm["tool_calls"]:
                            _ftc = dict(_tc) if isinstance(_tc, dict) else _tc
                            if isinstance(_ftc, dict) and "function" in _ftc:
                                _fn = dict(_ftc["function"])
                                if isinstance(_fn.get("arguments"), str):
                                    try:
                                        _fn["arguments"] = json.loads(_fn["arguments"])
                                    except (json.JSONDecodeError, TypeError):
                                        _fn["arguments"] = {}
                                _ftc = {**_ftc, "function": _fn}
                            _fixed_tcs.append(_ftc)
                        _cm["tool_calls"] = _fixed_tcs
                    _clean_msgs.append(_cm)

                _payload = {
                    "model": selected_model,
                    "messages": _clean_msgs,
                    "tools": tools,
                    "stream": False,
                    "options": {
                        "num_predict": self._effective_num_predict(max_tokens, selected_model),
                        "temperature": temperature,
                        "repeat_penalty": 1.15,
                    },
                }
                # Debug: dump payload to verify it's valid JSON
                import json as _json
                try:
                    _json_str = _json.dumps(_payload)
                    print(f"[OLLAMA] Tool call payload size: {len(_json_str)}, msgs: {len(messages)}, tools: {len(tools)}")
                except TypeError as _te:
                    print(f"[OLLAMA] Payload NOT JSON-serializable: {_te}")
                    # Find the problematic part
                    for i, m in enumerate(messages):
                        try:
                            _json.dumps(m)
                        except TypeError as _me:
                            print(f"[OLLAMA]   message[{i}] bad: {_me} — type={type(m)}, keys={m.keys() if hasattr(m, 'keys') else 'N/A'}")
                    for i, t in enumerate(tools):
                        try:
                            _json.dumps(t)
                        except TypeError as _tte:
                            print(f"[OLLAMA]   tool[{i}] bad: {_tte}")

                _resp = httpx.post(f"{_base}/api/chat", json=_payload, timeout=120.0)
                if _resp.status_code != 200:
                    print(f"[OLLAMA] Tool call HTTP {_resp.status_code}: {_resp.text[:500]}")
                _resp.raise_for_status()
                response = _resp.json()  # raw dict, bypasses Pydantic entirely
            else:
                response = chat_fn(
                    model=selected_model,
                    messages=messages,
                    options={
                        "num_predict": self._effective_num_predict(max_tokens, selected_model),
                        "temperature": temperature,
                        "repeat_penalty": 1.15,
                    },
                )

            msg = (
                response.message
                if hasattr(response, "message")
                else response.get("message", {})
            )

            # Debug: dump raw message
            if isinstance(msg, dict):
                _dbg_content = (msg.get("content") or "")[:300]
                _dbg_tcs = len(msg.get("tool_calls") or [])
                print(f"[OLLAMA_DEBUG] raw msg: content_len={len(msg.get('content') or '')}, tool_calls={_dbg_tcs}, content_preview={_dbg_content[:200]}")
            else:
                _dbg_content = (getattr(msg, 'content', '') or '')[:300]
                _dbg_tcs = len(getattr(msg, 'tool_calls', None) or [])
                print(f"[OLLAMA_DEBUG] pydantic msg: content_len={len(getattr(msg, 'content', '') or '')}, tool_calls={_dbg_tcs}, content_preview={_dbg_content[:200]}")

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
                    if isinstance(args, str):
                        try:
                            args = json.loads(args)
                        except (json.JSONDecodeError, TypeError):
                            args = {}
                    parsed_calls.append({
                        "name": tc.function.name,
                        "arguments": args if isinstance(args, dict) else {},
                    })
                elif isinstance(tc, dict) and "function" in tc:
                    fn = tc["function"]
                    args = fn.get("arguments", {})
                    if isinstance(args, str):
                        try:
                            args = json.loads(args)
                        except (json.JSONDecodeError, TypeError):
                            args = {}
                    parsed_calls.append({
                        "name": fn.get("name", ""),
                        "arguments": args if isinstance(args, dict) else {},
                    })

            # Extract content with thinking-token recovery (same as chat())
            raw_content = ""
            if hasattr(msg, "content"):
                raw_content = msg.content or ""
            elif isinstance(msg, dict):
                raw_content = msg.get("content", "") or ""

            thinking = ""
            if hasattr(msg, "thinking"):
                thinking = msg.thinking or ""
            elif isinstance(msg, dict):
                thinking = msg.get("thinking", "") or ""

            # Apply _resolve_visible_text so thinking content is recovered
            if raw_content or thinking:
                content = self._resolve_visible_text(raw_content, thinking)
            else:
                content = ""

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
