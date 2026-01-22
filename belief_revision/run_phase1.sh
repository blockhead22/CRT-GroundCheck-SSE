#!/bin/bash
# Phase 1 Quick Start Script
# Run this to execute all Phase 1 steps in sequence

echo "=================================================="
echo "PHASE 1: BeliefRevisionBench Data Collection"
echo "Week 1, Day 1"
echo "=================================================="
echo ""

cd /home/runner/work/AI_round2/AI_round2

echo "Step 1: Extracting real data from database..."
echo "----------------------------------------------"
python belief_revision/scripts/phase1_extract_data.py

echo ""
echo ""
echo "Step 2: Generating synthetic data..."
echo "----------------------------------------------"
python belief_revision/scripts/phase1_generate_synthetic.py

echo ""
echo ""
echo "=================================================="
echo "PHASE 1 DAY 1 COMPLETE!"
echo "=================================================="
echo ""
echo "✓ Real data extracted"
echo "✓ Synthetic data generated"
echo ""
echo "Next steps:"
echo "1. Review: belief_revision/data/extraction_report.md"
echo "2. Review: belief_revision/data/potential_belief_updates.json"
echo "3. Label 50 examples manually"
echo ""
echo "See: belief_revision/README.md for detailed instructions"
echo ""
