"""Demo of contradiction-aware grounding."""

from groundcheck import GroundCheck, Memory


def main():
    verifier = GroundCheck()
    
    print("=" * 70)
    print("CONTRADICTION-AWARE GROUNDING DEMO")
    print("=" * 70)
    
    # Example 1: Undisclosed contradiction
    print("\n1. UNDISCLOSED CONTRADICTION (FAILS)")
    print("-" * 70)
    
    memories = [
        Memory(
            id="m1",
            text="User works at Microsoft",
            trust=0.9,
            timestamp=1704067200  # Jan 2024
        ),
        Memory(
            id="m2",
            text="User works at Amazon",
            trust=0.9,
            timestamp=1706745600  # Feb 2024
        )
    ]
    
    output = "You work at Amazon"
    result = verifier.verify(output, memories)
    
    print(f"Memories:")
    print(f"  - m1: Microsoft (Jan 2024, trust=0.9)")
    print(f"  - m2: Amazon (Feb 2024, trust=0.9)")
    print(f"\nOutput: {output}")
    print(f"Passed: {result.passed}")
    print(f"Contradicted claims: {result.contradicted_claims}")
    print(f"Requires disclosure: {result.requires_disclosure}")
    print(f"Expected disclosure: {result.expected_disclosure}")
    
    if result.corrected:
        print(f"Corrected (strict mode): {result.corrected}")
    
    # Example 2: Properly disclosed contradiction
    print("\n2. DISCLOSED CONTRADICTION (PASSES)")
    print("-" * 70)
    
    output_disclosed = "You work at Amazon. You previously worked at Microsoft."
    result2 = verifier.verify(output_disclosed, memories)
    
    print(f"Output: {output_disclosed}")
    print(f"Passed: {result2.passed}")
    print(f"Requires disclosure: {result2.requires_disclosure}")
    print(f"Contradictions detected: {len(result2.contradiction_details)}")
    
    # Example 3: Multiple contradictions
    print("\n3. MULTIPLE CONTRADICTIONS")
    print("-" * 70)
    
    memories3 = [
        Memory(
            id="m1",
            text="User works at Microsoft in Seattle",
            trust=0.85,
            timestamp=1704067200
        ),
        Memory(
            id="m2",
            text="User works at Amazon in Portland",
            trust=0.85,
            timestamp=1709337600
        )
    ]
    
    output3 = "You live in Portland and work at Amazon"
    result3 = verifier.verify(output3, memories3)
    
    print(f"Memories:")
    print(f"  - m1: Seattle, Microsoft (Jan 2024)")
    print(f"  - m2: Portland, Amazon (Mar 2024)")
    print(f"\nOutput: {output3}")
    print(f"Passed: {result3.passed}")
    print(f"Contradictions found: {len(result3.contradiction_details)}")
    for c in result3.contradiction_details:
        print(f"  - {c.slot}: {' vs '.join(c.values)}")
    print(f"Requires disclosure: {result3.requires_disclosure}")
    
    # Example 4: Trust-weighted contradiction (no disclosure required)
    print("\n4. LOW-TRUST CONTRADICTION (PASSES - NO DISCLOSURE NEEDED)")
    print("-" * 70)
    
    memories4 = [
        Memory(
            id="m1",
            text="User works at Microsoft",
            trust=0.2  # Very low trust
        ),
        Memory(
            id="m2",
            text="User works at Amazon",
            trust=0.95  # High trust
        )
    ]
    
    output4 = "You work at Amazon"
    result4 = verifier.verify(output4, memories4)
    
    print(f"Memories:")
    print(f"  - m1: Microsoft (trust=0.2 - unreliable)")
    print(f"  - m2: Amazon (trust=0.95 - reliable)")
    print(f"\nOutput: {output4}")
    print(f"Passed: {result4.passed}")
    print(f"Requires disclosure: {result4.requires_disclosure}")
    print(f"Note: Large trust difference (0.75) means low-trust memory is")
    print(f"      considered noise and doesn't require disclosure")
    
    # Example 5: No contradiction (additive facts)
    print("\n5. ADDITIVE FACTS - NOT A CONTRADICTION")
    print("-" * 70)
    
    memories5 = [
        Memory(id="m1", text="User knows Python"),
        Memory(id="m2", text="User knows JavaScript")
    ]
    
    output5 = "You use Python and JavaScript"
    result5 = verifier.verify(output5, memories5)
    
    print(f"Memories:")
    print(f"  - m1: Knows Python")
    print(f"  - m2: Knows JavaScript")
    print(f"\nOutput: {output5}")
    print(f"Passed: {result5.passed}")
    print(f"Contradictions: {len(result5.contradiction_details)}")
    print(f"Note: Programming languages are additive, not contradictory.")
    print(f"      A person can know multiple languages.")
    
    # Example 6: Correction with disclosure
    print("\n6. AUTOMATIC CORRECTION WITH DISCLOSURE (STRICT MODE)")
    print("-" * 70)
    
    memories6 = [
        Memory(id="m1", text="User works at Microsoft", timestamp=1704067200, trust=0.85),
        Memory(id="m2", text="User works at Amazon", timestamp=1706745600, trust=0.85)
    ]
    
    output6 = "You work at Amazon"
    result6 = verifier.verify(output6, memories6, mode="strict")
    
    print(f"Original: {output6}")
    print(f"Passed: {result6.passed}")
    print(f"Corrected: {result6.corrected}")
    print(f"Note: Strict mode adds disclosure automatically")
    
    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)
    print("\nKey Features:")
    print("  ✓ Detects contradictions in mutually exclusive facts")
    print("  ✓ Verifies proper disclosure in generated outputs")
    print("  ✓ Uses trust scores to filter noise")
    print("  ✓ Generates disclosure suggestions")
    print("  ✓ Distinguishes contradictory vs. additive facts")
    print("\nThis is the novel contribution that differentiates GroundCheck")
    print("from SelfCheckGPT, CoVe, and RARR!")
    print("=" * 70)


if __name__ == "__main__":
    main()
