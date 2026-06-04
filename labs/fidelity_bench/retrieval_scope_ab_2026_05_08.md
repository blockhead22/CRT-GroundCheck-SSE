# Retrieval scope A/B — speech echo interference

Date: 2026-05-08  
Runner: `labs/fidelity_bench/run_retrieval_scope_ab.py`  
Result artifact: `labs/fidelity_bench/results/retrieval_scope_ab_1778221000.json`  
Chart: `labs/fidelity_bench/results/retrieval_scope_ab_1778221000.png`

## Result

On 577 real `belief_speech` rows with stored response embeddings, raw nearest-neighbor cosine over the full vector bank was **anti-predictive** of grounding:

| Retrieval scope | AUC vs stored `is_belief` |
|---|---:|
| Full vector bank | 0.456 |
| Belief lane only | 0.726 |
| Full bank, trust-weighted | 0.496 |
| Belief lane, trust-weighted | 0.713 |
| Response/query cosine baseline | 0.689 |

The cause is speech echo interference:

| Measurement | Value |
|---|---:|
| Full-bank top-5 generated-speech fraction | 92.1% |
| Full-bank top-1 is generated speech | 96.0% |
| Full-bank top-1 is near-exact echo | 61.4% |
| Belief-lane top-5 generated-speech fraction | 0.0% |

Grounded vs ungrounded mean top-5 cosine:

| Scope | Grounded | Ungrounded |
|---|---:|---:|
| Full vector bank | 0.735 | 0.755 |
| Belief lane | 0.465 | 0.363 |

In the full bank, ungrounded responses looked *more* similar to memory than grounded responses. After removing generated speech and keeping only belief/fact lanes, the expected ordering returned.

## Interpretation

Nearest-neighbor familiarity is not belief support.

The substrate had stored generated responses as `system/observation` memories. When a later response was scored against the full vector bank, cosine often found prior speech that sounded like the current response, including exact echoes. That creates a false sense of grounding: the system is retrieving things it said, not things it believes.

This is a direct measurement of Aether's Law 1:

> Speech cannot upgrade belief.

It also reframes the memory problem. The issue is not just "vector DBs forget" or "cosine is weak." The sharper failure mode is that unscoped semantic retrieval collapses belief and speech into the same neighborhood. You need lane separation, provenance, trust, and contradiction state before similarity becomes useful.

## Caveats

- Labels are the substrate's own stored `belief_speech.is_belief` flag, not an external human annotation.
- The full vector bank here is the 1,049 non-deprecated rows with full 384D vectors, not all 79,792 memory rows. Most self-model rows are compacted and do not have full vectors.
- This measures retrieval scope and grounding discrimination, not final user-visible answer quality.
- The result should be rerun after fixing storage policy so generated speech no longer enters the same retrieval lane as beliefs.

## Discord-sized version

Ran a new Aether bench on real substrate logs:

Raw cosine over the full memory vector bank was **anti-predictive** of grounding: AUC 0.456 vs the substrate's stored `is_belief` label. Why? 96% of full-bank top-1 hits were generated speech memories, and 61% were near-exact echoes of the current response.

After scoping retrieval to the belief/fact lane only, AUC jumped to **0.726** and generated-speech retrieval dropped to 0%.

So the failure mode is very concrete: semantic memory retrieves what the model has *said* because it sounds nearby, not what the system actually *believes*. This is exactly why Aether separates speech from belief. Nearest-neighbor familiarity is not belief support.
