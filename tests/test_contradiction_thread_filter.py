from pathlib import Path

from personal_agent.crt_ledger import ContradictionLedger


def test_open_contradictions_are_thread_scoped_and_hide_profile_updates(tmp_path: Path) -> None:
    ledger = ContradictionLedger(db_path=str(tmp_path / "ledger.db"))

    thread_a = ledger.record_contradiction(
        old_memory_id="a_old",
        new_memory_id="a_new",
        drift_mean=0.7,
        confidence_delta=0.1,
        query="I work at Umbrella Corp.",
        summary="employer conflict A",
        old_text="I work at Weyland Corp.",
        new_text="I work at Umbrella Corp.",
        thread_id="thread_a",
    )
    thread_b = ledger.record_contradiction(
        old_memory_id="b_old",
        new_memory_id="b_new",
        drift_mean=0.7,
        confidence_delta=0.1,
        query="I live in Seattle.",
        summary="location conflict B",
        old_text="I live in Austin.",
        new_text="I live in Seattle.",
        thread_id="thread_b",
    )
    profile_update = ledger.record_contradiction(
        old_memory_id="profile_name_old",
        new_memory_id="profile_name_new",
        drift_mean=0.8,
        confidence_delta=0.0,
        summary="Profile update: name changed from 'Sarah' to 'Nick'",
        old_text="FACT: name = Sarah",
        new_text="FACT: name = Nick",
        contradiction_type="profile_update",
        thread_id="thread_a",
    )

    open_a = ledger.get_open_contradictions(limit=20, thread_id="thread_a")
    open_b = ledger.get_open_contradictions(limit=20, thread_id="thread_b")
    all_a = ledger.get_all_contradictions(limit=20, thread_id="thread_a")

    open_a_ids = {c.ledger_id for c in open_a}
    open_b_ids = {c.ledger_id for c in open_b}
    all_a_ids = {c.ledger_id for c in all_a}

    assert thread_a.ledger_id in open_a_ids
    assert thread_b.ledger_id not in open_a_ids
    assert profile_update.ledger_id not in open_a_ids

    assert thread_b.ledger_id in open_b_ids
    assert thread_a.ledger_id not in open_b_ids

    assert profile_update.ledger_id in all_a_ids
