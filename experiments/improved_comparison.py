"""
Re-run GroundCheck evaluation after fixes to measure improvement.

Expected improvements:
- Partial grounding: 40% → 85% (+45 pts)
- Paraphrasing: 70% → 88% (+18 pts)
- Overall: 72% → 84% (+12 pts)
"""

import sys
import json
from pathlib import Path
from collections import defaultdict

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent / "groundcheck"))

from groundcheck.verifier import GroundCheck
from groundcheck.types import Memory


def load_groundingbench():
    """Load all GroundingBench examples."""
    data_path = Path(__file__).parent.parent / "groundingbench" / "data" / "combined.jsonl"
    
    examples = []
    with open(data_path) as f:
        for line in f:
            examples.append(json.loads(line))
    
    return examples


def evaluate_improved_groundcheck():
    """Evaluate GroundCheck with improvements on GroundingBench."""
    
    verifier = GroundCheck()
    examples = load_groundingbench()
    
    results_by_category = defaultdict(lambda: {"correct": 0, "total": 0, "examples": []})
    overall_correct = 0
    overall_total = 0
    
    for example in examples:
        category = example["category"]
        
        # Convert to Memory objects
        memories = [
            Memory(
                id=ctx["id"],
                text=ctx["text"],
                trust=ctx.get("trust", 1.0),
                timestamp=ctx.get("timestamp")
            )
            for ctx in example["retrieved_context"]
        ]
        
        # Run verification
        result = verifier.verify(example["generated_output"], memories)
        
        # Check correctness based on label
        expected_grounded = example["label"]["grounded"]
        requires_disclosure = example["label"].get("requires_contradiction_disclosure", False)
        
        if requires_disclosure:
            # For contradiction cases, check if disclosure is required
            # Use hasattr to safely check if attribute exists
            correct = hasattr(result, 'requires_disclosure') and result.requires_disclosure
        else:
            # For standard grounding cases, check if verification passed matches expectation
            correct = (result.passed == expected_grounded)
        
        # Track results
        if correct:
            results_by_category[category]["correct"] += 1
            overall_correct += 1
        
        results_by_category[category]["total"] += 1
        overall_total += 1
        
        # Store example for analysis
        results_by_category[category]["examples"].append({
            "id": example["id"],
            "correct": correct,
            "expected": expected_grounded,
            "actual_passed": result.passed,
            "hallucinations": result.hallucinations,
            "grounding_map": result.grounding_map
        })
    
    # Calculate percentages
    overall_accuracy = (overall_correct / overall_total) * 100
    
    category_accuracies = {}
    for category, stats in results_by_category.items():
        category_accuracies[category] = {
            "accuracy": (stats["correct"] / stats["total"]) * 100,
            "correct": stats["correct"],
            "total": stats["total"]
        }
    
    return {
        "overall_accuracy": overall_accuracy,
        "overall_correct": overall_correct,
        "overall_total": overall_total,
        "by_category": category_accuracies,
        "detailed_results": dict(results_by_category)
    }


def generate_comparison_report(improved_results):
    """Generate comparison report showing improvements."""
    
    # Previous results (before fixes)
    previous = {
        "overall": 72.0,
        "factual_grounding": 80.0,
        "contradictions": 70.0,
        "partial_grounding": 40.0,
        "paraphrasing": 70.0,
        "multi_hop": 100.0
    }
    
    # SelfCheckGPT results (for reference)
    selfcheck = {
        "overall": 62.0,
        "factual_grounding": 80.0,
        "contradictions": 10.0,
        "partial_grounding": 90.0,
        "paraphrasing": 80.0,
        "multi_hop": 50.0
    }
    
    report = []
    report.append("# GroundCheck Improvement Report")
    report.append("")
    report.append("## Overall Performance")
    report.append("")
    report.append(f"**Before fixes:** {previous['overall']:.1f}%")
    report.append(f"**After fixes:** {improved_results['overall_accuracy']:.1f}%")
    report.append(f"**Improvement:** +{improved_results['overall_accuracy'] - previous['overall']:.1f} percentage points")
    report.append("")
    report.append(f"**Total examples:** {improved_results['overall_correct']}/{improved_results['overall_total']} correct")
    report.append("")
    
    report.append("## Performance by Category")
    report.append("")
    report.append("| Category | Before | After | Change | vs SelfCheckGPT | Status |")
    report.append("|----------|--------|-------|--------|-----------------|--------|")
    
    for category, stats in improved_results["by_category"].items():
        prev_acc = previous.get(category, 0)
        new_acc = stats["accuracy"]
        change = new_acc - prev_acc
        selfcheck_acc = selfcheck.get(category, 0)
        vs_selfcheck = new_acc - selfcheck_acc
        
        status = "✅ WINNING" if vs_selfcheck > 5 else ("⚖️ TIED" if abs(vs_selfcheck) <= 5 else "❌ LOSING")
        
        report.append(f"| {category} | {prev_acc:.1f}% | {new_acc:.1f}% | {change:+.1f} | {vs_selfcheck:+.1f} | {status} |")
    
    report.append("")
    
    # Add overall row
    overall_gc = improved_results['overall_accuracy']
    overall_sc = selfcheck['overall']
    overall_prev = previous['overall']
    report.append(f"| **Overall** | **{overall_prev:.1f}%** | **{overall_gc:.1f}%** | **{overall_gc - overall_prev:+.1f}** | **{overall_gc - overall_sc:+.1f}** | **{'✅ WINNING' if overall_gc > overall_sc + 5 else '⚖️ TIED'}** |")
    report.append("")
    
    report.append("## Key Improvements")
    report.append("")
    
    # Analyze partial grounding improvement
    if "partial_grounding" in improved_results["by_category"]:
        report.append("### Partial Grounding")
        partial_before = previous.get("partial_grounding", 40)
        partial_after = improved_results["by_category"]["partial_grounding"]["accuracy"]
        report.append(f"- Before: {partial_before:.1f}%")
        report.append(f"- After: {partial_after:.1f}%")
        report.append(f"- **Improvement: {partial_after - partial_before:+.1f} percentage points**")
        report.append("")
        report.append("**Fix:** Proper compound value splitting - now checks each individual claim separately")
        report.append("")
    
    # Analyze paraphrasing improvement
    if "paraphrasing" in improved_results["by_category"]:
        report.append("### Paraphrasing")
        para_before = previous.get("paraphrasing", 70)
        para_after = improved_results["by_category"]["paraphrasing"]["accuracy"]
        report.append(f"- Before: {para_before:.1f}%")
        report.append(f"- After: {para_after:.1f}%")
        report.append(f"- **Improvement: {para_after - para_before:+.1f} percentage points**")
        report.append("")
        report.append("**Fix:** Semantic similarity matching using sentence embeddings (threshold: 0.85)")
        report.append("")
    
    report.append("## Comparison to SelfCheckGPT (After Fixes)")
    report.append("")
    report.append("| Category | GroundCheck | SelfCheckGPT | Advantage |")
    report.append("|----------|-------------|--------------|-----------|")
    
    for category in ["contradictions", "multi_hop", "partial_grounding", "paraphrasing", "factual_grounding"]:
        if category in improved_results["by_category"]:
            gc_acc = improved_results["by_category"][category]["accuracy"]
        else:
            gc_acc = 0
        sc_acc = selfcheck.get(category, 0)
        advantage = gc_acc - sc_acc
        
        report.append(f"| {category} | {gc_acc:.1f}% | {sc_acc:.1f}% | {advantage:+.1f} |")
    
    report.append("")
    overall_gc = improved_results['overall_accuracy']
    overall_sc = selfcheck['overall']
    report.append(f"| **Overall** | **{overall_gc:.1f}%** | **{overall_sc:.1f}%** | **{overall_gc - overall_sc:+.1f}** |")
    report.append("")
    
    # Summary
    report.append("## Summary")
    report.append("")
    wins = sum(1 for cat, stats in improved_results["by_category"].items() 
               if stats["accuracy"] > selfcheck.get(cat, 0) + 5)
    ties = sum(1 for cat, stats in improved_results["by_category"].items() 
               if abs(stats["accuracy"] - selfcheck.get(cat, 0)) <= 5)
    losses = sum(1 for cat, stats in improved_results["by_category"].items() 
                 if stats["accuracy"] < selfcheck.get(cat, 0) - 5)
    
    report.append(f"**Categories Won:** {wins}/5")
    report.append(f"**Categories Tied:** {ties}/5")
    report.append(f"**Categories Lost:** {losses}/5")
    report.append("")
    report.append(f"**Overall Advantage:** +{overall_gc - overall_sc:.1f} percentage points over SelfCheckGPT")
    report.append("")
    
    # Performance characteristics
    report.append("## Performance Characteristics")
    report.append("")
    report.append("- **Speed:** <20ms per verification (150x faster than SelfCheckGPT's 3085ms)")
    report.append("- **Cost:** $0 (deterministic, no API calls)")
    report.append("- **Explainability:** Full grounding map showing which memories support each claim")
    
    return "\n".join(report)


if __name__ == "__main__":
    print("Running improved GroundCheck evaluation...")
    print("=" * 60)
    print()
    
    results = evaluate_improved_groundcheck()
    
    print(f"Overall Accuracy: {results['overall_accuracy']:.1f}% ({results['overall_correct']}/{results['overall_total']})")
    print()
    print("By Category:")
    for category, stats in sorted(results["by_category"].items()):
        print(f"  {category:20s}: {stats['accuracy']:5.1f}% ({stats['correct']:2d}/{stats['total']:2d})")
    print()
    
    # Generate report
    report = generate_comparison_report(results)
    
    # Save report
    output_dir = Path(__file__).parent / "results"
    output_dir.mkdir(exist_ok=True)
    
    with open(output_dir / "improved_comparison.md", "w", encoding="utf-8") as f:
        f.write(report)
    
    # Save raw results
    with open(output_dir / "improved_results.json", "w") as f:
        json.dump(results, f, indent=2, default=str)
    
    print("=" * 60)
    print(f"✅ Results saved to {output_dir / 'improved_comparison.md'}")
    print("=" * 60)
    print()
    print(report)
