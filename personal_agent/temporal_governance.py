"""Temporal Governance — Phase 1

Type-dependent memory decay, freshness scoring, and supersession logic.

Each memory type has different temporal behavior:
  - FACT: no decay, superseded only by explicit contradiction
  - PREFERENCE: slow decay (months), reinforced on retrieval
  - EVENT: hard expiry at event end time
  - BELIEF: no decay, but covariance may widen over time
  - IDENTITY: no decay, highest protection from compression

Retrieval scoring:
  score = semantic_similarity * recency_weight(age, type) * trust * belief_weight

Belnap state transitions:
  - T + contradiction → Both (if held) or F (if resolvable)
  - Both + resolution → T (winner) + F (loser)
  - Both + time without resolution → stays Both (that's fine)
  - Neither + evidence → T
"""

import math
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, Dict, List, Tuple


# ---------------------------------------------------------------------------
# Decay policies per memory type
# ---------------------------------------------------------------------------

@dataclass
class DecayPolicy:
    """Temporal decay configuration for a memory type."""
    half_life_days: Optional[float]   # None = no decay
    hard_expiry: bool = False         # If True, memory dies at valid_until
    reinforcement_on_retrieval: bool = False  # Retrieval resets decay
    reinforcement_boost: float = 0.0  # How much retrieval boosts freshness (0-1)
    min_freshness: float = 0.0        # Floor — never decays below this
    compression_protection: float = 0.5  # 0=compress aggressively, 1=never compress


# Default policies — the 80% solution from THEORY.md Section 9
DECAY_POLICIES = {
    "fact": DecayPolicy(
        half_life_days=None,          # Facts don't decay
        reinforcement_on_retrieval=False,
        min_freshness=0.8,            # Always fairly fresh
        compression_protection=0.7,   # Protect from compression
    ),
    "preference": DecayPolicy(
        half_life_days=180,           # ~6 month half-life
        reinforcement_on_retrieval=True,
        reinforcement_boost=0.3,      # Retrieval restores 30% freshness
        min_freshness=0.1,
        compression_protection=0.4,
    ),
    "event": DecayPolicy(
        half_life_days=7,             # Events fade fast
        hard_expiry=True,             # Dead after valid_until
        reinforcement_on_retrieval=False,
        min_freshness=0.0,            # Can fully expire
        compression_protection=0.1,   # Compress aggressively after expiry
    ),
    "belief": DecayPolicy(
        half_life_days=None,          # Beliefs don't decay by time
        reinforcement_on_retrieval=True,
        reinforcement_boost=0.1,      # Slight boost on retrieval
        min_freshness=0.5,
        compression_protection=0.6,
    ),
    "identity": DecayPolicy(
        half_life_days=None,          # Identity never decays
        reinforcement_on_retrieval=True,
        reinforcement_boost=0.2,
        min_freshness=0.9,            # Always very fresh
        compression_protection=1.0,   # Maximum protection
    ),
}


# ---------------------------------------------------------------------------
# Freshness computation
# ---------------------------------------------------------------------------

def compute_freshness(
    created_at: float,
    memory_type: str,
    now: Optional[float] = None,
    last_retrieved_at: Optional[float] = None,
    valid_until: Optional[float] = None,
    retrieval_count: int = 0,
) -> float:
    """Compute freshness score (0-1) based on memory type and age.

    Freshness models how "current" a memory feels, not whether it's true.
    A fact about a birthday is always true but old events feel stale.
    """
    now = now or time.time()
    policy = DECAY_POLICIES.get(memory_type, DECAY_POLICIES["belief"])

    # Hard expiry check
    if policy.hard_expiry and valid_until and now > valid_until:
        return 0.0

    # No decay types
    if policy.half_life_days is None:
        base_freshness = 1.0
    else:
        age_days = (now - created_at) / 86400.0
        # Exponential decay: f = 2^(-age/half_life)
        base_freshness = math.pow(2, -age_days / policy.half_life_days)

    # Reinforcement from retrieval
    if policy.reinforcement_on_retrieval and last_retrieved_at:
        time_since_retrieval = (now - last_retrieved_at) / 86400.0
        if policy.half_life_days:
            retrieval_decay = math.pow(2, -time_since_retrieval / policy.half_life_days)
        else:
            retrieval_decay = 1.0
        retrieval_boost = policy.reinforcement_boost * retrieval_decay
        base_freshness = min(1.0, base_freshness + retrieval_boost)

    # Apply floor
    return max(policy.min_freshness, base_freshness)


# ---------------------------------------------------------------------------
# Recency-weighted retrieval scoring
# ---------------------------------------------------------------------------

def recency_weight(
    age_days: float,
    memory_type: str,
) -> float:
    """Compute recency weight for retrieval scoring.

    Different from freshness — this is the multiplier applied to
    semantic similarity during retrieval.

    Events: steep dropoff (old events are irrelevant)
    Facts: flat (a fact is a fact regardless of age)
    Preferences: moderate (recent preferences matter more)
    Beliefs/Identity: very flat (beliefs are long-lived)
    """
    weights = {
        "event":      lambda d: max(0.1, math.exp(-d / 3.0)),     # 3-day half-life
        "preference":  lambda d: max(0.3, math.exp(-d / 90.0)),    # 90-day half-life
        "fact":       lambda d: max(0.8, math.exp(-d / 365.0)),    # essentially flat
        "belief":     lambda d: max(0.6, math.exp(-d / 365.0)),    # very flat
        "identity":   lambda d: 1.0,                                # always full weight
    }
    fn = weights.get(memory_type, weights["belief"])
    return fn(age_days)


def retrieval_score(
    semantic_similarity: float,
    trust: float,
    confidence: float,
    age_days: float,
    memory_type: str,
    belief_weight_alpha: float = 0.7,
) -> float:
    """Full retrieval scoring from THEORY.md Section 9.

    score = similarity * recency_weight * trust * belief_weight

    belief_weight = alpha * trust + (1 - alpha) * confidence
    """
    rw = recency_weight(age_days, memory_type)
    bw = belief_weight_alpha * trust + (1 - belief_weight_alpha) * confidence
    return semantic_similarity * rw * bw


# ---------------------------------------------------------------------------
# Supersession logic
# ---------------------------------------------------------------------------

@dataclass
class SupersessionResult:
    """Result of checking whether a new memory supersedes an old one."""
    should_supersede: bool
    reason: str
    old_becomes: str = "deprecated"  # deprecated | held | watched


def check_supersession(
    old_text: str,
    new_text: str,
    old_type: str,
    new_type: str,
    old_trust: float,
    new_confidence: float,
    temporal_gap_days: float,
    disposition: str = "resolvable",
) -> SupersessionResult:
    """Determine if a new memory should supersede an old one.

    Only RESOLVABLE contradictions lead to supersession.
    HELD contradictions coexist. EVOLVING are watched.
    """
    if disposition == "held":
        return SupersessionResult(
            should_supersede=False,
            reason="Held contradiction — both memories preserved.",
            old_becomes="held",
        )

    if disposition == "evolving":
        return SupersessionResult(
            should_supersede=False,
            reason="Evolving belief — watching for resolution.",
            old_becomes="watched",
        )

    if disposition == "contextual":
        return SupersessionResult(
            should_supersede=False,
            reason="Contextual expression — same belief, different context.",
            old_becomes="held",
        )

    # RESOLVABLE — check if new should replace old
    if disposition == "resolvable":
        # Events always supersede
        if old_type == "event":
            return SupersessionResult(
                should_supersede=True,
                reason="Event update — new scheduling info supersedes old.",
            )

        # Facts with high confidence new > low trust old
        if new_confidence > old_trust:
            return SupersessionResult(
                should_supersede=True,
                reason=f"New confidence ({new_confidence:.2f}) > old trust ({old_trust:.2f}).",
            )

        # Recent correction (small gap)
        if temporal_gap_days < 1:
            return SupersessionResult(
                should_supersede=True,
                reason="Immediate correction — user is updating in real-time.",
            )

        # Large gap + factual = temporal progression
        if temporal_gap_days > 30 and old_type == "fact":
            return SupersessionResult(
                should_supersede=True,
                reason=f"Factual update after {temporal_gap_days:.0f} days.",
            )

        # Default: supersede if gap is reasonable
        if temporal_gap_days > 0:
            return SupersessionResult(
                should_supersede=True,
                reason="Resolvable contradiction — newer info takes precedence.",
            )

    return SupersessionResult(
        should_supersede=False,
        reason="Insufficient evidence for supersession.",
    )


# ---------------------------------------------------------------------------
# Integration: score and rank memories for retrieval
# ---------------------------------------------------------------------------

def rank_memories(
    query_similarity: Dict[str, float],  # memory_id -> cosine similarity
    memory_metadata: Dict[str, dict],     # memory_id -> {trust, confidence, created_at, type, ...}
    now: Optional[float] = None,
) -> List[Tuple[str, float, dict]]:
    """Rank memories by full retrieval score.

    Returns sorted list of (memory_id, score, debug_info).
    """
    now = now or time.time()
    results = []

    for mem_id, sim in query_similarity.items():
        meta = memory_metadata.get(mem_id, {})
        trust = meta.get('trust', 0.5)
        confidence = meta.get('confidence', 0.5)
        created_at = meta.get('created_at', now)
        mem_type = meta.get('memory_type', 'belief')
        valid_until = meta.get('valid_until')

        age_days = (now - created_at) / 86400.0

        # Check hard expiry
        fresh = compute_freshness(
            created_at, mem_type, now=now,
            valid_until=valid_until,
        )
        if fresh == 0.0:
            continue  # expired, skip

        score = retrieval_score(sim, trust, confidence, age_days, mem_type)

        debug = {
            'similarity': sim,
            'trust': trust,
            'confidence': confidence,
            'age_days': age_days,
            'memory_type': mem_type,
            'recency_weight': recency_weight(age_days, mem_type),
            'freshness': fresh,
            'final_score': score,
        }
        results.append((mem_id, score, debug))

    results.sort(key=lambda x: x[1], reverse=True)
    return results


# ---------------------------------------------------------------------------
# Test
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    print("=" * 70)
    print("TEMPORAL GOVERNANCE — Phase 1 Test")
    print("=" * 70)

    now = time.time()

    # --- Freshness tests ---
    print("\n  --- FRESHNESS BY TYPE AND AGE ---")
    print(f"  {'Type':<12} {'1 day':>8} {'7 days':>8} {'30 days':>8} {'90 days':>8} {'365 days':>8}")
    print(f"  {'-'*12} {'-'*8} {'-'*8} {'-'*8} {'-'*8} {'-'*8}")

    for mem_type in ["fact", "preference", "event", "belief", "identity"]:
        vals = []
        for days in [1, 7, 30, 90, 365]:
            ts = now - days * 86400
            f = compute_freshness(ts, mem_type, now=now)
            vals.append(f"{f:.3f}")
        print(f"  {mem_type:<12} {'  '.join(f'{v:>6}' for v in vals)}")

    # --- Event hard expiry ---
    print("\n  --- EVENT HARD EXPIRY ---")
    event_past = now - 86400 * 2  # 2 days ago
    event_future = now + 86400 * 2  # 2 days from now
    f_expired = compute_freshness(now - 86400 * 5, "event", now=now, valid_until=event_past)
    f_active = compute_freshness(now - 86400 * 1, "event", now=now, valid_until=event_future)
    print(f"  Expired event (valid_until 2 days ago): freshness={f_expired:.3f}")
    print(f"  Active event (valid_until 2 days out):  freshness={f_active:.3f}")

    # --- Recency weights ---
    print("\n  --- RECENCY WEIGHT CURVES ---")
    print(f"  {'Type':<12} {'1 day':>8} {'7 days':>8} {'30 days':>8} {'90 days':>8} {'365 days':>8}")
    print(f"  {'-'*12} {'-'*8} {'-'*8} {'-'*8} {'-'*8} {'-'*8}")

    for mem_type in ["fact", "preference", "event", "belief", "identity"]:
        vals = []
        for days in [1, 7, 30, 90, 365]:
            w = recency_weight(days, mem_type)
            vals.append(f"{w:.3f}")
        print(f"  {mem_type:<12} {'  '.join(f'{v:>6}' for v in vals)}")

    # --- Retrieval scoring ---
    print("\n  --- RETRIEVAL SCORE COMPARISON ---")
    print("  Same similarity (0.85), different types and ages:\n")

    test_memories = [
        ("Birthday is March 5", "fact", 0.85, 0.9, 365),
        ("Prefers dark mode", "preference", 0.85, 0.8, 60),
        ("Meeting at 3pm Tuesday", "event", 0.85, 0.9, 3),
        ("Loves photography", "belief", 0.85, 0.8, 90),
        ("I'm a builder", "identity", 0.85, 0.9, 180),
        ("Meeting at 3pm Tuesday (expired)", "event", 0.85, 0.9, 10),
    ]

    for text, mtype, trust, conf, age_days in test_memories:
        score = retrieval_score(0.85, trust, conf, age_days, mtype)
        rw = recency_weight(age_days, mtype)
        print(f"    score={score:.3f} | rw={rw:.3f} | {age_days:>3}d | {mtype:<11} | \"{text}\"")

    # --- Supersession logic ---
    print("\n  --- SUPERSESSION TESTS ---")

    sup_tests = [
        ("I work at Google", "I work at Microsoft", "fact", "fact",
         0.7, 0.9, 180, "resolvable"),
        ("I love my job", "My job is killing me", "belief", "belief",
         0.7, 0.8, 14, "held"),
        ("I used to love React", "Now I prefer Vue", "preference", "preference",
         0.6, 0.8, 90, "evolving"),
        ("Meeting Monday 3pm", "Meeting Tuesday 2pm", "event", "event",
         0.8, 0.9, 1, "resolvable"),
        ("I'm disciplined at work", "At home I'm lazy", "identity", "identity",
         0.7, 0.8, 1, "contextual"),
    ]

    for old_t, new_t, old_type, new_type, old_trust, new_conf, gap, disp in sup_tests:
        result = check_supersession(old_t, new_t, old_type, new_type,
                                     old_trust, new_conf, gap, disp)
        symbol = ">>>" if result.should_supersede else "==="
        print(f"    [{disp:>11}] {symbol} supersede={result.should_supersede} "
              f"| old_becomes={result.old_becomes}")
        print(f"      \"{old_t}\"  vs  \"{new_t}\"")
        print(f"      Reason: {result.reason}")
        print()

    # --- Full ranking test ---
    print("  --- FULL RANKING TEST ---")
    print("  Query: 'What do I do for work?' (all memories sim=0.85)\n")

    similarities = {
        "mem_birthday": 0.30,
        "mem_employer": 0.85,
        "mem_dark_mode": 0.20,
        "mem_meeting": 0.40,
        "mem_photography": 0.35,
        "mem_builder": 0.70,
        "mem_expired_event": 0.40,
    }

    metadata = {
        "mem_birthday": {"trust": 0.9, "confidence": 0.95, "created_at": now - 365*86400, "memory_type": "fact"},
        "mem_employer": {"trust": 0.8, "confidence": 0.9, "created_at": now - 30*86400, "memory_type": "fact"},
        "mem_dark_mode": {"trust": 0.7, "confidence": 0.8, "created_at": now - 60*86400, "memory_type": "preference"},
        "mem_meeting": {"trust": 0.9, "confidence": 0.9, "created_at": now - 1*86400, "memory_type": "event"},
        "mem_photography": {"trust": 0.8, "confidence": 0.8, "created_at": now - 90*86400, "memory_type": "belief"},
        "mem_builder": {"trust": 0.85, "confidence": 0.9, "created_at": now - 180*86400, "memory_type": "identity"},
        "mem_expired_event": {"trust": 0.9, "confidence": 0.9, "created_at": now - 10*86400,
                               "memory_type": "event", "valid_until": now - 86400 * 3},
    }

    ranked = rank_memories(similarities, metadata, now=now)
    labels = {
        "mem_birthday": "Birthday is March 5",
        "mem_employer": "I work at Microsoft",
        "mem_dark_mode": "Prefers dark mode",
        "mem_meeting": "Meeting at 3pm Tuesday",
        "mem_photography": "Loves photography",
        "mem_builder": "I'm a builder",
        "mem_expired_event": "Old meeting (expired)",
    }

    for mem_id, score, debug in ranked:
        label = labels.get(mem_id, mem_id)
        print(f"    score={score:.3f} | sim={debug['similarity']:.2f} "
              f"rw={debug['recency_weight']:.2f} trust={debug['trust']:.2f} "
              f"| {debug['memory_type']:<11} | \"{label}\"")

    if "mem_expired_event" not in [r[0] for r in ranked]:
        print(f"\n    (expired event correctly filtered out)")

    print(f"\n{'='*70}")
    print("TEMPORAL GOVERNANCE TEST COMPLETE")
    print(f"{'='*70}")
