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


def test_fact_slots_name_stops_at_but_conjunction() -> None:
    """Test that 'My name is nick but you said sarah' extracts 'nick', not 'nick but you'."""
    facts = extract_fact_slots("My name is nick but you said it sarah?")
    assert facts.get("name") is not None
    assert facts["name"].value.lower() == "nick"
    assert "but" not in facts["name"].value.lower()


def test_fact_slots_name_stops_at_and_conjunction() -> None:
    """Test that 'I am Nick and I work at Google' extracts 'Nick', not 'Nick and I'."""
    facts = extract_fact_slots("I am Nick and I work at Google")
    assert facts.get("name") is not None
    assert facts["name"].value.lower() == "nick"
    assert "and" not in facts["name"].value.lower()


def test_fact_slots_name_preserves_multiword_names() -> None:
    """Test that legitimate multi-word names like 'Nick Block' are preserved."""
    facts = extract_fact_slots("My name is Nick Block")
    assert facts.get("name") is not None
    assert facts["name"].value == "Nick Block"


def test_fact_slots_name_stops_at_but_preserves_previous_words() -> None:
    """Test 'My name is Sarah but I prefer Sally' extracts 'Sarah', not 'Sarah but I'."""
    facts = extract_fact_slots("My name is Sarah but I prefer Sally")
    assert facts.get("name") is not None
    assert facts["name"].value.lower() == "sarah"
    assert "but" not in facts["name"].value.lower()
