#!/usr/bin/env python3
"""
Evidence Verification Tool

Validates that evidence excerpts claimed by an AI reviewer actually exist
in the codebase at the specified locations, and checks for forbidden ungrounded
claims in metadata fields.

Usage:
    python tools/verify_evidence.py evidence.json

Evidence format:
    {
      "evidence": [
        {
          "id": "E001",
          "file": "personal_agent/crt_memory.py",
          "start_line": 43,
          "end_line": 46,
          "excerpt": "actual code...",
          "mechanism": "trust_confidence_schema"
        }
      ]
    }

Forbidden words check: Metadata fields (like "purpose") are scanned for words
that signal ungrounded claims: "novel", "unique", "defensible", "holy shit".
"""

import json
import re
import sys
from pathlib import Path
from typing import Dict, List, Tuple


FORBIDDEN_WORDS = ["novel", "unique", "holy shit", "defensible"]
FORBIDDEN_PATTERN = re.compile(
    r'\b(' + '|'.join(re.escape(w) for w in FORBIDDEN_WORDS) + r')\b',
    re.IGNORECASE
)



def verify_excerpt(
    base_path: Path,
    file_path: str,
    start_line: int,
    end_line: int,
    claimed_excerpt: str,
) -> Tuple[bool, str]:
    """
    Verify that the claimed excerpt matches the actual file contents.
    
    Returns:
        (is_valid, error_message)
    """
    full_path = base_path / file_path
    
    # Check file exists
    if not full_path.exists():
        return False, f"File not found: {file_path}"
    
    # Read file
    try:
        with open(full_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
    except Exception as e:
        return False, f"Could not read file: {e}"
    
    # Validate line numbers
    if start_line < 1 or start_line > len(lines):
        return False, f"start_line {start_line} out of range (file has {len(lines)} lines)"
    
    if end_line < start_line or end_line > len(lines):
        return False, f"end_line {end_line} out of range or before start_line"
    
    # Extract actual excerpt (lines are 1-indexed in the spec)
    actual_excerpt = ''.join(lines[start_line - 1:end_line])
    
    # Normalize for comparison (handle trailing whitespace variations)
    claimed_normalized = claimed_excerpt.strip()
    actual_normalized = actual_excerpt.strip()
    
    if claimed_normalized != actual_normalized:
        return False, f"Excerpt mismatch:\n  CLAIMED:\n{claimed_excerpt}\n  ACTUAL:\n{actual_excerpt}"
    
    return True, "OK"


def verify_evidence_pack(evidence_path: Path, base_path: Path = None) -> Dict:
    """
    Verify all evidence items in the JSON pack.
    
    Strict requirements:
    - Minimum 12 evidence items
    - Must include required mechanisms:
      * trust_confidence_schema
      * retrieval_scoring
      * gate_thresholds
      * contradiction_ledger or contradiction handling
      * stress_test_metrics
      * At least one failure/error evidence from logs
    
    Returns:
        {
            "total": int,
            "valid": int,
            "invalid": int,
            "errors": [{"id": str, "error": str}],
            "manifest": [str],
            "required_mechanisms": {mechanism: bool}
        }
    """
    if base_path is None:
        base_path = Path.cwd()
    
    # Load evidence JSON
    try:
        with open(evidence_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except Exception as e:
        return {
            "total": 0,
            "valid": 0,
            "invalid": 1,
            "errors": [{"id": "JSON_LOAD", "error": f"Could not load evidence file: {e}"}]
        }
    
    evidence_items = data.get("evidence", [])
    
    results = {
        "total": len(evidence_items),
        "valid": 0,
        "invalid": 0,
        "errors": [],
        "manifest": [],
        "forbidden_words_found": [],
        "required_mechanisms": {
            "trust_confidence_schema": False,
            "retrieval_scoring": False,
            "gate_thresholds": False,
            "contradiction_handling": False,
            "stress_test_metrics": False,
            "failure_evidence": False,
        }
    }
    
    for item in evidence_items:
        item_id = item.get("id", "UNKNOWN")
        file_path = item.get("file", "")
        start_line = item.get("start_line", 0)
        end_line = item.get("end_line", 0)
        excerpt = item.get("excerpt", "")
        mechanism = item.get("mechanism", "").lower()
        purpose = item.get("purpose", "")
        
        # Check for forbidden words in metadata
        forbidden_in_purpose = FORBIDDEN_PATTERN.findall(purpose)
        forbidden_in_mechanism = FORBIDDEN_PATTERN.findall(mechanism)
        
        if forbidden_in_purpose or forbidden_in_mechanism:
            for word in forbidden_in_purpose:
                results["forbidden_words_found"].append({
                    "id": item_id,
                    "field": "purpose",
                    "word": word,
                    "text": purpose[:100]
                })
            for word in forbidden_in_mechanism:
                results["forbidden_words_found"].append({
                    "id": item_id,
                    "field": "mechanism",
                    "word": word,
                    "text": mechanism[:100]
                })
        
        is_valid, error = verify_excerpt(base_path, file_path, start_line, end_line, excerpt)
        
        if is_valid:
            results["valid"] += 1
            manifest_line = f"{item_id:6} OK: {file_path}:{start_line}-{end_line} ({mechanism})"
            results["manifest"].append(manifest_line)
            
            # Track required mechanisms
            if "trust" in mechanism and "confidence" in mechanism:
                results["required_mechanisms"]["trust_confidence_schema"] = True
            if "retrieval" in mechanism and "scor" in mechanism:
                results["required_mechanisms"]["retrieval_scoring"] = True
            if "gate" in mechanism and "threshold" in mechanism:
                results["required_mechanisms"]["gate_thresholds"] = True
            if "contradiction" in mechanism:
                results["required_mechanisms"]["contradiction_handling"] = True
            if "stress" in mechanism or "metric" in mechanism:
                results["required_mechanisms"]["stress_test_metrics"] = True
            if "fail" in mechanism or "error" in mechanism:
                results["required_mechanisms"]["failure_evidence"] = True
        else:
            results["invalid"] += 1
            results["errors"].append({
                "id": item_id,
                "file": file_path,
                "lines": f"{start_line}-{end_line}",
                "error": error
            })
    
    return results


def main():
    if len(sys.argv) < 2:
        print("Usage: python tools/verify_evidence.py <evidence.json>")
        print("\nExample:")
        print("  python tools/verify_evidence.py artifacts/evidence_pack.json")
        sys.exit(1)
    
    evidence_path = Path(sys.argv[1])
    
    if not evidence_path.exists():
        print(f"ERROR: Evidence file not found: {evidence_path}")
        sys.exit(1)
    
    print("="*80)
    print(" EVIDENCE VERIFICATION ".center(80, "="))
    print("="*80)
    print(f"\nEvidence file: {evidence_path}")
    print(f"Base path: {Path.cwd()}")
    print()
    
    results = verify_evidence_pack(evidence_path)
    
    print(f"Total evidence items: {results['total']}")
    print(f"Valid: {results['valid']}")
    print(f"Invalid: {results['invalid']}")
    print()
    
    # Check for forbidden words
    if results.get('forbidden_words_found'):
        print("="*80)
        print(" FORBIDDEN WORDS IN METADATA ".center(80, "="))
        print("="*80)
        print("\nUngrounded claims detected in evidence metadata:")
        for violation in results['forbidden_words_found']:
            print(f"\n  {violation['id']} - '{violation['word']}' in {violation['field']}:")
            print(f"    {violation['text'][:70]}...")
        print("\nThese words signal ungrounded claims and must be removed.")
        print("Evidence should be descriptive, not evaluative.")
        print()
    
    # Check minimum evidence count
    if results['valid'] < 12:
        print("="*80)
        print(f"ERROR: Insufficient evidence ({results['valid']}/12 minimum)")
        print("="*80)
        print("\nEvidence pack must contain at least 12 valid, verified excerpts.")
        print("Current valid count does not meet the minimum requirement.")
        print()
    
    # Check required mechanisms
    missing_mechanisms = [k for k, v in results['required_mechanisms'].items() if not v]
    if missing_mechanisms:
        print("="*80)
        print(" MISSING REQUIRED MECHANISMS ".center(80, "="))
        print("="*80)
        for mech in missing_mechanisms:
            print(f"  ✗ {mech}")
        print()
    
    # Print manifest
    if results['manifest']:
        print("="*80)
        print(" EVIDENCE MANIFEST (Audit Receipt) ".center(80, "="))
        print("="*80)
        for line in results['manifest']:
            print(line)
        print()
    
    # Determine overall verdict
    has_errors = results['invalid'] > 0
    insufficient_count = results['valid'] < 12
    missing_required = len([k for k, v in results['required_mechanisms'].items() if not v]) > 0
    has_forbidden_words = len(results.get('forbidden_words_found', [])) > 0
    
    if has_errors:
        print("="*80)
        print(" VALIDATION ERRORS ".center(80, "="))
        print("="*80)
        
        for error in results['errors']:
            print(f"\n[{error['id']}] {error['file']}:{error['lines']}")
            print(f"  {error['error']}")
        print()
    
    if has_errors or insufficient_count or missing_required or has_forbidden_words:
        print("="*80)
        print("VERDICT: EVIDENCE PACK INVALID - Review cannot be trusted")
        print("="*80)
        if has_errors:
            print(f"  ✗ {results['invalid']} excerpts failed verification")
        if insufficient_count:
            print(f"  ✗ Insufficient evidence count ({results['valid']}/12 minimum)")
        if missing_required:
            print(f"  ✗ Missing {len([k for k, v in results['required_mechanisms'].items() if not v])} required mechanisms")
        if has_forbidden_words:
            print(f"  ✗ {len(results['forbidden_words_found'])} forbidden words in metadata (ungrounded claims)")
        print()
        sys.exit(2)
    else:
        print("="*80)
        print("VERDICT: EVIDENCE PACK VALID - All requirements met")
        print("="*80)
        print(f"  ✓ {results['valid']} excerpts verified")
        print(f"  ✓ All required mechanisms present")
        print(f"  ✓ Minimum evidence count met (12+)")
        print()
        print("Review may proceed to Phase 2.")
        print("="*80)
        sys.exit(0)


if __name__ == "__main__":
    main()
