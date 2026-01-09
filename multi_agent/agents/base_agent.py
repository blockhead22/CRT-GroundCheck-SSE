"""
Base Agent Class
All specialized agents inherit from this
"""

from abc import ABC, abstractmethod
from typing import Any
from ..task import Task


class BaseAgent(ABC):
    """
    Base class for all agents
    
    All agents must implement execute()
    """
    
    def __init__(self, name: str = None):
        """
        Initialize agent
        
        Args:
            name: Agent name (defaults to class name)
        """
        self.name = name or self.__class__.__name__
        self.context = {}
    
    @abstractmethod
    def execute(self, task: Task) -> Any:
        """
        Execute a task
        
        Args:
            task: Task to execute
        
        Returns:
            Task result (any type)
        
        Raises:
            Exception if task fails
        """
        raise NotImplementedError
    
    def set_context(self, key: str, value: Any):
        """Set context variable"""
        self.context[key] = value
    
    def get_context(self, key: str, default: Any = None) -> Any:
        """Get context variable"""
        return self.context.get(key, default)
    
    def log(self, message: str):
        """Log message"""
        print(f"  [{self.name}] {message}")
    
    def __str__(self) -> str:
        return f"{self.name}"
