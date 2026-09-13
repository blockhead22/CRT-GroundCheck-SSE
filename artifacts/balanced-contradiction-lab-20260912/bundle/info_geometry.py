"""Information Geometry for Belief Loci -- Step 8

The Fisher information metric as the "right" distance between beliefs.

Core problem: cosine similarity treats all dimensions equally.
But in a belief space, some dimensions carry more information than others.
Two beliefs that are "close" in embedding space might be very different
informationally, and vice versa.

The Fisher metric accounts for the curvature of probability space.
For Gaussian distributions (our belief loci), the Fisher metric has a
closed-form expression that weights dimensions by their precision
(inverse variance). Dimensions where the splat is tight (certain)
contribute MORE to distance than dimensions where it's wide (uncertain).

This means: two beliefs that differ on a dimension the agent is
CERTAIN about are further apart (in information space) than two
beliefs that differ on a dimension the agent is UNCERTAIN about.

That's the right behavior. Disagreement where you're sure matters
more than disagreement where you're already unsure.

For diagonal Gaussians N(mu, diag(sigma)):
  Fisher distance^2 ~ sum_i [ (mu1_i - mu2_i)^2 / sigma_avg_i
                              + (log(sigma1_i) - log(sigma2_i))^2 / 2 ]

Two terms:
  1. Precision-weighted center distance (certain dimensions count more)
  2. Covariance shape divergence (different uncertainty profiles)
"""

import time
import math
from dataclasses import dataclass
from typing import List, Optional, Tuple

import numpy as np

try:
    from .memory_splats import (
        BeliefLocus, create_locus, create_locus_from_type,
        cosine_similarity, bhattacharyya_distance,
        kl_divergence, overlap_integral,
        MemorySplat, create_splat, create_splat_from_type,  # backwards compat aliases
    )
except ImportError:
    from memory_splats import (
        BeliefLocus, create_locus, create_locus_from_type,
        cosine_similarity, bhattacharyya_distance,
        kl_divergence, overlap_integral,
        MemorySplat, create_splat, create_splat_from_type,  # backwards compat aliases
    )


# ---------------------------------------------------------------------------
# Fisher-Rao distance for diagonal Gaussians
# ---------------------------------------------------------------------------

def fisher_rao_distance(a: BeliefLocus, b: BeliefLocus) -> float:
    """Fisher-Rao distance between two diagonal Gaussian belief loci.

    The exact Fisher-Rao geodesic distance for multivariate Gaussians
    doesn't have a simple closed form. We use the commonly used
    approximation that decomposes into mean and covariance terms.

    For diagonal Gaussians, this becomes element-wise:
      d_FR^2 = sum_i [ (mu1_i - mu2_i)^2 / sigma_avg_i
                       + 0.5 * (log(sigma1_i/sigma2_i))^2 ]

    The first term is a precision-weighted Euclidean distance.
    The second term measures how different the uncertainty shapes are.
    """
    sigma_avg = (a.sigma + b.sigma) / 2.0
    diff_mu = a.mu - b.mu

    # Term 1: precision-weighted center distance
    # Dimensions where both loci are tight (low sigma) amplify differences
    # Dimensions where both are wide (high sigma) dampen differences
    mean_term = np.sum(diff_mu ** 2 / sigma_avg)

    # Term 2: covariance shape divergence
    # How different are the uncertainty profiles?
    log_ratio = np.log(a.sigma / b.sigma)
    cov_term = 0.5 * np.sum(log_ratio ** 2)

    return float(np.sqrt(mean_term + cov_term))


def fisher_mean_component(a: BeliefLocus, b: BeliefLocus) -> float:
    """Just the precision-weighted center distance (no cov term).

    Useful for isolating "how far apart are these beliefs,
    weighted by what we're sure about?"
    """
    sigma_avg = (a.sigma + b.sigma) / 2.0
    diff_mu = a.mu - b.mu
    return float(np.sqrt(np.sum(diff_mu ** 2 / sigma_avg)))


def fisher_cov_component(a: BeliefLocus, b: BeliefLocus) -> float:
    """Just the covariance shape divergence.

    Useful for detecting "these beliefs are about the same thing
    but one is much more certain than the other."
    """
    log_ratio = np.log(a.sigma / b.sigma)
    return float(np.sqrt(0.5 * np.sum(log_ratio ** 2)))


# ---------------------------------------------------------------------------
# Per-dimension Fisher contribution (which dimensions matter most?)
# ---------------------------------------------------------------------------

def fisher_dimension_contributions(
    a: BeliefLocus, b: BeliefLocus,
    top_k: int = 20,
) -> Tuple[np.ndarray, List[Tuple[int, float, str]]]:
    """Break down Fisher distance by dimension.

    Returns:
      - per_dim: array of per-dimension Fisher contributions
      - top_dims: list of (dim_index, contribution, reason) for top-k dims

    This tells you WHERE the beliefs disagree most, weighted by certainty.
    """
    sigma_avg = (a.sigma + b.sigma) / 2.0
    diff_mu = a.mu - b.mu

    # Per-dimension contributions
    mean_contrib = diff_mu ** 2 / sigma_avg
    log_ratio = np.log(a.sigma / b.sigma)
    cov_contrib = 0.5 * log_ratio ** 2

    per_dim = mean_contrib + cov_contrib

    # Top contributing dimensions
    top_indices = np.argsort(per_dim)[::-1][:top_k]
    top_dims = []
    for idx in top_indices:
        mc = float(mean_contrib[idx])
        cc = float(cov_contrib[idx])
        if mc > cc:
            reason = f"center disagreement (precision-amplified, sigma_avg={sigma_avg[idx]:.4f})"
        else:
            reason = f"uncertainty mismatch (sigma_a={a.sigma[idx]:.4f} vs sigma_b={b.sigma[idx]:.4f})"
        top_dims.append((int(idx), float(per_dim[idx]), reason))

    return per_dim, top_dims


# ---------------------------------------------------------------------------
# Fisher distance matrix (for topology, retrieval, etc.)
# ---------------------------------------------------------------------------

def fisher_distance_matrix(splats: List[BeliefLocus]) -> np.ndarray:
    """Pairwise Fisher-Rao distance matrix."""
    n = len(splats)
    D = np.zeros((n, n), dtype=np.float32)
    for i in range(n):
        for j in range(i + 1, n):
            d = fisher_rao_distance(splats[i], splats[j])
            D[i, j] = d
            D[j, i] = d
    return D


# ---------------------------------------------------------------------------
# Comparison: Fisher vs Cosine vs Bhattacharyya
# ---------------------------------------------------------------------------

@dataclass
class MetricComparison:
    """Side-by-side comparison of all distance metrics."""
    pair_label: str
    cosine_sim: float
    cosine_dist: float
    bhattacharyya: float
    kl_symmetrized: float
    fisher_total: float
    fisher_mean: float
    fisher_cov: float
    overlap: float


def compare_all_metrics(
    a: BeliefLocus, b: BeliefLocus, label: str = ""
) -> MetricComparison:
    """Compute all metrics between two belief loci for comparison."""
    cos = cosine_similarity(a, b)
    bd = bhattacharyya_distance(a, b)
    kl_ab = kl_divergence(a, b)
    kl_ba = kl_divergence(b, a)
    fr = fisher_rao_distance(a, b)
    fr_mean = fisher_mean_component(a, b)
    fr_cov = fisher_cov_component(a, b)
    ov = overlap_integral(a, b)

    return MetricComparison(
        pair_label=label,
        cosine_sim=cos,
        cosine_dist=1.0 - cos,
        bhattacharyya=bd,
        kl_symmetrized=(kl_ab + kl_ba) / 2,
        fisher_total=fr,
        fisher_mean=fr_mean,
        fisher_cov=fr_cov,
        overlap=ov,
    )


# ---------------------------------------------------------------------------
# Demonstration
# ---------------------------------------------------------------------------

def demo_info_geometry():
    """Show how Fisher distance reveals things cosine misses."""
    print("=" * 70)
    print("INFORMATION GEOMETRY -- Fisher Metric for Belief Loci")
    print("=" * 70)

    np.random.seed(42)
    d = 384

    # --- Scenario 1: Same center distance, different certainty ---
    print("\n  === SCENARIO 1: Same center distance, different certainty ===")
    print("  Two pairs of beliefs with identical cosine similarity,")
    print("  but one pair is certain and the other is uncertain.")

    base = np.random.randn(d).astype(np.float32)
    base /= np.linalg.norm(base)

    shift = np.random.randn(d).astype(np.float32) * 0.1
    shifted = base + shift
    shifted /= np.linalg.norm(shifted)

    # Pair A: tight splats (high certainty)
    tight_a = create_locus("tight_a", base.copy(), "certain belief A", "fact")
    tight_a.sigma *= 0.3  # very tight
    tight_b = create_locus("tight_b", shifted.copy(), "certain belief B", "fact")
    tight_b.sigma *= 0.3

    # Pair B: wide splats (low certainty)
    wide_a = create_locus("wide_a", base.copy(), "uncertain belief A", "belief")
    wide_a.sigma *= 3.0  # very wide
    wide_b = create_locus("wide_b", shifted.copy(), "uncertain belief B", "belief")
    wide_b.sigma *= 3.0

    m_tight = compare_all_metrics(tight_a, tight_b, "certain pair")
    m_wide = compare_all_metrics(wide_a, wide_b, "uncertain pair")

    print(f"\n  {'Metric':<20} | {'Certain Pair':>13} | {'Uncertain Pair':>14} | {'Ratio':>7}")
    print(f"  {'-'*20}-+-{'-'*13}-+-{'-'*14}-+-{'-'*7}")
    for field_name in ['cosine_dist', 'bhattacharyya', 'fisher_total', 'fisher_mean', 'fisher_cov']:
        v1 = getattr(m_tight, field_name)
        v2 = getattr(m_wide, field_name)
        ratio = v1 / v2 if v2 > 1e-8 else float('inf')
        print(f"  {field_name:<20} | {v1:13.4f} | {v2:14.4f} | {ratio:7.2f}x")

    print(f"\n  Key insight: Cosine distance is IDENTICAL for both pairs.")
    print(f"  Fisher distance is {m_tight.fisher_total / m_wide.fisher_total:.1f}x larger for the certain pair.")
    print(f"  Disagreement between certain beliefs matters more.")

    # --- Scenario 2: Same centers, different uncertainty shapes ---
    print(f"\n  === SCENARIO 2: Same center, different uncertainty shapes ===")
    print(f"  Two splats at the same location but one is tight, one is wide.")
    print(f"  Cosine sees them as identical. Fisher sees the shape difference.")

    same_center = base.copy()
    tight = create_locus("same_tight", same_center.copy(), "I know this", "fact")
    tight.sigma *= 0.2
    wide = create_locus("same_wide", same_center.copy(), "I think this maybe", "belief")
    wide.sigma *= 5.0

    m = compare_all_metrics(tight, wide, "same center, diff shape")
    print(f"\n  Cosine distance:     {m.cosine_dist:.6f}  (essentially zero)")
    print(f"  Fisher total:        {m.fisher_total:.4f}")
    print(f"  Fisher mean term:    {m.fisher_mean:.4f}  (centers are same)")
    print(f"  Fisher cov term:     {m.fisher_cov:.4f}  (uncertainty shapes differ)")
    print(f"\n  The covariance term is doing all the work here.")
    print(f"  'I know X' and 'I think maybe X' are the same claim")
    print(f"  but DIFFERENT beliefs. Fisher captures this. Cosine doesn't.")

    # --- Scenario 3: Which dimensions drive disagreement? ---
    print(f"\n  === SCENARIO 3: Per-dimension Fisher decomposition ===")
    print(f"  Where exactly do two beliefs disagree, weighted by certainty?")

    # Create splats where a few dimensions are very certain and different
    splat_a = create_locus("decomp_a", base.copy(), "belief A", "belief")
    splat_b = create_locus("decomp_b", shifted.copy(), "belief B", "belief")

    # Make splat_a very certain on dims 0-9 (tight sigma)
    splat_a.sigma[:10] *= 0.05
    # Make splat_b uncertain on dims 0-9 (wide sigma)
    splat_b.sigma[:10] *= 5.0

    per_dim, top_dims = fisher_dimension_contributions(splat_a, splat_b, top_k=10)

    print(f"\n  Top 10 dimensions by Fisher contribution:")
    print(f"  {'Dim':>5} | {'Contribution':>12} | Reason")
    print(f"  {'-'*5}-+-{'-'*12}-+{'-'*50}")
    for dim_idx, contrib, reason in top_dims:
        marker = " ***" if dim_idx < 10 else ""
        print(f"  {dim_idx:5d} | {contrib:12.4f} | {reason}{marker}")

    # Check: are the engineered dimensions (0-9) in the top?
    engineered_in_top = sum(1 for idx, _, _ in top_dims if idx < 10)
    print(f"\n  Engineered high-certainty dimensions in top 10: {engineered_in_top}/10")
    if engineered_in_top >= 5:
        print(f"  Fisher correctly identifies precision-amplified disagreement.")
    else:
        print(f"  Mixed result -- other dimensions also contribute significantly.")

    # --- Scenario 4: Fisher distance matrix vs cosine for retrieval ---
    print(f"\n  === SCENARIO 4: Retrieval ranking -- Fisher vs Cosine ===")
    print(f"  Given a query belief, do Fisher and cosine rank neighbors differently?")

    query = create_locus("query", base.copy(), "query belief", "belief")
    query.sigma *= 0.5  # moderately certain

    candidates = []
    # Close in cosine, uncertain
    c1 = create_locus("close_uncertain", (base + np.random.randn(d).astype(np.float32) * 0.05),
                       "close but uncertain", "belief")
    c1.mu /= np.linalg.norm(c1.mu)
    c1.sigma *= 4.0
    candidates.append(c1)

    # Close in cosine, certain
    c2 = create_locus("close_certain", (base + np.random.randn(d).astype(np.float32) * 0.05),
                       "close and certain", "fact")
    c2.mu /= np.linalg.norm(c2.mu)
    c2.sigma *= 0.3
    candidates.append(c2)

    # Medium distance, certain
    c3 = create_locus("medium_certain", (base + np.random.randn(d).astype(np.float32) * 0.15),
                       "medium distance, certain", "fact")
    c3.mu /= np.linalg.norm(c3.mu)
    c3.sigma *= 0.3
    candidates.append(c3)

    # Far in cosine, very certain
    c4 = create_locus("far_certain", (base + np.random.randn(d).astype(np.float32) * 0.3),
                       "far but very certain", "fact")
    c4.mu /= np.linalg.norm(c4.mu)
    c4.sigma *= 0.1
    candidates.append(c4)

    print(f"\n  {'Candidate':<20} | {'Cos Sim':>8} | {'Cos Rank':>8} | {'Fisher':>8} | {'Fish Rank':>9}")
    print(f"  {'-'*20}-+-{'-'*8}-+-{'-'*8}-+-{'-'*8}-+-{'-'*9}")

    cos_scores = [(i, cosine_similarity(query, c)) for i, c in enumerate(candidates)]
    fish_scores = [(i, fisher_rao_distance(query, c)) for i, c in enumerate(candidates)]

    cos_ranked = sorted(cos_scores, key=lambda x: -x[1])  # higher cos = more similar
    fish_ranked = sorted(fish_scores, key=lambda x: x[1])   # lower fisher = more similar

    cos_rank_map = {idx: rank + 1 for rank, (idx, _) in enumerate(cos_ranked)}
    fish_rank_map = {idx: rank + 1 for rank, (idx, _) in enumerate(fish_ranked)}

    for i, c in enumerate(candidates):
        cs = cosine_similarity(query, c)
        fd = fisher_rao_distance(query, c)
        print(f"  {c.memory_id:<20} | {cs:8.4f} | {cos_rank_map[i]:>8} | {fd:8.2f} | {fish_rank_map[i]:>9}")

    # Check if rankings differ
    cos_order = [idx for idx, _ in cos_ranked]
    fish_order = [idx for idx, _ in fish_ranked]
    if cos_order != fish_order:
        print(f"\n  Rankings DIFFER. Fisher reorders based on certainty.")
        print(f"  Cosine ranking:  {[candidates[i].memory_id for i in cos_order]}")
        print(f"  Fisher ranking:  {[candidates[i].memory_id for i in fish_order]}")
    else:
        print(f"\n  Rankings agree (certainty didn't change the order in this case).")

    # --- Summary ---
    print(f"\n  === SUMMARY: When to use which metric ===")
    print(f"  Cosine:   Fast. Good for topic similarity. Ignores uncertainty.")
    print(f"  Fisher:   Slower. Weights by certainty. Sees shape differences.")
    print(f"  Use cosine for: 'find related memories' (retrieval)")
    print(f"  Use Fisher for: 'how different are these beliefs REALLY?' (reasoning)")
    print(f"  Use Fisher cov term for: 'same claim, different confidence' detection")


if __name__ == "__main__":
    import sys
    sys.path.insert(0, r"D:\CRT\compression_lab")
    demo_info_geometry()
    print(f"\n{'='*70}")
    print("INFORMATION GEOMETRY -- COMPLETE")
    print(f"{'='*70}")
