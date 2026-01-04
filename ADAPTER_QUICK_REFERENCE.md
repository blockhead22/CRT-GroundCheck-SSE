# Phase 4.2 Quick Reference Guide

**Last Updated**: Current Session

---

## Quick Start: Using Adapters

### 1. Build Evidence Packet

```python
from sse.evidence_packet import EvidencePacketBuilder

builder = EvidencePacketBuilder("your query", "v1.0")
builder.add_claim("id_001", "claim text", "source", start, end, True, "regex")
builder.set_metrics("id_001", support=5, accuracy=0.95, evidence=1, opposition=0)
builder.add_contradiction("id_001", "id_002", "contradicts", 0.85)
builder.add_cluster(["id_001", "id_002"])
builder.log_event("event_type", {"details": "info"})

packet = builder.build().to_dict()
```

### 2. Process with RAG Adapter

```python
from sse.adapters.rag_adapter import RAGAdapter

rag = RAGAdapter()
result = rag.process_query(
    query="your question",
    packet_dict=packet,
    use_mock_llm=False
)

if result["valid"]:
    print(result["llm_response"])
else:
    print(f"Error: {result['error']}")
```

### 3. Render with Search Adapter

```python
from sse.adapters.search_adapter import SearchAdapter

search = SearchAdapter()

# Get search results
results = search.render_search_results(packet)
for claim in results["results"]:
    print(f"{claim['claim_id']}: {claim['text']} (highlighted: {claim['highlighted']})")

# Get contradiction graph
graph = search.render_contradiction_graph(packet)
print(f"Graph: {graph['statistics']['total_nodes']} nodes, {graph['statistics']['total_edges']} edges")

# Get high-contradiction nodes
highlighted = search.highlight_high_contradiction_nodes(packet, threshold=2.0)
```

---

## Adapter Guarantees

| Guarantee | RAG | Search |
|-----------|-----|--------|
| All claims preserved | ✅ | ✅ |
| All contradictions preserved | ✅ | ✅ |
| Events logged | ✅ | ✅ |
| Output validated | ✅ | ✅ |
| Topology highlighting | N/A | ✅ |
| No suppression | ✅ | ✅ |

---

## Test Results

**Phase 4.2 Tests**: 17/17 passing ✅
- RAG adapter: 5/5 passing
- Search adapter: 5/5 passing
- Adversarial injection: 5/5 passing
- End-to-end pipeline: 2/2 passing

**Full Integration**: 195/195 passing ✅

---

## API Reference

### RAGAdapter

```python
class RAGAdapter:
    def process_query(query, packet_dict, use_mock_llm=False):
        """Returns {"valid": bool, "packet": dict, "llm_response": str, "error": str}"""
    
    def process_packet(packet_dict, use_mock_llm=False):
        """Returns (packet_dict, llm_response) or raises ValueError"""
```

### SearchAdapter

```python
class SearchAdapter:
    def render_search_results(packet_dict, highlight_contradictions=True):
        """Returns {"results": [...], "contradictions": [...], "clusters": [...], "statistics": {...}}"""
    
    def render_contradiction_graph(packet_dict):
        """Returns {"nodes": [...], "edges": [...], "statistics": {...}}"""
    
    def highlight_high_contradiction_nodes(packet_dict, threshold=2.0):
        """Returns {"high_contradiction_nodes": [...]}"""
```

---

## Validation Details

### What Gets Validated

1. **Field Types**: All fields are correct type (string, number, list, object)
2. **Required Fields**: All required fields present
3. **Forbidden Fields**: No credibility, confidence, accuracy_estimate
4. **Forbidden Words**: No high/low credibility, trust, confidence, reliable
5. **Schema Compliance**: JSON Schema Draft 7 validation

### Validation Error Example

```python
is_valid, errors = EvidencePacketValidator.validate_complete(packet)
# is_valid: False
# errors: ["Field 'credibility' not allowed in claims"]
```

---

## Topology Highlighting Explained

```
Topology Score = contradiction_count + cluster_membership_count

Examples:
- Claim A: 2 contradictions + 1 cluster = score 3.0 → HIGHLIGHTED
- Claim B: 0 contradictions + 0 clusters = score 0.0 → NOT highlighted
- Claim C: 1 contradiction + 2 clusters = score 3.0 → HIGHLIGHTED
```

**Key**: Uses structure, never uses truth/credibility/confidence.

---

## Common Patterns

### Pattern 1: Build and Process

```python
packet = EvidencePacketBuilder("q").add_claim(...).build().to_dict()
rag = RAGAdapter()
result = rag.process_query("q", packet)
```

### Pattern 2: Process and Render

```python
result = rag.process_query("q", packet)
search = SearchAdapter()
ui_results = search.render_search_results(result["packet"])
```

### Pattern 3: Full Pipeline

```python
# Build
packet = builder.build().to_dict()

# Process
rag = RAGAdapter()
result = rag.process_query("q", packet)

# Render
search = SearchAdapter()
ui = search.render_search_results(result["packet"])

# Validate
is_valid, _ = EvidencePacketValidator.validate_complete(result["packet"])
```

---

## Testing Your Code

### Run Adapter Tests Only

```bash
pytest tests/test_phase_4_2_adapters.py -v
```

### Run Full Suite

```bash
pytest tests/ -v
```

### Run Specific Test

```bash
pytest tests/test_phase_4_2_adapters.py::TestRAGAdapterPipeline::test_rag_adapter_preserves_all_claims -v
```

---

## Common Issues & Solutions

### Issue 1: Invalid Packet Error

**Symptom**: `ValueError: Input packet invalid`

**Cause**: Packet doesn't validate (missing field, wrong type)

**Solution**:
```python
is_valid, errors = EvidencePacketValidator.validate_complete(packet)
print(errors)  # See what's wrong
```

### Issue 2: Forbidden Field Injected

**Symptom**: `ValueError: Adapter produced invalid packet: Additional properties...`

**Cause**: Adapter added forbidden field (credibility, confidence, etc.)

**Solution**: This is a bug in adapter code. Report and fix the adapter.

### Issue 3: LLM Response Invalid

**Symptom**: `ValueError: Adapter produced invalid packet`

**Cause**: LLM changed packet structure

**Solution**: This is the validation gate working. LLM response was invalid, so it was rejected. No data corruption occurred.

---

## Architecture Decisions

### Why Validation Gate?

To prevent adapters from corrupting data undetected.

```python
# Hard gate: cannot return invalid packet
is_valid, _ = validate(packet)
if not is_valid:
    raise ValueError(...)  # Will not return
```

### Why Explicit Contradictions in Prompt?

To ensure LLM sees contradiction landscape, not just claims.

```python
CONTRADICTIONS:
  - [claim_001] contradicts [claim_002] (0.85)
  - [claim_003] qualifies [claim_001] (0.70)
```

### Why Topology Highlighting?

To make highlighting objective and reproducible, never judgmental.

```python
# topology_score = contradictions + clusters
# NOT credibility, confidence, accuracy
```

---

## File Locations

| File | Purpose | Lines |
|------|---------|-------|
| `sse/adapters/__init__.py` | Module exports | 16 |
| `sse/adapters/rag_adapter.py` | RAG implementation | 400+ |
| `sse/adapters/search_adapter.py` | Search implementation | 350+ |
| `tests/test_phase_4_2_adapters.py` | Test suite | 500+, 17 tests |

---

## Success Metrics

| Metric | Target | Actual |
|--------|--------|--------|
| RAG tests passing | 5 | 5 ✅ |
| Search tests passing | 5 | 5 ✅ |
| Adversarial tests passing | 5 | 5 ✅ |
| End-to-end tests passing | 2 | 2 ✅ |
| Integration tests passing | 195 | 195 ✅ |
| No regressions | 0 failures | 0 failures ✅ |

---

## Next: Chat Adapter Gating

Chat adapter is **NOT YET IMPLEMENTED** because:

1. ✅ RAG adapter proven (5/5 tests)
2. ✅ Search adapter proven (5/5 tests)
3. ⏳ Waiting: 2+ weeks of stable production use
4. ⏳ Waiting: User feedback on RAG+Search UX
5. ⏳ Waiting: Chat role definition and constraints

When these are satisfied, Chat adapter will be implemented.

---

## Version Info

- **EvidencePacket Schema**: v1.0 (locked)
- **Phase 4.2**: Complete
- **Adapter Test Suite**: 17 tests, all passing
- **Integration Suite**: 195 tests, all passing
