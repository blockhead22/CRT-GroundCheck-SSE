"""
LLM-powered reasoning engine for agent loop.

Implements:
- Thought generation (what should I do next?)
- Action selection (which tool to use?)
- Plan creation (how to break down complex tasks?)
- Reflection (did that work? should I try something else?)

Uses structured prompts to guide LLM into ReAct pattern.
"""

from __future__ import annotations

import json
from typing import Any, Optional

try:
    from personal_agent.agent_loop import AgentAction, AgentTrace, AgentStep, ToolCall
    from personal_agent.ollama_client import get_ollama_client
except ImportError as e:
    print(f"Warning: Import failed in agent_reasoning.py: {e}")


# Prompts for LLM reasoning
THOUGHT_PROMPT = """You are an AI assistant with access to tools. Based on the task and your progress so far, decide what to do next.

TASK: {query}

PREVIOUS STEPS:
{previous_steps}

AVAILABLE TOOLS:
- search_memory: Search CRT memory for existing knowledge
- search_research: Search local documents for information
- store_memory: Store new information in memory
- check_contradiction: Check if statement contradicts beliefs
- calculate: Evaluate math expressions
- read_file: Read file contents
- list_files: List files in directory
- synthesize: Combine multiple pieces of information
- reflect: Analyze action outcomes
- plan: Generate step-by-step plan
- finish: Complete task with final answer

CURRENT SITUATION:
{current_situation}

What should you do next? Think step-by-step:
1. What have I learned so far?
2. What information is still missing?
3. Which tool would best help me make progress?
4. If I have enough information, should I finish?

THOUGHT:"""

ACTION_SELECTION_PROMPT = """Based on your thought, choose the best tool to use.

THOUGHT: {thought}

AVAILABLE TOOLS:
{tools_json}

Choose ONE tool and provide the arguments as JSON.

FORMAT:
{{
  "tool": "tool_name",
  "args": {{"arg1": "value1", "arg2": "value2"}},
  "reasoning": "why this tool"
}}

RESPONSE (JSON only):"""

PLAN_CREATION_PROMPT = """Create a step-by-step plan to accomplish this goal.

GOAL: {goal}

CONSTRAINTS:
{constraints}

AVAILABLE TOOLS:
{tools}

Generate a concrete, actionable plan with 3-7 steps. Each step should:
- Use a specific tool
- Have clear success criteria
- Build on previous steps

FORMAT:
{{
  "steps": [
    {{"step": 1, "action": "search_memory", "goal": "Find existing knowledge about X", "success_criteria": "Found at least 3 relevant memories"}},
    {{"step": 2, "action": "...", "goal": "...", "success_criteria": "..."}},
    ...
  ]
}}

PLAN (JSON only):"""

REFLECTION_PROMPT = """Analyze the outcome of the action you just took.

ACTION: {action}
RESULT: {result}
EXPECTED: {expected}

Questions:
1. Did the action achieve its goal?
2. Was the result useful for the overall task?
3. What did I learn from this?
4. Should I try a different approach?
5. Am I closer to finishing the task?

REFLECTION:"""

SYNTHESIS_PROMPT = """You have gathered information from multiple sources. Synthesize a final answer.

ORIGINAL QUERY: {query}

INFORMATION GATHERED:
{gathered_info}

REQUIREMENTS:
- Answer the query directly
- Cite sources when possible
- Be honest about gaps in knowledge
- Don't speculate beyond the evidence

FINAL ANSWER:"""


class AgentReasoning:
    """LLM-powered reasoning for agent decisions."""

    def __init__(self, llm_client: Optional[Any] = None, model: str = "llama3.2:latest"):
        """
        Initialize reasoning engine.
        
        Args:
            llm_client: Ollama client (will create if None)
            model: Model to use for reasoning
        """
        self.llm = llm_client
        self.model = model

        if not self.llm and get_ollama_client:
            try:
                self.llm = get_ollama_client()
            except Exception as e:
                print(f"Warning: Could not initialize Ollama client: {e}")

    def generate_thought(
        self,
        query: str,
        trace: AgentTrace,
        current_situation: str = "",
    ) -> str:
        """
        Generate agent's next thought.
        
        Args:
            query: Original user query
            trace: Current agent trace
            current_situation: Description of current state
            
        Returns:
            Thought string
        """
        if not self.llm:
            return self._default_thought(len(trace.steps) + 1)

        # Format previous steps
        prev_steps = self._format_previous_steps(trace.steps)

        prompt = THOUGHT_PROMPT.format(
            query=query,
            previous_steps=prev_steps,
            current_situation=current_situation or "Just starting the task",
        )

        try:
            response = self.llm.generate(model=self.model, prompt=prompt)
            return response.get("response", "").strip()
        except Exception as e:
            print(f"LLM thought generation failed: {e}")
            return self._default_thought(len(trace.steps) + 1)

    def select_action(
        self,
        thought: str,
        available_tools: list[AgentAction],
    ) -> Optional[ToolCall]:
        """
        Select which tool to use based on thought.
        
        Args:
            thought: Agent's current thought
            available_tools: List of available tools
            
        Returns:
            ToolCall or None
        """
        if not self.llm:
            return self._default_action(thought)

        # Format tools as JSON
        tools_json = json.dumps([tool.value for tool in available_tools], indent=2)

        prompt = ACTION_SELECTION_PROMPT.format(
            thought=thought,
            tools_json=tools_json,
        )

        try:
            response = self.llm.generate(model=self.model, prompt=prompt)
            response_text = response.get("response", "").strip()

            # Parse JSON response
            action_data = json.loads(response_text)

            return ToolCall(
                tool=AgentAction(action_data["tool"]),
                args=action_data.get("args", {}),
                reasoning=action_data.get("reasoning", ""),
            )
        except Exception as e:
            print(f"Action selection failed: {e}")
            return self._default_action(thought)

    def create_plan(
        self,
        goal: str,
        constraints: Optional[list[str]] = None,
        available_tools: Optional[list[AgentAction]] = None,
    ) -> dict:
        """
        Create step-by-step plan for complex goal.
        
        Args:
            goal: Goal to accomplish
            constraints: Optional constraints
            available_tools: Tools available for planning
            
        Returns:
            Plan dictionary with steps
        """
        if not self.llm:
            return self._default_plan(goal)

        constraints_text = "\n".join(f"- {c}" for c in (constraints or ["None"]))
        tools_text = ", ".join(t.value for t in (available_tools or list(AgentAction)))

        prompt = PLAN_CREATION_PROMPT.format(
            goal=goal,
            constraints=constraints_text,
            tools=tools_text,
        )

        try:
            response = self.llm.generate(model=self.model, prompt=prompt)
            response_text = response.get("response", "").strip()
            return json.loads(response_text)
        except Exception as e:
            print(f"Plan creation failed: {e}")
            return self._default_plan(goal)

    def reflect_on_action(
        self,
        action: str,
        result: Any,
        expected: str = "",
    ) -> str:
        """
        Reflect on action outcome.
        
        Args:
            action: Action taken
            result: Result received
            expected: What was expected
            
        Returns:
            Reflection text
        """
        if not self.llm:
            return self._default_reflection(result)

        prompt = REFLECTION_PROMPT.format(
            action=action,
            result=str(result)[:1000],  # Truncate long results
            expected=expected or "Useful information to advance task",
        )

        try:
            response = self.llm.generate(model=self.model, prompt=prompt)
            return response.get("response", "").strip()
        except Exception as e:
            print(f"Reflection failed: {e}")
            return self._default_reflection(result)

    def synthesize_answer(
        self,
        query: str,
        gathered_info: list[dict],
    ) -> str:
        """
        Synthesize final answer from gathered information.
        
        Args:
            query: Original query
            gathered_info: List of information dictionaries
            
        Returns:
            Synthesized answer
        """
        if not self.llm:
            return "Information gathered but LLM synthesis not available"

        # Format gathered info
        info_text = "\n\n".join(
            f"Source {i+1}: {info.get('source', 'unknown')}\n{info.get('content', str(info))}"
            for i, info in enumerate(gathered_info)
        )

        prompt = SYNTHESIS_PROMPT.format(
            query=query,
            gathered_info=info_text[:4000],  # Truncate if too long
        )

        try:
            response = self.llm.generate(model=self.model, prompt=prompt)
            return response.get("response", "").strip()
        except Exception as e:
            print(f"Synthesis failed: {e}")
            return f"Gathered {len(gathered_info)} pieces of information but synthesis failed: {e}"

    # Default fallback methods (when LLM unavailable)
    def _format_previous_steps(self, steps: list[AgentStep]) -> str:
        """Format previous steps for prompt."""
        if not steps:
            return "No previous steps"

        formatted = []
        for step in steps[-5:]:  # Last 5 steps only
            formatted.append(f"Step {step.step_num}: {step.thought}")
            if step.action:
                formatted.append(f"  Action: {step.action.tool.value} - {step.action.reasoning}")
            if step.observation:
                result_str = str(step.observation.result)[:200]
                formatted.append(f"  Result: {result_str}")

        return "\n".join(formatted)

    def _default_thought(self, step_num: int) -> str:
        """Default thought when LLM unavailable."""
        if step_num == 1:
            return "I should check memory for existing knowledge"
        elif step_num == 2:
            return "Memory search complete, should search documents"
        elif step_num == 3:
            return "I have enough information to formulate an answer"
        else:
            return "Continuing task execution"

    def _default_action(self, thought: str) -> ToolCall:
        """Default action when LLM unavailable."""
        if "memory" in thought.lower():
            return ToolCall(
                tool=AgentAction.SEARCH_MEMORY,
                args={"query": "placeholder", "top_k": 5},
                reasoning="Default: searching memory",
            )
        elif "document" in thought.lower() or "research" in thought.lower():
            return ToolCall(
                tool=AgentAction.SEARCH_RESEARCH,
                args={"query": "placeholder", "top_k": 3},
                reasoning="Default: searching documents",
            )
        else:
            return ToolCall(
                tool=AgentAction.FINISH,
                args={"answer": "Task completed with default actions"},
                reasoning="Default: finishing task",
            )

    def _default_plan(self, goal: str) -> dict:
        """Default plan when LLM unavailable."""
        return {
            "steps": [
                {
                    "step": 1,
                    "action": "search_memory",
                    "goal": "Find existing knowledge",
                    "success_criteria": "Retrieved memories",
                },
                {
                    "step": 2,
                    "action": "search_research",
                    "goal": "Find additional context",
                    "success_criteria": "Retrieved documents",
                },
                {
                    "step": 3,
                    "action": "synthesize",
                    "goal": "Combine findings",
                    "success_criteria": "Answer formulated",
                },
            ]
        }

    def _default_reflection(self, result: Any) -> str:
        """Default reflection when LLM unavailable."""
        if isinstance(result, dict) and result.get("error"):
            return "Action failed - should try alternative approach"
        else:
            return "Action completed - proceeding to next step"
