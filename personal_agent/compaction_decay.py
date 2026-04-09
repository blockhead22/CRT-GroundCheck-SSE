"""
Compaction Decay Enforcement — Compaction as Trust-Degrading Event

After any compaction event, memories that were not preserved verbatim get
trust penalties. This implements the thesis that compaction is epistemically
lossy — the system should distrust beliefs that survived only as summaries.

Decay factors:
- verbatim: no trust change (full fidelity preserved)
- summary: small trust reduction (some detail lost)
- slot_only: larger reduction (most context lost)
- dropped: largest reduction (belief no longer in context)

Repeated compaction amplifies decay — a memory that's been compacted 3 times
without re-verification is less trustworthy than one compacted once.

Tool-dependent beliefs (source_kind=tool_receipt or model_output) that survive
compaction get flagged for re-verification via review_after.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import Any, Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

SUMMARY_DECAY_FACTOR = 0.05
SLOT_ONLY_DECAY_FACTOR = 0.10
DROPPED_DECAY_FACTOR = 0.15
REPEATED_COMPACTION_MULTIPLIER = 1.5

# Source kinds that need re-verification after compaction
REVERIFICATION_SOURCE_KINDS = {"tool_receipt", "model_output"}

# Re-verification window (24 hours)
REVERIFICATION_WINDOW_SECONDS = 86400

# Minimum trust floor (from CRT config)
TRUST_FLOOR = 0.20


# ---------------------------------------------------------------------------
# Result dataclass
# ---------------------------------------------------------------------------

@dataclass
class CompactionDecayResult:
    """Summary of trust changes from a compaction event."""
    memories_decayed: int = 0
    total_trust_reduction: float = 0.0
    memories_flagged_reverification: int = 0
    compaction_events_logged: int = 0
    errors: int = 0


# ---------------------------------------------------------------------------
# Core decay logic
# ---------------------------------------------------------------------------

def _decay_factor_for_representation(representation: str) -> float:
    """Get the base decay factor for a compaction representation level."""
    if representation == "verbatim":
        return 0.0
    elif representation == "summary":
        return SUMMARY_DECAY_FACTOR
    elif representation == "slot_only":
        return SLOT_ONLY_DECAY_FACTOR
    elif representation == "dropped":
        return DROPPED_DECAY_FACTOR
    return 0.0


def _effective_decay(base_decay: float, compaction_count: int, compaction_generation: int,
                     access_count: int = 0) -> float:
    """Compute effective decay with repeated-compaction amplification.

    Each additional compaction without re-verification amplifies the penalty.
    High-access memories get decay resistance — a memory accessed 50+ times
    has been actively used and confirmed through retrieval. Decaying it
    aggressively destroys earned knowledge.
    """
    if base_decay <= 0:
        return 0.0

    # Generation-based amplification (how many times in this session)
    gen_factor = 1.0 + compaction_generation * 0.1

    # Count-based amplification (total lifetime compactions)
    count_factor = REPEATED_COMPACTION_MULTIPLIER ** max(0, compaction_count - 1)

    raw_decay = base_decay * gen_factor * min(count_factor, 3.0)  # cap at 3x

    # Access-count protection: frequently retrieved memories resist decay.
    # A memory accessed 10+ times has been actively used — reduce decay.
    # A memory accessed 50+ times is clearly load-bearing — minimal decay.
    if access_count >= 50:
        raw_decay *= 0.1   # 90% protection
    elif access_count >= 20:
        raw_decay *= 0.25  # 75% protection
    elif access_count >= 10:
        raw_decay *= 0.5   # 50% protection
    elif access_count >= 5:
        raw_decay *= 0.75  # 25% protection

    return raw_decay


def apply_compaction_decay(
    snapshot: Any,
    memory_system: Any,
    ledger: Optional[Any] = None,
) -> CompactionDecayResult:
    """Apply trust penalties after a compaction event.

    For each belief in the snapshot:
    - "verbatim": no trust change
    - "summary": trust -= effective_decay(SUMMARY_DECAY_FACTOR, ...)
    - "slot_only": trust -= effective_decay(SLOT_ONLY_DECAY_FACTOR, ...)
    - "dropped": trust -= effective_decay(DROPPED_DECAY_FACTOR, ...)

    Tool-dependent beliefs (source_kind in REVERIFICATION_SOURCE_KINDS) that
    survive compaction get review_after set to now + 24h.

    All changes logged to trust_log with reason="compaction_decay".
    Updates last_compacted, compaction_count, observation_type on memory records.
    Writes to compaction_provenance table (updates trust_after).
    """
    from .db_utils import retry_on_lock

    result = CompactionDecayResult()
    now = time.time()

    conn = memory_system._get_connection()
    cursor = conn.cursor()

    try:
        for belief in snapshot.beliefs:
            base_decay = _decay_factor_for_representation(belief.representation)

            # Fetch access_count for decay resistance
            _acc = 0
            try:
                _acc_row = cursor.execute(
                    "SELECT access_count FROM memories WHERE memory_id = ?",
                    (belief.memory_id,)
                ).fetchone()
                _acc = (_acc_row[0] or 0) if _acc_row else 0
            except Exception:
                pass

            effective = _effective_decay(
                base_decay,
                belief.compaction_generation,
                belief.compaction_generation,
                access_count=_acc,
            )

            old_trust = belief.trust
            new_trust = max(TRUST_FLOOR, old_trust - effective)
            trust_delta = old_trust - new_trust

            # Update memory record
            try:
                obs_type = "survived_compaction" if belief.representation != "dropped" else belief.observation_type

                cursor.execute("""
                    UPDATE memories SET
                        last_compacted = ?,
                        compaction_count = COALESCE(compaction_count, 0) + 1,
                        observation_type = ?
                    WHERE memory_id = ?
                """, (now, obs_type, belief.memory_id))

                # Apply trust decay if non-zero
                if trust_delta > 0:
                    cursor.execute("""
                        UPDATE memories SET trust = MAX(?, trust - ?)
                        WHERE memory_id = ?
                    """, (TRUST_FLOOR, effective, belief.memory_id))

                    # Log to trust_log
                    cursor.execute("""
                        INSERT INTO trust_log (memory_id, timestamp, old_trust, new_trust, reason, drift)
                        VALUES (?, ?, ?, ?, ?, ?)
                    """, (
                        belief.memory_id,
                        now,
                        old_trust,
                        new_trust,
                        "compaction_decay",
                        effective,
                    ))

                    result.memories_decayed += 1
                    result.total_trust_reduction += trust_delta

                # Log to memory_events
                import json
                cursor.execute("""
                    INSERT INTO memory_events
                        (memory_id, timestamp, event_type, actor, reason, metadata_json)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (
                    belief.memory_id,
                    now,
                    "compaction_decay",
                    "compaction_engine",
                    f"representation={belief.representation}, gen={belief.compaction_generation}",
                    json.dumps({
                        "representation": belief.representation,
                        "generation": belief.compaction_generation,
                        "trust_before": old_trust,
                        "trust_after": new_trust,
                        "decay_applied": effective,
                        "snapshot_id": snapshot.snapshot_id,
                    }),
                ))
                result.compaction_events_logged += 1

                # Update compaction_provenance trust_after
                cursor.execute("""
                    UPDATE compaction_provenance SET trust_after = ?
                    WHERE memory_id = ? AND snapshot_id = ?
                """, (new_trust, belief.memory_id, snapshot.snapshot_id))

                # Flag for re-verification if tool-dependent
                if belief.source_kind in REVERIFICATION_SOURCE_KINDS and belief.representation != "verbatim":
                    review_after = now + REVERIFICATION_WINDOW_SECONDS
                    cursor.execute("""
                        UPDATE memories SET review_after = ?
                        WHERE memory_id = ? AND (review_after IS NULL OR review_after > ?)
                    """, (review_after, belief.memory_id, review_after))

                    cursor.execute("""
                        UPDATE compaction_provenance SET flagged_reverification = 1
                        WHERE memory_id = ? AND snapshot_id = ?
                    """, (belief.memory_id, snapshot.snapshot_id))

                    result.memories_flagged_reverification += 1

            except Exception as e:
                logger.warning(f"[COMPACTION_DECAY] Error processing {belief.memory_id}: {e}")
                result.errors += 1

        conn.commit()
    except Exception as e:
        logger.error(f"[COMPACTION_DECAY] Failed to apply decay: {e}")
        conn.rollback()
    finally:
        conn.close()

    logger.info(
        f"[COMPACTION_DECAY] decayed={result.memories_decayed} "
        f"total_reduction={result.total_trust_reduction:.3f} "
        f"reverification={result.memories_flagged_reverification} "
        f"events={result.compaction_events_logged}"
    )

    return result
