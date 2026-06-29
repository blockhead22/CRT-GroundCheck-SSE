from labs.meaning_compression_lab.attention_profile_eval import CASES_WITH_GRANT
from labs.meaning_compression_lab.local_router_eval import (
    classify_request,
    route_for_task,
    run_router_eval,
)


def test_classify_request_maps_current_cases():
    by_name = {case.name: case for case in CASES_WITH_GRANT}

    assert classify_request(by_name["personal_rebuild_spiral"]) == "personal_synthesis"
    assert classify_request(by_name["local_model_thinking_architecture"]) == "architecture_synthesis"
    assert classify_request(by_name["grant_business_framing"]) == "grant_business"


def test_route_policy_matches_current_lab_findings():
    assert route_for_task("personal_synthesis").profile == "section_lock"
    assert route_for_task("architecture_synthesis").profile == "semantic_spine"
    assert route_for_task("grant_business").profile == "section_lock"
    assert route_for_task("exact_memory").model == "qwen2.5:7b-instruct"


def test_router_eval_accepts_injected_runner_without_ollama():
    def fake_runner(prompt: str, model: str, timeout: int) -> str:
        if "RTX 3060" in prompt or "grant" in prompt.lower():
            return (
                "Receipts: RTX 3060, RBT-1, Vault, CRT, and local deployment. "
                "Pattern: a low-cost privacy-preserving business R&D prototype. "
                "Limits: this is measurable through evals and not guaranteed. "
                "Next Useful Move: use a verifier to compare raw and scaffolded outputs."
            )
        if "Road America" in prompt:
            return (
                "Receipts: Road America, 12,730 steps, marigolds, water concern, and Aeteros. "
                "Pattern: momentum with fragility, not finished work. "
                "Limits: this is not proof and not a guarantee. "
                "Next Useful Move: keep the next grounded action small."
            )
        return (
            "The real mechanism is Mirus belief state, Holden rendering, SSE spine control, "
            "CRT overclaim gates, and a verifier checking raw claims. This is not proof of "
            "frontier capability, but it is a bounded local-model scaffold."
        )

    out = run_router_eval(write_results=False, runner=fake_runner)

    assert out["case_count"] == len(CASES_WITH_GRANT)
    assert out["aggregate"]["pass_count"] >= 2
    assert all("route" in row and "judgment" in row for row in out["rows"])


def test_router_can_use_fallback_when_first_route_is_worse():
    calls = []

    def fake_runner(prompt: str, model: str, timeout: int) -> str:
        calls.append(prompt)
        if "Answer with four compact titled sections" in prompt or "Draft:\nToo short." in prompt:
            return "Too short."
        return (
            "The CRT/Aether local scaffold uses RTX 3060, RBT-1, Vault, CRT, and local deployment. "
            "The measurable business claim is low-cost privacy-preserving workflow support with a verifier. "
            "This is not guaranteed and not frontier capability. The next useful move is to compare raw "
            "and scaffolded outputs through evals."
        )

    out = run_router_eval(write_results=False, runner=fake_runner)
    grant_row = next(row for row in out["rows"] if row["case"] == "grant_business_framing")

    assert grant_row["fallback_used"] is True
    assert len(calls) >= 2
