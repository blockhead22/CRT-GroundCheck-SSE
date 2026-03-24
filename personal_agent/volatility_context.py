"""
Volatility-Gated Context Window — Sprint 10

Dynamic context budget allocation based on memory uncertainty/volatility.

Core idea: volatile memories (recently contradicted, low-trust, changing)
get MORE context budget — they need nuance preserved. Stable high-trust
facts can be aggressively compressed to slot=value pairs.

Uses the existing V(t) formula from memory_compression.py:
  V(t) = 0.4*drift + 0.35*contradiction_density + 0.25*fidelity_loss

No new database tables — all computed on-the-fly from existing fields.
"""

from __future__ import annotations

import logging
import re
import time
from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Budget defaults (chars)
DEFAULT_MEMORY_BUDGET = 6000
MAX_PROACTIVE_ALERTS = 2
PROACTIVE_ALERT_BUDGET = 300
RECENT_CHANGE_DAYS = 7

# Volatility thresholds
VOLATILE_THRESHOLD = 0.4       # V(t) above this = volatile
HIGH_VOLATILE_THRESHOLD = 0.6  # force "full" allocation
LOW_VOLATILE_THRESHOLD = 0.15  # safe to compress aggressively
HIGH_TRUST_THRESHOLD = 0.85    # stable if also low-volatile

# Priority boost for volatile memories
VOLATILITY_BOOST = 1.5         # priority = relevance * (1 + VOLATILITY_BOOST * V)


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class MemoryAllocation:
    """Per-memory context allocation decision."""
    memory_id: str
    text: str                          # full or compressed text
    original_text: str                 # always the full text
    trust: float
    volatility: float
    relevance: float                   # retrieval score
    allocated_chars: int
    compression_applied: str           # "full" | "summary" | "slot_only"
    recently_changed: bool
    priority: float                    # computed priority score

    def to_dict(self) -> Dict:
        return {
            "memory_id": self.memory_id,
            "trust": round(self.trust, 3),
            "volatility": round(self.volatility, 3),
            "relevance": round(self.relevance, 3),
            "allocated_chars": self.allocated_chars,
            "compression_applied": self.compression_applied,
            "recently_changed": self.recently_changed,
            "priority": round(self.priority, 3),
        }


@dataclass
class ContextBudget:
    """Complete context budget allocation for a query."""
    total_chars: int
    available_chars: int               # total - fixed overhead
    used_chars: int
    allocations: List[MemoryAllocation]
    volatile_proactive: List[str]      # proactive alerts

    def to_dict(self) -> Dict:
        return {
            "total_chars": self.total_chars,
            "available_chars": self.available_chars,
            "used_chars": self.used_chars,
            "allocation_count": len(self.allocations),
            "allocations": [a.to_dict() for a in self.allocations],
            "volatile_proactive": self.volatile_proactive,
            "compression_breakdown": self._compression_breakdown(),
        }

    def _compression_breakdown(self) -> Dict[str, int]:
        breakdown: Dict[str, int] = {"full": 0, "summary": 0, "slot_only": 0}
        for a in self.allocations:
            breakdown[a.compression_applied] = breakdown.get(a.compression_applied, 0) + 1
        return breakdown


@dataclass
class VolatilityProfile:
    """Volatility profile for a single memory."""
    memory_id: str
    volatility: float
    trust: float
    compression_tier: int
    contradiction_count: int
    last_accessed: float
    days_since_change: Optional[float]

    def to_dict(self) -> Dict:
        return asdict(self)


# ---------------------------------------------------------------------------
# Volatility computation
# ---------------------------------------------------------------------------

def compute_memory_volatility(
    memory,
    ledger=None,
    memory_system=None,
) -> float:
    """Compute V(t) for a memory item.

    For memories with compression data, reuses memory_compression.compute_volatility().
    For memories without, uses a simplified formula based on available fields.
    """
    # Try full formula if compression data exists
    compressed_vec = getattr(memory, "compressed_vector", None)
    cogni_seed_dict = getattr(memory, "cogni_seed", None)

    if compressed_vec is not None and cogni_seed_dict is not None:
        try:
            from .memory_compression import compute_volatility, CogniSeed
            seed = CogniSeed.from_dict(cogni_seed_dict) if isinstance(cogni_seed_dict, dict) else None
            if seed is not None:
                return compute_volatility(
                    original_vector=getattr(memory, "vector", None),
                    compressed_vector=compressed_vec,
                    cogni_seed=seed,
                    contradiction_count=getattr(memory, "contradiction_count", 0),
                    access_count=max(getattr(memory, "access_count", 1), 1),
                )
        except Exception:
            pass

    # Simplified formula for memories without compression data
    trust = getattr(memory, "trust", 0.5)
    contra_count = getattr(memory, "contradiction_count", 0)
    access_count = max(getattr(memory, "access_count", 1), 1)

    # Check if memory has open contradictions in ledger
    has_open_contradiction = False
    if ledger is not None:
        try:
            mem_id = getattr(memory, "memory_id", "")
            open_contras = ledger.get_open_contradictions(limit=50)
            for c in open_contras:
                if getattr(c, "old_memory_id", "") == mem_id or getattr(c, "new_memory_id", "") == mem_id:
                    has_open_contradiction = True
                    break
        except Exception:
            pass

    # Check recency (recently stored/modified = more volatile)
    timestamp = getattr(memory, "timestamp", 0)
    age_days = (time.time() - timestamp) / 86400.0
    recency_factor = 1.0 if age_days < RECENT_CHANGE_DAYS else 0.0

    # V(t) = 0.35*contradiction_signal + 0.4*(1-trust) + 0.25*recency
    contradiction_signal = min(1.0, (contra_count / access_count) + (0.5 if has_open_contradiction else 0.0))
    trust_instability = 1.0 - trust

    v = 0.35 * contradiction_signal + 0.40 * trust_instability + 0.25 * recency_factor
    return float(min(1.0, max(0.0, v)))


def get_volatility_profile(
    memory,
    ledger=None,
    memory_system=None,
) -> VolatilityProfile:
    """Build a full volatility profile for a single memory."""
    vol = compute_memory_volatility(memory, ledger, memory_system)

    timestamp = getattr(memory, "timestamp", 0)
    age_days = (time.time() - timestamp) / 86400.0

    return VolatilityProfile(
        memory_id=getattr(memory, "memory_id", ""),
        volatility=vol,
        trust=getattr(memory, "trust", 0.5),
        compression_tier=getattr(memory, "compression_tier", 2),
        contradiction_count=getattr(memory, "contradiction_count", 0),
        last_accessed=timestamp,
        days_since_change=age_days if age_days < 365 else None,
    )


# ---------------------------------------------------------------------------
# Memory compression for context
# ---------------------------------------------------------------------------

def compress_memory_for_context(memory, level: str) -> str:
    """Compress a memory's text for context injection.

    Levels:
        "full":      raw text as-is
        "summary":   first sentence + slot=value pairs
        "slot_only": only extracted slot=value pairs
    """
    text = getattr(memory, "text", "")
    if not text:
        return ""

    if level == "full":
        return text

    # Extract slot=value pairs
    slot_pairs = _extract_slot_pairs(text)

    if level == "slot_only":
        if slot_pairs:
            return "; ".join(f"{s}={v}" for s, v in slot_pairs)
        # If no slots extractable, return first 60 chars as fallback
        return text[:60].rstrip() + ("..." if len(text) > 60 else "")

    if level == "summary":
        # First sentence
        first_sentence = _first_sentence(text)
        if slot_pairs:
            slots_str = "; ".join(f"{s}={v}" for s, v in slot_pairs)
            # Avoid duplication if first sentence IS the slot pair
            if len(first_sentence) > 10 and slots_str not in first_sentence:
                return f"{first_sentence} [{slots_str}]"
            return first_sentence
        return first_sentence

    return text  # unknown level, return full


def _extract_slot_pairs(text: str) -> List[Tuple[str, str]]:
    """Extract key=value facts from memory text."""
    try:
        from .fact_slots import extract_fact_slots
        slots = extract_fact_slots(text)
        return [(s, v) for s, v in slots if v]
    except Exception:
        return []


def _first_sentence(text: str) -> str:
    """Extract the first sentence from text."""
    # Split on sentence boundaries
    match = re.match(r"^(.+?[.!?])\s", text)
    if match:
        return match.group(1)
    # No sentence boundary found, take first 120 chars
    if len(text) > 120:
        return text[:120].rstrip() + "..."
    return text


# ---------------------------------------------------------------------------
# Budget allocation
# ---------------------------------------------------------------------------

def allocate_context_budget(
    query: str,
    retrieved: List[Tuple[Any, float]],
    total_budget: int = DEFAULT_MEMORY_BUDGET,
    ledger=None,
    memory_system=None,
) -> ContextBudget:
    """Allocate context budget across retrieved memories based on volatility.

    High-volatility memories get full text (they need nuance).
    Stable high-trust memories get compressed to slot=value pairs.

    Args:
        query: User's query
        retrieved: List of (MemoryItem, retrieval_score) tuples
        total_budget: Total character budget for memory section
        ledger: ContradictionLedger instance
        memory_system: CRTMemorySystem instance

    Returns:
        ContextBudget with per-memory allocations
    """
    if not retrieved:
        return ContextBudget(
            total_chars=total_budget,
            available_chars=total_budget,
            used_chars=0,
            allocations=[],
            volatile_proactive=[],
        )

    # Step 1: Compute volatility and priority for each memory
    scored: List[Tuple[Any, float, float, float]] = []  # (mem, score, vol, priority)
    for mem, score in retrieved:
        vol = compute_memory_volatility(mem, ledger, memory_system)
        priority = score * (1.0 + VOLATILITY_BOOST * vol)
        scored.append((mem, score, vol, priority))

    # Step 2: Sort by priority descending
    scored.sort(key=lambda x: x[3], reverse=True)

    # Step 3: Assign compression tiers
    n = len(scored)
    allocations: List[MemoryAllocation] = []

    for i, (mem, score, vol, priority) in enumerate(scored):
        trust = getattr(mem, "trust", 0.5)
        timestamp = getattr(mem, "timestamp", 0)
        age_days = (time.time() - timestamp) / 86400.0
        recently_changed = age_days < RECENT_CHANGE_DAYS

        # Determine compression level
        if vol >= HIGH_VOLATILE_THRESHOLD or (trust < 0.4 and vol > 0.3):
            # Always preserve volatile/uncertain memories in full
            level = "full"
        elif trust >= HIGH_TRUST_THRESHOLD and vol < LOW_VOLATILE_THRESHOLD:
            # Stable high-trust: aggressively compress
            level = "slot_only"
        elif i < n * 0.3:
            level = "full"
        elif i < n * 0.7:
            level = "summary"
        else:
            level = "slot_only"

        compressed_text = compress_memory_for_context(mem, level)
        original_text = getattr(mem, "text", "")

        allocations.append(MemoryAllocation(
            memory_id=getattr(mem, "memory_id", ""),
            text=compressed_text,
            original_text=original_text,
            trust=trust,
            volatility=vol,
            relevance=score,
            allocated_chars=len(compressed_text),
            compression_applied=level,
            recently_changed=recently_changed,
            priority=priority,
        ))

    # Step 4: Budget overflow — demote lowest-priority allocations
    alert_budget = PROACTIVE_ALERT_BUDGET
    available = total_budget - alert_budget
    total_used = sum(a.allocated_chars for a in allocations)

    _DEMOTION_ORDER = {"full": "summary", "summary": "slot_only"}

    while total_used > available:
        demoted = False
        # Find lowest-priority allocation that can be demoted
        for a in reversed(allocations):
            if a.compression_applied in _DEMOTION_ORDER:
                new_level = _DEMOTION_ORDER[a.compression_applied]
                # Find the original memory to re-compress
                for mem, score in retrieved:
                    if getattr(mem, "memory_id", "") == a.memory_id:
                        a.text = compress_memory_for_context(mem, new_level)
                        a.allocated_chars = len(a.text)
                        a.compression_applied = new_level
                        demoted = True
                        break
                if demoted:
                    break
        if not demoted:
            break  # Nothing left to demote
        total_used = sum(a.allocated_chars for a in allocations)

    # Step 5: Detect proactive alerts
    proactive = detect_proactive_alerts(
        [mem for mem, _score in retrieved],
        ledger,
    )

    return ContextBudget(
        total_chars=total_budget,
        available_chars=available,
        used_chars=total_used,
        allocations=allocations,
        volatile_proactive=proactive,
    )


# ---------------------------------------------------------------------------
# Proactive alerts
# ---------------------------------------------------------------------------

def detect_proactive_alerts(
    memories: list,
    ledger=None,
) -> List[str]:
    """Detect recently changed beliefs that should be proactively surfaced.

    Scans for resolved contradictions in the last RECENT_CHANGE_DAYS days.
    Returns natural-language alerts like:
      "You recently changed your mind about [slot]: was [old], now [new]"
    """
    if ledger is None:
        return []

    alerts: List[str] = []
    cutoff = time.time() - (RECENT_CHANGE_DAYS * 86400)

    try:
        # Get recently resolved contradictions
        conn = ledger._get_connection()
        cursor = conn.cursor()

        # Check what columns exist
        cols = {row[1] for row in cursor.execute("PRAGMA table_info(contradictions)").fetchall()}

        if "resolved_at" in cols and "affects_slots" in cols:
            cursor.execute(
                """SELECT affects_slots, claim_a_text, claim_b_text, resolved_at, resolution_method
                   FROM contradictions
                   WHERE status IN ('resolved', 'accepted')
                     AND resolved_at > ?
                   ORDER BY resolved_at DESC
                   LIMIT 5""",
                (cutoff,),
            )
            rows = cursor.fetchall()

            for row in rows:
                slots_str = row[0] or ""
                old_claim = row[1] or ""
                new_claim = row[2] or ""

                if old_claim and new_claim:
                    slot_label = slots_str.split(",")[0] if slots_str else "something"
                    slot_label = slot_label.replace("_", " ")
                    alert = (
                        f"You recently changed your mind about {slot_label}: "
                        f"was \"{old_claim[:60]}\" -> now \"{new_claim[:60]}\""
                    )
                    alerts.append(alert)

        conn.close()
    except Exception as e:
        logger.warning("[VOLATILITY] Proactive alert scan failed: %s", e)

    return alerts[:MAX_PROACTIVE_ALERTS]


# ---------------------------------------------------------------------------
# Volatility-aware re-ranking
# ---------------------------------------------------------------------------

def rerank_by_volatility(
    retrieved: List[Tuple[Any, float]],
    ledger=None,
    memory_system=None,
    boost_factor: float = 0.5,
) -> List[Tuple[Any, float]]:
    """Re-rank retrieved memories by boosting volatile ones.

    Volatile memories get a score boost so they surface higher in retrieval.
    This is a lightweight hook — the full budget allocation happens downstream.

    Args:
        retrieved: List of (MemoryItem, score) tuples
        ledger: ContradictionLedger
        memory_system: CRTMemorySystem
        boost_factor: How much volatility boosts score (default 0.5)

    Returns:
        Re-ranked list of (MemoryItem, adjusted_score) tuples
    """
    reranked = []
    for mem, score in retrieved:
        vol = compute_memory_volatility(mem, ledger, memory_system)
        adjusted = score * (1.0 + boost_factor * vol)
        reranked.append((mem, adjusted))

    reranked.sort(key=lambda x: x[1], reverse=True)
    return reranked
