from labs.meaning_compression_lab.local_router_cli import build_case, judge_trace, run_cli_request
from labs.meaning_compression_lab.spiral_synthesis_eval import judge_answer


def test_build_case_infers_grant_business_defaults():
    case = build_case("Frame this as a grant direction for local CRT/Aether work.")

    assert case.name == "cli_grant_business"
    assert "CRT" in case.expected_receipts
    assert "measurable" in case.required_concepts
    assert "guaranteed" in case.forbidden_claims


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
