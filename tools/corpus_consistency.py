"""Cross-thread consistency analyzer for ChatGPT corpus.

Measures whether GPT gave consistent answers across separate conversations
on the same topics over 13 months. Finds contradictions, drift, and
inconsistencies that a persistent memory system would have caught.

Usage:
    python -m tools.corpus_consistency run        # Full analysis
    python -m tools.corpus_consistency report      # Show results
"""

from __future__ import annotations

import json
import logging
import sqlite3
import sys
import time
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List, Tuple

import numpy as np

log = logging.getLogger(__name__)

CORPUS_DB = Path("data/chatgpt_corpus.db")
RESULTS_DB = Path("data/chatgpt_consistency.db")

# Topics to probe for cross-thread consistency
# These are questions GPT likely answered differently across threads
PROBE_TOPICS = [
    # Personal life advice
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
    # Career and identity
    "career direction and what to do with your life",
    "freelancing vs full time employment",
    "how to pitch yourself and your work",
    "imposter syndrome and self doubt",
    "when to quit vs when to persevere",
    # Creative and philosophical
    "what makes life meaningful",
    "creativity and artistic expression",
    "consciousness and what it means to be aware",
    "ethics of AI and building sentient systems",
    "the nature of intelligence",
    # Substance and lifestyle
    "cannabis use and its effects",
    "productivity habits and routines",
    "sleep and rest advice",
    "diet and nutrition",
]


def _get_encoder():
    from personal_agent.embeddings import get_encoder
    return get_encoder()


def _init_results_db(db_path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA journal_mode=WAL")
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS topic_clusters (
            cluster_id INTEGER PRIMARY KEY AUTOINCREMENT,
            probe_topic TEXT NOT NULL,
            num_responses INTEGER,
            num_threads INTEGER,
            mean_similarity REAL,
            min_similarity REAL,
            variance REAL,
            consistency_score REAL,
            model_drift_detected INTEGER DEFAULT 0,
            contradiction_pairs_json TEXT
        );

        CREATE TABLE IF NOT EXISTS cluster_members (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            cluster_id INTEGER,
            msg_id TEXT,
            conv_id TEXT,
            conv_title TEXT,
            model_slug TEXT,
            create_time REAL,
            content_preview TEXT,
            similarity_to_centroid REAL,
            FOREIGN KEY (cluster_id) REFERENCES topic_clusters(cluster_id)
        );

        CREATE TABLE IF NOT EXISTS contradictions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            probe_topic TEXT,
            msg_id_a TEXT,
            msg_id_b TEXT,
            conv_title_a TEXT,
            conv_title_b TEXT,
            model_a TEXT,
            model_b TEXT,
            time_a REAL,
            time_b REAL,
            similarity REAL,
            content_a TEXT,
            content_b TEXT
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
    """Find assistant responses most relevant to a probe topic via embedding similarity."""
    # Sample assistant responses (can't embed all 28k, sample strategically)
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

    # Batch encode
    texts = [r[2][:500] for r in rows]  # First 500 chars for efficiency
    embeddings = encoder.encode_batch(texts)

    # Compute similarities
    sims = embeddings @ probe_embedding
    top_indices = np.argsort(sims)[-top_k:][::-1]

    results = []
    for idx in top_indices:
        if sims[idx] < 0.3:  # minimum relevance threshold
            break
        r = rows[idx]
        results.append({
            "msg_id": r[0],
            "conv_id": r[1],
            "content": r[2],
            "create_time": r[3],
            "model_slug": r[4],
            "conv_title": r[5],
            "similarity": float(sims[idx]),
            "embedding": embeddings[idx],
        })

    return results


def run_analysis(
    corpus_db: Path = CORPUS_DB,
    results_db: Path = RESULTS_DB,
    sample_per_probe: int = 5000,
) -> Dict[str, Any]:
    """Run cross-thread consistency analysis."""
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    encoder = _get_encoder()
    corpus_conn = sqlite3.connect(str(corpus_db))
    corpus_conn.row_factory = sqlite3.Row
    results_conn = _init_results_db(results_db)

    # Clear previous results
    results_conn.executescript("""
        DELETE FROM topic_clusters;
        DELETE FROM cluster_members;
        DELETE FROM contradictions;
    """)

    total_contradictions = 0
    total_topics_analyzed = 0
    topic_results = []

    for probe_topic in PROBE_TOPICS:
        log.info("Probing: %s", probe_topic)
        probe_emb = encoder.encode(probe_topic)

        # Find relevant assistant responses
        relevant = _find_relevant_responses(corpus_conn, probe_emb, encoder)

        if len(relevant) < 3:
            log.info("  Skipped (only %d relevant responses)", len(relevant))
            continue

        # Filter to responses from different threads
        seen_threads = set()
        unique_thread_responses = []
        for r in relevant:
            if r["conv_id"] not in seen_threads:
                seen_threads.add(r["conv_id"])
                unique_thread_responses.append(r)

        if len(unique_thread_responses) < 3:
            log.info("  Skipped (only %d unique threads)", len(unique_thread_responses))
            continue

        # Compute pairwise similarity between responses
        response_embeddings = np.array([r["embedding"] for r in unique_thread_responses])
        pairwise_sims = response_embeddings @ response_embeddings.T

        # Extract upper triangle (unique pairs)
        n = len(unique_thread_responses)
        pair_sims = []
        contradiction_pairs = []
        for i in range(n):
            for j in range(i + 1, n):
                sim = float(pairwise_sims[i, j])
                pair_sims.append(sim)

                # Low similarity between responses on same topic = potential contradiction
                if sim < 0.5:
                    ri, rj = unique_thread_responses[i], unique_thread_responses[j]
                    contradiction_pairs.append({
                        "msg_id_a": ri["msg_id"],
                        "msg_id_b": rj["msg_id"],
                        "conv_title_a": ri["conv_title"],
                        "conv_title_b": rj["conv_title"],
                        "model_a": ri["model_slug"],
                        "model_b": rj["model_slug"],
                        "time_a": ri["create_time"],
                        "time_b": rj["create_time"],
                        "similarity": sim,
                        "content_a": ri["content"][:300],
                        "content_b": rj["content"][:300],
                    })

        mean_sim = float(np.mean(pair_sims)) if pair_sims else 0
        min_sim = float(np.min(pair_sims)) if pair_sims else 0
        variance = float(np.var(pair_sims)) if pair_sims else 0

        # Check for model drift (responses from different model versions diverge more)
        model_groups = defaultdict(list)
        for r in unique_thread_responses:
            model_groups[r["model_slug"] or "unknown"].append(r["embedding"])

        model_drift = False
        if len(model_groups) >= 2:
            group_centroids = {}
            for model, embs in model_groups.items():
                group_centroids[model] = np.mean(embs, axis=0)
            models = list(group_centroids.keys())
            for i in range(len(models)):
                for j in range(i + 1, len(models)):
                    cross_sim = float(np.dot(group_centroids[models[i]], group_centroids[models[j]]))
                    if cross_sim < 0.6:
                        model_drift = True

        # Consistency score: 1.0 = perfectly consistent, 0.0 = total contradiction
        consistency_score = mean_sim

        # Store results
        cursor = results_conn.execute(
            """INSERT INTO topic_clusters
               (probe_topic, num_responses, num_threads, mean_similarity, min_similarity,
                variance, consistency_score, model_drift_detected, contradiction_pairs_json)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (probe_topic, len(relevant), len(unique_thread_responses),
             mean_sim, min_sim, variance, consistency_score,
             1 if model_drift else 0,
             json.dumps([{"sim": cp["similarity"], "a": cp["conv_title_a"][:50], "b": cp["conv_title_b"][:50]} for cp in contradiction_pairs])),
        )
        cluster_id = cursor.lastrowid

        for r in unique_thread_responses:
            centroid = np.mean(response_embeddings, axis=0)
            sim_to_centroid = float(np.dot(r["embedding"], centroid))
            results_conn.execute(
                """INSERT INTO cluster_members
                   (cluster_id, msg_id, conv_id, conv_title, model_slug, create_time,
                    content_preview, similarity_to_centroid)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (cluster_id, r["msg_id"], r["conv_id"], r["conv_title"],
                 r["model_slug"], r["create_time"], r["content"][:300], sim_to_centroid),
            )

        for cp in contradiction_pairs:
            results_conn.execute(
                """INSERT INTO contradictions
                   (probe_topic, msg_id_a, msg_id_b, conv_title_a, conv_title_b,
                    model_a, model_b, time_a, time_b, similarity, content_a, content_b)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (probe_topic, cp["msg_id_a"], cp["msg_id_b"], cp["conv_title_a"], cp["conv_title_b"],
                 cp["model_a"], cp["model_b"], cp["time_a"], cp["time_b"],
                 cp["similarity"], cp["content_a"], cp["content_b"]),
            )
            total_contradictions += 1

        total_topics_analyzed += 1
        topic_results.append({
            "topic": probe_topic,
            "responses": len(relevant),
            "threads": len(unique_thread_responses),
            "consistency": round(consistency_score, 3),
            "contradictions": len(contradiction_pairs),
            "model_drift": model_drift,
        })

        log.info("  %d responses, %d threads, consistency=%.3f, contradictions=%d, drift=%s",
                 len(relevant), len(unique_thread_responses), consistency_score,
                 len(contradiction_pairs), model_drift)

    results_conn.commit()
    corpus_conn.close()
    results_conn.close()

    return {
        "topics_analyzed": total_topics_analyzed,
        "total_contradictions": total_contradictions,
        "results": topic_results,
    }


def show_report(results_db: Path = RESULTS_DB):
    """Print a summary report of the consistency analysis."""
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    conn = sqlite3.connect(str(results_db))
    conn.row_factory = sqlite3.Row

    topics = conn.execute(
        "SELECT * FROM topic_clusters ORDER BY consistency_score ASC"
    ).fetchall()

    if not topics:
        print("No results yet. Run: python -m tools.corpus_consistency run")
        return

    print("=" * 70)
    print("CROSS-THREAD CONSISTENCY REPORT")
    print("=" * 70)

    total_contradictions = 0
    drift_topics = 0

    for t in topics:
        marker = "!!!" if t["consistency_score"] < 0.5 else "  " if t["consistency_score"] > 0.7 else " !"
        print(f"\n{marker} [{t['consistency_score']:.3f}] {t['probe_topic']}")
        print(f"   {t['num_threads']} threads, {t['num_responses']} responses")

        pairs = json.loads(t["contradiction_pairs_json"] or "[]")
        if pairs:
            total_contradictions += len(pairs)
            print(f"   {len(pairs)} contradiction pair(s):")
            for p in pairs[:3]:
                print(f"     sim={p['sim']:.3f}: \"{p['a']}\" vs \"{p['b']}\"")

        if t["model_drift_detected"]:
            drift_topics += 1
            print(f"   MODEL DRIFT DETECTED across versions")

    # Summary
    scores = [t["consistency_score"] for t in topics]
    print(f"\n{'=' * 70}")
    print(f"SUMMARY")
    print(f"  Topics analyzed: {len(topics)}")
    print(f"  Mean consistency: {np.mean(scores):.3f}")
    print(f"  Worst consistency: {min(scores):.3f}")
    print(f"  Total contradiction pairs: {total_contradictions}")
    print(f"  Topics with model drift: {drift_topics}")
    print(f"{'=' * 70}")

    # Show worst contradictions
    worst = conn.execute(
        "SELECT * FROM contradictions ORDER BY similarity ASC LIMIT 5"
    ).fetchall()

    if worst:
        print(f"\nTOP 5 WORST CONTRADICTIONS:")
        for w in worst:
            ts_a = time.strftime("%Y-%m-%d", time.localtime(w["time_a"])) if w["time_a"] else "?"
            ts_b = time.strftime("%Y-%m-%d", time.localtime(w["time_b"])) if w["time_b"] else "?"
            print(f"\n  Topic: {w['probe_topic']}")
            print(f"  Similarity: {w['similarity']:.3f}")
            print(f"  [{ts_a}] {w['model_a'] or '?'} in \"{w['conv_title_a'][:50]}\"")
            print(f"    {w['content_a'][:150]}")
            print(f"  [{ts_b}] {w['model_b'] or '?'} in \"{w['conv_title_b'][:50]}\"")
            print(f"    {w['content_b'][:150]}")

    conn.close()


def main():
    import sys
    logging.basicConfig(level=logging.INFO, format="%(message)s")

    cmd = sys.argv[1] if len(sys.argv) > 1 else "run"

    if cmd == "run":
        result = run_analysis()
        print(json.dumps(result, indent=2, default=str))
    elif cmd == "report":
        show_report()
    else:
        print(f"Usage: python -m tools.corpus_consistency <run|report>")


if __name__ == "__main__":
    main()
