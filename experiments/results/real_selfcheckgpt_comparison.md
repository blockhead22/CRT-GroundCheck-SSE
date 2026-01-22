# Real SelfCheckGPT Comparison

**CRITICAL CREDIBILITY TEST**

This comparison uses the ACTUAL SelfCheckGPT library (not a mock implementation)
to validate GroundCheck's performance claims.

## Executive Summary

- **GroundCheck**: 72.0% overall accuracy
- **SelfCheckGPT**: 62.0% overall accuracy

## Detailed Results

### Overall Performance

| System | Overall | Correct | Total | Avg Latency |
|--------|---------|---------|-------|-------------|
| GroundCheck | 72.0% | 36 | 50 | 1.0ms |
| SelfCheckGPT (Real) | 62.0% | 31 | 50 | 3085.2ms |

### Performance By Category

| Category | GroundCheck | SelfCheckGPT | Difference |
|----------|-------------|--------------|------------|
| contradictions | 70.0% | 10.0% | +60.0% |
| factual_grounding | 80.0% | 80.0% | 0.0% |
| multi_hop | 100.0% | 50.0% | +50.0% |
| paraphrasing | 70.0% | 80.0% | -10.0% |
| partial_grounding | 40.0% | 90.0% | -50.0% |

## Key Findings

### Contradiction Handling

**GroundCheck**: 70.0% on contradiction examples
**SelfCheckGPT**: 10.0% on contradiction examples

**Advantage**: 60.0 percentage points

### Why The Difference?

**GroundCheck** explicitly:
- Detects contradictions in retrieved context
- Tracks contradiction history in ledger
- Requires disclosure when appropriate
- Uses trust-weighted contradiction resolution

**SelfCheckGPT**:
- Checks consistency between generated text and context
- Does NOT detect contradictions within context itself
- Does NOT verify contradiction disclosure
- No contradiction tracking or history

## Cost & Performance

- **GroundCheck**: $0.0000 total cost, 1.0ms avg latency
- **SelfCheckGPT (NLI)**: $0.0000 total cost, 3085.2ms avg latency

## Errors & Issues

No errors encountered in either system.

## Reproduction Instructions

```bash
# Install dependencies
pip install selfcheckgpt

# Run comparison
cd experiments
python real_selfcheckgpt_comparison.py
```

## Conclusion

This comparison validates GroundCheck's 60.0 percentage point advantage
on contradiction handling using the REAL SelfCheckGPT implementation.

The results confirm that explicit contradiction detection and disclosure verification
provides meaningful improvements over consistency-checking approaches.
