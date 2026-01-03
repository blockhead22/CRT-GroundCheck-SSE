# SSE-v0 (Semantic String Engine v0)

Local prototype for meaning-preserving semantic compression of text with explicit preservation of ambiguity and contradictions.

## Quick Start

### Installation

```bash
python -m venv .venv
# On Windows:
.venv\Scripts\activate
# On Linux/Mac:
source .venv/bin/activate

pip install -r requirements.txt
pip install -e .
```

### Commands

#### Compress a text file
```bash
sse compress --input notes.txt --out ./index_dir
```

Options:
- `--max-chars`: Maximum characters per chunk (default: 800)
- `--overlap`: Overlap size in characters (default: 200)
- `--embed-model`: Sentence transformer model (default: all-MiniLM-L6-v2)
- `--cluster-method`: hdbscan, agg, or kmeans (default: hdbscan)
- `--use-ollama`: Enable local Ollama LLM for NLI-based contradiction detection

#### Query the index
```bash
sse query --index ./index_dir/index.json --query "What are the main points?" --k 5
```

Returns top-k clusters with their claims, contradictions, and open questions.

#### Evaluate compression quality
```bash
sse eval --input notes.txt --index ./index_dir/index.json
```

Reports: compression ratio, semantic coverage, quote retention rate, contradiction count.

## Output Format

The compressed index is a single JSON file (`index.json`) containing:

```json
{
  "doc_id": "...",
  "timestamp": "...",
  "chunks": [
    {
      "chunk_id": "c0",
      "text": "...",
      "start_char": 0,
      "end_char": 123,
      "embedding_id": "e0"
    }
  ],
  "clusters": [
    {
      "cluster_id": "cl0",
      "chunk_ids": ["c0", "c1"],
      "centroid_embedding_id": "cent0"
    }
  ],
  "claims": [
    {
      "claim_id": "clm0",
      "claim_text": "...",
      "supporting_quotes": [
        {
          "quote_text": "...",
          "chunk_id": "c0",
          "start_char": 0,
          "end_char": 50
        }
      ],
      "ambiguity": {
        "hedge_score": 0.0,
        "contains_conflict_markers": false,
        "open_questions": []
      }
    }
  ],
  "contradictions": [
    {
      "pair": {
        "claim_id_a": "clm0",
        "claim_id_b": "clm1"
      },
      "label": "contradiction|entails|unrelated",
      "evidence_quotes": [...]
    }
  ]
}
```

## Architecture

### Pipeline

1. **Chunking**: Sentence-aware chunking with configurable overlap; preserves character offsets for citation.
2. **Embeddings**: Local sentence-transformers (all-MiniLM-L6-v2 default) or TF-IDF fallback; stored as numpy arrays.
3. **Clustering**: HDBSCAN (preferred) or Agglomerative/KMeans with cosine metric.
4. **Claim extraction**: Rule-based; extracts assertive sentences, deduplicates by cosine similarity, each claim has 1+ supporting quote with offsets.
5. **Ambiguity detection**: Hedge score (lexicon-based), open questions (sentences ending with ?).
6. **Contradiction detection**: Two-stage: cluster-limited comparisons; optional local LLM (Ollama) or negation heuristic fallback.
7. **Retrieval**: Query by embedding similarity; returns top-k clusters with filtered claims, contradictions, and open questions.
8. **Evaluation**: Compression ratio, semantic coverage, quote retention, contradiction count.

### Key Design Principles

- **Deterministic**: No randomness where possible; reproducible results.
- **Local-only**: No remote APIs; can run entirely offline.
- **No hallucination**: If uncertain, record as open_question, not a claim.
- **Explicit contradictions**: Record contradictions as first-class objects; never auto-resolve.
- **Traceable claims**: Every claim must have supporting quote(s) with character offsets.

## Optional: Local LLM (Ollama)

To enable NLI-based contradiction detection with a local LLM:

1. Install [Ollama](https://ollama.ai)
2. Pull a model (e.g., `ollama pull mistral`)
3. Start Ollama server (default: `http://localhost:11434`)
4. Use flag: `sse compress --input notes.txt --out ./index --use-ollama`

## Testing

```bash
pytest -v
```

All 11 tests pass, covering:
- Chunk offset integrity
- Chunk overlap behavior
- Claim extraction and deduplication
- Ambiguity detection
- Contradiction detection
- Clustering
- Schema validation

## No Remote APIs

By design, SSE-v0 does not depend on remote services. The optional Ollama integration is entirely local.
