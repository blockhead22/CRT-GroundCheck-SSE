import os
import re
import sqlite3
import sys
import time
import uuid
import json
import logging
import threading
import numpy as np

# Force UTF-8 stdout/stderr on Windows to prevent charmap encoding crashes
# when responses contain emoji or non-ASCII characters.
if sys.platform == "win32":
    for _stream in (sys.stdout, sys.stderr):
        if hasattr(_stream, "reconfigure"):
            try:
                _stream.reconfigure(encoding="utf-8", errors="replace")
            except Exception:
                pass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from personal_agent.text_utils import (
    sanitize_thread_id as _sanitize_thread_id,
    strip_thinking_tags as _strip_thinking_tags,
)

logger = logging.getLogger(__name__)

from fastapi import FastAPI, HTTPException, Request
from fastapi import Query
from fastapi import BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from routes import register_routes

from personal_agent.crt_rag import CRTEnhancedRAG
from personal_agent.fact_slots import extract_fact_slots, create_simple_fact
from personal_agent.two_tier_facts import TwoTierFactSystem, TwoTierExtractionResult
from personal_agent.artifact_store import now_iso_utc
from personal_agent.litellm_client import UnifiedLLMClient, create_llm_client
from personal_agent.idle_scheduler import CRTIdleScheduler
from personal_agent.evidence_packet import Citation, EvidencePacket
from personal_agent.research_engine import ResearchEngine
from personal_agent.scheduled_tasks import (
    ScheduledTasksLoop,
    ScheduledTask,
    TaskType,
    create_scheduled_task,
    get_pending_scheduled_tasks,
    get_due_tasks,
    cancel_scheduled_task,
    get_task_by_id,
    schedule_reminder,
    schedule_thought,
    parse_natural_time,
    extract_reminder_from_message,
    format_upcoming_tasks,
    init_scheduled_tasks_db,
)
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
from personal_agent.skill_registry import SkillRegistry
from personal_agent.training_loop import CRTTrainingLoop
from personal_agent.dnnt.background_learning import BackgroundLearningConfig
from personal_agent.dnnt_retraining_loop import DNNTBackgroundLoop
from personal_agent.model_router import ModelRouter
from personal_agent.active_learning import get_active_learning_coordinator, LearningStats
from personal_agent.db_utils import get_thread_session_db, get_db_connection
from personal_agent.engine.collapse_trails import get_collapse_trail_logger
from personal_agent.runtime_paths import (
    get_runtime_data_root,
    iter_existing_memory_dbs,
    resolve_active_learning_db_path,
    resolve_collapse_trails_db_path,
    resolve_jobs_artifacts_dir,
    resolve_jobs_db_path,
    resolve_runtime_dir,
    resolve_runtime_path,
    resolve_scheduled_tasks_db_path,
    resolve_skills_registry_db_path,
    resolve_managed_skills_dir,
    resolve_ledger_db_path,
    resolve_memory_db_path,
)
from personal_agent.continuous_loops import build_loops, maybe_reply_to_journal_entry
from personal_agent.greeting_system import get_time_based_greeting, GreetingSystem
from personal_agent.episodic_memory import get_episodic_manager, EpisodicMemoryManager
from personal_agent.reflection_system import run_reflection_pass, ReflectionDB, ReflectionResult
from personal_agent.heartbeat_system import HeartbeatConfig
from personal_agent.heartbeat_api import (
    HeartbeatConfigRequest,
    HeartbeatConfigResponse,
    HeartbeatRunResponse,
    HeartbeatHistoryResponse,
    HeartbeatHistoryItem,
    HeartbeatMDRequest,
    HeartbeatMDResponse,
)

# Auth module
from dotenv import load_dotenv

load_dotenv(override=True)

import auth as auth_module

# Constants for resolution policies
RESOLUTION_TRUST_BOOST = 0.1  # Trust boost for chosen memory in OVERRIDE resolution

# Tasking loop throttling (optional)
try:
    _TASKING_INTERVAL_SECONDS = float(os.getenv("CRT_TASKING_INTERVAL_SECONDS", "0") or 0)
except Exception:
    _TASKING_INTERVAL_SECONDS = 0.0
_TASKING_LAST_RUN: Dict[str, float] = {}
_TASKING_LOCK = threading.Lock()


# _sanitize_thread_id and _strip_thinking_tags imported from personal_agent.text_utils


def _env_bool(name: str, default: bool = True) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return str(raw).strip().lower() in {"1", "true", "yes", "y", "on"}


def _env_float(name: str, default: float) -> float:
    raw = os.getenv(name)
    if raw is None:
        return default
    try:
        return float(raw)
    except Exception:
        return default


def _journal_defaults() -> Dict[str, Any]:
    chance = max(0.0, min(1.0, _env_float("CRT_JOURNAL_SELF_REPLY_CHANCE", 0.25)))
    min_seconds = int(max(0, _env_float("CRT_JOURNAL_SELF_REPLY_MIN_SECONDS", 1800)))
    interval_seconds = int(max(60, _env_float("CRT_JOURNAL_SELF_REPLY_LOOP_SECONDS", 1800)))
    enabled = _env_bool("CRT_JOURNAL_SELF_REPLY_ENABLED", True)
    return {
        "auto_reply_enabled": enabled,
        "auto_reply_chance": chance,
        "auto_reply_min_seconds": min_seconds,
        "auto_reply_interval_seconds": interval_seconds,
    }


def _format_style_instruction(
    style_profile: Optional[Dict[str, Any]],
    personality_profile: Optional[Dict[str, Any]] = None,
) -> str:
    if not style_profile:
        return ""
    label = str(style_profile.get("tone_label") or "balanced").lower()
    personality_profile = personality_profile or {}
    verbosity_pref = str(personality_profile.get("verbosity") or "").lower()
    emoji_pref = str(personality_profile.get("emoji") or "").lower()
    format_pref = str(personality_profile.get("format") or "").lower()
    if label == "playful":
        base = (
            "Tone: playful and witty when appropriate; mirror the user's humor. "
            "Shift to serious and grounded when the topic is serious. Keep language natural and not overly formal."
        )
    elif label == "serious":
        base = (
            "Tone: calm, direct, and empathetic. Avoid jokes unless the user cues humor. "
            "Keep language natural and not overly formal."
        )
    elif label == "adaptive":
        base = (
            "Tone: adaptive; light when the user is playful, grounded when the user is serious. "
            "Keep a warm, consistent voice. Keep language natural and not overly formal."
        )
    else:
        base = (
            "Tone: friendly and flexible; lightly playful when the user is playful, "
            "and serious when they are serious. Keep language natural and not overly formal."
        )

    verbosity_line = ""
    if verbosity_pref == "concise":
        verbosity_line = "Prefer concise responses unless detail is explicitly requested."
    elif verbosity_pref == "verbose":
        verbosity_line = "Prefer detailed responses with concrete steps and examples."

    emoji_line = ""
    if emoji_pref == "off":
        emoji_line = "Avoid emojis unless the user uses them first."
    elif emoji_pref == "on":
        emoji_line = "Emojis are welcome if they match the tone."

    format_line = ""
    if format_pref == "structured":
        format_line = "Prefer structured formatting (short sections or bullets) when it helps clarity."
    elif format_pref == "freeform":
        format_line = "Prefer natural paragraphs over heavy bulleting unless requested."

    extras = " ".join([s for s in [verbosity_line, emoji_line, format_line] if s])
    return f"{base} {extras}".strip()


def _detect_response_mood(
    response: str,
    thinking: str = "",
    confidence: float = 0.7,
    contradiction_detected: bool = False,
) -> Dict[str, Any]:
    """
    Detect the mood/tone of a response for UI visualization.
    
    Returns:
        {
            "mood": "warm" | "intense" | "playful" | "curious" | "calm" | "uncertain",
            "intensity": 0.0-1.0,
            "thinking_depth": 0.0-1.0,
            "triggers": ["list", "of", "detected", "triggers"]
        }
    """
    response_lower = response.lower()
    thinking_lower = thinking.lower() if thinking else ""
    
    triggers = []
    mood = "calm"
    intensity = 0.3
    thinking_depth = min(1.0, len(thinking) / 2000) if thinking else 0.0
    
    # Warm/friendly indicators
    warm_words = ["happy", "glad", "great", "wonderful", "love", "enjoy", "excited", 
                  "welcome", "pleasure", "delighted", "awesome", "fantastic", "ðŸ˜Š", "ðŸŽ‰"]
    warm_count = sum(1 for w in warm_words if w in response_lower)
    
    # Playful/humor indicators
    playful_words = ["haha", "lol", "funny", "joke", "silly", "ðŸ˜„", "ðŸ˜‚", "ðŸ¤£", 
                     "quirky", "whimsical", "amusing", "teasing"]
    playful_count = sum(1 for w in playful_words if w in response_lower)
    
    # Intense/challenging indicators
    intense_words = ["important", "critical", "crucial", "significant", "challenge",
                     "complex", "difficult", "serious", "careful", "warning", "consider",
                     "however", "but", "actually", "contradiction", "conflict"]
    intense_count = sum(1 for w in intense_words if w in response_lower or w in thinking_lower)
    
    # Curious/questioning indicators
    curious_words = ["interesting", "wonder", "curious", "fascinating", "intriguing",
                     "hmm", "perhaps", "maybe", "what if", "ðŸ¤”"]
    curious_count = sum(1 for w in curious_words if w in response_lower or w in thinking_lower)
    
    # Uncertain indicators
    uncertain_words = ["unsure", "uncertain", "don't know", "not sure", "might be",
                       "possibly", "i think", "seems like", "could be"]
    uncertain_count = sum(1 for w in uncertain_words if w in response_lower)
    
    # Deep thinking indicators in thinking content
    deep_thinking_words = ["analyzing", "considering", "evaluating", "weighing",
                           "multiple", "factors", "implications", "reasoning",
                           "therefore", "because", "evidence", "conclusion"]
    deep_count = sum(1 for w in deep_thinking_words if w in thinking_lower)
    
    # Determine primary mood
    counts = {
        "warm": warm_count,
        "playful": playful_count,
        "intense": intense_count + (2 if contradiction_detected else 0),
        "curious": curious_count,
        "uncertain": uncertain_count,
    }
    
    max_mood = max(counts, key=counts.get)
    max_count = counts[max_mood]
    
    if max_count >= 2:
        mood = max_mood
        triggers.append(f"{mood}_keywords")
    
    # Adjust intensity based on various factors
    if contradiction_detected:
        intensity = max(intensity, 0.7)
        triggers.append("contradiction")
    
    if thinking_depth > 0.5:
        intensity = max(intensity, 0.5 + thinking_depth * 0.3)
        triggers.append("deep_thinking")
    
    if deep_count >= 3:
        intensity = max(intensity, 0.6)
        mood = "intense"
        triggers.append("complex_reasoning")
    
    if confidence < 0.5:
        mood = "uncertain"
        intensity = 0.4
        triggers.append("low_confidence")
    
    # Playful overrides if strong signal
    if playful_count >= 2:
        mood = "playful"
        intensity = min(0.6, intensity)
        
    # Warm overrides for very positive responses
    if warm_count >= 3:
        mood = "warm"
        intensity = max(0.4, min(0.7, intensity))
    
    return {
        "mood": mood,
        "intensity": round(min(1.0, intensity), 2),
        "thinking_depth": round(thinking_depth, 2),
        "triggers": triggers,
    }


_EXPAND_TRIGGERS = (
    "expand",
    "expand more",
    "explain more",
    "tell me more",
    "go deeper",
    "more detail",
    "more details",
    "elaborate",
    "continue",
)


def _user_requested_expansion(text: str) -> bool:
    t = (text or "").strip().lower()
    if not t:
        return False
    return any(t == trigger or t.startswith(trigger + " ") for trigger in _EXPAND_TRIGGERS)


def _get_verbosity_preference(thread_id: str, memory_system) -> Optional[str]:
    try:
        episodic_mgr = get_episodic_manager(memory_system=memory_system)
        ctx = episodic_mgr.get_user_context()
        prefs = ctx.get("preferences", {}) if isinstance(ctx, dict) else {}
        response_style = prefs.get("response_style", {}) if isinstance(prefs, dict) else {}
        verbosity = response_style.get("verbosity", {}) if isinstance(response_style, dict) else {}
        value = verbosity.get("value")
        if isinstance(value, str) and value.strip():
            return value.strip().lower()
    except Exception as e:
        logger.debug(f"[PREF] Failed to read verbosity preference for {thread_id}: {e}")
    return None


def _should_expand_response(
    question: str,
    response: str,
    reflection_result: Optional[ReflectionResult],
    verbosity_pref: Optional[str],
) -> Tuple[bool, Optional[str]]:
    if not response:
        return False, None
    if verbosity_pref == "concise":
        return False, None
    if _user_requested_expansion(question):
        return True, "user_requested"
    if reflection_result and reflection_result.suggested_action in ("refine", "re-query"):
        return True, f"reflection_{reflection_result.suggested_action}"
    if verbosity_pref == "verbose" and len(response) < 1400:
        return True, "preference_verbose"
    if len(response) < 360 and len(question or "") > 80:
        return True, "short_answer"
    return False, None


def _build_expansion_prompt(
    question: str,
    response: str,
    known_facts: str,
    reflection_result: Optional[ReflectionResult],
) -> str:
    parts = [
        "You are expanding a draft answer after a self-check.",
        "Rules:",
        "- Do not repeat the original answer verbatim.",
        "- Add missing details, examples, or concrete steps when useful.",
        "- If you are unsure, say what is uncertain instead of guessing.",
        "",
        f"Question:\n{question}",
        "",
        f"Draft answer:\n{response}",
    ]
    if known_facts:
        parts.append("")
        parts.append(f"Known facts:\n{known_facts}")
    if reflection_result:
        parts.append("")
        parts.append(
            f"Self-assessment: confidence={reflection_result.confidence_label}, "
            f"suggested_action={reflection_result.suggested_action}"
        )
    parts.append("")
    parts.append("Provide an expanded answer:")
    return "\n".join(parts)


def _generate_expansion(
    llm_client: Any,
    question: str,
    response: str,
    known_facts: str,
    style_profile: Optional[Dict[str, Any]],
    reflection_result: Optional[ReflectionResult],
    personality_profile: Optional[Dict[str, Any]] = None,
) -> Optional[str]:
    if not llm_client:
        return None
    style_instruction = _format_style_instruction(style_profile, personality_profile)
    system_lines = [
        "You are a careful assistant expanding a response after a self-check.",
        "Keep additions grounded in known facts. Avoid speculation.",
    ]
    if style_instruction:
        system_lines.append(style_instruction)
    system_prompt = " ".join(system_lines)
    prompt = _build_expansion_prompt(question, response, known_facts, reflection_result)
    expansion = llm_client.generate(prompt, system=system_prompt, max_tokens=420, temperature=0.4)
    if not isinstance(expansion, str):
        return None
    expansion = _strip_thinking_tags(expansion).strip()
    if not expansion or expansion.startswith("[Ollama error") or expansion.startswith("[Ollama connection error"):
        return None
    return expansion


def _chunk_text(text: str, chunk_size: int = 320) -> List[str]:
    if not text:
        return []
    return [text[i : i + chunk_size] for i in range(0, len(text), chunk_size)]


class ChatSendRequest(BaseModel):
    thread_id: str = Field(default="default", description="Client thread identifier")
    message: str = Field(min_length=1, description="User message")
    user_marked_important: bool = Field(default=False)
    mode: Optional[str] = Field(default=None, description="Optional reasoning mode")
    phase_mode: bool = Field(default=False, description="Emit phase events (analyze/plan/answer) in stream")
    channel: Optional[str] = Field(default=None, description="Inbound channel (telegram/web/api/etc)")
    origin: Optional[str] = Field(default=None, description="Provenance for the inbound message (URL, post id, message id)")
    authority: Optional[str] = Field(default=None, description="Optional authority override for governed memory writes")
    kind: Optional[str] = Field(default=None, description="Optional governed memory kind for inbound fact writes")
    actor_id: Optional[str] = Field(default=None, description="Channel actor/user identifier")
    channel_destination_id: Optional[str] = Field(default=None, description="Channel destination/chat identifier")
    meta_scope: Optional[str] = Field(default=None, description="Optional scope tag for channel/meta routing")


class ChatSendResponse(BaseModel):
    answer: str
    response_type: str
    gates_passed: bool
    gate_reason: Optional[str] = None
    session_id: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)
    xray: Optional[Dict[str, Any]] = Field(default=None, description="X-Ray mode: memory evidence and conflicts")


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
    authority: str = Field(default="confirmed")
    channel: str = Field(default="unknown")
    origin: Optional[str] = None
    kind: str = Field(default="observation")


class MemoryStoreRequest(BaseModel):
    thread_id: str = Field(default="default", description="Client thread identifier")
    text: str = Field(min_length=1, description="Memory text to persist")
    confidence: float = Field(default=0.95, ge=0.0, le=1.0)
    source: str = Field(default="user", description="Memory source enum value")
    context: Dict[str, Any] = Field(default_factory=dict)
    user_marked_important: bool = Field(default=False)
    contradiction_signal: float = Field(default=0.0, ge=0.0, le=1.0)
    authority: Optional[str] = Field(default=None)
    channel: Optional[str] = Field(default=None)
    origin: Optional[str] = Field(default=None)
    kind: Optional[str] = Field(default=None)


class MemoryStoreResponse(BaseModel):
    stored: bool
    memory: MemoryListItem
    fact_store_updated: bool = False
    contradiction_detected: bool = False
    contradiction_info: Optional[str] = None


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
    # Enhanced fields for UI
    contradiction_id: Optional[str] = None  # Alias for ledger_id
    slot: Optional[str] = None
    old_value: Optional[str] = None
    new_value: Optional[str] = None
    old_trust: Optional[float] = None
    new_trust: Optional[float] = None
    detected_at: Optional[float] = None  # Alias for timestamp
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
    next: Optional[ContradictionNextResponse] = None


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


class FactExtractionRequest(BaseModel):
    text: str = Field(min_length=1, description="Text to extract facts from")
    skip_llm: bool = Field(default=False, description="If true, only extract hard slots (faster)")


class ExtractedFactItem(BaseModel):
    slot: str
    value: str
    normalized: str
    tier: str  # "hard" or "open"
    source: str  # "regex" or "llm"
    confidence: Optional[float] = None


class FactExtractionResponse(BaseModel):
    text: str
    hard_facts: Dict[str, ExtractedFactItem]
    open_tuples: List[ExtractedFactItem]
    extraction_time: float
    methods_used: List[str]


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


# ============================================================================
# Auth models
# ============================================================================

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


def create_app() -> FastAPI:
    # NOTE: on_event("startup"/"shutdown") is deprecated in favor of lifespan.
    # Full migration deferred — startup references 10+ objects created mid-function.
    # Suppress the deprecation warning for now.
    import warnings
    warnings.filterwarnings("ignore", message=".*on_event is deprecated.*", category=DeprecationWarning)

    app = FastAPI(title="CRT API", version="3.0.0")
    app.state.runtime_data_root = str(get_runtime_data_root(create=True))

    runtime_cfg = get_runtime_config()
    reflection_cfg = (runtime_cfg.get("reflection") or {}) if isinstance(runtime_cfg, dict) else {}
    learned_cfg = (runtime_cfg.get("learned_suggestions") or {}) if isinstance(runtime_cfg, dict) else {}
    loop_cfg = (runtime_cfg.get("training_loop") or {}) if isinstance(runtime_cfg, dict) else {}
    jobs_cfg = (runtime_cfg.get("background_jobs") or {}) if isinstance(runtime_cfg, dict) else {}
    dnnt_cfg = (runtime_cfg.get("dnnt_retraining") or {}) if isinstance(runtime_cfg, dict) else {}
    agent_tool_policy_cfg = (
        (runtime_cfg.get("agent_tool_policy") or {}) if isinstance(runtime_cfg, dict) else {}
    )

    # Shared training loop (suggestion-only model). Stored in app.state for endpoints.
    training_loop = CRTTrainingLoop(
        repo_root=Path(__file__).resolve().parent,
        reflection_cfg=reflection_cfg,
        learned_cfg=learned_cfg,
        loop_cfg=loop_cfg,
    )
    app.state.training_loop = training_loop
    app.state.agent_tool_policy_config = dict(agent_tool_policy_cfg)
    app.state.agent_tool_policy_version = 1

    # Optional managed DNNT background retraining loop.
    dnnt_learning_cfg = BackgroundLearningConfig(
        output_dir=str(dnnt_cfg.get("output_dir") or "models/dnnt"),
        collected_examples_path=str(dnnt_cfg.get("collected_examples_path") or "data/dnnt_collected_training_data.jsonl"),
        collapse_trails_db_path=str(
            dnnt_cfg.get("collapse_trails_db_path")
            or dnnt_cfg.get("collapse_trails_path")
            or str(resolve_collapse_trails_db_path())
        ),
        active_learning_db_path=str(dnnt_cfg.get("active_learning_db_path") or str(resolve_active_learning_db_path())),
        state_path=str(dnnt_cfg.get("state_path") or "data/dnnt_background_state.json"),
        min_new_examples=int(dnnt_cfg.get("min_new_examples") or 24),
        max_examples_per_cycle=int(dnnt_cfg.get("max_examples_per_cycle") or dnnt_cfg.get("max_examples") or 512),
        max_steps_per_cycle=int(dnnt_cfg.get("max_steps_per_cycle") or 200),
        batch_size=int(dnnt_cfg.get("batch_size") or 8),
        learning_rate=float(dnnt_cfg.get("learning_rate") or 2e-4),
        poll_interval_sec=int(dnnt_cfg.get("poll_interval_sec") or 180),
    )
    dnnt_retraining_loop = DNNTBackgroundLoop(
        enabled=bool(dnnt_cfg.get("enabled", False)),
        poll_interval_seconds=float(dnnt_cfg.get("poll_interval_seconds") or 1800),
        config=dnnt_learning_cfg,
    )
    app.state.dnnt_retraining_loop = dnnt_retraining_loop

    # Optional: background jobs worker + idle scheduler.
    # Stored on app.state so endpoints can report status.
    root = Path(__file__).resolve().parent
    skills_db_path = str(resolve_runtime_path(str((runtime_cfg.get("skills") or {}).get("db_path") or resolve_skills_registry_db_path())))
    skills_managed_dir = str(resolve_runtime_dir(str((runtime_cfg.get("skills") or {}).get("managed_dir") or resolve_managed_skills_dir())))
    skill_source_roots = [
        str(root / ".agents" / "skills"),
        str(root / ".github" / "skills"),
    ]
    try:
        app.state.skill_registry = SkillRegistry(
            db_path=skills_db_path,
            managed_dir=skills_managed_dir,
            source_roots=skill_source_roots,
        )
        app.state.skill_registry.discover_skills()
        # Sync skill cache for services with stored credentials
        try:
            from personal_agent.task_agent import sync_skill_cache
            synced = sync_skill_cache()
            if synced:
                logger.info("[STARTUP] Cached skill files for: %s", synced)
        except Exception as e_sync:
            logger.warning("[STARTUP] Skill cache sync: %s", e_sync)
    except Exception as e:
        logger.warning(f"[STARTUP] Failed to initialize skill registry: {e}")
        app.state.skill_registry = None

    jobs_enabled = bool(jobs_cfg.get("enabled", False))
    jobs_db_path = str(resolve_runtime_path(str(jobs_cfg.get("jobs_db_path") or resolve_jobs_db_path())))
    jobs_artifacts_dir = str(resolve_runtime_dir(str(jobs_cfg.get("artifacts_dir") or resolve_jobs_artifacts_dir())))
    worker_interval = float(jobs_cfg.get("worker_interval_seconds") or 2)

    init_jobs_db(jobs_db_path)
    app.state.jobs_db_path = jobs_db_path
    app.state.jobs_artifacts_dir = jobs_artifacts_dir

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

    # Belief classifier (two-tap belief head on DNNT)
    try:
        from personal_agent.belief_classifier import init_belief_classifier
        _belief_clf = init_belief_classifier()
        app.state.belief_classifier = _belief_clf
    except Exception as _be:
        logger.warning("[BELIEF] Failed to init belief classifier: %s", _be)
        app.state.belief_classifier = None

    # Scheduled Tasks Loop (reminders, timed jobs, thoughts)
    scheduled_tasks_db_path = str(resolve_scheduled_tasks_db_path())
    init_scheduled_tasks_db(scheduled_tasks_db_path)
    
    # Get session DB for posting to Ledger
    _tasks_session_db = get_thread_session_db()
    
    # Callback for when a reminder is due
    def on_reminder_due(task: ScheduledTask):
        """Handle a due reminder — push directly to SSE stream."""
        try:
            from personal_agent.notifications import emit_generic_notification_sync
            reminder_text = str(task.payload.get("reminder_text") or "Reminder").strip()
            thread_id = _sanitize_thread_id(task.thread_id)
            original_time = str(task.payload.get("original_time_str") or "").strip()

            pushed = emit_generic_notification_sync(
                event_type="commitment_notification",
                content=reminder_text,
                metadata={
                    "task_id": task.task_id,
                    "thread_id": thread_id,
                    "reminder_text": reminder_text,
                    "original_time_str": original_time,
                    "scheduled_at": float(task.scheduled_at),
                    "category": "reminder",
                    "priority": "high",
                },
            )
            logger.info("[REMINDER] Fired: '%s' — pushed to %d SSE connection(s)", reminder_text, pushed)
        except Exception as e:
            logger.error(f"[REMINDER] Error handling reminder: {e}")
    # Callback for when a thought is due to be posted
    def on_thought_due(task: ScheduledTask):
        """Handle a due thought."""
        try:
            thought_content = task.payload.get("thought_content", "")
            thought_type = task.payload.get("thought_type", "scheduled")
            thread_id = task.thread_id
            logger.info(f"[THOUGHT] ðŸ’­ Thought for thread {thread_id}: {thought_content} (type: {thought_type})")
        except Exception as e:
            logger.error(f"[THOUGHT] Error handling thought: {e}")
    
    scheduled_tasks_loop = ScheduledTasksLoop(
        db_path=scheduled_tasks_db_path,
        check_interval=30.0,  # Check every 30 seconds
        enabled=True,
        on_reminder=on_reminder_due,
        on_thought=on_thought_due,
    )
    app.state.scheduled_tasks_loop = scheduled_tasks_loop
    app.state.scheduled_tasks_db_path = scheduled_tasks_db_path

    # Heartbeat scheduler (OpenClaw-style 24/7 proactive engagement)
    # Continuous reflection + personality + heartbeat loops (24/7, limited scope)
    session_db = get_thread_session_db()
    reflection_loop, personality_loop, journal_self_reply_loop, heartbeat_loop, contradiction_scan_loop, narrative_loop = build_loops(session_db)
    app.state.reflection_loop = reflection_loop
    app.state.personality_loop = personality_loop
    app.state.journal_self_reply_loop = journal_self_reply_loop
    app.state.heartbeat_loop = heartbeat_loop
    app.state.contradiction_scan_loop = contradiction_scan_loop
    app.state.narrative_loop = narrative_loop

    # CORS (dev-friendly). Configure via CRT_CORS_ORIGINS as comma-separated list or "*" for all.
    cors_env = os.getenv("CRT_CORS_ORIGINS", "http://localhost:5173,http://localhost:5174,http://127.0.0.1:5173,http://127.0.0.1:5174,app://aether")
    if cors_env.strip() == "*":
        origins = ["*"]
        # CORS spec forbids allow_credentials=True with allow_origins=["*"]
        allow_creds = False
    else:
        origins = [o.strip() for o in cors_env.split(",") if o.strip()]
        allow_creds = True
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins if origins else ["*"],
        allow_credentials=allow_creds,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type", "Accept"],
    )

    # Cache one CRT engine per thread (isolated DBs per thread).
    _engines_lock = threading.Lock()
    engines: Dict[str, CRTEnhancedRAG] = {}
    _turn_lock = threading.Lock()
    turn_counters: Dict[str, int] = {}  # Track turn numbers per thread

    docs_dir = root / "docs"
    doc_map: Dict[str, Dict[str, Any]] = {
        # Landing page.
        "index": {"title": "Documentation Index", "kind": "overview", "path": docs_dir / "INDEX.md"},
        # Getting started.
        "quick_start": {"title": "Quick Start Guide", "kind": "start", "path": docs_dir / "QUICK_START.md"},
        "requirements": {"title": "Requirements & Dependencies", "kind": "start", "path": docs_dir / "REQUIREMENTS.md"},
        "configuration": {"title": "Configuration & Environment Variables", "kind": "start", "path": docs_dir / "CONFIGURATION.md"},
        "crt_whitepaper": {"title": "CRT Whitepaper", "kind": "start", "path": docs_dir / "CRT_WHITE_PAPER.md"},
        # Core architecture.
        "three_laws": {"title": "The Three Laws of CRT", "kind": "core", "path": docs_dir / "THREE_LAWS.md"},
        "sys_architecture": {"title": "System Architecture", "kind": "core", "path": docs_dir / "ARCHITECTURE.md"},
        "request_lifecycle": {"title": "How a Request Flows Through CRT", "kind": "core", "path": docs_dir / "REQUEST_LIFECYCLE.md"},
        "what_makes_different": {"title": "What Makes CRT/Aether Different", "kind": "core", "path": docs_dir / "WHAT_MAKES_CRT_DIFFERENT.md"},
        # Memory & trust.
        "memory_lifecycle": {"title": "Memory Lifecycle", "kind": "memory", "path": docs_dir / "MEMORY_LIFECYCLE.md"},
        "compression": {"title": "Adaptive Semantic Compression", "kind": "memory", "path": docs_dir / "COMPRESSION.md"},
        "slot_discovery": {"title": "Dynamic Slot Discovery", "kind": "memory", "path": docs_dir / "SLOT_DISCOVERY.md"},
        "belief_synthesis": {"title": "Belief Synthesis & Volatility", "kind": "memory", "path": docs_dir / "BELIEF_SYNTHESIS.md"},
        # Intelligence & routing.
        "semantic_intent_router": {"title": "Semantic Intent Router", "kind": "intelligence", "path": docs_dir / "SEMANTIC_INTENT_ROUTER.md"},
        "task_triage": {"title": "Task Triage & Acknowledgment", "kind": "intelligence", "path": docs_dir / "TASK_TRIAGE.md"},
        "sub_agents": {"title": "Sub-Agents & Orchestration", "kind": "intelligence", "path": docs_dir / "SUB_AGENTS.md"},
        "intuition_check": {"title": "Intuition Check", "kind": "intelligence", "path": docs_dir / "INTUITION_CHECK.md"},
        "cloud_routing": {"title": "3-Tier Cloud Routing", "kind": "intelligence", "path": docs_dir / "CLOUD_ROUTING.md"},
        "self_model": {"title": "Self-Model & Reflection", "kind": "intelligence", "path": docs_dir / "SELF_MODEL.md"},
        # Agent capabilities.
        "desktop_control": {"title": "Desktop Control", "kind": "capabilities", "path": docs_dir / "DESKTOP_CONTROL.md"},
        "browser_control": {"title": "Browser Control", "kind": "capabilities", "path": docs_dir / "BROWSER_CONTROL.md"},
        "action_execution": {"title": "Action Execution Layer", "kind": "capabilities", "path": docs_dir / "ACTION_EXECUTION.md"},
        "commitments": {"title": "Commitments & Scheduling", "kind": "capabilities", "path": docs_dir / "COMMITMENTS.md"},
        "system_heartbeat": {"title": "System Info & Heartbeat", "kind": "capabilities", "path": docs_dir / "SYSTEM_HEARTBEAT.md"},
        "skill_system": {"title": "Skill System", "kind": "capabilities", "path": docs_dir / "SKILL_SYSTEM.md"},
        # Behavior & proactivity.
        "heartbeat_loop": {"title": "Heartbeat Loop", "kind": "behavior", "path": docs_dir / "HEARTBEAT_LOOP.md"},
        "greetings_warnings": {"title": "Greetings, Warnings & Response Behavior", "kind": "behavior", "path": docs_dir / "GREETINGS_WARNINGS.md"},
        # Settings & controls.
        "settings": {"title": "Settings Page", "kind": "settings", "path": docs_dir / "SETTINGS.md"},
        # Training & verification.
        "vilt_writeup": {"title": "ViLT Technical Writeup", "kind": "training", "path": docs_dir / "VILT_TECHNICAL_WRITEUP.md"},
        # Testing & quality.
        "testing_patterns": {"title": "Testing Patterns", "kind": "testing", "path": docs_dir / "TESTING_PATTERNS.md"},
        "testing_methods": {"title": "Testing Methods", "kind": "testing", "path": docs_dir / "TESTING_METHODS.md"},
        "adversarial_stress_test": {"title": "Adversarial Stress Test Report", "kind": "testing", "path": docs_dir / "ADVERSARIAL_STRESS_TEST_REPORT.md"},
        "anti_patterns": {"title": "What NOT to Do", "kind": "testing", "path": docs_dir / "ANTI_PATTERNS.md"},
        # Frozen specs (v0.9.0, Feb 2026).
        "api_contract": {"title": "API Contract (v0.9.0)", "kind": "spec", "path": docs_dir / "specs" / "API_CONTRACT.md"},
        "architecture_spec": {"title": "Architecture Spec", "kind": "spec", "path": docs_dir / "specs" / "ARCHITECTURE.md"},
        "freeze_manifest": {"title": "Freeze Manifest", "kind": "spec", "path": docs_dir / "specs" / "FREEZE_MANIFEST.md"},
        "innovation_pillars": {"title": "Innovation Pillars", "kind": "spec", "path": docs_dir / "specs" / "INNOVATION_PILLARS.md"},
        # Project meta.
        "changelog": {"title": "Changelog", "kind": "meta", "path": root / "CHANGELOG.md"},
        "roadmap": {"title": "Roadmap", "kind": "meta", "path": root / "ROADMAP.md"},
    }

    # Initialize shared LLM client for all threads (lazy initialization)
    _llm_client: Optional[UnifiedLLMClient] = None
    _llm_lock = threading.Lock()
    _default_router_model = str(
        os.getenv("CRT_OLLAMA_MODEL")
        or ((runtime_cfg.get("generation_stack") or {}).get("local") or {}).get("default_model")
        or "qwen2.5-coder:14b"
    ).strip() or "qwen2.5-coder:14b"
    model_router = ModelRouter(default_model=_default_router_model, runtime_config=runtime_cfg)

    def _llm_feature_enabled() -> bool:
        raw = str(os.getenv("CRT_ENABLE_LLM", "true") or "").strip().lower()
        return raw not in {"0", "false", "no", "off"}
    
    def get_llm_client() -> Optional[UnifiedLLMClient]:
        """Get or create the shared primary LLM client."""
        nonlocal _llm_client
        
        if not _llm_feature_enabled():
            logger.debug("[API] LLM extraction disabled (CRT_ENABLE_LLM=false)")
            return None

        with _llm_lock:
            if _llm_client is None:
                try:
                    logger.info("[API] Initializing primary LLM client...")
                    _llm_client = create_llm_client(runtime_cfg)
                    if _llm_client is not None:
                        logger.info(
                            "[API] Primary LLM initialized (product_mode=%s cloud_available=%s local_model=%s)",
                            getattr(_llm_client, "product_mode", "unknown"),
                            getattr(_llm_client, "cloud_available", False),
                            getattr(_llm_client, "model", ""),
                        )
                    else:
                        logger.warning("[API] No LLM client available after initialization")
                except Exception as e:
                    logger.warning(f"[API] Failed to initialize primary LLM client: {e}")
                    logger.warning("[API] Falling back to regex-only extraction")
                    _llm_client = None
        return _llm_client
    
    # Shared memory mode: All threads use same databases (optional)
    _shared_memory_enabled = os.getenv("CRT_SHARED_MEMORY", "false").lower() == "true"
    
    def get_engine(thread_id: str) -> CRTEnhancedRAG:
        tid = _sanitize_thread_id(thread_id)
        with _engines_lock:
            engine = engines.get(tid)
            if engine is not None:
                return engine

            # Hold the lock during creation to prevent double-init race.
            # This means the first request for a thread blocks others, but
            # subsequent requests hit the cache and return immediately.

            # Use shared DBs or per-thread isolation
            memory_db = str(resolve_memory_db_path(tid, shared=_shared_memory_enabled))
            ledger_db = str(resolve_ledger_db_path(tid, shared=_shared_memory_enabled))
            print("[ENGINE] Thread %s -> memory=%s" % (tid, memory_db))

            # Initialize engine and inject LLM client for hybrid extraction
            llm_client = get_llm_client()
            engine = CRTEnhancedRAG(memory_db=memory_db, ledger_db=ledger_db, llm_client=llm_client)
            setattr(engine, "thread_id", tid)
            try:
                engine.ledger.default_thread_id = tid
            except Exception:
                pass

            # Enable LLM extraction in FactStore if client is available
            if llm_client is not None and hasattr(engine, 'memory') and hasattr(engine.memory, 'set_llm_client'):
                try:
                    engine.memory.set_llm_client(llm_client)
                    logger.info(f"[API] Enabled hybrid LLM extraction for thread {tid}")
                except Exception as e:
                    logger.warning(f"[API] Failed to enable LLM extraction for thread {tid}: {e}")

            # Seed self-knowledge into this thread's memory (idempotent)
            try:
                from scripts.seed_self_knowledge import seed_self_knowledge
                seed_self_knowledge(engine.memory)
            except Exception as e:
                logger.debug(f"[API] Self-knowledge seed for {tid}: {e}")

            engines[tid] = engine

        with _turn_lock:
            turn_counters[tid] = 0  # Initialize turn counter
        return engine
    
    def get_turn_number(thread_id: str) -> int:
        """Get current turn number for thread."""
        tid = _sanitize_thread_id(thread_id)
        with _turn_lock:
            return turn_counters.get(tid, 0)
    
    def increment_turn(thread_id: str) -> int:
        """Increment and return new turn number."""
        tid = _sanitize_thread_id(thread_id)
        with _turn_lock:
            turn_counters[tid] = turn_counters.get(tid, 0) + 1
            return turn_counters[tid]

    def _thread_db_paths(thread_id: str) -> tuple[str, str]:
        tid = _sanitize_thread_id(thread_id)
        memory_db = str(resolve_memory_db_path(tid, shared=_shared_memory_enabled))
        ledger_db = str(resolve_ledger_db_path(tid, shared=_shared_memory_enabled))
        return memory_db, ledger_db

    collapse_logger = get_collapse_trail_logger()

    def _log_collapse_trail(
        *,
        thread_id: str,
        query: str,
        answer: str,
        result: Optional[Dict[str, Any]],
        stage: str,
        mode: Optional[str] = None,
        extra: Optional[Dict[str, Any]] = None,
    ) -> Optional[str]:
        try:
            payload = dict(result or {})
            payload.setdefault("answer", answer)
            return collapse_logger.log_trail(
                thread_id=_sanitize_thread_id(thread_id),
                query=query,
                answer=answer,
                result=payload,
                stage=stage,
                mode=mode,
                extra=extra,
            )
        except Exception as e:
            logger.debug(f"[COLLAPSE_TRAIL] Failed to log trail: {e}")
            return None

    # Expose closure-scoped helpers on app.state so modular route files can
    # access them via ``request.app.state.*`` without importing crt_api.
    app.state.get_engine = get_engine
    app.state.get_llm_client = get_llm_client
    app.state.get_turn_number = get_turn_number
    app.state.increment_turn = increment_turn
    app.state.thread_db_paths = _thread_db_paths
    app.state.doc_map = doc_map
    app.state.collapse_logger = collapse_logger
    app.state.log_collapse_trail = _log_collapse_trail
    app.state.engines = engines
    app.state.turn_counters = turn_counters
    app.state.model_router = model_router

    # Route modules (strangler pattern): endpoints move out of this file incrementally.
    register_routes(app)

    # ── SSE notification stream (Sprint 4 — commitment notifications) ────
    @app.get("/api/notifications/stream")
    async def notification_stream(request: Request):
        """SSE endpoint for real-time commitment notifications.

        Clients connect and receive commitment_notification events as they fire.
        """
        import asyncio as _asyncio
        from personal_agent.notifications import register_sse_connection, unregister_sse_connection

        queue = register_sse_connection("default")

        async def _event_generator():
            try:
                # Send keepalive immediately
                yield f"data: {json.dumps({'type': 'connected', 'content': 'notification stream active'})}\n\n"
                while True:
                    if await request.is_disconnected():
                        break
                    try:
                        event = await _asyncio.wait_for(queue.get(), timeout=30.0)
                        yield f"data: {json.dumps(event)}\n\n"
                    except _asyncio.TimeoutError:
                        # Send keepalive
                        yield f"data: {json.dumps({'type': 'keepalive', 'content': ''})}\n\n"
            finally:
                unregister_sse_connection(queue, "default")

        return StreamingResponse(
            _event_generator(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            },
        )

    @app.on_event("startup")
    def _startup() -> None:
        # Initialize auth database
        auth_module.ensure_db_initialized()

        # Pre-load embedding model to avoid timeout on first request
        logger.info("[STARTUP] Pre-loading embedding model...")
        try:
            from personal_agent.crt_core import encode_vector
            # Trigger model load with dummy text
            _ = encode_vector("test")
            logger.info("[STARTUP] âœ“ Embedding model loaded")
        except Exception as e:
            logger.warning(f"[STARTUP] Could not pre-load embedding model: {e}")
        
        # Pre-flight: verify Ollama is running before attempting model load
        _ollama_available = False
        try:
            import requests as _req
            from personal_agent.ollama_config import resolve_ollama_base_url
            _ollama_url = resolve_ollama_base_url()
            _resp = _req.get(f"{_ollama_url}/api/tags", timeout=3)
            if _resp.status_code == 200:
                _models = [m.get("name", "") for m in (_resp.json() or {}).get("models", [])]
                _ollama_available = True
                logger.info("[STARTUP] Ollama is running (%d models available)", len(_models))
                print(f"[STARTUP] Ollama OK: {len(_models)} models loaded")
            else:
                logger.warning("[STARTUP] Ollama responded with HTTP %d", _resp.status_code)
                print("[STARTUP] WARNING: Ollama responded but returned an error")
        except Exception as e:
            logger.warning("[STARTUP] Ollama is NOT running at %s (%s)", _ollama_url, e)
            print(f"[STARTUP] WARNING: Ollama is NOT running. Local LLM will be unavailable. Start with: ollama serve")

        # Pre-warm Ollama models so first request doesn't cold-load.
        # If a dedicated intent model is set, warm THAT instead of the heavy
        # generation model (they compete for VRAM on limited hardware).
        if _ollama_available:
            try:
                import ollama as _ollama_mod
                import threading as _threading
                # Intent model pre-warming removed — Layer 4 epistemic routing
                # handles routing via feature extraction, no LLM call needed.
                _gen_model = os.getenv("CRT_OLLAMA_MODEL") or "qwen3:14b"
                _warm_model = _gen_model or "qwen3:14b"
                print(f"[STARTUP] Pre-warming Ollama model: {_warm_model}")
                _ollama_mod.generate(model=_warm_model, prompt="", keep_alive="24h")
                print(f"[STARTUP] Ollama model {_warm_model} loaded into VRAM")
            except Exception as e:
                logger.warning("[STARTUP] Could not pre-warm Ollama model: %s", e)
                print(f"[STARTUP] WARNING: Ollama running but model pre-warm failed: {e}")
        else:
            logger.info("[STARTUP] Skipping Ollama pre-warm (not available)")

        # Start the (optional) training loop.
        try:
            training_loop.start()
            logger.info("[STARTUP] Training loop started")
        except Exception as e:
            logger.warning(f"[STARTUP] Failed to start training loop: {e}")

        try:
            jobs_worker.start()
            logger.info("[STARTUP] Jobs worker started")
        except Exception as e:
            logger.warning(f"[STARTUP] Failed to start jobs worker: {e}")

        try:
            idle_scheduler.start()
            logger.info("[STARTUP] Idle scheduler started")
        except Exception as e:
            logger.warning(f"[STARTUP] Failed to start idle scheduler: {e}")

        try:
            app.state.scheduled_tasks_loop.start()
            logger.info("[STARTUP] Scheduled tasks loop started")
        except Exception as e:
            logger.warning(f"[STARTUP] Failed to start scheduled tasks loop: {e}")

        try:
            app.state.dnnt_retraining_loop.start()
            logger.info("[STARTUP] DNNT retraining loop started")
        except Exception as e:
            logger.warning(f"[STARTUP] Failed to start DNNT retraining loop: {e}")

        try:
            app.state.reflection_loop.start()
            logger.info("[STARTUP] Reflection loop started")
        except Exception as e:
            logger.warning(f"[STARTUP] Failed to start reflection loop: {e}")

        try:
            app.state.personality_loop.start()
            logger.info("[STARTUP] Personality loop started")
        except Exception as e:
            logger.warning(f"[STARTUP] Failed to start personality loop: {e}")

        try:
            app.state.journal_self_reply_loop.start()
            logger.info("[STARTUP] Journal self-reply loop started")
        except Exception as e:
            logger.warning(f"[STARTUP] Failed to start journal self-reply loop: {e}")

        try:
            app.state.heartbeat_loop.start()
            logger.info("[STARTUP] Heartbeat loop started")
        except Exception as e:
            logger.warning(f"[STARTUP] Failed to start heartbeat loop: {e}")

        try:
            app.state.narrative_loop.start()
            logger.info("[STARTUP] Narrative synthesis loop started")
        except Exception as e:
            logger.warning(f"[STARTUP] Failed to start narrative synthesis loop: {e}")

        # Seed self-knowledge (idempotent â€” skips facts that already exist)
        try:
            from scripts.seed_self_knowledge import seed_self_knowledge
            thread_dbs = [str(p) for p in iter_existing_memory_dbs(include_shared=True)]
            total_seeded = 0
            for db_p in thread_dbs:
                try:
                    from personal_agent.crt_memory import CRTMemorySystem
                    from personal_agent.crt_core import CRTConfig
                    ms = CRTMemorySystem(db_p, CRTConfig())
                    c = seed_self_knowledge(ms)
                    total_seeded += c
                except Exception as e:
                    logger.warning(f"[STARTUP] Failed to seed {db_p}: {e}")
            if total_seeded:
                logger.info(f"[STARTUP] Seeded {total_seeded} self-knowledge memories across {len(thread_dbs)} DBs")
            else:
                logger.info(f"[STARTUP] Self-knowledge already seeded in {len(thread_dbs)} DBs")
        except Exception as e:
            logger.warning(f"[STARTUP] Failed to seed self-knowledge: {e}")

        # Initialize cloud feature service (optional — degrades gracefully)
        try:
            from personal_agent.cloud_features import init_cloud_feature_service
            _cloud_openai = None
            _cloud_cookie = None
            _oai_key = os.getenv("OPENAI_API_KEY", "").strip()
            if _oai_key:
                from personal_agent.litellm_client import OpenAICompatibleClient
                _cloud_openai = OpenAICompatibleClient(
                    model="gpt-4o-mini",
                    api_key_env="OPENAI_API_KEY",
                    timeout_seconds=15.0,
                )
            try:
                from tests.cloud_providers.providers import ClaudeCliProvider
                _cli_provider = ClaudeCliProvider()
                _cli_avail = _cli_provider.is_available()
                print(f"[STARTUP] ClaudeCliProvider available={_cli_avail}, bin={_cli_provider._brain._bin}")
                if _cli_avail:
                    _cloud_cookie = _cli_provider
                else:
                    print("[STARTUP] ClaudeCliProvider not available, falling back to CookieProvider")
                    _claude_cookie = os.getenv("CLAUDE_SESSION_COOKIE", "").strip()
                    if _claude_cookie:
                        from tests.cloud_providers.providers import CookieProvider
                        _cloud_cookie = CookieProvider()
            except Exception as _cli_err:
                print(f"[STARTUP] ClaudeCliProvider failed: {_cli_err}, trying CookieProvider")
                try:
                    from tests.cloud_providers.providers import CookieProvider
                    _cloud_cookie = CookieProvider()
                except Exception as _cookie_err:
                    print(f"[STARTUP] CookieProvider not available: {_cookie_err}")
            init_cloud_feature_service(
                openai_client=_cloud_openai,
                cookie_session=_cloud_cookie,
            )
            print(f"[STARTUP] Cloud feature service initialized (openai={_cloud_openai is not None}, cookie={_cloud_cookie is not None}, key_len={len(_oai_key)})")
        except Exception as e:
            print(f"[STARTUP] Cloud feature service not initialized (non-fatal): {e}")

        # Schedule periodic session cleanup (every 6 hours)
        def _session_cleanup_worker():
            while True:
                try:
                    time.sleep(6 * 3600)
                    removed = auth_module.cleanup_expired_sessions()
                    if removed:
                        logger.info(f"[CLEANUP] Purged {removed} expired sessions")
                except Exception as e:
                    logger.warning(f"[CLEANUP] Session cleanup error: {e}")

        cleanup_thread = threading.Thread(target=_session_cleanup_worker, daemon=True, name="session-cleanup")
        cleanup_thread.start()

    @app.on_event("shutdown")
    def _shutdown() -> None:
        try:
            training_loop.stop()
            logger.info("[SHUTDOWN] Training loop stopped")
        except Exception as e:
            logger.warning(f"[SHUTDOWN] Error stopping training loop: {e}")

        try:
            idle_scheduler.stop()
            logger.info("[SHUTDOWN] Idle scheduler stopped")
        except Exception as e:
            logger.warning(f"[SHUTDOWN] Error stopping idle scheduler: {e}")

        try:
            app.state.scheduled_tasks_loop.stop()
            logger.info("[SHUTDOWN] Scheduled tasks loop stopped")
        except Exception as e:
            logger.warning(f"[SHUTDOWN] Error stopping scheduled tasks: {e}")

        try:
            app.state.dnnt_retraining_loop.stop()
            logger.info("[SHUTDOWN] DNNT retraining loop stopped")
        except Exception as e:
            logger.warning(f"[SHUTDOWN] Error stopping DNNT retraining loop: {e}")

        try:
            jobs_worker.stop()
            logger.info("[SHUTDOWN] Jobs worker stopped")
        except Exception as e:
            logger.warning(f"[SHUTDOWN] Error stopping jobs worker: {e}")

        try:
            app.state.reflection_loop.stop()
            logger.info("[SHUTDOWN] Reflection loop stopped")
        except Exception as e:
            logger.warning(f"[SHUTDOWN] Error stopping reflection loop: {e}")

        try:
            app.state.personality_loop.stop()
            logger.info("[SHUTDOWN] Personality loop stopped")
        except Exception as e:
            logger.warning(f"[SHUTDOWN] Error stopping personality loop: {e}")

        try:
            app.state.journal_self_reply_loop.stop()
            logger.info("[SHUTDOWN] Journal self-reply loop stopped")
        except Exception as e:
            logger.warning(f"[SHUTDOWN] Error stopping journal loop: {e}")

        try:
            app.state.heartbeat_loop.stop()
            logger.info("[SHUTDOWN] Heartbeat loop stopped")
        except Exception as e:
            logger.warning(f"[SHUTDOWN] Error stopping heartbeat loop: {e}")

    # --- Endpoints extracted to routes/ ---
    # See routes/{module}.py for route handlers.

    # ── Serve frontend dist (for Electron production mode) ─────────────
    # Mounted LAST so /api/* routes take priority over the catch-all.
    _frontend_dist = root / "frontend" / "dist"
    if _frontend_dist.is_dir():
        from fastapi.staticfiles import StaticFiles
        from fastapi.responses import FileResponse

        # Serve static assets (JS, CSS, images)
        app.mount("/assets", StaticFiles(directory=str(_frontend_dist / "assets")), name="frontend-assets")

        # Catch-all: serve index.html for SPA routing (must be after all API routes)
        @app.get("/{full_path:path}", include_in_schema=False)
        async def _serve_spa(full_path: str):
            """Serve the React SPA for any non-API route."""
            # Don't intercept API or known backend paths
            if full_path.startswith(("api/", "health", "docs", "openapi")):
                raise HTTPException(status_code=404)
            file_path = _frontend_dist / full_path
            if file_path.is_file():
                return FileResponse(str(file_path))
            return FileResponse(str(_frontend_dist / "index.html"))

    return app


app = create_app()


if __name__ == "__main__":
    import logging as _logging
    import uvicorn

    # -- Suppress /health from access logs -------------------------
    # Health checks fire every few seconds from Electron + frontend.
    # Without this filter they drown out useful pipeline logs.
    class _HealthFilter(_logging.Filter):
        def filter(self, record: _logging.LogRecord) -> bool:
            msg = record.getMessage()
            if '"GET /health HTTP' in msg:
                return False
            return True

    _logging.getLogger("uvicorn.access").addFilter(_HealthFilter())

    # Default to localhost -- set CRT_HOST=0.0.0.0 only behind a reverse proxy
    host = os.getenv("CRT_HOST", "127.0.0.1")
    port = int(os.getenv("PORT", "8000"))
    uvicorn.run(app, host=host, port=port)



