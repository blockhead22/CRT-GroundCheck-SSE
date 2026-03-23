"""Semi-automatic labeling of contradiction pairs using heuristics.

The AutoLabeler produces training labels — it does NOT use a trained model.
"""

from __future__ import annotations

from typing import Tuple

from .features import extract_features
from .types import BeliefType, ContradictionPair, PolicyAction


class AutoLabeler:
    """Heuristic-based labeler that produces (label, confidence) tuples.

    Used to generate training data for the XGBoost classifiers.
    """

    # ── Belief classification ────────────────────────────────────────────

    def label_belief(
        self, pair: ContradictionPair
    ) -> Tuple[BeliefType, float]:
        """Return (predicted_label, confidence) using rule-based heuristics."""
        feats = extract_features(pair)

        has_temporal = feats["has_temporal_language"] > 0.5
        has_correction = feats["has_correction_language"] > 0.5
        has_negation = feats["has_negation"] > 0.5
        time_gap_hours = feats["time_gap_hours"]
        similarity = feats["similarity"]
        is_exclusive = feats["is_exclusive"] > 0.5
        trust_delta = feats["trust_delta"]

        # Rule 1: temporal language + significant time gap
        if has_temporal and time_gap_hours > 24.0:
            return BeliefType.TEMPORAL, 0.8

        # Rule 2: correction language + exclusive slot
        if has_correction and is_exclusive:
            return BeliefType.REVISION, 0.85

        # Rule 3: negation with high trust on the new statement
        if has_negation and pair.new_trust > 0.7:
            return BeliefType.CONFLICT, 0.7

        # Rule 4: very similar texts -> refinement
        if similarity > 0.85:
            return BeliefType.REFINEMENT, 0.75

        # Rule 5: exclusive slot + meaningful trust delta -> revision
        if is_exclusive and trust_delta > 0.2:
            return BeliefType.REVISION, 0.7

        # Default fallback
        return BeliefType.CONFLICT, 0.5

    # ── Policy classification ────────────────────────────────────────────

    def label_policy(
        self,
        pair: ContradictionPair,
        belief: BeliefType,
    ) -> Tuple[PolicyAction, float]:
        """Given a belief classification, determine the policy action."""
        feats = extract_features(pair)
        is_exclusive = feats["is_exclusive"] > 0.5
        trust_delta = feats["trust_delta"]

        if belief == BeliefType.REFINEMENT:
            # Both are compatible — keep them
            return PolicyAction.PRESERVE, 0.9

        if belief == BeliefType.REVISION:
            if is_exclusive and pair.new_trust > 0.7:
                return PolicyAction.OVERRIDE, 0.85
            return PolicyAction.PRESERVE, 0.7

        if belief == BeliefType.TEMPORAL:
            # Both true at different times
            return PolicyAction.PRESERVE, 0.9

        # CONFLICT
        if pair.old_trust > 0.8 and pair.new_trust > 0.8:
            return PolicyAction.ASK_USER, 0.8
        if abs(trust_delta) > 0.3:
            return PolicyAction.OVERRIDE, 0.75
        return PolicyAction.PRESERVE, 0.6
