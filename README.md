# SSE-v0 (Semantic String Engine v0)

Local prototype for meaning-preserving semantic compression of text with explicit preservation of ambiguity and contradictions.

## Quick Start

For the CRT (truthful personal AI) workflow (background jobs → proposals → approvals → apply), see:
- [CRT_HOW_TO_USE.md](CRT_HOW_TO_USE.md)

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

---

## CRT (Truthful Personal AI) — Current Status & Next Steps

**CRT** is a local-first, trust-weighted memory system that **doesn't lie**. Instead of hallucinating, it tracks contradictions explicitly and asks clarifying questions.

### ✅ What's Working Now (v0.85)

**Core Engine (Milestone M0-M2):**
- ✅ Trust-weighted memory with belief/speech separation
- ✅ Contradiction ledger (no silent overwrites)
- ✅ HTTP API (FastAPI) with `/api/chat`, `/api/contradictions`, `/api/jobs`
- ✅ React/Vite frontend (Chat, Dashboard, Docs, Jobs pages)
- ✅ Background jobs queue with SQLite persistence
- ✅ M2 contradiction resolution: 85%+ success rate in 100-turn tests
- ✅ Scope isolation: contradictions don't leak across unrelated topics
- ✅ Learned suggestion engine (metadata-only, never overwrites facts)
- ✅ Stress testing harness (200+ turn validation)

**What This Means:**
You can chat with CRT, it remembers what you tell it, flags contradictions instead of silently changing history, and asks you to resolve conflicts. Works locally, no cloud required.

### 🔧 Known Limitations & Polish Opportunities

**M2 Remaining Work (to reach 95%+):**
1. **Gate pass rate**: Currently 14-33% (target: 70%+)
   - Many legitimate queries flagged as "instructions" 
   - Needs gate logic review in `crt_rag.py`
2. **Contradiction classification polish**:
   - CONFLICT/REVISION/REFINEMENT/TEMPORAL types exist but need edge case tuning
3. **M2 edge cases**: 
   - Better handling of multi-slot contradictions
   - Improved clarification question templates

**Next Major Features (M3+):**
- **M3 - Evidence Packets**: Web research with citations (search → fetch → quote → cite)
- **M4 - Background Task Permissions**: Tier-based safety (read-only → notes → tools)
- **M5 - Learning Polish**: User-facing controls for suggestions, export/import

### 📚 Documentation

**Start Here:**
- `CRT_HOW_TO_USE.md` - Quick start guide
- `CRT_MASTER_FOCUS_ROADMAP.md` - Full roadmap + architecture
- `CRT_COMPANION_ROADMAP.md` - Milestone definitions (M0-M5)

**Technical Deep Dives:**
- `CRT_INTEGRATION.md` - Core math framework
- `CRT_QUICK_REFERENCE.md` - API reference
- `CRT_ARTIFACT_SCHEMAS.md` - Data schemas
- `CRT_BACKGROUND_LEARNING.md` - Subconscious worker design
- `BROWSER_BRIDGE_README.md` - Research mode setup

**Architecture Principles:**
- **No hallucination**: If uncertain, express uncertainty or ask
- **Explicit contradictions**: Never auto-resolve conflicts
- **Traceable claims**: Every fact grounded in memory text or citations

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

---

## Phase 6: Interface & Coherence Layer (ICL)

**Status:** Specification Complete (Implementation Pending)

Phase 6 is a **boundary-locking phase**. It defines how external systems can interact with SSE without corrupting it.

### What Phase 6 Delivers

**D1: Interface Contract** ([SSE_INTERFACE_CONTRACT.md](SSE_INTERFACE_CONTRACT.md))
- Formal specification of permitted operations (retrieval, search, filtering, navigation)
- Explicitly forbidden operations (synthesis, truth picking, ambiguity softening, suppression)
- Binding contract; violations raise `SSEBoundaryViolation`

**D2: Read-Only Interaction Layer** (implementation pending)
- Stateless navigator for natural language queries
- Preserves contradictions and ambiguity in all operations
- Enables conversation without decision-making

**D3: Coherence Tracking** ([SSE_COHERENCE_TRACKING.md](SSE_COHERENCE_TRACKING.md))
- Metadata about disagreement: persistence, source alignment, claim recurrence, ambiguity evolution
- Enables users to understand contradiction patterns without resolving them

**D4: Platform Integration Guide** ([SSE_PLATFORM_INTEGRATION.md](SSE_PLATFORM_INTEGRATION.md))
- How to integrate SSE into RAG systems, personal AIs, multi-agent systems, fact-checking pipelines
- Anti-patterns to avoid
- Examples of correct integration

**D5: Test Suite** (implementation pending)
- Verifies query parsing, contradiction preservation, boundary violations
- Ensures Interface Contract is enforced at code review time

### Why Phase 6 Matters

Most systems erode because they add features before locking integrity boundaries.

Phase 6 locks the boundaries **before** building on top. This ensures:
- Contradictions are never hidden
- Synthesis is never performed by SSE
- Ambiguity is never softened
- Provenance is always maintained

### Navigation

- **[PHASE_6_NAVIGATION.md](PHASE_6_NAVIGATION.md)** — Quick links and reading order
- **[PHASE_6_INFLECTION_POINT.md](PHASE_6_INFLECTION_POINT.md)** — Why this phase matters philosophically
- **[PHASE_6_PLAN.md](PHASE_6_PLAN.md)** — Complete Phase 6 strategy
- **[PHASE_6_SUMMARY.md](PHASE_6_SUMMARY.md)** — Deliverables checklist
