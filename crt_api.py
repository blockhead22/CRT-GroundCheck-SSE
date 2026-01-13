from __future__ import annotations

import os
import re
import sqlite3
import time
from pathlib import Path
from typing import Any, Dict, Optional

from fastapi import FastAPI
from fastapi import Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from personal_agent.crt_rag import CRTEnhancedRAG
from personal_agent.fact_slots import extract_fact_slots


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


class DocListItem(BaseModel):
    id: str
    title: str
    kind: str


class DocGetResponse(BaseModel):
    id: str
    title: str
    kind: str
    markdown: str


class DashboardOverviewResponse(BaseModel):
    thread_id: str
    session_id: Optional[str] = None
    memories_total: int
    open_contradictions: int
    belief_ratio: float
    speech_ratio: float
    belief_count: int
    speech_count: int


class MemoryListItem(BaseModel):
    memory_id: str
    text: str
    timestamp: float
    confidence: float
    trust: float
    source: str
    sse_mode: str
    thread_id: Optional[str] = None


class ContradictionListItem(BaseModel):
    ledger_id: str
    timestamp: float
    status: str
    contradiction_type: str
    drift_mean: float
    confidence_delta: float
    summary: Optional[str] = None
    query: Optional[str] = None
    old_memory_id: str
    new_memory_id: str


class ResolveContradictionRequest(BaseModel):
    thread_id: str = Field(default="default")
    ledger_id: str
    method: str = Field(description="resolution method (e.g., accept_both, user_clarified, reflection_merge)")
    new_status: str = Field(default="resolved")
    merged_memory_id: Optional[str] = None


class ProfileResponse(BaseModel):
    thread_id: str
    name: Optional[str] = None
    slots: Dict[str, str] = Field(default_factory=dict)


class ThreadExportResponse(BaseModel):
    thread_id: str
    generated_at: float
    memories: list[MemoryListItem]
    contradictions: list[ContradictionListItem]
    memories_total: int
    contradictions_total: int


class ThreadResetRequest(BaseModel):
    thread_id: str = Field(default="default")
    target: str = Field(default="all", description="memory | ledger | all")


class ThreadResetResponse(BaseModel):
    thread_id: str
    target: str
    deleted: Dict[str, bool] = Field(default_factory=dict)
    ok: bool = True


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

    root = Path(__file__).resolve().parent
    docs_dir = root / "docs"
    doc_map: Dict[str, Dict[str, Any]] = {
        # Mirrors the Streamlit dashboard docs tabs.
        "architecture": {"title": "CRT System Architecture", "kind": "docs", "path": docs_dir / "CRT_SYSTEM_ARCHITECTURE.md"},
        "faq": {"title": "CRT FAQ", "kind": "docs", "path": docs_dir / "CRT_FAQ.md"},
        "functional_spec": {"title": "CRT Functional Spec", "kind": "docs", "path": docs_dir / "CRT_FUNCTIONAL_SPEC.md"},
        # Convenience reference docs (same list as Streamlit dashboard).
        "how_it_works": {"title": "How It Works", "kind": "reference", "path": root / "HOW_IT_WORKS.md"},
        "project_summary": {"title": "Project Summary", "kind": "reference", "path": root / "PROJECT_SUMMARY.md"},
        "crt_quick_reference": {"title": "CRT Quick Reference", "kind": "reference", "path": root / "CRT_QUICK_REFERENCE.md"},
        "crt_whitepaper": {"title": "CRT Whitepaper", "kind": "reference", "path": root / "CRT_WHITEPAPER.md"},
        "crt_chat_gui_setup": {"title": "CRT Chat GUI Setup", "kind": "reference", "path": root / "CRT_CHAT_GUI_SETUP.md"},
        "crt_dashboard_guide": {"title": "CRT Dashboard Guide", "kind": "reference", "path": root / "CRT_DASHBOARD_GUIDE.md"},
        "multi_agent_user_guide": {"title": "Multi-Agent User Guide", "kind": "reference", "path": root / "MULTI_AGENT_USER_GUIDE.md"},
        "rag_start_here": {"title": "RAG Start Here", "kind": "reference", "path": root / "RAG_START_HERE.md"},
    }

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

    def _memory_item_to_dict(mem) -> Dict[str, Any]:
        return {
            "memory_id": getattr(mem, "memory_id", ""),
            "text": getattr(mem, "text", ""),
            "timestamp": float(getattr(mem, "timestamp", 0.0) or 0.0),
            "confidence": float(getattr(mem, "confidence", 0.0) or 0.0),
            "trust": float(getattr(mem, "trust", 0.0) or 0.0),
            "source": getattr(getattr(mem, "source", None), "value", None) or str(getattr(mem, "source", "")),
            "sse_mode": getattr(getattr(mem, "sse_mode", None), "value", None) or str(getattr(mem, "sse_mode", "")),
            "thread_id": getattr(mem, "thread_id", None),
        }

    def _extract_latest_profile_slots(engine: CRTEnhancedRAG) -> Dict[str, str]:
        """Best-effort extraction of latest fact slots from user memories.

        We treat structured facts like "FACT: name = Nick" as authoritative signals.
        """
        try:
            items = engine.memory._load_all_memories()
        except Exception:
            items = []

        best_by_slot: Dict[str, Dict[str, Any]] = {}
        for mem in items:
            src = getattr(getattr(mem, "source", None), "value", None) or str(getattr(mem, "source", ""))
            if str(src).lower() != "user":
                continue
            text = str(getattr(mem, "text", "") or "")
            facts = extract_fact_slots(text)
            if not facts:
                continue
            ts = float(getattr(mem, "timestamp", 0.0) or 0.0)
            for slot, extracted in facts.items():
                prev = best_by_slot.get(slot)
                if prev is None or ts >= float(prev.get("timestamp") or 0.0):
                    best_by_slot[slot] = {"value": str(extracted.value), "timestamp": ts}

        out: Dict[str, str] = {}
        for slot, d in best_by_slot.items():
            v = str(d.get("value") or "").strip()
            if v:
                out[str(slot)] = v
        return out

    def _list_contradictions(
        engine: CRTEnhancedRAG,
        *,
        include_resolved: bool,
        limit: int,
    ) -> list[ContradictionListItem]:
        if not include_resolved:
            try:
                entries = engine.ledger.get_open_contradictions(limit=limit)
            except Exception:
                entries = []
            return [ContradictionListItem(**e.to_dict()) for e in entries]

        # Best-effort: read the ledger DB directly to include resolved/accepted.
        db_path = getattr(engine.ledger, "db_path", None)
        if not db_path:
            return []

        try:
            conn = sqlite3.connect(str(db_path))
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT ledger_id, timestamp, status, contradiction_type, drift_mean, confidence_delta,
                       summary, query, old_memory_id, new_memory_id
                FROM contradictions
                ORDER BY timestamp DESC
                LIMIT ?
                """,
                (int(limit),),
            )
            rows = cursor.fetchall()
            conn.close()
        except Exception:
            return []

        out: list[ContradictionListItem] = []
        for r in rows:
            out.append(
                ContradictionListItem(
                    ledger_id=str(r[0]),
                    timestamp=float(r[1] or 0.0),
                    status=str(r[2] or ""),
                    contradiction_type=str(r[3] or ""),
                    drift_mean=float(r[4] or 0.0),
                    confidence_delta=float(r[5] or 0.0),
                    summary=(str(r[6]) if r[6] is not None else None),
                    query=(str(r[7]) if r[7] is not None else None),
                    old_memory_id=str(r[8] or ""),
                    new_memory_id=str(r[9] or ""),
                )
            )
        return out

    def _thread_db_paths(tid: str) -> Dict[str, Path]:
        return {
            "memory": (root / f"personal_agent/crt_memory_{tid}.db"),
            "ledger": (root / f"personal_agent/crt_ledger_{tid}.db"),
        }

    @app.get("/health")
    def health() -> Dict[str, str]:
        return {"status": "ok"}

    @app.get("/api/docs", response_model=list[DocListItem])
    def list_docs() -> list[DocListItem]:
        items: list[DocListItem] = []
        for doc_id, meta in doc_map.items():
            path: Path = meta["path"]
            if not path.exists() or not path.is_file():
                continue
            items.append(DocListItem(id=doc_id, title=str(meta.get("title") or doc_id), kind=str(meta.get("kind") or "docs")))
        # Stable ordering: docs first, then reference
        items.sort(key=lambda x: (0 if x.kind == "docs" else 1, x.title.lower()))
        return items

    @app.get("/api/docs/{doc_id}", response_model=DocGetResponse)
    def get_doc(doc_id: str) -> DocGetResponse:
        meta = doc_map.get(doc_id)
        if not meta:
            return DocGetResponse(id=doc_id, title="Not found", kind="error", markdown=f"# Not found\n\nUnknown doc id: `{doc_id}`")

        path: Path = meta["path"]
        try:
            markdown = path.read_text(encoding="utf-8")
        except Exception as e:
            markdown = f"# Missing document\n\nCould not read: `{path}`\n\nError: {e}"

        return DocGetResponse(
            id=doc_id,
            title=str(meta.get("title") or doc_id),
            kind=str(meta.get("kind") or "docs"),
            markdown=markdown,
        )

    @app.get("/api/profile", response_model=ProfileResponse)
    def get_profile(thread_id: str = Query(default="default")) -> ProfileResponse:
        engine = get_engine(thread_id)
        tid = _sanitize_thread_id(thread_id)
        slots = _extract_latest_profile_slots(engine)
        name = slots.get("name")
        return ProfileResponse(thread_id=tid, name=name, slots=slots)

    @app.get("/api/dashboard/overview", response_model=DashboardOverviewResponse)
    def dashboard_overview(thread_id: str = Query(default="default")) -> DashboardOverviewResponse:
        engine = get_engine(thread_id)
        tid = _sanitize_thread_id(thread_id)

        try:
            memories_total = len(engine.memory._load_all_memories())
        except Exception:
            memories_total = 0

        try:
            open_contradictions = len(engine.ledger.get_open_contradictions(limit=10_000))
        except Exception:
            open_contradictions = 0

        try:
            ratio = engine.memory.get_belief_speech_ratio(limit=100)
        except Exception:
            ratio = {"belief_ratio": 0.0, "speech_ratio": 0.0, "belief_count": 0, "speech_count": 0}

        return DashboardOverviewResponse(
            thread_id=tid,
            session_id=getattr(engine, "session_id", None),
            memories_total=memories_total,
            open_contradictions=open_contradictions,
            belief_ratio=float(ratio.get("belief_ratio") or 0.0),
            speech_ratio=float(ratio.get("speech_ratio") or 0.0),
            belief_count=int(ratio.get("belief_count") or 0),
            speech_count=int(ratio.get("speech_count") or 0),
        )

    @app.get("/api/memory/recent", response_model=list[MemoryListItem])
    def memory_recent(thread_id: str = Query(default="default"), limit: int = Query(default=30, ge=1, le=200)) -> list[MemoryListItem]:
        engine = get_engine(thread_id)
        try:
            items = engine.memory._load_all_memories()
        except Exception:
            items = []

        items.sort(key=lambda m: float(getattr(m, "timestamp", 0.0) or 0.0), reverse=True)
        out = []
        for mem in items[:limit]:
            out.append(MemoryListItem(**_memory_item_to_dict(mem)))
        return out

    @app.get("/api/memory/search", response_model=list[MemoryListItem])
    def memory_search(
        thread_id: str = Query(default="default"),
        q: str = Query(min_length=1),
        k: int = Query(default=10, ge=1, le=50),
        min_trust: float = Query(default=0.0, ge=0.0, le=1.0),
    ) -> list[MemoryListItem]:
        engine = get_engine(thread_id)
        try:
            retrieved = engine.retrieve(q, k=k, min_trust=min_trust)
        except Exception:
            retrieved = []
        out = []
        for mem, _score in retrieved:
            out.append(MemoryListItem(**_memory_item_to_dict(mem)))
        return out

    @app.get("/api/memory/{memory_id}", response_model=MemoryListItem)
    def memory_get(memory_id: str, thread_id: str = Query(default="default")) -> MemoryListItem:
        engine = get_engine(thread_id)
        mem = engine.memory.get_memory_by_id(memory_id)
        if mem is None:
            return MemoryListItem(
                memory_id=memory_id,
                text="",
                timestamp=0.0,
                confidence=0.0,
                trust=0.0,
                source="",
                sse_mode="",
                thread_id=None,
            )
        return MemoryListItem(**_memory_item_to_dict(mem))

    @app.get("/api/memory/{memory_id}/trust", response_model=list[dict])
    def memory_trust_history(memory_id: str, thread_id: str = Query(default="default")) -> list[dict]:
        engine = get_engine(thread_id)
        try:
            return engine.memory.get_trust_history(memory_id)
        except Exception:
            return []

    @app.get("/api/ledger/open", response_model=list[ContradictionListItem])
    def ledger_open(thread_id: str = Query(default="default"), limit: int = Query(default=50, ge=1, le=500)) -> list[ContradictionListItem]:
        engine = get_engine(thread_id)
        try:
            entries = engine.ledger.get_open_contradictions(limit=limit)
        except Exception:
            entries = []
        return [ContradictionListItem(**e.to_dict()) for e in entries]

    @app.post("/api/ledger/resolve")
    def ledger_resolve(req: ResolveContradictionRequest) -> Dict[str, Any]:
        engine = get_engine(req.thread_id)
        engine.ledger.resolve_contradiction(
            ledger_id=req.ledger_id,
            method=req.method,
            merged_memory_id=req.merged_memory_id,
            new_status=req.new_status,
        )
        return {"ok": True}

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
                    "memory_id": (m.get("memory_id") if isinstance(m, dict) else None),
                    "text": (m.get("text") if isinstance(m, dict) else None),
                    "source": (m.get("source") if isinstance(m, dict) else None),
                    "trust": (m.get("trust") if isinstance(m, dict) else None),
                    "confidence": (m.get("confidence") if isinstance(m, dict) else None),
                    "timestamp": (m.get("timestamp") if isinstance(m, dict) else None),
                    "sse_mode": (m.get("sse_mode") if isinstance(m, dict) else None),
                    "score": (m.get("score") if isinstance(m, dict) else None),
                }
                for m in (result.get("retrieved_memories") or [])
                if isinstance(m, dict)
            ],
            "prompt_memories": [
                {
                    "memory_id": (m.get("memory_id") if isinstance(m, dict) else None),
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

    @app.get("/api/thread/export", response_model=ThreadExportResponse)
    def thread_export(
        thread_id: str = Query(default="default"),
        include_resolved: bool = Query(default=True),
        memories_limit: int = Query(default=2000, ge=1, le=20000),
        contradictions_limit: int = Query(default=2000, ge=1, le=20000),
    ) -> ThreadExportResponse:
        tid = _sanitize_thread_id(thread_id)
        engine = get_engine(tid)

        try:
            mems = engine.memory._load_all_memories()
        except Exception:
            mems = []
        mems.sort(key=lambda m: float(getattr(m, "timestamp", 0.0) or 0.0), reverse=True)
        memories = [MemoryListItem(**_memory_item_to_dict(m)) for m in mems[: int(memories_limit)]]

        contradictions = _list_contradictions(engine, include_resolved=bool(include_resolved), limit=int(contradictions_limit))

        return ThreadExportResponse(
            thread_id=tid,
            generated_at=time.time(),
            memories=memories,
            contradictions=contradictions,
            memories_total=len(mems),
            contradictions_total=len(contradictions),
        )

    @app.post("/api/thread/reset", response_model=ThreadResetResponse)
    def thread_reset(req: ThreadResetRequest) -> ThreadResetResponse:
        tid = _sanitize_thread_id(req.thread_id)

        # Drop cached engine first to avoid holding references.
        engines.pop(tid, None)

        target = (req.target or "all").strip().lower()
        if target not in {"memory", "ledger", "all"}:
            target = "all"

        paths = _thread_db_paths(tid)
        deleted: Dict[str, bool] = {}

        def _delete_path(name: str) -> None:
            p = paths[name]
            try:
                if p.exists() and p.is_file():
                    p.unlink()
                    deleted[name] = True
                else:
                    deleted[name] = False
            except Exception:
                deleted[name] = False

        if target in {"memory", "all"}:
            _delete_path("memory")
        if target in {"ledger", "all"}:
            _delete_path("ledger")

        return ThreadResetResponse(thread_id=tid, target=target, deleted=deleted, ok=True)

    return app


app = create_app()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=int(os.getenv("PORT", "8000")))
