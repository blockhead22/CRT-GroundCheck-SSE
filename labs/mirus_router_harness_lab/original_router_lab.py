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

from personal_agent.llm_intent_router import LLMIntentRouter
from personal_agent.tool_registry import ToolDefinition, ToolParam


LAB_ROOT = Path(__file__).resolve().parent
RESULTS_DIR = LAB_ROOT / "results"


@dataclass(frozen=True)
class HarnessCase:
    case_id: str
    prompt: str
    expected_intent: str
    history: Optional[List[Dict[str, str]]] = None


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


def _tool_call(name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
    return {"tool_calls": [{"name": name, "arguments": arguments}], "content": "", "used_tools": True}


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
    if "dr. pepper" in lower:
        candidates.append(_candidate("profile_fact", "user:favorite_drink", "Dr. Pepper", 0.82))
    if "iced coffee" in lower:
        candidates.append(_candidate("profile_fact", "user:favorite_drink", "iced coffee", 0.78))
    if "brewers" in lower:
        candidates.append(_candidate("profile_fact", "user:favorite_sports_team", "Milwaukee Brewers", 0.84))
    if pending_slot and not candidates:
        value = _short_confirmation_value(message)
        if value:
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
    ),
    HarnessCase(
        case_id="short_confirmation_from_pending_sports_team",
        prompt="The Brewers",
        expected_intent="mirus_extract_candidates",
        history=[
            {"role": "user", "content": "What is my favorite sports team?"},
            {"role": "assistant", "content": "I need confirmation of your favorite sports team."},
        ],
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


def run_cases(cases: Iterable[HarnessCase] = DEFAULT_CASES) -> Dict[str, Any]:
    client = ScriptedToolCallingClient()
    router = LLMIntentRouter(
        client,
        build_mirus_tool_schemas(),
        source_label="mirus_original_router_lab",
    )
    results: List[HarnessResult] = []

    for case in cases:
        intent = router.classify(case.prompt, conversation_history=case.history)
        passed = intent.intent_type == case.expected_intent
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
            )
        )

    passed_count = sum(1 for result in results if result.passed)
    return {
        "lab": "mirus_router_harness_lab",
        "description": "Original LLMIntentRouter reused with Mirus review-only discovery tools.",
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


def write_result_artifact(report: Dict[str, Any]) -> Path:
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    path = RESULTS_DIR / f"mirus_router_harness_{int(time.time())}.json"
    path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    return path


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the Mirus original-router harness lab.")
    parser.add_argument("--write", action="store_true", help="Write JSON result artifact.")
    args = parser.parse_args()

    report = run_cases()
    if args.write:
        path = write_result_artifact(report)
        print(f"wrote {path}")
    print(json.dumps(report["summary"], indent=2))
    return 0 if report["summary"]["passed"] == report["summary"]["total"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

