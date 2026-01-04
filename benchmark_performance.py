"""
Performance Baseline Benchmark for SSE

This script measures execution time for each pipeline stage.
Does NOT attempt to optimize - just establishes baseline for future comparison.

Measures:
- Chunking time
- Embedding time (chunks and claims separately)
- Claim extraction time
- Deduplication time
- Contradiction detection time
- Clustering time
- Ambiguity analysis time

Output: JSON file with timing data for regression tracking.
"""

import time
import json
from pathlib import Path
from sse.chunker import chunk_text
from sse.embeddings import EmbeddingStore
from sse.extractor import extract_claims_from_chunks
from sse.contradictions import detect_contradictions, clear_nli_cache
from sse.clustering import cluster_embeddings
from sse.ambiguity import analyze_ambiguity_for_claims


def benchmark_pipeline(text_file: str, use_ollama: bool = False) -> dict:
    """Run full pipeline and measure each stage."""
    
    # Read input
    with open(text_file, 'r', encoding='utf-8') as f:
        text = f.read()
    
    results = {
        "input_file": text_file,
        "input_size_chars": len(text),
        "use_ollama": use_ollama,
        "timings": {}
    }
    
    # Stage 1: Chunking
    start = time.perf_counter()
    chunks = chunk_text(text, max_chars=500, overlap=100)
    results["timings"]["chunking_sec"] = time.perf_counter() - start
    results["chunk_count"] = len(chunks)
    
    # Stage 2: Chunk embeddings
    emb_store = EmbeddingStore("all-MiniLM-L6-v2")
    start = time.perf_counter()
    chunk_embeddings = emb_store.embed_texts([c["text"] for c in chunks])
    results["timings"]["chunk_embedding_sec"] = time.perf_counter() - start
    
    # Stage 3: Claim extraction
    start = time.perf_counter()
    claims = extract_claims_from_chunks(chunks, chunk_embeddings)
    results["timings"]["claim_extraction_sec"] = time.perf_counter() - start
    results["claim_count"] = len(claims)
    
    # Stage 4: Claim embeddings
    start = time.perf_counter()
    claim_embeddings = emb_store.embed_texts([c["claim_text"] for c in claims])
    results["timings"]["claim_embedding_sec"] = time.perf_counter() - start
    
    # Stage 5: Contradiction detection
    clear_nli_cache()
    start = time.perf_counter()
    contradictions = detect_contradictions(claims, claim_embeddings, use_ollama=use_ollama)
    results["timings"]["contradiction_detection_sec"] = time.perf_counter() - start
    results["contradiction_count"] = len(contradictions)
    
    # Stage 6: Clustering
    start = time.perf_counter()
    clusters = cluster_embeddings(claim_embeddings, method="hdbscan", min_cluster_size=2)
    results["timings"]["clustering_sec"] = time.perf_counter() - start
    results["cluster_count"] = len(clusters)
    
    # Stage 7: Ambiguity analysis
    start = time.perf_counter()
    claims = analyze_ambiguity_for_claims(claims)
    results["timings"]["ambiguity_analysis_sec"] = time.perf_counter() - start
    
    # Total pipeline time
    results["timings"]["total_sec"] = sum(
        v for k, v in results["timings"].items() if k != "total_sec"
    )
    
    return results


def run_benchmarks(output_file: str = "benchmark_baseline.json"):
    """Run benchmarks on canonical demo and all fixtures."""
    
    print("SSE Performance Baseline Benchmark")
    print("=" * 60)
    
    test_files = [
        "canonical_demo/input.txt",
        "fixtures/fixture1_license_must_may.txt",
        "fixtures/fixture2_medical_exceptions.txt",
        "fixtures/fixture3_numeric_contradictions.txt",
        "fixtures/fixture4_definitional_conflicts.txt",
        "fixtures/fixture5_scope_conflicts.txt"
    ]
    
    all_results = []
    
    for test_file in test_files:
        if not Path(test_file).exists():
            print(f"SKIP: {test_file} (not found)")
            continue
        
        print(f"\nBenchmarking: {test_file}")
        print("-" * 60)
        
        results = benchmark_pipeline(test_file, use_ollama=False)
        all_results.append(results)
        
        # Display results
        print(f"Input: {results['input_size_chars']} chars")
        print(f"Chunks: {results['chunk_count']}")
        print(f"Claims: {results['claim_count']}")
        print(f"Contradictions: {results['contradiction_count']}")
        print(f"Clusters: {results['cluster_count']}")
        print(f"\nTimings:")
        for stage, duration in results['timings'].items():
            print(f"  {stage:30s}: {duration:8.4f}s")
    
    # Save to JSON
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(all_results, f, indent=2)
    
    print("\n" + "=" * 60)
    print(f"Baseline saved to {output_file}")
    print("\nNOTE: These are baseline measurements, not optimization targets.")
    print("Use for regression tracking when refactoring pipeline stages.")


if __name__ == "__main__":
    run_benchmarks()
