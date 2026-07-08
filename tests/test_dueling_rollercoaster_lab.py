from __future__ import annotations

from labs.dueling_rollercoaster_lab.dueling_rollercoaster_lab import (
    MATRIX_MODES,
    RenderResult,
    build_compressed_prompt,
    build_hybrid_prompt,
    build_repair_prompt,
    build_prompt,
    cases,
    default_models,
    extract_public_trace,
    parse_model_spec,
    parse_mode_spec,
    run_lab,
    score_result,
    scripted_render,
)


def _aggregate(report, model_kind: str, mode: str):
    return next(
        row for row in report["aggregate"]
        if row["model_kind"] == model_kind and row["mode"] == mode
    )


def _case(report, case_id: str):
    return next(row for row in report["cases"] if row["case_id"] == case_id)


def _row(case_row, model_kind: str, mode: str):
    return next(
        row for row in case_row["rows"]
        if row["model_kind"] == model_kind and row["mode"] == mode
    )


def test_dueling_rollercoaster_scripted_matrix_has_expected_shape():
    report = run_lab(write_results=False)

    assert report["lab"] == "dueling_rollercoaster_v0"
    assert report["case_count"] == 4
    assert report["matrix_row_count"] == 88
    assert report["raw_hidden_chain_of_thought_stored"] is False
    assert report["public_reasoning_trace_only"] is True
    assert report["writes_performed"] is False
    assert set(report["modes"]) == set(MATRIX_MODES)


def test_governed_repair_beats_raw_and_standard_rag_for_standard_model():
    report = run_lab(write_results=False)

    raw = _aggregate(report, "standard", "raw_model")
    rag = _aggregate(report, "standard", "standard_rag")
    governed_repair = _aggregate(report, "standard", "governed_scaffolded_repair")

    assert governed_repair["avg_score"] > raw["avg_score"]
    assert governed_repair["avg_score"] > rag["avg_score"]
    assert governed_repair["passed"] > raw["passed"]
    assert governed_repair["coherence_breaks"] < raw["coherence_breaks"]
    assert governed_repair["semantic_passed"] >= governed_repair["passed"]


def test_reasoning_model_still_benefits_from_governed_repair():
    report = run_lab(write_results=False)

    raw = _aggregate(report, "reasoning", "raw_model")
    scaffold = _aggregate(report, "reasoning", "scaffolded_public_reasoning")
    governed_repair = _aggregate(report, "reasoning", "governed_scaffolded_repair")

    assert scaffold["avg_score"] >= raw["avg_score"]
    assert governed_repair["avg_score"] > scaffold["avg_score"]
    assert governed_repair["passed"] >= scaffold["passed"]


def test_deterministic_governance_ceiling_passes_every_case():
    report = run_lab(write_results=False)
    ceiling = _aggregate(report, "standard", "deterministic_governance_ceiling")

    assert ceiling["count"] == 4
    assert ceiling["passed"] == 4
    assert ceiling["avg_score"] >= 0.9


def test_purpose_color_case_catches_single_slot_collapse():
    report = run_lab(write_results=False)
    case_row = _case(report, "purpose_color_multi_fact")

    raw_standard = _row(case_row, "standard", "raw_model")
    repair_standard = _row(case_row, "standard", "governed_scaffolded_repair")

    assert "your favorite color is orange." in raw_standard["score"]["forbidden_present"]
    assert raw_standard["score"]["passed"] is False
    assert repair_standard["score"]["passed"] is True
    assert "single fact" in repair_standard["answer"].lower()


def test_sensitive_archive_case_keeps_medical_history_source_bound():
    report = run_lab(write_results=False)
    case_row = _case(report, "archive_medical_source_boundary")

    raw_standard = _row(case_row, "standard", "raw_model")
    governed = _row(case_row, "standard", "governed_scaffolded_repair")

    assert "medical history includes leukemia" in raw_standard["score"]["forbidden_present"]
    assert governed["score"]["forbidden_present"] == []
    assert "not confirmed memory" in governed["answer"].lower()
    assert governed["public_reasoning_trace"]


def test_governed_prompt_contains_public_trace_and_no_hidden_cot_contract():
    case = cases()[0]
    prompt = build_prompt(case, "governed_scaffolded_reasoning")

    assert "Public Reasoning" in prompt
    assert "Do not store hidden chain-of-thought" in prompt
    assert "Required claims" in prompt
    assert "Required boundaries" in prompt
    assert "Forbidden claims" in prompt


def test_compressed_prompt_keeps_contract_small_and_public():
    case = cases()[0]
    prompt = build_compressed_prompt(case)

    assert "compact governed render contract" in prompt
    assert "Must say:" in prompt
    assert "Must not say:" in prompt
    assert "Public Reasoning:" in prompt
    assert "No hidden chain-of-thought" in prompt
    assert len(prompt) < len(build_prompt(case, "governed_scaffolded_reasoning"))


def test_hybrid_prompt_keeps_compact_evidence_with_explicit_trace_skeleton():
    case = cases()[0]
    prompt = build_hybrid_prompt(case)

    assert "hybrid governed render contract" in prompt
    assert "Return exactly these public sections" in prompt
    assert "Public Reasoning:" in prompt
    assert "Held Tension:" in prompt
    assert "Answer:" in prompt
    assert "Boundary:" in prompt
    assert "identify request" in prompt
    assert "connect purpose" in prompt
    assert "Do not reveal or store hidden chain-of-thought" in prompt


def test_semantic_pass_can_be_separated_from_trace_marker_pass():
    case = next(case for case in cases() if case.case_id == "purpose_color_multi_fact")
    result = RenderResult(
        "test-model",
        "standard",
        "governed_scaffolded_repair",
        (
            "Aether's purpose is governed local context, memory, evidence, and "
            "bounded synthesis. Orange is relevant as a confirmed favorite color, "
            "but the answer should not reduce and should do not reduce the request "
            "to a single fact. "
            "Held tension: multi-fact, not just color."
        ),
        public_reasoning_trace=(),
    )

    score = score_result(case, result)

    assert score.semantic_passed is True
    assert score.trace_marker_passed is False
    assert score.passed is False


def test_negated_forbidden_medical_claim_is_not_flagged():
    case = next(case for case in cases() if case.case_id == "archive_medical_source_boundary")
    result = RenderResult(
        "test-model",
        "standard",
        "hybrid_governed_repair",
        (
            "Public Reasoning: source type archive; boundary; avoid confirmation. "
            "Held Tension: sensitive archive-only. "
            "Answer: The archive medical material may mention leukemia and should be "
            "handled as source-bound historical evidence for review. "
            "Boundary: These archive hits should not be treated as confirmed medical "
            "history and are not confirmed memory."
        ),
        public_reasoning_trace=("source type archive", "boundary", "avoid confirmation"),
    )

    score = score_result(case, result)

    assert score.forbidden_present == []
    assert score.semantic_passed is True


def test_boundary_aliases_score_without_forcing_a_winner():
    case = next(case for case in cases() if case.case_id == "held_tension_local_vs_frontier")
    answer = (
        "Public Reasoning: side a; side b; allowed synthesis. "
        "Held Tension: hold both tension. "
        "Answer: local models are limited, and governed local systems still matter. "
        "Boundary: They do not compete globally; both perspectives coexist without "
        "forcing a winner."
    )
    result = RenderResult(
        "test-model",
        "reasoning",
        "hybrid_governed_repair",
        answer,
        public_reasoning_trace=extract_public_trace(answer),
    )

    score = score_result(case, result)

    assert "do not force a winner" not in score.missing_boundaries
    assert score.semantic_passed is True


def test_parse_model_spec_labels_reasoning_models():
    models = parse_model_spec("qwen2.5:7b-instruct,qwen3:14b,deepseek-r1:8b")

    assert [model.model_kind for model in models] == [
        "standard",
        "reasoning",
        "reasoning",
    ]
    assert [model.model_id for model in default_models()] == [
        "qwen2.5:7b-instruct",
        "qwen3:14b",
        "deepseek-r1:8b",
    ]


def test_parse_mode_spec_filters_matrix_for_focused_live_runs():
    modes = parse_mode_spec("compressed_governed_repair")
    report = run_lab(modes=modes, write_results=False)

    assert modes == ("compressed_governed_repair",)
    assert report["modes"] == ("compressed_governed_repair",)
    assert report["matrix_row_count"] == 12


def test_public_reasoning_scaffold_scores_trace_quality_without_private_cot():
    case = next(case for case in cases() if case.case_id == "held_tension_local_vs_frontier")
    model = default_models()[0]
    result = scripted_render(case, model, "scaffolded_public_reasoning")
    score = score_result(case, result)

    assert result.public_reasoning_trace
    assert score.public_reasoning_trace_quality == 1.0
    assert "hidden" not in " ".join(result.public_reasoning_trace).lower()


def test_repair_prompt_uses_public_verifier_delta_not_hidden_cot():
    case = next(case for case in cases() if case.case_id == "purpose_color_multi_fact")
    model = default_models()[0]
    previous = scripted_render(case, model, "raw_model")
    score = score_result(case, previous)
    prompt = build_repair_prompt(case, previous, score)

    assert "Verifier delta:" in prompt
    assert "missing required claim: purpose" in prompt
    assert "forbidden claim present: your favorite color is orange." in prompt
    assert "Do not reveal or store hidden chain-of-thought" in prompt
    assert "Return sections: Public Reasoning, Answer, Boundary" in prompt
