from pathlib import Path

from labs.meaning_compression_lab.attention_profile_eval import section_lock_prompt
from labs.meaning_compression_lab.local_router_cli import build_case, judge_trace, load_saved_run, run_cli_request
from labs.meaning_compression_lab.spiral_synthesis_eval import judge_answer, repair_prompt


def test_build_case_infers_grant_business_defaults():
    case = build_case("Frame this as a grant direction for local CRT/Aether work.")

    assert case.name == "cli_grant_business"
    assert "CRT" in case.expected_receipts
    assert "measurable" in case.required_concepts
    assert "guaranteed" in case.forbidden_claims
    policy = case.spine["final_answer_policy"]
    assert "medical, clinical, therapeutic, or regulated-market claims" in policy["must_avoid"]
    assert "guaranteed outcomes or success claims" in policy["must_avoid"]


def test_build_case_infers_business_planning_defaults():
    case = build_case("With the camera gear I have, could I turn this into a small business if I applied myself?")

    assert case.name == "cli_business_planning"
    assert "camera gear" in case.expected_receipts
    assert "small business" in case.expected_receipts
    assert "offer" in case.required_concepts
    assert "full-time income" in case.forbidden_claims
    policy = case.spine["final_answer_policy"]
    assert "bounded offer and pricing language" in policy["must_use"]
    assert "guaranteed income or full-time replacement claims" in policy["must_avoid"]


def test_build_case_respects_overrides():
    case = build_case(
        "Explain this architecture.",
        task_type="architecture_synthesis",
        anchors=("Mirus", "Holden"),
        concepts=("spine",),
    )

    assert case.name == "cli_architecture_synthesis"
    assert case.expected_receipts == ("Mirus", "Holden")
    assert case.required_concepts == ("spine",)


def test_section_lock_prompt_includes_final_answer_policy():
    case = build_case("Frame this as a grant direction for local CRT/Aether work.")

    prompt = section_lock_prompt(case)

    assert "Final-answer policy" in prompt
    assert "Do not expose internal process language" in prompt
    assert "medical, clinical, therapeutic, or regulated-market claims" in prompt
    assert "Do not quote them, use them as headings" in prompt


def test_repair_prompt_includes_final_answer_policy():
    case = build_case("Frame this as a grant direction for local CRT/Aether work.")
    judgment = {
        "receipt_hits": [],
        "concept_hits": [],
    }

    prompt = repair_prompt(case, "Draft mentions a guaranteed medical product.", judgment)

    assert "Final-answer policy" in prompt
    assert "Do not expose internal process language" in prompt
    assert "guaranteed outcomes or success claims" in prompt
    assert "do not use guarantee wording" in prompt
    assert "not a guarantee" not in prompt
    assert "Do not quote them, use them as headings" in prompt


def test_personal_synthesis_policy_requires_receipts_before_identity_claims():
    case = build_case("Who am I embodying as a founder?", task_type="personal_synthesis")

    policy = case.spine["final_answer_policy"]

    assert "concrete receipts before identity claims" in policy["must_use"]
    assert "a request for two or three concrete receipts when only generic receipt anchors are available" in policy["must_use"]
    assert "generic founder comparison without evidence" in policy["must_avoid"]
    assert "naming specific founders or comparing the user to founders when concrete anchors are missing" in policy["must_avoid"]
    assert "identity claims when the only anchors are receipts or evidence" in policy["must_avoid"]
    assert "packet is not enough to compare the user to founders" in policy["rewrite_rule"]


def test_architecture_process_policy_blocks_banned_limit_phrasing():
    case = build_case("Explain fallback logging in parallel.", task_type="architecture_process")

    policy = case.spine["final_answer_policy"]

    assert "declaring that no code is needed" in policy["must_avoid"]
    assert "guaranteed or non-guaranteed wording" in policy["must_avoid"]


def test_architecture_process_allows_warning_about_no_code_needed_claim():
    case = build_case("Explain fallback logging in parallel.", task_type="architecture_process")
    answer = (
        "Receipts: roadmap, architecture, and risk. "
        "Pattern: the mechanism is a sequence with verification before implementation. "
        "Limits: avoid a No Code Needed Claim; this is a bounded process constraint, not a production-ready result. "
        "Next Useful Move: inspect the fallback log and choose the smallest testable implementation step."
    )

    judgment = judge_answer(answer, case)

    assert "no code needed" not in judgment["forbidden_hits"]


def test_personal_synthesis_blocks_identity_claim_without_concrete_receipts():
    case = build_case("Who am I embodying as a founder?", task_type="personal_synthesis")
    answer = (
        "Receipts: the evidence says you are becoming a resilient founder and builder. "
        "Pattern: you are embodying a grounded entrepreneurial identity. "
        "Limits: this is not finished or guaranteed. "
        "Next Useful Move: keep going with the work."
    )

    judgment = judge_answer(answer, case)

    assert judgment["passed"] is False
    assert "identity_claim_without_concrete_receipts" in judgment["weirdness_hits"]


def test_personal_synthesis_allows_receipt_request_when_context_is_missing():
    case = build_case("Who am I embodying as a founder?", task_type="personal_synthesis")
    answer = (
        "Receipts: I would need concrete receipts or examples before making an identity claim. "
        "Pattern: the useful move is to separate evidence from flattering founder language. "
        "Limits: without specifics, this is not finished and not guaranteed. "
        "Next Useful Move: give me two or three recent facts, then I can make the claim bounded."
    )

    judgment = judge_answer(answer, case)

    assert "identity_claim_without_concrete_receipts" not in judgment["weirdness_hits"]


def test_personal_synthesis_allows_grounded_identity_claim_with_concrete_receipts():
    case = build_case(
        "What pattern do you see in me right now?",
        task_type="personal_synthesis",
        anchors=("Road America", "12,730", "marigolds", "Aeteros"),
        concepts=("receipts", "pattern", "not finished"),
    )
    answer = (
        "Receipts: Road America, 12,730 steps, marigolds, and Aeteros are the concrete facts. "
        "Pattern: you are becoming someone who returns to the work after heavy days. "
        "Limits: that is an identity claim bounded by evidence, not proof and not finished. "
        "Next Useful Move: keep the next step small enough that it stays real."
    )

    judgment = judge_answer(answer, case)

    assert "insufficient_personal_receipts" not in judgment["weirdness_hits"]


def test_run_cli_request_accepts_injected_call_ollama(monkeypatch):
    def fake_call_ollama(prompt: str, model: str, timeout: int) -> str:
        return (
            "Receipts: local CRT and Aether. Pattern: a measurable low-cost business direction. "
            "Limits: this is not guaranteed and not frontier capability. "
            "Next Useful Move: use a verifier and evals to compare raw and scaffolded responses."
        )

    monkeypatch.setattr(
        "labs.meaning_compression_lab.local_router_cli.call_ollama",
        fake_call_ollama,
    )

    out = run_cli_request(
        "Frame this as a grant/business direction for local CRT/Aether.",
        write_result=False,
    )

    assert out["route"]["task_type"] == "grant_business"
    assert out["judgment"]["passed"] is True
    assert out["answer"].startswith("Receipts:")
    assert out["trace"]["trace_schema"] == "aether.local_router.trace.v0"
    assert out["trace_judgment"]["passed"] is True
    assert out["trace"]["raw_chain_of_thought_stored"] is False


def test_run_cli_request_writes_separate_trace_file(tmp_path, monkeypatch):
    def fake_call_ollama(prompt: str, model: str, timeout: int) -> str:
        return (
            "Receipts: local CRT and Aether. Pattern: measurable low-cost business support. "
            "Limits: this is not guaranteed and not frontier capability. "
            "Next Useful Move: use a verifier to compare raw and scaffolded responses."
        )

    monkeypatch.setattr("labs.meaning_compression_lab.local_router_cli.OUT_DIR", tmp_path)
    monkeypatch.setattr("labs.meaning_compression_lab.local_router_cli.TRACE_DIR", tmp_path / "traces")
    monkeypatch.setattr(
        "labs.meaning_compression_lab.local_router_cli.call_ollama",
        fake_call_ollama,
    )

    out = run_cli_request(
        "Frame this as a grant/business direction for local CRT/Aether.",
        write_result=True,
    )

    assert (tmp_path / "traces").exists()
    assert out["result_path"]
    assert out["trace_path"]
    assert out["trace_path"].endswith(".json")


def test_load_saved_run_reloads_external_trace(tmp_path, monkeypatch):
    def fake_call_ollama(prompt: str, model: str, timeout: int) -> str:
        return (
            "Receipts: local CRT and Aether. Pattern: measurable low-cost business support. "
            "Limits: this is not guaranteed and not frontier capability. "
            "Next Useful Move: use a verifier to compare raw and scaffolded responses."
        )

    monkeypatch.setattr("labs.meaning_compression_lab.local_router_cli.OUT_DIR", tmp_path)
    monkeypatch.setattr("labs.meaning_compression_lab.local_router_cli.TRACE_DIR", tmp_path / "traces")
    monkeypatch.setattr(
        "labs.meaning_compression_lab.local_router_cli.call_ollama",
        fake_call_ollama,
    )

    saved = run_cli_request(
        "Frame this as a grant/business direction for local CRT/Aether.",
        write_result=True,
    )
    loaded = load_saved_run(Path(saved["result_path"]))

    assert loaded["trace_source"] == "external"
    assert loaded["trace_file_exists"] is True
    assert loaded["consistent"] is True
    assert loaded["trace_judgment"]["passed"] is True
    assert loaded["trace"]["raw_chain_of_thought_stored"] is False


def test_judge_trace_blocks_raw_chain_of_thought_storage():
    trace = {
        "trace_schema": "aether.local_router.trace.v0",
        "turn_id": "t",
        "conversation_id": "c",
        "timestamp": 1,
        "user_request_summary": "x",
        "task_type": "grant_business",
        "route_selected": {"task_type": "grant_business", "model": "m", "profile": "p"},
        "model_selected": "m",
        "scaffold_profile": "p",
        "mirus_packet_summary": {},
        "evidence_anchors": [],
        "disallowed_inferences": [],
        "draft_quality_score": 0.9,
        "verifier_flags": {
            "passed": True,
            "truncated": False,
            "leakage_hits": [],
            "weirdness_hits": [],
            "forbidden_hits": [],
            "receipt_hits": [],
            "concept_hits": [],
        },
        "repair_attempts": 0,
        "fallback_used": False,
        "final_confidence": "high",
        "contradiction_notes": [],
        "learning_candidates": [],
        "promotion_status": "none",
        "raw_chain_of_thought_stored": True,
    }

    judgment = judge_trace(trace)

    assert judgment["passed"] is False
    assert judgment["no_raw_chain_of_thought"] is False


def test_grant_cli_case_blocks_network_router_drift():
    case = build_case("Frame the local router as a grant direction.", task_type="grant_business")
    answer = (
        "Receipts: local CRT and Aether network router. Pattern: improve network performance "
        "and secure file transfer. Limits: not guaranteed. Next Useful Move: measure packet routing."
    )

    judgment = judge_answer(answer, case)

    assert judgment["passed"] is False
    assert "network_router_drift" in judgment["weirdness_hits"]


def test_grant_cli_case_blocks_unsupported_numeric_claim():
    case = build_case("Frame the local router as a grant direction.", task_type="grant_business")
    answer = (
        "Receipts: local CRT and Aether AI request router. Pattern: low-cost business support. "
        "It can reduce deployment time by up to 50%. Limits: not guaranteed. "
        "Next Useful Move: measure it with a verifier."
    )

    judgment = judge_answer(answer, case)

    assert judgment["passed"] is False
    assert "unsupported_numeric_claim" in judgment["weirdness_hits"]


def test_grant_cli_allows_negated_guarantee_noun():
    case = build_case("Frame the local router as a grant direction.", task_type="grant_business")
    answer = (
        "Receipts: local CRT and Aether AI request router. Pattern: measurable low-cost business support. "
        "Limits: this is not a guarantee and not frontier capability. "
        "Next Useful Move: use a verifier to compare raw and scaffolded outputs."
    )

    judgment = judge_answer(answer, case)

    assert "guaranteed" not in judgment["forbidden_hits"]


def test_architecture_cli_blocks_acronym_drift():
    case = build_case("Explain the architecture.", task_type="architecture_synthesis")
    answer = (
        "Receipts: Mirus, Holden, SSE, and CRT. Pattern: Holden's research uses "
        "Structured System Evaluation and the Critical Review Tool. Limits: not proof. "
        "Next Useful Move: use a verifier."
    )

    judgment = judge_answer(answer, case)

    assert judgment["passed"] is False
    assert "misnamed_sse" in judgment["weirdness_hits"]
    assert "misnamed_crt_tool" in judgment["weirdness_hits"]


def test_architecture_allows_subconscious_memory_without_conscious_overclaim():
    case = build_case("Explain CRT and sub conscious memory encoding.", task_type="architecture_synthesis")
    answer = (
        "Receipts: Mirus, Holden, SSE, and CRT. Pattern: the mechanism is a semantic spine "
        "with a verifier checking overclaim risk. Limits: sub-conscious memory encoding here is "
        "a design phrase, not proof and not frontier-level capability. "
        "Next Useful Move: define the encoding path and test it."
    )

    judgment = judge_answer(answer, case)

    assert "conscious" not in judgment["forbidden_hits"]


def test_architecture_blocks_direct_conscious_overclaim():
    case = build_case("Explain CRT.", task_type="architecture_synthesis")
    answer = (
        "Receipts: Mirus, Holden, SSE, and CRT. Pattern: the mechanism is a semantic spine "
        "with a verifier, but the system is conscious and can avoid overclaim risk. "
        "Limits: this is not proof. Next Useful Move: test it."
    )

    judgment = judge_answer(answer, case)

    assert "conscious" in judgment["forbidden_hits"]
