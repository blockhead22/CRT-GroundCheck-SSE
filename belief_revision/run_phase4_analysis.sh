#!/bin/bash
# Run all Phase 4 baseline analysis scripts in sequence

set -e  # Exit on error

echo "=========================================="
echo "Phase 4: Baseline Analysis - Full Suite"
echo "=========================================="
echo ""

# Task 5: Per-Category Analysis
echo "Task 5: Running per-category analysis..."
python -m belief_revision.baselines.per_category_analysis
echo ""

# Task 6: Inference Time Benchmarking
echo "Task 6: Running inference time benchmark..."
python -m belief_revision.baselines.benchmark_inference_time
echo ""

# Summary
echo "=========================================="
echo "All Phase 4 Tasks Complete!"
echo "=========================================="
echo ""
echo "Generated outputs:"
echo "  - belief_revision/results/per_category_analysis.md"
echo "  - belief_revision/results/per_category_baseline_comparison.png"
echo "  - belief_revision/results/inference_time_benchmark.json"
echo "  - belief_revision/results/inference_time_comparison.png"
echo "  - belief_revision/BASELINE_COMPARISON_SUMMARY.md"
echo ""
echo "To view the master summary:"
echo "  cat belief_revision/BASELINE_COMPARISON_SUMMARY.md"
echo ""
