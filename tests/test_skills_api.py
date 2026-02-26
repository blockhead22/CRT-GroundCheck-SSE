from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

from personal_agent.skill_registry import SkillRegistry
from routes.skills import router


def _write_skill(dir_path: Path, name: str, version: str, description: str) -> None:
    dir_path.mkdir(parents=True, exist_ok=True)
    (dir_path / "SKILL.md").write_text(
        (
            "---\n"
            f"name: {name}\n"
            f"version: \"{version}\"\n"
            f"description: {description}\n"
            "---\n\n"
            "# Skill\n\n"
            "Body.\n"
        ),
        encoding="utf-8",
    )


def test_skills_api_lifecycle(tmp_path: Path):
    source_root = tmp_path / "sources"
    _write_skill(source_root / "demo-skill", "demo-skill", "1.0.0", "Demo skill")

    reg = SkillRegistry(
        db_path=str(tmp_path / "skills.db"),
        managed_dir=str(tmp_path / "managed"),
        source_roots=[str(source_root)],
    )

    app = FastAPI()
    app.include_router(router)
    app.state.skill_registry = reg
    client = TestClient(app)

    discover_resp = client.post("/api/skills/discover", json={"roots": [str(source_root)]})
    assert discover_resp.status_code == 200
    discovered = discover_resp.json()
    assert discovered["count"] == 1

    install_resp = client.post("/api/skills/install", json={"name": "demo-skill"})
    assert install_resp.status_code == 200
    install_data = install_resp.json()
    assert install_data["skill"]["installed"] is True

    trust_resp = client.post("/api/skills/demo-skill/trust", json={"trust_level": "trusted"})
    assert trust_resp.status_code == 200
    assert trust_resp.json()["skill"]["trust_level"] == "trusted"

    disable_resp = client.post("/api/skills/demo-skill/disable")
    assert disable_resp.status_code == 200
    assert disable_resp.json()["skill"]["enabled"] is False

    list_resp = client.get("/api/skills")
    assert list_resp.status_code == 200
    listing = list_resp.json()
    assert listing["total"] >= 1

    uninstall_resp = client.delete("/api/skills/demo-skill")
    assert uninstall_resp.status_code == 200
    assert uninstall_resp.json()["skill"]["installed"] is False
