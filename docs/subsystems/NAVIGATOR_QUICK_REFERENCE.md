## SSE Navigator Quick Reference

**Phase 6, D2: Read-Only Interaction Layer**

The Navigator enables you to explore SSE indices without synthesis, truth-picking, or ambiguity softening.

---

### Installation

```bash
pip install -e .
```

### Basic Usage

#### Show Index Info
```bash
sse navigate --index output_index/index.json --info
```

Output:
```
INDEX INFORMATION
doc_id: sample_sleep.txt
num_chunks: 6
num_claims: 6
num_clusters: 2
num_contradictions: 8
num_claims_with_ambiguity: 1
has_embeddings: True
```

---

#### Search for Claims (Keyword)
```bash
sse navigate --index output_index/index.json --query "sleep" --k 5
```

Search by topic, keyword, or phrase. Returns up to `k` matching claims.

---

#### Find Contradictions About a Topic
```bash
sse navigate --index output_index/index.json --topic-contradictions "vaccine"
```

Shows all contradictions where at least one claim mentions the topic. **Both sides shown in full. No interpretation provided.**

Example output:
```
CONTRADICTION DETECTED
[CLAIM A]
Vaccines are highly effective for disease prevention.
  Quote: "Vaccines are highly effective..."

[CLAIM B]
Some vaccine side effects require careful monitoring.
  Quote: "Some vaccine side effects..."

Label: contradiction
⚠️  Both claims are shown in full.
No interpretation is provided. You decide what this means.
```

---

#### Show Claim Provenance (Exact Source)
```bash
sse navigate --index output_index/index.json --provenance clm_001
```

Traces claim to exact source location with byte-level offsets:
```
CLAIM PROVENANCE
Claim ID: clm_001
Claim Text: Climate change impacts are already observable.

Supporting Quotes (1):
1. Quote: "Climate change impacts are already observable."
   Chunk ID: c5
   Byte Range: [1234:1290]
   Length: 56 characters
   Reconstructed Match: True
```

---

#### Show Uncertain Claims
```bash
sse navigate --index output_index/index.json --uncertain --min-hedge 0.5
```

List all claims with high uncertainty (hedge language, conflict markers, open questions).

Output:
```
Found 3 claims with uncertain language (hedge score >= 0.5):
1. [0.72] Some scientists suggest climate change may impact...
2. [0.68] Studies indicate possible correlation between...
3. [0.51] Evidence suggests that in certain circumstances...
```

---

#### Show All Contradictions
```bash
sse navigate --index output_index/index.json --all-contradictions
```

List all contradictions in the index. Each shown with both claims in full.

---

#### Get a Semantic Cluster
```bash
sse navigate --index output_index/index.json --cluster cls_001
```

Show all claims in a semantic cluster (requires embeddings).

---

### Python API

Use in your own Python code:

```python
from sse.interaction_layer import SSENavigator

nav = SSENavigator("output_index/index.json")

# Get index info
info = nav.info()
print(f"Claims: {info['num_claims']}")

# Search
results = nav.query("climate change", k=5, method="keyword")
for claim in results:
    print(claim["claim_text"])

# Find contradictions
contradictions = nav.get_contradictions_for_topic("vaccine")
for contra in contradictions:
    formatted = nav.format_contradiction(contra)
    print(formatted)

# Show provenance
prov = nav.get_provenance("clm_123")
for quote in prov["supporting_quotes"]:
    print(f"Quote: {quote['quote_text']}")
    print(f"Location: {quote['start_char']}:{quote['end_char']}")

# Find uncertain claims
uncertain = nav.get_uncertain_claims(min_hedge=0.5)
for claim in uncertain:
    ambiguity = claim.get("ambiguity", {})
    print(f"[{ambiguity['hedge_score']:.2f}] {claim['claim_text']}")

# Get all contradictions
all_contradictions = nav.get_contradictions()

# Show specific contradiction
claim_a = nav.get_claim_by_id("clm_001")
claim_b = nav.get_claim_by_id("clm_002")
contra = nav.get_contradiction_by_pair("clm_001", "clm_002")
```

---

### What the Navigator PERMITS

✅ **Retrieval**: Get claims, contradictions, clusters by ID
✅ **Search**: Find claims by keyword or semantic similarity
✅ **Filter**: Show only claims with high ambiguity, specific topics
✅ **Navigate**: Move through semantic clusters and related claims
✅ **Expose Provenance**: Show exact byte offsets and quotes
✅ **Expose Ambiguity**: Display hedge scores, conflict markers, open questions
✅ **Display**: Show claims in structured, readable formats

---

### What the Navigator FORBIDS

❌ **Synthesis**: Never generates new claims
❌ **Truth Picking**: Never selects one claim over another
❌ **Ambiguity Softening**: Never hides hedge language or uncertainty
❌ **Paraphrasing**: Always shows verbatim text from source
❌ **Suppression**: Always shows all contradictions, never hidden
❌ **Opinion**: Never interprets or judges claims
❌ **Modification**: Never changes claim text or quotes

Violating these constraints raises `SSEBoundaryViolation` exception.

---

### Examples

#### Exploring a Controversial Topic

```bash
# Find all claims about a topic
sse navigate --index index.json --query "artificial intelligence"

# See contradictions
sse navigate --index index.json --topic-contradictions "artificial intelligence"

# Examine uncertain claims
sse navigate --index index.json --uncertain --min-hedge 0.3

# Get exact sources
sse navigate --index index.json --provenance clm_042
```

#### Auditing a Specific Claim

```bash
# Get exact text and location
sse navigate --index index.json --provenance clm_042

# Find all contradicting claims
sse navigate --index index.json --query "clm_042"  # (not yet supported; use Python API)

# See all its supporting quotes and offsets
python -c "
from sse.interaction_layer import SSENavigator
nav = SSENavigator('index.json')
prov = nav.get_provenance('clm_042')
for quote in prov['supporting_quotes']:
    print(f'{quote[\"quote_text\"]} [{quote[\"start_char\"]}:{quote[\"end_char\"]}]')
"
```

#### Finding Ambiguity

```bash
# All claims with uncertain language
sse navigate --index index.json --uncertain --min-hedge 0.0

# Most uncertain claims
sse navigate --index index.json --uncertain --min-hedge 0.7
```

---

### Error Handling

```
$ sse navigate --index index.json --provenance nonexistent
Claim not found: nonexistent

$ sse navigate --index index.json --synthesize-answer "What is true?"
❌ SSE Boundary Violation: synthesize_answer
Reason: SSE does not synthesize or generate answers...
```

---

### Index Requirements

The navigator requires an SSE index created via:

```bash
sse compress --input document.txt --out output_index/
```

This creates:
- `output_index/index.json` - Main index with chunks, claims, contradictions
- `output_index/embeddings.npy` - Embeddings for semantic search (optional)

---

### Notes

- **Semantic search** requires embeddings (created automatically by `compress`)
- **Keyword search** works without embeddings
- All byte offsets are **0-indexed, inclusive start, exclusive end** (Python convention)
- Claim IDs are auto-generated as `clm0`, `clm1`, etc.
- Chunk IDs are auto-generated as `c0`, `c1`, etc.
- Cluster IDs are auto-generated as `cls0`, `cls1`, etc.

---

### Phase 6 Status

✅ D1: Interface Contract (SSE_INTERFACE_CONTRACT.md)
✅ D2: Interaction Layer (sse/interaction_layer.py) - **You are here**
⏳ D3: Coherence Tracking (SSE_COHERENCE_TRACKING.md)
⏳ D4: Platform Integration (SSE_PLATFORM_INTEGRATION.md)
⏳ D5: Test Suite (Full boundary violation coverage)

The navigator is the first concrete tool that enforces Phase 6 integrity boundaries.
