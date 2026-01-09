"""
Agent Router
Routes tasks to appropriate agents and manages parallel execution
"""

from typing import List, Dict
from concurrent.futures import ThreadPoolExecutor, as_completed
from .task import Task, TaskStatus, TaskResult


class AgentRouter:
    """
    Routes tasks to agents and manages execution
    
    Key features:
    - Respects task dependencies
    - Parallelizes independent tasks
    - Groups tasks by agent type (same agent can't run parallel)
    """
    
    def __init__(self, agents: Dict[str, 'BaseAgent'] = None):
        """
        Initialize router with available agents
        
        Args:
            agents: Dict mapping agent_type -> agent instance
        """
        self.agents = agents or {}
        self.max_parallel = 5  # Max parallel tasks
    
    def register_agent(self, agent_type: str, agent: 'BaseAgent'):
        """Register a new agent type"""
        self.agents[agent_type] = agent
    
    def execute_tasks(self, tasks: List[Task]) -> Dict[int, TaskResult]:
        """
        Execute all tasks respecting dependencies
        
        Returns:
            Dict mapping task_id -> TaskResult
        """
        results = {}
        remaining_tasks = tasks.copy()
        
        while remaining_tasks:
            # Find tasks ready to execute
            completed_ids = {task.id for task in tasks if task.status == TaskStatus.COMPLETED}
            ready_tasks = [t for t in remaining_tasks if t.is_ready(completed_ids)]
            
            if not ready_tasks:
                # Check for circular dependencies
                if remaining_tasks:
                    raise ValueError(f"Circular dependency detected in tasks: {[t.id for t in remaining_tasks]}")
                break
            
            # Execute ready tasks (parallel where possible)
            batch_results = self._execute_parallel(ready_tasks)
            
            # Update task statuses and results
            for task_id, result in batch_results.items():
                task = next(t for t in tasks if t.id == task_id)
                if result.success:
                    task.mark_completed(result.data)
                else:
                    task.mark_failed(result.error)
                results[task_id] = result
            
            # Remove completed/failed tasks
            remaining_tasks = [t for t in remaining_tasks 
                             if t.status not in (TaskStatus.COMPLETED, TaskStatus.FAILED)]
        
        return results
    
    def _execute_parallel(self, tasks: List[Task]) -> Dict[int, TaskResult]:
        """
        Execute tasks in parallel where possible
        
        Constraint: Same agent type cannot run multiple tasks simultaneously
        (to prevent race conditions and context pollution)
        """
        # Group by agent type
        grouped = self._group_by_agent(tasks)
        
        results = {}
        
        # Execute each agent type's tasks sequentially
        # But different agent types run in parallel
        with ThreadPoolExecutor(max_workers=min(len(grouped), self.max_parallel)) as executor:
            future_to_agent = {}
            
            for agent_type, agent_tasks in grouped.items():
                # Submit sequential execution of this agent's tasks
                future = executor.submit(self._execute_agent_tasks, agent_type, agent_tasks)
                future_to_agent[future] = agent_type
            
            # Collect results
            for future in as_completed(future_to_agent):
                agent_type = future_to_agent[future]
                try:
                    agent_results = future.result()
                    results.update(agent_results)
                except Exception as e:
                    print(f"Error executing {agent_type} tasks: {e}")
        
        return results
    
    def _execute_agent_tasks(self, agent_type: str, tasks: List[Task]) -> Dict[int, TaskResult]:
        """Execute all tasks for a specific agent type sequentially"""
        results = {}
        
        agent = self.agents.get(agent_type)
        if not agent:
            # Agent not registered - return errors
            for task in tasks:
                results[task.id] = TaskResult(
                    task_id=task.id,
                    success=False,
                    data=None,
                    error=f"Agent type '{agent_type}' not registered"
                )
            return results
        
        # Execute each task sequentially
        for task in tasks:
            task.status = TaskStatus.IN_PROGRESS
            try:
                result_data = agent.execute(task)
                results[task.id] = TaskResult(
                    task_id=task.id,
                    success=True,
                    data=result_data,
                    metadata={"agent_type": agent_type}
                )
            except Exception as e:
                results[task.id] = TaskResult(
                    task_id=task.id,
                    success=False,
                    data=None,
                    error=str(e),
                    metadata={"agent_type": agent_type}
                )
        
        return results
    
    def _group_by_agent(self, tasks: List[Task]) -> Dict[str, List[Task]]:
        """Group tasks by agent type"""
        grouped = {}
        for task in tasks:
            if task.agent_type not in grouped:
                grouped[task.agent_type] = []
            grouped[task.agent_type].append(task)
        return grouped
    
    def get_execution_plan(self, tasks: List[Task]) -> str:
        """
        Generate human-readable execution plan
        
        Returns:
            Formatted string showing task execution order
        """
        lines = ["Execution Plan:", "=" * 50]
        
        # Simulate execution to show order
        completed_ids = set()
        wave = 0
        remaining = tasks.copy()
        
        while remaining:
            ready = [t for t in remaining if t.is_ready(completed_ids)]
            if not ready:
                break
            
            wave += 1
            lines.append(f"\nWave {wave} (Parallel):")
            for task in ready:
                lines.append(f"  [{task.agent_type}] {task.description[:60]}")
                completed_ids.add(task.id)
            
            remaining = [t for t in remaining if t.id not in completed_ids]
        
        if remaining:
            lines.append(f"\n⚠️  Blocked tasks (circular dependency?):")
            for task in remaining:
                lines.append(f"  Task {task.id}: {task.description[:60]}")
        
        return "\n".join(lines)
