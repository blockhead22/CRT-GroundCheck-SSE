"""Test multi-document pipeline with fixtures"""
from sse.multi_doc import MultiDocSSE
from pathlib import Path

pipeline = MultiDocSSE()

# Add all fixtures
fixtures = [
    "fixtures/fixture1_license_must_may.txt",
    "fixtures/fixture2_medical_exceptions.txt",
    "fixtures/fixture3_numeric_contradictions.txt"
]

for f in fixtures:
    if Path(f).exists():
        doc_id = pipeline.add_document_from_file(f)
        print(f"Added: {Path(f).name} → {doc_id}")

print(f"\n=== PROCESSING {len(pipeline.registry)} DOCUMENTS ===")
pipeline.process_documents(max_chars=500, overlap=100)

index = pipeline.export_index()

print(f"\nStats:")
print(f"  Documents:      {index['stats']['document_count']}")
print(f"  Chunks:         {index['stats']['chunk_count']}")
print(f"  Claims:         {index['stats']['claim_count']}")
print(f"  Contradictions: {index['stats']['contradiction_count']}")
print(f"  Clusters:       {index['stats']['cluster_count']}")

# Validate offsets
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
            failures += 1
            print(f"FAIL: {claim['claim_id']} from {doc_id}")

if failures == 0:
    print(f"OK: All {index['stats']['claim_count']} claims reconstruct perfectly")
else:
    print(f"FAIL: {failures} reconstruction failures")

# Show cross-document provenance
print(f"\n=== CLAIMS PER DOCUMENT ===")
for doc in index['documents']:
    doc_id = doc['doc_id']
    claims = pipeline.get_claims_by_document(doc_id)
    contradictions = pipeline.get_contradictions_by_document(doc_id)
    print(f"{doc['filename']:40s} {len(claims):3d} claims, {len(contradictions):3d} contradictions")
