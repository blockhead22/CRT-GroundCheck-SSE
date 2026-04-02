"""Skill lifecycle registry.

Provides OpenClaw-style skill lifecycle management:
- discovery from local roots
- install/update into a managed directory
- enable/disable state
- trust flags
- persistent metadata in SQLite
"""

from __future__ import annotations

import json
import logging
import shutil
import sqlite3
import time
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

from personal_agent.runtime_paths import resolve_managed_skills_dir, resolve_skills_registry_db_path

logger = logging.getLogger(__name__)


_ALLOWED_TRUST_LEVELS = {"untrusted", "trusted", "verified", "blocked"}


def _norm_token(value: Any) -> str:
    return str(value or "").strip()


class SkillRegistry:
    """Persistent lifecycle registry for local skills."""

    def __init__(
        self,
        db_path: str = str(resolve_skills_registry_db_path()),
        managed_dir: str = str(resolve_managed_skills_dir()),
        source_roots: Optional[Iterable[str]] = None,
    ):
        self.db_path = Path(db_path)
        self.managed_dir = Path(managed_dir)
        self.source_roots = [Path(p) for p in (source_roots or [])]
        if not self.source_roots:
            self.source_roots = [Path(".agents/skills"), Path(".github/skills")]

        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.managed_dir.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path), timeout=30.0, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
        conn.execute("PRAGMA busy_timeout=5000")
        return conn

    def _init_db(self) -> None:
        conn = self._connect()
        cur = conn.cursor()
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS skills (
                name TEXT PRIMARY KEY,
                description TEXT,
                source_path TEXT,
                install_path TEXT,
                version TEXT,
                trust_level TEXT NOT NULL DEFAULT 'untrusted',
                enabled INTEGER NOT NULL DEFAULT 0,
                installed INTEGER NOT NULL DEFAULT 0,
                metadata_json TEXT,
                discovered_at REAL,
                last_installed_at REAL,
                updated_at REAL NOT NULL
            )
            """
        )
        cur.execute("CREATE INDEX IF NOT EXISTS idx_skills_enabled ON skills(enabled)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_skills_installed ON skills(installed)")
        conn.commit()
        conn.close()

    def _normalize_name(self, name: str) -> str:
        raw = _norm_token(name)
        if not raw:
            raise ValueError("skill name is required")
        cleaned = raw.lower()
        allowed = set("abcdefghijklmnopqrstuvwxyz0123456789._-")
        if any(ch not in allowed for ch in cleaned):
            raise ValueError("skill name must use [a-z0-9._-] characters")
        return cleaned

    def _parse_skill_manifest(self, skill_dir: Path) -> Dict[str, Any]:
        skill_md = skill_dir / "SKILL.md"
        if not skill_md.exists():
            raise FileNotFoundError(f"SKILL.md not found in {skill_dir}")

        text = skill_md.read_text(encoding="utf-8", errors="ignore")
        meta: Dict[str, Any] = {}
        description = ""

        if text.startswith("---"):
            lines = text.splitlines()
            end_idx = None
            for i in range(1, len(lines)):
                if lines[i].strip() == "---":
                    end_idx = i
                    break
            if end_idx:
                for line in lines[1:end_idx]:
                    if ":" not in line:
                        continue
                    key, value = line.split(":", 1)
                    meta[key.strip().lower()] = value.strip().strip('"').strip("'")

                body = "\n".join(lines[end_idx + 1 :]).strip()
            else:
                body = text
        else:
            body = text

        for line in body.splitlines():
            stripped = line.strip()
            if stripped and not stripped.startswith("#"):
                description = stripped
                break

        name = self._normalize_name(meta.get("name") or skill_dir.name)
        version = _norm_token(meta.get("version")) or "0.0.0"
        desc = _norm_token(meta.get("description")) or description
        author = _norm_token(meta.get("author"))

        out = {
            "name": name,
            "description": desc,
            "version": version,
            "source_path": str(skill_dir.resolve()),
        }
        if author:
            out["metadata"] = {"author": author}
        else:
            out["metadata"] = {}
        return out

    def _row_to_dict(self, row: sqlite3.Row) -> Dict[str, Any]:
        metadata = {}
        raw_meta = row["metadata_json"]
        if raw_meta:
            try:
                parsed = json.loads(raw_meta)
                if isinstance(parsed, dict):
                    metadata = parsed
            except Exception:
                metadata = {}
        return {
            "name": str(row["name"] or ""),
            "description": str(row["description"] or ""),
            "source_path": row["source_path"],
            "install_path": row["install_path"],
            "version": row["version"],
            "trust_level": str(row["trust_level"] or "untrusted"),
            "enabled": bool(row["enabled"]),
            "installed": bool(row["installed"]),
            "metadata": metadata,
            "discovered_at": row["discovered_at"],
            "last_installed_at": row["last_installed_at"],
            "updated_at": row["updated_at"],
        }

    def list_skills(self) -> List[Dict[str, Any]]:
        conn = self._connect()
        rows = conn.execute("SELECT * FROM skills ORDER BY name ASC").fetchall()
        conn.close()
        return [self._row_to_dict(row) for row in rows]

    def get_skill(self, name: str) -> Optional[Dict[str, Any]]:
        skill_name = self._normalize_name(name)
        conn = self._connect()
        row = conn.execute("SELECT * FROM skills WHERE name = ?", (skill_name,)).fetchone()
        conn.close()
        if not row:
            return None
        return self._row_to_dict(row)

    def discover_skills(self, roots: Optional[Iterable[str]] = None) -> List[Dict[str, Any]]:
        scan_roots = [Path(p) for p in roots] if roots else list(self.source_roots)
        now = time.time()
        discovered: List[Dict[str, Any]] = []

        conn = self._connect()
        cur = conn.cursor()
        try:
            for root in scan_roots:
                if not root.exists() or not root.is_dir():
                    continue
                for skill_md in root.rglob("SKILL.md"):
                    skill_dir = skill_md.parent
                    try:
                        item = self._parse_skill_manifest(skill_dir)
                    except Exception as e:
                        logger.debug(f"[SKILLS] Failed to parse {skill_dir}: {e}")
                        continue

                    discovered.append(item)
                    cur.execute(
                        """
                        INSERT INTO skills
                        (name, description, source_path, version, metadata_json, discovered_at, updated_at)
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                        ON CONFLICT(name) DO UPDATE SET
                            description = excluded.description,
                            source_path = excluded.source_path,
                            version = excluded.version,
                            metadata_json = excluded.metadata_json,
                            discovered_at = excluded.discovered_at,
                            updated_at = excluded.updated_at
                        """,
                        (
                            item["name"],
                            item.get("description") or "",
                            item["source_path"],
                            item.get("version"),
                            json.dumps(item.get("metadata") or {}),
                            now,
                            now,
                        ),
                    )
            conn.commit()
        finally:
            conn.close()

        out: List[Dict[str, Any]] = []
        for item in discovered:
            saved = self.get_skill(item["name"])
            if saved:
                out.append(saved)
        return out

    def install_skill(
        self,
        *,
        name: Optional[str] = None,
        source_path: Optional[str] = None,
        enabled: bool = True,
        trust_level: Optional[str] = None,
    ) -> Dict[str, Any]:
        if not name and not source_path:
            raise ValueError("either name or source_path is required")

        selected_source: Optional[Path] = None
        selected_name: Optional[str] = None
        existing: Optional[Dict[str, Any]] = None

        if name:
            selected_name = self._normalize_name(name)
            existing = self.get_skill(selected_name)
            if source_path:
                selected_source = Path(source_path)
            elif existing and existing.get("source_path"):
                selected_source = Path(str(existing["source_path"]))
        elif source_path:
            selected_source = Path(source_path)

        if not selected_source or not selected_source.exists():
            raise FileNotFoundError("skill source path not found")

        manifest = self._parse_skill_manifest(selected_source)
        skill_name = selected_name or manifest["name"]

        if trust_level is None and existing:
            trust_level = str(existing.get("trust_level") or "untrusted")
        trust = self._validate_trust_level(trust_level or "untrusted")

        install_path = self.managed_dir / skill_name
        if install_path.exists():
            shutil.rmtree(install_path)
        shutil.copytree(selected_source, install_path)

        now = time.time()
        conn = self._connect()
        conn.execute(
            """
            INSERT INTO skills
            (name, description, source_path, install_path, version, trust_level, enabled, installed, metadata_json, discovered_at, last_installed_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, 1, ?, ?, ?, ?)
            ON CONFLICT(name) DO UPDATE SET
                description = excluded.description,
                source_path = excluded.source_path,
                install_path = excluded.install_path,
                version = excluded.version,
                trust_level = excluded.trust_level,
                enabled = excluded.enabled,
                installed = 1,
                metadata_json = excluded.metadata_json,
                discovered_at = COALESCE(skills.discovered_at, excluded.discovered_at),
                last_installed_at = excluded.last_installed_at,
                updated_at = excluded.updated_at
            """,
            (
                skill_name,
                manifest.get("description") or "",
                str(selected_source.resolve()),
                str(install_path.resolve()),
                manifest.get("version"),
                trust,
                1 if enabled else 0,
                json.dumps(manifest.get("metadata") or {}),
                now,
                now,
                now,
            ),
        )
        conn.commit()
        conn.close()

        saved = self.get_skill(skill_name)
        if not saved:
            raise RuntimeError("failed to persist installed skill")
        return saved

    def update_skill(self, name: str) -> Dict[str, Any]:
        skill = self.get_skill(name)
        if not skill:
            raise KeyError("skill not found")
        source_path = str(skill.get("source_path") or "").strip()
        if not source_path:
            raise ValueError("skill has no source_path to update from")
        return self.install_skill(
            name=str(skill["name"]),
            source_path=source_path,
            enabled=bool(skill.get("enabled", True)),
            trust_level=str(skill.get("trust_level") or "untrusted"),
        )

    def set_enabled(self, name: str, enabled: bool) -> Dict[str, Any]:
        skill_name = self._normalize_name(name)
        now = time.time()
        conn = self._connect()
        cur = conn.cursor()
        cur.execute(
            "UPDATE skills SET enabled = ?, updated_at = ? WHERE name = ?",
            (1 if enabled else 0, now, skill_name),
        )
        conn.commit()
        changed = int(cur.rowcount or 0)
        conn.close()
        if changed == 0:
            raise KeyError("skill not found")
        saved = self.get_skill(skill_name)
        if not saved:
            raise RuntimeError("failed to load updated skill")
        return saved

    def set_trust_level(self, name: str, trust_level: str) -> Dict[str, Any]:
        skill_name = self._normalize_name(name)
        trust = self._validate_trust_level(trust_level)
        now = time.time()
        conn = self._connect()
        cur = conn.cursor()
        cur.execute(
            "UPDATE skills SET trust_level = ?, updated_at = ? WHERE name = ?",
            (trust, now, skill_name),
        )
        conn.commit()
        changed = int(cur.rowcount or 0)
        conn.close()
        if changed == 0:
            raise KeyError("skill not found")
        saved = self.get_skill(skill_name)
        if not saved:
            raise RuntimeError("failed to load updated skill")
        return saved

    def uninstall_skill(self, name: str, *, remove_files: bool = True) -> Dict[str, Any]:
        skill_name = self._normalize_name(name)
        skill = self.get_skill(skill_name)
        if not skill:
            raise KeyError("skill not found")

        install_path = _norm_token(skill.get("install_path"))
        if remove_files and install_path:
            target = Path(install_path)
            if target.exists() and target.is_dir():
                shutil.rmtree(target)

        now = time.time()
        conn = self._connect()
        conn.execute(
            """
            UPDATE skills
            SET install_path = NULL,
                installed = 0,
                enabled = 0,
                updated_at = ?
            WHERE name = ?
            """,
            (now, skill_name),
        )
        conn.commit()
        conn.close()

        saved = self.get_skill(skill_name)
        if not saved:
            raise RuntimeError("failed to load uninstalled skill")
        return saved

    def _validate_trust_level(self, trust_level: str) -> str:
        trust = _norm_token(trust_level).lower()
        if trust not in _ALLOWED_TRUST_LEVELS:
            allowed = ", ".join(sorted(_ALLOWED_TRUST_LEVELS))
            raise ValueError(f"trust_level must be one of: {allowed}")
        return trust
