# Aether Semantic Hybrid Shadow Results - 2026-07-10

## Question

Can an independent sentence-embedding score over six answer-class definitions
veto bad local-model route proposals without introducing a phrase catalog?

## Design

The scorer used the already cached `all-MiniLM-L6-v2` encoder. It embedded:

- the user request;
- one stable semantic definition for each answer class.

It did not embed example user phrases, learn from the held-out set, or mutate
prototypes. The hybrid accepted a shadow proposal only when:

1. the model proposal passed its existing schema/evidence validator;
2. the model class matched the embedding top class;
3. the top-two embedding margin was at least the fixed pre-run threshold `0.05`.

All other cases became ambiguity/fallback. Neither model nor embeddings received
authority over evidence release, tools, writes, contradictions, escalation, or
final prose.

## Fresh Holdout

The 24 prompts were not in the previous 48-case pack. They concentrate on:

- Continuity vs system meta;
- Continuity vs tool/workspace;
- Continuity vs general voice;
- direct memory lookup vs personal synthesis;
- missing-target ambiguity;
- lexical traps involving `continue`, `resume`, `history`, `change`, and `next`.

Artifact:
`labs/meaning_compression_lab/results/semantic_controller_hybrid_eval_1783699527.json`

## Result

| Mode | Class accuracy | Accepted | Continuity precision | Continuity recall | Ambiguity recall |
| --- | ---: | ---: | ---: | ---: | ---: |
| Mistral model only | 83.3% | 87.5% | 83.3% | 62.5% | 0% |
| Definition embeddings only | 50.0% | 54.2% | 66.7% | 50.0% | 100% |
| Hybrid agreement | 45.8% | 29.2% | 100% | 25.0% | 100% |

Mean latency was 2.012 seconds for Mistral and 0.032 seconds for embedding
scoring. Model evidence-needs fit remained 45.8%.

The hybrid is a strong abstention mechanism and a poor router. It removed all
accepted false-positive Continuity proposals, but accepted only 7/24 prompts and
recovered only 2/8 real Continuity requests.

Post-run threshold sensitivity was recorded for diagnosis, not selection:

| Margin | Accepted | Continuity precision | Continuity recall | Ambiguity recall |
| ---: | ---: | ---: | ---: | ---: |
| 0.00 | 41.7% | 100% | 50% | 66.7% |
| 0.02 | 37.5% | 100% | 50% | 100% |
| 0.05 | 29.2% | 100% | 25% | 100% |
| 0.10 | 20.8% | 100% | 25% | 100% |

No threshold turns definition-only agreement into a balanced controller.

## Failure Shape

One definition per broad answer class is too coarse:

- action requests containing `continue` score as Continuity;
- general stories and philosophical prompts score as personal synthesis or
  Continuity;
- direct personal facts can score as personal synthesis;
- system questions about Continuity can score as active project re-entry;
- semantically valid prompts often have small or inverted margins.

Adding many example utterances would likely improve the embedding scorer, but it
would reintroduce the phrase/prototype catalog this lane was meant to avoid. A
trained classifier might eventually be justified by reviewed route-correction
data, but the project does not have that dataset yet.

## Decision

Stop the natural-language semantic-controller lane here. Do not wire model-only,
embedding-only, or hybrid routing. Do not tune the margin against this holdout.

Keep:

- the shadow proposal/validation artifacts as evaluation infrastructure;
- exact `/where`, `/changed`, `/next`, and `/resume` commands;
- governance-built claim atoms;
- narrow Mistral wording with verifier/repair/fallback;
- deterministic route authority.

Return to the product roadmap: expose the proven exact Continuity job in
Workbench, ensure development startup enables its existing flags deliberately,
show earned source/render/verifier trace steps, and dogfood `/resume` as a daily
job before attempting semantic route discovery again.

## Safety and Verification

- encoder used a local cached model; no download occurred;
- route changes: 0;
- evidence releases: 0;
- tool authorizations: 0;
- durable writes: 0;
- hidden chain-of-thought or raw failed responses stored: false.
