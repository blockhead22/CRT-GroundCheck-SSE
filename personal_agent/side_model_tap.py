"""
Side Model Tap — lightweight LLM "quick tap" for situational awareness.

Three triggers:
  1. Ambiguous input  — intent classifier is unsure → ask clarifying question
  2. Post-task        — task just completed → suggest next step from context
  3. Reconnect        — user returns after silence → reconnect to open work

Uses gpt-4o-mini via the existing CloudFeatureService for ~150ms responses.
Falls back gracefully (returns None) if cloud is unavailable.
"""
from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


# ── Result types ────────────────────────────────────────────────────────

@dataclass
class TapResult:
    """Result from a side model tap."""
    action: str          # "clarify" | "suggest" | "reconnect" | "none"
    message: str         # Human-readable message to show the user
    confidence: float    # How confident the tap is in its suggestion
    metadata: Dict[str, Any] = field(default_factory=dict)
    latency_ms: int = 0


# ── Prompt templates ────────────────────────────────────────────────────

_CLARIFY_SYSTEM = """You are a quick-thinking intent disambiguator for a personal AI assistant called Aether.
The user sent a message but the intent is unclear. You have context about:
- What tools Aether can use (desktop control, file ops, git, shell, system info, web fetch)
- What tasks are currently open
- Recent conversation history

Your job: determine if the message needs clarification before acting, or if it's clear enough to proceed.

Respond with JSON only:
{
  "needs_clarification": true/false,
  "clarification_question": "short question if needed, null otherwise",
  "likely_intent": "best guess intent type if any",
  "confidence": 0.0-1.0
}"""

_SUGGEST_SYSTEM = """You are a proactive follow-up suggester for a personal AI assistant called Aether.
A task just completed. Based on:
- What was just done
- What tasks/todos are still open
- Recent context

Suggest a natural next step. Be brief and conversational — one sentence max.
If there's nothing useful to suggest, say so.

Respond with JSON only:
{
  "has_suggestion": true/false,
  "suggestion": "brief follow-up message or null",
  "suggested_action": "optional prefilled user message to trigger the action, or null",
  "relates_to_open_task": true/false
}"""

_RECONNECT_SYSTEM = """You are a context reconnector for a personal AI assistant called Aether.
The user is back after being idle. You know:
- What tasks are open/in-progress
- What was last discussed
- How long they've been away

Generate a brief, natural welcome-back message that reconnects them to their work.
If nothing is pending, just say a brief greeting.

Respond with JSON only:
{
  "has_context": true/false,
  "message": "brief reconnection message",
  "open_task_summary": "what's pending, or null"
}"""


# ── Main class ──────────────────────────────────────────────────────────

class SideModelTap:
    """Lightweight LLM side-channel for situational awareness."""

    def __init__(self, cloud_service=None):
        """
        Args:
            cloud_service: A CloudFeatureService instance (or None for disabled).
        """
        self._cloud = cloud_service
        self._call_count = 0
        self._total_latency_ms = 0

    # ── Public API ──────────────────────────────────────────────────

    def clarify(
        self,
        message: str,
        open_tasks: Optional[List[Dict]] = None,
        recent_history: Optional[List[str]] = None,
        classifier_confidence: float = 0.0,
    ) -> Optional[TapResult]:
        """Check if an ambiguous message needs clarification before routing.

        Call this when the regex classifier returns low confidence or
        falls through to conversational for something that looks task-like.

        Args:
            message: The user's message
            open_tasks: Active tasks from the session ledger
            recent_history: Last few messages for context
            classifier_confidence: What the regex classifier scored

        Returns:
            TapResult with action="clarify" if clarification needed, else None.
        """
        if not self._is_available():
            return None

        # Build context
        context_parts = [f"User message: \"{message}\""]
        context_parts.append(f"Classifier confidence: {classifier_confidence:.2f}")

        if open_tasks:
            task_strs = [t.get("description", t.get("intent_type", "unknown")) for t in open_tasks[:3]]
            context_parts.append(f"Open tasks: {', '.join(task_strs)}")
        else:
            context_parts.append("Open tasks: none")

        if recent_history:
            context_parts.append(f"Recent messages: {' | '.join(recent_history[-3:])}")

        prompt = "\n".join(context_parts)

        result = self._call(_CLARIFY_SYSTEM, prompt, feature="side_tap_clarify")
        if result is None:
            return None

        needs = result.get("needs_clarification", False)
        if not needs:
            return None

        return TapResult(
            action="clarify",
            message=result.get("clarification_question", "Could you clarify what you'd like me to do?"),
            confidence=result.get("confidence", 0.5),
            metadata={
                "likely_intent": result.get("likely_intent"),
                "classifier_confidence": classifier_confidence,
            },
            latency_ms=self._last_latency,
        )

    def suggest_next(
        self,
        completed_task: Dict[str, Any],
        open_tasks: Optional[List[Dict]] = None,
        recent_history: Optional[List[str]] = None,
    ) -> Optional[TapResult]:
        """Suggest a follow-up after a task completes.

        Call this right after task_done is emitted.

        Args:
            completed_task: Metadata about what just completed (intent_type, answer, etc.)
            open_tasks: Active tasks from the session ledger
            recent_history: Last few messages

        Returns:
            TapResult with action="suggest" if there's a useful follow-up, else None.
        """
        if not self._is_available():
            return None

        context_parts = [
            f"Just completed: {completed_task.get('intent_type', 'unknown')}",
            f"Result: {str(completed_task.get('answer', ''))[:200]}",
        ]

        if open_tasks:
            task_strs = [t.get("description", t.get("intent_type", "unknown")) for t in open_tasks[:3]]
            context_parts.append(f"Open tasks: {', '.join(task_strs)}")
        else:
            context_parts.append("Open tasks: none")

        if recent_history:
            context_parts.append(f"Recent conversation: {' | '.join(recent_history[-3:])}")

        prompt = "\n".join(context_parts)

        result = self._call(_SUGGEST_SYSTEM, prompt, feature="side_tap_suggest")
        if result is None:
            return None

        if not result.get("has_suggestion", False):
            return None

        return TapResult(
            action="suggest",
            message=result.get("suggestion", ""),
            confidence=0.7,
            metadata={
                "suggested_action": result.get("suggested_action"),
                "relates_to_open_task": result.get("relates_to_open_task", False),
                "completed_intent": completed_task.get("intent_type"),
            },
            latency_ms=self._last_latency,
        )

    def reconnect(
        self,
        open_tasks: Optional[List[Dict]] = None,
        last_message_age_seconds: float = 0,
        recent_history: Optional[List[str]] = None,
    ) -> Optional[TapResult]:
        """Generate a reconnection message after user returns from idle.

        Call this when the user sends a message after >5 minutes of silence.

        Args:
            open_tasks: Active tasks from the session ledger
            last_message_age_seconds: How long since the last message
            recent_history: Last few messages before the gap

        Returns:
            TapResult with action="reconnect" if there's context to reconnect to, else None.
        """
        if not self._is_available():
            return None

        # Only trigger if meaningful idle time
        if last_message_age_seconds < 300:  # 5 minutes
            return None

        idle_minutes = int(last_message_age_seconds / 60)

        context_parts = [f"User has been away for {idle_minutes} minutes."]

        if open_tasks:
            task_strs = [t.get("description", t.get("intent_type", "unknown")) for t in open_tasks[:3]]
            context_parts.append(f"Open tasks: {', '.join(task_strs)}")
        else:
            context_parts.append("No open tasks.")

        if recent_history:
            context_parts.append(f"Last conversation: {' | '.join(recent_history[-3:])}")

        prompt = "\n".join(context_parts)

        result = self._call(_RECONNECT_SYSTEM, prompt, feature="side_tap_reconnect")
        if result is None:
            return None

        if not result.get("has_context", False):
            return None

        return TapResult(
            action="reconnect",
            message=result.get("message", "Welcome back!"),
            confidence=0.6,
            metadata={
                "idle_minutes": idle_minutes,
                "open_task_summary": result.get("open_task_summary"),
            },
            latency_ms=self._last_latency,
        )

    # ── Stats ───────────────────────────────────────────────────────

    @property
    def stats(self) -> Dict[str, Any]:
        return {
            "calls": self._call_count,
            "total_latency_ms": self._total_latency_ms,
            "avg_latency_ms": (
                self._total_latency_ms // self._call_count
                if self._call_count > 0 else 0
            ),
        }

    # ── Internal ────────────────────────────────────────────────────

    _last_latency: int = 0

    def _is_available(self) -> bool:
        """Check if the cloud service is available for side taps."""
        if self._cloud is None:
            return False
        # Reuse the cloud service's OpenAI availability check
        try:
            return self._cloud._openai_available()
        except Exception:
            return False

    def _call(
        self,
        system: str,
        prompt: str,
        feature: str = "side_tap",
    ) -> Optional[Dict[str, Any]]:
        """Make a quick LLM call via the cloud service.

        Returns parsed JSON dict or None on failure.
        """
        t0 = time.perf_counter()
        try:
            result = self._cloud._call_openai(
                system, prompt, max_tokens=200, feature=feature,
            )
            self._last_latency = int((time.perf_counter() - t0) * 1000)
            self._call_count += 1
            self._total_latency_ms += self._last_latency

            if result is not None:
                logger.info(
                    "[SIDE_TAP] %s: %dms, result=%s",
                    feature, self._last_latency, json.dumps(result)[:200],
                )
            else:
                logger.debug("[SIDE_TAP] %s: %dms, no result", feature, self._last_latency)

            return result

        except Exception as e:
            self._last_latency = int((time.perf_counter() - t0) * 1000)
            logger.warning("[SIDE_TAP] %s failed (%dms): %s", feature, self._last_latency, e)
            return None


# ── Module-level singleton ──────────────────────────────────────────────

_tap_instance: Optional[SideModelTap] = None


def get_side_tap(cloud_service=None) -> SideModelTap:
    """Get or create the SideModelTap singleton.

    If cloud_service is provided on first call, it's used to initialize.
    Subsequent calls return the same instance.
    """
    global _tap_instance
    if _tap_instance is None:
        _tap_instance = SideModelTap(cloud_service=cloud_service)
    elif cloud_service is not None and _tap_instance._cloud is None:
        _tap_instance._cloud = cloud_service
    return _tap_instance
