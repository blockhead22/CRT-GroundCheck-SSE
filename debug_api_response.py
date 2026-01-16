#!/usr/bin/env python3
"""Debug what API is returning."""
import requests
import json

r = requests.post(
    "http://127.0.0.1:8123/api/chat/send",
    json={
        "thread_id": "debug_response_v1",
        "message": "Hi, I am Nick Block. Who are you?"
    }
)

print("Status Code:", r.status_code)
print("Response:")
print(json.dumps(r.json(), indent=2))
