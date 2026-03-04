"""Copilot-driven eval helper: send a message and print the response."""
import sys
import requests
import json

thread_id = sys.argv[1] if len(sys.argv) > 1 else "eval_copilot_001"
message = sys.argv[2] if len(sys.argv) > 2 else "Hello"
mode = sys.argv[3] if len(sys.argv) > 3 else "quick"

r = requests.post(
    "http://127.0.0.1:8123/api/chat/send",
    json={"message": message, "thread_id": thread_id, "mode": mode},
    timeout=300,
)
d = r.json()
print("=== ANSWER ===")
print(d.get("answer", ""))
print()
print("=== META ===")
meta = d.get("metadata", {})
print(f"  gates_passed: {d.get('gates_passed')}")
print(f"  gate_reason: {d.get('gate_reason')}")
print(f"  response_type: {d.get('response_type')}")
print(f"  confidence: {meta.get('confidence')}")
print(f"  intent_alignment: {meta.get('intent_alignment')}")
print(f"  memory_alignment: {meta.get('memory_alignment')}")
xray = d.get("xray", {})
if xray:
    print(f"  contradictions: {xray.get('contradictions_found')}")
    print(f"  facts_extracted: {xray.get('facts_extracted')}")
