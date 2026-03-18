"""Base channel interface for CRT-GroundCheck.

Provides a common abstraction for sending messages through the CRT engine,
whether called in-process (direct engine access) or via the HTTP API.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from typing import Any, Dict, Optional

import requests

from personal_agent.text_utils import strip_think_blocks

logger = logging.getLogger(__name__)


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


class CRTBridge:
    """Bridge between channel bots and the CRT engine.

    Two modes:
    - HTTP mode (default): POSTs to the running FastAPI server at /api/chat/send.
      Works when the bot runs as a separate process.
    - Direct mode: Calls engine.query() in-process. Requires the FastAPI app
      to be importable and initialized. Set via set_engine_factory().
    """

    def __init__(self, api_url: str = "http://127.0.0.1:8123"):
        self.api_url = api_url.rstrip("/")
        self._engine_factory = None  # Optional: direct engine access

    def set_engine_factory(self, factory):
        """Set a callable(thread_id) -> CRTEnhancedRAG for direct mode."""
        self._engine_factory = factory

    def send(self, msg: ChannelMessage) -> ChannelResponse:
        """Process a message through CRT and return the response."""
        if self._engine_factory:
            return self._send_direct(msg)
        return self._send_http(msg)

    def _send_http(self, msg: ChannelMessage) -> ChannelResponse:
        """Send via the FastAPI HTTP endpoint."""
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
        payload = {
            "thread_id": msg.thread_id,
            "message": msg.text,
            "user_marked_important": msg.important,
            "channel": msg.channel,
            "origin": origin,
            "actor_id": msg.sender_id,
            "channel_destination_id": destination_id,
            "meta_scope": meta_scope,
        }
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
