"""
Complete integration test simulating Nick's exact chat sequence.

This reproduces the bug as described in the chat logs:
1. "I work for myself as a freelance web developer"
2. "I might also be getting a job at Walmart"  
3. "What do I do?" -> should mention BOTH freelance and Walmart
4. "Do I freelance at anything?" -> should find freelance evidence

The bug was: system said "I couldn't find any evidence that suggests Nick freelances"
"""

import tempfile
import os

from personal_agent.user_profile import GlobalUserProfile


def test_nick_exact_chat_sequence():
    """
    Test the EXACT sequence from Nick's chat logs to ensure bug is fixed.
    """
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
        db_path = tmp.name
    
    try:
        profile = GlobalUserProfile(db_path=db_path)
        
        # Simulate Nick's name being stored first
        profile.update_from_text("Hi I am Nick!", thread_id="nick_chat")
        
        # Critical sequence starts here
        print("\n" + "="*70)
        print("NICK'S CHAT SEQUENCE - BUG REPRODUCTION")
        print("="*70)
        
        # Turn 1: Freelance declaration
        print("\n[Turn 1] User: 'I work for myself as a freelance web developer.'")
        profile.update_from_text("I work for myself as a freelance web developer.", 
                                thread_id="nick_chat")
        
        employers_1 = profile.get_all_facts_for_slot("employer")
        print(f"  → Stored employers: {[e.value for e in employers_1]}")
        assert len(employers_1) == 1
        assert any("self-employed" in e.value.lower() for e in employers_1)
        print("  ✓ Freelance fact stored correctly")
        
        # Turn 2: Walmart mention
        print("\n[Turn 2] User: 'I might also be getting a job at Walmart.'")
        profile.update_from_text("I might also be getting a job at Walmart.", 
                                thread_id="nick_chat")
        
        employers_2 = profile.get_all_facts_for_slot("employer")
        print(f"  → Stored employers: {[e.value for e in employers_2]}")
        
        # CRITICAL: Both should be present
        assert len(employers_2) == 2, \
            f"BUG REPRODUCED: Only {len(employers_2)} employer(s), expected 2"
        
        has_freelance = any("self-employed" in e.value.lower() for e in employers_2)
        has_walmart = any("walmart" in e.value.lower() for e in employers_2)
        
        assert has_freelance, "BUG: Freelance fact was lost!"
        assert has_walmart, "Walmart fact should be present"
        print("  ✓ Both employer facts preserved")
        
        # Turn 3: "What do I do?" query
        print("\n[Turn 3] User: 'What do I do?'")
        print("  System should retrieve: BOTH freelance AND Walmart")
        
        all_employers = profile.get_all_facts_for_slot("employer")
        print(f"  → Retrieved employers: {[e.value for e in all_employers]}")
        
        assert len(all_employers) == 2, \
            f"Should retrieve both employers, got {len(all_employers)}"
        print("  ✓ Both employers would be available to LLM")
        
        # Turn 4: "Do I freelance at anything?" query
        print("\n[Turn 4] User: 'Do I freelance at anything?'")
        print("  System should find: YES, evidence of freelancing")
        
        # Check memory texts that would be passed to LLM
        memory_texts = profile.to_memory_texts()
        employer_memories = [t for t in memory_texts if "employer" in t.lower()]
        
        print(f"  → Employer memory texts:")
        for mem in employer_memories:
            print(f"      - {mem}")
        
        # Critical check: freelance evidence should be present
        has_freelance_evidence = any(
            "self-employed" in mem.lower() or "freelance" in mem.lower()
            for mem in employer_memories
        )
        
        assert has_freelance_evidence, \
            "BUG: No freelance evidence found in memory! System would say 'no evidence'"
        
        print("  ✓ Freelance evidence IS present in memories")
        print("\n" + "="*70)
        print("✅ BUG FIX VERIFIED - All assertions passed!")
        print("="*70)
        print("\nThe system now:")
        print("  1. Stores BOTH employer facts (freelance + Walmart)")
        print("  2. Retrieves BOTH when queried about employment")
        print("  3. Can answer 'Do I freelance?' with YES + evidence")
        print("\nOriginal bug (overwriting freelance with Walmart) is FIXED!")
        
    finally:
        if os.path.exists(db_path):
            os.unlink(db_path)


if __name__ == "__main__":
    test_nick_exact_chat_sequence()
