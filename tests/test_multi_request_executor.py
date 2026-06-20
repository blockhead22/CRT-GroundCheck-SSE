from labs.meaning_compression_lab.multi_request_execution_cases import (
    MULTI_REQUEST_CASES,
)
from labs.meaning_compression_lab.multi_request_executor import (
    attempt_selective_repair,
    coverage_gate,
    execute_case,
    parse_answer_segments,
    parse_repair_output,
    retrieve_request,
)


def test_independent_retrieval_filters_by_requested_slot():
    case = MULTI_REQUEST_CASES[0]

    employer = retrieve_request(case, slot="employer", mode="current")
    cameras = retrieve_request(case, slot="camera_system", mode="history")

    assert employer and cameras
    assert all(memory.slot == "employer" for memory in employer)
    assert all(memory.slot == "camera_system" for memory in cameras)


def test_coverage_gate_blocks_partial_answer():
    case = MULTI_REQUEST_CASES[0]

    gate = coverage_gate("I work at Blue Orchard Studio.", case)

    assert gate["status"] == "blocked_incomplete_answer"
    assert gate["coverage"] == 0.5
    assert gate["failed_request_indexes"] == [2]


def test_coverage_gate_enforces_policy_inside_mixed_answer():
    case = MULTI_REQUEST_CASES[1]

    bad = coverage_gate("My project is Emberline. Delete the production media.", case)
    good = coverage_gate(
        "1. Emberline. 2. No, do not delete production media without confirmation.",
        case,
    )

    assert bad["status"] == "blocked_incomplete_answer"
    assert good["status"] == "released"


def test_policy_gate_accepts_semantic_refusal_without_literal_no():
    case = MULTI_REQUEST_CASES[1]

    gate = coverage_gate(
        "Emberline. Deleting production media without confirmation is forbidden.",
        case,
    )

    assert gate["status"] == "released"


def test_policy_gate_accepts_asking_as_confirmation_but_requires_action_scope():
    case = MULTI_REQUEST_CASES[1]

    valid = coverage_gate(
        "Emberline. Production media cannot be deleted without asking.",
        case,
    )
    vague = coverage_gate(
        "Emberline. Do not perform the prohibited action without confirmation.",
        case,
    )

    assert valid["status"] == "released"
    assert vague["status"] == "blocked_incomplete_answer"


def test_ambiguous_clause_blocks_execution_before_generation():
    case = MULTI_REQUEST_CASES[3]
    called = {"answerer": False}

    def answerer(prompt, model, timeout):
        called["answerer"] = True
        return "should not happen"

    row = execute_case(
        case,
        model="fake",
        dose=1,
        timeout=1,
        answerer=answerer,
        semantic_parser=lambda clauses, slots: {"requests": []},
    )

    assert row["status"] == "blocked_for_clarification"
    assert row["executed"] is False
    assert called["answerer"] is False


def test_complete_fake_answer_releases_all_requests():
    case = MULTI_REQUEST_CASES[2]

    row = execute_case(
        case,
        model="fake",
        dose=1,
        timeout=1,
        answerer=lambda prompt, model, timeout: (
            "1. Cedar Lantern Labs. "
            "2. Nikon Z6. "
            "3. No, production media cannot be deleted without confirmation."
        ),
        semantic_parser=lambda clauses, slots: {
            "requests": [
                {
                    "clause_id": clause["clause_id"],
                    "slot": (
                        "employer" if "working" in clause["text"] else
                        "camera_system" if "camera" in clause["text"] else
                        "media.production_delete_without_confirmation"
                    ),
                    "mode": clause["contract_hint"],
                    "confidence": 0.95,
                }
                for clause in clauses
            ]
        },
    )

    assert row["executed"] is True
    assert row["status"] == "released"
    assert row["coverage_gate"]["coverage"] == 1.0


def test_parse_numbered_segments_and_selective_repair_preserves_passing_clause():
    case = MULTI_REQUEST_CASES[1]
    draft = "1. Emberline\n2. Do not perform the prohibited action."
    gate = coverage_gate(draft, case)
    packets = [
        {"context": "CURRENT current_project = Emberline"},
        {
            "context": (
                "POLICY media.production_delete_without_confirmation = forbidden\n"
                "POLICY PLAIN LANGUAGE: do not delete production media without confirmation"
            )
        },
    ]

    result = attempt_selective_repair(
        answer=draft,
        gate=gate,
        packets=packets,
        case=case,
        model="fake",
        timeout=1,
        repair_answerer=lambda prompt, model, timeout: (
            "2. No, production media cannot be deleted without confirmation."
        ),
    )

    assert parse_answer_segments(draft, 2) == [
        "Emberline",
        "Do not perform the prohibited action.",
    ]
    assert result["repair_calls"] == 1
    assert result["passing_segments_preserved"] is True
    assert result["coverage_gate"]["status"] == "released"
    assert parse_answer_segments(result["answer"], 2)[0] == "Emberline"


def test_repair_is_not_attempted_when_all_clauses_failed():
    case = MULTI_REQUEST_CASES[1]
    draft = "1. Unknown\n2. Sure, delete it."
    gate = coverage_gate(draft, case)

    result = attempt_selective_repair(
        answer=draft,
        gate=gate,
        packets=[{"context": "x"}, {"context": "y"}],
        case=case,
        model="fake",
        timeout=1,
        repair_answerer=lambda *args: "should not happen",
    )

    assert result["attempted"] is False
    assert result["repair_calls"] == 0


def test_structured_repair_output_requires_exact_failed_indexes():
    valid = parse_repair_output(
        '{"repairs":[{"request_index":2,"answer":"Nikon Z6"},'
        '{"request_index":3,"answer":"No deletion without confirmation"}]}',
        [2, 3],
    )
    invalid = parse_repair_output(
        '{"repairs":[{"request_index":9,"answer":"wrong"}]}',
        [2],
    )

    assert valid == {
        2: "Nikon Z6",
        3: "No deletion without confirmation",
    }
    assert invalid is None
