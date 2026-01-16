#!/usr/bin/env python3
"""Option A: Test assertion storage."""
import requests
import json
import time

# Use the same thread as before to build on the conversation
thread_id = f"custom_test_{int(time.time())}"

print("=" * 80)
print("OPTION A: Testing assertion storage")
print("=" * 80)
print()

# Test assertion
message = "I work at Microsoft in Seattle as a senior engineer."

print(f"MESSAGE: {message}")
print()

r = requests.post(
    "http://127.0.0.1:8123/api/chat/send",
    json={"thread_id": thread_id, "message": message}
)

data = r.json()

print("ANSWER:")
print(data['answer'])
print()
print("=" * 80)
print("METADATA:")
print(f"  Mode: {data['metadata'].get('mode', 'N/A')}")
print(f"  Confidence: {data['metadata'].get('confidence', 'N/A')}")
print(f"  Gates Passed: {data.get('gates_passed', 'N/A')}")
print(f"  Gate Reason: {data.get('gate_reason', 'N/A')}")
print(f"  Retrieved Memories: {len(data['metadata'].get('retrieved_memories', []))}")
print(f"  Prompt Memories: {len(data['metadata'].get('prompt_memories', []))}")
print()

# Now test recall
print("=" * 80)
print("FOLLOW-UP: Testing fact recall")
print("=" * 80)
print()

recall_message = "Where do I work?"
print(f"MESSAGE: {recall_message}")
print()

r2 = requests.post(
    "http://127.0.0.1:8123/api/chat/send",
    json={"thread_id": thread_id, "message": recall_message}
)

data2 = r2.json()

print("ANSWER:")
print(data2['answer'])
print()
print("METADATA:")
print(f"  Confidence: {data2['metadata'].get('confidence', 'N/A')}")
print(f"  Gates Passed: {data2.get('gates_passed', 'N/A')}")
print(f"  Retrieved Memories: {len(data2['metadata'].get('retrieved_memories', []))}")
print()

if data2['metadata'].get('retrieved_memories'):
    print("RETRIEVED MEMORIES:")
    for i, mem in enumerate(data2['metadata']['retrieved_memories'], 1):
        print(f"  {i}. [{mem.get('source', '?')}] {mem.get('text', 'N/A')[:100]}")
