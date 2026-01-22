#!/usr/bin/env python3
"""Demonstration of GroundCheck neural features.

This script demonstrates the hybrid fact extraction and semantic matching
capabilities with graceful fallback when neural dependencies are unavailable.
"""

from groundcheck import GroundCheck, Memory

def demo_basic_grounding():
    """Demonstrate basic grounding verification."""
    print("=" * 60)
    print("1. Basic Grounding Verification")
    print("=" * 60)
    
    verifier = GroundCheck()
    
    memories = [
        Memory(id="m1", text="User works at Microsoft", trust=0.9),
        Memory(id="m2", text="User lives in Seattle", trust=0.85)
    ]
    
    # Grounded output
    result = verifier.verify("You work at Microsoft and live in Seattle", memories)
    print(f"✓ Grounded text: PASSED={result.passed}")
    
    # Hallucinated output
    result = verifier.verify("You work at Amazon and live in Boston", memories)
    print(f"✗ Hallucinated text: PASSED={result.passed}")
    print(f"  Hallucinations detected: {result.hallucinations}")
    print()

def demo_paraphrase_handling():
    """Demonstrate semantic paraphrase handling."""
    print("=" * 60)
    print("2. Paraphrase Detection (Semantic Matching)")
    print("=" * 60)
    
    verifier = GroundCheck()
    
    memories = [
        Memory(id="m1", text="User works at Google", trust=0.9)
    ]
    
    # Various paraphrases of the same fact
    paraphrases = [
        "You work at Google",
        "You're employed by Google",
        "Your employer is Google",
        "You have a job at Google",
    ]
    
    for text in paraphrases:
        result = verifier.verify(text, memories)
        status = "✓ PASSED" if result.passed else "✗ FAILED"
        print(f"{status}: '{text}'")
    print()

def demo_hybrid_extraction():
    """Demonstrate hybrid fact extraction."""
    print("=" * 60)
    print("3. Hybrid Fact Extraction (Regex + Neural)")
    print("=" * 60)
    
    try:
        from groundcheck import HybridFactExtractor
        
        extractor = HybridFactExtractor(use_neural=False)  # Regex-only for demo
        
        texts = [
            "I work at Microsoft",
            "My name is Alice and I live in Seattle",
            "Software engineer at Google based in San Francisco"
        ]
        
        for text in texts:
            result = extractor.extract(text)
            print(f"Text: '{text}'")
            print(f"  Method: {result.method}")
            print(f"  Confidence: {result.confidence:.2f}")
            print(f"  Entities: {result.entities}")
            print()
            
    except ImportError:
        print("Note: Neural extraction not available (optional dependencies not installed)")
        print("Install with: pip install groundcheck[neural]")
        print()

def demo_semantic_matcher():
    """Demonstrate semantic matching."""
    print("=" * 60)
    print("4. Semantic Matching (Multi-tier)")
    print("=" * 60)
    
    try:
        from groundcheck import SemanticMatcher
        
        matcher = SemanticMatcher(use_embeddings=False)  # No embeddings for demo
        
        test_cases = [
            ("Microsoft", {"Microsoft"}),  # Exact match
            ("microsoft", {"Microsoft"}),  # Case insensitive
            ("Microsoft", {"Microsoft Corporation"}),  # Substring
            ("works at", {"employed by"}),  # Synonym (with slot context)
        ]
        
        for claimed, supported in test_cases[:3]:
            is_match, method, matched = matcher.is_match(claimed, supported)
            print(f"Claimed: '{claimed}' vs Supported: {supported}")
            print(f"  Match: {is_match} (method: {method})")
        
        # Test with slot context for synonyms
        is_match, method, matched = matcher.is_match(
            "works at", {"employed by"}, slot="employer"
        )
        print(f"Claimed: 'works at' vs Supported: {{'employed by'}} (slot: employer)")
        print(f"  Match: {is_match} (method: {method})")
        print()
        
    except ImportError:
        print("Note: Semantic matcher not available")
        print()

def demo_contradiction_detection():
    """Demonstrate contradiction detection."""
    print("=" * 60)
    print("5. Contradiction Detection")
    print("=" * 60)
    
    verifier = GroundCheck()
    
    # Contradictory memories with different trust scores
    memories = [
        Memory(id="m1", text="User works at Microsoft", trust=0.9, timestamp=1640995200),
        Memory(id="m2", text="User works at Amazon", trust=0.85, timestamp=1656633600)
    ]
    
    # Output that acknowledges contradiction
    result = verifier.verify("You work at Amazon (changed from Microsoft)", memories)
    print(f"With disclosure: PASSED={result.passed}")
    print(f"  Contradictions detected: {len(result.contradiction_details)}")
    if result.contradiction_details:
        c = result.contradiction_details[0]
        print(f"  Conflicting values: {c.values}")
        print(f"  Most recent: {c.most_recent_value}")
    
    # Output that ignores contradiction
    result = verifier.verify("You work at Amazon", memories)
    print(f"Without disclosure: PASSED={result.passed}")
    print(f"  Requires disclosure: {result.requires_disclosure}")
    print()

def main():
    """Run all demonstrations."""
    print("\n" + "=" * 60)
    print("GroundCheck Neural Features Demo")
    print("=" * 60 + "\n")
    
    demo_basic_grounding()
    demo_paraphrase_handling()
    demo_hybrid_extraction()
    demo_semantic_matcher()
    demo_contradiction_detection()
    
    print("=" * 60)
    print("Demo Complete!")
    print("=" * 60)
    print("\nFor full neural features, install with:")
    print("  pip install groundcheck[neural]")
    print("\nThis includes:")
    print("  - Transformer-based NER for fact extraction")
    print("  - Sentence embeddings for semantic similarity")
    print("  - NLI models for contradiction detection")

if __name__ == "__main__":
    main()
