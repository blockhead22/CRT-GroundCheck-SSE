from labs.global_workspace_probe_lab.workspace_probe_lab import (
    _cases,
    build_compressed_model_prompt,
    build_compressed_repair_prompt,
    build_real_model_prompt,
    build_repair_prompt,
    render_external_workspace,
    render_raw_shadow,
    run_lab,
    verify_probe,
)


def test_global_workspace_probe_lab_v1_passes_without_activation_reads():
    result = run_lab()

    assert result["passed"] is True
    assert result["case_count"] == 9
    assert result["activation_reads_performed"] is False
    assert result["hf_or_jlens_dependency_required"] is False
    assert result["writes_performed"] is False
    assert result["raw_chain_of_thought_stored"] is False
    assert result["external_workspace_pass_count"] == 9
    assert result["external_workspace_wins"] == 9
    assert result["external_workspace_wins_over_real_model"] == 0
    assert result["external_workspace_model_case_count"] == 0
    assert result["external_workspace_model_repair_case_count"] == 0
    assert result["compressed_workspace_model_case_count"] == 0
    assert result["compressed_workspace_model_repair_case_count"] == 0


def test_probe_cases_cover_anthropic_comparison_classes():
    case_ids = {case.case_id for case in _cases()}

    assert case_ids == {
        "ascii_face_spatial_parse",
        "hidden_spider_step",
        "country_broadcast",
        "copy_while_thinking",
        "prompt_injection_suspicion",
        "external_workspace_compensation",
        "wrong_workspace_spider_ant",
        "held_tension_local_model_wedge",
        "held_tension_archive_not_memory",
    }
    assert all(case.repo_comparison for case in _cases())


def test_external_workspace_beats_raw_shadow_for_every_case():
    for case in _cases():
        raw = verify_probe(case, render_raw_shadow(case))
        external = verify_probe(case, render_external_workspace(case))

        assert external.passed is True
        assert external.total > raw.total


def test_ascii_face_case_tracks_screenshot_target():
    case = next(case for case in _cases() if case.case_id == "ascii_face_spatial_parse")
    raw = verify_probe(case, render_raw_shadow(case))
    external = verify_probe(case, render_external_workspace(case))

    assert "nose" in raw.missing_outputs
    assert "smile" in raw.missing_outputs
    assert "eye" in raw.missing_outputs
    assert external.reportability == 1.0
    assert external.output_correctness == 1.0


def test_prompt_injection_shadow_fails_safety_boundary():
    case = next(case for case in _cases() if case.case_id == "prompt_injection_suspicion")
    raw = verify_probe(case, render_raw_shadow(case))

    assert raw.passed is False
    assert "look trustworthy" in raw.forbidden_present


def test_optional_model_adapter_can_be_scored_without_jlens_dependency():
    def weak_model(case):
        return render_raw_shadow(case)

    result = run_lab(model_complete=weak_model, model_name="fake-local-model")

    assert result["model_name"] == "fake-local-model"
    assert result["activation_reads_performed"] is False
    assert result["hf_or_jlens_dependency_required"] is False
    assert result["external_workspace_pass_count"] == 9


def test_wrong_workspace_packet_is_rejected():
    case = next(case for case in _cases() if case.case_id == "wrong_workspace_spider_ant")
    raw = render_raw_shadow(case)
    raw_score = verify_probe(case, raw)
    external = render_external_workspace(case)
    external_score = verify_probe(case, external)

    assert raw_score.passed is False
    assert raw_score.forbidden_present == ["ant has 6 legs", "answer is 6"]
    assert external.packet_status == "rejected"
    assert external_score.passed is True
    assert "wrong workspace" in external.text.lower()
    assert "verifier" in external.text.lower()


def test_held_tension_cases_are_preserved_by_external_workspace():
    for case_id in ("held_tension_local_model_wedge", "held_tension_archive_not_memory"):
        case = next(case for case in _cases() if case.case_id == case_id)
        raw = verify_probe(case, render_raw_shadow(case))
        external = verify_probe(case, render_external_workspace(case))

        assert external.held_tension == 1.0
        assert external.total > raw.total
        assert external.passed is True


def test_real_model_adapter_can_be_scored_without_ollama():
    def fake_complete(prompt):
        if "wrong_workspace_spider_ant" in prompt:
            if "Failure delta:" in prompt:
                return (
                    "Reject: wrong workspace.\n"
                    "Side A: Prompt implies spider.\n"
                    "Side B: Workspace says ant.\n"
                    "Allowed synthesis: reject the packet and preserve spider.\n"
                    "Forbidden collapse: do not render ant as the answer.\n"
                    "Trace preview: verifier preserved forbidden collapse and wrong workspace.\n"
                    "Reported concepts: forbidden collapse, verifier, reject, wrong workspace"
                )
            if "Verifier failures:" in prompt:
                return (
                    "Reject: wrong workspace.\n"
                    "Held Tension: wrong hidden concept.\n"
                    "Side A: Prompt implies spider.\n"
                    "Side B: Workspace says ant.\n"
                    "Allowed synthesis: reject the packet and answer from the prompt concept.\n"
                    "Forbidden collapse: do not render ant as the answer.\n"
                    "Trace preview: verifier preserved the spider/ant mismatch.\n"
                    "Reported concepts: forbidden collapse, verifier, reject, wrong workspace"
                )
            if "Tension Packet / Workspace Spine" in prompt:
                return "8\nReported concepts: spider"
            if "Compressed render contract" in prompt:
                return "8\nReported concepts: spider"
            return "8\nReported concepts: spider"
        return "Generic answer.\nReported concepts: generic"

    case = next(case for case in _cases() if case.case_id == "wrong_workspace_spider_ant")
    result = run_lab(
        real_model_complete=fake_complete,
        real_model_name="fake-qwen",
    )
    row = next(row for row in result["cases"] if row["case_id"] == case.case_id)

    assert result["real_model_name"] == "fake-qwen"
    assert result["real_model_case_count"] == 9
    assert result["external_workspace_model_case_count"] == 4
    assert result["external_workspace_model_repair_case_count"] == 4
    assert result["external_workspace_model_repair_pass_count"] >= 1
    assert result["compressed_workspace_model_case_count"] == 4
    assert result["compressed_workspace_model_repair_case_count"] == 4
    assert result["compressed_workspace_model_repair_pass_count"] >= 1
    assert result["external_workspace_wins_over_real_model"] >= 1
    assert row["real_model"]["packet_status"] == "none"
    assert row["external_workspace_model_render"]["packet_status"] == "used"
    assert row["external_workspace_model_repair"]["packet_status"] == "rejected"
    assert row["external_workspace_model_repair"]["score"]["held_tension"] == 1.0
    assert row["external_workspace_model_repair_wins_over_model_render"] is True
    assert row["compressed_workspace_model_render"]["packet_status"] == "used"
    assert row["compressed_workspace_model_repair"]["packet_status"] == "rejected"
    assert row["compressed_workspace_model_repair_wins_over_compressed"] is True


def test_real_model_prompt_contains_packet_contract():
    case = next(case for case in _cases() if case.case_id == "held_tension_archive_not_memory")
    prompt = build_real_model_prompt(case, include_packet=True)
    raw_prompt = build_real_model_prompt(case)

    assert "Tension Packet / Workspace Spine" in prompt
    assert "Evidence nodes:" in prompt
    assert "Forbidden collapses:" in prompt
    assert "Verifier expectations:" in prompt
    assert "source_boundary_explanation" in prompt
    assert "No external packet supplied." in raw_prompt


def test_repair_prompt_exposes_public_contract_failures():
    case = next(case for case in _cases() if case.case_id == "held_tension_local_model_wedge")
    previous = render_raw_shadow(case)
    score = verify_probe(case, previous)
    prompt = build_repair_prompt(case, previous, score)

    assert "Verifier failures:" in prompt
    assert "Held Tension:" in prompt
    assert "Side A:" in prompt
    assert "Side B:" in prompt
    assert "Allowed synthesis:" in prompt
    assert "Forbidden collapse:" in prompt
    assert "Trace preview:" in prompt
    assert "do not force a winner" in prompt


def test_compressed_prompt_uses_tiny_render_contract():
    case = next(case for case in _cases() if case.case_id == "held_tension_archive_not_memory")
    prompt = build_compressed_model_prompt(case)

    assert "Compressed render contract" in prompt
    assert "Task:" in prompt
    assert "Side A:" in prompt
    assert "Side B:" in prompt
    assert "Must say:" in prompt
    assert "Must not say:" in prompt
    assert "Required format:" in prompt
    assert "Tension Packet / Workspace Spine" not in prompt
    assert "GPT logs are useful archive evidence" in prompt
    assert "not confirmed memory" in prompt


def test_compressed_repair_prompt_sends_failure_delta():
    case = next(case for case in _cases() if case.case_id == "held_tension_archive_not_memory")
    previous = render_raw_shadow(case)
    score = verify_probe(case, previous)
    prompt = build_compressed_repair_prompt(case, previous, score)

    assert "Failure delta:" in prompt
    assert "You omitted required phrase: not confirmed memory" in prompt
    assert "You omitted held-tension marker: source boundary" in prompt
    assert "Verifier failures:" not in prompt
