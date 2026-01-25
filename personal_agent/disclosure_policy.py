"""
Disclosure Policy for CRT System - Yellow Zone Routing.

Implements intelligent routing of uncertain facts (P(valid) in 0.4-0.9 range)
to clarification instead of binary accept/reject.

Design Philosophy:
- Not all facts are equally certain
- Yellow zone (medium confidence) should trigger clarification
- Green zone (high confidence) can be accepted
- Red zone (low confidence) should be rejected
- Disclosure budget prevents overwhelming users with constant questions

Usage:
    from personal_agent.disclosure_policy import DisclosurePolicy, DisclosureDecision
    
    policy = DisclosurePolicy()
    decision = policy.should_disclose(
        p_valid=0.65,
        slot="employer",
        old_value="Microsoft",
        new_value="Google"
    )
    
    if decision.action == "clarify":
        # Route to clarification
        prompt = decision.clarification_prompt
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Set

logger = logging.getLogger(__name__)


class DisclosureAction(str, Enum):
    """Actions for handling uncertain facts."""
    ACCEPT = "accept"      # High confidence - accept without question
    CLARIFY = "clarify"    # Medium confidence - ask user to clarify
    REJECT = "reject"      # Low confidence - reject as noise


@dataclass
class DisclosureDecision:
    """
    Decision about how to handle a fact or contradiction.
    
    Attributes:
        action: What action to take (accept, clarify, reject)
        reason: Why this decision was made
        p_valid: Probability that the fact is valid (0-1)
        clarification_prompt: Optional prompt to show user if action is CLARIFY
        metadata: Additional metadata for logging/debugging
    """
    action: DisclosureAction
    reason: str
    p_valid: float
    clarification_prompt: Optional[str] = None
    metadata: Dict[str, any] = field(default_factory=dict)


@dataclass
class DisclosureBudget:
    """
    Tracks disclosure budget to prevent overwhelming users.
    
    Attributes:
        max_disclosures_per_session: Maximum clarifications per session
        max_disclosures_per_slot: Maximum clarifications per fact slot
        cooldown_seconds: Minimum time between disclosures for same slot
    """
    max_disclosures_per_session: int = 3
    max_disclosures_per_slot: int = 2
    cooldown_seconds: float = 300.0  # 5 minutes
    
    # Tracking
    session_count: int = 0
    slot_counts: Dict[str, int] = field(default_factory=dict)
    last_disclosure_time: Dict[str, float] = field(default_factory=dict)
    
    def can_disclose(self, slot: str) -> bool:
        """Check if we can disclose for this slot given budget constraints."""
        # Check session limit
        if self.session_count >= self.max_disclosures_per_session:
            logger.debug(
                f"[DISCLOSURE] Session budget exhausted: "
                f"{self.session_count}/{self.max_disclosures_per_session}"
            )
            return False
        
        # Check per-slot limit
        slot_count = self.slot_counts.get(slot, 0)
        if slot_count >= self.max_disclosures_per_slot:
            logger.debug(
                f"[DISCLOSURE] Slot '{slot}' budget exhausted: "
                f"{slot_count}/{self.max_disclosures_per_slot}"
            )
            return False
        
        # Check cooldown
        last_time = self.last_disclosure_time.get(slot, 0)
        time_since = time.time() - last_time
        if time_since < self.cooldown_seconds:
            logger.debug(
                f"[DISCLOSURE] Slot '{slot}' in cooldown: "
                f"{time_since:.1f}s < {self.cooldown_seconds}s"
            )
            return False
        
        return True
    
    def record_disclosure(self, slot: str) -> None:
        """Record that a disclosure was made."""
        self.session_count += 1
        self.slot_counts[slot] = self.slot_counts.get(slot, 0) + 1
        self.last_disclosure_time[slot] = time.time()
        logger.info(
            f"[DISCLOSURE] Recorded for '{slot}': "
            f"session={self.session_count}, slot_count={self.slot_counts[slot]}"
        )


class DisclosurePolicy:
    """
    Manages disclosure decisions for uncertain facts.
    
    Implements three-zone threshold system:
    - Green zone (P >= 0.9): Accept without disclosure
    - Yellow zone (0.4 <= P < 0.9): Route to clarification
    - Red zone (P < 0.4): Reject as noise
    
    High-stakes domains (name, employer, medical) always get disclosure
    even if budget is exhausted.
    """
    
    # High-stakes domains that always require disclosure
    HIGH_STAKES_SLOTS: Set[str] = {
        "name",
        "employer",
        "location",
        "medical_diagnosis",
        "legal_status",
        "account_status",
    }
    
    def __init__(
        self,
        green_threshold: float = 0.9,
        yellow_threshold: float = 0.4,
        enable_budget: bool = True,
        budget: Optional[DisclosureBudget] = None,
    ):
        """
        Initialize disclosure policy.
        
        Args:
            green_threshold: Minimum P(valid) for auto-accept
            yellow_threshold: Minimum P(valid) for clarification (below is reject)
            enable_budget: Whether to enforce disclosure budgets
            budget: Custom budget (creates default if None)
        """
        self.green_threshold = green_threshold
        self.yellow_threshold = yellow_threshold
        self.enable_budget = enable_budget
        self.budget = budget or DisclosureBudget()
    
    def should_disclose(
        self,
        p_valid: float,
        slot: str,
        old_value: Optional[str] = None,
        new_value: Optional[str] = None,
        context: Optional[Dict[str, any]] = None,
    ) -> DisclosureDecision:
        """
        Decide how to handle a fact based on confidence.
        
        Args:
            p_valid: Probability that the fact is valid (0-1)
            slot: Fact slot (e.g., "employer", "name")
            old_value: Previous value (for contradictions)
            new_value: New value (for contradictions)
            context: Additional context for decision
            
        Returns:
            DisclosureDecision with action and optional clarification prompt
        """
        context = context or {}
        
        # ============================================================
        # Green zone: High confidence - accept without question
        # ============================================================
        if p_valid >= self.green_threshold:
            return DisclosureDecision(
                action=DisclosureAction.ACCEPT,
                reason=f"High confidence (P={p_valid:.2f} >= {self.green_threshold})",
                p_valid=p_valid,
                metadata={"zone": "green"}
            )
        
        # ============================================================
        # Red zone: Low confidence - reject as noise
        # ============================================================
        if p_valid < self.yellow_threshold:
            return DisclosureDecision(
                action=DisclosureAction.REJECT,
                reason=f"Low confidence (P={p_valid:.2f} < {self.yellow_threshold})",
                p_valid=p_valid,
                metadata={"zone": "red"}
            )
        
        # ============================================================
        # Yellow zone: Medium confidence - route to clarification
        # ============================================================
        
        # Check if this is a high-stakes slot (always disclose)
        is_high_stakes = slot in self.HIGH_STAKES_SLOTS
        
        # Check disclosure budget (unless high-stakes)
        can_disclose = True
        if self.enable_budget and not is_high_stakes:
            can_disclose = self.budget.can_disclose(slot)
        
        if not can_disclose:
            # Budget exhausted - default to accepting with uncertainty
            return DisclosureDecision(
                action=DisclosureAction.ACCEPT,
                reason=f"Yellow zone but budget exhausted (P={p_valid:.2f})",
                p_valid=p_valid,
                metadata={"zone": "yellow", "budget_exhausted": True}
            )
        
        # Generate clarification prompt
        prompt = self._generate_clarification_prompt(
            slot=slot,
            old_value=old_value,
            new_value=new_value,
            p_valid=p_valid
        )
        
        # Record disclosure if budget is enabled
        if self.enable_budget:
            self.budget.record_disclosure(slot)
        
        return DisclosureDecision(
            action=DisclosureAction.CLARIFY,
            reason=f"Yellow zone - needs clarification (P={p_valid:.2f})",
            p_valid=p_valid,
            clarification_prompt=prompt,
            metadata={"zone": "yellow", "high_stakes": is_high_stakes}
        )
    
    def _generate_clarification_prompt(
        self,
        slot: str,
        old_value: Optional[str],
        new_value: Optional[str],
        p_valid: float,
    ) -> str:
        """
        Generate a user-friendly clarification prompt.
        
        Args:
            slot: Fact slot
            old_value: Previous value (if contradiction)
            new_value: New value
            p_valid: Confidence level
            
        Returns:
            Natural language prompt for user
        """
        # Format slot name for display
        slot_display = slot.replace("_", " ").title()
        
        # If we have both old and new values, it's a contradiction
        if old_value and new_value:
            return (
                f"I noticed you mentioned {new_value} for your {slot_display}, "
                f"but I previously had {old_value}. "
                f"Which one is correct?"
            )
        
        # Otherwise, it's a new fact with medium confidence
        if new_value:
            return (
                f"Just to confirm - is your {slot_display} {new_value}? "
                f"I want to make sure I have this right."
            )
        
        # Fallback
        return f"Can you confirm your {slot_display}?"
    
    def reset_budget(self) -> None:
        """Reset disclosure budget (e.g., at start of new session)."""
        if self.enable_budget:
            self.budget = DisclosureBudget()
            logger.info("[DISCLOSURE] Budget reset")


def load_calibrated_thresholds(path: str) -> Optional[Dict[str, float]]:
    """
    Load calibrated thresholds from JSON file.
    
    Args:
        path: Path to calibrated thresholds JSON
        
    Returns:
        Dictionary with green_zone, yellow_zone, red_zone thresholds,
        or None if loading fails
    """
    try:
        import json
        from pathlib import Path
        
        threshold_file = Path(path)
        if not threshold_file.exists():
            logger.warning(f"[DISCLOSURE] Threshold file not found: {path}")
            return None
        
        with open(threshold_file) as f:
            data = json.load(f)
        
        return {
            "green_zone": data.get("green_zone", 0.9),
            "yellow_zone": data.get("yellow_zone", 0.65),
            "red_zone": data.get("red_zone", 0.4),
        }
    except Exception as e:
        logger.warning(f"[DISCLOSURE] Failed to load thresholds from {path}: {e}")
        return None


def create_disclosure_policy_from_calibration(
    calibration_path: str = "artifacts/calibrated_thresholds.json",
    enable_budget: bool = True,
) -> DisclosurePolicy:
    """
    Create a DisclosurePolicy using calibrated thresholds.
    
    Args:
        calibration_path: Path to calibrated thresholds JSON
        enable_budget: Whether to enable disclosure budgets
        
    Returns:
        DisclosurePolicy configured with calibrated thresholds
    """
    thresholds = load_calibrated_thresholds(calibration_path)
    
    if thresholds:
        logger.info(
            f"[DISCLOSURE] Using calibrated thresholds: "
            f"green={thresholds['green_zone']}, "
            f"yellow={thresholds['yellow_zone']}"
        )
        return DisclosurePolicy(
            green_threshold=thresholds["green_zone"],
            yellow_threshold=thresholds["yellow_zone"],
            enable_budget=enable_budget,
        )
    else:
        logger.info("[DISCLOSURE] Using default thresholds (calibration not found)")
        return DisclosurePolicy(enable_budget=enable_budget)
