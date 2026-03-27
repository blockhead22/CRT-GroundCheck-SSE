"""Phase G5: Analysis endpoints — topology, memory graph, Fisher decomposition.

On-demand diagnostic endpoints for belief geometry inspection.
"""

from __future__ import annotations

import json
import logging
import os
import sqlite3
import time
from typing import Any, Dict, List, Optional

import numpy as np
from fastapi import APIRouter, HTTPException, Query, Request

logger = logging.getLogger(__name__)
router = APIRouter()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_engine(request: Request, thread_id: str):
    return request.app.state.get_engine(thread_id)


def _build_splats_from_engine(engine, limit: int = 200) -> list:
    """Build MemorySplat objects from the memory system."""
    from personal_agent.memory_splats import MemorySplat

    db_path = getattr(engine.memory, "db_path", None)
    if not db_path or not os.path.exists(db_path):
        return []

    conn = sqlite3.connect(db_path, timeout=5)
    rows = conn.execute(
        """SELECT memory_id, vector_json, sigma, trust, text, memory_type,
                  timestamp, access_count, contradiction_count
           FROM memories
           WHERE deprecated = 0 AND sigma IS NOT NULL
           ORDER BY timestamp DESC LIMIT ?""",
        (limit,),
    ).fetchall()
    conn.close()

    splats = []
    for mid, vec_json, sigma_blob, trust, text, mtype, ts, acc, contra in rows:
        try:
            mu = np.array(json.loads(vec_json), dtype=np.float32)
            sigma = np.frombuffer(sigma_blob, dtype=np.float32)
            splat = MemorySplat(
                memory_id=mid, mu=mu, sigma=sigma,
                alpha=trust if trust is not None else 0.5,
                text=text or "", memory_type=mtype or "observation",
                created_at=ts or 0.0, last_updated=ts or 0.0,
                update_count=int(acc or 0) + int(contra or 0),
            )
            splats.append(splat)
        except Exception:
            continue
    return splats


# ---------------------------------------------------------------------------
# 18. Belief topology analysis
# ---------------------------------------------------------------------------

@router.get("/api/analysis/topology")
def belief_topology(
    request: Request,
    thread_id: str = Query(default="default"),
    distance: str = Query(default="confidence_weighted"),
    limit: int = Query(default=100, ge=10, le=500),
) -> Dict[str, Any]:
    """Run persistent homology on the belief space.

    Returns Betti numbers, significant features, and interpretation.
    """
    try:
        from personal_agent.belief_topology import compute_topology
    except ImportError as e:
        raise HTTPException(status_code=501, detail=f"ripser not available: {e}")

    engine = _get_engine(request, thread_id)
    splats = _build_splats_from_engine(engine, limit=limit)

    if len(splats) < 3:
        return {"error": "Need at least 3 memories with sigma for topology analysis",
                "n_memories": len(splats)}

    topo = compute_topology(splats, distance_fn=distance, max_dim=1)

    features = []
    for f in topo.features:
        features.append({
            "dimension": f.dimension,
            "birth": round(f.birth, 4),
            "death": round(f.death, 4),
            "persistence": round(f.persistence, 4),
        })

    return {
        "n_memories": topo.n_memories,
        "betti_0": topo.betti_0,
        "betti_1": topo.betti_1,
        "betti_2": topo.betti_2,
        "n_significant_h0": topo.n_significant_h0,
        "n_significant_h1": topo.n_significant_h1,
        "max_persistence_h0": round(topo.max_persistence_h0, 4),
        "max_persistence_h1": round(topo.max_persistence_h1, 4),
        "interpretation": topo.interpretation,
        "features": features[:50],
        "distance_fn": distance,
    }


# ---------------------------------------------------------------------------
# 19. Memory graph visualization
# ---------------------------------------------------------------------------

@router.get("/api/analysis/graph")
def memory_graph(
    request: Request,
    thread_id: str = Query(default="default"),
    center_id: Optional[str] = Query(default=None),
    hops: int = Query(default=2, ge=1, le=4),
    limit: int = Query(default=100, ge=10, le=500),
) -> Dict[str, Any]:
    """Return memory graph as nodes + edges for visualization.

    If center_id is provided, returns subgraph within `hops` distance.
    Otherwise returns the top `limit` memories by recency with their edges.
    """
    engine = _get_engine(request, thread_id)
    db_path = getattr(engine.memory, "db_path", None)
    if not db_path or not os.path.exists(db_path):
        raise HTTPException(status_code=404, detail="Memory database not found")

    ledger_path = db_path.replace("_memory", "_ledger")
    if "_memory" not in db_path:
        ledger_path = db_path.replace(".db", "_ledger.db")

    # Build nodes from memory DB
    conn = sqlite3.connect(db_path, timeout=5)
    rows = conn.execute(
        """SELECT memory_id, text, trust, confidence, timestamp,
                  memory_type, belnap_state, kind
           FROM memories
           WHERE deprecated = 0
           ORDER BY timestamp DESC LIMIT ?""",
        (limit,),
    ).fetchall()
    conn.close()

    node_ids = set()
    nodes = []
    for mid, text, trust, conf, ts, mtype, belnap, kind in rows:
        node_ids.add(mid)
        nodes.append({
            "id": mid,
            "text": (text or "")[:120],
            "trust": round(trust, 3) if trust else 0.5,
            "confidence": round(conf, 3) if conf else 0.5,
            "timestamp": ts,
            "memory_type": mtype or "observation",
            "belnap_state": belnap or "true",
            "kind": kind or "observation",
        })

    # Build edges from contradiction ledger
    edges = []
    if os.path.exists(ledger_path):
        lconn = sqlite3.connect(ledger_path, timeout=5)
        try:
            lrows = lconn.execute(
                """SELECT old_memory_id, new_memory_id, contradiction_type,
                          disposition, status, drift_mean
                   FROM contradictions
                   ORDER BY timestamp DESC LIMIT ?""",
                (limit * 2,),
            ).fetchall()
            for old_id, new_id, ctype, disp, status, drift in lrows:
                if old_id in node_ids or new_id in node_ids:
                    edges.append({
                        "source": old_id,
                        "target": new_id,
                        "type": "CONTRADICTS",
                        "contradiction_type": ctype,
                        "disposition": disp,
                        "status": status,
                        "drift": round(drift, 4) if drift else None,
                    })
        except Exception:
            pass
        lconn.close()

    # Filter to subgraph if center_id specified
    if center_id:
        # BFS to find nodes within hops
        reachable = {center_id}
        frontier = {center_id}
        for _ in range(hops):
            next_frontier = set()
            for edge in edges:
                if edge["source"] in frontier:
                    next_frontier.add(edge["target"])
                if edge["target"] in frontier:
                    next_frontier.add(edge["source"])
            frontier = next_frontier - reachable
            reachable |= frontier

        nodes = [n for n in nodes if n["id"] in reachable]
        edges = [e for e in edges if e["source"] in reachable and e["target"] in reachable]

    return {
        "nodes": nodes,
        "edges": edges,
        "node_count": len(nodes),
        "edge_count": len(edges),
    }


# ---------------------------------------------------------------------------
# 20. Fisher decomposition — "why do these beliefs disagree?"
# ---------------------------------------------------------------------------

@router.get("/api/analysis/fisher")
def fisher_decomposition(
    request: Request,
    memory_a: str = Query(..., description="First memory ID"),
    memory_b: str = Query(..., description="Second memory ID"),
    thread_id: str = Query(default="default"),
    top_k: int = Query(default=20, ge=5, le=50),
) -> Dict[str, Any]:
    """Decompose disagreement between two memories using Fisher-Rao geometry.

    Returns per-dimension contributions showing which embedding dimensions
    drive the disagreement and whether it's center distance or uncertainty mismatch.
    """
    from personal_agent.memory_splats import MemorySplat
    from personal_agent.info_geometry import (
        fisher_rao_distance,
        fisher_mean_component,
        fisher_cov_component,
        fisher_dimension_contributions,
    )

    engine = _get_engine(request, thread_id)
    db_path = getattr(engine.memory, "db_path", None)
    if not db_path:
        raise HTTPException(status_code=404, detail="Memory database not found")

    conn = sqlite3.connect(db_path, timeout=5)

    def _load_splat(mid: str) -> Optional[MemorySplat]:
        row = conn.execute(
            """SELECT memory_id, vector_json, sigma, trust, text, memory_type, timestamp
               FROM memories WHERE memory_id = ?""",
            (mid,),
        ).fetchone()
        if not row or not row[2]:
            return None
        return MemorySplat(
            memory_id=row[0],
            mu=np.array(json.loads(row[1]), dtype=np.float32),
            sigma=np.frombuffer(row[2], dtype=np.float32),
            alpha=row[3] if row[3] else 0.5,
            text=row[4] or "",
            memory_type=row[5] or "observation",
            created_at=row[6] or 0.0,
        )

    splat_a = _load_splat(memory_a)
    splat_b = _load_splat(memory_b)
    conn.close()

    if not splat_a:
        raise HTTPException(status_code=404, detail=f"Memory {memory_a} not found or has no sigma")
    if not splat_b:
        raise HTTPException(status_code=404, detail=f"Memory {memory_b} not found or has no sigma")

    # Compute Fisher metrics
    total_dist = fisher_rao_distance(splat_a, splat_b)
    mean_component = fisher_mean_component(splat_a, splat_b)
    cov_component = fisher_cov_component(splat_a, splat_b)
    per_dim, top_dims = fisher_dimension_contributions(splat_a, splat_b, top_k=top_k)

    # Cosine similarity for context
    cos_sim = float(np.dot(splat_a.mu, splat_b.mu) / (
        np.linalg.norm(splat_a.mu) * np.linalg.norm(splat_b.mu) + 1e-10
    ))

    top_dimensions = []
    for dim_idx, contribution, reason in top_dims:
        top_dimensions.append({
            "dimension": int(dim_idx),
            "contribution": round(float(contribution), 6),
            "reason": reason,
        })

    return {
        "memory_a": {"id": memory_a, "text": splat_a.text[:120], "type": splat_a.memory_type},
        "memory_b": {"id": memory_b, "text": splat_b.text[:120], "type": splat_b.memory_type},
        "fisher_distance": round(float(total_dist), 4),
        "mean_component": round(float(mean_component), 4),
        "cov_component": round(float(cov_component), 4),
        "mean_pct": round(float(mean_component / max(total_dist, 1e-10) * 100), 1),
        "cov_pct": round(float(cov_component / max(total_dist, 1e-10) * 100), 1),
        "cosine_similarity": round(cos_sim, 4),
        "top_dimensions": top_dimensions,
        "interpretation": _interpret_fisher(total_dist, mean_component, cov_component, cos_sim),
    }


def _interpret_fisher(
    total: float, mean_comp: float, cov_comp: float, cosine: float,
) -> str:
    """Generate human-readable interpretation of Fisher decomposition."""
    if total < 0.01:
        return "These beliefs are essentially identical in the geometric space."

    mean_pct = mean_comp / max(total, 1e-10) * 100
    parts = []

    if mean_pct > 70:
        parts.append("Disagreement is driven by center distance — these beliefs point to different facts.")
    elif mean_pct < 30:
        parts.append("Disagreement is driven by uncertainty mismatch — one belief is much more certain than the other.")
    else:
        parts.append("Disagreement comes from both factual difference and uncertainty mismatch.")

    if cosine > 0.8:
        parts.append("High cosine similarity means they're about the same topic.")
    elif cosine > 0.4:
        parts.append("Moderate topic overlap — related but distinct claims.")
    else:
        parts.append("Low topic overlap — these may not be directly comparable.")

    return " ".join(parts)
