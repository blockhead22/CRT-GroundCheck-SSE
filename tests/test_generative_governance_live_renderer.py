from labs.meaning_compression_lab.generative_governance_live_renderer import (
    expanded_holdout_cases,
    run_live_renderer_compare,
    scripted_renderer,
    strip_reasoning_blocks,
)


def test_live_renderer_compare_passes_with_scripted_renderer_without_writes():
    result = run_live_renderer_compare(scripted_renderer, renderer_label="scripted")

    assert result["passed"] is True
    assert result["case_count"] == 5
    assert result["writes_performed"] is False
    assert result["memory_write_performed"] is False
    assert result["support_pattern_import_performed"] is False
    assert result["reflection_create_performed"] is False
    assert result["raw_chain_of_thought_stored"] is False


def test_trace_memory_governance_avoids_model_calls_for_boundary_cases():
    result = run_live_renderer_compare(scripted_renderer, renderer_label="scripted")
    by_case = {row["case_id"]: row for row in result["rows"]}

    personal = by_case["holdout_personal_no_receipts"]["renders"][1]
    conflict = by_case["holdout_memory_conflict"]["renders"][1]

    assert personal["mode"] == "governance_only"
    assert personal["model_called"] is False
    assert conflict["mode"] == "governance_only"
    assert conflict["model_called"] is False
    assert result["summary"]["governance_model_calls_avoided"] == 2


def test_governed_renderer_scores_above_model_only_on_each_case():
    result = run_live_renderer_compare(scripted_renderer, renderer_label="scripted")

    for row in result["rows"]:
        model_only = row["renders"][0]["evaluation"]
        governed = row["renders"][1]["evaluation"]
        assert governed["score"] >= model_only["score"]
        assert governed["passed"] is True


def test_rich_cases_use_trace_memory_plus_model_path():
    result = run_live_renderer_compare(scripted_renderer, renderer_label="scripted")
    by_case = {row["case_id"]: row for row in result["rows"]}

    for case_id in (
        "holdout_personal_grounded_receipts",
        "holdout_architecture_governance",
        "holdout_business_bounded",
    ):
        render = by_case[case_id]["renders"][1]
        assert render["mode"] == "governance_trace_memory_plus_model"
        assert render["model_called"] is True
        assert render["prompt_kind"] == "mirus_trace_memory_spine"


def test_expanded_pack_passes_with_scripted_renderer():
    result = run_live_renderer_compare(
        scripted_renderer,
        renderer_label="scripted",
        cases=expanded_holdout_cases(),
    )

    assert result["passed"] is True
    assert result["case_count"] == 24
    assert result["summary"]["governed_passes"] == 24
    assert result["summary"]["governance_model_calls_avoided"] == 6


def test_expanded_pack_keeps_boundary_and_render_split():
    result = run_live_renderer_compare(
        scripted_renderer,
        renderer_label="scripted",
        cases=expanded_holdout_cases(),
    )

    boundary_rows = [
        row for row in result["rows"]
        if row["trace_memory_decision"]["decision"] == "governance_only"
    ]
    render_rows = [
        row for row in result["rows"]
        if row["trace_memory_decision"]["decision"] == "governance_plus_model"
    ]

    assert len(boundary_rows) == 6
    assert len(render_rows) == 18
    assert all(row["renders"][1]["model_called"] is False for row in boundary_rows)
    assert all(row["renders"][1]["model_called"] is True for row in render_rows)


def test_governed_renderer_can_repair_failed_public_answer():
    attempts = {"count": 0}

    def renderer(prompt: str) -> str:
        attempts["count"] += 1
        if "Verifier notes:" in prompt:
            return (
                "I am treating this as business planning. Receipts: The Printing Lair "
                "can produce low-batch stickers and custom prints; Camera work has "
                "examples but no stable full-time revenue proof. The bounded answer is "
                "that this is a practical lane to test, not a guaranteed income or "
                "full-time replacement claim."
            )
        return "Intent: business_planning."

    case = next(
        item for item in expanded_holdout_cases()
        if item.case_id == "expanded_business_001_print_camera_lane"
    )
    result = run_live_renderer_compare(renderer, renderer_label="repair-test", cases=(case,))
    governed = result["rows"][0]["renders"][1]

    assert result["passed"] is True
    assert attempts["count"] == 3
    assert governed["repair_count"] == 1
    assert governed["evaluation"]["passed"] is True
    assert "no_receipt_hits" in governed["repair_notes"]


def test_strip_reasoning_blocks_before_artifact_storage():
    text = "Hello. <think>private scratch text</think> Public answer. <reasoning>more scratch</reasoning>"

    stripped = strip_reasoning_blocks(text)

    assert stripped == "Hello.  Public answer."
    assert "private scratch" not in stripped
    assert "more scratch" not in stripped
