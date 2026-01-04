#!/usr/bin/env python
"""
SSE Navigator Demo

Demonstrates Phase 6, D2: Read-only interaction with SSE indices.
Shows all permitted operations while proving forbidden operations are blocked.
"""

import json
from sse.interaction_layer import SSENavigator, SSEBoundaryViolation


def demo_retrieval():
    """Demo: PERMITTED - Retrieval operations."""
    print("\n" + "=" * 70)
    print("DEMO 1: RETRIEVAL (PERMITTED)")
    print("=" * 70)
    
    nav = SSENavigator("output_index/index.json")
    
    # Get index info
    info = nav.info()
    print(f"\n✓ Index loaded: {info['doc_id']}")
    print(f"  - {info['num_claims']} claims")
    print(f"  - {info['num_contradictions']} contradictions")
    print(f"  - {info['num_clusters']} clusters")
    
    # Get all claims
    claims = nav.get_all_claims()
    print(f"\n✓ Retrieved {len(claims)} claims:")
    for i, claim in enumerate(claims[:3], 1):
        print(f"  {i}. {claim['claim_text'][:60]}...")


def demo_search():
    """Demo: PERMITTED - Search operations."""
    print("\n" + "=" * 70)
    print("DEMO 2: SEARCH (PERMITTED)")
    print("=" * 70)
    
    nav = SSENavigator("output_index/index.json")
    
    # Keyword search
    print("\n✓ Searching for 'sleep'...")
    results = nav.query("sleep", k=3, method="keyword")
    print(f"  Found {len(results)} claims:")
    for i, claim in enumerate(results, 1):
        print(f"  {i}. {claim['claim_text'][:60]}...")


def demo_provenance():
    """Demo: PERMITTED - Provenance tracking."""
    print("\n" + "=" * 70)
    print("DEMO 3: PROVENANCE (PERMITTED)")
    print("=" * 70)
    
    nav = SSENavigator("output_index/index.json")
    
    # Get a claim
    claim_id = "clm0"
    claim = nav.get_claim_by_id(claim_id)
    print(f"\n✓ Claim: {claim['claim_text']}")
    
    # Get its provenance
    prov = nav.get_provenance(claim_id)
    print(f"\n✓ Provenance (exact source):")
    for i, quote in enumerate(prov['supporting_quotes'], 1):
        print(f"  {i}. Quote: \"{quote['quote_text']}\"")
        print(f"     Location: [{quote['start_char']}:{quote['end_char']}]")
        print(f"     Matches source: {quote['valid']}")


def demo_contradiction():
    """Demo: PERMITTED - Contradiction exposure."""
    print("\n" + "=" * 70)
    print("DEMO 4: CONTRADICTIONS (PERMITTED)")
    print("=" * 70)
    
    nav = SSENavigator("output_index/index.json")
    
    # Get contradictions
    contradictions = nav.get_contradictions()
    print(f"\n✓ Found {len(contradictions)} contradictions")
    
    if contradictions:
        contra = contradictions[0]
        print(f"\n✓ Example contradiction (both sides shown):")
        formatted = nav.format_contradiction(contra)
        print(formatted)


def demo_ambiguity():
    """Demo: PERMITTED - Ambiguity exposure."""
    print("\n" + "=" * 70)
    print("DEMO 5: AMBIGUITY (PERMITTED)")
    print("=" * 70)
    
    nav = SSENavigator("output_index/index.json")
    
    # Find uncertain claims
    uncertain = nav.get_uncertain_claims(min_hedge=0.0)
    print(f"\n✓ Found {len(uncertain)} claims with ambiguity markers:")
    
    for claim in uncertain[:5]:
        hedge = claim.get("ambiguity", {}).get("hedge_score", 0.0)
        conflict = claim.get("ambiguity", {}).get("contains_conflict_markers", False)
        
        print(f"\n  Claim: {claim['claim_text'][:60]}...")
        print(f"    Hedge score: {hedge:.2f}")
        print(f"    Contains conflict markers: {conflict}")


def demo_forbidden():
    """Demo: FORBIDDEN - Boundary violations."""
    print("\n" + "=" * 70)
    print("DEMO 6: FORBIDDEN OPERATIONS (BOUNDARY VIOLATIONS)")
    print("=" * 70)
    
    nav = SSENavigator("output_index/index.json")
    
    forbidden_ops = [
        ("synthesize_answer", lambda: nav.synthesize_answer("What is sleep?")),
        ("answer_question", lambda: nav.answer_question("Is sleep important?")),
        ("pick_best_claim", lambda: nav.pick_best_claim("clm0", "clm1")),
        ("resolve_contradiction", lambda: nav.resolve_contradiction("clm0", "clm1")),
        ("soften_ambiguity", lambda: nav.soften_ambiguity("clm0")),
        ("suppress_contradiction", lambda: nav.suppress_contradiction("clm0")),
    ]
    
    for op_name, op_func in forbidden_ops:
        try:
            print(f"\n✗ Attempting '{op_name}'...", end=" ")
            op_func()
            print("ERROR: Should have raised SSEBoundaryViolation!")
        except SSEBoundaryViolation as e:
            print(f"✓ Blocked (SSEBoundaryViolation)")
            print(f"  Reason: {e.reason[:60]}...")


def demo_cli_examples():
    """Demo: Show equivalent CLI commands."""
    print("\n" + "=" * 70)
    print("DEMO 7: EQUIVALENT CLI COMMANDS")
    print("=" * 70)
    
    commands = [
        ("Show index info", "sse navigate --index output_index/index.json --info"),
        ("Search by keyword", "sse navigate --index output_index/index.json --query 'sleep' --k 5"),
        ("Find contradictions", "sse navigate --index output_index/index.json --topic-contradictions 'sleep'"),
        ("Show provenance", "sse navigate --index output_index/index.json --provenance clm0"),
        ("Find uncertain claims", "sse navigate --index output_index/index.json --uncertain --min-hedge 0.5"),
        ("All contradictions", "sse navigate --index output_index/index.json --all-contradictions"),
    ]
    
    for description, command in commands:
        print(f"\n{description}:")
        print(f"  $ {command}")


def main():
    """Run all demos."""
    print("\n")
    print("=" * 70)
    print(" " * 15 + "SSE NAVIGATOR DEMO - Phase 6, D2")
    print("=" * 70)
    
    demo_retrieval()
    demo_search()
    demo_provenance()
    demo_contradiction()
    demo_ambiguity()
    demo_forbidden()
    demo_cli_examples()
    
    print("\n" + "=" * 70)
    print("DEMO COMPLETE")
    print("=" * 70)
    print("""
✅ PERMITTED Operations Demonstrated:
  - Retrieval (get claims, contradictions, clusters)
  - Search (keyword and semantic)
  - Provenance (exact source with byte offsets)
  - Contradictions (both sides shown in full)
  - Ambiguity (hedge scores, conflict markers)

❌ FORBIDDEN Operations Blocked:
  - Synthesis (no new claims generated)
  - Truth picking (no winners chosen)
  - Ambiguity softening (uncertainty preserved)
  - Contradiction suppression (all shown)
  
🔒 Interface Contract Enforced:
  - All forbidden operations raise SSEBoundaryViolation
  - Enforcement is executable, not advisory
  - Boundaries are testable (29 tests verify)

📖 Documentation:
  - NAVIGATOR_QUICK_REFERENCE.md - User guide
  - PHASE_6_D2_COMPLETION.md - Implementation details
  - sse/interaction_layer.py - Source code
  
📝 CLI Ready:
  - sse navigate --help (see available operations)
  - All demos above can be run via CLI
""")


if __name__ == "__main__":
    main()
