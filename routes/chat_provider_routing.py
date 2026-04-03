"""Request-scoped provider routing for chat/task execution."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Generator, Optional

from fastapi import Request

from .models import ChatSendRequest


logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ProviderTarget:
    label: str
    provider: str
    model_name: str


@dataclass(frozen=True)
class ProviderPreference:
    generation_mode: str
    primary: ProviderTarget
    fallback: ProviderTarget


def _get_user_setting(uid: Optional[int], key: str, default: str) -> str:
    try:
        import auth as _auth_mod

        return str(_auth_mod.get_user_setting(int(uid) if uid else 1, key, default) or default).strip()
    except Exception:
        return str(default or "").strip()


def resolve_effective_generation_mode(req: ChatSendRequest, uid: Optional[int]) -> str:
    requested = str(getattr(req, "generation_mode", "") or "").strip()
    if not requested:
        requested = _get_user_setting(uid, "generation_mode", "cloud_openai")
    if requested == "local_network":
        return "local"
    return requested or "cloud_openai"


def resolve_provider_preference(req: ChatSendRequest, uid: Optional[int], base_client: Any) -> Optional[ProviderPreference]:
    generation_mode = resolve_effective_generation_mode(req, uid)
    if generation_mode not in ("cloud_claude", "cloud_openai"):
        return None

    claude_model = str(
        getattr(req, "cloud_model_claude", "") or _get_user_setting(uid, "cloud_model_claude", "") or getattr(base_client, "anthropic_model", "")
    ).strip() or str(getattr(base_client, "anthropic_model", "") or "claude-sonnet-4-20250514").strip()
    openai_model = str(
        getattr(req, "cloud_model_openai", "") or _get_user_setting(uid, "cloud_model_openai", "") or getattr(base_client, "cloud_model", "")
    ).strip() or str(getattr(base_client, "cloud_model", "") or "gpt-4o-mini").strip()

    claude = ProviderTarget(label="claude", provider="anthropic", model_name=claude_model)
    openai = ProviderTarget(label="openai", provider="cloud", model_name=openai_model)

    if generation_mode == "cloud_claude":
        return ProviderPreference(generation_mode=generation_mode, primary=claude, fallback=openai)
    return ProviderPreference(generation_mode=generation_mode, primary=openai, fallback=claude)


class RoutedCloudLLMClient:
    """Thin wrapper that enforces cloud-only primary/fallback ordering."""

    def __init__(self, base_client: Any, preference: ProviderPreference) -> None:
        self._base = base_client
        self._preference = preference
        self.fallback_policy = "cloud_only"
        self.model_roles = getattr(base_client, "model_roles", {})
        self.model = preference.primary.model_name

    def _targets(self) -> tuple[ProviderTarget, ProviderTarget]:
        return (self._preference.primary, self._preference.fallback)

    def _cloud_service(self):
        try:
            from personal_agent.cloud_features import get_cloud_feature_service

            return get_cloud_feature_service()
        except Exception:
            return None

    def _provider_available(self, target: ProviderTarget) -> tuple[bool, Optional[str]]:
        svc = self._cloud_service()
        if target.provider == "anthropic":
            if not getattr(self._base, "anthropic_api_key", ""):
                if svc is not None and getattr(svc, "_cookie_available", lambda: False)():
                    return True, None
                return False, "Anthropic API unavailable"
            if not self._base._check_anthropic_rate_limit():
                return False, "Anthropic rate limited"
            return True, None
        if target.provider == "cloud":
            if not getattr(self._base, "cloud_api_key", ""):
                if svc is not None and getattr(svc, "_openai_available", lambda: False)():
                    return True, None
                return False, "OpenAI API unavailable"
            return True, None
        return False, f"Unsupported provider {target.provider}"

    @staticmethod
    def _split_messages(messages: list[dict[str, Any]]) -> tuple[str, str]:
        system_parts: list[str] = []
        prompt_parts: list[str] = []
        for item in messages:
            if not isinstance(item, dict):
                continue
            role = str(item.get("role") or "user").strip().lower()
            content = str(item.get("content") or "").strip()
            if not content:
                continue
            if role == "system":
                system_parts.append(content)
            else:
                speaker = "User" if role == "user" else "Assistant"
                prompt_parts.append(f"{speaker}: {content}")
        return "\n\n".join(system_parts).strip(), "\n".join(prompt_parts).strip()

    def _service_text_call(
        self,
        target: ProviderTarget,
        messages: list[dict[str, Any]],
        *,
        max_tokens: int,
        temperature: float,
    ) -> str:
        svc = self._cloud_service()
        if svc is None:
            raise RuntimeError(f"{target.label} service unavailable")
        system, prompt = self._split_messages(messages)
        if not prompt:
            raise RuntimeError(f"{target.label} prompt unavailable")
        if target.provider == "cloud":
            openai = getattr(svc, "openai", None)
            if openai is None or not getattr(svc, "_openai_available", lambda: False)():
                raise RuntimeError("OpenAI API unavailable")
            raw = openai.generate(
                prompt=prompt,
                system=system or None,
                max_tokens=max_tokens,
                temperature=temperature,
                model=target.model_name or "gpt-4o-mini",
            )
            text = str(raw or "").strip()
            if not text or text.startswith("[Cloud LLM"):
                raise RuntimeError("OpenAI returned no visible answer")
            return text
        raw = svc._call_cookie_text(
            system or "You are Aether's cloud text generation layer.",
            prompt,
            max_tokens=max_tokens,
            feature="claude_generation",
            model=target.model_name or "claude-sonnet-4-5",
        )
        text = str(raw or "").strip()
        if not text:
            raise RuntimeError("Anthropic returned no visible answer")
        return text

    def _call_text_provider(
        self,
        target: ProviderTarget,
        messages: list[dict[str, Any]],
        *,
        max_tokens: int,
        temperature: float,
    ) -> str:
        ok, reason = self._provider_available(target)
        if not ok:
            raise RuntimeError(reason or f"{target.label} unavailable")
        if (
            (target.provider == "anthropic" and not getattr(self._base, "anthropic_api_key", ""))
            or (target.provider == "cloud" and not getattr(self._base, "cloud_api_key", ""))
        ):
            return self._service_text_call(
                target,
                messages,
                max_tokens=max_tokens,
                temperature=temperature,
            )
        resp = self._base._call(
            target.provider,
            target.model_name,
            messages,
            max_tokens,
            temperature,
            scrub=True,
        )
        if target.provider == "anthropic":
            self._base._record_anthropic_usage()
        content = resp.choices[0].message.content or ""
        text = self._base._resolve_visible_text(content)
        if not str(text or "").strip():
            raise RuntimeError(f"{target.label} returned no visible answer")
        return str(text)

    def chat(
        self,
        messages: list[dict[str, Any]],
        max_tokens: int = 500,
        temperature: float = 0.7,
        model: Optional[str] = None,
    ) -> str:
        del model
        errors: list[str] = []
        for target in self._targets():
            try:
                return self._call_text_provider(
                    target,
                    messages,
                    max_tokens=max_tokens,
                    temperature=temperature,
                )
            except Exception as exc:
                logger.warning("[PROVIDER_ROUTE] %s text call failed: %s", target.label, exc)
                errors.append(f"{target.label}: {exc}")
        return f"[Cloud fallback exhausted: {'; '.join(errors)}]"

    def chat_stream(
        self,
        messages: list[dict[str, Any]],
        max_tokens: int = 500,
        temperature: float = 0.7,
        model: Optional[str] = None,
    ) -> Generator[tuple[str, str], None, None]:
        del model
        errors: list[str] = []
        for target in self._targets():
            try:
                text = self._call_text_provider(
                    target,
                    messages,
                    max_tokens=max_tokens,
                    temperature=temperature,
                )
                if text:
                    yield ("content", text)
                    return
            except Exception as exc:
                logger.warning("[PROVIDER_ROUTE] %s stream failed: %s", target.label, exc)
                errors.append(f"{target.label}: {exc}")
        yield ("content", f"[stream error: cloud fallback exhausted ({'; '.join(errors)})]")

    def chat_with_tools(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
        max_tokens: int = 1000,
        temperature: float = 0.3,
        model: Optional[str] = None,
        timeout: Optional[float] = None,
    ) -> dict[str, Any]:
        del model, timeout
        errors: list[str] = []
        for target in self._targets():
            ok, reason = self._provider_available(target)
            if not ok:
                errors.append(f"{target.label}: {reason}")
                continue
            try:
                resp = self._base._call(
                    target.provider,
                    target.model_name,
                    messages,
                    max_tokens,
                    temperature,
                    tools=tools,
                    scrub=True,
                )
                if target.provider == "anthropic":
                    self._base._record_anthropic_usage()
                parsed = self._base._parse_tool_response(resp)
                parsed["generation_source"] = target.label
                if parsed.get("tool_calls") or str(parsed.get("content") or "").strip():
                    return parsed
                errors.append(f"{target.label}: empty tool response")
            except Exception as exc:
                logger.warning("[PROVIDER_ROUTE] %s tool call failed: %s", target.label, exc)
                errors.append(f"{target.label}: {exc}")
        return {
            "tool_calls": [],
            "content": f"[Cloud fallback exhausted: {'; '.join(errors)}]",
            "used_tools": False,
            "generation_source": "cloud_failed",
        }


def build_request_llm_client(request: Request, req: ChatSendRequest, uid: Optional[int]) -> Any:
    get_llm = request.app.state.get_llm_client
    base_client = get_llm()
    preference = resolve_provider_preference(req, uid, base_client) if base_client is not None else None
    if base_client is None or preference is None:
        return base_client
    return RoutedCloudLLMClient(base_client, preference)
