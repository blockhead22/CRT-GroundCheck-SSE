"""
Test temporal guard rails to prevent storing temporary activities as permanent facts.

Addresses user concern: "a user might say im working on homework and suddenly 
the system is confused about working on homework and working at walmart"
"""

import tempfile
import os

from personal_agent.user_profile import GlobalUserProfile


def test_temporal_guard_rails():
    """
    Test that temporal/temporary statements are NOT stored as permanent facts.
    """
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
        db_path = tmp.name
    
    try:
        profile = GlobalUserProfile(db_path=db_path)
        
        print("\n" + "="*70)
        print("TESTING TEMPORAL GUARD RAILS")
        print("="*70)
        
        # First, establish a permanent employer fact
        print("\n[Setup] Store permanent employer fact")
        profile.update_from_text("I work at Walmart", thread_id="test")
        employers = profile.get_all_facts_for_slot("employer")
        print(f"  → Permanent employer stored: {[e.value for e in employers]}")
        assert len(employers) == 1
        assert "Walmart" in employers[0].value
        
        # Test Case 1: Temporal activity should NOT be stored
        print("\n[Test 1] Temporal activity: 'I'm working on homework tonight'")
        result = profile.update_from_text("I'm working on homework tonight", thread_id="test")
        print(f"  → Facts updated: {result}")
        employers = profile.get_all_facts_for_slot("employer")
        print(f"  → Employers in profile: {[e.value for e in employers]}")
        
        # Should still only have Walmart, NOT homework
        assert len(employers) == 1, \
            f"Should not store 'homework' as employer. Found: {[e.value for e in employers]}"
        assert "Walmart" in employers[0].value
        print("  ✓ Guard rail working: temporal activity NOT stored")
        
        # Test Case 2: Another temporal activity
        print("\n[Test 2] Temporal activity: 'I'm currently reviewing code'")
        result = profile.update_from_text("I'm currently reviewing code", thread_id="test")
        print(f"  → Facts updated: {result}")
        employers = profile.get_all_facts_for_slot("employer")
        print(f"  → Employers in profile: {[e.value for e in employers]}")
        
        assert len(employers) == 1, \
            f"Should not store 'reviewing code' as employer. Found: {[e.value for e in employers]}"
        print("  ✓ Guard rail working: temporal activity NOT stored")
        
        # Test Case 3: Permanent fact SHOULD be stored
        print("\n[Test 3] Permanent fact: 'I work for myself as a freelance web developer'")
        result = profile.update_from_text("I work for myself as a freelance web developer", thread_id="test")
        print(f"  → Facts updated: {result}")
        employers = profile.get_all_facts_for_slot("employer")
        print(f"  → Employers in profile: {[e.value for e in employers]}")
        
        # Should now have BOTH Walmart and freelance (self-employed)
        assert len(employers) == 2, \
            f"Should have both employers. Found: {[e.value for e in employers]}"
        has_walmart = any("Walmart" in e.value for e in employers)
        has_freelance = any("self-employed" in e.value.lower() for e in employers)
        assert has_walmart and has_freelance, \
            f"Should have both Walmart and freelance. Found: {[e.value for e in employers]}"
        print("  ✓ Guard rail allows permanent facts to be stored")
        
        # Test Case 4: "working on" pattern (should be filtered)
        print("\n[Test 4] Temporary: 'I'm working on some freelance projects today'")
        result = profile.update_from_text("I'm working on some freelance projects today", thread_id="test")
        print(f"  → Facts updated: {result}")
        employers = profile.get_all_facts_for_slot("employer")
        print(f"  → Employers in profile: {[e.value for e in employers]}")
        
        # Should still only have 2 (Walmart + freelance from before)
        assert len(employers) == 2, \
            f"Should not add 'working on' as new employer. Found: {[e.value for e in employers]}"
        print("  ✓ Guard rail filters 'working on' patterns")
        
        print("\n" + "="*70)
        print("✅ ALL TEMPORAL GUARD RAIL TESTS PASSED!")
        print("="*70)
        print("\nSummary:")
        print("  - Temporal activities (homework tonight, reviewing code) → NOT stored ✓")
        print("  - Permanent facts (work at Walmart, freelance) → Stored correctly ✓")
        print("  - 'working on' patterns → Filtered as temporary ✓")
        
    finally:
        if os.path.exists(db_path):
            os.unlink(db_path)


def test_temporal_detection_examples():
    """
    Test the temporal detection helper function with various examples.
    """
    profile = GlobalUserProfile(db_path=":memory:")
    
    print("\n" + "="*70)
    print("TEMPORAL STATEMENT DETECTION EXAMPLES")
    print("="*70)
    
    temporal_examples = [
        "I'm working on homework tonight",
        "I'm currently reviewing code",
        "I'm studying for exams this week",
        "I'm doing some freelance work today",
        "I'm learning about Python recently",
    ]
    
    permanent_examples = [
        "I work at Walmart",
        "I'm a freelance web developer",
        "I graduated from MIT",
        "My name is Nick",
        "I live in Seattle",
    ]
    
    print("\nShould be detected as TEMPORAL (filtered out):")
    for text in temporal_examples:
        is_temporal = profile._is_temporal_statement(text)
        status = "✓ Filtered" if is_temporal else "✗ NOT filtered (BUG)"
        print(f"  {status}: {text}")
        assert is_temporal, f"Should detect as temporal: {text}"
    
    print("\nShould be detected as PERMANENT (allowed):")
    for text in permanent_examples:
        is_temporal = profile._is_temporal_statement(text)
        status = "✓ Allowed" if not is_temporal else "✗ Filtered (BUG)"
        print(f"  {status}: {text}")
        assert not is_temporal, f"Should allow as permanent: {text}"
    
    print("\n✅ All detection tests passed!")


if __name__ == "__main__":
    test_temporal_detection_examples()
    test_temporal_guard_rails()
