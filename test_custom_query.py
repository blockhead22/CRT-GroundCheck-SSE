#!/usr/bin/env python3
"""Send a custom test query to CRT."""
import requests
import json
import time

thread_id = f"custom_test_{int(time.time())}"

# Custom question
question = "I work at Microsoft in Seattle, and I'm thinking about moving to the Bay Area to work at Google. What should I consider?"

print("=" * 80)
print(f"QUESTION: {question}")
print("=" * 80)
print()

r = requests.post(
    "http://127.0.0.1:8123/api/chat/send",
    json={"thread_id": thread_id, "message": question}
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
print(f"  Intent Alignment: {data['metadata'].get('intent_alignment', 'N/A')}")
print(f"  Memory Alignment: {data['metadata'].get('memory_alignment', 'N/A')}")
print(f"  Retrieved Memories: {len(data['metadata'].get('retrieved_memories', []))}")
print(f"  Prompt Memories: {len(data['metadata'].get('prompt_memories', []))}")
print(f"  Contradiction Detected: {data['metadata'].get('contradiction_detected', 'N/A')}")
print()

if data['metadata'].get('retrieved_memories'):
    print("RETRIEVED MEMORIES:")
    for i, mem in enumerate(data['metadata']['retrieved_memories'][:3], 1):
        print(f"  {i}. {mem.get('text', 'N/A')[:80]}...")
    print()
