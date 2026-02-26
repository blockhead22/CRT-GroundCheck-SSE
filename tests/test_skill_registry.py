from __future__ import annotations

from pathlib import Path

import pytest

from personal_agent.skill_registry import SkillRegistry


def _write_skill(dir_path: Path, name: str, version: str, description: str) -> None:
    dir_path.mkdir(parents=True, exist_ok=True)
    (dir_path / "SKILL.md").write_text(
        (
            "---\n"
            f"name: {name}\n"
            f"version: \"{version}\"\n"
            f"description: {description}\n"
            "author: test-suite\n"
            "---\n\n"
            "# Skill\n\n"
            "Test skill.\n"
        ),
        encoding="utf-8",
    )
    (dir_path / "notes.txt").write_text("ok", encoding="utf-8")


def test_skill_registry_lifecycle(tmp_path: Path):
    source_root = tmp_path / "sources"
    skill_dir = source_root / "demo-skill"
    _write_skill(skill_dir, name="demo-skill", version="1.0.0", description="Demo skill")

    reg = SkillRegistry(
        db_path=str(tmp_path / "skills.db"),
        managed_dir=str(tmp_path / "managed"),
        source_roots=[str(source_root)],
    )

    discovered = reg.discover_skills()
    assert len(discovered) == 1
    assert discovered[0]["name"] == "demo-skill"

    installed = reg.install_skill(name="demo-skill", enabled=True, trust_level="trusted")
    assert installed["installed"] is True
    assert installed["enabled"] is True
    assert installed["trust_level"] == "trusted"
    assert Path(str(installed["install_path"])).exists()

    disabled = reg.set_enabled("demo-skill", False)
    assert disabled["enabled"] is False

    trusted = reg.set_trust_level("demo-skill", "verified")
    assert trusted["trust_level"] == "verified"

    _write_skill(skill_dir, name="demo-skill", version="1.1.0", description="Demo skill v2")
    updated = reg.update_skill("demo-skill")
    assert updated["version"] == "1.1.0"
    assert updated["installed"] is True

    removed = reg.uninstall_skill("demo-skill", remove_files=True)
    assert removed["installed"] is False
    assert removed["enabled"] is False
    assert not Path(str(installed["install_path"])).exists()


def test_skill_registry_rejects_invalid_trust_level(tmp_path: Path):
    source_root = tmp_path / "sources"
    skill_dir = source_root / "demo-skill"
    _write_skill(skill_dir, name="demo-skill", version="1.0.0", description="Demo skill")

    reg = SkillRegistry(
        db_path=str(tmp_path / "skills.db"),
        managed_dir=str(tmp_path / "managed"),
        source_roots=[str(source_root)],
    )
    reg.discover_skills()
    reg.install_skill(name="demo-skill")

    with pytest.raises(ValueError):
        reg.set_trust_level("demo-skill", "supertrusted")
