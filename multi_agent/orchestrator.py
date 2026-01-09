"""
Main Orchestrator
Coordinates task decomposition, agent routing, validation, and synthesis
"""

from typing import List, Dict, Any, Optional
from .task import Task, TaskResult
from .task_decomposer import TaskDecomposer
from .agent_router import AgentRouter
from .sse_validator import AgentValidator


class Orchestrator:
    """
    Main coordinator for multi-agent system
    
    Usage:
        orchestrator = Orchestrator()
        orchestrator.register_agents({
            "CodeAgent": CodeAgent(),
            "TestAgent": TestAgent(),
            ...
        })
        
        result = orchestrator.execute("Implement boundary test suite")
    """
    
    def __init__(self, workspace_path: str = "."):
        """
        Initialize orchestrator
        
        Args:
            workspace_path: Path to workspace root
        """
        self.workspace_path = workspace_path
        self.decomposer = TaskDecomposer()
        self.router = AgentRouter()
        self.validator = AgentValidator()
        self.context = {}
    
    def register_agents(self, agents: Dict[str, Any]):
        """
        Register agent instances
        
        Args:
            agents: Dict mapping agent_type -> agent instance
        """
        for agent_type, agent in agents.items():
            self.router.register_agent(agent_type, agent)
    
    def execute(self, user_request: str, context: dict = None) -> Dict[str, Any]:
        """
        Main execution pipeline
        
        Args:
            user_request: What the user wants done
            context: Additional context (phase, workspace state, etc.)
        
        Returns:
            Dict with results, validations, and synthesis
        """
        context = {**self.context, **(context or {})}
        
        print(f"\n{'='*60}")
        print(f"Orchestrator: Processing request")
        print(f"{'='*60}")
        print(f"Request: {user_request}\n")
        
        # 1. Decompose request into tasks
        print("Step 1: Task Decomposition")
        print("-" * 60)
        tasks = self.decomposer.decompose(user_request, context)
        self._print_tasks(tasks)
        
        # Show execution plan
        print("\n" + self.router.get_execution_plan(tasks))
        
        # 2. Execute tasks
        print(f"\n{'='*60}")
        print("Step 2: Task Execution")
        print("=" * 60)
        results = self.router.execute_tasks(tasks)
        self._print_results(results)
        
        # 3. Validate results
        print(f"\n{'='*60}")
        print("Step 3: Validation")
        print("=" * 60)
        violations = self._validate_results(results, tasks)
        self._print_violations(violations)
        
        # 4. Synthesize final output
        print(f"\n{'='*60}")
        print("Step 4: Result Synthesis")
        print("=" * 60)
        synthesis = self._synthesize(results, tasks, violations)
        
        return {
            "success": len(violations) == 0,
            "tasks": tasks,
            "results": results,
            "violations": violations,
            "synthesis": synthesis
        }
    
    def _validate_results(self, results: Dict[int, TaskResult], tasks: List[Task]) -> List[Dict]:
        """
        Validate agent outputs for contradictions and boundary violations
        
        Returns:
            List of violations
        """
        violations = []
        
        # Extract agent outputs
        agent_outputs = {}
        for task_id, result in results.items():
            if result.success:
                task = next(t for t in tasks if t.id == task_id)
                agent_type = task.agent_type
                
                if agent_type not in agent_outputs:
                    agent_outputs[agent_type] = []
                agent_outputs[agent_type].append(str(result.data))
        
        # Check for contradictions between agents
        agent_violations = self.validator.validate_agent_outputs(agent_outputs)
        violations.extend(agent_violations)
        
        # Check code against Phase 6 charter
        if "CodeAgent" in agent_outputs:
            code = "\n".join(agent_outputs["CodeAgent"])
            charter_violations = self.validator.validate_against_charter(code)
            violations.extend(charter_violations)
        
        return violations
    
    def _synthesize(self, results: Dict[int, TaskResult], tasks: List[Task], 
                    violations: List[Dict]) -> str:
        """
        Synthesize results into coherent output
        
        Returns:
            Human-readable synthesis
        """
        if violations:
            return self._synthesize_with_violations(results, tasks, violations)
        
        # No violations - synthesize normally
        lines = ["✅ All tasks completed successfully with no violations\n"]
        
        # Group results by agent type
        agent_results = {}
        for task_id, result in results.items():
            if result.success:
                task = next(t for t in tasks if t.id == task_id)
                agent_type = task.agent_type
                
                if agent_type not in agent_results:
                    agent_results[agent_type] = []
                agent_results[agent_type].append({
                    "task": task.description,
                    "result": result.data
                })
        
        # Format by agent
        for agent_type, agent_data in agent_results.items():
            lines.append(f"\n[{agent_type}]")
            for item in agent_data:
                lines.append(f"  ✓ {item['task'][:60]}")
                if item['result']:
                    lines.append(f"    → {str(item['result'])[:80]}")
        
        return "\n".join(lines)
    
    def _synthesize_with_violations(self, results: Dict[int, TaskResult], 
                                    tasks: List[Task], violations: List[Dict]) -> str:
        """Synthesize when violations detected"""
        lines = [
            "🛑 VIOLATIONS DETECTED - Tasks completed but validation failed\n",
            f"Total violations: {len(violations)}\n"
        ]
        
        # Group violations by type
        by_type = {}
        for v in violations:
            vtype = v.get("type", "unknown")
            if vtype not in by_type:
                by_type[vtype] = []
            by_type[vtype].append(v)
        
        for vtype, vlist in by_type.items():
            lines.append(f"\n{vtype.upper()}:")
            for v in vlist:
                lines.append(f"  - {v.get('message', str(v))}")
        
        lines.append("\n" + "="*60)
        lines.append("RECOMMENDATION: Fix violations before proceeding")
        
        return "\n".join(lines)
    
    def _print_tasks(self, tasks: List[Task]):
        """Print task list"""
        for task in tasks:
            deps = f" (depends on: {task.dependencies})" if task.dependencies else ""
            print(f"  Task {task.id}: [{task.agent_type}] {task.description[:60]}{deps}")
    
    def _print_results(self, results: Dict[int, TaskResult]):
        """Print execution results"""
        for task_id in sorted(results.keys()):
            result = results[task_id]
            status = "✓" if result.success else "✗"
            print(f"  {status} Task {task_id}: {result.success}")
            if result.error:
                print(f"      Error: {result.error}")
    
    def _print_violations(self, violations: List[Dict]):
        """Print validation violations"""
        if not violations:
            print("  ✓ No violations detected")
        else:
            print(f"  ⚠️  {len(violations)} violation(s) detected:")
            for v in violations:
                print(f"    - {v.get('type', 'unknown')}: {v.get('message', str(v))}")
    
    def set_context(self, key: str, value: Any):
        """Update workspace context"""
        self.context[key] = value
    
    def get_context(self) -> dict:
        """Get current workspace context"""
        return self.context.copy()
