"""
Code Agent
Writes production code and implements features
"""

from typing import Dict, Any
from .base_agent import BaseAgent
from ..task import Task


class CodeAgent(BaseAgent):
    """
    Implementation agent
    
    Responsibilities:
    - Write production code
    - Implement features
    - Refactor existing code
    - Follow boundaries (validated by BoundaryAgent)
    """
    
    def __init__(self):
        super().__init__("CodeAgent")
        self.boundaries = None  # Set by context
    
    def execute(self, task: Task) -> Dict:
        """Execute code generation task"""
        self.log(f"Executing: {task.description[:50]}")
        
        # Get boundaries from context (from BoundaryAgent)
        self.boundaries = task.context.get("forbidden_patterns", {})
        
        description = task.description.lower()
        
        if "test" in description and ("boundary" in description or "phase_6" in description):
            return self._generate_boundary_tests(task.context)
        
        elif "sseclient" in description or "safe wrapper" in description:
            return self._generate_safe_client(task.context)
        
        elif "multi-frame" in description or "multiframeexplainer" in description:
            return self._generate_multi_frame(task.context)
        
        else:
            # Generic code generation
            return self._generate_generic_code(task)
    
    def _generate_boundary_tests(self, context: dict) -> Dict:
        """Generate boundary test code"""
        code = '''"""
Phase 6 Boundary Tests
Tests that ensure SSE never crosses into Phase D-G
"""

import pytest


class TestOutcomeMeasurementForbidden:
    """Verify no outcome measurement exists"""
    
    def test_no_outcome_tracking_tables(self):
        """No database tables for tracking outcomes"""
        # Check database schema
        forbidden_tables = [
            "outcome_data", "recommendation_results",
            "user_followed_advice", "success_metrics"
        ]
        # Implementation: scan schema, ensure none exist
        pass
    
    def test_no_measure_success_methods(self):
        """No methods that measure recommendation success"""
        forbidden_methods = [
            "measure_success", "track_outcome",
            "record_user_action", "measure_recommendation_success"
        ]
        # Implementation: scan all classes, ensure none exist
        pass
    
    def test_recommendations_not_logged_with_outcomes(self):
        """Recommendations logged without outcome tracking"""
        # Can log "recommendation made"
        # Cannot log "recommendation followed" or "recommendation worked"
        pass


class TestPersistentStateForbidden:
    """Verify no persistent learning state"""
    
    def test_no_model_update_methods(self):
        """No methods that update models based on outcomes"""
        forbidden = ["update_model", "learn_from", "improve_confidence"]
        pass
    
    def test_state_is_stateless(self):
        """Each request is independent"""
        # Same input = same output, regardless of history
        pass


class TestConfidenceScoringForbidden:
    """Verify no confidence scores assigned"""
    
    def test_no_confidence_in_contradictions(self):
        """Contradictions have no confidence scores"""
        pass
    
    def test_no_reliability_ratings(self):
        """No rating of claim reliability"""
        pass


class TestTruthFilteringForbidden:
    """Verify all contradictions shown equally"""
    
    def test_no_filtering_by_truth(self):
        """No contradictions filtered by perceived truth"""
        pass
    
    def test_all_contradictions_returned(self):
        """All detected contradictions returned"""
        pass


class TestExplanationRankingForbidden:
    """Verify explanations not ranked"""
    
    def test_no_best_explanation_selection(self):
        """No 'best' explanation picked"""
        pass
    
    def test_all_frames_equal_weight(self):
        """All explanation frames have equal weight"""
        pass
'''
        
        return {
            "file": "tests/test_phase_6_boundaries.py",
            "code": code,
            "tests": 11,
            "categories": 5
        }
    
    def _generate_safe_client(self, context: dict) -> Dict:
        """Generate SSEClient safe wrapper"""
        code = '''"""
SSE Safe Client
Exposes only Phase A-C methods, blocks Phase D-G operations
"""


class SSEClient:
    """
    Safe wrapper around SSE
    Only 9 methods permitted (Phase A-C)
    """
    
    def __init__(self, sse_instance):
        self._sse = sse_instance
    
    # PHASE A: Observation (4 methods)
    
    def extract_contradictions(self, text: str):
        """Extract contradictions from text"""
        return self._sse.extract_contradictions(text)
    
    def get_claims(self, text: str):
        """Extract claims"""
        return self._sse.extract_claims(text)
    
    def get_provenance(self, contradiction_id: str):
        """Get provenance for contradiction"""
        return self._sse.get_provenance(contradiction_id)
    
    def navigate_contradictions(self, filters: dict = None):
        """Navigate contradiction space"""
        return self._sse.navigate(filters)
    
    # PHASE B: Reasoning (2 methods)
    
    def explain_contradiction(self, contradiction_id: str, num_frames: int = 5):
        """Generate multiple explanation frames (unranked)"""
        # Returns 5 frames, no ranking
        return self._sse.multi_frame_explain(contradiction_id, num_frames)
    
    def cite_sources(self, contradiction_id: str):
        """Get source citations"""
        return self._sse.cite_sources(contradiction_id)
    
    # PHASE C: Recommendations (3 methods)
    
    def suggest_investigation(self, contradiction_id: str):
        """Suggest areas to investigate (stateless)"""
        return self._sse.suggest_investigation(contradiction_id)
    
    def log_recommendation(self, recommendation: str):
        """Log recommendation (write-only, no outcome tracking)"""
        # FORBIDDEN: measure if user followed it
        return self._sse.log_recommendation(recommendation)
    
    def get_recommendation_log(self):
        """Get recommendation history (no outcome data)"""
        # Returns: [{"recommendation": "...", "timestamp": "..."}]
        # NOT: [{"recommendation": "...", "followed": true}]
        return self._sse.get_recommendation_log()
    
    # FORBIDDEN METHODS (do not exist)
    # measure_recommendation_success()  <- Phase D
    # track_user_action()               <- Phase D
    # update_model()                    <- Phase E
    # get_confidence_score()            <- Phase D
    # filter_by_truth()                 <- Phase C violation
    # rank_explanations()               <- Phase B violation
'''
        
        return {
            "file": "sse/client.py",
            "code": code,
            "methods": 9,
            "forbidden_methods_documented": 6
        }
    
    def _generate_multi_frame(self, context: dict) -> Dict:
        """Generate MultiFrameExplainer"""
        code = '''"""
Multi-Frame Explanation Engine (Phase B)
Generates multiple explanation frames WITHOUT ranking
"""


class MultiFrameExplainer:
    """
    Generates 5 independent explanation frames
    CRITICAL: No ranking, all frames equal
    """
    
    def __init__(self, llm_client):
        self.llm = llm_client
    
    def explain(self, contradiction: dict) -> list[dict]:
        """
        Generate 5 explanation frames
        
        Returns:
            List of 5 frames (NO RANKING, NO CONFIDENCE SCORES)
        """
        frames = [
            self._frame_cultural(contradiction),
            self._frame_temporal(contradiction),
            self._frame_contextual(contradiction),
            self._frame_psychological(contradiction),
            self._frame_research(contradiction)
        ]
        
        # FORBIDDEN: sort, rank, score, filter
        # All frames returned equally
        return frames
    
    def _frame_cultural(self, contradiction: dict) -> dict:
        """Frame 1: Cultural/social perspective"""
        prompt = f"""
        Explain this contradiction from a cultural/social perspective.
        Do not judge which is correct.
        
        Contradiction: {contradiction}
        """
        return {"frame": "cultural", "explanation": self.llm.generate(prompt)}
    
    def _frame_temporal(self, contradiction: dict) -> dict:
        """Frame 2: Temporal (time-based) perspective"""
        prompt = f"""
        Explain how this contradiction might reflect change over time.
        Do not resolve the contradiction.
        
        Contradiction: {contradiction}
        """
        return {"frame": "temporal", "explanation": self.llm.generate(prompt)}
    
    def _frame_contextual(self, contradiction: dict) -> dict:
        """Frame 3: Contextual (situation-dependent) perspective"""
        return {"frame": "contextual", "explanation": "..."}
    
    def _frame_psychological(self, contradiction: dict) -> dict:
        """Frame 4: Psychological perspective"""
        return {"frame": "psychological", "explanation": "..."}
    
    def _frame_research(self, contradiction: dict) -> dict:
        """Frame 5: Research/evidence perspective"""
        return {"frame": "research", "explanation": "..."}
'''
        
        return {
            "file": "sse/multi_frame_explainer.py",
            "code": code,
            "frames": 5,
            "ranking": "NONE (forbidden)"
        }
    
    def _generate_generic_code(self, task: Task) -> Dict:
        """Generic code generation"""
        return {
            "code": f"# Implementation for: {task.description}",
            "status": "generated (generic)"
        }
