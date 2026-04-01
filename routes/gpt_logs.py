"""API routes for GPT Log Store — semantic search over ChatGPT export data."""

import logging
import time
from typing import Optional

from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

router = APIRouter()


# ---------------------------------------------------------------------------
# Request / Response models
# ---------------------------------------------------------------------------

class IngestRequest(BaseModel):
    export_dir: str = Field(default="data/chatgpt_export", description="Path to ChatGPT export directory")

class IngestResponse(BaseModel):
    success: bool
    stats: dict

class SearchRequest(BaseModel):
    query: str
    top_k: int = Field(default=20, ge=1, le=100)
    role: Optional[str] = Field(default=None, description="Filter by role: user, assistant, system")
    date_after: Optional[float] = None
    date_before: Optional[float] = None
    model: Optional[str] = None

class MessageResult(BaseModel):
    msg_id: str
    conv_id: str
    conv_title: str
    role: str
    text: str
    timestamp: float
    score: float
    model: str = ""

class SearchResponse(BaseModel):
    results: list[MessageResult]
    query: str
    count: int

class ConversationResponse(BaseModel):
    conv_id: str
    title: str
    model: str
    create_time: float
    update_time: float
    messages: list[dict]

class PromoteRequest(BaseModel):
    msg_id: str
    thread_id: str = Field(default="default")

class PromoteResponse(BaseModel):
    success: bool
    memory_id: Optional[str] = None
    error: Optional[str] = None

class StatsResponse(BaseModel):
    conversations: int
    messages: int
    embedded: int
    index_size: int
    roles: dict


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_store():
    from personal_agent.gpt_log_store import get_gpt_log_store
    return get_gpt_log_store()


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post("/api/gpt-logs/ingest", response_model=IngestResponse)
def ingest_gpt_logs(req: IngestRequest):
    """Ingest ChatGPT export data into the log store."""
    store = _get_store()
    try:
        t0 = time.time()
        stats = store.ingest_export(req.export_dir)
        stats["elapsed_seconds"] = round(time.time() - t0, 1)
        return IngestResponse(success=True, stats=stats)
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.exception("[GPT-LOGS] Ingestion failed")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/api/gpt-logs/search", response_model=SearchResponse)
def search_gpt_logs(req: SearchRequest):
    """Semantic search over GPT logs."""
    store = _get_store()
    results = store.search(
        query=req.query,
        top_k=req.top_k,
        role_filter=req.role,
        date_after=req.date_after,
        date_before=req.date_before,
        model_filter=req.model,
    )
    return SearchResponse(
        results=[MessageResult(
            msg_id=r.msg_id, conv_id=r.conv_id, conv_title=r.conv_title,
            role=r.role, text=r.text, timestamp=r.timestamp,
            score=r.score, model=r.model,
        ) for r in results],
        query=req.query,
        count=len(results),
    )


@router.get("/api/gpt-logs/search")
def search_gpt_logs_get(
    q: str = Query(..., description="Search query"),
    top_k: int = Query(default=20, ge=1, le=100),
    role: Optional[str] = Query(default=None),
):
    """GET-based semantic search (convenience)."""
    store = _get_store()
    results = store.search(query=q, top_k=top_k, role_filter=role)
    return {
        "results": [
            {
                "msg_id": r.msg_id, "conv_id": r.conv_id, "conv_title": r.conv_title,
                "role": r.role, "text": r.text[:500], "timestamp": r.timestamp,
                "score": round(r.score, 4), "model": r.model,
            }
            for r in results
        ],
        "query": q,
        "count": len(results),
    }


@router.get("/api/gpt-logs/conversation/{conv_id}")
def get_conversation(conv_id: str):
    """Get a full conversation with all messages."""
    store = _get_store()
    conv, messages = store.get_conversation(conv_id)
    if conv is None:
        raise HTTPException(status_code=404, detail=f"Conversation {conv_id} not found")
    return ConversationResponse(
        conv_id=conv.conv_id,
        title=conv.title,
        model=conv.model,
        create_time=conv.create_time,
        update_time=conv.update_time,
        messages=[
            {"msg_id": m.msg_id, "role": m.role, "text": m.text, "timestamp": m.timestamp, "model": m.model}
            for m in messages
        ],
    )


@router.get("/api/gpt-logs/context/{msg_id}")
def get_message_context(msg_id: str, window: int = Query(default=3, ge=1, le=20)):
    """Get a message and its surrounding conversation context."""
    store = _get_store()
    messages = store.get_message_context(msg_id, window=window)
    if not messages:
        raise HTTPException(status_code=404, detail=f"Message {msg_id} not found")
    return {
        "messages": [
            {"msg_id": m.msg_id, "role": m.role, "text": m.text, "timestamp": m.timestamp, "model": m.model}
            for m in messages
        ],
        "count": len(messages),
    }


@router.post("/api/gpt-logs/promote", response_model=PromoteResponse)
def promote_to_crt(req: PromoteRequest, request: Request):
    """Promote a GPT log message into a CRT memory."""
    store = _get_store()
    try:
        engine = request.app.state.get_engine(req.thread_id)
        memory_id = store.promote_to_crt(req.msg_id, engine, thread_id=req.thread_id)
        if memory_id:
            return PromoteResponse(success=True, memory_id=memory_id)
        else:
            return PromoteResponse(success=False, error="Message not found")
    except Exception as e:
        logger.exception("[GPT-LOGS] Promotion failed")
        return PromoteResponse(success=False, error=str(e))


@router.get("/api/gpt-logs/stats", response_model=StatsResponse)
def get_stats():
    """Get GPT log store statistics."""
    store = _get_store()
    s = store.stats()
    return StatsResponse(**s)


@router.get("/api/gpt-logs/conversations")
def list_conversations(
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    title: Optional[str] = Query(default=None),
):
    """List conversations, optionally filtered by title."""
    store = _get_store()
    convs = store.list_conversations(limit=limit, offset=offset, search_title=title)
    return {
        "conversations": [
            {"conv_id": c.conv_id, "title": c.title, "model": c.model,
             "create_time": c.create_time, "update_time": c.update_time,
             "message_count": c.message_count}
            for c in convs
        ],
        "count": len(convs),
    }
