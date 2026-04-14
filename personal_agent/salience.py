"""
Salience-Gated Softmax Re-Ranking
==================================

Computes salience scores for contradictions and memories, then applies
softmax with temperature to produce exponentially-stretched rankings.

Formula:
    S = α·V + β·D + γ·R + δ·C

    V = volatility (how contested this slot is)
    D = drift (measured semantic distance between conflicting memories)
    R = recency (newer = more salient)
    C = cascade weight (identity slots > preference slots)

Softmax with temperature:
    priority_i = exp(S_i / T) / Σ_j exp(S_j / T)

    Low T (0.3)  = sharp ranking — one winner dominates
    Mid T (1.0)  = standard softmax
    High T (2.0) = soft ranking — spread across candidates

No resolution performed — ranking only.

Lab 11 validation: 4/4 pass (Adnan Syed), 3/3 pass (live data).
"""

import math
import time
from typing import Any, Dict, List, Optional, Sequence, Tuple, TypeVar

import numpy as np

# ── Tuned weights from Lab 11 ──────────────────────────────────────
ALPHA = 0.30   # volatility weight
BETA = 0.25    # drift weight
GAMMA = 0.15   # recency weight
DELTA = 0.30   # cascade / slot importance weight

# ── Cascade weight map ─────────────────────────────────────────────
# Identity-critical slots get higher weight than preferences.
# This means a name contradiction outranks a coffee preference change.
CASCADE_WEIGHTS: Dict[str, float] = {
    "name": 1.0,
    "age": 0.9,
    "spouse": 0.85,
    "employer": 0.8,
    "location": 0.7,
    "title": 0.7,
    "assistant_name": 0.6,
    "programming_language": 0.4,
    "favorite_color": 0.3,
    "coffee": 0.2,
}

DEFAULT_CASCADE_WEIGHT = 0.5


def softmax(scores: np.ndarray, temperature: float = 1.0) -> np.ndarray:
    """Softmax with temperature. Lower T = sharper, higher T = softer."""
    if temperature <= 0:
        temperature = 1.0
    scaled = scores / temperature
    shifted = scaled - np.max(scaled)  # numerical stability
    exp_scores = np.exp(shifted)
    return exp_scores / np.sum(exp_scores)


def compute_contradiction_salience(
    drift_mean: float,
    slot: str,
    slot_open_count: int = 1,
    timestamp: float = 0.0,
    t_now: Optional[float] = None,
) -> float:
    """
    Compute salience score for a single contradiction.

    Args:
        drift_mean: Semantic drift between the two conflicting memories (0-1+).
        slot: The fact slot affected (e.g., "name", "employer").
        slot_open_count: How many open contradictions share this slot.
        timestamp: When the contradiction was detected.
        t_now: Current time (defaults to time.time()).

    Returns:
        Salience score (float, higher = more salient).
    """
    if t_now is None:
        t_now = time.time()

    # V: Volatility — how contested is this slot?
    V = min(1.0, slot_open_count / 6.0)

    # D: Drift — directly from the contradiction detector
    D = min(1.0, drift_mean or 0.0)

    # R: Recency — newer contradictions are more salient
    age_hours = max(0.0, (t_now - (timestamp or t_now)) / 3600.0)
    R = math.exp(-age_hours / (24.0 * 30))  # ~30-day half-life

    # C: Cascade weight — identity slots matter more than preferences
    C = CASCADE_WEIGHTS.get(slot, DEFAULT_CASCADE_WEIGHT)

    return ALPHA * V + BETA * D + GAMMA * R + DELTA * C


T = TypeVar("T")


def softmax_rerank(
    items: Sequence[T],
    scores: np.ndarray,
    temperature: float = 1.0,
) -> List[Tuple[T, float]]:
    """
    Apply softmax with temperature to scores and return items sorted
    by priority (descending).

    Args:
        items: Sequence of items to rank.
        scores: Raw salience scores (same length as items).
        temperature: Softmax temperature (lower = sharper).

    Returns:
        List of (item, priority) tuples sorted by priority descending.
    """
    if len(items) == 0:
        return []
    if len(items) == 1:
        return [(items[0], 1.0)]

    priorities = softmax(scores, temperature=temperature)
    ranked = sorted(zip(items, priorities), key=lambda x: x[1], reverse=True)
    return ranked


def classify_query_temperature(query: str) -> float:
    """
    Auto-assign temperature based on query characteristics.

    Factual queries get sharp ranking (T=0.3).
    Reflective queries get soft ranking (T=2.0).
    Contradiction queries get medium ranking (T=1.0).
    """
    q = query.lower()

    contradiction_signals = [
        "conflict", "contradict", "both sides", "tension",
        "disagree", "inconsistent", "opposing",
    ]
    if any(s in q for s in contradiction_signals):
        return 1.0

    factual_signals = [
        "what is", "who is", "where was", "when did",
        "what was", "which", "how many",
    ]
    if any(s in q for s in factual_signals):
        return 0.3

    reflective_signals = [
        "strongest", "most important", "what matters",
        "biggest", "main", "key", "significant",
        "doubts", "concerns", "problems",
    ]
    if any(s in q for s in reflective_signals):
        return 2.0

    return 1.0  # default: standard softmax
