"""
BoundaryAgent
Enforces Phase 6 boundaries and detects forbidden patterns
"""

from typing import List, Dict, Optional
from .base_agent import BaseAgent
from ..task import Task
from ..llm_client import LLMClient


class BoundaryAgent(BaseAgent):
    """
    Phase 6 enforcement agent
    
    Responsibilities:
    - Define forbidden patterns
    - Scan code for violations
    - Validate against charter
    - Generate violation reports
    """
    
    def __init__(self, llm_client: Optional[LLMClient] = None):
        super().__init__("BoundaryAgent")
        self.forbidden_patterns = self._load_forbidden_patterns()
        self.llm = llm_client  # Optional LLM for semantic analysis
    
    def execute(self, task: Task) -> Dict:
        """
        Execute boundary-related task
        
        Tasks:
        - "Define forbidden patterns" -> return pattern definitions
        - "Scan for violations" -> scan code and return violations
        - "Verify feature compliance" -> check feature against boundaries
        """
        self.log(f"Executing: {task.description[:50]}")
        
        description = task.description.lower()
        
        if "define" in description and "forbidden" in description:
            return self._define_forbidden_patterns()
        
        elif "scan" in description or "check" in description:
            code = task.context.get("code", "")
            return self._scan_for_violations(code)
        
        elif "verify" in description:
            feature = task.context.get("feature", "")
            return self._verify_feature(feature)
        
        else:
            # Generic boundary check
            return self._define_forbidden_patterns()
    
    def _define_forbidden_patterns(self) -> Dict:
        """Return forbidden pattern definitions"""
        return {
            "outcome_measurement": {
                "description": "Measuring whether recommendations worked",
                "patterns": [
                    "measure_success", "track_outcome", "user_followed",
                    "recommendation_accepted", "outcome_data", "success_rate"
                ],
                "rationale": "Phase D violation - creates optimization feedback loop"
            },
            "persistent_learning": {
                "description": "Learning from outcomes to improve future outputs",
                "patterns": [
                    "update_model", "learn_from", "improve_confidence",
                    "historical_accuracy", "save_state", "model_update"
                ],
                "rationale": "Phase E violation - leads to confirmation bias"
            },
            "confidence_scoring": {
                "description": "Assigning confidence/certainty scores",
                "patterns": [
                    "confidence_score", "certainty_level", "reliability_rating",
                    "trust_score", "accuracy_metric"
                ],
                "rationale": "Phase D violation - implies measurement of truth"
            },
            "truth_filtering": {
                "description": "Filtering contradictions by perceived truth",
                "patterns": [
                    "filter_by_truth", "select_best", "rank_by_accuracy",
                    "filter_wrong", "choose_correct"
                ],
                "rationale": "Phase C violation - SSE shows all contradictions equally"
            },
            "explanation_ranking": {
                "description": "Ranking explanations by quality/likelihood",
                "patterns": [
                    "best_explanation", "rank_hypotheses", "score_reasoning",
                    "preferred_explanation", "select_best_frame"
                ],
                "rationale": "Phase B violation - all explanations must be shown equally"
            }
        }
    
    def _scan_for_violations(self, code: str) -> Dict:
        """
        Scan code for forbidden patterns
        
        Returns:
            Dict with violations found
        """
        violations = []
        
        code_lower = code.lower()
        
        # Pattern-based detection
        for category, data in self.forbidden_patterns.items():
            for pattern in data["patterns"]:
                if pattern in code_lower:
                    violations.append({
                        "category": category,
                        "pattern": pattern,
                        "message": f"Forbidden pattern '{pattern}' detected",
                        "rationale": data["rationale"]
                    })
        
        # LLM-based semantic analysis (if available)
        if self.llm and code.strip():
            self.log("Using LLM for semantic boundary analysis...")
            try:
                analysis = self.llm.analyze_code(code, analysis_type="boundaries")
                # Parse LLM response for additional insights
                # (In production, would structure this better)
                if "violation" in analysis.lower() or "forbidden" in analysis.lower():
                    violations.append({
                        "category": "semantic_analysis",
                        "pattern": "LLM-detected",
                        "message": f"LLM detected potential violation: {analysis[:200]}",
                        "rationale": "Semantic analysis by LLM"
                    })
            except Exception as e:
                self.log(f"LLM analysis error: {e}")
        
        return {
            "violations": violations,
            "compliant": len(violations) == 0,
            "scanned_patterns": sum(len(d["patterns"]) for d in self.forbidden_patterns.values()),
            "llm_used": self.llm is not None
        }
    
    def _verify_feature(self, feature_name: str) -> Dict:
        """
        Verify feature doesn't violate boundaries
        
        Returns:
            Verification result
        """
        # Check feature name against forbidden concepts
        feature_lower = feature_name.lower()
        
        violations = []
        for category, data in self.forbidden_patterns.items():
            if any(pattern in feature_lower for pattern in data["patterns"]):
                violations.append({
                    "category": category,
                    "message": f"Feature name '{feature_name}' contains forbidden concept",
                    "rationale": data["rationale"]
                })
        
        return {
            "feature": feature_name,
            "compliant": len(violations) == 0,
            "violations": violations,
            "recommendation": "APPROVED" if len(violations) == 0 else "REJECTED"
        }
    
    def _load_forbidden_patterns(self) -> Dict:
        """Load forbidden patterns (from config or hardcoded)"""
        return {
            "outcome_measurement": {
                "patterns": [
                    "measure_success", "track_outcome", "user_followed",
                    "recommendation_accepted", "outcome_data", "success_rate",
                    "measure_recommendation", "track_user_action"
                ],
                "rationale": "Phase D - outcome feedback creates optimization loop"
            },
            "persistent_learning": {
                "patterns": [
                    "update_model", "learn_from", "improve_confidence",
                    "save_learned", "model_update", "persistent_state"
                ],
                "rationale": "Phase E - learning leads to confirmation bias"
            },
            "confidence_scoring": {
                "patterns": [
                    "confidence", "certainty", "reliability_score",
                    "trust_metric", "accuracy_rating"
                ],
                "rationale": "Implies measurement of truth"
            },
            "truth_filtering": {
                "patterns": [
                    "filter_by_truth", "select_correct", "remove_wrong",
                    "rank_accuracy", "best_claim"
                ],
                "rationale": "SSE shows all contradictions, doesn't filter"
            },
            "explanation_ranking": {
                "patterns": [
                    "best_explanation", "rank_hypotheses", "top_frame",
                    "preferred_reasoning", "score_explanation"
                ],
                "rationale": "All explanations shown equally"
            }
        }
