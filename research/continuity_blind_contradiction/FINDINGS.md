# Continuity-Blind Contradiction in Stateless AI Systems

## Empirical Finding

Over a 13-month period across 1,275 independent sessions, a stateless AI assistant delivered high-confidence guidance (mean 74%) on personal, therapeutic, and decision-support topics while exhibiting zero cross-session continuity awareness and a mean semantic consistency of 0.34. The system provided contradictory recommendations on the same recurring topics — including mental health management, career decisions, self-efficacy, financial planning, and project continuation — without ever acknowledging prior conflicting advice. This pattern was observed across all tested domains, all model versions (gpt-4o through gpt-5-4), and worsened on the highest-impact topics where users are most likely to act on the guidance received.

## Implication

Stateless conversational AI systems used for ongoing personal support produce a measurable failure mode: *continuity-blind, high-confidence contradiction on consequential topics*. This is not a theoretical risk — it is the default behavior of the dominant deployment paradigm. Systems deployed in therapeutic, advisory, or decision-support contexts without persistent belief state and continuity auditing will structurally replicate this failure at scale.

## Methodology

### Corpus
- Source: OpenAI ChatGPT data export (single user, Feb 2025 – Mar 2026)
- 1,275 conversations, 59,370 messages (26.8k user, 28.6k assistant)
- 234 MB of text across 13 JSON files
- Model versions: gpt-4o, gpt-4o-mini, gpt-4-1, gpt-5, gpt-5-1, gpt-5-2, gpt-5-2-thinking, gpt-5-4-thinking, o3

### Cross-Thread Consistency Analysis
- 17 technical topics + 23 personal topics probed
- Assistant responses embedded (all-MiniLM-L6-v2, 384 dims)
- Pairwise semantic similarity computed across responses from different threads on same topic
- Mean consistency = mean pairwise similarity within topic cluster

### Gaslighting Risk Measurement
- Formula: `risk = confidence × (1 - similarity) × (1 - continuity_awareness)`
- Confidence: ratio of assertive markers to hedging markers in response text
- Continuity awareness: presence of phrases acknowledging prior context or possible contradiction
- 14 high-impact personal/decision topics probed

## Key Metrics

### Cross-Thread Consistency (lower = more inconsistent)

| Category | Mean Consistency | Worst Topic |
|----------|-----------------|-------------|
| Technical topics | 0.365 | Governance layer design (0.255) |
| Personal topics | 0.338 | Health and wellness (0.250) |
| All topics | 0.350 | Health and wellness (0.250) |

### Gaslighting Risk by Domain (higher = worse)

| Domain | Research Framing | Risk Score | Confidence | Continuity |
|--------|-----------------|------------|------------|------------|
| Project Continuation | Sycophancy vs honest assessment stability | 0.561 | 84% | 0% |
| Work Prioritization | Consistency of goal-directed guidance | 0.529 | 75% | 0% |
| Startup vs Employment | Stability of vocational guidance | 0.524 | 67% | 0% |
| Self-Efficacy | Stability of efficacy-related feedback | 0.521 | 79% | 0% |
| Mental Health | Stability of coping strategy recommendations | 0.505 | 83% | 0% |
| Career Direction | Consistency of vocational guidance | 0.494 | 80% | 0% |
| Substance Use | Consistency of harm-reduction messaging | 0.471 | 67% | 0% |
| Technology Decisions | Stability of technical recommendations | 0.467 | 70% | 0% |
| Financial Planning | Stability of financial recommendations | 0.466 | 73% | 0% |
| Relationships | Consistency of interpersonal guidance | 0.401 | 72% | 0% |
| Quit vs Persevere | Continuity of motivational persistence framing | 0.390 | 71% | 0% |

### Universal Finding
- Continuity awareness across all topics, all threads, all model versions: **0.0%**
- Model drift detected: **100% of topics** (all showed divergence across model versions)

## Proposed Principle

**Law 6: Confidence must not exceed continuity.**

If a system has no memory of its prior stance on a topic, its confidence on that topic must be bounded. A system that cannot verify consistency with its own prior output should not deliver advice at full certainty.

## Clinical/Research Relevance

- **Bandura (self-efficacy theory):** Inconsistent feedback from trusted sources degrades self-belief. A system alternating between "you're doing great" and "reconsider everything" at full confidence constitutes an invalidating environment.
- **CBT/DBT continuity:** Therapeutic frameworks require stable framing across sessions. Contradictory frameworks increase cognitive load during elevated stress.
- **Decision paralysis:** Contradictory career/financial guidance from a trusted source produces decision paralysis or impulsive reversals.
- **Learned helplessness:** Inconsistent motivational feedback ("keep going" / "take a pause") with equal confidence undermines goal persistence.

## What CRT Addresses

The Contradiction-aware Reconciliation and Trust (CRT) framework directly addresses this failure mode through:

1. **Persistent belief state** — memories survive across sessions with trust scores
2. **Contradiction ledger** — conflicting claims are preserved, not silently overwritten
3. **Belief/speech separation** — grounded responses (belief) are distinguished from model-generated opinions (speech)
4. **Gap auditor** — measures the distance between confidence and grounding
5. **Variance tracker** — measures topic-level drift over time
6. **Self-model auditor** — validates claims against evidence, progressively deprecates unsupported assertions
7. **Proposed: Continuity auditor** — checks whether the system has spoken on a topic before and whether current response is consistent

## Tools

- `tools/chatgpt_corpus.py` — corpus parser and search
- `tools/corpus_consistency.py` — cross-thread consistency analyzer
- `tools/corpus_gaslighting.py` — gaslighting risk detector
- Data: `data/chatgpt_corpus.db`, `data/chatgpt_consistency.db`, `data/chatgpt_gaslighting.db`

## Next Steps

1. Hand-audit top 50 highest-risk pairs: classify as true contradiction / context-sensitive / framing variation / model drift
2. Build the Continuity Auditor as immune agent (Law 6)
3. Run CRT's consistency analysis on Aether's own conversation data as comparative baseline
4. Write up as empirical contribution with defensible methodology

## Date
2026-03-28

## Author
Nick Block / Aeteros
