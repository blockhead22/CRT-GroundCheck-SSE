from __future__ import annotations

from pathlib import Path

from personal_agent.runtime_paths import (
    get_runtime_data_root,
    resolve_runtime_path,
)


def test_get_runtime_data_root_honors_env_override(monkeypatch, tmp_path: Path) -> None:
    root = tmp_path / "runtime-root"
    monkeypatch.setenv("CRT_RUNTIME_DATA_ROOT", str(root))

    resolved = get_runtime_data_root(create=False)

    assert resolved == root.resolve()
    assert not root.exists()


def test_resolve_runtime_path_returns_absolute_path_unchanged(tmp_path: Path) -> None:
    absolute = (tmp_path / "already-absolute.db").resolve()

    resolved = resolve_runtime_path(absolute)

    assert resolved == absolute


def test_resolve_runtime_path_prefers_existing_runtime_target(tmp_path: Path) -> None:
    runtime_root = tmp_path / "runtime"
    target = runtime_root / "crt_memory_shared.db"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("runtime")
    legacy = tmp_path / "legacy.db"
    legacy.write_text("legacy")

    resolved = resolve_runtime_path(
        "crt_memory_shared.db",
        runtime_root=runtime_root,
        legacy_path=legacy,
    )

    assert resolved == target.resolve()
    assert target.read_text() == "runtime"
    assert legacy.read_text() == "legacy"


def test_resolve_runtime_path_uses_legacy_when_target_missing_and_auto_migrate_disabled(
    monkeypatch,
    tmp_path: Path,
) -> None:
    monkeypatch.delenv("CRT_RUNTIME_AUTO_MIGRATE", raising=False)
    runtime_root = tmp_path / "runtime"
    legacy = tmp_path / "legacy.db"
    legacy.write_text("legacy")

    resolved = resolve_runtime_path(
        "crt_memory_shared.db",
        runtime_root=runtime_root,
        legacy_path=legacy,
    )

    assert resolved == legacy
    assert legacy.exists()
    assert not (runtime_root / "crt_memory_shared.db").exists()


def test_resolve_runtime_path_auto_migrates_only_when_env_enabled(
    monkeypatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("CRT_RUNTIME_AUTO_MIGRATE", "true")
    runtime_root = tmp_path / "runtime"
    legacy = tmp_path / "legacy.db"
    legacy.write_text("legacy")
    Path(str(legacy) + "-wal").write_text("wal")
    Path(str(legacy) + "-shm").write_text("shm")

    resolved = resolve_runtime_path(
        "crt_memory_shared.db",
        runtime_root=runtime_root,
        legacy_path=legacy,
    )

    target = (runtime_root / "crt_memory_shared.db").resolve()
    assert resolved == target
    assert target.read_text() == "legacy"
    assert Path(str(target) + "-wal").read_text() == "wal"
    assert Path(str(target) + "-shm").read_text() == "shm"
    assert not legacy.exists()
    assert not Path(str(legacy) + "-wal").exists()
    assert not Path(str(legacy) + "-shm").exists()


def test_resolve_runtime_path_creates_runtime_target_for_fresh_path(tmp_path: Path) -> None:
    runtime_root = tmp_path / "runtime"

    resolved = resolve_runtime_path(
        "nested/crt_memory_shared.db",
        runtime_root=runtime_root,
    )

    assert resolved == (runtime_root / "nested" / "crt_memory_shared.db").resolve()
    assert resolved.parent.exists()
