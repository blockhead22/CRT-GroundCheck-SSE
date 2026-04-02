"""Runtime data path resolution for mutable SQLite/state artifacts.

This module exists to pull live runtime state out of the source tree over time.
It provides:

- an explicit runtime data root (configurable via env)
- stable path helpers for hot-path databases
- conservative legacy fallback while the migration is still in progress

The migration policy is intentionally safe:
- prefer the external/runtime path when it already exists
- if only a legacy repo-local DB exists, keep using it
- only move legacy DBs automatically when `CRT_RUNTIME_AUTO_MIGRATE=true`

That lets us tighten the boundary without surprising the running system by
silently moving large or locked databases.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Iterable, Optional

logger = logging.getLogger(__name__)

_REPO_ROOT = Path(__file__).resolve().parents[1]
_LEGACY_RUNTIME_DIR = _REPO_ROOT / "personal_agent"


def _default_runtime_data_root() -> Path:
    override = os.getenv("CRT_RUNTIME_DATA_ROOT", "").strip()
    if override:
        return Path(override).expanduser().resolve()

    if os.name == "nt":
        base = os.getenv("LOCALAPPDATA", "").strip()
        if base:
            return (Path(base) / "AetherCRT" / "runtime").resolve()
        return (Path.home() / "AppData" / "Local" / "AetherCRT" / "runtime").resolve()

    xdg_state = os.getenv("XDG_STATE_HOME", "").strip()
    if xdg_state:
        return (Path(xdg_state) / "aethercrt" / "runtime").resolve()
    return (Path.home() / ".local" / "state" / "aethercrt" / "runtime").resolve()


def get_runtime_data_root(*, create: bool = True) -> Path:
    root = _default_runtime_data_root()
    if create:
        root.mkdir(parents=True, exist_ok=True)
    return root


def resolve_runtime_dir(
    relative_path: str | Path,
    *,
    runtime_root: Optional[Path] = None,
) -> Path:
    """Resolve a mutable runtime directory under the runtime root."""
    rel = Path(relative_path)
    if rel.is_absolute():
        rel.mkdir(parents=True, exist_ok=True)
        return rel

    root = Path(runtime_root) if runtime_root is not None else get_runtime_data_root(create=True)
    target = (root / rel).resolve()
    target.mkdir(parents=True, exist_ok=True)
    return target


def _legacy_path_for(path: Path, *, legacy_path: Optional[Path] = None) -> Path:
    if legacy_path is not None:
        return Path(legacy_path)
    return _LEGACY_RUNTIME_DIR / path


def _sqlite_sidecars(path: Path) -> Iterable[Path]:
    yield Path(str(path) + "-wal")
    yield Path(str(path) + "-shm")


def _move_sqlite_bundle(src: Path, dst: Path) -> None:
    dst.parent.mkdir(parents=True, exist_ok=True)
    src.replace(dst)
    for src_sidecar in _sqlite_sidecars(src):
        if src_sidecar.exists():
            dst_sidecar = Path(str(dst) + src_sidecar.name[len(src.name):])
            try:
                src_sidecar.replace(dst_sidecar)
            except Exception:
                logger.debug("[RUNTIME_PATHS] Could not move sidecar %s -> %s", src_sidecar, dst_sidecar)


def resolve_runtime_path(
    relative_path: str | Path,
    *,
    runtime_root: Optional[Path] = None,
    legacy_path: Optional[Path] = None,
    migrate_legacy: bool = True,
) -> Path:
    """Resolve a mutable runtime artifact path.

    Absolute paths are returned unchanged.

    For relative names, the preferred target is under the runtime data root.
    If a legacy repo-local file exists and the new target does not, the legacy
    path is kept unless opt-in migration is explicitly enabled via env or the
    `migrate_legacy` flag is disabled by the caller.
    """

    rel = Path(relative_path)
    if rel.is_absolute():
        return rel

    root = Path(runtime_root) if runtime_root is not None else get_runtime_data_root(create=True)
    target = (root / rel).resolve()

    if target.exists():
        return target

    legacy = _legacy_path_for(rel, legacy_path=legacy_path)
    if legacy.exists():
        auto_migrate = str(os.getenv("CRT_RUNTIME_AUTO_MIGRATE", "false")).strip().lower() in {
            "1", "true", "yes", "on",
        }
        if migrate_legacy and auto_migrate:
            try:
                _move_sqlite_bundle(legacy, target)
                logger.info("[RUNTIME_PATHS] Migrated %s -> %s", legacy, target)
                return target
            except Exception as e:
                logger.warning("[RUNTIME_PATHS] Using legacy path %s (migration to %s failed: %s)", legacy, target, e)
                return legacy
        return legacy

    target.parent.mkdir(parents=True, exist_ok=True)
    return target


def runtime_candidates(relative_path: str | Path) -> list[Path]:
    """Return preferred runtime path followed by legacy path when distinct."""
    rel = Path(relative_path)
    if rel.is_absolute():
        return [rel]
    target = (get_runtime_data_root(create=True) / rel).resolve()
    legacy = _LEGACY_RUNTIME_DIR / rel
    candidates = [target]
    if legacy != target:
        candidates.append(legacy)
    return candidates


def resolve_memory_db_path(thread_id: str, *, shared: bool) -> Path:
    if shared:
        return resolve_runtime_path("crt_memory_shared.db")
    return resolve_runtime_path(f"crt_memory_{thread_id}.db")


def resolve_ledger_db_path(thread_id: str, *, shared: bool) -> Path:
    if shared:
        return resolve_runtime_path("crt_ledger_shared.db")
    return resolve_runtime_path(f"crt_ledger_{thread_id}.db")


def resolve_facts_db_path() -> Path:
    return resolve_runtime_path("crt_facts.db")


def resolve_active_learning_db_path() -> Path:
    return resolve_runtime_path("active_learning.db")


def resolve_agent_runs_db_path() -> Path:
    return resolve_runtime_path("agent_runs.db")


def resolve_action_receipts_db_path() -> Path:
    return resolve_runtime_path("action_receipts.db")


def resolve_jobs_db_path() -> Path:
    return resolve_runtime_path("crt_jobs.db")


def resolve_collapse_trails_db_path() -> Path:
    return resolve_runtime_path("crt_collapse_trails.db")


def resolve_thread_sessions_db_path() -> Path:
    return resolve_runtime_path("crt_thread_sessions.db")


def resolve_profile_db_path() -> Path:
    return resolve_runtime_path("crt_user_profile.db")


def resolve_episodic_db_path() -> Path:
    return resolve_runtime_path("crt_episodic.db")


def resolve_scheduled_tasks_db_path() -> Path:
    return resolve_runtime_path("scheduled_tasks.db")


def resolve_jobs_artifacts_dir() -> Path:
    return resolve_runtime_dir("artifacts")


def resolve_skills_registry_db_path() -> Path:
    return resolve_runtime_path("skills_registry.db")


def resolve_managed_skills_dir() -> Path:
    return resolve_runtime_dir("managed_skills")


def iter_existing_memory_dbs(*, include_shared: bool = True) -> list[Path]:
    """Return existing memory DBs across runtime root and legacy dir."""
    seen: set[Path] = set()
    out: list[Path] = []
    for root in (get_runtime_data_root(create=True), _LEGACY_RUNTIME_DIR):
        for path in sorted(root.glob("crt_memory_*.db")):
            if path not in seen:
                seen.add(path)
                out.append(path)
        if include_shared:
            shared = root / "crt_memory_shared.db"
            if shared.exists() and shared not in seen:
                seen.add(shared)
                out.append(shared)
    return out
