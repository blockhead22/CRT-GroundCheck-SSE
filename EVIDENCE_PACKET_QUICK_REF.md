# EvidencePacket v1.0 - Quick Reference

## Creating a Packet (Builder Pattern)

```python
from sse.evidence_packet import EvidencePacketBuilder

# Create builder
builder = EvidencePacketBuilder(
    query="your search query",
    indexed_version="v1.0"
)

# Add claims with complete metadata
builder.add_claim(
    claim_id="claim_abcd1234",
    claim_text="The claim text as extracted",
    source_document_id="doc_123",
    offset_start=0,
    offset_end=45,
    extraction_verified=True,
    extraction_method="chunker"
)

# Set metrics for the claim
builder.set_metrics(
    claim_id="claim_abcd1234",
    source_count=2,           # how many docs mention it
    retrieval_score=0.85,     # relevance [0.0-1.0]
    contradiction_count=1,    # how many contradictions
    cluster_membership_count=1  # how many clusters
)

# Add contradictions
builder.add_contradiction(
    claim_a_id="claim_abcd1234",
    claim_b_id="claim_xyz9876",
    relationship_type="contradicts",  # or "qualifies", "extends"
    topology_strength=0.92  # [0.0-1.0]
)

# Add contradiction clusters
builder.add_cluster(["claim_abcd1234", "claim_xyz9876"])

# Log events
builder.log_event(
    event_type="query_executed",  # or contradiction_found, etc
    details={"status": "success"}
)

# Build packet (validates automatically)
packet = builder.build()

# Serialize
json_str = packet.to_json()
```

## Validating a Packet

```python
from sse.evidence_packet import EvidencePacketValidator
import json

data = json.load(open("packet.json"))

# Schema validation only
try:
    EvidencePacketValidator.validate_schema(data)
except ValueError as e:
    print(f"Schema error: {e}")

# Complete validation (schema + semantics)
is_valid, errors = EvidencePacketValidator.validate_complete(data)
if not is_valid:
    for error in errors:
        print(f"Error: {error}")

# Or construct object (validates on init)
from sse.evidence_packet import EvidencePacket
try:
    packet = EvidencePacket.from_dict(data)
except ValueError as e:
    print(f"Validation error: {e}")
```

## What's Forbidden

### Forbidden Field Names
```python
"confidence", "credibility", "truth_score", "importance_weight",
"coherence_score", "synthesis_ready", "interpretation"
```

### Forbidden Words in Events
```python
"confidence", "credibility", "reliability", "truth_likelihood",
"importance", "quality", "consensus", "agreement", "resolved",
"settled", "preferred", "better", "worse", "synthesize",
"reconcile", "harmonize"
```

### Examples That Will FAIL
```python
# ❌ FAIL: Adding confidence field to claim
claim_text = "some claim",
confidence = 0.95  # Schema rejects unknown field

# ❌ FAIL: Adding credibility to support_metrics
support_metrics = {
    "source_count": 1,
    "credibility": 0.85  # Schema rejects unknown field
}

# ❌ FAIL: Forbidden word in event
log_event("query_executed", {
    "status": "high confidence in results"  # Word "confidence" detected
})

# ❌ FAIL: Invalid relationship type
contradiction = {
    "relationship_type": "probably_contradicts"  # Not in enum
}

# ❌ FAIL: Out-of-range score
support_metrics = {
    "retrieval_score": 1.5  # Must be [0.0-1.0]
}
```

### Examples That PASS
```python
# ✅ PASS: Only allowed fields
claim = {
    "claim_id": "claim_abcd1234",
    "claim_text": "extracted text",
    "source_document_id": "doc_1",
    "extraction_offset": {"start": 0, "end": 45},
    "extraction_verified": True
}

# ✅ PASS: Describe contradictions factually
log_event("contradiction_found", {
    "claim_a": "claim_1",
    "claim_b": "claim_2",
    "topology_strength": 0.92,
    "relationship_type": "contradicts"
})

# ✅ PASS: Valid enum value
contradiction = {
    "relationship_type": "contradicts"  # or "qualifies", "extends"
}

# ✅ PASS: In-range metrics
support_metrics = {
    "source_count": 3,
    "retrieval_score": 0.85,
    "contradiction_count": 2,
    "cluster_membership_count": 1
}
```

## Packet Contract

### Required for Every Claim
1. claim_id (unique, format: claim_XXXXXXXX)
2. claim_text (exact text as extracted)
3. source_document_id
4. extraction_offset (start, end)
5. extraction_verified (boolean)
6. support_metrics entry
7. provenance entry

### Required for Every Contradiction
1. claim_a_id (must reference valid claim)
2. claim_b_id (must reference valid claim)
3. relationship_type (enum: contradicts|qualifies|extends)
4. topology_strength (numeric [0.0-1.0])
5. detected_timestamp (ISO8601)

### Required for Every Event
1. event_type (enum: 6 allowed types)
2. timestamp (ISO8601)
3. details (object, no forbidden words)

### No Field Names Can Be Added
```python
# WRONG: Adding new field
claim = {
    "claim_id": "...",
    "claim_text": "...",
    "confidence": 0.95  # Schema rejects this
}

# RIGHT: Only use schema-defined fields
claim = {
    "claim_id": "...",
    "claim_text": "...",
    "source_document_id": "...",
    "extraction_offset": {...},
    "extraction_verified": True
}
```

## Design Principle

**All claims included. All contradictions included. No filtering. No suppression. No interpretation.**

The schema prevents corruption architecturally:
- Unknown fields rejected by schema
- Forbidden fields rejected by schema
- Out-of-range values rejected by schema
- Invalid enum values rejected by schema
- Forbidden words detected at validation time

This is not a recommendation or policy—it's enforced by the data structure itself.

## Event Types (6 Allowed)

```
query_executed           - Query was processed
contradiction_found      - New contradiction detected
topology_changed         - Contradiction graph structure changed
boundary_violation       - Observer tried forbidden operation
adaptation_event         - Adapter processed packet
contradiction_suppressed - Contradiction excluded (audit trail)
```

## Relationship Types (3 Allowed)

```
contradicts  - Claims directly oppose each other
qualifies    - One claim modifies/qualifies the other
extends      - One claim builds on/extends the other
```

## Files Reference

| File | Purpose |
|------|---------|
| `sse/evidence_packet.py` | Python implementation (validator, builder, classes) |
| `evidence_packet.v1.schema.json` | JSON Schema defining packet structure |
| `tests/test_evidence_packet.py` | 22 tests covering all validation |

## Testing Your Adapter

```python
from sse.evidence_packet import EvidencePacketValidator

# After your adapter produces output
is_valid, errors = EvidencePacketValidator.validate_complete(
    adapter_output
)

if not is_valid:
    raise ValueError(
        f"Adapter produced invalid packet:\n" +
        "\n".join(errors)
    )

# Continue only if valid
return adapter_output
```

## Summary

- **All claims preserved**: No filtering, no cherry-picking
- **All contradictions preserved**: No hiding disagreement
- **No interpretation fields**: Schema rejects them automatically
- **Metrics are counts**: Evidence density, not credibility
- **Events are audit trail**: What happened, not why it's true
- **Validation is architectural**: Not just code policy
