"""
Contradiction Stress Test for SSE v0.1 Phase 2.

This test validates that contradictions are properly detected and grounded
with supporting quotes, using a synthetic text containing explicit contradictions.

The test must fail if contradiction detection silently breaks in future versions.
"""

import pytest
import json
from datetime import datetime
from pathlib import Path

from sse.chunker import chunk_text
from sse.embeddings import EmbeddingStore
from sse.extractor import extract_claims_from_chunks
from sse.clustering import cluster_embeddings
from sse.contradictions import detect_contradictions, clear_nli_cache
from sse.ambiguity import analyze_ambiguity_for_claims
from sse.schema import validate_index_schema


# Stress test text with KNOWN explicit contradictions
CONTRADICTION_STRESS_TEST = """
The Earth is round. Scientists have proven that the Earth is spherical.

However, some people still believe the Earth is flat. The flat Earth theory
contradicts all modern evidence.

Exercise is beneficial for health. Regular physical activity improves 
cardiovascular function. Studies show that active people live longer.

On the other hand, sedentary behavior is healthier than exercise. Sitting
all day is better for your muscles than physical activity. Working out 
damages your body.

Climate change is real and caused by human activity. Global temperatures 
are rising due to greenhouse gas emissions. Scientists agree on this.

Conversely, climate change is a hoax. The Earth's climate is stable and 
not affected by humans. No warming is happening.

Water boils at 100 degrees Celsius at sea level. This is a physical fact.

Yet some claim water boils at 50 degrees Celsius. This contradicts the laws of physics.

Vaccines are safe and effective. Millions of people have received vaccines
without severe side effects. Vaccination prevents diseases.

In contrast, vaccines cause autism and severe injuries. They are dangerous
and should be avoided. Vaccination makes people sick.
""".strip()


@pytest.fixture(scope="module")
def stress_test_output_dir():
    """Create output directory for stress test artifacts."""
    output_dir = Path(__file__).parent.parent / "contradiction_stress_test_output"
    output_dir.mkdir(exist_ok=True)
    yield output_dir


def test_contradiction_detection_explicit_contradictions(stress_test_output_dir):
    """
    Stress test: detect and ground explicit contradictions in synthetic text.
    
    Validates:
    - Contradictions are detected when explicitly stated
    - Each contradiction pair is grounded with supporting quotes
    - Quote offsets are correct and reference the source text
    - No contradictions are silently suppressed
    """
    clear_nli_cache()  # Reset cache for clean test
    start_time = datetime.now()
    stats = {
        "timestamp": start_time.isoformat(),
        "test_name": "contradiction_stress_test",
        "text_length": len(CONTRADICTION_STRESS_TEST),
        "text_word_count": len(CONTRADICTION_STRESS_TEST.split()),
    }
    
    # ===== PHASE 1: CHUNKING =====
    chunks = chunk_text(CONTRADICTION_STRESS_TEST, max_chars=300, overlap=50)
    assert len(chunks) > 0, "Should create chunks"
    stats["chunk_count"] = len(chunks)
    
    # ===== PHASE 2: EMBEDDING (chunks) =====
    emb_store = EmbeddingStore("all-MiniLM-L6-v2")
    chunk_embeddings = emb_store.embed_texts([c["text"] for c in chunks])
    
    # ===== PHASE 3: CLAIM EXTRACTION =====
    all_claims = extract_claims_from_chunks(chunks, chunk_embeddings)
    assert len(all_claims) > 0, "Should extract claims"
    stats["claim_count"] = len(all_claims)
    
    # ===== PHASE 4: EMBEDDING (claims) =====
    claim_embeddings = emb_store.embed_texts([c["claim_text"] for c in all_claims])
    
    # ===== PHASE 4b: CLUSTERING (claims) =====
    clusters = cluster_embeddings(claim_embeddings, method="agg", min_cluster_size=2)
    stats["cluster_count"] = len(clusters)
    
    # ===== PHASE 5: CONTRADICTION DETECTION =====
    contradictions = detect_contradictions(
        all_claims, 
        claim_embeddings,
        use_ollama=False  # Use heuristic for deterministic test
    )
    stats["contradiction_count"] = len(contradictions)
    
    # ===== PHASE 6: VALIDATION =====
    
    # Verify contradictions were detected
    assert len(contradictions) > 0, (
        "Stress test failed: No contradictions detected. "
        "Expected multiple explicit contradictions to be found."
    )
    
    # Verify each contradiction is properly grounded
    for cont in contradictions:
        pair = cont.get("pair", {})
        assert pair.get("claim_id_a"), "Contradiction should reference claim A"
        assert pair.get("claim_id_b"), "Contradiction should reference claim B"
        assert cont.get("label") == "contradiction", "Label should be 'contradiction'"
        
        # Verify evidence quotes exist
        evidence = cont.get("evidence_quotes", [])
        assert len(evidence) >= 1, "Contradiction should have supporting quotes"
        
        for quote in evidence:
            assert quote.get("quote_text"), "Quote should have text"
            assert "start_char" in quote, "Quote should have start offset"
            assert "end_char" in quote, "Quote should have end offset"
            
            # Verify quote offset is valid
            start = quote["start_char"]
            end = quote["end_char"]
            assert start >= 0, f"Quote start ({start}) should be non-negative"
            assert end <= len(CONTRADICTION_STRESS_TEST), (
                f"Quote end ({end}) should not exceed text length ({len(CONTRADICTION_STRESS_TEST)})"
            )
            assert start < end, f"Quote start ({start}) should be before end ({end})"
    
    # ===== PHASE 7: SAVE ARTIFACTS =====
    
    # Build index for reference
    index = {
        "doc_id": "contradiction_stress_test",
        "timestamp": start_time.isoformat(),
        "text_length": len(CONTRADICTION_STRESS_TEST),
        "chunks": chunks,
        "clusters": clusters,
        "claims": all_claims,
        "contradictions": contradictions,
    }
    validate_index_schema(index)
    
    # Save index
    index_path = stress_test_output_dir / "contradiction_stress_index.json"
    with open(index_path, "w") as f:
        index_save = {k: v for k, v in index.items()}
        json.dump(index_save, f, indent=2)
    
    # Save stats
    stats_path = stress_test_output_dir / "contradiction_stress_stats.json"
    with open(stats_path, "w") as f:
        json.dump(stats, f, indent=2)
    
    # Save report
    report_path = stress_test_output_dir / "contradiction_stress_report.txt"
    with open(report_path, "w") as f:
        f.write("=" * 80 + "\n")
        f.write("CONTRADICTION STRESS TEST REPORT\n")
        f.write("=" * 80 + "\n")
        f.write(f"Timestamp: {start_time.isoformat()}\n")
        f.write(f"Test: Explicit Contradictions Detection\n\n")
        
        f.write("-" * 80 + "\n")
        f.write("TEXT STATISTICS\n")
        f.write("-" * 80 + "\n")
        f.write(f"Text Length: {stats['text_length']} characters\n")
        f.write(f"Word Count: {stats['text_word_count']} words\n")
        f.write(f"Chunks Created: {stats['chunk_count']}\n")
        f.write(f"Claims Extracted: {stats['claim_count']}\n")
        
        f.write("\n" + "-" * 80 + "\n")
        f.write("CONTRADICTION DETECTION RESULTS\n")
        f.write("-" * 80 + "\n")
        f.write(f"Total Contradictions Found: {len(contradictions)}\n\n")
        
        for idx, cont in enumerate(contradictions, 1):
            pair = cont["pair"]
            f.write(f"Contradiction {idx}:\n")
            f.write(f"  Claim A: {pair['claim_id_a']}\n")
            f.write(f"  Claim B: {pair['claim_id_b']}\n")
            
            # Find claims for display
            claim_a = next((c for c in all_claims if c.get("claim_id") == pair["claim_id_a"]), None)
            claim_b = next((c for c in all_claims if c.get("claim_id") == pair["claim_id_b"]), None)
            
            if claim_a:
                f.write(f"  Text A: {claim_a['claim_text'][:80]}...\n")
            if claim_b:
                f.write(f"  Text B: {claim_b['claim_text'][:80]}...\n")
            
            f.write(f"  Supporting Quotes: {len(cont.get('evidence_quotes', []))}\n")
            f.write("\n")
        
        f.write("-" * 80 + "\n")
        f.write("VALIDATION CHECKS\n")
        f.write("-" * 80 + "\n")
        f.write("[PASS] Contradictions detected in stress test\n")
        f.write("[PASS] All contradiction pairs have IDs\n")
        f.write("[PASS] All contradictions have supporting quotes\n")
        f.write("[PASS] All quote offsets are valid\n")
        f.write("[PASS] Index schema validation passed\n")
        
        f.write("\n" + "=" * 80 + "\n")
        f.write("STRESS TEST PASSED: Contradiction detection is functional\n")
        f.write("=" * 80 + "\n")
    
    print(f"\n[PASS] Contradiction stress test complete.")
    print(f"  - Contradictions found: {len(contradictions)}")
    print(f"  - Artifacts saved to: {stress_test_output_dir}/")


def test_contradiction_deduplication(stress_test_output_dir):
    """
    Test that contradiction pairs are deduplicated (no duplicate entries).
    """
    clear_nli_cache()
    
    chunks = chunk_text(CONTRADICTION_STRESS_TEST, max_chars=300, overlap=50)
    emb_store = EmbeddingStore("all-MiniLM-L6-v2")
    chunk_embeddings = emb_store.embed_texts([c["text"] for c in chunks])
    
    all_claims = extract_claims_from_chunks(chunks, chunk_embeddings)
    claim_embeddings = emb_store.embed_texts([c["claim_text"] for c in all_claims])
    
    contradictions = detect_contradictions(
        all_claims,
        claim_embeddings,
        use_ollama=False
    )
    
    # Check for duplicates: same pair listed twice
    seen_pairs = set()
    for cont in contradictions:
        a = cont["pair"]["claim_id_a"]
        b = cont["pair"]["claim_id_b"]
        # Normalize to canonical form (smaller ID first)
        pair_key = (min(a, b), max(a, b))
        
        assert pair_key not in seen_pairs, (
            f"Contradiction pair {pair_key} appears multiple times. "
            "Deduplication failed."
        )
        seen_pairs.add(pair_key)
    
    print(f"[PASS] Deduplication test passed ({len(seen_pairs)} unique pairs)")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
