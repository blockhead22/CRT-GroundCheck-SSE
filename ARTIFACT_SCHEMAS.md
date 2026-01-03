# SSE Artifact Schemas: Complete JSON Documentation

## Overview

All SSE outputs are JSON documents following strict schemas. This document defines each schema, explains each field, and shows why it exists.

These schemas are **data contracts**. SSE guarantees that all outputs conform to these schemas.

---

## 1. Chunk Schema

### JSON Structure

```json
{
  "chunk_id": "c0",
  "text": "The Earth is round. Scientists have proven...",
  "start_char": 0,
  "end_char": 256
}
```

### Field Definitions

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `chunk_id` | string | Yes | Unique identifier for this chunk, format: `c{index}` |
| `text` | string | Yes | The exact substring from source: `source[start_char:end_char]` |
| `start_char` | integer | Yes | 0-indexed byte offset where chunk begins (inclusive) |
| `end_char` | integer | Yes | 0-indexed byte offset where chunk ends (exclusive) |

### Validation Rules

1. `start_char < end_char` (non-empty chunk)
2. `0 <= start_char < end_char <= len(source)`
3. `source[start_char:end_char] == text` (exact match)
4. Chunk IDs are sequential: `c0, c1, c2, ...`
5. Chunks may overlap (controlled by `overlap` parameter in `chunk_text()`)

### Why This Schema?

- **Traceability**: Every chunk maps to exact source position
- **Reconstruction**: Original text can be perfectly reconstructed from chunks
- **Verification**: Third parties can verify claims against source using these offsets
- **Deduplication**: Overlapping chunks prevent loss of content at boundaries

### Example

```json
{
  "chunk_id": "c0",
  "text": "The Earth is round. Scientists have definitively proven that the Earth is a sphere.",
  "start_char": 0,
  "end_char": 85
}
```

---

## 2. Claim Schema

### JSON Structure

```json
{
  "claim_id": "clm0",
  "claim_text": "The Earth is round.",
  "supporting_quotes": [
    {
      "text": "The Earth is round.",
      "chunk_id": "c0",
      "start_char": 0,
      "end_char": 18
    }
  ],
  "ambiguity": {
    "score": 0.1,
    "type": "none",
    "hedge_detected": false,
    "details": {}
  }
}
```

### Field Definitions

#### Top Level

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `claim_id` | string | Yes | Unique identifier, format: `clm{index}` |
| `claim_text` | string | Yes | The claim text (usually verbatim from source, may be extracted sentence) |
| `supporting_quotes` | array | Yes | Array of quote objects grounding this claim (non-empty) |
| `ambiguity` | object | Yes | Ambiguity assessment for this claim |

#### Supporting Quote (nested in `supporting_quotes`)

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `text` | string | Yes | The exact quote text from source |
| `chunk_id` | string | Yes | Which chunk this quote belongs to |
| `start_char` | integer | Yes | 0-indexed byte offset where quote begins |
| `end_char` | integer | Yes | 0-indexed byte offset where quote ends |

#### Ambiguity (nested in `ambiguity`)

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `score` | float | Yes | Ambiguity score 0.0 (clear) to 1.0 (completely ambiguous) |
| `type` | string | Yes | Category: `"none"`, `"hedge"`, `"pronoun"`, `"scope"`, `"attribution"`, `"other"` |
| `hedge_detected` | boolean | Yes | True if claim contains hedge words ("may", "might", "some", "possibly", etc.) |
| `details` | object | Yes | Free-form explanation of ambiguity (may be empty) |

### Validation Rules

1. Every claim has at least one supporting quote
2. For each quote: `source[start_char:end_char] == text` (byte-exact match)
3. `claim_text` is typically verbatim from `supporting_quotes[0].text` or very similar
4. `ambiguity.score` is in range [0.0, 1.0]
5. `ambiguity.type` is one of the enumerated values
6. If `hedge_detected == true`, then `ambiguity.score >= 0.3`

### Why This Schema?

- **Quoting Invariant**: Every claim grounded in source via supporting quotes
- **Traceability Invariant**: Byte offsets allow verification
- **Uncertainty Invariant**: Ambiguity scores flag claims that lack clarity
- **Auditability**: Readers can check claim against source

### Example

```json
{
  "claim_id": "clm0",
  "claim_text": "The Earth is round.",
  "supporting_quotes": [
    {
      "text": "The Earth is round.",
      "chunk_id": "c0",
      "start_char": 0,
      "end_char": 18
    }
  ],
  "ambiguity": {
    "score": 0.05,
    "type": "none",
    "hedge_detected": false,
    "details": {}
  }
}
```

### Example: Hedged Claim

```json
{
  "claim_id": "clm5",
  "claim_text": "Some flat Earth believers claim the Earth is flat.",
  "supporting_quotes": [
    {
      "text": "Some flat Earth believers claim the Earth is flat.",
      "chunk_id": "c0",
      "start_char": 260,
      "end_char": 309
    }
  ],
  "ambiguity": {
    "score": 0.6,
    "type": "attribution",
    "hedge_detected": true,
    "details": {
      "hedge_words": ["some", "claim"],
      "reason": "Attribution to vague group; actual belief holders unclear"
    }
  }
}
```

---

## 3. Contradiction Schema

### JSON Structure

```json
{
  "pair": {
    "claim_id_a": "clm0",
    "claim_id_b": "clm3"
  },
  "label": "contradiction",
  "evidence_quotes": [
    {
      "text": "The Earth is round.",
      "chunk_id": "c0",
      "start_char": 0,
      "end_char": 18
    },
    {
      "text": "Some flat Earth believers claim the Earth is flat.",
      "chunk_id": "c0",
      "start_char": 260,
      "end_char": 309
    }
  ]
}
```

### Field Definitions

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `pair` | object | Yes | The two claims in the contradiction |
| `pair.claim_id_a` | string | Yes | ID of first claim in pair |
| `pair.claim_id_b` | string | Yes | ID of second claim in pair |
| `label` | string | Yes | Always `"contradiction"` in canonical output |
| `evidence_quotes` | array | Yes | Array of quotes supporting each side (min 2, usually 2) |

### Validation Rules

1. `claim_id_a` and `claim_id_b` must reference claims in the claims array
2. `label` is always `"contradiction"` (no other labels in primary output)
3. `evidence_quotes` has exactly 2 elements (one for each claim in pair)
4. Each quote must be valid (start < end, within source bounds, exact match)
5. `claim_id_a < claim_id_b` (ordered pair to prevent duplicates)

### Why This Schema?

- **Contradiction Preservation Invariant**: Both sides of contradiction recorded with evidence
- **Deduplication**: Ordered pairs prevent reporting same contradiction twice
- **Grounding**: Quotes prove that both sides actually exist in source

### Example

```json
{
  "pair": {
    "claim_id_a": "clm0",
    "claim_id_b": "clm3"
  },
  "label": "contradiction",
  "evidence_quotes": [
    {
      "text": "The Earth is round.",
      "chunk_id": "c0",
      "start_char": 0,
      "end_char": 18
    },
    {
      "text": "However, some flat Earth believers claim the Earth is flat.",
      "chunk_id": "c0",
      "start_char": 250,
      "end_char": 308
    }
  ]
}
```

---

## 4. Cluster Schema

### JSON Structure

```json
{
  "cluster_id": 0,
  "claim_ids": ["clm0", "clm1", "clm2"]
}
```

### Field Definitions

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `cluster_id` | integer | Yes | 0-indexed cluster identifier |
| `claim_ids` | array | Yes | List of claim IDs in this cluster |

### Validation Rules

1. `cluster_id` values are sequential starting from 0
2. `claim_ids` references actual claims from claims array
3. A claim appears in exactly one cluster (disjoint clustering)
4. Clusters are non-empty (min 1 claim)

### Why This Schema?

- **Semantic Organization**: Groups similar claims together
- **No Deduplication**: Clustering is informational, not deduplicative
- **Relationship Visibility**: Shows claim relationships without removing claims

### Example

```json
{
  "cluster_id": 0,
  "claim_ids": ["clm0", "clm1", "clm2"]
}
```

---

## 5. Metadata Schema

### JSON Structure

```json
{
  "timestamp": "2025-12-31T21:43:03.210373",
  "canonical_version": "1.0",
  "input_length_chars": 1407,
  "input_word_count": 213,
  "chunks_count": 6,
  "claims_count": 28,
  "contradictions_count": 34,
  "clusters_count": 12,
  "embedding_model": "all-MiniLM-L6-v2",
  "embedding_dimensions": 384,
  "contradiction_detector": "heuristic",
  "ollama_available": false
}
```

### Field Definitions

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `timestamp` | ISO 8601 string | Yes | When this run was executed |
| `canonical_version` | string | Yes | Version of canonical run (rarely changes) |
| `input_length_chars` | integer | Yes | Length of input text in characters |
| `input_word_count` | integer | Yes | Approximate word count of input |
| `chunks_count` | integer | Yes | Number of chunks created |
| `claims_count` | integer | Yes | Number of claims extracted |
| `contradictions_count` | integer | Yes | Number of contradictions detected |
| `clusters_count` | integer | Yes | Number of semantic clusters |
| `embedding_model` | string | Yes | Which embedding model was used |
| `embedding_dimensions` | integer | Yes | Dimensionality of embeddings |
| `contradiction_detector` | string | Yes | Which detector was used: `"heuristic"` or `"llm"` |
| `ollama_available` | boolean | Yes | Whether Ollama LLM service was available |

### Why This Schema?

- **Computational Honesty Invariant**: Documents conditions under which run occurred
- **Reproducibility**: Readers understand what settings produced these outputs
- **Debugging**: When outputs change, metadata explains whether it's due to model change, service availability, etc.
- **Validation**: Allows comparison between runs

### Example

```json
{
  "timestamp": "2025-12-31T21:43:03.210373",
  "canonical_version": "1.0",
  "input_length_chars": 1407,
  "input_word_count": 213,
  "chunks_count": 6,
  "claims_count": 28,
  "contradictions_count": 34,
  "clusters_count": 12,
  "embedding_model": "all-MiniLM-L6-v2",
  "embedding_dimensions": 384,
  "contradiction_detector": "heuristic",
  "ollama_available": false
}
```

---

## 6. Index Schema (Full Output)

### JSON Structure

This is the top-level document combining all of the above:

```json
{
  "doc_id": "contradiction_stress_test",
  "timestamp": "2025-12-31T21:43:03.210373",
  "chunks": [ /* array of chunk objects */ ],
  "clusters": [ /* array of cluster objects */ ],
  "claims": [ /* array of claim objects */ ],
  "contradictions": [ /* array of contradiction objects */ ]
}
```

### Field Definitions

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `doc_id` | string | Yes | Document identifier or name |
| `timestamp` | ISO 8601 string | Yes | When this analysis was performed |
| `chunks` | array | Yes | Array of chunk objects |
| `clusters` | array | Yes | Array of cluster objects |
| `claims` | array | Yes | Array of claim objects |
| `contradictions` | array | Yes | Array of contradiction objects |

### Validation Rules

1. `chunks`, `clusters`, `claims`, `contradictions` are all present and non-null
2. All referenced IDs are valid (e.g., every claim ID in contradictions exists in claims)
3. Schema for each element matches the respective schema above
4. No duplicate claim IDs, chunk IDs, etc.

### Why This Schema?

- **Completeness**: Single document contains entire analysis
- **Self-Contained**: No external references required for validation
- **Auditability**: Easy to check consistency of entire output
- **Archival**: Can be stored, versioned, and compared over time

---

## Schema Validation

### How to Validate

All SSE outputs should be validated against these schemas. Use a JSON schema validator:

```bash
# Example: Python
from jsonschema import validate

validate(instance=claims_output, schema=CLAIMS_SCHEMA)
```

### Common Validation Checks

```python
# Every claim has supporting quotes
assert all(len(c['supporting_quotes']) > 0 for c in claims)

# Every quote offset is valid
for claim in claims:
    for quote in claim['supporting_quotes']:
        assert 0 <= quote['start_char'] < quote['end_char'] <= len(source)
        assert source[quote['start_char']:quote['end_char']] == quote['text']

# Every contradiction references valid claims
claim_ids = {c['claim_id'] for c in claims}
for cont in contradictions:
    assert cont['pair']['claim_id_a'] in claim_ids
    assert cont['pair']['claim_id_b'] in claim_ids
```

---

## Summary Table

| Schema | Purpose | Key Invariant |
|--------|---------|---------------|
| Chunk | Text segmentation | Traceability |
| Claim | Extracted assertion | Quoting |
| Contradiction | Paired opposites | Contradiction Preservation |
| Cluster | Semantic grouping | Relationship Visibility |
| Metadata | Execution context | Computational Honesty |
| Index | Full output | Completeness |

All schemas work together to enforce the **seven invariants** defined in `SSE_INVARIANTS.md`.

---

## Design Principles

### Minimalism
Schemas include only what's necessary for core functionality and validation. No decorative fields.

### Traceability
Every significant claim includes source offsets for verification.

### Honesty
Metadata explicitly documents conditions and limitations.

### Auditability
All outputs are human-readable JSON, not binary or compressed formats.

### Determinism
Same input + same configuration = same output (no random fields, no timestamps in deterministic sections).

---

## JSON Pretty-Printing

All SSE JSON outputs are formatted with 2-space indentation for human readability:

```python
json.dump(data, f, indent=2, sort_keys=False)
```

This makes outputs easier to inspect, diff, and version control.

---

## Backward Compatibility

These schemas are stable. Future changes will:
1. **Add optional fields** (not break existing consumers)
2. **Never remove required fields**
3. **Be documented in CHANGELOG**
4. **Maintain version in metadata**

Consumers can rely on these schemas remaining backward compatible.
