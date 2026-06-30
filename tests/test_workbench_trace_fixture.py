import json
import sys
from pathlib import Path

import pytest

root = Path(__file__).resolve().parents[1]
aether_core = root / "aether-core"
if str(root) not in sys.path:
    sys.path.insert(0, str(root))
if str(aether_core) not in sys.path:
    sys.path.insert(1, str(aether_core))

from labs.meaning_compression_lab.workbench_trace_evidence_attach_cli import (
    LIVE_DB_CONFIRMATION,
    main as attach_cli_main,
)
from labs.meaning_compression_lab.workbench_trace_fixture import (
    attach_rag_evidence_review_to_trace_fixture,
    import_local_router_trace_fixture,
)
from aether.sidecar.consolidation import propose_consolidation_candidates


def _load_workbench_db():
    if str(aether_core) not in sys.path:
        sys.path.insert(1, str(aether_core))
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


def test_attach_rag_evidence_review_to_trace_fixture_persists_review_metadata(tmp_path):
    db_path = tmp_path / "workbench.db"
    result = import_local_router_trace_fixture(
        _trace(),
        db_path=db_path,
        answer="Fixture answer.",
    )

    receipt = attach_rag_evidence_review_to_trace_fixture(
        db_path=db_path,
        turn_id=result["turn_id"],
        rag_result_path=Path("labs/meaning_compression_lab/results/local_router_rag_suite_1782766406.json"),
    )

    WorkbenchDB = _load_workbench_db()
    loaded = WorkbenchDB(db_path).get_trace(result["turn_id"])
    review = loaded["trace"]["local_router_trace"]["evidence_review"]
    assert receipt["evidence_review_attached"] is True
    assert receipt["memory_writes_performed"] is False
    assert receipt["support_pattern_import_performed"] is False
    assert receipt["reflection_create_performed"] is False
    assert review["kind"] == "local_router_rag_evidence_review"
    assert review["baseline_to_beat"] == "scaffolded_rag"
    assert review["safety_contract"]["memory_writes_allowed"] is False
    assert loaded["trace"]["local_router_trace"]["evidence_review_fixture_import_only"] is True


def test_attached_rag_evidence_review_surfaces_as_read_only_consolidation_candidate(tmp_path):
    db_path = tmp_path / "workbench.db"
    result = import_local_router_trace_fixture(
        _trace(),
        db_path=db_path,
        answer="Fixture answer.",
    )
    attach_rag_evidence_review_to_trace_fixture(
        db_path=db_path,
        turn_id=result["turn_id"],
        rag_result_path=Path("labs/meaning_compression_lab/results/local_router_rag_suite_1782766406.json"),
    )

    WorkbenchDB = _load_workbench_db()
    rows = WorkbenchDB(db_path).recent_turn_traces(limit=10)
    candidates = propose_consolidation_candidates(rows, limit=10)

    candidate = next(
        item for item in candidates
        if item["category"] == "local_router_rag_evidence"
    )
    assert candidate["review_route"]["surface"] == "reflections"
    assert candidate["review_route"]["requires_adapter"] is True
    assert candidate["memory_write_allowed"] is False
    assert candidate["confirmed_fact"] is False
    assert "governed 6/6 trace 6/6" in candidate["evidence"][0]["summary"]


def test_attach_rag_evidence_review_refuses_live_workbench_db():
    with pytest.raises(ValueError, match="live Workbench DB"):
        attach_rag_evidence_review_to_trace_fixture(
            db_path=Path.home() / ".aether" / "workbench.db",
            turn_id="turn_missing",
            rag_result_path=Path("labs/meaning_compression_lab/results/local_router_rag_suite_1782766406.json"),
        )


def test_trace_evidence_attach_cli_writes_receipt_for_isolated_db(tmp_path):
    db_path = tmp_path / "workbench.db"
    receipt_path = tmp_path / "attach_receipt.json"
    result = import_local_router_trace_fixture(
        _trace(),
        db_path=db_path,
        answer="Fixture answer.",
    )

    exit_code = attach_cli_main([
        "--db-path",
        str(db_path),
        "--turn-id",
        result["turn_id"],
        "--rag-result-path",
        "labs/meaning_compression_lab/results/local_router_rag_suite_1782766406.json",
        "--output",
        str(receipt_path),
    ])

    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    WorkbenchDB = _load_workbench_db()
    loaded = WorkbenchDB(db_path).get_trace(result["turn_id"])
    assert exit_code == 0
    assert receipt["evidence_review_attached"] is True
    assert receipt["memory_writes_performed"] is False
    assert loaded["trace"]["local_router_trace"]["evidence_review"]["kind"] == "local_router_rag_evidence_review"


def test_trace_evidence_attach_cli_requires_exact_live_confirmation():
    with pytest.raises(ValueError, match="Live Workbench DB attachment requires"):
        attach_cli_main([
            "--db-path",
            str(Path.home() / ".aether" / "workbench.db"),
            "--turn-id",
            "turn_missing",
            "--rag-result-path",
            "labs/meaning_compression_lab/results/local_router_rag_suite_1782766406.json",
            "--allow-live-db",
            "--confirm-live-db",
            "wrong",
        ])

    assert LIVE_DB_CONFIRMATION == "ATTACH_REVIEW_ONLY_TRACE_EVIDENCE"
