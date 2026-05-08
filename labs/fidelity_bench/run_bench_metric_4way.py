"""
4-way metric A/B: cosine vs Fisher-Rao vs Bhattacharyya vs KL-symmetrized.

Extends run_bench_metric_ab.py:
- N=1000 by default (vs 200)
- Four metrics, all on the same vectors
- Per-metric AUC against the substrate's stored is_belief flag
- Pearson correlation per metric
- All metrics share the default type-calibrated sigma — see SIGMA NOTE below.

SIGMA NOTE
==========
Inspecting `memories.sigma` BLOBs (2026-05-07): 0 of 629 stored sigmas have
per-dimension variance — they are all uniform defaults from
`create_locus_from_type`, scaled only by memory_type. So "stored sigma"
adds no signal beyond defaults on this data. The natural follow-up is
sigma adaptation via belief-update history; logged in CLAIMS_AUDIT.md.

This bench therefore measures the metric-shape difference (which works
even with uniform sigma) and not the sigma-adaptation difference.
"""
from __future__ import annotations

import json
import random
import sqlite3
import sys
import time
from pathlib import Path
from statistics import mean, median

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from personal_agent.crt_core import encode_vector  # noqa: E402
from personal_agent.memory_subsystem.splats import (  # noqa: E402
    create_locus_from_type, bhattacharyya_distance, kl_divergence,
)
from personal_agent.info_geometry import fisher_rao_distance  # noqa: E402

MEM_DB = ROOT / "personal_agent" / "crt_memory_shared.db"
OUT_DIR = Path(__file__).parent / "results"
OUT_DIR.mkdir(exist_ok=True)

SAMPLE_SIZE = 1000
RANDOM_SEED = 42
MEM_BANK_SIZE = 30

W_BELIEF = 0.2
W_REQUEST = 0.4
W_GROUNDING = 0.4


def _encode(text: str) -> np.ndarray | None:
    if not text:
        return None
    try:
        v = encode_vector(text[:1000])
        if v is None:
            return None
        return np.asarray(v, dtype=np.float32)
    except Exception:
        return None


def _cos(a, b):
    na, nb = np.linalg.norm(a), np.linalg.norm(b)
    if na < 1e-8 or nb < 1e-8:
        return 0.0
    return float(np.dot(a, b) / (na * nb))


def _make_locus(vec, mtype="belief"):
    return create_locus_from_type("x", vec, memory_type=mtype)


def _fisher_sim(a, b):
    return 1.0 / (1.0 + fisher_rao_distance(_make_locus(a), _make_locus(b)))


def _bhatt_sim(a, b):
    return 1.0 / (1.0 + bhattacharyya_distance(_make_locus(a), _make_locus(b)))


def _kl_sim(a, b):
    la, lb = _make_locus(a), _make_locus(b)
    d = (kl_divergence(la, lb) + kl_divergence(lb, la)) / 2.0
    return 1.0 / (1.0 + d)


METRICS = {
    "cosine": _cos,
    "fisher_rao": _fisher_sim,
    "bhattacharyya": _bhatt_sim,
    "kl_sym": _kl_sim,
}


def fetch_pairs(n: int) -> list[dict]:
    conn = sqlite3.connect(MEM_DB)
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        """
        SELECT entry_id, timestamp, query, response, is_belief, memory_ids_json, trust_avg
        FROM belief_speech
        WHERE length(query) > 10 AND length(response) > 30
        ORDER BY timestamp DESC LIMIT 4000
        """
    ).fetchall()
    conn.close()
    pool = [dict(r) for r in rows]
    rng = random.Random(RANDOM_SEED)
    rng.shuffle(pool)
    return pool[:n]


def fetch_memory_bank(memory_ids_json, fallback_n=MEM_BANK_SIZE):
    conn = sqlite3.connect(MEM_DB)
    conn.row_factory = sqlite3.Row
    mems = []
    try:
        if memory_ids_json:
            ids = json.loads(memory_ids_json)
            if ids:
                p = ",".join("?" for _ in ids)
                rows = conn.execute(
                    f"SELECT memory_id, text, trust FROM memories WHERE memory_id IN ({p})", ids
                ).fetchall()
                mems = [{"memory_id": r["memory_id"], "text": r["text"], "trust": r["trust"]} for r in rows]
        if len(mems) < 5:
            rows = conn.execute(
                "SELECT memory_id, text, trust FROM memories "
                "WHERE deprecated = 0 AND length(text) > 20 "
                "ORDER BY trust DESC LIMIT ?", (fallback_n,)
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


def score_one(query, response, memories):
    rv = _encode(response)
    qv = _encode(query)
    if rv is None or qv is None:
        return None
    mem_vecs = []
    for m in memories:
        mv = _encode(m.get("text", "")[:300])
        if mv is None:
            continue
        mem_vecs.append((float(m.get("trust", 0.5)), mv))
    if not mem_vecs:
        return None

    sents = [s.strip() for s in response.split(".") if len(s.strip()) > 20][:10]
    sent_vecs = []
    for s in sents:
        sv = _encode(s)
        if sv is not None:
            sent_vecs.append(sv)

    out = {}
    for name, fn in METRICS.items():
        belief = float(np.mean([fn(rv, mv) * (0.5 + 0.5 * t) for t, mv in mem_vecs]))
        req = fn(rv, qv)
        if not sent_vecs:
            ground = min(1.0, max(fn(rv, mv) for _, mv in mem_vecs) * 1.5)
        else:
            grounded = sum(
                1 for sv in sent_vecs if max(fn(sv, mv) for _, mv in mem_vecs) > 0.4
            )
            ground = grounded / len(sent_vecs)
        comp = W_BELIEF * belief + W_REQUEST * req + W_GROUNDING * ground
        out[name] = {
            "belief": round(belief, 3),
            "request": round(req, 3),
            "grounding": round(ground, 3),
            "composite": round(comp, 3),
        }
    return out


def auc(scores, labels):
    pos = [s for s, y in zip(scores, labels) if y == 1]
    neg = [s for s, y in zip(scores, labels) if y == 0]
    if not pos or not neg:
        return float("nan")
    wins = ties = 0
    for p in pos:
        for n in neg:
            if p > n:
                wins += 1
            elif p == n:
                ties += 1
    return (wins + 0.5 * ties) / (len(pos) * len(neg))


def corr(xs, ys):
    x, y = np.asarray(xs, np.float64), np.asarray(ys, np.float64)
    if x.std() < 1e-10 or y.std() < 1e-10:
        return 0.0
    return float(np.corrcoef(x, y)[0, 1])


def run():
    pairs = fetch_pairs(SAMPLE_SIZE)
    print(f"[4way] sampled {len(pairs)} pairs")

    results = []
    t0 = time.perf_counter()
    for i, pair in enumerate(pairs, 1):
        mems = fetch_memory_bank(pair.get("memory_ids_json"))
        scored = score_one(pair["query"], pair["response"], mems)
        if scored is None:
            continue
        results.append({
            "entry_id": pair["entry_id"],
            "is_belief_stored": int(pair["is_belief"]),
            **scored,
        })
        if i % 100 == 0:
            print(f"  [{i}/{len(pairs)}] composites: " + ", ".join(
                f"{m}={scored[m]['composite']:.2f}" for m in METRICS
            ))
    elapsed = time.perf_counter() - t0
    print(f"[4way] {len(results)} usable in {elapsed:.0f}s")

    labels = [r["is_belief_stored"] for r in results]
    summary = {"n_samples": len(results), "elapsed_sec": round(elapsed, 1), "metrics": {}}
    for m in METRICS:
        comps = [r[m]["composite"] for r in results]
        beliefs = [r[m]["belief"] for r in results]
        reqs = [r[m]["request"] for r in results]
        grounds = [r[m]["grounding"] for r in results]
        summary["metrics"][m] = {
            "composite_mean": round(mean(comps), 3),
            "composite_median": round(median(comps), 3),
            "belief_mean": round(mean(beliefs), 3),
            "request_mean": round(mean(reqs), 3),
            "grounding_mean": round(mean(grounds), 3),
            "auc_vs_is_belief": round(auc(comps, labels), 3),
            "pearson_r": round(corr(comps, labels), 3),
        }
    summary["stored_grounded_rate"] = round(mean(labels), 3)

    # Deltas vs cosine baseline
    base = summary["metrics"]["cosine"]["auc_vs_is_belief"]
    base_r = summary["metrics"]["cosine"]["pearson_r"]
    summary["delta_vs_cosine"] = {
        m: {
            "auc": round(summary["metrics"][m]["auc_vs_is_belief"] - base, 3),
            "pearson_r": round(summary["metrics"][m]["pearson_r"] - base_r, 3),
        }
        for m in METRICS if m != "cosine"
    }
    summary["headline"] = " | ".join(
        f"{m} AUC={summary['metrics'][m]['auc_vs_is_belief']}" for m in METRICS
    )

    out_path = OUT_DIR / f"fidelity_bench_4way_{int(time.time())}.json"
    out_path.write_text(json.dumps({"summary": summary, "results": results}, indent=2))
    print(f"[4way] wrote {out_path}")
    print(f"[4way] HEADLINE: {summary['headline']}")
    print(json.dumps(summary, indent=2))

    # Chart
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt

        fig, axes = plt.subplots(1, 2, figsize=(13, 5))
        names = list(METRICS.keys())
        aucs = [summary["metrics"][m]["auc_vs_is_belief"] for m in names]
        prs = [summary["metrics"][m]["pearson_r"] for m in names]
        colors = ["#D4845C", "#5C9BD4", "#7FB47A", "#E8B36B"]

        x = np.arange(len(names))
        axes[0].bar(x, aucs, color=colors)
        axes[0].axhline(0.5, color="#555", linestyle=":", linewidth=1)
        axes[0].set_xticks(x)
        axes[0].set_xticklabels(names, rotation=15)
        axes[0].set_ylim(0.45, max(0.85, max(aucs) + 0.05))
        axes[0].set_ylabel("AUC vs stored is_belief")
        axes[0].set_title(f"Discrimination AUC (N={len(results)})")
        for i, v in enumerate(aucs):
            axes[0].text(i, v + 0.005, f"{v:.3f}", ha="center", fontsize=10, fontweight="bold")

        axes[1].bar(x, prs, color=colors)
        axes[1].axhline(0, color="#555", linestyle=":", linewidth=1)
        axes[1].set_xticks(x)
        axes[1].set_xticklabels(names, rotation=15)
        axes[1].set_ylabel("Pearson r vs stored is_belief")
        axes[1].set_title("Correlation with substrate's stored grounding flag")
        for i, v in enumerate(prs):
            axes[1].text(i, v + 0.005, f"{v:.3f}", ha="center", fontsize=10, fontweight="bold")

        fig.suptitle(
            f"Fidelity Mirror — 4-way metric comparison (N={len(results)}, default sigma)",
            fontsize=12,
        )
        fig.tight_layout()
        chart_path = OUT_DIR / f"fidelity_bench_4way_{int(time.time())}.png"
        fig.savefig(chart_path, dpi=120, facecolor="#141210")
        plt.close(fig)
        print(f"[4way] wrote {chart_path}")
    except Exception as e:
        print(f"[4way] chart skipped: {e}")

    return summary


if __name__ == "__main__":
    run()
