"""
Proactive Triggers for CRT Agent

Automatically detects situations requiring autonomous actions:
- Low confidence → trigger research
- Contradictions detected → resolve proactively
- Insufficient context → gather more information
- Complex query → decompose and plan
- Memory gaps → initiate learning

This enables the agent to act autonomously without explicit user commands.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional

try:
    from personal_agent.agent_loop import create_agent, AgentTrace
    from personal_agent.crt_memory import CRTMemoryEngine
    from personal_agent.research_engine import ResearchEngine
except ImportError as e:
    print(f"Warning: Import failed in proactive_triggers.py: {e}")


class TriggerType(str, Enum):
    """Types of proactive triggers."""
    LOW_CONFIDENCE = "low_confidence"
    CONTRADICTION = "contradiction"
    INSUFFICIENT_CONTEXT = "insufficient_context"
    COMPLEX_QUERY = "complex_query"
    MEMORY_GAP = "memory_gap"
    RESEARCH_NEEDED = "research_needed"


@dataclass
class TriggerEvent:
    """Represents a detected trigger event."""
    trigger_type: TriggerType
    reason: str
    suggested_action: str
    confidence_threshold: float = 0.5
    should_auto_execute: bool = True


class ProactiveTriggers:
    """
    Detects situations requiring autonomous agent actions.
    
    Monitors CRT responses and activates agent when needed.
    """

    def __init__(
        self,
        confidence_threshold: float = 0.5,
        auto_research_threshold: float = 0.4,
        contradiction_auto_resolve: bool = True,
    ):
        """
        Initialize proactive triggers.
        
        Args:
            confidence_threshold: Below this, trigger research
            auto_research_threshold: Below this, auto-execute research
            contradiction_auto_resolve: Auto-resolve contradictions
        """
        self.confidence_threshold = confidence_threshold
        self.auto_research_threshold = auto_research_threshold
        self.contradiction_auto_resolve = contradiction_auto_resolve

    def analyze_response(self, response: dict) -> list[TriggerEvent]:
        """
        Analyze CRT response for trigger conditions.
        
        Args:
            response: CRT response dictionary from crt_rag.query()
            
        Returns:
            List of triggered events
        """
        triggers = []

        # 1. Low confidence trigger
        confidence = response.get("confidence", 0)
        if confidence < self.confidence_threshold:
            should_auto = confidence < self.auto_research_threshold
            triggers.append(
                TriggerEvent(
                    trigger_type=TriggerType.LOW_CONFIDENCE,
                    reason=f"Confidence {confidence:.2f} below threshold {self.confidence_threshold}",
                    suggested_action="search_research",
                    should_auto_execute=should_auto,
                )
            )

        # 2. Contradiction detected
        if response.get("contradiction_detected"):
            triggers.append(
                TriggerEvent(
                    trigger_type=TriggerType.CONTRADICTION,
                    reason="Contradiction detected in memory",
                    suggested_action="resolve_contradiction",
                    should_auto_execute=self.contradiction_auto_resolve,
                )
            )

        # 3. Insufficient context (fallback response)
        if response.get("response_type") == "fallback":
            gate_reason = response.get("gate_reason", "")
            triggers.append(
                TriggerEvent(
                    trigger_type=TriggerType.INSUFFICIENT_CONTEXT,
                    reason=f"Gate failed: {gate_reason}",
                    suggested_action="search_memory_and_research",
                    should_auto_execute=True,
                )
            )

        # 4. Few retrieved memories (potential gap)
        mem_count = len(response.get("retrieved_memories", []))
        if mem_count < 2 and response.get("response_type") != "fallback":
            triggers.append(
                TriggerEvent(
                    trigger_type=TriggerType.MEMORY_GAP,
                    reason=f"Only {mem_count} memories retrieved",
                    suggested_action="expand_search",
                    should_auto_execute=False,  # User should confirm
                )
            )

        # 5. Complex query detection (heuristic: > 15 words or multiple questions)
        query = response.get("query", "")
        if len(query.split()) > 15 or query.count("?") > 1:
            triggers.append(
                TriggerEvent(
                    trigger_type=TriggerType.COMPLEX_QUERY,
                    reason="Multi-part query detected",
                    suggested_action="create_plan",
                    should_auto_execute=False,
                )
            )

        return triggers

    def should_activate_agent(self, triggers: list[TriggerEvent]) -> bool:
        """
        Determine if agent should be activated.
        
        Args:
            triggers: List of detected triggers
            
        Returns:
            True if agent should run autonomously
        """
        # Activate if any trigger suggests auto-execution
        return any(t.should_auto_execute for t in triggers)

    def get_agent_task(self, triggers: list[TriggerEvent], original_query: str) -> str:
        """
        Formulate agent task based on triggers.
        
        Args:
            triggers: Detected triggers
            original_query: User's original query
            
        Returns:
            Task string for agent
        """
        if not triggers:
            return original_query

        # Prioritize triggers
        priority_order = [
            TriggerType.CONTRADICTION,
            TriggerType.LOW_CONFIDENCE,
            TriggerType.INSUFFICIENT_CONTEXT,
            TriggerType.MEMORY_GAP,
            TriggerType.COMPLEX_QUERY,
        ]

        for trigger_type in priority_order:
            matching = [t for t in triggers if t.trigger_type == trigger_type]
            if matching:
                trigger = matching[0]
                return self._format_agent_task(trigger, original_query)

        return original_query

    def _format_agent_task(self, trigger: TriggerEvent, query: str) -> str:
        """Format task instruction for agent."""
        if trigger.trigger_type == TriggerType.LOW_CONFIDENCE:
            return f"Research this query thoroughly: {query}. Find relevant documents and citations."

        elif trigger.trigger_type == TriggerType.CONTRADICTION:
            return f"Resolve contradiction related to: {query}. Check memory for conflicting statements."

        elif trigger.trigger_type == TriggerType.INSUFFICIENT_CONTEXT:
            return f"Gather comprehensive context for: {query}. Search memory and documents."

        elif trigger.trigger_type == TriggerType.MEMORY_GAP:
            return f"Find additional information about: {query}. Expand search to fill knowledge gaps."

        elif trigger.trigger_type == TriggerType.COMPLEX_QUERY:
            return f"Break down and answer systematically: {query}. Create plan and execute steps."

        else:
            return query


class AgenticChatMode:
    """
    Wraps CRT RAG with proactive agent capabilities.
    
    Monitors responses and triggers autonomous actions when needed.
    """

    def __init__(
        self,
        memory_engine: CRTMemoryEngine,
        research_engine: Optional[ResearchEngine] = None,
        auto_mode: bool = True,
        verbose: bool = False,
    ):
        """
        Initialize agentic chat mode.
        
        Args:
            memory_engine: CRT memory engine
            research_engine: Research engine
            auto_mode: Enable autonomous agent execution
            verbose: Print agent traces
        """
        self.memory = memory_engine
        self.research = research_engine
        self.auto_mode = auto_mode
        self.verbose = verbose
        self.triggers = ProactiveTriggers()
        self.agent = None

        # Lazy load agent
        self._agent_available = False
        try:
            from personal_agent.agent_loop import create_agent
            self.agent = create_agent(
                memory_engine=memory_engine,
                research_engine=research_engine,
            )
            self._agent_available = True
        except Exception as e:
            if verbose:
                print(f"Agent not available: {e}")

    def query(self, user_query: str, crt_response: dict) -> dict:
        """
        Process query with proactive agent triggers.
        
        Args:
            user_query: User's query
            crt_response: Response from CRT RAG
            
        Returns:
            Enhanced response with agent actions
        """
        # Analyze response for triggers
        detected_triggers = self.triggers.analyze_response(crt_response)

        if not detected_triggers:
            # No triggers - return original response
            return {
                **crt_response,
                "agent_activated": False,
                "triggers": [],
            }

        # Check if agent should run
        should_run = self.auto_mode and self.triggers.should_activate_agent(detected_triggers)

        result = {
            **crt_response,
            "agent_activated": should_run,
            "triggers": [
                {
                    "type": t.trigger_type.value,
                    "reason": t.reason,
                    "suggested_action": t.suggested_action,
                    "auto_execute": t.should_auto_execute,
                }
                for t in detected_triggers
            ],
        }

        if should_run and self._agent_available and self.agent:
            # Run agent
            task = self.triggers.get_agent_task(detected_triggers, user_query)

            if self.verbose:
                print(f"\n🤖 Agent activated: {detected_triggers[0].trigger_type.value}")
                print(f"   Task: {task}")

            trace = self.agent.run(task)

            if self.verbose:
                print(f"   Steps: {len(trace.steps)}")
                print(f"   Success: {trace.success}")

            # Merge agent results into response
            result["agent_trace"] = trace.to_dict()
            if trace.final_answer:
                result["agent_answer"] = trace.final_answer
                result["answer"] = f"{crt_response['answer']}\n\n🔍 Agent Research:\n{trace.final_answer}"

        return result

    def enable_auto_mode(self):
        """Enable autonomous agent execution."""
        self.auto_mode = True

    def disable_auto_mode(self):
        """Disable autonomous agent execution (manual triggers only)."""
        self.auto_mode = False
