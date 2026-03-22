"""Adaptive semantic memory compression with volatility-triggered promotion.

Core concepts (from Nick's whiteboard math):
- V(t) = α·D(t) + β·C(t) + γ·F(t)  — Semantic Volatility Score
- H(t) = H₀ · e^(-s·V(t))           — Throttle function
- C_w(t+1) = C_w(t) + H(t) · F      — Collapse weighting

Tier system:
- Tier 0 (hot):  10D  — routine facts, cheap retrieval
- Tier 1 (warm): 64D  — promoted when volatility spikes
- Tier 2 (cold): full — identity, medical, high-contradiction facts

Cogni seed: compact statistical summary (~16 floats) that guides
reconstruction from low-dim back to higher-dim.
"""

from __future__ import annotations

import math
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

import numpy as np

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

TIER_DIMS = {0: 10, 1: 64, 2: 384}  # tier → dimensionality
VOLATILITY_ALPHA = 0.4   # drift weight
VOLATILITY_BETA = 0.35   # contradiction weight
VOLATILITY_GAMMA = 0.25  # fidelity loss weight
THROTTLE_H0 = 1.0        # base throttle
THROTTLE_S = 3.0          # throttle sensitivity
PROMOTION_THRESHOLD = 0.6  # V(t) above this → promote
DEMOTION_THRESHOLD = 0.1   # V(t) below this for N cycles → demote
DEMOTION_STABLE_CYCLES = 10  # how many low-volatility cycles before demotion


# ---------------------------------------------------------------------------
# Cogni Seed — compact reconstruction guide
# ---------------------------------------------------------------------------

@dataclass
class CogniSeed:
    """Statistical summary of how a vector was folded down.

    NOT a full reconstruction key — just enough metadata for a
    reconstructor model to approximate the unfolding.
    """
    original_dim: int
    target_dim: int
    mean_contribution: np.ndarray       # mean value per target dim
    variance_contribution: np.ndarray   # variance per target dim
    dominant_indices: np.ndarray        # which original dims contributed most
    polarity_bias: float                # overall positive/negative skew
    fold_timestamp: float = 0.0

    def to_dict(self) -> dict:
        return {
            "original_dim": self.original_dim,
            "target_dim": self.target_dim,
            "mean": self.mean_contribution.tolist(),
            "variance": self.variance_contribution.tolist(),
            "dominant": self.dominant_indices.tolist(),
            "polarity": self.polarity_bias,
            "ts": self.fold_timestamp,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "CogniSeed":
        return cls(
            original_dim=d["original_dim"],
            target_dim=d["target_dim"],
            mean_contribution=np.array(d["mean"]),
            variance_contribution=np.array(d["variance"]),
            dominant_indices=np.array(d["dominant"]),
            polarity_bias=d["polarity"],
            fold_timestamp=d.get("ts", 0.0),
        )

    @property
    def byte_size(self) -> int:
        """Approximate storage cost in bytes."""
        # 2 arrays of target_dim floats + 1 array of target_dim ints + 2 scalars
        return (self.target_dim * 4 * 2) + (self.target_dim * 4) + 16


# ---------------------------------------------------------------------------
# Compressed Memory Entry
# ---------------------------------------------------------------------------

@dataclass
class CompressedMemory:
    """A memory stored at a specific compression tier."""
    memory_id: str
    text: str
    vector: np.ndarray           # current compressed vector
    tier: int = 0                # 0=hot(10D), 1=warm(64D), 2=cold(full)
    trust: float = 0.7
    cogni_seed: Optional[CogniSeed] = None
    original_vector: Optional[np.ndarray] = None  # kept only for testing/validation

    # Volatility tracking
    volatility_history: List[float] = field(default_factory=list)
    contradiction_count: int = 0
    access_count: int = 0
    last_accessed: float = 0.0
    created_at: float = field(default_factory=time.time)
    stable_cycles: int = 0      # consecutive cycles with low volatility


# ---------------------------------------------------------------------------
# Folding — compress a vector to a target dimensionality
# ---------------------------------------------------------------------------

def fold_vector(
    vector: np.ndarray,
    target_dim: int,
    projection_matrix: Optional[np.ndarray] = None,
) -> Tuple[np.ndarray, CogniSeed]:
    """Fold a high-dimensional vector down to target_dim.

    Uses PCA-style projection. Returns the compressed vector + a CogniSeed
    for approximate reconstruction.

    Args:
        vector: source vector (any dimensionality)
        target_dim: target dimensionality (e.g., 10)
        projection_matrix: optional pre-computed projection matrix (dim × target_dim)

    Returns:
        (compressed_vector, cogni_seed)
    """
    vec = np.array(vector, dtype=np.float32).flatten()
    original_dim = len(vec)

    if original_dim <= target_dim:
        # Already small enough — pad with zeros
        padded = np.zeros(target_dim, dtype=np.float32)
        padded[:original_dim] = vec
        seed = CogniSeed(
            original_dim=original_dim,
            target_dim=target_dim,
            mean_contribution=padded,
            variance_contribution=np.zeros(target_dim, dtype=np.float32),
            dominant_indices=np.arange(min(original_dim, target_dim)),
            polarity_bias=float(np.mean(vec)),
            fold_timestamp=time.time(),
        )
        return padded, seed

    if projection_matrix is not None:
        compressed = vec @ projection_matrix
    else:
        # Simple chunked averaging as default folding strategy
        chunk_size = original_dim // target_dim
        remainder = original_dim % target_dim
        compressed = np.zeros(target_dim, dtype=np.float32)

        for i in range(target_dim):
            start = i * chunk_size + min(i, remainder)
            end = (i + 1) * chunk_size + min(i + 1, remainder)
            chunk = vec[start:end]
            compressed[i] = np.mean(chunk)

    # Build cogni seed
    # Mean contribution per target dimension
    mean_contrib = compressed.copy()
    # Variance: how much each chunk varied internally
    var_contrib = np.zeros(target_dim, dtype=np.float32)
    chunk_size = original_dim // target_dim
    remainder = original_dim % target_dim
    for i in range(target_dim):
        start = i * chunk_size + min(i, remainder)
        end = (i + 1) * chunk_size + min(i + 1, remainder)
        chunk = vec[start:end]
        var_contrib[i] = np.var(chunk)

    # Dominant indices: which target dims carry the most signal
    dominant = np.argsort(np.abs(compressed))[::-1][:target_dim]

    seed = CogniSeed(
        original_dim=original_dim,
        target_dim=target_dim,
        mean_contribution=mean_contrib,
        variance_contribution=var_contrib,
        dominant_indices=dominant,
        polarity_bias=float(np.mean(vec)),
        fold_timestamp=time.time(),
    )

    return compressed, seed


# ---------------------------------------------------------------------------
# Unfolding — approximate reconstruction from compressed + seed
# ---------------------------------------------------------------------------

def unfold_vector(
    compressed: np.ndarray,
    seed: CogniSeed,
) -> np.ndarray:
    """Approximate reconstruction of the original vector from compressed + seed.

    This is NOT lossless — it's a best-effort reconstruction using the
    statistical hints in the cogni seed.
    """
    target_dim = seed.original_dim
    source_dim = seed.target_dim
    result = np.zeros(target_dim, dtype=np.float32)

    chunk_size = target_dim // source_dim
    remainder = target_dim % source_dim

    for i in range(source_dim):
        start = i * chunk_size + min(i, remainder)
        end = (i + 1) * chunk_size + min(i + 1, remainder)
        chunk_len = end - start

        # Base: spread the compressed value across the chunk
        base_val = compressed[i]
        # Add variance-guided noise to approximate original distribution
        variance = seed.variance_contribution[i]
        if variance > 0 and chunk_len > 1:
            # Deterministic spread based on variance (not random — reproducible)
            spread = np.linspace(-1, 1, chunk_len) * math.sqrt(variance)
            result[start:end] = base_val + spread
        else:
            result[start:end] = base_val

    return result


# ---------------------------------------------------------------------------
# Volatility scoring
# ---------------------------------------------------------------------------

def compute_volatility(
    memory: CompressedMemory,
    current_vector: Optional[np.ndarray] = None,
) -> float:
    """Compute semantic volatility V(t) for a memory.

    V(t) = α·D(t) + β·C(t) + γ·F(t)
    - D(t): drift — how much the vector has shifted from its original
    - C(t): contradiction density — contradictions per access
    - F(t): fidelity loss — reconstruction error at current tier
    """
    # D(t): drift score
    drift = 0.0
    if current_vector is not None and memory.original_vector is not None:
        original_norm = np.linalg.norm(memory.original_vector)
        if original_norm > 0:
            # Cosine distance between current compressed (unfolded) and original
            reconstructed = unfold_vector(memory.vector, memory.cogni_seed) if memory.cogni_seed else memory.vector
            if len(reconstructed) == len(memory.original_vector):
                cos_sim = np.dot(reconstructed, memory.original_vector) / (
                    np.linalg.norm(reconstructed) * original_norm + 1e-8
                )
                drift = 1.0 - max(0.0, cos_sim)

    # C(t): contradiction density
    contradiction_density = (
        memory.contradiction_count / max(memory.access_count, 1)
    )

    # F(t): fidelity loss — reconstruction error
    fidelity_loss = 0.0
    if memory.cogni_seed and memory.original_vector is not None:
        reconstructed = unfold_vector(memory.vector, memory.cogni_seed)
        if len(reconstructed) == len(memory.original_vector):
            mse = np.mean((reconstructed - memory.original_vector) ** 2)
            fidelity_loss = min(1.0, mse * 10)  # scale to 0-1

    v = (
        VOLATILITY_ALPHA * drift
        + VOLATILITY_BETA * contradiction_density
        + VOLATILITY_GAMMA * fidelity_loss
    )
    return float(min(1.0, v))


def compute_throttle(volatility: float) -> float:
    """Throttle function H(t) = H₀ · e^(-s · V(t))

    High volatility → low throttle → stop compressing, promote instead.
    Low volatility → high throttle → safe to compress further.
    """
    return THROTTLE_H0 * math.exp(-THROTTLE_S * volatility)


# ---------------------------------------------------------------------------
# Tier promotion / demotion
# ---------------------------------------------------------------------------

def should_promote(memory: CompressedMemory, volatility: float) -> bool:
    """Should this memory be promoted to a higher-fidelity tier?"""
    if memory.tier >= 2:
        return False  # already at max
    if volatility >= PROMOTION_THRESHOLD:
        return True
    # High trust + any volatility → promote proactively
    if memory.trust >= 0.9 and volatility >= PROMOTION_THRESHOLD * 0.5:
        return True
    return False


def should_demote(memory: CompressedMemory, volatility: float) -> bool:
    """Should this memory be demoted to a more compressed tier?"""
    if memory.tier <= 0:
        return False  # already at min
    if volatility < DEMOTION_THRESHOLD:
        return memory.stable_cycles >= DEMOTION_STABLE_CYCLES
    return False


def promote_memory(
    memory: CompressedMemory,
    original_vector: Optional[np.ndarray] = None,
) -> CompressedMemory:
    """Promote a memory to the next tier (higher dimensionality)."""
    new_tier = min(memory.tier + 1, 2)
    new_dim = TIER_DIMS[new_tier]

    if original_vector is not None:
        # Re-fold from original at higher fidelity
        new_vec, new_seed = fold_vector(original_vector, new_dim)
        memory.vector = new_vec
        memory.cogni_seed = new_seed
    elif memory.cogni_seed:
        # Unfold current, then re-fold at higher dim
        reconstructed = unfold_vector(memory.vector, memory.cogni_seed)
        new_vec, new_seed = fold_vector(reconstructed, new_dim)
        memory.vector = new_vec
        memory.cogni_seed = new_seed

    memory.tier = new_tier
    memory.stable_cycles = 0
    return memory


def demote_memory(memory: CompressedMemory) -> CompressedMemory:
    """Demote a memory to a more compressed tier."""
    new_tier = max(memory.tier - 1, 0)
    new_dim = TIER_DIMS[new_tier]

    if memory.cogni_seed:
        # Unfold current, then re-fold at lower dim
        reconstructed = unfold_vector(memory.vector, memory.cogni_seed)
        new_vec, new_seed = fold_vector(reconstructed, new_dim)
        memory.vector = new_vec
        memory.cogni_seed = new_seed
    else:
        new_vec, new_seed = fold_vector(memory.vector, new_dim)
        memory.vector = new_vec
        memory.cogni_seed = new_seed

    memory.tier = new_tier
    return memory


# ---------------------------------------------------------------------------
# Similarity search across tiers
# ---------------------------------------------------------------------------

def cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    """Cosine similarity between two vectors of same dimensionality."""
    norm_a = np.linalg.norm(a)
    norm_b = np.linalg.norm(b)
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return float(np.dot(a, b) / (norm_a * norm_b))


def search_memories(
    query_vector: np.ndarray,
    memories: List[CompressedMemory],
    top_k: int = 5,
) -> List[Tuple[CompressedMemory, float]]:
    """Search across memories at different tiers.

    For each memory, folds the query vector to the memory's tier dimensionality
    before computing similarity. This allows mixed-tier search.
    """
    results: List[Tuple[CompressedMemory, float]] = []

    for mem in memories:
        mem_dim = len(mem.vector)
        # Fold query to same dimensionality
        if len(query_vector) != mem_dim:
            folded_query, _ = fold_vector(query_vector, mem_dim)
        else:
            folded_query = query_vector

        sim = cosine_similarity(folded_query, mem.vector)
        # Trust-weighted score
        score = sim * (0.5 + 0.5 * mem.trust)
        results.append((mem, score))

    results.sort(key=lambda x: x[1], reverse=True)
    return results[:top_k]
