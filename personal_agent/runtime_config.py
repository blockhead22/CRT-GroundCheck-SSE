from __future__ import annotations

import json
import os
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, Optional


_DEFAULT_CONFIG: Dict[str, Any] = {
    "learned_suggestions": {
        "enabled": True,
        "emit_metadata": True,
        "print_in_stress_test": False,
        "write_jsonl": True,
        "jsonl_include_full_answer": False,
    }
}


def _deep_merge(base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
    out: Dict[str, Any] = dict(base)
    for key, value in (override or {}).items():
        if isinstance(value, dict) and isinstance(out.get(key), dict):
            out[key] = _deep_merge(out[key], value)
        else:
            out[key] = value
    return out


def load_runtime_config(config_path: Optional[str] = None) -> Dict[str, Any]:
    """Load CRT runtime config.

    Resolution order:
    1) explicit config_path
    2) env var CRT_RUNTIME_CONFIG_PATH
    3) repo-root file ./crt_runtime_config.json if it exists

    If nothing exists / parse fails, returns defaults.
    """

    candidate = config_path or os.environ.get("CRT_RUNTIME_CONFIG_PATH")

    if candidate:
        path = Path(candidate)
        if path.exists() and path.is_file():
            try:
                return _deep_merge(_DEFAULT_CONFIG, json.loads(path.read_text(encoding="utf-8")))
            except Exception:
                return dict(_DEFAULT_CONFIG)
        return dict(_DEFAULT_CONFIG)

    # Prefer resolving relative to the repo (personal_agent/..), then CWD.
    module_default = Path(__file__).resolve().parents[1] / "crt_runtime_config.json"
    for candidate_path in (module_default, Path.cwd() / "crt_runtime_config.json"):
        if candidate_path.exists() and candidate_path.is_file():
            try:
                return _deep_merge(_DEFAULT_CONFIG, json.loads(candidate_path.read_text(encoding="utf-8")))
            except Exception:
                return dict(_DEFAULT_CONFIG)

    return dict(_DEFAULT_CONFIG)


@lru_cache(maxsize=1)
def get_runtime_config() -> Dict[str, Any]:
    return load_runtime_config(None)
