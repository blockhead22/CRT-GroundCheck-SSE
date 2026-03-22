"""Heuristic model routing for per-request LLM selection."""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from typing import Any, Dict, Optional, Tuple


@dataclass
class RoutedModel:
    route: str
    model: str
    reason: str
    provider: str = "local"
    escalation: bool = False
    product_mode: str = "local_only"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "route": self.route,
            "model": self.model,
            "reason": self.reason,
            "provider": self.provider,
            "escalation": bool(self.escalation),
            "product_mode": self.product_mode,
        }


class ModelRouter:
    """Select a model per request using lightweight intent heuristics."""

    CODE_HINTS = (
        "code",
        "debug",
        "function",
        "class",
        "api",
        "sql",
        "python",
        "javascript",
        "typescript",
        "bash",
        "regex",
    )
    RESEARCH_HINTS = (
        "latest",
        "today",
        "news",
        "research",
        "look up",
        "search",
        "current",
        "state of",
    )
    DEEP_REASONING_HINTS = (
        "analyze",
        "compare",
        "tradeoff",
        "why",
        "how",
        "design",
        "architecture",
        "step by step",
    )
    CREATIVE_HINTS = (
        "brainstorm",
        "story",
        "creative",
        "rewrite",
        "tone",
        "draft",
    )

    def __init__(
        self,
        *,
        default_model: Optional[str] = None,
        runtime_config: Optional[Dict[str, Any]] = None,
    ) -> None:
        fallback_default = default_model or os.getenv("CRT_OLLAMA_MODEL") or "qwen3:14b"
        runtime_config = runtime_config or {}
        generation_cfg = runtime_config.get("generation_stack") if isinstance(runtime_config, dict) else {}
        local_cfg = (generation_cfg.get("local") or {}) if isinstance(generation_cfg, dict) else {}
        cloud_cfg = (generation_cfg.get("cloud") or {}) if isinstance(generation_cfg, dict) else {}
        routing_cfg = (generation_cfg.get("routing") or {}) if isinstance(generation_cfg, dict) else {}
        product_cfg = runtime_config.get("product_mode") if isinstance(runtime_config, dict) else {}

        self.product_mode = str(
            (product_cfg or {}).get("mode") or os.getenv("CRT_PRODUCT_MODE") or "local_only"
        ).strip().lower() or "local_only"
        self.cloud_enabled = bool(cloud_cfg.get("enabled", False))
        self.cloud_model = str(
            os.getenv("CRT_CLOUD_MODEL") or cloud_cfg.get("model") or "gpt-5.4-thinking"
        ).strip()
        allowed_channels = cloud_cfg.get("allowed_channels")
        denied_channels = cloud_cfg.get("denied_channels")
        self.allowed_channels = {
            str(x).strip().lower()
            for x in (allowed_channels if isinstance(allowed_channels, list) else [])
            if str(x).strip()
        }
        self.denied_channels = {
            str(x).strip().lower()
            for x in (denied_channels if isinstance(denied_channels, list) else [])
            if str(x).strip()
        }
        routes_raw = routing_cfg.get("cloud_routes")
        if isinstance(routes_raw, list):
            self.cloud_routes = {str(x).strip().lower() for x in routes_raw if str(x).strip()}
        else:
            env_routes = os.getenv("CRT_CLOUD_ROUTES", "reasoning,research,creative")
            self.cloud_routes = {part.strip().lower() for part in env_routes.split(",") if part.strip()}
        try:
            self.min_tokens_for_cloud = int(
                os.getenv("CRT_MIN_TOKENS_FOR_CLOUD") or routing_cfg.get("min_tokens_for_cloud") or 16
            )
        except Exception:
            self.min_tokens_for_cloud = 16

        _config_default = str(local_cfg.get("default_model") or fallback_default)
        self.models = {
            "default": _config_default,
            "fast": os.getenv("CRT_MODEL_FAST", _config_default),
            "reasoning": os.getenv("CRT_MODEL_REASONING", fallback_default),
            "research": os.getenv("CRT_MODEL_RESEARCH", fallback_default),
            "code": os.getenv("CRT_MODEL_CODE", fallback_default),
            "creative": os.getenv("CRT_MODEL_CREATIVE", fallback_default),
        }

    def _routed_local(self, *, route: str, reason: str, allow_cloud: bool = False) -> RoutedModel:
        model = str(self.models.get(route) or self.models.get("default") or "").strip()
        if (
            allow_cloud
            and self.product_mode == "hybrid_verified"
            and self.cloud_enabled
            and self.cloud_model
            and route in self.cloud_routes
        ):
            return RoutedModel(
                route=route,
                model=f"cloud:{self.cloud_model}",
                reason=f"{reason}; escalated to cloud generation",
                provider="cloud",
                escalation=True,
                product_mode=self.product_mode,
            )
        return RoutedModel(
            route=route,
            model=model,
            reason=reason,
            provider="local",
            escalation=False,
            product_mode=self.product_mode,
        )

    @staticmethod
    def _contains_any(text: str, candidates: tuple[str, ...]) -> bool:
        t = (text or "").strip().lower()
        return any(c in t for c in candidates)

    @staticmethod
    def _get_pref(
        preference_profile: Optional[Dict[str, Any]],
        category: str,
        key: str,
    ) -> Tuple[Optional[str], float]:
        """
        Read episodic preference value/confidence.

        Supports both nested `{category: {key: {value, confidence}}}` and
        flat `{key: {value, confidence}}` shapes for compatibility.
        """
        if not isinstance(preference_profile, dict):
            return None, 0.0

        bucket = preference_profile.get(category)
        if isinstance(bucket, dict):
            entry = bucket.get(key)
            if isinstance(entry, dict):
                value = entry.get("value")
                conf = float(entry.get("confidence") or 0.0)
                return (str(value).strip().lower() if value else None), conf
            if isinstance(entry, str):
                return entry.strip().lower(), 0.5

        direct = preference_profile.get(key)
        if isinstance(direct, dict):
            value = direct.get("value")
            conf = float(direct.get("confidence") or 0.0)
            return (str(value).strip().lower() if value else None), conf
        if isinstance(direct, str):
            return direct.strip().lower(), 0.5

        return None, 0.0

    def route(
        self,
        *,
        query: str,
        requested_mode: Optional[str] = None,
        preference_profile: Optional[Dict[str, Any]] = None,
        channel: Optional[str] = None,
    ) -> RoutedModel:
        q = (query or "").strip()
        mode = (requested_mode or "").strip().lower()
        channel_name = str(channel or "").strip().lower()
        token_count = len(re.findall(r"\w+", q))
        verbosity_pref, verbosity_conf = self._get_pref(preference_profile, "response_style", "verbosity")
        structure_pref, structure_conf = self._get_pref(preference_profile, "response_style", "structure")
        citation_pref, citation_conf = self._get_pref(preference_profile, "response_style", "citation_style")
        code_lang_pref, code_lang_conf = self._get_pref(preference_profile, "code_style", "language")

        def _should_cloud(route_name: str) -> bool:
            if channel_name and channel_name in self.denied_channels:
                return False
            if self.allowed_channels and channel_name not in self.allowed_channels:
                return False
            return (
                self.product_mode == "hybrid_verified"
                and self.cloud_enabled
                and token_count >= self.min_tokens_for_cloud
                and route_name in self.cloud_routes
            )

        if mode in {"research"} or self._contains_any(q, self.RESEARCH_HINTS):
            reason = "research/news cues detected"
            if _should_cloud("research"):
                reason += " + cloud escalation policy"
            return self._routed_local(route="research", reason=reason, allow_cloud=_should_cloud("research"))

        if (
            citation_pref in {"required", "include_sources", "sources"}
            and citation_conf >= 0.55
            and token_count >= 8
        ):
            return RoutedModel(
                route="research",
                model=(
                    f"cloud:{self.cloud_model}"
                    if _should_cloud("research")
                    else self.models["research"]
                ),
                reason=(
                    "high-confidence citation preference + cloud escalation policy"
                    if _should_cloud("research")
                    else "high-confidence citation preference"
                ),
                provider="cloud" if _should_cloud("research") else "local",
                escalation=_should_cloud("research"),
                product_mode=self.product_mode,
            )

        if self._contains_any(q, self.CODE_HINTS):
            reason = "code-related cues detected"
            if code_lang_pref and code_lang_conf >= 0.55:
                reason = f"code cues + language preference ({code_lang_pref})"
            if _should_cloud("code"):
                reason += " + cloud escalation policy"
            return self._routed_local(route="code", reason=reason, allow_cloud=_should_cloud("code"))

        if mode in {"deep", "thinking"} or self._contains_any(q, self.DEEP_REASONING_HINTS) or token_count >= 80:
            reason = "complex reasoning cues detected"
            if _should_cloud("reasoning"):
                reason += " + cloud escalation policy"
            return self._routed_local(route="reasoning", reason=reason, allow_cloud=_should_cloud("reasoning"))

        if (
            verbosity_pref == "verbose"
            and verbosity_conf >= 0.6
            and token_count >= 15
        ):
            return RoutedModel(
                route="reasoning",
                model=(
                    f"cloud:{self.cloud_model}"
                    if _should_cloud("reasoning")
                    else self.models["reasoning"]
                ),
                reason=(
                    "high-confidence verbose preference + cloud escalation policy"
                    if _should_cloud("reasoning")
                    else "high-confidence verbose preference"
                ),
                provider="cloud" if _should_cloud("reasoning") else "local",
                escalation=_should_cloud("reasoning"),
                product_mode=self.product_mode,
            )

        if (
            structure_pref in {"step_by_step", "structured"}
            and structure_conf >= 0.6
            and token_count >= 12
        ):
            return RoutedModel(
                route="reasoning",
                model=(
                    f"cloud:{self.cloud_model}"
                    if _should_cloud("reasoning")
                    else self.models["reasoning"]
                ),
                reason=(
                    "high-confidence structured preference + cloud escalation policy"
                    if _should_cloud("reasoning")
                    else "high-confidence structured preference"
                ),
                provider="cloud" if _should_cloud("reasoning") else "local",
                escalation=_should_cloud("reasoning"),
                product_mode=self.product_mode,
            )

        if self._contains_any(q, self.CREATIVE_HINTS):
            reason = "creative-writing cues detected"
            if _should_cloud("creative"):
                reason += " + cloud escalation policy"
            return self._routed_local(route="creative", reason=reason, allow_cloud=_should_cloud("creative"))

        if verbosity_pref == "concise" and verbosity_conf >= 0.6 and token_count <= 60:
            return RoutedModel(
                route="fast",
                model=self.models["fast"],
                reason="high-confidence concise preference",
                provider="local",
                escalation=False,
                product_mode=self.product_mode,
            )

        return RoutedModel(
            route="fast",
            model=self.models["fast"],
            reason="default low-latency route",
            provider="local",
            escalation=False,
            product_mode=self.product_mode,
        )
