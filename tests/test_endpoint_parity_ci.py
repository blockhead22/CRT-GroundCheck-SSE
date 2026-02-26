from __future__ import annotations

import json
from pathlib import Path
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

import crt_api
from channels.base import CRTBridge, ChannelMessage
from personal_agent.crt_rag import CRTEnhancedRAG


class FakeLLM:
    def generate(self, prompt: str, max_tokens: int = 1000, stream: bool = False):
        return "OK"


class _BridgeResp:
    def __init__(self, status_code: int, payload: dict):
        self.status_code = int(status_code)
        self._payload = payload

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")

    def json(self):
        return self._payload


def _parse_sse(raw_text: str) -> list[dict]:
    out: list[dict] = []
    for line in raw_text.splitlines():
        if line.startswith("data: "):
            out.append(json.loads(line[len("data: ") :]))
    return out


@pytest.fixture()
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    class PatchedRAG(CRTEnhancedRAG):
        def __init__(self, memory_db: str, ledger_db: str, *args, **kwargs):
            mem_name = Path(memory_db).name
            led_name = Path(ledger_db).name
            profile_name = f"profile_{Path(memory_db).stem}.db"
            super().__init__(
                memory_db=str(tmp_path / mem_name),
                ledger_db=str(tmp_path / led_name),
                profile_db=str(tmp_path / profile_name),
                llm_client=FakeLLM(),
            )

    def _runtime_config():
        return {
            "background_jobs": {"enabled": False, "idle_scheduler_enabled": False},
            "training_loop": {"enabled": False},
            "learned_suggestions": {"enabled": False},
            "dnnt_retraining": {"enabled": False},
        }

    monkeypatch.setenv("CRT_REFLECTION_LOOP_ENABLED", "false")
    monkeypatch.setenv("CRT_PERSONALITY_LOOP_ENABLED", "false")
    monkeypatch.setenv("CRT_JOURNAL_SELF_REPLY_LOOP_ENABLED", "false")
    monkeypatch.setenv("CRT_HEARTBEAT_LOOP_ENABLED", "false")

    monkeypatch.setattr(crt_api, "CRTEnhancedRAG", PatchedRAG)
    monkeypatch.setattr(crt_api, "get_runtime_config", _runtime_config)

    app = crt_api.create_app()
    return TestClient(app)


def test_send_and_stream_done_payloads_match(client: TestClient):
    message = "My name is Parity Tester."
    send_tid = f"parity_send_{uuid4().hex[:8]}"
    stream_tid = f"parity_stream_{uuid4().hex[:8]}"

    send_resp = client.post(
        "/api/chat/send",
        json={"thread_id": send_tid, "message": message},
    )
    assert send_resp.status_code == 200
    send_data = send_resp.json()

    stream_resp = client.post(
        "/api/chat/stream",
        json={"thread_id": stream_tid, "message": message},
    )
    assert stream_resp.status_code == 200
    events = _parse_sse(stream_resp.text)
    done = next(e for e in events if e.get("type") == "done")

    assert done.get("content") == send_data.get("answer")
    assert done.get("metadata", {}).get("gate_reason") == send_data.get("gate_reason")
    assert done.get("metadata", {}).get("gates_passed") == send_data.get("gates_passed")
    assert "error" not in [e.get("type") for e in events]


def test_telegram_bridge_matches_send_endpoint(client: TestClient, monkeypatch: pytest.MonkeyPatch):
    bridge = CRTBridge(api_url="http://testserver")

    def fake_post(url: str, json: dict, timeout: int = 120):
        if "/api/chat/send" not in url:
            return _BridgeResp(404, {"error": "not found"})
        path = "/api/chat/send"
        resp = client.post(path, json=json)
        return _BridgeResp(resp.status_code, resp.json())

    import channels.base as base_mod

    monkeypatch.setattr(base_mod.requests, "post", fake_post)

    thread_id = f"parity_tg_{uuid4().hex[:8]}"
    msg = "My favorite color is orange."

    api_resp = client.post(
        "/api/chat/send",
        json={"thread_id": thread_id + "_api", "message": msg},
    )
    assert api_resp.status_code == 200
    api_data = api_resp.json()

    ch_resp = bridge.send(
        ChannelMessage(
            text=msg,
            thread_id=thread_id + "_tg",
            sender_id="123",
            sender_name="Parity",
            channel="telegram",
        )
    )

    assert ch_resp.text == api_data["answer"]
    assert ch_resp.gates_passed == api_data["gates_passed"]
    assert ch_resp.gate_reason == api_data.get("gate_reason")

