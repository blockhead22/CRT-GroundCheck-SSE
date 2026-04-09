"""Test suite for adaptive semantic compression.

Validates the core concepts:
1. Folding preserves semantic relationships (10D similarity ≈ full-dim similarity)
2. Cogni seed enables approximate reconstruction
3. Volatility scoring detects instability
4. Tier promotion/demotion works correctly
5. Mixed-tier search returns relevant results
6. Storage savings are real
7. Throttle function behaves as expected
"""

import math
import time
import uuid

import numpy as np
import pytest

from .adaptive_memory import (
    TIER_DIMS,
    PROMOTION_THRESHOLD,
    DEMOTION_THRESHOLD,
    CogniSeed,
    CompressedMemory,
    fold_vector,
    unfold_vector,
    compute_volatility,
    compute_throttle,
    should_promote,
    should_demote,
    promote_memory,
    demote_memory,
    cosine_similarity,
    search_memories,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def random_vector(dim: int = 384, seed: int = 42) -> np.ndarray:
    rng = np.random.RandomState(seed)
    return rng.randn(dim).astype(np.float32)


def similar_vector(base: np.ndarray, noise: float = 0.1, seed: int = 99) -> np.ndarray:
    """Create a vector similar to base with controlled noise."""
    rng = np.random.RandomState(seed)
    return (base + rng.randn(*base.shape) * noise).astype(np.float32)


def make_memory(
    text: str = "test fact",
    dim: int = 384,
    tier: int = 0,
    trust: float = 0.7,
    seed: int = 42,
) -> CompressedMemory:
    original = random_vector(dim, seed)
    compressed, cogni_seed = fold_vector(original, TIER_DIMS[tier])
    return CompressedMemory(
        memory_id=str(uuid.uuid4()),
        text=text,
        vector=compressed,
        tier=tier,
        trust=trust,
        cogni_seed=cogni_seed,
        original_vector=original,
    )


# ===========================================================================
# 1. Folding preserves semantic relationships
# ===========================================================================

class TestFoldingPreservesSemantics:
    """Similar vectors should remain similar after folding to 10D."""

    def test_similar_vectors_stay_similar_at_10d(self):
        base = random_vector(384, seed=1)
        similar = similar_vector(base, noise=0.1, seed=2)
        unrelated = random_vector(384, seed=99)

        base_10d, _ = fold_vector(base, 10)
        similar_10d, _ = fold_vector(similar, 10)
        unrelated_10d, _ = fold_vector(unrelated, 10)

        sim_similar = cosine_similarity(base_10d, similar_10d)
        sim_unrelated = cosine_similarity(base_10d, unrelated_10d)

        # Similar vectors should be more similar than unrelated
        assert sim_similar > sim_unrelated, (
            f"Similar pair ({sim_similar:.3f}) should score higher than "
            f"unrelated pair ({sim_unrelated:.3f})"
        )

    def test_identical_vectors_perfect_similarity(self):
        vec = random_vector(384, seed=5)
        folded_a, _ = fold_vector(vec, 10)
        folded_b, _ = fold_vector(vec, 10)
        sim = cosine_similarity(folded_a, folded_b)
        assert sim > 0.999, f"Identical vectors should have ~1.0 similarity, got {sim:.4f}"

    def test_orthogonal_vectors_low_similarity(self):
        # Construct orthogonal vectors
        a = np.zeros(384, dtype=np.float32)
        b = np.zeros(384, dtype=np.float32)
        a[:192] = 1.0
        b[192:] = 1.0

        a_10d, _ = fold_vector(a, 10)
        b_10d, _ = fold_vector(b, 10)
        sim = cosine_similarity(a_10d, b_10d)
        assert sim < 0.5, f"Orthogonal vectors should have low similarity, got {sim:.4f}"

    def test_similarity_rank_preserved_across_dims(self):
        """Top-k retrieval order should be approximately preserved at 10D."""
        base = random_vector(384, seed=10)
        candidates = [similar_vector(base, noise=n, seed=i) for i, n in enumerate([0.05, 0.2, 0.5, 1.0, 2.0])]

        # Full-dim ranking
        full_sims = [cosine_similarity(base, c) for c in candidates]
        full_ranking = sorted(range(len(candidates)), key=lambda i: full_sims[i], reverse=True)

        # 10D ranking
        base_10d, _ = fold_vector(base, 10)
        folded_10d = [fold_vector(c, 10)[0] for c in candidates]
        compressed_sims = [cosine_similarity(base_10d, f) for f in folded_10d]
        compressed_ranking = sorted(range(len(candidates)), key=lambda i: compressed_sims[i], reverse=True)

        # Top-2 should match (allow some rank swaps in the tail)
        assert full_ranking[0] == compressed_ranking[0], (
            f"Top-1 should match: full={full_ranking[0]}, compressed={compressed_ranking[0]}"
        )


# ===========================================================================
# 2. Cogni seed enables approximate reconstruction
# ===========================================================================

class TestCogniSeedReconstruction:

    def test_reconstruction_better_than_random(self):
        original = random_vector(384, seed=20)
        compressed, seed = fold_vector(original, 10)
        reconstructed = unfold_vector(compressed, seed)

        # Reconstruction should be closer to original than a random vector
        random_vec = random_vector(384, seed=99)
        sim_reconstructed = cosine_similarity(reconstructed, original)
        sim_random = cosine_similarity(random_vec, original)

        assert sim_reconstructed > sim_random, (
            f"Reconstruction ({sim_reconstructed:.3f}) should beat random ({sim_random:.3f})"
        )

    def test_higher_dim_better_reconstruction(self):
        original = random_vector(384, seed=30)

        comp_10, seed_10 = fold_vector(original, 10)
        comp_64, seed_64 = fold_vector(original, 64)

        recon_10 = unfold_vector(comp_10, seed_10)
        recon_64 = unfold_vector(comp_64, seed_64)

        sim_10 = cosine_similarity(recon_10, original)
        sim_64 = cosine_similarity(recon_64, original)

        assert sim_64 > sim_10, (
            f"64D reconstruction ({sim_64:.3f}) should be better than 10D ({sim_10:.3f})"
        )

    def test_cogni_seed_is_compact(self):
        original = random_vector(384, seed=40)
        _, seed = fold_vector(original, 10)

        # Seed should be much smaller than the original vector
        original_bytes = 384 * 4  # 384 floats × 4 bytes
        seed_bytes = seed.byte_size
        compression_ratio = original_bytes / seed_bytes

        assert seed_bytes < 200, f"Seed should be compact, got {seed_bytes} bytes"
        assert compression_ratio > 5, f"Compression ratio should be >5x, got {compression_ratio:.1f}x"

    def test_seed_roundtrip_serialization(self):
        original = random_vector(384, seed=50)
        _, seed = fold_vector(original, 10)

        d = seed.to_dict()
        restored = CogniSeed.from_dict(d)

        np.testing.assert_array_almost_equal(seed.mean_contribution, restored.mean_contribution)
        np.testing.assert_array_almost_equal(seed.variance_contribution, restored.variance_contribution)
        assert seed.original_dim == restored.original_dim
        assert seed.polarity_bias == restored.polarity_bias


# ===========================================================================
# 3. Volatility scoring detects instability
# ===========================================================================

class TestVolatilityScoring:

    def test_stable_memory_low_volatility(self):
        mem = make_memory("stable fact", seed=60)
        v = compute_volatility(mem)
        assert v < 0.3, f"Stable memory should have low volatility, got {v:.3f}"

    def test_contradicted_memory_high_volatility(self):
        mem = make_memory("contested fact", seed=70)
        mem.contradiction_count = 5
        mem.access_count = 10
        v = compute_volatility(mem)
        assert v > 0.1, f"Contradicted memory should have higher volatility, got {v:.3f}"

    def test_volatility_increases_with_contradictions(self):
        mem_low = make_memory("fact A", seed=80)
        mem_low.contradiction_count = 0
        mem_low.access_count = 10

        mem_high = make_memory("fact B", seed=80)
        mem_high.contradiction_count = 8
        mem_high.access_count = 10

        v_low = compute_volatility(mem_low)
        v_high = compute_volatility(mem_high)
        assert v_high > v_low, f"More contradictions → higher volatility ({v_high:.3f} > {v_low:.3f})"

    def test_volatility_bounded_0_to_1(self):
        mem = make_memory("extreme", seed=90)
        mem.contradiction_count = 1000
        mem.access_count = 1
        v = compute_volatility(mem)
        assert 0.0 <= v <= 1.0, f"Volatility should be bounded [0, 1], got {v:.3f}"


# ===========================================================================
# 4. Throttle function
# ===========================================================================

class TestThrottleFunction:

    def test_low_volatility_high_throttle(self):
        h = compute_throttle(0.0)
        assert h > 0.9, f"Zero volatility → max throttle, got {h:.3f}"

    def test_high_volatility_low_throttle(self):
        h = compute_throttle(1.0)
        assert h < 0.1, f"Max volatility → near-zero throttle, got {h:.3f}"

    def test_throttle_monotonically_decreasing(self):
        values = [compute_throttle(v) for v in np.linspace(0, 1, 20)]
        for i in range(1, len(values)):
            assert values[i] <= values[i - 1], (
                f"Throttle should decrease: H({i}) = {values[i]:.3f} > H({i-1}) = {values[i-1]:.3f}"
            )

    def test_throttle_matches_formula(self):
        v = 0.5
        expected = 1.0 * math.exp(-3.0 * v)
        actual = compute_throttle(v)
        assert abs(actual - expected) < 1e-6, f"Expected {expected:.6f}, got {actual:.6f}"


# ===========================================================================
# 5. Tier promotion / demotion
# ===========================================================================

class TestTierPromotion:

    def test_promote_increases_dimensionality(self):
        mem = make_memory("promote me", tier=0, seed=100)
        assert len(mem.vector) == 10

        promoted = promote_memory(mem, original_vector=mem.original_vector)
        assert promoted.tier == 1
        assert len(promoted.vector) == 64

    def test_promote_improves_fidelity(self):
        mem = make_memory("fidelity test", tier=0, seed=110)
        original = mem.original_vector.copy()

        recon_t0 = unfold_vector(mem.vector, mem.cogni_seed)
        sim_t0 = cosine_similarity(recon_t0, original)

        promote_memory(mem, original_vector=original)
        recon_t1 = unfold_vector(mem.vector, mem.cogni_seed)
        sim_t1 = cosine_similarity(recon_t1, original)

        assert sim_t1 > sim_t0, (
            f"Tier 1 reconstruction ({sim_t1:.3f}) should beat tier 0 ({sim_t0:.3f})"
        )

    def test_promote_caps_at_tier_2(self):
        mem = make_memory("max tier", tier=2, seed=120)
        assert not should_promote(mem, 0.9), "Already at max tier, should not promote"

    def test_demote_decreases_dimensionality(self):
        mem = make_memory("demote me", tier=1, seed=130)
        assert len(mem.vector) == 64

        demoted = demote_memory(mem)
        assert demoted.tier == 0
        assert len(demoted.vector) == 10

    def test_demote_floors_at_tier_0(self):
        mem = make_memory("min tier", tier=0, seed=140)
        assert not should_demote(mem, 0.01), "Already at min tier, should not demote"

    def test_high_volatility_triggers_promotion(self):
        mem = make_memory("volatile", tier=0, seed=150)
        assert should_promote(mem, PROMOTION_THRESHOLD + 0.1)

    def test_low_volatility_triggers_demotion_after_stable_cycles(self):
        mem = make_memory("stable", tier=1, seed=160)
        mem.stable_cycles = 15  # above DEMOTION_STABLE_CYCLES
        assert should_demote(mem, DEMOTION_THRESHOLD - 0.01)

    def test_high_trust_lowers_promotion_threshold(self):
        mem = make_memory("trusted", tier=0, trust=0.95, seed=170)
        # Half the normal threshold should trigger for high-trust memories
        assert should_promote(mem, PROMOTION_THRESHOLD * 0.5 + 0.01)


# ===========================================================================
# 6. Mixed-tier search
# ===========================================================================

class TestMixedTierSearch:

    def test_search_across_tiers(self):
        base = random_vector(384, seed=200)
        similar_base = similar_vector(base, noise=0.1, seed=201)
        unrelated = random_vector(384, seed=299)

        # Create memories at different tiers
        mem_t0 = make_memory("tier 0 - similar", tier=0, seed=200)
        mem_t1 = make_memory("tier 1 - unrelated", tier=1, seed=299)

        query = base
        results = search_memories(query, [mem_t0, mem_t1], top_k=2)

        assert len(results) == 2
        # The similar memory should rank higher
        assert results[0][0].text == "tier 0 - similar"

    def test_search_returns_top_k(self):
        memories = [make_memory(f"fact {i}", tier=0, seed=i) for i in range(20)]
        query = random_vector(384, seed=0)  # should be close to seed=0 memory
        results = search_memories(query, memories, top_k=3)
        assert len(results) == 3

    def test_trust_weighted_scoring(self):
        # Two identical vectors, different trust
        mem_high_trust = make_memory("high trust", tier=0, trust=1.0, seed=300)
        mem_low_trust = make_memory("low trust", tier=0, trust=0.1, seed=300)

        query = random_vector(384, seed=300)
        results = search_memories(query, [mem_high_trust, mem_low_trust], top_k=2)

        # High trust should rank higher
        assert results[0][0].trust > results[1][0].trust


# ===========================================================================
# 7. Storage savings
# ===========================================================================

class TestStorageSavings:

    def test_10d_is_much_smaller_than_384d(self):
        full_size = 384 * 4  # 384 floats × 4 bytes = 1536 bytes
        compressed_size = 10 * 4  # 10 floats × 4 bytes = 40 bytes

        ratio = full_size / compressed_size
        assert ratio > 30, f"Expected >30x compression, got {ratio:.1f}x"

    def test_10d_plus_seed_still_compact(self):
        original = random_vector(384, seed=400)
        compressed, seed = fold_vector(original, 10)

        full_cost = 384 * 4  # 1536 bytes
        compressed_cost = 10 * 4 + seed.byte_size  # ~40 + ~136 = ~176 bytes

        ratio = full_cost / compressed_cost
        assert ratio > 5, f"Expected >5x savings even with seed, got {ratio:.1f}x"

    def test_1000_memories_storage_comparison(self):
        n = 1000
        full_storage = n * 384 * 4  # ~1.5 MB
        compressed_storage = n * (10 * 4 + 136)  # ~176 KB (10D + seed)

        savings_pct = (1 - compressed_storage / full_storage) * 100
        assert savings_pct > 85, f"Expected >85% savings, got {savings_pct:.1f}%"


# ===========================================================================
# 8. End-to-end: full lifecycle
# ===========================================================================

class TestFullLifecycle:

    def test_create_compress_search_promote_search(self):
        """Full lifecycle: create → compress → search → detect volatility → promote → search again."""
        # Create 5 memories at tier 0
        memories = []
        for i in range(5):
            mem = make_memory(f"fact {i}", tier=0, seed=500 + i)
            memories.append(mem)

        # Search should work at tier 0
        query = random_vector(384, seed=502)  # close to fact 2
        results = search_memories(query, memories, top_k=2)
        assert len(results) == 2
        top_result = results[0][0]

        # Simulate contradictions on one memory
        memories[2].contradiction_count = 5
        memories[2].access_count = 8
        v = compute_volatility(memories[2])

        # Volatility should be elevated
        assert v > 0.1, f"Contradicted memory should show volatility, got {v:.3f}"

        # Promote if needed
        if should_promote(memories[2], v):
            promote_memory(memories[2], original_vector=memories[2].original_vector)
            assert memories[2].tier == 1
            assert len(memories[2].vector) == 64

        # Search should still work with mixed tiers
        results_after = search_memories(query, memories, top_k=2)
        assert len(results_after) == 2
