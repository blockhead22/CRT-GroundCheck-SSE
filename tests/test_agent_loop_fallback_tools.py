from personal_agent.agent_loop import AgentAction, AgentLoop, AgentTrace, ToolRegistry


def test_agent_loop_prefers_moltbook_tool_for_moltbook_queries():
    loop = AgentLoop(
        tool_registry=ToolRegistry(),
        max_steps=4,
        llm_client=None,
        reasoning_engine=None,
    )
    loop.trace = AgentTrace(query="Whats new on moltbook?")

    action = loop._choose_action("Starting task execution", context=None)

    assert action is not None
    assert action.tool == AgentAction.MOLTBOOK
    assert action.args.get("action") == "feed"


def test_agent_loop_prefers_fetch_url_for_explicit_url_requests():
    loop = AgentLoop(
        tool_registry=ToolRegistry(),
        max_steps=4,
        llm_client=None,
        reasoning_engine=None,
    )
    loop.trace = AgentTrace(query="Read https://www.moltbook.com/skill.md")

    action = loop._choose_action("Starting task execution", context=None)

    assert action is not None
    assert action.tool == AgentAction.FETCH_URL
    assert action.args.get("url") == "https://www.moltbook.com/skill.md"
