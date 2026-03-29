"""Enhanced GPT corpus drift detection.

Goes beyond corpus_consistency.py's cosine similarity:
- Temporal drift curves per model version
- Semantic entropy per topic cluster (DBSCAN)
- Per-cluster scatter metric (comparable to CRT 0.345 baseline)
- Model-version comparison matrix
- Drift velocity (how fast opinions change over time)

Usage:
    python -m tools.corpus_drift run       # Full analysis
    python -m tools.corpus_drift report    # Show results
    python -m tools.corpus_drift compare   # Compare to CRT baseline
"""

from __future__ import annotations

import json
import logging
import sqlite3
import sys
import time
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

log = logging.getLogger(__name__)

CORPUS_DB = Path("data/chatgpt_corpus.db")
RESULTS_DB = Path("data/chatgpt_drift.db")
CONSISTENCY_DB = Path("data/chatgpt_consistency.db")

# Same probe topics as corpus_consistency
PROBE_TOPICS = [
    "how to deal with stress and burnout",
    "relationship advice",
    "self improvement and personal growth",
    "dealing with anger and frustration",
    "work life balance",
    "managing anxiety",
    "how to stay motivated",
    "dealing with loneliness",
    "financial advice and money management",
    "health and wellness advice",
    "career direction and what to do with your life",
    "freelancing vs full time employment",
    "how to pitch yourself and your work",
    "imposter syndrome and self doubt",
    "when to quit vs when to persevere",
    "what makes life meaningful",
    "creativity and artistic expression",
    "consciousness and what it means to be aware",
    "ethics of AI and building sentient systems",
    "the nature of intelligence",
    "cannabis use and its effects",
    "productivity habits and routines",
    "sleep and rest advice",
]

# Domain classification for topics
DOMAIN_MAP = {
    "how to deal with stress and burnout": "emotional",
    "relationship advice": "emotional",
    "self improvement and personal growth": "aspirational",
    "dealing with anger and frustration": "emotional",
    "work life balance": "practical",
    "managing anxiety": "emotional",
    "how to stay motivated": "aspirational",
    "dealing with loneliness": "emotional",
    "financial advice and money management": "practical",
    "health and wellness advice": "practical",
    "career direction and what to do with your life": "aspirational",
    "freelancing vs full time employment": "practical",
    "how to pitch yourself and your work": "practical",
    "imposter syndrome and self doubt": "emotional",
    "when to quit vs when to persevere": "aspirational",
    "what makes life meaningful": "philosophical",
    "creativity and artistic expression": "philosophical",
    "consciousness and what it means to be aware": "philosophical",
    "ethics of AI and building sentient systems": "philosophical",
    "the nature of intelligence": "philosophical",
    "cannabis use and its effects": "practical",
    "productivity habits and routines": "practical",
    "sleep and rest advice": "practical",
}


def _get_encoder():
    from personal_agent.embeddings import get_encoder
    return get_encoder()


def _init_drift_db(db_path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA journal_mode=WAL")
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS drift_analysis (
            analysis_id INTEGER PRIMARY KEY AUTOINCREMENT,
            probe_topic TEXT NOT NULL,
            domain TEXT,
            num_responses INTEGER,
            num_threads INTEGER,
            num_models INTEGER,

            -- Scatter metrics (comparable to CRT 0.345)
            mean_pairwise_distance REAL,
            response_variance REAL,
            semantic_entropy REAL,
            num_semantic_clusters INTEGER,

            -- Temporal drift
            drift_velocity REAL,
            temporal_span_days REAL,
            early_consistency REAL,
            late_consistency REAL,
            consistency_trend REAL,

            -- Model version comparison
            model_versions_json TEXT,
            cross_model_drift REAL,
            worst_model_pair_json TEXT,

            -- Raw data
            pairwise_distances_json TEXT,
            temporal_points_json TEXT
        );

        CREATE TABLE IF NOT EXISTS model_comparison (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            probe_topic TEXT,
            model_a TEXT,
            model_b TEXT,
            cross_similarity REAL,
            num_responses_a INTEGER,
            num_responses_b INTEGER,
            centroid_distance REAL
        );

        CREATE TABLE IF NOT EXISTS drift_summary (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp REAL,
            total_topics INTEGER,
            mean_scatter REAL,
            mean_entropy REAL,
            mean_drift_velocity REAL,
            domain_scatter_json TEXT,
            model_scatter_json TEXT,
            crt_comparison_json TEXT
        );
    """)
    conn.commit()
    return conn


def _find_relevant_responses(
    corpus_conn: sqlite3.Connection,
    probe_embedding: np.ndarray,
    encoder,
    top_k: int = 50,
    min_length: int = 100,
) -> List[Dict]:
    """Find assistant responses most relevant to a probe topic."""
    rows = corpus_conn.execute("""
        SELECT m.msg_id, m.conv_id, m.content, m.create_time, m.model_slug,
               c.title as conv_title
        FROM messages m
        JOIN conversations c ON m.conv_id = c.conv_id
        WHERE m.role = 'assistant'
          AND m.char_count > ?
          AND m.char_count < 5000
        ORDER BY RANDOM()
        LIMIT 5000
    """, (min_length,)).fetchall()

    if not rows:
        return []

    texts = [r[2][:500] for r in rows]
    embeddings = encoder.encode_batch(texts)
    sims = embeddings @ probe_embedding
    top_indices = np.argsort(sims)[-top_k:][::-1]

    results = []
    for idx in top_indices:
        if sims[idx] < 0.3:
            break
        r = rows[idx]
        results.append({
            "msg_id": r[0],
            "conv_id": r[1],
            "content": r[2],
            "create_time": r[3],
            "model_slug": r[4] or "unknown",
            "conv_title": r[5],
            "similarity": float(sims[idx]),
            "embedding": embeddings[idx],
        })

    return results


def _compute_semantic_entropy(embeddings: np.ndarray, eps: float = 0.35, min_samples: int = 2) -> Tuple[float, int]:
    """Compute semantic entropy via DBSCAN clustering."""
    from sklearn.cluster import DBSCAN

    if len(embeddings) < 3:
        return 0.0, 1

    # Use cosine distance
    distances = 1.0 - embeddings @ embeddings.T
    np.fill_diagonal(distances, 0)

    clustering = DBSCAN(eps=eps, min_samples=min_samples, metric='precomputed')
    labels = clustering.fit_predict(distances)

    # Count cluster sizes (including noise as separate cluster)
    unique_labels = set(labels)
    n_clusters = len(unique_labels - {-1})
    if -1 in unique_labels:
        n_clusters += 1  # noise points as their own "cluster"

    # Shannon entropy of cluster assignment
    counts = np.bincount(labels + 1)  # +1 to handle -1 noise label
    probs = counts[counts > 0] / counts.sum()
    entropy = -np.sum(probs * np.log2(probs + 1e-10))

    return float(entropy), n_clusters


def _compute_drift_velocity(responses: List[Dict]) -> Tuple[float, float, float, float, List]:
    """Compute how fast responses drift over time.

    Returns: (velocity, temporal_span_days, early_consistency, late_consistency, temporal_points)
    """
    # Sort by time
    timed = [(r["create_time"], r["embedding"]) for r in responses if r["create_time"]]
    if len(timed) < 4:
        return 0.0, 0.0, 0.0, 0.0, []

    timed.sort(key=lambda x: x[0])
    times = [t[0] for t in timed]
    embs = [t[1] for t in timed]

    temporal_span = (times[-1] - times[0]) / 86400  # days

    # Compute consecutive drift
    consecutive_dists = []
    temporal_points = []
    for i in range(1, len(embs)):
        dist = 1.0 - float(np.dot(embs[i], embs[i-1]))
        consecutive_dists.append(dist)
        temporal_points.append({
            "time": times[i],
            "drift_from_prev": dist,
        })

    # Drift velocity = mean consecutive distance / time span
    velocity = float(np.mean(consecutive_dists)) / max(temporal_span, 1.0) if consecutive_dists else 0.0

    # Early vs late consistency
    mid = len(embs) // 2
    early_embs = np.array(embs[:mid])
    late_embs = np.array(embs[mid:])

    early_sims = early_embs @ early_embs.T
    late_sims = late_embs @ late_embs.T

    # Mean off-diagonal similarity
    n_e = len(early_embs)
    n_l = len(late_embs)
    early_consistency = float((early_sims.sum() - n_e) / max(n_e * (n_e - 1), 1))
    late_consistency = float((late_sims.sum() - n_l) / max(n_l * (n_l - 1), 1))

    return velocity, temporal_span, early_consistency, late_consistency, temporal_points


def run_drift_analysis(
    corpus_db: Path = CORPUS_DB,
    results_db: Path = RESULTS_DB,
) -> Dict[str, Any]:
    """Run enhanced drift detection across all topic clusters."""
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    encoder = _get_encoder()
    corpus_conn = sqlite3.connect(str(corpus_db))
    corpus_conn.row_factory = sqlite3.Row
    drift_conn = _init_drift_db(results_db)

    # Clear previous
    drift_conn.executescript("""
        DELETE FROM drift_analysis;
        DELETE FROM model_comparison;
        DELETE FROM drift_summary;
    """)

    topic_results = []
    domain_scatter = defaultdict(list)
    model_scatter = defaultdict(list)

    for probe_topic in PROBE_TOPICS:
        domain = DOMAIN_MAP.get(probe_topic, "other")
        print(f"  Analyzing: {probe_topic} [{domain}]")
        probe_emb = encoder.encode(probe_topic)

        # Find relevant responses
        relevant = _find_relevant_responses(corpus_conn, probe_emb, encoder)
        if len(relevant) < 3:
            print(f"    Skipped ({len(relevant)} responses)")
            continue

        # Deduplicate by thread
        seen_threads = set()
        unique = []
        for r in relevant:
            if r["conv_id"] not in seen_threads:
                seen_threads.add(r["conv_id"])
                unique.append(r)

        if len(unique) < 3:
            continue

        embeddings = np.array([r["embedding"] for r in unique])

        # --- Scatter metrics ---
        pairwise_sims = embeddings @ embeddings.T
        n = len(unique)
        pair_dists = []
        for i in range(n):
            for j in range(i + 1, n):
                pair_dists.append(1.0 - float(pairwise_sims[i, j]))

        mean_dist = float(np.mean(pair_dists))
        variance = float(np.var(pair_dists))
        entropy, n_clusters = _compute_semantic_entropy(embeddings)

        # --- Temporal drift ---
        velocity, span_days, early_c, late_c, temporal_points = _compute_drift_velocity(unique)
        consistency_trend = late_c - early_c  # positive = converging

        # --- Model version comparison ---
        model_groups = defaultdict(list)
        for r in unique:
            model_groups[r["model_slug"]].append(r)

        model_versions = {}
        for model, resps in model_groups.items():
            m_embs = np.array([r["embedding"] for r in resps])
            m_sims = m_embs @ m_embs.T
            m_n = len(m_embs)
            intra_sim = float((m_sims.sum() - m_n) / max(m_n * (m_n - 1), 1)) if m_n > 1 else 1.0
            model_versions[model] = {
                "count": m_n,
                "intra_consistency": round(intra_sim, 3),
                "scatter": round(1.0 - intra_sim, 3),
            }
            model_scatter[model].append(1.0 - intra_sim)

        # Cross-model drift
        cross_model_drift = 0.0
        worst_pair = None
        models = list(model_groups.keys())
        for i in range(len(models)):
            for j in range(i + 1, len(models)):
                m_a = models[i]
                m_b = models[j]
                embs_a = np.array([r["embedding"] for r in model_groups[m_a]])
                embs_b = np.array([r["embedding"] for r in model_groups[m_b]])
                centroid_a = embs_a.mean(axis=0)
                centroid_b = embs_b.mean(axis=0)
                c_dist = 1.0 - float(np.dot(centroid_a, centroid_b))

                if c_dist > cross_model_drift:
                    cross_model_drift = c_dist
                    worst_pair = {"model_a": m_a, "model_b": m_b, "distance": round(c_dist, 4)}

                drift_conn.execute(
                    """INSERT INTO model_comparison
                       (probe_topic, model_a, model_b, cross_similarity, num_responses_a,
                        num_responses_b, centroid_distance)
                       VALUES (?, ?, ?, ?, ?, ?, ?)""",
                    (probe_topic, m_a, m_b, round(1.0 - c_dist, 4),
                     len(model_groups[m_a]), len(model_groups[m_b]), round(c_dist, 4)),
                )

        result = {
            "topic": probe_topic,
            "domain": domain,
            "responses": len(relevant),
            "threads": len(unique),
            "models": len(model_groups),
            "scatter": round(mean_dist, 4),
            "variance": round(variance, 4),
            "entropy": round(entropy, 3),
            "n_clusters": n_clusters,
            "drift_velocity": round(velocity, 6),
            "temporal_span_days": round(span_days, 1),
            "early_consistency": round(early_c, 3),
            "late_consistency": round(late_c, 3),
            "consistency_trend": round(consistency_trend, 3),
            "cross_model_drift": round(cross_model_drift, 4),
        }
        topic_results.append(result)
        domain_scatter[domain].append(mean_dist)

        # Store
        drift_conn.execute(
            """INSERT INTO drift_analysis
               (probe_topic, domain, num_responses, num_threads, num_models,
                mean_pairwise_distance, response_variance, semantic_entropy,
                num_semantic_clusters, drift_velocity, temporal_span_days,
                early_consistency, late_consistency, consistency_trend,
                model_versions_json, cross_model_drift, worst_model_pair_json,
                pairwise_distances_json, temporal_points_json)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (probe_topic, domain, len(relevant), len(unique), len(model_groups),
             mean_dist, variance, entropy, n_clusters,
             velocity, span_days, early_c, late_c, consistency_trend,
             json.dumps(model_versions),
             cross_model_drift,
             json.dumps(worst_pair) if worst_pair else None,
             json.dumps([round(d, 4) for d in pair_dists[:100]]),  # cap storage
             json.dumps(temporal_points[:50])),
        )

        print(f"    scatter={mean_dist:.3f} entropy={entropy:.2f} clusters={n_clusters} "
              f"velocity={velocity:.5f} models={len(model_groups)} trend={'converging' if consistency_trend > 0 else 'diverging'}")

    # Domain summary
    domain_summary = {}
    for domain, scatters in domain_scatter.items():
        domain_summary[domain] = {
            "mean_scatter": round(float(np.mean(scatters)), 4),
            "std_scatter": round(float(np.std(scatters)), 4),
            "n_topics": len(scatters),
        }

    # Model summary
    model_summary = {}
    for model, scatters in model_scatter.items():
        if len(scatters) >= 2:
            model_summary[model] = {
                "mean_scatter": round(float(np.mean(scatters)), 4),
                "n_topics": len(scatters),
            }

    # CRT comparison
    crt_baseline = 0.345  # from memory: GPT variance baseline 0.223 scatter vs CRT 0.345
    gpt_mean_scatter = float(np.mean([r["scatter"] for r in topic_results])) if topic_results else 0.0
    crt_comparison = {
        "gpt_mean_scatter": round(gpt_mean_scatter, 4),
        "crt_scatter": crt_baseline,
        "delta": round(gpt_mean_scatter - crt_baseline, 4),
        "gpt_more_consistent": gpt_mean_scatter < crt_baseline,
    }

    # Store summary
    drift_conn.execute(
        """INSERT INTO drift_summary
           (timestamp, total_topics, mean_scatter, mean_entropy,
            mean_drift_velocity, domain_scatter_json, model_scatter_json,
            crt_comparison_json)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        (time.time(), len(topic_results),
         gpt_mean_scatter,
         float(np.mean([r["entropy"] for r in topic_results])) if topic_results else 0,
         float(np.mean([r["drift_velocity"] for r in topic_results])) if topic_results else 0,
         json.dumps(domain_summary),
         json.dumps(model_summary),
         json.dumps(crt_comparison)),
    )

    drift_conn.commit()
    corpus_conn.close()
    drift_conn.close()

    return {
        "topics_analyzed": len(topic_results),
        "mean_scatter": round(gpt_mean_scatter, 4),
        "crt_comparison": crt_comparison,
        "domain_summary": domain_summary,
        "model_summary": model_summary,
        "results": topic_results,
    }


def show_report(results_db: Path = RESULTS_DB):
    """Print detailed drift report."""
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    conn = sqlite3.connect(str(results_db))
    conn.row_factory = sqlite3.Row

    topics = conn.execute(
        "SELECT * FROM drift_analysis ORDER BY mean_pairwise_distance DESC"
    ).fetchall()

    if not topics:
        print("No results. Run: python -m tools.corpus_drift run")
        return

    print("=" * 75)
    print("GPT CORPUS DRIFT ANALYSIS — ALL 23 TOPIC CLUSTERS")
    print("=" * 75)

    # Group by domain
    by_domain = defaultdict(list)
    for t in topics:
        by_domain[t["domain"]].append(t)

    for domain in ["emotional", "aspirational", "practical", "philosophical"]:
        if domain not in by_domain:
            continue
        domain_topics = by_domain[domain]
        domain_scatter = np.mean([t["mean_pairwise_distance"] for t in domain_topics])
        print(f"\n--- {domain.upper()} (mean scatter: {domain_scatter:.3f}) ---")

        for t in sorted(domain_topics, key=lambda x: x["mean_pairwise_distance"], reverse=True):
            trend = "+" if t["consistency_trend"] > 0 else "-"
            print(f"\n  [{t['mean_pairwise_distance']:.3f}] {t['probe_topic']}")
            print(f"    {t['num_threads']} threads, {t['num_responses']} responses, {t['num_models']} models")
            print(f"    entropy={t['semantic_entropy']:.2f} ({t['num_semantic_clusters']} clusters)")
            print(f"    velocity={t['drift_velocity']:.5f}/day over {t['temporal_span_days']:.0f} days")
            print(f"    early={t['early_consistency']:.3f} late={t['late_consistency']:.3f} trend={trend}{abs(t['consistency_trend']):.3f}")
            print(f"    cross-model drift={t['cross_model_drift']:.3f}")

            mv = json.loads(t["model_versions_json"] or "{}")
            if mv:
                top_models = sorted(mv.items(), key=lambda x: x[1].get("scatter", 0), reverse=True)[:3]
                for m, stats in top_models:
                    print(f"      {m}: n={stats['count']} scatter={stats['scatter']:.3f}")

    # Summary
    summary = conn.execute("SELECT * FROM drift_summary ORDER BY id DESC LIMIT 1").fetchone()
    if summary:
        print(f"\n{'=' * 75}")
        print("SUMMARY")
        print(f"  Topics: {summary['total_topics']}")
        print(f"  Mean scatter: {summary['mean_scatter']:.4f}")
        print(f"  Mean entropy: {summary['mean_entropy']:.3f}")
        print(f"  Mean drift velocity: {summary['mean_drift_velocity']:.6f}/day")

        crt = json.loads(summary["crt_comparison_json"] or "{}")
        if crt:
            print(f"\n  GPT vs CRT comparison:")
            print(f"    GPT scatter: {crt.get('gpt_mean_scatter', 0):.4f}")
            print(f"    CRT scatter: {crt.get('crt_scatter', 0):.4f}")
            delta = crt.get('delta', 0)
            direction = "MORE consistent" if delta < 0 else "LESS consistent"
            print(f"    GPT is {direction} than CRT by {abs(delta):.4f}")

        ds = json.loads(summary["domain_scatter_json"] or "{}")
        if ds:
            print(f"\n  Domain scatter ranking:")
            for domain, stats in sorted(ds.items(), key=lambda x: x[1]["mean_scatter"], reverse=True):
                print(f"    {domain}: {stats['mean_scatter']:.4f} (n={stats['n_topics']})")

        ms = json.loads(summary["model_scatter_json"] or "{}")
        if ms:
            print(f"\n  Model scatter ranking:")
            for model, stats in sorted(ms.items(), key=lambda x: x[1]["mean_scatter"], reverse=True):
                print(f"    {model}: {stats['mean_scatter']:.4f} (n={stats['n_topics']})")

    # Worst cross-model pairs
    worst = conn.execute(
        "SELECT * FROM model_comparison ORDER BY centroid_distance DESC LIMIT 10"
    ).fetchall()
    if worst:
        print(f"\n  Top 10 worst cross-model drifts:")
        for w in worst:
            print(f"    [{w['centroid_distance']:.3f}] {w['probe_topic'][:40]}: "
                  f"{w['model_a']} ({w['num_responses_a']}) vs "
                  f"{w['model_b']} ({w['num_responses_b']})")

    print(f"\n{'=' * 75}")
    conn.close()


def main():
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    cmd = sys.argv[1] if len(sys.argv) > 1 else "run"

    if cmd == "run":
        print("Running enhanced drift analysis on GPT corpus...")
        result = run_drift_analysis()
        print(f"\nDone. {result['topics_analyzed']} topics analyzed.")
        print(f"Mean scatter: {result['mean_scatter']:.4f}")
        print(f"GPT vs CRT: {json.dumps(result['crt_comparison'], indent=2)}")
    elif cmd == "report":
        show_report()
    else:
        print("Usage: python -m tools.corpus_drift <run|report>")


if __name__ == "__main__":
    main()
