"""
CANONICAL REFERENCE RUN

This script generates the canonical frozen reference output for SSE.

This output is the ground truth for what SSE should produce.
Future runs are compared against this canonical run to detect philosophical drift.

DO NOT REGENERATE AUTOMATICALLY.
If behavior must change, update this canonical reference AND document why in the README.
"""

import json
from datetime import datetime
from pathlib import Path

from sse.chunker import chunk_text
from sse.embeddings import EmbeddingStore
from sse.extractor import extract_claims_from_chunks
from sse.contradictions import detect_contradictions, clear_nli_cache
from sse.ambiguity import analyze_ambiguity_for_claims
from sse.clustering import cluster_embeddings


# This is the canonical test input
# Deliberately designed to include contradictions, hedges, and ambiguity
CANONICAL_INPUT = """
The Earth is round. Scientists have definitively proven that the Earth is a sphere.
Our planet orbits the Sun in an elliptical path.

However, some flat Earth believers claim the Earth is flat. They argue that gravity is a hoax.
The flat Earth theory contradicts all modern evidence.

Exercise is beneficial for health. Regular physical activity improves cardiovascular function.
Studies show that active people live longer. Exercise prevents many diseases.

But some extremists insist that exercise is harmful and causes injury.
On the other hand, sedentary behavior is healthier than exercise.
Sitting all day is better for your muscles than physical activity.

Climate change is real and caused by human activity. Global temperatures are rising due to
greenhouse gas emissions. Scientists agree on this.

Conversely, climate skeptics claim climate change is a hoax.
The Earth's climate is stable and not affected by humans.

Water boils at 100 degrees Celsius at sea level. This is a fundamental fact taught in every
science class.

Yet some pseudoscience advocates insist water boils at 50 degrees Celsius.

Vaccines are safe and effective. Millions of people have received vaccines without severe
side effects. Vaccination prevents diseases.

In contrast, anti-vaccine activists claim vaccines cause autism and severe injuries.
They are dangerous and should be avoided. Vaccination makes people sick.
"""

def main():
    """Generate canonical reference output."""
    output_dir = Path(__file__).parent
    
    print("=" * 80)
    print("CANONICAL SSE REFERENCE RUN")
    print("=" * 80)
    print(f"Timestamp: {datetime.now().isoformat()}")
    print(f"Output directory: {output_dir}")
    print()
    
    # Step 1: Chunking
    print("Step 1: Chunking")
    chunks = chunk_text(CANONICAL_INPUT, max_chars=300, overlap=50)
    print(f"  Created {len(chunks)} chunks")
    
    # Step 2: Embedding (chunks)
    print("Step 2: Embedding chunks")
    emb_store = EmbeddingStore("all-MiniLM-L6-v2")
    chunk_embeddings = emb_store.embed_texts([c["text"] for c in chunks])
    print(f"  Embedded {len(chunks)} chunks to 384-dim vectors")
    
    # Step 3: Claim Extraction
    print("Step 3: Extracting claims")
    claims = extract_claims_from_chunks(chunks, chunk_embeddings)
    print(f"  Extracted {len(claims)} claims")
    for i, claim in enumerate(claims, 1):
        print(f"    {i}. {claim['claim_text'][:60]}...")
    
    # Step 4: Embedding (claims)
    print("Step 4: Embedding claims")
    claim_embeddings = emb_store.embed_texts([c["claim_text"] for c in claims])
    print(f"  Embedded {len(claims)} claims to 384-dim vectors")
    
    # Step 5: Clustering
    print("Step 5: Clustering claims")
    clusters = cluster_embeddings(claim_embeddings, method="agg", min_cluster_size=2)
    print(f"  Created {len(clusters)} clusters")
    
    # Step 6: Ambiguity Analysis
    print("Step 6: Analyzing ambiguity")
    for claim in claims:
        claim["ambiguity"] = analyze_ambiguity_for_claims([claim])[0].get("ambiguity", {})
    print(f"  Analyzed ambiguity for {len(claims)} claims")
    
    # Step 7: Contradiction Detection
    print("Step 7: Detecting contradictions")
    clear_nli_cache()
    contradictions = detect_contradictions(claims, claim_embeddings, use_ollama=False)
    print(f"  Detected {len(contradictions)} contradictions")
    for i, cont in enumerate(contradictions, 1):
        print(f"    {i}. {cont['pair']['claim_id_a']} vs {cont['pair']['claim_id_b']}")
    
    # Save outputs
    print()
    print("Saving canonical reference artifacts...")
    
    # Save input
    with open(output_dir / "input.txt", "w") as f:
        f.write(CANONICAL_INPUT)
    print(f"  ✓ input.txt ({len(CANONICAL_INPUT)} chars)")
    
    # Save chunks
    with open(output_dir / "chunks.json", "w") as f:
        json.dump(chunks, f, indent=2)
    print(f"  ✓ chunks.json ({len(chunks)} chunks)")
    
    # Save claims
    # Convert embeddings to lists for JSON serialization
    claims_json = []
    for claim in claims:
        c = dict(claim)
        claims_json.append(c)
    
    with open(output_dir / "claims.json", "w") as f:
        json.dump(claims_json, f, indent=2)
    print(f"  ✓ claims.json ({len(claims)} claims)")
    
    # Save contradictions
    with open(output_dir / "contradictions.json", "w") as f:
        json.dump(contradictions, f, indent=2)
    print(f"  ✓ contradictions.json ({len(contradictions)} contradictions)")
    
    # Save clusters
    with open(output_dir / "clusters.json", "w") as f:
        json.dump(clusters, f, indent=2)
    print(f"  ✓ clusters.json ({len(clusters)} clusters)")
    
    # Save metadata
    metadata = {
        "timestamp": datetime.now().isoformat(),
        "canonical_version": "1.0",
        "input_length_chars": len(CANONICAL_INPUT),
        "input_word_count": len(CANONICAL_INPUT.split()),
        "chunks_count": len(chunks),
        "claims_count": len(claims),
        "contradictions_count": len(contradictions),
        "clusters_count": len(clusters),
        "embedding_model": "all-MiniLM-L6-v2",
        "embedding_dimensions": 384,
        "contradiction_detector": "heuristic",
        "ollama_available": False,
    }
    
    with open(output_dir / "metadata.json", "w") as f:
        json.dump(metadata, f, indent=2)
    print(f"  ✓ metadata.json")
    
    print()
    print("=" * 80)
    print("CANONICAL RUN COMPLETE")
    print("=" * 80)
    print()
    print("SUMMARY:")
    print(f"  Input: {metadata['input_length_chars']} characters, {metadata['input_word_count']} words")
    print(f"  Chunks: {metadata['chunks_count']}")
    print(f"  Claims: {metadata['claims_count']}")
    print(f"  Contradictions: {metadata['contradictions_count']}")
    print(f"  Clusters: {metadata['clusters_count']}")
    print()
    print("Files saved to: canonical_demo/")
    print("Reference these artifacts when validating SSE behavior.")


if __name__ == "__main__":
    main()
