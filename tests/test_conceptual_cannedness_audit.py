from labs.meaning_compression_lab.conceptual_cannedness_audit import (
    audit_cases,
    run_audit,
)


def test_conceptual_cannedness_audit_classifies_current_routes():
    result = run_audit()

    assert result["case_count"] == 9
    assert result["counts"] == {
        "safe_deterministic": 2,
        "governed_synthesis": 4,
        "deterministic_watch": 3,
    }
    assert result["next_upgrade_candidates"] == [
        "aether_purpose",
        "system_theory",
        "project_purpose",
    ]


def test_meaning_value_is_marked_as_governed_synthesis():
    cases = {case.route_id: case for case in audit_cases()}

    assert cases["meaning_value"].status == "governed_synthesis"
    assert "formula card" in cases["meaning_value"].reason
    assert cases["over_reservation_pressure"].status == "governed_synthesis"
    assert cases["exact_memory_lookup"].status == "safe_deterministic"
    assert cases["aether_purpose"].status == "deterministic_watch"
