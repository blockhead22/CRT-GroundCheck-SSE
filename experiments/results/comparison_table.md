# Baseline Comparison Results

## Overall Performance

| Method | Accuracy | Avg Latency | Avg Cost | Notes |
|--------|----------|-------------|----------|-------|
| groundcheck | 80.0% | 0.00ms | $0.000000 | Deterministic |
| vanilla_rag | 54.0% | 0.00ms | $0.000000 | Deterministic |
| selfcheck_gpt | 72.0% | 0.23ms | $0.000000 | Deterministic |
| cove | 72.0% | 0.20ms | $0.000000 | Deterministic |

## Category Breakdown

| Category | groundcheck | vanilla_rag | selfcheck_gpt | cove |
|----------|----------|----------|----------|----------|
| factual_grounding | 80.0% | 40.0% | 80.0% | 80.0% |
| contradictions | 70.0% | 40.0% | 30.0% | 30.0% |
| partial_grounding | 70.0% | 0.0% | 70.0% | 70.0% |
| paraphrasing | 80.0% | 90.0% | 80.0% | 80.0% |
| multi_hop | 100.0% | 100.0% | 100.0% | 100.0% |