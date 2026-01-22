"""Tests for fact extraction functionality."""

import pytest
from groundcheck.fact_extractor import extract_fact_slots, is_question


def test_extract_name_basic():
    """Test basic name extraction."""
    facts = extract_fact_slots("My name is Alice")
    assert "name" in facts
    assert facts["name"].value == "Alice"
    assert facts["name"].normalized == "alice"


def test_extract_name_call_me():
    """Test 'call me' pattern."""
    facts = extract_fact_slots("Call me Bob")
    assert "name" in facts
    assert facts["name"].value == "Bob"


def test_extract_name_im():
    """Test 'I'm' pattern."""
    facts = extract_fact_slots("I'm Sarah")
    assert "name" in facts
    assert facts["name"].value == "Sarah"


def test_extract_employer():
    """Test employer extraction."""
    facts = extract_fact_slots("I work at Microsoft")
    assert "employer" in facts
    assert facts["employer"].value == "Microsoft"


def test_extract_employer_work_for():
    """Test 'work for' pattern."""
    facts = extract_fact_slots("I work for Amazon")
    assert "employer" in facts
    assert facts["employer"].value == "Amazon"


def test_extract_self_employed():
    """Test self-employment detection."""
    facts = extract_fact_slots("I work for myself")
    assert "employer" in facts
    assert facts["employer"].value == "self-employed"


def test_extract_location():
    """Test location extraction."""
    facts = extract_fact_slots("I live in Seattle")
    assert "location" in facts
    assert facts["location"].value == "Seattle"


def test_extract_location_moved():
    """Test 'moved to' pattern."""
    facts = extract_fact_slots("I moved to Denver")
    assert "location" in facts
    assert facts["location"].value == "Denver"


def test_extract_job_title():
    """Test job title extraction."""
    facts = extract_fact_slots("My role is Senior Developer")
    assert "title" in facts
    assert facts["title"].value == "Senior Developer"


def test_extract_favorite_color():
    """Test favorite color extraction."""
    facts = extract_fact_slots("My favorite color is blue")
    assert "favorite_color" in facts
    assert facts["favorite_color"].value == "blue"


def test_extract_programming_years():
    """Test programming years extraction."""
    facts = extract_fact_slots("I've been programming for 10 years")
    assert "programming_years" in facts
    assert facts["programming_years"].value == 10


def test_extract_first_language():
    """Test first programming language extraction."""
    facts = extract_fact_slots("I started with Python")
    assert "first_language" in facts
    assert facts["first_language"].value == "Python"


def test_extract_multiple_facts():
    """Test extraction of multiple facts from one text."""
    facts = extract_fact_slots(
        "My name is Alice and I work at Microsoft in Seattle"
    )
    assert "name" in facts
    assert facts["name"].value == "Alice"
    assert "employer" in facts
    assert facts["employer"].value == "Microsoft"
    assert "location" in facts
    assert facts["location"].value == "Seattle"


def test_extract_structured_fact():
    """Test structured FACT: format."""
    facts = extract_fact_slots("FACT: name = Bob")
    assert "name" in facts
    assert facts["name"].value == "Bob"


def test_extract_no_facts():
    """Test text with no extractable facts."""
    facts = extract_fact_slots("Hello, how are you?")
    assert len(facts) == 0


def test_extract_education_undergrad():
    """Test undergraduate school extraction."""
    facts = extract_fact_slots("My undergraduate degree was from MIT")
    assert "undergrad_school" in facts
    assert facts["undergrad_school"].value == "MIT"


def test_extract_education_masters():
    """Test master's school extraction."""
    facts = extract_fact_slots("My master's degree was from Stanford")
    assert "masters_school" in facts
    assert facts["masters_school"].value == "Stanford"


def test_extract_siblings():
    """Test siblings extraction."""
    facts = extract_fact_slots("I have two siblings")
    assert "siblings" in facts
    assert facts["siblings"].value == "2"


def test_extract_languages_spoken():
    """Test languages spoken extraction."""
    facts = extract_fact_slots("I speak three languages")
    assert "languages_spoken" in facts
    assert facts["languages_spoken"].value == "3"


def test_extract_graduation_year():
    """Test graduation year extraction."""
    facts = extract_fact_slots("I graduated in 2020")
    assert "graduation_year" in facts
    assert facts["graduation_year"].value == "2020"


def test_extract_pet():
    """Test pet extraction."""
    facts = extract_fact_slots("I have a golden retriever named Murphy")
    assert "pet" in facts
    assert facts["pet"].value == "golden retriever"
    assert "pet_name" in facts
    assert facts["pet_name"].value == "Murphy"


def test_extract_coffee_preference():
    """Test coffee preference extraction."""
    facts = extract_fact_slots("I prefer dark roast")
    assert "coffee" in facts
    assert facts["coffee"].value == "dark roast"


def test_extract_hobby():
    """Test hobby extraction."""
    facts = extract_fact_slots("My hobby is rock climbing")
    assert "hobby" in facts
    assert facts["hobby"].value == "rock climbing"


def test_extract_project():
    """Test project name extraction."""
    facts = extract_fact_slots("My project is called CRT")
    assert "project" in facts
    assert facts["project"].value == "CRT"


def test_extract_programming_language():
    """Test favorite programming language extraction."""
    facts = extract_fact_slots("My favorite programming language is Rust")
    assert "programming_language" in facts
    assert facts["programming_language"].value == "Rust"


def test_is_question_true():
    """Test question detection - positive cases."""
    assert is_question("What is your name?") == True
    assert is_question("Where do you work?") == True
    assert is_question("How are you?") == True
    assert is_question("Can you help me?") == True


def test_is_question_false():
    """Test question detection - negative cases."""
    assert is_question("My name is Alice") == False
    assert is_question("I work at Microsoft") == False
    assert is_question("Hello there") == False


def test_name_stopword_filter():
    """Test that name stopwords are filtered out."""
    # These should NOT extract a name because they contain stopwords
    facts = extract_fact_slots("I'm good")
    assert "name" not in facts
    
    facts = extract_fact_slots("I'm ready")
    assert "name" not in facts


def test_compound_introduction():
    """Test compound introduction pattern."""
    facts = extract_fact_slots("I am a Software Engineer from Seattle")
    assert "occupation" in facts
    assert "location" in facts


def test_empty_input():
    """Test extraction from empty input."""
    facts = extract_fact_slots("")
    assert len(facts) == 0
    
    facts = extract_fact_slots("   ")
    assert len(facts) == 0


def test_compound_value_splitting():
    """Test splitting of compound values."""
    from groundcheck.fact_extractor import _split_compound_values
    
    # Test comma-separated values
    result = _split_compound_values("Python, JavaScript, Ruby")
    assert result == ["Python", "JavaScript", "Ruby"]
    
    # Test "and" conjunction
    result = _split_compound_values("Python and JavaScript")
    assert result == ["Python", "JavaScript"]
    
    # Test "or" conjunction
    result = _split_compound_values("Python or Go")
    assert result == ["Python", "Go"]
    
    # Test mixed
    result = _split_compound_values("Python, JavaScript, and Go")
    assert result == ["Python", "JavaScript", "Go"]
    
    # Test single value
    result = _split_compound_values("Python")
    assert result == ["Python"]


def test_extract_employer_employed_by():
    """Test extraction of employer from 'employed by' pattern."""
    facts = extract_fact_slots("User is employed by Microsoft as a Software Engineer")
    assert "employer" in facts
    assert facts["employer"].value == "Microsoft"


def test_extract_title_from_as_pattern():
    """Test extraction of job title from 'as X' pattern."""
    facts = extract_fact_slots("You work at Microsoft as a Product Manager")
    assert "title" in facts
    assert facts["title"].value == "Product Manager"
    assert "employer" in facts
    assert facts["employer"].value == "Microsoft"


def test_extract_location_resides():
    """Test extraction of location from 'resides in' pattern."""
    facts = extract_fact_slots("User resides in Seattle, Washington")
    assert "location" in facts
    # Should extract just the city, not the state
    assert "Seattle" in facts["location"].value


def test_extract_school_studied_at():
    """Test extraction of school from 'studied at' pattern."""
    facts = extract_fact_slots("You studied CS at Stanford")
    assert "school" in facts
    assert facts["school"].value == "Stanford"


def test_extract_programming_languages_list():
    """Test extraction of programming languages from 'use/know' patterns."""
    facts = extract_fact_slots("You use Python, JavaScript, Ruby, and Go")
    assert "programming_language" in facts
    # The value should contain all the languages
    value = facts["programming_language"].value
    assert "Python" in value
    assert "JavaScript" in value
