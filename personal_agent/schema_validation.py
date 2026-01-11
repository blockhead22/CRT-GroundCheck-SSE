from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, Iterable, List

from jsonschema import Draft7Validator


def _repo_root() -> Path:
    # personal_agent/ -> repo root
    return Path(__file__).resolve().parents[1]


@lru_cache(maxsize=32)
def load_schema(schema_filename: str) -> Dict[str, Any]:
    schema_path = _repo_root() / schema_filename
    if not schema_path.exists() or not schema_path.is_file():
        raise FileNotFoundError(f"Schema not found: {schema_path}")
    return json.loads(schema_path.read_text(encoding="utf-8"))


def validate_instance(instance: Any, schema: Dict[str, Any]) -> List[str]:
    """Return a list of human-friendly validation error strings."""

    validator = Draft7Validator(schema)
    errors = sorted(validator.iter_errors(instance), key=lambda e: list(e.absolute_path))

    out: List[str] = []
    for err in errors:
        path = "/".join(str(p) for p in err.absolute_path)
        loc = f" at '{path}'" if path else ""
        out.append(f"{err.message}{loc}")
    return out


def format_errors(errors: Iterable[str], *, max_errors: int = 20) -> str:
    lines = list(errors)
    if len(lines) > max_errors:
        lines = lines[:max_errors] + [f"... ({len(lines) - max_errors} more)"]
    return "\n".join(f"- {line}" for line in lines)
