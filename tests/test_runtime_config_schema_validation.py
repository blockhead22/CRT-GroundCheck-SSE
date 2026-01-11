from __future__ import annotations

import json
from pathlib import Path

import pytest

from personal_agent import runtime_config


def test_default_runtime_config_validates_in_strict_mode() -> None:
    # No file needed; should validate defaults.
    cfg = runtime_config.load_runtime_config(None, strict=True)
    assert isinstance(cfg, dict)
    assert cfg.get("assistant_profile", {}).get("enabled") is True


def test_invalid_runtime_config_raises_in_strict_mode(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    cfg_path = tmp_path / "cfg.json"
    cfg_path.write_text(json.dumps({"not_a_real_key": True}), encoding="utf-8")

    monkeypatch.setenv("CRT_RUNTIME_CONFIG_PATH", str(cfg_path))
    runtime_config.clear_runtime_config_cache()

    with pytest.raises(ValueError):
        runtime_config.get_runtime_config(strict=True)
