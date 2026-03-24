"""Base channel interface for CRT-GroundCheck.

Provides a common abstraction for sending messages through the CRT engine,
whether called in-process (direct engine access) or via the HTTP API.

As of Sprint 8, the bridge uses /api/chat/stream (SSE) by default so that
Telegram and other channels benefit from intent classification, sub-agent
orchestration, capability re-route, and the full task pipeline.  The old
/api/chat/send path is kept as a fallback.
"""

from __future__ import annotations

import json
import logging
import os
import re
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

import requests

from personal_agent.text_utils import strip_think_blocks

logger = logging.getLogger(__name__)

# Intent types that require user confirmation before executing via Telegram.
# Everything else auto-confirms (system_info, dir_list, git_action, etc.)
_HIGH_RISK_INTENTS = {"file_write", "shell_exec", "desktop_action"}

# Whether to auto-confirm checkpoints for low-risk intents
_AUTO_CONFIRM_LOW_RISK = True


def _derive_origin(msg: "ChannelMessage", destination_id: Optional[str]) -> Optional[str]:
    if not isinstance(msg.raw, dict):
        return None
    explicit = str(msg.raw.get("origin") or "").strip()
    if explicit:
        return explicit
    message_id = msg.raw.get("message_id")
    if message_id is None:
        return None
    destination = str(destination_id or msg.raw.get("chat_id") or "").strip()
    if destination:
        return f"{msg.channel}:{destination}:{message_id}"
    return f"{msg.channel}:message:{message_id}"


@dataclass
class ChannelMessage:
    """A normalized inbound message from any channel."""

    text: str
    thread_id: str
    sender_id: str
    sender_name: str = ""
    channel: str = "unknown"
    important: bool = False
    raw: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ChannelResponse:
    """A normalized outbound response to any channel."""

    text: str
    gates_passed: bool = True
    gate_reason: Optional[str] = None
    confidence: float = 0.7
    contradiction_detected: bool = False
    metadata: Dict[str, Any] = field(default_factory=dict)
    # New fields for task pipeline visibility
    route: str = "conversational"  # "task" or "conversational"
    intent_type: Optional[str] = None
    task_steps: List[Dict[str, Any]] = field(default_factory=list)
    orchestration: Optional[Dict[str, Any]] = None


class CRTBridge:
    """Bridge between channel bots and the CRT engine.

    Three modes:
    - Stream mode (default): Consumes SSE from /api/chat/stream.
      Gets the full pipeline: intent classification, sub-agents, orchestrator.
    - HTTP mode (fallback): POSTs to /api/chat/send.
      Conversational only — no task agent, no tools.
    - Direct mode: Calls engine.query() in-process.
    """

    def __init__(self, api_url: str = "http://127.0.0.1:8123"):
        self.api_url = api_url.rstrip("/")
        self._engine_factory = None  # Optional: direct engine access
        self._use_stream = True  # Use /stream by default
        self._checkpoint_callback: Optional[Callable] = None  # For interactive checkpoints

    def set_engine_factory(self, factory):
        """Set a callable(thread_id) -> CRTEnhancedRAG for direct mode."""
        self._engine_factory = factory

    def set_checkpoint_callback(self, callback: Callable):
        """Set a callback for interactive checkpoint confirmations.

        callback(intent_type: str, description: str) -> bool
        Returns True to confirm, False to cancel.
        """
        self._checkpoint_callback = callback

    def send(self, msg: ChannelMessage) -> ChannelResponse:
        """Process a message through CRT and return the response."""
        if self._engine_factory:
            return self._send_direct(msg)
        if self._use_stream:
            try:
                return self._send_stream(msg)
            except Exception as e:
                logger.warning("[BRIDGE] Stream failed, falling back to /send: %s", e)
                return self._send_http(msg)
        return self._send_http(msg)

    def _build_payload(self, msg: ChannelMessage) -> dict:
        """Build the request payload (shared between /send and /stream)."""
        destination_id = None
        meta_scope = None
        if isinstance(msg.raw, dict):
            raw_chat_id = msg.raw.get("chat_id")
            if raw_chat_id is not None:
                destination_id = str(raw_chat_id)
            raw_scope = msg.raw.get("meta_scope")
            if raw_scope is not None:
                meta_scope = str(raw_scope)
        origin = _derive_origin(msg, destination_id)
        return {
            "thread_id": msg.thread_id,
            "message": msg.text,
            "user_marked_important": msg.important,
            "channel": msg.channel,
            "origin": origin,
            "actor_id": msg.sender_id,
            "channel_destination_id": destination_id,
            "meta_scope": meta_scope,
        }

    def _consume_sse(self, resp, state: dict) -> bool:
        """Parse SSE lines from a requests response and update *state* dict.

        Returns True if a checkpoint was encountered (stream ended early and
        a follow-up confirmation stream is needed).
        """
        checkpoint_hit = False
        for line in resp.iter_lines(decode_unicode=True):
            if not line or not line.startswith("data: "):
                continue

            raw_data = line[6:]
            try:
                event = json.loads(raw_data)
            except json.JSONDecodeError:
                continue

            event_type = event.get("type", "")
            content = event.get("content", "")
            event_meta = event.get("metadata", {})

            # ── Intent preview ──────────────────────────────────────────
            if event_type == "intent_preview":
                state["route"] = event_meta.get("route", state["route"])
                state["intent_type"] = event_meta.get("intent_type", state["intent_type"])
                state["confidence"] = event_meta.get("confidence", state["confidence"])
                logger.info("[BRIDGE:STREAM] Intent: %s/%s (%.2f)",
                            state["route"], state["intent_type"], state["confidence"])

            # ── Checkpoint (task confirmation gate) ─────────────────────
            elif event_type in ("agent_checkpoint", "agent_checkpoint_write", "checkpoint"):
                state["checkpoint_intent"] = event_meta.get("intent_type", "")
                state["checkpoint_desc"] = content or f"Execute {state['checkpoint_intent']} task"
                logger.info("[BRIDGE:STREAM] Checkpoint: %s — %s",
                            state["checkpoint_intent"], state["checkpoint_desc"])
                checkpoint_hit = True
                # Don't break — let the stream finish naturally

            # ── Task acknowledged ───────────────────────────────────────
            elif event_type == "task_acknowledged":
                logger.info("[BRIDGE:STREAM] Task acknowledged: %s", str(content)[:80])

            # ── Tool/subtask progress ───────────────────────────────────
            elif event_type == "tool_start":
                state["task_steps"].append({"tool": content, "status": "running"})
            elif event_type == "tool_result":
                if state["task_steps"]:
                    state["task_steps"][-1]["status"] = "done"
                    state["task_steps"][-1]["result_preview"] = str(content)[:200]

            elif event_type == "subtask_start":
                state["task_steps"].append({
                    "agent": event_meta.get("agent_name", content),
                    "task_id": event_meta.get("task_id", ""),
                    "status": "running",
                })
            elif event_type == "subtask_done":
                tid = event_meta.get("task_id", "")
                for step in state["task_steps"]:
                    if step.get("task_id") == tid:
                        step["status"] = "done"
                        step["duration_ms"] = event_meta.get("duration_ms")
                        break

            elif event_type == "orchestration_done":
                state["orchestration"] = {
                    "merged_trust": event_meta.get("merged_trust"),
                    "all_ok": event_meta.get("all_ok"),
                    "subtask_count": event_meta.get("subtask_count"),
                }

            # ── Streaming tokens (conversational) ───────────────────────
            elif event_type == "token":
                state["answer_parts"].append(content)

            # ── Task done ───────────────────────────────────────────────
            elif event_type == "task_done":
                state["task_answer"] = content
                if event_meta:
                    state["metadata"].update(event_meta)
                    state["gates_passed"] = event_meta.get("gates_passed", True)
                    state["gate_reason"] = event_meta.get("gate_reason")

            # ── Done ────────────────────────────────────────────────────
            elif event_type == "done":
                if content and not state["task_answer"] and not state["answer_parts"]:
                    state["answer_parts"].append(content)
                if event_meta:
                    state["metadata"].update(event_meta)
                    state["gates_passed"] = event_meta.get("gates_passed", state["gates_passed"])
                    state["gate_reason"] = event_meta.get("gate_reason", state["gate_reason"])
                    state["contradiction_detected"] = event_meta.get(
                        "contradiction_detected", state["contradiction_detected"]
                    )
                break

            # ── Error ───────────────────────────────────────────────────
            elif event_type == "error":
                logger.error("[BRIDGE:STREAM] Error event: %s", content)
                state["error"] = content
                break

        return checkpoint_hit

    def _send_stream(self, msg: ChannelMessage) -> ChannelResponse:
        """Send via /api/chat/stream and consume SSE events.

        This gives Telegram the full pipeline: intent classification,
        sub-agent orchestration, capability re-route, side model tap.

        If a checkpoint gate fires (task needs confirmation), the bridge
        auto-confirms low-risk intents and sends a follow-up stream to
        get the actual task result.
        """
        payload = self._build_payload(msg)

        state = {
            "answer_parts": [],
            "task_answer": None,
            "route": "conversational",
            "intent_type": None,
            "confidence": 0.7,
            "gates_passed": True,
            "gate_reason": None,
            "contradiction_detected": False,
            "task_steps": [],
            "orchestration": None,
            "metadata": {},
            "checkpoint_intent": None,
            "checkpoint_desc": None,
            "error": None,
        }

        # ── First stream: send the user's message ──────────────────────
        resp = requests.post(
            f"{self.api_url}/api/chat/stream",
            json=payload,
            timeout=300,
            stream=True,
            headers={"Accept": "text/event-stream"},
        )
        resp.raise_for_status()

        checkpoint_hit = self._consume_sse(resp, state)

        if state["error"]:
            return ChannelResponse(
                text=f"Error: {state['error']}",
                gates_passed=False,
                gate_reason="stream_error",
                route=state["route"],
                intent_type=state["intent_type"],
            )

        # ── Handle checkpoint: auto-confirm and consume second stream ──
        if checkpoint_hit and state["checkpoint_intent"]:
            cp_intent = state["checkpoint_intent"]
            should_confirm = True

            if cp_intent in _HIGH_RISK_INTENTS and self._checkpoint_callback:
                should_confirm = self._checkpoint_callback(
                    cp_intent, state["checkpoint_desc"] or ""
                )

            if should_confirm:
                logger.info("[BRIDGE:STREAM] Auto-confirming checkpoint: %s", cp_intent)
                # Send confirmation as a new stream and consume it
                confirm_payload = dict(payload)
                confirm_payload["message"] = "yes"
                try:
                    confirm_resp = requests.post(
                        f"{self.api_url}/api/chat/stream",
                        json=confirm_payload,
                        timeout=300,
                        stream=True,
                        headers={"Accept": "text/event-stream"},
                    )
                    confirm_resp.raise_for_status()
                    self._consume_sse(confirm_resp, state)
                except Exception as e:
                    logger.warning("[BRIDGE:STREAM] Confirmation stream failed: %s", e)
            else:
                return ChannelResponse(
                    text=f"Task cancelled: {state['checkpoint_desc']}",
                    route="task",
                    intent_type=cp_intent,
                )

        # ── Assemble final answer ──────────────────────────────────────
        final_answer = state["task_answer"] or "".join(state["answer_parts"])
        if not final_answer:
            final_answer = "I processed your request but didn't generate a response."

        final_answer = strip_think_blocks(final_answer)

        return ChannelResponse(
            text=final_answer,
            gates_passed=state["gates_passed"],
            gate_reason=state["gate_reason"],
            confidence=state["confidence"],
            contradiction_detected=state["contradiction_detected"],
            metadata=state["metadata"],
            route=state["route"],
            intent_type=state["intent_type"],
            task_steps=state["task_steps"],
            orchestration=state["orchestration"],
        )

    def _send_http(self, msg: ChannelMessage) -> ChannelResponse:
        """Send via the FastAPI HTTP endpoint (fallback, conversational only)."""
        payload = self._build_payload(msg)
        try:
            resp = requests.post(
                f"{self.api_url}/api/chat/send",
                json=payload,
                timeout=300,
            )
            resp.raise_for_status()
            data = resp.json()
            return ChannelResponse(
                text=strip_think_blocks(data.get("answer", "Sorry, I couldn't process that.")),
                gates_passed=data.get("gates_passed", True),
                gate_reason=data.get("gate_reason"),
                confidence=data.get("metadata", {}).get("confidence", 0.7),
                contradiction_detected=data.get("metadata", {}).get(
                    "contradiction_detected", False
                ),
                metadata=data.get("metadata", {}),
            )
        except requests.ConnectionError:
            logger.error("[BRIDGE] Cannot reach CRT API at %s", self.api_url)
            return ChannelResponse(
                text="I'm having trouble connecting to my memory system. Is the CRT server running?",
                gates_passed=False,
                gate_reason="connection_error",
            )
        except Exception as e:
            logger.error("[BRIDGE] HTTP error: %s", e)
            return ChannelResponse(
                text=f"Something went wrong: {e}",
                gates_passed=False,
                gate_reason="error",
            )

    def _send_direct(self, msg: ChannelMessage) -> ChannelResponse:
        """Send directly through the CRT engine (in-process)."""
        try:
            engine = self._engine_factory(msg.thread_id)
            result = engine.query(
                user_query=msg.text,
                user_marked_important=msg.important,
                thread_id=msg.thread_id,
                channel=msg.channel,
                origin=_derive_origin(msg, None),
            )
            answer = strip_think_blocks(result.get("answer", "I don't have an answer for that."))
            return ChannelResponse(
                text=answer,
                gates_passed=result.get("gates_passed", True),
                gate_reason=result.get("gate_reason"),
                confidence=result.get("confidence", 0.7),
                contradiction_detected=result.get("contradiction_detected", False),
                metadata={
                    k: v
                    for k, v in result.items()
                    if k not in ("answer", "gates_passed", "gate_reason")
                },
            )
        except Exception as e:
            logger.error("[BRIDGE] Direct engine error: %s", e)
            return ChannelResponse(
                text=f"Engine error: {e}",
                gates_passed=False,
                gate_reason="engine_error",
            )
