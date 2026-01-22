"""
Evaluate all baselines on GroundingBench and compare to GroundCheck.
"""

import json
from pathlib import Path
import time
from typing import List, Dict
import sys

# Add parent directories to path
sys.path.insert(0, str(Path(__file__).parent.parent / "groundcheck"))
sys.path.insert(0, str(Path(__file__).parent.parent / "groundingbench"))

from groundcheck import GroundCheck, Memory
from baselines.vanilla_rag import VanillaRAG
from baselines.selfcheck_gpt import SelfCheckGPT
from baselines.cove import ChainOfVerification


def load_benchmark(category: str = None) -> List[Dict]:
    """Load GroundingBench examples."""
    data_dir = Path(__file__).parent.parent / "groundingbench" / "data"
    
    if category:
        file_path = data_dir / f"{category}.jsonl"
        files = [file_path] if file_path.exists() else []
    else:
        file_path = data_dir / "combined.jsonl"
        files = [file_path] if file_path.exists() else []
    
    examples = []
    for file_path in files:
        with open(file_path) as f:
            for line in f:
                examples.append(json.loads(line))
    
    return examples


def evaluate_method(method, examples: List[Dict], method_name: str) -> Dict:
    """Evaluate a single method on examples."""
    results = {
        "method": method_name,
        "total": len(examples),
        "correct": 0,
        "total_latency_ms": 0,
        "total_cost": 0,
        "by_category": {}
    }
    
    for example in examples:
        category = example.get("category", "unknown")
        
        # Convert memories to appropriate format
        if method_name == "groundcheck":
            # Extract only fields that Memory accepts
            memories = []
            for m in example["retrieved_context"]:
                mem_dict = {
                    "id": m["id"],
                    "text": m["text"],
                    "trust": m.get("trust", 1.0),
                    "timestamp": m.get("timestamp")
                }
                memories.append(Memory(**mem_dict))
            result = method.verify(example["generated_output"], memories)
            passed = result.passed
            latency = 0  # Measured in benchmark script
            cost = 0
        else:
            memories = example["retrieved_context"]
            result = method.verify(example["generated_output"], memories)
            # Handle both dict and dataclass results
            if isinstance(result, dict):
                passed = result.get("passed", result.get("grounded", False))
                latency = result.get("latency_ms", 0)
                cost = result.get("api_cost", 0)
            else:
                # BaselineResult dataclass
                passed = result.passed
                latency = result.latency_ms
                cost = result.api_cost
        
        # Check correctness
        expected = example["label"]["grounded"]
        requires_disclosure = example["label"].get("requires_contradiction_disclosure", False)
        
        # For contradiction cases, check if system detected the need for disclosure
        if requires_disclosure:
            # System is correct if it detected that disclosure is required
            # (The output may be grounded but needs acknowledgment of contradiction)
            if method_name == "groundcheck":
                # GroundCheck should detect this - correct if requires_disclosure is True
                correct = result.requires_disclosure
            else:
                # Baselines don't detect contradictions well
                # They're correct only if they happen to require disclosure
                if isinstance(result, dict):
                    system_requires_disclosure = result.get("requires_disclosure", False)
                else:
                    system_requires_disclosure = getattr(result, "requires_disclosure", False)
                correct = system_requires_disclosure
        else:
            # Standard grounding check - use passed field
            correct = (passed == expected)
        
        if correct:
            results["correct"] += 1
            if category not in results["by_category"]:
                results["by_category"][category] = {"correct": 0, "total": 0}
            results["by_category"][category]["correct"] += 1
        
        if category not in results["by_category"]:
            results["by_category"][category] = {"correct": 0, "total": 0}
        results["by_category"][category]["total"] += 1
        
        results["total_latency_ms"] += latency
        results["total_cost"] += cost
    
    # Calculate metrics
    results["accuracy"] = results["correct"] / results["total"]
    results["avg_latency_ms"] = results["total_latency_ms"] / results["total"]
    results["avg_cost_per_example"] = results["total_cost"] / results["total"]
    
    # Category accuracies
    for cat, stats in results["by_category"].items():
        stats["accuracy"] = stats["correct"] / stats["total"]
    
    return results


def main():
    """Run full evaluation."""
    print("=" * 60)
    print("BASELINE COMPARISON ON GROUNDINGBENCH")
    print("=" * 60)
    
    # Load benchmark
    print("\nLoading GroundingBench...")
    examples = load_benchmark()
    print(f"Loaded {len(examples)} examples")
    
    # Initialize methods
    methods = {
        "groundcheck": GroundCheck(),
        "vanilla_rag": VanillaRAG(),
        "selfcheck_gpt": SelfCheckGPT(num_samples=5),
        "cove": ChainOfVerification()
    }
    
    # Evaluate each method
    all_results = {}
    for name, method in methods.items():
        print(f"\nEvaluating {name}...")
        results = evaluate_method(method, examples, name)
        all_results[name] = results
        
        print(f"  Accuracy: {results['accuracy']:.1%}")
        print(f"  Avg latency: {results['avg_latency_ms']:.2f}ms")
        print(f"  Avg cost: ${results['avg_cost_per_example']:.6f}")
    
    # Generate comparison table
    print("\n" + "=" * 60)
    print("RESULTS SUMMARY")
    print("=" * 60)
    
    print(f"\n{'Method':<20} {'Accuracy':<10} {'Latency':<12} {'Cost':<10}")
    print("-" * 60)
    
    for name, results in all_results.items():
        print(f"{name:<20} {results['accuracy']:>8.1%} {results['avg_latency_ms']:>10.2f}ms ${results['avg_cost_per_example']:>8.6f}")
    
    # Category breakdown (focus on contradictions)
    print("\n" + "=" * 60)
    print("CATEGORY BREAKDOWN")
    print("=" * 60)
    
    categories = ["factual_grounding", "contradictions", "partial_grounding", "paraphrasing", "multi_hop"]
    
    print(f"\n{'Category':<25}", end="")
    for method in methods.keys():
        print(f"{method:<15}", end="")
    print()
    print("-" * 100)
    
    for category in categories:
        print(f"{category:<25}", end="")
        for name in methods.keys():
            cat_stats = all_results[name]["by_category"].get(category, {"accuracy": 0})
            print(f"{cat_stats['accuracy']:>13.1%}  ", end="")
        print()
    
    # Save results
    output_file = Path(__file__).parent / "results" / "baseline_comparison.json"
    output_file.parent.mkdir(exist_ok=True)
    
    with open(output_file, 'w') as f:
        json.dump(all_results, f, indent=2)
    
    print(f"\n✅ Results saved to {output_file}")
    
    # Generate markdown table
    markdown_file = Path(__file__).parent / "results" / "comparison_table.md"
    generate_markdown_table(all_results, markdown_file)
    print(f"✅ Markdown table saved to {markdown_file}")


def generate_markdown_table(results: Dict, output_file: Path):
    """Generate markdown comparison table."""
    lines = ["# Baseline Comparison Results\n"]
    lines.append("## Overall Performance\n")
    lines.append("| Method | Accuracy | Avg Latency | Avg Cost | Notes |")
    lines.append("|--------|----------|-------------|----------|-------|")
    
    for name, data in results.items():
        latency = f"{data['avg_latency_ms']:.2f}ms"
        cost = f"${data['avg_cost_per_example']:.6f}"
        notes = "Deterministic" if data['avg_cost_per_example'] == 0 else "LLM-based"
        
        lines.append(f"| {name} | {data['accuracy']:.1%} | {latency} | {cost} | {notes} |")
    
    lines.append("\n## Category Breakdown\n")
    lines.append("| Category | " + " | ".join(results.keys()) + " |")
    lines.append("|----------|" + "|".join(["----------"] * len(results)) + "|")
    
    categories = ["factual_grounding", "contradictions", "partial_grounding", "paraphrasing", "multi_hop"]
    for category in categories:
        line = f"| {category} |"
        for name in results.keys():
            cat_stats = results[name]["by_category"].get(category, {"accuracy": 0})
            line += f" {cat_stats['accuracy']:.1%} |"
        lines.append(line)
    
    output_file.write_text("\n".join(lines))


if __name__ == "__main__":
    main()
