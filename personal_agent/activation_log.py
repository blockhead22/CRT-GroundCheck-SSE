"""
Retrieval Activation Logging
============================

Logs every retrieval activation pattern: which memories fired, scores, edges,
contradictions triggered. Over time these patterns become data for:
- Co-activation frequency (memories that always fire together)
- Dead memory detection (high-trust but never activated)
- Fragile region mapping (queries that consistently trigger contradictions)
- Retrieval patterns AS beliefs about relevance

Storage: SQLite table `retrieval_activations` in the memory DB.
"""

from __future__ import annotations

import json
import logging
import sqlite3
import time
import hashlib
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


@dataclass
class ActivationRecord:
    """A single retrieval activation event."""
    activation_id: str = ""
    timestamp: float = 0.0
    thread_id: str = ""
    query: str = ""
    query_hash: str = ""  # for dedup / co-activation grouping

    # What activated
    memory_ids: List[str] = field(default_factory=list)
    scores: List[float] = field(default_factory=list)
    trusts: List[float] = field(default_factory=list)
    kinds: List[str] = field(default_factory=list)

    # Edges between activated memories
    edges: List[Dict[str, Any]] = field(default_factory=list)  # [{from, to, type, weight}]

    # Contradictions triggered
    contradictions_detected: int = 0
    contradiction_ids: List[str] = field(default_factory=list)

    # PCA coordinates (for replay)
    pca_coords: List[Dict[str, float]] = field(default_factory=list)  # [{x, y, memory_id}]

    # Response metadata
    belief_confidence: float = 0.0
    response_type: str = ""  # "belief" | "speech"
    generation_source: str = ""  # "local" | "cloud_claude" | "openai"


# ---------------------------------------------------------------------------
# Schema
# ---------------------------------------------------------------------------

_SCHEMA = """
CREATE TABLE IF NOT EXISTS retrieval_activations (
    activation_id TEXT PRIMARY KEY,
    timestamp REAL NOT NULL,
    thread_id TEXT,
    query TEXT,
    query_hash TEXT,
    memory_ids_json TEXT,
    scores_json TEXT,
    trusts_json TEXT,
    kinds_json TEXT,
    edges_json TEXT,
    pca_coords_json TEXT,
    contradictions_detected INTEGER DEFAULT 0,
    contradiction_ids_json TEXT,
    belief_confidence REAL,
    response_type TEXT,
    generation_source TEXT,
    memory_count INTEGER DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_activations_timestamp ON retrieval_activations(timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_activations_thread ON retrieval_activations(thread_id);
CREATE INDEX IF NOT EXISTS idx_activations_query_hash ON retrieval_activations(query_hash);
"""


def _init_db(db_path: str):
    conn = sqlite3.connect(db_path)
    conn.executescript(_SCHEMA)
    conn.close()


# ---------------------------------------------------------------------------
# Write
# ---------------------------------------------------------------------------

def log_activation(
    db_path: str,
    record: ActivationRecord,
) -> None:
    """Persist an activation record."""
    try:
        _init_db(db_path)
        conn = sqlite3.connect(db_path)
        conn.execute(
            """INSERT OR REPLACE INTO retrieval_activations
               (activation_id, timestamp, thread_id, query, query_hash,
                memory_ids_json, scores_json, trusts_json, kinds_json,
                edges_json, pca_coords_json,
                contradictions_detected, contradiction_ids_json,
                belief_confidence, response_type, generation_source, memory_count)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                record.activation_id,
                record.timestamp,
                record.thread_id,
                record.query[:500],
                record.query_hash,
                json.dumps(record.memory_ids),
                json.dumps([round(s, 4) for s in record.scores]),
                json.dumps([round(t, 3) for t in record.trusts]),
                json.dumps(record.kinds),
                json.dumps(record.edges),
                json.dumps(record.pca_coords),
                record.contradictions_detected,
                json.dumps(record.contradiction_ids),
                record.belief_confidence,
                record.response_type,
                record.generation_source,
                len(record.memory_ids),
            ),
        )
        conn.commit()
        conn.close()
    except Exception as e:
        logger.debug(f"[ACTIVATION_LOG] Failed to write: {e}")


# ---------------------------------------------------------------------------
# Read / Analytics
# ---------------------------------------------------------------------------

def get_recent_activations(
    db_path: str,
    limit: int = 20,
    thread_id: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Get recent activation records."""
    try:
        _init_db(db_path)
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        if thread_id:
            rows = conn.execute(
                "SELECT * FROM retrieval_activations WHERE thread_id=? ORDER BY timestamp DESC LIMIT ?",
                (thread_id, limit),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM retrieval_activations ORDER BY timestamp DESC LIMIT ?",
                (limit,),
            ).fetchall()
        conn.close()
        return [_row_to_dict(r) for r in rows]
    except Exception:
        return []


def get_coactivation_matrix(
    db_path: str,
    min_coactivations: int = 3,
    limit: int = 500,
) -> List[Dict[str, Any]]:
    """Find memory pairs that frequently co-activate.

    Returns list of {memory_a, memory_b, count, avg_score_a, avg_score_b}.
    """
    try:
        _init_db(db_path)
        conn = sqlite3.connect(db_path)
        rows = conn.execute(
            "SELECT memory_ids_json, scores_json FROM retrieval_activations ORDER BY timestamp DESC LIMIT ?",
            (limit,),
        ).fetchall()
        conn.close()

        # Count co-occurrences
        pair_counts: Dict[Tuple[str, str], int] = {}
        pair_scores: Dict[Tuple[str, str], List[Tuple[float, float]]] = {}

        for r in rows:
            mids = json.loads(r[0] or "[]")
            scores = json.loads(r[1] or "[]")
            score_map = dict(zip(mids, scores)) if len(mids) == len(scores) else {}

            for i in range(len(mids)):
                for j in range(i + 1, len(mids)):
                    pair = tuple(sorted([mids[i], mids[j]]))
                    pair_counts[pair] = pair_counts.get(pair, 0) + 1
                    if pair not in pair_scores:
                        pair_scores[pair] = []
                    pair_scores[pair].append((
                        score_map.get(mids[i], 0),
                        score_map.get(mids[j], 0),
                    ))

        result = []
        for pair, count in sorted(pair_counts.items(), key=lambda x: -x[1]):
            if count >= min_coactivations:
                scores_a = [s[0] for s in pair_scores[pair]]
                scores_b = [s[1] for s in pair_scores[pair]]
                result.append({
                    "memory_a": pair[0],
                    "memory_b": pair[1],
                    "count": count,
                    "avg_score_a": round(sum(scores_a) / len(scores_a), 4),
                    "avg_score_b": round(sum(scores_b) / len(scores_b), 4),
                })

        return result
    except Exception:
        return []


def get_dead_memories(
    db_path: str,
    memory_db_path: str,
    lookback_activations: int = 200,
    min_trust: float = 0.3,
) -> List[Dict[str, Any]]:
    """Find high-trust memories that never activate in recent retrievals."""
    try:
        _init_db(db_path)
        conn = sqlite3.connect(db_path)

        # Collect all memory IDs that activated recently
        rows = conn.execute(
            "SELECT memory_ids_json FROM retrieval_activations ORDER BY timestamp DESC LIMIT ?",
            (lookback_activations,),
        ).fetchall()
        conn.close()

        activated_ids = set()
        for r in rows:
            mids = json.loads(r[0] or "[]")
            activated_ids.update(mids)

        # Get all active memories above trust threshold
        mem_conn = sqlite3.connect(memory_db_path)
        mem_conn.row_factory = sqlite3.Row
        all_mems = mem_conn.execute(
            "SELECT memory_id, text, trust FROM memories WHERE deprecated=0 AND trust >= ?",
            (min_trust,),
        ).fetchall()
        mem_conn.close()

        dead = []
        for m in all_mems:
            if m["memory_id"] not in activated_ids:
                dead.append({
                    "memory_id": m["memory_id"],
                    "text": m["text"][:150],
                    "trust": m["trust"],
                })

        return sorted(dead, key=lambda x: -x["trust"])
    except Exception:
        return []


def get_activation_stats(db_path: str) -> Dict[str, Any]:
    """Aggregate activation statistics."""
    try:
        _init_db(db_path)
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row

        total = conn.execute("SELECT COUNT(*) FROM retrieval_activations").fetchone()[0]
        avg_count = conn.execute("SELECT AVG(memory_count) FROM retrieval_activations").fetchone()[0]
        avg_confidence = conn.execute("SELECT AVG(belief_confidence) FROM retrieval_activations WHERE belief_confidence > 0").fetchone()[0]
        contra_rate = conn.execute(
            "SELECT CAST(SUM(CASE WHEN contradictions_detected > 0 THEN 1 ELSE 0 END) AS REAL) / MAX(1, COUNT(*)) FROM retrieval_activations"
        ).fetchone()[0]

        conn.close()
        return {
            "total_activations": total,
            "avg_memories_per_query": round(avg_count or 0, 1),
            "avg_belief_confidence": round(avg_confidence or 0, 3),
            "contradiction_trigger_rate": round(contra_rate or 0, 3),
        }
    except Exception:
        return {}


def _row_to_dict(row) -> Dict[str, Any]:
    d = dict(row)
    for key in ("memory_ids_json", "scores_json", "trusts_json", "kinds_json",
                "edges_json", "pca_coords_json", "contradiction_ids_json"):
        if key in d:
            try:
                d[key.replace("_json", "")] = json.loads(d.pop(key) or "[]")
            except Exception:
                d[key.replace("_json", "")] = []
    return d


def make_query_hash(query: str) -> str:
    """Stable hash for grouping similar queries."""
    # Normalize: lowercase, strip, first 200 chars
    normalized = query.lower().strip()[:200]
    return hashlib.md5(normalized.encode()).hexdigest()[:12]
