from __future__ import annotations

import logging
import os
import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

import requests

from .ollama_client import OllamaClient
from .text_utils import extract_think_content

logger = logging.getLogger(__name__)

# Lazy import to avoid hard dependency
_AnthropicClient = None

def _get_anthropic_client_class():
    global _AnthropicClient
    if _AnthropicClient is None:
        try:
            from .anthropic_client import AnthropicClient
            _AnthropicClient = AnthropicClient
        except ImportError:
            _AnthropicClient = None
    return _AnthropicClient


def _env_bool(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return str(raw).strip().lower() in {"1", "true", "yes", "y", "on"}


def _normalize_visible_text(content: str) -> str:
    visible = str(content or "").strip()
    if visible:
        return visible
    _, extracted_visible = extract_think_content(str(content or ""))
    extracted_visible = str(extracted_visible or "").strip()
    return extracted_visible


@dataclass
class CloudPromptPolicy:
    redact_memory_metadata: bool = True
    max_context_chars: int = 14000
    fact_allowlist: Tuple[str, ...] = ()
    slot_denylist: Tuple[str, ...] = ()


class OpenAICompatibleClient:
    """Minimal OpenAI-compatible chat client using plain HTTP."""

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
        return self.chat(
            messages,
            max_tokens=max_tokens,
            temperature=temperature,
            model=model,
            stream=stream,
        )

    def chat(
        self,
        messages: List[Dict[str, str]],
        max_tokens: int = 500,
        temperature: float = 0.7,
        model: Optional[str] = None,
        stream: bool = False,
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
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        try:
            resp = requests.post(
                f"{self.base_url}/chat/completions",
                json=payload,
                headers=headers,
                timeout=self.timeout_seconds,
            )
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
                if isinstance(item, dict):
                    text = item.get("text")
                    if text:
                        parts.append(str(text))
            content = "".join(parts)
        return _normalize_visible_text(str(content or "")) or "[Cloud LLM returned no visible answer]"


class HybridLLMClient:
    """Local-first client that can explicitly route generation to cloud or Anthropic."""

    def __init__(
        self,
        *,
        local_client: Optional[OllamaClient] = None,
        cloud_client: Optional[OpenAICompatibleClient] = None,
        anthropic_client: Optional[Any] = None,
        product_mode: str = "local_only",
        cloud_policy: Optional[CloudPromptPolicy] = None,
        rate_limiter: Optional[Any] = None,
        model_roles: Optional[Dict[str, str]] = None,
    ) -> None:
        self.local_client = local_client
        self.cloud_client = cloud_client
        self.anthropic_client = anthropic_client
        self.product_mode = str(product_mode or "local_only").strip().lower() or "local_only"
        self.cloud_policy = cloud_policy or CloudPromptPolicy()
        self.rate_limiter = rate_limiter
        self.model_roles: Dict[str, str] = model_roles or {}

    @property
    def model(self) -> str:
        if self.local_client is not None:
            return str(getattr(self.local_client, "model", "") or "")
        if self.anthropic_client is not None:
            return str(getattr(self.anthropic_client, "model", "") or "")
        if self.cloud_client is not None:
            return str(getattr(self.cloud_client, "model", "") or "")
        return ""

    @property
    def cloud_available(self) -> bool:
        return bool(self.cloud_client is not None and self.cloud_client.is_available)

    @property
    def anthropic_available(self) -> bool:
        return bool(self.anthropic_client is not None and getattr(self.anthropic_client, "is_available", False))

    def _resolve_target(self, model: Optional[str]) -> Tuple[str, Optional[str]]:
        """
        Resolve a model string to (provider, model_name).

        Supported prefixes:
          - "anthropic:claude-sonnet-4-6" → ("anthropic", "claude-sonnet-4-6")
          - "cloud:gpt-4o" → ("cloud", "gpt-4o")
          - "local:qwen3:14b" → ("local", "qwen3:14b")
          - "role:answer" → looks up model_roles["answer"] → re-resolves
          - plain string → ("local", string)

        Also checks env var overrides: CRT_MODEL_ROLE_{ROLE} (e.g. CRT_MODEL_ROLE_ANSWER)
        """
        selected = str(model or "").strip()

        # Role-based resolution
        if selected.startswith("role:"):
            role_name = selected.split(":", 1)[1].strip()
            # Env var override (hot-switchable without restart)
            env_key = f"CRT_MODEL_ROLE_{role_name.upper()}"
            resolved = os.getenv(env_key) or self.model_roles.get(role_name, "")
            if not resolved:
                return "local", None
            # Re-resolve the looked-up value (could be "anthropic:..." etc)
            return self._resolve_target(resolved)

        if selected.startswith("anthropic:"):
            return "anthropic", selected.split(":", 1)[1].strip() or None
        if selected.startswith("cloud:"):
            return "cloud", selected.split(":", 1)[1].strip() or None
        if selected.startswith("local:"):
            return "local", selected.split(":", 1)[1].strip() or None
        return "local", selected or None

    def _check_anthropic_rate_limit(self) -> bool:
        """Check if Anthropic requests are within rate limits. Returns True if OK."""
        if self.rate_limiter is None:
            return True
        return self.rate_limiter.can_request()

    def _record_anthropic_usage(self, tokens: int = 0) -> None:
        """Record an Anthropic API call for rate limiting."""
        if self.rate_limiter is not None:
            self.rate_limiter.record_request(tokens)

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
            match = re.search(r"\b(?:FACT|PREF):\s*([A-Za-z0-9_ ]+)\s*=\s*(.+?)\s*$", clean, flags=re.IGNORECASE)
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
            r"(=== (?:RETRIEVED MEMORIES: USER FACTS|VERIFIED USER FACTS) ===\n)(.*?)(?=\n===|\Z)",
            flags=re.DOTALL,
        )

        def _user_fact_repl(match: re.Match[str]) -> str:
            header = match.group(1)
            body = match.group(2)
            return header + self._filter_user_fact_lines(body, numbered=True)

        text = user_fact_pattern.sub(_user_fact_repl, text)

        context_pattern = re.compile(
            r"(Context from memory \(facts ABOUT THE USER\):\n)(.*?)(?=\n\n|\Z)",
            flags=re.DOTALL,
        )

        def _context_repl(match: re.Match[str]) -> str:
            header = match.group(1)
            body = match.group(2)
            return header + self._filter_user_fact_lines(body, numbered=False)

        text = context_pattern.sub(_context_repl, text)

        memory_context_pattern = re.compile(
            r"(MEMORY_CONTEXT \(for reference only; do not fact-check it\):\n)(.*?)(?=\n\n[A-Z]|\Z)",
            flags=re.DOTALL,
        )

        def _memory_ctx_repl(match: re.Match[str]) -> str:
            header = match.group(1)
            body = match.group(2)
            return header + self._filter_user_fact_lines(body, numbered=False)

        return memory_context_pattern.sub(_memory_ctx_repl, text)

    def _scrub_prompt_for_cloud(self, prompt: str) -> str:
        text = str(prompt or "")
        if self.cloud_policy.redact_memory_metadata:
            text = re.sub(r"\s*\[trust:\s*[^\]]+\]", "", text, flags=re.IGNORECASE)
            text = re.sub(r"\s*\[similarity:\s*[^\]]+\]", "", text, flags=re.IGNORECASE)
            text = re.sub(r"\s*\(source:\s*[^)]+\)", "", text, flags=re.IGNORECASE)
            text = text.replace("=== RETRIEVED MEMORIES: USER FACTS ===", "=== VERIFIED USER FACTS ===")
            text = text.replace("=== RETRIEVED MEMORIES: YOUR OWN ARCHITECTURE ===", "=== VERIFIED SYSTEM FACTS ===")
        text = self._filter_structured_user_fact_sections(text)
        max_chars = int(self.cloud_policy.max_context_chars or 0)
        if max_chars > 0 and len(text) > max_chars:
            text = text[:max_chars].rstrip() + "\n\n[Prompt truncated by hybrid cloud policy]"
        return text

    def generate(
        self,
        prompt: str,
        system: Optional[str] = None,
        max_tokens: int = 500,
        temperature: float = 0.7,
        stream: bool = False,
        model: Optional[str] = None,
    ) -> str:
        provider, selected_model = self._resolve_target(model)

        # Anthropic route
        if provider == "anthropic" and self.anthropic_client is not None:
            if self._check_anthropic_rate_limit():
                safe_prompt = self._scrub_prompt_for_cloud(prompt)
                result = self.anthropic_client.generate(
                    safe_prompt, system=system, max_tokens=max_tokens,
                    temperature=temperature, model=selected_model,
                )
                self._record_anthropic_usage()
                return result
            else:
                logger.info("[HYBRID] Anthropic rate limited, falling back to local")
                if self.rate_limiter:
                    self.rate_limiter.record_fallback()
                provider = "local"

        if provider == "cloud" and self.cloud_available and self.cloud_client is not None:
            safe_prompt = self._scrub_prompt_for_cloud(prompt)
            return self.cloud_client.generate(
                safe_prompt, system=system, max_tokens=max_tokens,
                temperature=temperature, stream=stream, model=selected_model,
            )

        if self.local_client is not None:
            return self.local_client.generate(
                prompt, system=system, max_tokens=max_tokens,
                temperature=temperature, stream=stream, model=selected_model,
            )

        if self.cloud_client is not None:
            safe_prompt = self._scrub_prompt_for_cloud(prompt)
            return self.cloud_client.generate(
                safe_prompt, system=system, max_tokens=max_tokens,
                temperature=temperature, stream=stream, model=selected_model,
            )

        return "[No LLM available]"

    def chat(
        self,
        messages: List[Dict[str, str]],
        max_tokens: int = 500,
        temperature: float = 0.7,
        model: Optional[str] = None,
    ) -> str:
        provider, selected_model = self._resolve_target(model)

        # Anthropic route
        if provider == "anthropic" and self.anthropic_client is not None:
            if self._check_anthropic_rate_limit():
                safe_messages = self._scrub_messages_for_cloud(messages)
                result = self.anthropic_client.chat(
                    safe_messages, max_tokens=max_tokens,
                    temperature=temperature, model=selected_model,
                )
                self._record_anthropic_usage()
                return result
            else:
                logger.info("[HYBRID] Anthropic rate limited, falling back to local")
                if self.rate_limiter:
                    self.rate_limiter.record_fallback()
                provider = "local"

        if provider == "cloud" and self.cloud_available and self.cloud_client is not None:
            safe_messages = self._scrub_messages_for_cloud(messages)
            return self.cloud_client.chat(
                safe_messages, max_tokens=max_tokens,
                temperature=temperature, model=selected_model,
            )

        if self.local_client is not None:
            return self.local_client.chat(
                messages, max_tokens=max_tokens,
                temperature=temperature, model=selected_model,
            )

        if self.cloud_client is not None:
            return self.cloud_client.chat(
                messages, max_tokens=max_tokens,
                temperature=temperature, model=selected_model,
            )

        return "[No LLM available]"

    def _scrub_messages_for_cloud(self, messages: List[Dict[str, str]]) -> List[Dict[str, str]]:
        """Scrub PII from messages before sending to cloud/anthropic."""
        safe_messages: List[Dict[str, str]] = []
        for item in list(messages or []):
            if not isinstance(item, dict):
                continue
            safe_item = dict(item)
            safe_item["content"] = self._scrub_prompt_for_cloud(str(item.get("content") or ""))
            safe_messages.append(safe_item)
        return safe_messages

    def chat_with_tools(
        self,
        messages: List[Dict[str, Any]],
        tools: List[Dict[str, Any]],
        max_tokens: int = 1000,
        temperature: float = 0.3,
        model: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Tool-calling — routes to anthropic, local, or cloud."""
        provider, selected_model = self._resolve_target(model)

        # Anthropic route — Claude has native tool calling
        if provider == "anthropic" and self.anthropic_client is not None:
            if self._check_anthropic_rate_limit():
                safe_messages = self._scrub_messages_for_cloud(messages)
                result = self.anthropic_client.chat_with_tools(
                    safe_messages, tools=tools, max_tokens=max_tokens,
                    temperature=temperature, model=selected_model,
                )
                self._record_anthropic_usage()
                return result
            else:
                logger.info("[HYBRID] Anthropic rate limited for tool call, falling back to local")
                if self.rate_limiter:
                    self.rate_limiter.record_fallback()

        # Local route (default)
        if self.local_client is not None and hasattr(self.local_client, "chat_with_tools"):
            return self.local_client.chat_with_tools(
                messages, tools=tools, max_tokens=max_tokens,
                temperature=temperature, model=selected_model,
            )

        # Anthropic fallback if local unavailable
        if self.anthropic_client is not None and self._check_anthropic_rate_limit():
            result = self.anthropic_client.chat_with_tools(
                messages, tools=tools, max_tokens=max_tokens,
                temperature=temperature, model=selected_model,
            )
            self._record_anthropic_usage()
            return result

        return {"tool_calls": [], "content": "", "used_tools": False}

    def chat_stream(
        self,
        messages: List[Dict[str, str]],
        max_tokens: int = 500,
        temperature: float = 0.7,
        model: Optional[str] = None,
    ):
        """Stream (token_type, text) tuples — routes to anthropic, local, or cloud."""
        provider, selected_model = self._resolve_target(model)

        # Anthropic route — Claude supports streaming
        if provider == "anthropic" and self.anthropic_client is not None:
            if self._check_anthropic_rate_limit():
                safe_messages = self._scrub_messages_for_cloud(messages)
                yield from self.anthropic_client.chat_stream(
                    safe_messages, max_tokens=max_tokens,
                    temperature=temperature, model=selected_model,
                )
                self._record_anthropic_usage()
                return
            else:
                logger.info("[HYBRID] Anthropic rate limited for stream, falling back to local")
                if self.rate_limiter:
                    self.rate_limiter.record_fallback()

        # Local route (default)
        if self.local_client is not None:
            yield from self.local_client.chat_stream(
                messages, max_tokens=max_tokens, temperature=temperature, model=selected_model
            )
        else:
            # No streaming available — yield full response as single content token
            yield ("content", self.chat(messages, max_tokens, temperature, model))


def create_primary_llm_client(runtime_cfg: Optional[Dict[str, Any]] = None) -> Optional[HybridLLMClient]:
    runtime_cfg = runtime_cfg or {}
    product_cfg = runtime_cfg.get("product_mode") if isinstance(runtime_cfg, dict) else {}
    generation_cfg = runtime_cfg.get("generation_stack") if isinstance(runtime_cfg, dict) else {}
    local_cfg = (generation_cfg.get("local") or {}) if isinstance(generation_cfg, dict) else {}
    cloud_cfg = (generation_cfg.get("cloud") or {}) if isinstance(generation_cfg, dict) else {}
    anthropic_cfg = (generation_cfg.get("anthropic") or {}) if isinstance(generation_cfg, dict) else {}
    model_roles_cfg = (generation_cfg.get("model_roles") or {}) if isinstance(generation_cfg, dict) else {}

    product_mode = str((product_cfg or {}).get("mode") or os.getenv("CRT_PRODUCT_MODE") or "local_only").strip().lower()

    # ── Local client ──────────────────────────────────────────────────
    local_enabled = bool(local_cfg.get("enabled", True)) and _env_bool("CRT_ENABLE_LLM", True)
    local_model = str(os.getenv("CRT_OLLAMA_MODEL") or local_cfg.get("default_model") or "llama3.2:latest").strip()

    local_client: Optional[OllamaClient] = None
    if local_enabled:
        try:
            local_client = OllamaClient(model=local_model)
        except Exception:
            local_client = None

    # ── Cloud client (OpenAI-compatible) ──────────────────────────────
    cloud_enabled = bool(cloud_cfg.get("enabled", False)) and product_mode == "hybrid_verified"
    cloud_model = str(os.getenv("CRT_CLOUD_MODEL") or cloud_cfg.get("model") or "").strip()
    cloud_api_key_env = str(cloud_cfg.get("api_key_env") or "OPENAI_API_KEY").strip()
    cloud_base_url = str(os.getenv("CRT_CLOUD_BASE_URL") or cloud_cfg.get("base_url") or "https://api.openai.com/v1").strip()
    cloud_timeout = float(os.getenv("CRT_CLOUD_TIMEOUT_SECONDS") or cloud_cfg.get("timeout_seconds") or 120)

    cloud_client: Optional[OpenAICompatibleClient] = None
    if cloud_enabled and cloud_model:
        candidate = OpenAICompatibleClient(
            model=cloud_model,
            api_key_env=cloud_api_key_env,
            base_url=cloud_base_url,
            timeout_seconds=cloud_timeout,
            provider_label=str(cloud_cfg.get("provider") or "openai_compatible"),
        )
        if candidate.is_available:
            cloud_client = candidate

    # ── Anthropic client ──────────────────────────────────────────────
    anthropic_enabled = bool(anthropic_cfg.get("enabled", False))
    anthropic_model = str(os.getenv("CRT_ANTHROPIC_MODEL") or anthropic_cfg.get("model") or "claude-sonnet-4-6").strip()
    anthropic_api_key_env = str(anthropic_cfg.get("api_key_env") or "ANTHROPIC_API_KEY").strip()
    anthropic_timeout = float(anthropic_cfg.get("timeout_seconds") or 120)

    anthropic_client = None
    if anthropic_enabled and os.getenv(anthropic_api_key_env):
        AnthropicClientClass = _get_anthropic_client_class()
        if AnthropicClientClass is not None:
            try:
                anthropic_client = AnthropicClientClass(
                    model=anthropic_model,
                    api_key_env=anthropic_api_key_env,
                    timeout_seconds=anthropic_timeout,
                )
                logger.info("[HYBRID] Anthropic client initialized: model=%s", anthropic_model)
            except Exception as e:
                logger.warning("[HYBRID] Failed to init Anthropic client: %s", e)
                anthropic_client = None
        else:
            logger.info("[HYBRID] anthropic package not installed, skipping Anthropic client")

    # ── Rate limiter ──────────────────────────────────────────────────
    rate_limiter = None
    if anthropic_client is not None:
        rate_limits = anthropic_cfg.get("rate_limits") or {}
        rpm = int(rate_limits.get("rpm") or os.getenv("CRT_ANTHROPIC_RPM") or 50)
        tpd = int(rate_limits.get("tpd") or os.getenv("CRT_ANTHROPIC_TPD") or 1_000_000)
        try:
            from .rate_limiter import PersonalRateLimiter
            rate_limiter = PersonalRateLimiter(provider="anthropic", rpm_limit=rpm, tpd_limit=tpd)
        except Exception as e:
            logger.warning("[HYBRID] Failed to init rate limiter: %s", e)

    # ── Model roles ───────────────────────────────────────────────────
    model_roles: Dict[str, str] = {}
    for role_name, role_model in model_roles_cfg.items():
        # Env var override: CRT_MODEL_ROLE_ANSWER, CRT_MODEL_ROLE_FAST, etc.
        env_key = f"CRT_MODEL_ROLE_{str(role_name).upper()}"
        model_roles[str(role_name)] = str(os.getenv(env_key) or role_model or "").strip()
    if model_roles:
        logger.info("[HYBRID] Model roles: %s", model_roles)

    # ── Cloud prompt policy ───────────────────────────────────────────
    policy = CloudPromptPolicy(
        redact_memory_metadata=bool(cloud_cfg.get("redact_memory_metadata", True)),
        max_context_chars=int(cloud_cfg.get("max_context_chars") or 14000),
        fact_allowlist=tuple(str(x).strip() for x in (cloud_cfg.get("fact_allowlist") or []) if str(x).strip()),
        slot_denylist=tuple(str(x).strip() for x in (cloud_cfg.get("slot_denylist") or []) if str(x).strip()),
    )

    if local_client is None and cloud_client is None and anthropic_client is None:
        return None

    return HybridLLMClient(
        local_client=local_client,
        cloud_client=cloud_client,
        anthropic_client=anthropic_client,
        product_mode=product_mode,
        cloud_policy=policy,
        rate_limiter=rate_limiter,
        model_roles=model_roles,
    )
