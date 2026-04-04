from types import SimpleNamespace

from personal_agent.task_agent import CRTTaskAgent, TaskIntent
from personal_agent.tool_gate import get_tools_for_intent
from tools.local_capability_lab import ScenarioResult, evaluate_result


def test_broad_recall_builds_memory_recall_plan():
    agent = CRTTaskAgent(memory_agent=None, llm_client=None, session_db=None)
    intent = TaskIntent(route="task", intent_type="broad_recall", slots={}, confidence=0.95)

    plan = agent._build_plan(intent, "What do you know about me?", None)

    assert plan == [{"tool": "memory_recall", "input": {"query": "What do you know about me?"}}]


def test_user_reflection_builds_memory_recall_plan():
    agent = CRTTaskAgent(memory_agent=None, llm_client=None, session_db=None)
    intent = TaskIntent(route="task", intent_type="user_reflection", slots={}, confidence=0.95)

    plan = agent._build_plan(intent, "What do you think I value?", None)

    assert plan == [{"tool": "memory_recall", "input": {"query": "What do you think I value?"}}]


def test_local_only_tool_gate_hides_web_search_for_generic_task(monkeypatch):
    def _fake_setting(uid, key, default=""):
        if key == "routing_mode":
            return "local_only"
        return default

    monkeypatch.setattr("auth.get_user_setting", _fake_setting)

    tools = get_tools_for_intent("task")

    assert "web_search" not in tools
    assert "memory_recall" in tools
    assert "file_read" in tools


def test_local_only_tool_gate_keeps_web_search_for_explicit_web_intent(monkeypatch):
    def _fake_setting(uid, key, default=""):
        if key == "routing_mode":
            return "local_only"
        return default

    monkeypatch.setattr("auth.get_user_setting", _fake_setting)

    tools = get_tools_for_intent("web_search")

    assert "web_search" in tools


def test_lab_evaluation_flags_wrong_tool_and_think_leak():
    result = ScenarioResult(
        name="memory_grounding",
        prompt="prompt",
        thread_id="t1",
        response_text="Yosemite <think>hidden</think>",
        tool_names=["llm_respond"],
        tool_events=[],
        event_types=[],
        done_metadata={},
        failures=[],
    )

    evaluated = evaluate_result(result)

    assert evaluated.passed is False
    assert "memory prompt did not call memory_recall" in evaluated.failures
    assert "visible <think> leakage" in evaluated.failures


def test_lab_evaluation_accepts_grounded_file_read_result():
    result = ScenarioResult(
        name="local_file_tool",
        prompt="prompt",
        thread_id="t1",
        response_text="The current in-progress phase is v3.7.x Cookie Orchestrator Stabilization.",
        tool_names=["file_read"],
        tool_events=[],
        event_types=[],
        done_metadata={},
        failures=[],
    )

    evaluated = evaluate_result(result)

    assert evaluated.passed is True
