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

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

TIER_DIMS: Dict[int, int] = {0: 10, 1: 64, 2: 384}
TIER_NAMES: Dict[int, str] = {0: "cold·10D", 1: "warm·64D", 2: "full·384D"}

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

def compute_volatility(
    *,
    original_vector: Optional[np.ndarray],
    compressed_vector: Optional[np.ndarray],
    cogni_seed: Optional[CogniSeed],
    contradiction_count: int,
    access_count: int,
) -> float:
    """Compute V(t) = alpha*D(t) + beta*C(t) + gamma*F(t)."""

    # D(t): drift — reconstruction vs original
    drift = 0.0
    if compressed_vector is not None and cogni_seed is not None and original_vector is not None:
        reconstructed = unfold_vector(compressed_vector, cogni_seed)
        if len(reconstructed) == len(original_vector):
            norm_o = np.linalg.norm(original_vector)
            norm_r = np.linalg.norm(reconstructed)
            if norm_o > 0 and norm_r > 0:
                cos_sim = np.dot(reconstructed, original_vector) / (norm_r * norm_o)
                drift = 1.0 - max(0.0, float(cos_sim))

    # C(t): contradiction density
    c_density = contradiction_count / max(access_count, 1)

    # F(t): fidelity loss (MSE-based)
    fidelity_loss = 0.0
    if compressed_vector is not None and cogni_seed is not None and original_vector is not None:
        reconstructed = unfold_vector(compressed_vector, cogni_seed)
        if len(reconstructed) == len(original_vector):
            mse = float(np.mean((reconstructed - original_vector) ** 2))
            fidelity_loss = min(1.0, mse * 10)

    v = VOLATILITY_ALPHA * drift + VOLATILITY_BETA * c_density + VOLATILITY_GAMMA * fidelity_loss
    return float(min(1.0, v))


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
        cogni_seed = None
        if compressed_json:
            try:
                compressed_vector = np.array(json.loads(compressed_json), dtype=np.float32)
            except Exception:
                pass
        if seed_json:
            try:
                cogni_seed = CogniSeed.from_dict(json.loads(seed_json))
            except Exception:
                pass

        # Protection check
        min_t = minimum_tier(kind=kind, authority=authority, source=source, trust=trust)
        if min_t >= 2:
            skipped_protected += 1
            continue

        # Compute volatility
        volatility = compute_volatility(
            original_vector=original_vector,
            compressed_vector=compressed_vector,
            cogni_seed=cogni_seed,
            contradiction_count=contra_count,
            access_count=access_cnt,
        )

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
                new_dim = TIER_DIMS[new_tier]
                new_vec, new_seed = fold_vector(original_vector, new_dim)
                conn.execute(
                    f"""UPDATE memories SET
                            compression_tier = ?,
                            compressed_vector_json = ?,
                            cogni_seed_json = ?,
                            stable_cycles = 0
                        WHERE {id_col} = ?""",
                    (new_tier, json.dumps(new_vec.tolist()), json.dumps(new_seed.to_dict()), mem_id),
                )
            _log_unfold(mem_id, text, tier, new_tier, volatility, trust)
            unfolded += 1

        # Demote?
        elif should_demote(tier, volatility, trust, stable_cyc, min_tier=min_t):
            new_tier = max(tier - 1, min_t)
            new_dim = TIER_DIMS[new_tier]
            new_vec, new_seed = fold_vector(original_vector, new_dim)
            conn.execute(
                f"""UPDATE memories SET
                        compression_tier = ?,
                        compressed_vector_json = ?,
                        cogni_seed_json = ?,
                        stable_cycles = 0
                    WHERE {id_col} = ?""",
                (new_tier, json.dumps(new_vec.tolist()), json.dumps(new_seed.to_dict()), mem_id),
            )
            _log_fold(mem_id, text, tier, new_tier, volatility, trust)
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
