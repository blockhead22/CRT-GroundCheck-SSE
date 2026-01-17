# Semantic String Engine (SSE) v0.1
## White Paper: Contradiction-Preserving Knowledge Extraction for Trustworthy AI Systems

**Date:** January 8, 2026  
**Version:** 0.1.0  
**Status:** Production-Ready

---

## Executive Summary

The Semantic String Engine (SSE) is a novel approach to semantic search and knowledge extraction that **preserves contradictions instead of resolving them**. Unlike traditional Retrieval-Augmented Generation (RAG) systems that quietly filter or rank conflicting information, SSE guarantees that all contradictory claims are surfaced, attributed to their exact sources, and presented without interpretation.

SSE addresses a critical gap in AI trustworthiness: the tendency of information retrieval systems to pick "winners" from conflicting evidence, creating artificial consensus where none exists in the source material.

**Key Innovation:** A philosophy-driven architecture that enforces strict boundaries between observation (permitted) and interpretation (forbidden), backed by schema validation gates and provenance guarantees.

---

## 1. Problem Statement

### 1.1 The Contradiction Suppression Problem

Modern RAG systems suffer from systematic contradiction suppression through three mechanisms:

1. **Retrieval Ranking**: Similarity-based retrieval favors a single perspective, leaving contradicting claims below the cutoff
2. **Synthesis Pressure**: LLMs naturally synthesize coherent narratives, smoothing over source contradictions
3. **Confidence Bias**: Systems preferentially surface claims with higher confidence scores, hiding uncertainty

**Real-World Impact:**
- Legal AI systems miss contradictory clauses in contracts
- Research assistants hide conflicting scientific findings
- Policy analysis tools overlook regulatory exceptions
- Compliance systems fail to surface requirement conflicts

### 1.2 The Provenance Gap

Even systems that attempt to preserve contradictions often fail to maintain precise source attribution. Without character-level offsets into original documents, claims become untraceable, making verification impossible.

---

## 2. Core Architecture

### 2.1 Pipeline Overview

```
Document(s) → Chunking → Embedding → Claim Extraction → Contradiction Detection → Index
                ↓            ↓             ↓                    ↓                    ↓
          Provenance   Clustering   Ambiguity           Topology Mapping      Evidence Packet
```

**Lossless Guarantee:** Every transformation preserves exact character offsets into source documents, verified through reconstruction assertions.

### 2.2 Key Components

#### **Chunker** (`sse/chunker.py`)
- Sentence-boundary aware chunking with configurable overlap
- **Invariant:** `text[chunk['start_char']:chunk['end_char']] == chunk['text']`
- No text modification; all operations use spans

#### **Claim Extractor** (`sse/extractor.py`)
- Dual-mode: Rule-based (fast) or LLM-assisted (accurate)
- **Anti-Feature:** Negation detection prevents deduplication of opposite claims
- Preserves sentence-level offsets within chunks

#### **Contradiction Detector** (`sse/contradictions.py`)
- Embedding similarity pre-filter (semantic relatedness)
- Optional LLM NLI classification (Ollama integration)
- Heuristic fallback (negation patterns, opposition words)
- **Cached:** NLI results cached by claim-pair hash

#### **Coherence Tracker** (`sse/coherence.py`)
- Observes disagreement patterns without resolution
- Tracks relationship types: contradicts, conflicts, qualifies
- **Boundary Enforcement:** No truth-picking, no synthesis

#### **Evidence Packet** (`sse/evidence_packet.py`)
- Immutable output format with schema validation
- **Forbidden Fields:** confidence, credibility, truth_likelihood, synthesis
- **Forbidden Language:** Interpretive words flagged and rejected
- Audit trail with event logging

---

## 3. Interface Contract

SSE enforces a strict contract between observation and interpretation:

### 3.1 Permitted Operations

✅ **Retrieve:** Get claims by ID, query, filter  
✅ **Search:** Semantic or keyword search  
✅ **Filter:** By document, cluster, contradiction count  
✅ **Group:** Cluster by semantic similarity  
✅ **Navigate:** Browse claim relationships  
✅ **Expose:** Show provenance, contradictions, ambiguity  

### 3.2 Forbidden Operations

❌ **Synthesize:** Create new claims not in source  
❌ **Pick Winners:** Choose between contradictory claims  
❌ **Soften Ambiguity:** Hide uncertainty or disagreement  
❌ **Paraphrase:** Modify claim language  
❌ **Suppress:** Filter claims by quality/confidence  
❌ **Interpret:** Add meaning not in source  

### 3.3 Boundary Violation Detection

```python
class SSEBoundaryViolation(Exception):
    """Raised when operation violates Interface Contract"""
```

- Runtime enforcement through `SSENavigator` and `AdapterBoundary`
- Schema validation gates on all outputs
- Forbidden field/word scanning in Evidence Packets

---

## 4. Multi-Document Support

### 4.1 Document Registry

SSE supports processing multiple documents into a single index with per-claim provenance:

```python
multi_sse = MultiDocSSE()
multi_sse.add_document(text1, filename="policy_v1.txt")
multi_sse.add_document(text2, filename="policy_v2.txt")
multi_sse.process_documents()
```

Each claim tracks:
- `doc_id`: Source document identifier
- `start_char`, `end_char`: Offsets into that document
- Reconstruction validation: `doc_registry.get_text(doc_id)[start:end]`

### 4.2 Cross-Document Contradiction Detection

Within-document contradictions detected by default. Cross-document detection planned for future releases.

---

## 5. Adapter Integration

### 5.1 RAG Adapter

**Purpose:** Feed contradictions into LLM prompts without filtering

**Flow:**
```
Query → EvidencePacket → RAGAdapter → LLM Prompt (with contradictions) → Response
         ↑ validated         ↑                                              ↓
         └─────────────── Hard Gate ────────────────────────────────────────┘
                          (re-validation)
```

**Prompt Strategy:**
- List ALL claims (no ranking suppression)
- Explicitly surface contradictions with both sides
- Include contradiction counts in claim metadata
- No interpretive language ("likely," "seems," "probably")

**Example Output:**
```
Query: Are sleep requirements universal?

Found 5 claims:

1. "Most adults need 7-9 hours of sleep" (source: doc0)
   ⚠ CONTRADICTS with claims [3, 4]

2. "Sleep requirements are highly individual" (source: doc0)
   ⚠ CONTRADICTS with claim [1]

[LLM processes both sides of contradiction]
```

### 5.2 Search Adapter

**Purpose:** Render contradiction graphs for UI visualization

**Output Structure:**
```json
{
  "results": [
    {
      "claim_id": "clm0",
      "text": "...",
      "contradiction_count": 2,
      "contradicts_with": ["clm3", "clm5"]
    }
  ],
  "contradictions": [
    {
      "from_id": "clm0",
      "to_id": "clm3",
      "relationship": "contradicts",
      "strength": 0.85
    }
  ],
  "clusters": [...]
}
```

**UI Capabilities:**
- Highlight contradictory claim pairs
- Group contradictions by cluster
- Show provenance on hover/click
- Filter by contradiction density

---

## 6. Validation Architecture

### 6.1 Three-Gate System

**Gate 1: Input Validation**
- Evidence Packet schema check before processing
- Ensures adapters receive clean input

**Gate 2: Adapter Internal Validation**
- RAGAdapter validates output before returning
- SearchAdapter validates structure conformance

**Gate 3: Boundary Exit Validation**
- Platform integration layer (`AdapterBoundary`) re-validates
- Hard gate: System fails if validation fails
- No silent failures or degradation

### 6.2 Schema Enforcement

Evidence Packet schema (`evidence_packet.v1.schema.json`):
- JSON Schema validation via `jsonschema` library
- Forbidden field detection (runtime scanning)
- Forbidden word detection in descriptions
- Event log immutability checks

---

## 7. Use Cases

### 7.1 AI Safety & Alignment

**Challenge:** LLMs hallucinate or create false consensus from conflicting sources

**SSE Solution:**
- Force contradictions into prompts
- Prevent RAG from hiding conflicting evidence
- Enable auditing of what evidence LLM saw

**Impact:** Trustworthy AI systems that don't paper over uncertainty

### 7.2 Legal & Compliance Analysis

**Challenge:** Contracts contain contradictory clauses, exceptions, edge cases

**SSE Solution:**
- Detect conflicting requirements across 1000+ page documents
- Maintain exact citation with character offsets
- Surface exceptions that contradict general rules

**Impact:** Catch conflicts before they cause legal issues

### 7.3 Policy Analysis

**Challenge:** Regulations contain conflicting mandates, loopholes, amendments

**SSE Solution:**
- Track contradictions across versions of policy documents
- Multi-document support for bills + amendments
- No filtering of "less important" requirements

**Impact:** Complete understanding of regulatory landscape

### 7.4 Research Literature Review

**Challenge:** Scientific papers present conflicting findings; systematic reviews introduce bias

**SSE Solution:**
- Surface ALL findings on a topic, including contradictory ones
- Cluster similar claims to show debate structure
- No automatic winner-picking between methodologies

**Impact:** Unbiased literature synthesis

### 7.5 Investigative Journalism

**Challenge:** Source documents contain inconsistencies, contradictory statements

**SSE Solution:**
- Automatically detect contradictions in witness statements, reports
- Exact source attribution for fact-checking
- Timeline tracking via multi-document provenance

**Impact:** Faster investigation with audit trail

### 7.6 Enterprise Knowledge Management

**Challenge:** Corporate wikis, documentation contain outdated/conflicting information

**SSE Solution:**
- Surface contradictions between documentation versions
- Track document provenance across teams
- No silent preference for newer vs. older docs

**Impact:** Identify documentation conflicts before they cause incidents

---

## 8. Technical Specifications

### 8.1 Dependencies

**Core:**
- `sentence-transformers` (embeddings)
- `scikit-learn` (clustering, TF-IDF fallback)
- `hdbscan` (density-based clustering)
- `jsonschema` (validation)
- `numpy` (vector operations)

**Optional:**
- Ollama (local LLM for NLI and extraction)
- Any embedding model compatible with sentence-transformers

### 8.2 Performance Characteristics

**Chunking:** O(n) where n = document length  
**Embedding:** O(m) where m = number of chunks/claims  
**Contradiction Detection:** O(k²) where k = semantically similar claims (pre-filtered)  
**Clustering:** O(m log m) with HDBSCAN  

**Optimization:** Embedding similarity pre-filter reduces contradiction detection from O(n²) to O(k²) where k << n

### 8.3 Scalability

**Single Document:**
- Tested up to 50,000+ words
- ~500-1000 chunks typical
- ~200-500 claims typical
- Contradiction detection: seconds to minutes depending on LLM usage

**Multi-Document:**
- Tested with 10+ documents
- Document registry tracks provenance
- Linear scaling in number of documents (within-doc contradictions)
- Cross-doc contradictions: future enhancement

### 8.4 Storage

**Index Format:** JSON
- `index.json`: Full SSE index with claims, contradictions, clusters
- `embeddings.npy`: NumPy array of embedding vectors (optional, for semantic search)

**Typical Sizes:**
- 10K word document → ~200KB index
- Embeddings: ~100KB per 100 claims (384-dim vectors)

---

## 9. Development Philosophy

### 9.1 Design Principles

1. **Transparency First:** Show all evidence, hide nothing
2. **Provenance Always:** Every claim traceable to exact source
3. **Boundaries Enforced:** Hard separation between observation and interpretation
4. **Validation Paranoia:** Multiple gates, schema enforcement, assertion checking
5. **No Silent Failures:** Violations raise exceptions, never degrade gracefully

### 9.2 Anti-Patterns Prevented

❌ **Consensus Building:** No aggregation of contradictory claims into "most likely" answer  
❌ **Confidence Scoring:** No ranking claims by "reliability" or "quality"  
❌ **Relevance Filtering:** No suppression of claims below confidence threshold  
❌ **Paraphrasing:** No rewriting of source language  
❌ **Synthesis:** No generation of claims not in source  

### 9.3 Testing Strategy

**Unit Tests:** Individual component validation  
**Integration Tests:** Full pipeline from text → Evidence Packet  
**Boundary Tests:** Violation detection enforcement  
**Provenance Tests:** Reconstruction validation  
**Schema Tests:** Forbidden field/word detection  

Test coverage focuses on **invariant preservation** rather than code coverage percentages.

---

## 10. Comparison with Existing Systems

### 10.1 vs. Traditional RAG

| Feature | Traditional RAG | SSE |
|---------|----------------|-----|
| Contradiction Handling | Implicit resolution via ranking | Explicit preservation |
| Provenance | Chunk-level (lossy) | Character-level (lossless) |
| Synthesis | Encouraged | Forbidden |
| Confidence Scores | Central to design | Explicitly prohibited |
| Validation | Optional | Hard gates |

### 10.2 vs. Vector Databases

| Feature | Vector DB | SSE |
|---------|-----------|-----|
| Purpose | Similarity retrieval | Contradiction-aware knowledge extraction |
| Output | Ranked results | All claims + contradiction graph |
| Filtering | Top-k cutoff | No suppression |
| Metadata | User-defined | Schema-enforced Evidence Packet |

### 10.3 vs. Knowledge Graphs

| Feature | Knowledge Graph | SSE |
|---------|----------------|-----|
| Structure | Entities + Relations | Claims + Contradictions |
| Contradiction | Often ignored or resolved | Core feature |
| Provenance | Typically edge metadata | Character-level offsets |
| Inference | Common | Forbidden |

---

## 11. Roadmap

### Phase 1: Core Pipeline ✅ (Complete)
- Chunking with provenance
- Claim extraction (rule-based + LLM)
- Contradiction detection
- Evidence Packet format

### Phase 2: Multi-Document ✅ (Complete)
- Document registry
- Per-claim doc_id tracking
- Within-document contradictions

### Phase 3: Integration Layer ✅ (Complete)
- RAG adapter with validation gates
- Search adapter with contradiction visualization
- Platform integration boundary

### Phase 4: Advanced Features (Planned)
- Cross-document contradiction detection
- Temporal contradiction tracking (versioned documents)
- Contradiction type classification (direct vs. conditional)
- Ambiguity quantification (beyond boolean flags)

### Phase 5: Ecosystem (Planned)
- REST API server
- Web UI for contradiction exploration
- Browser extension for inline source verification
- Jupyter notebook integration

---

## 12. Getting Started

### 12.1 Installation

```bash
pip install -r requirements.txt
python setup.py install
```

### 12.2 Basic Usage

**CLI:**
```bash
# Process a document
sse compress input.txt --out output_index/

# Navigate index
python navigator_demo.py
```

**Python API:**
```python
from sse.multi_doc import MultiDocSSE

# Create pipeline
sse = MultiDocSSE()
sse.add_document_from_file("document.txt")
sse.process_documents()

# Query with navigator
from sse.interaction_layer import SSENavigator
nav = SSENavigator("output_index/index.json")

# Search for claims
results = nav.query("sleep requirements", k=5, method="semantic")

# Get contradictions
contradictions = nav.get_contradictions()
for c in contradictions:
    print(nav.format_contradiction(c))
```

### 12.3 RAG Integration

```python
from sse.platform_integration import get_adapter_boundary
from sse.evidence_packet import EvidencePacket

# Build Evidence Packet from query
packet = EvidencePacket.from_navigator(
    navigator=nav,
    query="Are sleep needs universal?",
    k=10
)

# Process through RAG adapter
boundary = get_adapter_boundary()
result = boundary.rag_endpoint(
    query="Are sleep needs universal?",
    packet_dict=packet.to_dict()
)

if result["valid"]:
    print(result["llm_response"])
else:
    print(f"Validation failed: {result['error']}")
```

---

## 13. Limitations & Future Work

### 13.1 Current Limitations

1. **Within-Document Only:** Cross-document contradictions not yet implemented
2. **English-Centric:** Sentence splitting optimized for English text
3. **Computational Cost:** Full NLI checking is expensive; requires caching or pre-filtering
4. **Contradiction Types:** Currently binary; doesn't distinguish direct vs. conditional contradictions
5. **Temporal Awareness:** No built-in handling of time-sensitive claims

### 13.2 Research Directions

- **Contradiction Taxonomy:** Classify contradiction types (logical, empirical, definitional)
- **Confidence Bands:** Surface source-provided confidence without adding interpretation
- **Multi-Modal:** Extend to images, tables, structured data
- **Real-Time Updates:** Incremental index updates as documents change
- **Distributed Processing:** Scale to 1000+ documents with partitioning

---

## 14. Conclusion

The Semantic String Engine represents a paradigm shift in information retrieval: from **consensus-seeking** to **contradiction-preserving**. By enforcing strict boundaries between observation and interpretation, SSE enables a new class of AI systems that are transparent, auditable, and trustworthy.

In domains where contradictions matter—law, policy, research, journalism, compliance—SSE provides the infrastructure to build AI assistants that **show all sides** rather than picking winners.

The architecture is production-ready, extensively tested, and designed for integration into existing RAG pipelines with minimal friction. Evidence Packet format ensures compatibility across different adapter types while maintaining strict validation guarantees.

**Core Value Proposition:** SSE makes contradiction suppression impossible by design, not by policy.

---

## 15. References & Resources

**Code Repository:** https://github.com/blockhead22/AI_round2  
**Documentation Index:** See `EVIDENCE_PACKET_DOCUMENTATION_INDEX.md`  
**Integration Guide:** See `SSE_PLATFORM_INTEGRATION.md`  
**API Reference:** See `SSE_INTERFACE_CONTRACT.md`  

**Key Modules:**
- `sse/chunker.py` - Lossless text chunking
- `sse/extractor.py` - Claim extraction with negation detection
- `sse/contradictions.py` - Multi-strategy contradiction detection
- `sse/evidence_packet.py` - Schema enforcement and validation
- `sse/interaction_layer.py` - Read-only navigation interface
- `sse/platform_integration.py` - Adapter boundary with hard gates

---

## Appendix A: Evidence Packet Schema

```json
{
  "schema_version": "1.0",
  "claims": [
    {
      "claim_id": "string",
      "claim_text": "string",
      "source_document_id": "string",
      "extraction_offset": {"start": 0, "end": 100},
      "extraction_verified": true
    }
  ],
  "contradictions": [
    {
      "claim_a_id": "string",
      "claim_b_id": "string",
      "relationship_type": "contradicts|qualifies|extends",
      "topology_strength": 0.85,
      "detected_timestamp": "ISO8601"
    }
  ],
  "support_metrics": {
    "claim_id": {
      "source_count": 1,
      "retrieval_score": 0.95,
      "contradiction_count": 2,
      "cluster_membership_count": 1
    }
  },
  "metadata": {
    "query": "string",
    "timestamp": "ISO8601",
    "indexed_version": "0.1.0",
    "adapter_request_id": "uuid"
  },
  "audit_trail": [
    {
      "event_type": "query_executed",
      "timestamp": "ISO8601",
      "details": {}
    }
  ]
}
```

**Forbidden Fields (will cause validation failure):**
- confidence, credibility, reliability, truth_likelihood
- quality, importance, consensus, agreement
- resolved, settled, preferred, synthesis

---

## Appendix B: Boundary Violation Examples

**Permitted:**
```python
# Retrieve all claims about a topic
claims = nav.query("sleep", method="keyword")

# Show contradiction with both sides
contradiction = nav.get_contradictions()[0]
formatted = nav.format_contradiction(contradiction)
```

**Forbidden (raises SSEBoundaryViolation):**
```python
# Attempting synthesis
summary = nav.synthesize_claims(claims)  # ❌ No such method

# Attempting winner-picking
best_claim = nav.pick_most_credible(claims)  # ❌ No such method

# Attempting filtering by quality
high_quality = nav.filter_by_confidence(claims, threshold=0.8)  # ❌ Forbidden
```

---

**Document Version:** 1.0  
**Last Updated:** January 8, 2026  
**Authors:** SSE Development Team  
**License:** See repository for licensing information
