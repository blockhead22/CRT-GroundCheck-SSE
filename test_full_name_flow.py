#!/usr/bin/env python3
"""Full test of name extraction and recall."""
import requests
import time

thread_id = f"test_name_flow_{int(time.time())}"

print("=" * 70)
print("TEST 1: Hi, I am Nick Block. Who are you?")
print("=" * 70)
r1 = requests.post(
    "http://127.0.0.1:8123/api/chat/send",
    json={"thread_id": thread_id, "message": "Hi, I am Nick Block. Who are you?"}
)
d1 = r1.json()
print(f"Answer: {d1['answer']}")
print(f"Gate Reason: {d1.get('gate_reason', 'N/A')}")
print()

print("=" * 70)
print("TEST 2: My favorite color is orange")
print("=" * 70)
r2 = requests.post(
    "http://127.0.0.1:8123/api/chat/send",
    json={"thread_id": thread_id, "message": "My favorite color is orange"}
)
d2 = r2.json()
print(f"Answer: {d2['answer']}")
print()

print("=" * 70)
print("TEST 3: What's my name?")
print("=" * 70)
r3 = requests.post(
    "http://127.0.0.1:8123/api/chat/send",
    json={"thread_id": thread_id, "message": "What's my name?"}
)
d3 = r3.json()
print(f"Answer: {d3['answer']}")
print(f"Confidence: {d3['metadata'].get('confidence', 'N/A')}")
print()

print("=" * 70)
print("TEST 4: Explain how you remember my name")
print("=" * 70)
r4 = requests.post(
    "http://127.0.0.1:8123/api/chat/send",
    json={"thread_id": thread_id, "message": "Explain how you remember my name"}
)
d4 = r4.json()
print(f"Answer: {d4['answer']}")
print(f"Gates Passed: {d4.get('gates_passed', 'N/A')}")
