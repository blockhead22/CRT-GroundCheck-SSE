from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from routes.agent import router


def _make_client() -> TestClient:
    app = FastAPI()
    app.include_router(router)
    app.state.agent_tool_policy_config = {
        "enabled": True,
        "default_allow": True,
        "global_max_calls_per_run": 10,
        "tools": {},
    }
    app.state.agent_tool_policy_version = 1
    return TestClient(app)


def test_get_tool_policy_returns_state():
    client = _make_client()
    resp = client.get("/api/agent/tool-policy")
    assert resp.status_code == 200
    data = resp.json()
    assert data["ok"] is True
    assert data["version"] == 1
    assert data["config"]["enabled"] is True


def test_put_tool_policy_updates_version_and_config():
    client = _make_client()
    payload = {
        "config": {
            "enabled": True,
            "default_allow": False,
            "global_max_calls_per_run": 7,
            "tools": {
                "execute_code": {
                    "enabled": True,
                    "require_approval": True,
                    "max_calls_per_run": 1,
                    "allowed_channels": ["api"],
                    "denied_channels": [],
                    "allowed_users": [],
                    "denied_users": [],
                }
            },
        }
    }
    put_resp = client.put("/api/agent/tool-policy", json=payload)
    assert put_resp.status_code == 200
    put_data = put_resp.json()
    assert put_data["version"] == 2
    assert put_data["config"]["default_allow"] is False
    assert put_data["config"]["tools"]["execute_code"]["require_approval"] is True

    get_resp = client.get("/api/agent/tool-policy")
    assert get_resp.status_code == 200
    get_data = get_resp.json()
    assert get_data["version"] == 2
    assert get_data["config"]["global_max_calls_per_run"] == 7
