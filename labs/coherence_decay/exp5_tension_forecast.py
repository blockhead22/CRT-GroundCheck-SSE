"""Experiment #5: Structural Tension Forecasting

Question: Does high tension predict user corrections?

Method:
1. Measure tension across all memory pairs in topic clusters
2. Record which memories have high tension scores
3. Track trust_log for corrections (slot_demotion, user_correction, tension_conflict)
4. Correlate: do high-tension memories get corrected more often?

If tension predicts corrections → the tension meter is a genuine early warning system.
If tension doesn't predict → it's post-hoc storytelling.

This experiment reads existing data. No new infrastructure needed.
The tension meter and trust_log are already running.
"""

import json
import math
import sqlite3
import sys
import time
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Tuple

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "personal_agent"))

import builtins
_real_open = builtins.open

MEMORY_DB = r"D:\AI_round2\personal_agent\crt_memory_shared.db"
LOG_FILE = Path(__file__).parent / "results" / "raw" / "exp5_tension_forecast.jsonl"


def p(msg):
    print(str(msg).encode("ascii", "replace").decode("ascii"), flush=True)


def log(entry):
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    with _real_open(LOG_FILE, "a") as f:
        f.write(json.dumps(entry, default=str) + "\n")


def load_memories():
    """Load all active memories with vectors."""
    conn = sqlite3.connect(MEMORY_DB, timeout=30.0)
    conn.row_factory = sqlite3.Row
    rows = conn.execute("""
        SELECT memory_id, text, trust, confidence, source, timestamp, vector_json, deprecated
        FROM memories WHERE deprecated = 0
        ORDER BY timestamp DESC
    """).fetchall()
    conn.close()

    memories = []
    for row in rows:
        vec = []
        try:
            vec = json.loads(row["vector_json"])
        except:
            pass
        memories.append({
            "memory_id": row["memory_id"],
            "text": row["text"] or "",
            "trust": float(row["trust"] or 0.0),
            "confidence": float(row["confidence"] or 0.0),
            "source": row["source"] or "",
            "timestamp": float(row["timestamp"] or 0.0),
            "vector": np.array(vec, dtype=np.float32) if vec else None,
        })
    return memories


def load_trust_log():
    """Load all trust changes — these are the 'corrections' we're predicting."""
    conn = sqlite3.connect(MEMORY_DB, timeout=30.0)
    conn.row_factory = sqlite3.Row
    rows = conn.execute("""
        SELECT memory_id, timestamp, old_trust, new_trust, reason
        FROM trust_log
        ORDER BY timestamp DESC
    """).fetchall()
    conn.close()

    return [{
        "memory_id": row["memory_id"],
        "timestamp": float(row["timestamp"] or 0.0),
        "old_trust": float(row["old_trust"] or 0.0),
        "new_trust": float(row["new_trust"] or 0.0),
        "reason": row["reason"] or "",
        "delta": float(row["new_trust"] or 0.0) - float(row["old_trust"] or 0.0),
    } for row in rows]


def load_contradictions():
    """Load contradiction ledger entries."""
    conn = sqlite3.connect(MEMORY_DB, timeout=30.0)
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute("""
            SELECT ledger_id, old_memory_id, new_memory_id, status, summary, timestamp
            FROM contradictions
            ORDER BY timestamp DESC
        """).fetchall()
    except:
        rows = []
    conn.close()

    return [{
        "old_id": row["old_memory_id"],
        "new_id": row["new_memory_id"],
        "status": row["status"],
        "summary": row["summary"] or "",
        "timestamp": float(row["timestamp"] or 0.0),
    } for row in rows]


def cosine_sim(a, b):
    if a is None or b is None or len(a) == 0 or len(b) == 0:
        return 0.0
    dot = float(np.dot(a, b))
    na = float(np.linalg.norm(a))
    nb = float(np.linalg.norm(b))
    if na == 0 or nb == 0:
        return 0.0
    return dot / (na * nb)


def measure_tension_field(memories):
    """Measure tension for every memory based on its neighborhood."""
    p("  Computing pairwise tensions...")

    # For each memory, find its top-5 neighbors and compute tension indicators
    tension_scores = {}
    for i, mem_a in enumerate(memories):
        if mem_a["vector"] is None:
            continue

        # Find neighbors
        neighbors = []
        for j, mem_b in enumerate(memories):
            if i == j or mem_b["vector"] is None:
                continue
            sim = cosine_sim(mem_a["vector"], mem_b["vector"])
            if sim > 0.5:
                neighbors.append((mem_b, sim))

        neighbors.sort(key=lambda x: x[1], reverse=True)
        neighbors = neighbors[:5]

        if not neighbors:
            tension_scores[mem_a["memory_id"]] = {
                "tension": 0.0,
                "trust_variance": 0.0,
                "neighbor_count": 0,
                "avg_similarity": 0.0,
                "trust_delta_max": 0.0,
            }
            continue

        # Tension indicators
        neighbor_trusts = [n["trust"] for n, _ in neighbors]
        trust_variance = float(np.var(neighbor_trusts)) if neighbor_trusts else 0.0
        trust_delta_max = max(abs(mem_a["trust"] - n["trust"]) for n, _ in neighbors)
        avg_sim = sum(s for _, s in neighbors) / len(neighbors)

        # Composite tension: high variance + high trust delta + high similarity = tension
        tension = trust_variance * trust_delta_max * avg_sim
        tension = min(1.0, tension * 10)  # Scale to 0-1

        tension_scores[mem_a["memory_id"]] = {
            "tension": round(tension, 4),
            "trust_variance": round(trust_variance, 4),
            "neighbor_count": len(neighbors),
            "avg_similarity": round(avg_sim, 4),
            "trust_delta_max": round(trust_delta_max, 4),
            "trust": mem_a["trust"],
            "text_preview": mem_a["text"][:80],
        }

    return tension_scores


def correlate(tension_scores, trust_log, contradictions):
    """Correlate tension with actual corrections."""
    p("  Correlating tension with corrections...")

    # Build sets of "corrected" memory IDs
    # ONLY count real corrections, not routine decay/recalibration
    REAL_CORRECTION_PREFIXES = (
        "slot_demotion",       # User corrected a fact
        "cascade",             # Belief backprop from contradiction
        "governance_bridge",   # Drift penalty
        "contested_cap",       # Contested memory
        "tension_conflict",    # Structural tension (our new system)
        "tension_refinement",  # Structural refinement
        "breathing_loop",      # Breathing loop action
    )
    NOISE_PREFIXES = (
        "compaction_decay",
        "Aligned",
        "trust_recalibration",
        "retrieval_reinforcement",
    )

    corrected_ids = set()
    correction_reasons = defaultdict(list)
    for entry in trust_log:
        reason = entry.get("reason", "") or ""
        is_real = any(reason.startswith(prefix) for prefix in REAL_CORRECTION_PREFIXES)
        if entry["delta"] < -0.05 and is_real:
            corrected_ids.add(entry["memory_id"])
            correction_reasons[entry["memory_id"]].append(reason)

    # Also add contradiction participants
    for c in contradictions:
        corrected_ids.add(c["old_id"])
        corrected_ids.add(c["new_id"])

    # Split memories into high-tension and low-tension groups
    scored_memories = [(mid, data) for mid, data in tension_scores.items() if data["tension"] > 0]
    if not scored_memories:
        return None

    # Sort by tension
    scored_memories.sort(key=lambda x: x[1]["tension"], reverse=True)

    # Top quartile = high tension, bottom quartile = low tension
    n = len(scored_memories)
    quartile = max(1, n // 4)

    high_tension = scored_memories[:quartile]
    low_tension = scored_memories[-quartile:]

    high_tension_corrected = sum(1 for mid, _ in high_tension if mid in corrected_ids)
    low_tension_corrected = sum(1 for mid, _ in low_tension if mid in corrected_ids)

    high_rate = high_tension_corrected / len(high_tension) if high_tension else 0
    low_rate = low_tension_corrected / len(low_tension) if low_tension else 0

    return {
        "total_memories": len(tension_scores),
        "memories_with_tension": n,
        "corrected_memories": len(corrected_ids),
        "high_tension_group": len(high_tension),
        "high_tension_corrected": high_tension_corrected,
        "high_tension_correction_rate": round(high_rate, 4),
        "low_tension_group": len(low_tension),
        "low_tension_corrected": low_tension_corrected,
        "low_tension_correction_rate": round(low_rate, 4),
        "ratio": round(high_rate / low_rate, 2) if low_rate > 0 else float("inf"),
    }


def run():
    if LOG_FILE.exists():
        LOG_FILE.unlink()

    p("=" * 60)
    p("EXPERIMENT #5: Structural Tension Forecasting")
    p("=" * 60)
    p(f"Memory DB: {MEMORY_DB}")
    p("Question: Does high tension predict corrections?")
    p("=" * 60)

    # Load data
    p("\nLoading memories...")
    memories = load_memories()
    p(f"  {len(memories)} active memories")

    p("Loading trust log...")
    trust_log = load_trust_log()
    p(f"  {len(trust_log)} trust changes recorded")

    p("Loading contradictions...")
    contradictions = load_contradictions()
    p(f"  {len(contradictions)} contradictions recorded")

    # Measure tension field
    p("\nMeasuring tension field...")
    tension_scores = measure_tension_field(memories)
    tensioned = {k: v for k, v in tension_scores.items() if v["tension"] > 0}
    p(f"  {len(tensioned)} memories with non-zero tension")

    # Show top 10 highest tension
    top_tension = sorted(tensioned.items(), key=lambda x: x[1]["tension"], reverse=True)[:10]
    p(f"\n  TOP 10 HIGHEST TENSION:")
    for mid, data in top_tension:
        corrected = mid in {e["memory_id"] for e in trust_log if e["delta"] < -0.05}
        icon = "!" if corrected else " "
        p(f"    [{icon}] tension={data['tension']:.4f} trust={data['trust']:.2f} delta_max={data['trust_delta_max']:.2f} | {data['text_preview']}")

    # Correlate
    p(f"\nCorrelating...")
    result = correlate(tension_scores, trust_log, contradictions)

    if result is None:
        p("  Not enough data to correlate.")
        return

    p(f"\n{'='*60}")
    p("RESULTS")
    p(f"{'='*60}")
    p(f"  Total memories analyzed: {result['total_memories']}")
    p(f"  Memories with tension: {result['memories_with_tension']}")
    p(f"  Memories ever corrected: {result['corrected_memories']}")
    p(f"")
    p(f"  HIGH TENSION group ({result['high_tension_group']} memories):")
    p(f"    Corrected: {result['high_tension_corrected']} ({result['high_tension_correction_rate']:.1%})")
    p(f"")
    p(f"  LOW TENSION group ({result['low_tension_group']} memories):")
    p(f"    Corrected: {result['low_tension_corrected']} ({result['low_tension_correction_rate']:.1%})")
    p(f"")
    p(f"  RATIO: {result['ratio']}x")
    p(f"")

    if result["ratio"] > 1.5:
        p(f"  FINDING: High-tension memories are {result['ratio']}x more likely to be corrected.")
        p(f"  Tension PREDICTS corrections. The meter is a genuine early warning system.")
    elif result["ratio"] > 1.0:
        p(f"  FINDING: Weak signal. High tension is slightly predictive ({result['ratio']}x).")
        p(f"  Tension has some value but isn't a strong predictor.")
    elif result["ratio"] == float("inf"):
        p(f"  FINDING: High-tension group has corrections, low-tension has none.")
        p(f"  Direction is correct but denominator is zero - need more data.")
    else:
        p(f"  FINDING: Tension does NOT predict corrections ({result['ratio']}x).")
        p(f"  The tension meter may be measuring noise, not signal.")

    # Log
    log({
        "experiment": "tension_forecasting",
        "timestamp": time.time(),
        "result": result,
        "top_tension": [(mid, data) for mid, data in top_tension],
    })

    p(f"\n  Log: {LOG_FILE}")


if __name__ == "__main__":
    run()
