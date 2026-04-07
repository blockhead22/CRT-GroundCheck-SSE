"""Agent run log analytics endpoints.

Exposes execution data from agent_runs.db for the run log dashboard.
"""

from __future__ import annotations

import json
import logging
import time
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Query

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/agent-runs", tags=["agent-runs"])


def _get_db():
    from personal_agent.agent_run_log import get_run_log_db
    return get_run_log_db()


@router.get("/analytics")
def get_analytics() -> Dict[str, Any]:
    """Aggregate analytics across all orchestrator runs."""
    try:
        db = _get_db()
        return db.get_analytics()
    except Exception as e:
        logger.warning("[AGENT_RUNS] Analytics failed: %s", e)
        return {"error": str(e)}


@router.get("/recent")
def get_recent_runs(
    limit: int = Query(20, ge=1, le=200),
) -> List[Dict[str, Any]]:
    """Recent runs ordered by timestamp DESC."""
    try:
        db = _get_db()
        runs = db.get_recent_runs(limit=limit)
        # Parse JSON fields for frontend consumption
        result = []
        for r in runs:
            row = dict(r) if hasattr(r, 'keys') else r
            # Parse steps_json for per-step alignment data
            steps = []
            try:
                steps = json.loads(row.get("steps_json") or "[]")
            except Exception:
                pass
            row["steps"] = steps
            row["step_count"] = len(steps)
            # Parse drift_json
            drifts = []
            try:
                drifts = json.loads(row.get("drift_json") or "[]")
            except Exception:
                pass
            row["drifts"] = drifts
            # Alignment summary
            alignments = [s.get("intent_alignment") for s in steps
                         if s.get("intent_alignment") is not None]
            row["alignment_min"] = min(alignments) if alignments else None
            row["alignment_max"] = max(alignments) if alignments else None
            row["alignment_avg"] = (sum(alignments) / len(alignments)) if alignments else None
            # Clean up large JSON fields for list view
            row.pop("steps_json", None)
            row.pop("drift_json", None)
            row.pop("metadata_json", None)
            result.append(row)
        return result
    except Exception as e:
        logger.warning("[AGENT_RUNS] Recent runs failed: %s", e)
        return []


@router.get("/timeline")
def get_timeline(
    group_by: str = Query("day"),
    days: int = Query(30, ge=1, le=365),
) -> List[Dict[str, Any]]:
    """Runs grouped by time bucket for timeline chart."""
    try:
        import sqlite3
        from personal_agent.agent_run_log import _DB_PATH
        conn = sqlite3.connect(str(_DB_PATH))
        conn.row_factory = sqlite3.Row

        cutoff = time.time() - (days * 86400)

        if group_by == "hour":
            bucket_sql = "CAST(timestamp / 3600 AS INTEGER) * 3600"
        else:
            bucket_sql = "CAST(timestamp / 86400 AS INTEGER) * 86400"

        rows = conn.execute(f"""
            SELECT {bucket_sql} as bucket,
                   COUNT(*) as run_count,
                   AVG(total_iterations) as avg_iterations,
                   AVG(total_ms) as avg_latency_ms,
                   SUM(CASE WHEN success = 1 THEN 1 ELSE 0 END) as success_count,
                   SUM(drift_count) as total_drifts
            FROM agent_runs
            WHERE timestamp > ?
            GROUP BY bucket
            ORDER BY bucket
        """, (cutoff,)).fetchall()

        result = []
        for r in rows:
            result.append({
                "timestamp": r["bucket"],
                "run_count": r["run_count"],
                "avg_iterations": round(r["avg_iterations"] or 0, 1),
                "avg_latency_ms": round(r["avg_latency_ms"] or 0, 0),
                "success_rate": round((r["success_count"] or 0) / max(1, r["run_count"]), 2),
                "total_drifts": r["total_drifts"] or 0,
            })

        conn.close()
        return result
    except Exception as e:
        logger.warning("[AGENT_RUNS] Timeline failed: %s", e)
        return []


@router.get("/tool-usage")
def get_tool_usage() -> Dict[str, int]:
    """Tool usage distribution across all runs."""
    try:
        import sqlite3
        from personal_agent.agent_run_log import _DB_PATH
        conn = sqlite3.connect(str(_DB_PATH))

        rows = conn.execute("SELECT tools_called FROM agent_runs WHERE tools_called IS NOT NULL").fetchall()
        counts: Dict[str, int] = {}
        for r in rows:
            try:
                tools = json.loads(r[0] or "[]")
                for t in tools:
                    counts[t] = counts.get(t, 0) + 1
            except Exception:
                pass

        conn.close()
        # Sort by frequency
        return dict(sorted(counts.items(), key=lambda x: -x[1]))
    except Exception as e:
        logger.warning("[AGENT_RUNS] Tool usage failed: %s", e)
        return {}


@router.get("/activations/stats")
def get_activation_stats() -> Dict[str, Any]:
    """Aggregate activation statistics."""
    try:
        from personal_agent.activation_log import get_activation_stats
        return get_activation_stats("personal_agent/crt_memory_shared.db")
    except Exception as e:
        return {"error": str(e)}


@router.get("/activations/recent")
def get_recent_activations(
    limit: int = Query(20, ge=1, le=100),
    thread_id: Optional[str] = Query(None),
) -> List[Dict[str, Any]]:
    """Recent retrieval activations with PCA coords and edges."""
    try:
        from personal_agent.activation_log import get_recent_activations
        return get_recent_activations(
            "personal_agent/crt_memory_shared.db",
            limit=limit,
            thread_id=thread_id,
        )
    except Exception as e:
        return []


@router.get("/activations/coactivation")
def get_coactivation(
    min_count: int = Query(3, ge=2, le=50),
) -> List[Dict[str, Any]]:
    """Memory pairs that frequently co-activate."""
    try:
        from personal_agent.activation_log import get_coactivation_matrix
        return get_coactivation_matrix(
            "personal_agent/crt_memory_shared.db",
            min_coactivations=min_count,
        )
    except Exception as e:
        return []


@router.get("/activations/dead-memories")
def get_dead_memories(
    min_trust: float = Query(0.3, ge=0.0, le=1.0),
) -> List[Dict[str, Any]]:
    """High-trust memories that never activate in recent retrievals."""
    try:
        from personal_agent.activation_log import get_dead_memories
        return get_dead_memories(
            "personal_agent/crt_memory_shared.db",
            "personal_agent/crt_memory_shared.db",
            min_trust=min_trust,
        )
    except Exception as e:
        return []


@router.get("/{run_id}")
def get_run_detail(run_id: str) -> Dict[str, Any]:
    """Full detail for a single run including steps and drift events."""
    try:
        import sqlite3
        from personal_agent.agent_run_log import _DB_PATH
        conn = sqlite3.connect(str(_DB_PATH))
        conn.row_factory = sqlite3.Row

        row = conn.execute("SELECT * FROM agent_runs WHERE run_id = ?", (run_id,)).fetchone()
        conn.close()

        if not row:
            return {"error": "Run not found"}

        result = dict(row)
        result["steps"] = json.loads(result.pop("steps_json", "[]") or "[]")
        result["drifts"] = json.loads(result.pop("drift_json", "[]") or "[]")
        result["metadata"] = json.loads(result.pop("metadata_json", "{}") or "{}")
        return result
    except Exception as e:
        logger.warning("[AGENT_RUNS] Run detail failed: %s", e)
        return {"error": str(e)}
