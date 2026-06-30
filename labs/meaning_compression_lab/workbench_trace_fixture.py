"""Isolated Workbench fixture import for local-router lab traces."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

from labs.meaning_compression_lab.workbench_evidence_adapter import load_rag_suite_result_for_workbench_review
from labs.meaning_compression_lab.workbench_trace_adapter import adapt_local_router_trace_for_workbench


def import_local_router_trace_fixture(
    trace: dict[str, Any],
    *,
    db_path: Path,
    answer: str = "Adapted local-router lab trace fixture.",
    conversation_id: str | None = None,
    allow_live_db: bool = False,
) -> dict[str, Any]:
    """Write an adapted lab trace into an isolated Workbench DB.

    This is a fixture/import bridge for tests and demos. By default it refuses
    Nick's live Workbench DB path so lab traces cannot be accidentally promoted
    into the dogfood database.
    """
    db_path = Path(db_path).expanduser()
    if not allow_live_db:
        _assert_not_live_workbench_db(db_path)
    WorkbenchDB = _load_workbench_db()
    adapted = adapt_local_router_trace_for_workbench(trace)
    db = WorkbenchDB(db_path)
    conversation_id, turn_id = db.begin_turn(
        conversation_id=conversation_id,
        message=str(adapted.get("query") or trace.get("user_request_summary") or ""),
        model=str(adapted.get("model") or trace.get("model_selected") or ""),
    )
    source_turn_id = adapted.get("turn_id")
    adapted["turn_id"] = turn_id
    adapted["conversation_id"] = conversation_id
    adapted.setdefault("local_router_trace", {})["source_turn_id"] = source_turn_id
    adapted["local_router_trace"]["fixture_import_only"] = True
    adapted["local_router_trace"]["memory_write_allowed"] = False
    db.save_trace(turn_id, adapted)
    db.complete_turn(
        turn_id,
        answer,
        needs_stronger_model=bool(adapted.get("completion", {}).get("needs_stronger_model")),
    )
    return {
        "db_path": str(db_path),
        "conversation_id": conversation_id,
        "turn_id": turn_id,
        "trace": adapted,
        "writes_performed": ["turn", "trace"],
        "memory_writes_performed": False,
        "fixture_import_only": True,
    }


def attach_rag_evidence_review_to_trace_fixture(
    *,
    db_path: Path,
    turn_id: str,
    rag_result_path: Path,
    allow_live_db: bool = False,
) -> dict[str, Any]:
    """Attach generated RAG evidence review metadata to an existing trace.

    This is intentionally fixture/import scoped. By default it refuses the live
    Workbench DB, and it only updates the trace JSON payload. It does not create
    reflections, import support patterns, or write memory.
    """
    db_path = Path(db_path).expanduser()
    if not allow_live_db:
        _assert_not_live_workbench_db(db_path)
    WorkbenchDB = _load_workbench_db()
    db = WorkbenchDB(db_path)
    row = db.get_trace(turn_id)
    if row is None:
        raise KeyError(f"Trace turn not found: {turn_id}")
    trace = dict(row.get("trace") or {})
    evidence_review = load_rag_suite_result_for_workbench_review(Path(rag_result_path))
    _assert_review_only_evidence(evidence_review)
    local_router_trace = dict(trace.get("local_router_trace") or {})
    local_router_trace["evidence_review"] = evidence_review
    local_router_trace["evidence_review_fixture_import_only"] = True
    local_router_trace["memory_write_allowed"] = False
    trace["local_router_trace"] = local_router_trace
    db.save_trace(turn_id, trace)
    return {
        "db_path": str(db_path),
        "turn_id": turn_id,
        "rag_result_path": str(rag_result_path),
        "evidence_review_attached": True,
        "writes_performed": ["trace"],
        "memory_writes_performed": False,
        "support_pattern_import_performed": False,
        "reflection_create_performed": False,
        "fixture_import_only": True,
    }


def _load_workbench_db():
    root = Path(__file__).resolve().parents[2]
    aether_core = root / "aether-core"
    if str(aether_core) not in sys.path:
        sys.path.insert(0, str(aether_core))
    from aether.sidecar.db import WorkbenchDB

    return WorkbenchDB


def _assert_not_live_workbench_db(db_path: Path) -> None:
    live = (Path.home() / ".aether" / "workbench.db").resolve()
    target = db_path.resolve()
    if target == live:
        raise ValueError(
            "Refusing to import lab trace fixture into the live Workbench DB. "
            "Use a temporary DB path or pass allow_live_db=True intentionally."
        )


def _assert_review_only_evidence(review: dict[str, Any]) -> None:
    if review.get("kind") != "local_router_rag_evidence_review":
        raise ValueError("RAG evidence review has an unexpected kind.")
    safety = review.get("safety_contract") or {}
    if safety.get("memory_writes_allowed") is not False:
        raise ValueError("RAG evidence review must block memory writes.")
    if safety.get("raw_chain_of_thought_stored") is not False:
        raise ValueError("RAG evidence review must not store raw hidden chain-of-thought.")
    if safety.get("silent_policy_mutation_allowed") is not False:
        raise ValueError("RAG evidence review must block silent policy mutation.")
