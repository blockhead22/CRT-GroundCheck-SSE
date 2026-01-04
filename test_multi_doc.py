"""Test multi-document SSE pipeline"""
from sse.multi_doc import MultiDocSSE
import json

# Create pipeline
pipeline = MultiDocSSE()

# Add multiple documents
doc1_id = pipeline.add_document(
    "The Earth is round. This is scientifically proven.",
    filename="earth_science.txt"
)

doc2_id = pipeline.add_document(
    "The Earth is flat. Many people believe this.",
    filename="flat_earth.txt"
)

doc3_id = pipeline.add_document(
    "Exercise is beneficial. Regular activity improves health.",
    filename="health.txt"
)

print(f"Registered documents:")
for doc in pipeline.registry.list_documents():
    print(f"  {doc['doc_id']}: {doc['filename']} ({doc['char_count']} chars)")

# Process all documents
print(f"\nProcessing {len(pipeline.registry)} documents...")
pipeline.process_documents(max_chars=200, overlap=50)

# Export index
index = pipeline.export_index()

print(f"\n=== RESULTS ===")
print(f"Chunks: {index['stats']['chunk_count']}")
print(f"Claims: {index['stats']['claim_count']}")
print(f"Contradictions: {index['stats']['contradiction_count']}")
print(f"Clusters: {index['stats']['cluster_count']}")

print(f"\n=== CLAIMS BY DOCUMENT ===")
for doc in index['documents']:
    doc_id = doc['doc_id']
    claims = pipeline.get_claims_by_document(doc_id)
    print(f"\n{doc['filename']} ({doc_id}):")
    for claim in claims:
        print(f"  - {claim['claim_id']}: {claim['claim_text']}")

print(f"\n=== CONTRADICTIONS ===")
for i, cont in enumerate(index['contradictions'][:5]):  # Show first 5
    pair = cont['pair']
    claim_a = next(c for c in pipeline.claims if c['claim_id'] == pair['claim_id_a'])
    claim_b = next(c for c in pipeline.claims if c['claim_id'] == pair['claim_id_b'])
    
    print(f"\nContradiction {i}:")
    print(f"  [{claim_a['claim_id']}] {claim_a['claim_text']} (from {claim_a['doc_id']})")
    print(f"  [{claim_b['claim_id']}] {claim_b['claim_text']} (from {claim_b['doc_id']})")

# Validate offset reconstruction across all documents
print(f"\n=== OFFSET VALIDATION ===")
failures = 0
for claim in pipeline.claims:
    doc_id = claim['doc_id']
    doc_text = pipeline.registry.get_text(doc_id)
    
    for quote in claim['supporting_quotes']:
        start = quote['start_char']
        end = quote['end_char']
        reconstructed = doc_text[start:end]
        quote_text = quote.get('quote_text') or quote.get('text')
        
        if reconstructed != quote_text:
            print(f"FAIL: {claim['claim_id']} offset mismatch")
            failures += 1

if failures == 0:
    print(f"OK: All {len(pipeline.claims)} claims reconstruct correctly across {len(pipeline.registry)} documents")
else:
    print(f"FAIL: {failures} offset reconstruction failures")
