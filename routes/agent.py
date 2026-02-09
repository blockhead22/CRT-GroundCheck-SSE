"""Agent route module – autonomous ReAct agent endpoints."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict

from fastapi import APIRouter, HTTPException, Query, Request

from routes.deps import sanitize_thread_id
from routes.models import (
    AgentRunRequest,
    AgentRunResponse,
    AgentStepModel,
    AgentStatusResponse,
    AgentTraceModel,
    AgentTriggersResponse,
)

router = APIRouter(prefix="/api/agent", tags=["agent"])


@router.post("/run", response_model=AgentRunResponse)
def run_agent(req: AgentRunRequest, request: Request) -> AgentRunResponse:
    """
    Run autonomous agent for a task.

    Executes ReAct loop: Thought → Action → Observation cycles.
    Returns complete execution trace.
    """
    tid = sanitize_thread_id(req.thread_id)
    engine = request.app.state.get_engine(tid)

    try:
        from personal_agent.agent_loop import create_agent
        from personal_agent.research_engine import ResearchEngine as _RE

        # Create research engine if not exists
        research_engine = None
        try:
            research_engine = _RE()
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


@router.post("/analyze-triggers", response_model=AgentTriggersResponse)
def analyze_triggers(
    request: Request,
    thread_id: str = Query(default="default"),
    response_data: Dict[str, Any] = None,
) -> AgentTriggersResponse:
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
    tid = sanitize_thread_id(thread_id)

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


@router.get("/status", response_model=AgentStatusResponse)
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

