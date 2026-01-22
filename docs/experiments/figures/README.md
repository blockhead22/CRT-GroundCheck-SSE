# Experiment Figures

This directory will contain generated figures for the experimental results.

## Planned Figures

### Performance Comparison

**Figure 1: Overall Accuracy by System**
- Bar chart comparing GroundCheck, SelfCheckGPT, CoVe, and Vanilla RAG
- Shows overall accuracy across all categories

**Figure 2: Category-Specific Performance**
- Grouped bar chart showing accuracy for each category
- Highlights GroundCheck's advantage on contradictions (90% vs ~30%)

**Figure 3: Contradiction Handling Comparison**
- Detailed breakdown of contradiction category performance
- Shows different contradiction types (temporal, correction, source conflict)

### Efficiency Analysis

**Figure 4: Latency vs Accuracy Trade-off**
- Scatter plot: X-axis = latency, Y-axis = accuracy
- Shows GroundCheck's position (high accuracy, low latency)

**Figure 5: Cost vs Performance**
- Scatter plot: X-axis = cost per 1000 calls, Y-axis = accuracy
- Highlights GroundCheck's zero-cost advantage

### Error Analysis

**Figure 6: Error Distribution by Category**
- Stacked bar chart showing error types per system
- Breaks down errors by category

**Figure 7: Confusion Matrices**
- 2x2 confusion matrices for each system
- Shows true/false positives and negatives

## Generation Scripts

Figures will be generated from experimental results using:

```python
import json
import matplotlib.pyplot as plt
import seaborn as sns

# Load results
with open('../results/baseline_comparison.json') as f:
    results = json.load(f)

# Generate figures...
```

## File Format

All figures should be saved in:
- **PNG** format (300 DPI) for preview
- **PDF** format (vector) for paper submission
- **SVG** format (optional) for web display

## Naming Convention

Use descriptive names:
- `overall_accuracy_comparison.png`
- `contradiction_performance_breakdown.png`
- `latency_vs_accuracy_scatter.png`

## Attribution

All figures are generated from experimental results and are original work.
