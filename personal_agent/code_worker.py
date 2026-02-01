"""
Background Code Worker - Processes code execution tasks autonomously.

This worker runs in the background and processes code execution tasks
from a queue. The LLM can submit tasks, and the worker will:
1. Execute the code
2. If it fails, have the LLM fix and retry
3. Store results

Can be started as a background thread or standalone process.
"""

import asyncio
import json
import queue
import threading
import time
from dataclasses import dataclass, asdict, field
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, List, Any, Callable
import logging

logger = logging.getLogger(__name__)

# Task queue for background processing
TASK_QUEUE: queue.Queue = queue.Queue()
TASK_RESULTS: Dict[str, Dict] = {}


@dataclass
class CodeTask:
    """A code execution task."""
    task_id: str
    task_type: str  # 'direct' | 'llm_task'
    code: Optional[str] = None
    task_description: Optional[str] = None
    context: Optional[str] = None
    max_retries: int = 3
    timeout_seconds: int = 30
    thread_id: Optional[str] = None
    priority: int = 0  # Higher = more urgent
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    status: str = "pending"
    

class BackgroundCodeWorker:
    """
    Background worker that processes code tasks.
    
    Can run autonomously, picking up tasks and executing them.
    Integrates with the LLM for task-based code generation.
    """
    
    def __init__(
        self,
        llm_executor = None,
        poll_interval: float = 1.0,
        max_concurrent: int = 2
    ):
        self.llm = llm_executor
        self.poll_interval = poll_interval
        self.max_concurrent = max_concurrent
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._active_tasks: Dict[str, CodeTask] = {}
    
    def start(self):
        """Start the background worker."""
        if self._running:
            return
        
        self._running = True
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()
        logger.info("Background code worker started")
    
    def stop(self):
        """Stop the background worker."""
        self._running = False
        if self._thread:
            self._thread.join(timeout=5.0)
        logger.info("Background code worker stopped")
    
    def _run_loop(self):
        """Main worker loop."""
        while self._running:
            try:
                # Check for new tasks
                if len(self._active_tasks) < self.max_concurrent:
                    try:
                        task = TASK_QUEUE.get_nowait()
                        self._process_task(task)
                    except queue.Empty:
                        pass
                
                time.sleep(self.poll_interval)
                
            except Exception as e:
                logger.error(f"Worker loop error: {e}")
                time.sleep(1)
    
    def _process_task(self, task: CodeTask):
        """Process a single task."""
        task.status = "running"
        self._active_tasks[task.task_id] = task
        
        try:
            if task.task_type == "direct":
                result = self._execute_direct(task)
            elif task.task_type == "llm_task":
                result = self._execute_llm_task(task)
            else:
                result = {"error": f"Unknown task type: {task.task_type}"}
            
            TASK_RESULTS[task.task_id] = {
                "task": asdict(task),
                "result": result,
                "completed_at": datetime.utcnow().isoformat()
            }
            
            task.status = "completed" if result.get("success") else "failed"
            
        except Exception as e:
            TASK_RESULTS[task.task_id] = {
                "task": asdict(task),
                "result": {"error": str(e), "success": False},
                "completed_at": datetime.utcnow().isoformat()
            }
            task.status = "failed"
        
        finally:
            del self._active_tasks[task.task_id]
    
    def _execute_direct(self, task: CodeTask) -> Dict:
        """Execute code directly."""
        from personal_agent.code_executor import run_code_with_retry
        
        return run_code_with_retry(
            code_or_task=task.code,
            is_task=False,
            max_retries=task.max_retries,
            timeout=task.timeout_seconds
        )
    
    def _execute_llm_task(self, task: CodeTask) -> Dict:
        """Execute a task using LLM to generate code."""
        if not self.llm:
            return {"error": "LLM not available for task execution", "success": False}
        
        # Run async task in sync context
        loop = asyncio.new_event_loop()
        try:
            from personal_agent.code_executor import CodeWorkLoop
            
            work_loop = CodeWorkLoop(
                llm_executor=self.llm,
                max_retries=task.max_retries,
                timeout_seconds=task.timeout_seconds
            )
            
            result = loop.run_until_complete(
                work_loop.run_task(
                    task_description=task.task_description,
                    context=task.context,
                    thread_id=task.thread_id
                )
            )
            
            return {
                "success": result.get("status") == "success",
                **result
            }
        finally:
            loop.close()


# Global worker instance
_worker: Optional[BackgroundCodeWorker] = None


def get_code_worker(llm_executor=None) -> BackgroundCodeWorker:
    """Get or create the background worker."""
    global _worker
    if _worker is None:
        _worker = BackgroundCodeWorker(llm_executor=llm_executor)
    elif llm_executor and _worker.llm is None:
        _worker.llm = llm_executor
    return _worker


def submit_code_task(
    code: Optional[str] = None,
    task_description: Optional[str] = None,
    context: Optional[str] = None,
    max_retries: int = 3,
    timeout: int = 30,
    priority: int = 0,
    thread_id: Optional[str] = None
) -> str:
    """
    Submit a code task for background execution.
    
    Either provide `code` for direct execution, or `task_description`
    for LLM-powered code generation.
    
    Returns task_id for tracking.
    """
    task_id = f"bg_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}"
    
    if code:
        task = CodeTask(
            task_id=task_id,
            task_type="direct",
            code=code,
            max_retries=max_retries,
            timeout_seconds=timeout,
            priority=priority
        )
    elif task_description:
        task = CodeTask(
            task_id=task_id,
            task_type="llm_task",
            task_description=task_description,
            context=context,
            max_retries=max_retries,
            timeout_seconds=timeout,
            thread_id=thread_id,
            priority=priority
        )
    else:
        raise ValueError("Must provide either code or task_description")
    
    TASK_QUEUE.put(task)
    return task_id


def get_task_result(task_id: str) -> Optional[Dict]:
    """Get result of a completed task."""
    return TASK_RESULTS.get(task_id)


def get_pending_tasks() -> List[Dict]:
    """Get list of pending tasks."""
    tasks = []
    # Peek at queue without removing
    with TASK_QUEUE.mutex:
        for task in list(TASK_QUEUE.queue):
            tasks.append(asdict(task))
    return tasks


def get_worker_status() -> Dict:
    """Get status of the background worker."""
    worker = get_code_worker()
    return {
        "running": worker._running,
        "active_tasks": len(worker._active_tasks),
        "pending_tasks": TASK_QUEUE.qsize(),
        "completed_tasks": len(TASK_RESULTS)
    }


if __name__ == "__main__":
    # Demo: Start worker and submit tasks
    print("Starting background code worker...")
    
    worker = get_code_worker()
    worker.start()
    
    # Submit some test tasks
    task1 = submit_code_task(code='print("Hello from background!")')
    print(f"Submitted task: {task1}")
    
    task2 = submit_code_task(code='import json; print(json.dumps({"status": "ok"}))')
    print(f"Submitted task: {task2}")
    
    # Wait for completion
    print("Waiting for tasks...")
    time.sleep(5)
    
    # Check results
    print("\n--- Results ---")
    for task_id in [task1, task2]:
        result = get_task_result(task_id)
        if result:
            success = result["result"].get("success", False)
            print(f"{task_id}: {'✓' if success else '✗'}")
    
    print("\n--- Worker Status ---")
    print(json.dumps(get_worker_status(), indent=2))
    
    worker.stop()
