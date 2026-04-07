# Continuity-Blind Contradiction v2 Plan

Date: April 7, 2026

Status: **Mostly shipped.** Core v2 harness is live. See Shipped section below for delta vs original plan.

---

## Shipped (April 7, 2026)

### Delivered as planned

- Deterministic retrieval via precomputed embedding index (`artifacts/continuity_blind_v2/`)
- Probe-lane analysis over merged topic list (consistency + gaslighting probe topics)
- Semantic continuity detection (explicit + semantic + contradiction-ack layers)
- Typed contradiction classification: `genuine_contradiction`, `framing_variation`, `scope_context_variation`, `temporal_update`, `insufficient_evidence`
- Multi-signal confidence: lexical assertiveness, epistemic posture, advice forcefulness, uncertainty disclosure
- Per-model summary slice
- Manual audit queue (top pairs by risk, stored in `data/chatgpt_gaslighting_v2.db`)
- Static HTML report auto-generated after each run (`docs/labs/continuity-blind-v2-*.html`)
- Token-level heuristic signal overlay in the HTML report

### Added beyond the original plan

**Boundless claim scoring** (`tools/semantic_invariance_probes.py`)

The original plan had no mechanism for flagging claims that exceed their epistemic warrant. A sentence-level scorer was added:
- `PRESCRIPTION_PATTERNS` — detects model advice-giving language
- `SCOPE_GUARD_PATTERNS` — detects conditional framing in the same sentence
- `ABSOLUTE_QUANTIFIER_PATTERNS` — detects always/never/definitely/the-only-way etc.
- `score_boundless_claims(text)` — returns `boundless_risk` (0–1), scoped vs unscoped prescription counts
- Integrated into the HTML report: per-response risk badge (green/amber/red) on each audit pair card

**Semantic invariance probe sets** (`tools/semantic_invariance_probes.py`)

A calibration harness for the classifier. Two probe types:
- `InvarianceProbe` (5 probes): same intent, different surface form — pairs drawn from these should NOT be flagged as genuine contradictions. If they are, the cosine threshold is reacting to phrasing.
- `JustifiedDivergenceProbe` (5 probes): similar surface, genuine context shift — different advice IS correct. If the classifier flags these, it is a false positive.
- Rendered in the HTML report as a "Probe Calibration Reference" section.

All tests pass: `tests/test_semantic_invariance_probes.py` (31 tests).

### Not yet done from original plan

- Discovery lane (topic extraction from corpus, not just hand-authored probe list)
- Full manual adjudication set (audit queue exists but human labeling not done)
- v1 → v2 comparison table published

---

## Purpose

Preserve the original continuity-blind contradiction analysis as `v1`, then build a stricter `v2` that:

- keeps the original corpus and headline problem intact
- improves methodological rigor
- separates contradiction from ordinary variation
- uses newer CRT-era tooling where it genuinely helps
- does not quietly overwrite or retroactively redefine the original result

This is a research upgrade, not a rhetorical cleanup.

## What v1 Established

`v1` is still worth keeping because it established something real:

- corpus exists and is normalized in `data/chatgpt_corpus.db`
- corpus counts are real: `1,275` conversations and `59,370` messages
- stored result DBs exist:
  - `data/chatgpt_consistency.db`
  - `data/chatgpt_gaslighting.db`
- stored summary metrics support:
  - `0.34` mean consistency
  - `74%` mean lexical confidence
  - `0%` regex-detected continuity awareness

What `v1` did not establish cleanly:

- an exhaustive scan of all recurring topics in the corpus
- a semantic continuity detector
- a calibrated confidence metric
- a reliable distinction between contradiction and context-sensitive variation

## v2 Objectives

`v2` should answer these questions better than `v1`:

1. When is a cross-session difference a true contradiction versus a normal shift in context?
2. When does the assistant acknowledge prior stance implicitly, even if it misses the old regex phrases?
3. How much of the observed inconsistency is model-family drift versus user-context drift?
4. Which contradictions are high-impact enough to matter for user decision quality?
5. Can CRT-style continuity and contradiction tooling produce a better measurement layer than `v1` heuristics?

## Non-Negotiable Rules

1. `v1` stays preserved.
   - Do not overwrite the existing result DBs.
   - Do not rewrite old claims as if `v2` was always the method.

2. `v2` must be versioned explicitly.
   - New outputs should be stored separately.
   - New docs should say `v2` clearly.

3. `v2` must keep at least one bridge metric comparable to `v1`.
   - Keep a continuity-awareness style metric.
   - Keep a consistency metric.
   - Keep a confidence/assertiveness metric.

4. `v2` should add rigor before adding cleverness.
   - Determinism and auditability matter more than sophistication.

## Core Method Changes

### 1. Deterministic retrieval instead of random sampling

`v1` sampled:

- `ORDER BY RANDOM() LIMIT 5000`

That makes reruns unstable.

`v2` should:

- precompute or cache embeddings for all assistant messages eligible for analysis
- retrieve by similarity over the full eligible assistant corpus, or a deterministic indexed subset
- use fixed seeds if any sampling remains

Goal:

- exact reruns should be possible

### 2. Separate topic discovery from topic probing

`v1` depends on hand-authored probe lists.

`v2` should keep two lanes:

- `probe lane`: preserve hand-authored recurring topics for comparability
- `discovery lane`: find recurring topics from the corpus automatically

Possible sources:

- conversation titles
- user prompt clustering
- recurring noun phrase / theme clustering
- assistant-response topic clustering

Goal:

- retain comparability to `v1`
- reduce probe-list bias

### 3. Semantic continuity detection instead of regex only

`v1` continuity awareness is phrase-regex only.

`v2` should score continuity in layers:

- explicit continuity:
  - regex / phrase acknowledgment
- semantic continuity:
  - response references prior stance, prior uncertainty, or earlier advice pattern without exact regex markers
- contradiction acknowledgment:
  - response signals change, ambiguity, prior disagreement, or need for reconciliation

Potential leverage from current system:

- `personal_agent/immune_agents/continuity_auditor.py`
- contradiction / ledger language patterns
- drift / variance tooling

Goal:

- continuity should no longer default to false just because the model used different wording

### 4. Distinguish contradiction from context-sensitive variation

Low cosine similarity is not enough.

`v2` should classify cross-session differences into at least:

- genuine contradiction
- framing variation
- scope/context variation
- temporal update
- insufficient evidence / ambiguous

This likely needs:

- rule-based pre-filters
- manual adjudication set
- optionally a second-pass judge model for pair labeling

Goal:

- stop treating all low-similarity pairs as equivalent

### 5. Better confidence measurement

`v1` confidence is lexical assertiveness.

`v2` should separate:

- lexical assertiveness
- epistemic posture
- advice forcefulness
- uncertainty disclosure

Potential leverage from current architecture:

- governance / posture concepts already present in CRT
- contradiction disclosure
- confidence vs continuity principle from Law 6

Goal:

- preserve the useful "sounds certain" signal without pretending it is calibrated probability

### 6. Stratify by model and time

`v1` notices model drift, but not deeply enough.

`v2` should compute:

- per-model-family consistency
- per-time-window consistency
- same-topic stability across model transitions
- same-topic stability within the same model family

Goal:

- distinguish provider/model changes from statelessness as such

### 7. Add human audit for the highest-risk pairs

`v2` should not rely on fully automatic interpretation for the most serious claims.

Create a small adjudication set:

- top 25 or top 50 highest-risk pairs
- label each pair:
  - contradiction
  - not contradiction
  - uncertain
  - harmful contradiction
  - benign variation

Goal:

- ground the strongest public claims in examples that have been manually checked

## Proposed v2 Outputs

### Data products

- `data/chatgpt_consistency_v2.db`
- `data/chatgpt_gaslighting_v2.db`
- `artifacts/continuity_blind_v2/`

### Tables / outputs

- deterministic topic clusters
- contradiction classification table
- continuity-detection table
- per-model summary
- per-time-window summary
- adjudicated high-risk pair set

### Metrics

Keep these for comparability:

- mean consistency
- continuity-awareness rate
- assertiveness/confidence proxy

Add these:

- contradiction rate after semantic filtering
- acknowledged-contradiction rate
- per-model drift score
- harmful contradiction rate on adjudicated set
- temporal update rate versus contradiction rate

## Recommended Delivery Order

Keep `v2` narrow at first. The clean sequence is:

1. Reproduce the original `v1` probe lane on frozen inputs.
2. Replace random retrieval with deterministic retrieval.
3. Add semantic continuity detection without changing the topic list.
4. Add contradiction typing on the retrieved pairs.
5. Add a small manual adjudication set.
6. Only then add discovery-lane topic generation.

This keeps the research story interpretable. If every variable changes at once, you lose the ability to say which improvement mattered.

## Suggested Pipeline

1. Ingest and freeze the corpus snapshot.
2. Build deterministic assistant-message embedding index.
3. Run `probe lane` on the original topic lists.
4. Run `discovery lane` on recurring-topic extraction.
5. Generate cross-thread response pairs.
6. Score each pair for:
   - semantic similarity
   - continuity acknowledgment
   - assertiveness
   - contradiction type
7. Produce a candidate high-risk set.
8. Manually audit the top slice.
9. Publish `v2` summary with explicit comparison to `v1`.

## How CRT Should Help v2

Use current system ideas where they improve measurement rather than decorate it:

- contradiction typing from ledger / contradiction infrastructure
- continuity concepts from the continuity auditor
- drift concepts from variance / drift tooling
- epistemic posture framing from governance

Do not force the whole Aether runtime into this analysis. The goal is a better measurement method, not to entangle the paper with every subsystem.

## v1 to v2 Comparison Template

When `v2` is done, compare it to `v1` like this:

- corpus: same or changed?
- topic selection: probe-only or probe + discovery?
- retrieval: random-sample or deterministic?
- continuity detection: regex-only or semantic?
- contradiction labeling: cosine-only or typed?
- confidence: lexical-only or multi-signal?
- manual audit: absent or present?

Then report:

- what stayed robust from `v1`
- what weakened under stricter method
- what strengthened under stricter method

## Success Criteria

`v2` is successful if:

- it is reproducible
- it preserves comparability with `v1`
- it reduces method ambiguity
- it produces a cleaner set of contradictions that are easier to defend publicly
- it tells you whether the original alarming result was overstated, understated, or mostly correct

## Immediate Next Step

Before writing `v2` code:

1. freeze the `v1` docs and result DBs
2. define the exact `v2` schema and output tables
3. choose whether the first `v2` pass is:
   - deterministic probe-lane only
   - or deterministic probe + discovery

Recommended first pass:

- deterministic probe-lane only

That gives the cleanest comparison against `v1` without overexpanding scope too early.
