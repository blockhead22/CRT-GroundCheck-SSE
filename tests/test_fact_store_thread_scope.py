from pathlib import Path

from personal_agent.fact_store import FactStore


def test_fact_store_user_facts_are_thread_scoped(tmp_path: Path) -> None:
    db_path = tmp_path / "facts.db"
    store = FactStore(str(db_path))

    store.process_input("My name is Nick", thread_id="thread_a")
    store.process_input("My name is Mike", thread_id="thread_b")

    assert store.answer("What's my name?", thread_id="thread_a") == "Nick"
    assert store.answer("What's my name?", thread_id="thread_b") == "Mike"

    facts_a = store.get_all_facts(thread_id="thread_a")
    facts_b = store.get_all_facts(thread_id="thread_b")

    assert facts_a["user.name"]["value"] == "Nick"
    assert facts_b["user.name"]["value"] == "Mike"
    assert facts_a["user.name"]["thread_id"] == "thread_a"
    assert facts_b["user.name"]["thread_id"] == "thread_b"


def test_fact_store_llm_claim_disclosures_are_thread_scoped(tmp_path: Path) -> None:
    db_path = tmp_path / "facts.db"
    store = FactStore(str(db_path))

    first = store.process_llm_response("Your name is Mike.", thread_id="thread_a")
    second = store.process_llm_response("Your name is Nick.", thread_id="thread_b")
    third = store.process_llm_response("Your name is Alex.", thread_id="thread_a")

    assert first["disclosures"] == []
    assert second["disclosures"] == []
    assert len(third["disclosures"]) == 1
    assert "Mike" in third["disclosures"][0]
    assert "Alex" in third["disclosures"][0]

    claims_a = store.get_all_llm_claims(thread_id="thread_a")
    claims_b = store.get_all_llm_claims(thread_id="thread_b")

    assert claims_a["user.name"]["value"] == "Alex"
    assert claims_b["user.name"]["value"] == "Nick"
