"""
Unit tests for caveat detection in stress test.

These tests ensure that the caveat detection regex patterns correctly identify
caveat language and its variants in LLM-generated answers.
"""

import re


def get_caveat_regex():
    """Get the caveat detection regex (matches crt_stress_test.py implementation)."""
    caveat_patterns = [
        # Original exact matches
        r"\b(most recent|latest|conflicting|though|however|according to)\b",
        
        # Update/correction family
        r"\b(updat(e|ed|ing)|correct(ed|ing|ion)?|clarif(y|ied|ying))\b",
        
        # Temporal references
        r"\b(earlier|previously|before|prior|former)\b",
        
        # Acknowledgment/confirmation
        r"\b(mentioned|noted|stated|said|established)\b",
        
        # Change/revision family
        r"\b(chang(e|ed|ing)|revis(e|ed|ing)|adjust(ed|ing)?|modif(y|ied|ying))\b",
        
        # Contradiction signals
        r"\b(actually|instead|rather|in fact)\b",
    ]
    return re.compile('|'.join(caveat_patterns), re.IGNORECASE)


class TestCaveatDetection:
    """Test suite for caveat keyword detection."""
    
    def test_update_variants(self):
        """Test detection of 'update' and its variants."""
        regex = get_caveat_regex()
        
        # Should match
        assert regex.search("I will update this")
        assert regex.search("I'm updating this")
        assert regex.search("I updated this")
        
        # Should NOT match (false positives)
        assert not regex.search("I will upend this")
        assert not regex.search("supdate is not a word")
    
    def test_clarify_variants(self):
        """Test detection of 'clarify' and its variants."""
        regex = get_caveat_regex()
        
        # Should match
        assert regex.search("Let me clarify")
        assert regex.search("We clarified that")
        assert regex.search("I'm clarifying")
        
        # Case insensitive
        assert regex.search("To CLARIFY")
        assert regex.search("I'm Clarifying this point")
    
    def test_correct_variants(self):
        """Test detection of 'correct' and its variants."""
        regex = get_caveat_regex()
        
        # Should match
        assert regex.search("You're correct")
        assert regex.search("I corrected the information")
        assert regex.search("This needs correction")
        assert regex.search("I'm correcting this")
        
        # Should NOT match (false positives)
        assert not regex.search("incorrect information")  # 'incorrect' is not 'correct'
    
    def test_temporal_references(self):
        """Test detection of temporal reference words."""
        regex = get_caveat_regex()
        
        # Should match
        assert regex.search("You mentioned earlier")
        assert regex.search("As stated previously")
        assert regex.search("Your prior statement")
        assert regex.search("The former option")
        assert regex.search("Before we discussed")
        
        # Case insensitive
        assert regex.search("EARLIER today")
    
    def test_acknowledgment_words(self):
        """Test detection of acknowledgment/confirmation words."""
        regex = get_caveat_regex()
        
        # Should match
        assert regex.search("You mentioned that")
        assert regex.search("As I noted before")
        assert regex.search("You stated earlier")
        assert regex.search("As you said")
        assert regex.search("We've established")
    
    def test_original_keywords(self):
        """Test detection of original keyword list."""
        regex = get_caveat_regex()
        
        # Should match
        assert regex.search("According to our previous conversation")
        assert regex.search("The most recent information")
        assert regex.search("The latest update")
        assert regex.search("Conflicting information")
        assert regex.search("Though I mentioned")
        assert regex.search("However, you said")
    
    def test_change_revision_words(self):
        """Test detection of change/revision family words."""
        regex = get_caveat_regex()
        
        # Should match
        assert regex.search("I changed this")
        assert regex.search("We're changing our approach")
        assert regex.search("This was revised")
        assert regex.search("I'm revising the answer")
        assert regex.search("The adjusted value")
        assert regex.search("We modified that")
    
    def test_contradiction_signals(self):
        """Test detection of contradiction signal words."""
        regex = get_caveat_regex()
        
        # Should match
        assert regex.search("Actually, it's different")
        assert regex.search("Instead of that")
        assert regex.search("Rather than this")
        assert regex.search("In fact, the answer is")
    
    def test_no_false_positives(self):
        """Test that normal conversation doesn't trigger false positives."""
        regex = get_caveat_regex()
        
        # Should NOT match
        assert not regex.search("Hello, how are you?")
        assert not regex.search("I can help with that")
        assert not regex.search("What would you like to know?")
        assert not regex.search("Your name is important")
        assert not regex.search("Thank you for sharing")
    
    def test_real_violation_examples(self):
        """Test with real examples from the stress test violations."""
        regex = get_caveat_regex()
        
        # Turn 14 - Should match (has "updating" and "clarify")
        answer_14 = "You're updating your count of programming years. So, to clarify, you've been programming for a total of 8 years."
        assert regex.search(answer_14)
        
        # Turn 16 - Should match (has "mentioned" and "earlier")
        answer_16 = "You mentioned earlier that you live in the Bellevue area"
        assert regex.search(answer_16)
        
        # Turn 21 - Should match (has "clarified")
        answer_21 = "I'm glad we clarified that."
        assert regex.search(answer_21)
        
        # Turn 25 - Should match (has "correct")
        answer_25 = "You're correct that your master's school"
        assert regex.search(answer_25)
    
    def test_working_examples(self):
        """Test with examples that already worked (should still match)."""
        regex = get_caveat_regex()
        
        # Turn 11 - Should match (has "according to" and "update")
        answer_11 = "According to our previous conversation, you mentioned that you work at Amazon. I will make sure to update my memory"
        assert regex.search(answer_11)
        
        # Turn 13 - Should match (has "according to")
        answer_13 = "According to your facts about yourself"
        assert regex.search(answer_13)
    
    def test_word_boundaries(self):
        """Test that word boundaries work correctly."""
        regex = get_caveat_regex()
        
        # Should match (whole words)
        assert regex.search("I will update")
        assert regex.search("update the info")
        
        # Should NOT match (partial words - depends on pattern design)
        # Note: Our patterns use \b which should prevent matching inside words
        assert not regex.search("superupdate")  # 'update' not at word boundary
        
    def test_case_insensitivity(self):
        """Test that pattern matching is case-insensitive."""
        regex = get_caveat_regex()
        
        # All variations should match
        assert regex.search("UPDATE")
        assert regex.search("Update")
        assert regex.search("update")
        assert regex.search("UpDaTe")
        
        assert regex.search("CLARIFY")
        assert regex.search("Clarify")
        assert regex.search("clarify")


def run_tests():
    """Run all tests and report results."""
    test_suite = TestCaveatDetection()
    methods = [m for m in dir(test_suite) if m.startswith('test_')]
    
    passed = 0
    failed = 0
    
    print("Running Caveat Detection Tests...")
    print("=" * 70)
    
    for method_name in methods:
        try:
            method = getattr(test_suite, method_name)
            method()
            print(f"✓ {method_name}")
            passed += 1
        except AssertionError as e:
            print(f"✗ {method_name}: {e}")
            failed += 1
        except Exception as e:
            print(f"✗ {method_name}: Unexpected error: {e}")
            failed += 1
    
    print("=" * 70)
    print(f"Results: {passed} passed, {failed} failed")
    
    if failed > 0:
        return 1
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(run_tests())

