from __future__ import annotations

import json
from pathlib import Path

import jsonschema

from tools.agentic_eval.types import (
    AgentTurnPlan,
    ApiTurnResponse,
    JudgeAssessment,
    ProbeSnapshot,
    RunSummary,
    ScoreState,
    TurnRecord,
)


def _load_schema(name: str) -> dict:
    path = Path(__file__).resolve().parent.parent / "schemas" / name
    return json.loads(path.read_text(encoding="utf-8"))


def test_turn_artifact_schema_validates():
    turn = TurnRecord(
        turn=1,
        campaign_id=1,
        objective_id="obj_a",
        attacker_plan=AgentTurnPlan(
            objective_id="obj_a",
            user_message="Adaptive generated user turn.",
            hypothesis="test",
            expected_signals=["signal1"],
        ),
        api_result=ApiTurnResponse(
            answer="assistant answer",
            response_type="speech",
            gates_passed=True,
            gate_reason=None,
            session_id="abc",
            metadata={"confidence": 0.9, "unresolved_hard_conflicts": 0},
            status_code=200,
            ok=True,
        ),
        probes=ProbeSnapshot(
            contradictions=[],
            ledger_open=[],
            profile={},
            memory_recent=[],
            introspection={},
            notifications_recent=[],
            self_model={"reflection": {"updated_at": 1.0}},
            reflection_journal=[],
            memory_trust=[],
        ),
        judge=JudgeAssessment(
            objective_id="obj_a",
            objective_passed=True,
            summary="ok",
            findings=[],
        ),
        rule_findings=[],
        lineage_evidence={"has_traceable_memory": True},
        discovery_signals={"ambiguous_input": False},
        reinforcement_signals={"reinforcement_prompt": False},
        meta_awareness_signals={"meta_prompt": False},
        journal_signals={"entries_count": 0},
        hard_fail_triggered=False,
        hard_fail_reasons=[],
        timestamp_utc="2026-03-01T00:00:00Z",
    )
    schema = _load_schema("crt_agentic_eval_turn.v1.schema.json")
    jsonschema.validate(turn.to_dict(), schema)


def test_run_artifact_schema_validates():
    summary = RunSummary(
        run_id="run_1",
        started_at_utc="2026-03-01T00:00:00Z",
        finished_at_utc="2026-03-01T00:10:00Z",
        campaigns=1,
        turns_total=10,
        hard_fail=False,
        hard_fail_reasons=[],
        verdict="PASS",
        score=ScoreState(),
        model_selection={"attacker_model": "a", "judge_model": "b"},
        groundcheck_lane={"cases_total": 2, "cases_passed": 2, "hard_fail": False},
        section_scores={
            "continuity_endurance": 95.0,
            "fact_discovery_reinforcement": 92.0,
            "traceability_lineage": 96.0,
            "meta_awareness_authenticity": 94.0,
        },
        lane_summary={"agentic_lane": {"turns_total": 10}, "groundcheck_lane": {"cases_total": 2}},
    )
    schema = _load_schema("crt_agentic_eval_run.v1.schema.json")
    jsonschema.validate(summary.to_dict(), schema)
