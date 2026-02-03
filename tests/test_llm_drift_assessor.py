"""Tests for LLM-based drift assessment."""

import pytest
from personal_agent.llm_drift_assessor import (
    LLMDriftAssessor,
    DriftType,
    DriftAssessment,
    is_gradual_drift,
)


class TestHeuristicFallback:
    """Test heuristic drift detection when LLM unavailable."""
    
    def test_career_progression_detected(self):
        """Career progression should be detected as gradual drift."""
        assessor = LLMDriftAssessor()
        is_gradual, reason = assessor._heuristic_gradual_check(
            "I work as an engineer",
            "I work as a senior engineer"
        )
        assert is_gradual is True
        assert reason == "career_progression"
    
    def test_temporal_markers_detected(self):
        """Temporal markers should indicate gradual drift."""
        assessor = LLMDriftAssessor()
        
        temporal_phrases = [
            ("I work at Google", "I work at Microsoft now"),
            ("I live in Seattle", "I recently moved to Portland"),
            ("I prefer Java", "I currently prefer Python"),
            ("I'm single", "I switched to being married"),
        ]
        
        for old, new in temporal_phrases:
            is_gradual, reason = assessor._heuristic_gradual_check(old, new)
            assert is_gradual is True, f"Expected gradual for: {old} -> {new}"
            assert reason == "temporal_marker_detected"
    
    def test_refinement_detected(self):
        """More specific details should be detected as refinement."""
        assessor = LLMDriftAssessor()
        
        # "specifically" keyword
        is_gradual, reason = assessor._heuristic_gradual_check(
            "I live in the Bay Area",
            "I live in San Francisco specifically"
        )
        assert is_gradual is True
        assert reason == "refinement"
    
    def test_hard_conflict_not_gradual(self):
        """Hard conflicts without markers should not be gradual."""
        assessor = LLMDriftAssessor()
        
        is_gradual, reason = assessor._heuristic_gradual_check(
            "I work at Google",
            "I work at Microsoft"
        )
        assert is_gradual is False
        assert reason is None
    
    def test_name_change_not_gradual(self):
        """Name changes should be hard conflicts."""
        assessor = LLMDriftAssessor()
        
        is_gradual, reason = assessor._heuristic_gradual_check(
            "My name is John",
            "My name is Sarah"
        )
        assert is_gradual is False


class TestDriftTypeMapping:
    """Test drift type to contradiction type mapping."""
    
    def test_drift_types_exist(self):
        """All expected drift types should exist."""
        expected_types = [
            "contradiction",
            "evolution", 
            "refinement",
            "correction",
            "temporal",
            "preference",
            "compatible",
        ]
        for t in expected_types:
            assert DriftType(t) is not None


class TestResponseParsing:
    """Test JSON response parsing."""
    
    def test_parse_valid_json(self):
        """Valid JSON should parse correctly."""
        assessor = LLMDriftAssessor()
        
        response = '{"type": "temporal", "confidence": 0.85, "hard_conflict": false, "reason": "career progression", "action": "accept_new"}'
        result = assessor._parse_response(response, slot="employer")
        
        assert result is not None
        assert result.drift_type == DriftType.TEMPORAL
        assert result.confidence == 0.85
        assert result.is_hard_contradiction is False
        assert result.suggested_action == "accept_new"
        assert result.slot_affected == "employer"
    
    def test_parse_json_with_extra_text(self):
        """JSON embedded in extra text should still parse."""
        assessor = LLMDriftAssessor()
        
        response = 'Here is my analysis: {"type": "contradiction", "confidence": 0.9, "hard_conflict": true, "reason": "different companies", "action": "ask_user"} Hope this helps!'
        result = assessor._parse_response(response, slot=None)
        
        assert result is not None
        assert result.drift_type == DriftType.CONTRADICTION
        assert result.is_hard_contradiction is True
    
    def test_parse_invalid_json_returns_none(self):
        """Invalid JSON should return None."""
        assessor = LLMDriftAssessor()
        
        response = "This is not JSON at all"
        result = assessor._parse_response(response, slot=None)
        
        assert result is None
    
    def test_parse_unknown_type_defaults_to_contradiction(self):
        """Unknown drift type should default to contradiction for safety."""
        assessor = LLMDriftAssessor()
        
        response = '{"type": "unknown_type", "confidence": 0.5, "hard_conflict": false, "reason": "test", "action": "ask_user"}'
        result = assessor._parse_response(response, slot=None)
        
        assert result is not None
        assert result.drift_type == DriftType.CONTRADICTION


class TestConvenienceFunctions:
    """Test module-level convenience functions."""
    
    def test_is_gradual_drift_function(self):
        """Convenience function should work."""
        is_gradual, reason = is_gradual_drift(
            "I work as a developer",
            "I work as a senior developer now"
        )
        assert is_gradual is True
