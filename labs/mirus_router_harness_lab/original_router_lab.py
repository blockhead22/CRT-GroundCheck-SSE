"""Mirus harness lab built around the original CRT LLM intent router.

This is intentionally a lab, not live Aether wiring. It reuses the old
LLMIntentRouter and ToolDefinition schema path with a small Mirus-flavored
tool list so we can test whether model-assisted tool discovery can catch
multi-fact turns better than one-slot deterministic extraction.
"""

from __future__ import annotations

import argparse
import json
import re
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional
from urllib.request import Request, urlopen

from personal_agent.llm_intent_router import LLMIntentRouter
from personal_agent.tool_registry import ToolDefinition, ToolParam


LAB_ROOT = Path(__file__).resolve().parent
RESULTS_DIR = LAB_ROOT / "results"
DEFAULT_CASE_PACK_PATH = LAB_ROOT / "mirus_governed_discovery_cases.json"


@dataclass(frozen=True)
class HarnessCase:
    case_id: str
    prompt: str
    expected_intent: str
    history: Optional[List[Dict[str, str]]] = None
    min_candidates: int = 0
    required_candidate_slots: tuple[str, ...] = ()
    require_review_only: bool = False


@dataclass
class HarnessResult:
    case_id: str
    prompt: str
    route: str
    intent_type: str
    confidence: float
    source: str
    reason: str
    slots: Dict[str, Any]
    passed: bool
    expected_intent: str
    quality_flags: List[str]
    repairs: List[str]
    logic_graph: Dict[str, Any]


@dataclass(frozen=True)
class FrontPacket:
    preferred_intent: Optional[str]
    pending_slot: Optional[str]
    candidate_hints: tuple[str, ...]
    reasons: tuple[str, ...]


def build_mirus_tool_definitions() -> List[ToolDefinition]:
    """Return lab tools using the original ToolDefinition contract."""
    return [
        ToolDefinition(
            name="mirus_extract_candidates",
            description=(
                "Extract review-only Mirus memory, relation, project, or support "
                "candidates from the user turn. Use this when the user provides "
                "new personal/project facts, reasons, corrections, or multiple "
                "related facts. This tool never writes memory."
            ),
            parameters=[
                ToolParam(
                    "payload",
                    "object",
                    (
                        "Object containing candidates. Expected shape: "
                        "{candidates:[{kind, slot, value, reason, confidence, "
                        "source_boundary, memory_write_allowed}]}"
                    ),
                    required=True,
                ),
            ],
            access_layer=1,
            checkpoint_tier="none",
            intent_type="mirus_candidate_extract",
            synthesis_mode="never",
            examples=[
                "My favorite flowers are marigolds because they are orange.",
                "I like the Milwaukee Brewers. The Brewers are my favorite team.",
                "They are both orange.",
            ],
        ),
        ToolDefinition(
            name="gpt_log_search",
            description=(
                "Search bounded GPT/archive logs as historical evidence. Results "
                "are archive evidence only, not confirmed memory."
            ),
            parameters=[
                ToolParam("query", "string", "Archive search query", required=True),
                ToolParam("top_k", "integer", "Maximum archive hits", required=False, default=5),
            ],
            access_layer=2,
            checkpoint_tier="none",
            intent_type="archive_search",
            synthesis_mode="smart",
            examples=[
                "search my gpt logs for CRT concepts",
                "use my old chats to find medical history evidence",
                "check the GPT archive for what held me back",
            ],
        ),
        ToolDefinition(
            name="project_context_search",
            description=(
                "Search current project context or project documents for bounded "
                "evidence about a named project, feature, place, or code area."
            ),
            parameters=[
                ToolParam("query", "string", "Project search query", required=True),
                ToolParam("project", "string", "Optional project name", required=False),
            ],
            access_layer=2,
            checkpoint_tier="none",
            intent_type="project_context_search",
            synthesis_mode="smart",
            examples=[
                "what is my state parks project",
                "what is the history on Mill Bluff",
                "why is Mill Bluff important to the state parks project",
            ],
        ),
        ToolDefinition(
            name="memory_recall",
            description="Recall confirmed governed memory for user facts.",
            parameters=[
                ToolParam("query", "string", "Memory query", required=True),
            ],
            access_layer=1,
            checkpoint_tier="none",
            intent_type="broad_recall",
            synthesis_mode="smart",
            examples=[
                "what is my favorite color",
                "what do you know about me",
                "who do I work for",
            ],
        ),
    ]


def build_mirus_tool_schemas() -> List[Dict[str, Any]]:
    return [tool.to_llm_schema() for tool in build_mirus_tool_definitions()]


class ScriptedToolCallingClient:
    """Deterministic stand-in for a small tool-calling model.

    The lab goal is not to make another regex router. It is to exercise the
    original LLMIntentRouter parse and tool-call contract without requiring a
    live local model in CI. A live client can be swapped in later because the
    harness only depends on chat_with_tools(...).
    """

    def __init__(self) -> None:
        self.calls: List[Dict[str, Any]] = []

    def chat_with_tools(
        self,
        messages: List[Dict[str, str]],
        tools: List[Dict[str, Any]],
        **_: Any,
    ) -> Dict[str, Any]:
        user_message = messages[-1]["content"]
        normalized = user_message.lower()
        available = {
            schema.get("function", {}).get("name")
            for schema in tools
            if schema.get("type") == "function"
        }
        self.calls.append({"message": user_message, "available": sorted(available)})

        if "gpt log" in normalized or "gpt archive" in normalized or "old chat" in normalized:
            return _tool_call("gpt_log_search", {"query": user_message, "top_k": 5})

        if "mill bluff" in normalized or "state parks project" in normalized:
            return _tool_call(
                "project_context_search",
                {"query": user_message, "project": "wisconsin-state-parks-map"},
            )

        pending = _history_mentions_pending_favorite(messages)
        if _looks_like_fact_update(normalized) or pending:
            candidates = _extract_review_candidates(user_message, pending_slot=pending)
            if candidates:
                return _tool_call(
                    "mirus_extract_candidates",
                    {
                        "payload": {
                            "candidates": candidates,
                            "source_boundary": "current_turn_or_recent_turns",
                            "memory_write_allowed": False,
                        }
                    },
                )

        if "favorite" in normalized or "what do you know about me" in normalized:
            return _tool_call("memory_recall", {"query": user_message})

        return {"tool_calls": [], "content": "No tool needed.", "used_tools": False}


class OllamaToolCallingClient:
    """Lab-only Ollama adapter for the old router's chat_with_tools contract."""

    def __init__(
        self,
        *,
        model: str = "qwen2.5:7b-instruct",
        base_url: str = "http://127.0.0.1:11434",
        timeout: int = 120,
    ) -> None:
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.calls: List[Dict[str, Any]] = []

    def chat_with_tools(
        self,
        messages: List[Dict[str, str]],
        tools: List[Dict[str, Any]],
        **kwargs: Any,
    ) -> Dict[str, Any]:
        payload: Dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "stream": False,
            "tools": tools,
            "options": {
                "temperature": float(kwargs.get("temperature", 0.0)),
                "num_predict": int(kwargs.get("max_tokens", 500)),
            },
        }
        if "qwen3" in self.model.lower():
            payload["think"] = False

        started = time.time()
        try:
            req = Request(
                f"{self.base_url}/api/chat",
                data=json.dumps(payload).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urlopen(req, timeout=self.timeout) as response:
                data = json.loads(response.read().decode("utf-8"))
        except Exception as exc:  # pragma: no cover - live-only path
            return {"tool_calls": [], "content": "", "used_tools": False, "error": str(exc)}

        elapsed_ms = int((time.time() - started) * 1000)
        message = data.get("message") or {}
        content = str(message.get("content") or "")
        tool_calls = _normalize_ollama_tool_calls(message.get("tool_calls") or [])
        self.calls.append(
            {
                "message": messages[-1].get("content", ""),
                "elapsed_ms": elapsed_ms,
                "tool_calls": tool_calls,
                "content_preview": content[:160],
            }
        )
        return {"tool_calls": tool_calls, "content": content, "used_tools": bool(tool_calls)}


def _normalize_ollama_tool_calls(raw_calls: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    normalized: List[Dict[str, Any]] = []
    for call in raw_calls:
        function = call.get("function") or {}
        name = str(function.get("name") or call.get("name") or "").strip()
        arguments = function.get("arguments")
        if arguments is None:
            arguments = call.get("arguments") or {}
        if isinstance(arguments, str):
            try:
                arguments = json.loads(arguments)
            except json.JSONDecodeError:
                arguments = {"raw_arguments": arguments}
        if name:
            normalized.append({"name": name, "arguments": arguments if isinstance(arguments, dict) else {}})
    return normalized


def _tool_call(name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
    return {"tool_calls": [{"name": name, "arguments": arguments}], "content": "", "used_tools": True}


def build_front_packet(prompt: str, history: Optional[List[Dict[str, str]]] = None) -> FrontPacket:
    """Mirus-side prepass: cheap task-shape packet before the model routes.

    This is not a memory write and not truth authority. It is an attention
    packet: what kind of turn does governance suspect this is?
    """
    history = history or []
    normalized = prompt.lower()
    reasons: List[str] = []
    pending_slot = _history_mentions_pending_favorite([*history, {"role": "user", "content": prompt}])
    candidate_hints = tuple(candidate["slot"] for candidate in _extract_review_candidates(prompt, pending_slot=pending_slot))
    archive_request = _is_archive_request(normalized)
    project_request = _is_project_context_request(normalized)
    conversational_boundary = _is_explicit_no_archive_concept_question(normalized)

    if pending_slot:
        reasons.append(f"recent context has pending slot {pending_slot}")
    if _looks_like_fact_update(normalized):
        reasons.append("current turn looks like user-supplied fact/update/reason")
    if candidate_hints:
        reasons.append(f"detected candidate slots: {', '.join(candidate_hints)}")
    if archive_request:
        reasons.append("current turn asks for bounded archive/GPT-log search")
    if project_request:
        reasons.append("current turn asks for project/code context search")
    if conversational_boundary:
        reasons.append("current turn explicitly says not to use GPT logs/archive")

    preferred_intent: Optional[str]
    if conversational_boundary:
        preferred_intent = "conversational"
    elif candidate_hints and project_request:
        preferred_intent = "multi_step"
    elif pending_slot or candidate_hints:
        preferred_intent = "mirus_extract_candidates"
    elif archive_request:
        preferred_intent = "gpt_log_search"
    elif project_request:
        preferred_intent = "project_context_search"
    else:
        preferred_intent = None
    return FrontPacket(
        preferred_intent=preferred_intent,
        pending_slot=pending_slot,
        candidate_hints=candidate_hints,
        reasons=tuple(reasons),
    )


def _looks_like_fact_update(normalized: str) -> bool:
    markers = (
        "my favorite",
        "i like ",
        "i also like ",
        "i work ",
        "i am ",
        "i'm ",
        "because ",
        "they are both",
        "it is ",
        "the brewers",
    )
    return any(marker in normalized for marker in markers)


def _is_archive_request(normalized: str) -> bool:
    if "without using gpt log" in normalized or "do not use gpt log" in normalized:
        return False
    return any(
        marker in normalized
        for marker in ("gpt log", "gpt archive", "old chat", "chatgpt archive", "gpt corpus")
    )


def _is_project_context_request(normalized: str) -> bool:
    return any(
        marker in normalized
        for marker in (
            "state parks project",
            "wisconsin state parks",
            "mill bluff",
            "glaciation",
            "look through this project",
            "find where",
            "thinking / process",
            "drawer is rendered",
        )
    )


def _is_explicit_no_archive_concept_question(normalized: str) -> bool:
    return (
        ("without using gpt log" in normalized or "do not use gpt log" in normalized)
        and ("is this system still valid" in normalized or "explain" in normalized)
    )


def _history_mentions_pending_favorite(messages: List[Dict[str, str]]) -> Optional[str]:
    for message in reversed(messages[:-1]):
        content = message.get("content", "").lower()
        if "favorite sports team" in content:
            return "user:favorite_sports_team"
        if "favorite flower" in content:
            return "user:favorite_flower"
        if "favorite drink" in content:
            return "user:favorite_drink"
    return None


def _extract_review_candidates(message: str, *, pending_slot: Optional[str] = None) -> List[Dict[str, Any]]:
    lower = message.lower()
    candidates: List[Dict[str, Any]] = []

    if "marigold" in lower:
        candidates.append(_candidate("profile_fact", "user:favorite_flower", "marigolds", 0.86))
    if "both orange" in lower or ("orange" in lower and "marigold" in lower):
        candidates.append(
            _candidate(
                "profile_relation",
                "user:favorite_flower_reason",
                "marigolds are a favorite partly because they are orange",
                0.72,
            )
        )
    if "orange" in lower and "favorite color" in lower:
        candidates.append(_candidate("profile_fact", "user:favorite_color", "orange", 0.86))
    if "orange" in lower and "leukemia awareness" in lower:
        candidates.append(
            _candidate(
                "profile_relation",
                "user:favorite_color_reason",
                "orange connects to leukemia awareness",
                0.72,
            )
        )
    if "dr. pepper" in lower:
        candidates.append(_candidate("profile_fact", "user:favorite_drink", "Dr. Pepper", 0.82))
    if "iced coffee" in lower:
        candidates.append(_candidate("profile_fact", "user:favorite_drink", "iced coffee", 0.78))
    if "health" in lower and "iced coffee" in lower:
        candidates.append(
            _candidate(
                "profile_relation",
                "user:favorite_drink_concern",
                "iced coffee is a favorite drink but has a health worry attached",
                0.66,
            )
        )
    if ("actually not dr. pepper" in lower or "not dr. pepper" in lower) and "iced coffee" in lower:
        candidates.append(
            _candidate(
                "profile_correction",
                "user:favorite_drink_correction",
                "iced coffee supersedes Dr. Pepper as the main favorite drink",
                0.74,
            )
        )
    if "brewers" in lower:
        candidates.append(_candidate("profile_fact", "user:favorite_sports_team", "Milwaukee Brewers", 0.84))
    if "bucks" in lower:
        candidates.append(_candidate("profile_fact", "user:sports_interest", "Milwaukee Bucks", 0.62))
    if pending_slot and not candidates:
        value = _short_confirmation_value(message)
        if value:
            if pending_slot == "user:favorite_sports_team" and "brewers" in lower:
                value = "Milwaukee Brewers"
            candidates.append(_candidate("profile_fact", pending_slot, value, 0.68))

    return candidates


def _candidate(kind: str, slot: str, value: str, confidence: float) -> Dict[str, Any]:
    return {
        "kind": kind,
        "slot": slot,
        "value": value,
        "reason": "model-assisted discovery candidate; requires review",
        "confidence": confidence,
        "source_boundary": "not confirmed memory until reviewed",
        "memory_write_allowed": False,
    }


def _short_confirmation_value(message: str) -> str:
    cleaned = re.sub(r"[^\w\s.-]", "", message).strip()
    if 1 <= len(cleaned.split()) <= 4:
        return cleaned
    return ""


DEFAULT_CASES: List[HarnessCase] = [
    HarnessCase(
        case_id="multi_fact_marigold_orange",
        prompt="My favorite flowers are marigolds because they are orange.",
        expected_intent="mirus_extract_candidates",
        min_candidates=2,
        required_candidate_slots=("user:favorite_flower", "user:favorite_flower_reason"),
        require_review_only=True,
    ),
    HarnessCase(
        case_id="short_confirmation_from_pending_sports_team",
        prompt="The Brewers",
        expected_intent="mirus_extract_candidates",
        history=[
            {"role": "user", "content": "What is my favorite sports team?"},
            {"role": "assistant", "content": "I need confirmation of your favorite sports team."},
        ],
        min_candidates=1,
        required_candidate_slots=("user:favorite_sports_team",),
        require_review_only=True,
    ),
    HarnessCase(
        case_id="archive_search_gpt_logs",
        prompt="Search my GPT logs for CRT concepts.",
        expected_intent="gpt_log_search",
    ),
    HarnessCase(
        case_id="project_context_mill_bluff",
        prompt="Why is Mill Bluff important to the state parks project?",
        expected_intent="project_context_search",
    ),
    HarnessCase(
        case_id="casual_hello_prefilter",
        prompt="hello",
        expected_intent="conversational",
    ),
]


def run_cases(
    cases: Iterable[HarnessCase] = DEFAULT_CASES,
    *,
    client: Any | None = None,
    client_label: str = "scripted",
) -> Dict[str, Any]:
    client = client or ScriptedToolCallingClient()
    router = LLMIntentRouter(
        client,
        build_mirus_tool_schemas(),
        source_label="mirus_original_router_lab",
    )
    results: List[HarnessResult] = []

    for case in cases:
        intent = router.classify(case.prompt, conversation_history=case.history)
        quality_flags = _quality_flags(case, dict(intent.slots))
        passed = intent.intent_type == case.expected_intent and not quality_flags
        graph = _logic_graph(
            case=case,
            front_packet=None,
            model_intent=intent.intent_type,
            quality_flags=quality_flags,
            repairs=[],
            final_intent=intent.intent_type,
            final_passed=passed,
        )
        results.append(
            HarnessResult(
                case_id=case.case_id,
                prompt=case.prompt,
                route=intent.route,
                intent_type=intent.intent_type,
                confidence=float(intent.confidence),
                source=intent.source,
                reason=intent.reason,
                slots=dict(intent.slots),
                passed=passed,
                expected_intent=case.expected_intent,
                quality_flags=quality_flags,
                repairs=[],
                logic_graph=graph,
            )
        )

    passed_count = sum(1 for result in results if result.passed)
    return {
        "lab": "mirus_router_harness_lab",
        "description": "Original LLMIntentRouter reused with Mirus review-only discovery tools.",
        "client": client_label,
        "safety": {
            "production_writes": False,
            "memory_write_allowed": False,
            "raw_hidden_cot_stored": False,
        },
        "summary": {
            "passed": passed_count,
            "total": len(results),
        },
        "results": [asdict(result) for result in results],
        "client_calls": client.calls,
    }


def run_governed_cases(
    cases: Iterable[HarnessCase] = DEFAULT_CASES,
    *,
    client: Any | None = None,
    client_label: str = "scripted",
) -> Dict[str, Any]:
    """Run old router with Mirus-front and CRT-back governance around it."""
    client = client or ScriptedToolCallingClient()
    router = LLMIntentRouter(
        client,
        build_mirus_tool_schemas(),
        source_label="mirus_original_router_lab",
    )
    results: List[HarnessResult] = []

    for case in cases:
        front_packet = build_front_packet(case.prompt, case.history)
        intent = router.classify(case.prompt, conversation_history=case.history)
        slots = dict(intent.slots)
        quality_flags = _quality_flags(case, slots)
        repairs: List[str] = []
        final_intent_type = intent.intent_type
        final_route = intent.route
        final_reason = intent.reason
        final_confidence = float(intent.confidence)
        final_source = intent.source

        should_repair_candidate = (
            front_packet.preferred_intent in {"mirus_extract_candidates", "multi_step"}
            and (
                intent.intent_type not in {"mirus_extract_candidates", "multi_step"}
                or bool(quality_flags)
            )
        )
        if should_repair_candidate:
            slots, repairs = _repair_candidate_slots(
                prompt=case.prompt,
                history=case.history,
                front_packet=front_packet,
                model_slots=slots,
                initial_flags=quality_flags,
            )
            final_intent_type = front_packet.preferred_intent or "mirus_extract_candidates"
            final_route = "task"
            final_reason = f"{intent.reason}; CRT backpass repaired Mirus candidate payload"
            final_confidence = min(0.84, max(final_confidence, 0.72))
            final_source = f"{intent.source}+mirus_front_crt_back"
            if final_intent_type == "multi_step":
                slots["steps"] = _multi_step_payload(case.prompt, slots)
            quality_flags = _quality_flags(case, slots)

        elif front_packet.preferred_intent == "project_context_search" and intent.intent_type != "project_context_search":
            repairs = ["front_packet_overrode_non_project_route"]
            slots = {
                "raw_message": case.prompt,
                "query": case.prompt,
                "project": _project_name_for_prompt(case.prompt),
            }
            final_intent_type = "project_context_search"
            final_route = "task"
            final_reason = f"{intent.reason}; Mirus front packet selected project context search"
            final_confidence = 0.8
            final_source = f"{intent.source}+mirus_front"

        elif front_packet.preferred_intent == "gpt_log_search" and intent.intent_type != "gpt_log_search":
            repairs = ["front_packet_overrode_non_archive_route"]
            slots = {"raw_message": case.prompt, "query": case.prompt, "top_k": 5}
            final_intent_type = "gpt_log_search"
            final_route = "task"
            final_reason = f"{intent.reason}; Mirus front packet selected bounded archive search"
            final_confidence = 0.8
            final_source = f"{intent.source}+mirus_front"

        elif front_packet.preferred_intent == "conversational" and intent.intent_type != "conversational":
            repairs = ["front_packet_blocked_disallowed_archive_route"]
            slots = {
                "raw_message": case.prompt,
                "llm_response": "No archive/tool route: user explicitly excluded GPT logs.",
            }
            final_intent_type = "conversational"
            final_route = "conversational"
            final_reason = f"{intent.reason}; Mirus front packet honored no-archive boundary"
            final_confidence = 0.82
            final_source = f"{intent.source}+mirus_front"

        passed = final_intent_type == case.expected_intent and not quality_flags
        graph = _logic_graph(
            case=case,
            front_packet=front_packet,
            model_intent=intent.intent_type,
            quality_flags=quality_flags,
            repairs=repairs,
            final_intent=final_intent_type,
            final_passed=passed,
        )
        results.append(
            HarnessResult(
                case_id=case.case_id,
                prompt=case.prompt,
                route=final_route,
                intent_type=final_intent_type,
                confidence=final_confidence,
                source=final_source,
                reason=final_reason,
                slots=slots,
                passed=passed,
                expected_intent=case.expected_intent,
                quality_flags=quality_flags,
                repairs=repairs,
                logic_graph=graph,
            )
        )

    passed_count = sum(1 for result in results if result.passed)
    return {
        "lab": "mirus_router_harness_lab",
        "mode": "mirus_front_holden_router_crt_back",
        "description": (
            "Original LLMIntentRouter with Mirus front packet, Holden/model routing, "
            "CRT payload validation, repair, and JSON logic graph."
        ),
        "client": client_label,
        "safety": {
            "production_writes": False,
            "memory_write_allowed": False,
            "raw_hidden_cot_stored": False,
        },
        "summary": {
            "passed": passed_count,
            "total": len(results),
        },
        "results": [asdict(result) for result in results],
        "client_calls": client.calls,
    }


def _repair_candidate_slots(
    *,
    prompt: str,
    history: Optional[List[Dict[str, str]]],
    front_packet: FrontPacket,
    model_slots: Dict[str, Any],
    initial_flags: List[str],
) -> tuple[Dict[str, Any], List[str]]:
    repairs = [f"initial_flags:{','.join(initial_flags) or 'wrong_tool'}"]
    pending_slot = front_packet.pending_slot or _history_mentions_pending_favorite(
        [*(history or []), {"role": "user", "content": prompt}]
    )
    candidates = _extract_review_candidates(prompt, pending_slot=pending_slot)

    model_payload = model_slots.get("payload")
    if isinstance(model_payload, dict):
        model_candidates = model_payload.get("candidates")
        if isinstance(model_candidates, list):
            normalized = _normalize_model_candidates(model_candidates)
            if normalized:
                repairs.append("normalized_model_candidates")
                candidates = _merge_candidates(candidates, normalized)

    slots = dict(model_slots)
    slots["payload"] = {
        "candidates": candidates,
        "source_boundary": "current_turn_or_recent_turns_review_only",
        "memory_write_allowed": False,
        "front_packet": asdict(front_packet),
    }
    repairs.append("forced_review_only_candidate_payload")
    return slots, repairs


def _multi_step_payload(prompt: str, slots: Dict[str, Any]) -> List[Dict[str, Any]]:
    return [
        {"tool": "mirus_extract_candidates", "params": {"payload": slots.get("payload", {})}},
        {
            "tool": "project_context_search",
            "params": {"query": prompt, "project": _project_name_for_prompt(prompt)},
        },
    ]


def _project_name_for_prompt(prompt: str) -> str:
    lower = prompt.lower()
    if "state parks" in lower or "mill bluff" in lower or "glaciation" in lower:
        return "wisconsin-state-parks-map"
    return "current-workspace"


def _normalize_model_candidates(raw_candidates: List[Any]) -> List[Dict[str, Any]]:
    normalized: List[Dict[str, Any]] = []
    for item in raw_candidates:
        if not isinstance(item, dict):
            continue
        slot = _normalize_slot_name(str(item.get("slot", "")).strip())
        value = str(item.get("value", "")).strip()
        if not slot or not value:
            continue
        kind = str(item.get("kind", "") or "profile_fact").strip()
        confidence = item.get("confidence", 0.6)
        try:
            confidence_value = float(confidence)
        except (TypeError, ValueError):
            confidence_value = 0.6
        normalized.append(_candidate(kind, slot, value, min(max(confidence_value, 0.0), 0.95)))
    return normalized


def _normalize_slot_name(slot: str) -> str:
    if not slot:
        return ""
    if slot.startswith("user:"):
        return slot
    known = {
        "favorite_flower": "user:favorite_flower",
        "favorite_flower_reason": "user:favorite_flower_reason",
        "favorite_sports_team": "user:favorite_sports_team",
        "favorite_drink": "user:favorite_drink",
        "favorite_drink_concern": "user:favorite_drink_concern",
        "favorite_drink_correction": "user:favorite_drink_correction",
        "favorite_color": "user:favorite_color",
        "favorite_color_reason": "user:favorite_color_reason",
        "sports_interest": "user:sports_interest",
    }
    return known.get(slot, f"user:{slot}")


def _merge_candidates(first: List[Dict[str, Any]], second: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    merged: Dict[tuple[str, str], Dict[str, Any]] = {}
    for candidate in [*first, *second]:
        key = (str(candidate.get("slot", "")), str(candidate.get("value", "")))
        if key[0] and key[1] and key not in merged:
            merged[key] = candidate
    return list(merged.values())


def _logic_graph(
    *,
    case: HarnessCase,
    front_packet: Optional[FrontPacket],
    model_intent: str,
    quality_flags: List[str],
    repairs: List[str],
    final_intent: str,
    final_passed: bool,
) -> Dict[str, Any]:
    nodes: List[Dict[str, Any]] = [
        {"id": "input", "kind": "user_turn", "label": case.prompt},
    ]
    edges: List[Dict[str, str]] = []

    if front_packet is not None:
        nodes.append(
            {
                "id": "mirus_front",
                "kind": "front_packet",
                "label": front_packet.preferred_intent or "no preferred intent",
                "data": asdict(front_packet),
            }
        )
        edges.append({"from": "input", "to": "mirus_front", "label": "compress task shape"})
        previous = "mirus_front"
    else:
        previous = "input"

    nodes.append({"id": "holden_router", "kind": "model_router", "label": model_intent})
    edges.append({"from": previous, "to": "holden_router", "label": "tool choice"})

    nodes.append(
        {
            "id": "crt_validator",
            "kind": "validator",
            "label": "passed" if not quality_flags else "flags",
            "data": {"quality_flags": quality_flags},
        }
    )
    edges.append({"from": "holden_router", "to": "crt_validator", "label": "validate boundaries"})

    if repairs:
        nodes.append({"id": "crt_repair", "kind": "repair", "label": "repaired", "data": {"repairs": repairs}})
        edges.append({"from": "crt_validator", "to": "crt_repair", "label": "repair unsafe or wrong shape"})
        previous = "crt_repair"
    else:
        previous = "crt_validator"

    nodes.append(
        {
            "id": "final",
            "kind": "result",
            "label": final_intent,
            "data": {"passed": final_passed},
        }
    )
    edges.append({"from": previous, "to": "final", "label": "release review-only intent"})
    return {"nodes": nodes, "edges": edges}


def load_case_pack(path: Path) -> List[HarnessCase]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    cases: List[HarnessCase] = []
    for item in raw:
        cases.append(
            HarnessCase(
                case_id=str(item["case_id"]),
                prompt=str(item["prompt"]),
                expected_intent=str(item["expected_intent"]),
                history=item.get("history"),
                min_candidates=int(item.get("min_candidates", 0)),
                required_candidate_slots=tuple(item.get("required_candidate_slots", ())),
                require_review_only=bool(item.get("require_review_only", False)),
            )
        )
    return cases


def run_comparison(
    cases: Iterable[HarnessCase],
    *,
    raw_client: Any | None = None,
    governed_client: Any | None = None,
    client_label: str = "scripted",
) -> Dict[str, Any]:
    case_list = list(cases)
    raw = run_cases(case_list, client=raw_client or ScriptedToolCallingClient(), client_label=client_label)
    governed = run_governed_cases(
        case_list,
        client=governed_client or ScriptedToolCallingClient(),
        client_label=client_label,
    )
    return {
        "lab": "mirus_router_harness_lab",
        "mode": "raw_vs_governed_comparison",
        "client": client_label,
        "summary": {
            "raw_passed": raw["summary"]["passed"],
            "governed_passed": governed["summary"]["passed"],
            "total": len(case_list),
            "delta": governed["summary"]["passed"] - raw["summary"]["passed"],
        },
        "raw": raw,
        "governed": governed,
    }


def _quality_flags(case: HarnessCase, slots: Dict[str, Any]) -> List[str]:
    flags: List[str] = []
    if case.min_candidates <= 0 and not case.required_candidate_slots and not case.require_review_only:
        return flags

    payload = slots.get("payload")
    if not isinstance(payload, dict):
        flags.append("missing_candidate_payload")
        return flags

    candidates = payload.get("candidates")
    if not isinstance(candidates, list):
        flags.append("missing_candidates")
        return flags

    if len(candidates) < case.min_candidates:
        flags.append(f"too_few_candidates:{len(candidates)}<{case.min_candidates}")

    candidate_slots = {
        str(candidate.get("slot", "")).strip()
        for candidate in candidates
        if isinstance(candidate, dict)
    }
    for required_slot in case.required_candidate_slots:
        if required_slot not in candidate_slots:
            flags.append(f"missing_candidate_slot:{required_slot}")

    if case.require_review_only:
        if payload.get("memory_write_allowed") is not False:
            flags.append("payload_not_review_only")
        for index, candidate in enumerate(candidates):
            if not isinstance(candidate, dict):
                flags.append(f"candidate_not_object:{index}")
                continue
            if candidate.get("memory_write_allowed") is not False:
                flags.append(f"candidate_not_review_only:{index}")
            boundary = str(candidate.get("source_boundary", "")).lower()
            if "review" not in boundary:
                flags.append(f"candidate_missing_review_boundary:{index}")

    return flags


def write_result_artifact(report: Dict[str, Any]) -> Path:
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    path = RESULTS_DIR / f"mirus_router_harness_{int(time.time())}.json"
    path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    return path


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the Mirus original-router harness lab.")
    parser.add_argument("--write", action="store_true", help="Write JSON result artifact.")
    parser.add_argument("--live-ollama", action="store_true", help="Use live Ollama tool calling instead of scripted client.")
    parser.add_argument("--model", default="qwen2.5:7b-instruct", help="Ollama model for --live-ollama.")
    parser.add_argument("--base-url", default="http://127.0.0.1:11434", help="Ollama base URL.")
    parser.add_argument("--timeout", type=int, default=120, help="Live Ollama timeout in seconds.")
    parser.add_argument("--governed", action="store_true", help="Wrap old router in Mirus front + CRT backpass.")
    parser.add_argument("--case-pack", default="", help="Optional JSON case pack path.")
    parser.add_argument("--compare", action="store_true", help="Run raw and governed modes over the same cases.")
    args = parser.parse_args()

    cases = load_case_pack(Path(args.case_pack)) if args.case_pack else DEFAULT_CASES

    def make_client() -> Any:
        if args.live_ollama:
            return OllamaToolCallingClient(model=args.model, base_url=args.base_url, timeout=args.timeout)
        return ScriptedToolCallingClient()

    client_label = f"ollama/{args.model}" if args.live_ollama else "scripted"

    if args.compare:
        report = run_comparison(
            cases,
            raw_client=make_client(),
            governed_client=make_client(),
            client_label=client_label,
        )
        if args.write:
            path = write_result_artifact(report)
            print(f"wrote {path}")
        print(json.dumps(report["summary"], indent=2))
        return 0 if report["summary"]["governed_passed"] == report["summary"]["total"] else 1

    if args.live_ollama:
        client = make_client()
        if args.governed:
            report = run_governed_cases(cases, client=client, client_label=client_label)
        else:
            report = run_cases(cases, client=client, client_label=client_label)
    else:
        report = run_governed_cases(cases) if args.governed else run_cases(cases)
    if args.write:
        path = write_result_artifact(report)
        print(f"wrote {path}")
    print(json.dumps(report["summary"], indent=2))
    return 0 if report["summary"]["passed"] == report["summary"]["total"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
