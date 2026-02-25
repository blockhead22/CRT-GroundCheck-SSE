"""Shared Pydantic models for modularized routes.

All Pydantic request/response models live here so route modules and crt_api.py
can share them without circular imports.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Health / Misc
# ---------------------------------------------------------------------------

class HealthResponse(BaseModel):
    status: str


# ---------------------------------------------------------------------------
# Chat
# ---------------------------------------------------------------------------

class ChatSendRequest(BaseModel):
    thread_id: str = Field(default="default", description="Client thread identifier")
    message: str = Field(min_length=1, description="User message")
    user_marked_important: bool = Field(default=False)
    mode: Optional[str] = Field(default=None, description="Optional reasoning mode")
    phase_mode: bool = Field(default=False, description="Emit phase events (analyze/plan/answer) in stream")


class ChatSendResponse(BaseModel):
    answer: str
    response_type: str
    gates_passed: bool
    gate_reason: Optional[str] = None
    session_id: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)
    xray: Optional[Dict[str, Any]] = Field(default=None, description="X-Ray mode: memory evidence and conflicts")


# ---------------------------------------------------------------------------
# Docs
# ---------------------------------------------------------------------------

class DocListItem(BaseModel):
    id: str
    title: str
    kind: str


class DocGetResponse(BaseModel):
    id: str
    title: str
    kind: str
    markdown: str


# ---------------------------------------------------------------------------
# Dashboard
# ---------------------------------------------------------------------------

class DashboardOverviewResponse(BaseModel):
    thread_id: str
    session_id: Optional[str] = None
    memories_total: int
    open_contradictions: int
    belief_ratio: float
    speech_ratio: float
    belief_count: int
    speech_count: int


# ---------------------------------------------------------------------------
# Memory
# ---------------------------------------------------------------------------

class MemoryListItem(BaseModel):
    memory_id: str
    text: str
    timestamp: float
    confidence: float
    trust: float
    source: str
    sse_mode: str
    thread_id: Optional[str] = None


# ---------------------------------------------------------------------------
# Contradictions
# ---------------------------------------------------------------------------

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
    contradiction_id: Optional[str] = None
    slot: Optional[str] = None
    old_value: Optional[str] = None
    new_value: Optional[str] = None
    old_trust: Optional[float] = None
    new_trust: Optional[float] = None
    detected_at: Optional[float] = None
    policy: Optional[str] = None


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
    semantic_anchor: Optional[Dict[str, Any]] = None


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
    next: Optional[ContradictionNextResponse] = None


class ResolveContradictionPolicyRequest(BaseModel):
    """Request for policy-driven contradiction resolution."""
    thread_id: str = Field(default="default")
    ledger_id: str
    resolution: str = Field(description="OVERRIDE | PRESERVE | ASK_USER")
    chosen_memory_id: Optional[str] = Field(default=None, description="Required for OVERRIDE")
    user_confirmation: str = Field(default="", description="User feedback/explanation")


class ResolveContradictionPolicyResponse(BaseModel):
    """Response from policy-driven contradiction resolution."""
    status: str
    ledger_id: str
    resolution: str
    deprecated_memory: Optional[str] = None
    active_memory: Optional[str] = None
    message: Optional[str] = None


# ---------------------------------------------------------------------------
# Loops / Journal
# ---------------------------------------------------------------------------

class LoopRunRequest(BaseModel):
    thread_id: str = Field(default="default")
    mode: Optional[str] = Field(default="both", description="reflection | personality | both")
    prompt: Optional[str] = Field(default=None, description="Optional manual prompt for the loop run")


class LoopRunResponse(BaseModel):
    ok: bool = True
    thread_id: str
    ran: List[str] = Field(default_factory=list)
    reflection_scorecard: Optional[Dict[str, Any]] = None
    personality_profile: Optional[Dict[str, Any]] = None
    open_contradictions: Optional[int] = None


class JournalSettingsRequest(BaseModel):
    thread_id: str = Field(default="default")
    auto_reply_enabled: bool = Field(default=True)


class JournalSettingsResponse(BaseModel):
    thread_id: str
    auto_reply_enabled: bool
    auto_reply_enabled_override: Optional[bool] = None
    auto_reply_chance: float
    auto_reply_min_seconds: int
    auto_reply_interval_seconds: int


class JournalReplyRequest(BaseModel):
    thread_id: str = Field(default="default")
    reply_to: int = Field(ge=1)
    body: str = Field(min_length=1, max_length=4000)
    author: Optional[str] = None
    title: Optional[str] = None


class JournalReplyResponse(BaseModel):
    ok: bool = True
    entry: Dict[str, Any]
    auto_reply_created: bool = False


# ---------------------------------------------------------------------------
# Fact Extraction
# ---------------------------------------------------------------------------

class FactExtractionRequest(BaseModel):
    text: str = Field(min_length=1, description="Text to extract facts from")
    skip_llm: bool = Field(default=False, description="If true, only extract hard slots (faster)")


class ExtractedFactItem(BaseModel):
    slot: str
    value: str
    normalized: str
    tier: str
    source: str
    confidence: Optional[float] = None


class FactExtractionResponse(BaseModel):
    text: str
    hard_facts: Dict[str, ExtractedFactItem]
    open_tuples: List[ExtractedFactItem]
    extraction_time: float
    methods_used: List[str]


class StructuredFactsResponse(BaseModel):
    thread_id: str
    facts: Dict[str, Any]
    count: int


class FactHistoryResponse(BaseModel):
    thread_id: str
    slot: str
    history: List[Dict[str, Any]]


class IntentQueryRequest(BaseModel):
    thread_id: str = Field(default="default")
    message: str = Field(min_length=1)
    user_marked_important: bool = Field(default=False)
    include_trace: bool = Field(default=False)


class IntentQueryResponse(BaseModel):
    answer: str
    intent: str
    confidence: float
    response_type: str
    gates_passed: bool
    gate_reason: Optional[str] = None
    trace: Optional[List[Dict[str, Any]]] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


# ---------------------------------------------------------------------------
# Jobs
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# Learning / Active Learning
# ---------------------------------------------------------------------------

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


class LearnRunRequest(BaseModel):
    confirm: bool = Field(default=False, description="must be true to run training")


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


class CorrectionRequest(BaseModel):
    corrected_type: str = Field(description="Correct response type: factual/explanatory/conversational")


# ---------------------------------------------------------------------------
# Feedback
# ---------------------------------------------------------------------------

class FeedbackThumbsRequest(BaseModel):
    interaction_id: str = Field(description="ID of the interaction to rate")
    thumbs_up: bool = Field(description="True for thumbs up, False for thumbs down")
    comment: Optional[str] = Field(default=None, description="Optional feedback comment")


class FeedbackCorrectionRequest(BaseModel):
    interaction_id: str = Field(description="ID of the interaction to correct")
    correction_type: str = Field(description="Type: fact, slot, response, other")
    field_name: Optional[str] = Field(default=None, description="Field being corrected (e.g., 'name')")
    incorrect_value: Optional[str] = Field(default=None, description="The incorrect value")
    correct_value: Optional[str] = Field(default=None, description="The correct value")
    comment: Optional[str] = Field(default=None, description="Additional context")


class FeedbackReportRequest(BaseModel):
    interaction_id: str = Field(description="ID of the interaction to report")
    issue_type: str = Field(description="Type of issue: incorrect, offensive, other")
    description: str = Field(description="Describe the issue")


# ---------------------------------------------------------------------------
# Threads
# ---------------------------------------------------------------------------

class ThreadListItem(BaseModel):
    id: str
    title: str
    updated_at: float
    message_count: int


class ThreadCreateRequest(BaseModel):
    title: str = Field(default="New chat", max_length=200)


class ThreadUpdateRequest(BaseModel):
    title: str = Field(max_length=200)


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


# ---------------------------------------------------------------------------
# Profile
# ---------------------------------------------------------------------------

class ProfileResponse(BaseModel):
    thread_id: str
    name: Optional[str] = None
    slots: Dict[str, str] = Field(default_factory=dict)


# ---------------------------------------------------------------------------
# Research
# ---------------------------------------------------------------------------

class CitationModel(BaseModel):
    quote_text: str
    source_url: str
    char_offset: list[int]
    fetched_at: str
    confidence: float = 0.8


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


# ---------------------------------------------------------------------------
# Email
# ---------------------------------------------------------------------------

class EmailDigestRequest(BaseModel):
    thread_id: str = Field(default="default")
    to: str = Field(min_length=3, description="Recipient email address")
    subject: Optional[str] = Field(default=None, description="Optional subject override")


class EmailDigestResponse(BaseModel):
    ok: bool
    to: str
    subject: str
    error: Optional[str] = None


# ---------------------------------------------------------------------------
# Agent
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# Scheduled Tasks
# ---------------------------------------------------------------------------

class CreateScheduledTaskRequest(BaseModel):
    task_type: str = "reminder"
    scheduled_at: Optional[float] = None
    scheduled_time_text: Optional[str] = None
    thread_id: str = "default"
    reminder_text: Optional[str] = None
    thought_content: Optional[str] = None
    job_type: Optional[str] = None
    job_payload: Optional[Dict[str, Any]] = None
    recurrence: Optional[str] = None


class ScheduledTaskResponse(BaseModel):
    task_id: str
    task_type: str
    scheduled_at: float
    scheduled_time_formatted: str
    thread_id: str
    status: str
    payload: Dict[str, Any]
    recurrence: Optional[str] = None


class QuickReminderRequest(BaseModel):
    text: str = Field(..., description="Message like 'remind me in 2 hours to call mom'")
    thread_id: str = "default"


class ScheduleThoughtRequest(BaseModel):
    thought_content: str = Field(..., description="The thought or topic to ponder")
    scheduled_time_text: str = Field(..., description="When to post the thought, e.g. 'in 1 hour'")
    thread_id: str = "default"


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------

class AuthRegisterRequest(BaseModel):
    username: str
    password: str
    display_name: Optional[str] = None


class AuthLoginRequest(BaseModel):
    username: str
    password: str


class AuthUserResponse(BaseModel):
    id: int
    username: str
    display_name: str
    created_at: int


class AuthLoginResponse(BaseModel):
    ok: bool
    token: str
    user: AuthUserResponse


class AuthMeResponse(BaseModel):
    ok: bool
    user: Optional[AuthUserResponse] = None


class ChatThreadModel(BaseModel):
    id: str
    title: str
    messages: list[dict]
    updatedAt: int


class SyncChatRequest(BaseModel):
    threads: list[ChatThreadModel]


class SyncChatResponse(BaseModel):
    ok: bool
    threads: list[dict]
