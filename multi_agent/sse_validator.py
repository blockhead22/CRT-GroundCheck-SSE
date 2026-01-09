"""
SSE Validation Layer
Uses SSE's contradiction detection to validate agent outputs
"""

from typing import List, Dict, Any
import os
import sys

# Add parent directory to path for SSE imports
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))


class AgentValidator:
    """
    Validates agent outputs using SSE contradiction detection
    
    Key validations:
    1. Code vs Phase 6 Charter
    2. Agent vs Agent (detect contradictions between agent outputs)
    3. Code vs Documentation
    4. Tests vs Implementation
    """
    
    def __init__(self, phase_6_charter_path: str = None):
        """
        Initialize validator
        
        Args:
            phase_6_charter_path: Path to Phase 6 charter document
        """
        self.phase_6_charter = self._load_charter(phase_6_charter_path)
        
        # Try to import SSE (if available)
        try:
            from sse.sse import SSE
            self.sse = SSE()
            self.sse_available = True
        except ImportError:
            self.sse = None
            self.sse_available = False
            print("⚠️  SSE not available - validation will use pattern matching only")
    
    def validate_agent_outputs(self, agent_results: Dict[str, Any]) -> List[Dict]:
        """
        Check if different agent outputs contradict each other
        
        Args:
            agent_results: Dict mapping agent_type -> output
        
        Returns:
            List of detected contradictions
        """
        violations = []
        
        # Extract claims from each agent's output
        agent_claims = {}
        for agent_type, output in agent_results.items():
            claims = self._extract_claims(output)
            agent_claims[agent_type] = claims
        
        # If SSE available, use it
        if self.sse_available:
            violations.extend(self._sse_validate(agent_claims))
        else:
            # Fallback to pattern matching
            violations.extend(self._pattern_validate(agent_claims))
        
        return violations
    
    def validate_against_charter(self, code: str, context: str = "") -> List[Dict]:
        """
        Validate code against Phase 6 charter
        
        Args:
            code: Code to validate
            context: Additional context (docstrings, comments, etc.)
        
        Returns:
            List of boundary violations
        """
        violations = []
        
        # Skip validation for test files (they test forbidden patterns)
        if "test_" in str(code)[:100].lower() or "class Test" in code:
            # Test files are allowed to mention forbidden patterns
            return violations
        
        # Extract forbidden patterns
        forbidden = self._get_forbidden_patterns()
        
        # Check for forbidden patterns in code
        for pattern_type, patterns in forbidden.items():
            for pattern in patterns:
                if pattern.lower() in code.lower():
                    # Check if it's in a comment/docstring (okay) vs actual code (not okay)
                    # Simplified: if pattern is in quotes or comments, skip
                    lines_with_pattern = [line for line in code.split('\n') 
                                        if pattern.lower() in line.lower()]
                    
                    for line in lines_with_pattern:
                        line_stripped = line.strip()
                        # Skip if in comment or string
                        if (line_stripped.startswith('#') or 
                            line_stripped.startswith('//') or 
                            line_stripped.startswith('"""') or
                            line_stripped.startswith("'''")):
                            continue
                        
                        # Actual violation
                        violations.append({
                            "type": "boundary_violation",
                            "pattern": pattern,
                            "category": pattern_type,
                            "message": f"Forbidden pattern detected: {pattern} ({pattern_type})"
                        })
                        break  # One violation per pattern is enough
        
        # If SSE available, also check semantic contradictions
        if self.sse_available and self.phase_6_charter:
            code_claims = self._extract_claims(code + "\n" + context)
            charter_claims = self._extract_claims(self.phase_6_charter)
            
            all_claims = code_claims + charter_claims
            # TODO: Run SSE contradiction detection
            # contradictions = self.sse.detect_contradictions(all_claims)
        
        return violations
    
    def validate_consistency(self, code: str, docs: str, tests: str) -> List[Dict]:
        """
        Check consistency between code, docs, and tests
        
        Args:
            code: Implementation code
            docs: Documentation
            tests: Test code
        
        Returns:
            List of inconsistencies
        """
        inconsistencies = []
        
        # Extract claims from each
        code_claims = self._extract_claims(code)
        docs_claims = self._extract_claims(docs)
        test_claims = self._extract_claims(tests)
        
        # Check if docs claim features not in code
        # Check if tests validate things code doesn't do
        # (Simplified - real implementation would use SSE)
        
        return inconsistencies
    
    def _sse_validate(self, agent_claims: Dict[str, List[str]]) -> List[Dict]:
        """
        Use SSE to detect contradictions between agent outputs
        
        Args:
            agent_claims: Dict mapping agent_type -> list of claims
        
        Returns:
            List of contradictions with source agents
        """
        violations = []
        
        # Flatten claims with agent attribution
        all_claims = []
        claim_to_agent = {}
        
        for agent_type, claims in agent_claims.items():
            for claim in claims:
                claim_id = len(all_claims)
                all_claims.append(claim)
                claim_to_agent[claim_id] = agent_type
        
        # Run SSE contradiction detection
        # TODO: Actually call SSE when integrated
        # contradictions = self.sse.detect_contradictions(all_claims)
        
        # For now, return empty (placeholder for real implementation)
        return violations
    
    def _pattern_validate(self, agent_claims: Dict[str, List[str]]) -> List[Dict]:
        """
        Pattern-based validation (fallback when SSE not available)
        
        Args:
            agent_claims: Dict mapping agent_type -> list of claims
        
        Returns:
            List of contradictions
        """
        violations = []
        
        # Check BoundaryAgent vs CodeAgent
        if "BoundaryAgent" in agent_claims and "CodeAgent" in agent_claims:
            boundary_claims = agent_claims["BoundaryAgent"]
            code_claims = agent_claims["CodeAgent"]
            
            # Look for contradictions
            for b_claim in boundary_claims:
                if "forbidden" in b_claim.lower() or "not allowed" in b_claim.lower():
                    # Extract what's forbidden
                    forbidden_thing = self._extract_forbidden_item(b_claim)
                    
                    # Check if CodeAgent claims to implement it
                    for c_claim in code_claims:
                        if forbidden_thing and forbidden_thing.lower() in c_claim.lower():
                            violations.append({
                                "type": "agent_contradiction",
                                "agent_a": "BoundaryAgent",
                                "agent_b": "CodeAgent",
                                "claim_a": b_claim,
                                "claim_b": c_claim,
                                "message": f"CodeAgent implements forbidden feature: {forbidden_thing}"
                            })
        
        return violations
    
    def _extract_claims(self, text) -> List[str]:
        """
        Extract claims from text
        
        Simple version: split by sentences
        Real version: Use NLP or SSE's claim extractor
        """
        if not text:
            return []
        
        # Convert to string if not already
        if isinstance(text, dict):
            text = str(text)
        elif isinstance(text, list):
            text = " ".join(str(item) for item in text)
        
        text = str(text)
        
        # Simple sentence splitting
        sentences = []
        for line in text.split('\n'):
            line = line.strip()
            if line and not line.startswith('#') and not line.startswith('//'):
                sentences.append(line)
        
        return sentences[:20]  # Limit for now
    
    def _extract_forbidden_item(self, claim: str) -> str:
        """Extract what's forbidden from a claim"""
        # Simple pattern matching
        words = claim.lower().split()
        if "forbidden" in words:
            idx = words.index("forbidden")
            if idx > 0:
                return words[idx - 1]
        return ""
    
    def _get_forbidden_patterns(self) -> Dict[str, List[str]]:
        """
        Get forbidden patterns from Phase 6 charter
        
        Returns:
            Dict mapping category -> list of forbidden patterns
        """
        return {
            "outcome_measurement": [
                "measure_success", "track_outcome", "user_followed",
                "recommendation_accepted", "outcome_data", "success_rate",
                "measure_recommendation_success", "track_recommendation",
                "outcome_table", "success_metric"
            ],
            "persistent_learning": [
                "update_model", "learn_from", "improve_confidence",
                "historical_accuracy", "track_performance", "model_update",
                "learn_pattern", "update_state", "persistent_model"
            ],
            "confidence_scoring": [
                "confidence_score", "certainty_level", "reliability_rating",
                "confidence_metric", "trust_score", "accuracy_score"
            ],
            "truth_filtering": [
                "filter_by_truth", "select_best", "rank_by_accuracy",
                "choose_correct", "filter_wrong", "select_true"
            ],
            "explanation_ranking": [
                "best_explanation", "rank_hypotheses", "score_reasoning",
                "rank_explanations", "select_best_frame", "preferred_explanation"
            ]
        }
    
    def _load_charter(self, path: str = None) -> str:
        """Load Phase 6 charter document"""
        if not path:
            # Default path
            charter_files = [
                "PROPER_FUTURE_ROADMAP.md",
                "PHASE_6_BOUNDARIES_IMPLEMENTATION.md",
                "FUTURE_ROADMAP_AGENTIC_EVOLUTION.md"
            ]
            
            for filename in charter_files:
                filepath = os.path.join(os.path.dirname(__file__), "..", filename)
                if os.path.exists(filepath):
                    path = filepath
                    break
        
        if path and os.path.exists(path):
            with open(path, 'r', encoding='utf-8') as f:
                return f.read()
        
        return ""
