import json
from pathlib import Path

import pytest
from jsonschema import Draft7Validator


CRT_SCHEMA_FILES = [
    "crt_runtime_config.v1.schema.json",
    "crt_background_job.v1.schema.json",
    "crt_promotion_proposals.v1.schema.json",
    "crt_audit_answer_record.v1.schema.json",
]


@pytest.mark.parametrize("schema_path", CRT_SCHEMA_FILES)
def test_crt_schema_loads_and_is_valid_draft7(schema_path: str):
    p = Path(__file__).resolve().parents[1] / schema_path
    assert p.exists(), f"Missing schema file: {p}"

    schema = json.loads(p.read_text(encoding="utf-8"))
    assert schema.get("$schema") == "http://json-schema.org/draft-07/schema#"

    # Validates that the schema itself is well-formed.
    Draft7Validator.check_schema(schema)
