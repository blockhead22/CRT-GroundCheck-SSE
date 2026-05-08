"""
Fidelity benchmark — produce a belief/speech-gap number.

Pulls real query/response pairs from the belief_speech log and runs
fidelity_mirror.check_fidelity over each, producing:
  - aggregate grounded vs ungrounded fractions (the "gap")
  - per-dimension distributions (belief_fidelity, request_alignment, factual_grounding)
  - correlation with the stored is_belief flag
  - a JSON dump and a matplotlib chart

This is the NLA-analog: a single number that quantifies how often the
system's spoken output is grounded in its belief state.
"""
from __future__ import annotations

import json
import random
import sqlite3
import sys
import time
from pathlib import Path
from statistics import mean, median, stdev

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from personal_agent.fidelity_mirror import check_fidelity  # noqa: E402

MEM_DB = ROOT / "personal_agent" / "crt_memory_shared.db"
OUT_DIR = Path(__file__).parent / "results"
OUT_DIR.mkdir(exist_ok=True)

SAMPLE_SIZE = 30
RANDOM_SEED = 42
MEM_BANK_SIZE = 30  # candidate memories per query


def fetch_pairs(n: int) -> list[dict]:
    """Sample N (query, response, is_belief, trust_avg) rows from belief_speech."""
    conn = sqlite3.connect(MEM_DB)
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        """
        SELECT entry_id, timestamp, query, response, is_belief, memory_ids_json, trust_avg
        FROM belief_speech
        WHERE length(query) > 10 AND length(response) > 30
        ORDER BY timestamp DESC
        LIMIT 500
        """
    ).fetchall()
    conn.close()
    pool = [dict(r) for r in rows]
    rng = random.Random(RANDOM_SEED)
    rng.shuffle(pool)
    return pool[:n]


def fetch_memory_bank(memory_ids_json: str | None, fallback_n: int = MEM_BANK_SIZE) -> list[dict]:
    """Resolve memory IDs from belief_speech; fall back to top-trust memories."""
    conn = sqlite3.connect(MEM_DB)
    conn.row_factory = sqlite3.Row
    mems: list[dict] = []
    try:
        if memory_ids_json:
            ids = json.loads(memory_ids_json)
            if ids:
                placeholders = ",".join("?" for _ in ids)
                rows = conn.execute(
                    f"SELECT memory_id, text, trust FROM memories WHERE memory_id IN ({placeholders})",
                    ids,
                ).fetchall()
                mems = [{"memory_id": r["memory_id"], "text": r["text"], "trust": r["trust"]} for r in rows]
        if len(mems) < 5:
            rows = conn.execute(
                "SELECT memory_id, text, trust FROM memories "
                "WHERE deprecated = 0 AND length(text) > 20 "
                "ORDER BY trust DESC LIMIT ?",
                (fallback_n,),
            ).fetchall()
            seen = {m["memory_id"] for m in mems}
            for r in rows:
                if r["memory_id"] not in seen:
                    mems.append({"memory_id": r["memory_id"], "text": r["text"], "trust": r["trust"]})
                if len(mems) >= fallback_n:
                    break
    finally:
        conn.close()
    return mems


def run() -> dict:
    pairs = fetch_pairs(SAMPLE_SIZE)
    print(f"[bench] Sampled {len(pairs)} query/response pairs")

    results = []
    t0 = time.perf_counter()
    for i, pair in enumerate(pairs, 1):
        mems = fetch_memory_bank(pair.get("memory_ids_json"))
        score = check_fidelity(pair["response"], pair["query"], mems)
        results.append({
            "entry_id": pair["entry_id"],
            "is_belief_stored": int(pair["is_belief"]),
            "trust_avg_stored": pair.get("trust_avg"),
            "belief_fidelity": score.belief_fidelity,
            "request_alignment": score.request_alignment,
            "factual_grounding": score.factual_grounding,
            "composite": score.composite,
            "passed": int(score.passed),
            "n_memories": len(mems),
            "latency_ms": score.latency_ms,
            "query": pair["query"][:120],
            "response_preview": pair["response"][:160],
        })
        if i % 5 == 0:
            print(f"  [{i}/{len(pairs)}] composite={score.composite:.2f} passed={score.passed}")
    elapsed = time.perf_counter() - t0

    # Aggregates
    composites = [r["composite"] for r in results]
    bf = [r["belief_fidelity"] for r in results]
    ra = [r["request_alignment"] for r in results]
    fg = [r["factual_grounding"] for r in results]
    pass_rate = sum(r["passed"] for r in results) / len(results)

    # The "belief/speech gap" — fraction of responses tagged ungrounded by stored flag,
    # vs fraction that fidelity_mirror flags as failed.
    stored_grounded = sum(1 for r in results if r["is_belief_stored"] == 1) / len(results)
    measured_grounded = pass_rate
    gap = abs(stored_grounded - measured_grounded)

    summary = {
        "n_samples": len(results),
        "elapsed_sec": round(elapsed, 1),
        "composite_mean": round(mean(composites), 3),
        "composite_median": round(median(composites), 3),
        "composite_stdev": round(stdev(composites) if len(composites) > 1 else 0.0, 3),
        "belief_fidelity_mean": round(mean(bf), 3),
        "request_alignment_mean": round(mean(ra), 3),
        "factual_grounding_mean": round(mean(fg), 3),
        "pass_rate": round(pass_rate, 3),
        "stored_grounded_rate": round(stored_grounded, 3),
        "measured_grounded_rate": round(measured_grounded, 3),
        "stored_vs_measured_gap": round(gap, 3),
        "headline": (
            f"{int(measured_grounded * 100)}% of responses grounded by fidelity_mirror; "
            f"{int(stored_grounded * 100)}% by stored is_belief flag — "
            f"gap = {int(gap * 100)}pp"
        ),
    }

    out = {"summary": summary, "results": results}
    out_path = OUT_DIR / f"fidelity_bench_{int(time.time())}.json"
    out_path.write_text(json.dumps(out, indent=2))
    print(f"\n[bench] Wrote {out_path}")
    print(f"[bench] HEADLINE: {summary['headline']}")
    print(json.dumps(summary, indent=2))

    # Chart
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt

        fig, axes = plt.subplots(1, 2, figsize=(12, 4.5))

        # Left: distribution histogram of composite scores
        axes[0].hist(composites, bins=15, color="#D4845C", edgecolor="#1a1714")
        axes[0].axvline(0.25, color="#D47058", linestyle="--", label="threshold (0.25)")
        axes[0].axvline(summary["composite_mean"], color="#5C9BD4", linestyle="-",
                        label=f"mean ({summary['composite_mean']:.2f})")
        axes[0].set_xlabel("Fidelity composite score")
        axes[0].set_ylabel("Count")
        axes[0].set_title(f"Composite distribution — N={len(results)}")
        axes[0].legend(fontsize=8)

        # Right: per-dimension means as bars
        labels = ["belief_fidelity", "request_alignment", "factual_grounding", "composite"]
        vals = [
            summary["belief_fidelity_mean"],
            summary["request_alignment_mean"],
            summary["factual_grounding_mean"],
            summary["composite_mean"],
        ]
        colors = ["#D4845C", "#E8B36B", "#7FB47A", "#5C9BD4"]
        axes[1].bar(labels, vals, color=colors)
        axes[1].set_ylim(0, 1)
        axes[1].set_ylabel("Mean score")
        axes[1].set_title(
            f"Grounded: {int(measured_grounded*100)}% (mirror) vs "
            f"{int(stored_grounded*100)}% (stored)"
        )
        for i, v in enumerate(vals):
            axes[1].text(i, v + 0.02, f"{v:.2f}", ha="center", fontsize=9)
        plt.setp(axes[1].get_xticklabels(), rotation=20, ha="right", fontsize=8)

        fig.suptitle("Fidelity Mirror Benchmark — belief/speech gap on real conversation log",
                     fontsize=11)
        fig.tight_layout()
        chart_path = OUT_DIR / f"fidelity_bench_{int(time.time())}.png"
        fig.savefig(chart_path, dpi=120, facecolor="#141210")
        plt.close(fig)
        print(f"[bench] Wrote {chart_path}")
    except Exception as e:
        print(f"[bench] Chart skipped: {e}")

    return out


if __name__ == "__main__":
    run()
