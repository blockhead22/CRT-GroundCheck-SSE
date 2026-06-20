from labs.meaning_compression_lab.inferred_bounded_fetch_eval import infer_case
from labs.meaning_compression_lab.untouched_fetch_cases import UNTOUCHED_FETCH_CASES


def test_inferred_fetch_cases_resolve_or_safely_block_without_wrong_slot():
    resolved = 0
    blocked = 0
    for case in UNTOUCHED_FETCH_CASES:
        inference = infer_case(case)["inference"]
        if inference.status == "resolved":
            resolved += 1
            assert inference.requested_slots == (case.requested_slot,)
        else:
            blocked += 1
            assert inference.requested_slots == ()

    assert resolved == 5
    assert blocked == 1
