"""
Retrieval-scope A/B: full substrate vs belief lane.

Question
========
Does raw nearest-neighbor similarity measure grounding, or does it create
"false familiarity" where ungrounded responses still look semantically close
to something in memory?

This bench uses the real `crt_memory_shared.db`:
- ~79k memories, most of them self_reflection/self_model
- belief_speech rows with stored response embeddings and `is_belief` labels

For each response, it retrieves top-k memories two ways:
1. full vector bank: every non-deprecated memory with a full 384D vector
2. belief lane: user/project/actionable fact lanes, excluding generated speech

It reports:
- AUC of top-k similarity against stored `is_belief`
- how much of top-k is self_model/self_reflection pollution
- grounded-vs-ungrounded top-k similarity means
- top example retrievals for inspection

No model calls. No network. Reads existing SQLite only.
"""
from __future__ import annotations

import json
import sqlite3
import time
from pathlib import Path
from statistics import mean

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
MEM_DB = ROOT / "personal_agent" / "crt_memory_shared.db"
OUT_DIR = Path(__file__).parent / "results"
OUT_DIR.mkdir(exist_ok=True)

SAMPLE_LIMIT = 1000
TOP_K = 5

USER_BELIEF_KINDS = {
    "user_fact",
    "user_belief",
    "preference",
    "default",
}
SYSTEM_BELIEF_KINDS = {
    "ops",
    "identity_constant",
    "hypothesis",
}
EXCLUDED_SOURCES = {"self_reflection"}
EXCLUDED_KINDS = {"self_model"}


def _vec_from_json(raw: str) -> np.ndarray:
    return np.asarray(json.loads(raw), dtype=np.float32)


def _vec_from_blob(raw: bytes) -> np.ndarray:
    return np.frombuffer(raw, dtype=np.float32)


def _normalize(mat: np.ndarray) -> np.ndarray:
    norms = np.linalg.norm(mat, axis=1, keepdims=True)
    norms[norms < 1e-8] = 1.0
    return mat / norms


def _auc(scores: list[float], labels: list[int]) -> float:
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


def load_memories() -> dict:
    conn = sqlite3.connect(MEM_DB)
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        """
        SELECT memory_id, vector_json, text, trust, kind, source
        FROM memories
        WHERE COALESCE(deprecated, 0) = 0
          AND vector_json IS NOT NULL
          AND length(vector_json) > 1000
        """
    ).fetchall()
    conn.close()

    ids: list[str] = []
    texts: list[str] = []
    trusts: list[float] = []
    kinds: list[str] = []
    sources: list[str] = []
    vecs: list[np.ndarray] = []
    for r in rows:
        try:
            v = _vec_from_json(r["vector_json"])
        except Exception:
            continue
        if v.shape[0] != 384:
            continue
        ids.append(r["memory_id"])
        texts.append(r["text"] or "")
        trusts.append(float(r["trust"] or 0.0))
        kinds.append(r["kind"] or "")
        sources.append(r["source"] or "")
        vecs.append(v)

    mat = _normalize(np.vstack(vecs).astype(np.float32))
    kinds_arr = np.asarray(kinds, dtype=object)
    sources_arr = np.asarray(sources, dtype=object)
    belief_mask = np.asarray(
        [
            (
                (s == "user" and k in USER_BELIEF_KINDS)
                or (s in {"system", "external", "mcp_client"} and k in SYSTEM_BELIEF_KINDS)
                or (s in {"external", "mcp_client"} and k in {"user_fact", "preference"})
            )
            and (k not in EXCLUDED_KINDS)
            and (s not in EXCLUDED_SOURCES)
            for k, s in zip(kinds, sources)
        ],
        dtype=bool,
    )
    self_mask = np.asarray(
        [(k in EXCLUDED_KINDS) or (s in EXCLUDED_SOURCES) for k, s in zip(kinds, sources)],
        dtype=bool,
    )
    return {
        "ids": ids,
        "texts": texts,
        "trusts": np.asarray(trusts, dtype=np.float32),
        "kinds": kinds_arr,
        "sources": sources_arr,
        "matrix": mat,
        "belief_mask": belief_mask,
        "self_mask": self_mask,
    }


def load_samples(limit: int) -> list[dict]:
    conn = sqlite3.connect(MEM_DB)
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        """
        SELECT entry_id, query, response, is_belief, query_embedding, response_embedding
        FROM belief_speech
        WHERE response_embedding IS NOT NULL
          AND length(response_embedding) = 1536
          AND length(response) > 30
        ORDER BY timestamp DESC
        LIMIT ?
        """,
        (limit,),
    ).fetchall()
    conn.close()
    out = []
    for r in rows:
        v = _vec_from_blob(r["response_embedding"]).astype(np.float32)
        if v.shape[0] != 384:
            continue
        n = np.linalg.norm(v)
        if n < 1e-8:
            continue
        out.append(
            {
                "entry_id": int(r["entry_id"]),
                "query": r["query"] or "",
                "response": r["response"] or "",
                "label": int(r["is_belief"]),
                "vec": v / n,
                "query_vec": _vec_from_blob(r["query_embedding"]).astype(np.float32),
            }
        )
        qn = np.linalg.norm(out[-1]["query_vec"])
        if qn < 1e-8:
            out.pop()
        else:
            out[-1]["query_vec"] = out[-1]["query_vec"] / qn
    return out


def topk(mat: np.ndarray, q: np.ndarray, k: int) -> tuple[np.ndarray, np.ndarray]:
    scores = mat @ q
    if scores.shape[0] <= k:
        idx = np.argsort(-scores)
    else:
        idx = np.argpartition(-scores, k)[:k]
        idx = idx[np.argsort(-scores[idx])]
    return idx, scores[idx]


def summarize_top(indices, scores, mem, max_items=3):
    rows = []
    for idx, score in zip(indices[:max_items], scores[:max_items]):
        rows.append(
            {
                "memory_id": mem["ids"][int(idx)],
                "score": round(float(score), 4),
                "trust": round(float(mem["trusts"][int(idx)]), 3),
                "kind": str(mem["kinds"][int(idx)]),
                "source": str(mem["sources"][int(idx)]),
                "text": mem["texts"][int(idx)][:180].replace("\n", " "),
            }
        )
    return rows


def run() -> dict:
    t0 = time.perf_counter()
    mem = load_memories()
    samples = load_samples(SAMPLE_LIMIT)
    belief_indices = np.flatnonzero(mem["belief_mask"])
    belief_mat = mem["matrix"][belief_indices]

    full_scores: list[float] = []
    scoped_scores: list[float] = []
    full_trust_scores: list[float] = []
    scoped_trust_scores: list[float] = []
    labels: list[int] = []
    full_self_fracs: list[float] = []
    scoped_self_fracs: list[float] = []
    response_query_sims: list[float] = []
    full_speech_fracs: list[float] = []
    scoped_speech_fracs: list[float] = []
    full_top1_speech: list[bool] = []
    full_top1_exact_echo: list[bool] = []
    examples: list[dict] = []

    for s in samples:
        labels.append(s["label"])
        response_query_sims.append(float(np.dot(s["vec"], s["query_vec"])))

        full_idx, full_sim = topk(mem["matrix"], s["vec"], TOP_K)
        scoped_local_idx, scoped_sim = topk(belief_mat, s["vec"], TOP_K)
        scoped_idx = belief_indices[scoped_local_idx]

        full_scores.append(float(np.mean(full_sim)))
        scoped_scores.append(float(np.mean(scoped_sim)))
        full_trust_scores.append(
            float(np.mean(full_sim * (0.5 + 0.5 * mem["trusts"][full_idx])))
        )
        scoped_trust_scores.append(
            float(np.mean(scoped_sim * (0.5 + 0.5 * mem["trusts"][scoped_idx])))
        )
        full_self_fracs.append(float(np.mean(mem["self_mask"][full_idx])))
        scoped_self_fracs.append(float(np.mean(mem["self_mask"][scoped_idx])))
        full_speech_mask = np.asarray(
            [
                (str(mem["sources"][int(i)]) == "system" and str(mem["kinds"][int(i)]) == "observation")
                for i in full_idx
            ],
            dtype=bool,
        )
        scoped_speech_mask = np.asarray(
            [
                (str(mem["sources"][int(i)]) == "system" and str(mem["kinds"][int(i)]) == "observation")
                for i in scoped_idx
            ],
            dtype=bool,
        )
        full_speech_fracs.append(float(np.mean(full_speech_mask)))
        scoped_speech_fracs.append(float(np.mean(scoped_speech_mask)))
        full_top1_speech.append(bool(full_speech_mask[0]))
        full_top1_exact_echo.append(
            bool(full_sim[0] >= 0.999 and mem["texts"][int(full_idx[0])][:80] in s["response"][:200])
        )

        if len(examples) < 8:
            examples.append(
                {
                    "entry_id": s["entry_id"],
                    "is_belief": s["label"],
                    "query": s["query"][:180].replace("\n", " "),
                    "response": s["response"][:240].replace("\n", " "),
                    "response_query_cosine": round(float(np.dot(s["vec"], s["query_vec"])), 4),
                    "full_top": summarize_top(full_idx, full_sim, mem),
                    "belief_lane_top": summarize_top(scoped_idx, scoped_sim, mem),
                }
            )

    def group_mean(values: list[float], label_value: int) -> float:
        vals = [v for v, y in zip(values, labels) if y == label_value]
        return round(mean(vals), 3) if vals else float("nan")

    summary = {
        "n_samples": len(samples),
        "stored_grounded_rate": round(mean(labels), 3),
        "memory_count_total": int(mem["matrix"].shape[0]),
        "memory_count_belief_lane": int(mem["belief_mask"].sum()),
        "memory_count_self_reflection": int(mem["self_mask"].sum()),
        "top_k": TOP_K,
        "auc": {
            "full_raw_cosine": round(_auc(full_scores, labels), 3),
            "belief_lane_raw_cosine": round(_auc(scoped_scores, labels), 3),
            "full_trust_weighted": round(_auc(full_trust_scores, labels), 3),
            "belief_lane_trust_weighted": round(_auc(scoped_trust_scores, labels), 3),
            "response_query_cosine": round(_auc(response_query_sims, labels), 3),
        },
        "mean_topk_similarity": {
            "full": round(mean(full_scores), 3),
            "belief_lane": round(mean(scoped_scores), 3),
        },
        "mean_topk_similarity_by_label": {
            "full_grounded": group_mean(full_scores, 1),
            "full_ungrounded": group_mean(full_scores, 0),
            "belief_lane_grounded": group_mean(scoped_scores, 1),
            "belief_lane_ungrounded": group_mean(scoped_scores, 0),
        },
        "mean_response_query_cosine_by_label": {
            "grounded": group_mean(response_query_sims, 1),
            "ungrounded": group_mean(response_query_sims, 0),
        },
        "mean_topk_self_reflection_fraction": {
            "full": round(mean(full_self_fracs), 3),
            "belief_lane": round(mean(scoped_self_fracs), 3),
        },
        "mean_topk_generated_speech_fraction": {
            "full": round(mean(full_speech_fracs), 3),
            "belief_lane": round(mean(scoped_speech_fracs), 3),
        },
        "responses_with_generated_speech_top1": {
            "full": round(mean(full_top1_speech), 3),
        },
        "responses_with_exact_echo_top1": {
            "full": round(mean(full_top1_exact_echo), 3),
        },
        "responses_with_any_self_reflection_in_topk": {
            "full": round(mean([x > 0 for x in full_self_fracs]), 3),
            "belief_lane": round(mean([x > 0 for x in scoped_self_fracs]), 3),
        },
        "elapsed_sec": round(time.perf_counter() - t0, 1),
    }
    summary["headline"] = (
        f"Raw top-{TOP_K} cosine over the full-vector memory bank is anti-predictive "
        f"of grounding: AUC={summary['auc']['full_raw_cosine']:.3f}. "
        f"Ungrounded responses have higher mean top-{TOP_K} similarity "
        f"({summary['mean_topk_similarity_by_label']['full_ungrounded']:.3f}) "
        f"than grounded ones ({summary['mean_topk_similarity_by_label']['full_grounded']:.3f}). "
        f"{summary['responses_with_generated_speech_top1']['full']:.0%} of full-bank top-1 hits "
        "are generated speech memories. Nearest-neighbor familiarity is not belief support."
    )

    out = {
        "summary": summary,
        "examples": examples,
        "notes": [
            "Labels are the substrate's stored belief_speech.is_belief flag.",
            "Full substrate includes self_model/self_reflection memories.",
            "Belief lane excludes self_reflection source and self_model kind.",
            "This measures retrieval scope, not final answer quality.",
        ],
    }
    stamp = int(time.time())
    out_path = OUT_DIR / f"retrieval_scope_ab_{stamp}.json"
    out_path.write_text(json.dumps(out, indent=2), encoding="utf-8")

    try:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt

        fig, axes = plt.subplots(1, 2, figsize=(12, 4.5))
        names = ["full", "belief lane"]
        aucs = [summary["auc"]["full_raw_cosine"], summary["auc"]["belief_lane_raw_cosine"]]
        pollution = [
            summary["mean_topk_generated_speech_fraction"]["full"],
            summary["mean_topk_generated_speech_fraction"]["belief_lane"],
        ]
        colors = ["#D4845C", "#5C9BD4"]
        axes[0].bar(names, aucs, color=colors)
        axes[0].axhline(0.5, color="#555", linestyle=":", linewidth=1)
        axes[0].set_ylim(0.45, max(0.75, max(aucs) + 0.05))
        axes[0].set_ylabel("AUC vs stored is_belief")
        axes[0].set_title("Grounding discrimination")
        for i, v in enumerate(aucs):
            axes[0].text(i, v + 0.006, f"{v:.3f}", ha="center", fontweight="bold")

        axes[1].bar(names, pollution, color=colors)
        axes[1].set_ylim(0, 1)
        axes[1].set_ylabel("Mean generated-speech fraction in top-k")
        axes[1].set_title(f"Speech echo interference (top-{TOP_K})")
        for i, v in enumerate(pollution):
            axes[1].text(i, v + 0.025, f"{v:.0%}", ha="center", fontweight="bold")

        fig.suptitle(f"Retrieval scope A/B on real substrate (N={len(samples)})")
        fig.tight_layout()
        chart_path = OUT_DIR / f"retrieval_scope_ab_{stamp}.png"
        fig.savefig(chart_path, dpi=130, facecolor="#141210")
        plt.close(fig)
    except Exception as e:
        chart_path = None
        print(f"[scope-ab] chart skipped: {e}")

    print(json.dumps(summary, indent=2))
    print(f"[scope-ab] wrote {out_path}")
    if chart_path:
        print(f"[scope-ab] wrote {chart_path}")
    return out


if __name__ == "__main__":
    run()
