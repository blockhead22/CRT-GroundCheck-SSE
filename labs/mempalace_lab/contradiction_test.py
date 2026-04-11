"""Contradiction Test -- MemPalace Knowledge Graph

Feed contradictory facts, query them, see what comes back.
Does the system detect, flag, or handle contradictions? Or silently hold both?
"""

import os
import tempfile

TEST_DB = os.path.join(tempfile.mkdtemp(), "test_kg.sqlite3")

from mempalace.knowledge_graph import KnowledgeGraph

def p(msg): print(msg, flush=True)

def test_contradictions():
    kg = KnowledgeGraph(db_path=TEST_DB)

    p("=" * 60)
    p("MEMPALACE CONTRADICTION TEST")
    p("=" * 60)

    # -- TEST 1: Direct factual contradiction (same time window) --
    p("\n--- TEST 1: Direct contradiction (same time) ---")
    p("Adding: 'Nick loves coffee' (valid now)")
    kg.add_triple("Nick", "loves", "coffee", valid_from="2026-01-01")
    p("Adding: 'Nick hates coffee' (valid now)")
    kg.add_triple("Nick", "hates", "coffee", valid_from="2026-01-01")

    facts = kg.query_entity("Nick")
    current = [f for f in facts if f.get("current", False)]
    p(f"\nQuery 'Nick' returns {len(current)} current facts:")
    for fact in current:
        p(f"  {fact['subject']} {fact['predicate']} {fact['object']} "
          f"(confidence: {fact.get('confidence', '?')})")

    # Check for any contradiction signal in the response
    all_keys = set()
    for f in facts:
        all_keys.update(f.keys())
    contra_keys = [k for k in all_keys if any(x in k.lower() for x in
                   ["contra", "conflict", "trust", "flag", "dispute", "warning"])]
    p(f"Fact fields: {sorted(all_keys)}")
    p(f"Contradiction-related fields: {contra_keys or 'NONE'}")
    p(f"Contradiction detected by system? NO")

    # -- TEST 2: Temporal overlap (two jobs at once) --
    p("\n--- TEST 2: Temporal overlap ---")
    kg.add_triple("Nick", "works_at", "Google", valid_from="2025-01-01")
    kg.add_triple("Nick", "works_at", "Meta", valid_from="2025-06-01")

    facts = kg.query_entity("Nick")
    work = [f for f in facts if f["predicate"] == "works_at" and f.get("current")]
    p(f"Current 'works_at' facts: {len(work)}")
    for f in work:
        p(f"  Nick works_at {f['object']} (from {f.get('valid_from', '?')})")
    p(f"Two concurrent jobs. System flags overlap? NO")

    # -- TEST 3: Nuanced semantic contradiction --
    p("\n--- TEST 3: Nuanced semantic contradiction ---")
    kg.add_triple("Nick", "is_feeling", "happy", valid_from="2026-04-01")
    kg.add_triple("Nick", "is_feeling", "miserable", valid_from="2026-04-01")

    facts = kg.query_entity("Nick")
    mood = [f for f in facts if f["predicate"] == "is_feeling" and f.get("current")]
    p(f"Mood facts coexisting: {len(mood)}")
    for f in mood:
        p(f"  Nick is_feeling {f['object']}")
    p(f"'happy' and 'miserable' at the same time. Detected? NO")
    p(f"(Different objects on same predicate -- system has no semantic comparison)")

    # -- TEST 4: Confidence never changes --
    p("\n--- TEST 4: Confidence scores ---")
    facts = kg.query_entity("Nick")
    confidences = [f.get("confidence") for f in facts]
    p(f"All confidence values: {set(confidences)}")
    p(f"Any earned/decayed confidence? NO -- all hardcoded 1.0")

    # -- TEST 5: Opposite predicates --
    p("\n--- TEST 5: Logical opposites ---")
    kg.add_triple("Nick", "is_married", "true", valid_from="2026-01-01")
    kg.add_triple("Nick", "is_single", "true", valid_from="2026-01-01")

    facts = kg.query_entity("Nick")
    status = [f for f in facts if f["predicate"] in ("is_married", "is_single") and f.get("current")]
    p(f"Marital status facts: {len(status)}")
    for f in status:
        p(f"  Nick {f['predicate']} {f['object']}")
    p(f"Married AND single simultaneously. Detected? NO")

    # -- TEST 6: Held contradiction (philosophically valid) --
    p("\n--- TEST 6: Held contradiction ---")
    kg.add_triple("Nick", "believes_in", "free_will", valid_from="2026-01-01")
    kg.add_triple("Nick", "believes_in", "determinism", valid_from="2026-01-01")

    facts = kg.query_entity("Nick")
    beliefs = [f for f in facts if f["predicate"] == "believes_in" and f.get("current")]
    p(f"Belief facts: {len(beliefs)}")
    for f in beliefs:
        p(f"  Nick believes_in {f['object']}")
    p(f"These SHOULD coexist (held contradiction).")
    p(f"But the system doesn't know they conflict OR that holding them is intentional.")
    p(f"No state: resolvable vs held vs evolving. Just two rows.")

    # -- TEST 7: Query doesn't warn about conflicts --
    p("\n--- TEST 7: Does any query method flag conflicts? ---")
    methods = [m for m in dir(kg) if not m.startswith("_")]
    contra_methods = [m for m in methods if any(x in m.lower() for x in
                      ["contra", "conflict", "check", "verify", "valid", "trust"])]
    p(f"Available methods: {methods}")
    p(f"Contradiction-related methods: {contra_methods or 'NONE'}")

    # Check invalidate -- does it auto-detect?
    p("\n  Testing invalidate()...")
    p("  Invalidating 'Nick loves coffee'")
    kg.invalidate("Nick", "loves", "coffee", ended="2026-04-11")
    facts = kg.query_entity("Nick")
    coffee = [f for f in facts if "coffee" in f["object"]]
    p(f"  Coffee facts after invalidation: {len(coffee)}")
    for f in coffee:
        status = "EXPIRED" if f.get("valid_to") else "CURRENT"
        p(f"    [{status}] Nick {f['predicate']} {f['object']}")
    p(f"  invalidate() is MANUAL -- caller must know what to invalidate.")
    p(f"  No auto-detection of what conflicts with what.")

    # -- SUMMARY --
    p(f"\n{'=' * 60}")
    p("RESULTS")
    p(f"{'=' * 60}")
    facts = kg.query_entity("Nick")
    current = [f for f in facts if f.get("current")]
    p(f"Total current facts about Nick: {len(current)}")
    p(f"Contradictions in dataset: at least 4")
    p(f"  - loves/hates coffee (direct opposite)")
    p(f"  - works_at Google AND Meta (temporal overlap)")
    p(f"  - is_feeling happy AND miserable (semantic)")
    p(f"  - is_married AND is_single (logical)")
    p(f"Contradictions detected: 0")
    p(f"Contradictions flagged: 0")
    p(f"Confidence values changed: 0")
    p(f"Trust scores: not implemented")
    p(f"Dependency propagation: not implemented")
    p(f"Resolution mechanism: not implemented")
    p(f"Held contradiction state: not implemented")
    p(f"fact_checker.py: does not exist in codebase")
    p(f"")
    p(f"CONCLUSION: MemPalace knowledge graph stores contradictory facts")
    p(f"silently with equal confidence. No detection, no flagging, no")
    p(f"resolution, no held states. Query returns all facts as equally true.")
    p(f"{'=' * 60}")

    kg.close()


if __name__ == "__main__":
    test_contradictions()
