#!/usr/bin/env python3
"""
Review Phase 2 Validator

Validates that a Phase 2 architecture review follows the evidence-grounding rules:
- Every claim cites evidence IDs
- Forbidden words only appear AFTER sufficient evidence is cited
- No hallucinated line numbers or file paths

Usage:
    python tools/validate_review.py review.md evidence.json
"""

import re
import sys
from pathlib import Path
import json


FORBIDDEN_WORDS = ["novel", "unique", "holy shit", "defensible"]
FORBIDDEN_PATTERN = re.compile(
    r'\b(' + '|'.join(re.escape(w) for w in FORBIDDEN_WORDS) + r')\b',
    re.IGNORECASE
)


def count_evidence_citations(review_text: str) -> int:
    """Count unique evidence IDs cited in the review."""
    # Match patterns like [E001], [E002, E003], etc.
    pattern = r'\[E\d+(?:,\s*E\d+)*\]'
    matches = re.findall(pattern, review_text)
    
    unique_ids = set()
    for match in matches:
        # Extract individual IDs from the match
        ids = re.findall(r'E\d+', match)
        unique_ids.update(ids)
    
    return len(unique_ids)


def find_forbidden_words_before_threshold(review_text: str, threshold: int = 5) -> list:
    """Find forbidden words that appear before threshold evidence is cited."""
    lines = review_text.split('\n')
    evidence_count = 0
    violations = []
    
    for i, line in enumerate(lines, start=1):
        # Count evidence citations in this line
        line_citations = re.findall(r'E\d+', line)
        evidence_count += len(set(line_citations))
        
        # Check for forbidden words
        if evidence_count < threshold:
            forbidden_matches = FORBIDDEN_PATTERN.findall(line)
            if forbidden_matches:
                violations.append({
                    'line': i,
                    'text': line.strip(),
                    'word': forbidden_matches[0],
                    'evidence_count': evidence_count
                })
    
    return violations


def check_speculation_labels(review_text: str) -> list:
    """Find claims that should be labeled SPECULATION but aren't."""
    # Look for claims without evidence citations
    lines = review_text.split('\n')
    missing_citations = []
    
    for i, line in enumerate(lines, start=1):
        line_stripped = line.strip()
        
        # Skip empty lines, headers, lists
        if not line_stripped or line_stripped.startswith('#') or line_stripped.startswith('-'):
            continue
        
        # Skip lines that are already labeled SPECULATION
        if line_stripped.startswith('SPECULATION:'):
            continue
        
        # If line makes a claim but has no evidence citation
        claim_indicators = ['implements', 'uses', 'calculates', 'prevents', 'enables', 'provides']
        has_claim = any(indicator in line_stripped.lower() for indicator in claim_indicators)
        has_citation = bool(re.search(r'\[E\d+\]', line_stripped))
        
        if has_claim and not has_citation:
            missing_citations.append({
                'line': i,
                'text': line_stripped[:100]  # Truncate for display
            })
    
    return missing_citations


def validate_review(review_path: Path, evidence_path: Path) -> dict:
    """Validate a Phase 2 review against the evidence pack."""
    
    # Load evidence to get valid IDs
    try:
        with open(evidence_path, 'r', encoding='utf-8') as f:
            evidence_data = json.load(f)
    except Exception as e:
        return {
            'valid': False,
            'error': f'Could not load evidence file: {e}'
        }
    
    valid_evidence_ids = set(item['id'] for item in evidence_data.get('evidence', []))
    
    # Load review
    try:
        with open(review_path, 'r', encoding='utf-8') as f:
            review_text = f.read()
    except Exception as e:
        return {
            'valid': False,
            'error': f'Could not load review file: {e}'
        }
    
    # Count evidence citations
    unique_citations = count_evidence_citations(review_text)
    
    # Check forbidden words
    forbidden_violations = find_forbidden_words_before_threshold(review_text, threshold=5)
    
    # Check for uncited claims
    missing_citations = check_speculation_labels(review_text)
    
    # Check for invalid evidence IDs
    cited_ids = set(re.findall(r'E\d+', review_text))
    invalid_ids = cited_ids - valid_evidence_ids
    
    return {
        'valid': len(forbidden_violations) == 0 and len(invalid_ids) == 0,
        'unique_citations': unique_citations,
        'forbidden_violations': forbidden_violations,
        'missing_citations': missing_citations[:10],  # Limit output
        'invalid_evidence_ids': list(invalid_ids),
        'total_cited_ids': len(cited_ids)
    }


def main():
    if len(sys.argv) < 3:
        print("Usage: python tools/validate_review.py <review.md> <evidence.json>")
        print("\nExample:")
        print("  python tools/validate_review.py artifacts/architecture_review.md artifacts/evidence_pack.json")
        sys.exit(1)
    
    review_path = Path(sys.argv[1])
    evidence_path = Path(sys.argv[2])
    
    if not review_path.exists():
        print(f"ERROR: Review file not found: {review_path}")
        sys.exit(1)
    
    if not evidence_path.exists():
        print(f"ERROR: Evidence file not found: {evidence_path}")
        sys.exit(1)
    
    print("="*80)
    print(" PHASE 2 REVIEW VALIDATION ".center(80, "="))
    print("="*80)
    print(f"\nReview file: {review_path}")
    print(f"Evidence pack: {evidence_path}")
    print()
    
    results = validate_review(review_path, evidence_path)
    
    if 'error' in results:
        print(f"ERROR: {results['error']}")
        sys.exit(1)
    
    print(f"Evidence citations: {results['unique_citations']} unique IDs cited")
    print(f"Total evidence references: {results['total_cited_ids']}")
    print()
    
    # Report forbidden word violations
    if results['forbidden_violations']:
        print("="*80)
        print(" FORBIDDEN WORD VIOLATIONS ".center(80, "="))
        print("="*80)
        print("\nForbidden words used before citing 5+ evidence items:")
        for v in results['forbidden_violations']:
            print(f"\n  Line {v['line']}: '{v['word']}' (only {v['evidence_count']} evidence cited)")
            print(f"    {v['text'][:70]}...")
        print()
    
    # Report invalid evidence IDs
    if results['invalid_evidence_ids']:
        print("="*80)
        print(" INVALID EVIDENCE IDs ".center(80, "="))
        print("="*80)
        print("\nCited evidence IDs that don't exist in the evidence pack:")
        for eid in sorted(results['invalid_evidence_ids']):
            print(f"  {eid}")
        print()
    
    # Report missing citations (sample)
    if results['missing_citations']:
        print("="*80)
        print(" POTENTIAL UNCITED CLAIMS (Sample) ".center(80, "="))
        print("="*80)
        print("\nClaims that may need evidence citations or SPECULATION label:")
        for m in results['missing_citations']:
            print(f"\n  Line {m['line']}:")
            print(f"    {m['text']}")
        print()
    
    # Final verdict
    if results['valid']:
        print("="*80)
        print("VERDICT: REVIEW VALID - Evidence-grounded requirements met")
        print("="*80)
        print(f"  ✓ No forbidden words before threshold")
        print(f"  ✓ All cited evidence IDs exist")
        print(f"  ✓ {results['unique_citations']} unique evidence items cited")
        print()
        sys.exit(0)
    else:
        print("="*80)
        print("VERDICT: REVIEW INVALID - Evidence-grounding rules violated")
        print("="*80)
        if results['forbidden_violations']:
            print(f"  ✗ {len(results['forbidden_violations'])} forbidden word violations")
        if results['invalid_evidence_ids']:
            print(f"  ✗ {len(results['invalid_evidence_ids'])} invalid evidence IDs cited")
        print()
        sys.exit(2)


if __name__ == "__main__":
    main()
