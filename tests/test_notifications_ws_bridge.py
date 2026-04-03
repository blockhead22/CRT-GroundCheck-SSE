import asyncio
from types import SimpleNamespace

from personal_agent import notifications as notifications_mod


class _FakeBus:
    def __init__(self) -> None:
        self.calls = []

    async def emit(self, event_type, data=None, thread_id=None):
        self.calls.append(
            {
                "event_type": event_type,
                "data": data or {},
                "thread_id": thread_id,
            }
        )
        return 1


def test_commitment_notification_emits_thread_scoped_bus_event(monkeypatch):
    fake_bus = _FakeBus()
    monkeypatch.setattr(
        "personal_agent.event_bus.get_event_bus",
        lambda: fake_bus,
    )

    commitment = SimpleNamespace(
        commitment_id="c1",
        thread_id="thread-123",
        intent="follow up",
        description="Follow up tomorrow",
        priority="medium",
        consequence="none",
        recurrence="daily",
        fire_count=2,
    )

    pushed = asyncio.run(notifications_mod.emit_commitment_notification(commitment))

    assert pushed == 0
    assert len(fake_bus.calls) == 1
    call = fake_bus.calls[0]
    assert call["event_type"] == "notification"
    assert call["thread_id"] == "thread-123"
    assert call["data"]["subtype"] == "commitment"
    assert call["data"]["metadata"]["thread_id"] == "thread-123"


def test_generic_notification_uses_metadata_thread_for_bus_event(monkeypatch):
    fake_bus = _FakeBus()
    monkeypatch.setattr(
        "personal_agent.event_bus.get_event_bus",
        lambda: fake_bus,
    )

    pushed = asyncio.run(
        notifications_mod.emit_generic_notification(
            event_type="heartbeat_contradiction",
            content="I noticed something changed",
            metadata={"thread_id": "thread-xyz", "drift_score": 0.42},
        )
    )

    assert pushed == 0
    assert len(fake_bus.calls) == 1
    call = fake_bus.calls[0]
    assert call["event_type"] == "notification"
    assert call["thread_id"] == "thread-xyz"
    assert call["data"]["subtype"] == "heartbeat_contradiction"
    assert call["data"]["metadata"]["drift_score"] == 0.42
