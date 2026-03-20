from __future__ import annotations

import json
import subprocess
from pathlib import Path

from personal_agent import openclaw_bridge


def test_build_openclaw_prompt_includes_crt_helper_when_available(tmp_path: Path, monkeypatch) -> None:
    helper = tmp_path / "crt_client.py"
    helper.write_text("# helper\n", encoding="utf-8")
    monkeypatch.setenv("OPENCLAW_CRT_CLIENT", str(helper))

    prompt = openclaw_bridge.build_openclaw_prompt(
        user_command="research the latest memory systems",
        thread_id="tg_123",
        crt_api_url="http://127.0.0.1:8123",
        channel="telegram",
        origin="telegram:123:77",
        actor_id="123",
        structured_facts={"favorite_color": "orange"},
        include_api_guide=True,
        max_fact_items=8,
    )

    assert "CRT API base: http://127.0.0.1:8123" in prompt
    assert str(helper) in prompt
    assert "Compact CRT facts:" in prompt
    assert "favorite_color" in prompt


def test_run_openclaw_agent_exports_crt_env(monkeypatch) -> None:
    captured: dict = {}

    def _fake_run(cmd, capture_output, text, encoding, errors, timeout, cwd, env):
        captured["cmd"] = cmd
        captured["timeout"] = timeout
        captured["cwd"] = cwd
        captured["env"] = env
        captured["encoding"] = encoding
        captured["errors"] = errors
        return subprocess.CompletedProcess(cmd, 0, stdout='{"output":"delegated ok"}', stderr="")

    monkeypatch.setattr(openclaw_bridge.subprocess, "run", _fake_run)
    monkeypatch.setenv("OPENCLAW_CRT_CLIENT", r"C:\temp\crt_client.py")
    monkeypatch.setenv("OPENCLAW_BIN", r"C:\Users\block\AppData\Roaming\npm\openclaw.cmd")

    result = openclaw_bridge.run_openclaw_agent(
        user_command="research github issues",
        thread_id="tg_999",
        crt_api_url="http://127.0.0.1:8123",
        channel="telegram",
        origin="telegram:999:88",
        actor_id="999",
        structured_facts={"favorite_color": "orange"},
        runtime_config={"openclaw_handoff": {"timeout_seconds": 30}},
        workdir=Path("d:/AI_round2"),
    )

    assert result["ok"] is True
    assert result["answer"] == "delegated ok"
    assert captured["cmd"][0] == r"C:\Users\block\AppData\Roaming\npm\openclaw.cmd"
    assert captured["encoding"] == "utf-8"
    assert captured["errors"] == "replace"
    assert captured["env"]["CRT_API_URL"] == "http://127.0.0.1:8123"
    assert captured["env"]["CRT_THREAD_ID"] == "tg_999"
    assert captured["env"]["CRT_CHANNEL"] == "telegram"
    assert captured["env"]["CRT_ORIGIN"] == "telegram:999:88"
    assert captured["env"]["CRT_ACTOR_ID"] == "999"
    assert captured["env"]["OPENCLAW_CRT_CLIENT"] == r"C:\temp\crt_client.py"
    assert captured["env"]["PYTHONIOENCODING"] == "utf-8"


def test_should_delegate_to_openclaw_for_webchat_url_action() -> None:
    allowed, reason = openclaw_bridge.should_delegate_to_openclaw(
        message="Read https://www.moltbook.com/skill.md and follow the instructions to join Moltbook",
        channel="webchat",
        meta_scope=None,
        mode=None,
        runtime_config={
            "openclaw_handoff": {
                "enabled": True,
                "agent_id": "main",
                "session_prefix": "crt",
                "timeout_seconds": 30,
                "allowed_channels": ["telegram", "webchat"],
                "denied_channels": [],
                "inject_crt_context": True,
                "include_api_guide": True,
                "max_fact_items": 8,
                "auto_keywords": ["moltbook"],
            }
        },
    )

    assert allowed is True
    assert reason == "url_action"


def test_resolve_openclaw_executable_prefers_env_override(monkeypatch) -> None:
    monkeypatch.setenv("OPENCLAW_BIN", r"C:\custom\openclaw.cmd")
    assert openclaw_bridge.resolve_openclaw_executable() == r"C:\custom\openclaw.cmd"


def test_run_openclaw_agent_parses_payloads_shape(monkeypatch) -> None:
    def _fake_run(cmd, capture_output, text, encoding, errors, timeout, cwd, env):
        payload = {
            "payloads": [
                {"text": "First answer block."},
                {"text": "Second answer block."},
            ]
        }
        return subprocess.CompletedProcess(cmd, 0, stdout=json.dumps(payload), stderr="")

    monkeypatch.setattr(openclaw_bridge.subprocess, "run", _fake_run)
    monkeypatch.setenv("OPENCLAW_BIN", r"C:\Users\block\AppData\Roaming\npm\openclaw.cmd")

    result = openclaw_bridge.run_openclaw_agent(
        user_command="research github issues",
        thread_id="tg_1000",
        crt_api_url="http://127.0.0.1:8123",
        runtime_config={"openclaw_handoff": {"timeout_seconds": 30}},
        workdir=Path("d:/AI_round2"),
    )

    assert result["ok"] is True
    assert result["answer"] == "First answer block.\n\nSecond answer block."


def test_run_openclaw_agent_parses_last_json_line(monkeypatch) -> None:
    def _fake_run(cmd, capture_output, text, encoding, errors, timeout, cwd, env):
        stdout = "\n".join(
            [
                "OpenClaw status: booting",
                '{"payloads":[{"text":"Recovered answer."}]}',
            ]
        )
        return subprocess.CompletedProcess(cmd, 0, stdout=stdout, stderr="")

    monkeypatch.setattr(openclaw_bridge.subprocess, "run", _fake_run)
    monkeypatch.setenv("OPENCLAW_BIN", r"C:\Users\block\AppData\Roaming\npm\openclaw.cmd")

    result = openclaw_bridge.run_openclaw_agent(
        user_command="check moltbook",
        thread_id="tg_1001",
        crt_api_url="http://127.0.0.1:8123",
        runtime_config={"openclaw_handoff": {"timeout_seconds": 30}},
        workdir=Path("d:/AI_round2"),
    )

    assert result["ok"] is True
    assert result["answer"] == "Recovered answer."
