"""
Agentic Loop - ReAct Pattern Implementation for CRT

This module implements autonomous agent behaviors:
- Tool orchestration (function calling)
- Multi-step planning
- Self-reflection and critique
- Proactive memory/research integration
- Automatic contradiction detection and resolution

Architecture:
- AgentLoop orchestrates thought → action → observation cycles
- ToolRegistry provides 10+ callable tools
- PlanningEngine breaks complex tasks into steps
- ReflectionEngine critiques outputs and detects errors

Integration with CRT:
- Uses CRT memory for context
- Triggers research automatically on low confidence
- Detects contradictions proactively
- Stores agent traces in memory with provenance
"""

from __future__ import annotations

import ast
import json
import operator
import re
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Literal, Optional

# Conditional imports
try:
    from personal_agent.crt_memory import CRTMemorySystem
    from personal_agent.research_engine import ResearchEngine
    from personal_agent.evidence_packet import EvidencePacket
    from personal_agent.ollama_client import get_ollama_client
except ImportError as e:
    print(f"Warning: Import failed in agent_loop.py: {e}")
    CRTMemorySystem = None
    ResearchEngine = None
    EvidencePacket = None
    get_ollama_client = None


class AgentAction(str, Enum):
    """Available agent actions."""
    SEARCH_MEMORY = "search_memory"
    SEARCH_RESEARCH = "search_research"
    STORE_MEMORY = "store_memory"
    CHECK_CONTRADICTION = "check_contradiction"
    CALCULATE = "calculate"
    READ_FILE = "read_file"
    LIST_FILES = "list_files"
    EXECUTE_CODE = "execute_code"  # Run Python code
    SYNTHESIZE = "synthesize"
    REFLECT = "reflect"
    PLAN = "plan"
    FINISH = "finish"


@dataclass
class ToolCall:
    """Represents a tool invocation."""
    tool: AgentAction
    args: dict[str, Any]
    reasoning: str  # Why the agent chose this tool


@dataclass
class ToolResult:
    """Result from tool execution."""
    tool: AgentAction
    success: bool
    result: Any
    error: Optional[str] = None


@dataclass
class AgentStep:
    """Single step in agent loop (thought → action → observation)."""
    step_num: int
    thought: str  # Agent's reasoning
    action: Optional[ToolCall] = None
    observation: Optional[ToolResult] = None
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class AgentTrace:
    """Complete trace of agent execution."""
    query: str
    steps: list[AgentStep] = field(default_factory=list)
    final_answer: Optional[str] = None
    success: bool = False
    error: Optional[str] = None
    started_at: datetime = field(default_factory=datetime.now)
    completed_at: Optional[datetime] = None

    def to_dict(self) -> dict:
        """Serialize trace."""
        return {
            "query": self.query,
            "steps": [
                {
                    "step_num": s.step_num,
                    "thought": s.thought,
                    "action": {
                        "tool": s.action.tool.value if s.action else None,
                        "args": s.action.args if s.action else None,
                        "reasoning": s.action.reasoning if s.action else None,
                    } if s.action else None,
                    "observation": {
                        "tool": s.observation.tool.value if s.observation else None,
                        "success": s.observation.success if s.observation else None,
                        "result": str(s.observation.result)[:500] if s.observation else None,  # Truncate
                        "error": s.observation.error if s.observation else None,
                    } if s.observation else None,
                    "timestamp": s.timestamp.isoformat(),
                }
                for s in self.steps
            ],
            "final_answer": self.final_answer,
            "success": self.success,
            "error": self.error,
            "started_at": self.started_at.isoformat(),
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
        }


class ToolRegistry:
    """Registry of available tools for the agent."""

    def __init__(
        self,
        memory_engine: Optional[CRTMemorySystem] = None,
        research_engine: Optional[ResearchEngine] = None,
        workspace_root: Optional[Path] = None,
    ):
        self.memory = memory_engine
        self.research = research_engine
        self.workspace = workspace_root or Path.cwd()
        self.llm_client: Optional[Any] = None  # Set by AgentLoop
        self._tools: dict[AgentAction, Callable] = self._register_tools()

    def _register_tools(self) -> dict[AgentAction, Callable]:
        """Register all available tools."""
        return {
            AgentAction.SEARCH_MEMORY: self._search_memory,
            AgentAction.SEARCH_RESEARCH: self._search_research,
            AgentAction.STORE_MEMORY: self._store_memory,
            AgentAction.CHECK_CONTRADICTION: self._check_contradiction,
            AgentAction.CALCULATE: self._calculate,
            AgentAction.READ_FILE: self._read_file,
            AgentAction.LIST_FILES: self._list_files,
            AgentAction.EXECUTE_CODE: self._execute_code,
            AgentAction.SYNTHESIZE: self._synthesize,
            AgentAction.REFLECT: self._reflect,
            AgentAction.PLAN: self._plan,
        }

    def execute(self, tool_call: ToolCall) -> ToolResult:
        """Execute a tool and return result."""
        try:
            if tool_call.tool not in self._tools:
                return ToolResult(
                    tool=tool_call.tool,
                    success=False,
                    result=None,
                    error=f"Unknown tool: {tool_call.tool}",
                )

            tool_fn = self._tools[tool_call.tool]
            result = tool_fn(**tool_call.args)

            return ToolResult(
                tool=tool_call.tool,
                success=True,
                result=result,
            )

        except Exception as e:
            return ToolResult(
                tool=tool_call.tool,
                success=False,
                result=None,
                error=str(e),
            )

    # Tool implementations
    def _search_memory(self, query: str, top_k: int = 5) -> dict:
        """Search CRT memory."""
        if not self.memory:
            return {"error": "Memory engine not available"}

        memories = self.memory.retrieve_with_context(query, limit=top_k)
        return {
            "found": len(memories),
            "memories": [
                {
                    "text": m["text"],
                    "trust": m["trust"],
                    "source": m["source"],
                    "created": m.get("created_at", "unknown"),
                }
                for m in memories
            ],
        }

    def _search_research(self, query: str, top_k: int = 3) -> dict:
        """Search local documents."""
        if not self.research:
            return {"error": "Research engine not available"}

        packet = self.research.research(query, max_results=top_k)
        return {
            "summary": packet.summary,
            "citations": [
                {
                    "quote": c.quote_text,
                    "source": c.source_url,
                }
                for c in packet.citations
            ],
        }

    def _store_memory(self, text: str, source: str = "AGENT", trust: float = 0.6) -> dict:
        """Store new memory."""
        if not self.memory:
            return {"error": "Memory engine not available"}

        mem_id = self.memory.store(
            text=text,
            source=source,
            trust=trust,
            metadata={"agent_generated": True},
        )
        return {"memory_id": mem_id, "stored": True}

    def _check_contradiction(self, statement: str) -> dict:
        """Check if statement contradicts existing high-trust memories."""
        if not self.memory:
            return {"error": "Memory engine not available"}

        # Retrieve related memories
        memories = self.memory.retrieve_with_context(statement, limit=10)
        high_trust = [m for m in memories if m["trust"] >= 0.7]

        if not high_trust:
            return {"contradiction": False, "reason": "No high-trust memories found"}

        # Check for semantic opposition using simple keyword negation detection
        statement_lower = statement.lower().strip()
        contradictions_found = []
        for mem in high_trust:
            mem_text = mem.get("text", "").lower().strip()
            # Detect negation patterns between statement and memory
            negation_words = {"not", "no longer", "never", "don't", "doesn't", "isn't", "aren't", "wasn't"}
            stmt_has_negation = any(nw in statement_lower for nw in negation_words)
            mem_has_negation = any(nw in mem_text for nw in negation_words)
            # If one negates and the other doesn't on similar topic, flag potential contradiction
            if stmt_has_negation != mem_has_negation:
                # Check for word overlap (shared topic)
                stmt_words = set(statement_lower.split())
                mem_words = set(mem_text.split())
                overlap = stmt_words & mem_words - negation_words - {"i", "a", "the", "is", "am", "was", "my"}
                if len(overlap) >= 2:
                    contradictions_found.append({
                        "memory_id": mem.get("memory_id", "unknown"),
                        "memory_text": mem.get("text", "")[:100],
                        "overlap_words": list(overlap)[:5],
                    })

        return {
            "contradiction": len(contradictions_found) > 0,
            "checked_against": len(high_trust),
            "contradictions": contradictions_found[:3],
        }

    def _calculate(self, expression: str) -> dict:
        """Safely evaluate math expressions using AST parsing (no eval)."""
        try:
            # Reject obviously dangerous input
            if any(kw in expression for kw in ("import", "exec", "eval", "__", "lambda", "open")):
                return {"error": "Expression contains forbidden keywords"}

            _SAFE_OPS = {
                ast.Add: operator.add, ast.Sub: operator.sub,
                ast.Mult: operator.mul, ast.Div: operator.truediv,
                ast.FloorDiv: operator.floordiv, ast.Mod: operator.mod,
                ast.Pow: operator.pow, ast.USub: operator.neg,
                ast.UAdd: operator.pos,
            }
            _SAFE_FUNCS = {"abs": abs, "min": min, "max": max, "sum": sum, "round": round}

            def _safe_eval(node):
                if isinstance(node, ast.Expression):
                    return _safe_eval(node.body)
                elif isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
                    return node.value
                elif isinstance(node, ast.BinOp) and type(node.op) in _SAFE_OPS:
                    left = _safe_eval(node.left)
                    right = _safe_eval(node.right)
                    if isinstance(node.op, ast.Pow) and right > 100:
                        raise ValueError("Exponent too large")
                    return _SAFE_OPS[type(node.op)](left, right)
                elif isinstance(node, ast.UnaryOp) and type(node.op) in _SAFE_OPS:
                    return _SAFE_OPS[type(node.op)](_safe_eval(node.operand))
                elif isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                    fname = node.func.id
                    if fname not in _SAFE_FUNCS:
                        raise ValueError(f"Function '{fname}' not allowed")
                    args = [_safe_eval(a) for a in node.args]
                    return _SAFE_FUNCS[fname](*args)
                else:
                    raise ValueError(f"Unsupported expression: {ast.dump(node)}")

            tree = ast.parse(expression.strip(), mode="eval")
            result = _safe_eval(tree)
            return {"result": result}
        except Exception as e:
            return {"error": f"Calculation failed: {e}"}

    def _read_file(self, path: str, max_lines: int = 100) -> dict:
        """Read file contents (sandboxed to workspace directory)."""
        try:
            file_path = Path(path)
            if not file_path.is_absolute():
                file_path = self.workspace / file_path

            # Security: resolve symlinks and verify the file is within workspace
            resolved = file_path.resolve()
            workspace_resolved = self.workspace.resolve()
            if not str(resolved).startswith(str(workspace_resolved)):
                return {"error": f"Access denied: path '{path}' is outside workspace"}

            if not resolved.exists():
                return {"error": f"File not found: {path}"}

            lines = resolved.read_text(encoding="utf-8", errors="ignore").splitlines()
            truncated = lines[:max_lines]

            return {
                "path": str(resolved),
                "lines": len(lines),
                "truncated": len(lines) > max_lines,
                "content": "\n".join(truncated),
            }
        except Exception as e:
            return {"error": str(e)}

    def _list_files(self, directory: str = ".", pattern: str = "*") -> dict:
        """List files in directory (sandboxed to workspace)."""
        try:
            dir_path = Path(directory)
            if not dir_path.is_absolute():
                dir_path = self.workspace / dir_path

            # Security: resolve symlinks and verify within workspace
            resolved = dir_path.resolve()
            workspace_resolved = self.workspace.resolve()
            if not str(resolved).startswith(str(workspace_resolved)):
                return {"error": f"Access denied: path '{directory}' is outside workspace"}

            if not resolved.exists():
                return {"error": f"Directory not found: {directory}"}

            files = list(resolved.glob(pattern))
            return {
                "directory": str(dir_path),
                "pattern": pattern,
                "count": len(files),
                "files": [str(f.relative_to(dir_path)) for f in files[:50]],  # Limit output
            }
        except Exception as e:
            return {"error": str(e)}

    def _execute_code(self, code: str, timeout: int = 30) -> dict:
        """Execute Python code and return results."""
        try:
            from personal_agent.code_executor import execute_python_code
            
            result = execute_python_code(
                code=code,
                timeout_seconds=timeout,
                working_dir=str(self.workspace)
            )
            
            return {
                "success": result.success,
                "stdout": result.stdout,
                "stderr": result.stderr,
                "error_type": result.error_type,
                "error_message": result.error_message,
                "execution_time_ms": result.execution_time_ms,
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    def _synthesize(self, pieces: list[str]) -> dict:
        """Combine multiple pieces of information."""
        return {
            "combined": " ".join(pieces),
            "piece_count": len(pieces),
        }

    def _reflect(self, action: str, result: Any) -> dict:
        """Reflect on action outcome."""
        # Simple reflection heuristic
        success_indicators = ["success", "found", "stored", "true"]
        failure_indicators = ["error", "failed", "not found", "false"]

        result_str = str(result).lower()
        likely_success = any(ind in result_str for ind in success_indicators)
        likely_failure = any(ind in result_str for ind in failure_indicators)

        if likely_failure:
            return {
                "assessment": "Action likely failed",
                "suggestion": "Try alternative approach or different tool",
            }
        elif likely_success:
            return {
                "assessment": "Action likely succeeded",
                "suggestion": "Proceed to next step",
            }
        else:
            return {
                "assessment": "Unclear outcome",
                "suggestion": "Verify result before proceeding",
            }

    def _plan(self, goal: str, constraints: Optional[list[str]] = None) -> dict:
        """Generate step-by-step plan."""
        # Placeholder - in production use LLM for planning
        return {
            "goal": goal,
            "constraints": constraints or [],
            "steps": [
                "1. Gather relevant information",
                "2. Analyze available data",
                "3. Synthesize findings",
                "4. Formulate answer",
            ],
            "note": "Using default plan template - LLM planning not implemented",
        }


class AgentLoop:
    """
    Main agent loop implementing ReAct pattern.
    
    Executes: Thought → Action → Observation cycles until task completion.
    """

    def __init__(
        self,
        tool_registry: ToolRegistry,
        max_steps: int = 10,
        llm_client: Optional[Any] = None,
        reasoning_engine: Optional[Any] = None,
    ):
        self.tools = tool_registry
        self.max_steps = max_steps
        self.llm = llm_client
        self.reasoning = reasoning_engine
        self.trace: Optional[AgentTrace] = None
        
        # Pass LLM to tools for finish action
        self.tools.llm_client = llm_client

    def run(self, query: str, context: Optional[dict] = None) -> AgentTrace:
        """
        Execute agent loop for given query.
        
        Args:
            query: User query/task
            context: Optional context dictionary
            
        Returns:
            AgentTrace with complete execution history
        """
        self.trace = AgentTrace(query=query)

        try:
            for step_num in range(1, self.max_steps + 1):
                step = self._execute_step(step_num, context)
                self.trace.steps.append(step)

                # Check if agent wants to finish
                if step.action and step.action.tool == AgentAction.FINISH:
                    # If finish with placeholder answer and we have LLM, generate real answer
                    placeholder_answer = step.action.args.get("answer", "")
                    if "placeholder" in placeholder_answer.lower() or "built-in knowledge" in placeholder_answer.lower():
                        if self.llm:
                            # Use LLM to answer the original query
                            real_answer = self._generate_llm_answer(self.trace.query)
                            self.trace.final_answer = real_answer
                        else:
                            self.trace.final_answer = "I don't have access to web search or enough local information to answer this general knowledge question."
                    else:
                        self.trace.final_answer = placeholder_answer
                    
                    self.trace.success = True
                    break

                # Check if step failed critically
                if step.observation and not step.observation.success:
                    error = step.observation.error
                    if "critical" in error.lower():
                        self.trace.error = error
                        self.trace.success = False
                        break

            else:
                # Max steps reached without finishing
                self.trace.error = f"Max steps ({self.max_steps}) reached without completion"
                self.trace.success = False
                self.trace.final_answer = "Task incomplete - reached step limit"

        except Exception as e:
            self.trace.error = str(e)
            self.trace.success = False
            self.trace.final_answer = f"Agent error: {e}"

        finally:
            self.trace.completed_at = datetime.now()

        return self.trace

    def _execute_step(self, step_num: int, context: Optional[dict]) -> AgentStep:
        """Execute single agent step."""
        step = AgentStep(step_num=step_num, thought="")

        # 1. THOUGHT: Decide what to do
        step.thought = self._generate_thought(step_num, context)

        # 2. ACTION: Choose and execute tool
        tool_call = self._choose_action(step.thought, context)
        if tool_call:
            step.action = tool_call

            # 3. OBSERVATION: Get result
            result = self.tools.execute(tool_call)
            step.observation = result

        return step

    def _generate_thought(self, step_num: int, context: Optional[dict]) -> str:
        """Generate agent's reasoning for this step."""
        if self.reasoning:
            # Use LLM reasoning
            current_situation = self._describe_current_situation()
            return self.reasoning.generate_thought(
                query=self.trace.query,
                trace=self.trace,
                current_situation=current_situation,
            )
        else:
            # Fallback heuristic
            if step_num == 1:
                return "Starting task execution - need to gather relevant information"
            elif step_num < 4:
                return "Analyzing gathered data to formulate answer"
            else:
                return "Synthesizing final response"

    def _choose_action(self, thought: str, context: Optional[dict]) -> Optional[ToolCall]:
        """Choose which tool to use based on thought."""
        if self.reasoning:
            # Use LLM reasoning for tool selection
            available_tools = list(AgentAction)
            return self.reasoning.select_action(thought, available_tools)
        else:
            # Fallback heuristic
            step_num = len(self.trace.steps) + 1

            if step_num == 1:
                return ToolCall(
                    tool=AgentAction.SEARCH_MEMORY,
                    args={"query": self.trace.query, "top_k": 5},
                    reasoning="Checking existing knowledge in memory",
                )
            elif step_num == 2:
                return ToolCall(
                    tool=AgentAction.SEARCH_RESEARCH,
                    args={"query": self.trace.query, "top_k": 3},
                    reasoning="Searching local documents for additional context",
                )
            elif step_num >= 3:
                return ToolCall(
                    tool=AgentAction.FINISH,
                    args={"answer": "Placeholder answer - LLM synthesis not implemented"},
                    reasoning="Sufficient information gathered - providing answer",
                )

            return None

    def _describe_current_situation(self) -> str:
        """Describe current state for reasoning."""
        if not self.trace.steps:
            return "Just starting the task"

        last_step = self.trace.steps[-1]
        if last_step.observation:
            if last_step.observation.success:
                return f"Last action ({last_step.action.tool.value}) succeeded. Ready for next step."
            else:
                return f"Last action failed: {last_step.observation.error}. Need alternative approach."
        else:
            return "Evaluating previous step"
    
    def _generate_llm_answer(self, query: str) -> str:
        """Generate answer using LLM's general knowledge."""
        if not self.llm:
            return "LLM not available for general knowledge queries."
        
        prompt = f"""Answer this question concisely using your general knowledge:

{query}

Provide a clear, accurate answer in 2-4 sentences."""

        try:
            response = self.llm.generate(prompt=prompt)
            answer = response.get("response", "").strip()
            return answer if answer else "Could not generate answer."
        except Exception as e:
            return f"Error generating answer: {e}"


# Convenience functions
def create_agent(
    memory_engine: Optional[CRTMemorySystem] = None,
    research_engine: Optional[ResearchEngine] = None,
    workspace_root: Optional[Path] = None,
    max_steps: int = 10,
) -> AgentLoop:
    """
    Create and configure an agent instance.
    
    Args:
        memory_engine: CRT memory engine
        research_engine: Research engine for local docs
        workspace_root: Root directory for file operations
        max_steps: Maximum agent steps before timeout
        
    Returns:
        Configured AgentLoop ready to run
    """
    tools = ToolRegistry(
        memory_engine=memory_engine,
        research_engine=research_engine,
        workspace_root=workspace_root,
    )

    llm_client = None
    reasoning_engine = None
    if get_ollama_client:
        try:
            llm_client = get_ollama_client()
            # Import reasoning engine lazily
            from personal_agent.agent_reasoning import AgentReasoning
            reasoning_engine = AgentReasoning(llm_client=llm_client)
        except Exception as e:
            print(f"Warning: Could not initialize reasoning engine: {e}")

    return AgentLoop(
        tool_registry=tools,
        max_steps=max_steps,
        llm_client=llm_client,
        reasoning_engine=reasoning_engine,
    )


def run_agent(
    query: str,
    memory_engine: Optional[CRTMemorySystem] = None,
    research_engine: Optional[ResearchEngine] = None,
    workspace_root: Optional[Path] = None,
    max_steps: int = 10,
) -> AgentTrace:
    """
    Convenience function to create and run agent in one call.
    
    Args:
        query: User query/task
        memory_engine: CRT memory engine
        research_engine: Research engine
        workspace_root: Workspace root directory
        max_steps: Maximum steps
        
    Returns:
        AgentTrace with execution history
    """
    agent = create_agent(
        memory_engine=memory_engine,
        research_engine=research_engine,
        workspace_root=workspace_root,
        max_steps=max_steps,
    )
    return agent.run(query)
