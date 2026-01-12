from __future__ import annotations


from personal_agent.fact_slots import extract_fact_slots


def test_fact_slots_name_avoids_im_trying_false_positive() -> None:
    facts = extract_fact_slots("You are the ai im trying to build")
    assert "name" not in facts


def test_fact_slots_name_accepts_lowercase_name() -> None:
    facts = extract_fact_slots("my name is nick")
    assert facts.get("name") is not None
    assert facts["name"].normalized == "nick"
