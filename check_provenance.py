"""
Diagnostic: Check provenance reconstruction across all claims.
"""

from sse.interaction_layer import SSENavigator

nav = SSENavigator('output_index/index.json')
claims = nav.get_all_claims()

print('PROVENANCE VALIDATION CHECK')
print('='*70)

failed_count = 0
passed_count = 0

for claim in claims:
    claim_id = claim['claim_id']
    prov = nav.get_provenance(claim_id)
    
    for quote in prov['supporting_quotes']:
        if quote['valid']:
            passed_count += 1
            status = '✓'
        else:
            failed_count += 1
            status = '✗'
        
        claim_text = prov['claim_text'][:50] + '...'
        print(f"\n{status} {claim_id}: {claim_text}")
        print(f"  Quote: \"{quote['quote_text'][:60]}...\"")
        print(f"  Offsets: [{quote['start_char']}:{quote['end_char']}]")
        print(f"  Match: {quote['valid']}")

print('\n' + '='*70)
print(f"SUMMARY: {passed_count} passed, {failed_count} failed")
print(f"Pass rate: {100 * passed_count / (passed_count + failed_count):.1f}%")

if failed_count > 0:
    print("\n⚠️  RECONSTRUCTION MISMATCH DETECTED")
    print("This likely indicates an offset calculation bug in the chunker.")
    print("Need to investigate byte position handling.")
