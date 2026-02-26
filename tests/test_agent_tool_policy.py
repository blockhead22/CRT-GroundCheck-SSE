from __future__ import annotations

from pathlib import Path

from personal_agent.agent_loop import AgentAction, ToolCall, ToolRegistry
from personal_agent.tool_policy import AgentToolPolicy, ToolExecutionContext


def _make_policy(require_code_approval: bool = True, calculate_quota: int | None = None) -> AgentToolPolicy:
    tools = {
        "execute_code": {
            "enabled": True,
            "require_approval": require_code_approval,
            "max_calls_per_run": 2,
        }
    }
    if calculate_quota is not None:
        tools["calculate"] = {
            "enabled": True,
            "require_approval": False,
            "max_calls_per_run": int(calculate_quota),
        }
    return AgentToolPolicy(
        {
            "enabled": True,
            "default_allow": True,
            "global_max_calls_per_run": 20,
            "tools": tools,
        }
    )


def test_execute_code_requires_explicit_approval(tmp_path: Path):
    policy = _make_policy(require_code_approval=True)
    registry = ToolRegistry(
        workspace_root=tmp_path,
        policy_engine=policy,
        execution_context=ToolExecutionContext(
            thread_id="t1",
            channel="api",
            actor_id="user-1",
            approved_tools=set(),
        ),
    )

    result = registry.execute(
        ToolCall(
            tool=AgentAction.EXECUTE_CODE,
            args={"code": "print('hello')", "timeout": 5},
            reasoning="need code execution",
        )
    )
    assert result.success is False
    assert "policy_blocked:approval_required" in str(result.error)


def test_execute_code_runs_when_approved(tmp_path: Path):
    policy = _make_policy(require_code_approval=True)
    registry = ToolRegistry(
        workspace_root=tmp_path,
        policy_engine=policy,
        execution_context=ToolExecutionContext(
            thread_id="t1",
            channel="api",
            actor_id="user-1",
            approved_tools={"execute_code"},
        ),
    )

    result = registry.execute(
        ToolCall(
            tool=AgentAction.EXECUTE_CODE,
            args={"code": "print('policy-ok')", "timeout": 5},
            reasoning="need code execution",
        )
    )
    assert result.success is True
    assert "policy-ok" in str((result.result or {}).get("stdout", ""))


def test_per_tool_quota_blocks_after_limit(tmp_path: Path):
    policy = _make_policy(require_code_approval=False, calculate_quota=1)
    registry = ToolRegistry(
        workspace_root=tmp_path,
        policy_engine=policy,
        execution_context=ToolExecutionContext(
            thread_id="t1",
            channel="api",
            actor_id="user-1",
            approved_tools=set(),
        ),
    )

    first = registry.execute(
        ToolCall(
            tool=AgentAction.CALCULATE,
            args={"expression": "1+2"},
            reasoning="math",
        )
    )
    assert first.success is True
    assert (first.result or {}).get("result") == 3

    second = registry.execute(
        ToolCall(
            tool=AgentAction.CALCULATE,
            args={"expression": "2+3"},
            reasoning="math again",
        )
    )
    assert second.success is False
    assert "policy_blocked:quota_exceeded" in str(second.error)
