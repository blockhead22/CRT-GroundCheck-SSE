from __future__ import annotations

import json
from typing import Any, Dict, List

from personal_agent.cookie_orchestrator import BrainResult, Orchestrator
from personal_agent.task_agent import TaskIntent, classify_intent_hybrid


class _NoCacheRouteDb:
    def lookup_recent(self, message: str, max_age_hours: int = 24):
        return None

    def log_classification(self, **kwargs) -> None:
        return None


def _force_router_conversational(monkeypatch) -> None:
    monkeypatch.setattr("personal_agent.route_learning.get_route_learning_db", lambda: _NoCacheRouteDb())
    monkeypatch.setattr("auth.get_user_settings", lambda uid: {"routing_mode": "hybrid"})
    monkeypatch.setattr(
        "personal_agent.task_agent._try_llm_router",
        lambda *args, **kwargs: TaskIntent(
            route="conversational",
            intent_type="conversational",
            slots={"raw_message": args[0], "llm_response": "just chat"},
            confidence=0.95,
            reason="forced_conversational_for_test",
            source="test",
        ),
    )
    monkeypatch.setattr("personal_agent.task_agent._try_embedding_classifier", lambda *args, **kwargs: None)


def test_active_task_go_ahead_routes_as_task_continuation(monkeypatch) -> None:
    _force_router_conversational(monkeypatch)

    intent = classify_intent_hybrid(
        "go ahead",
        active_task={"status": "active", "title": "Refactor routing"},
    )

    assert intent.route == "task"
    assert intent.intent_type == "task_continuation"
    assert intent.reason == "active_task_continuation"


def test_phased_work_prompt_routes_as_multi_step(monkeypatch) -> None:
    _force_router_conversational(monkeypatch)

    intent = classify_intent_hybrid(
        "Break this work into tiny next steps and keep going phase by phase until everything is fully complete."
    )

    assert intent.route == "task"
    assert intent.intent_type == "multi_step"
    assert intent.reason == "agentic_work_pattern"


def test_draft_changes_prompt_routes_as_multi_step(monkeypatch) -> None:
    _force_router_conversational(monkeypatch)

    intent = classify_intent_hybrid(
        "Draft the file changes you would make, but ask me before writing anything important."
    )

    assert intent.route == "task"
    assert intent.intent_type == "multi_step"
    assert intent.reason == "agentic_work_pattern"


def test_orchestrator_rejects_invented_tool_and_recovers(monkeypatch) -> None:
    prompts: List[Dict[str, str]] = []
    executed_tools: List[str] = []

    class _ScriptedBrain:
        _model = "scripted"

        def __init__(self) -> None:
            self.idx = 0
            self.outputs = [
                {"action": "plan", "message": "Plan.", "steps": ["Read the file"], "estimated_depth": 2},
                {"action": "tool_call", "tool": "Read", "args": {"file_path": "README.md"}, "reasoning": "Need to read the file"},
                {"action": "tool_call", "tool": "file_read", "args": {"path": "README.md"}, "reasoning": "Use the exact registry tool name"},
                {"action": "respond", "message": "Recovered after invalid tool.", "reasoning": "Done", "complete": True},
            ]

        def complete(self, system: str, prompt: str, max_tokens: int = 800) -> BrainResult:
            prompts.append({"system": system, "prompt": prompt})
            payload = self.outputs[min(self.idx, len(self.outputs) - 1)]
            self.idx += 1
            return BrainResult(content=json.dumps(payload), provider="test", latency_ms=1)

    def _fake_execute_tool(tool_name: str, args: Dict[str, Any], memory_system=None) -> Dict[str, Any]:
        executed_tools.append(tool_name)
        return {"content": f"{tool_name} ok", "status": "ok"}

    monkeypatch.setattr("personal_agent.cookie_orchestrator.execute_tool", _fake_execute_tool)

    orch = Orchestrator(brain=_ScriptedBrain(), max_iterations=5)
    events = list(orch.run("Read a file and summarize it", intent_type="task", route="task"))

    assert any("Valid tool names for this run:" in call["system"] for call in prompts)
    assert executed_tools == ["file_read"]
    assert not any(event.get("tool") == "Read" for event in events if event.get("type") == "tool_call")
    assert any(event.get("tool") == "file_read" for event in events if event.get("type") == "tool_call")
    assert any(event.get("type") == "response" and "Recovered after invalid tool." in event.get("content", "") for event in events)
