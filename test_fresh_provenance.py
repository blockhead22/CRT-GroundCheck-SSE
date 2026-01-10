"""Test provenance on fresh index."""

from pathlib import Path

import pytest

from sse.interaction_layer import SSENavigator

index_path = Path('output_index_fresh/index.json')
if not index_path.exists():
    pytest.skip(f"Missing required artifact: {index_path}", allow_module_level=True)

nav = SSENavigator(str(index_path))

# Check all claims
claims = nav.get_all_claims()
passed = 0
failed = 0

print('PROVENANCE VALIDATION (Fresh Index)')
print('='*70)

for claim in claims[:5]:
    claim_id = claim['claim_id']
    prov = nav.get_provenance(claim_id)
    
    for quote in prov['supporting_quotes']:
        if quote['valid']:
            passed += 1
            status = '✓'
        else:
            failed += 1
            status = '✗'
        
        print(f"{status} {claim_id}: [{quote['start_char']}:{quote['end_char']}]")
        if not quote['valid']:
            print(f"  Stored: {quote['quote_text'][:50]}...")
            print(f"  Actual: {quote['reconstructed_text'][:50] if quote['reconstructed_text'] else 'None'}...")

print()
print(f"Summary: {passed} passed, {failed} failed")
