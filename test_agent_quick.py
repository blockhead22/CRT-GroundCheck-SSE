#!/usr/bin/env python3
"""Quick test to verify agent system works"""
import requests
import json

BASE_URL = "http://127.0.0.1:8123"

print("=" * 60)
print("QUICK AGENT TEST")
print("=" * 60)

# Test 1: Agent status
print("\n1. Checking agent status...")
try:
    r = requests.get(f"{BASE_URL}/api/agent/status", timeout=5)
    if r.status_code == 200:
        data = r.json()
        print(f"   ✅ Agent available: {data.get('available')}")
        print(f"   ✅ Tools count: {data.get('tools_count')}")
        print(f"   LLM available: {data.get('llm_available')}")
    else:
        print(f"   ❌ Status code: {r.status_code}")
        exit(1)
except Exception as e:
    print(f"   ❌ Error: {e}")
    print("\n⚠️  Is the API running? Start it with:")
    print("   uvicorn crt_api:app --reload --port 8123")
    exit(1)

# Test 2: Send a chat message that should trigger agent
print("\n2. Sending test message (should trigger low confidence)...")
try:
    payload = {
        "thread_id": "test_agent",
        "message": "What is quantum entanglement?"  # Likely not in memory
    }
    r = requests.post(f"{BASE_URL}/api/chat/send", json=payload, timeout=30)
    
    if r.status_code == 200:
        data = r.json()
        metadata = data.get("metadata", {})
        
        print(f"   ✅ Response received")
        print(f"   Confidence: {metadata.get('confidence')}")
        print(f"   Agent activated: {metadata.get('agent_activated')}")
        
        if metadata.get("agent_activated"):
            print("\n   🎉 AGENT EXECUTED!")
            trace = metadata.get("agent_trace", {})
            print(f"   Steps taken: {len(trace.get('steps', []))}")
            print(f"   Success: {trace.get('success')}")
            
            if trace.get('steps'):
                print("\n   First step:")
                step1 = trace['steps'][0]
                print(f"     💭 Thought: {step1.get('thought', 'N/A')[:60]}...")
                if step1.get('action'):
                    print(f"     ⚡ Action: {step1['action'].get('tool')}")
        else:
            print("\n   ℹ️  Agent did not activate (confidence may be high enough)")
    else:
        print(f"   ❌ Error: {r.status_code}")
        print(f"   {r.text}")
except Exception as e:
    print(f"   ❌ Error: {e}")

# Test 3: Direct agent run
print("\n3. Running agent directly...")
try:
    payload = {
        "thread_id": "test_agent",
        "query": "Find information about CRT system architecture",
        "max_steps": 5
    }
    r = requests.post(f"{BASE_URL}/api/agent/run", json=payload, timeout=30)
    
    if r.status_code == 200:
        data = r.json()
        trace = data.get("trace", {})
        
        print(f"   ✅ Agent ran successfully")
        print(f"   Steps: {len(trace.get('steps', []))}")
        print(f"   Success: {trace.get('success')}")
        
        if trace.get('steps'):
            print("\n   Step summary:")
            for step in trace['steps']:
                action = step.get('action', {})
                obs = step.get('observation', {})
                tool = action.get('tool', 'unknown')
                success = '✅' if obs.get('success') else '❌'
                print(f"     {step.get('step_num')}. {tool} {success}")
    else:
        print(f"   ❌ Error: {r.status_code}")
        print(f"   {r.text}")
except Exception as e:
    print(f"   ❌ Error: {e}")

print("\n" + "=" * 60)
print("FRONTEND TEST:")
print("=" * 60)
print("1. Open http://localhost:5174 in your browser")
print("2. Send a message like: 'What is quantum mechanics?'")
print("3. Look for blue '🤖 AGENT TRACE' badge on response")
print("4. Click the badge to see agent execution steps")
print("=" * 60)
