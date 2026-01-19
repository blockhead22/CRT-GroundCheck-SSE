"""Simulate comprehensive validation conditions with many facts."""
import requests
import time
import uuid

API_BASE = "http://localhost:8123"
THREAD_ID = f"simulate_full_{uuid.uuid4().hex[:8]}"

# Mimic comprehensive validation: store ALL facts from all phases
all_facts = [
    # Phase 1
    "My name is Alex Chen",
    "I work at TechCorp", 
    "I live in San Francisco",
    "My favorite color is blue",
    "I have two siblings",  # ← FAILING
    # Phase 3
    "I enjoy programming in Python",
    "I like machine learning",
    "I'm interested in AI safety",
    # Phase 4
    "I graduated in 2020",  # ← FAILING
    "My project is called CRT",
    "I speak three languages",  # ← FAILING
]

print(f"Thread: {THREAD_ID}")
print("Simulating comprehensive validation conditions...")
print("=" * 80)

# Store all facts
for fact in all_facts:
    resp = requests.post(f"{API_BASE}/api/chat/send", json={
        "message": fact,
        "thread_id": THREAD_ID
    })
    time.sleep(0.2)
print(f"Stored {len(all_facts)} facts")

# Test the 3 failing queries
failing_queries = [
    ("How many siblings do I have?", "two siblings"),
    ("When did I graduate?", "2020"),
    ("How many languages do I speak?", "three"),
]

print("\nTesting queries:")
print("=" * 80)

for query, expected in failing_queries:
    resp = requests.post(f"{API_BASE}/api/chat/send", json={
        "message": query,
        "thread_id": THREAD_ID
    })
    data = resp.json()
    
    passed = data['gates_passed'] and expected in data['answer'].lower()
    
    print(f"\nQuery: {query}")
    print(f"Gates: {data['gates_passed']}")
    print(f"Expected: '{expected}' in answer")
    print(f"Answer: {data['answer'][:150]}")
    print(f"Result: {'✓ PASS' if passed else '✗ FAIL'}")
