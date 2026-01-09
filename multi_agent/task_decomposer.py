"""
Task Decomposition Engine
Breaks complex user requests into agent-specific subtasks
"""

from typing import List
from .task import Task


class TaskDecomposer:
    """
    Analyzes user requests and creates execution plans
    
    Example:
        decomposer = TaskDecomposer()
        tasks = decomposer.decompose("Implement boundary test suite")
        
        # Returns:
        # [
        #   Task(1, BoundaryAgent, "Define forbidden patterns"),
        #   Task(2, CodeAgent, "Write test file", dependencies=[1]),
        #   Task(3, TestAgent, "Run tests", dependencies=[2]),
        # ]
    """
    
    def __init__(self):
        self.task_patterns = self._load_patterns()
    
    def decompose(self, user_request: str, context: dict = None) -> List[Task]:
        """
        Break user request into subtasks
        
        Args:
            user_request: What the user wants done
            context: Additional context (project phase, workspace state, etc.)
        
        Returns:
            List of tasks with dependencies
        """
        context = context or {}
        
        # Pattern matching for common SSE development tasks
        if "boundary test" in user_request.lower():
            return self._decompose_boundary_tests(context)
        
        elif "implement" in user_request.lower() and "roadmap" in user_request.lower():
            return self._decompose_roadmap_feature(user_request, context)
        
        elif "review" in user_request.lower() or "pr" in user_request.lower():
            return self._decompose_code_review(context)
        
        elif "multi-frame" in user_request.lower() or "explanation" in user_request.lower():
            return self._decompose_multi_frame(context)
        
        else:
            # Generic decomposition
            return self._decompose_generic(user_request, context)
    
    def _decompose_boundary_tests(self, context: dict) -> List[Task]:
        """Decompose: Implement boundary test suite"""
        return [
            Task(
                id=1,
                agent_type="BoundaryAgent",
                description="Define all forbidden patterns (outcome measurement, persistent state, etc.)",
                dependencies=[],
                context={**context, "output": "forbidden_patterns.json"}
            ),
            Task(
                id=2,
                agent_type="CodeAgent",
                description="Write tests/test_phase_6_boundaries.py with 20+ boundary tests",
                dependencies=[1],
                context={**context, "template": "boundary_test_template"}
            ),
            Task(
                id=3,
                agent_type="TestAgent",
                description="Run boundary tests and ensure they catch violations",
                dependencies=[2],
                context={**context, "validation": True}
            ),
            Task(
                id=4,
                agent_type="DocsAgent",
                description="Update test documentation with boundary test suite",
                dependencies=[2],
                context={**context, "doc_file": "docs/boundary_tests.md"}
            ),
            Task(
                id=5,
                agent_type="AnalysisAgent",
                description="Search existing codebase for any boundary violations",
                dependencies=[1],
                context={**context, "scan_mode": "deep"}
            )
        ]
    
    def _decompose_roadmap_feature(self, user_request: str, context: dict) -> List[Task]:
        """Decompose: Implement feature from roadmap"""
        # Extract feature name from request
        feature_name = self._extract_feature_name(user_request)
        
        return [
            Task(
                id=1,
                agent_type="AnalysisAgent",
                description=f"Read roadmap pseudocode for {feature_name}",
                dependencies=[],
                context={**context, "feature": feature_name}
            ),
            Task(
                id=2,
                agent_type="BoundaryAgent",
                description=f"Verify {feature_name} doesn't violate Phase 6 boundaries",
                dependencies=[1],
                context={**context, "boundary_check": True}
            ),
            Task(
                id=3,
                agent_type="CodeAgent",
                description=f"Implement {feature_name} based on roadmap pseudocode",
                dependencies=[1, 2],
                context={**context, "follow_pseudocode": True}
            ),
            Task(
                id=4,
                agent_type="TestAgent",
                description=f"Write and run tests for {feature_name}",
                dependencies=[3],
                context={**context, "coverage_target": 100}
            ),
            Task(
                id=5,
                agent_type="DocsAgent",
                description=f"Document {feature_name} usage and API",
                dependencies=[3],
                context={**context, "api_docs": True}
            )
        ]
    
    def _decompose_code_review(self, context: dict) -> List[Task]:
        """Decompose: Review PR for Phase 6 compliance"""
        pr_number = context.get("pr_number", "unknown")
        
        return [
            Task(
                id=1,
                agent_type="AnalysisAgent",
                description=f"Get PR #{pr_number} diff and extract changes",
                dependencies=[],
                context={**context, "pr": pr_number}
            ),
            Task(
                id=2,
                agent_type="BoundaryAgent",
                description="Scan PR for forbidden patterns",
                dependencies=[1],
                context={**context, "strict_mode": True}
            ),
            Task(
                id=3,
                agent_type="TestAgent",
                description="Run boundary tests on PR code",
                dependencies=[1],
                context={**context, "test_pr_code": True}
            ),
            Task(
                id=4,
                agent_type="DocsAgent",
                description="Check if documentation was updated consistently",
                dependencies=[1],
                context={**context, "check_docs": True}
            )
        ]
    
    def _decompose_multi_frame(self, context: dict) -> List[Task]:
        """Decompose: Implement multi-frame explanation engine"""
        return [
            Task(
                id=1,
                agent_type="AnalysisAgent",
                description="Read multi-frame pseudocode from roadmap",
                dependencies=[],
                context={**context, "feature": "MultiFrameExplainer"}
            ),
            Task(
                id=2,
                agent_type="BoundaryAgent",
                description="Define constraints: no ranking, all frames equal weight",
                dependencies=[],
                context={**context, "constraint": "equal_frames"}
            ),
            Task(
                id=3,
                agent_type="CodeAgent",
                description="Implement MultiFrameExplainer with 5 independent framings",
                dependencies=[1, 2],
                context={**context, "num_frames": 5}
            ),
            Task(
                id=4,
                agent_type="TestAgent",
                description="Test that all 5 frames are generated and none ranked",
                dependencies=[3],
                context={**context, "validate_no_ranking": True}
            ),
            Task(
                id=5,
                agent_type="DocsAgent",
                description="Document multi-frame system usage",
                dependencies=[3],
                context={**context, "include_examples": True}
            )
        ]
    
    def _decompose_generic(self, user_request: str, context: dict) -> List[Task]:
        """Generic decomposition for unrecognized requests"""
        # Simple single-agent task
        return [
            Task(
                id=1,
                agent_type="AnalysisAgent",
                description=f"Analyze request: {user_request}",
                dependencies=[],
                context=context
            )
        ]
    
    def _extract_feature_name(self, request: str) -> str:
        """Extract feature name from user request"""
        # Simple extraction (can be made smarter with NLP)
        keywords = ["multi-frame", "boundary test", "SSEClient", "audit"]
        for keyword in keywords:
            if keyword in request.lower():
                return keyword
        return "feature"
    
    def _load_patterns(self) -> dict:
        """Load common task patterns (future: load from config)"""
        return {
            "boundary": self._decompose_boundary_tests,
            "roadmap": self._decompose_roadmap_feature,
            "review": self._decompose_code_review,
            "multi_frame": self._decompose_multi_frame
        }
