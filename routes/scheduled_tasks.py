"""Scheduled tasks routes – extracted from crt_api.py."""

import json
import sqlite3
import time
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, HTTPException, Request, Query

from personal_agent.scheduled_tasks import (
    create_scheduled_task,
    get_pending_scheduled_tasks,
    cancel_scheduled_task,
    get_task_by_id,
    schedule_reminder,
    schedule_thought,
    parse_natural_time,
    extract_reminder_from_message,
    format_upcoming_tasks,
    init_scheduled_tasks_db,
    TaskType,
)
from personal_agent.db_utils import get_db_connection
from routes.models import (
    CreateScheduledTaskRequest,
    ScheduledTaskResponse,
    QuickReminderRequest,
    ScheduleThoughtRequest,
)

router = APIRouter()


# =========================================================================
# Scheduled Tasks API
# =========================================================================


@router.post("/api/scheduled-tasks", response_model=ScheduledTaskResponse)
def create_scheduled_task_endpoint(req: CreateScheduledTaskRequest, request: Request):
    """Create a new scheduled task (reminder, thought, or job)."""
    db_path = request.app.state.scheduled_tasks_db_path

    # Determine scheduled time
    if req.scheduled_at:
        scheduled_time = datetime.fromtimestamp(req.scheduled_at)
    elif req.scheduled_time_text:
        scheduled_time = parse_natural_time(req.scheduled_time_text)
        if not scheduled_time:
            raise HTTPException(400, f"Could not parse time: {req.scheduled_time_text}")
    else:
        raise HTTPException(400, "Must provide scheduled_at or scheduled_time_text")

    # Create task based on type
    task_id = f"{req.task_type}_{req.thread_id}_{int(time.time() * 1000)}"

    if req.task_type == "reminder":
        if not req.reminder_text:
            raise HTTPException(400, "reminder_text required for reminder tasks")
        payload = {
            "reminder_text": req.reminder_text,
            "original_time_str": scheduled_time.strftime("%I:%M %p on %A, %B %d"),
        }
    elif req.task_type == "thought":
        if not req.thought_content:
            raise HTTPException(400, "thought_content required for thought tasks")
        payload = {
            "thought_content": req.thought_content,
            "thought_type": "scheduled",
        }
    elif req.task_type == "scheduled_job":
        payload = {
            "job_type": req.job_type or "custom",
            "job_payload": req.job_payload or {},
        }
    else:
        payload = {}

    task = create_scheduled_task(
        db_path=db_path,
        task_id=task_id,
        task_type=req.task_type,
        scheduled_at=scheduled_time.timestamp(),
        thread_id=req.thread_id,
        payload=payload,
        recurrence=req.recurrence,
    )

    return ScheduledTaskResponse(
        task_id=task.task_id,
        task_type=task.task_type,
        scheduled_at=task.scheduled_at,
        scheduled_time_formatted=task.formatted_time(),
        thread_id=task.thread_id,
        status=task.status,
        payload=task.payload,
        recurrence=task.recurrence,
    )


@router.get("/api/scheduled-tasks")
def list_scheduled_tasks(
    request: Request,
    thread_id: Optional[str] = None,
    include_completed: bool = False,
):
    """List scheduled tasks, optionally filtered by thread."""
    db_path = request.app.state.scheduled_tasks_db_path

    if include_completed:
        # Get all tasks
        init_scheduled_tasks_db(db_path)
        with get_db_connection(db_path) as conn:
            conn.row_factory = sqlite3.Row
            cur = conn.cursor()
            if thread_id:
                cur.execute(
                    "SELECT * FROM scheduled_tasks WHERE thread_id = ? ORDER BY scheduled_at DESC",
                    (thread_id,),
                )
            else:
                cur.execute("SELECT * FROM scheduled_tasks ORDER BY scheduled_at DESC")
            rows = cur.fetchall()

        tasks = []
        for row in rows:
            tasks.append({
                "task_id": row["task_id"],
                "task_type": row["task_type"],
                "scheduled_at": row["scheduled_at"],
                "scheduled_time_formatted": datetime.fromtimestamp(row["scheduled_at"]).strftime(
                    "%I:%M %p on %A, %B %d"
                ),
                "thread_id": row["thread_id"],
                "status": row["status"],
                "payload": json.loads(row["payload_json"]),
                "recurrence": row["recurrence"],
                "completed_at": row["completed_at"],
                "error": row["error"],
            })
    else:
        tasks_list = get_pending_scheduled_tasks(db_path, thread_id)
        tasks = [
            {
                "task_id": t.task_id,
                "task_type": t.task_type,
                "scheduled_at": t.scheduled_at,
                "scheduled_time_formatted": t.formatted_time(),
                "thread_id": t.thread_id,
                "status": t.status,
                "payload": t.payload,
                "recurrence": t.recurrence,
                "time_until_seconds": t.time_until(),
            }
            for t in tasks_list
        ]

    return {"tasks": tasks, "count": len(tasks)}


@router.get("/api/scheduled-tasks/{task_id}")
def get_scheduled_task(task_id: str, request: Request):
    """Get a specific scheduled task by ID."""
    db_path = request.app.state.scheduled_tasks_db_path
    task = get_task_by_id(db_path, task_id)

    if not task:
        raise HTTPException(404, f"Task not found: {task_id}")

    return {
        "task_id": task.task_id,
        "task_type": task.task_type,
        "scheduled_at": task.scheduled_at,
        "scheduled_time_formatted": task.formatted_time(),
        "thread_id": task.thread_id,
        "status": task.status,
        "payload": task.payload,
        "recurrence": task.recurrence,
        "created_at": task.created_at,
        "completed_at": task.completed_at,
        "error": task.error,
    }


@router.delete("/api/scheduled-tasks/{task_id}")
def delete_scheduled_task(task_id: str, request: Request):
    """Cancel a pending scheduled task."""
    db_path = request.app.state.scheduled_tasks_db_path
    success = cancel_scheduled_task(db_path, task_id)

    if not success:
        raise HTTPException(404, f"Task not found or already completed: {task_id}")

    return {"status": "cancelled", "task_id": task_id}


@router.post("/api/scheduled-tasks/parse-time")
def parse_time_endpoint(text: str = Query(..., description="Natural language time expression")):
    """Parse a natural language time expression (for testing/preview)."""
    result = parse_natural_time(text)

    if not result:
        return {"success": False, "error": f"Could not parse: {text}"}

    return {
        "success": True,
        "parsed_time": result.isoformat(),
        "timestamp": result.timestamp(),
        "formatted": result.strftime("%I:%M %p on %A, %B %d, %Y"),
    }


@router.post("/api/quick-reminder")
def quick_reminder_endpoint(req: QuickReminderRequest, request: Request):
    """
    Parse a natural language reminder request and schedule it.

    Examples:
    - "remind me in 2 hours to call mom"
    - "remind me tomorrow at 5pm to check the oven"
    - "remind me next monday to submit the report"
    """
    db_path = request.app.state.scheduled_tasks_db_path

    # Extract reminder info from text
    reminder_info = extract_reminder_from_message(req.text)

    if not reminder_info:
        return {
            "success": False,
            "error": "Could not parse reminder from message. Try: 'remind me in X to Y' or 'remind me at X to Y'",
        }

    reminder_text, time_expression = reminder_info
    scheduled_time = parse_natural_time(time_expression)

    if not scheduled_time:
        return {
            "success": False,
            "error": f"Could not parse time expression: {time_expression}",
        }

    # Create the scheduled task
    task = schedule_reminder(
        db_path=db_path,
        reminder_text=reminder_text,
        scheduled_at=scheduled_time,
        thread_id=req.thread_id,
    )

    return {
        "success": True,
        "task_id": task.task_id,
        "reminder_text": reminder_text,
        "scheduled_for": scheduled_time.strftime("%I:%M %p on %A, %B %d, %Y"),
        "time_until_seconds": task.time_until(),
        "message": f"✅ I'll remind you to '{reminder_text}' at {scheduled_time.strftime('%I:%M %p on %A, %B %d')}",
    }


@router.post("/api/schedule-thought")
def schedule_thought_endpoint(req: ScheduleThoughtRequest, request: Request):
    """
    Schedule a thought to be posted to the Ledger later.

    This allows CRT to "ponder" - scheduling reflections to be posted at a later time.
    """
    db_path = request.app.state.scheduled_tasks_db_path

    scheduled_time = parse_natural_time(req.scheduled_time_text)
    if not scheduled_time:
        return {"success": False, "error": f"Could not parse time: {req.scheduled_time_text}"}

    task = schedule_thought(
        db_path=db_path,
        thought_content=req.thought_content,
        scheduled_at=scheduled_time,
        thread_id=req.thread_id,
    )

    return {
        "success": True,
        "task_id": task.task_id,
        "thought_preview": req.thought_content[:100] + "..."
        if len(req.thought_content) > 100
        else req.thought_content,
        "scheduled_for": scheduled_time.strftime("%I:%M %p on %A, %B %d, %Y"),
        "message": f"💭 Thought scheduled for {scheduled_time.strftime('%I:%M %p on %A, %B %d')}",
    }

