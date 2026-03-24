"""Commitment governance system for CRT/Aether.

A commitment is distinct from a memory fact. Facts describe what IS.
Commitments describe what SHOULD HAPPEN — reminders, scheduled actions,
recurring obligations.

Persisted to SQLite: data/commitments.db
"""

from __future__ import annotations

import json
import logging
import os
import re
import sqlite3
import time
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

_DB_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "data",
    "commitments.db",
)

_CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS commitments (
    commitment_id TEXT PRIMARY KEY,
    thread_id TEXT,
    intent TEXT NOT NULL,
    description TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending',
    origin TEXT NOT NULL DEFAULT 'user_requested',
    priority TEXT NOT NULL DEFAULT 'medium',
    consequence TEXT,
    created_at REAL NOT NULL,
    deadline REAL,
    recurrence TEXT,
    last_fired_at REAL,
    next_fire_at REAL,
    metadata TEXT DEFAULT '{}',
    fire_count INTEGER DEFAULT 0
)
"""


@dataclass
class Commitment:
    commitment_id: str          # unique ID
    thread_id: str              # which conversation created it
    intent: str                 # "take medication", "check deploy", "call dentist"
    description: str            # full human-readable description
    status: str                 # "pending", "fired", "done", "missed", "cancelled"
    origin: str                 # "user_requested", "system_suggested", "proactive"
    priority: str               # "low", "medium", "high", "critical"
    consequence: Optional[str]  # "health", "work", "social", None
    created_at: float           # timestamp
    deadline: Optional[float]   # when it should fire (epoch timestamp)
    recurrence: Optional[str]   # "daily", "weekly", "weekdays", cron, or None
    last_fired_at: Optional[float]
    next_fire_at: Optional[float]
    metadata: Dict[str, Any] = field(default_factory=dict)
    fire_count: int = 0

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        # Add human-readable times
        if self.next_fire_at:
            d["next_fire_formatted"] = format_timestamp(self.next_fire_at)
        if self.deadline:
            d["deadline_formatted"] = format_timestamp(self.deadline)
        return d


# ---------------------------------------------------------------------------
# Human-readable time formatting
# ---------------------------------------------------------------------------

def format_timestamp(ts: float) -> str:
    """Format epoch timestamp to human-readable: 'today at 10:30 PM', 'tomorrow at 9:00 AM', etc."""
    dt = datetime.fromtimestamp(ts)
    now = datetime.now()
    today = now.date()
    target_date = dt.date()

    time_str = dt.strftime("%I:%M %p").lstrip("0")

    if target_date == today:
        return f"today at {time_str}"
    elif target_date == today + timedelta(days=1):
        return f"tomorrow at {time_str}"
    elif target_date == today - timedelta(days=1):
        return f"yesterday at {time_str}"
    elif (target_date - today).days < 7 and (target_date - today).days > 0:
        return f"{dt.strftime('%A')} at {time_str}"
    else:
        return f"{dt.strftime('%b %d')} at {time_str}"


# ---------------------------------------------------------------------------
# Database helpers
# ---------------------------------------------------------------------------

def _get_db() -> sqlite3.Connection:
    """Get or create the commitments database."""
    os.makedirs(os.path.dirname(_DB_PATH), exist_ok=True)
    conn = sqlite3.connect(_DB_PATH, timeout=10.0)
    conn.execute(_CREATE_TABLE_SQL)
    conn.commit()
    return conn


def _row_to_commitment(row: tuple) -> Commitment:
    return Commitment(
        commitment_id=row[0],
        thread_id=row[1],
        intent=row[2],
        description=row[3],
        status=row[4],
        origin=row[5],
        priority=row[6],
        consequence=row[7],
        created_at=row[8],
        deadline=row[9],
        recurrence=row[10],
        last_fired_at=row[11],
        next_fire_at=row[12],
        metadata=json.loads(row[13]) if row[13] else {},
        fire_count=row[14] if len(row) > 14 else 0,
    )


# ---------------------------------------------------------------------------
# Recurrence / cron parsing
# ---------------------------------------------------------------------------

def _parse_cron_field(field_str: str, min_val: int, max_val: int) -> List[int]:
    """Parse a single cron field into list of matching values."""
    results = set()
    for part in field_str.split(","):
        part = part.strip()
        # */N — every N
        m = re.match(r"^\*/(\d+)$", part)
        if m:
            step = int(m.group(1))
            for v in range(min_val, max_val + 1, step):
                results.add(v)
            continue
        # N-M — range
        m = re.match(r"^(\d+)-(\d+)$", part)
        if m:
            lo, hi = int(m.group(1)), int(m.group(2))
            for v in range(lo, hi + 1):
                if min_val <= v <= max_val:
                    results.add(v)
            continue
        # * — wildcard
        if part == "*":
            return list(range(min_val, max_val + 1))
        # N — literal
        try:
            v = int(part)
            if min_val <= v <= max_val:
                results.add(v)
        except ValueError:
            pass
    return sorted(results) if results else list(range(min_val, max_val + 1))


def _next_cron_time(cron_expr: str, after: float) -> Optional[float]:
    """Compute next fire time for a 5-field cron expression after `after` epoch."""
    parts = cron_expr.strip().split()
    if len(parts) != 5:
        return None

    minutes = _parse_cron_field(parts[0], 0, 59)
    hours = _parse_cron_field(parts[1], 0, 23)
    doms = _parse_cron_field(parts[2], 1, 31)
    months = _parse_cron_field(parts[3], 1, 12)
    dows = _parse_cron_field(parts[4], 0, 6)  # 0=Sun, 6=Sat

    dt = datetime.fromtimestamp(after) + timedelta(minutes=1)
    dt = dt.replace(second=0, microsecond=0)

    # Search up to 366 days ahead
    for _ in range(366 * 24 * 60):
        if (dt.month in months
                and dt.day in doms
                and dt.weekday() in [(d - 1) % 7 for d in dows] if dows != list(range(0, 7)) else True
                and dt.hour in hours
                and dt.minute in minutes):
            # Check day-of-week: cron uses 0=Sun, Python uses 0=Mon
            py_dow = dt.weekday()  # 0=Mon
            cron_dow = (py_dow + 1) % 7  # 0=Sun
            if parts[4] == "*" or cron_dow in dows:
                return dt.timestamp()
        dt += timedelta(minutes=1)
        # Skip ahead if we're past all minutes in this hour
        if dt.minute == 0 and dt.hour not in hours:
            # Jump to next valid hour
            dt += timedelta(hours=1)
            dt = dt.replace(minute=0)

    return None


def compute_next_fire(commitment: Commitment) -> Optional[float]:
    """Given recurrence pattern + last_fired, compute next fire time."""
    rec = commitment.recurrence
    if not rec:
        return None  # one-shot, no next fire

    base_time = commitment.last_fired_at or commitment.deadline or time.time()
    base_dt = datetime.fromtimestamp(base_time)

    if rec == "daily":
        next_dt = base_dt + timedelta(days=1)
        return next_dt.timestamp()

    elif rec == "weekly":
        next_dt = base_dt + timedelta(weeks=1)
        return next_dt.timestamp()

    elif rec == "weekdays":
        next_dt = base_dt + timedelta(days=1)
        while next_dt.weekday() >= 5:  # skip Sat/Sun
            next_dt += timedelta(days=1)
        return next_dt.timestamp()

    # "every N hours" / "every N minutes"
    m = re.match(r"every\s+(\d+)\s+(hour|minute|min)s?", rec, re.IGNORECASE)
    if m:
        amount = int(m.group(1))
        unit = m.group(2).lower()
        if unit == "hour":
            delta = timedelta(hours=amount)
        else:
            delta = timedelta(minutes=amount)
        next_ts = base_time + delta.total_seconds()
        return next_ts

    # 5-field cron expression
    if len(rec.split()) == 5:
        return _next_cron_time(rec, base_time)

    return None


# ---------------------------------------------------------------------------
# CRUD operations
# ---------------------------------------------------------------------------

def create_commitment(
    thread_id: str,
    intent: str,
    description: str,
    deadline: Optional[float] = None,
    recurrence: Optional[str] = None,
    priority: str = "medium",
    consequence: Optional[str] = None,
    origin: str = "user_requested",
    metadata: Optional[Dict[str, Any]] = None,
) -> Commitment:
    """Create a new commitment and persist to SQLite."""
    cid = str(uuid.uuid4())
    now = time.time()

    c = Commitment(
        commitment_id=cid,
        thread_id=thread_id,
        intent=intent,
        description=description,
        status="pending",
        origin=origin,
        priority=priority,
        consequence=consequence,
        created_at=now,
        deadline=deadline,
        recurrence=recurrence,
        last_fired_at=None,
        next_fire_at=deadline,  # first fire at deadline
        metadata=metadata or {},
        fire_count=0,
    )

    try:
        conn = _get_db()
        conn.execute(
            """INSERT INTO commitments
               (commitment_id, thread_id, intent, description, status, origin,
                priority, consequence, created_at, deadline, recurrence,
                last_fired_at, next_fire_at, metadata, fire_count)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                c.commitment_id, c.thread_id, c.intent, c.description,
                c.status, c.origin, c.priority, c.consequence,
                c.created_at, c.deadline, c.recurrence,
                c.last_fired_at, c.next_fire_at,
                json.dumps(c.metadata, default=str),
                c.fire_count,
            ),
        )
        conn.commit()
        conn.close()
        logger.info("[COMMITMENTS] Created %s: %s (next_fire=%s)",
                     cid[:8], intent, format_timestamp(deadline) if deadline else "none")
    except Exception as e:
        logger.warning("[COMMITMENTS] Failed to create: %s", e)
        raise

    return c


def get_pending_commitments(before_timestamp: Optional[float] = None) -> List[Commitment]:
    """Return commitments due before the given time (or all pending if None)."""
    try:
        conn = _get_db()
        if before_timestamp is not None:
            cursor = conn.execute(
                """SELECT commitment_id, thread_id, intent, description, status,
                          origin, priority, consequence, created_at, deadline,
                          recurrence, last_fired_at, next_fire_at, metadata, fire_count
                   FROM commitments
                   WHERE status = 'pending' AND next_fire_at IS NOT NULL AND next_fire_at <= ?
                   ORDER BY next_fire_at ASC""",
                (before_timestamp,),
            )
        else:
            cursor = conn.execute(
                """SELECT commitment_id, thread_id, intent, description, status,
                          origin, priority, consequence, created_at, deadline,
                          recurrence, last_fired_at, next_fire_at, metadata, fire_count
                   FROM commitments
                   WHERE status = 'pending'
                   ORDER BY next_fire_at ASC""",
            )
        rows = cursor.fetchall()
        conn.close()
        return [_row_to_commitment(r) for r in rows]
    except Exception as e:
        logger.warning("[COMMITMENTS] Failed to get pending: %s", e)
        return []


def get_all_commitments(
    thread_id: Optional[str] = None,
    status: Optional[str] = None,
) -> List[Commitment]:
    """Get all commitments, optionally filtered by thread_id and/or status."""
    try:
        conn = _get_db()
        query = """SELECT commitment_id, thread_id, intent, description, status,
                          origin, priority, consequence, created_at, deadline,
                          recurrence, last_fired_at, next_fire_at, metadata, fire_count
                   FROM commitments WHERE 1=1"""
        params: List[Any] = []
        if thread_id:
            query += " AND thread_id = ?"
            params.append(thread_id)
        if status:
            query += " AND status = ?"
            params.append(status)
        query += " ORDER BY created_at DESC"
        cursor = conn.execute(query, params)
        rows = cursor.fetchall()
        conn.close()
        return [_row_to_commitment(r) for r in rows]
    except Exception as e:
        logger.warning("[COMMITMENTS] Failed to get all: %s", e)
        return []


def get_commitment(commitment_id: str) -> Optional[Commitment]:
    """Get a single commitment by ID."""
    try:
        conn = _get_db()
        cursor = conn.execute(
            """SELECT commitment_id, thread_id, intent, description, status,
                      origin, priority, consequence, created_at, deadline,
                      recurrence, last_fired_at, next_fire_at, metadata, fire_count
               FROM commitments WHERE commitment_id = ?""",
            (commitment_id,),
        )
        row = cursor.fetchone()
        conn.close()
        if row:
            return _row_to_commitment(row)
        return None
    except Exception as e:
        logger.warning("[COMMITMENTS] Failed to get %s: %s", commitment_id, e)
        return None


def update_commitment_status(commitment_id: str, status: str) -> Optional[Commitment]:
    """Update the status of a commitment."""
    try:
        conn = _get_db()
        conn.execute(
            "UPDATE commitments SET status = ? WHERE commitment_id = ?",
            (status, commitment_id),
        )
        conn.commit()
        conn.close()
        logger.info("[COMMITMENTS] Updated %s → status=%s", commitment_id[:8], status)
        return get_commitment(commitment_id)
    except Exception as e:
        logger.warning("[COMMITMENTS] Failed to update status: %s", e)
        return None


def cancel_commitment(commitment_id: str) -> Optional[Commitment]:
    """Cancel a commitment."""
    return update_commitment_status(commitment_id, "cancelled")


def fire_commitment(commitment_id: str) -> Optional[Commitment]:
    """Mark a commitment as fired, update counters, compute next fire for recurring."""
    try:
        c = get_commitment(commitment_id)
        if not c:
            return None

        now = time.time()
        c.last_fired_at = now
        c.fire_count += 1

        if c.recurrence:
            # Recurring: compute next fire, keep pending
            c.status = "pending"
            c.next_fire_at = compute_next_fire(c)
        else:
            # One-shot: mark as done
            c.status = "done"
            c.next_fire_at = None

        conn = _get_db()
        conn.execute(
            """UPDATE commitments
               SET status = ?, last_fired_at = ?, next_fire_at = ?,
                   fire_count = ?
               WHERE commitment_id = ?""",
            (c.status, c.last_fired_at, c.next_fire_at, c.fire_count, commitment_id),
        )
        conn.commit()
        conn.close()

        logger.info("[COMMITMENTS] Fired %s: %s (count=%d, next=%s)",
                     commitment_id[:8], c.intent, c.fire_count,
                     format_timestamp(c.next_fire_at) if c.next_fire_at else "none")
        return c
    except Exception as e:
        logger.warning("[COMMITMENTS] Failed to fire %s: %s", commitment_id, e)
        return None


def search_commitments(search_term: str, status: str = "pending") -> List[Commitment]:
    """Fuzzy search commitments by intent or description."""
    try:
        conn = _get_db()
        cursor = conn.execute(
            """SELECT commitment_id, thread_id, intent, description, status,
                      origin, priority, consequence, created_at, deadline,
                      recurrence, last_fired_at, next_fire_at, metadata, fire_count
               FROM commitments
               WHERE status = ?
                 AND (LOWER(intent) LIKE ? OR LOWER(description) LIKE ?)
               ORDER BY created_at DESC""",
            (status, f"%{search_term.lower()}%", f"%{search_term.lower()}%"),
        )
        rows = cursor.fetchall()
        conn.close()
        return [_row_to_commitment(r) for r in rows]
    except Exception as e:
        logger.warning("[COMMITMENTS] Search failed: %s", e)
        return []


def get_missed_commitments() -> List[Commitment]:
    """Get commitments that were missed (next_fire_at < now, still pending)."""
    try:
        now = time.time()
        conn = _get_db()
        cursor = conn.execute(
            """SELECT commitment_id, thread_id, intent, description, status,
                      origin, priority, consequence, created_at, deadline,
                      recurrence, last_fired_at, next_fire_at, metadata, fire_count
               FROM commitments
               WHERE status = 'pending'
                 AND next_fire_at IS NOT NULL
                 AND next_fire_at < ?
               ORDER BY next_fire_at ASC""",
            (now - 300,),  # 5 min grace period
        )
        rows = cursor.fetchall()
        conn.close()
        return [_row_to_commitment(r) for r in rows]
    except Exception as e:
        logger.warning("[COMMITMENTS] Failed to get missed: %s", e)
        return []


def get_stale_commitments(fire_count_threshold: int = 3) -> List[Commitment]:
    """Get commitments fired N+ times without user acknowledgement."""
    try:
        conn = _get_db()
        cursor = conn.execute(
            """SELECT commitment_id, thread_id, intent, description, status,
                      origin, priority, consequence, created_at, deadline,
                      recurrence, last_fired_at, next_fire_at, metadata, fire_count
               FROM commitments
               WHERE status = 'pending'
                 AND fire_count >= ?
               ORDER BY fire_count DESC""",
            (fire_count_threshold,),
        )
        rows = cursor.fetchall()
        conn.close()
        return [_row_to_commitment(r) for r in rows]
    except Exception as e:
        logger.warning("[COMMITMENTS] Failed to get stale: %s", e)
        return []
