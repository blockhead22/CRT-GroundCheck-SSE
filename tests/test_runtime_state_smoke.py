from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import crt_api
import personal_agent.db_utils as db_utils
import personal_agent.runtime_paths as runtime_paths


def _runtime_config() -> dict:
    return {
        "background_jobs": {"enabled": False, "idle_scheduler_enabled": False},
        "training_loop": {"enabled": False},
        "learned_suggestions": {"enabled": False},
        "dnnt_retraining": {"enabled": False},
    }


def _make_client(monkeypatch: pytest.MonkeyPatch, runtime_root: Path, legacy_root: Path) -> TestClient:
    monkeypatch.setenv("CRT_RUNTIME_DATA_ROOT", str(runtime_root))
    monkeypatch.setenv("CRT_ENABLE_LLM", "false")
    monkeypatch.setenv("CRT_REFLECTION_LOOP_ENABLED", "false")
    monkeypatch.setenv("CRT_PERSONALITY_LOOP_ENABLED", "false")
    monkeypatch.setenv("CRT_JOURNAL_SELF_REPLY_LOOP_ENABLED", "false")
    monkeypatch.setenv("CRT_HEARTBEAT_LOOP_ENABLED", "false")
    monkeypatch.setattr(crt_api, "get_runtime_config", _runtime_config)
    monkeypatch.setattr(runtime_paths, "_LEGACY_RUNTIME_DIR", legacy_root)
    db_utils._thread_session_db = None
    app = crt_api.create_app()
    return TestClient(app)


def test_runtime_status_reports_externalized_write_locations(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    runtime_root = tmp_path / "runtime"
    legacy_root = tmp_path / "legacy"
    legacy_root.mkdir(parents=True, exist_ok=True)

    with _make_client(monkeypatch, runtime_root, legacy_root) as client:
        status = client.get("/api/runtime/status")
        assert status.status_code == 200
        body = status.json()

        assert body["runtime_data_root"] == str(runtime_root.resolve())
        assert body["auto_migrate_enabled"] is False

        profile = client.get("/api/profile", params={"thread_id": "default"})
        assert profile.status_code == 200

        body = client.get("/api/runtime/status").json()
        paths = body["paths"]

        expected_paths = [
            "default_memory_db",
            "default_ledger_db",
            "thread_sessions_db",
            "facts_db",
            "profile_db",
            "agent_runs_db",
            "action_receipts_db",
            "scheduled_tasks_db",
            "jobs_db",
            "skills_registry_db",
        ]
        for key in expected_paths:
            path = Path(paths[key])
            assert runtime_root.resolve() in path.resolve().parents

        created_files = [
            "default_memory_db",
            "default_ledger_db",
            "thread_sessions_db",
            "scheduled_tasks_db",
            "jobs_db",
            "skills_registry_db",
        ]
        for key in created_files:
            assert Path(paths[key]).exists(), key

        expected_dirs = ["jobs_artifacts_dir", "managed_skills_dir"]
        for key in expected_dirs:
            path = Path(paths[key])
            assert path.exists(), key
            assert path.is_dir(), key
            assert runtime_root.resolve() in path.resolve().parents or path.resolve() == runtime_root.resolve()


def test_runtime_status_preserves_legacy_thread_sessions_fallback(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    runtime_root = tmp_path / "runtime"
    legacy_root = tmp_path / "legacy"
    legacy_root.mkdir(parents=True, exist_ok=True)
    legacy_thread_sessions = legacy_root / "crt_thread_sessions.db"
    legacy_thread_sessions.touch()

    with _make_client(monkeypatch, runtime_root, legacy_root) as client:
        status = client.get("/api/runtime/status")
        assert status.status_code == 200
        body = status.json()

        assert body["paths"]["thread_sessions_db"] == str(legacy_thread_sessions.resolve())
        assert legacy_thread_sessions.exists()
        assert not (runtime_root / "crt_thread_sessions.db").exists()
