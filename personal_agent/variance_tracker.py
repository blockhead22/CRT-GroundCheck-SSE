"""
Opinion/Belief Variance Tracker

Tracks how Aether's responses on the same topic drift over time as memories
accumulate. Groups queries by semantic similarity, then computes per-topic
metrics: response drift, belief flip rate, opinion convergence, belief stability.
"""

import json
import logging
import sqlite3
import time
from typing import Dict, List, Optional

import numpy as np

from .embeddings import encode_text, get_encoder

log = logging.getLogger(__name__)

ANALYSIS_COOLDOWN_SECONDS = 6 * 3600  # 6 hours


class VarianceTracker:
    """Tracks opinion and belief variance across topics over time."""

    def __init__(self, db_path: str):
        self.db_path = db_path
        self._governance_bridge = None
        self.ensure_tables()

    def set_governance_bridge(self, bridge) -> None:
        """Attach a GovernanceBridge for drift->trust feedback."""
        self._governance_bridge = bridge

    def ensure_tables(self):
        conn = self._get_connection()
        try:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS opinion_topics (
                    topic_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    label TEXT,
                    centroid_embedding BLOB NOT NULL,
                    entry_count INTEGER DEFAULT 0,
                    first_seen REAL NOT NULL,
                    last_seen REAL NOT NULL,
                    last_analyzed REAL,
                    metrics_json TEXT
                );

                CREATE TABLE IF NOT EXISTS variance_snapshots (
                    snapshot_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp REAL NOT NULL,
                    num_topics INTEGER,
                    avg_drift REAL,
                    avg_belief_stability REAL,
                    avg_speech_entropy REAL,
                    global_flip_rate REAL,
                    details_json TEXT
                );
            """)
            conn.commit()
        finally:
            conn.close()

    def _get_connection(self) -> sqlite3.Connection:
        return sqlite3.connect(self.db_path)

    # ── Recording ──────────────────────────────────────────────────

    def store_embeddings(self, entry_id: int, query_embedding: bytes, response_embedding: bytes):
        """Store precomputed embeddings for a belief_speech entry."""
        conn = self._get_connection()
        try:
            conn.execute(
                "UPDATE belief_speech SET query_embedding=?, response_embedding=? WHERE entry_id=?",
                (query_embedding, response_embedding, entry_id),
            )
            conn.commit()
        finally:
            conn.close()

    # ── Periodic analysis ──────────────────────────────────────────

    def run_analysis(self, force: bool = False) -> Dict:
        """Run full variance analysis across all topics. Skips if last run was <6h ago."""
        conn = self._get_connection()
        try:
            row = conn.execute(
                "SELECT MAX(timestamp) FROM variance_snapshots"
            ).fetchone()
            last_ts = row[0] if row and row[0] else 0.0

            if not force and (time.time() - last_ts) < ANALYSIS_COOLDOWN_SECONDS:
                log.info("Skipping analysis, last run %.1fh ago", (time.time() - last_ts) / 3600)
                return {"skipped": True, "hours_since_last": (time.time() - last_ts) / 3600}
        finally:
            conn.close()

        num_topics = self.recluster_topics()

        conn = self._get_connection()
        try:
            topics = conn.execute(
                "SELECT topic_id, last_analyzed FROM opinion_topics"
            ).fetchall()
        finally:
            conn.close()

        topic_metrics = {}
        for topic_id, last_analyzed in topics:
            metrics = self.compute_topic_metrics(topic_id)
            topic_metrics[topic_id] = metrics

        drifts = [m.get("mean_drift", 0) for m in topic_metrics.values() if m.get("mean_drift") is not None]
        stabilities = [m.get("belief_stability", 0) for m in topic_metrics.values() if m.get("belief_stability") is not None]
        entropies = [m.get("opinion_entropy", 0) for m in topic_metrics.values() if m.get("opinion_entropy") is not None]

        total_flips = sum(m.get("belief_flip_count", 0) for m in topic_metrics.values())
        total_entries = sum(m.get("entry_count", 0) for m in topic_metrics.values())
        global_flip_rate = total_flips / max(total_entries - num_topics, 1)

        snapshot = {
            "timestamp": time.time(),
            "num_topics": num_topics,
            "avg_drift": float(np.mean(drifts)) if drifts else None,
            "avg_belief_stability": float(np.mean(stabilities)) if stabilities else None,
            "avg_speech_entropy": float(np.mean(entropies)) if entropies else None,
            "global_flip_rate": global_flip_rate,
            "details_json": json.dumps(topic_metrics, default=str),
        }

        conn = self._get_connection()
        try:
            conn.execute(
                """INSERT INTO variance_snapshots
                   (timestamp, num_topics, avg_drift, avg_belief_stability, avg_speech_entropy, global_flip_rate, details_json)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (
                    snapshot["timestamp"],
                    snapshot["num_topics"],
                    snapshot["avg_drift"],
                    snapshot["avg_belief_stability"],
                    snapshot["avg_speech_entropy"],
                    snapshot["global_flip_rate"],
                    snapshot["details_json"],
                ),
            )
            conn.commit()
        finally:
            conn.close()

        snapshot["topics_updated"] = len(topic_metrics)
        log.info("Variance analysis complete: %d topics, avg_drift=%.4f", num_topics, snapshot["avg_drift"] or 0)

        # Governance bridge: feed drift metrics back into memory trust
        if self._governance_bridge is not None:
            try:
                bridge_result = self._governance_bridge.apply_drift_penalty(
                    {"topic_metrics": topic_metrics}
                )
                snapshot["bridge_result"] = bridge_result
                if bridge_result.get("memories_penalized", 0) > 0:
                    log.info(
                        "[GOVERNANCE_BRIDGE] %d memories penalized across %d flagged topics",
                        bridge_result["memories_penalized"],
                        bridge_result["topics_flagged"],
                    )
            except Exception as e:
                log.warning("[GOVERNANCE_BRIDGE] Drift penalty failed: %s", e)

        return snapshot

    def recluster_topics(self) -> int:
        """Recluster all belief_speech entries by query embedding similarity."""
        from sklearn.cluster import DBSCAN
        from sklearn.metrics.pairwise import cosine_distances

        conn = self._get_connection()
        try:
            rows = conn.execute(
                "SELECT entry_id, query_embedding, query, timestamp FROM belief_speech WHERE query_embedding IS NOT NULL"
            ).fetchall()
        finally:
            conn.close()

        if len(rows) < 3:
            log.info("Not enough entries with embeddings for clustering (%d)", len(rows))
            return 0

        entry_ids = [r[0] for r in rows]
        embeddings = np.array([np.frombuffer(r[1], dtype=np.float32) for r in rows])
        queries = [r[2] for r in rows]
        timestamps = [r[3] for r in rows]

        dist_matrix = cosine_distances(embeddings)
        clustering = DBSCAN(eps=0.35, min_samples=3, metric="precomputed").fit(dist_matrix)
        labels = clustering.labels_

        unique_labels = set(labels)
        unique_labels.discard(-1)

        conn = self._get_connection()
        try:
            # Reset all topic assignments
            conn.execute("UPDATE belief_speech SET topic_id = NULL WHERE query_embedding IS NOT NULL")

            # Clear old topics
            conn.execute("DELETE FROM opinion_topics")

            for cluster_label in sorted(unique_labels):
                mask = labels == cluster_label
                cluster_indices = np.where(mask)[0]

                cluster_embeddings = embeddings[cluster_indices]
                centroid = cluster_embeddings.mean(axis=0)
                norm = np.linalg.norm(centroid)
                if norm > 0:
                    centroid = centroid / norm

                cluster_queries = [queries[i] for i in cluster_indices]
                cluster_entry_ids = [entry_ids[i] for i in cluster_indices]
                cluster_timestamps = [timestamps[i] for i in cluster_indices]

                label_text = min(cluster_queries, key=len)[:60]

                cursor = conn.execute(
                    """INSERT INTO opinion_topics (label, centroid_embedding, entry_count, first_seen, last_seen)
                       VALUES (?, ?, ?, ?, ?)""",
                    (
                        label_text,
                        centroid.astype(np.float32).tobytes(),
                        len(cluster_indices),
                        min(cluster_timestamps),
                        max(cluster_timestamps),
                    ),
                )
                topic_id = cursor.lastrowid

                for eid in cluster_entry_ids:
                    conn.execute(
                        "UPDATE belief_speech SET topic_id=? WHERE entry_id=?",
                        (topic_id, eid),
                    )

            conn.commit()

            topic_count = conn.execute("SELECT COUNT(*) FROM opinion_topics").fetchone()[0]
        finally:
            conn.close()

        log.info("Reclustered into %d topics (%d noise entries)", topic_count, int((labels == -1).sum()))
        return topic_count

    def compute_topic_metrics(self, topic_id: int) -> Dict:
        """Compute drift, flip rate, entropy, and stability metrics for a topic."""
        from sklearn.cluster import DBSCAN
        from sklearn.metrics.pairwise import cosine_distances

        conn = self._get_connection()
        try:
            rows = conn.execute(
                """SELECT entry_id, timestamp, response, is_belief, response_embedding
                   FROM belief_speech
                   WHERE topic_id=? AND response_embedding IS NOT NULL
                   ORDER BY timestamp ASC""",
                (topic_id,),
            ).fetchall()
        finally:
            conn.close()

        if not rows:
            return {"entry_count": 0}

        response_embeddings = [np.frombuffer(r[4], dtype=np.float32) for r in rows]
        is_beliefs = [r[3] for r in rows]

        metrics: Dict = {"entry_count": len(rows)}

        # 1. Response drift (consecutive cosine distance)
        response_drift = []
        for i in range(1, len(response_embeddings)):
            drift = 1.0 - float(np.dot(response_embeddings[i - 1], response_embeddings[i]))
            response_drift.append(max(0.0, drift))  # clamp numerical noise

        metrics["response_drift"] = response_drift
        metrics["mean_drift"] = float(np.mean(response_drift)) if response_drift else None

        # 2. Belief flip count/rate
        flip_count = 0
        for i in range(1, len(is_beliefs)):
            if is_beliefs[i] != is_beliefs[i - 1]:
                flip_count += 1

        metrics["belief_flip_count"] = flip_count
        metrics["belief_flip_rate"] = flip_count / max(len(is_beliefs) - 1, 1)

        # 3. Opinion entropy (speech entries only)
        speech_embeddings = [
            response_embeddings[i] for i in range(len(rows)) if not is_beliefs[i]
        ]
        if len(speech_embeddings) >= 2:
            speech_matrix = np.array(speech_embeddings)
            dist = cosine_distances(speech_matrix)
            sub_clustering = DBSCAN(eps=0.3, min_samples=2, metric="precomputed").fit(dist)
            sub_labels = sub_clustering.labels_
            n_clusters = len(set(sub_labels) - {-1})
            # Entropy: more clusters = more diverse opinions
            if n_clusters > 0:
                cluster_sizes = []
                for cl in set(sub_labels):
                    if cl == -1:
                        continue
                    cluster_sizes.append(int((sub_labels == cl).sum()))
                total = sum(cluster_sizes)
                probs = [s / total for s in cluster_sizes]
                metrics["opinion_entropy"] = float(-sum(p * np.log2(p) for p in probs if p > 0))
            else:
                metrics["opinion_entropy"] = 0.0
        else:
            metrics["opinion_entropy"] = None

        # 4. Belief stability (belief entries only)
        belief_embeddings = [
            response_embeddings[i] for i in range(len(rows)) if is_beliefs[i]
        ]
        if len(belief_embeddings) >= 2:
            belief_matrix = np.array(belief_embeddings)
            pairwise_dist = cosine_distances(belief_matrix)
            n = len(belief_matrix)
            upper_tri = pairwise_dist[np.triu_indices(n, k=1)]
            metrics["belief_stability"] = 1.0 - float(np.mean(upper_tri))
        else:
            metrics["belief_stability"] = None

        # 5. Opinion entropy trend (linear regression on windowed entropy)
        if len(speech_embeddings) >= 5:
            window = 3
            entropies = []
            for start in range(len(speech_embeddings) - window + 1):
                window_embs = np.array(speech_embeddings[start : start + window])
                dist_w = cosine_distances(window_embs)
                sub_cl = DBSCAN(eps=0.3, min_samples=2, metric="precomputed").fit(dist_w)
                sub_l = sub_cl.labels_
                n_cl = len(set(sub_l) - {-1})
                if n_cl > 0:
                    sizes = [int((sub_l == c).sum()) for c in set(sub_l) if c != -1]
                    total = sum(sizes)
                    ps = [s / total for s in sizes]
                    entropies.append(float(-sum(p * np.log2(p) for p in ps if p > 0)))
                else:
                    entropies.append(0.0)

            if len(entropies) >= 2:
                x = np.arange(len(entropies), dtype=np.float64)
                y = np.array(entropies, dtype=np.float64)
                slope = float(np.polyfit(x, y, 1)[0])
                metrics["opinion_entropy_trend"] = slope
                if slope < -0.01:
                    metrics["convergence_direction"] = "converging"
                elif slope > 0.01:
                    metrics["convergence_direction"] = "diverging"
                else:
                    metrics["convergence_direction"] = "stable"
            else:
                metrics["opinion_entropy_trend"] = None
                metrics["convergence_direction"] = "stable"
        else:
            metrics["opinion_entropy_trend"] = None
            metrics["convergence_direction"] = None

        # 6. Memory count at analysis time
        conn = self._get_connection()
        try:
            metrics["memory_count_at_analysis"] = conn.execute(
                "SELECT COUNT(*) FROM belief_speech"
            ).fetchone()[0]

            conn.execute(
                "UPDATE opinion_topics SET metrics_json=?, last_analyzed=?, entry_count=? WHERE topic_id=?",
                (json.dumps(metrics, default=str), time.time(), len(rows), topic_id),
            )
            conn.commit()
        finally:
            conn.close()

        return metrics

    # ── Read methods (API) ─────────────────────────────────────────

    def get_all_topics_summary(self, min_entries: int = 3) -> List[Dict]:
        """Return summary for all topics meeting the minimum entry threshold."""
        conn = self._get_connection()
        try:
            rows = conn.execute(
                """SELECT topic_id, label, entry_count, first_seen, last_seen, metrics_json
                   FROM opinion_topics WHERE entry_count >= ?
                   ORDER BY last_seen DESC""",
                (min_entries,),
            ).fetchall()
        finally:
            conn.close()

        results = []
        for r in rows:
            metrics = json.loads(r[5]) if r[5] else {}
            results.append({
                "topic_id": r[0],
                "label": r[1],
                "entry_count": r[2],
                "first_seen": r[3],
                "last_seen": r[4],
                "metrics": metrics,
            })
        return results

    def get_topic_detail(self, topic_id: int) -> Dict:
        """Return full topic info including all entries with per-entry drift."""
        conn = self._get_connection()
        try:
            topic_row = conn.execute(
                "SELECT topic_id, label, entry_count, first_seen, last_seen, metrics_json FROM opinion_topics WHERE topic_id=?",
                (topic_id,),
            ).fetchone()

            if not topic_row:
                return {}

            entries = conn.execute(
                """SELECT entry_id, timestamp, query, response, is_belief, response_embedding
                   FROM belief_speech WHERE topic_id=? ORDER BY timestamp ASC""",
                (topic_id,),
            ).fetchall()
        finally:
            conn.close()

        entry_list = []
        flip_events = []
        prev_embedding = None
        prev_is_belief = None

        for e in entries:
            entry_dict = {
                "entry_id": e[0],
                "timestamp": e[1],
                "query": e[2],
                "response": e[3],
                "is_belief": bool(e[4]),
                "drift_from_previous": None,
            }

            if e[5] is not None:
                emb = np.frombuffer(e[5], dtype=np.float32)
                if prev_embedding is not None:
                    entry_dict["drift_from_previous"] = max(0.0, 1.0 - float(np.dot(prev_embedding, emb)))
                prev_embedding = emb

            if prev_is_belief is not None and e[4] != prev_is_belief:
                flip_events.append({
                    "entry_id": e[0],
                    "timestamp": e[1],
                    "from_belief": bool(prev_is_belief),
                    "to_belief": bool(e[4]),
                })
            prev_is_belief = e[4]

            entry_list.append(entry_dict)

        metrics = json.loads(topic_row[5]) if topic_row[5] else {}

        return {
            "topic_id": topic_row[0],
            "label": topic_row[1],
            "entry_count": topic_row[2],
            "first_seen": topic_row[3],
            "last_seen": topic_row[4],
            "metrics": metrics,
            "entries": entry_list,
            "flip_events": flip_events,
        }

    def get_global_snapshot(self) -> Optional[Dict]:
        """Return the most recent variance snapshot."""
        conn = self._get_connection()
        try:
            row = conn.execute(
                """SELECT snapshot_id, timestamp, num_topics, avg_drift, avg_belief_stability,
                          avg_speech_entropy, global_flip_rate, details_json
                   FROM variance_snapshots ORDER BY timestamp DESC LIMIT 1"""
            ).fetchone()
        finally:
            conn.close()

        if not row:
            return None

        return {
            "snapshot_id": row[0],
            "timestamp": row[1],
            "num_topics": row[2],
            "avg_drift": row[3],
            "avg_belief_stability": row[4],
            "avg_speech_entropy": row[5],
            "global_flip_rate": row[6],
            "details": json.loads(row[7]) if row[7] else {},
        }

    def get_snapshots(self, limit: int = 20) -> List[Dict]:
        """Return recent variance snapshots."""
        conn = self._get_connection()
        try:
            rows = conn.execute(
                """SELECT snapshot_id, timestamp, num_topics, avg_drift, avg_belief_stability,
                          avg_speech_entropy, global_flip_rate, details_json
                   FROM variance_snapshots ORDER BY timestamp DESC LIMIT ?""",
                (limit,),
            ).fetchall()
        finally:
            conn.close()

        return [
            {
                "snapshot_id": r[0],
                "timestamp": r[1],
                "num_topics": r[2],
                "avg_drift": r[3],
                "avg_belief_stability": r[4],
                "avg_speech_entropy": r[5],
                "global_flip_rate": r[6],
                "details": json.loads(r[7]) if r[7] else {},
            }
            for r in rows
        ]

    def get_embedding_map(self, dimensions: int = 2) -> Dict:
        """Return PCA-projected coordinates for all belief_speech entries.

        Args:
            dimensions: 2 for flat map, 3 for 3D belief space (default 2).
        """
        from sklearn.decomposition import PCA
        dimensions = max(2, min(3, dimensions))

        conn = self._get_connection()
        try:
            rows = conn.execute(
                """SELECT entry_id, timestamp, query, response, is_belief, trust_avg,
                          response_embedding, topic_id
                   FROM belief_speech
                   WHERE response_embedding IS NOT NULL
                   ORDER BY timestamp ASC"""
            ).fetchall()

            # Load topic labels
            topic_rows = conn.execute(
                "SELECT topic_id, label, centroid_embedding FROM opinion_topics"
            ).fetchall()
        finally:
            conn.close()

        if not rows:
            return {"points": [], "contradictions": [], "topics": []}

        entry_ids = [r[0] for r in rows]
        embeddings = np.array([np.frombuffer(r[6], dtype=np.float32) for r in rows])

        # PCA to N dimensions
        if len(embeddings) < 2:
            coords = np.zeros((len(embeddings), dimensions))
        else:
            n_comp = min(dimensions, len(embeddings))
            pca = PCA(n_components=n_comp)
            coords = pca.fit_transform(embeddings)
            # Pad if needed (fewer samples than dimensions)
            if coords.shape[1] < dimensions:
                coords = np.hstack([coords, np.zeros((len(coords), dimensions - coords.shape[1]))])

        # Normalize to [-1, 1] range for frontend
        if coords.size > 0:
            for dim in range(dimensions):
                vmin, vmax = coords[:, dim].min(), coords[:, dim].max()
                span = vmax - vmin
                if span > 1e-8:
                    coords[:, dim] = 2.0 * (coords[:, dim] - vmin) / span - 1.0

        # Build topic lookup
        topic_labels = {r[0]: r[1] for r in topic_rows}

        # Build points
        points = []
        for i, r in enumerate(rows):
            pt = {
                "entry_id": r[0],
                "x": round(float(coords[i, 0]), 4),
                "y": round(float(coords[i, 1]), 4),
                "is_belief": bool(r[4]),
                "trust_avg": r[5],
                "topic_id": r[7],
                "topic_label": topic_labels.get(r[7]),
                "query": (r[2] or "")[:80],
                "response_preview": (r[3] or "")[:120],
                "timestamp": r[1],
            }
            if dimensions >= 3:
                pt["z"] = round(float(coords[i, 2]), 4)
            points.append(pt)

        # Project topic centroids (store raw PCA range for normalization)
        topics = []
        if topic_rows and len(embeddings) >= 2:
            raw_coords = pca.transform(embeddings)
            for tr in topic_rows:
                centroid = np.frombuffer(tr[2], dtype=np.float32).reshape(1, -1)
                try:
                    c_proj = pca.transform(centroid)[0]
                    for dim in range(min(dimensions, len(c_proj))):
                        vmin, vmax = raw_coords[:, dim].min(), raw_coords[:, dim].max()
                        span = vmax - vmin
                        if span > 1e-8:
                            c_proj[dim] = 2.0 * (c_proj[dim] - vmin) / span - 1.0
                    t_entry = {
                        "topic_id": tr[0],
                        "label": tr[1],
                        "centroid_x": round(float(c_proj[0]), 4),
                        "centroid_y": round(float(c_proj[1]), 4),
                    }
                    if dimensions >= 3 and len(c_proj) >= 3:
                        t_entry["centroid_z"] = round(float(c_proj[2]), 4)
                    topics.append(t_entry)
                except Exception:
                    topics.append({
                        "topic_id": tr[0], "label": tr[1],
                        "centroid_x": 0.0, "centroid_y": 0.0,
                    })

        # --- Contradiction edges from ledger ---
        contradictions = []
        try:
            from personal_agent.crt_ledger import ContradictionLedger
            from pathlib import Path as _Path_vt
            # Derive ledger DB path from memory DB path
            _mem_db = str(getattr(self, 'db_path', '') or '')
            _ledger_candidates = [
                _mem_db.replace("_memory_", "_ledger_").replace("crt_memory_", "crt_ledger_"),
                str(_Path_vt(_mem_db).parent / "crt_ledger_shared.db"),
            ]
            _ledger_path = None
            for _lc in _ledger_candidates:
                if _lc and _Path_vt(_lc).exists():
                    _ledger_path = _lc
                    break

            if _ledger_path:
                _ledger = ContradictionLedger(db_path=_ledger_path)
                _open = _ledger.get_open_contradictions(limit=50)
                _resolved = []
                try:
                    _resolved = _ledger.get_resolved_contradictions(limit=50)
                except Exception:
                    pass

                # Map memory IDs to belief_speech entry IDs
                # The belief_speech table stores queries, not memory_ids directly.
                # But we can include memory_id pairs for the frontend to match.
                _entry_id_set = set(entry_ids)
                for c in (_open + _resolved):
                    contradictions.append({
                        "entry_id_a": c.old_memory_id,
                        "entry_id_b": c.new_memory_id,
                        "ledger_id": c.ledger_id,
                        "status": c.status,
                        "type": getattr(c, 'contradiction_type', 'unknown'),
                        "disposition": getattr(c, 'disposition', 'unknown'),
                        "slots": getattr(c, 'affects_slots', ''),
                        "summary": (getattr(c, 'summary', '') or '')[:150],
                    })
        except Exception as _ledger_err:
            import logging
            logging.getLogger(__name__).debug("[BELIEF_MAP] Ledger query failed: %s", _ledger_err)

        # --- BDG dependency edges ---
        bdg_edges = []
        try:
            from personal_agent.memory_graph import get_live_bdg
            _bdg = get_live_bdg()
            if _bdg:
                _bdg.ensure_built()
                _graph = _bdg.bdg.graph if hasattr(_bdg, 'bdg') and _bdg.bdg else None
                if _graph and _graph.number_of_edges() > 0:
                    for src, tgt, edata in _graph.edges(data=True):
                        bdg_edges.append({
                            "source": src,
                            "target": tgt,
                            "edge_type": edata.get("edge_type", "SUPPORTS"),
                            "weight": round(float(edata.get("weight", 0.5)), 3),
                        })
        except Exception as _bdg_err:
            import logging
            logging.getLogger(__name__).debug("[BELIEF_MAP] BDG edge query failed: %s", _bdg_err)

        return {
            "points": points,
            "contradictions": contradictions,
            "topics": topics,
            "bdg_edges": bdg_edges,
        }
