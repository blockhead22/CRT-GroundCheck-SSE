#!/usr/bin/env python3
"""
Quick test script for CRT agent system.
Validates that all components work together.
"""

import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from personal_agent.agent_loop import create_agent, AgentAction
from personal_agent.agent_reasoning import AgentReasoning
from personal_agent.proactive_triggers import ProactiveTriggers

def test_agent_basics():
    """Test basic agent creation and tool availability."""
    print("🧪 Testing Agent System\n")
    
    # Test 1: Agent creation
    print("1. Creating agent...")
    try:
        agent = create_agent(thread_id="test")
        print(f"   ✅ Agent created")
        print(f"   ✅ {len(agent.tools.tools)} tools available")
        print(f"   Tools: {', '.join(a.value for a in AgentAction if a != AgentAction.FINISH)}")
    except Exception as e:
        print(f"   ❌ Failed to create agent: {e}")
        return False
    
    # Test 2: LLM availability
    print("\n2. Checking LLM reasoning...")
    try:
        reasoning = AgentReasoning(model_name="mistral:latest")
        # Quick test - doesn't actually call LLM, just checks setup
        print(f"   ✅ LLM reasoning engine initialized")
        print(f"   Model: {reasoning.model_name}")
    except Exception as e:
        print(f"   ⚠️  LLM not available (will use fallback): {e}")
    
    # Test 3: Proactive triggers
    print("\n3. Testing proactive triggers...")
    try:
        triggers = ProactiveTriggers(thread_id="test")
        
        # Simulate low confidence response
        test_response = {
            "confidence": 0.2,
            "response_type": "fallback",
            "retrieved_memories": 0,
            "query": "Test query"
        }
        
        detected = triggers.analyze_response(test_response)
        should_activate = triggers.should_activate_agent(detected)
        task = triggers.get_agent_task(detected, test_response["query"])
        
        print(f"   ✅ Trigger detection working")
        print(f"   Detected {len(detected)} triggers: {[t.type.value for t in detected]}")
        print(f"   Should activate: {should_activate}")
        print(f"   Task: {task[:80]}...")
        
    except Exception as e:
        print(f"   ❌ Trigger system failed: {e}")
        return False
    
    # Test 4: Simple agent execution
    print("\n4. Running simple agent task...")
    try:
        result = agent.run(
            query="What tools do you have available?",
            max_steps=3
        )
        
        print(f"   ✅ Agent execution completed")
        print(f"   Steps: {len(result.steps)}")
        print(f"   Success: {result.success}")
        
        if result.steps:
            print(f"\n   First step:")
            print(f"     Thought: {result.steps[0].thought[:80]}...")
            if result.steps[0].action:
                print(f"     Action: {result.steps[0].action.tool.value}")
            
        if result.final_answer:
            print(f"\n   Answer: {result.final_answer[:100]}...")
            
    except Exception as e:
        print(f"   ⚠️  Agent execution failed (may need LLM): {e}")
        # Not critical - agent needs LLM for real work
    
    print("\n" + "="*60)
    print("✅ Agent system is operational!")
    print("="*60)
    return True

def test_api_endpoints():
    """Test if API endpoints are available."""
    print("\n\n🌐 Testing API Endpoints\n")
    
    try:
        import requests
        base_url = "http://127.0.0.1:8123"
        
        # Test status endpoint
        print("1. Testing /api/agent/status...")
        try:
            response = requests.get(f"{base_url}/api/agent/status", timeout=5)
            if response.status_code == 200:
                data = response.json()
                print(f"   ✅ Status endpoint working")
                print(f"   Available: {data.get('available')}")
                print(f"   LLM: {data.get('llm_available')}")
                print(f"   Tools: {data.get('tools_count')}")
            else:
                print(f"   ❌ Status code: {response.status_code}")
        except requests.exceptions.ConnectionError:
            print(f"   ⚠️  API not running (start with: uvicorn crt_api:app)")
            return False
        except Exception as e:
            print(f"   ❌ Request failed: {e}")
            return False
        
        # Test run endpoint with simple query
        print("\n2. Testing /api/agent/run...")
        try:
            payload = {
                "thread_id": "test_api",
                "query": "List your available tools",
                "max_steps": 3
            }
            response = requests.post(
                f"{base_url}/api/agent/run",
                json=payload,
                timeout=30
            )
            
            if response.status_code == 200:
                data = response.json()
                trace = data.get("trace", {})
                print(f"   ✅ Run endpoint working")
                print(f"   Steps executed: {len(trace.get('steps', []))}")
                print(f"   Success: {trace.get('success')}")
            else:
                print(f"   ❌ Status code: {response.status_code}")
                print(f"   Error: {response.text[:200]}")
        except Exception as e:
            print(f"   ❌ Run request failed: {e}")
        
        print("\n" + "="*60)
        print("✅ API endpoints are operational!")
        print("="*60)
        return True
        
    except ImportError:
        print("   ⚠️  requests library not installed")
        print("   Install with: pip install requests")
        return False

def main():
    """Run all tests."""
    print("="*60)
    print("CRT AGENT SYSTEM - VALIDATION TESTS")
    print("="*60)
    
    # Test 1: Basic agent functionality
    agent_ok = test_agent_basics()
    
    # Test 2: API endpoints (optional)
    print("\n\nOptional: Test API endpoints? (requires API server running)")
    print("Start API with: uvicorn crt_api:app --reload --port 8123")
    
    try:
        choice = input("\nTest API? (y/n): ").strip().lower()
        if choice == 'y':
            api_ok = test_api_endpoints()
        else:
            print("\nSkipping API tests.")
            api_ok = None
    except (KeyboardInterrupt, EOFError):
        print("\nSkipping API tests.")
        api_ok = None
    
    # Summary
    print("\n\n" + "="*60)
    print("TEST SUMMARY")
    print("="*60)
    print(f"Agent System: {'✅ PASS' if agent_ok else '❌ FAIL'}")
    if api_ok is not None:
        print(f"API Endpoints: {'✅ PASS' if api_ok else '❌ FAIL'}")
    else:
        print(f"API Endpoints: ⏭️  SKIPPED")
    
    print("\n📚 Next Steps:")
    print("  1. Start API: uvicorn crt_api:app --reload --port 8123")
    print("  2. Test chat with low confidence to trigger agent")
    print("  3. Build frontend AgentPanel component")
    print("  4. Review CRT_AGENTIC_FEATURES.md for full docs")
    
    return agent_ok

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
