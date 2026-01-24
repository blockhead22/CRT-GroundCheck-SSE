"""
Test expanded resolution patterns.

Tests that the new conversational resolution patterns are:
1. Correctly detected
2. Properly matched
3. Documented and extensible
"""

import pytest
from personal_agent.resolution_patterns import (
    has_resolution_intent,
    get_matched_patterns,
    add_custom_pattern,
    get_all_patterns,
    get_pattern_description,
    RESOLUTION_PATTERNS
)


class TestResolutionPatternDetection:
    """Test that resolution patterns are correctly detected"""
    
    def test_is_correct_pattern(self):
        """Test 'is correct' pattern"""
        assert has_resolution_intent("Google is correct")
        assert has_resolution_intent("Microsoft was right")
        assert has_resolution_intent("That is accurate")
    
    def test_actually_pattern(self):
        """Test 'actually' revision marker"""
        assert has_resolution_intent("Actually, it's Google now")
        assert has_resolution_intent("Actually I meant Seattle")
    
    def test_i_meant_pattern(self):
        """Test 'I meant' clarification"""
        assert has_resolution_intent("I meant Google, not Microsoft")
        assert has_resolution_intent("I meant to say Seattle")
    
    def test_switched_jobs_pattern(self):
        """Test job change patterns"""
        assert has_resolution_intent("I switched jobs to Google")
        assert has_resolution_intent("I switched companies")
        assert has_resolution_intent("switched to Amazon")
    
    def test_changed_to_pattern(self):
        """Test general 'changed to' pattern"""
        assert has_resolution_intent("I changed to Google")
        assert has_resolution_intent("changed to Seattle")
        assert has_resolution_intent("It changed to blue")
    
    def test_moved_to_pattern(self):
        """Test 'moved to' pattern"""
        assert has_resolution_intent("I moved to Seattle")
        assert has_resolution_intent("moved to Amazon")
    
    def test_now_working_pattern(self):
        """Test current status patterns"""
        assert has_resolution_intent("I now work at Google")
        assert has_resolution_intent("Now working at Microsoft")
    
    def test_correct_one_pattern(self):
        """Test correctness confirmation patterns"""
        assert has_resolution_intent("That's the correct answer")
        assert has_resolution_intent("The correct value is Google")
        assert has_resolution_intent("correct status")
    
    def test_ignore_pattern(self):
        """Test ignore/discard patterns"""
        assert has_resolution_intent("ignore the old one")
        assert has_resolution_intent("ignore that")
    
    # NEW PATTERNS
    
    def test_keep_old_pattern(self):
        """Test 'keep old' patterns (NEW)"""
        assert has_resolution_intent("keep the old value")
        assert has_resolution_intent("keep old")
        assert has_resolution_intent("keep the original")
        assert has_resolution_intent("keep the first one")
    
    def test_stick_with_old_pattern(self):
        """Test 'stick with old' patterns (NEW)"""
        assert has_resolution_intent("stick with the old value")
        assert has_resolution_intent("stick with original")
        assert has_resolution_intent("stick with the previous one")
    
    def test_stick_with_value_pattern(self):
        """Test 'stick with X' patterns (NEW)"""
        assert has_resolution_intent("stick with Google")
        assert has_resolution_intent("stick with Seattle")
        assert has_resolution_intent("stick with blue")
    
    def test_go_with_pattern(self):
        """Test 'go with X' patterns (NEW)"""
        assert has_resolution_intent("go with Google")
        assert has_resolution_intent("go with the new one")
        assert has_resolution_intent("let's go with Seattle")
    
    def test_prefer_pattern(self):
        """Test 'prefer X' patterns (NEW)"""
        assert has_resolution_intent("prefer Google")
        assert has_resolution_intent("I prefer Seattle")
        assert has_resolution_intent("prefer the old value")
    
    def test_use_instead_pattern(self):
        """Test 'use X instead' patterns (NEW)"""
        assert has_resolution_intent("use Google instead")
        assert has_resolution_intent("use Seattle instead")
        assert has_resolution_intent("let's use Microsoft instead")
    
    def test_replace_with_pattern(self):
        """Test 'replace with X' patterns (NEW)"""
        assert has_resolution_intent("replace with Google")
        assert has_resolution_intent("replace it with Seattle")
    
    def test_override_pattern(self):
        """Test 'override' patterns (NEW)"""
        assert has_resolution_intent("override with Google")
        assert has_resolution_intent("override to Seattle")
    
    def test_update_pattern(self):
        """Test 'update' patterns (NEW)"""
        assert has_resolution_intent("update to Google")
        assert has_resolution_intent("update it to Seattle")
    
    def test_choose_pattern(self):
        """Test 'choose X' patterns (NEW)"""
        assert has_resolution_intent("choose Google")
        assert has_resolution_intent("I choose Seattle")
        assert has_resolution_intent("let's choose Microsoft")
    
    def test_select_pattern(self):
        """Test 'select X' patterns (NEW)"""
        assert has_resolution_intent("select Google")
        assert has_resolution_intent("I'll select Seattle")
    
    def test_pick_pattern(self):
        """Test 'pick X' patterns (NEW)"""
        assert has_resolution_intent("pick Google")
        assert has_resolution_intent("I'll pick Seattle")
    
    def test_no_resolution_intent(self):
        """Test that non-resolution text is not detected"""
        assert not has_resolution_intent("My name is Alice")
        assert not has_resolution_intent("I work at Google")
        assert not has_resolution_intent("What's the weather?")
        assert not has_resolution_intent("Tell me about my profile")


class TestPatternMatching:
    """Test detailed pattern matching"""
    
    def test_get_matched_patterns_single(self):
        """Test getting matched patterns with single match"""
        matches = get_matched_patterns("Google is correct")
        
        assert len(matches) >= 1
        assert any("correct" in m['match'].lower() for m in matches)
    
    def test_get_matched_patterns_multiple(self):
        """Test getting matched patterns with multiple matches"""
        text = "Actually, Google is correct now"
        matches = get_matched_patterns(text)
        
        # Should match both "actually" and "is correct"
        assert len(matches) >= 2
    
    def test_matched_pattern_details(self):
        """Test that matched patterns include all details"""
        matches = get_matched_patterns("I prefer Google")
        
        assert len(matches) >= 1
        match = matches[0]
        
        assert 'pattern' in match
        assert 'match' in match
        assert 'start' in match
        assert 'end' in match
    
    def test_no_matches(self):
        """Test that non-resolution text returns empty list"""
        matches = get_matched_patterns("My name is Alice")
        assert len(matches) == 0


class TestPatternExtension:
    """Test pattern extensibility"""
    
    def test_add_custom_pattern(self):
        """Test adding a custom pattern"""
        initial_count = len(get_all_patterns())
        
        # Add custom pattern
        add_custom_pattern(r'\bswap\s+to\s+([A-Za-z0-9\s]+)')
        
        # Should have one more pattern
        assert len(get_all_patterns()) == initial_count + 1
        
        # Should now detect the custom pattern
        assert has_resolution_intent("swap to Google")
    
    def test_add_duplicate_pattern(self):
        """Test that duplicate patterns are not added"""
        initial_count = len(get_all_patterns())
        
        # Try to add existing pattern
        add_custom_pattern(r'\bactually\b')
        
        # Count should not increase
        assert len(get_all_patterns()) == initial_count
    
    def test_get_all_patterns(self):
        """Test getting all patterns"""
        patterns = get_all_patterns()
        
        assert isinstance(patterns, list)
        assert len(patterns) > 0
        
        # Should be a copy, not the original
        patterns.append("test")
        assert len(get_all_patterns()) != len(patterns)


class TestPatternDocumentation:
    """Test pattern documentation"""
    
    def test_pattern_descriptions_exist(self):
        """Test that pattern descriptions are available"""
        # Should have descriptions for common patterns
        desc = get_pattern_description(r'\bactually\b')
        assert desc is not None
        assert len(desc) > 0
    
    def test_pattern_description_fallback(self):
        """Test that unknown patterns return the pattern itself"""
        unknown_pattern = r'\bunknown_pattern\b'
        desc = get_pattern_description(unknown_pattern)
        assert desc == unknown_pattern
    
    def test_all_patterns_have_descriptions(self):
        """Test that all patterns have descriptions or fallbacks"""
        for pattern in RESOLUTION_PATTERNS:
            desc = get_pattern_description(pattern)
            assert desc is not None
            assert len(desc) > 0


class TestRealWorldExamples:
    """Test real-world user examples"""
    
    def test_example_from_problem_statement(self):
        """Test example from the problem statement"""
        # "User: 'I changed snack to pretzels' → Resolution phrase triggers"
        assert has_resolution_intent("I changed snack to pretzels")
        
        matches = get_matched_patterns("I changed snack to pretzels")
        assert len(matches) >= 1
    
    def test_casual_resolution(self):
        """Test casual resolution language"""
        examples = [
            "Google is correct, I switched jobs",
            "Actually it's Google now",
            "I meant Google not Microsoft",
            "Keep the old one",
            "Let's go with Seattle",
            "Use Microsoft instead",
            "Choose the first option",
        ]
        
        for example in examples:
            assert has_resolution_intent(example), f"Failed to detect: {example}"
    
    def test_formal_resolution(self):
        """Test formal resolution language"""
        examples = [
            "Please update to Google",
            "Override with Seattle",
            "Replace it with Microsoft",
            "Select the new value",
        ]
        
        for example in examples:
            assert has_resolution_intent(example), f"Failed to detect: {example}"
    
    def test_mixed_case_and_punctuation(self):
        """Test that patterns work regardless of case and punctuation"""
        examples = [
            "GOOGLE IS CORRECT!",
            "actually, it's google now.",
            "I MEANT GOOGLE, NOT MICROSOFT!",
            "keep the old value...",
        ]
        
        for example in examples:
            assert has_resolution_intent(example), f"Failed to detect: {example}"


class TestPatternCoverage:
    """Test that we have sufficient pattern coverage"""
    
    def test_minimum_pattern_count(self):
        """Test that we have at least 10 new patterns beyond original"""
        # Original patterns: ~12
        # Requirement: Add at least 10 more
        # So we should have at least 22 total
        patterns = get_all_patterns()
        assert len(patterns) >= 22, f"Only {len(patterns)} patterns, need at least 22"
    
    def test_pattern_variety(self):
        """Test that patterns cover different resolution intents"""
        patterns = get_all_patterns()
        pattern_text = " ".join(patterns)
        
        # Should have patterns for different intents
        assert "keep" in pattern_text.lower()
        assert "choose" in pattern_text.lower()
        assert "prefer" in pattern_text.lower()
        assert "update" in pattern_text.lower()
        assert "replace" in pattern_text.lower()
