from __future__ import annotations

import os
import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

import requests

from .ollama_client import OllamaClient
from .text_utils import extract_think_content


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
    """Local-first client that can explicitly route generation to cloud."""

    def __init__(
        self,
        *,
        local_client: Optional[OllamaClient] = None,
        cloud_client: Optional[OpenAICompatibleClient] = None,
        product_mode: str = "local_only",
        cloud_policy: Optional[CloudPromptPolicy] = None,
    ) -> None:
        self.local_client = local_client
        self.cloud_client = cloud_client
        self.product_mode = str(product_mode or "local_only").strip().lower() or "local_only"
        self.cloud_policy = cloud_policy or CloudPromptPolicy()

    @property
    def model(self) -> str:
        if self.local_client is not None:
            return str(getattr(self.local_client, "model", "") or "")
        if self.cloud_client is not None:
            return str(getattr(self.cloud_client, "model", "") or "")
        return ""

    @property
    def cloud_available(self) -> bool:
        return bool(self.cloud_client is not None and self.cloud_client.is_available)

    def _resolve_target(self, model: Optional[str]) -> Tuple[str, Optional[str]]:
        selected = str(model or "").strip()
        if selected.startswith("cloud:"):
            return "cloud", selected.split(":", 1)[1].strip() or None
        if selected.startswith("local:"):
            return "local", selected.split(":", 1)[1].strip() or None
        return "local", selected or None

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

        if provider == "cloud" and self.cloud_available and self.cloud_client is not None:
            safe_prompt = self._scrub_prompt_for_cloud(prompt)
            return self.cloud_client.generate(
                safe_prompt,
                system=system,
                max_tokens=max_tokens,
                temperature=temperature,
                stream=stream,
                model=selected_model,
            )

        if self.local_client is not None:
            return self.local_client.generate(
                prompt,
                system=system,
                max_tokens=max_tokens,
                temperature=temperature,
                stream=stream,
                model=selected_model,
            )

        if provider == "cloud" and self.cloud_client is not None:
            safe_prompt = self._scrub_prompt_for_cloud(prompt)
            return self.cloud_client.generate(
                safe_prompt,
                system=system,
                max_tokens=max_tokens,
                temperature=temperature,
                stream=stream,
                model=selected_model,
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

        if provider == "cloud" and self.cloud_available and self.cloud_client is not None:
            safe_messages: List[Dict[str, str]] = []
            for item in list(messages or []):
                if not isinstance(item, dict):
                    continue
                safe_item = dict(item)
                safe_item["content"] = self._scrub_prompt_for_cloud(str(item.get("content") or ""))
                safe_messages.append(safe_item)
            return self.cloud_client.chat(
                safe_messages,
                max_tokens=max_tokens,
                temperature=temperature,
                model=selected_model,
            )

        if self.local_client is not None:
            return self.local_client.chat(
                messages,
                max_tokens=max_tokens,
                temperature=temperature,
                model=selected_model,
            )

        if provider == "cloud" and self.cloud_client is not None:
            return self.cloud_client.chat(
                messages,
                max_tokens=max_tokens,
                temperature=temperature,
                model=selected_model,
            )

        return "[No LLM available]"

    def chat_stream(
        self,
        messages: List[Dict[str, str]],
        max_tokens: int = 500,
        temperature: float = 0.7,
        model: Optional[str] = None,
    ):
        """Stream (token_type, text) tuples — delegates to local client."""
        _provider, selected_model = self._resolve_target(model)
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

    product_mode = str((product_cfg or {}).get("mode") or os.getenv("CRT_PRODUCT_MODE") or "local_only").strip().lower()

    local_enabled = bool(local_cfg.get("enabled", True)) and _env_bool("CRT_ENABLE_LLM", True)
    local_model = str(os.getenv("CRT_OLLAMA_MODEL") or local_cfg.get("default_model") or "llama3.2:latest").strip()

    local_client: Optional[OllamaClient] = None
    if local_enabled:
        try:
            local_client = OllamaClient(model=local_model)
        except Exception:
            local_client = None

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

    policy = CloudPromptPolicy(
        redact_memory_metadata=bool(cloud_cfg.get("redact_memory_metadata", True)),
        max_context_chars=int(cloud_cfg.get("max_context_chars") or 14000),
        fact_allowlist=tuple(str(x).strip() for x in (cloud_cfg.get("fact_allowlist") or []) if str(x).strip()),
        slot_denylist=tuple(str(x).strip() for x in (cloud_cfg.get("slot_denylist") or []) if str(x).strip()),
    )
    if local_client is None and cloud_client is None:
        return None
    return HybridLLMClient(
        local_client=local_client,
        cloud_client=cloud_client,
        product_mode=product_mode,
        cloud_policy=policy,
    )
