"""Debug OVERRIDE resolution failure"""
import requests
import json
import time
import traceback

API_URL = "http://127.0.0.1:8123/api/chat/send"
API_CONTRA = "http://127.0.0.1:8123/api/contradictions"
API_RESOLVE = "http://127.0.0.1:8123/api/resolve_contradiction"

thread_id = f"override_debug_{int(time.time())}"

# Create contradiction
print("1. Creating contradiction...")
r1 = requests.post(API_URL, json={"thread_id": thread_id, "message": "I work at Microsoft"}, timeout=30)
print(f"   Response: {r1.status_code}")

time.sleep(0.5)

r2 = requests.post(API_URL, json={"thread_id": thread_id, "message": "I work at Amazon"}, timeout=30)
print(f"   Response: {r2.status_code}")

# Get contradictions
print("\n2. Getting contradictions...")
r_contra = requests.get(API_CONTRA, params={"thread_id": thread_id}, timeout=30)
contradictions = r_contra.json().get("contradictions", [])

if not contradictions:
    print("   No contradictions found!")
    exit(1)

print(f"   Found {len(contradictions)} contradiction(s)")

contra = contradictions[0]
ledger_id = contra["ledger_id"]
old_mem = contra.get("old_memory_id")
new_mem = contra.get("new_memory_id")

print(f"   Ledger ID: {ledger_id}")
print(f"   Old memory: {old_mem}")
print(f"   New memory: {new_mem}")

# Try OVERRIDE
print("\n3. Attempting OVERRIDE...")
try:
    resolve_resp = requests.post(API_RESOLVE, json={
        "thread_id": thread_id,
        "ledger_id": ledger_id,
        "resolution": "OVERRIDE",
        "chosen_memory_id": new_mem,
        "user_confirmation": "Amazon is correct"
    }, timeout=30)
    
    print(f"   Status: {resolve_resp.status_code}")
    print(f"   Headers: {dict(resolve_resp.headers)}")
    print(f"   Response text: {resolve_resp.text[:500]}")
    
    if resolve_resp.status_code == 500:
        # Parse error details
        try:
            error_detail = resolve_resp.json()
            print(f"   Error JSON: {json.dumps(error_detail, indent=2)}")
        except:
            pass
    
except Exception as e:
    print(f"   Exception: {e}")
    traceback.print_exc()
