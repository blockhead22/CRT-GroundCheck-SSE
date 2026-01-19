import os
import re
import sqlite3
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, HTTPException
from fastapi import Query
from fastapi import BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from personal_agent.crt_rag import CRTEnhancedRAG
from personal_agent.fact_slots import extract_fact_slots
from personal_agent.artifact_store import now_iso_utc
from personal_agent.idle_scheduler import CRTIdleScheduler
from personal_agent.evidence_packet import Citation, EvidencePacket
from personal_agent.research_engine import ResearchEngine
from personal_agent.jobs_db import (
    enqueue_job,
    get_job,
    init_jobs_db,
    list_job_artifacts,
    list_job_events,
    list_jobs,
)
from personal_agent.jobs_worker import CRTJobsWorker
from personal_agent.runtime_config import get_runtime_config
from personal_agent.training_loop import CRTTrainingLoop
from personal_agent.active_learning import get_active_learning_coordinator, LearningStats


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


class ContradictionWorkItem(BaseModel):
    thread_id: str
    ledger_id: str
    status: str
    contradiction_type: str
    drift_mean: float
    summary: Optional[str] = None
    ask_count: int = 0
    last_asked_at: Optional[float] = None
    next_action: str
    suggested_question: str
    semantic_anchor: Optional[Dict[str, Any]] = None  # Carries contradiction context


class ContradictionNextResponse(BaseModel):
    thread_id: str
    has_item: bool
    item: Optional[ContradictionWorkItem] = None


class ContradictionAskedRequest(BaseModel):
    thread_id: str = Field(default="default")
    ledger_id: str


class ContradictionRespondRequest(BaseModel):
    thread_id: str = Field(default="default")
    ledger_id: str
    answer: str = Field(default="", description="User clarification/answer")
    resolve: bool = Field(default=True, description="If true, mark the contradiction resolved")
    resolution_method: str = Field(default="user_clarified")
    new_status: str = Field(default="resolved")
    merged_memory_id: Optional[str] = None


class ContradictionRespondResponse(BaseModel):
    ok: bool = True
    thread_id: str
    ledger_id: str
    recorded: bool = True
    resolved: bool = False
    next: ContradictionNextResponse


class ThreadListItem(BaseModel):
    id: str
    title: str
    updated_at: float
    message_count: int


class ThreadCreateRequest(BaseModel):
    title: str = Field(default="New chat", max_length=200)


class ThreadUpdateRequest(BaseModel):
    title: str = Field(max_length=200)


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


class ThreadPurgeMemoriesRequest(BaseModel):
    thread_id: str = Field(default="default")
    sources: list[str] = Field(default_factory=lambda: ["system", "fallback"], description="memory sources to delete")
    confirm: bool = Field(default=False, description="must be true to execute")


class ThreadPurgeMemoriesResponse(BaseModel):
    thread_id: str
    sources: list[str]
    confirm: bool
    deleted_memories: int = 0
    deleted_trust_log: int = 0
    ok: bool = True


# M3: Research API Models
class CitationModel(BaseModel):
    quote_text: str
    source_url: str
    char_offset: list[int]  # [start, end]
    fetched_at: str  # ISO timestamp
    confidence: float = 0.8


# Agent API Models
class AgentStepModel(BaseModel):
    step_num: int
    thought: str
    action: Optional[Dict[str, Any]] = None
    observation: Optional[Dict[str, Any]] = None
    timestamp: str


class AgentTraceModel(BaseModel):
    query: str
    steps: list[AgentStepModel]
    final_answer: Optional[str] = None
    success: bool
    error: Optional[str] = None
    started_at: str
    completed_at: Optional[str] = None


class AgentRunRequest(BaseModel):
    thread_id: str = Field(default="default")
    query: str = Field(min_length=1, description="Task for agent")
    max_steps: int = Field(default=10, ge=1, le=50)
    auto_mode: bool = Field(default=True, description="Enable autonomous execution")


class AgentRunResponse(BaseModel):
    trace: AgentTraceModel
    triggered_by: Optional[str] = None


class AgentTriggersResponse(BaseModel):
    thread_id: str
    triggers: list[Dict[str, Any]]
    should_activate: bool
    suggested_task: Optional[str] = None


class AgentStatusResponse(BaseModel):
    available: bool
    llm_available: bool
    reasoning_available: bool
    tools_count: int


class ResearchSearchRequest(BaseModel):
    thread_id: str = Field(default="default")
    query: str = Field(min_length=1, description="Research query")
    max_sources: int = Field(default=3, ge=1, le=10)


class ResearchSearchResponse(BaseModel):
    packet_id: str
    query: str
    summary: str
    citations: list[CitationModel]
    memory_id: str
    citation_count: int


class ResearchCitationsResponse(BaseModel):
    memory_id: str
    citations: list[CitationModel]


class ResearchPromoteRequest(BaseModel):
    thread_id: str = Field(default="default")
    memory_id: str
    user_confirmed: bool = Field(default=False)


class ResearchPromoteResponse(BaseModel):
    ok: bool
    memory_id: str
    promoted: bool


def create_app() -> FastAPI:
    app = FastAPI(title="CRT API", version="0.1.0")

    runtime_cfg = get_runtime_config()
    reflection_cfg = (runtime_cfg.get("reflection") or {}) if isinstance(runtime_cfg, dict) else {}
    learned_cfg = (runtime_cfg.get("learned_suggestions") or {}) if isinstance(runtime_cfg, dict) else {}
    loop_cfg = (runtime_cfg.get("training_loop") or {}) if isinstance(runtime_cfg, dict) else {}
    jobs_cfg = (runtime_cfg.get("background_jobs") or {}) if isinstance(runtime_cfg, dict) else {}

    # Shared training loop (suggestion-only model). Stored in app.state for endpoints.
    training_loop = CRTTrainingLoop(
        repo_root=Path(__file__).resolve().parent,
        reflection_cfg=reflection_cfg,
        learned_cfg=learned_cfg,
        loop_cfg=loop_cfg,
    )
    app.state.training_loop = training_loop

    # Optional: background jobs worker + idle scheduler.
    # Stored on app.state so endpoints can report status.
    root = Path(__file__).resolve().parent
    jobs_enabled = bool(jobs_cfg.get("enabled", False))
    jobs_db_path = str(jobs_cfg.get("jobs_db_path") or "artifacts/crt_jobs.db")
    jobs_artifacts_dir = str(jobs_cfg.get("artifacts_dir") or "artifacts")
    worker_interval = float(jobs_cfg.get("worker_interval_seconds") or 2)

    init_jobs_db(jobs_db_path)
    app.state.jobs_db_path = jobs_db_path

    jobs_worker = CRTJobsWorker(
        repo_root=root,
        jobs_db_path=jobs_db_path,
        artifacts_dir=jobs_artifacts_dir,
        enabled=jobs_enabled,
        interval_seconds=worker_interval,
    )
    app.state.jobs_worker = jobs_worker

    idle_enabled = bool(jobs_cfg.get("idle_scheduler_enabled", False)) and jobs_enabled
    idle_seconds = int(jobs_cfg.get("idle_seconds") or 120)
    idle_scheduler = CRTIdleScheduler(
        repo_root=root,
        jobs_db_path=jobs_db_path,
        enabled=idle_enabled,
        idle_seconds=idle_seconds,
        interval_seconds=10,
        auto_resolve_contradictions_enabled=bool(jobs_cfg.get("auto_resolve_contradictions_enabled", False)),
        auto_web_research_enabled=bool(jobs_cfg.get("auto_web_research_enabled", False)),
        auto_learning_enabled=bool(jobs_cfg.get("auto_learning_enabled", True)),
    )
    app.state.idle_scheduler = idle_scheduler

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
    turn_counters: Dict[str, int] = {}  # Track turn numbers per thread

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
        turn_counters[tid] = 0  # Initialize turn counter
        return engine
    
    def get_turn_number(thread_id: str) -> int:
        """Get current turn number for thread."""
        tid = _sanitize_thread_id(thread_id)
        return turn_counters.get(tid, 0)
    
    def increment_turn(thread_id: str) -> int:
        """Increment and return new turn number."""
        tid = _sanitize_thread_id(thread_id)
        turn_counters[tid] = turn_counters.get(tid, 0) + 1
        return turn_counters[tid]

    def _thread_db_paths(thread_id: str) -> tuple[str, str]:
        tid = _sanitize_thread_id(thread_id)
        memory_db = f"personal_agent/crt_memory_{tid}.db"
        ledger_db = f"personal_agent/crt_ledger_{tid}.db"
        return memory_db, ledger_db

    @app.on_event("startup")
    def _startup() -> None:
        # Start the (optional) training loop.
        try:
            training_loop.start()
        except Exception:
            pass

        try:
            jobs_worker.start()
        except Exception:
            pass

        try:
            idle_scheduler.start()
        except Exception:
            pass

    @app.on_event("shutdown")
    def _shutdown() -> None:
        try:
            training_loop.stop()
        except Exception:
            pass

        try:
            idle_scheduler.stop()
        except Exception:
            pass

        try:
            jobs_worker.stop()
        except Exception:
            pass

    class JobListItem(BaseModel):
        id: str
        type: str
        status: str
        priority: int
        created_at: str
        started_at: Optional[str] = None
        finished_at: Optional[str] = None
        payload: Dict[str, Any] = Field(default_factory=dict)
        error: Optional[str] = None

    class JobsListResponse(BaseModel):
        jobs: list[JobListItem]

    class JobDetailResponse(BaseModel):
        job: JobListItem
        events: list[Dict[str, Any]]
        artifacts: list[Dict[str, Any]]

    class JobsStatusResponse(BaseModel):
        enabled: bool
        worker: Dict[str, Any]
        idle_scheduler_enabled: bool
        jobs_db_path: str

    class EnqueueJobRequest(BaseModel):
        type: str = Field(description="job type")
        payload: Dict[str, Any] = Field(default_factory=dict)
        priority: int = Field(default=0)
        job_id: Optional[str] = Field(default=None, description="optional custom job id")

    class EnqueueJobResponse(BaseModel):
        ok: bool = True
        job_id: str

    @app.get("/api/jobs/status", response_model=JobsStatusResponse)
    def jobs_status() -> JobsStatusResponse:
        st = app.state.jobs_worker.status().to_dict() if getattr(app.state, "jobs_worker", None) else {}
        return JobsStatusResponse(
            enabled=bool(getattr(app.state.jobs_worker, "enabled", False)),
            worker=st,
            idle_scheduler_enabled=bool(getattr(app.state.idle_scheduler, "enabled", False)),
            jobs_db_path=str(getattr(app.state, "jobs_db_path", "")),
        )

    @app.get("/api/jobs", response_model=JobsListResponse)
    def jobs_list(
        status: Optional[str] = Query(default=None),
        limit: int = Query(default=50, ge=1, le=200),
        offset: int = Query(default=0, ge=0),
    ) -> JobsListResponse:
        rows = list_jobs(app.state.jobs_db_path, status=status, limit=limit, offset=offset)
        return JobsListResponse(
            jobs=[
                JobListItem(
                    id=r.id,
                    type=r.type,
                    status=r.status,
                    priority=r.priority,
                    created_at=r.created_at,
                    started_at=r.started_at,
                    finished_at=r.finished_at,
                    payload=r.payload,
                    error=r.error,
                )
                for r in rows
            ]
        )

    @app.get("/api/jobs/{job_id}", response_model=JobDetailResponse)
    def job_get(job_id: str) -> JobDetailResponse:
        row = get_job(app.state.jobs_db_path, job_id)
        if row is None:
            raise HTTPException(status_code=404, detail=f"Job not found: {job_id}")

        return JobDetailResponse(
            job=JobListItem(
                id=row.id,
                type=row.type,
                status=row.status,
                priority=row.priority,
                created_at=row.created_at,
                started_at=row.started_at,
                finished_at=row.finished_at,
                payload=row.payload,
                error=row.error,
            ),
            events=list_job_events(app.state.jobs_db_path, job_id),
            artifacts=list_job_artifacts(app.state.jobs_db_path, job_id),
        )

    @app.post("/api/jobs", response_model=EnqueueJobResponse)
    def jobs_enqueue(req: EnqueueJobRequest) -> EnqueueJobResponse:
        jid = (req.job_id or "").strip() or f"job_{int(time.time())}_{uuid.uuid4().hex[:8]}"

        payload: Dict[str, Any] = dict(req.payload or {})
        thread_id = str(payload.get("thread_id") or payload.get("thread") or "").strip() or None
        if thread_id:
            mem_db, led_db = _thread_db_paths(thread_id)

            # Convenience: infer DB paths when absent.
            if req.type in {"propose_promotions"}:
                payload.setdefault("memory_db", mem_db)
            if req.type in {"auto_resolve_contradictions"}:
                payload.setdefault("memory_db", mem_db)
                payload.setdefault("ledger_db", led_db)

            # Research jobs optionally store EXTERNAL memory; if requested, infer memory_db.
            if req.type in {"research_fetch", "research_summarize"}:
                if bool(payload.get("store_as_external_memory")):
                    payload.setdefault("memory_db", mem_db)

        enqueue_job(
            db_path=app.state.jobs_db_path,
            job_id=jid,
            job_type=req.type,
            created_at=now_iso_utc(),
            payload=payload,
            priority=int(req.priority or 0),
        )
        return EnqueueJobResponse(job_id=jid)

    class LearnStatusResponse(BaseModel):
        enabled: bool
        running: bool
        last_started_at: Optional[float] = None
        last_finished_at: Optional[float] = None
        last_ok: Optional[bool] = None
        last_decision: Optional[str] = None
        last_reason: Optional[str] = None
        last_report_path: Optional[str] = None
        last_error: Optional[str] = None
        model_path: Optional[str] = None
        model_file_exists: bool = False

    @app.get("/api/learn/status", response_model=LearnStatusResponse)
    def learn_status() -> LearnStatusResponse:
        st = training_loop.status().to_dict()
        model_path = os.environ.get("CRT_LEARNED_MODEL_PATH")
        exists = bool(model_path and Path(model_path).exists())
        return LearnStatusResponse(
            enabled=bool(st.get("enabled")),
            running=bool(st.get("running")),
            last_started_at=st.get("last_started_at"),
            last_finished_at=st.get("last_finished_at"),
            last_ok=st.get("last_ok"),
            last_decision=st.get("last_decision"),
            last_reason=st.get("last_reason"),
            last_report_path=st.get("last_report_path"),
            last_error=st.get("last_error"),
            model_path=model_path,
            model_file_exists=exists,
        )

    class LearnRunRequest(BaseModel):
        confirm: bool = Field(default=False, description="must be true to run training")

    @app.post("/api/learn/run")
    def learn_run(req: LearnRunRequest, background: BackgroundTasks) -> Dict[str, Any]:
        if not bool(req.confirm):
            return {"ok": False, "error": "confirm must be true"}
        if not training_loop.enabled():
            return {"ok": False, "error": "training loop disabled"}

        kicked = training_loop.trigger_async()
        return {"ok": bool(kicked), "running": training_loop.status().running}
    
    # ========================================================================
    # ACTIVE LEARNING ENDPOINTS
    # ========================================================================
    
    class LearningStatsResponse(BaseModel):
        total_events: int
        total_corrections: int
        model_loaded: bool
        model_version: Optional[int]
        model_accuracy: Optional[float]
        pending_training: bool
        recent_gate_pass_rate: Optional[float]
        recent_events_24h: int
    
    class CorrectionItem(BaseModel):
        event_id: int
        question: str
        predicted_type: str
        corrected_type: str
        timestamp: str
    
    @app.get("/api/learning/stats", response_model=LearningStatsResponse)
    def learning_stats() -> LearningStatsResponse:
        """Get active learning statistics."""
        try:
            coordinator = get_active_learning_coordinator()
            stats: LearningStats = coordinator.get_stats()
            
            return LearningStatsResponse(
                total_events=stats.total_gate_events,
                total_corrections=stats.total_corrections,
                model_loaded=(stats.current_model_version != "none"),
                model_version=int(stats.current_model_version) if stats.current_model_version.isdigit() else None,
                model_accuracy=stats.current_model_accuracy,
                pending_training=(stats.pending_corrections >= stats.next_training_threshold),
                recent_gate_pass_rate=None,  # TODO: Calculate from recent events
                recent_events_24h=0,  # TODO: Calculate from timestamp
            )
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to get learning stats: {e}")
    
    @app.get("/api/learning/events")
    def learning_events_needing_correction(limit: int = Query(default=50, ge=1, le=100)) -> List[Dict[str, Any]]:
        """Get recent gate events that need user correction."""
        try:
            coordinator = get_active_learning_coordinator()
            return coordinator.get_events_needing_correction(limit=limit)
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to get events: {e}")
    
    @app.get("/api/learning/corrections", response_model=list[CorrectionItem])
    def learning_corrections(limit: int = Query(default=10, ge=1, le=100)) -> list[CorrectionItem]:
        """Get recent user corrections."""
        try:
            coordinator = get_active_learning_coordinator()
            corrections = coordinator.get_recent_corrections(limit=limit)
            
            return [
                CorrectionItem(
                    event_id=c["event_id"],
                    question=c["question"],
                    predicted_type=c["predicted_type"],
                    corrected_type=c["corrected_type"],
                    timestamp=c["timestamp"],
                )
                for c in corrections
            ]
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to get corrections: {e}")
    
    class CorrectionRequest(BaseModel):
        corrected_type: str = Field(description="Correct response type: factual/explanatory/conversational")
    
    @app.post("/api/learning/correct/{event_id}")
    def learning_correct(event_id: int, req: CorrectionRequest) -> Dict[str, Any]:
        """Submit user correction for a gate event."""
        try:
            coordinator = get_active_learning_coordinator()
            coordinator.record_user_correction(
                event_id=event_id,
                corrected_type=req.corrected_type,
            )
            
            stats = coordinator.get_stats()
            return {
                "ok": True,
                "pending_training": stats.pending_training,
                "total_corrections": stats.total_corrections,
            }
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to record correction: {e}")

    def _is_architecture_explanation_request(text: str) -> bool:
        t = (text or '').strip().lower()
        if not t:
            return False
        needles = (
            # Direct "what is memory" questions about the system.
            'what is memory to you',
            'what does memory mean to you',
            'why is memory important',
            'why is memory so important',
            'memory to you',
            'how do you work',
            'how you work',
            'how does crt work',
            'how does sse work',
            'crt architecture',
            'system architecture',
            'reconstruction gate',
            'reconstruction gates',
            'trust-weighted',
            'trust weighted',
            'trust weights',
            'contradiction preservation',
            'contradiction ledger',
            'coherence priority',
            'cognitive-reflective',
            'cognitive reflective',
            'sse',
        )
        return any(n in t for n in needles)

    def _is_contradiction_inventory_request(text: str) -> bool:
        """Detect user requests asking about contradictions/conflicts in the conversation.
        
        IMPORTANT: Only trigger on QUERIES, not assertions mentioning contradiction as a topic.
        """
        t = (text or "").strip().lower()
        if not t:
            return False

        # Require contradiction-related terms
        if not any(k in t for k in ("contradict", "inconsisten", "conflict")):
            return False

        # Explicit interrogative patterns
        needles = (
            "what contradictions",
            "which contradictions",
            "any contradictions",
            "are there contradictions",
            "do you have contradictions",
            "contradictions have you",
            "contradictions did you",
            "contradictions detected",
            "contradictions found",
            "what conflicts",
            "any conflicts",
            "in our conversation",
            "in our chat",
        )
        if any(n in t for n in needles):
            return True

        # REMOVED: Fallback check that matched "contradiction detection" assertions
        # Old code: return ("contradict" in t) and ("detect" in t or "found" in t)
        # This caused false positives on assertions like "I work on contradiction detection"
        
        return False

    def _suggest_contradiction_question(engine: CRTEnhancedRAG, entry: Any) -> str:
        """Deterministic, low-risk clarifying question for a ledger entry."""
        try:
            old_id = getattr(entry, "old_memory_id", None)
            new_id = getattr(entry, "new_memory_id", None)
            old_mem = engine.memory.get_memory_by_id(old_id) if old_id else None
            new_mem = engine.memory.get_memory_by_id(new_id) if new_id else None
            old_text = (getattr(old_mem, "text", "") or "").strip()
            new_text = (getattr(new_mem, "text", "") or "").strip()
        except Exception:
            old_text, new_text = "", ""

        if old_text and new_text:
            q = (
                "I have two conflicting statements recorded:\n"
                f"1) {old_text}\n"
                f"2) {new_text}\n\n"
                "Which is correct right now? If both can be true, tell me how."
            )
        else:
            q = "I have a potential contradiction recorded. Can you clarify which version is correct?"

        ctype = (getattr(entry, "contradiction_type", None) or "conflict").strip().lower()
        if ctype == "refinement":
            return q + " (If it’s a refinement, please specify the more precise version.)"
        if ctype == "temporal":
            return q + " (If this changed over time, tell me the current value and when it changed.)"
        return q

    def _work_item_for_entry(engine: CRTEnhancedRAG, thread_id: str, entry: Any) -> ContradictionWorkItem:
        ledger_id = str(getattr(entry, "ledger_id", "") or "")
        status = str(getattr(entry, "status", "") or "open")
        ctype = str(getattr(entry, "contradiction_type", "") or "conflict")
        drift = float(getattr(entry, "drift_mean", 0.0) or 0.0)
        summary = getattr(entry, "summary", None)

        try:
            wl = engine.ledger.get_contradiction_worklog(ledger_id)
        except Exception:
            wl = {"ask_count": 0, "last_asked_at": None}

        # M2 heuristic: open conflicts/revisions should ask user; refinements ask for precision; temporal asks for timeline.
        next_action = "ask_user"
        
        # Create semantic anchor for this contradiction
        semantic_anchor_dict = None
        suggested = None
        try:
            # Retrieve the memory texts
            old_mem_id = str(getattr(entry, "old_memory_id", ""))
            new_mem_id = str(getattr(entry, "new_memory_id", ""))
            
            old_mem = engine.memory.get_memory_by_id(old_mem_id) if old_mem_id else None
            new_mem = engine.memory.get_memory_by_id(new_mem_id) if new_mem_id else None
            
            if old_mem and new_mem:
                old_text = old_mem.text
                new_text = new_mem.text
                
                # Get current turn number for this thread
                turn_num = get_turn_number(thread_id)
                
                # Create the semantic anchor
                anchor = engine.ledger.create_semantic_anchor(
                    entry=entry,
                    old_text=old_text,
                    new_text=new_text,
                    turn_number=turn_num,
                )
                semantic_anchor_dict = anchor.to_dict()
                # Use the anchor's type-aware clarification prompt
                suggested = anchor.clarification_prompt
        except Exception:
            # If anchor creation fails, fall back to no anchor (degraded mode)
            pass
        
        # Fall back to old generic question if anchor creation failed
        if not suggested:
            suggested = _suggest_contradiction_question(engine, entry)

        return ContradictionWorkItem(
            thread_id=_sanitize_thread_id(thread_id),
            ledger_id=ledger_id,
            status=status,
            contradiction_type=ctype,
            drift_mean=drift,
            summary=summary,
            ask_count=int(wl.get("ask_count") or 0),
            last_asked_at=(wl.get("last_asked_at") if wl else None),
            next_action=next_action,
            suggested_question=suggested,
            semantic_anchor=semantic_anchor_dict,
        )

    def _priority_key(item: ContradictionWorkItem) -> tuple:
        # Higher drift first, then fewer asks first, then most recently created (best-effort via ledger_id timestamp).
        return (
            -float(item.drift_mean or 0.0),
            int(item.ask_count or 0),
            item.ledger_id,
        )

    def _load_doc_text(doc_id: str) -> str:
        info = doc_map.get(doc_id)
        if not info:
            return ''
        path = info.get('path')
        try:
            return Path(path).read_text(encoding='utf-8', errors='ignore')  # type: ignore[arg-type]
        except Exception:
            return ''

    def _score_snippet(snippet: str, q_words: list[str]) -> float:
        s = snippet.lower()
        score = 0.0
        for w in q_words:
            if not w:
                continue
            if w in s:
                score += 1.0
        # Prefer shorter, denser snippets.
        score *= 1.0 / max(1.0, (len(snippet) / 800.0))
        return score

    def _answer_from_docs(query: str) -> tuple[str, list[dict[str, Any]]]:
        q = (query or '').strip()
        ql = q.lower()
        q_words = [w for w in re.split(r"[^a-z0-9_]+", ql) if len(w) >= 3]

        # Pick a small curated set of docs for architecture explanations.
        doc_ids = [
            'how_it_works',
            'crt_whitepaper',
            'crt_quick_reference',
            'project_summary',
            'crt_dashboard_guide',
            'architecture',
            'functional_spec',
        ]

        candidates: list[tuple[float, str, str]] = []  # (score, doc_id, snippet)
        for did in doc_ids:
            txt = _load_doc_text(did)
            if not txt:
                continue
            # Split on blank lines; keep paragraph-ish chunks.
            parts = [p.strip() for p in re.split(r"\n\s*\n", txt) if p.strip()]
            for p in parts:
                if len(p) < 60:
                    continue
                if len(p) > 1600:
                    p = p[:1600] + '…'
                sc = _score_snippet(p, q_words)
                if sc <= 0:
                    continue
                candidates.append((sc, did, p))

        candidates.sort(key=lambda x: x[0], reverse=True)
        top = candidates[:6]

        # Build a safe, doc-grounded explanation.
        lines: list[str] = []
        lines.append('This is a design/spec explanation (doc-grounded), not a personal memory claim.')
        lines.append('')
        lines.append(f'Question: {q}')
        lines.append('')

        if not top:
            lines.append('I could not find a relevant section in the local docs set.')
            lines.append('Try asking about a specific component (e.g., “reconstruction gates”, “contradiction ledger”, “trust-weighted memories”).')
            return '\n'.join(lines), []

        prompt_items: list[dict[str, Any]] = []
        for i, (_sc, did, snippet) in enumerate(top, start=1):
            title = str((doc_map.get(did) or {}).get('title') or did)
            lines.append(f'{i}. From {title}:')
            lines.append(snippet)
            lines.append('')
            prompt_items.append({
                'memory_id': f'doc:{did}',
                'text': f'DOC[{did}]: {snippet}',
                'source': 'docs',
                'trust': None,
                'confidence': None,
            })

        lines.append('If you want, tell me which part to go deeper on (gates, memory, ledger, coherence), and I’ll expand that section.')
        return '\n'.join(lines).strip(), prompt_items

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

    def _thread_db_paths_map(tid: str) -> Dict[str, Path]:
        return {
            "memory": (root / f"personal_agent/crt_memory_{tid}.db"),
            "ledger": (root / f"personal_agent/crt_ledger_{tid}.db"),
        }

    def _purge_memory_sources(db_path: Path, sources: list[str]) -> tuple[int, int]:
        # Returns: (deleted_memories, deleted_trust_log)
        if not sources:
            return (0, 0)
        norm_sources = [str(s).strip().lower() for s in sources if str(s).strip()]
        norm_sources = [s for s in norm_sources if s]
        if not norm_sources:
            return (0, 0)

        if not db_path.exists() or not db_path.is_file():
            return (0, 0)

        placeholders = ",".join(["?"] * len(norm_sources))
        deleted_memories = 0
        deleted_trust_log = 0

        try:
            conn = sqlite3.connect(str(db_path))
            cur = conn.cursor()

            # Collect ids to clean up trust_log.
            cur.execute(
                f"SELECT memory_id FROM memories WHERE lower(source) IN ({placeholders})",
                tuple(norm_sources),
            )
            ids = [str(r[0]) for r in cur.fetchall() if r and r[0]]

            if ids:
                id_placeholders = ",".join(["?"] * len(ids))
                cur.execute(
                    f"DELETE FROM trust_log WHERE memory_id IN ({id_placeholders})",
                    tuple(ids),
                )
                deleted_trust_log = int(cur.rowcount or 0)

            cur.execute(
                f"DELETE FROM memories WHERE lower(source) IN ({placeholders})",
                tuple(norm_sources),
            )
            deleted_memories = int(cur.rowcount or 0)

            conn.commit()
            conn.close()
        except Exception:
            try:
                conn.close()  # type: ignore[name-defined]
            except Exception:
                pass
            return (0, 0)

        return (deleted_memories, deleted_trust_log)

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

    @app.post("/api/profile/set_name")
    async def set_profile_name(req: ChatSendRequest) -> ChatSendResponse:
        """Set profile name by sending a FACT message through CRT."""
        # Forward to the main chat endpoint - this ensures proper CRT processing
        return chat_send(req)

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

    @app.get("/api/contradictions/work-items", response_model=list[ContradictionWorkItem])
    def contradiction_work_items(
        thread_id: str = Query(default="default"),
        limit: int = Query(default=20, ge=1, le=200),
    ) -> list[ContradictionWorkItem]:
        engine = get_engine(thread_id)
        try:
            entries = engine.ledger.get_open_contradictions(limit=500)
        except Exception:
            entries = []

        items = [_work_item_for_entry(engine, thread_id, e) for e in entries]
        items.sort(key=_priority_key)
        return items[: int(limit)]

    @app.get("/api/contradictions/next", response_model=ContradictionNextResponse)
    def contradiction_next(thread_id: str = Query(default="default")) -> ContradictionNextResponse:
        engine = get_engine(thread_id)
        try:
            entries = engine.ledger.get_open_contradictions(limit=500)
        except Exception:
            entries = []
        if not entries:
            return ContradictionNextResponse(thread_id=_sanitize_thread_id(thread_id), has_item=False, item=None)

        items = [_work_item_for_entry(engine, thread_id, e) for e in entries]
        items.sort(key=_priority_key)
        return ContradictionNextResponse(thread_id=_sanitize_thread_id(thread_id), has_item=True, item=items[0])

    @app.post("/api/contradictions/asked")
    def contradiction_mark_asked(req: ContradictionAskedRequest) -> Dict[str, Any]:
        engine = get_engine(req.thread_id)
        try:
            engine.ledger.mark_contradiction_asked(req.ledger_id)
        except Exception:
            return {"ok": False}
        return {"ok": True}

    @app.post("/api/contradictions/respond", response_model=ContradictionRespondResponse)
    def contradiction_respond(req: ContradictionRespondRequest) -> ContradictionRespondResponse:
        engine = get_engine(req.thread_id)

        recorded = False
        resolved = False
        parse_result = None
        
        try:
            engine.ledger.record_contradiction_user_answer(req.ledger_id, req.answer)
            recorded = True
        except Exception:
            recorded = False

        if bool(req.resolve):
            # Try to use semantic anchor for intelligent parsing
            try:
                # Get the contradiction entry to build anchor
                entries = [e for e in engine.ledger.get_all_contradictions(limit=1000) 
                          if getattr(e, 'ledger_id', '') == req.ledger_id]
                
                if entries:
                    entry = entries[0]
                    old_mem_id = str(getattr(entry, "old_memory_id", ""))
                    new_mem_id = str(getattr(entry, "new_memory_id", ""))
                    
                    # Retrieve memory texts
                    old_mem = engine.memory.get_memory_by_id(old_mem_id) if old_mem_id else None
                    new_mem = engine.memory.get_memory_by_id(new_mem_id) if new_mem_id else None
                    
                    if old_mem and new_mem:
                        # Create semantic anchor
                        from personal_agent.crt_semantic_anchor import (
                            parse_user_answer,
                            is_resolution_grounded
                        )
                        
                        anchor = engine.ledger.create_semantic_anchor(
                            entry=entry,
                            old_text=old_mem.text,
                            new_text=new_mem.text,
                            turn_number=get_turn_number(req.thread_id),
                        )
                        
                        # Parse the user's answer using semantic anchor
                        parse_result = parse_user_answer(anchor, req.answer)
                        
                        # Validate grounding
                        if is_resolution_grounded(anchor, parse_result):
                            # Use parsed resolution instead of raw request
                            resolution_method = parse_result.get("resolution_method", req.resolution_method)
                            chosen_memory_id = parse_result.get("chosen_memory_id", req.merged_memory_id)
                            new_status = parse_result.get("new_status", req.new_status)
                        else:
                            # Grounding check failed - fall back to request params
                            resolution_method = req.resolution_method
                            chosen_memory_id = req.merged_memory_id
                            new_status = req.new_status
                    else:
                        # No memories found - use request params
                        resolution_method = req.resolution_method
                        chosen_memory_id = req.merged_memory_id
                        new_status = req.new_status
                else:
                    # No entry found - use request params
                    resolution_method = req.resolution_method
                    chosen_memory_id = req.merged_memory_id
                    new_status = req.new_status
                    
            except Exception:
                # Parsing failed - fall back to request params
                resolution_method = req.resolution_method
                chosen_memory_id = req.merged_memory_id
                new_status = req.new_status
            
            try:
                engine.ledger.resolve_contradiction(
                    ledger_id=req.ledger_id,
                    method=str(resolution_method or "user_clarified"),
                    merged_memory_id=chosen_memory_id,
                    new_status=str(new_status or "resolved"),
                )
                resolved = True
            except Exception:
                resolved = False

        # Return the next work item for convenience (M2 loop).
        try:
            nxt = contradiction_next(thread_id=req.thread_id)
        except Exception:
            nxt = ContradictionNextResponse(thread_id=_sanitize_thread_id(req.thread_id), has_item=False, item=None)

        return ContradictionRespondResponse(
            ok=bool(recorded),
            thread_id=_sanitize_thread_id(req.thread_id),
            ledger_id=str(req.ledger_id),
            recorded=bool(recorded),
            resolved=bool(resolved),
            next=nxt,
        )

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
        
        # Increment turn counter
        increment_turn(req.thread_id)

        # Deterministic ledger-backed contradiction inventory.
        # This is intentionally handled outside the LLM path for auditability.
        if _is_contradiction_inventory_request(req.message):
            try:
                open_entries = engine.ledger.get_open_contradictions(limit=50)
            except Exception:
                open_entries = []

            open_count = len(open_entries)
            hard_conflicts = sum(1 for e in open_entries if (getattr(e, "contradiction_type", "") or "") == "conflict")

            if open_entries:
                lines = [
                    "I can summarize what I've recorded in the contradiction ledger so far.",
                    f"Open contradictions: {open_count}.",
                    "",
                    "Most recent open items:",
                ]
                for e in open_entries[:10]:
                    typ = getattr(e, "contradiction_type", None) or "conflict"
                    status = getattr(e, "status", None) or "open"
                    summary = getattr(e, "summary", None) or "(no summary)"
                    lines.append(f"- [{typ}/{status}] {summary}")
                answer = "\n".join(lines)
            else:
                answer = (
                    "I don't currently have any open contradictions recorded in the ledger. "
                    "If you think something conflicts, point it out and I'll log it explicitly."
                )

            return ChatSendResponse(
                answer=answer,
                response_type="explanation",
                gates_passed=False,
                gate_reason="ledger_contradictions",
                session_id=getattr(engine, "session_id", None),
                metadata={
                    "mode": "uncertainty",
                    "confidence": 0.65,
                    "contradiction_detected": bool(open_count),
                    "unresolved_contradictions_total": open_count,
                    "unresolved_hard_conflicts": hard_conflicts,
                    "retrieved_memories": [],
                    "prompt_memories": [],
                },
            )

        # Safe doc-grounded channel for architecture/system explanation questions.
        if _is_architecture_explanation_request(req.message):
            answer, prompt_items = _answer_from_docs(req.message)
            return ChatSendResponse(
                answer=answer,
                response_type='explanation',
                gates_passed=True,  # Doc-grounded explanations are safe - citing real docs
                gate_reason='docs_explanation',
                session_id=getattr(engine, 'session_id', None),
                metadata={
                    'confidence': 0.85,
                    'retrieved_memories': [],
                    'prompt_memories': prompt_items,
                },
            )

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

        # AGENT INTEGRATION: Check for proactive triggers
        agent_activated = False
        agent_trace_data = None
        agent_answer = None
        
        try:
            from personal_agent.proactive_triggers import ProactiveTriggers
            from personal_agent.agent_loop import create_agent
            from pathlib import Path
            
            # Analyze response for triggers
            triggers_engine = ProactiveTriggers(
                confidence_threshold=0.5,
                auto_research_threshold=0.4,  # Auto-activate below 0.4 (was 0.3)
                contradiction_auto_resolve=False,  # Don't auto-resolve contradictions
            )
            detected_triggers = triggers_engine.analyze_response(result)
            
            # Auto-activate agent if triggers detected
            if triggers_engine.should_activate_agent(detected_triggers):
                # Create research engine
                research_engine = None
                try:
                    from personal_agent.research_engine import ResearchEngine
                    research_engine = ResearchEngine()
                except Exception:
                    pass
                
                # Create and run agent
                agent = create_agent(
                    memory_engine=engine.memory,
                    research_engine=research_engine,
                    workspace_root=Path.cwd(),
                    max_steps=8,
                )
                
                task = triggers_engine.get_agent_task(detected_triggers, req.message)
                trace = agent.run(task)
                
                agent_activated = True
                agent_answer = trace.final_answer
                agent_trace_data = trace.to_dict()
                
        except Exception as e:
            # Agent execution failed - continue without agent
            print(f"Agent execution error: {e}")
            pass

        # Keep the payload compact and UI-friendly.
        metadata: Dict[str, Any] = {
            "mode": result.get("mode"),
            "confidence": result.get("confidence"),
            "intent_alignment": result.get("intent_alignment"),
            "memory_alignment": result.get("memory_alignment"),
            "contradiction_detected": result.get("contradiction_detected"),
            "unresolved_contradictions_total": result.get("unresolved_contradictions_total"),
            "unresolved_hard_conflicts": result.get("unresolved_hard_conflicts"),
            "learned_suggestions": result.get("learned_suggestions") or [],
            "heuristic_suggestions": result.get("heuristic_suggestions") or [],
            "agent_activated": agent_activated,
            "agent_answer": agent_answer,
            "agent_trace": agent_trace_data,
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

    # ========================================================================
    # M3: Research API Endpoints
    # ========================================================================
    
    @app.post("/api/research/search", response_model=ResearchSearchResponse)
    def research_search(req: ResearchSearchRequest) -> ResearchSearchResponse:
        """
        Execute research query and return evidence packet with citations.
        
        Design:
        - Searches local workspace documents (Phase 1)
        - Stores result in notes lane (quarantined, trust=0.4)
        - Returns citations with full provenance
        - Never auto-promotes to belief lane
        """
        tid = _sanitize_thread_id(req.thread_id)
        engine = get_engine(tid)
        
        # Get workspace root for local document search
        workspace_root = str(Path.cwd())
        
        # Execute research query
        research_engine = ResearchEngine(workspace_root=workspace_root)
        packet = research_engine.research(
            query=req.query,
            max_sources=req.max_sources,
            search_local=True,
            search_web=False,  # M3.5
        )
        
        # Store in memory with provenance
        memory_id = engine.memory.store_research_result(
            query=req.query,
            evidence_packet=packet,
        )
        
        # Convert citations to response model
        citations = [
            CitationModel(
                quote_text=c.quote_text,
                source_url=c.source_url,
                char_offset=[c.char_offset[0], c.char_offset[1]],
                fetched_at=c.fetched_at.isoformat(),
                confidence=c.confidence,
            )
            for c in packet.citations
        ]
        
        return ResearchSearchResponse(
            packet_id=packet.packet_id,
            query=req.query,
            summary=packet.summary,
            citations=citations,
            memory_id=memory_id,
            citation_count=packet.citation_count(),
        )
    
    @app.get("/api/research/citations/{memory_id}", response_model=ResearchCitationsResponse)
    def get_citations(memory_id: str, thread_id: str = Query(default="default")) -> ResearchCitationsResponse:
        """Get citations for a research memory."""
        tid = _sanitize_thread_id(thread_id)
        engine = get_engine(tid)
        
        # Get citations from memory context
        citations_data = engine.memory.get_research_citations(memory_id)
        
        citations = [
            CitationModel(
                quote_text=c["quote_text"],
                source_url=c["source_url"],
                char_offset=c["char_offset"],
                fetched_at=c["fetched_at"],
                confidence=c.get("confidence", 0.8),
            )
            for c in citations_data
        ]
        
        return ResearchCitationsResponse(
            memory_id=memory_id,
            citations=citations,
        )
    
    @app.post("/api/research/promote", response_model=ResearchPromoteResponse)
    def promote_research(req: ResearchPromoteRequest) -> ResearchPromoteResponse:
        """
        Promote research note to belief lane.
        
        Requires explicit user confirmation (user_confirmed=True).
        Increases trust from 0.4 → 0.8 (belief threshold).
        """
        tid = _sanitize_thread_id(req.thread_id)
        engine = get_engine(tid)
        
        if not req.user_confirmed:
            return ResearchPromoteResponse(
                ok=False,
                memory_id=req.memory_id,
                promoted=False,
            )
        
        # Promote to belief lane
        promoted = engine.memory.promote_to_belief(
            memory_id=req.memory_id,
            user_confirmed=True,
        )
        
        return ResearchPromoteResponse(
            ok=True,
            memory_id=req.memory_id,
            promoted=promoted,
        )

    # Agent API Endpoints
    @app.post("/api/agent/run", response_model=AgentRunResponse)
    def run_agent(req: AgentRunRequest) -> AgentRunResponse:
        """
        Run autonomous agent for a task.
        
        Executes ReAct loop: Thought → Action → Observation cycles.
        Returns complete execution trace.
        """
        tid = _sanitize_thread_id(req.thread_id)
        engine = get_engine(tid)
        
        try:
            from personal_agent.agent_loop import create_agent
            from pathlib import Path
            
            # Create research engine if not exists
            research_engine = None
            try:
                from personal_agent.research_engine import ResearchEngine
                research_engine = ResearchEngine()
            except Exception:
                pass
            
            agent = create_agent(
                memory_engine=engine.memory,
                research_engine=research_engine,
                workspace_root=Path.cwd(),
                max_steps=req.max_steps,
            )
            
            trace = agent.run(req.query)
            
            # Convert trace to response model
            steps = [
                AgentStepModel(
                    step_num=s.step_num,
                    thought=s.thought,
                    action={
                        "tool": s.action.tool.value if s.action else None,
                        "args": s.action.args if s.action else None,
                        "reasoning": s.action.reasoning if s.action else None,
                    } if s.action else None,
                    observation={
                        "tool": s.observation.tool.value if s.observation else None,
                        "success": s.observation.success if s.observation else None,
                        "result": str(s.observation.result)[:500] if s.observation and s.observation.result else None,
                        "error": s.observation.error if s.observation else None,
                    } if s.observation else None,
                    timestamp=s.timestamp.isoformat(),
                )
                for s in trace.steps
            ]
            
            return AgentRunResponse(
                trace=AgentTraceModel(
                    query=trace.query,
                    steps=steps,
                    final_answer=trace.final_answer,
                    success=trace.success,
                    error=trace.error,
                    started_at=trace.started_at.isoformat(),
                    completed_at=trace.completed_at.isoformat() if trace.completed_at else None,
                ),
                triggered_by=None,
            )
            
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Agent execution failed: {str(e)}")
    
    @app.post("/api/agent/analyze-triggers", response_model=AgentTriggersResponse)
    def analyze_triggers(thread_id: str = Query(default="default"), response_data: Dict[str, Any] = None) -> AgentTriggersResponse:
        """
        Analyze CRT response for agent trigger conditions.
        
        Checks for:
        - Low confidence
        - Contradictions
        - Insufficient context
        - Memory gaps
        - Complex queries
        
        Returns suggested agent activation.
        """
        tid = _sanitize_thread_id(thread_id)
        
        if not response_data:
            return AgentTriggersResponse(
                thread_id=tid,
                triggers=[],
                should_activate=False,
                suggested_task=None,
            )
        
        try:
            from personal_agent.proactive_triggers import ProactiveTriggers
            
            triggers_engine = ProactiveTriggers()
            detected = triggers_engine.analyze_response(response_data)
            should_activate = triggers_engine.should_activate_agent(detected)
            
            suggested_task = None
            if detected and response_data.get("query"):
                suggested_task = triggers_engine.get_agent_task(detected, response_data["query"])
            
            return AgentTriggersResponse(
                thread_id=tid,
                triggers=[
                    {
                        "type": t.trigger_type.value,
                        "reason": t.reason,
                        "suggested_action": t.suggested_action,
                        "auto_execute": t.should_auto_execute,
                    }
                    for t in detected
                ],
                should_activate=should_activate,
                suggested_task=suggested_task,
            )
            
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Trigger analysis failed: {str(e)}")
    
    @app.get("/api/agent/status", response_model=AgentStatusResponse)
    def agent_status() -> AgentStatusResponse:
        """Get agent system status."""
        available = False
        llm_available = False
        reasoning_available = False
        tools_count = 0
        
        try:
            from personal_agent.agent_loop import create_agent
            from personal_agent.ollama_client import get_ollama_client
            
            # Test agent creation
            agent = create_agent()
            available = True
            tools_count = len(agent.tools._tools)
            
            # Test LLM
            try:
                llm = get_ollama_client()
                llm_available = True
            except Exception:
                pass
            
            # Test reasoning
            reasoning_available = agent.reasoning is not None
            
        except Exception:
            pass
        
        return AgentStatusResponse(
            available=available,
            llm_available=llm_available,
            reasoning_available=reasoning_available,
            tools_count=tools_count,
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

        paths = _thread_db_paths_map(tid)
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

    @app.post("/api/thread/purge_memories", response_model=ThreadPurgeMemoriesResponse)
    def thread_purge_memories(req: ThreadPurgeMemoriesRequest) -> ThreadPurgeMemoriesResponse:
        tid = _sanitize_thread_id(req.thread_id)

        # Require explicit confirmation.
        if not bool(req.confirm):
            return ThreadPurgeMemoriesResponse(
                thread_id=tid,
                sources=list(req.sources or []),
                confirm=False,
                deleted_memories=0,
                deleted_trust_log=0,
                ok=False,
            )

        # Drop cached engine first to avoid holding references and to ensure re-open.
        engines.pop(tid, None)

        sources = [str(s) for s in (req.sources or [])]
        paths = _thread_db_paths_map(tid)
        deleted_memories, deleted_trust_log = _purge_memory_sources(paths["memory"], sources)

        return ThreadPurgeMemoriesResponse(
            thread_id=tid,
            sources=sources,
            confirm=True,
            deleted_memories=deleted_memories,
            deleted_trust_log=deleted_trust_log,
            ok=True,
        )

    # ============================================================================
    # Thread Management
    # ============================================================================

    @app.get("/api/threads", response_model=list[ThreadListItem])
    def list_threads() -> list[ThreadListItem]:
        """List all threads with basic metadata."""
        # For now, return threads from in-memory engines cache
        # In production, this would query a threads table in the database
        result = []
        for tid in engines.keys():
            result.append(ThreadListItem(
                id=tid,
                title=tid.replace('_', ' ').title(),
                updated_at=time.time(),
                message_count=0
            ))
        # Always include 'default' if not present
        if not any(t.id == 'default' for t in result):
            result.insert(0, ThreadListItem(
                id='default',
                title='Default Thread',
                updated_at=time.time(),
                message_count=0
            ))
        return result

    @app.post("/api/threads", response_model=ThreadListItem)
    def create_thread(req: ThreadCreateRequest) -> ThreadListItem:
        """Create a new thread."""
        thread_id = str(uuid.uuid4())[:8]
        tid = _sanitize_thread_id(thread_id)
        
        # Initialize engine for this thread (creates DBs)
        get_engine(tid)
        
        return ThreadListItem(
            id=tid,
            title=req.title,
            updated_at=time.time(),
            message_count=0
        )

    @app.put("/api/threads/{thread_id}", response_model=ThreadListItem)
    def update_thread(thread_id: str, req: ThreadUpdateRequest) -> ThreadListItem:
        """Update thread metadata (e.g., title)."""
        tid = _sanitize_thread_id(thread_id)
        
        # Ensure thread exists
        get_engine(tid)
        
        return ThreadListItem(
            id=tid,
            title=req.title,
            updated_at=time.time(),
            message_count=0
        )

    @app.delete("/api/threads/{thread_id}")
    def delete_thread(thread_id: str) -> dict:
        """Delete a thread and its associated data."""
        tid = _sanitize_thread_id(thread_id)
        
        if tid == 'default':
            raise HTTPException(status_code=400, detail="Cannot delete default thread")
        
        # Remove from engines cache
        if tid in engines:
            del engines[tid]
        if tid in turn_counters:
            del turn_counters[tid]
        
        # Optionally delete the DB files
        memory_db, ledger_db = _thread_db_paths(tid)
        try:
            if Path(memory_db).exists():
                Path(memory_db).unlink()
            if Path(ledger_db).exists():
                Path(ledger_db).unlink()
        except Exception as e:
            # Log but don't fail on DB deletion errors
            pass
        
        return {"ok": True, "thread_id": tid, "deleted": True}

    return app


app = create_app()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=int(os.getenv("PORT", "8000")))
