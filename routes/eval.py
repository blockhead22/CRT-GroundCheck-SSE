"""Production eval scoring + Capability Lab API endpoints.

Exposes /api/eval/production to score the live system from its
production databases without running new conversations.

Exposes /api/eval/capability-probe, /api/eval/capability-map, etc.
for empirical capability mapping of local models.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException, Query

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/eval", tags=["eval"])

_ROOT = Path(__file__).resolve().parent.parent


def _default_paths():
    return {
        "memory_db": str(_ROOT / "personal_agent" / "crt_memory_shared.db"),
        "agent_runs_db": str(_ROOT / "personal_agent" / "agent_runs.db"),
    }


@router.get("/production")
def eval_production() -> Dict[str, Any]:
    """Score the live production system across 6 dimensions.

    Returns scores for: retrieval, trust_evolution, gate_accuracy,
    drift_health, governance_bridge, agent_performance.

    Each dimension includes a 0-1 score, details dict, and
    recommendations list.
    """
    try:
        from eval.production_scorer import ProductionScorer

        paths = _default_paths()
        scorer = ProductionScorer(
            memory_db_path=paths["memory_db"],
            agent_runs_db_path=paths["agent_runs_db"],
        )
        return scorer.score_all()
    except Exception as e:
        logger.error("[eval] Production scoring failed: %s", e, exc_info=True)
        return {"error": str(e)}


# ---------------------------------------------------------------------------
# Capability Lab endpoints
# ---------------------------------------------------------------------------

@router.post("/capability-probe")
def run_capability_probe(
    model: str = Query("gemma3:latest", description="Ollama model name to probe"),
    categories: Optional[str] = Query(
        None,
        description="Comma-separated category filter (e.g. 'reasoning,code_generation'). Omit to run all.",
    ),
    ollama_url: Optional[str] = Query(None, description="Override Ollama base URL"),
):
    """Run capability probes against a local model and return results."""
    from personal_agent.capability_lab import CapabilityLab

    cat_list = [c.strip() for c in categories.split(",") if c.strip()] if categories else None
    try:
        lab = CapabilityLab()
        results = lab.probe_model(model, ollama_base_url=ollama_url, categories=cat_list)
        return results
    except Exception as exc:
        logger.exception("Capability probe failed")
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/capability-map")
def get_capability_map():
    """Get stored capability summaries for all probed models."""
    from personal_agent.capability_lab import CapabilityLab

    try:
        lab = CapabilityLab()
        return lab.get_all_summaries()
    except Exception as exc:
        logger.exception("Failed to load capability map")
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/capability-map/{model_name}")
def get_model_capability(model_name: str):
    """Get capability summary for a specific model."""
    from personal_agent.capability_lab import CapabilityLab

    try:
        lab = CapabilityLab()
        summary = lab.get_model_summary(model_name)
        if not summary["categories"]:
            raise HTTPException(status_code=404, detail=f"No probe data for model '{model_name}'")
        return summary
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Failed to load model capability")
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/probe-history")
def get_probe_history(
    model: Optional[str] = Query(None),
    category: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=500),
):
    """Get raw probe history for analysis."""
    from personal_agent.capability_lab import CapabilityLab

    try:
        lab = CapabilityLab()
        return {"probes": lab.get_probe_history(model_name=model, category=category, limit=limit)}
    except Exception as exc:
        logger.exception("Failed to load probe history")
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/should-escalate")
def should_escalate(
    model: str = Query(..., description="Model name"),
    category: str = Query(..., description="Category to check"),
    threshold: float = Query(0.5, ge=0.0, le=1.0),
):
    """Check whether a model should escalate for a given category."""
    from personal_agent.capability_lab import CapabilityLab

    try:
        lab = CapabilityLab()
        result = lab.should_escalate(model, category, threshold)
        return {
            "model": model,
            "category": category,
            "threshold": threshold,
            "should_escalate": result,
            "note": "null means no probe data -- run a probe first" if result is None else None,
        }
    except Exception as exc:
        logger.exception("Escalation check failed")
        raise HTTPException(status_code=500, detail=str(exc))
