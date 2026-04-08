"""
Governance Bridge: Memory Store <-> Belief/Speech

Connects two previously independent data stores:
- memories table (trust-weighted facts)
- belief_speech table (what Aether said, tracked by VarianceTracker)

Three feedback loops:
1. Drift -> Trust Penalty: high topic instability penalizes supporting memories
2. Trust Drop -> Belief Reclassification: deprecated memories demote stale beliefs
3. Cross-validation at Recording: unstable topics dampen new belief trust
"""

import json
import logging
import time
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# Thresholds
DRIFT_PENALTY_THRESHOLD = 0.4       # mean_drift above this triggers penalty
FLIP_RATE_PENALTY_THRESHOLD = 0.3   # belief_flip_rate above this triggers penalty
TRUST_FLOOR_FOR_PENALTY = 0.6       # only penalize memories with trust above this
BASE_PENALTY = -0.03                # minimum penalty per cycle
MAX_PENALTY = -0.05                 # cap per cycle
RECLASSIFY_TRUST_THRESHOLD = 0.3    # trust below this triggers reclassification
REMAINING_AVG_THRESHOLD = 0.4       # remaining memories must avg above this to keep belief
UNSTABLE_TOPIC_DRIFT = 0.5          # cross-validation dampening threshold
DAMPENING_FACTOR = 0.85             # multiply trust_avg by this in unstable topics


class GovernanceBridge:
    """Bidirectional governance between memory trust and belief/speech tracking."""

    def __init__(self, memory_system, variance_tracker=None):
        """
        Args:
            memory_system: CRTMemorySystem instance (required)
            variance_tracker: VarianceTracker instance (optional, bridge is no-op without it)
        """
        self._mem = memory_system
        self._var = variance_tracker

    # ------------------------------------------------------------------
    # Bridge 1: Drift -> Trust Penalty
    # ------------------------------------------------------------------

    def apply_drift_penalty(self, analysis_result: Dict) -> Dict:
        """After variance analysis, penalize memories supporting unstable topics.

        Args:
            analysis_result: dict from VarianceTracker.run_analysis() containing
                topic_metrics (parsed) or details_json (raw).

        Returns:
            Summary dict with counts of flagged topics and penalized memories.
        """
        if self._var is None:
            return {"skipped": True}

        # Parse topic metrics
        topic_metrics = analysis_result.get("topic_metrics")
        if topic_metrics is None:
            raw = analysis_result.get("details_json", "{}")
            try:
                topic_metrics = json.loads(raw) if isinstance(raw, str) else raw
            except (json.JSONDecodeError, TypeError):
                return {"error": "could not parse topic_metrics"}

        flagged_topics = 0
        memories_penalized = 0
        penalties = []

        for topic_id, metrics in topic_metrics.items():
            mean_drift = metrics.get("mean_drift", 0) or 0
            flip_rate = metrics.get("belief_flip_rate", 0) or 0

            if mean_drift < DRIFT_PENALTY_THRESHOLD and flip_rate < FLIP_RATE_PENALTY_THRESHOLD:
                continue

            flagged_topics += 1

            # Collect memory IDs from belief entries in this topic
            memory_ids = self._get_memory_ids_for_topic(int(topic_id))
            if not memory_ids:
                continue

            # Compute penalty magnitude
            excess = max(mean_drift - DRIFT_PENALTY_THRESHOLD, 0) + max(flip_rate - FLIP_RATE_PENALTY_THRESHOLD, 0)
            penalty = max(MAX_PENALTY, BASE_PENALTY * (1 + excess))

            # Apply to each qualifying memory (skip user-stated facts —
            # those should only be demoted by explicit contradiction detection,
            # not drift analysis. Bug #7 fix: prevents runaway decay on real preferences.)
            for mid in memory_ids:
                _kind = self._get_memory_kind(mid)
                if _kind in ("user_fact", "correction"):
                    continue
                current_trust = self._get_memory_trust(mid)
                if current_trust is None or current_trust <= TRUST_FLOOR_FOR_PENALTY:
                    continue

                new_trust = max(0.0, current_trust + penalty)
                try:
                    self._mem.update_trust(
                        memory_id=mid,
                        new_trust=new_trust,
                        reason=f"governance_bridge:drift_penalty (topic={topic_id}, drift={mean_drift:.3f}, flip={flip_rate:.3f})",
                        drift=mean_drift,
                    )
                    memories_penalized += 1
                    penalties.append({
                        "memory_id": mid,
                        "old_trust": round(current_trust, 3),
                        "new_trust": round(new_trust, 3),
                        "topic_id": topic_id,
                    })
                except Exception as e:
                    logger.warning("[GOVERNANCE_BRIDGE] Failed to penalize %s: %s", mid, e)

        if memories_penalized > 0:
            logger.info(
                "[GOVERNANCE_BRIDGE] Drift penalty: %d memories penalized across %d flagged topics",
                memories_penalized, flagged_topics,
            )

        return {
            "topics_flagged": flagged_topics,
            "memories_penalized": memories_penalized,
            "penalties": penalties,
        }

    # ------------------------------------------------------------------
    # Bridge 2: Trust Drop -> Belief Reclassification
    # ------------------------------------------------------------------

    def reclassify_stale_beliefs(self, memory_id: str, new_trust: float) -> Dict:
        """When a memory's trust drops below threshold, reclassify belief entries.

        Finds belief_speech entries that relied on this memory. If this was the
        only high-trust supporting memory (or remaining avg trust is too low),
        flips is_belief from 1 to 0.

        Args:
            memory_id: The memory whose trust dropped.
            new_trust: The new (low) trust value.

        Returns:
            Summary dict with reclassification counts.
        """
        if new_trust >= RECLASSIFY_TRUST_THRESHOLD:
            return {"skipped": True, "reason": "trust above threshold"}

        conn = self._mem._get_connection()
        try:
            # Find belief entries referencing this memory
            rows = conn.execute(
                "SELECT entry_id, memory_ids_json, trust_avg FROM belief_speech "
                "WHERE is_belief = 1 AND memory_ids_json IS NOT NULL"
            ).fetchall()
        finally:
            conn.close()

        entries_to_reclassify = []

        for entry_id, mids_json, trust_avg in rows:
            try:
                mids = json.loads(mids_json)
            except (json.JSONDecodeError, TypeError):
                continue

            if memory_id not in mids:
                continue

            # Check remaining memories (exclude the dropped one)
            remaining = [m for m in mids if m != memory_id]

            if not remaining:
                # This was the only supporting memory
                entries_to_reclassify.append((entry_id, 0.0))
                continue

            # Check avg trust of remaining memories
            remaining_trusts = [self._get_memory_trust(m) for m in remaining]
            remaining_trusts = [t for t in remaining_trusts if t is not None]

            if not remaining_trusts:
                entries_to_reclassify.append((entry_id, 0.0))
                continue

            avg_remaining = sum(remaining_trusts) / len(remaining_trusts)
            if avg_remaining < REMAINING_AVG_THRESHOLD:
                entries_to_reclassify.append((entry_id, round(avg_remaining, 3)))

        # Reclassify
        if entries_to_reclassify:
            conn = self._mem._get_connection()
            try:
                for entry_id, new_avg in entries_to_reclassify:
                    conn.execute(
                        "UPDATE belief_speech SET is_belief = 0, trust_avg = ? WHERE entry_id = ?",
                        (new_avg, entry_id),
                    )
                conn.commit()
            finally:
                conn.close()

            logger.info(
                "[GOVERNANCE_BRIDGE] Reclassified %d belief entries to speech (memory %s trust=%.3f)",
                len(entries_to_reclassify), memory_id, new_trust,
            )

        return {
            "entries_reclassified": len(entries_to_reclassify),
            "memory_id": memory_id,
            "trigger_trust": round(new_trust, 3),
        }

    # ------------------------------------------------------------------
    # Bridge 3: Cross-validation at Recording Time
    # ------------------------------------------------------------------

    def validate_new_belief(
        self, query: str, memory_ids: List[str], avg_trust: float
    ) -> Tuple[float, Optional[str]]:
        """Check if the topic is unstable before recording a belief.

        Uses cached topic metrics from opinion_topics.metrics_json (no re-analysis).

        Args:
            query: The user query.
            memory_ids: Memory IDs that support this belief.
            avg_trust: Computed average trust of supporting memories.

        Returns:
            (adjusted_trust, warning_string_or_None)
        """
        if self._var is None:
            return (avg_trust, None)

        # Find topics whose belief entries reference any of these memory IDs
        max_drift = 0.0
        matched_topic = None

        conn = self._mem._get_connection()
        try:
            topics = conn.execute(
                "SELECT topic_id, metrics_json FROM opinion_topics WHERE metrics_json IS NOT NULL"
            ).fetchall()
        finally:
            conn.close()

        if not topics:
            return (avg_trust, None)

        # Check which topics contain entries referencing our memory IDs
        memory_set = set(memory_ids)
        for topic_id, metrics_json in topics:
            # Quick check: does this topic have high drift?
            try:
                metrics = json.loads(metrics_json)
            except (json.JSONDecodeError, TypeError):
                continue

            drift = metrics.get("mean_drift", 0) or 0
            if drift <= UNSTABLE_TOPIC_DRIFT:
                continue

            # Check if any belief entries in this topic reference our memories
            conn = self._mem._get_connection()
            try:
                rows = conn.execute(
                    "SELECT memory_ids_json FROM belief_speech "
                    "WHERE topic_id = ? AND is_belief = 1 AND memory_ids_json IS NOT NULL "
                    "LIMIT 20",
                    (topic_id,),
                ).fetchall()
            finally:
                conn.close()

            for (mids_json,) in rows:
                try:
                    mids = json.loads(mids_json)
                except (json.JSONDecodeError, TypeError):
                    continue
                if memory_set & set(mids):
                    if drift > max_drift:
                        max_drift = drift
                        matched_topic = topic_id
                    break

        if matched_topic is not None and max_drift > UNSTABLE_TOPIC_DRIFT:
            dampened = round(avg_trust * DAMPENING_FACTOR, 4)
            warning = (
                f"governance_bridge:unstable_topic (topic={matched_topic}, "
                f"drift={max_drift:.3f}, trust {avg_trust:.3f}->{dampened:.3f})"
            )
            logger.info("[GOVERNANCE_BRIDGE] %s", warning)
            return (dampened, warning)

        return (avg_trust, None)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _get_memory_ids_for_topic(self, topic_id: int) -> List[str]:
        """Extract unique memory IDs from belief entries in a topic."""
        conn = self._mem._get_connection()
        try:
            rows = conn.execute(
                "SELECT memory_ids_json FROM belief_speech "
                "WHERE topic_id = ? AND is_belief = 1 AND memory_ids_json IS NOT NULL",
                (topic_id,),
            ).fetchall()
        finally:
            conn.close()

        seen = set()
        for (mids_json,) in rows:
            try:
                mids = json.loads(mids_json)
                seen.update(mids)
            except (json.JSONDecodeError, TypeError):
                continue
        return list(seen)

    def _get_memory_kind(self, memory_id: str) -> Optional[str]:
        """Get the kind field for a memory, or None if not found."""
        conn = self._mem._get_connection()
        try:
            row = conn.execute(
                "SELECT kind FROM memories WHERE memory_id = ? AND deprecated = 0",
                (memory_id,),
            ).fetchone()
            return str(row[0]) if row else None
        except Exception:
            return None
        finally:
            conn.close()

    def _get_memory_trust(self, memory_id: str) -> Optional[float]:
        """Get current trust score for a memory, or None if not found."""
        conn = self._mem._get_connection()
        try:
            row = conn.execute(
                "SELECT trust FROM memories WHERE memory_id = ? AND deprecated = 0",
                (memory_id,),
            ).fetchone()
            return float(row[0]) if row else None
        finally:
            conn.close()
