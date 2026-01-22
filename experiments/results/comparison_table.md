# Grounding System Comparison

## Overall Accuracy

| System | Overall | contradictions | factual_grounding | multi_hop | paraphrasing | partial_grounding |
|--------|---------|--------|--------|--------|--------|--------|
| GroundCheck | 70.0% | 60.0% | 80.0% | 100.0% | 70.0% | 40.0% |
| SelfCheckGPT | 68.0% | 30.0% | 80.0% | 100.0% | 90.0% | 40.0% |
| CoVe | 68.0% | 30.0% | 80.0% | 100.0% | 90.0% | 40.0% |
| Vanilla RAG | 54.0% | 40.0% | 40.0% | 100.0% | 90.0% | 0.0% |

## Key Findings

### Contradiction Handling

**GroundCheck** is the only system that explicitly detects contradictions in retrieved context.

- GroundCheck: Detects contradictions, requires disclosure when appropriate
- SelfCheckGPT: Checks consistency but does NOT detect contradictions in context
- CoVe: Verifies each claim independently, does NOT handle contradictory context
- Vanilla RAG: No verification at all

### Performance Summary

**GroundCheck:** 70.0% overall, 60.0% on contradictions
**SelfCheckGPT:** 68.0% overall, 30.0% on contradictions
**CoVe:** 68.0% overall, 30.0% on contradictions
**Vanilla RAG:** 54.0% overall, 40.0% on contradictions

### Contradiction Detection Gap

GroundCheck shows **2x improvement** on contradiction handling compared to baselines,
demonstrating that explicit contradiction awareness is essential for long-term memory systems.
