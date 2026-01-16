#!/usr/bin/env python3
"""Test with a fresh thread ID."""
import requests
import json
import time

thread_id = f"test_fresh_{int(time.time())}"

r = requests.post(
    "http://127.0.0.1:8123/api/chat/send",
    json={
        "thread_id": thread_id,
        "message": "Hi, I am Nick Block. Who are you?"
    }
)

print("Thread ID:", thread_id)
print("Status Code:", r.status_code)
print()
print("Response:")
data = r.json()
print("Answer:", data['answer'])
print("Gate Reason:", data.get('gate_reason', 'N/A'))
print("Session ID:", data.get('session_id', 'N/A'))
