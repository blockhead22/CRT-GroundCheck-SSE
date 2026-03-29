"""
Four-Arm Memory Protection Experiment

Tests four strategies for protecting critical memories:
  Arm 1: Baseline (uniform 3-bit)
  Arm 2: Bit allocation (sensitivity-ranked 2/3/4-bit) — control, expected to lose
  Arm 3: Shadow cache (3-bit for all + full-precision shadow for top-risk)
  Arm 4: Alias protection (3-bit for all + paraphrase embeddings for top-risk)

Evaluated on CRITICAL FACT RECALL, not mean recall.

Key insight from prior experiments: bit-level redistribution fails because
MemQuant's quality curve is concave (Jensen's inequality). The real lever
is discontinuous protection — shadow copies or alias routes that create
categorical separation between ordinary and critical memories.
"""

import json
import os
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from personal_agent.memory_compression import quantize_vector, dequantize_vector


# ---------------------------------------------------------------------------
# Memory atom extraction from CRT memories
# ---------------------------------------------------------------------------

@dataclass
class MemoryAtom:
    """A memory with risk classification."""
    memory_id: str
    text: str
    vector: np.ndarray
    trust: float
    kind: str
    source: str
    contradiction_count: int
    access_count: int
    stable_cycles: int
    risk_score: float = 0.0
    is_critical: bool = False


def compute_risk(m: MemoryAtom) -> float:
    """Compute risk score: how bad is it if we lose this memory?"""
    # Kind-based criticality
    KIND_CRITICALITY = {
        "identity_constant": 1.0,
        "user_fact": 0.9,
        "preference": 0.7,
        "narrative_note": 0.75,
        "hypothesis": 0.3,
        "observation": 0.15,
        "ops": 0.1,
        "self_model": 0.05,
    }
    criticality = KIND_CRITICALITY.get(m.kind, 0.15)

    # Trust amplifies risk (high-trust facts are more costly to lose)
    trust_weight = m.trust

    # Access frequency = query likelihood proxy
    access_weight = min(1.0, m.access_count / 15.0)

    # Contradiction involvement increases irreversibility
    contradiction_weight = min(1.0, m.contradiction_count * 0.5)

    # Source credibility
    SOURCE_WEIGHT = {"user": 1.0, "external": 0.8, "system": 0.3, "fallback": 0.1, "self_reflection": 0.5}
    source_weight = SOURCE_WEIGHT.get(m.source, 0.3)

    # Stability reduces risk (stable = less likely to cause harm if slightly degraded)
    stability_discount = min(0.3, m.stable_cycles / 100.0)

    risk = (
        0.30 * criticality
        + 0.25 * trust_weight
        + 0.15 * access_weight
        + 0.10 * contradiction_weight
        + 0.10 * source_weight
        - 0.10 * stability_discount
    )
    return max(0.0, min(1.0, risk))


# ---------------------------------------------------------------------------
# Paraphrase generation for alias protection
# ---------------------------------------------------------------------------

def generate_paraphrases(text: str, vector: np.ndarray, n: int = 2) -> List[np.ndarray]:
    """Generate paraphrase embeddings for alias protection.

    Since we can't call an LLM from a benchmark script, we use a
    deterministic perturbation strategy:
      1. Terse form: embed just the key facts (first sentence or clause)
      2. Question form: embed as if someone were asking about this fact

    In production this would use an LLM to generate real paraphrases.
    """
    from personal_agent.embeddings import encode_text

    paraphrases = []

    # Terse form: first sentence only
    first_sentence = text.split(".")[0].strip() + "."
    if len(first_sentence) > 15 and first_sentence != text.strip():
        try:
            v = np.array(encode_text(first_sentence), dtype=np.float32)
            paraphrases.append(v)
        except Exception:
            pass

    # Question form: "What about [key topic]?"
    # Extract key noun phrases heuristically
    words = text.split()
    if len(words) > 5:
        # Take the subject (skip "Nick" or similar name)
        key_phrase = " ".join(words[1:6]) if words[0].lower() in ("nick", "nick's", "the", "a", "an") else " ".join(words[:5])
        question = f"What about {key_phrase}?"
        try:
            v = np.array(encode_text(question), dtype=np.float32)
            paraphrases.append(v)
        except Exception:
            pass

    # If we still need more, use light perturbation (noise + re-normalize)
    while len(paraphrases) < n:
        rng = np.random.RandomState(hash(text) % (2**31) + len(paraphrases))
        noise = rng.randn(len(vector)).astype(np.float32) * 0.08
        perturbed = vector + noise
        perturbed = perturbed / (np.linalg.norm(perturbed) + 1e-8)
        paraphrases.append(perturbed)

    return paraphrases[:n]


# ---------------------------------------------------------------------------
# Compression helpers
# ---------------------------------------------------------------------------

def compress_3bit(vector: np.ndarray) -> np.ndarray:
    """Compress to 3-bit and reconstruct."""
    try:
        indices, meta = quantize_vector(vector, 3)
        return dequantize_vector(indices, meta)
    except Exception:
        return vector


def compute_bytes_for_arm(n_total: int, n_critical: int, arm: str) -> int:
    """Estimate total storage bytes for an arm."""
    base_bytes = 152  # 3-bit per vector
    full_bytes = 384 * 4  # float32

    if arm == "baseline":
        return n_total * base_bytes
    elif arm == "bit_alloc":
        # 20% at 4-bit (200), 60% at 3-bit (152), 20% at 2-bit (104)
        return int(n_total * 0.2 * 200 + n_total * 0.6 * 152 + n_total * 0.2 * 104)
    elif arm == "shadow":
        # All at 3-bit + critical at full precision
        return n_total * base_bytes + n_critical * full_bytes
    elif arm == "alias":
        # All at 3-bit + critical get 2 extra vectors at 3-bit
        return n_total * base_bytes + n_critical * 2 * base_bytes
    return n_total * base_bytes


# ---------------------------------------------------------------------------
# Benchmark
# ---------------------------------------------------------------------------

def run_experiment():
    print("=" * 70)
    print("  FOUR-ARM MEMORY PROTECTION EXPERIMENT")
    print("  Baseline | Bit Alloc | Shadow Cache | Alias Protection")
    print("=" * 70)

    db_path = str(PROJECT_ROOT / "personal_agent" / "crt_memory_shared.db")

    # ── Load memories ─────────────────────────────────────────────
    import sqlite3
    conn = sqlite3.connect(db_path)
    rows = conn.execute("""
        SELECT memory_id, text, vector_json, trust, kind, source,
               contradiction_count, stable_cycles, access_count
        FROM memories
        WHERE deprecated = 0 AND vector_json IS NOT NULL AND LENGTH(text) > 10
        ORDER BY trust DESC
    """).fetchall()
    conn.close()

    memories: List[MemoryAtom] = []
    for mid, text, vj, trust, kind, source, cc, sc, ac in rows:
        try:
            vec = np.array(json.loads(vj), dtype=np.float32)
            if np.linalg.norm(vec) == 0:
                continue
            memories.append(MemoryAtom(
                memory_id=mid, text=text or "", vector=vec,
                trust=trust or 0.0,
                kind=(kind or "observation").strip().lower(),
                source=(source or "system").strip().lower(),
                contradiction_count=int(cc or 0),
                stable_cycles=int(sc or 0),
                access_count=int(ac or 0),
            ))
        except Exception:
            continue

    print(f"\n  Loaded {len(memories)} memory atoms")

    # ── Compute risk scores ───────────────────────────────────────
    for m in memories:
        m.risk_score = compute_risk(m)

    risks = [m.risk_score for m in memories]
    print(f"  Risk: min={min(risks):.3f}, max={max(risks):.3f}, mean={np.mean(risks):.3f}")

    # Top 3% are "critical"
    risk_threshold = np.percentile(risks, 97)
    for m in memories:
        m.is_critical = m.risk_score >= risk_threshold

    critical = [m for m in memories if m.is_critical]
    non_critical = [m for m in memories if not m.is_critical]
    print(f"  Critical memories (top 3%): {len(critical)}")
    print(f"  Non-critical: {len(non_critical)}")

    print(f"\n  Critical memories:")
    for m in sorted(critical, key=lambda x: -x.risk_score)[:10]:
        print(f"    risk={m.risk_score:.3f} trust={m.trust:.2f} kind={m.kind:20s} | {m.text[:60]}")

    # ── Build query set: queries that SHOULD hit critical memories ──
    print("\n  Building query set...")

    # Generate queries from critical memory texts (the queries that matter)
    from personal_agent.embeddings import encode_text

    critical_queries = []
    critical_query_target_ids = []

    for m in critical:
        # Query = the question someone would ask to retrieve this memory
        words = m.text.split()
        if len(words) > 3:
            query_text = " ".join(words[:8]) + "?"
        else:
            query_text = m.text
        try:
            qvec = np.array(encode_text(query_text), dtype=np.float32)
            critical_queries.append(qvec)
            critical_query_target_ids.append(m.memory_id)
        except Exception:
            pass

    # Also add some generic queries (non-critical) for overall recall
    rng = np.random.RandomState(42)
    generic_indices = rng.choice(len(non_critical), size=min(100, len(non_critical)), replace=False)
    generic_queries = []
    generic_target_ids = []
    for i in generic_indices:
        m = non_critical[i]
        try:
            qvec = np.array(encode_text(m.text[:100]), dtype=np.float32)
            generic_queries.append(qvec)
            generic_target_ids.append(m.memory_id)
        except Exception:
            pass

    all_queries = critical_queries + generic_queries
    all_target_ids = critical_query_target_ids + generic_target_ids
    is_critical_query = [True] * len(critical_queries) + [False] * len(generic_queries)

    print(f"  Critical queries: {len(critical_queries)}")
    print(f"  Generic queries: {len(generic_queries)}")
    print(f"  Total queries: {len(all_queries)}")

    # ── Ground truth: full 384D retrieval ─────────────────────────
    print("\n  Computing ground truth...")
    K = 10
    all_vecs = np.array([m.vector for m in memories])
    all_ids = [m.memory_id for m in memories]
    all_norms = all_vecs / (np.linalg.norm(all_vecs, axis=1, keepdims=True) + 1e-8)

    gt_top_k = []
    for q in all_queries:
        q_norm = q / (np.linalg.norm(q) + 1e-8)
        sims = all_norms @ q_norm
        top_indices = np.argsort(-sims)[:K]
        gt_top_k.append([all_ids[i] for i in top_indices])

    # ── ARM 1: Baseline (uniform 3-bit) ───────────────────────────
    print("\n  Running arms...")

    compressed_baseline = np.array([compress_3bit(m.vector) for m in memories])

    def retrieve(index_vecs, query, k=10):
        q_norm = query / (np.linalg.norm(query) + 1e-8)
        norms = index_vecs / (np.linalg.norm(index_vecs, axis=1, keepdims=True) + 1e-8)
        sims = norms @ q_norm
        top_idx = np.argsort(-sims)[:k]
        return top_idx

    def eval_arm(name, index_vecs, index_ids, extra_bytes=0):
        """Evaluate an arm's retrieval quality."""
        critical_recalls = []
        generic_recalls = []
        critical_target_found = []

        for qi, q in enumerate(all_queries):
            top_idx = retrieve(index_vecs, q, K)
            predicted_ids = set(index_ids[i] for i in top_idx)
            gt_ids = set(gt_top_k[qi])

            recall = len(predicted_ids & gt_ids) / K

            # Did we find the target memory?
            target_found = all_target_ids[qi] in predicted_ids

            if is_critical_query[qi]:
                critical_recalls.append(recall)
                critical_target_found.append(1.0 if target_found else 0.0)
            else:
                generic_recalls.append(recall)

        base_bytes = len(memories) * 152
        total_bytes = base_bytes + extra_bytes

        return {
            "name": name,
            "critical_recall": float(np.mean(critical_recalls)) if critical_recalls else 0.0,
            "critical_target_hit": float(np.mean(critical_target_found)) if critical_target_found else 0.0,
            "generic_recall": float(np.mean(generic_recalls)) if generic_recalls else 0.0,
            "total_bytes": total_bytes,
        }

    # Arm 1: Baseline
    baseline_ids = np.array(all_ids)
    r1 = eval_arm("Arm 1: Baseline (3-bit)", compressed_baseline, baseline_ids)
    print(f"    {r1['name']}: crit_recall={r1['critical_recall']:.3f}, target_hit={r1['critical_target_hit']:.3f}, bytes={r1['total_bytes']:,}")

    # ── ARM 2: Bit allocation (sensitivity-ranked) ────────────────
    ranked = sorted(range(len(memories)), key=lambda i: memories[i].risk_score, reverse=True)
    bit_alloc_vecs = np.zeros_like(all_vecs)
    n = len(memories)
    for rank, idx in enumerate(ranked):
        if rank < int(n * 0.20):
            bits = 4
        elif rank < int(n * 0.80):
            bits = 3
        else:
            bits = 2
        try:
            indices, meta = quantize_vector(memories[idx].vector, bits)
            bit_alloc_vecs[idx] = dequantize_vector(indices, meta)
        except Exception:
            bit_alloc_vecs[idx] = memories[idx].vector

    r2 = eval_arm("Arm 2: Bit allocation (2/3/4)", bit_alloc_vecs, baseline_ids)
    print(f"    {r2['name']}: crit_recall={r2['critical_recall']:.3f}, target_hit={r2['critical_target_hit']:.3f}, bytes={r2['total_bytes']:,}")

    # ── ARM 3: Shadow cache ───────────────────────────────────────
    # All at 3-bit, but critical memories also have full-precision copy
    shadow_vecs = list(compressed_baseline)
    shadow_ids = list(all_ids)

    for m in critical:
        # Add full-precision shadow entry
        shadow_vecs.append(m.vector)
        shadow_ids.append(m.memory_id)  # same ID = will match in retrieval

    shadow_vecs = np.array(shadow_vecs)
    shadow_ids = np.array(shadow_ids)
    shadow_extra_bytes = len(critical) * (384 * 4)  # full float32 per critical

    r3 = eval_arm("Arm 3: Shadow cache (3-bit + full critical)", shadow_vecs, shadow_ids, shadow_extra_bytes)
    print(f"    {r3['name']}: crit_recall={r3['critical_recall']:.3f}, target_hit={r3['critical_target_hit']:.3f}, bytes={r3['total_bytes']:,}")

    # ── ARM 4: Alias protection ───────────────────────────────────
    # All at 3-bit, but critical memories get 2 paraphrase embeddings
    alias_vecs = list(compressed_baseline)
    alias_ids = list(all_ids)

    print("    Generating paraphrase aliases for critical memories...")
    for m in critical:
        paraphrases = generate_paraphrases(m.text, m.vector, n=2)
        for pv in paraphrases:
            # Compress paraphrases to 3-bit too
            alias_vecs.append(compress_3bit(pv))
            alias_ids.append(m.memory_id)  # same ID = routes back to same memory

    alias_vecs = np.array(alias_vecs)
    alias_ids = np.array(alias_ids)
    alias_extra_bytes = len(critical) * 2 * 152  # 2 aliases at 3-bit each

    r4 = eval_arm("Arm 4: Alias protection (3-bit + 2 aliases)", alias_vecs, alias_ids, alias_extra_bytes)
    print(f"    {r4['name']}: crit_recall={r4['critical_recall']:.3f}, target_hit={r4['critical_target_hit']:.3f}, bytes={r4['total_bytes']:,}")

    # ── Results ───────────────────────────────────────────────────
    results = [r1, r2, r3, r4]

    print("\n" + "=" * 70)
    print("  RESULTS")
    print("=" * 70)
    print(f"\n  {'Arm':<50s} {'Crit Recall':>11s} {'Target Hit':>11s} {'Gen Recall':>11s} {'Bytes':>12s}")
    print(f"  {'-'*50} {'-'*11} {'-'*11} {'-'*11} {'-'*12}")

    for r in results:
        print(f"  {r['name']:<50s} {r['critical_recall']:>11.3f} {r['critical_target_hit']:>11.3f} "
              f"{r['generic_recall']:>11.3f} {r['total_bytes']:>12,}")

    # ── Delta vs baseline ─────────────────────────────────────────
    print(f"\n  === Delta vs Baseline ===")
    for r in results[1:]:
        dcr = r["critical_recall"] - r1["critical_recall"]
        dth = r["critical_target_hit"] - r1["critical_target_hit"]
        dgr = r["generic_recall"] - r1["generic_recall"]
        db = (r["total_bytes"] - r1["total_bytes"]) / r1["total_bytes"] * 100

        print(f"\n  {r['name']}:")
        print(f"    Critical recall: {dcr:+.4f} ({'BETTER' if dcr > 0.001 else 'worse' if dcr < -0.001 else 'same'})")
        print(f"    Target hit rate: {dth:+.4f} ({'BETTER' if dth > 0.001 else 'worse' if dth < -0.001 else 'same'})")
        print(f"    Generic recall:  {dgr:+.4f}")
        print(f"    Storage:         {db:+.1f}%")

    # ── Save ──────────────────────────────────────────────────────
    output = {
        "timestamp": time.time(),
        "num_memories": len(memories),
        "num_critical": len(critical),
        "risk_threshold": float(risk_threshold),
        "num_queries": len(all_queries),
        "num_critical_queries": len(critical_queries),
        "results": results,
    }
    out_path = Path(__file__).parent / "four_arm_results.json"
    with open(out_path, "w") as f:
        json.dump(output, f, indent=2)
    print(f"\n  Results saved to: {out_path}")


if __name__ == "__main__":
    run_experiment()
