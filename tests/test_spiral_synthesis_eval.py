from labs.meaning_compression_lab.local_router_cli import build_case
from labs.meaning_compression_lab.spiral_synthesis_eval import CASES, judge_answer, run


def test_judge_rewards_grounded_bounded_spiral():
    case = CASES[0]
    answer = (
        "The pattern is not that you are fixed or finished. The receipts are Road America, "
        "12,730 steps, marigolds, water-weight worry, and Aeteros still being pulled into a "
        "working structure. Those receipts support a bounded claim: you are acting like someone "
        "with return points. That matters because the work is concrete, but it does not prove the "
        "whole arc is solved. The useful identity statement is smaller and sturdier: momentum is "
        "showing up again, and the system should not turn that into pressure. The anchor is to keep "
        "the next move close enough to touch."
    )

    judgment = judge_answer(answer, case)

    assert judgment["passed"] is True
    assert judgment["forbidden_hits"] == []
    assert "Road America" in judgment["receipt_hits"]
    assert "pattern" in judgment["concept_hits"]


def test_judge_blocks_forbidden_overclaim():
    case = CASES[0]
    answer = (
        "The pattern is that you are fixed, cured, guaranteed, superior, and done. "
        "Road America and Aeteros prove it."
    )

    judgment = judge_answer(answer, case)

    assert judgment["passed"] is False
    assert set(judgment["forbidden_hits"]) >= {"fixed", "cured", "guaranteed"}


def test_judge_blocks_truncated_answer_even_with_receipts():
    case = CASES[0]
    answer = (
        "The pattern uses receipts like Road America, 12,730 steps, marigolds, water, "
        "and Aeteros. It is not finished and not guaranteed, but"
    )

    judgment = judge_answer(answer, case)

    assert judgment["passed"] is False
    assert judgment["truncated"] is True


def test_judge_blocks_symbolic_misuse_of_receipts():
    case = CASES[0]
    answer = (
        "The receipts are Road America, 12,730 units, marigolds, water, and Aeteros. "
        "The pattern is not finished. Marigolds and water are symbolic data points that "
        "hint at environmental factors rather than concrete lived receipts. This is not "
        "proof or a guarantee. The next useful move is to keep the claim bounded and grounded."
    )

    judgment = judge_answer(answer, case)

    assert judgment["passed"] is False
    assert judgment["weirdness_hits"]


def test_judge_blocks_roleplay_leakage():
    case = CASES[0]
    answer = (
        "Holden's voice fills the room. The receipts are Road America, 12,730 steps, "
        "marigolds, water, and Aeteros. The pattern is not finished and not guaranteed. "
        "The answer is grounded in evidence and cautions against pressure. The final anchor "
        "is to keep the next concrete move small."
    )

    judgment = judge_answer(answer, case)

    assert judgment["passed"] is False
    assert "roleplay_holden" in judgment["leakage_hits"]


def test_judge_allows_negated_network_router_phrase():
    case = build_case(
        "Frame Aeteros and Aether as a practical grant direction.",
        task_type="grant_business",
        anchors=("Aeteros", "Aether", "CRT"),
        concepts=("business", "measurable", "AI request router"),
    )
    answer = (
        "Receipts: Aeteros, Aether, and CRT define the local project. "
        "Pattern: the AI request router is not a network router; it selects a local policy, "
        "a scaffold, and a repair path. Limits: this is not finished, not proof, and not a "
        "guarantee. Next Useful Move: measure whether the governed route improves small-business "
        "draft quality without claiming frontier performance."
    )

    judgment = judge_answer(answer, case)

    assert judgment["weirdness_hits"] == []


def test_personal_receipt_gate_allows_explicit_receipt_request_without_identity_synthesis():
    case = build_case(
        "Say whether this prompt alone supports a grounded identity read.",
        task_type="personal_synthesis",
        anchors=("receipts", "evidence"),
        concepts=("pattern", "limits", "next useful move"),
    )
    answer = (
        "Receipts: this packet alone does not provide enough concrete evidence for a grounded "
        "identity read. Pattern: the safe move is to separate the request from unsupported "
        "identity synthesis. Limits: without specific recent receipts, no identity claim can be "
        "made from the current packet alone. Next Useful Move: provide two or three concrete "
        "receipts or examples, and then the pattern can be evaluated in a bounded way."
    )

    judgment = judge_answer(answer, case)

    assert judgment["passed"] is True
    assert "insufficient_personal_receipts" not in judgment["weirdness_hits"]
    assert "identity_claim_without_concrete_receipts" not in judgment["weirdness_hits"]


def test_personal_receipt_gate_still_blocks_generic_founder_drift_with_receipt_request():
    case = build_case(
        "Tell me what can and cannot be inferred before comparing me to founders.",
        task_type="personal_synthesis",
        anchors=("receipts", "evidence"),
        concepts=("pattern", "limits", "next useful move"),
    )
    answer = (
        "Receipts: this packet does not provide enough concrete evidence for a founder comparison. "
        "Pattern: generic founder journeys often involve resource constraints and skepticism, so "
        "that is the broader entrepreneurial pattern. Limits: this is bounded and not finished. "
        "Next Useful Move: provide two or three concrete receipts or examples before any identity "
        "claim is made."
    )

    judgment = judge_answer(answer, case)

    assert judgment["passed"] is False
    assert "generic_founder_comparison" in judgment["weirdness_hits"]


def test_judge_treats_limitations_as_limits_concept_and_bounded_language():
    case = build_case(
        "Earlier notes say Shopify, but the correction says the store uses a custom backend.",
        task_type="exact_memory",
        anchors=("custom backend", "Shopify", "stale"),
        concepts=("current", "limits"),
    )
    answer = (
        "Current: the custom backend should be treated as current, while Shopify is stale "
        "prior context. Pattern: answer from the latest correction instead of the older note. "
        "Limitations: this cannot be guaranteed without further verification, so do not overclaim "
        "exclusive usage. Next Useful Move: keep custom backend as current and Shopify as stale "
        "until a newer receipt contradicts it."
    )

    judgment = judge_answer(answer, case)

    assert judgment["passed"] is True
    assert "limits" in judgment["concept_hits"]
    assert judgment["has_limit_language"] is True


def test_judge_treats_applied_effort_as_applied_myself_anchor():
    case = build_case(
        "Could camera gear become a small business if I applied myself?",
        task_type="business_planning",
        anchors=("camera gear", "applied myself", "small business"),
        concepts=("offer", "pricing", "risk", "next useful move"),
    )
    answer = (
        "Receipts: camera gear, the right application of effort, and a small business test. "
        "Pattern: start with one offer instead of a vague dream. Limits: pricing and risk need "
        "proof before any full-time claim. Next Useful Move: practice with one paid package."
    )

    judgment = judge_answer(answer, case)

    assert "applied myself" in judgment["receipt_hits"]
    assert judgment["passed"] is True


def test_run_accepts_injected_runner_without_ollama():
    def fake_runner(prompt: str, model: str, timeout: int) -> str:
        if "personal_rebuild_spiral" in prompt or "Road America" in prompt:
            return (
                "The pattern is not finished. Receipts: Road America, 12,730 steps, marigolds, "
                "water-weight worry, and Aeteros. The bounded pattern is that the evidence points "
                "to continuity, not completion. That answer should stay grounded because the win is "
                "real but should not become pressure. The final anchor is simple: keep choosing the "
                "next concrete return point."
            )
        return (
            "The real mechanism is belief state first, raw output second. Mirus handles belief and "
            "trust, SSE builds the spine, CRT catches overclaim and drift, Holden renders the answer, "
            "and a verifier checks the claims. This does not prove a local model is frontier-level; "
            "it shows the scaffold can make raw local chat more coherent."
        )

    out = run(model="fake", write_results=False, runner=fake_runner)

    assert out["aggregate"]["scaffold_pass_count"] >= 1
    assert out["case_count"] == len(CASES)
    assert all("raw_answer" in row and "scaffold_answer" in row for row in out["rows"])
