"""Basic usage example for GroundCheck library."""

from groundcheck import GroundCheck, Memory


def main():
    """Demonstrate basic GroundCheck usage."""
    
    print("=" * 60)
    print("GroundCheck - Basic Usage Example")
    print("=" * 60)
    print()
    
    # Initialize the verifier
    verifier = GroundCheck()
    print("✓ Initialized GroundCheck verifier")
    print()
    
    # Example 1: Successful verification (all claims grounded)
    print("Example 1: Fully Grounded Text")
    print("-" * 60)
    
    memories = [
        Memory(id="mem_1", text="User works at Microsoft", trust=0.9),
        Memory(id="mem_2", text="User lives in Seattle", trust=0.85)
    ]
    
    result = verifier.verify(
        "You work at Microsoft and live in Seattle",
        memories
    )
    
    print(f"Generated text: 'You work at Microsoft and live in Seattle'")
    print(f"Passed: {result.passed}")
    print(f"Hallucinations: {result.hallucinations}")
    print(f"Grounding map: {result.grounding_map}")
    print(f"Confidence: {result.confidence:.2f}")
    print()
    
    # Example 2: Hallucination detection
    print("Example 2: Hallucination Detection")
    print("-" * 60)
    
    result = verifier.verify(
        "You work at Amazon and live in Seattle",
        memories
    )
    
    print(f"Generated text: 'You work at Amazon and live in Seattle'")
    print(f"Passed: {result.passed}")
    print(f"Hallucinations: {result.hallucinations}")
    print(f"Grounding map: {result.grounding_map}")
    print(f"Confidence: {result.confidence:.2f}")
    print()
    
    # Example 3: Strict mode with correction
    print("Example 3: Strict Mode with Automatic Correction")
    print("-" * 60)
    
    result = verifier.verify(
        "You work at Amazon",
        memories,
        mode="strict"
    )
    
    print(f"Original: 'You work at Amazon'")
    print(f"Passed: {result.passed}")
    print(f"Hallucinations: {result.hallucinations}")
    print(f"Corrected: {result.corrected}")
    print()
    
    # Example 4: Fact extraction
    print("Example 4: Fact Extraction")
    print("-" * 60)
    
    claims = verifier.extract_claims(
        "My name is Alice and I work at Microsoft in Seattle"
    )
    
    print("Extracted facts:")
    for slot, fact in claims.items():
        print(f"  - {slot}: {fact.value}")
    print()
    
    # Example 5: Trust-weighted verification
    print("Example 5: Trust-Weighted Verification")
    print("-" * 60)
    
    memories_with_trust = [
        Memory(id="m1", text="User works at Microsoft", trust=0.3),
        Memory(id="m2", text="User works at Amazon", trust=0.95)
    ]
    
    result = verifier.verify(
        "You work at Amazon",
        memories_with_trust
    )
    
    print("Memories:")
    print("  - Microsoft (trust: 0.3)")
    print("  - Amazon (trust: 0.95)")
    print(f"Verifying: 'You work at Amazon'")
    print(f"Passed: {result.passed}")
    print(f"Confidence: {result.confidence:.2f}")
    print()
    
    # Example 6: Memory claim sanitization
    print("Example 6: Memory Claim Sanitization")
    print("-" * 60)
    
    memories_simple = [
        Memory(id="m1", text="User works at Microsoft")
    ]
    
    result = verifier.verify(
        "I remember you work at Amazon",
        memories_simple,
        mode="strict"
    )
    
    print(f"Original: 'I remember you work at Amazon'")
    print(f"Passed: {result.passed}")
    print(f"Hallucinations: {result.hallucinations}")
    print(f"Corrected text:")
    print(f"  {result.corrected}")
    print()
    
    print("=" * 60)
    print("Examples complete!")
    print("=" * 60)


if __name__ == "__main__":
    main()
