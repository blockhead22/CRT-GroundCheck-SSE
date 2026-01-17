# The Semantic String Engine (SSE) v0

## Overview

The **Semantic String Engine** is a semantic indexing and contradiction exposure system. It processes unstructured text into a structured, auditable index that extracts explicit claims, detects contradictions, and preserves semantic relationships—without summarizing, interpreting, or deciding what is true.

SSE is not a summarization engine, reasoning system, or QA tool. It is a **structural analyzer** that:
- Extracts claims as exact substrings from source text with byte-level provenance
- Clusters semantically related claims without merging contradictory ones
- Detects contradictions explicitly and preserves both sides
- Exposes ambiguity markers (hedging, conflict language, open questions)

The engine is built on non-negotiable architectural invariants that prioritize auditability, contradiction preservation, and semantic fidelity over narrative coherence.

SSE is designed for domains where contradictions are information (not noise), auditability is mandatory, and competing claims must be preserved intact—legal documents, medical records, policy analysis, and multi-source research synthesis.

---

## Core Philosophy: The Four Invariants

SSE is built on four immutable architectural principles that govern all behavior:

### I. The Quoting Invariant
**Every claim must be grounded in verbatim source text.**

- No paraphrasing or rewording claims
- Every claim includes an exact substring from the original text
- Byte-level start/end offsets enable reconstruction and verification
- Readers can always verify claims by checking the source

**Example:**
```
Source: "The Earth is round and orbits the Sun."
Extracted claim: "The Earth is round."
Quote: "The Earth is round."
Offsets: [0:18]
```

### II. The Contradiction Preservation Invariant
**All contradictions in the source must be extracted and preserved.**

- Both sides of contradictory claims must be extracted
- Contradictions are detected but never auto-resolved
- No claim is suppressed to achieve narrative coherence
- Users see conflicting viewpoints and form their own conclusions

**Example:**
```
Source: "Exercise is healthy. Some people say exercise damages joints."
Claims extracted: 
  1. "Exercise is healthy."
  2. "Exercise damages joints."
Contradictions detected: [1 ↔ 2]
```

### III. The Anti-Deduplication Invariant
**Opposite or conflicting claims are never merged.**

- Deduplication only removes true near-duplicates (typos, exact repeats)
- Semantically opposite claims are always kept separate
- "A is beneficial" and "A is harmful" remain distinct
- All extracted claims survive to final output

### IV. The Non-Fabrication Invariant
**SSE never creates, infers, or hallucinates information.**

- Every output element traces back to exact source spans
- Claims are pattern-matched and extracted, never inferred
- Uncertainty is marked as "unknown" rather than guessed
- The system is transparent about its limitations

---

## How It Works: Core Pipeline (Phases 1–5)

SSE has a **core 5-phase pipeline** that is deterministic and always-on. This is what SSE guarantees.

**Phases 6–10 are optional modules** that enhance or expose the core index. They do not affect the core extraction or contradiction detection.

---

## Core Phases: Structural Analysis

### Phase 1: Chunking
**Input:** Unstructured text  
**Output:** Overlapping chunks with byte-level offsets

The text is divided into overlapping segments (default: 800 characters per chunk with 200-character overlap). Overlap prevents semantic boundaries from being cut mid-sentence. Every chunk retains byte-level offsets to map back to the source.

```python
chunks = chunk_text(
    text, 
    max_chars=800,      # characters per chunk
    overlap=200         # overlap in characters
)
```

**Guarantee:** All chunk offsets are accurate and enable character-level reconstruction.

### Phase 2: Chunk Embedding
**Input:** Text chunks  
**Output:** Dense vectors representing semantic content

Each chunk is embedded using a sentence transformer model (default: `all-MiniLM-L6-v2`). These vectors enable semantic clustering and similarity comparisons without any modification to the original text.

```python
embeddings = EmbeddingStore('all-MiniLM-L6-v2')
vectors = embeddings.embed_texts([chunk['text'] for chunk in chunks])
```

**Guarantee:** Embeddings are used only for clustering and retrieval, never to modify or rewrite claims.

### Phase 3: Claim Extraction
**Input:** Chunks  
**Output:** Explicit claims with verbatim supporting quotes

Claims are extracted using rule-based pattern matching:
- Identifies declarative sentences and statement-like units
- Preserves exact character boundaries
- Extracts supporting quotes as exact substrings from source
- No paraphrasing or restatement

Every extracted claim includes:
- The claim text (extracted directly from source)
- Supporting quote(s) with byte offsets
- Proof of reconstruction: `source[start_char:end_char] == quote_text`

```json
{
  "claim_id": "clm0",
  "claim_text": "The process requires careful attention.",
  "supporting_quotes": [
    {
      "quote_text": "requires careful attention",
      "chunk_id": "c2",
      "start_char": 142,
      "end_char": 167
    }
  ]
}
```

**Guarantee:** Every claim is quoted verbatim. Claims never exist without source backing.

**Optional enhancement:** If Ollama is available (`--use-ollama`), LLM-based extraction can identify additional claims or implicit statements. This is experimental and may infer claims not explicitly stated. Use only if inference is acceptable for your domain.

### Phase 4: Claim Embedding
**Input:** Extracted claims  
**Output:** Dense vectors for claims

Claims are embedded separately to capture their semantic meaning independent of surrounding context. This enables claim-level clustering and contradiction detection.

**Guarantee:** Embeddings do not modify claims; they only represent them numerically.

### Phase 5: Clustering
**Input:** Claim embeddings  
**Output:** Semantic clusters

Clustering groups semantically related claims without merging them. Supported methods:
- **HDBSCAN** (default): Density-based, adapts to cluster size, robust to outliers
- **Agglomerative**: Hierarchical clustering
- **K-means**: Fast, requires pre-specified cluster count

```python
clusters = cluster_embeddings(
    vectors,
    method='hdbscan',
    min_cluster_size=2
)
```

**Guarantee:** Clustering is structural only. No claims are merged, deduplicated, or deleted. All extracted claims appear in the index.

---

## Optional Modules (Phases 6–10)

The following modules enhance the index with additional analysis or provide alternative views. They are **not required** for SSE to function and do not affect the core extraction.

### Phase 6 (Optional): Ambiguity Detection
**Input:** Claims  
**Output:** Ambiguity markers

Analyzes each claim for:
- **Hedge score**: Presence of uncertainty language ("may," "possibly," "might")
- **Conflict markers**: Phrases indicating disagreement ("some say," "debate," "contend")
- **Open questions**: Sentences phrased as unknowns or queries

```json
{
  "claim_id": "clm5",
  "ambiguity": {
    "hedge_score": 0.6,
    "contains_conflict_markers": false,
    "open_questions": []
  }
}
```

**Status:** Implemented, deterministic. Does not modify claims.

### Phase 7 (Optional): Contradiction Detection
**Input:** All claims  
**Output:** Pairs of contradictory claims

Detects contradictions using:
- **Semantic analysis**: Do claim embeddings represent opposite meanings?
- **Negation patterns**: Does one claim explicitly negate another?
- **NLI (experimental)**: With `--use-ollama`, uses local LLMs for natural language inference

Contradictions are **preserved, not resolved**. Both claims remain in the index unchanged.

```json
{
  "pair": {
    "claim_id_a": "clm1",
    "claim_id_b": "clm3"
  },
  "label": "contradiction",
  "evidence_quotes": [...]
}
```

**Guarantee:** If two claims contradict, both are extracted and the contradiction is reported.

**Status:** Semantic + negation detection is core. NLI labeling is optional (requires Ollama).

### Phase 8 (Optional): Index Building
**Input:** All components  
**Output:** Structured JSON index

All analysis is assembled into a single JSON index:
- Complete chunk data with offsets
- Cluster definitions
- All extracted claims with quotes
- All detected contradictions
- Metadata (document ID, timestamp)

The index is validated against a schema to ensure structural integrity.

**Status:** Deterministic, always-on if earlier phases complete.

### Phase 9 (Optional): Evidence Projections
**Input:** Semantic index  
**Output:** Structural reorganizations of the index

The index can be reformatted for different viewing needs:

**Claim-centric view:**
- List all claims with their quotes
- Organized by cluster or topic
- No rewriting or paraphrasing
- All text is verbatim from the index

**Chunk-centric view:**
- All chunks in order with claim annotations
- Shows where claims originated
- Preserves narrative flow of source

**Contradiction-centric view:**
- Pairs of contradictory claims grouped
- Highlights tension in the source
- Both sides shown in full

**Important:** These are structural reorganizations only. No paraphrasing, summarization, or interpretation occurs. All text is verbatim claims or direct quotes.

**Status:** Formatting utilities, not core engine.

### Phase 10 (Optional): Artifact Persistence
**Input:** All outputs  
**Output:** Files written to disk

All results are persisted:
- `index.json` – Complete semantic index
- `embeddings.npy` – Embedding vectors (NumPy format)
- Projection files (text files in various formats)

```
output_index/
├── index.json           (Full semantic index)
├── embeddings.npy       (Embedding vectors)
└── [projections]        (Structural reorganizations)
```

**Status:** Deterministic, always-on.

---

## Command-Line Interface

### Core: Compress and Index
```bash
sse compress --input document.txt --out ./index_dir
```

Produces the semantic index by running Phases 1–5 and optional Phases 6–7.

**Options:**
- `--max-chars`: Maximum chunk size in characters (default: 800)
- `--overlap`: Character overlap between chunks (default: 200)
- `--embed-model`: Sentence transformer model (default: all-MiniLM-L6-v2)
- `--cluster-method`: Clustering algorithm: hdbscan, agg, kmeans (default: hdbscan)
- `--min-cluster-size`: Minimum cluster size (default: 2)
- `--use-ollama`: Enable local LLM for enhanced extraction and NLI-based contradiction detection (optional, experimental)
- `--ollama-model`: Which Ollama model to use (default: llama2; only if `--use-ollama` is set)

### Optional: Retrieve and Navigate the Index
```bash
sse query --index ./index_dir/index.json --query "capital of France" --k 5
```

Retrieves the top-k clusters **most semantically similar** to the query term. This is **not QA**—it does not answer questions. Instead, it shows clusters containing related claims.

Returns for each cluster:
- All claims in the cluster
- Supporting quotes for each claim
- Any detected contradictions involving those claims
- Ambiguity markers

**Options:**
- `--index`: Path to the index JSON file (required)
- `--query`: Retrieval term or topic keyword (required)
- `--k`: Number of top clusters to return (default: 5)

**Important caveat:** The query system is a **retrieval/navigation tool**, not a semantic answering system. Provide topic keywords, entity names, or claim fragments. Do not expect natural language questions to be answered.

Examples of appropriate queries:
- `"climate change"`
- `"vaccine safety"`
- `"contract obligations"`

Examples of inappropriate queries (will not work as expected):
- `"What is the main point?"`
- `"Why did X happen?"`
- `"Should I believe A or B?"`

### Optional: Evaluate Index Quality
```bash
sse eval --input document.txt --index ./index_dir/index.json
```

Produces a quantitative report on the index:
- **Compression ratio**: Size of original text vs. size of index
- **Claim density**: Number of claims extracted
- **Quote coverage**: Percentage of source text quoted in claims
- **Contradiction count**: Number of detected contradictions
- **Cluster distribution**: How claims are distributed across clusters

**Note:** These metrics are descriptive, not normative. A "good" compression ratio, claim density, or quote coverage depends on your domain. SSE does not claim that any specific ratio indicates quality.

---

## Output Schema

### Index Structure
```json
{
  "doc_id": "filename.txt",
  "timestamp": "2025-01-03T12:34:56.789Z",
  
  "chunks": [
    {
      "chunk_id": "c0",
      "text": "...",
      "start_char": 0,
      "end_char": 800,
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

---

## Key Design Decisions

### Why Quoting?
Verbatim quotes are the foundation of auditability. They prevent claim drift and enable readers to independently verify SSE's extractions against the source. Because phase 5 achieved strict offset reconstruction, claims like "byte-level offsets enable verification" are now concrete, not aspirational.

### Why Preserve Contradictions?
Suppressing contradictions to achieve narrative coherence would be information loss. SSE exposes contradictions as factual observations: these two claims exist in the source and they contradict. The system never decides which is true. This is essential in domains where competing claims are information, not noise.

### Why Clustering Over Summarization?
Clustering groups semantically related claims structurally. It does not fuse them, merge opposite ones, or create summaries. Clustering enables users to navigate the semantic shape of the source without losing any original content.

### Why Rule-Based Extraction by Default?
The default claim extraction uses pattern matching: it is slow, conservative, and never hallucinates. It only extracts what is explicitly present in the source text. Optional LLM extraction is available for domains where inference is acceptable, but it is not default.

### Why Local Embeddings (Not Cloud)?
Sentence transformers and optional local Ollama models avoid cloud dependencies, preserve privacy, and eliminate latency. SSE works offline and on-device.

### Why Not "Semantic Coverage" Metrics?
Early drafts promised "% of meaning preserved." This metric is philosophically tricky: it assumes "meaning" is well-defined, measurable, and that compression ratios indicate quality. SSE instead reports raw descriptive metrics (claim count, quote coverage, contradiction count) and leaves interpretation to the user. A dense index with many contradictions is not "worse" than a sparse one—it is more honest.

---

## Use Cases

### Legal Document Analysis
Extract claims from contracts, regulations, and legislation. Identify contradictions and ambiguities. Preserve verbatim language for compliance auditing. Enable navigation of complex regulatory text without lossy summarization.

### Medical Record Synthesis
Compress clinical notes while preserving all observations and contradictions. Detect conflicting diagnoses or treatment recommendations. Maintain quote trails for malpractice review or quality assurance.

### Research Paper Analysis
Index claims from papers, group by topic, detect contradictions with cited work, preserve exact citations for attribution. Navigate related claims across multiple sources.

### Policy Document Auditing
Analyze policy language for internal contradictions, ambiguities, and conflicting obligations. Preserve exact commitment language for enforcement. Expose unresolved tensions in policy.

### Multi-Source Fact-Checking
Combine claims from multiple sources, detect systematic contradictions, identify where ambiguity differs across sources. Maintain provenance trails for each claim across document boundaries.

---

## Summary

The Semantic String Engine is a semantic indexing and contradiction exposure system. It extracts claims as exact substrings, organizes them into semantic clusters, detects contradictions, and exposes ambiguity—without summarizing, interpreting, or deciding what is true.

**What SSE guarantees:**
- Every claim is quoted verbatim from the source with byte-level offsets
- Contradictions are detected and both sides are preserved
- Claims are never merged or deduplicationed because they contradict
- Nothing is fabricated or inferred beyond explicit pattern matching
- All claims and contradictions are auditable and traceable to source

**What SSE is not:**
- Not a summarizer (it does not condense or abstract)
- Not a QA system (it does not answer questions)
- Not a reasoning engine (it does not draw conclusions)
- Not an interpreter (it does not decide meaning)
- Not an inference system by default (optional LLM extraction is experimental)

**What SSE does uniquely:**
- Exposes rather than resolves contradictions
- Preserves competing claims without narrative rewriting
- Maintains strict auditability through verbatim quoting
- Enables navigation and retrieval without lossy compression
- Surfaces ambiguity and hedging for human review

The system is ideal for domains where contradictions are information (not noise), auditability is mandatory, and competing claims must be preserved intact: legal analysis, policy review, medical synthesis, and research fact-checking.

Once tightened as above, SSE clearly distinguishes itself from RAG systems (which retrieve but do not extract contradictions), summarizers (which abstract), NLI classifiers (which label, not extract), and "AI explanations" (which interpret). It is a structural analyzer that exposes, rather than resolves, the semantic tension in text.
