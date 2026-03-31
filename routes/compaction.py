"""Compaction & Consolidation route module.

Provides manual triggers for:
- Belief-aware compaction (produces a BeliefSnapshot)
- Memory consolidation (batch NLI contradiction sweep)
- Compaction event history
"""

from __future__ import annotations

import logging
import time
from typing import Optional

from fastapi import APIRouter, HTTPException, Query, Request

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["compaction"])


def _resolve_db_paths(thread_id: str):
    """Resolve memory and ledger DB paths for a thread."""
    import os
    pa_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "personal_agent")
    mem_db = os.path.join(pa_dir, f"crt_memory_{thread_id}.db")
    led_db = os.path.join(pa_dir, f"crt_ledger_{thread_id}.db")
    return mem_db, led_db


@router.post("/compaction/run")
async def run_compaction(
    request: Request,
    thread_id: str = Query("default"),
    token_budget: int = Query(4000),
):
    """Manually trigger belief-aware compaction."""
    from personal_agent.context_feed import build_compacted_context

    mem_db, _ = _resolve_db_paths(thread_id)

    try:
        result = build_compacted_context(
            thread_id=thread_id,
            memory_db_path=mem_db,
            token_budget=token_budget,
            trigger="manual",
        )
        return {
            "status": "ok",
            "thread_id": thread_id,
            "token_budget": token_budget,
            "snapshot_text_length": len(result),
            "snapshot_preview": result[:500] if result else "",
        }
    except Exception as e:
        logger.error(f"[COMPACTION] Manual run failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/consolidation/run")
async def run_consolidation(
    request: Request,
    thread_id: str = Query("default"),
    max_pairs: int = Query(50),
):
    """Manually trigger memory consolidation pass."""
    import os
    from personal_agent.crt_memory import CRTMemorySystem
    from personal_agent.crt_ledger import ContradictionLedger
    from personal_agent.memory_consolidation import run_consolidation_pass

    mem_db, led_db = _resolve_db_paths(thread_id)

    if not os.path.exists(mem_db):
        raise HTTPException(status_code=404, detail=f"Memory DB not found for thread {thread_id}")

    try:
        mem_sys = CRTMemorySystem(db_path=mem_db)
        ledger = ContradictionLedger(db_path=led_db)

        # Try to load memory graph
        memory_graph = None
        try:
            from personal_agent.memory_graph import MemoryGraph
            memory_graph = MemoryGraph()
        except ImportError:
            pass

        result = run_consolidation_pass(
            memory_system=mem_sys,
            ledger=ledger,
            memory_graph=memory_graph,
            max_pairs=max_pairs,
        )

        return {
            "status": "ok",
            "thread_id": thread_id,
            "pairs_checked": result.pairs_checked,
            "new_contradictions_found": result.new_contradictions_found,
            "auto_resolved": result.auto_resolved,
            "held_created": result.held_created,
            "evolving_tracked": result.evolving_tracked,
            "trust_updates": result.trust_updates,
            "bdg_edges_added": result.bdg_edges_added,
            "duration_seconds": round(result.duration_seconds, 2),
            "errors": result.errors,
        }
    except Exception as e:
        logger.error(f"[CONSOLIDATION] Manual run failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/compaction/history")
async def compaction_history(
    request: Request,
    thread_id: str = Query("default"),
    limit: int = Query(20),
):
    """List recent compaction events."""
    import os
    from personal_agent.db_utils import get_db_connection

    mem_db, _ = _resolve_db_paths(thread_id)
    if not os.path.exists(mem_db):
        return {"events": []}

    try:
        with get_db_connection(mem_db) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT snapshot_id, timestamp, generation,
                       total_beliefs, verbatim_count, summary_count,
                       slot_only_count, dropped_count,
                       token_budget, tokens_used, trigger
                FROM compaction_events
                ORDER BY timestamp DESC
                LIMIT ?
            """, (limit,))
            rows = cursor.fetchall()

        events = []
        for row in rows:
            events.append({
                "snapshot_id": row[0],
                "timestamp": row[1],
                "generation": row[2],
                "total_beliefs": row[3],
                "verbatim_count": row[4],
                "summary_count": row[5],
                "slot_only_count": row[6],
                "dropped_count": row[7],
                "token_budget": row[8],
                "tokens_used": row[9],
                "trigger": row[10],
            })

        return {"events": events}
    except Exception as e:
        return {"events": [], "error": str(e)}
