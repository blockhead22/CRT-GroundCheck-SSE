"""
Cloud Feature Service — production wrapper around cloud provider patterns.

Promotes the test harness (tests/cloud_providers/) into a callable service
used by the CRT pipeline for:
  1. Slot classification (gpt-4o-mini / Tier 1)
  2. NLI contradiction detection (gpt-4o-mini / Tier 1)
  3. Reflection validation (claude-sonnet-4-5 / Tier 2, falls back to Tier 1)

Each method returns a parsed dict on success, or None on graceful degradation.
"""
from __future__ import annotations

import json
import logging
import time
from datetime import date
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

from personal_agent.cloud_usage_logger import get_cloud_usage_logger

# Re-use the structured prompts from the test harness
from tests.cloud_providers.prompts import (
    slot_classification_prompt,
    nli_contradiction_prompt,
    reflection_validation_prompt,
)


class CloudFeatureService:
    """Thin production wrapper that routes CRT cloud features to the right provider."""

    # Default daily limits per feature (can be scaled via user setting multiplier)
    DEFAULT_DAILY_LIMITS: Dict[str, int] = {
        "slot_classification": 10,
        "nli_contradiction": 10,
        "reflection_validation": 3,
    }

    def __init__(
        self,
        openai_client=None,
        cookie_session=None,
    ):
        """
        Args:
            openai_client: An OpenAICompatibleClient (or compatible) for Tier 1 calls.
            cookie_session: A CookieProvider instance for Tier 2 calls (optional).
        """
        self.openai = openai_client
        self.cookie = cookie_session

        # Usage tracking (in-memory, resets on restart)
        self.usage: Dict[str, Any] = {
            "slot_classification": {"calls": 0, "est_tokens": 0},
            "nli_contradiction": {"calls": 0, "est_tokens": 0},
            "reflection_validation": {"calls": 0, "est_tokens": 0},
            "total_cost_est": 0.0,
        }

        # Daily cycle limits
        self.daily_limits: Dict[str, int] = dict(self.DEFAULT_DAILY_LIMITS)
        self._daily_counts: Dict[str, int] = {
            "slot_classification": 0,
            "nli_contradiction": 0,
            "reflection_validation": 0,
        }
        self._daily_counts_date: str = str(date.today())
        self._limit_multiplier: float = 1.0

    # ------------------------------------------------------------------
    # Daily limit helpers
    # ------------------------------------------------------------------

    def set_limit_multiplier(self, multiplier: float) -> None:
        """Set the user-configured daily limit multiplier."""
        self._limit_multiplier = max(0.0, float(multiplier))

    def _reset_daily_if_needed(self) -> None:
        today = str(date.today())
        if today != self._daily_counts_date:
            self._daily_counts = {k: 0 for k in self._daily_counts}
            self._daily_counts_date = today

    def _check_daily_limit(self, feature: str) -> bool:
        """Return True if the feature is within its daily limit."""
        self._reset_daily_if_needed()
        base_limit = self.daily_limits.get(feature, 0)
        effective_limit = int(base_limit * self._limit_multiplier)
        current = self._daily_counts.get(feature, 0)
        if current >= effective_limit:
            logger.warning(
                "[CLOUD] Daily limit reached for %s: %d/%d",
                feature, current, effective_limit,
            )
            return False
        return True

    def _record_daily_call(self, feature: str) -> None:
        self._reset_daily_if_needed()
        self._daily_counts[feature] = self._daily_counts.get(feature, 0) + 1

    def get_daily_counts(self) -> Dict[str, Any]:
        self._reset_daily_if_needed()
        result = {}
        for feature in self.daily_limits:
            base_limit = self.daily_limits[feature]
            effective_limit = int(base_limit * self._limit_multiplier)
            result[feature] = {
                "used": self._daily_counts.get(feature, 0),
                "limit": effective_limit,
            }
        return result

    # ------------------------------------------------------------------
    # Internal call helpers
    # ------------------------------------------------------------------

    def _openai_available(self) -> bool:
        if self.openai is None:
            return False
        return bool(getattr(self.openai, "is_available", False))

    def _cookie_available(self) -> bool:
        if self.cookie is None:
            return False
        try:
            return self.cookie.is_available()
        except Exception:
            return False

    def _call_openai(
        self, system: str, prompt: str, max_tokens: int = 300, *, feature: str = "unknown",
    ) -> Optional[Dict[str, Any]]:
        """Call the OpenAI-compatible client and parse JSON response."""
        if not self._openai_available():
            return None
        usage_logger = get_cloud_usage_logger()
        full_prompt = f"{system}\n{prompt}"
        t0 = time.time()
        raw: Optional[str] = None
        try:
            raw = self.openai.generate(
                prompt=prompt,
                system=system,
                max_tokens=max_tokens,
                temperature=0.3,
                model="gpt-4o-mini",
            )
            latency = int((time.time() - t0) * 1000)
            if not raw or raw.startswith("[Cloud LLM"):
                usage_logger.log(
                    provider="openai", feature=feature, model="gpt-4o-mini",
                    prompt=full_prompt, response=raw or "", latency_ms=latency,
                    success=False, error_message="Empty or placeholder response",
                )
                return None
            # Strip markdown fences if present
            text = raw.strip()
            if text.startswith("```"):
                lines = text.split("\n")
                lines = [l for l in lines if not l.strip().startswith("```")]
                text = "\n".join(lines).strip()
            parsed = json.loads(text)
            usage_logger.log(
                provider="openai", feature=feature, model="gpt-4o-mini",
                prompt=full_prompt, response=raw, latency_ms=latency, success=True,
            )
            return parsed
        except (json.JSONDecodeError, Exception) as e:
            latency = int((time.time() - t0) * 1000)
            usage_logger.log(
                provider="openai", feature=feature, model="gpt-4o-mini",
                prompt=full_prompt, response=raw or "", latency_ms=latency,
                success=False, error_message=str(e),
            )
            logger.warning("[CLOUD] OpenAI call failed: %s", e)
            return None

    def _call_cookie(
        self, system: str, prompt: str, max_tokens: int = 300, *, feature: str = "unknown",
    ) -> Optional[Dict[str, Any]]:
        """Call the Cookie (Claude session) provider and parse JSON response."""
        if not self._cookie_available():
            return None
        usage_logger = get_cloud_usage_logger()
        full_prompt = f"{system}\n{prompt}"
        t0 = time.time()
        raw_content: str = ""
        try:
            result = self.cookie.complete(system, prompt, max_tokens=max_tokens)
            latency = int((time.time() - t0) * 1000)
            raw_content = getattr(result, "content", "") or ""
            if result.error:
                usage_logger.log(
                    provider="claude_subscription", feature=feature,
                    model="claude-sonnet-4-5", prompt=full_prompt,
                    response=raw_content, latency_ms=latency,
                    success=False, error_message=str(result.error),
                )
                logger.warning("[CLOUD] Cookie call failed: %s", result.error)
                return None
            if result.parsed is not None:
                usage_logger.log(
                    provider="claude_subscription", feature=feature,
                    model="claude-sonnet-4-5", prompt=full_prompt,
                    response=raw_content, latency_ms=latency, success=True,
                )
                return result.parsed
            # Try manual parse
            text = raw_content.strip()
            if text.startswith("```"):
                lines = text.split("\n")
                lines = [l for l in lines if not l.strip().startswith("```")]
                text = "\n".join(lines).strip()
            parsed = json.loads(text)
            usage_logger.log(
                provider="claude_subscription", feature=feature,
                model="claude-sonnet-4-5", prompt=full_prompt,
                response=raw_content, latency_ms=latency, success=True,
            )
            return parsed
        except (json.JSONDecodeError, Exception) as e:
            latency = int((time.time() - t0) * 1000)
            usage_logger.log(
                provider="claude_subscription", feature=feature,
                model="claude-sonnet-4-5", prompt=full_prompt,
                response=raw_content, latency_ms=latency,
                success=False, error_message=str(e),
            )
            logger.warning("[CLOUD] Cookie call failed: %s", e)
            return None

    def _track_usage(self, feature: str, est_tokens: int = 200, cost: float = 0.0) -> None:
        bucket = self.usage.get(feature)
        if bucket and isinstance(bucket, dict):
            bucket["calls"] = bucket.get("calls", 0) + 1
            bucket["est_tokens"] = bucket.get("est_tokens", 0) + est_tokens
        self.usage["total_cost_est"] = self.usage.get("total_cost_est", 0.0) + cost

    # ------------------------------------------------------------------
    # Feature 1: Slot Classification
    # ------------------------------------------------------------------

    def classify_slot(
        self,
        statement: str,
        existing_slots: List[str],
    ) -> Optional[Dict[str, Any]]:
        """Classify a user statement into a memory slot using cloud LLM.

        Returns parsed dict with keys like contains_fact, slot_name, value, etc.
        Returns None if no provider available or limit exceeded.
        """
        if not self._check_daily_limit("slot_classification"):
            return None

        system, prompt = slot_classification_prompt(statement, existing_slots)
        result = self._call_openai(system, prompt, feature="slot_classification")

        if result is not None:
            self._track_usage("slot_classification", est_tokens=250, cost=0.000075)
            self._record_daily_call("slot_classification")
            logger.info("[CLOUD] Slot classification: %s", result.get("slot_name", "none"))
            return result

        logger.debug("[CLOUD] Slot classification unavailable (no provider)")
        return None

    # ------------------------------------------------------------------
    # Feature 2: NLI Contradiction Detection
    # ------------------------------------------------------------------

    def check_contradiction(
        self,
        fact_a: str,
        fact_b: str,
    ) -> Optional[Dict[str, Any]]:
        """Check if two facts contradict using cloud NLI.

        Returns parsed dict with keys: relation, confidence, explanation, severity.
        Returns None if no provider available or limit exceeded.
        """
        if not self._check_daily_limit("nli_contradiction"):
            return None

        system, prompt = nli_contradiction_prompt(fact_a, fact_b)
        result = self._call_openai(system, prompt, feature="nli_contradiction")

        if result is not None:
            self._track_usage("nli_contradiction", est_tokens=200, cost=0.00006)
            self._record_daily_call("nli_contradiction")
            logger.info(
                "[CLOUD] NLI check: %s (confidence=%s)",
                result.get("relation", "?"),
                result.get("confidence", "?"),
            )
            return result

        logger.debug("[CLOUD] NLI contradiction check unavailable (no provider)")
        return None

    # ------------------------------------------------------------------
    # Feature 3: Reflection Validation
    # ------------------------------------------------------------------

    def validate_reflection(
        self,
        evidence: List[Dict[str, Any]],
        proposed_update: Dict[str, Any],
    ) -> Optional[Dict[str, Any]]:
        """Validate a self-model reflection update against evidence.

        Prefers Tier 2 (Cookie/Claude) for deeper reasoning, falls back to Tier 1 (OpenAI).
        Returns parsed dict with keys: valid, confidence, concerns, suggestion.
        Returns None if no provider available or limit exceeded.
        """
        if not self._check_daily_limit("reflection_validation"):
            return None

        system, prompt = reflection_validation_prompt(evidence, proposed_update)

        # Try Tier 2 first (Claude via cookie session — better at nuanced reasoning)
        result = self._call_cookie(system, prompt, max_tokens=500, feature="reflection_validation")
        if result is not None:
            self._track_usage("reflection_validation", est_tokens=400, cost=0.0)
            self._record_daily_call("reflection_validation")
            logger.info("[CLOUD] Reflection validation (Tier 2): valid=%s", result.get("valid"))
            return result

        # Fall back to Tier 1 (OpenAI)
        result = self._call_openai(system, prompt, max_tokens=500, feature="reflection_validation")
        if result is not None:
            self._track_usage("reflection_validation", est_tokens=400, cost=0.0002)
            self._record_daily_call("reflection_validation")
            logger.info("[CLOUD] Reflection validation (Tier 1 fallback): valid=%s", result.get("valid"))
            return result

        logger.debug("[CLOUD] Reflection validation unavailable (no provider)")
        return None

    # ------------------------------------------------------------------
    # Convenience
    # ------------------------------------------------------------------

    def get_usage_summary(self) -> Dict[str, Any]:
        """Return usage stats plus daily limit status."""
        return {
            **self.usage,
            "daily_limits": self.get_daily_counts(),
        }


# ---------------------------------------------------------------------------
# Module-level singleton (lazy init)
# ---------------------------------------------------------------------------

_cloud_service: Optional[CloudFeatureService] = None


def get_cloud_feature_service() -> Optional[CloudFeatureService]:
    """Return the module-level CloudFeatureService singleton, or None if not initialized."""
    return _cloud_service


def init_cloud_feature_service(
    openai_client=None,
    cookie_session=None,
) -> CloudFeatureService:
    """Initialize and return the CloudFeatureService singleton."""
    global _cloud_service
    _cloud_service = CloudFeatureService(
        openai_client=openai_client,
        cookie_session=cookie_session,
    )
    logger.info(
        "[CLOUD] CloudFeatureService initialized (openai=%s, cookie=%s)",
        _cloud_service._openai_available(),
        _cloud_service._cookie_available(),
    )
    return _cloud_service
