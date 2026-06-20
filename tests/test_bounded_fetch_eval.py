from pathlib import Path

import pytest

from labs.meaning_compression_lab.bounded_fetch_eval import (
    FROZEN_PROFILE_SHA256,
    evidence_sufficiency,
    fetch_requested_slot,
    load_frozen_profiles,
    merge_records,
)
from labs.meaning_compression_lab.run_lab import canonical_meaning_state
from labs.meaning_compression_lab.untouched_fetch_cases import UNTOUCHED_FETCH_CASES


def test_frozen_profile_hash_is_enforced(tmp_path: Path):
    path = tmp_path / "profiles.json"
    path.write_text("{}", encoding="utf-8")

    with pytest.raises(RuntimeError, match="profile artifact changed"):
        load_frozen_profiles(path)

    assert len(FROZEN_PROFILE_SHA256) == 64


def test_current_case_requests_only_declared_slot_when_initial_state_is_missing():
    case = UNTOUCHED_FETCH_CASES[0]
    state = canonical_meaning_state(case.scenario.memories[:2])

    result = evidence_sufficiency(case, state)

    assert result == {
        "sufficient": False,
        "requested_slots": ["name"],
        "reason_code": "missing_confirmed_current_value",
    }


def test_slot_fetch_returns_only_requested_slot_and_is_bounded():
    case = UNTOUCHED_FETCH_CASES[2]

    rows = fetch_requested_slot(case, "camera_system", k=4)

    assert rows
    assert len(rows) <= 4
    assert all(row["slot"] == "camera_system" for row in rows)


def test_merge_deduplicates_initial_and_fetched_evidence():
    row = {"text": "same", "timestamp": 1, "slot": "name"}

    merged = merge_records([row], [row])

    assert merged == [row]
