"""Tests for MemQuant compression (rotation + Lloyd-Max quantization).

Tests:
  1. Round-trip cosine similarity at each bit depth
  2. Inner product preservation
  3. Determinism (same seed = same output)
  4. Zero vector handling
  5. Integration: run_compression_pass uses memquant format
  6. Backward compat: old fold-format memories still load
"""

import json
import math
import sqlite3
import time
import unittest

import numpy as np


# ---------------------------------------------------------------------------
# Helpers
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


def _insert_memory(conn, memory_id, text, trust=0.7, timestamp=None,
                   authority="confirmed", kind="observation", source="user",
                   vector_seed=42, stable_cycles=0, contradiction_count=0,
                   access_count=1, compression_tier=2):
    if timestamp is None:
        timestamp = time.time() - 86400 * 30
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

class TestMemQuantRoundTrip(unittest.TestCase):
    """Round-trip compression at each bit depth."""

    def test_3bit_cosine_above_threshold(self):
        from personal_agent.memory_compression import quantize_vector, dequantize_vector

        vec = _random_vector(384, seed=1)
        indices, metadata = quantize_vector(vec, bits=3)
        reconstructed = dequantize_vector(indices, metadata)

        cos_sim = float(np.dot(vec, reconstructed) / (
            np.linalg.norm(vec) * np.linalg.norm(reconstructed) + 1e-10))
        self.assertGreater(cos_sim, 0.93, f"3-bit round-trip cosine too low: {cos_sim}")

    def test_2bit_cosine_above_threshold(self):
        from personal_agent.memory_compression import quantize_vector, dequantize_vector

        vec = _random_vector(384, seed=2)
        indices, metadata = quantize_vector(vec, bits=2)
        reconstructed = dequantize_vector(indices, metadata)

        cos_sim = float(np.dot(vec, reconstructed) / (
            np.linalg.norm(vec) * np.linalg.norm(reconstructed) + 1e-10))
        self.assertGreater(cos_sim, 0.85, f"2-bit round-trip cosine too low: {cos_sim}")

    def test_4bit_cosine_above_threshold(self):
        from personal_agent.memory_compression import quantize_vector, dequantize_vector

        vec = _random_vector(384, seed=3)
        indices, metadata = quantize_vector(vec, bits=4)
        reconstructed = dequantize_vector(indices, metadata)

        cos_sim = float(np.dot(vec, reconstructed) / (
            np.linalg.norm(vec) * np.linalg.norm(reconstructed) + 1e-10))
        self.assertGreater(cos_sim, 0.97, f"4-bit round-trip cosine too low: {cos_sim}")

    def test_8bit_cosine_near_perfect(self):
        from personal_agent.memory_compression import quantize_vector, dequantize_vector

        vec = _random_vector(384, seed=4)
        indices, metadata = quantize_vector(vec, bits=8)
        reconstructed = dequantize_vector(indices, metadata)

        cos_sim = float(np.dot(vec, reconstructed) / (
            np.linalg.norm(vec) * np.linalg.norm(reconstructed) + 1e-10))
        self.assertGreater(cos_sim, 0.999, f"8-bit round-trip cosine too low: {cos_sim}")


class TestInnerProductPreservation(unittest.TestCase):
    """Inner product accuracy from compressed form."""

    def test_3bit_ip_correlation(self):
        from personal_agent.memory_compression import quantize_vector, quantized_inner_product

        rng = np.random.RandomState(123)
        true_ips = []
        est_ips = []
        for i in range(100):
            v1 = rng.randn(384).astype(np.float32)
            v1 /= np.linalg.norm(v1)
            v2 = rng.randn(384).astype(np.float32)
            v2 /= np.linalg.norm(v2)

            true_ip = float(np.dot(v1, v2))
            indices, metadata = quantize_vector(v2, bits=3)
            est_ip = quantized_inner_product(v1, indices, metadata)

            true_ips.append(true_ip)
            est_ips.append(est_ip)

        correlation = float(np.corrcoef(true_ips, est_ips)[0, 1])
        self.assertGreater(correlation, 0.95, f"IP correlation too low: {correlation}")


class TestDeterminism(unittest.TestCase):
    """Same input + same seed = same output."""

    def test_deterministic_compression(self):
        from personal_agent.memory_compression import quantize_vector

        vec = _random_vector(384, seed=7)
        indices1, meta1 = quantize_vector(vec, bits=3)
        indices2, meta2 = quantize_vector(vec, bits=3)

        np.testing.assert_array_equal(indices1, indices2)
        self.assertEqual(meta1["norm"], meta2["norm"])


class TestZeroVector(unittest.TestCase):
    """Zero vector should not crash."""

    def test_zero_vector_roundtrip(self):
        from personal_agent.memory_compression import quantize_vector, dequantize_vector

        vec = np.zeros(384, dtype=np.float32)
        indices, metadata = quantize_vector(vec, bits=3)
        reconstructed = dequantize_vector(indices, metadata)

        self.assertEqual(float(np.linalg.norm(reconstructed)), 0.0)


class TestCompressionPassMemQuant(unittest.TestCase):
    """Integration: run_compression_pass produces memquant-format data."""

    def test_demotion_uses_memquant(self):
        from personal_agent.memory_compression import run_compression_pass

        conn = _make_db()
        _insert_memory(
            conn, "mem_demote_mq", "The sky is blue",
            trust=0.2, stable_cycles=15, contradiction_count=0, access_count=5,
            timestamp=time.time() - 86400 * 30,
        )
        grace_cutoff = time.time() - 86400 * 7

        result = run_compression_pass(conn, grace_cutoff=grace_cutoff)
        self.assertEqual(result["folded"], 1)

        row = conn.execute(
            "SELECT compression_tier, compressed_vector_json, cogni_seed_json FROM memories WHERE memory_id = 'mem_demote_mq'"
        ).fetchone()
        self.assertLess(row[0], 2)
        self.assertIsNotNone(row[1])
        self.assertIsNotNone(row[2])

        # Verify memquant format
        seed = json.loads(row[2])
        self.assertEqual(seed["method"], "memquant")
        self.assertIn("bits", seed)
        self.assertIn("norm", seed)

        # Verify indices are valid uint8 values
        indices = json.loads(row[1])
        self.assertEqual(len(indices), 384)
        for idx in indices:
            self.assertGreaterEqual(idx, 0)
            self.assertLess(idx, 256)

    def test_memquant_volatile_memory_promotes(self):
        """A memquant-compressed memory with high contradictions should promote."""
        from personal_agent.memory_compression import run_compression_pass, quantize_vector

        conn = _make_db()
        vec = _random_vector(384, seed=42)
        indices, metadata = quantize_vector(vec, bits=2)

        conn.execute(
            """INSERT INTO memories
               (memory_id, vector_json, text, timestamp, confidence, trust,
                source, sse_mode, authority, kind,
                compression_tier, compressed_vector_json, cogni_seed_json,
                stable_cycles, contradiction_count, access_count)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            ("mem_volatile_mq", json.dumps(vec.tolist()), "Disputed fact",
             time.time() - 86400 * 30, 0.8, 0.2,
             "user", "L", "confirmed", "observation",
             0, json.dumps(indices.tolist()), json.dumps(metadata),
             0, 20, 10),
        )
        conn.commit()

        grace_cutoff = time.time() - 86400 * 7
        result = run_compression_pass(conn, grace_cutoff=grace_cutoff)
        self.assertEqual(result["unfolded"], 1)

        row = conn.execute(
            "SELECT compression_tier FROM memories WHERE memory_id = 'mem_volatile_mq'"
        ).fetchone()
        self.assertGreater(row[0], 0)


class TestBackwardCompat(unittest.TestCase):
    """Old fold-format memories should still work."""

    def test_legacy_fold_still_loads_in_compression_pass(self):
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
            ("mem_legacy", json.dumps(vec.tolist()), "Legacy memory",
             time.time() - 86400 * 30, 0.8, 0.2,
             "user", "L", "confirmed", "observation",
             0, json.dumps(compressed.tolist()), json.dumps(seed.to_dict()),
             0, 8, 10),
        )
        conn.commit()

        # Should not crash — legacy format detected and handled
        grace_cutoff = time.time() - 86400 * 7
        result = run_compression_pass(conn, grace_cutoff=grace_cutoff)
        # Legacy fold at tier 0 with contradictions should promote
        self.assertEqual(result["unfolded"], 1)

    def test_legacy_volatility_computation(self):
        """compute_volatility still works with CogniSeed objects."""
        from personal_agent.memory_compression import compute_volatility, fold_vector

        original = _random_vector(384, seed=5)
        compressed, seed = fold_vector(original, 64)
        v = compute_volatility(
            original_vector=original,
            compressed_vector=compressed,
            cogni_seed=seed,
            contradiction_count=0,
            access_count=10,
        )
        self.assertIsInstance(v, float)
        self.assertGreaterEqual(v, 0.0)
        self.assertLessEqual(v, 1.0)


class TestMemQuantVolatility(unittest.TestCase):
    """Volatility with memquant should be much lower than with fold."""

    def test_memquant_drift_lower_than_fold(self):
        from personal_agent.memory_compression import (
            compute_volatility, fold_vector, quantize_vector, dequantize_vector,
        )

        original = _random_vector(384, seed=10)

        # Fold to 10D (old method)
        compressed_fold, seed_fold = fold_vector(original, 10)
        v_fold = compute_volatility(
            original_vector=original,
            compressed_vector=compressed_fold,
            cogni_seed=seed_fold,
            contradiction_count=0,
            access_count=10,
        )

        # MemQuant at 3-bit (new method)
        indices, metadata = quantize_vector(original, bits=3)
        v_memquant = compute_volatility(
            original_vector=original,
            compressed_vector=indices,
            cogni_seed=metadata,
            contradiction_count=0,
            access_count=10,
        )

        self.assertLess(v_memquant, v_fold,
                        f"MemQuant volatility ({v_memquant}) should be < fold ({v_fold})")


if __name__ == "__main__":
    unittest.main()
