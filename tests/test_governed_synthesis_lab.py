from labs.meaning_compression_lab.governed_synthesis_lab import (
    _cases,
    build_hybrid_model_render_prompt,
    build_model_render_prompt,
    repair_model_answer,
    render_canned_answer,
    render_governed_answer,
    render_model_hybrid_answer,
    render_model_answer,
    render_raw_answer,
    render_spine_only_answer,
    run_lab,
    verify_render,
)


def test_governed_synthesis_lab_passes_without_writes():
    result = run_lab()

    assert result["passed"] is True
    assert result["case_count"] == 13
    assert {case["case_id"] for case in result["cases"]} == {
        "deterministic_vs_epistemic_governance",
        "crt_epistemic_integrity",
        "purpose_color_ai",
        "archive_personal_blockers",
        "flower_orange_health_boundary",
        "state_parks_mill_bluff",
        "sensitive_archive_medical_summary",
        "tension_local_models_frontier_wedge",
        "tension_archive_evidence_not_memory",
        "tension_personal_aether_general_core",
        "tension_personality_without_fake_intimacy",
        "tension_mempalace_meaning_weight",
        "code_search_memory_candidates",
    }
    assert result["writes_performed"] is False
    assert result["support_pattern_import_performed"] is False
    assert result["reflection_create_performed"] is False
    assert result["raw_chain_of_thought_stored"] is False
    assert all(case["governed_wins"] for case in result["cases"])


def test_governed_render_beats_canned_and_raw_for_each_case():
    for spine in _cases():
        governed = verify_render(spine, render_governed_answer(spine))
        canned = verify_render(spine, render_canned_answer(spine))
        raw = verify_render(spine, render_raw_answer(spine))

        assert governed.passed is True
        assert governed.total_score > canned.total_score
        assert governed.total_score > raw.total_score
        assert governed.cannedness_score < canned.cannedness_score


def test_tension_packet_adds_value_over_plain_spine_render():
    tension_cases = [case for case in _cases() if case.tension_packet]

    assert {case.case_id for case in tension_cases} == {
        "tension_local_models_frontier_wedge",
        "tension_archive_evidence_not_memory",
        "tension_personal_aether_general_core",
        "tension_personality_without_fake_intimacy",
        "tension_mempalace_meaning_weight",
    }
    for spine in tension_cases:
        packet_render = verify_render(spine, render_governed_answer(spine))
        plain_render = verify_render(spine, render_spine_only_answer(spine))
        raw = verify_render(spine, render_raw_answer(spine))

        assert packet_render.passed is True
        assert packet_render.held_tension_score >= 0.65
        assert packet_render.total_score > plain_render.total_score
        assert plain_render.held_tension_score < packet_render.held_tension_score
        assert raw.passed is False
        assert raw.held_tension_score == 0.0


def test_crt_raw_answer_drift_is_caught():
    spine = next(case for case in _cases() if case.case_id == "crt_epistemic_integrity")
    raw = verify_render(spine, render_raw_answer(spine))

    assert raw.passed is False
    assert "Comprehensive Research and Technology" in raw.forbidden_claims_present


def test_canned_answer_fails_synthesis_even_when_not_dangerous():
    spine = next(case for case in _cases() if case.case_id == "purpose_color_ai")
    canned = verify_render(spine, render_canned_answer(spine))

    assert canned.passed is False
    assert canned.synthesis_score < 0.3
    assert canned.cannedness_score >= 0.5


def test_model_render_prompt_carries_spine_contract():
    spine = next(
        case for case in _cases()
        if case.case_id == "deterministic_vs_epistemic_governance"
    )

    prompt = build_model_render_prompt(spine)

    assert "You are Holden" in prompt
    assert "Mirus has already built the governed answer spine" in prompt
    assert "Include exactly these sections: Answer, Evidence Used, Boundary" in prompt
    assert "Required claims" in prompt
    assert "Forbidden claims" in prompt
    assert "Do not collapse mechanism and goal into the same concept" in prompt


def test_model_render_prompt_carries_tension_packet_when_present():
    spine = next(
        case for case in _cases()
        if case.case_id == "tension_archive_evidence_not_memory"
    )

    prompt = build_model_render_prompt(spine)

    assert "Tension Packet" in prompt
    assert "tp_archive_evidence_boundary" in prompt
    assert "Archive evidence is valuable" in prompt
    assert "Archive evidence is not confirmed memory" in prompt
    assert "Forbidden collapse" in prompt
    assert "include a short Held Tension section" in prompt


def test_hybrid_model_prompt_preserves_compact_evidence_and_trace_skeleton():
    spine = next(
        case for case in _cases()
        if case.case_id == "tension_mempalace_meaning_weight"
    )

    prompt = build_hybrid_model_render_prompt(spine)

    assert "hybrid contract" in prompt
    assert "compact evidence" in prompt
    assert "no hidden chain-of-thought" in prompt
    assert "Answer:" in prompt
    assert "Evidence Used:" in prompt
    assert "Held Tension:" in prompt
    assert "Boundary:" in prompt
    assert "Allowed synthesis" in prompt
    assert "Forbidden collapse" in prompt
    assert "Trace preview" in prompt
    assert "Mempalace" in prompt


def test_hybrid_model_renderer_can_pass_when_it_obeys_spine():
    spine = next(
        case for case in _cases()
        if case.case_id == "tension_local_models_frontier_wedge"
    )

    rendered = render_model_hybrid_answer(
        spine,
        complete=lambda _prompt: (
            "Answer:\n"
            "Frontier models have more parameters, inference compute, training, "
            "routing, and broad capability. Still, a small local model wrapped "
            "in governed memory, routing, verifier, repair, and trace can become "
            "more inspectable and personally continuous because Aether can hold "
            "evidence, scaffold, and rules outside the model. The wedge is not "
            "raw intelligence; it is externalized governance, continuity, "
            "inspection, and bounded synthesis.\n\n"
            "Evidence Used:\n"
            "- Frontier-model limit\n"
            "- Local-governance wedge\n"
            "- External workspace thesis\n\n"
            "Held Tension:\n"
            "- Side A: Local models are limited compared with frontier models.\n"
            "- Side B: A small local model wrapped in governed memory, routing, "
            "verifier, repair, and trace can be useful in narrower "
            "personal-continuity workflows.\n"
            "- Allowed synthesis: The wedge is not raw intelligence; it is "
            "externalized governance, continuity, inspection, and bounded synthesis.\n"
            "- Forbidden collapse: Do not flatten this into either frontier "
            "defeatism or local-model hype.\n"
            "- Trace preview: Hold both sides: frontier capability is real, "
            "local governed continuity can still be useful.\n\n"
            "Boundary:\n"
            "Do not claim local governance makes a small model globally frontier-level."
        ),
    )
    result = verify_render(spine, rendered)

    assert rendered.mode == "model_hybrid"
    assert rendered.render_mode == "hybrid_governed_spine_model_render"
    assert result.passed is True


def test_verifier_accepts_evidence_ids_as_receipts():
    spine = next(
        case for case in _cases()
        if case.case_id == "tension_personality_without_fake_intimacy"
    )
    rendered = render_model_hybrid_answer(
        spine,
        complete=lambda _prompt: (
            "Answer:\n"
            "Aether should feel warmer, more responsive, and less like a canned "
            "FAQ while not faking intimacy, flattering, transplanting GPT voice, "
            "or turning tone into confirmed truth. Personality should be "
            "grounded by evidence, source boundaries, review traces, and "
            "correction loops.\n\n"
            "Evidence Used:\n"
            "- personality_need\n"
            "- intimacy_boundary\n"
            "- trace_need\n\n"
            "Held Tension:\n"
            "- Side A: Personality matters.\n"
            "- Side B: Fake intimacy is unsafe.\n"
            "- Allowed synthesis: Aether can render with warmth when the warmth "
            "stays grounded in evidence, boundaries, traces, and user correction.\n"
            "- Forbidden collapse: Do not make Aether either sterile or "
            "ungroundedly intimate.\n"
            "- Trace preview: Governed personality means warmer rendering without "
            "surrendering source authority.\n\n"
            "Boundary:\n"
            "Do not solve stiffness by allowing fake intimacy or unreviewed voice transplant."
        ),
    )
    result = verify_render(spine, rendered)

    assert set(result.evidence_ids_used) == {
        "personality_need",
        "intimacy_boundary",
        "trace_need",
    }
    assert result.passed is True


def test_model_renderer_can_pass_when_it_obeys_the_spine():
    spine = next(case for case in _cases() if case.case_id == "crt_epistemic_integrity")

    rendered = render_model_answer(
        spine,
        complete=lambda _prompt: (
            "**CRT / epistemic integrity explanation**\n\n"
            "Evidence, inference, uncertainty, contradiction, and authority "
            "must stay separate. aether.crt contains trust, volatility, drift, "
            "and contradiction scoring. Trace receipts show route, memory, "
            "tools, verifier, repair, and learning candidates.\n\n"
            "**Boundary**\nDo not invent acronym expansions."
        ),
    )
    result = verify_render(spine, rendered)

    assert rendered.mode == "model"
    assert rendered.render_mode == "governed_spine_model_render"
    assert result.passed is True


def test_model_renderer_drift_is_caught_by_same_verifier():
    spine = next(case for case in _cases() if case.case_id == "crt_epistemic_integrity")

    rendered = render_model_answer(
        spine,
        complete=lambda _prompt: (
            "CRT means Comprehensive Research and Technology. It generally "
            "helps AI systems be more useful."
        ),
    )
    result = verify_render(spine, rendered)

    assert result.passed is False
    assert "Comprehensive Research and Technology" in result.forbidden_claims_present


def test_model_repair_can_rewrite_failed_render_to_pass():
    spine = next(case for case in _cases() if case.case_id == "crt_epistemic_integrity")
    failed = render_model_answer(
        spine,
        complete=lambda _prompt: (
            "CRT means Comprehensive Research and Technology. It generally "
            "helps AI systems be more useful."
        ),
    )
    failed_result = verify_render(spine, failed)

    repaired = repair_model_answer(
        spine,
        failed_answer=failed.text,
        verification=failed_result,
        complete=lambda prompt: (
            "**Answer**\n"
            "Evidence, inference, uncertainty, contradiction, and authority "
            "must stay separate. aether.crt contains trust, volatility, drift, "
            "and contradiction scoring. Trace receipts show route, memory, "
            "tools, verifier, repair, and learning candidates.\n\n"
            "**Evidence Used**\n"
            "- Governance boundary\n"
            "- CRT math layer\n"
            "- Workbench trace\n\n"
            "**Boundary**\n"
            "Do not invent acronym expansions."
        ),
    )

    assert repaired.render_mode == "governed_spine_model_repair"
    assert verify_render(spine, repaired).passed is True


def test_run_lab_can_include_model_adapter_results_without_writes():
    def complete(prompt: str) -> str:
        assert "Mirus has already built the governed answer spine" in prompt
        return (
            "This answer intentionally misses most required claims, but it does "
            "not write memory or store hidden reasoning."
        )

    result = run_lab(model_complete=complete, model_name="fake-small-model")

    assert result["model_name"] == "fake-small-model"
    assert result["model_repair_enabled"] is False
    assert result["model_case_count"] == 13
    assert result["model_pass_count"] == 0
    assert result["writes_performed"] is False
    assert result["raw_chain_of_thought_stored"] is False
    assert result["passed"] is True


def test_run_lab_can_filter_cases_and_use_hybrid_model_adapter():
    def complete(prompt: str) -> str:
        assert "hybrid contract" in prompt
        return "Generic failed hybrid answer."

    result = run_lab(
        model_complete=complete,
        model_name="fake-hybrid-model",
        hybrid_model=True,
        case_ids={"tension_mempalace_meaning_weight"},
    )

    assert result["model_name"] == "fake-hybrid-model"
    assert result["model_hybrid_enabled"] is True
    assert result["case_count"] == 1
    assert result["model_case_count"] == 1
    assert result["model_pass_count"] == 0
    assert result["writes_performed"] is False
    assert result["raw_chain_of_thought_stored"] is False
    assert result["passed"] is True


def test_run_lab_can_enable_model_repair_without_writes():
    def complete(_prompt: str) -> str:
        return (
            "**Answer**\n"
            "Deterministic governance means predictable rule application. "
            "Epistemic governance means preserving evidence, inference, "
            "uncertainty, contradiction, and authority. Aether should be "
            "deterministic about truth boundaries and generative about "
            "human-facing synthesis.\n\n"
            "**Evidence Used**\n"
            "- Deterministic mechanism\n"
            "- Epistemic goal\n"
            "- Synthesis rule\n\n"
            "**Boundary**\n"
            "Do not collapse mechanism and goal into the same concept."
        )

    spine = next(
        case for case in _cases()
        if case.case_id == "deterministic_vs_epistemic_governance"
    )
    initial = render_model_answer(spine, complete=lambda _prompt: "Generic failed answer.")
    repaired = repair_model_answer(
        spine,
        failed_answer=initial.text,
        verification=verify_render(spine, initial),
        complete=lambda _prompt: complete("repair"),
    )

    assert verify_render(spine, repaired).passed is True
