from __future__ import annotations

import json
import os
import tempfile
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
from typing import Any, Dict, Optional

from personal_agent.schema_validation import format_errors, load_schema, validate_instance


def now_iso_utc() -> str:
    # RFC3339-ish; jsonschema "date-time" accepts offsets.
    return datetime.now(timezone.utc).isoformat()


def atomic_write_text(path: Path, text: str, *, encoding: str = "utf-8") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd = None
    tmp_path = None
    try:
        fd, tmp_path = tempfile.mkstemp(prefix=path.name + ".tmp_", dir=str(path.parent))
        with os.fdopen(fd, "w", encoding=encoding, newline="\n") as f:
            f.write(text)
        fd = None
        Path(tmp_path).replace(path)
    finally:
        if fd is not None:
            try:
                os.close(fd)
            except Exception:
                pass
        if tmp_path is not None:
            try:
                p = Path(tmp_path)
                if p.exists():
                    p.unlink()
            except Exception:
                pass


def atomic_write_json(path: Path, payload: Any, *, indent: int = 2) -> None:
    atomic_write_text(path, json.dumps(payload, indent=indent, sort_keys=True) + "\n")


def validate_payload_against_schema(payload: Any, schema_filename: str) -> None:
    schema = load_schema(schema_filename)
    errors = validate_instance(payload, schema)
    if errors:
        raise ValueError(f"Schema validation failed ({schema_filename}):\n" + format_errors(errors))


def write_validated_json(path: Path, payload: Any, schema_filename: str) -> None:
    validate_payload_against_schema(payload, schema_filename)
    atomic_write_json(path, payload)


def sha256_file(path: Path) -> str:
    h = sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def write_background_job_artifact(path: Path, payload: Dict[str, Any]) -> None:
    write_validated_json(path, payload, "crt_background_job.v1.schema.json")


def write_promotion_proposals(path: Path, payload: Dict[str, Any]) -> None:
    write_validated_json(path, payload, "crt_promotion_proposals.v1.schema.json")


def write_audit_answer_record(path: Path, payload: Dict[str, Any]) -> None:
    write_validated_json(path, payload, "crt_audit_answer_record.v1.schema.json")


def make_minimal_audit_answer_record(
    *,
    answer_id: str,
    user_text: str,
    answer_text: str,
    mode: str,
    gate_reason: Optional[str] = None,
) -> Dict[str, Any]:
    return {
        "id": answer_id,
        "ts": now_iso_utc(),
        "user_text": user_text,
        "answer_text": answer_text,
        "mode": mode,
        "gate_reason": gate_reason,
        "retrieved_memory_ids": [],
        "retrieved_doc_ids": [],
        "contradiction_detected": None,
        "unresolved_contradictions": None,
    }
