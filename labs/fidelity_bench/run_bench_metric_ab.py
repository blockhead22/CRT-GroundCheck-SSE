"""
Fidelity benchmark — A/B test cosine vs Fisher-Rao.

Premise (from Goodfire 2026-05): concept geometry in latent space is curved,
not flat — linear/cosine metrics undercount real semantic structure. Aether
already has Fisher-Rao distance for diagonal-Gaussian belief loci
(`personal_agent/info_geometry.py`), but `fidelity_mirror.py` scores in
plain cosine. This bench measures whether swapping the metric moves the
30pp belief/speech gap measured today.

Method:
  - Pull the same 30 query/response pairs from belief_speech as run_bench.py.
  - For each pair, encode response/memory texts ONCE.
  - Compute two scores:
      cos_score = mean(cosine_sim(response_vec, mem_vec))
      fr_score  = mean(fisher_sim(response_locus, mem_locus))
    where fisher_sim(a, b) = 1 / (1 + fisher_rao_distance(a, b)),
    mapping distance ∈ [0, ∞) into similarity ∈ (0, 1].
  - Apply the same composite weights (belief/request/grounding 0.2/0.4/0.4)
    as fidelity_mirror.

Loci are built with create_locus_from_type defaults — uniform sigma per
type — to isolate the metric change from the sigma-quality question.
A follow-up could pull stored sigma from memories.sigma BLOB.

Output: per-sample side-by-side, summary deltas, overlay chart.
"""
from __future__ import annotations

import json
import random
import sqlite3
import sys
import time
from pathlib import Path
from statistics import mean, median, stdev

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from personal_agent.crt_core import encode_vector  # noqa: E402
from personal_agent.memory_subsystem.splats import (  # noqa: E402
    create_locus_from_type,
)
from personal_agent.info_geometry import fisher_rao_distance  # noqa: E402

MEM_DB = ROOT / "personal_agent" / "crt_memory_shared.db"
OUT_DIR = Path(__file__).parent / "results"
OUT_DIR.mkdir(exist_ok=True)

SAMPLE_SIZE = 200
RANDOM_SEED = 42
MEM_BANK_SIZE = 30

# Same composite weights as fidelity_mirror.py
W_BELIEF = 0.2
W_REQUEST = 0.4
W_GROUNDING = 0.4
THRESHOLD = 0.25


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


def _cos(a: np.ndarray, b: np.ndarray) -> float:
    na, nb = np.linalg.norm(a), np.linalg.norm(b)
    if na < 1e-8 or nb < 1e-8:
        return 0.0
    return float(np.dot(a, b) / (na * nb))


def _fisher_sim(vec_a: np.ndarray, vec_b: np.ndarray, mem_type_a: str = "belief",
                mem_type_b: str = "belief") -> float:
    """Map Fisher-Rao distance into a [0, 1] similarity.

    Uses the type-calibrated default sigma. The 1/(1+d) mapping is monotonic,
    so the resulting score preserves the metric's ordering.
    """
    a = create_locus_from_type("a", vec_a, memory_type=mem_type_a)
    b = create_locus_from_type("b", vec_b, memory_type=mem_type_b)
    d = fisher_rao_distance(a, b)
    return 1.0 / (1.0 + d)


def fetch_pairs(n: int) -> list[dict]:
    conn = sqlite3.connect(MEM_DB)
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        """
        SELECT entry_id, timestamp, query, response, is_belief, memory_ids_json, trust_avg
        FROM belief_speech
        WHERE length(query) > 10 AND length(response) > 30
        ORDER BY timestamp DESC LIMIT 2000
        """
    ).fetchall()
    conn.close()
    pool = [dict(r) for r in rows]
    rng = random.Random(RANDOM_SEED)
    rng.shuffle(pool)
    return pool[:n]


def fetch_memory_bank(memory_ids_json: str | None, fallback_n: int = MEM_BANK_SIZE) -> list[dict]:
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


def score_one(query: str, response: str, memories: list[dict]) -> dict:
    """Compute both cosine- and fisher-rao-based fidelity scores on the same vectors."""
    rv = _encode(response)
    qv = _encode(query)
    if rv is None or qv is None:
        return {"skipped": True}

    # Per-memory similarities, computed once per metric
    mem_vecs: list[tuple[float, np.ndarray]] = []
    for m in memories:
        mv = _encode(m.get("text", "")[:300])
        if mv is None:
            continue
        mem_vecs.append((float(m.get("trust", 0.5)), mv))

    if not mem_vecs:
        return {"skipped": True}

    # Belief fidelity (response vs each memory, trust-weighted)
    cos_belief = float(np.mean([_cos(rv, mv) * (0.5 + 0.5 * t) for t, mv in mem_vecs]))
    fr_belief = float(np.mean([_fisher_sim(rv, mv) * (0.5 + 0.5 * t) for t, mv in mem_vecs]))

    # Request alignment (response vs query)
    cos_req = _cos(rv, qv)
    fr_req = _fisher_sim(rv, qv)

    # Factual grounding (per-sentence max similarity to any memory)
    sents = [s.strip() for s in response.split(".") if len(s.strip()) > 20][:10]
    if not sents:
        # short response — mirror fidelity_mirror's whole-response fallback
        cos_ground = min(1.0, max(_cos(rv, mv) for _, mv in mem_vecs) * 1.5)
        fr_ground = min(1.0, max(_fisher_sim(rv, mv) for _, mv in mem_vecs) * 1.5)
    else:
        cos_per_sent = []
        fr_per_sent = []
        for s in sents:
            sv = _encode(s)
            if sv is None:
                continue
            cos_max = max(_cos(sv, mv) for _, mv in mem_vecs)
            fr_max = max(_fisher_sim(sv, mv) for _, mv in mem_vecs)
            cos_per_sent.append(1.0 if cos_max > 0.4 else 0.0)
            fr_per_sent.append(1.0 if fr_max > 0.4 else 0.0)
        cos_ground = float(np.mean(cos_per_sent)) if cos_per_sent else 0.5
        fr_ground = float(np.mean(fr_per_sent)) if fr_per_sent else 0.5

    cos_comp = W_BELIEF * cos_belief + W_REQUEST * cos_req + W_GROUNDING * cos_ground
    fr_comp = W_BELIEF * fr_belief + W_REQUEST * fr_req + W_GROUNDING * fr_ground

    return {
        "skipped": False,
        "cosine": {
            "belief": round(cos_belief, 3),
            "request": round(cos_req, 3),
            "grounding": round(cos_ground, 3),
            "composite": round(cos_comp, 3),
            "passed": int(cos_comp >= THRESHOLD),
        },
        "fisher_rao": {
            "belief": round(fr_belief, 3),
            "request": round(fr_req, 3),
            "grounding": round(fr_ground, 3),
            "composite": round(fr_comp, 3),
            "passed": int(fr_comp >= THRESHOLD),
        },
        "n_memories": len(memories),
    }


def run() -> dict:
    pairs = fetch_pairs(SAMPLE_SIZE)
    print(f"[ab] sampled {len(pairs)} pairs")

    results = []
    t0 = time.perf_counter()
    for i, pair in enumerate(pairs, 1):
        mems = fetch_memory_bank(pair.get("memory_ids_json"))
        scored = score_one(pair["query"], pair["response"], mems)
        if scored.get("skipped"):
            continue
        results.append({
            "entry_id": pair["entry_id"],
            "is_belief_stored": int(pair["is_belief"]),
            **scored,
            "query": pair["query"][:120],
        })
        if i % 5 == 0:
            print(
                f"  [{i}/{len(pairs)}] "
                f"cos={scored['cosine']['composite']:.2f} "
                f"fr={scored['fisher_rao']['composite']:.2f}"
            )
    elapsed = time.perf_counter() - t0

    def agg(key: str, sub: str) -> float:
        return round(mean(r[key][sub] for r in results), 3)

    summary = {
        "n_samples": len(results),
        "elapsed_sec": round(elapsed, 1),
        "cosine": {
            "belief_mean": agg("cosine", "belief"),
            "request_mean": agg("cosine", "request"),
            "grounding_mean": agg("cosine", "grounding"),
            "composite_mean": agg("cosine", "composite"),
            "pass_rate": round(mean(r["cosine"]["passed"] for r in results), 3),
        },
        "fisher_rao": {
            "belief_mean": agg("fisher_rao", "belief"),
            "request_mean": agg("fisher_rao", "request"),
            "grounding_mean": agg("fisher_rao", "grounding"),
            "composite_mean": agg("fisher_rao", "composite"),
            "pass_rate": round(mean(r["fisher_rao"]["passed"] for r in results), 3),
        },
        "stored_grounded_rate": round(
            mean(r["is_belief_stored"] for r in results), 3
        ),
    }
    summary["delta"] = {
        "composite_mean": round(
            summary["fisher_rao"]["composite_mean"] - summary["cosine"]["composite_mean"], 3
        ),
        "pass_rate": round(
            summary["fisher_rao"]["pass_rate"] - summary["cosine"]["pass_rate"], 3
        ),
        "gap_to_stored_cosine": round(
            summary["cosine"]["pass_rate"] - summary["stored_grounded_rate"], 3
        ),
        "gap_to_stored_fisher": round(
            summary["fisher_rao"]["pass_rate"] - summary["stored_grounded_rate"], 3
        ),
    }

    # Discrimination: how well does each metric separate stored is_belief=1 from =0?
    # The pass-rate comparison is unfair across metrics on different scales,
    # but rank-discrimination (AUC) is scale-invariant. Higher AUC = better
    # ordering of grounded above ungrounded.
    def _auc(scores: list[float], labels: list[int]) -> float:
        # Mann-Whitney U / Wilcoxon AUC. No sklearn dep.
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

    labels = [r["is_belief_stored"] for r in results]
    cos_scores = [r["cosine"]["composite"] for r in results]
    fr_scores = [r["fisher_rao"]["composite"] for r in results]
    cos_auc = _auc(cos_scores, labels)
    fr_auc = _auc(fr_scores, labels)

    # Pearson correlation with stored is_belief flag
    def _corr(xs: list[float], ys: list[int]) -> float:
        x = np.asarray(xs, dtype=np.float64)
        y = np.asarray(ys, dtype=np.float64)
        if x.std() < 1e-10 or y.std() < 1e-10:
            return 0.0
        return float(np.corrcoef(x, y)[0, 1])

    summary["discrimination"] = {
        "cosine_auc": round(cos_auc, 3),
        "fisher_auc": round(fr_auc, 3),
        "delta_auc": round(fr_auc - cos_auc, 3),
        "cosine_corr_is_belief": round(_corr(cos_scores, labels), 3),
        "fisher_corr_is_belief": round(_corr(fr_scores, labels), 3),
    }

    # Agreement: how often do the two metrics agree on pass/fail at their own threshold?
    agree = sum(1 for r in results if r["cosine"]["passed"] == r["fisher_rao"]["passed"])
    flips = sum(1 for r in results if r["cosine"]["passed"] != r["fisher_rao"]["passed"])
    summary["agreement_rate"] = round(agree / len(results), 3)
    summary["flips"] = flips
    summary["headline"] = (
        f"cosine AUC={cos_auc:.3f} fisher AUC={fr_auc:.3f} "
        f"delta={fr_auc - cos_auc:+.3f} (positive = fisher discriminates better)"
    )

    out = {"summary": summary, "results": results}
    out_path = OUT_DIR / f"fidelity_bench_metric_ab_{int(time.time())}.json"
    out_path.write_text(json.dumps(out, indent=2))
    print(f"\n[ab] wrote {out_path}")
    print(f"[ab] HEADLINE: {summary['headline']}")
    print(json.dumps(summary, indent=2))

    # Chart: side-by-side composite distributions + per-dimension bars
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt

        cos_comp = [r["cosine"]["composite"] for r in results]
        fr_comp = [r["fisher_rao"]["composite"] for r in results]

        fig, axes = plt.subplots(1, 2, figsize=(12, 4.5))

        bins = np.linspace(0, 1, 16)
        axes[0].hist(cos_comp, bins=bins, alpha=0.6, color="#D4845C", label="cosine")
        axes[0].hist(fr_comp, bins=bins, alpha=0.6, color="#5C9BD4", label="fisher_rao")
        axes[0].axvline(THRESHOLD, color="#D47058", linestyle="--", label="threshold")
        axes[0].set_xlabel("Fidelity composite score")
        axes[0].set_ylabel("Count")
        axes[0].set_title(f"Composite distribution — N={len(results)}")
        axes[0].legend(fontsize=9)

        labels = ["belief", "request", "grounding", "composite"]
        cos_vals = [
            summary["cosine"]["belief_mean"],
            summary["cosine"]["request_mean"],
            summary["cosine"]["grounding_mean"],
            summary["cosine"]["composite_mean"],
        ]
        fr_vals = [
            summary["fisher_rao"]["belief_mean"],
            summary["fisher_rao"]["request_mean"],
            summary["fisher_rao"]["grounding_mean"],
            summary["fisher_rao"]["composite_mean"],
        ]
        x = np.arange(len(labels))
        w = 0.38
        axes[1].bar(x - w / 2, cos_vals, w, color="#D4845C", label="cosine")
        axes[1].bar(x + w / 2, fr_vals, w, color="#5C9BD4", label="fisher_rao")
        axes[1].set_xticks(x)
        axes[1].set_xticklabels(labels, rotation=15, ha="right", fontsize=9)
        axes[1].set_ylabel("Mean score")
        axes[1].set_title(
            f"cos pass {int(summary['cosine']['pass_rate']*100)}% vs "
            f"fr pass {int(summary['fisher_rao']['pass_rate']*100)}% "
            f"(stored {int(summary['stored_grounded_rate']*100)}%)"
        )
        axes[1].set_ylim(0, 1)
        axes[1].legend(fontsize=9)
        for i, v in enumerate(cos_vals):
            axes[1].text(i - w / 2, v + 0.02, f"{v:.2f}", ha="center", fontsize=8)
        for i, v in enumerate(fr_vals):
            axes[1].text(i + w / 2, v + 0.02, f"{v:.2f}", ha="center", fontsize=8)

        fig.suptitle("Fidelity Mirror — cosine vs Fisher-Rao A/B", fontsize=11)
        fig.tight_layout()
        chart_path = OUT_DIR / f"fidelity_bench_metric_ab_{int(time.time())}.png"
        fig.savefig(chart_path, dpi=120, facecolor="#141210")
        plt.close(fig)
        print(f"[ab] wrote {chart_path}")
    except Exception as e:
        print(f"[ab] chart skipped: {e}")

    return out


if __name__ == "__main__":
    run()
