"""
UnifiedLLMClient — LiteLLM-based replacement for the 3-file client layer.

Replaces hybrid_llm_client.py + ollama_client.py + anthropic_client.py (~1,751 lines).
Preserves: model prefix routing, thinking model support, quality gate fallback,
rate limiting, prompt scrubbing, streaming with thinking/content separation.
"""

from __future__ import annotations

import json
import logging
import os
import re
import time
from dataclasses import dataclass
from typing import Any, Dict, Generator, List, Optional, Tuple

import litellm
import requests

from .text_utils import extract_think_content

logger = logging.getLogger(__name__)

# Reduce LiteLLM noise
litellm.suppress_debug_info = True
litellm.set_verbose = False


def _env_bool(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return str(raw).strip().lower() in {"1", "true", "yes", "y", "on"}


def _normalize_visible_text(content: str) -> str:
    """Strip <think> tags and return visible text."""
    visible = str(content or "").strip()
    if visible:
        return visible
    _, extracted = extract_think_content(str(content or ""))
    return str(extracted or "").strip()


# ── CloudPromptPolicy ────────────────────────────────────────────────────


@dataclass
class CloudPromptPolicy:
    redact_memory_metadata: bool = True
    max_context_chars: int = 14000
    fact_allowlist: Tuple[str, ...] = ()
    slot_denylist: Tuple[str, ...] = ()


# ── OpenAICompatibleClient (preserved for cloud_features.py) ─────────────


class OpenAICompatibleClient:
    """Minimal OpenAI-compatible chat client using plain HTTP.

    Kept for cloud_features.py which needs a simple HTTP client for
    slot classification, NLI, and other CRT governance features.
    """

    def __init__(
        self,
        *,
        model: str,
        api_key_env: str = "OPENAI_API_KEY",
        base_url: str = "https://api.openai.com/v1",
        timeout_seconds: float = 300.0,
        provider_label: str = "openai_compatible",
    ) -> None:
        self.model = str(model or "").strip()
        self.api_key_env = str(api_key_env or "OPENAI_API_KEY").strip()
        self.base_url = str(base_url or "https://api.openai.com/v1").rstrip("/")
        self.timeout_seconds = float(timeout_seconds or 300.0)
        self.provider_label = str(provider_label or "openai_compatible").strip()

    @property
    def api_key(self) -> str:
        return str(os.getenv(self.api_key_env) or "").strip()

    @property
    def is_available(self) -> bool:
        return bool(self.model and self.api_key)

    def generate(
        self, prompt: str, system: Optional[str] = None, max_tokens: int = 500,
        temperature: float = 0.7, stream: bool = False, model: Optional[str] = None,
    ) -> str:
        messages: List[Dict[str, str]] = []
        if system:
            messages.append({"role": "system", "content": str(system)})
        messages.append({"role": "user", "content": str(prompt or "")})
        return self.chat(messages, max_tokens=max_tokens, temperature=temperature,
                         model=model, stream=stream)

    def chat(
        self, messages: List[Dict[str, str]], max_tokens: int = 500,
        temperature: float = 0.7, model: Optional[str] = None, stream: bool = False,
    ) -> str:
        if not self.is_available:
            return f"[Cloud LLM unavailable: set {self.api_key_env}]"
        payload: Dict[str, Any] = {
            "model": str(model or self.model or "").strip(),
            "messages": list(messages or []),
            "max_tokens": int(max_tokens or 500),
            "temperature": float(temperature),
            "stream": bool(stream),
        }
        headers = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}
        try:
            resp = requests.post(f"{self.base_url}/chat/completions", json=payload,
                                 headers=headers, timeout=self.timeout_seconds)
            resp.raise_for_status()
            data = resp.json() or {}
        except Exception as e:
            return f"[Cloud LLM error: {e}]"

        choices = data.get("choices")
        if not isinstance(choices, list) or not choices:
            err = data.get("error") or {}
            if isinstance(err, dict) and err.get("message"):
                return f"[Cloud LLM error: {err.get('message')}]"
            return "[Cloud LLM error: no choices returned]"

        message = choices[0].get("message") or {}
        content = message.get("content", "")
        if isinstance(content, list):
            parts: List[str] = []
            for item in content:
                if isinstance(item, dict) and item.get("text"):
                    parts.append(str(item["text"]))
            content = "".join(parts)
        return _normalize_visible_text(str(content or "")) or "[Cloud LLM returned no visible answer]"


# ── UnifiedLLMClient ─────────────────────────────────────────────────────


class UnifiedLLMClient:
    """Drop-in replacement for HybridLLMClient using LiteLLM.

    Routes to Ollama (local), OpenAI-compatible (cloud), or Anthropic
    based on model prefix strings and product_mode configuration.
    """

    THINKING_MODELS = {"qwen3", "deepseek-r1", "qwq"}
    _META_STARTS = (
        "i should", "i need to", "let me", "i will",
        "i'll", "the next step", "now i", "i want to",
        "[model returned internal",
    )

    def __init__(self, config: dict):
        cfg = config or {}
        self.ollama_model = cfg.get("ollama_model", "qwen3:14b")
        self.ollama_base_url = cfg.get("ollama_base_url", "http://localhost:11434")
        self.cloud_model = cfg.get("cloud_model", "")
        self.cloud_api_key = cfg.get("cloud_api_key", "")
        self.cloud_base_url = cfg.get("cloud_base_url", "")
        self.anthropic_model = cfg.get("anthropic_model", "claude-sonnet-4-6")
        self.anthropic_api_key = cfg.get("anthropic_api_key", "")
        self.product_mode = cfg.get("product_mode", "hybrid_verified")
        self.model_roles: Dict[str, str] = cfg.get("model_roles", {})
        self.fallback_enabled = cfg.get("fallback_enabled", True)
        self.cloud_policy = CloudPromptPolicy(
            redact_memory_metadata=cfg.get("redact_memory_metadata", True),
            max_context_chars=cfg.get("max_context_chars", 14000),
            fact_allowlist=tuple(cfg.get("fact_allowlist", ())),
            slot_denylist=tuple(cfg.get("slot_denylist", ())),
        )
        self.rate_limiter = cfg.get("rate_limiter")
        self.fallback_policy: str = "cloud_to_local"
        self.last_thinking: str = ""

        logger.info(
            "[LITELLM] Client initialized: ollama=%s anthropic=%s cloud=%s mode=%s",
            self.ollama_model, self.anthropic_model or "(none)",
            self.cloud_model or "(none)", self.product_mode,
        )

    # ── Properties ────────────────────────────────────────────────────

    @property
    def model(self) -> str:
        return self.ollama_model

    @property
    def cloud_available(self) -> bool:
        return bool(self.cloud_model and self.cloud_api_key)

    @property
    def anthropic_available(self) -> bool:
        return bool(self.anthropic_api_key)

    # ── Model resolution ──────────────────────────────────────────────

    def _resolve_target(self, model: Optional[str]) -> Tuple[str, Optional[str]]:
        """Resolve model string to (provider, model_name).

        Prefixes: anthropic:, cloud:, local:, role:
        No prefix → local.
        """
        selected = str(model or "").strip()

        if selected.startswith("role:"):
            role_name = selected.split(":", 1)[1].strip()
            env_key = f"CRT_MODEL_ROLE_{role_name.upper()}"
            resolved = os.getenv(env_key) or self.model_roles.get(role_name, "")
            if not resolved:
                return "local", None
            return self._resolve_target(resolved)

        if selected.startswith("anthropic:"):
            return "anthropic", selected.split(":", 1)[1].strip() or None
        if selected.startswith("cloud:"):
            return "cloud", selected.split(":", 1)[1].strip() or None
        if selected.startswith("local:"):
            return "local", selected.split(":", 1)[1].strip() or None
        return "local", selected or None

    def _to_litellm_params(self, provider: str, model_name: Optional[str]) -> Dict[str, Any]:
        """Convert (provider, model_name) to litellm.completion kwargs."""
        if provider == "anthropic":
            resolved = model_name or self.anthropic_model
            if not resolved.startswith("anthropic/"):
                resolved = f"anthropic/{resolved}"
            params: Dict[str, Any] = {"model": resolved, "timeout": 120}
            if self.anthropic_api_key:
                params["api_key"] = self.anthropic_api_key
            return params

        if provider == "cloud":
            resolved = model_name or self.cloud_model
            params = {"model": resolved, "timeout": 120}
            if self.cloud_api_key:
                params["api_key"] = self.cloud_api_key
            if self.cloud_base_url:
                params["api_base"] = self.cloud_base_url
            return params

        # Default: local (Ollama)
        resolved = model_name or self.ollama_model
        if not resolved.startswith("ollama/"):
            resolved = f"ollama/{resolved}"
        return {
            "model": resolved,
            "api_base": self.ollama_base_url,
            "timeout": 120,
        }

    def _is_thinking_model(self, model: str) -> bool:
        name = (model or "").lower()
        return any(t in name for t in self.THINKING_MODELS)

    def _effective_max_tokens(self, max_tokens: int, model: str) -> int:
        if self._is_thinking_model(model):
            return max(max_tokens * 4, 8192)
        return max_tokens

    # ── Scrubbing (preserved from hybrid_llm_client.py) ───────────────

    @staticmethod
    def _normalize_slot(slot: str) -> str:
        return re.sub(r"\s+", "_", str(slot or "").strip().lower())

    def _slot_allowed_for_cloud(self, slot: str) -> bool:
        normalized = self._normalize_slot(slot)
        deny = {self._normalize_slot(x) for x in self.cloud_policy.slot_denylist}
        allow = {self._normalize_slot(x) for x in self.cloud_policy.fact_allowlist}
        if normalized in deny:
            return False
        if allow and normalized not in allow:
            return False
        return True

    def _filter_user_fact_lines(self, raw_block: str, *, numbered: bool) -> str:
        kept: List[str] = []
        for line in str(raw_block or "").splitlines():
            clean = re.sub(r"^\s*(?:\d+\.\s*|[-*]\s*)", "", line).strip()
            if not clean:
                continue
            match = re.search(
                r"\b(?:FACT|PREF):\s*([A-Za-z0-9_ ]+)\s*=\s*(.+?)\s*$",
                clean, re.IGNORECASE,
            )
            if not match:
                continue
            slot = self._normalize_slot(match.group(1))
            if not self._slot_allowed_for_cloud(slot):
                continue
            prefix = "PREF" if clean.upper().startswith("PREF:") else "FACT"
            value = str(match.group(2) or "").strip()
            kept.append(f"{prefix}: {slot} = {value}")
        if not kept:
            return "[User facts withheld by cloud policy]\n"
        if numbered:
            return "\n".join(f"{idx + 1}. {line}" for idx, line in enumerate(kept)) + "\n"
        return "\n".join(kept) + "\n"

    def _filter_structured_user_fact_sections(self, text: str) -> str:
        user_fact_pattern = re.compile(
            r"(=== (?:RETRIEVED MEMORIES: USER FACTS|VERIFIED USER FACTS) ===\n)"
            r"(.*?)(?=\n===|\Z)", flags=re.DOTALL,
        )

        def _uf_repl(m: re.Match) -> str:
            return m.group(1) + self._filter_user_fact_lines(m.group(2), numbered=True)

        text = user_fact_pattern.sub(_uf_repl, text)

        context_pattern = re.compile(
            r"(Context from memory \(facts ABOUT THE USER\):\n)(.*?)(?=\n\n|\Z)",
            flags=re.DOTALL,
        )

        def _ctx_repl(m: re.Match) -> str:
            return m.group(1) + self._filter_user_fact_lines(m.group(2), numbered=False)

        text = context_pattern.sub(_ctx_repl, text)

        mem_ctx_pattern = re.compile(
            r"(MEMORY_CONTEXT \(for reference only; do not fact-check it\):\n)"
            r"(.*?)(?=\n\n[A-Z]|\Z)", flags=re.DOTALL,
        )

        def _mc_repl(m: re.Match) -> str:
            return m.group(1) + self._filter_user_fact_lines(m.group(2), numbered=False)

        return mem_ctx_pattern.sub(_mc_repl, text)

    def _scrub_prompt_for_cloud(self, prompt: str) -> str:
        text = str(prompt or "")
        if self.cloud_policy.redact_memory_metadata:
            text = re.sub(r"\s*\[trust:\s*[^\]]+\]", "", text, flags=re.IGNORECASE)
            text = re.sub(r"\s*\[similarity:\s*[^\]]+\]", "", text, flags=re.IGNORECASE)
            text = re.sub(r"\s*\(source:\s*[^)]+\)", "", text, flags=re.IGNORECASE)
            text = text.replace(
                "=== RETRIEVED MEMORIES: USER FACTS ===",
                "=== VERIFIED USER FACTS ===",
            )
            text = text.replace(
                "=== RETRIEVED MEMORIES: YOUR OWN ARCHITECTURE ===",
                "=== VERIFIED SYSTEM FACTS ===",
            )
        text = self._filter_structured_user_fact_sections(text)
        max_chars = int(self.cloud_policy.max_context_chars or 0)
        if max_chars > 0 and len(text) > max_chars:
            text = text[:max_chars].rstrip() + "\n\n[Prompt truncated by hybrid cloud policy]"
        return text

    def _scrub_messages_for_cloud(
        self, messages: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        safe: List[Dict[str, Any]] = []
        for item in list(messages or []):
            if not isinstance(item, dict):
                continue
            safe_item = dict(item)
            content = item.get("content")
            if isinstance(content, str):
                safe_item["content"] = self._scrub_prompt_for_cloud(content)
            safe.append(safe_item)
        return safe

    # ── Rate limiting ─────────────────────────────────────────────────

    def _check_anthropic_rate_limit(self) -> bool:
        if self.rate_limiter is None:
            return True
        return self.rate_limiter.can_request()

    def _record_anthropic_usage(self, tokens: int = 0) -> None:
        if self.rate_limiter is not None:
            self.rate_limiter.record_request(tokens)

    # ── Visible text extraction ───────────────────────────────────────

    def _resolve_visible_text(self, content: str, thinking: str = "") -> str:
        """Return visible text, stripping <think> tags. Matches OllamaClient."""
        visible = str(content or "").strip()
        if visible:
            _, visible = extract_think_content(visible)
            visible = str(visible or "").strip()
            if visible:
                return visible

        thinking_text = str(thinking or "").strip()
        if not thinking_text:
            return ""

        if "<think>" in thinking_text.lower():
            _, extracted = extract_think_content(thinking_text)
            extracted = str(extracted or "").strip()
            if extracted:
                return extracted

        # Native thinking field with no content — try last line as answer
        lines = [ln.strip() for ln in thinking_text.splitlines() if ln.strip()]
        if lines:
            _meta = ("so ", "wait", "hmm", "let me", "i think", "i need",
                     "but ", "however", "actually", "okay")
            last = lines[-1]
            if not last.lower().startswith(_meta) and len(last) > 5:
                return last
            if len(lines) >= 2:
                second_last = lines[-2]
                if not second_last.lower().startswith(_meta) and len(second_last) > 5:
                    return second_last

        return "[Model returned internal reasoning without a final answer. Please retry.]"

    # ── Core LiteLLM call ─────────────────────────────────────────────

    def _ollama_direct_tool_call(self, messages, tools, max_tokens, temperature, model_name):
        """Bypass litellm and call Ollama directly for tool calls.

        Litellm corrupts Qwen3 thinking+tools responses (returns '{}').
        Direct Ollama /api/chat works correctly.
        """
        import requests as _req

        model = (model_name or self.ollama_model or "").replace("ollama/", "")
        effective_max = self._effective_max_tokens(max_tokens, model)

        # Flatten tool messages for multi-turn
        flat_messages = self._flatten_tool_messages_for_ollama(messages)

        payload = {
            "model": model,
            "messages": flat_messages,
            "stream": False,
            "options": {
                "temperature": temperature,
                "num_predict": effective_max,
            },
        }
        if tools:
            payload["tools"] = tools

        try:
            resp = _req.post(
                f"{self.ollama_base_url}/api/chat",
                json=payload,
                timeout=120,
            )
            if resp.status_code != 200:
                print(f"[LITELLM] Ollama direct call failed: HTTP {resp.status_code}")
                return None

            data = resp.json()
            msg = data.get("message", {})
            content = msg.get("content", "")
            tool_calls = msg.get("tool_calls", [])
            thinking = msg.get("thinking", "")

            # If thinking but no content, try to use thinking as fallback
            if not content and thinking:
                print(f"[LITELLM] Ollama thinking-only response, extracting visible text")
                content = self._resolve_visible_text(content, thinking=thinking)

            parsed_calls = []
            if tool_calls:
                for tc in tool_calls:
                    fn = tc.get("function", {})
                    parsed_calls.append({
                        "name": fn.get("name", ""),
                        "arguments": fn.get("arguments", {}),
                    })

            result = {
                "tool_calls": parsed_calls,
                "content": content,
                "used_tools": len(parsed_calls) > 0,
            }

            # Quality gate
            if parsed_calls:
                return result
            stripped = content.strip().lower()
            if stripped and stripped not in ("{}", "[]", "null", '""', "''"):
                return result

            print(f"[LITELLM] Ollama direct returned degenerate: {repr(content[:80])}")
            return None

        except Exception as e:
            print(f"[LITELLM] Ollama direct call error: {e}")
            return None

    @staticmethod
    def _flatten_tool_messages_for_ollama(messages: List[Dict]) -> List[Dict]:
        """Flatten tool_call / tool_result messages into plain chat for Ollama.

        Ollama (via LiteLLM's prompt template) chokes on multi-turn tool
        conversations — it returns '{}' on iteration 2+.  This converts:

          assistant: {tool_calls: [{name: "memory_recall", args: {query: "name"}}]}
          tool:      {content: "Nick [trust=0.95]"}

        Into:

          assistant: [Calling memory_recall({"query": "name"})]
          user:      [Tool result from memory_recall]: Nick [trust=0.95]

        Cloud models that handle OpenAI tool format correctly skip this path.
        """
        has_tool_content = any(
            m.get("role") == "tool" or m.get("tool_calls")
            for m in messages if isinstance(m, dict)
        )
        if not has_tool_content:
            return messages

        flat: List[Dict] = []
        for msg in messages:
            if not isinstance(msg, dict):
                flat.append(msg)
                continue

            role = msg.get("role", "")

            # Assistant message with tool_calls → convert to plain text
            if role == "assistant" and msg.get("tool_calls"):
                parts = []
                existing = msg.get("content") or ""
                if existing.strip():
                    parts.append(existing.strip())
                for tc in msg["tool_calls"]:
                    if isinstance(tc, dict):
                        fn = tc.get("function", tc)
                        name = fn.get("name", "unknown")
                        args = fn.get("arguments", {})
                        if isinstance(args, str):
                            args_str = args
                        else:
                            args_str = json.dumps(args)
                        parts.append(f"[Calling {name}({args_str})]")
                flat.append({"role": "assistant", "content": "\n".join(parts) or "..."})
                continue

            # Tool result message → convert to user message
            if role == "tool":
                name = msg.get("name", "tool")
                content = msg.get("content", "")
                flat.append({
                    "role": "user",
                    "content": f"[Tool result from {name}]: {content}",
                })
                continue

            # Everything else passes through (strip stale tool_calls from normal msgs)
            clean = {k: v for k, v in msg.items() if k != "tool_calls"}
            flat.append(clean)

        return flat

    @staticmethod
    def _fix_tool_call_ids(messages: List[Dict]) -> List[Dict]:
        """Ensure every tool_call in the message history has an 'id' field.

        LiteLLM's Ollama prompt template expects OpenAI-format tool calls
        with an 'id' key.  The CRT agent loop stores tool calls as
        {"name": ..., "arguments": ...} without 'id'.  This patch adds
        synthetic IDs so LiteLLM doesn't crash on iteration 2+.
        """
        fixed: List[Dict] = []
        call_counter = 0
        for msg in messages:
            if not isinstance(msg, dict):
                fixed.append(msg)
                continue
            msg = dict(msg)  # shallow copy

            # Fix assistant messages with tool_calls
            if msg.get("tool_calls"):
                new_tcs = []
                for tc in msg["tool_calls"]:
                    tc = dict(tc) if isinstance(tc, dict) else tc
                    if isinstance(tc, dict):
                        if "id" not in tc:
                            tc["id"] = f"call_{call_counter}"
                            call_counter += 1
                        # Ensure OpenAI structure: {"id", "type", "function": {"name", "arguments"}}
                        if "function" not in tc and "name" in tc:
                            args = tc.get("arguments", {})
                            if isinstance(args, dict):
                                args = json.dumps(args)
                            tc = {
                                "id": tc["id"],
                                "type": "function",
                                "function": {
                                    "name": tc["name"],
                                    "arguments": args,
                                },
                            }
                        elif "function" in tc:
                            # Already OpenAI format — ensure arguments is a string
                            fn = tc["function"]
                            if isinstance(fn, dict) and isinstance(fn.get("arguments"), dict):
                                tc["function"] = dict(fn)
                                tc["function"]["arguments"] = json.dumps(fn["arguments"])
                    new_tcs.append(tc)
                msg["tool_calls"] = new_tcs
                # Ollama requires content to be non-null on assistant msgs
                if msg.get("content") is None:
                    msg["content"] = ""

            # Fix tool result messages — must have a tool_call_id
            if msg.get("role") == "tool" and not msg.get("tool_call_id"):
                # Try to match by name to a preceding call, else use synthetic
                msg["tool_call_id"] = msg.get("name") or f"call_{call_counter}"

            fixed.append(msg)
        return fixed

    def _call(
        self,
        provider: str,
        model_name: Optional[str],
        messages: List[Dict],
        max_tokens: int,
        temperature: float,
        tools: Optional[List] = None,
        stream: bool = False,
        scrub: bool = False,
    ) -> Any:
        """Single litellm.completion call with token inflation and scrubbing."""
        params = self._to_litellm_params(provider, model_name)
        resolved_model = params.get("model", "")

        if scrub and provider in ("cloud", "anthropic"):
            messages = self._scrub_messages_for_cloud(messages)

        # For Ollama: flatten tool_call/tool_result messages into plain chat
        # so the prompt template doesn't choke (returns '{}' otherwise).
        # Keep tools available so Ollama can still make real tool calls.
        if provider == "local":
            messages = self._flatten_tool_messages_for_ollama(messages)

        # Patch tool call messages for LiteLLM compatibility (cloud models)
        messages = self._fix_tool_call_ids(messages)

        effective_max = self._effective_max_tokens(max_tokens, resolved_model)

        kwargs: Dict[str, Any] = {
            **params,
            "messages": messages,
            "max_tokens": effective_max,
            "temperature": temperature,
            "stream": stream,
        }
        if tools:
            kwargs["tools"] = tools

        if provider == "local" and tools:
            print(f"[LITELLM_DEBUG] Local tool call: model={resolved_model}, max_tokens={effective_max}, "
                  f"tools={len(tools)}, msgs={len(messages)}, "
                  f"msg_chars={sum(len(str(m.get('content',''))) for m in messages)}")

        return litellm.completion(**kwargs)

    # ── generate() ────────────────────────────────────────────────────

    def generate(
        self,
        prompt: str,
        system: Optional[str] = None,
        max_tokens: int = 500,
        temperature: float = 0.7,
        stream: bool = False,
        model: Optional[str] = None,
    ) -> str:
        messages: List[Dict[str, str]] = []
        if system:
            messages.append({"role": "system", "content": str(system)})
        messages.append({"role": "user", "content": str(prompt or "")})
        return self.chat(messages, max_tokens=max_tokens, temperature=temperature, model=model)

    # ── chat() ────────────────────────────────────────────────────────

    def chat(
        self,
        messages: List[Dict[str, str]],
        max_tokens: int = 500,
        temperature: float = 0.7,
        model: Optional[str] = None,
    ) -> str:
        provider, model_name = self._resolve_target(model)

        # Anthropic with rate limiting
        if provider == "anthropic":
            if self._check_anthropic_rate_limit():
                try:
                    resp = self._call(provider, model_name, messages, max_tokens,
                                      temperature, scrub=True)
                    content = resp.choices[0].message.content or ""
                    self._record_anthropic_usage()
                    return self._resolve_visible_text(content) or "[No response from Claude]"
                except Exception as e:
                    logger.warning("[LITELLM] Anthropic chat failed: %s", e)
                    return f"[Claude API error: {e}]"
            else:
                logger.info("[LITELLM] Anthropic rate limited, falling back to local")
                if self.rate_limiter:
                    self.rate_limiter.record_fallback()
                provider = "local"

        # Cloud route
        if provider == "cloud" and self.cloud_available:
            try:
                resp = self._call("cloud", model_name, messages, max_tokens,
                                  temperature, scrub=True)
                content = resp.choices[0].message.content or ""
                return self._resolve_visible_text(content) or "[Cloud LLM returned no visible answer]"
            except Exception as e:
                logger.warning("[LITELLM] Cloud chat failed: %s", e)
                return f"[Cloud LLM error: {e}]"

        # Local (Ollama) — default
        try:
            resp = self._call("local", model_name, messages, max_tokens, temperature)
            content = resp.choices[0].message.content or ""
            return self._resolve_visible_text(content) or ""
        except Exception as e:
            error_msg = str(e)
            if "connection" in error_msg.lower():
                return "[Ollama connection error: Is Ollama running? Try: ollama serve]"
            elif "not found" in error_msg.lower():
                target = model_name or self.ollama_model
                return f"[Model '{target}' not found. Try: ollama pull {target}]"
            return f"[Ollama error: {e}]"

    # ── chat_with_tools() ─────────────────────────────────────────────

    def _parse_tool_response(self, response) -> Dict[str, Any]:
        """Parse LiteLLM response into CRT tool call format."""
        msg = response.choices[0].message
        raw_content = msg.content or ""

        # Qwen3 thinking models: content may be in thinking_content or reasoning_content
        thinking = getattr(msg, "thinking_content", None) or getattr(msg, "reasoning_content", None) or ""
        if not raw_content and thinking:
            print(f"[LITELLM] Thinking model returned empty content, thinking={str(thinking)[:120]}")

        content = self._resolve_visible_text(raw_content, thinking=str(thinking))

        parsed_calls: List[Dict[str, Any]] = []
        if msg.tool_calls:
            for tc in msg.tool_calls:
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

        return {
            "tool_calls": parsed_calls,
            "content": content,
            "used_tools": len(parsed_calls) > 0,
        }

    def _try_local_tools(self, messages, tools, max_tokens, temperature, model_name):
        """Attempt local tool call with quality gate. Returns result or None."""
        try:
            # Bypass litellm for Ollama tool calls — litellm corrupts Qwen3 thinking+tools
            result = self._ollama_direct_tool_call(messages, tools, max_tokens, temperature, model_name)
            if result is not None:
                return result
            # Fallback to litellm path
            resp = self._call("local", model_name, messages, max_tokens,
                              temperature, tools=tools)
            result = self._parse_tool_response(resp)
        except Exception as e:
            print(f"[LITELLM] Local tool call failed: {e}")
            return None

        # Quality gate: tool calls are always valid
        if result["tool_calls"]:
            return result

        content = (result["content"] or "").strip()
        if content:
            _lower = content.lower()
            # Degenerate JSON-only responses (e.g. "{}", "[]", "null")
            if _lower in ("{}", "[]", "null", '""', "''"):
                print(f"[LITELLM] Local returned degenerate response '{content}', falling through")
                return None
            if not any(_lower.startswith(p) for p in self._META_STARTS):
                return result
            print(f"[LITELLM] Local returned meta-reasoning, falling through: {content[:100]}")
        else:
            print("[LITELLM] Local chat_with_tools returned empty, falling through")
        return None

    def _try_anthropic_tools(self, messages, tools, max_tokens, temperature, model_name):
        """Attempt Anthropic tool call. Returns result or None."""
        if not self.anthropic_api_key or not self._check_anthropic_rate_limit():
            return None
        try:
            resp = self._call("anthropic", model_name, messages, max_tokens,
                              temperature, tools=tools, scrub=True)
            self._record_anthropic_usage()
            return self._parse_tool_response(resp)
        except Exception as e:
            logger.warning("[LITELLM] Anthropic tool call failed: %s", e)
            return None

    def _try_cookie_text_fallback(self, messages) -> Optional[Dict[str, Any]]:
        """Last-resort fallback: use cookie-based Claude for a plain text answer.

        When local returns garbage and there's no Anthropic API key, try the
        cookie provider (CLAUDE_SESSION_COOKIE) for a text-only synthesis.
        No tool calling — just ask Claude to answer based on the conversation.
        """
        try:
            from .cloud_features import get_cloud_feature_service
            svc = get_cloud_feature_service()
            if svc is None or not svc._cookie_available():
                return None

            # Build a simple prompt from the message history
            prompt_parts: List[str] = []
            for msg in messages:
                role = msg.get("role", "user")
                content = msg.get("content", "")
                if not content or not isinstance(content, str):
                    continue
                if role == "system":
                    continue  # system prompt is too long; cookie has its own
                if role == "tool":
                    # Include tool results as context
                    name = msg.get("name", "tool")
                    prompt_parts.append(f"[Tool result from {name}]: {content[:500]}")
                elif role == "user":
                    prompt_parts.append(f"User: {content}")
                elif role == "assistant" and content.strip():
                    prompt_parts.append(f"Assistant: {content[:300]}")

            if not prompt_parts:
                return None

            system = (
                "You are a personal AI assistant powered by Claude, running in a persistent memory system. "
                "The user asked a question and tools have already gathered the information below. "
                "Synthesize a direct, natural answer from the tool results. "
                "Be concise and warm. Speak in first person. "
                "When stating facts about the user, use second person (your/you). "
                "Reply with ONLY the answer text — no JSON, no markdown fences, no wrapping."
            )
            prompt = "\n".join(prompt_parts[-8:])  # last 8 turns max

            print("[LITELLM] Trying cookie-based Claude fallback for text answer")
            raw = svc._call_cookie_text(system, prompt, max_tokens=1024, feature="agent_fallback")
            if raw and raw.strip():
                text = raw.strip()
                # Strip JSON/markdown wrapping if Claude ignores the instruction
                text = self._unwrap_json_response(text)
                print(f"[LITELLM] Cookie fallback succeeded: {len(text)} chars")
                return {"tool_calls": [], "content": text, "used_tools": False}

            print("[LITELLM] Cookie fallback returned empty")
        except Exception as e:
            print(f"[LITELLM] Cookie fallback failed: {e}")
        return None

    @staticmethod
    def _unwrap_json_response(text: str) -> str:
        """Extract plain text from JSON-wrapped or markdown-fenced responses."""
        t = text.strip()
        # Strip markdown code fences
        if t.startswith("```"):
            lines = t.split("\n")
            lines = [l for l in lines if not l.strip().startswith("```")]
            t = "\n".join(lines).strip()
        # Try to extract text from JSON wrapper
        if t.startswith("{"):
            try:
                parsed = json.loads(t)
                if isinstance(parsed, dict):
                    # Look for common text keys
                    for key in ("response", "answer", "content", "text", "message"):
                        if key in parsed and isinstance(parsed[key], str):
                            return parsed[key].strip()
            except (json.JSONDecodeError, TypeError):
                pass
        return t

    def chat_with_tools(
        self,
        messages: List[Dict[str, Any]],
        tools: List[Dict[str, Any]],
        max_tokens: int = 1000,
        temperature: float = 0.3,
        model: Optional[str] = None,
    ) -> Dict[str, Any]:
        provider, model_name = self._resolve_target(model)

        # Explicit anthropic prefix
        if provider == "anthropic":
            result = self._try_anthropic_tools(
                messages, tools, max_tokens, temperature, model_name,
            )
            if result:
                return result
            if self.rate_limiter:
                self.rate_limiter.record_fallback()

        policy = self.fallback_policy or "cloud_to_local"

        # Respect cloud_claude_enabled setting — downgrade cloud policies to local_only
        if policy in ("local_to_cloud", "cloud_only", "cloud_to_local"):
            try:
                import auth as _auth_mod
                _cloud_on = str(_auth_mod.get_user_setting(1, "cloud_claude_enabled", "false")).lower() in ("true", "1", "yes", "on")
                if not _cloud_on:
                    print(f"[LITELLM] Cloud disabled in settings, overriding {policy} → local_only")
                    policy = "local_only"
            except Exception:
                pass

        if policy == "cloud_only":
            result = self._try_anthropic_tools(
                messages, tools, max_tokens, temperature, model_name,
            )
            if result:
                return result
            result = self._try_cookie_text_fallback(messages)
            return result or {
                "tool_calls": [], "content": "[Cloud unavailable or rate-limited]",
                "used_tools": False,
            }

        if policy == "local_only":
            result = self._try_local_tools(
                messages, tools, max_tokens, temperature, model_name,
            )
            if result:
                return result
            # Local tool call failed — retry without tools for a plain text answer
            print("[LITELLM] Local tool call failed, retrying without tools for text answer")
            try:
                resp = self._call("local", model_name, messages, max_tokens, temperature)
                text = (resp.get("content") or "").strip() if isinstance(resp, dict) else str(resp).strip()
                if text and text.lower() not in ("{}", "[]", "null", '""', "''"):
                    return {"tool_calls": [], "content": text, "used_tools": False}
            except Exception as _e:
                print(f"[LITELLM] Local text-only retry also failed: {_e}")
            return {"tool_calls": [], "content": "", "used_tools": False}

        if policy == "cloud_to_local":
            result = self._try_anthropic_tools(
                messages, tools, max_tokens, temperature, model_name,
            )
            if result:
                return result
            print("[LITELLM] Cloud unavailable, trying local")
            result = self._try_local_tools(
                messages, tools, max_tokens, temperature, model_name,
            )
            return result or {"tool_calls": [], "content": "", "used_tools": False}

        # Default: cloud_to_local (cloud-first, local as last resort)
        result = self._try_anthropic_tools(
            messages, tools, max_tokens, temperature, model_name,
        )
        if result:
            return result
        print("[LITELLM] Cloud failed, trying cookie fallback")
        result = self._try_cookie_text_fallback(messages)
        if result:
            return result
        print("[LITELLM] Cookie failed, trying local (Ollama) as last resort")
        result = self._try_local_tools(
            messages, tools, max_tokens, temperature, model_name,
        )
        return result or {"tool_calls": [], "content": "", "used_tools": False}

    # ── chat_stream() ─────────────────────────────────────────────────

    def chat_stream(
        self,
        messages: List[Dict[str, str]],
        max_tokens: int = 500,
        temperature: float = 0.7,
        model: Optional[str] = None,
    ) -> Generator[Tuple[str, str], None, None]:
        """Stream (token_type, text) tuples. token_type: 'thinking' | 'content'."""
        provider, model_name = self._resolve_target(model)

        if provider == "anthropic" and self.anthropic_available:
            if self._check_anthropic_rate_limit():
                yield from self._stream_provider(
                    "anthropic", model_name, messages, max_tokens, temperature, scrub=True,
                )
                self._record_anthropic_usage()
                return
            else:
                logger.info("[LITELLM] Anthropic rate limited for stream, falling back")
                if self.rate_limiter:
                    self.rate_limiter.record_fallback()

        # Local route (default)
        yield from self._stream_provider(
            "local", model_name, messages, max_tokens, temperature,
        )

    def _stream_provider(
        self, provider: str, model_name: Optional[str], messages: List[Dict],
        max_tokens: int, temperature: float, scrub: bool = False,
    ) -> Generator[Tuple[str, str], None, None]:
        """Stream from a provider, parsing inline <think> tags."""
        try:
            resp = self._call(
                provider, model_name, messages, max_tokens, temperature,
                stream=True, scrub=scrub,
            )
        except Exception as e:
            yield ("content", f"[stream error: {e}]")
            return

        in_think = False
        buf = ""

        try:
            for chunk in resp:
                if not chunk.choices:
                    continue
                delta = chunk.choices[0].delta
                if not delta:
                    continue
                content_tok = delta.content or ""
                if not content_tok:
                    continue

                # Parse inline <think>...</think> tags
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

    # ── chat_with_image() ─────────────────────────────────────────────

    def chat_with_image(
        self,
        prompt: str,
        image_b64: str,
        image_media_type: str = "image/png",
        max_tokens: int = 1024,
        temperature: float = 0.5,
        model: Optional[str] = None,
    ) -> str:
        """Vision chat. Routes to Anthropic by default."""
        provider, model_name = self._resolve_target(model or "anthropic:")

        messages: List[Dict[str, Any]] = [{
            "role": "user",
            "content": [
                {
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:{image_media_type};base64,{image_b64}",
                    },
                },
                {"type": "text", "text": prompt},
            ],
        }]

        try:
            resp = self._call(provider, model_name, messages, max_tokens, temperature)
            content = resp.choices[0].message.content or ""
            return content.strip() or "[No response]"
        except Exception as e:
            logger.warning("[LITELLM] chat_with_image failed: %s", e)
            return f"[Vision error: {e}]"


# ── Factory ──────────────────────────────────────────────────────────────


def create_llm_client(
    runtime_cfg: Optional[Dict[str, Any]] = None,
) -> Optional[UnifiedLLMClient]:
    """Factory replacing create_primary_llm_client. Returns None if no provider available."""
    runtime_cfg = runtime_cfg or {}
    product_cfg = (runtime_cfg.get("product_mode") or {}) if isinstance(runtime_cfg, dict) else {}
    generation_cfg = (runtime_cfg.get("generation_stack") or {}) if isinstance(runtime_cfg, dict) else {}
    local_cfg = (generation_cfg.get("local") or {}) if isinstance(generation_cfg, dict) else {}
    cloud_cfg = (generation_cfg.get("cloud") or {}) if isinstance(generation_cfg, dict) else {}
    anthropic_cfg = (generation_cfg.get("anthropic") or {}) if isinstance(generation_cfg, dict) else {}
    model_roles_cfg = (generation_cfg.get("model_roles") or {}) if isinstance(generation_cfg, dict) else {}

    product_mode = str(
        (product_cfg or {}).get("mode")
        or os.getenv("CRT_PRODUCT_MODE")
        or "local_only"
    ).strip().lower()

    # ── Local ─────────────────────────────────────────────────────
    local_enabled = bool(local_cfg.get("enabled", True)) and _env_bool("CRT_ENABLE_LLM", True)
    ollama_model = str(
        os.getenv("CRT_OLLAMA_MODEL")
        or local_cfg.get("default_model")
        or "llama3.2:latest"
    ).strip()

    # ── Cloud (OpenAI-compatible) ─────────────────────────────────
    cloud_enabled = bool(cloud_cfg.get("enabled", False)) and product_mode == "hybrid_verified"
    cloud_model = str(os.getenv("CRT_CLOUD_MODEL") or cloud_cfg.get("model") or "").strip()
    cloud_api_key = str(os.getenv("OPENAI_API_KEY") or "").strip()
    cloud_base_url = str(
        os.getenv("CRT_CLOUD_BASE_URL") or cloud_cfg.get("base_url") or ""
    ).strip()

    # ── Anthropic ─────────────────────────────────────────────────
    anthropic_enabled = bool(anthropic_cfg.get("enabled", False))
    anthropic_model = str(
        os.getenv("CRT_ANTHROPIC_MODEL")
        or anthropic_cfg.get("model")
        or "claude-sonnet-4-6"
    ).strip()
    anthropic_api_key_env = str(anthropic_cfg.get("api_key_env") or "ANTHROPIC_API_KEY").strip()
    anthropic_api_key = str(os.getenv(anthropic_api_key_env) or "").strip()

    # ── Rate limiter ──────────────────────────────────────────────
    rate_limiter = None
    if anthropic_enabled and anthropic_api_key:
        rate_limits = anthropic_cfg.get("rate_limits") or {}
        rpm = int(rate_limits.get("rpm") or os.getenv("CRT_ANTHROPIC_RPM") or 50)
        tpd = int(rate_limits.get("tpd") or os.getenv("CRT_ANTHROPIC_TPD") or 1_000_000)
        try:
            from .rate_limiter import PersonalRateLimiter
            rate_limiter = PersonalRateLimiter(provider="anthropic", rpm_limit=rpm, tpd_limit=tpd)
        except Exception as e:
            logger.warning("[LITELLM] Failed to init rate limiter: %s", e)

    # ── Model roles ───────────────────────────────────────────────
    model_roles: Dict[str, str] = {}
    for role_name, role_model in model_roles_cfg.items():
        env_key = f"CRT_MODEL_ROLE_{str(role_name).upper()}"
        model_roles[str(role_name)] = str(os.getenv(env_key) or role_model or "").strip()
    if model_roles:
        logger.info("[LITELLM] Model roles: %s", model_roles)

    # ── Cloud prompt policy ───────────────────────────────────────
    policy_cfg = {
        "redact_memory_metadata": bool(cloud_cfg.get("redact_memory_metadata", True)),
        "max_context_chars": int(cloud_cfg.get("max_context_chars") or 14000),
        "fact_allowlist": tuple(
            str(x).strip() for x in (cloud_cfg.get("fact_allowlist") or []) if str(x).strip()
        ),
        "slot_denylist": tuple(
            str(x).strip() for x in (cloud_cfg.get("slot_denylist") or []) if str(x).strip()
        ),
    }

    # ── Availability check ────────────────────────────────────────
    has_local = local_enabled and bool(ollama_model)
    has_cloud = cloud_enabled and bool(cloud_model) and bool(cloud_api_key)
    has_anthropic = anthropic_enabled and bool(anthropic_api_key)

    if not has_local and not has_cloud and not has_anthropic:
        return None

    return UnifiedLLMClient({
        "ollama_model": ollama_model if local_enabled else "",
        "ollama_base_url": os.getenv("OLLAMA_BASE_URL", "http://localhost:11434"),
        "cloud_model": cloud_model if cloud_enabled else "",
        "cloud_api_key": cloud_api_key if cloud_enabled else "",
        "cloud_base_url": cloud_base_url,
        "anthropic_model": anthropic_model if anthropic_enabled else "",
        "anthropic_api_key": anthropic_api_key if anthropic_enabled else "",
        "product_mode": product_mode,
        "model_roles": model_roles,
        "fallback_enabled": True,
        "rate_limiter": rate_limiter,
        **policy_cfg,
    })


# ── Convenience helpers (replace get_ollama_client / AnthropicClient) ────


_default_client: Optional[UnifiedLLMClient] = None


def get_default_llm_client(model: str = None) -> UnifiedLLMClient:
    """Get or create a default UnifiedLLMClient. Drop-in for get_ollama_client()."""
    global _default_client
    model = model or os.getenv("CRT_OLLAMA_MODEL", "qwen3:14b")
    if _default_client is None or _default_client.ollama_model != model:
        _default_client = UnifiedLLMClient({"ollama_model": model})
    return _default_client


def create_vision_client() -> UnifiedLLMClient:
    """Create a UnifiedLLMClient configured for Anthropic vision. Replaces AnthropicClient()."""
    return UnifiedLLMClient({
        "anthropic_api_key": os.getenv("ANTHROPIC_API_KEY", ""),
        "anthropic_model": os.getenv("CRT_ANTHROPIC_MODEL", "claude-sonnet-4-6"),
        "ollama_model": "",
    })
