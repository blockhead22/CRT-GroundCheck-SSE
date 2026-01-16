#!/usr/bin/env python3
"""Quick test for name extraction fix."""
import requests

# Test 1: Name + Question
print("=" * 60)
print("TEST 1: Hi, I am Nick Block. Who are you?")
print("=" * 60)
r1 = requests.post(
    "http://127.0.0.1:8123/api/chat/send",
    json={
        "thread_id": "test_name_extraction_v1",
        "message": "Hi, I am Nick Block. Who are you?"
    }
)
d1 = r1.json()
print(f"Answer: {d1['answer']}")
print(f"Confidence: {d1['confidence']}")
print(f"Gates: {d1.get('gates_passed', 'N/A')}")
print()

# Test 2: Ask about name memory
print("=" * 60)
print("TEST 2: Explain how you remember my name")
print("=" * 60)
r2 = requests.post(
    "http://127.0.0.1:8123/api/chat/send",
    json={
        "thread_id": "test_name_extraction_v1",
        "message": "Explain how you remember my name"
    }
)
d2 = r2.json()
print(f"Answer: {d2['answer']}")
print(f"Confidence: {d2['confidence']}")
print()

# Test 3: Simple name check
print("=" * 60)
print("TEST 3: What's my name?")
print("=" * 60)
r3 = requests.post(
    "http://127.0.0.1:8123/api/chat/send",
    json={
        "thread_id": "test_name_extraction_v1",
        "message": "What's my name?"
    }
)
d3 = r3.json()
print(f"Answer: {d3['answer']}")
print(f"Confidence: {d3['confidence']}")
