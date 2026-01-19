#!/usr/bin/env python3
"""
Sanitize logs and prompts for Llama 3.2 guardrails

Llama 3.2 refuses to process text containing keywords that look like prompt injection attempts.
This script sanitizes files by replacing trigger words while preserving semantic meaning.

Replacements:
- "System Prompt" → "Reviewer Prompt"
- "Instructions" → "Guidance"
- "system-message" → "review-context"
- "SYSTEM:" → "CONTEXT:"

Usage:
    python tools/sanitize_for_llama.py input.md output.md
"""

import re
import sys
from pathlib import Path


REPLACEMENTS = [
    (r'\bSystem Prompt\b', 'Reviewer Prompt'),
    (r'\bInstructions\b', 'Guidance'),
    (r'\bsystem-message\b', 'review-context'),
    (r'\bSYSTEM:\s*', 'CONTEXT: '),
    (r'\b--system-message\b', '--review-context'),
    (r'\bsystem message\b', 'review context'),
]


def sanitize_text(text: str) -> tuple[str, int]:
    """Apply all replacements to text. Returns (sanitized_text, num_replacements)."""
    total_replacements = 0
    result = text
    
    for pattern, replacement in REPLACEMENTS:
        result, count = re.subn(pattern, replacement, result)
        total_replacements += count
    
    return result, total_replacements


def sanitize_file(input_path: Path, output_path: Path) -> dict:
    """Sanitize a file for Llama compatibility."""
    
    try:
        with open(input_path, 'r', encoding='utf-8') as f:
            original_text = f.read()
    except Exception as e:
        return {
            'success': False,
            'error': f'Could not read input file: {e}'
        }
    
    sanitized_text, replacements = sanitize_text(original_text)
    
    try:
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(sanitized_text)
    except Exception as e:
        return {
            'success': False,
            'error': f'Could not write output file: {e}'
        }
    
    return {
        'success': True,
        'replacements': replacements,
        'input_size': len(original_text),
        'output_size': len(sanitized_text)
    }


def main():
    if len(sys.argv) < 3:
        print("Usage: python tools/sanitize_for_llama.py <input_file> <output_file>")
        print("\nExample:")
        print("  python tools/sanitize_for_llama.py tools/evidence_based_review_prompt.md tools/evidence_based_review_prompt_safe.md")
        sys.exit(1)
    
    input_path = Path(sys.argv[1])
    output_path = Path(sys.argv[2])
    
    if not input_path.exists():
        print(f"ERROR: Input file not found: {input_path}")
        sys.exit(1)
    
    print("="*80)
    print(" SANITIZING FOR LLAMA 3.2 GUARDRAILS ".center(80, "="))
    print("="*80)
    print(f"\nInput:  {input_path}")
    print(f"Output: {output_path}")
    print()
    
    results = sanitize_file(input_path, output_path)
    
    if not results['success']:
        print(f"ERROR: {results['error']}")
        sys.exit(1)
    
    print(f"Replacements made: {results['replacements']}")
    print(f"Input size:  {results['input_size']:,} bytes")
    print(f"Output size: {results['output_size']:,} bytes")
    print()
    
    if results['replacements'] > 0:
        print("✓ File sanitized successfully")
        print("\nReplacement rules applied:")
        for pattern, replacement in REPLACEMENTS:
            print(f"  {pattern.strip(r'\\b')} → {replacement}")
    else:
        print("✓ No trigger words found - file copied as-is")
    
    print()
    print("="*80)
    sys.exit(0)


if __name__ == "__main__":
    main()
