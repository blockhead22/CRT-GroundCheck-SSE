---
name: deep_research_results
description: Deep research session results (2026-03-26) — 6 directions investigated, competitive landscape, archive/sprint/research decisions, priority queue
type: project
---

## Session Output
Full report: D:\CRT\compression_lab\DEEP_RESEARCH_RESULTS.md

## Sprint Queue (build now)
1. **Rename TurboQuant** — Google published same name at ICLR 2026. Day 1.
2. **Contradiction disposition classifier Phase 1** — NLI + subjectivity + temporal gap + entity specificity. Rule-based routing to resolvable/held/evolving. 2-3 weeks. THIS IS THE MOAT.
3. **Memory graph** — NetworkX + JSON. Automated CONTRADICTS/SUPERSEDES edges. Subgraph retrieval. 2-3 weeks.
4. **Temporal governance** — type tag (fact/preference/event/belief) + policy table + Belnap state (T/F/Both/Neither). 1 week.
5. **Package as focused library** — pip installable, 3 integration examples, README. 2-4 weeks.
6. **ADC-style asymmetric comparison** — free improvement to RVQ retrieval. 1 day.

## Active Research (worth testing/publishing)
1. Subjectivity × contradiction interaction — nobody has combined these. Run both pipelines on real memory pairs. Potentially publishable.
2. "Contradiction as importance" hypothesis — test empirically: do high-contradiction-density topics correlate with retrieval frequency/engagement/valence?
3. Temporal type classification — zero-shot DeBERTa accuracy on real memories for fact/preference/event/belief tagging.
4. Belnap formalization — implement T/F/Both/Neither as first-class states, study retrieval behavior changes.
5. Epistemic entrenchment mapping — AGM theory predicts beliefs you resist giving up = identity. Test against real memory revision patterns.

## Archived (alive, hardware/data gated)
- **GNN subgraph encoding** — needs 5K+ memories with typed edges + local GPU. Concept is sound, prerequisites not met. Revisit when graph is populated.
- **QINCo-style learned correction** — small neural net for cross-depth similarity correction. Needs training data generation + GPU. Archive.
- **Fine-tuned DeBERTa Phase 3** — end-to-end disposition classification. Needs real user contradiction pairs from Phase 1/2. Archive until data exists.
- **Online codebook refit** — proven marginal by TurboQuant theory (Gaussian assumption near-optimal after rotation). Low ceiling. Skip.
- **Formal cross-precision bounds** — academically interesting, not product-relevant. Empirical measurement faster.

## Competitive Landscape (as of 2026-03-26)
- Mem0: $24M raised, 80K devs, AWS exclusive, 186M API calls/quarter. Does ADD/UPDATE/DELETE — no held contradictions.
- Zep: $1M revenue, 5 people, temporal KG with invalidation — closest to governed memory but resolves everything.
- Letta: $10M seed, $70M val. Self-editing memory, different angle.
- Personize.ai: published "Governed Memory" paper with production system.
- Google: "TurboQuant" at ICLR 2026 — name collision, validates approach.
- NOBODY has contradiction disposition classification.

## Key Insight
Don't build a platform. Build a focused library around the one thing nobody else has: the ability to detect contradictions AND decide what to do about them (resolve/hold/watch). The held contradiction concept is defensible because it requires a philosophical position, not just engineering.

**Why:** Funded teams can add NLI detection in 2-4 weeks. They can't add held contradictions without fundamentally rethinking their architecture — it violates the assumption that consistency is always the goal.

## IMPLEMENTATION SESSION (2026-03-26)

### All 8 theory steps built and tested:
| Step | Module | Key Result |
|---|---|---|
| 1. Disposition classifier | disposition_classifier.py | 18/18 on test suite. Rule-based, no ML needed. |
| 2. Memory graph | memory_graph.py | Typed edges, Belnap states, importance proxy works. |
| 3. Temporal governance | temporal_governance.py | Type-dependent decay, correct retrieval ranking. |
| 4. Memory splats | memory_splats.py | Diagonal covariance, evidence updates, trajectory tracking. |
| 5. Predictive contradiction | predictive_contradiction.py | 40% advance warning, zero false positives on control. |
| 6. Belief topology | belief_topology.py | Persistent homology detects avoidance patterns (H1 holes). |
| 7. Belief/speech separation | belief_speech.py | Auditable gap, deceptive alignment early warning. |
| 8. Information geometry | info_geometry.py | Fisher metric 3.16x amplification on certain disagreement. |

### Key experimental findings:
- **Two-mode geometry:** Static detection uses cosine (overlap near-zero in 384D). Dynamic/predictive detection uses overlap TREND. The splat is a trajectory, not a better point.
- **Fisher reranks retrieval:** Confident matches promoted, uncertain demoted. "I know X" vs "I think maybe X" invisible to cosine (dist=0), visible to Fisher (dist=44.6).
- **Topology detects structure:** Ring of beliefs around avoided topic = measurable persistent H1 feature. Confidence weighting amplifies holes.
- **Gap trend = deceptive alignment warning:** System detects its own increasing opacity over time.

### Backpocket experiment:
**LLM belief variance mapping** — prompt an LLM hundreds of times on the same questions with no context. Measure response distribution variance per topic. High variance = model "contradicts itself" = high importance/ambivalence topics. Could map an LLM's belief landscape empirically. First dataset of its kind.

### Three paths forward:
1. **Library:** Package classifier + splats + prediction as pip library. Open source. Blog post. See if anyone cares.
2. **Paper:** Formalize into position paper. Preliminary results (synthetic) but novel framework. Workshop submission.
3. **Experiment:** When OpenAI dump arrives, run pipeline on real data. Test contradiction density vs importance correlation. THE empirical result that makes everything credible.

### Updated priority queue:
1. RENAME TURBOQUANT — day 1 (Google owns the name)
2. Get real data — OpenAI export dump, Aether memory DB text
3. Run disposition classifier on organic contradictions
4. Test contradiction density vs importance hypothesis
5. Write position paper / blog post
6. Package as library
