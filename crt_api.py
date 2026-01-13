from __future__ import annotations

import os
import re
from typing import Any, Dict, Optional

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from personal_agent.crt_rag import CRTEnhancedRAG


def _sanitize_thread_id(value: str) -> str:
    value = (value or "").strip()
    if not value:
        return "default"
    value = re.sub(r"[^a-zA-Z0-9_-]+", "_", value)
    return value[:64] or "default"


class ChatSendRequest(BaseModel):
    thread_id: str = Field(default="default", description="Client thread identifier")
    message: str = Field(min_length=1, description="User message")
    user_marked_important: bool = Field(default=False)
    mode: Optional[str] = Field(default=None, description="Optional reasoning mode")


class ChatSendResponse(BaseModel):
    answer: str
    response_type: str
    gates_passed: bool
    gate_reason: Optional[str] = None
    session_id: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


def create_app() -> FastAPI:
    app = FastAPI(title="CRT API", version="0.1.0")

    # CORS (dev-friendly). Configure via CRT_CORS_ORIGINS as comma-separated list.
    cors_env = os.getenv("CRT_CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173")
    origins = [o.strip() for o in cors_env.split(",") if o.strip()]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins if origins else ["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Cache one CRT engine per thread (isolated DBs per thread).
    engines: Dict[str, CRTEnhancedRAG] = {}

    def get_engine(thread_id: str) -> CRTEnhancedRAG:
        tid = _sanitize_thread_id(thread_id)
        engine = engines.get(tid)
        if engine is not None:
            return engine

        memory_db = f"personal_agent/crt_memory_{tid}.db"
        ledger_db = f"personal_agent/crt_ledger_{tid}.db"
        engine = CRTEnhancedRAG(memory_db=memory_db, ledger_db=ledger_db)
        engines[tid] = engine
        return engine

    @app.get("/health")
    def health() -> Dict[str, str]:
        return {"status": "ok"}

    @app.post("/api/chat/send", response_model=ChatSendResponse)
    def chat_send(req: ChatSendRequest) -> ChatSendResponse:
        engine = get_engine(req.thread_id)

        mode_arg = None
        if req.mode:
            # Accept string modes, but keep this permissive: unknown values fall back to None.
            try:
                from personal_agent.reasoning import ReasoningMode

                mode_arg = ReasoningMode(req.mode)  # type: ignore[arg-type]
            except Exception:
                mode_arg = None

        result = engine.query(
            user_query=req.message,
            user_marked_important=req.user_marked_important,
            mode=mode_arg,
        )

        # Keep the payload compact and UI-friendly.
        metadata: Dict[str, Any] = {
            "confidence": result.get("confidence"),
            "intent_alignment": result.get("intent_alignment"),
            "memory_alignment": result.get("memory_alignment"),
            "contradiction_detected": result.get("contradiction_detected"),
            "unresolved_contradictions_total": result.get("unresolved_contradictions_total"),
            "unresolved_hard_conflicts": result.get("unresolved_hard_conflicts"),
            "learned_suggestions": result.get("learned_suggestions") or [],
            "heuristic_suggestions": result.get("heuristic_suggestions") or [],
            "retrieved_memories": [
                {
                    "text": (m.get("text") if isinstance(m, dict) else None),
                    "source": (m.get("source") if isinstance(m, dict) else None),
                    "trust": (m.get("trust") if isinstance(m, dict) else None),
                    "confidence": (m.get("confidence") if isinstance(m, dict) else None),
                }
                for m in (result.get("retrieved_memories") or [])
                if isinstance(m, dict)
            ],
            "prompt_memories": [
                {
                    "text": (m.get("text") if isinstance(m, dict) else None),
                    "source": (m.get("source") if isinstance(m, dict) else None),
                    "trust": (m.get("trust") if isinstance(m, dict) else None),
                    "confidence": (m.get("confidence") if isinstance(m, dict) else None),
                }
                for m in (result.get("prompt_memories") or [])
                if isinstance(m, dict)
            ],
        }

        return ChatSendResponse(
            answer=str(result.get("answer") or ""),
            response_type=str(result.get("response_type") or "speech"),
            gates_passed=bool(result.get("gates_passed")),
            gate_reason=(result.get("gate_reason") if isinstance(result.get("gate_reason"), str) else None),
            session_id=(result.get("session_id") if isinstance(result.get("session_id"), str) else None),
            metadata=metadata,
        )

    return app


app = create_app()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=int(os.getenv("PORT", "8000")))
