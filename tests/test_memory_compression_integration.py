"""Integration tests for adaptive memory compression (Phase 1).

Tests the full lifecycle:
  store -> age -> compress -> retrieve -> promote -> retrieve

Uses an in-memory SQLite database — no side effects on production data.
"""

import json
import math
import sqlite3
import time
import unittest

import numpy as np

# ---------------------------------------------------------------------------
# Helpers — minimal CRT memory table for testing
# ---------------------------------------------------------------------------

_SCHEMA = """
CREATE TABLE memories (
    memory_id TEXT PRIMARY KEY,
    vector_json TEXT NOT NULL,
    text TEXT NOT NULL,
    timestamp REAL NOT NULL,
    confidence REAL NOT NULL,
    trust REAL NOT NULL,
    source TEXT NOT NULL,
    sse_mode TEXT NOT NULL,
    context_json TEXT,
    tags_json TEXT,
    thread_id TEXT,
    deprecated INTEGER DEFAULT 0,
    deprecation_reason TEXT,
    fact_tuples TEXT,
    extraction_method TEXT DEFAULT 'regex',
    temporal_status TEXT DEFAULT 'active',
    valid_from REAL,
    valid_until REAL,
    domain_tags TEXT,
    authority TEXT DEFAULT 'confirmed',
    channel TEXT DEFAULT 'unknown',
    origin TEXT,
    kind TEXT DEFAULT 'observation',
    review_after REAL,
    source_kind TEXT DEFAULT 'principal',
    model_id TEXT,
    run_id TEXT,
    compression_tier INTEGER DEFAULT 2,
    compressed_vector_json TEXT,
    cogni_seed_json TEXT,
    stable_cycles INTEGER DEFAULT 0,
    contradiction_count INTEGER DEFAULT 0,
    access_count INTEGER DEFAULT 0
);
"""


def _make_db() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.executescript(_SCHEMA)
    return conn


def _random_vector(dim: int = 384, seed: int = 42) -> np.ndarray:
    rng = np.random.RandomState(seed)
    v = rng.randn(dim).astype(np.float32)
    return v / (np.linalg.norm(v) + 1e-8)


def _insert_memory(
    conn,
    memory_id: str,
    text: str,
    trust: float = 0.7,
    timestamp: float = None,
    authority: str = "confirmed",
    kind: str = "observation",
    source: str = "user",
    vector_seed: int = 42,
    stable_cycles: int = 0,
    contradiction_count: int = 0,
    access_count: int = 1,
    compression_tier: int = 2,
):
    if timestamp is None:
        timestamp = time.time() - 86400 * 30  # 30 days ago
    vec = _random_vector(384, seed=vector_seed)
    conn.execute(
        """INSERT INTO memories
           (memory_id, vector_json, text, timestamp, confidence, trust,
            source, sse_mode, authority, kind,
            compression_tier, stable_cycles, contradiction_count, access_count)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (memory_id, json.dumps(vec.tolist()), text, timestamp, 0.8, trust,
         source, "L", authority, kind,
         compression_tier, stable_cycles, contradiction_count, access_count),
    )
    conn.commit()
    return vec


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestFoldUnfold(unittest.TestCase):
    """Basic fold/unfold sanity."""

    def test_fold_preserves_similarity_rank(self):
        from personal_agent.memory_compression import fold_vector

        v1 = _random_vector(384, seed=1)
        v2 = v1 + np.random.RandomState(10).randn(384).astype(np.float32) * 0.02  # close
        v2 = v2 / (np.linalg.norm(v2) + 1e-8)
        v3 = _random_vector(384, seed=99)  # far

        f1, _ = fold_vector(v1, 10)
        f2, _ = fold_vector(v2, 10)
        f3, _ = fold_vector(v3, 10)

        sim_close = float(np.dot(f1, f2) / (np.linalg.norm(f1) * np.linalg.norm(f2) + 1e-8))
        sim_far = float(np.dot(f1, f3) / (np.linalg.norm(f1) * np.linalg.norm(f3) + 1e-8))
        self.assertGreater(sim_close, sim_far, "Folded similarity rank should be preserved")

    def test_unfold_beats_random(self):
        """Reconstruction at 64D should beat a random vector's similarity."""
        from personal_agent.memory_compression import fold_vector, unfold_vector

        original = _random_vector(384, seed=7)
        # Use 64D for this test — 10D reconstruction is too lossy for reliable comparison
        compressed, seed = fold_vector(original, 64)
        reconstructed = unfold_vector(compressed, seed)

        sim_recon = float(np.dot(original, reconstructed) / (
            np.linalg.norm(original) * np.linalg.norm(reconstructed) + 1e-8))
        # Average over multiple random vectors to avoid seed-dependent flukes
        sim_randoms = []
        for s in range(100, 110):
            rv = _random_vector(384, seed=s)
            sim_randoms.append(float(np.dot(original, rv) / (
                np.linalg.norm(original) * np.linalg.norm(rv) + 1e-8)))
        avg_random = sum(sim_randoms) / len(sim_randoms)

        self.assertGreater(sim_recon, avg_random, "Reconstruction should beat average random")

    def test_cogni_seed_roundtrip(self):
        from personal_agent.memory_compression import fold_vector, CogniSeed

        original = _random_vector(384, seed=3)
        _, seed = fold_vector(original, 10)
        d = seed.to_dict()
        restored = CogniSeed.from_dict(d)
        self.assertEqual(seed.original_dim, restored.original_dim)
        self.assertEqual(seed.target_dim, restored.target_dim)
        np.testing.assert_array_almost_equal(seed.mean_contribution, restored.mean_contribution)


class TestVolatility(unittest.TestCase):
    """V(t) computation."""

    def test_stable_memory_low_volatility(self):
        from personal_agent.memory_compression import compute_volatility, fold_vector, CogniSeed

        original = _random_vector(384, seed=5)
        compressed, seed = fold_vector(original, 10)
        v = compute_volatility(
            original_vector=original,
            compressed_vector=compressed,
            cogni_seed=seed,
            contradiction_count=0,
            access_count=10,
        )
        self.assertLess(v, 0.5, f"Stable memory volatility should be low, got {v}")

    def test_contradicted_memory_higher_volatility(self):
        from personal_agent.memory_compression import compute_volatility, fold_vector

        original = _random_vector(384, seed=5)
        compressed, seed = fold_vector(original, 10)
        v_stable = compute_volatility(
            original_vector=original,
            compressed_vector=compressed,
            cogni_seed=seed,
            contradiction_count=0,
            access_count=10,
        )
        v_contradicted = compute_volatility(
            original_vector=original,
            compressed_vector=compressed,
            cogni_seed=seed,
            contradiction_count=8,
            access_count=10,
        )
        self.assertGreater(v_contradicted, v_stable)


class TestProtection(unittest.TestCase):
    """Memory protection rules."""

    def test_locked_authority_protected(self):
        from personal_agent.memory_compression import is_protected, minimum_tier
        self.assertTrue(is_protected(kind="observation", authority="locked", source="user", trust=0.5))
        self.assertEqual(minimum_tier(kind="observation", authority="locked", source="user", trust=0.5), 2)

    def test_identity_constant_protected(self):
        from personal_agent.memory_compression import is_protected
        self.assertTrue(is_protected(kind="identity_constant", authority="confirmed", source="system", trust=0.5))

    def test_high_trust_user_min_tier_1(self):
        from personal_agent.memory_compression import minimum_tier
        self.assertEqual(minimum_tier(kind="observation", authority="confirmed", source="user", trust=0.9), 1)

    def test_low_trust_can_go_to_tier_0(self):
        from personal_agent.memory_compression import minimum_tier
        self.assertEqual(minimum_tier(kind="observation", authority="confirmed", source="fallback", trust=0.2), 0)


class TestCompressionPass(unittest.TestCase):
    """Integration test for run_compression_pass."""

    def test_low_trust_stable_memory_gets_demoted(self):
        from personal_agent.memory_compression import run_compression_pass

        conn = _make_db()
        _insert_memory(
            conn, "mem_old_stable", "The sky is blue",
            trust=0.2, stable_cycles=15, contradiction_count=0, access_count=5,
            timestamp=time.time() - 86400 * 30,
        )
        grace_cutoff = time.time() - 86400 * 7

        result = run_compression_pass(conn, grace_cutoff=grace_cutoff)
        self.assertEqual(result["folded"], 1, f"Expected 1 fold, got {result}")

        row = conn.execute(
            "SELECT compression_tier, compressed_vector_json, cogni_seed_json FROM memories WHERE memory_id = 'mem_old_stable'"
        ).fetchone()
        self.assertLess(row[0], 2, "Tier should be below 2 after demotion")
        self.assertIsNotNone(row[1], "compressed_vector_json should be set")
        self.assertIsNotNone(row[2], "cogni_seed_json should be set")

    def test_locked_memory_skipped(self):
        from personal_agent.memory_compression import run_compression_pass

        conn = _make_db()
        _insert_memory(
            conn, "mem_locked", "My name is Nick",
            trust=0.2, stable_cycles=20, authority="locked",
            timestamp=time.time() - 86400 * 30,
        )
        grace_cutoff = time.time() - 86400 * 7
        result = run_compression_pass(conn, grace_cutoff=grace_cutoff)
        self.assertEqual(result["skipped_protected"], 1)
        self.assertEqual(result["folded"], 0)

    def test_high_trust_memory_not_demoted(self):
        from personal_agent.memory_compression import run_compression_pass

        conn = _make_db()
        _insert_memory(
            conn, "mem_high_trust", "Important fact",
            trust=0.8, stable_cycles=20,
            timestamp=time.time() - 86400 * 30,
        )
        grace_cutoff = time.time() - 86400 * 7
        result = run_compression_pass(conn, grace_cutoff=grace_cutoff)
        self.assertEqual(result["folded"], 0)

    def test_volatile_compressed_memory_gets_promoted(self):
        """A compressed memory with high contradictions should promote."""
        from personal_agent.memory_compression import run_compression_pass, fold_vector

        conn = _make_db()
        vec = _random_vector(384, seed=42)
        compressed, seed = fold_vector(vec, 10)

        conn.execute(
            """INSERT INTO memories
               (memory_id, vector_json, text, timestamp, confidence, trust,
                source, sse_mode, authority, kind,
                compression_tier, compressed_vector_json, cogni_seed_json,
                stable_cycles, contradiction_count, access_count)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            ("mem_volatile", json.dumps(vec.tolist()), "Disputed fact",
             time.time() - 86400 * 30, 0.8, 0.2,
             "user", "L", "confirmed", "observation",
             0, json.dumps(compressed.tolist()), json.dumps(seed.to_dict()),
             0, 8, 10),
        )
        conn.commit()

        grace_cutoff = time.time() - 86400 * 7
        result = run_compression_pass(conn, grace_cutoff=grace_cutoff)
        self.assertEqual(result["unfolded"], 1, f"Expected 1 unfold, got {result}")

        row = conn.execute(
            "SELECT compression_tier FROM memories WHERE memory_id = 'mem_volatile'"
        ).fetchone()
        self.assertGreater(row[0], 0, "Tier should have increased after promotion")


class TestTierAwareRetrieval(unittest.TestCase):
    """Test that retrieval works across mixed tiers."""

    def test_compressed_memory_still_findable(self):
        from personal_agent.memory_compression import fold_vector

        conn = _make_db()
        # Insert a compressed memory at tier 0
        vec = _random_vector(384, seed=42)
        compressed, seed = fold_vector(vec, 10)

        conn.execute(
            """INSERT INTO memories
               (memory_id, vector_json, text, timestamp, confidence, trust,
                source, sse_mode, authority, kind,
                compression_tier, compressed_vector_json, cogni_seed_json,
                stable_cycles, contradiction_count, access_count)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            ("mem_compressed", json.dumps(vec.tolist()), "Compressed fact",
             time.time() - 86400 * 10, 0.8, 0.5,
             "user", "L", "confirmed", "observation",
             0, json.dumps(compressed.tolist()), json.dumps(seed.to_dict()),
             5, 0, 3),
        )
        conn.commit()

        # Search with same vector — should find it via folded comparison
        query = vec  # exact same vector
        query_folded, _ = fold_vector(query, 10)
        sim = float(np.dot(query_folded, compressed) / (
            np.linalg.norm(query_folded) * np.linalg.norm(compressed) + 1e-8
        ))
        self.assertGreater(sim, 0.9, f"Self-similarity at 10D should be high, got {sim}")


class TestFullLifecycle(unittest.TestCase):
    """End-to-end: store -> age -> compress -> retrieve -> contradict -> promote."""

    def test_lifecycle(self):
        from personal_agent.memory_compression import run_compression_pass, fold_vector

        conn = _make_db()
        vec = _insert_memory(
            conn, "mem_lifecycle", "Cats are mammals",
            trust=0.25, stable_cycles=0, contradiction_count=0,
            timestamp=time.time() - 86400 * 30,
        )

        grace_cutoff = time.time() - 86400 * 7

        # Step 1: Not enough stable cycles yet — should just tick
        result = run_compression_pass(conn, grace_cutoff=grace_cutoff)
        self.assertEqual(result["folded"], 0)

        # Step 2: Simulate 12 stable cycles
        conn.execute("UPDATE memories SET stable_cycles = 12 WHERE memory_id = 'mem_lifecycle'")
        conn.commit()

        result = run_compression_pass(conn, grace_cutoff=grace_cutoff)
        self.assertEqual(result["folded"], 1, f"Should fold after 12 stable cycles: {result}")

        # Verify compression happened
        row = conn.execute(
            "SELECT compression_tier, compressed_vector_json FROM memories WHERE memory_id = 'mem_lifecycle'"
        ).fetchone()
        self.assertEqual(row[0], 1)  # tier 2 -> tier 1 (64D)
        self.assertIsNotNone(row[1])

        # Step 3: Add contradictions -> promote back
        conn.execute(
            "UPDATE memories SET contradiction_count = 10, access_count = 10 WHERE memory_id = 'mem_lifecycle'"
        )
        conn.commit()

        result = run_compression_pass(conn, grace_cutoff=grace_cutoff)
        self.assertEqual(result["unfolded"], 1, f"Should unfold after contradictions: {result}")

        row = conn.execute(
            "SELECT compression_tier FROM memories WHERE memory_id = 'mem_lifecycle'"
        ).fetchone()
        self.assertEqual(row[0], 2, "Should be back at full fidelity")


class TestLogging(unittest.TestCase):
    """Verify log output uses the diamond prefix."""

    def test_log_messages_use_diamond(self):
        import logging
        from personal_agent.memory_compression import _log_fold, _log_pass_summary

        with self.assertLogs("personal_agent.memory_compression", level="INFO") as cm:
            _log_fold("mem_test12345", "test text", 2, 1, 0.05, 0.2)
            _log_pass_summary(10, 1, 0, 5, 2)

        # Check diamond appears in log output
        combined = "\n".join(cm.output)
        self.assertIn("\u25C7", combined, "Log should contain diamond prefix")
        self.assertIn("FOLD", combined)
        self.assertIn("COMPRESSION PASS", combined)


if __name__ == "__main__":
    unittest.main()
