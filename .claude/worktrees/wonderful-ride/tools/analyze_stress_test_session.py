#!/usr/bin/env python3
"""
CRT Stress Test Learning Analyzer
Automatically extracts patterns from stress test runs

Usage:
    python tools/analyze_stress_test_session.py artifacts/crt_stress_run.20260125_212908.jsonl
"""

import argparse
import json
from pathlib import Path
from datetime import datetime
from collections import defaultdict

def analyze_stress_test(jsonl_path: Path):
    """Analyze a stress test run and extract learning patterns."""
    
    patterns = defaultdict(list)
    
    with open(jsonl_path, 'r') as f:
        events = [json.loads(line) for line in f]
    
    # Analyze contradictions
    contradictions = [e for e in events if e.get('event_type') == 'contradiction_detected']
    if contradictions:
        patterns['contradiction_handling'].append({
            'count': len(contradictions),
            'types': list(set([c.get('conflict_type', 'unknown') for c in contradictions])),
            'context': f"Detected {len(contradictions)} contradictions across test run"
        })
    
    # Analyze failures
    failures = [e for e in events if e.get('gates_passed') == False]
    if failures:
        failure_reasons = defaultdict(int)
        for f in failures:
            reason = f.get('validation', {}).get('description', 'unknown')
            failure_reasons[reason] += 1
        
        patterns['error_resolution'].append({
            'failures': dict(failure_reasons),
            'context': f"Gate failures occurred in {len(failures)} turns"
        })
    
    # Analyze trust score patterns
    trust_scores = [e.get('trust_score') for e in events if e.get('trust_score')]
    if trust_scores:
        avg_trust = sum(trust_scores) / len(trust_scores)
        trust_variance = sum((t - avg_trust)**2 for t in trust_scores) / len(trust_scores)
        
        patterns['trust_score_tuning'].append({
            'avg': round(avg_trust, 3),
            'variance': round(trust_variance, 3),
            'context': f"Trust scores show {'high' if trust_variance > 0.1 else 'low'} variance"
        })
    
    # Analyze eval check failures
    eval_failures = [e for e in events if e.get('eval_failures')]
    if eval_failures:
        unique_failures = set()
        for e in eval_failures:
            for fail in e.get('eval_failures', []):
                unique_failures.add(fail.get('check_name', 'unknown'))
        
        patterns['groundcheck_verification'].append({
            'failed_checks': list(unique_failures),
            'context': f"Evaluation failures in checks: {', '.join(unique_failures)}"
        })
    
    return patterns


def save_learning_session(patterns: dict, source_file: str):
    """Save extracted patterns as a learning session."""
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    learned_path = Path.home() / ".claude" / "skills" / "learned"
    learned_path.mkdir(parents=True, exist_ok=True)
    
    session_file = learned_path / f"stress_test_{timestamp}.json"
    
    # Convert to session format
    patterns_list = []
    for pattern_type, details in patterns.items():
        for detail in details:
            patterns_list.append({
                'type': pattern_type,
                'confidence': 'high',
                'context': detail.get('context', ''),
                'metadata': {k: v for k, v in detail.items() if k != 'context'}
            })
    
    session_data = {
        'timestamp': timestamp,
        'source': 'stress_test',
        'source_file': str(source_file),
        'patterns_detected': patterns_list,
        'status': 'pending_review'
    }
    
    with open(session_file, 'w') as f:
        json.dump(session_data, f, indent=2)
    
    print(f"✓ Learning session saved: {session_file}")
    print(f"✓ Detected {len(patterns_list)} patterns from stress test")
    
    return session_file


def main():
    parser = argparse.ArgumentParser(description="Analyze CRT stress test for learning patterns")
    parser.add_argument("jsonl_file", type=Path, help="Path to stress test JSONL file")
    
    args = parser.parse_args()
    
    if not args.jsonl_file.exists():
        print(f"Error: File not found: {args.jsonl_file}")
        return 1
    
    print(f"Analyzing stress test: {args.jsonl_file}")
    patterns = analyze_stress_test(args.jsonl_file)
    
    if not patterns:
        print("No patterns detected in this stress test run")
        return 0
    
    print("\nDetected patterns:")
    for pattern_type, details in patterns.items():
        print(f"  • {pattern_type}: {len(details)} occurrence(s)")
    
    session_file = save_learning_session(patterns, args.jsonl_file)
    print(f"\nReview with: .\\tools\\review_learned_skills.ps1")
    
    return 0


if __name__ == "__main__":
    exit(main())
