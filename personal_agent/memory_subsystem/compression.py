"""Adaptive semantic memory compression for CRT.

Ported from compression_lab/adaptive_memory.py for production integration.

Core math (Nick's whiteboard, April 2025):
  V(t) = alpha * D(t) + beta * C(t) + gamma * F(t)   -- volatility
  H(t) = H0 * e^(-s * V(t))                           -- throttle

Tier system:
  Tier 0: 10D   (cold)  -- routine, stable, low-trust facts
  Tier 1: 64D   (warm)  -- intermediate fidelity
  Tier 2: 384D  (full)  -- identity, high-trust, volatile memories

Console logging uses a distinctive ◊ diamond prefix for all compression events
so they stand out in the API log stream.
"""

from __future__ import annotations

import logging
import math
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
from scipy.stats import norm

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Deprecated — kept for backward-compat with old fold-format memories
TIER_DIMS: Dict[int, int] = {0: 10, 1: 64, 2: 384}

# New MemQuant tier mapping: tiers → bit depths (all stay 384D)
TIER_BITS: Dict[int, int] = {0: 2, 1: 3, 2: 0}  # 0 = uncompressed
TIER_NAMES: Dict[int, str] = {0: "cold·2bit", 1: "warm·3bit", 2: "full·384D"}


# ---------------------------------------------------------------------------
# Lloyd-Max codebook for Gaussian N(0, sigma)
# ---------------------------------------------------------------------------

def lloyd_max_codebook(n_levels: int, sigma: float = 1.0, max_iter: int = 200) -> tuple:
    """Compute optimal Lloyd-Max quantizer for N(0, sigma).

    Returns (boundaries, centroids).
    """
    centroids = np.linspace(-3 * sigma, 3 * sigma, n_levels)

    for _ in range(max_iter):
        boundaries = np.zeros(n_levels + 1)
        boundaries[0] = -np.inf
        boundaries[-1] = np.inf
        for i in range(1, n_levels):
            boundaries[i] = (centroids[i - 1] + centroids[i]) / 2.0

        new_centroids = np.zeros(n_levels)
        for i in range(n_levels):
            lo, hi = boundaries[i], boundaries[i + 1]
            lo_s = lo / sigma if lo != -np.inf else -10.0
            hi_s = hi / sigma if hi != np.inf else 10.0
            prob = norm.cdf(hi_s) - norm.cdf(lo_s)
            if prob < 1e-15:
                new_centroids[i] = (lo_s + hi_s) / 2.0 * sigma
            else:
                new_centroids[i] = sigma * (norm.pdf(lo_s) - norm.pdf(hi_s)) / prob

        if np.allclose(centroids, new_centroids, atol=1e-10):
            break
        centroids = new_centroids

    return boundaries, centroids


# ---------------------------------------------------------------------------
# QuantizedMemory — compressed representation
# ---------------------------------------------------------------------------

@dataclass
class QuantizedMemory:
    """Compressed representation of a single memory vector via MemQuant."""
    indices: np.ndarray   # uint8 quantization indices, shape (dim,)
    bits: int             # bit depth used
    norm: float           # original vector L2 norm


# ---------------------------------------------------------------------------
# MemQuantizer — rotation + Lloyd-Max scalar quantization
# ---------------------------------------------------------------------------

class MemQuantizer:
    """MemQuant: random orthogonal rotation + Lloyd-Max scalar quantization.

    Data-oblivious (no training needed). Deterministic for a given seed.
    """

    def __init__(self, dim: int = 384, bits: int = 3, seed: int = 42):
        self.dim = dim
        self.bits = bits
        self.n_levels = 2 ** bits

        rng = np.random.RandomState(seed)

        # Random orthogonal rotation matrix via QR decomposition
        gaussian = rng.randn(dim, dim).astype(np.float32)
        Q, _R = np.linalg.qr(gaussian)
        self.rotation = Q.astype(np.float32)

        # Lloyd-Max codebook for N(0, 1/sqrt(dim))
        self.sigma = 1.0 / np.sqrt(dim)
        self.boundaries, self.centroids = lloyd_max_codebook(self.n_levels, self.sigma)
        self.boundaries = self.boundaries.astype(np.float32)
        self.centroids = self.centroids.astype(np.float32)

    def _quantize(self, values: np.ndarray) -> tuple:
        """Quantize array of floats to nearest centroid. Returns (indices, reconstructed)."""
        indices = np.digitize(values, self.boundaries[1:-1]).astype(np.uint8)
        indices = np.clip(indices, 0, self.n_levels - 1)
        reconstructed = self.centroids[indices]
        return indices, reconstructed

    def compress(self, vector: np.ndarray) -> QuantizedMemory:
        """Compress a memory vector using rotation + Lloyd-Max quantization."""
        vec = np.asarray(vector, dtype=np.float32).flatten()
        assert len(vec) == self.dim, f"Expected {self.dim}D, got {len(vec)}D"

        vec_norm = float(np.linalg.norm(vec))
        if vec_norm < 1e-10:
            return QuantizedMemory(
                indices=np.zeros(self.dim, dtype=np.uint8),
                bits=self.bits, norm=0.0,
            )

        normalized = vec / vec_norm
        rotated = normalized @ self.rotation
        indices, _reconstructed = self._quantize(rotated)

        return QuantizedMemory(indices=indices, bits=self.bits, norm=vec_norm)

    def decompress(self, compressed: QuantizedMemory) -> np.ndarray:
        """Approximate reconstruction from quantized form."""
        if compressed.norm < 1e-10:
            return np.zeros(self.dim, dtype=np.float32)

        reconstructed_rotated = self.centroids[compressed.indices]
        reconstructed = reconstructed_rotated @ self.rotation.T
        return reconstructed * compressed.norm

    def inner_product(self, query: np.ndarray, compressed: QuantizedMemory) -> float:
        """Compute inner product <query, original> from compressed form."""
        q = np.asarray(query, dtype=np.float32).flatten()
        if compressed.norm < 1e-10:
            return 0.0

        reconstructed_rotated = self.centroids[compressed.indices]
        reconstructed = (reconstructed_rotated @ self.rotation.T) * compressed.norm
        return float(np.dot(q, reconstructed))


# ---------------------------------------------------------------------------
# Module-level quantizer singletons
# ---------------------------------------------------------------------------

_QUANTIZERS: Dict[tuple, MemQuantizer] = {}


def _get_quantizer(bits: int, dim: int = 384) -> MemQuantizer:
    """Get or create a MemQuantizer singleton for (bits, dim)."""
    key = (bits, dim)
    if key not in _QUANTIZERS:
        _QUANTIZERS[key] = MemQuantizer(dim=dim, bits=bits, seed=42)
    return _QUANTIZERS[key]


# ---------------------------------------------------------------------------
# Public quantize / dequantize API
# ---------------------------------------------------------------------------

def quantize_vector(vector: np.ndarray, bits: int) -> Tuple[np.ndarray, dict]:
    """Compress using MemQuant. Returns (uint8_indices, metadata_dict)."""
    q = _get_quantizer(bits, dim=len(vector))
    compressed = q.compress(vector)
    metadata = {
        "method": "memquant",
        "bits": bits,
        "norm": compressed.norm,
        "original_dim": len(vector),
    }
    return compressed.indices.astype(np.uint8), metadata


def dequantize_vector(indices: np.ndarray, metadata: dict) -> np.ndarray:
    """Reconstruct from MemQuant compressed form."""
    bits = metadata["bits"]
    norm_val = metadata["norm"]
    dim = metadata.get("original_dim", 384)
    q = _get_quantizer(bits, dim=dim)
    cm = QuantizedMemory(indices=indices.astype(np.uint8), bits=bits, norm=norm_val)
    return q.decompress(cm)


def quantized_inner_product(query: np.ndarray, indices: np.ndarray, metadata: dict) -> float:
    """Compute inner product directly from compressed form."""
    bits = metadata["bits"]
    norm_val = metadata["norm"]
    dim = metadata.get("original_dim", 384)
    q = _get_quantizer(bits, dim=dim)
    cm = QuantizedMemory(indices=indices.astype(np.uint8), bits=bits, norm=norm_val)
    return q.inner_product(query, cm)

VOLATILITY_ALPHA = 0.4    # drift weight
VOLATILITY_BETA  = 0.35   # contradiction weight
VOLATILITY_GAMMA = 0.25   # fidelity loss weight

THROTTLE_H0 = 1.0
THROTTLE_S  = 3.0

PROMOTION_THRESHOLD    = 0.6
DEMOTION_THRESHOLD     = 0.1
DEMOTION_STABLE_CYCLES = 10
DEMOTION_MAX_TRUST     = 0.3   # only demote if trust below this

# Kinds / authorities that are never compressed
PROTECTED_KINDS       = {"identity_constant"}
PROTECTED_AUTHORITIES = {"locked"}

# ---------------------------------------------------------------------------
# Distinctive console logging
# ---------------------------------------------------------------------------

_DIAMOND = "\u25C7"  # ◇

def _log_fold(memory_id: str, text_preview: str, from_tier: int, to_tier: int, volatility: float, trust: float):
    """Log a fold/demotion event with diamond prefix."""
    logger.info(
        f"{_DIAMOND} FOLD  {memory_id[:12]}  "
        f"{TIER_NAMES[from_tier]} \u2192 {TIER_NAMES[to_tier]}  "
        f"V={volatility:.3f}  \u03C4={trust:.3f}  "
        f"\"{text_preview[:50]}\""
    )

def _log_unfold(memory_id: str, text_preview: str, from_tier: int, to_tier: int, volatility: float, trust: float):
    """Log an unfold/promotion event with diamond prefix."""
    logger.info(
        f"{_DIAMOND} UNFOLD  {memory_id[:12]}  "
        f"{TIER_NAMES[from_tier]} \u2192 {TIER_NAMES[to_tier]}  "
        f"V={volatility:.3f}  \u03C4={trust:.3f}  "
        f"\"{text_preview[:50]}\""
    )

def _log_stable(memory_id: str, stable_cycles: int, volatility: float):
    """Log a stability tick."""
    logger.debug(
        f"{_DIAMOND} STABLE  {memory_id[:12]}  "
        f"cycles={stable_cycles}  V={volatility:.3f}"
    )

def _log_pass_summary(total: int, folded: int, unfolded: int, stable_ticks: int, skipped_protected: int):
    """Log compression pass summary."""
    logger.info(
        f"{_DIAMOND}{_DIAMOND}{_DIAMOND} COMPRESSION PASS  "
        f"scanned={total}  folded={folded}  unfolded={unfolded}  "
        f"stable_ticks={stable_ticks}  protected={skipped_protected}"
    )


# ---------------------------------------------------------------------------
# CogniSeed — compact reconstruction guide
# ---------------------------------------------------------------------------

@dataclass
class CogniSeed:
    """Statistical summary of how a vector was folded.

    Enables approximate reconstruction without storing the full vector.
    Storage cost: ~(target_dim * 12 + 16) bytes.
    """
    original_dim: int
    target_dim: int
    mean_contribution: np.ndarray
    variance_contribution: np.ndarray
    dominant_indices: np.ndarray
    polarity_bias: float
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
            mean_contribution=np.array(d["mean"], dtype=np.float32),
            variance_contribution=np.array(d["variance"], dtype=np.float32),
            dominant_indices=np.array(d["dominant"]),
            polarity_bias=d["polarity"],
            fold_timestamp=d.get("ts", 0.0),
        )


# ---------------------------------------------------------------------------
# Folding — compress a vector to target dimensionality
# ---------------------------------------------------------------------------

def fold_vector(
    vector: np.ndarray,
    target_dim: int,
) -> Tuple[np.ndarray, CogniSeed]:
    """Fold a high-dimensional vector down to target_dim via chunked averaging.

    Returns (compressed_vector, cogni_seed).
    """
    vec = np.array(vector, dtype=np.float32).flatten()
    original_dim = len(vec)

    if original_dim <= target_dim:
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

    chunk_size = original_dim // target_dim
    remainder = original_dim % target_dim
    compressed = np.zeros(target_dim, dtype=np.float32)
    var_contrib = np.zeros(target_dim, dtype=np.float32)

    for i in range(target_dim):
        start = i * chunk_size + min(i, remainder)
        end = (i + 1) * chunk_size + min(i + 1, remainder)
        chunk = vec[start:end]
        compressed[i] = np.mean(chunk)
        var_contrib[i] = np.var(chunk)

    dominant = np.argsort(np.abs(compressed))[::-1][:target_dim]

    seed = CogniSeed(
        original_dim=original_dim,
        target_dim=target_dim,
        mean_contribution=compressed.copy(),
        variance_contribution=var_contrib,
        dominant_indices=dominant,
        polarity_bias=float(np.mean(vec)),
        fold_timestamp=time.time(),
    )
    return compressed, seed


# ---------------------------------------------------------------------------
# Unfolding — approximate reconstruction
# ---------------------------------------------------------------------------

def unfold_vector(compressed: np.ndarray, seed: CogniSeed) -> np.ndarray:
    """Approximate reconstruction from compressed vector + cogni seed.

    Deterministic (no randomness) — same inputs always produce same output.
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

        base_val = compressed[i]
        variance = seed.variance_contribution[i]
        if variance > 0 and chunk_len > 1:
            spread = np.linspace(-1, 1, chunk_len) * math.sqrt(variance)
            result[start:end] = base_val + spread
        else:
            result[start:end] = base_val

    return result


# ---------------------------------------------------------------------------
# Volatility & throttle
# ---------------------------------------------------------------------------

def _reconstruct_vector(
    compressed_vector: Optional[np.ndarray],
    cogni_seed,
) -> Optional[np.ndarray]:
    """Reconstruct a vector from either memquant or legacy fold format."""
    if compressed_vector is None or cogni_seed is None:
        return None
    if isinstance(cogni_seed, dict) and cogni_seed.get("method") == "memquant":
        return dequantize_vector(compressed_vector, cogni_seed)
    elif isinstance(cogni_seed, CogniSeed):
        return unfold_vector(compressed_vector, cogni_seed)
    return None


def _compute_volatility_from_reconstructed(
    *,
    original_vector: Optional[np.ndarray],
    reconstructed: Optional[np.ndarray],
    contradiction_count: int,
    access_count: int,
) -> float:
    """Compute V(t) given a pre-reconstructed vector (avoids double reconstruction)."""
    drift = 0.0
    if reconstructed is not None and original_vector is not None and len(reconstructed) == len(original_vector):
        norm_o = np.linalg.norm(original_vector)
        norm_r = np.linalg.norm(reconstructed)
        if norm_o > 0 and norm_r > 0:
            cos_sim = np.dot(reconstructed, original_vector) / (norm_r * norm_o)
            drift = 1.0 - max(0.0, float(cos_sim))

    c_density = contradiction_count / max(access_count, 1)

    fidelity_loss = 0.0
    if reconstructed is not None and original_vector is not None and len(reconstructed) == len(original_vector):
        mse = float(np.mean((reconstructed - original_vector) ** 2))
        fidelity_loss = min(1.0, mse * 10)

    v = VOLATILITY_ALPHA * drift + VOLATILITY_BETA * c_density + VOLATILITY_GAMMA * fidelity_loss
    return float(min(1.0, v))


def compute_volatility(
    *,
    original_vector: Optional[np.ndarray],
    compressed_vector: Optional[np.ndarray],
    cogni_seed=None,
    contradiction_count: int,
    access_count: int,
) -> float:
    """Compute V(t) = alpha*D(t) + beta*C(t) + gamma*F(t).

    Handles both legacy CogniSeed and memquant dict formats.
    """
    reconstructed = _reconstruct_vector(compressed_vector, cogni_seed)
    return _compute_volatility_from_reconstructed(
        original_vector=original_vector,
        reconstructed=reconstructed,
        contradiction_count=contradiction_count,
        access_count=access_count,
    )


def compute_volatility_from_item(
    memory_item,
    contradiction_count: Optional[int] = None,
) -> float:
    """Convenience wrapper: compute V(t) from a MemoryItem without manual field extraction.

    Handles both legacy CogniSeed and memquant dict formats.
    """
    vec = getattr(memory_item, "vector", None)
    comp_vec = getattr(memory_item, "compressed_vector", None)
    seed_dict = getattr(memory_item, "cogni_seed", None)

    # Detect format: memquant dicts pass through, legacy dicts get parsed to CogniSeed
    seed = None
    if seed_dict is not None and isinstance(seed_dict, dict):
        if seed_dict.get("method") == "memquant":
            seed = seed_dict  # pass through as dict
        else:
            try:
                seed = CogniSeed.from_dict(seed_dict)
            except Exception:
                pass

    if contradiction_count is None:
        contradiction_count = getattr(memory_item, "contradiction_count", 0)
    access_count = max(getattr(memory_item, "access_count", 1), 1)

    return compute_volatility(
        original_vector=vec,
        compressed_vector=comp_vec,
        cogni_seed=seed,
        contradiction_count=contradiction_count,
        access_count=access_count,
    )


def compute_throttle(volatility: float) -> float:
    """H(t) = H0 * e^(-s * V(t)).  High V → low H → stop compressing."""
    return THROTTLE_H0 * math.exp(-THROTTLE_S * volatility)


# ---------------------------------------------------------------------------
# Protection checks
# ---------------------------------------------------------------------------

def is_protected(*, kind: str, authority: str, source: str, trust: float) -> bool:
    """Returns True if this memory must never be compressed below tier 2."""
    if kind in PROTECTED_KINDS:
        return True
    if authority in PROTECTED_AUTHORITIES:
        return True
    return False


def minimum_tier(*, kind: str, authority: str, source: str, trust: float) -> int:
    """Returns the lowest tier this memory is allowed to reach."""
    if is_protected(kind=kind, authority=authority, source=source, trust=trust):
        return 2
    # High-trust user memories: minimum tier 1
    if source == "user" and trust >= 0.8:
        return 1
    return 0


# ---------------------------------------------------------------------------
# Tier transition decisions
# ---------------------------------------------------------------------------

def should_promote(
    tier: int, volatility: float, trust: float,
) -> bool:
    """Should this memory move to a higher-fidelity tier?"""
    if tier >= 2:
        return False
    if volatility >= PROMOTION_THRESHOLD:
        return True
    if trust >= 0.9 and volatility >= PROMOTION_THRESHOLD * 0.5:
        return True
    return False


def should_demote(
    tier: int, volatility: float, trust: float, stable_cycles: int,
    min_tier: int = 0,
) -> bool:
    """Should this memory be compressed to a lower tier?"""
    if tier <= min_tier:
        return False
    if trust > DEMOTION_MAX_TRUST:
        return False
    if volatility < DEMOTION_THRESHOLD:
        return stable_cycles >= DEMOTION_STABLE_CYCLES
    return False


# ---------------------------------------------------------------------------
# Phase G2: volatility → covariance bridge
# ---------------------------------------------------------------------------

_SIGMA_SETTLE_RATE = 0.02   # per-cycle tightening when volatility is low
_SIGMA_WIDEN_RATE = 0.05    # per-cycle widening when volatility is high
_VOLATILITY_MIDPOINT = 0.3  # V(t) above this widens, below tightens


def _save_trajectory_snapshot(conn, id_col: str, mem_id: str) -> None:
    """Save a lightweight trajectory snapshot during the compression pass."""
    row = conn.execute(
        f"SELECT vector_json, sigma, trust FROM memories WHERE {id_col} = ?",
        (mem_id,),
    ).fetchone()
    if not row or row[1] is None:
        return
    sigma = np.frombuffer(row[1], dtype=np.float32)
    total_unc = float(np.sum(sigma))
    mu_blob = None
    if row[0]:
        try:
            mu_blob = np.array(json.loads(row[0]), dtype=np.float32).tobytes()
        except Exception:
            pass
    alpha = row[2] if row[2] is not None else 0.5
    import time as _t
    conn.execute(
        """INSERT INTO trajectory_snapshots
           (memory_id, timestamp, mu, sigma, alpha, total_uncertainty)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (mem_id, _t.time(), mu_blob, row[1], alpha, total_unc),
    )


def _bridge_volatility_to_sigma(conn, id_col: str, mem_id: str, volatility: float) -> None:
    """Nudge sigma toward the volatility signal each heartbeat cycle.

    Low volatility  → sigma shrinks (belief settling)
    High volatility → sigma grows   (belief under pressure)

    This keeps the geometric representation in sync with the scalar
    compression system without replacing either.
    """
    row = conn.execute(
        f"SELECT sigma FROM memories WHERE {id_col} = ?", (mem_id,)
    ).fetchone()
    if not row or row[0] is None:
        return

    sigma = np.frombuffer(row[0], dtype=np.float32).copy()

    if volatility < _VOLATILITY_MIDPOINT:
        # Settle: gently tighten
        factor = 1.0 - _SIGMA_SETTLE_RATE * (1.0 - volatility / _VOLATILITY_MIDPOINT)
        sigma *= factor
    else:
        # Pressure: gently widen
        excess = (volatility - _VOLATILITY_MIDPOINT) / (1.0 - _VOLATILITY_MIDPOINT + 1e-8)
        factor = 1.0 + _SIGMA_WIDEN_RATE * excess
        sigma *= factor

    np.maximum(sigma, 1e-8, out=sigma)

    conn.execute(
        f"UPDATE memories SET sigma = ? WHERE {id_col} = ?",
        (sigma.tobytes(), mem_id),
    )


# ---------------------------------------------------------------------------
# Compression pass — called from trust_decay heartbeat
# ---------------------------------------------------------------------------

def run_compression_pass(
    conn,
    id_col: str = "memory_id",
    grace_cutoff: float = 0.0,
) -> Dict[str, int]:
    """Run one compression pass over all memories in the database.

    Reads compression state, computes volatility, and promotes/demotes as needed.
    Called after trust decay in the heartbeat.

    Returns summary dict.
    """
    import json

    now = time.time()

    # Check if columns exist
    cols = {row[1] for row in conn.execute("PRAGMA table_info(memories)").fetchall()}
    if "compression_tier" not in cols:
        return {"skipped": True, "reason": "no_compression_columns"}

    rows = conn.execute(
        f"""SELECT {id_col}, vector_json, text, trust, timestamp,
                   compression_tier, compressed_vector_json, cogni_seed_json,
                   stable_cycles, contradiction_count, access_count,
                   authority, kind, source
            FROM memories
            WHERE (deprecated IS NULL OR deprecated = 0)
              AND timestamp < ?""",
        (grace_cutoff,),
    ).fetchall()

    folded = 0
    unfolded = 0
    stable_ticks = 0
    skipped_protected = 0

    for row in rows:
        mem_id = row[0]
        trust = float(row[3])
        tier = int(row[5]) if row[5] is not None else 2
        compressed_json = row[6]
        seed_json = row[7]
        stable_cyc = int(row[8]) if row[8] is not None else 0
        contra_count = int(row[9]) if row[9] is not None else 0
        access_cnt = int(row[10]) if row[10] is not None else 0
        authority = str(row[11] or "confirmed")
        kind = str(row[12] or "observation")
        source = str(row[13] or "user")
        text = str(row[2] or "")

        # Parse vectors
        try:
            original_vector = np.array(json.loads(row[1]), dtype=np.float32)
        except Exception:
            continue

        compressed_vector = None
        cogni_seed = None  # CogniSeed (legacy) or dict with method=memquant (new)
        is_memquant = False
        if seed_json:
            try:
                parsed_seed = json.loads(seed_json)
                if isinstance(parsed_seed, dict) and parsed_seed.get("method") == "memquant":
                    cogni_seed = parsed_seed  # keep as dict for memquant
                    is_memquant = True
                else:
                    cogni_seed = CogniSeed.from_dict(parsed_seed)
            except Exception:
                pass
        if compressed_json:
            try:
                if is_memquant:
                    compressed_vector = np.array(json.loads(compressed_json), dtype=np.uint8)
                else:
                    compressed_vector = np.array(json.loads(compressed_json), dtype=np.float32)
            except Exception:
                pass

        # Protection check
        min_t = minimum_tier(kind=kind, authority=authority, source=source, trust=trust)
        if min_t >= 2:
            skipped_protected += 1
            continue

        # Compute volatility — reconstruct based on format
        reconstructed = None
        if compressed_vector is not None and cogni_seed is not None and original_vector is not None:
            if is_memquant:
                reconstructed = dequantize_vector(compressed_vector, cogni_seed)
            else:
                reconstructed = unfold_vector(compressed_vector, cogni_seed)

        volatility = _compute_volatility_from_reconstructed(
            original_vector=original_vector,
            reconstructed=reconstructed,
            contradiction_count=contra_count,
            access_count=access_cnt,
        )

        # Phase G2: bridge volatility → covariance (sigma)
        # High volatility → widen sigma, low volatility → tighten sigma
        try:
            _bridge_volatility_to_sigma(conn, id_col, mem_id, volatility)
            # Snapshot every 5 stable cycles or on any promote/demote (handled below)
            if stable_cyc > 0 and stable_cyc % 5 == 0:
                _save_trajectory_snapshot(conn, id_col, mem_id)
        except Exception:
            pass

        # Promote?
        if should_promote(tier, volatility, trust):
            new_tier = min(tier + 1, 2)
            if new_tier == 2:
                # Back to full — clear compressed fields
                conn.execute(
                    f"""UPDATE memories SET
                            compression_tier = 2,
                            compressed_vector_json = NULL,
                            cogni_seed_json = NULL,
                            stable_cycles = 0
                        WHERE {id_col} = ?""",
                    (mem_id,),
                )
            else:
                bits = TIER_BITS[new_tier]
                indices, metadata = quantize_vector(original_vector, bits)
                conn.execute(
                    f"""UPDATE memories SET
                            compression_tier = ?,
                            compressed_vector_json = ?,
                            cogni_seed_json = ?,
                            stable_cycles = 0
                        WHERE {id_col} = ?""",
                    (new_tier, json.dumps(indices.tolist()), json.dumps(metadata), mem_id),
                )
            _log_unfold(mem_id, text, tier, new_tier, volatility, trust)
            try:
                _save_trajectory_snapshot(conn, id_col, mem_id)
            except Exception:
                pass
            unfolded += 1

        # Demote?
        elif should_demote(tier, volatility, trust, stable_cyc, min_tier=min_t):
            new_tier = max(tier - 1, min_t)
            bits = TIER_BITS[new_tier]
            indices, metadata = quantize_vector(original_vector, bits)
            conn.execute(
                f"""UPDATE memories SET
                        compression_tier = ?,
                        compressed_vector_json = ?,
                        cogni_seed_json = ?,
                        stable_cycles = 0
                    WHERE {id_col} = ?""",
                (new_tier, json.dumps(indices.tolist()), json.dumps(metadata), mem_id),
            )
            _log_fold(mem_id, text, tier, new_tier, volatility, trust)
            try:
                _save_trajectory_snapshot(conn, id_col, mem_id)
            except Exception:
                pass
            folded += 1

        # Stability tracking
        elif volatility < DEMOTION_THRESHOLD:
            new_cyc = stable_cyc + 1
            conn.execute(
                f"UPDATE memories SET stable_cycles = ? WHERE {id_col} = ?",
                (new_cyc, mem_id),
            )
            _log_stable(mem_id, new_cyc, volatility)
            stable_ticks += 1
        else:
            # Volatility above threshold — reset stability
            if stable_cyc > 0:
                conn.execute(
                    f"UPDATE memories SET stable_cycles = 0 WHERE {id_col} = ?",
                    (mem_id,),
                )

    _log_pass_summary(len(rows), folded, unfolded, stable_ticks, skipped_protected)

    return {
        "total_scanned": len(rows),
        "folded": folded,
        "unfolded": unfolded,
        "stable_ticks": stable_ticks,
        "skipped_protected": skipped_protected,
    }
