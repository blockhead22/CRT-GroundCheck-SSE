from labs.meaning_compression_lab.heldout_cases import HELDOUT_CASES
from labs.meaning_compression_lab.run_lab import scenario_pack


def test_heldout_pack_expands_total_to_twenty_five_without_touching_frozen_pack():
    frozen = scenario_pack(include_adversarial=True, include_hardening=True)

    assert len(frozen) == 19
    assert len(HELDOUT_CASES) == 6
    assert len(frozen) + len(HELDOUT_CASES) == 25
    assert not ({case.scenario.name for case in HELDOUT_CASES} & {case.name for case in frozen})


def test_every_heldout_case_exercises_top_k_retrieval_and_declares_evidence():
    for case in HELDOUT_CASES:
        assert len(case.scenario.memories) > 4
        assert case.required_evidence
        assert case.probe.expected_contains or case.probe.expected_behavior != "answer"
