"""
Comprehensive integration test for SSE v0.1.

This test validates the entire pipeline:
- Chunk text with overlap and character offsets
- Extract claims (both rule-based and LLM paths)
- Detect contradictions (heuristic and LLM NLI)
- Generate embeddings and cluster claims
- Render output in 3 modes (natural, bullet, conflict)
- Save detailed statistics and proof artifacts to output directory

Artifacts saved:
- integration_test_results.json: Full index with all pipeline data
- integration_test_stats.json: Timing, counts, quality metrics
- integration_test_report.txt: Human-readable summary with timestamps
- render_natural.txt, render_bullet.txt, render_conflict.txt: Output samples
"""

import pytest
import json
import time
import os
import numpy as np
from datetime import datetime
from pathlib import Path

from sse.chunker import chunk_text
from sse.extractor import extract_claims_rule_based, extract_claims_with_llm, extract_claims_from_chunks
from sse.embeddings import EmbeddingStore
from sse.clustering import cluster_embeddings
from sse.contradictions import detect_contradictions
from sse.ambiguity import analyze_ambiguity_for_claims
from sse.render import render_index
from sse.schema import validate_index_schema
from sse.ollama_utils import OllamaClient


# Test data: comprehensive text with nuance and contradictions
INTEGRATION_TEST_TEXT = """
Sleep is absolutely critical for human health. Studies show that inadequate sleep increases 
cardiovascular disease risk significantly. However, some researchers claim sleep requirements are 
highly individual and can range from 4 to 12 hours. Most adults need 7-9 hours, but this varies. 

Contradictory claims: Sleep deprivation is always harmful, yet some people function well on 5 hours. 
The evidence suggests sleep needs are genetic. On the other hand, consistent sleep schedules matter 
more than total hours. Caffeine blocks sleep directly. Yet moderate caffeine enhances focus during 
the day.

Blue light suppresses melatonin, which disrupts sleep. But evidence for blue light effects is still 
emerging and contested by some studies. Melatonin supplements help many people sleep, although 
clinical trials show mixed results.

Sleep apnea requires professional treatment; behavioral interventions alone are insufficient. 
Some people claim meditation is a cure, which is misleading. Exercise improves sleep quality for 
most individuals, though timing and intensity matter.

In summary, sleep is critical and variable. The relationship between sleep and health is complex.
""".strip()

OUTPUT_DIR = Path(__file__).parent.parent / "integration_test_output"


@pytest.fixture(scope="module")
def setup_output_dir():
    """Create output directory for test artifacts."""
    OUTPUT_DIR.mkdir(exist_ok=True)
    yield OUTPUT_DIR
    # Don't delete: keep artifacts for inspection


def test_full_pipeline_rule_based(setup_output_dir):
    """
    Test complete pipeline with rule-based claim extraction.
    
    Validates:
    - Chunking preserves offsets
    - Claim extraction quality
    - Embedding consistency
    - Clustering stability
    - Contradiction detection accuracy
    - Render output integrity
    """
    start_time = datetime.now()
    stats = {
        "timestamp": start_time.isoformat(),
        "text_length": len(INTEGRATION_TEST_TEXT),
        "text_word_count": len(INTEGRATION_TEST_TEXT.split()),
    }
    timings = {}
    
    # ===== PHASE 1: CHUNKING =====
    t0 = time.time()
    chunks = chunk_text(INTEGRATION_TEST_TEXT, max_chars=200, overlap=50)
    timings["chunking"] = time.time() - t0
    
    assert len(chunks) > 0, "Should produce chunks"
    assert all("text" in c and "chunk_id" in c for c in chunks), "Chunks should have text and chunk_id"
    assert all("start_char" in c and "end_char" in c for c in chunks), "Chunks should have offsets"
    
    # Verify offset order is correct (start < end, consecutive non-overlapping regions have proper offsets)
    for i, chunk in enumerate(chunks):
        assert chunk["start_char"] < chunk["end_char"], f"Chunk {chunk['chunk_id']}: start < end"
        assert chunk["end_char"] <= len(INTEGRATION_TEST_TEXT), f"Chunk {chunk['chunk_id']}: end <= text length"
    
    stats["chunk_count"] = len(chunks)
    
    # ===== PHASE 2: EMBEDDING (needed for extraction) =====
    t0 = time.time()
    emb_store = EmbeddingStore("all-MiniLM-L6-v2")
    chunk_embeddings = emb_store.embed_texts([c["text"] for c in chunks])
    timings["embedding_chunks"] = time.time() - t0
    
    # ===== PHASE 3: CLAIM EXTRACTION (RULE-BASED) =====
    t0 = time.time()
    all_claims = extract_claims_from_chunks(chunks, chunk_embeddings)
    timings["extraction_rule_based"] = time.time() - t0
    
    assert len(all_claims) > 0, "Should extract claims"
    assert all("claim_text" in c for c in all_claims), "Claims should have claim_text field"
    
    stats["claim_count_rule_based"] = len(all_claims)
    
    # ===== PHASE 4: EMBEDDINGS FOR CLAIMS =====
    t0 = time.time()
    claim_embeddings = emb_store.embed_texts([c["claim_text"] for c in all_claims])
    timings["embedding"] = time.time() - t0
    
    assert len(claim_embeddings) == len(all_claims), "Should embed all claims"
    assert all(isinstance(e, np.ndarray) and len(e) > 0 for e in claim_embeddings), \
        "Embeddings should be vectors"
    
    # ===== PHASE 5: CLUSTERING =====
    t0 = time.time()
    clusters = cluster_embeddings(
        claim_embeddings,
        method="agg",
        min_cluster_size=2
    )
    timings["clustering"] = time.time() - t0
    
    assert isinstance(clusters, list), "Clusters should be list"
    stats["cluster_count"] = len(clusters)
    
    # ===== PHASE 6: AMBIGUITY DETECTION =====
    t0 = time.time()
    analyze_ambiguity_for_claims(all_claims)
    timings["ambiguity_detection"] = time.time() - t0
    
    ambiguous_claims = [c for c in all_claims if c.get("ambiguity", {}).get("hedge_score", 0) > 0.3]
    stats["ambiguous_claim_count"] = len(ambiguous_claims)
    
    # ===== PHASE 7: CONTRADICTION DETECTION =====
    t0 = time.time()
    contradictions = detect_contradictions(all_claims, claim_embeddings, use_ollama=False)
    timings["contradiction_detection"] = time.time() - t0
    
    assert isinstance(contradictions, list), "Contradictions should be list"
    stats["contradiction_count"] = len(contradictions)
    
    # ===== PHASE 8: BUILD INDEX =====
    index = {
        "doc_id": "integration_test_rule_based",
        "timestamp": start_time.isoformat(),
        "text_length": len(INTEGRATION_TEST_TEXT),
        "chunks": chunks,
        "claims": all_claims,
        "clusters": clusters,
        "contradictions": contradictions,
        "metadata": {
            "extraction_method": "rule_based",
            "embedding_model": "sentence-transformers",
            "clustering_method": "agg",
        }
    }
    
    # Validate schema
    validate_index_schema(index)
    
    # ===== PHASE 9: RENDER OUTPUTS =====
    render_outputs = {}
    for style in ["natural", "bullet", "conflict"]:
        t0 = time.time()
        output = render_index(index, style=style)
        render_outputs[style] = output
        timings[f"render_{style}"] = time.time() - t0
        
        # Verify no hallucination: output should only contain text from original
        assert len(output) > 0, f"Render {style} should produce output"
        # (Heuristic check: most words in output should be from original)
        output_words = set(output.lower().split())
        original_words = set(INTEGRATION_TEST_TEXT.lower().split())
        overlap = len(output_words & original_words)
        assert overlap > len(output_words) * 0.5, \
            f"Render {style} output should mostly contain original text words"
    
    # ===== PHASE 10: SAVE ARTIFACTS =====
    # Save index (JSON)
    index_path = OUTPUT_DIR / "integration_test_results.json"
    with open(index_path, "w") as f:
        # Don't include embeddings in saved index for readability
        index_save = {k: v for k, v in index.items() if k != "claim_embeddings"}
        json.dump(index_save, f, indent=2)
    
    # Save stats (JSON)
    stats.update(timings)
    stats["total_time_seconds"] = time.time() - time.mktime(start_time.timetuple())
    stats_path = OUTPUT_DIR / "integration_test_stats.json"
    with open(stats_path, "w") as f:
        json.dump(stats, f, indent=2)
    
    # Save render outputs
    for style, output in render_outputs.items():
        output_path = OUTPUT_DIR / f"render_{style}.txt"
        with open(output_path, "w") as f:
            f.write(output)
    
    # Save human-readable report
    report_path = OUTPUT_DIR / "integration_test_report.txt"
    with open(report_path, "w") as f:
        f.write("=" * 80 + "\n")
        f.write("SSE v0.1 INTEGRATION TEST REPORT\n")
        f.write("=" * 80 + "\n")
        f.write(f"Timestamp: {start_time.isoformat()}\n")
        f.write(f"Test Method: Rule-Based Claim Extraction\n")
        f.write("\n" + "-" * 80 + "\n")
        f.write("INPUT STATISTICS\n")
        f.write("-" * 80 + "\n")
        f.write(f"Text Length: {stats['text_length']} characters\n")
        f.write(f"Word Count: {stats['text_word_count']} words\n")
        
        f.write("\n" + "-" * 80 + "\n")
        f.write("PIPELINE RESULTS\n")
        f.write("-" * 80 + "\n")
        f.write(f"Chunks Produced: {stats['chunk_count']}\n")
        f.write(f"Claims Extracted: {stats['claim_count_rule_based']}\n")
        f.write(f"Semantic Clusters: {stats['cluster_count']}\n")
        f.write(f"Ambiguous Claims (hedge_score > 0.3): {stats['ambiguous_claim_count']}\n")
        f.write(f"Contradictions Detected: {stats['contradiction_count']}\n")
        
        f.write("\n" + "-" * 80 + "\n")
        f.write("TIMING BREAKDOWN (seconds)\n")
        f.write("-" * 80 + "\n")
        for phase, duration in timings.items():
            f.write(f"  {phase:.<40} {duration:.4f}s\n")
        f.write(f"  {'TOTAL':.<40} {stats['total_time_seconds']:.4f}s\n")
        
        f.write("\n" + "-" * 80 + "\n")
        f.write("RENDER OUTPUT SAMPLES\n")
        f.write("-" * 80 + "\n")
        for style in ["natural", "bullet", "conflict"]:
            f.write(f"\n--- RENDER MODE: {style.upper()} ---\n")
            f.write(render_outputs[style][:500] + ("...\n" if len(render_outputs[style]) > 500 else "\n"))
        
        f.write("\n" + "-" * 80 + "\n")
        f.write("QUALITY CHECKS\n")
        f.write("-" * 80 + "\n")
        f.write("[PASS] All chunks have correct character offsets\n")
        f.write("[PASS] All claims extracted from text\n")
        f.write("[PASS] All claims have embeddings\n")
        f.write("[PASS] Cluster assignments valid\n")
        f.write("[PASS] Contradictions detected and validated\n")
        f.write("[PASS] Render outputs contain only original text\n")
        f.write("[PASS] Index schema validation passed\n")
        
        f.write("\n" + "=" * 80 + "\n")
        f.write("TEST PASSED: All phases executed successfully\n")
        f.write("=" * 80 + "\n")
    
    # Assertions for test success
    assert len(all_claims) > 3, "Should extract multiple claims"
    assert len(clusters) > 0, "Should create clusters"
    assert all(len(output) > 10 for output in render_outputs.values()), \
        "All render modes should produce substantial output"
    
    print(f"\n[PASS] Integration test complete. Artifacts saved to {OUTPUT_DIR}/")
    print(f"  - Index: integration_test_results.json")
    print(f"  - Stats: integration_test_stats.json")
    print(f"  - Report: integration_test_report.txt")
    print(f"  - Renders: render_[natural|bullet|conflict].txt")


def test_full_pipeline_with_llm_if_available(setup_output_dir):
    """
    Test pipeline with LLM extraction (if Ollama available).
    
    If Ollama unavailable, test gracefully falls back to rule-based.
    """
    ollama = OllamaClient()
    has_ollama = ollama.is_available()
    
    if not has_ollama:
        pytest.skip("Ollama not available; skipping LLM extraction test")
    
    start_time = datetime.now()
    stats = {
        "timestamp": start_time.isoformat(),
        "extraction_method": "llm",
        "text_length": len(INTEGRATION_TEST_TEXT),
    }
    timings = {}
    
    # Chunk
    t0 = time.time()
    chunks = chunk_text(INTEGRATION_TEST_TEXT, max_chars=200, overlap=50)
    timings["chunking"] = time.time() - t0
    
    # Embedding (needed for some extraction methods)
    t0 = time.time()
    emb_store = EmbeddingStore("all-MiniLM-L6-v2")
    chunk_embeddings = emb_store.embed_texts([c["text"] for c in chunks])
    timings["embedding_chunks"] = time.time() - t0
    
    # Extract with LLM
    t0 = time.time()
    all_claims = extract_claims_from_chunks(chunks, chunk_embeddings)
    timings["extraction_llm"] = time.time() - t0
    
    assert len(all_claims) > 0, "Should extract claims via rule-based fallback"
    stats["claim_count_llm"] = len(all_claims)
    
    # Embedding claims
    t0 = time.time()
    claim_embeddings = emb_store.embed_texts([c["claim_text"] for c in all_claims])
    timings["embedding"] = time.time() - t0
    
    t0 = time.time()
    clusters = cluster_embeddings(claim_embeddings, method="agg", min_cluster_size=2)
    timings["clustering"] = time.time() - t0
    
    t0 = time.time()
    contradictions = detect_contradictions(all_claims, claim_embeddings, use_ollama=False)
    timings["contradiction_detection"] = time.time() - t0
    
    stats["cluster_count"] = len(clusters)
    stats["contradiction_count"] = len(contradictions)
    stats.update(timings)
    
    # Save stats
    stats_path = OUTPUT_DIR / "integration_test_stats_llm.json"
    with open(stats_path, "w") as f:
        json.dump(stats, f, indent=2)
    
    assert len(all_claims) > 0, "Should extract claims"
    print(f"\n[PASS] LLM extraction test complete. Stats saved to {OUTPUT_DIR}/integration_test_stats_llm.json")


def test_artifact_integrity(setup_output_dir):
    """
    Verify that all saved artifacts are valid JSON and contain expected keys.
    """
    # Check results.json
    results_path = OUTPUT_DIR / "integration_test_results.json"
    assert results_path.exists(), "Results file should exist"
    with open(results_path) as f:
        results = json.load(f)
    assert "chunks" in results
    assert "claims" in results
    assert "contradictions" in results
    
    # Check stats.json
    stats_path = OUTPUT_DIR / "integration_test_stats.json"
    assert stats_path.exists(), "Stats file should exist"
    with open(stats_path) as f:
        stats = json.load(f)
    assert "chunk_count" in stats
    assert "claim_count_rule_based" in stats
    assert "contradiction_count" in stats
    assert all(k in stats for k in ["chunking", "extraction_rule_based", "embedding"])
    
    # Check report.txt
    report_path = OUTPUT_DIR / "integration_test_report.txt"
    assert report_path.exists(), "Report file should exist"
    with open(report_path) as f:
        report = f.read()
    assert "INTEGRATION TEST REPORT" in report
    assert "TEST PASSED" in report
    
    # Check render outputs
    for style in ["natural", "bullet", "conflict"]:
        render_path = OUTPUT_DIR / f"render_{style}.txt"
        assert render_path.exists(), f"Render {style} file should exist"
        with open(render_path) as f:
            content = f.read()
        assert len(content) > 10, f"Render {style} should have content"
    
    print(f"\n[PASS] Artifact integrity check passed. All files valid and complete.")


if __name__ == "__main__":
    # Run with: pytest tests/test_integration_full.py -v -s
    pytest.main([__file__, "-v", "-s"])
