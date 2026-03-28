"""
Scheduled Tasks System - Time-based job execution for CRT.

Features:
- Schedule tasks to run at specific times (reminders, jobs, etc.)
- Natural language time parsing ("tomorrow at 5pm", "in 2 hours")
- Background loop that checks for and executes due tasks
- Integration with chat for "remind me..." parsing
"""

import json
import logging
import re
import sqlite3
import threading
import time
from dataclasses import dataclass, asdict, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

from personal_agent.db_utils import get_db_connection
from enum import Enum

logger = logging.getLogger(__name__)


class TaskType(str, Enum):
    REMINDER = "reminder"  # Send a message to chat
    SCHEDULED_JOB = "scheduled_job"  # Run a background job
    THOUGHT = "thought"  # AI posting a thought to Ledger
    CUSTOM = "custom"  # Custom callback


@dataclass
class ScheduledTask:
    """A task scheduled to run at a specific time."""
    task_id: str
    task_type: str
    scheduled_at: float  # Unix timestamp
    thread_id: str
    payload: Dict[str, Any]
    created_at: float = field(default_factory=time.time)
    status: str = "pending"  # pending, completed, cancelled, failed
    completed_at: Optional[float] = None
    error: Optional[str] = None
    recurrence: Optional[str] = None  # None, "daily", "weekly", etc.
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
    
    @staticmethod
    def from_dict(data: Dict[str, Any]) -> "ScheduledTask":
        return ScheduledTask(
            task_id=data["task_id"],
            task_type=data["task_type"],
            scheduled_at=float(data["scheduled_at"]),
            thread_id=data["thread_id"],
            payload=data.get("payload", {}),
            created_at=float(data.get("created_at", time.time())),
            status=data.get("status", "pending"),
            completed_at=data.get("completed_at"),
            error=data.get("error"),
            recurrence=data.get("recurrence"),
        )
    
    def is_due(self) -> bool:
        """Check if task is due for execution."""
        return self.status == "pending" and time.time() >= self.scheduled_at
    
    def time_until(self) -> float:
        """Seconds until task is due (negative if overdue)."""
        return self.scheduled_at - time.time()
    
    def formatted_time(self) -> str:
        """Human-readable scheduled time."""
        dt = datetime.fromtimestamp(self.scheduled_at)
        return dt.strftime("%A, %B %d at %I:%M %p")


# ============================================================================
# Natural Language Time Parser
# ============================================================================

_WORD_NUMBERS: Dict[str, int] = {
    "one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
    "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10,
    "eleven": 11, "twelve": 12, "thirteen": 13, "fourteen": 14,
    "fifteen": 15, "twenty": 20, "thirty": 30, "forty": 40,
    "forty-five": 45, "an": 1, "a": 1, "half": 30,
}


def _normalize_word_numbers(text: str) -> str:
    """Replace word-form numbers with digits so regex patterns can match.

    Handles:
      - "in two minutes" -> "in 2 minutes"
      - "in a minute"    -> "in 1 minute"
      - "in an hour"     -> "in 1 hour"
      - "in half an hour" -> "in 30 minutes"
    """
    # Special case: "half an hour" / "half hour"
    text = re.sub(r"\bhalf\s+(?:an?\s+)?hour\b", "30 minutes", text)
    # "a couple" -> "2"
    text = re.sub(r"\ba\s+couple\s+(?:of\s+)?", "2 ", text)
    # "a few" -> "3" (reasonable default)
    text = re.sub(r"\ba\s+few\s+", "3 ", text)
    # Replace "in a minute" / "in an hour" etc.
    text = re.sub(
        r"\b(in\s+)an?\s+(minute|min|hour|hr|day|week|second|sec)\b",
        r"\g<1>1 \2",
        text,
    )
    # Replace standalone word numbers adjacent to time units
    for word, digit in _WORD_NUMBERS.items():
        text = re.sub(
            rf"\b{re.escape(word)}\s+(minute|min|hour|hr|day|week|second|sec)s?\b",
            rf"{digit} \1",
            text,
        )
    return text


def parse_natural_time(text: str, reference_time: Optional[datetime] = None) -> Optional[datetime]:
    """
    Parse natural language time expressions into datetime.

    Supports:
    - "in X minutes/hours/days"
    - "tomorrow at 5pm"
    - "next monday at 9am"
    - "at 3:30pm"
    - "tonight at 8"
    - "this afternoon"
    - "in 2 hours and 30 minutes"
    - "in two minutes" (word-form numbers)
    - "in a minute", "in an hour", "in half an hour"

    Returns None if parsing fails.
    """
    if reference_time is None:
        reference_time = datetime.now()

    text = _normalize_word_numbers(text.lower().strip())
    
    # Pattern: "in X minutes/hours/days/weeks"
    in_pattern = r"in\s+(\d+)\s*(minute|min|hour|hr|day|week|second|sec)s?"
    match = re.search(in_pattern, text)
    if match:
        amount = int(match.group(1))
        unit = match.group(2)
        if unit in ("minute", "min"):
            return reference_time + timedelta(minutes=amount)
        elif unit in ("hour", "hr"):
            return reference_time + timedelta(hours=amount)
        elif unit == "day":
            return reference_time + timedelta(days=amount)
        elif unit == "week":
            return reference_time + timedelta(weeks=amount)
        elif unit in ("second", "sec"):
            return reference_time + timedelta(seconds=amount)
    
    # Pattern: "in X hours and Y minutes"
    complex_pattern = r"in\s+(\d+)\s*(?:hour|hr)s?\s*(?:and)?\s*(\d+)\s*(?:minute|min)s?"
    match = re.search(complex_pattern, text)
    if match:
        hours = int(match.group(1))
        minutes = int(match.group(2))
        return reference_time + timedelta(hours=hours, minutes=minutes)
    
    # Pattern: "tomorrow at X"
    if "tomorrow" in text:
        tomorrow = reference_time + timedelta(days=1)
        time_match = re.search(r"(\d{1,2})(?::(\d{2}))?\s*(am|pm)?", text)
        if time_match:
            hour = int(time_match.group(1))
            minute = int(time_match.group(2) or 0)
            ampm = time_match.group(3)
            if ampm == "pm" and hour < 12:
                hour += 12
            elif ampm == "am" and hour == 12:
                hour = 0
            return tomorrow.replace(hour=hour, minute=minute, second=0, microsecond=0)
        return tomorrow.replace(hour=9, minute=0, second=0, microsecond=0)  # Default 9am
    
    # Pattern: "today at X" or "at X"
    time_match = re.search(r"(?:today\s+)?at\s+(\d{1,2})(?::(\d{2}))?\s*(am|pm)?", text)
    if time_match:
        hour = int(time_match.group(1))
        minute = int(time_match.group(2) or 0)
        ampm = time_match.group(3)
        if ampm == "pm" and hour < 12:
            hour += 12
        elif ampm == "am" and hour == 12:
            hour = 0
        elif ampm is None and hour < 12 and hour < reference_time.hour:
            # Assume PM if no AM/PM and hour has passed
            hour += 12
        result = reference_time.replace(hour=hour, minute=minute, second=0, microsecond=0)
        if result < reference_time:
            result += timedelta(days=1)  # If time passed, assume tomorrow
        return result
    
    # Pattern: "tonight at X"
    if "tonight" in text:
        time_match = re.search(r"(\d{1,2})(?::(\d{2}))?", text)
        if time_match:
            hour = int(time_match.group(1))
            minute = int(time_match.group(2) or 0)
            if hour < 12:
                hour += 12  # Assume PM for tonight
            return reference_time.replace(hour=hour, minute=minute, second=0, microsecond=0)
        return reference_time.replace(hour=20, minute=0, second=0, microsecond=0)  # Default 8pm
    
    # Pattern: "this afternoon/evening/morning"
    if "this afternoon" in text:
        return reference_time.replace(hour=14, minute=0, second=0, microsecond=0)
    if "this evening" in text:
        return reference_time.replace(hour=18, minute=0, second=0, microsecond=0)
    if "this morning" in text:
        result = reference_time.replace(hour=9, minute=0, second=0, microsecond=0)
        if result < reference_time:
            result += timedelta(days=1)
        return result
    
    # Pattern: "next monday/tuesday/etc at X"
    days_of_week = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
    for i, day_name in enumerate(days_of_week):
        if f"next {day_name}" in text or text.startswith(day_name):
            current_day = reference_time.weekday()
            days_ahead = i - current_day
            if days_ahead <= 0:
                days_ahead += 7
            target_date = reference_time + timedelta(days=days_ahead)
            
            time_match = re.search(r"(\d{1,2})(?::(\d{2}))?\s*(am|pm)?", text)
            if time_match:
                hour = int(time_match.group(1))
                minute = int(time_match.group(2) or 0)
                ampm = time_match.group(3)
                if ampm == "pm" and hour < 12:
                    hour += 12
                elif ampm == "am" and hour == 12:
                    hour = 0
                return target_date.replace(hour=hour, minute=minute, second=0, microsecond=0)
            return target_date.replace(hour=9, minute=0, second=0, microsecond=0)
    
    return None


def extract_reminder_from_message(message: str) -> Optional[Tuple[str, datetime]]:
    """
    Extract reminder content and time from a natural language message.
    
    Examples:
    - "remind me to call mom tomorrow at 5pm" -> ("call mom", <datetime>)
    - "remind me in 2 hours to check the oven" -> ("check the oven", <datetime>)
    - "set a reminder for 3pm: meeting with John" -> ("meeting with John", <datetime>)
    
    Returns (reminder_text, scheduled_time) or None if not a reminder.
    """
    message_lower = message.lower()
    
    # First check if this looks like a reminder request
    if not any(kw in message_lower for kw in ["remind", "reminder", "alert me", "notify me"]):
        return None
    
    # Parse the time first
    scheduled_time = parse_natural_time(message)
    if not scheduled_time:
        return None
    
    reminder_text = None
    
    # Pattern 1: "remind me to X at/in/on TIME" -> extract X
    match = re.search(r"remind\s+me\s+to\s+(.+?)\s+(?:at|in|on|tomorrow|tonight|next\s+\w+|this\s+\w+)", message_lower)
    if match:
        reminder_text = match.group(1).strip()
    
    # Pattern 2: "remind me at/in TIME to X" -> extract X
    if not reminder_text:
        # Find "to" after time expressions
        time_patterns = [
            r"(?:at\s+)?[\d:]+\s*(?:am|pm)?\s+to\s+(.+)",
            r"in\s+\d+\s+(?:hour|minute|min|hr|day|week)s?\s+to\s+(.+)",
            r"tomorrow\s+(?:at\s+)?(?:[\d:]+\s*(?:am|pm)?)?\s*to\s+(.+)",
            r"tonight\s+(?:at\s+)?(?:[\d:]+\s*(?:am|pm)?)?\s*to\s+(.+)",
            r"next\s+\w+\s+(?:at\s+)?(?:[\d:]+\s*(?:am|pm)?)?\s*to\s+(.+)",
        ]
        for pattern in time_patterns:
            match = re.search(pattern, message_lower)
            if match:
                reminder_text = match.group(1).strip()
                break
    
    # Pattern 3: "set a reminder for TIME: X" -> extract X
    if not reminder_text:
        match = re.search(r"reminder\s+(?:for\s+)?[\d:]+\s*(?:am|pm)?[:\s]+(.+)", message_lower)
        if match:
            reminder_text = match.group(1).strip()
    
    # Pattern 4: "remind me about X" + time detected elsewhere
    if not reminder_text:
        match = re.search(r"remind\s+me\s+(?:about|that)\s+(.+)", message_lower)
        if match:
            # Remove time expressions from the end
            text = match.group(1).strip()
            text = re.sub(r"\s+(?:at|in|on|tomorrow|tonight|next|this)\s+.*$", "", text)
            if text:
                reminder_text = text
    
    # Fallback: take everything after "to" in a remind sentence
    if not reminder_text:
        match = re.search(r"remind\s+me\s+.+?\s+to\s+(.+?)(?:\s*$|\s+at\s|\s+in\s|\s+on\s)", message_lower)
        if match:
            reminder_text = match.group(1).strip()
    
    if not reminder_text:
        return None
    
    # Clean up reminder text - remove trailing time expressions
    reminder_text = re.sub(r"\s+at\s+\d.*$", "", reminder_text, flags=re.IGNORECASE)
    reminder_text = re.sub(r"\s+in\s+\d.*$", "", reminder_text, flags=re.IGNORECASE)
    reminder_text = reminder_text.strip(" .,!?")
    
    if len(reminder_text) < 2:
        return None
    
    return (reminder_text, scheduled_time)


# ============================================================================
# Database Functions
# ============================================================================

def init_scheduled_tasks_db(db_path: str) -> None:
    """Initialize the scheduled tasks database."""
    path = Path(db_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    
    with get_db_connection(db_path) as conn:
        cur = conn.cursor()
        
        cur.execute("""
            CREATE TABLE IF NOT EXISTS scheduled_tasks (
                task_id TEXT PRIMARY KEY,
                task_type TEXT NOT NULL,
                scheduled_at REAL NOT NULL,
                thread_id TEXT NOT NULL,
                payload_json TEXT NOT NULL,
                created_at REAL NOT NULL,
                status TEXT NOT NULL DEFAULT 'pending',
                completed_at REAL,
                error TEXT,
                recurrence TEXT
            )
        """)
        
        cur.execute("CREATE INDEX IF NOT EXISTS idx_scheduled_tasks_status ON scheduled_tasks(status)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_scheduled_tasks_scheduled_at ON scheduled_tasks(scheduled_at)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_scheduled_tasks_thread ON scheduled_tasks(thread_id)")
        
        conn.commit()


def create_scheduled_task(
    db_path: str,
    task_id: str,
    task_type: str,
    scheduled_at: float,
    thread_id: str,
    payload: Dict[str, Any],
    recurrence: Optional[str] = None,
) -> ScheduledTask:
    """Create a new scheduled task."""
    init_scheduled_tasks_db(db_path)
    
    task = ScheduledTask(
        task_id=task_id,
        task_type=task_type,
        scheduled_at=scheduled_at,
        thread_id=thread_id,
        payload=payload,
        recurrence=recurrence,
    )
    
    with get_db_connection(db_path) as conn:
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO scheduled_tasks 
            (task_id, task_type, scheduled_at, thread_id, payload_json, created_at, status, recurrence)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            task.task_id,
            task.task_type,
            task.scheduled_at,
            task.thread_id,
            json.dumps(task.payload),
            task.created_at,
            task.status,
            task.recurrence,
        ))
        conn.commit()
    
    logger.info(f"[SCHEDULED] Created task {task_id}: {task_type} at {task.formatted_time()}")
    return task


def get_pending_scheduled_tasks(db_path: str, thread_id: Optional[str] = None) -> List[ScheduledTask]:
    """Get all pending scheduled tasks, optionally filtered by thread."""
    init_scheduled_tasks_db(db_path)
    
    with get_db_connection(db_path) as conn:
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        
        if thread_id:
            cur.execute("""
                SELECT * FROM scheduled_tasks 
                WHERE status = 'pending' AND thread_id = ?
                ORDER BY scheduled_at ASC
            """, (thread_id,))
        else:
            cur.execute("""
                SELECT * FROM scheduled_tasks 
                WHERE status = 'pending'
                ORDER BY scheduled_at ASC
            """)
        
        rows = cur.fetchall()
    
    tasks = []
    for row in rows:
        tasks.append(ScheduledTask(
            task_id=row["task_id"],
            task_type=row["task_type"],
            scheduled_at=row["scheduled_at"],
            thread_id=row["thread_id"],
            payload=json.loads(row["payload_json"]),
            created_at=row["created_at"],
            status=row["status"],
            completed_at=row["completed_at"],
            error=row["error"],
            recurrence=row["recurrence"],
        ))
    
    return tasks


def get_due_tasks(db_path: str) -> List[ScheduledTask]:
    """Get all tasks that are due for execution."""
    init_scheduled_tasks_db(db_path)
    
    now = time.time()
    with get_db_connection(db_path) as conn:
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        
        cur.execute("""
            SELECT * FROM scheduled_tasks 
            WHERE status = 'pending' AND scheduled_at <= ?
            ORDER BY scheduled_at ASC
        """, (now,))
        
        rows = cur.fetchall()
    
    tasks = []
    for row in rows:
        tasks.append(ScheduledTask(
            task_id=row["task_id"],
            task_type=row["task_type"],
            scheduled_at=row["scheduled_at"],
            thread_id=row["thread_id"],
            payload=json.loads(row["payload_json"]),
            created_at=row["created_at"],
            status=row["status"],
            completed_at=row["completed_at"],
            error=row["error"],
            recurrence=row["recurrence"],
        ))
    
    return tasks


def mark_task_completed(db_path: str, task_id: str, error: Optional[str] = None) -> None:
    """Mark a task as completed (or failed if error provided)."""
    with get_db_connection(db_path) as conn:
        cur = conn.cursor()
        
        status = "failed" if error else "completed"
        cur.execute("""
            UPDATE scheduled_tasks 
            SET status = ?, completed_at = ?, error = ?
            WHERE task_id = ?
        """, (status, time.time(), error, task_id))
        
        conn.commit()
    
    logger.info(f"[SCHEDULED] Task {task_id} marked as {status}")


def cancel_scheduled_task(db_path: str, task_id: str) -> bool:
    """Cancel a pending scheduled task."""
    with get_db_connection(db_path) as conn:
        cur = conn.cursor()
        
        cur.execute("""
            UPDATE scheduled_tasks 
            SET status = 'cancelled', completed_at = ?
            WHERE task_id = ? AND status = 'pending'
        """, (time.time(), task_id))
        
        affected = cur.rowcount
        conn.commit()
    
    if affected > 0:
        logger.info(f"[SCHEDULED] Cancelled task {task_id}")
        return True
    return False


def get_task_by_id(db_path: str, task_id: str) -> Optional[ScheduledTask]:
    """Get a specific task by ID."""
    with get_db_connection(db_path) as conn:
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        
        cur.execute("SELECT * FROM scheduled_tasks WHERE task_id = ?", (task_id,))
        row = cur.fetchone()
    
    if not row:
        return None
    
    return ScheduledTask(
        task_id=row["task_id"],
        task_type=row["task_type"],
        scheduled_at=row["scheduled_at"],
        thread_id=row["thread_id"],
        payload=json.loads(row["payload_json"]),
        created_at=row["created_at"],
        status=row["status"],
        completed_at=row["completed_at"],
        error=row["error"],
        recurrence=row["recurrence"],
    )


# ============================================================================
# Scheduled Tasks Loop (Background Worker)
# ============================================================================

class ScheduledTasksLoop:
    """
    Background loop that checks for and executes due scheduled tasks.
    
    Runs every minute by default, checking for tasks whose scheduled_at
    has passed and executing them.
    """
    
    def __init__(
        self,
        db_path: str,
        check_interval: float = 30.0,  # Check every 30 seconds
        enabled: bool = True,
        on_reminder: Optional[Callable[[ScheduledTask], None]] = None,
        on_thought: Optional[Callable[[ScheduledTask], None]] = None,
    ):
        self.db_path = db_path
        self.check_interval = check_interval
        self.enabled = enabled
        self.on_reminder = on_reminder
        self.on_thought = on_thought
        
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        
        # Initialize DB
        init_scheduled_tasks_db(db_path)
    
    def start(self) -> None:
        """Start the scheduled tasks loop."""
        if not self.enabled:
            logger.debug("[SCHEDULED] Loop disabled, not starting")
            return
        if self._running:
            logger.debug("[SCHEDULED] Loop already running")
            return
        
        self._running = True
        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._run,
            name="crt-scheduled-tasks",
            daemon=True,
        )
        self._thread.start()
        logger.info("[SCHEDULED] Tasks loop started")
    
    def stop(self) -> None:
        """Stop the scheduled tasks loop."""
        self._running = False
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=5.0)
        logger.info("[SCHEDULED] Tasks loop stopped")
    
    def _run(self) -> None:
        """Main loop - check for due tasks periodically."""
        logger.info(f"[SCHEDULED] Loop running (check every {self.check_interval}s)")
        
        while self._running and not self._stop_event.is_set():
            try:
                self._process_due_tasks()
            except Exception as e:
                logger.error(f"[SCHEDULED] Loop error: {e}", exc_info=True)
            
            self._stop_event.wait(timeout=self.check_interval)
    
    def _process_due_tasks(self) -> None:
        """Find and execute all due tasks."""
        due_tasks = get_due_tasks(self.db_path)
        
        for task in due_tasks:
            try:
                self._execute_task(task)
            except Exception as e:
                logger.error(f"[SCHEDULED] Failed to execute task {task.task_id}: {e}")
                mark_task_completed(self.db_path, task.task_id, error=str(e))
    
    def _execute_task(self, task: ScheduledTask) -> None:
        """Execute a single scheduled task."""
        logger.info(f"[SCHEDULED] Executing task {task.task_id}: {task.task_type}")
        
        if task.task_type == TaskType.REMINDER:
            if self.on_reminder:
                self.on_reminder(task)
            else:
                logger.warning(f"[SCHEDULED] No reminder handler for task {task.task_id}")
        
        elif task.task_type == TaskType.THOUGHT:
            if self.on_thought:
                self.on_thought(task)
            else:
                logger.warning(f"[SCHEDULED] No thought handler for task {task.task_id}")
        
        elif task.task_type == TaskType.SCHEDULED_JOB:
            # Import here to avoid circular imports
            try:
                from personal_agent.jobs_db import enqueue_job
                from personal_agent.artifact_store import now_iso_utc
                
                job_payload = task.payload.get("job_payload", {})
                job_type = task.payload.get("job_type", "custom")
                job_id = f"scheduled_{task.task_id}_{int(time.time())}"
                
                enqueue_job(
                    db_path=task.payload.get("jobs_db_path", self.db_path.replace("scheduled_tasks.db", "jobs.db")),
                    job_id=job_id,
                    job_type=job_type,
                    created_at=now_iso_utc(),
                    payload=job_payload,
                )
                logger.info(f"[SCHEDULED] Enqueued job {job_id} from scheduled task")
            except Exception as e:
                logger.error(f"[SCHEDULED] Failed to enqueue job: {e}")
                mark_task_completed(self.db_path, task.task_id, error=str(e))
                return
        
        # Mark as completed
        mark_task_completed(self.db_path, task.task_id)
        
        # Handle recurrence
        if task.recurrence:
            self._schedule_next_recurrence(task)
    
    def _schedule_next_recurrence(self, task: ScheduledTask) -> None:
        """Schedule the next occurrence of a recurring task."""
        if task.recurrence == "daily":
            next_time = task.scheduled_at + 86400  # 24 hours
        elif task.recurrence == "weekly":
            next_time = task.scheduled_at + 604800  # 7 days
        elif task.recurrence == "hourly":
            next_time = task.scheduled_at + 3600  # 1 hour
        else:
            return  # Unknown recurrence
        
        new_task_id = f"{task.task_id.rsplit('_', 1)[0]}_{int(time.time())}"
        
        create_scheduled_task(
            db_path=self.db_path,
            task_id=new_task_id,
            task_type=task.task_type,
            scheduled_at=next_time,
            thread_id=task.thread_id,
            payload=task.payload,
            recurrence=task.recurrence,
        )
        
        logger.info(f"[SCHEDULED] Scheduled next recurrence: {new_task_id}")


# ============================================================================
# Helper Functions
# ============================================================================

def schedule_reminder(
    db_path: str,
    thread_id: str,
    reminder_text: str,
    scheduled_time: datetime,
    recurrence: Optional[str] = None,
) -> ScheduledTask:
    """Helper to schedule a reminder."""
    task_id = f"reminder_{thread_id}_{int(time.time() * 1000)}"
    
    return create_scheduled_task(
        db_path=db_path,
        task_id=task_id,
        task_type=TaskType.REMINDER,
        scheduled_at=scheduled_time.timestamp(),
        thread_id=thread_id,
        payload={
            "reminder_text": reminder_text,
            "original_time_str": scheduled_time.strftime("%I:%M %p on %A, %B %d"),
        },
        recurrence=recurrence,
    )


def schedule_thought(
    db_path: str,
    thread_id: str,
    thought_content: str,
    scheduled_time: Optional[datetime] = None,
) -> ScheduledTask:
    """Schedule a thought to be posted to the Ledger."""
    if scheduled_time is None:
        scheduled_time = datetime.now()  # Post immediately
    
    task_id = f"thought_{thread_id}_{int(time.time() * 1000)}"
    
    return create_scheduled_task(
        db_path=db_path,
        task_id=task_id,
        task_type=TaskType.THOUGHT,
        scheduled_at=scheduled_time.timestamp(),
        thread_id=thread_id,
        payload={
            "thought_content": thought_content,
            "thought_type": "reflection",
        },
    )


def format_upcoming_tasks(tasks: List[ScheduledTask]) -> str:
    """Format a list of tasks for display."""
    if not tasks:
        return "No upcoming scheduled tasks."
    
    lines = ["📅 **Upcoming Tasks:**"]
    for task in tasks[:10]:  # Limit to 10
        dt = datetime.fromtimestamp(task.scheduled_at)
        time_str = dt.strftime("%I:%M %p on %a, %b %d")
        
        if task.task_type == TaskType.REMINDER:
            emoji = "⏰"
            desc = task.payload.get("reminder_text", "Reminder")
        elif task.task_type == TaskType.THOUGHT:
            emoji = "💭"
            desc = "Post thought"
        else:
            emoji = "📋"
            desc = task.task_type
        
        lines.append(f"- {emoji} {time_str}: {desc}")
    
    return "\n".join(lines)
