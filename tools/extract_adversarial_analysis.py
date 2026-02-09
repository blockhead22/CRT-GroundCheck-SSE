#!/usr/bin/env python3
"""Extract key analysis from adversarial stress test results."""
import json, sys

path = r"D:\AI_round2\artifacts\agent_adversarial_d71b807f59ab_20260209_105645.json"
data = json.load(open(path, encoding="utf-8"))

turns = {t["turn"]: t for t in data["turns"]}

print("=" * 70)
print("ADVERSARIAL STRESS TEST - DETAILED ANALYSIS")
print("=" * 70)

print("\n--- SCORE ---")
s = data["score"]
print(f"  Total attacks: {s['total_attacks']}")
print(f"  CRT correct:  {s['crt_correct']} ({s['crt_correct']/max(s['total_attacks'],1)*100:.0f}%)")
print(f"  CRT missed:   {s['crt_missed']}")

print("\n--- PHASE 1 ANOMALIES ---")
t1 = turns[1]
print(f"  T1 (name declaration):")
print(f"    gates_passed={t1['gates_passed']}, gate_reason={t1['gate_reason']}")
print(f"    contradiction_detected={t1['contradiction_detected']}")
print(f"    confidence={t1['confidence']}")
print(f"    Answer: {t1['crt_answer'][:200]}")
print(f"    ISSUE: GATE_FAIL + CONTRADICTION on very first message (fresh thread)")

t3 = turns[3]
print(f"\n  T3 (age='32'):")
print(f"    crt_answer: {t3['crt_answer'][:200]}")
print(f"    ISSUE: CRT says 'previously said your age was 34' -- user said 32, never said 34")

t13 = turns[13]
print(f"\n  T13 (verify 'How old am I?'):")
print(f"    crt_answer: {t13['crt_answer'][:200]}")
print(f"    ISSUE: Returns '34 years' when user said '32' at T3 -- wrong baseline")

print("\n--- PHASE 3: DIRECT CONTRADICTIONS (8/9 MISSED) ---")
for i in range(16, 25):
    t = turns[i]
    detected = "DETECTED" if t["contradiction_detected"] else "MISSED"
    print(f"  T{i}: {detected} | conf={t['confidence']} | hard_conflicts={t['unresolved_hard_conflicts']} | unresolved={t['unresolved_contradictions']}")
    print(f"    User: {t['user_message'][:80]}")
    print(f"    CRT:  {t['crt_answer'][:120]}")
    meta = t.get("raw_metadata", {})
    # Check what the contradiction system actually saw
    contra_keys = [k for k in meta if "contra" in k.lower()]
    if contra_keys:
        print(f"    Metadata contradiction fields: {', '.join(f'{k}={meta[k]}' for k in contra_keys)}")
    print()

print("--- PHASE 4: POST-CONTRADICTION VERIFICATION ---")
for i in range(25, 34):
    t = turns[i]
    print(f"  T{i}: Q='{t['user_message']}' conf={t['confidence']}")
    print(f"    Answer: {t['crt_answer'][:150]}")
    print()

print("--- PHASE 5: GASLIGHTING ---")
for i in range(34, 39):
    t = turns[i]
    print(f"  T{i}: gates={t['gates_passed']}, contradiction={t['contradiction_detected']}")
    print(f"    User: {t['user_message'][:80]}")
    print(f"    CRT:  {t['crt_answer'][:150]}")
    print()

print("--- PHASE 7: META PROBES ---")
for i in range(44, 50):
    t = turns[i]
    print(f"  T{i}: Q='{t['user_message'][:50]}...'")
    print(f"    Answer ({len(t['crt_answer'])} chars): {t['crt_answer'][:300]}")
    print()

print("--- LATENCY ---")
latencies = [t["latency_ms"] for t in data["turns"]]
print(f"  Min: {min(latencies)/1000:.1f}s")
print(f"  Max: {max(latencies)/1000:.1f}s")
print(f"  Avg: {sum(latencies)/len(latencies)/1000:.1f}s")
print(f"  Total: {sum(latencies)/1000:.0f}s ({sum(latencies)/60000:.0f} min)")
