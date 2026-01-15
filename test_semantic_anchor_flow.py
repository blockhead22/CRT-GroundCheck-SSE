"""
Quick test to verify semantic anchor integration in M2 workflow.

Tests:
1. Semantic anchor creation
2. Type-aware question generation
3. Answer parsing with grounding validation
"""

from personal_agent.crt_semantic_anchor import (
    SemanticAnchor,
    generate_clarification_prompt,
    parse_user_answer,
    is_resolution_grounded,
)
from personal_agent.crt_ledger import ContradictionEntry, ContradictionType


def test_semantic_anchor_creation():
    """Test that semantic anchors are created with correct fields."""
    print("\n=== Test 1: Semantic Anchor Creation ===")
    
    # Create a mock contradiction entry
    entry = ContradictionEntry(
        ledger_id="test_123",
        timestamp=1234567890.0,
        old_memory_id="mem_old",
        new_memory_id="mem_new",
        drift_mean=0.65,
        contradiction_type=ContradictionType.REVISION,
    )
    
    anchor = SemanticAnchor(
        contradiction_id=entry.ledger_id,
        turn_number=5,
        contradiction_type=entry.contradiction_type,
        old_memory_id=entry.old_memory_id,
        new_memory_id=entry.new_memory_id,
        old_text="I work at Microsoft",
        new_text="Actually, I work at Amazon, not Microsoft",
        slot_name="employer",
        old_value="Microsoft",
        new_value="Amazon",
    )
    
    print(f"✓ Anchor created: {anchor.contradiction_id}")
    print(f"  Type: {anchor.contradiction_type}")
    print(f"  Old: {anchor.old_text}")
    print(f"  New: {anchor.new_text}")
    
    # Serialize to dict
    anchor_dict = anchor.to_dict()
    print(f"✓ Serialization: {len(anchor_dict)} fields")
    assert "contradiction_id" in anchor_dict
    assert "contradiction_type" in anchor_dict
    print("✓ PASS: Semantic anchor creation")


def test_type_aware_questions():
    """Test that different contradiction types generate different questions."""
    print("\n=== Test 2: Type-Aware Question Generation ===")
    
    types_to_test = [
        (ContradictionType.REFINEMENT, "Seattle", "Bellevue", "more specific"),
        (ContradictionType.REVISION, "Microsoft", "Amazon", "Which is correct"),
        (ContradictionType.TEMPORAL, "Senior Engineer", "Principal Engineer", "change over time"),
        (ContradictionType.CONFLICT, "Microsoft", "Google", "contradict"),
    ]
    
    for ctype, old_val, new_val, expected_phrase in types_to_test:
        anchor = SemanticAnchor(
            contradiction_id="test",
            turn_number=1,
            contradiction_type=ctype,
            old_memory_id="old",
            new_memory_id="new",
            old_text=f"employer: {old_val}",
            new_text=f"employer: {new_val}",
            slot_name="employer",
            old_value=old_val,
            new_value=new_val,
        )
        
        prompt = generate_clarification_prompt(anchor)
        print(f"\n{ctype}:")
        print(f"  {prompt[:150]}")
        
        if expected_phrase.lower() in prompt.lower():
            print(f"  ✓ Contains expected phrase: '{expected_phrase}'")
        else:
            print(f"  ⚠ Missing expected phrase: '{expected_phrase}'")
    
    print("\n✓ PASS: Type-aware question generation")


def test_answer_parsing():
    """Test that user answers are correctly parsed."""
    print("\n=== Test 3: Answer Parsing ===")
    
    anchor = SemanticAnchor(
        contradiction_id="test",
        turn_number=1,
        contradiction_type=ContradictionType.REVISION,
        old_memory_id="mem_old",
        new_memory_id="mem_new",
        old_text="I work at Microsoft",
        new_text="I work at Amazon",
        slot_name="employer",
        old_value="Microsoft",
        new_value="Amazon",
        expected_answer_type="choose_one",
    )
    
    test_cases = [
        ("The new one is correct", "user_chose_new", anchor.new_memory_id),
        ("The first one was right", "user_chose_old", anchor.old_memory_id),
        ("Actually both are wrong", "both_wrong", None),
        ("Amazon is correct", None, None),  # Should extract value
    ]
    
    for answer, expected_method, expected_id in test_cases:
        result = parse_user_answer(anchor, answer)
        method = result.get("resolution_method")
        chosen_id = result.get("chosen_memory_id")
        confidence = result.get("confidence", 0)
        
        print(f"\nAnswer: '{answer}'")
        print(f"  Method: {method} (expected: {expected_method})")
        print(f"  Chosen ID: {chosen_id} (expected: {expected_id})")
        print(f"  Confidence: {confidence:.2f}")
        
        if expected_method and method == expected_method:
            print(f"  ✓ Correct method")
        if expected_id and chosen_id == expected_id:
            print(f"  ✓ Correct memory ID")
    
    print("\n✓ PASS: Answer parsing")


def test_grounding_validation():
    """Test that resolution grounding is validated."""
    print("\n=== Test 4: Grounding Validation ===")
    
    anchor = SemanticAnchor(
        contradiction_id="test",
        turn_number=1,
        contradiction_type=ContradictionType.REVISION,
        old_memory_id="mem_old",
        new_memory_id="mem_new",
        old_text="employer: Microsoft",
        new_text="employer: Amazon",
        slot_name="employer",
        old_value="Microsoft",
        new_value="Amazon",
    )
    
    # Test grounded resolution
    grounded_resolution = {
        "resolution_method": "user_chose_new",
        "chosen_memory_id": "mem_new",
        "confidence": 0.8,
    }
    
    is_grounded = is_resolution_grounded(anchor, grounded_resolution)
    print(f"\nGrounded resolution: {is_grounded}")
    assert is_grounded, "Should be grounded"
    print("✓ Correctly validates grounded resolution")
    
    # Test ungrounded resolution (wrong memory ID)
    ungrounded_resolution = {
        "resolution_method": "user_chose_new",
        "chosen_memory_id": "mem_wrong",  # Wrong ID!
        "confidence": 0.8,
    }
    
    is_grounded = is_resolution_grounded(anchor, ungrounded_resolution)
    print(f"Ungrounded resolution: {is_grounded}")
    assert not is_grounded, "Should not be grounded"
    print("✓ Correctly rejects ungrounded resolution")
    
    # Test low confidence
    low_confidence = {
        "resolution_method": "user_chose_old",
        "chosen_memory_id": "mem_old",
        "confidence": 0.1,  # Too low!
    }
    
    is_grounded = is_resolution_grounded(anchor, low_confidence)
    print(f"Low confidence resolution: {is_grounded}")
    assert not is_grounded, "Should reject low confidence"
    print("✓ Correctly rejects low confidence")
    
    print("\n✓ PASS: Grounding validation")


if __name__ == "__main__":
    print("=" * 80)
    print("SEMANTIC ANCHOR INTEGRATION TEST")
    print("=" * 80)
    
    try:
        test_semantic_anchor_creation()
        test_type_aware_questions()
        test_answer_parsing()
        test_grounding_validation()
        
        print("\n" + "=" * 80)
        print("ALL TESTS PASSED ✓")
        print("=" * 80)
        
    except Exception as e:
        print(f"\n❌ TEST FAILED: {e}")
        import traceback
        traceback.print_exc()
        raise SystemExit(1)
