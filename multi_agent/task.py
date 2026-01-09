"""
Task representation and management
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import List, Any, Optional


class TaskStatus(Enum):
    """Task execution status"""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    BLOCKED = "blocked"  # Dependencies not met


@dataclass
class Task:
    """
    Represents a unit of work for an agent
    
    Example:
        Task(
            id=1,
            agent_type="CodeAgent",
            description="Implement SSEClient safe wrapper",
            dependencies=[],
            context={"phase": "Phase 6", "week": 1}
        )
    """
    id: int
    agent_type: str
    description: str
    dependencies: List[int] = field(default_factory=list)
    context: dict = field(default_factory=dict)
    status: TaskStatus = TaskStatus.PENDING
    result: Optional[Any] = None
    error: Optional[str] = None
    
    def is_ready(self, completed_task_ids: set[int]) -> bool:
        """Check if all dependencies are completed"""
        return all(dep_id in completed_task_ids for dep_id in self.dependencies)
    
    def mark_completed(self, result: Any):
        """Mark task as successfully completed"""
        self.status = TaskStatus.COMPLETED
        self.result = result
    
    def mark_failed(self, error: str):
        """Mark task as failed"""
        self.status = TaskStatus.FAILED
        self.error = error
    
    def __str__(self) -> str:
        return f"Task({self.id}, {self.agent_type}, {self.status.value}): {self.description[:50]}"


@dataclass
class TaskResult:
    """Result from task execution"""
    task_id: int
    success: bool
    data: Any
    error: Optional[str] = None
    metadata: dict = field(default_factory=dict)
