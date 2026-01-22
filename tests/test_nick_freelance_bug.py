"""
Test for Nick's freelance bug - system forgetting previously stored employer facts.

Bug reproduction from chat logs:
1. User: "I work for myself as a freelance web developer" -> Stored
2. User: "I might also be getting a job at Walmart" -> Overwrites freelance job
3. User: "Do I freelance at anything?" -> System says "I couldn't find any evidence"

Root cause: user_profile.py uses PRIMARY KEY on slot, allowing only ONE employer value.
"""

import tempfile
import os
from pathlib import Path

from personal_agent.user_profile import GlobalUserProfile
from personal_agent.fact_slots import extract_fact_slots


def test_nick_freelance_bug_minimal():
    """
    Minimal reproduction: User says they're freelance, then says they're getting Walmart job.
    System should remember BOTH facts, not overwrite freelance with Walmart.
    """
    # Use temp DB for test
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
        db_path = tmp.name
    
    try:
        profile = GlobalUserProfile(db_path=db_path)
        
        # Step 1: User declares freelance work
        text1 = "I work for myself as a freelance web developer."
        updated1 = profile.update_from_text(text1, thread_id="test_thread")
        print(f"Step 1 - Updated facts: {updated1}")
        
        # Verify freelance fact was stored
        facts1 = profile.get_all_facts()
        print(f"Step 1 - All facts: {[(k, v.value) for k, v in facts1.items()]}")
        
        assert "employer" in facts1, "Employer fact should be stored"
        assert "self-employed" in facts1["employer"].value.lower() or \
               "freelance" in facts1["employer"].normalized, \
               f"Freelance fact should be stored, got: {facts1['employer'].value}"
        
        # Step 2: User mentions potential Walmart job
        text2 = "I might also be getting a job at Walmart."
        updated2 = profile.update_from_text(text2, thread_id="test_thread")
        print(f"Step 2 - Updated facts: {updated2}")
        
        # Verify BOTH facts are stored
        facts2 = profile.get_all_facts_expanded()  # Use expanded view to see all values
        print(f"Step 2 - All facts (expanded): {[(k, [f.value for f in v]) for k, v in facts2.items()]}")
        
        # CRITICAL BUG CHECK: Both employer facts should be present
        # Current bug: freelance fact gets overwritten by Walmart
        employer_facts = facts2.get("employer", [])
        print(f"Employer facts found: {[f.value for f in employer_facts]}")
        
        # Split assertion for clarity
        assert len(employer_facts) >= 2, \
            f"Expected at least 2 employers, got {len(employer_facts)}: {[f.value for f in employer_facts]}"
        
        # Verify we can retrieve the freelance fact
        has_freelance = any(
            "freelance" in f.value.lower() or "self-employed" in f.value.lower()
            for f in employer_facts
        )
        has_walmart = any("walmart" in f.value.lower() for f in employer_facts)
        
        assert has_freelance, "Freelance fact should still be present"
        assert has_walmart, "Walmart fact should be present"
        
    finally:
        # Cleanup
        if os.path.exists(db_path):
            os.unlink(db_path)


def test_fact_extraction_preserves_both_employers():
    """
    Verify fact_slots.py correctly extracts both employer facts.
    This test checks that fact extraction is working correctly.
    """
    # Test freelance extraction
    text1 = "I work for myself as a freelance web developer."
    facts1 = extract_fact_slots(text1)
    print(f"Facts from freelance: {facts1}")
    assert "employer" in facts1, "Should extract employer from freelance statement"
    assert "self-employed" in facts1["employer"].normalized or \
           "self-employed" in facts1["employer"].value.lower(), \
           f"Should recognize self-employment, got: {facts1['employer'].value}"
    
    # Test Walmart extraction
    text2 = "I might also be getting a job at Walmart."
    facts2 = extract_fact_slots(text2)
    print(f"Facts from Walmart: {facts2}")
    assert "employer" in facts2, "Should extract employer from Walmart statement"
    assert "walmart" in facts2["employer"].normalized, \
           f"Should recognize Walmart, got: {facts2['employer'].value}"
    
    # Both extractions work correctly - the bug is in storage, not extraction
    print("\n✓ Fact extraction works correctly for both statements")
    print("✗ Bug is in user_profile.py storage (PRIMARY KEY overwrites)")


if __name__ == "__main__":
    print("="*60)
    print("Testing Nick's Freelance Bug")
    print("="*60)
    
    print("\n--- Test 1: Fact Extraction (should pass) ---")
    test_fact_extraction_preserves_both_employers()
    
    print("\n--- Test 2: User Profile Storage (should FAIL - this is the bug) ---")
    try:
        test_nick_freelance_bug_minimal()
        print("\n✅ TEST PASSED - Bug is fixed!")
    except AssertionError as e:
        print(f"\n❌ TEST FAILED - Bug reproduced: {e}")
