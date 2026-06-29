from labs.meaning_compression_lab.attention_profile_eval import (
    CASES_WITH_GRANT,
    PROFILE_BUILDERS,
    run_profile,
)


def test_profile_builders_cover_expected_profiles():
    assert set(PROFILE_BUILDERS) == {"raw", "semantic_spine", "mirus_holden", "section_lock"}
    assert any(case.name == "grant_business_framing" for case in CASES_WITH_GRANT)


def test_run_profile_accepts_injected_runner_without_ollama():
    def fake_runner(prompt: str, model: str, timeout: int) -> str:
        if "grant" in prompt.lower() or "RTX 3060" in prompt:
            return (
                "Receipts: RTX 3060, RBT-1, Vault, CRT, and local deployment. "
                "The measurable claim is low-cost privacy-preserving business support with a verifier. "
                "This is not guaranteed and not frontier capability. The useful business fit is a "
                "small R&D prototype for creative-production workflows."
            )
        if "Road America" in prompt:
            return (
                "The receipts are Road America, 12,730 steps, marigolds, water concern, and Aeteros. "
                "The pattern is momentum, not finished work. This is not proof or a guarantee. "
                "The next useful move is to keep the claim bounded."
            )
        return (
            "Mirus owns belief, Holden renders speech, SSE holds the spine, CRT catches overclaim, "
            "and the verifier checks raw claims. This is not proof of frontier capability."
        )

    out = run_profile(model="fake", timeout=1, write_results=False, runner=fake_runner)

    assert out["case_count"] == len(CASES_WITH_GRANT)
    assert out["aggregate"]["mirus_holden"]["pass_count"] >= 1
    assert all(len(row["profiles"]) == len(PROFILE_BUILDERS) for row in out["rows"])
