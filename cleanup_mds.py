"""
Clean up all markdown files using the multi-agent system
"""

import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from multi_agent.orchestrator import Orchestrator
from multi_agent.llm_client import LLMPool
from multi_agent.agents import (
    BoundaryAgent,
    AnalysisAgent,
    CodeAgent,
    TestAgent,
    DocsAgent
)


def main():
    """Clean up all markdown documentation files"""
    print("\n" + "="*80)
    print("MARKDOWN CLEANUP - Using Multi-Agent System")
    print("="*80)
    
    # Setup LLM pool
    print("\nSetting up LLM pool...")
    pool = LLMPool.create_default_pool()
    
    clients = pool.list_clients()
    if clients:
        print(f"Available LLMs: {', '.join(clients)}")
    
    # Initialize orchestrator with LLM pool
    print("\nInitializing orchestrator...")
    orchestrator = Orchestrator(workspace_path=".", llm_pool=pool)
    
    # Register agents with LLMs
    orchestrator.register_agents({
        "BoundaryAgent": BoundaryAgent(llm_client=pool.get("analysis")),
        "AnalysisAgent": AnalysisAgent(workspace_path=".", llm_client=pool.get("analysis")),
        "DocsAgent": DocsAgent(),
    })
    
    # Execute cleanup task
    print("\nExecuting markdown cleanup task...")
    result = orchestrator.execute(
        "Organize and clean up all markdown documentation files: "
        "1) Identify duplicate or redundant MD files, "
        "2) Consolidate related documentation, "
        "3) Archive outdated phase reports, "
        "4) Create a master index of current documentation, "
        "5) Ensure all active docs follow consistent formatting"
    )
    
    print("\n" + "="*80)
    print("CLEANUP RESULT:")
    print("="*80)
    print(result["synthesis"])
    
    if not result["success"]:
        print("\n⚠️  VIOLATIONS DETECTED:")
        for v in result.get("violations", []):
            print(f"  - {v}")
    
    return result


if __name__ == "__main__":
    main()
