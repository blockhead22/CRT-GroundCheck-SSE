"""Emotional Router — routes to providers based on emotional state of the conversation.

Collects signals from existing detectors (mood, volatility, tension, cascade,
active inference urgency) and recommends a provider tier and generation parameters.

This router is ADVISORY — it can escalate but never downgrade from whatever
the existing escalation policy already decided.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# Tier ordering for comparison (higher index = more capable)
TIER_RANK = {"local": 0, "openai": 1, "claude": 2}


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class EmotionalState:
    """Snapshot of the conversation's emotional signals."""
    mood: str = "calm"                 # calm/warm/playful/intense/curious/uncertain
    intensity: float = 0.3             # 0-1
    volatility: float = 0.0            # V(t) from existing formula
    urgency: str = "NONE"              # NONE/LOW/MEDIUM/HIGH/CRITICAL (active inference)
    tension_count: int = 0             # active tensions from tension_detector
    cascade_pressure: float = 0.0      # max_pressure from last cascade
    held_contradictions: int = 0       # count of BOTH-state contradictions
    drift_severity: float = 0.0        # from last drift event alignment

    def to_dict(self) -> Dict[str, Any]:
        return {
            "mood": self.mood,
            "intensity": round(self.intensity, 2),
            "volatility": round(self.volatility, 3),
            "urgency": self.urgency,
            "tension_count": self.tension_count,
            "cascade_pressure": round(self.cascade_pressure, 3),
            "held_contradictions": self.held_contradictions,
            "drift_severity": round(self.drift_severity, 3),
        }


@dataclass
class RoutingRecommendation:
    """Recommended provider tier and generation parameters."""
    provider_tier: str = "local"       # "local", "openai", "claude"
    temperature: float = 0.5           # 0.0-1.0
    max_tokens_multiplier: float = 1.0 # scale the adaptive depth
    reasoning_mode: str = "quick"      # quick/thinking/deep
    reason: str = "default"            # why this recommendation

    def to_dict(self) -> Dict[str, Any]:
        return {
            "provider_tier": self.provider_tier,
            "temperature": self.temperature,
            "max_tokens_multiplier": round(self.max_tokens_multiplier, 2),
            "reasoning_mode": self.reasoning_mode,
            "reason": self.reason,
        }


# ---------------------------------------------------------------------------
# Compute EmotionalState from existing signals
# ---------------------------------------------------------------------------

def compute_emotional_state(
    mood_result: Optional[Dict[str, Any]] = None,
    volatility: float = 0.0,
    urgency: str = "NONE",
    tensions: Optional[List[Any]] = None,
    cascade_pressure: float = 0.0,
    held_contradictions: int = 0,
    drift_severity: float = 0.0,
) -> EmotionalState:
    """Collect signals from existing detectors into a unified EmotionalState.

    Args:
        mood_result: Dict from _detect_response_mood() with keys mood, intensity, triggers.
        volatility: V(t) from volatility_context or computed inline.
        urgency: From active_inference Urgency enum value (LOW/MEDIUM/HIGH/CRITICAL)
                 or string "NONE" if no active inquiry.
        tensions: List of Tension objects from tension_detector.
        cascade_pressure: max_pressure from last cascade result.
        held_contradictions: Count of BOTH-state contradictions from ledger.
        drift_severity: From last drift event alignment score.

    Returns:
        EmotionalState ready for routing.
    """
    mood = "calm"
    intensity = 0.3

    if mood_result and isinstance(mood_result, dict):
        mood = mood_result.get("mood", "calm")
        intensity = mood_result.get("intensity", 0.3)

    tension_count = len(tensions) if tensions else 0

    # Normalize urgency to uppercase string
    urgency_str = str(urgency).upper().strip()
    if urgency_str not in ("NONE", "LOW", "MEDIUM", "HIGH", "CRITICAL"):
        urgency_str = "NONE"

    return EmotionalState(
        mood=mood,
        intensity=intensity,
        volatility=volatility,
        urgency=urgency_str,
        tension_count=tension_count,
        cascade_pressure=cascade_pressure,
        held_contradictions=held_contradictions,
        drift_severity=drift_severity,
    )


# ---------------------------------------------------------------------------
# EmotionalRouter
# ---------------------------------------------------------------------------

class EmotionalRouter:
    """Routes to providers based on emotional state of the conversation.

    Six rules, evaluated in priority order. First match wins.
    The router only ESCALATES — it never recommends a lower tier than
    what the existing escalation policy decided.
    """

    def route(self, state: EmotionalState) -> RoutingRecommendation:
        """Given the emotional state, recommend a provider and parameters.

        Rules (priority order):
        1. HIGH PRESSURE   — urgency=CRITICAL/IMMINENT or volatility > 0.7
        2. MOUNTING TENSION — urgency=HIGH/WARN or tension_count >= 2
        3. HELD CONTRADICTION — held_contradictions > 0 and mood=uncertain
        4. UNCERTAINTY/WIDENING — mood=uncertain and volatility > 0.4
        5. CURIOUS/EXPLORATORY — mood=curious and intensity > 0.5
        6. CALM/WARM — mood in (calm, warm) and volatility < 0.2
        """

        # Rule 1: HIGH PRESSURE
        if state.urgency in ("CRITICAL", "IMMINENT") or state.volatility > 0.7:
            return RoutingRecommendation(
                provider_tier="claude",
                temperature=0.1,
                max_tokens_multiplier=1.5,
                reasoning_mode="deep",
                reason="high emotional pressure requires most capable model",
            )

        # Rule 2: MOUNTING TENSION
        if state.urgency in ("HIGH", "WARN") or state.tension_count >= 2:
            return RoutingRecommendation(
                provider_tier="openai",
                temperature=0.3,
                max_tokens_multiplier=1.2,
                reasoning_mode="thinking",
                reason="tension requires careful reasoning",
            )

        # Rule 3: HELD CONTRADICTION (does NOT escalate — local is fine)
        if state.held_contradictions > 0 and state.mood == "uncertain":
            return RoutingRecommendation(
                provider_tier="local",
                temperature=0.0,
                max_tokens_multiplier=1.0,
                reasoning_mode="quick",
                reason="held states don't need escalation, need retrieval",
            )

        # Rule 4: UNCERTAINTY / WIDENING
        if state.mood == "uncertain" and state.volatility > 0.4:
            return RoutingRecommendation(
                provider_tier="openai",
                temperature=0.2,
                max_tokens_multiplier=1.2,
                reasoning_mode="thinking",
                reason="growing uncertainty benefits from stronger model",
            )

        # Rule 5: CURIOUS / EXPLORATORY
        if state.mood == "curious" and state.intensity > 0.5:
            return RoutingRecommendation(
                provider_tier="openai",
                temperature=0.6,
                max_tokens_multiplier=1.0,
                reasoning_mode="thinking",
                reason="exploratory queries benefit from broader knowledge",
            )

        # Rule 6: CALM / WARM (default low tier)
        if state.mood in ("calm", "warm") and state.volatility < 0.2:
            return RoutingRecommendation(
                provider_tier="local",
                temperature=0.5,
                max_tokens_multiplier=1.0,
                reasoning_mode="quick",
                reason="stable state, local model sufficient",
            )

        # Fallback: moderate parameters, no escalation
        return RoutingRecommendation(
            provider_tier="local",
            temperature=0.4,
            max_tokens_multiplier=1.0,
            reasoning_mode="quick",
            reason="no emotional routing trigger matched",
        )

    def apply_to_decision(
        self,
        state: EmotionalState,
        current_tier: str,
        current_reason: str,
    ) -> Dict[str, Any]:
        """Route and apply as an escalation-only override.

        Returns a dict with:
            - escalated: bool (True if emotional routing changed the tier)
            - new_tier: str (the tier after emotional routing)
            - recommendation: RoutingRecommendation
            - reason_suffix: str (to append to existing reason)
        """
        rec = self.route(state)

        current_rank = TIER_RANK.get(current_tier, 0)
        rec_rank = TIER_RANK.get(rec.provider_tier, 0)

        escalated = rec_rank > current_rank
        new_tier = rec.provider_tier if escalated else current_tier

        # Log the routing decision
        logger.info(
            "[EMOTIONAL_ROUTING] mood=%s volatility=%.2f urgency=%s "
            "tensions=%d held=%d → %s temp=%.1f mode=%s%s",
            state.mood, state.volatility, state.urgency,
            state.tension_count, state.held_contradictions,
            rec.provider_tier, rec.temperature, rec.reasoning_mode,
            " (ESCALATED)" if escalated else " (no change)",
        )

        reason_suffix = ""
        if escalated:
            reason_suffix = f" + emotional_routing: {rec.reason}"

        return {
            "escalated": escalated,
            "new_tier": new_tier,
            "recommendation": rec,
            "reason_suffix": reason_suffix,
        }


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------

_instance: Optional[EmotionalRouter] = None


def get_emotional_router() -> EmotionalRouter:
    """Get or create the singleton EmotionalRouter."""
    global _instance
    if _instance is None:
        _instance = EmotionalRouter()
    return _instance
