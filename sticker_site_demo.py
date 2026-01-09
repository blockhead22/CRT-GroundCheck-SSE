"""
Multi-Agent System Demo: Build Sticker Business Website
Shows CodeAgent, AnalysisAgent, and DocsAgent working together
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
    DocsAgent
)


def setup_llm_pool() -> LLMPool:
    """Setup LLM pool (auto-detects available providers)"""
    print("\n" + "="*80)
    print("LLM SETUP")
    print("="*80)
    
    pool = LLMPool.create_default_pool()
    
    clients = pool.list_clients()
    if clients:
        print(f"✓ Available LLMs: {', '.join(clients)}")
        for name in clients:
            client = pool.get(name)
            if client:
                print(f"  • {name}: {client.provider.value} / {client.model}")
    else:
        print("ℹ No API LLMs detected - using mock provider")
        print("  (For real LLM integration, set OPENAI_API_KEY or install Ollama)")
    
    return pool


def demo_sticker_website():
    """Demo: Build complete sticker business website"""
    print("\n" + "="*80)
    print("DEMO: Build Sticker Business Website")
    print("="*80)
    print("\nRequest: Create HTML, CSS, and content for a sticker business\n")
    
    # Setup LLM pool
    pool = setup_llm_pool()
    
    # Initialize orchestrator
    orchestrator = Orchestrator(workspace_path=".", llm_pool=pool)
    
    # Register agents with LLM assignments
    print("\n" + "="*80)
    print("REGISTERING AGENTS")
    print("="*80)
    
    agents = {
        "BoundaryAgent": BoundaryAgent(llm_client=pool.get("analysis")),
        "AnalysisAgent": AnalysisAgent(workspace_path=".", llm_client=pool.get("analysis")),
        "CodeAgent": CodeAgent(llm_client=pool.get("code")),
        "DocsAgent": DocsAgent()
    }
    
    orchestrator.register_agents(agents)
    
    for name, agent in agents.items():
        llm_status = "with LLM" if hasattr(agent, 'llm') and agent.llm else "template-based"
        print(f"  ✓ {name}: {llm_status}")
    
    # Execute request
    print("\n" + "="*80)
    print("EXECUTING REQUEST")
    print("="*80)
    print("\nThe orchestrator will:")
    print("  1. Decompose task into subtasks")
    print("  2. Route tasks to appropriate agents")
    print("  3. Execute in parallel waves (respecting dependencies)")
    print("  4. Validate outputs (BoundaryAgent)")
    print("  5. Synthesize final result\n")
    
    result = orchestrator.execute(
        "Create a complete website for a sticker business called 'Sticky Vibes'. "
        "Include: 1) HTML structure with header, hero section, product gallery, about section, and footer. "
        "2) Professional CSS with modern design, responsive layout, and animations. "
        "3) Engaging marketing content describing the business and products."
    )
    
    # Display results
    print("\n" + "="*80)
    print("EXECUTION SUMMARY")
    print("="*80)
    print(result["synthesis"])
    
    # Extract and save generated files from synthesis text
    print("\n" + "="*80)
    print("EXTRACTING GENERATED CODE")
    print("="*80)
    
    # The synthesis contains agent outputs - let's parse them
    synthesis_text = result["synthesis"]
    
    # Extract HTML from CodeAgent output in synthesis
    html_start = synthesis_text.find("'<!DOCTYPE html>")
    if html_start == -1:
        html_start = synthesis_text.find('"<!DOCTYPE html>')
    
    html_content = None
    css_content = None
    
    if html_start > 0:
        # Find the end of the HTML code block
        html_end = synthesis_text.find("'", html_start + 2)
        if html_end > html_start:
            html_raw = synthesis_text[html_start+1:html_end]
            # Unescape newlines
            html_content = html_raw.replace('\\n', '\n').replace("\\'", "'")
            print(f"✓ Extracted HTML ({len(html_content)} chars)")
    
    # Extract CSS
    css_start = synthesis_text.find("'* {\\n")
    if css_start == -1:
        css_start = synthesis_text.find('"* {\\n')
    
    if css_start > 0:
        css_end = synthesis_text.find("'", css_start + 2)
        if css_end > css_start:
            css_raw = synthesis_text[css_start+1:css_end]
            css_content = css_raw.replace('\\n', '\n').replace("\\'", "'")
            print(f"✓ Extracted CSS ({len(css_content)} chars)")
    
    # If extraction from synthesis failed, generate manually
    if not html_content or not css_content:
        print("\n⚠ Synthesis extraction failed, generating code manually...")
        
        from multi_agent.agents.code_agent import CodeAgent as CodeGenAgent
        from multi_agent.task import Task
        
        code_agent = CodeGenAgent()
        
        if not html_content:
            html_task = Task(
                id=100,
                agent_type="CodeAgent",
                description="Generate HTML",
                dependencies=[],
                context={"business": "Sticky Vibes", "code_type": "html"}
            )
            html_result = code_agent.execute(html_task)
            html_content = html_result.get("code", "")
            print(f"✓ Generated HTML ({len(html_content)} chars)")
        
        if not css_content:
            css_task = Task(
                id=101,
                agent_type="CodeAgent",
                description="Generate CSS",
                dependencies=[],
                context={"business": "Sticky Vibes", "code_type": "css"}
            )
            css_result = code_agent.execute(css_task)
            css_content = css_result.get("code", "")
            print(f"✓ Generated CSS ({len(css_content)} chars)")
    
    # Save files
    output_dir = "sticker_business_website"
    os.makedirs(output_dir, exist_ok=True)
    
    if html_content:
        html_path = os.path.join(output_dir, "index.html")
        with open(html_path, "w", encoding="utf-8") as f:
            f.write(html_content)
        print(f"\n✓ Saved: {html_path}")
    
    if css_content:
        css_path = os.path.join(output_dir, "styles.css")
        with open(css_path, "w", encoding="utf-8") as f:
            f.write(css_content)
        print(f"✓ Saved: {css_path}")
    
    # Display preview
    if html_content:
        print("\n" + "="*80)
        print("HTML PREVIEW (first 500 chars)")
        print("="*80)
        print(html_content[:500] + "..." if len(html_content) > 500 else html_content)
    
    if css_content:
        print("\n" + "="*80)
        print("CSS PREVIEW (first 500 chars)")
        print("="*80)
        print(css_content[:500] + "..." if len(css_content) > 500 else css_content)
    
    print("\n" + "="*80)
    print("DEMO COMPLETE")
    print("="*80)
    print(f"\nOpen {os.path.join(output_dir, 'index.html')} in a browser to view the website!")
    
    return result


if __name__ == "__main__":
    demo_sticker_website()
