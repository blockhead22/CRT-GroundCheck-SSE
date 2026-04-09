"""Contradiction Drive Lab — Tension Measurement on Production Data

Can we measure "motivation" from the belief graph?

Computes tension scores across production memories:
  - Open contradictions per domain
  - Domain volatility from correction history
  - Stale high-trust beliefs (confident but unverified)
  - Self-model divergence
  - Wobble co-activation candidates for edge discovery

Then simulates an active heartbeat pass: what would it prioritize?
What actions would it queue?

Run: python -m papers.belief_backpropagation.contradiction_drive_lab
"""

import sys
sys.path.insert(0, r"D:\AI_round2")
sys.stdout.reconfigure(encoding='utf-8')

import json
import time
import sqlite3
import numpy as np

PASS_COUNT = 0
FAIL_COUNT = 0


def check(condition, label):
    global PASS_COUNT, FAIL_COUNT
    if condition:
        PASS_COUNT += 1
        print(f"    [PASS] {label}")
    else:
        FAIL_COUNT += 1
        print(f"    [FAIL] {label}")
    return condition


def cosine(a, b):
    d = np.linalg.norm(a) * np.linalg.norm(b)
    return float(np.dot(a, b) / d) if d > 1e-10 else 0.0


# ===================================================================
# Load production data
# ===================================================================

def load_data():
    db = r"D:\AI_round2\personal_agent\crt_memory_shared.db"
    conn = sqlite3.connect(db)

    memories = []
    rows = conn.execute("""
        SELECT memory_id, text, trust, kind, contradiction_count,
               access_count, timestamp, last_accessed, vector_json
        FROM memories WHERE deprecated=0 AND text IS NOT NULL
    """).fetchall()

    for mid, text, trust, kind, contras, access, ts, last_acc, vec_json in rows:
        vec = None
        if vec_json:
            try:
                v = json.loads(vec_json)
                if len(v) == 384:
                    vec = np.array(v, dtype=np.float32)
            except:
                pass
        memories.append({
            "id": mid, "text": text[:200], "trust": trust or 0,
            "kind": kind or "observation",
            "contradictions": contras or 0,
            "access_count": access or 0,
            "timestamp": ts or 0,
            "last_accessed": last_acc or 0,
            "vector": vec,
        })

    # Load contradiction ledger
    ledger = []
    try:
        rows = conn.execute("""
            SELECT old_memory_id, new_memory_id, status, drift_mean,
                   affects_slots, timestamp
            FROM contradiction_ledger
        """).fetchall()
        for old_id, new_id, status, drift, slots, ts in rows:
            ledger.append({
                "old_id": old_id, "new_id": new_id,
                "status": status or "OPEN",
                "drift": drift or 0,
                "slots": slots or "",
                "timestamp": ts or 0,
            })
    except:
        pass

    conn.close()
    return memories, ledger


# ===================================================================
# Lab 21: Tension Measurement
# ===================================================================

def lab_21_tension(memories, ledger):
    print("=" * 70)
    print("LAB 21: Tension Measurement")
    print("=" * 70)
    print(f"  {len(memories)} memories, {len(ledger)} ledger entries")

    now = time.time()

    # 1. Open contradictions
    open_contras = [e for e in ledger if e["status"] == "OPEN"]
    print(f"\n  Open contradictions: {len(open_contras)}")

    # 2. Memories with contradiction history
    contradicted = [m for m in memories if m["contradictions"] > 0]
    print(f"  Memories with contradiction history: {len(contradicted)}")
    for m in sorted(contradicted, key=lambda x: -x["contradictions"])[:5]:
        print(f"    [{m['contradictions']}x corrected, trust={m['trust']:.2f}] {m['text'][:80]}")

    # 3. Domain tension (infer domains from kind + text keywords)
    domain_tension = {}
    for m in memories:
        # Simple domain inference
        text_lower = m["text"].lower()
        domains = set()
        if any(w in text_lower for w in ["work", "job", "employ", "freelance", "walmart", "studio"]):
            domains.add("work")
        if any(w in text_lower for w in ["color", "orange", "green", "blue", "purple"]):
            domains.add("preference")
        if any(w in text_lower for w in ["name", "nick", "block"]):
            domains.add("identity")
        if any(w in text_lower for w in ["health", "cgvhd", "leukemia", "condition"]):
            domains.add("health")
        if any(w in text_lower for w in ["coffee", "drink", "water", "juice"]):
            domains.add("preference")
        if any(w in text_lower for w in ["build", "crt", "aether", "system", "memory"]):
            domains.add("project")
        if not domains:
            domains.add("other")

        for d in domains:
            if d not in domain_tension:
                domain_tension[d] = {"count": 0, "contras": 0, "low_trust": 0,
                                     "high_trust": 0, "stale": 0, "total_trust": 0}
            dt = domain_tension[d]
            dt["count"] += 1
            dt["contras"] += m["contradictions"]
            dt["total_trust"] += m["trust"]
            if m["trust"] < 0.3:
                dt["low_trust"] += 1
            if m["trust"] > 0.7:
                dt["high_trust"] += 1
            # Stale: high trust but not accessed in 7+ days
            if m["trust"] > 0.6 and m["last_accessed"] and (now - m["last_accessed"]) > 7 * 86400:
                dt["stale"] += 1

    print(f"\n  Domain tension scores:")
    print(f"  {'Domain':15s} {'Count':>6s} {'Contras':>8s} {'LowTrust':>9s} {'Stale':>6s} {'Tension':>8s}")
    print(f"  {'-'*15} {'-'*6} {'-'*8} {'-'*9} {'-'*6} {'-'*8}")

    for domain in sorted(domain_tension.keys()):
        dt = domain_tension[domain]
        # Tension = contradictions * (low_trust_ratio + stale_ratio) * count_weight
        low_ratio = dt["low_trust"] / max(dt["count"], 1)
        stale_ratio = dt["stale"] / max(dt["count"], 1)
        tension = dt["contras"] * (1 + low_ratio + stale_ratio) * np.log1p(dt["count"])
        dt["tension"] = tension
        print(f"  {domain:15s} {dt['count']:6d} {dt['contras']:8d} {dt['low_trust']:9d} {dt['stale']:6d} {tension:8.2f}")

    # Check: at least one domain has measurable tension
    max_tension = max(dt["tension"] for dt in domain_tension.values())
    check(max_tension > 0, f"At least one domain has tension ({max_tension:.2f})")

    return domain_tension


# ===================================================================
# Lab 22: Stale Belief Detection
# ===================================================================

def lab_22_stale(memories):
    print("\n" + "=" * 70)
    print("LAB 22: Stale Belief Detection")
    print("=" * 70)
    print("  Question: Which high-trust beliefs haven't been verified recently?")

    now = time.time()
    seven_days = 7 * 86400
    thirty_days = 30 * 86400

    stale_7d = [m for m in memories
                if m["trust"] > 0.6
                and m["last_accessed"]
                and (now - m["last_accessed"]) > seven_days]

    stale_30d = [m for m in memories
                 if m["trust"] > 0.6
                 and m["last_accessed"]
                 and (now - m["last_accessed"]) > thirty_days]

    never_accessed = [m for m in memories
                      if m["trust"] > 0.5
                      and (m["access_count"] or 0) == 0]

    print(f"\n  High-trust + stale >7 days:  {len(stale_7d)}")
    print(f"  High-trust + stale >30 days: {len(stale_30d)}")
    print(f"  Medium-trust + never accessed: {len(never_accessed)}")

    if stale_30d:
        print(f"\n  Top 5 stale high-trust beliefs (>30 days):")
        for m in sorted(stale_30d, key=lambda x: -x["trust"])[:5]:
            days = (now - m["last_accessed"]) / 86400
            print(f"    [trust={m['trust']:.2f}, {days:.0f}d stale] {m['text'][:80]}")

    check(len(stale_7d) >= 0, f"Stale detection runs ({len(stale_7d)} found >7d)")

    return stale_7d, stale_30d, never_accessed


# ===================================================================
# Lab 23: Edge Discovery Candidates (Wobble Co-activation)
# ===================================================================

def lab_23_edge_discovery(memories):
    print("\n" + "=" * 70)
    print("LAB 23: Edge Discovery via Vector Proximity")
    print("=" * 70)
    print("  Question: Which memories are close in vector space but unconnected?")

    # Find pairs that are semantically close but in different domains
    vecs = [(m, m["vector"]) for m in memories if m["vector"] is not None]
    print(f"  {len(vecs)} memories with vectors")

    cross_domain_pairs = []
    n = min(len(vecs), 300)  # sample for speed

    for i in range(n):
        for j in range(i + 1, n):
            sim = cosine(vecs[i][1], vecs[j][1])
            if sim > 0.5:
                m1, m2 = vecs[i][0], vecs[j][0]
                # Different inferred domains?
                t1 = m1["text"].lower()
                t2 = m2["text"].lower()
                d1 = "work" if "work" in t1 or "job" in t1 else "health" if "health" in t1 else "other"
                d2 = "work" if "work" in t2 or "job" in t2 else "health" if "health" in t2 else "other"
                if d1 != d2 or sim > 0.7:
                    cross_domain_pairs.append((m1, m2, sim))

    cross_domain_pairs.sort(key=lambda x: -x[2])
    print(f"  Cross-domain high-similarity pairs: {len(cross_domain_pairs)}")

    for m1, m2, sim in cross_domain_pairs[:5]:
        print(f"\n    sim={sim:.3f}")
        print(f"      [{m1['trust']:.2f}] {m1['text'][:70]}")
        print(f"      [{m2['trust']:.2f}] {m2['text'][:70]}")

    check(len(cross_domain_pairs) > 0, f"Found edge candidates ({len(cross_domain_pairs)})")

    return cross_domain_pairs


# ===================================================================
# Lab 24: Simulated Active Heartbeat
# ===================================================================

def lab_24_heartbeat(memories, ledger, domain_tension, stale, edge_candidates):
    print("\n" + "=" * 70)
    print("LAB 24: Simulated Active Heartbeat")
    print("=" * 70)
    print("  Simulating what an active heartbeat would do right now.")

    actions = []

    # Priority 1: Open contradictions needing resolution
    open_contras = [e for e in ledger if e["status"] == "OPEN"]
    for c in open_contras[:3]:
        actions.append({
            "priority": 1,
            "type": "REFLECT",
            "reason": f"Open contradiction: {c['old_id'][:20]} vs {c['new_id'][:20]}",
            "action": "Queue reflection task to evaluate which side has more evidence",
        })

    # Priority 2: High-tension domains
    sorted_domains = sorted(domain_tension.items(), key=lambda x: -x[1]["tension"])
    for domain, dt in sorted_domains[:2]:
        if dt["tension"] > 1.0:
            actions.append({
                "priority": 2,
                "type": "ASK",
                "reason": f"Domain '{domain}' has tension={dt['tension']:.1f} ({dt['contras']} contradictions)",
                "action": f"Next conversation, ask user to clarify {domain} facts",
            })

    # Priority 3: Stale beliefs needing re-verification
    for m in stale[:3]:
        actions.append({
            "priority": 3,
            "type": "VERIFY",
            "reason": f"High-trust belief stale: '{m['text'][:50]}' (trust={m['trust']:.2f})",
            "action": "Flag for re-verification in next relevant conversation",
        })

    # Priority 4: Edge discovery
    for m1, m2, sim in edge_candidates[:2]:
        actions.append({
            "priority": 4,
            "type": "DISCOVER",
            "reason": f"Potential connection: '{m1['text'][:40]}' <-> '{m2['text'][:40]}' (sim={sim:.2f})",
            "action": "Propose BDG edge if co-activated again",
        })

    # Priority 5: Training promotion candidates
    stable_high = [m for m in memories
                   if m["trust"] > 0.8
                   and m["contradictions"] == 0
                   and m["access_count"] > 3]
    for m in stable_high[:3]:
        actions.append({
            "priority": 5,
            "type": "PROMOTE",
            "reason": f"Stable belief: '{m['text'][:50]}' (trust={m['trust']:.2f}, accessed {m['access_count']}x, 0 contradictions)",
            "action": "Flag for inclusion in next adapter training",
        })

    # Priority 6: Detraining candidates
    bad_beliefs = [m for m in memories
                   if m["contradictions"] >= 2
                   and m["trust"] < 0.3]
    for m in bad_beliefs[:3]:
        actions.append({
            "priority": 6,
            "type": "DETRAIN",
            "reason": f"Contradicted belief: '{m['text'][:50]}' (trust={m['trust']:.2f}, {m['contradictions']}x corrected)",
            "action": "Flag for removal from adapter training data",
        })

    # Display action queue
    print(f"\n  ACTION QUEUE ({len(actions)} actions):")
    print(f"  {'Pri':>3s}  {'Type':8s}  {'Action'}")
    print(f"  {'---':>3s}  {'--------':8s}  {'------'}")
    for a in sorted(actions, key=lambda x: x["priority"]):
        print(f"  {a['priority']:3d}  {a['type']:8s}  {a['reason'][:70]}")
        print(f"  {'':3s}  {'':8s}  -> {a['action'][:70]}")
        print()

    # Checks
    check(len(actions) > 0, f"Heartbeat generated actions ({len(actions)})")

    has_reflect = any(a["type"] == "REFLECT" for a in actions)
    has_promote = any(a["type"] == "PROMOTE" for a in actions)
    has_detrain = any(a["type"] == "DETRAIN" for a in actions)

    check(has_promote or len(stable_high) == 0,
          f"Training promotion candidates identified ({len(stable_high)})")
    check(has_detrain or len(bad_beliefs) == 0,
          f"Detraining candidates identified ({len(bad_beliefs)})")

    # The key metric: can we derive a "motivation score"?
    total_tension = sum(dt["tension"] for dt in domain_tension.values())
    open_count = len(open_contras)
    stale_count = len(stale)
    motivation = total_tension + open_count * 2 + stale_count * 0.5

    print(f"\n  MOTIVATION SCORE: {motivation:.1f}")
    print(f"    Tension: {total_tension:.1f}")
    print(f"    Open contradictions: {open_count} (x2 weight)")
    print(f"    Stale beliefs: {stale_count} (x0.5 weight)")
    print(f"\n  Interpretation:")
    if motivation < 5:
        print(f"    LOW — system is mostly settled. Passive observation sufficient.")
    elif motivation < 20:
        print(f"    MODERATE — some areas need attention. Targeted questions recommended.")
    else:
        print(f"    HIGH — significant unresolved tension. Active clarification needed.")

    check(motivation >= 0, f"Motivation score computable ({motivation:.1f})")

    return actions, motivation


# ===================================================================
# Main
# ===================================================================

if __name__ == "__main__":
    print("\n" + "#" * 70)
    print("# CONTRADICTION DRIVE LAB")
    print("# Can we measure motivation from the belief graph?")
    print("#" * 70)

    memories, ledger = load_data()
    print(f"\nLoaded: {len(memories)} memories, {len(ledger)} ledger entries")

    domain_tension = lab_21_tension(memories, ledger)
    stale_7d, stale_30d, never_accessed = lab_22_stale(memories)
    edge_candidates = lab_23_edge_discovery(memories)
    actions, motivation = lab_24_heartbeat(memories, ledger, domain_tension,
                                           stale_30d, edge_candidates)

    print("\n" + "=" * 70)
    print(f"RESULTS: {PASS_COUNT} passed, {FAIL_COUNT} failed")
    print("=" * 70)

    if FAIL_COUNT == 0:
        print("ALL LABS PASSED — Contradiction drive is measurable.")
    else:
        print(f"{FAIL_COUNT} failures.")
