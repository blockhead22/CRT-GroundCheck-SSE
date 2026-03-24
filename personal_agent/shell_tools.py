"""
Layer 3-4 — Shell and git execution tools.

Provides execute_command() and execute_git() with path enforcement
and blocked-command safety checks.
"""

import logging
import re
import subprocess
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from personal_agent.file_tools import _check_path_allowed

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Blocked commands — refuse to execute destructive operations
# ---------------------------------------------------------------------------

_BLOCKED_PATTERNS = [
    re.compile(r"\brm\s+-rf\s+/\s*$", re.IGNORECASE),
    re.compile(r"\brm\s+-rf\s+/\s", re.IGNORECASE),
    re.compile(r"\bformat\s+[A-Za-z]:", re.IGNORECASE),
    re.compile(r"\bdel\s+/s\s+/q\s+[A-Za-z]:\\", re.IGNORECASE),
    re.compile(r"\bshutdown\b", re.IGNORECASE),
    re.compile(r"\bmkfs\b", re.IGNORECASE),
    re.compile(r">\s*/dev/sd[a-z]", re.IGNORECASE),
    re.compile(r"\bdd\s+.*of=/dev/sd", re.IGNORECASE),
    re.compile(r"\brm\s+-rf\s+\*\s*$", re.IGNORECASE),
    re.compile(r"\b(rd|rmdir)\s+/s\s+/q\s+[A-Za-z]:\\", re.IGNORECASE),
]

_MAX_OUTPUT_CHARS = 5000


def _is_blocked(command: str) -> Optional[str]:
    """Check if a command matches any blocked pattern. Returns reason or None."""
    for pattern in _BLOCKED_PATTERNS:
        if pattern.search(command):
            return f"Blocked: command matches destructive pattern '{pattern.pattern}'"
    return None


# ---------------------------------------------------------------------------
# execute_command
# ---------------------------------------------------------------------------

def execute_command(
    command: str,
    cwd: Optional[str] = None,
    timeout: int = 30,
) -> Dict[str, Any]:
    """Run a shell command. Returns structured result with stdout/stderr.

    Validates cwd against allowed paths and blocks destructive commands.
    Truncates stdout/stderr to 5000 chars each.
    """
    # Check blocked commands
    blocked = _is_blocked(command)
    if blocked:
        logger.warning("[SHELL_TOOLS] Blocked command: %s", command)
        return {"error": blocked, "command": command, "tool": "shell_exec"}

    # Validate cwd
    work_dir = cwd or "D:/AI_round2"
    err = _check_path_allowed(work_dir)
    if err:
        return {"error": err, "command": command, "tool": "shell_exec"}

    resolved_cwd = str(Path(work_dir).resolve()).replace("\\", "/")

    t0 = time.monotonic()
    try:
        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=resolved_cwd,
        )
        duration_ms = round((time.monotonic() - t0) * 1000)

        stdout = result.stdout or ""
        stderr = result.stderr or ""
        stdout_truncated = len(stdout) > _MAX_OUTPUT_CHARS
        stderr_truncated = len(stderr) > _MAX_OUTPUT_CHARS
        if stdout_truncated:
            stdout = stdout[:_MAX_OUTPUT_CHARS] + f"\n... (truncated, {len(result.stdout)} total chars)"
        if stderr_truncated:
            stderr = stderr[:_MAX_OUTPUT_CHARS] + f"\n... (truncated, {len(result.stderr)} total chars)"

        logger.info("[SHELL_TOOLS] execute_command '%s' — exit=%d, %dms",
                    command[:80], result.returncode, duration_ms)

        return {
            "command": command,
            "exit_code": result.returncode,
            "stdout": stdout,
            "stderr": stderr,
            "duration_ms": duration_ms,
            "cwd": resolved_cwd,
            "tool": "shell_exec",
        }
    except subprocess.TimeoutExpired:
        duration_ms = round((time.monotonic() - t0) * 1000)
        logger.warning("[SHELL_TOOLS] Command timed out after %ds: %s", timeout, command[:80])
        return {
            "error": f"Command timed out after {timeout}s",
            "command": command,
            "duration_ms": duration_ms,
            "cwd": resolved_cwd,
            "tool": "shell_exec",
        }
    except Exception as e:
        logger.warning("[SHELL_TOOLS] Command failed: %s — %s", command[:80], e)
        return {
            "error": str(e),
            "command": command,
            "cwd": resolved_cwd,
            "tool": "shell_exec",
        }


# ---------------------------------------------------------------------------
# execute_git
# ---------------------------------------------------------------------------

def execute_git(
    args: List[str],
    cwd: str,
    timeout: int = 30,
) -> Dict[str, Any]:
    """Run a git command. Wrapper around execute_command with validation.

    args: list of git arguments, e.g. ["commit", "-m", "update"]
    cwd: project directory (must be in allowed paths)
    """
    err = _check_path_allowed(cwd)
    if err:
        return {"error": err, "command": f"git {' '.join(args)}", "tool": "git"}

    resolved_cwd = str(Path(cwd).resolve()).replace("\\", "/")
    command = "git " + " ".join(args)

    t0 = time.monotonic()
    try:
        result = subprocess.run(
            ["git"] + args,
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=resolved_cwd,
        )
        duration_ms = round((time.monotonic() - t0) * 1000)

        stdout = result.stdout or ""
        stderr = result.stderr or ""
        if len(stdout) > _MAX_OUTPUT_CHARS:
            stdout = stdout[:_MAX_OUTPUT_CHARS] + f"\n... (truncated)"
        if len(stderr) > _MAX_OUTPUT_CHARS:
            stderr = stderr[:_MAX_OUTPUT_CHARS] + f"\n... (truncated)"

        logger.info("[SHELL_TOOLS] execute_git '%s' — exit=%d, %dms",
                    command[:80], result.returncode, duration_ms)

        return {
            "command": command,
            "exit_code": result.returncode,
            "stdout": stdout,
            "stderr": stderr,
            "duration_ms": duration_ms,
            "cwd": resolved_cwd,
            "tool": "git",
        }
    except subprocess.TimeoutExpired:
        duration_ms = round((time.monotonic() - t0) * 1000)
        return {
            "error": f"git command timed out after {timeout}s",
            "command": command,
            "duration_ms": duration_ms,
            "cwd": resolved_cwd,
            "tool": "git",
        }
    except FileNotFoundError:
        return {
            "error": "git not found on PATH",
            "command": command,
            "cwd": resolved_cwd,
            "tool": "git",
        }
    except Exception as e:
        return {
            "error": str(e),
            "command": command,
            "cwd": resolved_cwd,
            "tool": "git",
        }
