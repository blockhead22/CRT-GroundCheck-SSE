import sys
from pathlib import Path

import pytest

from labs.meaning_compression_lab.workbench_trace_fixture import import_local_router_trace_fixture


def _load_workbench_db():
    root = Path(__file__).resolve().parents[1]
    aether_core = root / "aether-core"
    if str(aether_core) not in sys.path:
        sys.path.insert(0, str(aether_core))
    from aether.sidecar.db import WorkbenchDB

    return WorkbenchDB


def _trace() -> dict:
    return {
        "trace_schema": "aether.local_router.trace.v0",
        "turn_id": "local_router_cli:cli_architecture_process:1",
        "conversation_id": "local_router_cli",
        "source": "local_router_cli",
        "user_request_summary": "Map the local-router trace into Workbench.",
        "task_type": "architecture_process",
        "route_selected": {
            "task_type": "architecture_process",
            "model": "qwen2.5:7b-instruct",
            "profile": "section_lock",
            "reason": "Architecture/process planning needs concrete next steps.",
        },
        "model_selected": "qwen2.5:7b-instruct",
        "scaffold_profile": "section_lock",
        "mirus_packet_summary": {
            "required_concept_count": 4,
        },
        "evidence_anchors": ["roadmap", "architecture", "risk"],
        "verifier_flags": {
            "passed": True,
            "truncated": False,
            "leakage_hits": [],
            "weirdness_hits": [],
            "forbidden_hits": [],
            "receipt_hits": ["roadmap", "architecture", "risk"],
            "concept_hits": ["mechanism", "sequence", "verification", "next useful move"],
        },
        "repair_attempts": 0,
        "fallback_used": False,
        "final_confidence": "high",
        "promotion_status": "none",
        "raw_chain_of_thought_stored": False,
    }


def test_import_local_router_trace_fixture_writes_reloadable_workbench_trace(tmp_path):
    db_path = tmp_path / "workbench.db"

    result = import_local_router_trace_fixture(
        _trace(),
        db_path=db_path,
        answer="Fixture answer.",
    )

    WorkbenchDB = _load_workbench_db()
    loaded = WorkbenchDB(db_path).get_trace(result["turn_id"])
    assert loaded is not None
    assert loaded["local_answer"] == "Fixture answer."
    assert loaded["trace"]["turn_id"] == result["turn_id"]
    assert loaded["trace"]["conversation_id"] == result["conversation_id"]
    assert loaded["trace"]["route_decision"]["selected_route"] == "local_router_architecture_process"
    assert loaded["trace"]["local_router_trace"]["fixture_import_only"] is True
    assert loaded["trace"]["local_router_trace"]["memory_write_allowed"] is False
    assert loaded["trace"]["local_router_trace"]["source_turn_id"] == "local_router_cli:cli_architecture_process:1"
    assert result["memory_writes_performed"] is False


def test_import_local_router_trace_fixture_refuses_live_workbench_db():
    with pytest.raises(ValueError, match="live Workbench DB"):
        import_local_router_trace_fixture(
            _trace(),
            db_path=Path.home() / ".aether" / "workbench.db",
        )
