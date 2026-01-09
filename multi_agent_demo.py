"""
Multi-Agent System Demo
Shows the orchestration system in action
"""

import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from multi_agent.orchestrator import Orchestrator
from multi_agent.llm_client import LLMPool, LLMClient, LLMProvider
from multi_agent.agents import (
    BoundaryAgent,
    AnalysisAgent,
    CodeAgent,
    TestAgent,
    DocsAgent
)


def setup_llm_pool() -> LLMPool:
    """
    Setup LLM pool (tries API, falls back to local, then mock)
    """
    print("\n" + "="*80)
    print("LLM Setup")
    print("="*80)
    
    pool = LLMPool.create_default_pool()
    
    clients = pool.list_clients()
    if clients:
        print(f"Available LLMs: {', '.join(clients)}")
        for name in clients:
            client = pool.get(name)
            if client:
                print(f"  {name}: {client.provider.value} / {client.model}")
    else:
        print("No LLMs available - using mock")
    
    return pool


def demo_boundary_tests():
    """Demo: Implement boundary test suite"""
    print("\n" + "="*80)
    print("DEMO 1: Implement Boundary Test Suite (with LLM support)")
    print("="*80)
    
    # Setup LLM pool
    pool = setup_llm_pool()
    
    # Initialize orchestrator with LLM pool
    orchestrator = Orchestrator(workspace_path=".", llm_pool=pool)
    
    # Register agents with LLMs
    orchestrator.register_agents({
        "BoundaryAgent": BoundaryAgent(llm_client=pool.get("analysis")),
        "AnalysisAgent": AnalysisAgent(workspace_path=".", llm_client=pool.get("analysis")),
        "CodeAgent": CodeAgent(llm_client=pool.get("code")),
        "TestAgent": TestAgent(),
        "DocsAgent": DocsAgent()
    })
    
    # Execute request
    result = orchestrator.execute("Implement boundary test suite")
    
    print("\n" + "="*80)
    print("RESULT:")
    print("="*80)
    print(result["synthesis"])
    
    return result


def demo_code_review():
    """Demo: Review code for Phase 6 compliance"""
    print("\n" + "="*80)
    print("DEMO 2: Code Review for Boundary Violations")
    print("="*80)
    
    orchestrator = Orchestrator(workspace_path=".")
    
    orchestrator.register_agents({
        "BoundaryAgent": BoundaryAgent(),
        "AnalysisAgent": AnalysisAgent(workspace_path="."),
        "TestAgent": TestAgent(),
        "DocsAgent": DocsAgent()
    })
    
    # Set context for PR review
    orchestrator.set_context("pr_number", 42)
    
    result = orchestrator.execute("Review PR for Phase 6 compliance")
    
    print("\n" + "="*80)
    print("RESULT:")
    print("="*80)
    print(result["synthesis"])
    
    return result


def demo_multi_frame():
    """Demo: Implement multi-frame explanation engine"""
    print("\n" + "="*80)
    print("DEMO 3: Implement Multi-Frame Explanation Engine")
    print("="*80)
    
    orchestrator = Orchestrator(workspace_path=".")
    
    orchestrator.register_agents({
        "BoundaryAgent": BoundaryAgent(),
        "AnalysisAgent": AnalysisAgent(workspace_path="."),
        "CodeAgent": CodeAgent(),
        "TestAgent": TestAgent(),
        "DocsAgent": DocsAgent()
    })
    
    result = orchestrator.execute("Implement multi-frame explanation engine")
    
    print("\n" + "="*80)
    print("RESULT:")
    print("="*80)
    print(result["synthesis"])
    
    return result


def demo_boundary_violation():
    """Demo: Show what happens when violation detected"""
    print("\n" + "="*80)
    print("DEMO 4: Detecting Boundary Violations")
    print("="*80)
    
    # Simulate a violation by injecting bad code
    from multi_agent.sse_validator import AgentValidator
    
    validator = AgentValidator()
    
    # Bad code with forbidden patterns
    bad_code = """
    def track_recommendation_success(user_id, recommendation_id):
        # Track if user followed recommendation
        outcome = measure_user_action(user_id)
        success_rate = calculate_success_rate(recommendation_id)
        update_model_confidence(success_rate)
        return {"outcome": outcome, "success": True}
    """
    
    violations = validator.validate_against_charter(bad_code)
    
    print("\nCode to validate:")
    print("-" * 80)
    print(bad_code)
    
    print("\n" + "="*80)
    print("VIOLATIONS DETECTED:")
    print("="*80)
    
    if violations:
        for v in violations:
            print(f"\n🛑 {v['category'].upper()}")
            print(f"   Pattern: {v['pattern']}")
            print(f"   Message: {v['message']}")
    else:
        print("✅ No violations detected")
    
    return violations


def demo_all():
    """Run all demos"""
    demos = [
        ("Boundary Test Suite", demo_boundary_tests),
        ("Code Review", demo_code_review),
        ("Multi-Frame Engine", demo_multi_frame),
        ("Boundary Violation Detection", demo_boundary_violation)
    ]
    
    results = {}
    
    for name, demo_func in demos:
        try:
            results[name] = demo_func()
            input("\nPress Enter to continue to next demo...")
        except Exception as e:
            print(f"\n⚠️  Error in {name}: {e}")
            import traceback
            traceback.print_exc()
    
    print("\n" + "="*80)
    print("ALL DEMOS COMPLETE")
    print("="*80)
    
    return results


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Multi-Agent System Demo")
    parser.add_argument("--demo", type=int, choices=[1, 2, 3, 4], 
                       help="Run specific demo (1-4)")
    args = parser.parse_args()
    
    if args.demo == 1:
        demo_boundary_tests()
    elif args.demo == 2:
        demo_code_review()
    elif args.demo == 3:
        demo_multi_frame()
    elif args.demo == 4:
        demo_boundary_violation()
    else:
        # Run all demos
        demo_all()
