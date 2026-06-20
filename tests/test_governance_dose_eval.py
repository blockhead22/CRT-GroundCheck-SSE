from labs.meaning_compression_lab.governance_dose_eval import (
    EvalCase,
    dose_context,
    profile_score,
    select_profile,
)
from labs.meaning_compression_lab.heldout_cases import HELDOUT_CASES
from labs.meaning_compression_lab.scaffold_eval import build_meaning_scaffold


def test_dose_ladder_increases_visible_governance_for_current_question():
    heldout = HELDOUT_CASES[0]
    scaffold = build_meaning_scaffold(heldout.scenario)
    records = [
        {
            "rank": index,
            "text": memory.text,
            "timestamp": memory.timestamp,
            "source": memory.channel,
            "kind": memory.kind,
            "authority": memory.authority,
            "slot": memory.slot,
            "value": memory.value,
            "prior_value": memory.prior_value,
        }
        for index, memory in enumerate(heldout.scenario.memories, start=1)
    ]

    _, dose1 = dose_context(
        dose=1, records=records, scaffold=scaffold, probe=heldout.probe
    )
    _, dose2 = dose_context(
        dose=2, records=records, scaffold=scaffold, probe=heldout.probe
    )
    _, dose3 = dose_context(
        dose=3, records=records, scaffold=scaffold, probe=heldout.probe
    )
    _, dose4 = dose_context(
        dose=4, records=records, scaffold=scaffold, probe=heldout.probe
    )

    assert "CURRENT name = Marcus" in dose1
    assert "AUTHORITY name" not in dose1
    assert "AUTHORITY name = confirmed" in dose2
    assert "HISTORY name" not in dose2
    assert "HISTORY name" in dose3
    assert "PREFERENCE preference.theme" in dose4


def test_profile_selection_uses_scores_and_ties_choose_lower_dose():
    aggregates = {
        1: {
            "case_count": 10, "contract": 9, "severe_failures": 0,
            "scope_failures": 1, "format_failures": 0,
        },
        2: {
            "case_count": 10, "contract": 10, "severe_failures": 0,
            "scope_failures": 0, "format_failures": 0,
        },
        3: {
            "case_count": 10, "contract": 10, "severe_failures": 0,
            "scope_failures": 0, "format_failures": 0,
        },
    }

    profile = select_profile(aggregates)

    assert profile_score(aggregates[2]) == profile_score(aggregates[3])
    assert profile["selected_dose"] == 2


def test_eval_case_profile_has_no_model_name_field():
    heldout = HELDOUT_CASES[0]
    case = EvalCase(heldout.scenario, heldout.probe, "validation")

    assert not hasattr(case, "model")
