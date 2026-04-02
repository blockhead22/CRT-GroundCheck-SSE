from __future__ import annotations

import pytest

from personal_agent.stream_events import (
    CHAT_STREAM_EVENT_TYPES,
    WS_SERVER_EVENT_TYPES,
    encode_sse_event,
    make_stream_event,
    normalize_stream_event,
)


def test_make_stream_event_normalizes_chat_envelope() -> None:
    event = make_stream_event(
        "tool_start",
        "Running search_code",
        metadata={"tool_name": "search_code", "step_index": 1},
    )
    assert event == {
        "type": "tool_start",
        "content": "Running search_code",
        "metadata": {"tool_name": "search_code", "step_index": 1},
    }


def test_ws_only_event_requires_allow_ws() -> None:
    with pytest.raises(ValueError):
        normalize_stream_event({"type": "connected", "content": "ok"})

    event = normalize_stream_event({"type": "connected", "content": "ok"}, allow_ws=True)
    assert event["type"] == "connected"
    assert event["content"] == "ok"


def test_metadata_must_be_mapping() -> None:
    with pytest.raises(TypeError):
        normalize_stream_event({"type": "status", "content": "x", "metadata": ["bad"]})


def test_encode_sse_event_uses_normalized_payload() -> None:
    payload = encode_sse_event({"type": "phase_start", "phase": "plan", "content": "Processing"})
    assert payload.startswith("data: ")
    assert '"type": "phase_start"' in payload
    assert '"phase": "plan"' in payload


def test_contract_sets_include_expected_types() -> None:
    assert "followup_suggest" in CHAT_STREAM_EVENT_TYPES
    assert "connected" in WS_SERVER_EVENT_TYPES
    assert "proactive_turn" in WS_SERVER_EVENT_TYPES
