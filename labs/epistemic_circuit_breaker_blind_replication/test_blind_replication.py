from __future__ import annotations

from collections import Counter
import hashlib
import json
from pathlib import Path

from labs.epistemic_circuit_breaker_blind_replication.blind_evaluator import (
    independent_decision,
    independent_safety,
)
from labs.epistemic_circuit_breaker_blind_replication.blind_pack_generator import (
    CASES_PER_CATEGORY,
    CATEGORIES,
    generate_pack,
)


ROOT = Path(__file__).resolve().parents[2]
TARGET = (
    ROOT
    / "labs"
    / "epistemic_circuit_breaker_lab"
    / "epistemic_circuit_breaker_lab.py"
)
FIRST_REVEAL_SEAL = (
    ROOT
    / "artifacts"
    / "epistemic-circuit-breaker-blind-replication"
    / "blind_manifest_seal_20260718.json"
)
FIRST_TARGET_SHA256 = (
    "2ffba478f33d3c831541fe883c217c89a51f4eb344a3cc3f07150dfabf202232"
)


def test_pack_shape_and_balance() -> None:
    pack = generate_pack()

    assert len(pack["cases"]) == 96
    assert Counter(case["category"] for case in pack["cases"]) == {
        category: CASES_PER_CATEGORY for category in CATEGORIES
    }
    assert Counter(
        case["blind_expectation"]["action"] for case in pack["cases"]
    ) == {"reject": 40, "accept": 24, "quarantine": 24, "hold": 8}


def test_all_analytical_expectations_match_independent_model() -> None:
    for case in generate_pack()["cases"]:
        actual = independent_decision(case)
        expected = case["blind_expectation"]
        assert actual["action"] == expected["action"]
        assert actual["reason"] == expected["reason_class"]


def test_dag_fanout_and_parallel_sign_hazard_are_distinct() -> None:
    cases = generate_pack()["cases"]
    fanout = next(case for case in cases if case["category"] == "broad_fanout")
    parallel = next(
        case for case in cases if case["category"] == "parallel_sign_cancellation"
    )

    fanout_state = independent_safety(fanout)
    parallel_state = independent_safety(parallel)
    assert fanout_state["spectral_radius"] == 0.0
    assert fanout_state["total_impact"] > 6.0
    assert parallel_state["spectral_radius"] >= 0.99


def test_first_reveal_seal_preserves_original_target_after_repair() -> None:
    sealed = json.loads(FIRST_REVEAL_SEAL.read_text(encoding="utf-8"))

    assert sealed["target_sha256"] == FIRST_TARGET_SHA256
    assert hashlib.sha256(TARGET.read_bytes()).hexdigest() != FIRST_TARGET_SHA256
