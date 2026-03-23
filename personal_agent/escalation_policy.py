"""Escalation Policy — smart tier routing with circuit breaker.

Decides which generation tier to start at (local, openai, claude) based on:
1. Circuit breaker state — recent failure history per tier
2. Query characteristics — token budget, reflection blindspot boost

State is in-memory (resets on server restart). No DB tables needed.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

TIERS = ("local", "openai", "claude")


@dataclass
class TierState:
    name: str
    consecutive_failures: int = 0
    last_failure_ts: float = 0.0
    last_success_ts: float = 0.0
    cooldown_until: float = 0.0
    # Track failure timestamps for windowed counting
    failure_timestamps: List[float] = field(default_factory=list)


@dataclass
class EscalationDecision:
    start_tier: str          # which tier to try first
    skip_tiers: List[str]    # tiers to skip entirely
    reason: str              # human-readable for logging
    boosted: bool = False    # True if query characteristics escalated

    def to_dict(self) -> Dict[str, Any]:
        return {
            "start_tier": self.start_tier,
            "skip_tiers": self.skip_tiers,
            "reason": self.reason,
            "boosted": self.boosted,
        }


# ---------------------------------------------------------------------------
# Default config
# ---------------------------------------------------------------------------

_DEFAULT_ESCALATION_CONFIG: Dict[str, Any] = {
    "enabled": True,
    "circuit_breaker": {
        "trip_threshold": 3,
        "window_seconds": 600,
        "cooldown_local_seconds": 300,
        "cooldown_cloud_seconds": 120,
    },
    "query_routing": {
        "token_threshold_for_cloud": 6000,
        "gate_boost_threshold": 0.10,
    },
}


# ---------------------------------------------------------------------------
# EscalationPolicy
# ---------------------------------------------------------------------------

class EscalationPolicy:
    """Stateful tier routing with circuit breaker and query-aware escalation."""

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        cfg = config or _DEFAULT_ESCALATION_CONFIG
        self.enabled: bool = cfg.get("enabled", True)

        cb = cfg.get("circuit_breaker", {})
        self.trip_threshold: int = cb.get("trip_threshold", 3)
        self.window_seconds: float = cb.get("window_seconds", 600)
        self.cooldown_local: float = cb.get("cooldown_local_seconds", 300)
        self.cooldown_cloud: float = cb.get("cooldown_cloud_seconds", 120)

        qr = cfg.get("query_routing", {})
        self.token_threshold: int = qr.get("token_threshold_for_cloud", 6000)
        self.gate_boost_threshold: float = qr.get("gate_boost_threshold", 0.10)

        self._tiers: Dict[str, TierState] = {
            name: TierState(name=name) for name in TIERS
        }

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def decide(
        self,
        query: str = "",
        generation_mode: str = "local",
        context_token_estimate: int = 0,
        gate_boost: float = 0.0,
    ) -> EscalationDecision:
        """Decide which tier to start generation at.

        Args:
            query: The user's message (unused for now, reserved for future heuristics).
            generation_mode: User's configured generation mode ("local", "cloud_openai", "cloud_claude").
            context_token_estimate: Estimated token count of prompt + history + memories.
            gate_boost: Reflection loop blindspot gate boost (0.0-0.15).

        Returns:
            EscalationDecision with start_tier, skip_tiers, and reason.
        """
        if not self.enabled:
            return EscalationDecision(
                start_tier=self._mode_to_tier(generation_mode),
                skip_tiers=[],
                reason="escalation_disabled",
            )

        # If user explicitly chose a cloud mode, respect it — no escalation needed
        if generation_mode in ("cloud_openai", "cloud_claude"):
            tier = "openai" if generation_mode == "cloud_openai" else "claude"
            return EscalationDecision(
                start_tier=tier,
                skip_tiers=[],
                reason=f"user_selected_{tier}",
            )

        # --- generation_mode == "local" from here ---
        now = time.time()
        skip: List[str] = []
        reasons: List[str] = []
        boosted = False

        # 1. Circuit breaker — check if local tier is in cooldown
        local_state = self._tiers["local"]
        if self._is_tripped(local_state, now):
            skip.append("local")
            remaining = int(local_state.cooldown_until - now)
            reasons.append(f"circuit_breaker_local ({remaining}s remaining)")
            logger.info(
                "[ESCALATION] Skipping local tier — cooldown active until %s",
                time.strftime("%H:%M:%S", time.localtime(local_state.cooldown_until)),
            )

        # 2. Query-aware routing — token budget
        if "local" not in skip and context_token_estimate > self.token_threshold:
            skip.append("local")
            reasons.append(
                f"token_estimate_{context_token_estimate}>{self.token_threshold}"
            )
            boosted = True
            logger.info(
                "[ESCALATION] Query token estimate %d > threshold %d — routing to cloud",
                context_token_estimate,
                self.token_threshold,
            )

        # 3. Query-aware routing — reflection blindspot boost
        if "local" not in skip and gate_boost > self.gate_boost_threshold:
            skip.append("local")
            reasons.append(f"blindspot_boost_{gate_boost:.2f}>{self.gate_boost_threshold}")
            boosted = True
            logger.info(
                "[ESCALATION] Blindspot gate boost %.2f > threshold %.2f — routing to cloud",
                gate_boost,
                self.gate_boost_threshold,
            )

        # Determine start tier
        if "local" in skip:
            # Check openai tier health
            openai_state = self._tiers["openai"]
            if self._is_tripped(openai_state, now):
                skip.append("openai")
                reasons.append("circuit_breaker_openai")
                start_tier = "claude"
            else:
                start_tier = "openai"
        else:
            start_tier = "local"

        reason = "; ".join(reasons) if reasons else "default_local"

        decision = EscalationDecision(
            start_tier=start_tier,
            skip_tiers=skip,
            reason=reason,
            boosted=boosted,
        )

        if skip:
            logger.info(
                "[ESCALATION] Decision: start_tier=%s, skip=%s, reason=%s",
                start_tier,
                skip,
                reason,
            )

        return decision

    def record_success(self, tier: str) -> None:
        """Record a successful generation — resets circuit breaker for the tier."""
        state = self._tiers.get(tier)
        if state is None:
            return
        state.consecutive_failures = 0
        state.failure_timestamps.clear()
        state.last_success_ts = time.time()
        state.cooldown_until = 0.0
        logger.debug("[ESCALATION] Success recorded for %s — circuit breaker reset", tier)

    def record_failure(self, tier: str, error_type: str = "error") -> None:
        """Record a failed generation — may trip circuit breaker."""
        state = self._tiers.get(tier)
        if state is None:
            return

        now = time.time()
        state.last_failure_ts = now
        state.failure_timestamps.append(now)

        # Prune old failures outside the window
        cutoff = now - self.window_seconds
        state.failure_timestamps = [ts for ts in state.failure_timestamps if ts > cutoff]
        state.consecutive_failures = len(state.failure_timestamps)

        if state.consecutive_failures >= self.trip_threshold:
            cooldown = self.cooldown_local if tier == "local" else self.cooldown_cloud
            state.cooldown_until = now + cooldown
            logger.info(
                "[ESCALATION] Circuit breaker tripped for %s (%d failures in %dm) — cooldown %ds",
                tier,
                state.consecutive_failures,
                int(self.window_seconds / 60),
                int(cooldown),
            )
        else:
            logger.debug(
                "[ESCALATION] Failure recorded for %s (%s) — %d/%d in window",
                tier,
                error_type,
                state.consecutive_failures,
                self.trip_threshold,
            )

    def get_tier_states(self) -> Dict[str, Dict[str, Any]]:
        """Return current tier states for debugging/API exposure."""
        now = time.time()
        return {
            name: {
                "consecutive_failures": s.consecutive_failures,
                "last_failure_ts": s.last_failure_ts,
                "last_success_ts": s.last_success_ts,
                "cooldown_until": s.cooldown_until,
                "is_tripped": self._is_tripped(s, now),
            }
            for name, s in self._tiers.items()
        }

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _is_tripped(self, state: TierState, now: float) -> bool:
        """Check if a tier's circuit breaker is currently tripped (in cooldown)."""
        return state.cooldown_until > now

    @staticmethod
    def _mode_to_tier(generation_mode: str) -> str:
        if generation_mode == "cloud_openai":
            return "openai"
        if generation_mode == "cloud_claude":
            return "claude"
        return "local"


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------

_instance: Optional[EscalationPolicy] = None


def get_escalation_policy(config: Optional[Dict[str, Any]] = None) -> EscalationPolicy:
    """Get or create the singleton EscalationPolicy."""
    global _instance
    if _instance is None:
        if config is None:
            # Try to load from runtime config
            try:
                from personal_agent.runtime_config import get_runtime_config
                rc = get_runtime_config()
                config = rc.get("escalation_policy", _DEFAULT_ESCALATION_CONFIG)
            except Exception:
                config = _DEFAULT_ESCALATION_CONFIG
        _instance = EscalationPolicy(config=config)
    return _instance
