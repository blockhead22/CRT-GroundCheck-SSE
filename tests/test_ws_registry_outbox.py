from __future__ import annotations

import asyncio
from typing import Any, List

from starlette.websockets import WebSocketState

from personal_agent.outbox import get_outbox, reset_outbox
from routes.ws import ConnectionRegistry


class _FakeWebSocket:
    def __init__(self) -> None:
        self.client_state = WebSocketState.CONNECTED
        self.sent: List[dict[str, Any]] = []
        self.accepted = False

    async def accept(self) -> None:
        self.accepted = True

    async def send_json(self, data: dict[str, Any]) -> None:
        self.sent.append(data)


def test_subscribe_flushes_existing_outbox_message() -> None:
    async def _run() -> None:
        reset_outbox()
        outbox = get_outbox()
        outbox.push(
            thread_id="thread-1",
            content="Background task finished.",
            trigger="job_complete",
            metadata={"job_id": "j1"},
        )

        registry = ConnectionRegistry()
        ws = _FakeWebSocket()
        await registry.connect(ws)
        await registry.subscribe_to(ws, ["thread:thread-1"])

        proactive = [evt for evt in ws.sent if evt.get("type") == "proactive_turn"]
        assert len(proactive) == 1
        assert proactive[0]["content"] == "Background task finished."
        assert proactive[0]["thread_id"] == "thread-1"
        assert outbox.count("thread-1") == 0

        await registry.disconnect(ws)

    asyncio.run(_run())


def test_outbox_push_immediately_flushes_to_subscribed_thread() -> None:
    async def _run() -> None:
        reset_outbox()
        outbox = get_outbox()
        registry = ConnectionRegistry()
        ws = _FakeWebSocket()

        await registry.connect(ws)
        await registry.subscribe_to(ws, ["thread:thread-2"])
        baseline = len(ws.sent)

        outbox.push(
            thread_id="thread-2",
            content="I found something while you were away.",
            trigger="proactive_research",
            metadata={"source": "research"},
        )

        await asyncio.sleep(0.05)

        new_events = ws.sent[baseline:]
        proactive = [evt for evt in new_events if evt.get("type") == "proactive_turn"]
        assert len(proactive) == 1
        assert proactive[0]["content"] == "I found something while you were away."
        assert proactive[0]["metadata"]["source"] == "research"
        assert outbox.count("thread-2") == 0

        await registry.disconnect(ws)

    asyncio.run(_run())
