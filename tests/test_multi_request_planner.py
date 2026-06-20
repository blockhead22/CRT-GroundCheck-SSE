from labs.meaning_compression_lab.multi_request_planner import (
    build_retrieval_plan,
    plan_requests,
    semantic_parser_prompt,
    split_clauses,
)


SLOTS = [
    "employer",
    "camera_system",
    "media.production_delete_without_confirmation",
    "current_project",
    "store_platform",
    "name",
    "file_naming",
]


def test_clause_split_and_multi_slot_recall():
    query = (
        "Where am I currently working, and which camera system did I use before? "
        "Also, can you delete production media without confirmation?"
    )

    plan = plan_requests(query, SLOTS)

    assert len(split_clauses(query)) == 3
    assert plan.status == "resolved"
    assert plan.coverage == 1.0
    assert {(request.slot, request.mode) for request in plan.requests} == {
        ("employer", "current"),
        ("camera_system", "history"),
        ("media.production_delete_without_confirmation", "policy"),
    }


def test_comma_separated_questions_split_without_repeated_and():
    query = (
        "Where am I working now, what camera was before Blackmagic, "
        "and can production media be deleted without asking?"
    )

    clauses = split_clauses(query)

    assert clauses == [
        "Where am I working now",
        "what camera was before Blackmagic",
        "and can production media be deleted without asking",
    ]


def test_ambiguous_clause_does_not_erase_resolved_clause():
    query = "Where am I currently working, and what name should appear in generated files?"

    plan = plan_requests(query, SLOTS)

    assert plan.status == "partial"
    assert plan.coverage == 0.5
    assert {(request.slot, request.mode) for request in plan.requests} == {
        ("employer", "current")
    }
    assert plan.unresolved_clauses == ("c2",)


def test_semantic_parser_can_resolve_only_unresolved_clause():
    def parser(clauses, slots):
        assert clauses[0]["clause_id"] == "c2"
        assert "file_naming" in slots
        return {
            "requests": [
                {
                    "clause_id": "c2",
                    "slot": "file_naming",
                    "mode": "current",
                    "confidence": 0.91,
                }
            ]
        }

    plan = plan_requests(
        "Where am I currently working, and what name should appear in generated files?",
        SLOTS,
        semantic_parser=parser,
    )

    assert plan.status == "resolved"
    assert plan.coverage == 1.0
    assert {(request.slot, request.source) for request in plan.requests} == {
        ("employer", "deterministic"),
        ("file_naming", "semantic_parser"),
    }
    assert [request.clause_id for request in plan.requests] == ["c1", "c2"]


def test_semantic_parser_invented_slot_is_rejected():
    plan = plan_requests(
        "Explain the thing I mentioned yesterday.",
        SLOTS,
        semantic_parser=lambda clauses, slots: {
            "requests": [
                {
                    "clause_id": "c1",
                    "slot": "invented_slot",
                    "mode": "current",
                    "confidence": 0.99,
                }
            ]
        },
    )

    assert plan.status == "unknown"
    assert plan.requests == ()
    assert plan.coverage == 0.0


def test_retrieval_plan_preserves_independent_requests():
    plan = plan_requests(
        "Where am I currently working and which camera system did I use before?",
        SLOTS,
    )

    retrieval = build_retrieval_plan(plan, per_request_k=3)

    assert len(retrieval) == 2
    assert {row["slot"] for row in retrieval} == {"employer", "camera_system"}
    assert all(row["top_k"] == 3 for row in retrieval)


def test_semantic_parser_prompt_exposes_catalog_and_schema():
    prompt = semantic_parser_prompt(
        [{"clause_id": "c1", "text": "What did I use?", "candidate_slots": []}],
        SLOTS,
    )

    assert "Do not invent slots" in prompt
    assert "camera_system" in prompt
    assert '"requests"' in prompt
