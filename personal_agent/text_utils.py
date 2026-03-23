"""Shared text utilities for CRT.

Consolidates commonly duplicated helpers: think-tag stripping,
thread ID sanitisation, whitespace normalisation, and think-tag
content extraction (for deepseek-r1 style responses).

Every call-site that previously had its own copy should import from here.
"""

from __future__ import annotations

import re
from typing import Optional, Tuple

# ---------------------------------------------------------------------------
# Compiled patterns (module-level for performance)
# ---------------------------------------------------------------------------

_THINKING_TAG_RE = re.compile(r"</?think(?:ing)?>", re.IGNORECASE)
_THINK_BLOCK_RE = re.compile(r"<think>(.*?)</think>", re.DOTALL | re.IGNORECASE)
_THINKING_BLOCK_RE = re.compile(r"<thinking>(.*?)</thinking>", re.DOTALL | re.IGNORECASE)
# Heuristic: qwen sometimes dumps reasoning without tags — detect and strip
# Patterns like "Wait, the user's...", "So maybe the original...", "Let me think..."
_REASONING_LEAK_RE = re.compile(
    r"(?:^|\n)"
    r"(?:Wait,? |So (?:maybe|perhaps|the)|Let me (?:think|check|re-read)|"
    r"Hmm,? |The user'?s (?:correction|original|stored|message)|"
    r"But (?:the correction|in this case|wait)|"
    r"Maybe the original answer|"
    r"Or maybe the user)"
    r".*?(?=\n[A-Z]|\n\n|\Z)",
    re.DOTALL | re.IGNORECASE,
)
_THREAD_ID_RE = re.compile(r"[^a-zA-Z0-9_-]+")
_WS_RE = re.compile(r"\s+")


# ---------------------------------------------------------------------------
# Think-tag helpers
# ---------------------------------------------------------------------------

def strip_thinking_tags(text: str) -> str:
    """Remove ``<think>``/``<thinking>`` wrapper tags from text.

    This does **not** remove the *content* inside the tags – only the
    tags themselves.  Use :func:`strip_think_blocks` to remove both
    tags and content.
    """
    if not text:
        return ""
    return _THINKING_TAG_RE.sub("", text).strip()


def strip_think_blocks(text: str) -> str:
    """Remove entire ``<think>…</think>`` blocks (tags + content).

    Also strips ``<thinking>…</thinking>`` blocks and heuristic
    reasoning leaks from models like qwen that sometimes dump
    internal reasoning without tags.
    """
    if not text:
        return ""
    result = _THINK_BLOCK_RE.sub("", text)
    result = _THINKING_BLOCK_RE.sub("", result)
    result = _REASONING_LEAK_RE.sub("", result)
    return result.strip()


def extract_think_content(text: str) -> Tuple[str, str]:
    """Split *text* into (thinking_content, visible_response).

    For LLMs like deepseek-r1 that wrap all reasoning in ``<think>``
    tags, this extracts what's inside and what's outside.

    Returns ``("", cleaned)`` when no think tags are present.
    """
    if not text:
        return "", ""
    match = _THINK_BLOCK_RE.search(text)
    if not match:
        return "", strip_thinking_tags(text)
    thinking = match.group(1).strip()
    visible = _THINK_BLOCK_RE.sub("", text).strip()
    # Remove any stray tags that survived
    visible = _THINKING_TAG_RE.sub("", visible).strip()
    return thinking, visible


# ---------------------------------------------------------------------------
# Thread-ID sanitisation
# ---------------------------------------------------------------------------

def sanitize_thread_id(value: str, *, max_length: int = 64) -> str:
    """Normalise a thread ID to ``[a-zA-Z0-9_-]`` characters.

    Returns ``"default"`` for empty / whitespace-only input.
    """
    value = (value or "").strip()
    if not value:
        return "default"
    value = _THREAD_ID_RE.sub("_", value)
    return value[:max_length] or "default"


# ---------------------------------------------------------------------------
# Whitespace normalisation
# ---------------------------------------------------------------------------

def norm_whitespace(text: str) -> str:
    """Collapse runs of whitespace to a single space and strip."""
    return _WS_RE.sub(" ", (text or "").strip())


def norm_text(text: str) -> str:
    """Lower-case + whitespace-normalised version of *text*."""
    return norm_whitespace(text).lower()
