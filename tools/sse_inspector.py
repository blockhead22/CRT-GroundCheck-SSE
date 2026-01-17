#!/usr/bin/env python3
"""
SSE CLI Inspector - Minimal tool to run SSE and inspect outputs.

Phase 4c diagnostic tool. Accelerates fixture development and debugging.

Commands:
  sse run <file>              - Run SSE pipeline, show counts + clusters
  sse show --cluster N        - Display cluster N with all claims
  sse show --contradiction N  - Display contradiction pair N with quotes
  sse search "keyword"        - Find claims containing keyword
  sse validate-offsets        - Verify all offsets reconstruct correctly
  sse export --json <file>    - Export full index to JSON
"""

import sys
import os
import json
import argparse
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from sse.chunker import chunk_text
from sse.embeddings import EmbeddingStore
from sse.extractor import extract_claims_from_chunks
from sse.clustering import cluster_embeddings
from sse.ambiguity import analyze_ambiguity_for_claims
from sse.contradictions import detect_contradictions


class SSEInspector:
    """Minimal SSE pipeline runner and inspector."""
    
    def __init__(self, text: str, embed_model: str = "all-MiniLM-L6-v2"):
        self.original_text = text
        self.embed_model = embed_model
        self.chunks = None
        self.chunk_embeddings = None
        self.claims = None
        self.claim_embeddings = None
        self.clusters = None
        self.contradictions = None
        
    def run_pipeline(self):
        """Execute full SSE pipeline."""
        print("SSE Pipeline Execution")
        print("=" * 60)
        
        # Step 1: Chunking
        print(f"Input: {len(self.original_text)} chars")
        self.chunks = chunk_text(self.original_text, max_chars=500, overlap=50)
        print(f"OK Chunks: {len(self.chunks)}")
        
        # Step 2: Embed chunks
        emb_store = EmbeddingStore(self.embed_model)
        self.chunk_embeddings = emb_store.embed_texts([c["text"] for c in self.chunks])
        print(f"OK Chunk embeddings: {self.chunk_embeddings.shape}")
        
        # Step 3: Extract claims
        self.claims = extract_claims_from_chunks(self.chunks, self.chunk_embeddings)
        print(f"OK Claims extracted: {len(self.claims)}")
        
        # Step 4: Embed claims
        self.claim_embeddings = emb_store.embed_texts([c["claim_text"] for c in self.claims])
        print(f"OK Claim embeddings: {self.claim_embeddings.shape}")
        
        # Step 5: Cluster claims
        self.clusters = cluster_embeddings(self.claim_embeddings, method="hdbscan", min_cluster_size=2)
        print(f"OK Clusters: {len(self.clusters)}")
        
        # Step 6: Analyze ambiguity
        self.claims = analyze_ambiguity_for_claims(self.claims)
        print(f"OK Ambiguity analyzed")
        
        # Step 7: Detect contradictions
        self.contradictions = detect_contradictions(self.claims, self.claim_embeddings, use_ollama=False)
        print(f"OK Contradictions detected: {len(self.contradictions)}")
        
        print("=" * 60)
        
    def show_summary(self):
        """Display high-level summary."""
        print("\nSUMMARY")
        print("-" * 60)
        print(f"Chunks:         {len(self.chunks)}")
        print(f"Claims:         {len(self.claims)}")
        print(f"Clusters:       {len(self.clusters)}")
        print(f"Contradictions: {len(self.contradictions)}")
        print()
        
    def show_clusters(self):
        """Display all clusters with claim counts."""
        print("\nCLUSTERS")
        print("-" * 60)
        for cluster in self.clusters:
            # Clusters map to chunk indices, convert to claim IDs
            chunk_ids = cluster.get("chunk_ids", [])
            # Extract numeric indices from chunk_ids like "c0", "c1"
            indices = [int(cid[1:]) for cid in chunk_ids if cid.startswith("c")]
            # Map to claims (claims also map by index)
            relevant_claims = [c for i, c in enumerate(self.claims) if i in indices]
            
            print(f"Cluster {cluster['cluster_id']}: {len(relevant_claims)} claims (from {len(chunk_ids)} chunks)")
            for claim in relevant_claims[:3]:  # Show first 3
                text = claim["claim_text"]
                preview = text[:60] + "..." if len(text) > 60 else text
                print(f"  - {claim['claim_id']}: {preview}")
            if len(relevant_claims) > 3:
                print(f"  ... and {len(relevant_claims) - 3} more")
            print()
            
    def show_cluster(self, cluster_id: str):
        """Display specific cluster with all claims and quotes."""
        cluster = next((c for c in self.clusters if c["cluster_id"] == cluster_id), None)
        if not cluster:
            print(f"Cluster {cluster_id} not found")
            return
            
        print(f"\nCLUSTER {cluster_id}")
        print("=" * 60)
        
        # Convert chunk IDs to claim indices
        chunk_ids = cluster.get("chunk_ids", [])
        indices = [int(cid[1:]) for cid in chunk_ids if cid.startswith("c")]
        relevant_claims = [c for i, c in enumerate(self.claims) if i in indices]
        
        print(f"Claims: {len(relevant_claims)}")
        print()
        
        for claim in relevant_claims:
            print(f"[{claim['claim_id']}] {claim['claim_text']}")
            for quote in claim["supporting_quotes"]:
                start, end = quote["start_char"], quote["end_char"]
                print(f"  Quote: \"{quote['quote_text']}\"")
                print(f"  Offset: [{start}:{end}]")
            print()
            
    def show_contradiction(self, index: int):
        """Display specific contradiction with full quotes."""
        if index >= len(self.contradictions):
            print(f"Contradiction {index} not found (max: {len(self.contradictions) - 1})")
            return
            
        cont = self.contradictions[index]
        claim_a_id = cont["pair"]["claim_id_a"]
        claim_b_id = cont["pair"]["claim_id_b"]
        
        claim_a = next(c for c in self.claims if c["claim_id"] == claim_a_id)
        claim_b = next(c for c in self.claims if c["claim_id"] == claim_b_id)
        
        print(f"\nCONTRADICTION {index}")
        print("=" * 60)
        print(f"Label: {cont.get('label', 'unknown')}")
        print()
        print(f"[{claim_a_id}] {claim_a['claim_text']}")
        for q in claim_a["supporting_quotes"]:
            print(f"  → \"{q['quote_text']}\" [{q['start_char']}:{q['end_char']}]")
        print()
        print(f"[{claim_b_id}] {claim_b['claim_text']}")
        for q in claim_b["supporting_quotes"]:
            print(f"  → \"{q['quote_text']}\" [{q['start_char']}:{q['end_char']}]")
        print()
        
    def search_claims(self, keyword: str):
        """Find claims containing keyword (case-insensitive)."""
        keyword_lower = keyword.lower()
        matches = [c for c in self.claims if keyword_lower in c["claim_text"].lower()]
        
        print(f"\nSEARCH: \"{keyword}\"")
        print("=" * 60)
        print(f"Found {len(matches)} claims")
        print()
        
        for claim in matches:
            print(f"[{claim['claim_id']}] {claim['claim_text']}")
            for quote in claim["supporting_quotes"]:
                start, end = quote["start_char"], quote["end_char"]
                print(f"  Offset: [{start}:{end}]")
            print()
            
    def validate_offsets(self):
        """Verify all offsets reconstruct correctly."""
        print("\nOFFSET VALIDATION")
        print("=" * 60)
        
        errors = 0
        total = 0
        
        for claim in self.claims:
            for quote in claim["supporting_quotes"]:
                total += 1
                start = quote["start_char"]
                end = quote["end_char"]
                quote_text = quote["quote_text"]
                
                reconstructed = self.original_text[start:end]
                
                if reconstructed != quote_text:
                    errors += 1
                    print(f"FAIL MISMATCH [{claim['claim_id']}]")
                    print(f"   Expected: \"{quote_text}\"")
                    print(f"   Got:      \"{reconstructed}\"")
                    print(f"   Offset:   [{start}:{end}]")
                    # Show context
                    context_start = max(0, start - 50)
                    context_end = min(len(self.original_text), end + 50)
                    context = self.original_text[context_start:context_end]
                    print(f"   Context:  ...{context}...")
                    print()
                    
        if errors == 0:
            print(f"OK All {total} offsets reconstruct correctly")
        else:
            print(f"FAIL {errors}/{total} offsets failed validation")
            
        return errors == 0
        
    def export_json(self, output_path: str):
        """Export full index to JSON."""
        index = {
            "doc_id": "inspector_output",
            "timestamp": str(Path(output_path).stat().st_mtime if Path(output_path).exists() else 0),
            "text_length": len(self.original_text),
            "chunks": self.chunks,
            "claims": self.claims,
            "clusters": self.clusters,
            "contradictions": self.contradictions,
            "metadata": {
                "embedding_model": self.embed_model,
                "detector": "heuristic",
                "ollama_available": False
            }
        }
        
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(index, f, indent=2, ensure_ascii=False)
            
        print(f"OK Exported to {output_path}")
        print(f"  Chunks: {len(self.chunks)}")
        print(f"  Claims: {len(self.claims)}")
        print(f"  Contradictions: {len(self.contradictions)}")


def main():
    parser = argparse.ArgumentParser(
        description="SSE CLI Inspector - Examine SSE outputs",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    subparsers = parser.add_subparsers(dest="command", help="Command to run")
    
    # sse run
    run_parser = subparsers.add_parser("run", help="Run SSE pipeline on file")
    run_parser.add_argument("file", help="Input text file")
    run_parser.add_argument("--embed-model", default="all-MiniLM-L6-v2", help="Embedding model")
    
    # sse show
    show_parser = subparsers.add_parser("show", help="Show specific cluster or contradiction")
    show_parser.add_argument("--cluster", help="Cluster ID to display")
    show_parser.add_argument("--contradiction", type=int, help="Contradiction index to display")
    show_parser.add_argument("--cache", default=".sse_cache.json", help="Cache file from previous run")
    
    # sse search
    search_parser = subparsers.add_parser("search", help="Search for claims by keyword")
    search_parser.add_argument("keyword", help="Keyword to search for")
    search_parser.add_argument("--cache", default=".sse_cache.json", help="Cache file from previous run")
    
    # sse validate-offsets
    validate_parser = subparsers.add_parser("validate-offsets", help="Verify offset reconstruction")
    validate_parser.add_argument("--cache", default=".sse_cache.json", help="Cache file from previous run")
    
    # sse export
    export_parser = subparsers.add_parser("export", help="Export to JSON")
    export_parser.add_argument("--json", required=True, help="Output JSON file")
    export_parser.add_argument("--cache", default=".sse_cache.json", help="Cache file from previous run")
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return
        
    # Handle 'run' command
    if args.command == "run":
        if not os.path.exists(args.file):
            print(f"Error: File not found: {args.file}")
            return
            
        with open(args.file, "r", encoding="utf-8") as f:
            text = f.read()
            
        inspector = SSEInspector(text, embed_model=args.embed_model)
        inspector.run_pipeline()
        inspector.show_summary()
        inspector.show_clusters()
        
        # Cache results for subsequent commands
        cache_data = {
            "text": text,
            "claims": inspector.claims,
            "clusters": inspector.clusters,
            "contradictions": inspector.contradictions,
            "embed_model": args.embed_model
        }
        with open(".sse_cache.json", "w", encoding="utf-8") as f:
            json.dump(cache_data, f, ensure_ascii=False)
        print(f"\nOK Cached results to .sse_cache.json")
        
    # Handle commands that use cached data
    else:
        if not os.path.exists(args.cache):
            print(f"Error: No cached data found. Run 'sse run <file>' first.")
            return
            
        with open(args.cache, "r", encoding="utf-8") as f:
            cache_data = json.load(f)
            
        inspector = SSEInspector(cache_data["text"], embed_model=cache_data["embed_model"])
        inspector.claims = cache_data["claims"]
        inspector.clusters = cache_data["clusters"]
        inspector.contradictions = cache_data["contradictions"]
        
        if args.command == "show":
            if args.cluster:
                inspector.show_cluster(args.cluster)
            elif args.contradiction is not None:
                inspector.show_contradiction(args.contradiction)
            else:
                print("Error: Specify --cluster or --contradiction")
                
        elif args.command == "search":
            inspector.search_claims(args.keyword)
            
        elif args.command == "validate-offsets":
            inspector.validate_offsets()
            
        elif args.command == "export":
            inspector.export_json(args.json)


if __name__ == "__main__":
    main()
