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

    args = parser.parse_args()
    if args.cmd == "compress":
        compress(args)
    elif args.cmd == "query":
        query(args)
    elif args.cmd == "eval":
        eval_cmd(args)
    elif args.cmd == "render":
        render_cmd(args)
    else:
        parser.print_help()

if __name__ == "__main__":
    main()
