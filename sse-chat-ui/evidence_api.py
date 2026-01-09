#!/usr/bin/env python3
"""
Python Flask API for SSE Evidence Search.

Loads pre-built index from output_index/ and exposes search endpoint.
Uses semantic similarity to find relevant claims and contradictions.
"""

from flask import Flask, request, jsonify
from pathlib import Path
import json
import numpy as np
import sys
import os

# Set UTF-8 encoding for output
os.environ['PYTHONIOENCODING'] = 'utf-8'

# Add sse module to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from sse.embeddings import EmbeddingStore
from sse.retrieval import query_index

app = Flask(__name__)

# Load index once at startup
INDEX_PATH = Path(__file__).parent.parent / "output_index"
index = None
embeddings = None
embed_store = None

def load_index():
    """Load pre-built index and embeddings from output_index/"""
    global index, embeddings, embed_store
    
    try:
        # Load index JSON
        index_file = INDEX_PATH / "index.json"
        if not index_file.exists():
            print(f"[ERROR] Index file not found: {index_file}")
            return False
        
        with open(index_file, 'r', encoding='utf-8') as f:
            index = json.load(f)
        print(f"[OK] Index loaded: {len(index.get('claims', []))} claims, {len(index.get('contradictions', []))} contradictions")
        
        # Load embeddings
        emb_file = INDEX_PATH / "embeddings.npy"
        if not emb_file.exists():
            print(f"[ERROR] Embeddings file not found: {emb_file}")
            return False
        
        embeddings = np.load(emb_file)
        print(f"[OK] Embeddings loaded: shape {embeddings.shape}")
        
        # Initialize embedding store for query encoding (lazy load on first use)
        # Don't load model at startup to avoid network access
        embed_store = None  # Will be initialized on first search
        print(f"[OK] EmbeddingStore will be lazily initialized on first search")
        
        return True
        
    except Exception as e:
        print(f"[ERROR] Failed to load index: {e}")
        import traceback
        traceback.print_exc()
        return False

@app.route('/api/health', methods=['GET'])
def health():
    """Health check"""
    return jsonify({
        'status': 'ok',
        'index_loaded': index is not None,
        'claims_count': len(index.get('claims', [])) if index else 0,
        'contradictions_count': len(index.get('contradictions', [])) if index else 0
    })

@app.route('/api/search', methods=['POST'])
def search():
    """
    Search endpoint returning claims and contradictions
    
    Request:
    {
        "query": "string",
        "k": 5,
        "highlight_contradictions": true
    }
    
    Response:
    {
        "valid": true,
        "packet": {
            "query": "...",
            "query_embedding_id": "...",
            "k": 5,
            "claims": [...],
            "contradictions": [...],
            "clusters": [...]
        },
        "query": "...",
        "search_k": 5
    }
    """
    try:
        print("\n[REQUEST] Search endpoint called")
        data = request.get_json()
        print(f"   Data: {data}")
        
        query = data.get('query', '').strip()
        k = data.get('k', 5)
        highlight_contradictions = data.get('highlight_contradictions', True)
        
        print(f"   Query: '{query}', k: {k}")
        
        if not query:
            return jsonify({'valid': False, 'error': 'Query required'}), 400
        
        if index is None or embeddings is None:
            return jsonify({
                'valid': False,
                'error': 'Search index not loaded'
            }), 503
        
        # Lazily initialize embedding store on first search
        global embed_store
        if embed_store is None:
            print(f"   [INIT] Initializing EmbeddingStore (first use)...")
            try:
                embed_store = EmbeddingStore("all-MiniLM-L6-v2")
                print(f"   [OK] EmbeddingStore initialized")
            except Exception as e:
                print(f"   [ERROR] Failed to initialize EmbeddingStore: {e}")
                return jsonify({
                    'valid': False,
                    'error': f'Failed to initialize embedding model: {str(e)}'
                }), 503
        
        # Encode query
        print(f"   [ENCODE] Encoding query...")
        query_embedding = embed_store.embed_texts([query])[0]
        print(f"   [OK] Query embedding shape: {query_embedding.shape}")
        
        # Query the index
        print(f"   [QUERY] Querying index with k={k}...")
        results = query_index(query_embedding, index, embeddings, k=k)
        print(f"   [OK] Got {len(results.get('query_results', []))} results")
        
        # Build evidence packet
        packet = {
            'query': query,
            'k': k,
            'query_results': results.get('query_results', []),
            'total_clusters': results.get('total_clusters', 0),
            'highlight_contradictions': highlight_contradictions,
        }
        
        print(f"   [OK] Search completed")
        
        # Return with metadata
        return jsonify({
            'valid': True,
            'packet': packet,
            'query': query,
            'search_k': k
        })
    
    except Exception as e:
        print(f"\n[ERROR] Search error: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({
            'valid': False,
            'error': f'Search failed: {str(e)}'
        }), 500

if __name__ == '__main__':
    if load_index():
        print("\n[START] Evidence API Server")
        print("   Running on http://127.0.0.1:5000")
        print("   POST /api/search - Search for evidence")
        print("   GET /api/health - Health check\n")
        app.run(host='127.0.0.1', port=5000, debug=False, use_reloader=False)
    else:
        print("\n[ERROR] Failed to load index. Cannot start server.")
        sys.exit(1)
