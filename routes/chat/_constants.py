"""Module-level constants and shared state extracted from routes/chat.py."""

from __future__ import annotations

import contextvars
import os
import queue as _queue_mod
import re
import threading
from typing import Dict, Optional

# ---------------------------------------------------------------------------
# Pipeline status queue -- allows chat_send stages to push real-time status
# events that the SSE generator can yield to the frontend.
# ---------------------------------------------------------------------------
_pipeline_status_queue: contextvars.ContextVar[Optional[_queue_mod.Queue]] = contextvars.ContextVar(
    "_pipeline_status_queue", default=None
)

# ---------------------------------------------------------------------------
# Structured event queue -- lets chat_send() push retrieval/trust_shift/
# verification dicts without yielding (which would turn it into a generator).
# ---------------------------------------------------------------------------
_pipeline_event_queue: contextvars.ContextVar[Optional[_queue_mod.Queue]] = contextvars.ContextVar(
    "_pipeline_event_queue", default=None
)

# ---------------------------------------------------------------------------
# Tasking interval
# ---------------------------------------------------------------------------
try:
    _TASKING_INTERVAL_SECONDS = float(os.getenv("CRT_TASKING_INTERVAL_SECONDS", "0") or 0)
except Exception:
    _TASKING_INTERVAL_SECONDS = 0.0

_TASKING_LAST_RUN: Dict[str, float] = {}
_TASKING_LOCK = threading.Lock()

# ---------------------------------------------------------------------------
# Expand triggers
# ---------------------------------------------------------------------------
_EXPAND_TRIGGERS = (
    "expand",
    "expand more",
    "explain more",
    "tell me more",
    "go deeper",
    "more detail",
    "more details",
    "elaborate",
    "continue",
)

# ---------------------------------------------------------------------------
# Continuity followup hints
# ---------------------------------------------------------------------------
_CONTINUITY_FOLLOWUP_HINTS = (
    "tell me more",
    "continue",
    "try again",
    "let's try again",
    "lets try again",
    "retry that",
    "redo that",
    "and then",
    "what about",
    "how about",
    "what else",
    "how do you know",
    "how are you sure",
    "how did you know",
    "the highlights",
    "highlights",
    "summarize",
    "summary",
    "give me details",
    "details about that",
    "more about that",
    "elaborate",
    "expand on",
    "about that",
    "about this",
    "about it",
    "go on",
    "keep going",
    "go deeper",
    "explain that",
    "explain it",
    "why is that",
    "interesting fact",
    "who am i",
    "about me",
    "about who i am",
    "more about me",
)

# ---------------------------------------------------------------------------
# Pending followup shortcuts
# ---------------------------------------------------------------------------
_PENDING_FOLLOWUP_SHORTCUTS = (
    "tell me",
    "go on",
    "go ahead",
    "continue",
    "keep going",
    "say more",
    "what do you mean",
    "explain",
    "explain that",
    "explain it",
)

# ---------------------------------------------------------------------------
# GroundCheck bridge state + contradiction caveat regex
# ---------------------------------------------------------------------------
_GROUNDCHECK_BRIDGE_LOCK = threading.Lock()
_GROUNDCHECK_BRIDGE_LAST_SYNC: Dict[str, float] = {}
_CONTRADICTION_CAVEAT_RE = re.compile(
    r"("
    r"\b(most recent|latest|conflicting|however|according to)\b|"
    r"\b(updat(e|ed|ing)|correct(ed|ing|ion)?|clarif(y|ied|ying))\b|"
    r"\b(earlier|previously|before|prior|former)\b|"
    r"\b(chang(e|ed|ing)|revis(e|ed|ing)|adjust(ed|ing)?|modif(y|ied|ying))\b|"
    r"\(changed from|\(most recent|\(updated|"
    r"\b(versus|vs|compared to)\b|"
    r"\bno longer\b|"
    r"\bas of\b"
    r")",
    flags=re.IGNORECASE,
)
