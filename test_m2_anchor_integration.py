"""
M2 Semantic Anchor Integration Verification

This script verifies that the full M2 contradiction resolution flow
works correctly with semantic anchors, without needing to start the API server.

Tests the local engine directly.
"""

import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from personal_agent.crt_rag import CRTEnhancedRAG
from personal_agent.crt_ledger import ContradictionType
from personal_agent.crt_semantic_anchor import (
    generate_clarification_prompt,
    parse_user_answer,
    is_resolution_grounded,
)


def test_m2_flow():
    """Test the full M2 flow with semantic anchors."""
    print("=" * 80)
    print("M2 SEMANTIC ANCHOR INTEGRATION TEST")
    print("=" * 80)
    
    # Create a fresh engine
    engine = CRTEnhancedRAG(
        memory_db="test_m2_anchor_memory.db",
        ledger_db="test_m2_anchor_ledger.db",
    )
    
    # Reset databases
    import sqlite3
    for db_path in ["test_m2_anchor_memory.db", "test_m2_anchor_ledger.db"]:
        if os.path.exists(db_path):
            os.remove(db_path)
    
    # Recreate engine with fresh DBs
    engine = CRTEnhancedRAG(
        memory_db="test_m2_anchor_memory.db",
        ledger_db="test_m2_anchor_ledger.db",
    )
    
    print("\n1. Create initial memory:")
    print("   User: 'I work at Microsoft'")
    result1 = engine.query("I work at Microsoft")
    print(f"   Response: {result1.get('answer', '')[:100]}")
    
    print("\n2. Create contradicting memory:")
    print("   User: 'Actually, I work at Amazon, not Microsoft'")
    result2 = engine.query("Actually, I work at Amazon, not Microsoft")
    print(f"   Response: {result2.get('answer', '')[:100]}")
    
    print("\n3. Check for contradiction detection:")
    entries = engine.ledger.get_open_contradictions(limit=10)
    if entries:
        print(f"   ✓ Detected {len(entries)} contradiction(s)")
        entry = entries[0]
        print(f"   Ledger ID: {entry.ledger_id}")
        print(f"   Type: {entry.contradiction_type}")
        print(f"   Drift: {entry.drift_mean:.3f}")
    else:
        print("   ✗ No contradictions detected")
        return False
    
    print("\n4. Create semantic anchor:")
    try:
        # Get memory texts
        old_mem_id = entry.old_memory_id
        new_mem_id = entry.new_memory_id
        
        old_mem = engine.memory.get_memory_by_id(old_mem_id)
        new_mem = engine.memory.get_memory_by_id(new_mem_id)
        
        if old_mem and new_mem:
            old_text = old_mem.text
            new_text = new_mem.text
            
            print(f"   Old memory: {old_text[:80]}")
            print(f"   New memory: {new_text[:80]}")
            
            # Create anchor
            anchor = engine.ledger.create_semantic_anchor(
                entry=entry,
                old_text=old_text,
                new_text=new_text,
                turn_number=2,
            )
            
            print(f"   ✓ Anchor created")
            print(f"   Contradiction type: {anchor.contradiction_type}")
            print(f"   Expected answer: {anchor.expected_answer_type}")
        else:
            print("   ✗ Could not retrieve memories")
            return False
            
    except Exception as e:
        print(f"   ✗ Anchor creation failed: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    print("\n5. Generate clarification prompt:")
    prompt = generate_clarification_prompt(anchor)
    print(f"   {prompt[:150]}")
    
    print("\n6. Parse user answer:")
    user_answer = "The new one is correct - I work at Amazon now"
    print(f"   User: '{user_answer}'")
    
    resolution = parse_user_answer(anchor, user_answer)
    print(f"   Method: {resolution.get('resolution_method')}")
    print(f"   Chosen ID: {resolution.get('chosen_memory_id')}")
    print(f"   Confidence: {resolution.get('confidence'):.2f}")
    
    print("\n7. Validate grounding:")
    is_grounded = is_resolution_grounded(anchor, resolution)
    print(f"   Grounded: {is_grounded}")
    
    if is_grounded:
        print("   ✓ Resolution is properly grounded")
    else:
        print("   ✗ Resolution failed grounding check")
        return False
    
    print("\n8. Apply resolution:")
    try:
        engine.ledger.resolve_contradiction(
            ledger_id=entry.ledger_id,
            method=resolution.get("resolution_method", "user_clarified"),
            merged_memory_id=resolution.get("chosen_memory_id"),
            new_status=resolution.get("new_status", "resolved"),
        )
        print("   ✓ Contradiction resolved")
    except Exception as e:
        print(f"   ✗ Resolution failed: {e}")
        return False
    
    print("\n9. Verify resolution:")
    open_entries = engine.ledger.get_open_contradictions(limit=10)
    print(f"   Open contradictions: {len(open_entries)}")
    if len(open_entries) == 0:
        print("   ✓ Contradiction successfully cleared")
    else:
        print("   ⚠ Contradiction still open")
    
    # Cleanup
    for db_path in ["test_m2_anchor_memory.db", "test_m2_anchor_ledger.db"]:
        if os.path.exists(db_path):
            os.remove(db_path)
    
    return True


if __name__ == "__main__":
    print()
    try:
        success = test_m2_flow()
        if success:
            print("\n" + "=" * 80)
            print("✅ M2 SEMANTIC ANCHOR INTEGRATION: PASS")
            print("=" * 80)
            print()
            sys.exit(0)
        else:
            print("\n" + "=" * 80)
            print("❌ M2 SEMANTIC ANCHOR INTEGRATION: FAIL")
            print("=" * 80)
            print()
            sys.exit(1)
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
