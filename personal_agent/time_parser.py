"""Natural language time parsing for CRT/Aether commitments.

Parses time expressions into epoch timestamps. No external dependencies.

Returns: {"deadline": float_epoch, "recurrence": str | None}
"""

from __future__ import annotations

import re
import time
from datetime import datetime, timedelta
from typing import Any, Dict, Optional

# ---------------------------------------------------------------------------
# Patterns
# ---------------------------------------------------------------------------

# "in 5 minutes", "in 2 hours", "in 30 seconds"
_IN_DELTA_RE = re.compile(
    r"\bin\s+(\d+)\s*(seconds?|secs?|minutes?|mins?|hours?|hrs?|days?)\b",
    re.IGNORECASE,
)

# "at 10:30", "at 10:30pm", "at 3pm", "at 15:00"
_AT_TIME_RE = re.compile(
    r"\bat\s+(\d{1,2})(?::(\d{2}))?\s*(am|pm)?\b",
    re.IGNORECASE,
)

# "tomorrow at 3pm", "tomorrow morning"
_TOMORROW_RE = re.compile(r"\btomorrow\b", re.IGNORECASE)

# Named time-of-day
_MORNING_RE = re.compile(r"\bmorning\b", re.IGNORECASE)
_AFTERNOON_RE = re.compile(r"\b(?:this\s+)?afternoon\b", re.IGNORECASE)
_EVENING_RE = re.compile(r"\b(?:this\s+)?evening\b", re.IGNORECASE)
_TONIGHT_RE = re.compile(r"\btonight\b", re.IGNORECASE)

# Recurring: "every day at 10:30pm", "every weekday at 9am", "at 10:30pm every day"
_EVERY_DAY_RE = re.compile(
    r"\bevery\s+(?:day|night)\s+at\s+(\d{1,2})(?::(\d{2}))?\s*(am|pm)?\b"
    r"|"
    r"\bat\s+(\d{1,2})(?::(\d{2}))?\s*(am|pm)?\s+every\s+(?:day|night)\b",
    re.IGNORECASE,
)
_EVERY_WEEKDAY_RE = re.compile(
    r"\bevery\s+weekday\s+at\s+(\d{1,2})(?::(\d{2}))?\s*(am|pm)?\b"
    r"|"
    r"\bat\s+(\d{1,2})(?::(\d{2}))?\s*(am|pm)?\s+every\s+weekday\b",
    re.IGNORECASE,
)

# "every hour", "every 30 minutes", "every 2 hours"
_EVERY_INTERVAL_RE = re.compile(
    r"\bevery\s+(\d+)?\s*(hours?|hrs?|minutes?|mins?)\b",
    re.IGNORECASE,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _resolve_hour(hour: int, minute: int, ampm: Optional[str]) -> tuple[int, int]:
    """Resolve hour with AM/PM. Returns (hour_24, minute)."""
    if ampm:
        ampm = ampm.lower()
        if ampm == "pm" and hour != 12:
            hour += 12
        elif ampm == "am" and hour == 12:
            hour = 0
    return hour, minute


def _make_time_today_or_tomorrow(hour: int, minute: int) -> datetime:
    """Create datetime for today at given time. If past, use tomorrow."""
    now = datetime.now()
    target = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
    if target <= now:
        target += timedelta(days=1)
    return target


def _make_time_tomorrow(hour: int, minute: int) -> datetime:
    """Create datetime for tomorrow at given time."""
    now = datetime.now()
    tomorrow = now + timedelta(days=1)
    return tomorrow.replace(hour=hour, minute=minute, second=0, microsecond=0)


# ---------------------------------------------------------------------------
# Main parser
# ---------------------------------------------------------------------------

def parse_time_expression(text: str) -> Dict[str, Any]:
    """Parse natural language time into deadline + recurrence.

    Returns:
        {"deadline": float_epoch, "recurrence": str | None}
        or {"deadline": None, "recurrence": None} if parsing fails.
    """
    text = text.strip()

    # --- Recurring patterns first ---

    # "every day at 10:30pm" or "at 10:30pm every day"
    m = _EVERY_DAY_RE.search(text)
    if m:
        # Groups: (1,2,3) from first alt, (4,5,6) from second alt
        hour = int(m.group(1) or m.group(4))
        minute = int(m.group(2) or m.group(5) or 0)
        ampm = m.group(3) or m.group(6)
        hour, minute = _resolve_hour(hour, minute, ampm)
        target = _make_time_today_or_tomorrow(hour, minute)
        return {"deadline": target.timestamp(), "recurrence": "daily"}

    # "every weekday at 9am" or "at 9am every weekday"
    m = _EVERY_WEEKDAY_RE.search(text)
    if m:
        hour = int(m.group(1) or m.group(4))
        minute = int(m.group(2) or m.group(5) or 0)
        ampm = m.group(3) or m.group(6)
        hour, minute = _resolve_hour(hour, minute, ampm)
        target = _make_time_today_or_tomorrow(hour, minute)
        # Ensure it lands on a weekday
        while target.weekday() >= 5:
            target += timedelta(days=1)
        return {"deadline": target.timestamp(), "recurrence": "weekdays"}

    # "every hour", "every 30 minutes", "every 2 hours"
    m = _EVERY_INTERVAL_RE.search(text)
    if m:
        amount = int(m.group(1) or 1)
        unit = m.group(2).lower()
        if unit.startswith("hour") or unit.startswith("hr"):
            recurrence = f"every {amount} hours"
            delta = timedelta(hours=amount)
        else:
            recurrence = f"every {amount} minutes"
            delta = timedelta(minutes=amount)
        deadline = time.time() + delta.total_seconds()
        return {"deadline": deadline, "recurrence": recurrence}

    # --- One-shot patterns ---

    # "in 5 minutes" / "in 2 hours"
    m = _IN_DELTA_RE.search(text)
    if m:
        amount = int(m.group(1))
        unit = m.group(2).lower()
        if unit.startswith("sec"):
            delta = timedelta(seconds=amount)
        elif unit.startswith("min"):
            delta = timedelta(minutes=amount)
        elif unit.startswith("hour") or unit.startswith("hr"):
            delta = timedelta(hours=amount)
        elif unit.startswith("day"):
            delta = timedelta(days=amount)
        else:
            delta = timedelta(minutes=amount)
        deadline = time.time() + delta.total_seconds()
        return {"deadline": deadline, "recurrence": None}

    is_tomorrow = bool(_TOMORROW_RE.search(text))

    # "at 10:30pm" (with or without "tomorrow")
    m = _AT_TIME_RE.search(text)
    if m:
        hour, minute = int(m.group(1)), int(m.group(2) or 0)
        hour, minute = _resolve_hour(hour, minute, m.group(3))
        if is_tomorrow:
            target = _make_time_tomorrow(hour, minute)
        else:
            target = _make_time_today_or_tomorrow(hour, minute)
        return {"deadline": target.timestamp(), "recurrence": None}

    # "tomorrow morning" (no specific time)
    if is_tomorrow:
        if _MORNING_RE.search(text):
            target = _make_time_tomorrow(9, 0)
        elif _AFTERNOON_RE.search(text):
            target = _make_time_tomorrow(14, 0)
        elif _EVENING_RE.search(text):
            target = _make_time_tomorrow(18, 0)
        elif _TONIGHT_RE.search(text):
            target = _make_time_tomorrow(21, 0)
        else:
            # "tomorrow" alone → 9am
            target = _make_time_tomorrow(9, 0)
        return {"deadline": target.timestamp(), "recurrence": None}

    # Named time-of-day without "tomorrow"
    if _TONIGHT_RE.search(text):
        target = _make_time_today_or_tomorrow(21, 0)
        return {"deadline": target.timestamp(), "recurrence": None}

    if _EVENING_RE.search(text):
        target = _make_time_today_or_tomorrow(18, 0)
        return {"deadline": target.timestamp(), "recurrence": None}

    if _AFTERNOON_RE.search(text):
        target = _make_time_today_or_tomorrow(14, 0)
        return {"deadline": target.timestamp(), "recurrence": None}

    if _MORNING_RE.search(text):
        target = _make_time_today_or_tomorrow(9, 0)
        return {"deadline": target.timestamp(), "recurrence": None}

    # No match
    return {"deadline": None, "recurrence": None}


def extract_reminder_intent(text: str) -> Dict[str, Any]:
    """Extract the reminder intent from a message.

    Given "remind me to take my meds at 10:30pm every day",
    returns:
        {
            "intent": "take my meds",
            "deadline": <epoch>,
            "recurrence": "daily",
        }
    """
    # Strip common prefixes
    cleaned = text
    for prefix in [
        r"remind\s+me\s+to\s+",
        r"set\s+a?\s*reminder\s+(?:to\s+)?",
        r"don't\s+let\s+me\s+forget\s+to\s+",
        r"alert\s+me\s+to\s+",
        r"notify\s+me\s+to\s+",
        r"schedule\s+",
    ]:
        cleaned = re.sub(prefix, "", cleaned, count=1, flags=re.IGNORECASE)

    # Extract time info
    time_info = parse_time_expression(text)

    # Strip time expressions from cleaned text to get the pure intent
    intent = cleaned
    for pattern in [
        _EVERY_DAY_RE, _EVERY_WEEKDAY_RE, _EVERY_INTERVAL_RE,
        _IN_DELTA_RE, _AT_TIME_RE, _TOMORROW_RE,
        _TONIGHT_RE, _EVENING_RE, _AFTERNOON_RE, _MORNING_RE,
    ]:
        intent = pattern.sub("", intent)

    # Clean up
    intent = re.sub(r"\s+", " ", intent).strip().rstrip(".,;")
    if not intent:
        intent = cleaned.strip()

    return {
        "intent": intent,
        "deadline": time_info["deadline"],
        "recurrence": time_info["recurrence"],
    }
