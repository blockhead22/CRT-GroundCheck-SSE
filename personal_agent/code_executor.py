"""
Code Executor - Let the LLM write and run Python with retry loop
Executes code safely with timeouts and captures all output
"""

import subprocess
import sys
import tempfile
import os
import json
import traceback
from pathlib import Path
from datetime import datetime
from typing import Dict, Optional, List, Any
from dataclasses import dataclass, asdict
import threading
import queue

# Execution history stored in memory (could persist to DB)
EXECUTION_HISTORY: List[Dict] = []
MAX_HISTORY = 100


@dataclass
class ExecutionResult:
    """Result of a Python code execution"""
    success: bool
    code: str
    stdout: str
    stderr: str
    return_value: Optional[str]
    error_type: Optional[str]
    error_message: Optional[str]
    execution_time_ms: int
    attempt: int
    timestamp: str
    task_id: str


def execute_python_code(
    code: str,
    timeout_seconds: int = 30,
    task_id: Optional[str] = None,
    attempt: int = 1,
    working_dir: Optional[str] = None
) -> ExecutionResult:
    """
    Execute Python code in a subprocess with timeout.
    
    Args:
        code: Python code to execute
        timeout_seconds: Max execution time (default 30s)
        task_id: Unique ID for this task
        attempt: Which attempt this is (for retry tracking)
        working_dir: Directory to run code in
    
    Returns:
        ExecutionResult with stdout, stderr, success status
    """
    import time
    start_time = time.time()
    
    if not task_id:
        task_id = f"exec_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}"
    
    # Create a temp file for the code
    with tempfile.NamedTemporaryFile(
        mode='w', 
        suffix='.py', 
        delete=False,
        encoding='utf-8'
    ) as f:
        f.write(code)
        temp_file = f.name
    
    try:
        # Run in subprocess
        result = subprocess.run(
            [sys.executable, temp_file],
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            cwd=working_dir or os.getcwd(),
            env={**os.environ, 'PYTHONIOENCODING': 'utf-8'}
        )
        
        execution_time = int((time.time() - start_time) * 1000)
        
        exec_result = ExecutionResult(
            success=result.returncode == 0,
            code=code,
            stdout=result.stdout,
            stderr=result.stderr,
            return_value=None,
            error_type=None if result.returncode == 0 else "RuntimeError",
            error_message=result.stderr if result.returncode != 0 else None,
            execution_time_ms=execution_time,
            attempt=attempt,
            timestamp=datetime.utcnow().isoformat(),
            task_id=task_id
        )
        
    except subprocess.TimeoutExpired:
        execution_time = int((time.time() - start_time) * 1000)
        exec_result = ExecutionResult(
            success=False,
            code=code,
            stdout="",
            stderr=f"Execution timed out after {timeout_seconds} seconds",
            return_value=None,
            error_type="TimeoutError",
            error_message=f"Code took longer than {timeout_seconds}s to execute",
            execution_time_ms=execution_time,
            attempt=attempt,
            timestamp=datetime.utcnow().isoformat(),
            task_id=task_id
        )
    except Exception as e:
        execution_time = int((time.time() - start_time) * 1000)
        exec_result = ExecutionResult(
            success=False,
            code=code,
            stdout="",
            stderr=str(e),
            return_value=None,
            error_type=type(e).__name__,
            error_message=str(e),
            execution_time_ms=execution_time,
            attempt=attempt,
            timestamp=datetime.utcnow().isoformat(),
            task_id=task_id
        )
    finally:
        # Clean up temp file
        try:
            os.unlink(temp_file)
        except:
            pass
    
    # Store in history
    EXECUTION_HISTORY.append(asdict(exec_result))
    if len(EXECUTION_HISTORY) > MAX_HISTORY:
        EXECUTION_HISTORY.pop(0)
    
    return exec_result


class CodeWorkLoop:
    """
    Autonomous work loop that lets LLM write, execute, and retry code.
    
    The LLM describes a task, writes code, runs it, and if it fails,
    analyzes the error and tries again up to max_retries times.
    """
    
    def __init__(
        self, 
        llm_executor,  # The LLM executor to use for code generation
        max_retries: int = 3,
        timeout_seconds: int = 30
    ):
        self.llm = llm_executor
        self.max_retries = max_retries
        self.timeout = timeout_seconds
        self.current_task: Optional[Dict] = None
        self.task_history: List[Dict] = []
    
    async def run_task(
        self,
        task_description: str,
        context: Optional[str] = None,
        thread_id: Optional[str] = None
    ) -> Dict:
        """
        Run an autonomous code execution task.
        
        Args:
            task_description: What the LLM should accomplish
            context: Optional additional context
            thread_id: Thread ID for memory context
        
        Returns:
            Task result with all attempts
        """
        task_id = f"task_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        self.current_task = {
            "task_id": task_id,
            "description": task_description,
            "context": context,
            "attempts": [],
            "status": "running",
            "started_at": datetime.utcnow().isoformat()
        }
        
        for attempt in range(1, self.max_retries + 1):
            print(f"\n🔄 Attempt {attempt}/{self.max_retries}")
            
            # Build prompt for code generation
            prompt = self._build_code_prompt(
                task_description,
                context,
                self.current_task["attempts"]
            )
            
            # Ask LLM to write code
            llm_response = await self._generate_code(prompt, thread_id)
            code = self._extract_code(llm_response)
            
            if not code:
                self.current_task["attempts"].append({
                    "attempt": attempt,
                    "error": "Failed to extract code from LLM response",
                    "llm_response": llm_response
                })
                continue
            
            # Execute the code
            result = execute_python_code(
                code=code,
                timeout_seconds=self.timeout,
                task_id=task_id,
                attempt=attempt
            )
            
            self.current_task["attempts"].append({
                "attempt": attempt,
                "code": code,
                "result": asdict(result)
            })
            
            if result.success:
                self.current_task["status"] = "success"
                self.current_task["completed_at"] = datetime.utcnow().isoformat()
                break
            
            print(f"❌ Attempt {attempt} failed: {result.error_message}")
        
        else:
            # All retries exhausted
            self.current_task["status"] = "failed"
            self.current_task["completed_at"] = datetime.utcnow().isoformat()
        
        self.task_history.append(self.current_task)
        return self.current_task
    
    def _build_code_prompt(
        self,
        task: str,
        context: Optional[str],
        previous_attempts: List[Dict]
    ) -> str:
        """Build the prompt for code generation."""
        
        prompt = f"""You are a Python code writer. Write ONLY executable Python code to accomplish this task.

TASK: {task}
"""
        
        if context:
            prompt += f"\nCONTEXT: {context}\n"
        
        if previous_attempts:
            prompt += "\n--- PREVIOUS ATTEMPTS (learn from these errors) ---\n"
            for attempt in previous_attempts:
                if "code" in attempt and "result" in attempt:
                    result = attempt["result"]
                    prompt += f"\nAttempt {attempt['attempt']}:\n"
                    prompt += f"Code:\n```python\n{attempt['code']}\n```\n"
                    if not result["success"]:
                        prompt += f"ERROR: {result['error_type']}: {result['error_message']}\n"
                        if result["stderr"]:
                            prompt += f"STDERR: {result['stderr'][:500]}\n"
            prompt += "\n--- Fix the issues above ---\n"
        
        prompt += """
RULES:
1. Write ONLY Python code, no explanations
2. Use print() to show results
3. Handle errors gracefully
4. The code must be complete and runnable
5. Do not use input() - no interactive input

Respond with ONLY the Python code wrapped in ```python ... ```
"""
        return prompt
    
    async def _generate_code(self, prompt: str, thread_id: Optional[str]) -> str:
        """Ask LLM to generate code."""
        try:
            # Use the LLM executor
            response = await self.llm.generate(
                prompt=prompt,
                thread_id=thread_id or "code_executor",
                system_prompt="You are a Python code generator. Output ONLY valid Python code."
            )
            return response
        except Exception as e:
            return f"Error generating code: {e}"
    
    def _extract_code(self, response: str) -> Optional[str]:
        """Extract Python code from LLM response."""
        import re
        
        # Try to find ```python ... ``` blocks
        pattern = r'```python\s*(.*?)\s*```'
        matches = re.findall(pattern, response, re.DOTALL)
        
        if matches:
            return matches[0].strip()
        
        # Try ``` ... ``` blocks
        pattern = r'```\s*(.*?)\s*```'
        matches = re.findall(pattern, response, re.DOTALL)
        
        if matches:
            return matches[0].strip()
        
        # If response looks like code, use it directly
        if response.strip().startswith(('import ', 'from ', 'def ', 'class ', '#')):
            return response.strip()
        
        return None


# Simple synchronous version for direct use
def run_code_with_retry(
    code_or_task: str,
    is_task: bool = False,
    max_retries: int = 3,
    timeout: int = 30
) -> Dict:
    """
    Run code directly or as a task description.
    
    Args:
        code_or_task: Either Python code or a task description
        is_task: If True, treat input as task description (requires LLM)
        max_retries: Number of retry attempts
        timeout: Execution timeout in seconds
    
    Returns:
        Execution results
    """
    if not is_task:
        # Direct code execution with retry on failure
        task_id = f"direct_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        results = []
        
        for attempt in range(1, max_retries + 1):
            result = execute_python_code(
                code=code_or_task,
                timeout_seconds=timeout,
                task_id=task_id,
                attempt=attempt
            )
            results.append(asdict(result))
            
            if result.success:
                return {
                    "success": True,
                    "attempts": results,
                    "final_output": result.stdout
                }
        
        return {
            "success": False,
            "attempts": results,
            "final_error": results[-1]["error_message"] if results else "No attempts"
        }
    else:
        # Task-based execution requires LLM - return instruction
        return {
            "error": "Task-based execution requires LLM. Use CodeWorkLoop class."
        }


def get_execution_history(limit: int = 20) -> List[Dict]:
    """Get recent execution history."""
    return EXECUTION_HISTORY[-limit:]


def clear_execution_history():
    """Clear execution history."""
    EXECUTION_HISTORY.clear()


# Allowed imports whitelist for sandboxing (optional stricter mode)
SAFE_IMPORTS = {
    'json', 'math', 'random', 'datetime', 'collections', 
    'itertools', 'functools', 'string', 're', 'os.path',
    'pathlib', 'typing', 'dataclasses', 'enum', 'statistics',
    'requests', 'httpx', 'aiohttp',  # Allow HTTP
    'sqlite3',  # Allow DB
    'pandas', 'numpy',  # Data science
}


if __name__ == "__main__":
    # Test execution
    test_code = '''
import json
data = {"message": "Hello from code executor!", "status": "success"}
print(json.dumps(data, indent=2))
'''
    
    print("Testing code executor...")
    result = execute_python_code(test_code)
    
    print(f"\nSuccess: {result.success}")
    print(f"Output:\n{result.stdout}")
    if result.stderr:
        print(f"Errors:\n{result.stderr}")
    print(f"Time: {result.execution_time_ms}ms")
    
    # Test failure + retry
    print("\n" + "="*50)
    print("Testing retry on failure...")
    
    bad_code = '''
# This will fail
x = undefined_variable
print(x)
'''
    
    result = run_code_with_retry(bad_code, max_retries=2)
    print(f"Final success: {result['success']}")
    print(f"Attempts: {len(result['attempts'])}")
