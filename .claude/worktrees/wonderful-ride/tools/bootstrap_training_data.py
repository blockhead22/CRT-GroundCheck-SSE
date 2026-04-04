"""
Bootstrap Training Data from Existing Stress Tests

Extracts training examples from stress test JSONL files to bootstrap
active learning before we have user corrections.

What we learn from:
1. Gate failures vs passes - weak labels for response type
2. Question patterns - instruction vs question classification
3. Confidence scores - quality signals
4. Contradiction patterns - which queries trigger contradictions

Usage:
    python tools/bootstrap_training_data.py --output training_data/bootstrap_v1.jsonl
"""

import json
import re
from pathlib import Path
from typing import List, Dict, Any, Tuple
from collections import Counter, defaultdict


def load_stress_test_runs(artifacts_dir: Path) -> List[Dict[str, Any]]:
    """Load all JSONL stress test runs."""
    runs = []
    for jsonl_file in artifacts_dir.glob("crt_stress_run.*.jsonl"):
        try:
            with open(jsonl_file, 'r', encoding='utf-8') as f:
                for line in f:
                    if line.strip():
                        runs.append(json.loads(line))
        except Exception as e:
            print(f"Error loading {jsonl_file}: {e}")
    return runs


def classify_response_type_weak_label(
    question: str,
    answer: str,
    gates_passed: bool,
    confidence: float
) -> str:
    """
    Weak labeling heuristic for response type.
    
    Uses patterns from existing code + gate results as signals.
    Not perfect but good enough to bootstrap.
    """
    q = question.lower().strip()
    
    # Factual questions (should have high standards)
    factual_patterns = [
        r'\bwhat is my\b',
        r'\bwhere (do|did) (i|you)\b',
        r'\bwhen (did|do) (i|you)\b',
        r'\bwho is my\b',
    ]
    if any(re.search(p, q) for p in factual_patterns):
        return "factual"
    
    # Explanatory questions (can be more synthetic)
    explanatory_patterns = [
        r'\bhow (would|could|do|does)\b',
        r'\bwhy (do|does|is|are)\b',
        r'\bexplain\b',
        r'\btell me about\b',
        r'\bwhat (are|is) the\b',
    ]
    if any(re.search(p, q) for p in explanatory_patterns):
        return "explanatory"
    
    # Conversational (greetings, acknowledgments, questions about assistant)
    conversational_patterns = [
        r'\bhello\b',
        r'\bhi\b',
        r'\bthanks\b',
        r'\bokay\b',
        r'\bwho are you\b',
        r'\bwhat are you\b',
    ]
    if any(re.search(p, q) for p in conversational_patterns):
        return "conversational"
    
    # Default: use gate result + confidence as signal
    if gates_passed and confidence > 0.7:
        return "conversational"  # Passed gates, likely safe
    elif not gates_passed:
        return "explanatory"  # Failed gates, might need relaxed standards
    else:
        return "conversational"  # Medium confidence


def extract_gate_failure_features(question: str, answer: str) -> Dict[str, Any]:
    """Extract features useful for learning gate logic."""
    q = question.lower().strip()
    
    # Question word features
    question_words = ['what', 'where', 'when', 'who', 'why', 'how']
    has_question_word = any(w in q for w in question_words)
    starts_with_question = q.split()[0] in question_words if q else False
    
    # Imperative mood detection
    imperative_verbs = ['tell', 'explain', 'describe', 'show', 'give', 'list']
    starts_with_imperative = q.split()[0] in imperative_verbs if q else False
    
    # Second person pronouns
    has_you_your = bool(re.search(r'\b(you|your)\b', q))
    
    # Question mark
    has_question_mark = '?' in question
    
    return {
        'has_question_word': has_question_word,
        'starts_with_question': starts_with_question,
        'starts_with_imperative': starts_with_imperative,
        'has_you_your': has_you_your,
        'has_question_mark': has_question_mark,
        'question_length': len(question),
        'word_count': len(question.split()),
    }


def build_training_dataset(runs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Build training dataset from stress test runs."""
    training_examples = []
    
    gate_failure_stats = Counter()
    response_type_stats = Counter()
    
    for run in runs:
        question = run.get('question', '')
        answer = run.get('answer', '')
        gates_passed = run.get('gates_passed', False)
        confidence = run.get('confidence', 0.0)
        
        if not question:
            continue
        
        # Weak label for response type
        response_type = classify_response_type_weak_label(
            question, answer, gates_passed, confidence
        )
        
        # Extract features
        features = extract_gate_failure_features(question, answer)
        
        training_example = {
            'question': question,
            'answer': answer,
            'response_type': response_type,  # Weak label
            'gates_passed': gates_passed,
            'confidence': confidence,
            'features': features,
            'run_id': run.get('run_id'),
            'turn': run.get('turn'),
        }
        
        training_examples.append(training_example)
        
        # Stats
        gate_failure_stats[gates_passed] += 1
        response_type_stats[response_type] += 1
    
    print(f"\n=== Training Data Statistics ===")
    print(f"Total examples: {len(training_examples)}")
    print(f"Gate passes: {gate_failure_stats[True]}")
    print(f"Gate failures: {gate_failure_stats[False]}")
    print(f"Pass rate: {gate_failure_stats[True] / len(training_examples) * 100:.1f}%")
    print(f"\nResponse type distribution:")
    for rtype, count in response_type_stats.most_common():
        print(f"  {rtype}: {count} ({count/len(training_examples)*100:.1f}%)")
    
    return training_examples


def analyze_gate_failure_patterns(examples: List[Dict[str, Any]]) -> None:
    """Analyze what causes gate failures."""
    print(f"\n=== Gate Failure Pattern Analysis ===")
    
    passed = [ex for ex in examples if ex['gates_passed']]
    failed = [ex for ex in examples if not ex['gates_passed']]
    
    if not failed:
        print("No gate failures found!")
        return
    
    print(f"\nFailed examples: {len(failed)}")
    print(f"\nSample failed questions:")
    for ex in failed[:10]:
        print(f"  - {ex['question'][:80]}...")
        print(f"    Type: {ex['response_type']}, Confidence: {ex['confidence']:.2f}")
    
    # Feature correlation with failure
    print(f"\n=== Feature Correlation with Gate Failure ===")
    
    features_to_check = [
        'has_question_word',
        'starts_with_question',
        'starts_with_imperative',
        'has_you_your',
        'has_question_mark',
    ]
    
    for feature in features_to_check:
        passed_pct = sum(ex['features'][feature] for ex in passed) / len(passed) * 100 if passed else 0
        failed_pct = sum(ex['features'][feature] for ex in failed) / len(failed) * 100 if failed else 0
        
        print(f"{feature:30} Passed: {passed_pct:5.1f}%  Failed: {failed_pct:5.1f}%  Diff: {failed_pct - passed_pct:+.1f}%")


def suggest_threshold_improvements(examples: List[Dict[str, Any]]) -> None:
    """Suggest threshold adjustments based on data."""
    print(f"\n=== Suggested Threshold Adjustments ===")
    
    # Group by response type and gate result
    by_type = defaultdict(lambda: {'passed': [], 'failed': []})
    
    for ex in examples:
        rtype = ex['response_type']
        key = 'passed' if ex['gates_passed'] else 'failed'
        by_type[rtype][key].append(ex)
    
    print(f"\nCurrent gate pass rates by response type:")
    for rtype in ['factual', 'explanatory', 'conversational']:
        passed = len(by_type[rtype]['passed'])
        failed = len(by_type[rtype]['failed'])
        total = passed + failed
        if total > 0:
            pass_rate = passed / total * 100
            print(f"  {rtype:20} {pass_rate:5.1f}% ({passed}/{total} passed)")
    
    print(f"\nRecommendations:")
    
    # Explanatory should have high fail rate with current gates
    explanatory_pass_rate = (
        len(by_type['explanatory']['passed']) / 
        (len(by_type['explanatory']['passed']) + len(by_type['explanatory']['failed']))
        * 100
    ) if (len(by_type['explanatory']['passed']) + len(by_type['explanatory']['failed'])) > 0 else 0
    
    if explanatory_pass_rate < 30:
        print(f"  ✓ Explanatory questions need LOWER thresholds (current {explanatory_pass_rate:.1f}% pass)")
        print(f"    Suggested: theta_intent=0.4, theta_mem=0.25")
    
    # Factual should have moderate pass rate
    factual_pass_rate = (
        len(by_type['factual']['passed']) / 
        (len(by_type['factual']['passed']) + len(by_type['factual']['failed']))
        * 100
    ) if (len(by_type['factual']['passed']) + len(by_type['factual']['failed'])) > 0 else 0
    
    if factual_pass_rate < 50:
        print(f"  ⚠ Factual questions failing too often ({factual_pass_rate:.1f}%)")
        print(f"    Consider: theta_intent=0.55, theta_mem=0.4")


def main():
    import argparse
    
    parser = argparse.ArgumentParser(description="Bootstrap training data from stress tests")
    parser.add_argument('--artifacts-dir', type=Path, default=Path('artifacts'),
                       help='Directory containing stress test JSONL files')
    parser.add_argument('--output', type=Path, default=Path('training_data/bootstrap_v1.jsonl'),
                       help='Output JSONL file for training data')
    parser.add_argument('--analyze-only', action='store_true',
                       help='Only analyze, do not write output')
    
    args = parser.parse_args()
    
    print(f"Loading stress test runs from {args.artifacts_dir}...")
    runs = load_stress_test_runs(args.artifacts_dir)
    print(f"Loaded {len(runs)} examples from stress tests")
    
    if not runs:
        print("No data found! Check artifacts directory.")
        return
    
    # Build training dataset
    training_examples = build_training_dataset(runs)
    
    # Analyze patterns
    analyze_gate_failure_patterns(training_examples)
    suggest_threshold_improvements(training_examples)
    
    if not args.analyze_only:
        # Write output
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with open(args.output, 'w', encoding='utf-8') as f:
            for example in training_examples:
                f.write(json.dumps(example) + '\n')
        
        print(f"\n✓ Wrote {len(training_examples)} training examples to {args.output}")
        print(f"\nNext steps:")
        print(f"  1. Review the analysis above")
        print(f"  2. Train response-type classifier: python tools/train_response_classifier.py")
        print(f"  3. Test new gates: python tools/crt_stress_test.py --use-learned-gates")
    else:
        print(f"\n(--analyze-only mode, no files written)")


if __name__ == '__main__':
    main()
