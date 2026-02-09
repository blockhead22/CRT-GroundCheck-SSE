import json, sys

with open(r'D:\AI_round2\artifacts\agent_adversarial_d71b807f59ab_20260209_105645.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

# Check top-level keys  
print("TOP-LEVEL KEYS:", list(data.keys()))
print()

# Check for server warnings
if 'server_warnings' in data:
    print("SERVER WARNINGS:", json.dumps(data['server_warnings'], indent=2)[:2000])
if 'errors' in data:
    print("ERRORS:", json.dumps(data['errors'], indent=2)[:2000])
if 'warnings' in data:
    print("WARNINGS:", json.dumps(data['warnings'], indent=2)[:2000])

# Check metadata
for k in data:
    if k not in ('turns', 'attacks', 'facts', 'score'):
        val = data[k]
        if isinstance(val, (str, int, float, bool, type(None))):
            print(f"{k}: {val}")
        elif isinstance(val, list) and len(val) < 20:
            print(f"{k}: {json.dumps(val, indent=2)[:500]}")
        elif isinstance(val, dict) and len(json.dumps(val)) < 1000:
            print(f"{k}: {json.dumps(val, indent=2)[:500]}")
        else:
            print(f"{k}: ({type(val).__name__}, len={len(val) if hasattr(val,'__len__') else '?'})")

print()
print(f"Total turns: {len(data['turns'])}")

# Check for error/warning patterns in CRT answers
for t in data['turns']:
    ans = t.get('crt_answer','')
    if 'database is locked' in ans.lower() or 'NOT NULL' in ans or 'error' in ans.lower()[:50]:
        print(f"T{t['turn']} has error-like answer: {ans[:200]}")
    # Also check raw_metadata for server errors
    rm = t.get('raw_metadata',{})
    if rm and isinstance(rm, dict):
        for k,v in rm.items():
            if isinstance(v, str) and ('error' in v.lower() or 'locked' in v.lower() or 'NOT NULL' in v.lower()):
                print(f"T{t['turn']} raw_metadata.{k} has error: {v[:200]}")

# Check for warnings/errors within turn structure
print("\n=== TURN ANOMALIES ===")
for t in data['turns']:
    if t.get('warnings'):
        print(f"T{t['turn']} warnings: {t['warnings']}")
    if t.get('errors'):
        print(f"T{t['turn']} errors: {t['errors']}")
    if t.get('server_error'):
        print(f"T{t['turn']} server_error: {t['server_error']}")

# Response-type anomalies: speech answers that returned wrong slots
print("\n=== SPEECH RESPONSE ANOMALIES (verification phase T25-T33) ===")
for tn in range(25, 34):
    t = data['turns'][tn-1]
    print(f"T{t['turn']}: Q='{t['user_message']}' -> A='{t['crt_answer'][:100]}' type={t['response_type']} conf={t['confidence']}")

# T2 baseline
print("\n=== T2 BASELINE ===")
t2 = data['turns'][1]
print(f"user: {t2['user_message']}")
print(f"crt: {t2['crt_answer'][:300]}")
print(f"gates={t2['gates_passed']} contra={t2['contradiction_detected']}")

# Gate failure summary
print("\n=== ALL GATE FAILURES ===")
for t in data['turns']:
    if not t['gates_passed']:
        print(f"T{t['turn']}: type={t['response_type']} reason={t.get('gate_reason','?')} conf={t['confidence']} contra={t['contradiction_detected']} answer='{t['crt_answer'][:120]}'")

# Latency stats
latencies = [t['latency_ms'] for t in data['turns']]
print(f"\n=== LATENCY ===")
print(f"Min: {min(latencies):.0f}ms  Max: {max(latencies):.0f}ms  Avg: {sum(latencies)/len(latencies):.0f}ms")

for tn in turns_wanted:
    t = data['turns'][tn - 1]
    print(f"=== TURN {t['turn']} ===")
    print(f"user: {t['user_message']}")
    ans = t['crt_answer'][:400]
    print(f"crt: {ans}...")
    print(f"gates={t['gates_passed']} contra={t['contradiction_detected']} unresolved={t['unresolved_contradictions']} type={t['response_type']} conf={t['confidence']}")
    pu = t.get('profile_updates', [])
    if pu:
        print(f"profile_updates: {json.dumps(pu)}")
    # Check raw_metadata for contradiction fields
    rm = t.get('raw_metadata', {})
    print(f"raw: contra_detected={rm.get('contradiction_detected')} contra_resolved={rm.get('contradiction_resolved')} unresolved_total={rm.get('unresolved_contradictions_total')} hard={rm.get('unresolved_hard_conflicts')}")
    print()
