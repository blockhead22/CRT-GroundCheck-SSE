import argparse
import json
import os
from datetime import datetime
from .chunker import chunk_text
from .embeddings import EmbeddingStore
from .clustering import cluster_embeddings
from .extractor import extract_claims_from_chunks, extract_claims_with_llm
from .ambiguity import analyze_ambiguity_for_claims
from .contradictions import detect_contradictions
from .eval import evaluate_index
from .schema import validate_index_schema
from .ollama_utils import OllamaClient
from .render import render_index
from .interaction_layer import SSENavigator, SSEBoundaryViolation


def compress(args):
    try:
        with open(args.input, "r", encoding="utf-8") as f:
            text = f.read()
        if not text.strip():
            print(f"Error: input file '{args.input}' is empty.")
            return
        
        print(f"Chunking text ({len(text)} chars)...")
        chunks = chunk_text(text, max_chars=args.max_chars, overlap=args.overlap)
        print(f"✓ Created {len(chunks)} chunks")
        
        print(f"Embedding with model '{args.embed_model}'...")
        emb_store = EmbeddingStore(args.embed_model)
        emb_vectors = emb_store.embed_texts([c["text"] for c in chunks])
        emb_path = os.path.join(args.out, "embeddings.npy")
        os.makedirs(args.out, exist_ok=True)
        import numpy as np
        np.save(emb_path, emb_vectors.astype("float32"))
        print(f"✓ Saved embeddings to {emb_path}")
        
        print(f"Clustering with method '{args.cluster_method}'...")
        clusters = cluster_embeddings(emb_vectors, method=args.cluster_method, min_cluster_size=args.min_cluster_size)
        print(f"✓ Created {len(clusters)} clusters")
        
        # Initialize Ollama if requested
        ollama_client = None
        if args.use_ollama:
            print("Initializing Ollama...")
            ollama_client = OllamaClient()
            if ollama_client.is_available():
                print(f"✓ Ollama available (using model: {args.ollama_model})")
            else:
                print("⚠ Ollama not available; falling back to rule-based extraction")
                ollama_client = None
        
        print("Extracting claims...")
        claims = []
        claim_id_counter = 0
        
        for cidx, c in enumerate(chunks):
            if ollama_client:
                chunk_claims = extract_claims_with_llm(
                    c["text"],
                    c["chunk_id"],
                    c["start_char"],
                    ollama_client=ollama_client,
                    model=args.ollama_model
                )
            else:
                # Use rule-based extraction
                chunk_claims = extract_claims_from_chunks([c], emb_vectors[cidx:cidx+1])
            
            for claim in chunk_claims:
                if claim.get("claim_id") is None:
                    claim["claim_id"] = f"clm{claim_id_counter}"
                    claim_id_counter += 1
                claims.append(claim)
        
        print(f"✓ Extracted {len(claims)} claims")
        
        # attach ambiguity
        analyze_ambiguity_for_claims(claims)
        
        print("Detecting contradictions...")
        contradictions = detect_contradictions(claims, emb_vectors, use_ollama=args.use_ollama)
        print(f"✓ Found {len(contradictions)} contradictions")
        
        index = {
            "doc_id": os.path.basename(args.input),
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "chunks": chunks,
            "clusters": clusters,
            "claims": claims,
            "contradictions": contradictions,
        }
        validate_index_schema(index)
        index_path = os.path.join(args.out, "index.json")
        with open(index_path, "w", encoding="utf-8") as f:
            json.dump(index, f, ensure_ascii=False, indent=2)
        print(f"✓ Wrote index to {index_path}")
    except Exception as e:
        print(f"Error during compression: {e}")
        import traceback
        traceback.print_exc()


def query(args):
    try:
        import numpy as np
        if not os.path.exists(args.index):
            print(f"Error: index file '{args.index}' not found.")
            return
        idx_dir = os.path.dirname(args.index)
        idx = json.load(open(args.index, "r", encoding="utf-8"))
        emb_path = os.path.join(idx_dir, "embeddings.npy")
        if not os.path.exists(emb_path):
            print(f"Error: embeddings file '{emb_path}' not found.")
            return
        emb_vectors = np.load(emb_path)
        emb_store = EmbeddingStore(args.embed_model)
        qv = emb_store.embed_texts([args.query])[0]
        from .retrieval import query_index
        results = query_index(qv, idx, emb_vectors, k=args.k)
        print(json.dumps(results, ensure_ascii=False, indent=2))
    except Exception as e:
        print(f"Error during query: {e}")
        import traceback
        traceback.print_exc()


def eval_cmd(args):
    try:
        if not os.path.exists(args.input):
            print(f"Error: input file '{args.input}' not found.")
            return
        if not os.path.exists(args.index):
            print(f"Error: index file '{args.index}' not found.")
            return
        report = evaluate_index(args.input, args.index)
        print(json.dumps(report, ensure_ascii=False, indent=2))
    except Exception as e:
        print(f"Error during eval: {e}")
        import traceback
        traceback.print_exc()


def render_cmd(args):
    try:
        if not os.path.exists(args.index):
            print(f"Error: index file '{args.index}' not found.")
            return
        idx = json.load(open(args.index, "r", encoding="utf-8"))
        output = render_index(idx, style=args.style)
        print(output)
    except Exception as e:
        print(f"Error during render: {e}")
        import traceback
        traceback.print_exc()


def navigate(args):
    """Navigate SSE index: retrieve claims, contradictions, provenance, uncertainty."""
    try:
        if not os.path.exists(args.index):
            print(f"Error: index file '{args.index}' not found.")
            return
        
        nav = SSENavigator(args.index, embed_model=args.embed_model)
        
        # Show index info if requested
        if args.info:
            info = nav.info()
            print("=" * 60)
            print("INDEX INFORMATION")
            print("=" * 60)
            for key, value in info.items():
                print(f"{key}: {value}")
            print("=" * 60)
            return
        
        # Query: search for claims by topic/keyword
        if args.query:
            method = "semantic" if args.semantic else "keyword"
            results = nav.query(args.query, k=args.k, method=method)
            print(nav.format_search_results(results))
            return
        
        # Topic contradictions: find all contradictions about a topic
        if args.topic_contradictions:
            contradictions = nav.get_contradictions_for_topic(args.topic_contradictions)
            if not contradictions:
                print(f"No contradictions found for topic: {args.topic_contradictions}")
                return
            
            print(f"Found {len(contradictions)} contradictions about '{args.topic_contradictions}':\n")
            for i, contra in enumerate(contradictions, 1):
                print(nav.format_contradiction(contra))
                print("\n")
            return
        
        # Provenance: show exact source for a claim
        if args.provenance:
            claim = nav.get_claim_by_id(args.provenance)
            if not claim:
                print(f"Claim not found: {args.provenance}")
                return
            
            prov = nav.get_provenance(args.provenance)
            print("=" * 60)
            print("CLAIM PROVENANCE")
            print("=" * 60)
            print(f"Claim ID: {prov['claim_id']}")
            print(f"Claim Text: {prov['claim_text']}")
            print(f"\nSupporting Quotes ({len(prov['supporting_quotes'])}):")
            
            for i, quote in enumerate(prov['supporting_quotes'], 1):
                print(f"\n{i}. Quote:")
                print(f"   Text: \"{quote['quote_text']}\"")
                print(f"   Chunk ID: {quote['chunk_id']}")
                print(f"   Byte Range: [{quote['start_char']}:{quote['end_char']}]")
                print(f"   Length: {quote['char_count']} characters")
                print(f"   Reconstructed Match: {quote['valid']}")
            
            print("=" * 60)
            return
        
        # Uncertainty: show claims with high hedge scores
        if args.uncertain:
            uncertain = nav.get_uncertain_claims(min_hedge=args.min_hedge)
            if not uncertain:
                print(f"No claims with hedge score >= {args.min_hedge}")
                return
            
            print(f"Found {len(uncertain)} claims with uncertain language (hedge score >= {args.min_hedge}):\n")
            for i, claim in enumerate(uncertain, 1):
                hedge = claim.get("ambiguity", {}).get("hedge_score", 0.0)
                print(f"{i}. [{hedge:.2f}] {claim.get('claim_text')}")
            print()
            return
        
        # Cluster: show all claims in a cluster
        if args.cluster:
            cluster_info = nav.get_cluster(args.cluster)
            print("=" * 60)
            print(f"CLUSTER {args.cluster}")
            print("=" * 60)
            print(f"Number of claims: {cluster_info['num_claims']}")
            print("\nClaims:")
            
            for i, claim in enumerate(cluster_info['claims'], 1):
                print(f"\n{i}. {claim.get('claim_text')}")
                for quote in claim.get("supporting_quotes", []):
                    print(f"   Quote: \"{quote.get('quote_text')}\"")
            
            print("=" * 60)
            return
        
        # Show all contradictions
        if args.all_contradictions:
            contradictions = nav.get_contradictions()
            if not contradictions:
                print("No contradictions found.")
                return
            
            print(f"Found {len(contradictions)} total contradictions:\n")
            for i, contra in enumerate(contradictions, 1):
                print(nav.format_contradiction(contra))
                print("\n")
            return
        
        # Coherence: show disagreement metadata for a claim
        if args.coherence:
            coherence = nav.get_claim_coherence(args.coherence)
            if not coherence:
                print(f"Claim not found: {args.coherence}")
                return
            
            print("=" * 60)
            print("CLAIM COHERENCE METADATA")
            print("=" * 60)
            print(f"Claim ID: {coherence['claim_id']}")
            print(f"Claim Text: {coherence['claim_text']}")
            print(f"\nTotal Relationships: {coherence['total_relationships']}")
            print(f"  Contradictions: {coherence['contradictions']}")
            print(f"  Conflicts: {coherence['conflicts']}")
            print(f"  Qualifications: {coherence['qualifications']}")
            print(f"  Agreements: {coherence['agreements']}")
            print(f"  Ambiguous: {coherence['ambiguous_relationships']}")
            
            if coherence['total_relationships'] > 0:
                print(f"\nDisagreement Edges:")
                edges = nav.get_disagreement_edges(args.coherence)
                for i, edge in enumerate(edges, 1):
                    print(f"{i}. {edge['claim_id_a']} ←→ {edge['claim_id_b']}")
                    print(f"   Relationship: {edge['relationship']}")
                    print(f"   Confidence: {edge['confidence']:.2f}")
                    if edge['reasoning']:
                        print(f"   Reasoning: {edge['reasoning']}")
            
            print("=" * 60)
            return
        
        # Related claims: show claims related to a specific one
        if args.related_to:
            related = nav.get_related_claims(args.related_to)
            if not related:
                print(f"No related claims found for: {args.related_to}")
                return
            
            print("=" * 60)
            print(f"CLAIMS RELATED TO {args.related_to}")
            print("=" * 60)
            for i, rel in enumerate(related, 1):
                print(f"{i}. {rel['claim_id']}")
                print(f"   Text: {rel['claim_text']}")
                print(f"   Relationship: {rel['relationship']}")
            print("=" * 60)
            return
        
        # Disagreement clusters: show groups of claims that disagree
        if args.disagreement_clusters:
            clusters = nav.get_disagreement_clusters()
            if not clusters:
                print("No disagreement clusters found.")
                return
            
            print("=" * 60)
            print(f"DISAGREEMENT CLUSTERS ({len(clusters)})")
            print("=" * 60)
            for i, cluster in enumerate(clusters, 1):
                print(f"\nCluster {i}: {len(cluster)} claims")
                for claim_id in cluster:
                    claim = nav.get_claim_by_id(claim_id)
                    print(f"  • {claim_id}: {claim.get('claim_text', 'N/A')[:60]}...")
            print("=" * 60)
            return
        
        # Coherence report: show overall disagreement statistics
        if args.coherence_report:
            report = nav.get_coherence_report()
            print("=" * 60)
            print("COHERENCE REPORT")
            print("=" * 60)
            print(f"Total Claims: {report['total_claims']}")
            print(f"Total Disagreement Edges: {report['total_disagreement_edges']}")
            print(f"Contradiction Edges: {report['contradiction_edges']}")
            print(f"Conflict Edges: {report['conflict_edges']}")
            print(f"Qualification Edges: {report['qualification_edges']}")
            print(f"Ambiguous Edges: {report['ambiguous_edges']}")
            print(f"Disagreement Density: {report['disagreement_density']:.4f}")
            print(f"Isolated Claims (no disagreements): {report['num_isolated_claims']}")
            
            if report['highest_conflict_claims']:
                print(f"\nHighest Conflict Claims:")
                for i, item in enumerate(report['highest_conflict_claims'], 1):
                    print(f"  {i}. {item['claim_id']}: {item['relationships']} relationships")
            
            if report['disagreement_clusters']:
                print(f"\nDisagreement Clusters ({len(report['disagreement_clusters'])}):")
                for i, cluster in enumerate(report['disagreement_clusters'], 1):
                    print(f"  Cluster {i}: {len(cluster)} claims - {', '.join(cluster[:3])}{'...' if len(cluster) > 3 else ''}")
            
            print("=" * 60)
            return
        
        # If no operation specified, show help
        print("No operation specified. Use --query, --topic-contradictions, --provenance, --uncertain, --cluster, --coherence, --related-to, --disagreement-clusters, or --coherence-report")
        
    except SSEBoundaryViolation as e:
        print(f"❌ {e}")
    except Exception as e:
        print(f"Error during navigation: {e}")
        import traceback
        traceback.print_exc()


def main():
    parser = argparse.ArgumentParser(prog="sse", description="Semantic String Engine v0.1: local semantic compression for text.")
    sub = parser.add_subparsers(dest="cmd")
    
    p = sub.add_parser("compress", help="Compress a text file into an indexed JSON structure.")
    p.add_argument("--input", required=True, help="Path to input text file")
    p.add_argument("--out", required=True, help="Output directory for index and embeddings")
    p.add_argument("--max-chars", type=int, default=800, help="Max characters per chunk")
    p.add_argument("--overlap", type=int, default=200, help="Overlap size in characters")
    p.add_argument("--embed-model", default="all-MiniLM-L6-v2", help="Sentence transformer model name")
    p.add_argument("--cluster-method", choices=["hdbscan","agg","kmeans"], default="agg", help="Clustering method")
    p.add_argument("--min-cluster-size", type=int, default=2, help="Minimum cluster size")
    p.add_argument("--use-ollama", action="store_true", help="Use local Ollama for LLM-based extraction and NLI")
    p.add_argument("--ollama-model", default="mistral", help="Ollama model to use")

    q = sub.add_parser("query", help="Query the index by text embedding similarity.")
    q.add_argument("--index", required=True, help="Path to index JSON file")
    q.add_argument("--query", required=True, help="Query text")
    q.add_argument("--k", type=int, default=5, help="Number of top clusters to return")
    q.add_argument("--embed-model", default="all-MiniLM-L6-v2", help="Sentence transformer model name")

    e = sub.add_parser("eval", help="Evaluate the compression quality of an index.")
    e.add_argument("--input", required=True, help="Path to original text file")
    e.add_argument("--index", required=True, help="Path to index JSON file")

    r = sub.add_parser("render", help="Render an index as honest, grounded summary (never hallucinates).")
    r.add_argument("--index", required=True, help="Path to index JSON file")
    r.add_argument("--style", choices=["natural", "bullet", "conflict"], default="natural", help="Render style")

    n = sub.add_parser("navigate", help="Navigate SSE index: query, contradictions, provenance, uncertainty, coherence.")
    n.add_argument("--index", required=True, help="Path to index JSON file")
    n.add_argument("--embed-model", default="all-MiniLM-L6-v2", help="Sentence transformer model name")
    n.add_argument("--query", help="Search for claims about a topic/keyword")
    n.add_argument("--semantic", action="store_true", help="Use semantic search (requires embeddings)")
    n.add_argument("--k", type=int, default=5, help="Number of results to return")
    n.add_argument("--topic-contradictions", help="Find all contradictions about a topic")
    n.add_argument("--provenance", help="Show exact source for a claim (by claim_id)")
    n.add_argument("--uncertain", action="store_true", help="Show all claims with uncertain language")
    n.add_argument("--min-hedge", type=float, default=0.5, help="Minimum hedge score for --uncertain")
    n.add_argument("--cluster", help="Show all claims in a semantic cluster (by cluster_id)")
    n.add_argument("--all-contradictions", action="store_true", help="Show all contradictions in the index")
    n.add_argument("--info", action="store_true", help="Show index information (num claims, clusters, etc)")
    n.add_argument("--coherence", help="Show coherence metadata for a claim (by claim_id)")
    n.add_argument("--related-to", help="Show claims related to a specific claim (by claim_id)")
    n.add_argument("--disagreement-clusters", action="store_true", help="Show groups of claims that disagree")
    n.add_argument("--coherence-report", action="store_true", help="Show overall disagreement statistics")

    args = parser.parse_args()
    if args.cmd == "compress":
        compress(args)
    elif args.cmd == "query":
        query(args)
    elif args.cmd == "eval":
        eval_cmd(args)
    elif args.cmd == "render":
        render_cmd(args)
    elif args.cmd == "navigate":
        navigate(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
