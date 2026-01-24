"""
Test dynamic fact storage and extraction.

Tests that the system can:
1. Learn and store facts beyond the original 20 hardcoded slots
2. Automatically create new categories based on user input
3. Support "favorite X" pattern for unlimited favorites
4. Handle structured facts with dynamic slot names
"""

import pytest
from personal_agent.fact_slots import extract_fact_slots


def test_structured_fact_favorite_snack():
    """Test structured fact with new category: favorite_snack"""
    text = "FACT: favorite_snack = popcorn"
    facts = extract_fact_slots(text)
    
    assert "favorite_snack" in facts
    assert facts["favorite_snack"].value == "popcorn"
    assert facts["favorite_snack"].normalized == "popcorn"


def test_structured_fact_favorite_movie():
    """Test structured fact with new category: favorite_movie"""
    text = "FACT: favorite_movie = The Matrix"
    facts = extract_fact_slots(text)
    
    assert "favorite_movie" in facts
    assert facts["favorite_movie"].value == "The Matrix"


def test_structured_fact_my_custom():
    """Test structured fact with my_ prefix"""
    text = "FACT: my_hometown = Seattle"
    facts = extract_fact_slots(text)
    
    assert "my_hometown" in facts
    assert facts["my_hometown"].value == "Seattle"


def test_structured_fact_preference():
    """Test structured fact with _preference suffix"""
    text = "PREF: workspace_preference = quiet"
    facts = extract_fact_slots(text)
    
    assert "workspace_preference" in facts
    assert facts["workspace_preference"].value == "quiet"


def test_natural_language_favorite_snack():
    """Test natural language extraction: My favorite snack is..."""
    text = "My favorite snack is popcorn"
    facts = extract_fact_slots(text)
    
    assert "favorite_snack" in facts
    assert facts["favorite_snack"].value == "popcorn"


def test_natural_language_favorite_movie():
    """Test natural language extraction: My favorite movie is..."""
    text = "My favorite movie is The Matrix"
    facts = extract_fact_slots(text)
    
    assert "favorite_movie" in facts
    assert facts["favorite_movie"].value == "The Matrix"


def test_natural_language_favorite_book():
    """Test natural language extraction: My favourite book is..."""
    text = "My favourite book is 1984"
    facts = extract_fact_slots(text)
    
    assert "favorite_book" in facts
    assert facts["favorite_book"].value == "1984"


def test_natural_language_favorite_band():
    """Test natural language extraction: My favorite band is..."""
    text = "My favorite band is The Beatles"
    facts = extract_fact_slots(text)
    
    assert "favorite_band" in facts
    assert facts["favorite_band"].value == "The Beatles"


def test_multiple_dynamic_facts():
    """Test that multiple dynamic facts can be stored"""
    texts = [
        "FACT: favorite_snack = popcorn",
        "FACT: favorite_drink = coffee",
        "FACT: favorite_sport = basketball",
        "FACT: favorite_season = autumn",
    ]
    
    all_facts = {}
    for text in texts:
        facts = extract_fact_slots(text)
        all_facts.update(facts)
    
    assert len(all_facts) == 4
    assert "favorite_snack" in all_facts
    assert "favorite_drink" in all_facts
    assert "favorite_sport" in all_facts
    assert "favorite_season" in all_facts


def test_beyond_20_facts():
    """Test that we can store more than 20 different fact categories"""
    # Create 25 different favorite categories
    categories = [
        "snack", "drink", "movie", "book", "band", "sport", "season", "color",
        "food", "animal", "city", "country", "game", "hobby", "language",
        "framework", "editor", "os", "browser", "restaurant", "dish", "dessert",
        "beverage", "activity", "subject"
    ]
    
    all_facts = {}
    for i, category in enumerate(categories):
        text = f"FACT: favorite_{category} = value{i}"
        facts = extract_fact_slots(text)
        all_facts.update(facts)
    
    # Should have all 25 categories
    assert len(all_facts) == 25
    for category in categories:
        assert f"favorite_{category}" in all_facts


def test_favorite_color_not_overridden():
    """Test that specific favorite_color pattern takes precedence"""
    text = "My favorite color is blue"
    facts = extract_fact_slots(text)
    
    # Should use the specific favorite_color slot
    assert "favorite_color" in facts
    assert facts["favorite_color"].value == "blue"


def test_dynamic_status_slot():
    """Test slots with _status suffix"""
    text = "FACT: project_status = in progress"
    facts = extract_fact_slots(text)
    
    assert "project_status" in facts
    assert facts["project_status"].value == "in progress"


def test_dynamic_count_slot():
    """Test slots with _count suffix"""
    text = "FACT: vacation_count = 3"
    facts = extract_fact_slots(text)
    
    assert "vacation_count" in facts
    assert facts["vacation_count"].value == "3"


def test_dynamic_name_slot():
    """Test slots with _name suffix"""
    text = "FACT: company_name = TechCorp"
    facts = extract_fact_slots(text)
    
    assert "company_name" in facts
    assert facts["company_name"].value == "TechCorp"


def test_dynamic_type_slot():
    """Test slots with _type suffix"""
    text = "FACT: database_type = PostgreSQL"
    facts = extract_fact_slots(text)
    
    assert "database_type" in facts
    assert facts["database_type"].value == "PostgreSQL"


def test_skip_generic_categories():
    """Test that overly generic categories are skipped"""
    # "thing", "one", "part" etc. should be skipped
    text = "My favorite thing is coding"
    facts = extract_fact_slots(text)
    
    # Should not create favorite_thing
    assert "favorite_thing" not in facts


def test_natural_language_favorite_with_continuation():
    """Test extraction with common continuations trimmed"""
    text = "My favorite snack is popcorn and pretzels"
    facts = extract_fact_slots(text)
    
    assert "favorite_snack" in facts
    # Should trim at "and"
    assert facts["favorite_snack"].value == "popcorn"


def test_core_slots_still_work():
    """Test that core hardcoded slots still work"""
    texts = [
        "FACT: name = Alice",
        "FACT: employer = Microsoft",
        "FACT: location = Seattle",
        "FACT: title = Engineer",
    ]
    
    all_facts = {}
    for text in texts:
        facts = extract_fact_slots(text)
        all_facts.update(facts)
    
    assert "name" in all_facts
    assert "employer" in all_facts
    assert "location" in all_facts
    assert "title" in all_facts
