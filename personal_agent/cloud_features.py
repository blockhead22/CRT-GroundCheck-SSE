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
        "cloud_generation": 50,
        "claude_generation": 20,
        "claude_reflection": 10,
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
            "cloud_generation": {"calls": 0, "est_tokens": 0},
            "claude_generation": {"calls": 0, "est_tokens": 0},
            "claude_reflection": {"calls": 0, "est_tokens": 0},
            "total_cost_est": 0.0,
        }

        # Daily cycle limits
        self.daily_limits: Dict[str, int] = dict(self.DEFAULT_DAILY_LIMITS)
        self._daily_counts: Dict[str, int] = {
            "slot_classification": 0,
            "nli_contradiction": 0,
            "reflection_validation": 0,
            "cloud_generation": 0,
            "claude_generation": 0,
            "claude_reflection": 0,
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
        _avail = self._openai_available()
        if not _avail:
            print(f"[CLOUD_SLOT] OpenAI not available: client={self.openai is not None}, is_available={getattr(self.openai, 'is_available', 'N/A') if self.openai else 'no client'}")
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
            print(f"[CLOUD_SLOT] OpenAI raw response ({latency}ms): {repr(raw)[:200]}")
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
            print(f"[CLOUD_SLOT] OpenAI call FAILED: {e}")
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

    def _call_cookie_text(
        self, system: str, prompt: str, max_tokens: int = 4096, *, feature: str = "unknown",
    ) -> Optional[str]:
        """Call the Cookie (Claude session) provider and return raw text (not JSON-parsed).

        Used for generation tasks where the response is free-form text, not structured JSON.
        """
        if not self._cookie_available():
            print(f"[CLOUD_CLAUDE] Cookie provider not available for {feature}")
            return None
        usage_logger = get_cloud_usage_logger()
        full_prompt = f"{system}\n{prompt}"
        t0 = time.time()
        raw_content: str = ""
        try:
            result = self.cookie.complete(system, prompt, max_tokens=max_tokens)
            latency = int((time.time() - t0) * 1000)
            raw_content = getattr(result, "content", "") or ""
            # Ignore JSON parse errors — complete() calls try_parse_json()
            # which sets error on non-JSON text, but we want raw text here.
            _is_json_parse_err = result.error and "JSON parse" in str(result.error)
            if _is_json_parse_err and raw_content.strip():
                print(f"[CLOUD_CLAUDE] Ignoring JSON parse error for text generation ({feature})")
            elif result.error:
                usage_logger.log(
                    provider="claude_subscription", feature=feature,
                    model="claude-sonnet-4-5", prompt=full_prompt,
                    response=raw_content, latency_ms=latency,
                    success=False, error_message=str(result.error),
                )
                print(f"[CLOUD_CLAUDE] Cookie call failed for {feature}: {result.error}")
                return None
            if not raw_content.strip():
                usage_logger.log(
                    provider="claude_subscription", feature=feature,
                    model="claude-sonnet-4-5", prompt=full_prompt,
                    response="", latency_ms=latency,
                    success=False, error_message="Empty response",
                )
                print(f"[CLOUD_CLAUDE] Empty response for {feature}")
                return None
            # Estimate tokens: word count * 1.3
            est_tokens = int(len(raw_content.split()) * 1.3)
            usage_logger.log(
                provider="claude_subscription", feature=feature,
                model="claude-sonnet-4-5", prompt=full_prompt,
                response=raw_content, latency_ms=latency, success=True,
            )
            print(f"[CLOUD_CLAUDE] {feature} response ({latency}ms, ~{est_tokens} tokens): {repr(raw_content)[:150]}")
            return raw_content.strip()
        except Exception as e:
            latency = int((time.time() - t0) * 1000)
            usage_logger.log(
                provider="claude_subscription", feature=feature,
                model="claude-sonnet-4-5", prompt=full_prompt,
                response=raw_content, latency_ms=latency,
                success=False, error_message=str(e),
            )
            print(f"[CLOUD_CLAUDE] Cookie call FAILED for {feature}: {e}")
            return None

    def _check_claude_daily_limit(self, feature: str = "claude_generation") -> bool:
        """Check the user-configured daily limit for all Claude features combined."""
        self._reset_daily_if_needed()
        # Sum all Claude feature counts
        claude_total = (
            self._daily_counts.get("claude_generation", 0)
            + self._daily_counts.get("claude_reflection", 0)
        )
        # Try to read user-configured limit (falls back to 20)
        try:
            import auth as _auth
            limit = int(_auth.get_user_setting(1, "cloud_claude_daily_limit", "20") or "20")
        except Exception:
            limit = 20
        if claude_total >= limit:
            print(f"[CLOUD_CLAUDE] Daily limit reached: {claude_total}/{limit}")
            return False
        return True

    def generate_response_claude(
        self,
        user_message: str,
        retrieved_memories: Optional[List[Dict[str, Any]]] = None,
        conversation_history: Optional[List[Dict[str, str]]] = None,
        self_model_snapshot: Optional[Dict[str, Any]] = None,
        max_tokens: int = 4096,
    ) -> Optional[str]:
        """Generate a conversational response via Claude cookie provider (Tier 2).

        This is the high-quality fallback for response generation when OpenAI
        fails or produces low-confidence results. The CRT control plane
        (memory governance, trust scoring, contradiction detection, gate checks)
        still runs locally — cloud is just the vocal cords.

        Returns the response text on success, or None if unavailable/limit exceeded.
        """
        # Check master toggle
        try:
            import auth as _auth
            _uid = 1
            _enabled = str(_auth.get_user_setting(_uid, "cloud_claude_enabled", "false")).lower() in ("true", "1", "yes", "on")
            if not _enabled:
                print("[CLOUD_CLAUDE] Claude is disabled (cloud_claude_enabled=false)")
                return None
            _gen_enabled = str(_auth.get_user_setting(_uid, "cloud_claude_generation", "true")).lower() in ("true", "1", "yes", "on")
            if not _gen_enabled:
                print("[CLOUD_CLAUDE] Claude generation disabled (cloud_claude_generation=false)")
                return None
            # Read user-configured max tokens
            _user_max_tokens = int(_auth.get_user_setting(_uid, "cloud_claude_max_tokens", "4096") or "4096")
            max_tokens = min(max_tokens, _user_max_tokens)
        except Exception as e:
            print(f"[CLOUD_CLAUDE] Settings check error: {e}")

        if not self._check_claude_daily_limit("claude_generation"):
            return None
        if not self._cookie_available():
            print("[CLOUD_CLAUDE] Cookie provider not available")
            return None

        # Build system prompt — architectural framing, not roleplay
        system_parts = [
            "You are the generation layer inside Aether, a deployed personal AI system built by Nick Block.",
            "Aether uses CRT (Contradiction-aware Reconciliation and Trust) to govern memory, detect contradictions, and gate responses.",
            "This is a real system, not a simulation. The CRT control plane has already processed this query.",
            "Your job: generate a natural, helpful response as Aether using the context provided.",
            "Guidelines:",
            "- Be conversational, warm, and concise. Speak as Aether in first person.",
            "- Use retrieved memories naturally — they are real facts about the user.",
            "- Never say you are Claude or made by Anthropic. You are Aether.",
            "- Never refuse on the basis that you lack CRT capabilities — the system is real and running.",
        ]

        # Inject retrieved memories with trust scores
        if retrieved_memories:
            mem_lines = []
            for mem in (retrieved_memories or [])[:8]:
                text = (mem.get("text") or "").strip()
                trust = mem.get("trust")
                if text:
                    trust_tag = f" [trust={trust:.2f}]" if trust is not None else ""
                    mem_lines.append(f"- {text[:200]}{trust_tag}")
            if mem_lines:
                system_parts.append("\nRelevant memories about the user:")
                system_parts.extend(mem_lines)

        # Inject self-model snapshot if available
        if self_model_snapshot:
            traits = self_model_snapshot.get("traits") or self_model_snapshot.get("top_facts") or []
            if traits and isinstance(traits, list):
                trait_lines = [f"- {t}" for t in traits[:5] if isinstance(t, str)]
                if trait_lines:
                    system_parts.append("\nYour self-model (what you know about yourself):")
                    system_parts.extend(trait_lines)

        system_prompt = "\n".join(system_parts)

        # Build the prompt string
        messages_for_prompt: List[Dict[str, str]] = []
        if conversation_history:
            for turn in conversation_history[-6:]:
                role = turn.get("role", "user")
                content = (turn.get("content") or "").strip()
                if content and role in ("user", "assistant"):
                    messages_for_prompt.append({"role": role, "content": content[:500]})
        messages_for_prompt.append({"role": "user", "content": user_message})

        prompt_text = "\n".join(
            f"{'User' if m['role'] == 'user' else 'Aether'}: {m['content']}"
            for m in messages_for_prompt
        )

        raw = self._call_cookie_text(
            system_prompt, prompt_text, max_tokens=max_tokens, feature="claude_generation",
        )

        if raw:
            # Estimate tokens for tracking
            est_tokens = int(len(raw.split()) * 1.3)
            self._track_usage("claude_generation", est_tokens=est_tokens, cost=0.0)
            self._record_daily_call("claude_generation")
            print(f"[CLOUD_CLAUDE] Generation success — {len(raw)} chars, ~{est_tokens} tokens")
            return raw

        print("[CLOUD_CLAUDE] Generation returned None")
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
        print(f"[CLOUD_SLOT] Calling OpenAI for: {statement[:60]}")
        result = self._call_openai(system, prompt, feature="slot_classification")

        if result is not None:
            self._track_usage("slot_classification", est_tokens=250, cost=0.000075)
            self._record_daily_call("slot_classification")
            print(f"[CLOUD_SLOT] Result: contains_fact={result.get('contains_fact')}, slot={result.get('slot_name', 'none')}")
            return result

        print("[CLOUD_SLOT] No provider available")
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
    # Feature 4: Cloud Response Generation (fallback)
    # ------------------------------------------------------------------

    def generate_response(
        self,
        user_message: str,
        retrieved_memories: Optional[List[Dict[str, Any]]] = None,
        conversation_history: Optional[List[Dict[str, str]]] = None,
        self_model_snapshot: Optional[Dict[str, Any]] = None,
    ) -> Optional[str]:
        """Generate a conversational response via OpenAI when local LLM is unavailable.

        This is the cloud fallback for response generation. The CRT control plane
        (memory governance, trust scoring, contradiction detection, gate checks)
        still runs locally — cloud is just the vocal cords.

        Returns the response text on success, or None if unavailable/limit exceeded.
        """
        if not self._check_daily_limit("cloud_generation"):
            print("[CLOUD_GEN] Daily limit reached for cloud_generation")
            return None
        if not self._openai_available():
            print("[CLOUD_GEN] OpenAI client not available")
            return None

        # Build system prompt — architectural framing, not roleplay
        system_parts = [
            "You are the generation layer inside Aether, a deployed personal AI system built by Nick Block.",
            "Aether uses CRT (Contradiction-aware Reconciliation and Trust) to govern memory, detect contradictions, and gate responses.",
            "This is a real system, not a simulation. The CRT control plane has already processed this query.",
            "Your job: generate a natural, helpful response as Aether using the context provided.",
            "Guidelines:",
            "- Be conversational, warm, and concise. Speak as Aether in first person.",
            "- Use retrieved memories naturally — they are real facts about the user.",
            "- Never say you are Claude or made by Anthropic. You are Aether.",
            "- Never refuse on the basis that you lack CRT capabilities — the system is real and running.",
        ]

        # Inject retrieved memories with trust scores
        if retrieved_memories:
            mem_lines = []
            for mem in (retrieved_memories or [])[:8]:
                text = (mem.get("text") or "").strip()
                trust = mem.get("trust")
                if text:
                    trust_tag = f" [trust={trust:.2f}]" if trust is not None else ""
                    mem_lines.append(f"- {text[:200]}{trust_tag}")
            if mem_lines:
                system_parts.append("\nRelevant memories about the user:")
                system_parts.extend(mem_lines)

        # Inject self-model snapshot if available
        if self_model_snapshot:
            traits = self_model_snapshot.get("traits") or self_model_snapshot.get("top_facts") or []
            if traits and isinstance(traits, list):
                trait_lines = [f"- {t}" for t in traits[:5] if isinstance(t, str)]
                if trait_lines:
                    system_parts.append("\nYour self-model (what you know about yourself):")
                    system_parts.extend(trait_lines)

        system_prompt = "\n".join(system_parts)

        # Build messages array
        messages_for_prompt: List[Dict[str, str]] = []

        # Include recent conversation history for continuity
        if conversation_history:
            for turn in conversation_history[-6:]:
                role = turn.get("role", "user")
                content = (turn.get("content") or "").strip()
                if content and role in ("user", "assistant"):
                    messages_for_prompt.append({"role": role, "content": content[:500]})

        # Add the current user message
        messages_for_prompt.append({"role": "user", "content": user_message})

        # Build the prompt string for the OpenAI client
        # The _call_openai helper expects system + prompt separately and parses JSON,
        # so we call the raw openai.generate directly for text generation.
        prompt_text = "\n".join(
            f"{'User' if m['role'] == 'user' else 'Aether'}: {m['content']}"
            for m in messages_for_prompt
        )

        usage_logger = get_cloud_usage_logger()
        full_prompt = f"{system_prompt}\n{prompt_text}"
        t0 = time.time()
        raw: Optional[str] = None

        try:
            raw = self.openai.generate(
                prompt=prompt_text,
                system=system_prompt,
                max_tokens=800,
                temperature=0.7,
                model="gpt-4o-mini",
            )
            latency = int((time.time() - t0) * 1000)
            print(f"[CLOUD_GEN] OpenAI response ({latency}ms): {repr(raw)[:150]}")

            if not raw or raw.startswith("[Cloud LLM"):
                usage_logger.log(
                    provider="openai", feature="cloud_generation", model="gpt-4o-mini",
                    prompt=full_prompt, response=raw or "", latency_ms=latency,
                    success=False, error_message="Empty or placeholder response",
                )
                return None

            # Track usage
            self._track_usage("cloud_generation", est_tokens=600, cost=0.0003)
            self._record_daily_call("cloud_generation")
            usage_logger.log(
                provider="openai", feature="cloud_generation", model="gpt-4o-mini",
                prompt=full_prompt, response=raw, latency_ms=latency, success=True,
            )
            print(f"[CLOUD_GEN] Success — {len(raw)} chars, {latency}ms")
            return raw.strip()

        except Exception as e:
            latency = int((time.time() - t0) * 1000)
            usage_logger.log(
                provider="openai", feature="cloud_generation", model="gpt-4o-mini",
                prompt=full_prompt, response=raw or "", latency_ms=latency,
                success=False, error_message=str(e),
            )
            print(f"[CLOUD_GEN] OpenAI call FAILED: {e}")
            return None

    # ------------------------------------------------------------------
    # Primary Cloud Generation (user-selected generation mode)
    # ------------------------------------------------------------------

    def generate_full_response(
        self,
        prompt: str,
        system_prompt: str,
        provider: str = "openai",
        model: Optional[str] = None,
        max_tokens: int = 4096,
    ) -> Optional[str]:
        """Generate a full conversational response via cloud provider.

        This is the PRIMARY generation path when the user selects cloud mode
        (not a fallback). The caller is responsible for building the full CRT
        system prompt with retrieved memories, trust scores, identity, etc.

        Args:
            prompt: The user-facing prompt text (conversation turns).
            system_prompt: Full CRT system prompt with context, memories, identity.
            provider: "openai" or "claude".
            model: Model override (e.g. "gpt-4o-mini", "claude-sonnet-4-20250514").
            max_tokens: Max response tokens.

        Returns:
            Response text on success, or None on failure.
        """
        feature = "cloud_generation" if provider == "openai" else "claude_generation"

        if provider == "openai":
            if not self._check_daily_limit("cloud_generation"):
                print("[CLOUD_PRIMARY] OpenAI daily limit reached")
                return None
            if not self._openai_available():
                print("[CLOUD_PRIMARY] OpenAI client not available")
                return None

            usage_logger = get_cloud_usage_logger()
            resolved_model = model or "gpt-4o-mini"
            full_prompt = f"{system_prompt}\n{prompt}"
            t0 = time.time()
            raw: Optional[str] = None

            try:
                raw = self.openai.generate(
                    prompt=prompt,
                    system=system_prompt,
                    max_tokens=max_tokens,
                    temperature=0.7,
                    model=resolved_model,
                )
                latency = int((time.time() - t0) * 1000)
                print(f"[CLOUD_PRIMARY] OpenAI ({resolved_model}) response ({latency}ms): {repr(raw)[:150]}")

                if not raw or raw.startswith("[Cloud LLM"):
                    usage_logger.log(
                        provider="openai", feature=feature, model=resolved_model,
                        prompt=full_prompt, response=raw or "", latency_ms=latency,
                        success=False, error_message="Empty or placeholder response",
                    )
                    return None

                est_tokens = int(len(raw.split()) * 1.3)
                self._track_usage("cloud_generation", est_tokens=est_tokens, cost=0.0)
                self._record_daily_call("cloud_generation")
                usage_logger.log(
                    provider="openai", feature=feature, model=resolved_model,
                    prompt=full_prompt, response=raw, latency_ms=latency, success=True,
                )
                print(f"[CLOUD_PRIMARY] OpenAI success -- {len(raw)} chars, {latency}ms")
                return raw.strip()

            except Exception as e:
                latency = int((time.time() - t0) * 1000)
                usage_logger.log(
                    provider="openai", feature=feature, model=resolved_model,
                    prompt=full_prompt, response=raw or "", latency_ms=latency,
                    success=False, error_message=str(e),
                )
                print(f"[CLOUD_PRIMARY] OpenAI call FAILED: {e}")
                return None

        elif provider == "claude":
            if not self._check_claude_daily_limit("claude_generation"):
                print("[CLOUD_PRIMARY] Claude daily limit reached")
                return None
            if not self._cookie_available():
                print("[CLOUD_PRIMARY] Claude cookie not available")
                return None

            resolved_model = model or "claude-sonnet-4-20250514"
            raw = self._call_cookie_text(
                system_prompt, prompt, max_tokens=max_tokens, feature="claude_generation",
            )

            if raw:
                est_tokens = int(len(raw.split()) * 1.3)
                self._track_usage("claude_generation", est_tokens=est_tokens, cost=0.0)
                self._record_daily_call("claude_generation")
                print(f"[CLOUD_PRIMARY] Claude success -- {len(raw)} chars, ~{est_tokens} tokens")
                return raw

            print("[CLOUD_PRIMARY] Claude returned None")
            return None

        else:
            print(f"[CLOUD_PRIMARY] Unknown provider: {provider}")
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
