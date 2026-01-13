from __future__ import annotations


from personal_agent.fact_slots import extract_fact_slots


def test_fact_slots_name_avoids_im_trying_false_positive() -> None:
    facts = extract_fact_slots("You are the ai im trying to build")
    assert "name" not in facts


def test_fact_slots_name_accepts_lowercase_name() -> None:
    facts = extract_fact_slots("my name is nick")
    assert facts.get("name") is not None
    assert facts["name"].normalized == "nick"


def test_fact_slots_name_accepts_call_me_pattern() -> None:
    facts = extract_fact_slots("Call me Nick")
    assert facts.get("name") is not None
    assert facts["name"].normalized == "nick"


def test_fact_slots_name_accepts_short_correction_pattern() -> None:
    facts = extract_fact_slots("Nick not Ben")
    assert facts.get("name") is not None
    assert facts["name"].normalized == "nick"


def test_fact_slots_favorite_color_extracts_value() -> None:
    facts = extract_fact_slots("My favorite color is orange.")
    assert facts.get("favorite_color") is not None
    assert facts["favorite_color"].normalized == "orange"


def test_fact_slots_favourite_colour_variant_extracts_value() -> None:
    facts = extract_fact_slots("My favourite colour is light blue!")
    assert facts.get("favorite_color") is not None
    assert facts["favorite_color"].normalized == "light blue"
