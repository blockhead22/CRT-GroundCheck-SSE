"""
Intent Router API endpoints — debugging, prototype management, stats.

Sprint 7: Provides observability into the hybrid intent classification system.
"""

import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/intents", tags=["intents"])


def _get_router():
    """Get the SemanticIntentRouter singleton (lazy-loaded via task_agent)."""
    from personal_agent.task_agent import _get_semantic_router
    router = _get_semantic_router()
    if router is None:
        raise HTTPException(status_code=503, detail="Semantic intent router not available (model not loaded)")
    return router


# ---------------------------------------------------------------------------
# GET /api/intents/prototypes — list all intent prototypes
# ---------------------------------------------------------------------------

@router.get("/prototypes")
def get_prototypes():
    """Returns all intent prototypes with phrase counts."""
    sr = _get_router()
    return sr.get_prototypes()


# ---------------------------------------------------------------------------
# POST /api/intents/prototypes/{intent_type} — add a prototype phrase
# ---------------------------------------------------------------------------

class AddPhraseRequest(BaseModel):
    phrase: str


@router.post("/prototypes/{intent_type}")
def add_prototype(intent_type: str, body: AddPhraseRequest):
    """Add a new prototype phrase for an intent type."""
    sr = _get_router()
    if not body.phrase.strip():
        raise HTTPException(status_code=400, detail="Phrase cannot be empty")
    ok = sr.add_prototype(intent_type, body.phrase.strip())
    if not ok:
        raise HTTPException(status_code=404, detail=f"Unknown intent type: {intent_type}")
    return {"status": "added", "intent_type": intent_type, "phrase": body.phrase.strip()}


# ---------------------------------------------------------------------------
# DELETE /api/intents/prototypes/{intent_type}/{phrase_index} — remove phrase
# ---------------------------------------------------------------------------

@router.delete("/prototypes/{intent_type}/{phrase_index}")
def remove_prototype(intent_type: str, phrase_index: int):
    """Remove a prototype phrase by index (only custom prototypes can be removed)."""
    sr = _get_router()
    ok = sr.remove_prototype(intent_type, phrase_index)
    if not ok:
        raise HTTPException(status_code=404, detail="Phrase not found or is a base prototype (cannot remove)")
    return {"status": "removed", "intent_type": intent_type, "phrase_index": phrase_index}


# ---------------------------------------------------------------------------
# GET /api/intents/classify — debug endpoint: classify a message
# ---------------------------------------------------------------------------

@router.get("/classify")
def classify_message(message: str = Query(..., min_length=1)):
    """
    Debug endpoint: classify a message and return all scores.
    Useful for testing the intent router without sending a real chat message.
    """
    sr = _get_router()
    scores = sr.classify(message)
    multi = sr.detect_multi_intent(scores)
    ambiguity = sr.handle_ambiguity(scores, message)

    # Also run regex for comparison
    from personal_agent.task_agent import _classify_intent_regex
    regex_result = _classify_intent_regex(message)

    return {
        "message": message,
        "embedding_scores": [
            {"intent_type": s.intent_type, "confidence": round(s.confidence, 4)}
            for s in scores[:10]
        ],
        "multi_intent": [
            {"intent_type": m.intent_type, "confidence": round(m.confidence, 4)}
            for m in multi
        ],
        "ambiguity_action": ambiguity.get("action"),
        "regex_result": {
            "intent_type": regex_result.intent_type,
            "confidence": regex_result.confidence,
            "route": regex_result.route,
        },
    }


# ---------------------------------------------------------------------------
# GET /api/intents/corrections — list recent corrections
# ---------------------------------------------------------------------------

@router.get("/corrections")
def get_corrections(limit: int = Query(50, ge=1, le=500)):
    """List recent intent corrections with before/after."""
    sr = _get_router()
    corrections = sr.load_recent_corrections(limit)
    return {"corrections": corrections, "count": len(corrections)}


# ---------------------------------------------------------------------------
# GET /api/intents/stats — classification stats
# ---------------------------------------------------------------------------

@router.get("/stats")
def get_stats():
    """Classification stats: total prototypes, corrections, etc."""
    sr = _get_router()
    return sr.get_stats()
