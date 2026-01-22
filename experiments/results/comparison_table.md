# Baseline Comparison Results

## Overall Performance

| Method | Accuracy | Avg Latency | Avg Cost | Notes |
|--------|----------|-------------|----------|-------|
| groundcheck | 72.0% | 0.00ms | $0.000000 | Deterministic |
| vanilla_rag | 54.0% | 0.00ms | $0.000000 | Deterministic |
| selfcheck_gpt | 68.0% | 0.16ms | $0.000000 | Deterministic |
| cove | 68.0% | 0.16ms | $0.000000 | Deterministic |

## Category Breakdown

| Category | groundcheck | vanilla_rag | selfcheck_gpt | cove |
|----------|----------|----------|----------|----------|
| factual_grounding | 80.0% | 40.0% | 80.0% | 80.0% |
| contradictions | 70.0% | 40.0% | 30.0% | 30.0% |
| partial_grounding | 40.0% | 0.0% | 40.0% | 40.0% |
| paraphrasing | 70.0% | 90.0% | 90.0% | 90.0% |
| multi_hop | 100.0% | 100.0% | 100.0% | 100.0% |