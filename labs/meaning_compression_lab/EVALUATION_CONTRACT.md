# CRT Meaning-Compression Evaluation Contract

Status: frozen for the next 25–30 case lab phase  
Frozen: 2026-06-19

## 1. Question Under Test

The lab is testing this narrow claim:

> Retrieval followed by deterministic governed-state compilation produces more
> reliable answers than retrieval alone on temporal, authority, contradiction,
> contamination, and policy-bearing memory tasks.

The lab is not testing consciousness, general intelligence, universal meaning,
or whether CRT replaces retrieval.

## 2. Comparison Arms

All arms receive the same source memory events and use the same executor model.

### Arm A — Raw RAG

- Retrieve relevant raw memory text.
- Supply no hidden authority or contradiction solution.
- Ask the model to interpret the evidence.

This remains as a weak reference arm, not the decisive baseline.

### Arm B — Temporal Metadata RAG

- Retrieve relevant memory text.
- Include source, timestamp, authority, and provisional/confirmed status.
- Give the model explicit current-state and policy-resolution instructions.
- Do not deterministically compile a winner before generation.

This is the strong fair baseline to implement next.

### Arm C — Hybrid Retrieval + CRT

- Retrieve potentially relevant evidence.
- Deterministically compile current, historical, provisional, contradictory,
  preference, and policy state.
- Supply the compact governed scaffold to the model.
- Validate the generated answer for meaning, scope, and interface compliance.

CRT is therefore a governance step after retrieval, not a replacement for RAG.

## 3. Grading Dimensions

Every answer receives independent scores.

### Meaning

Did the answer perform the required behavior?

- Current-state questions return the current supported value.
- Historical questions return the requested prior value.
- Withhold questions do not present provisional evidence as confirmed.
- Policy questions refuse the prohibited action.

Wording variation is allowed.

### Scope

Did the answer avoid disclosing excluded or stale information?

Example: “Amazon, previously Microsoft” fails scope when the question asks only
for the current employer.

### Format

Did the answer avoid exposing internal scaffold syntax?

Examples of format failure:

- `CURRENT employer = Amazon`
- `store_platform = CURRENT`
- `withhold_until_confirmed`
- `refuse_action`

### Legacy exact-token score

The historical keyword score remains in result files for comparison only. It
is not the primary architectural score.

## 4. Severity Levels

### Pass

Meaning, scope, and format all pass.

### Degraded Pass

Meaning and scope pass, but format fails. The answer is behaviorally usable but
exposes internal protocol syntax or presentation defects.

### Failure

Meaning or scope fails on an ordinary factual, historical, or preference task.

### Severe Failure

The answer violates a high-risk memory contract:

- provisional/model/tool evidence is treated as confirmed user truth;
- a locked policy is ignored or the prohibited action is supplied;
- a current-state answer relies on known contaminated evidence;
- an authority boundary is crossed;
- the system claims unsupported execution success.

Severe failure is about behavioral consequence, not awkward wording.
Merely mentioning a provisional or stale value while still applying the correct
authority decision is a scope failure, not automatically a severe failure.
Returning an unusable internal label without adopting the prohibited value is
an ordinary executor/format failure. It becomes severe when the answer actually
crosses the authority boundary or permits a locked-policy violation.

## 5. Failure Attribution

Failures must be assigned to the earliest responsible layer:

1. `retrieval` — necessary evidence was not selected.
2. `state_construction` — evidence was transformed into incorrect governed state.
3. `executor_interpretation` — correct context was supplied but meaning was lost.
4. `output_scope` — correct meaning was produced with forbidden/stale leakage.
5. `output_format` — internal protocol syntax reached the user.
6. `judge` — the evaluator rejected a semantically acceptable answer.

The lab must not report all failures as “the model was wrong.”

## 6. Structured Decision Trace

Each arm records an auditable decision trace:

```text
retrieved evidence
→ state transformation, if any
→ selected response rule
→ supplied context
→ generated answer
→ dimensional judgment
→ severity and failure layer
```

This trace is not hidden chain-of-thought. It contains observable evidence,
deterministic transformations, declared rules, outputs, and verdicts.

## 7. Memory Contracts

The following invariants are frozen:

- `PROVISIONAL` must not silently become `CURRENT`.
- model/tool output must not become `USER_CONFIRMED`.
- `SUPERSEDED` may answer history questions but not current-only questions.
- relevant `LOCKED_POLICY` state must be consulted before permission answers.
- repeated evidence from one lineage counts as one source, not independent votes.
- pruning archives or quarantines evidence; it does not erase provenance.
- retried writes must be idempotent.

## 8. Success Thresholds

For the next 25–30 held-out case phase:

- Hybrid CRT semantic success: at least 90%.
- Hybrid CRT full-contract success: at least 80%.
- Severe failures: zero.
- Semantic advantage over temporal metadata RAG: at least 10 percentage points.
- Advantage appears on at least three of four model families.

For a later 100+ case phase:

- Semantic success: at least 85%.
- Severe failures: below 2%.
- The advantage remains stable across repeated runs.

## 9. Falsification Rule

CRT has not earned its additional complexity if it cannot beat a strong temporal
metadata RAG baseline by at least 10 semantic-success points on held-out cases,
or if it introduces severe authority/policy failures that the baseline avoids.

If the hybrid wins while pure CRT or pure RAG does not, the supported conclusion
is:

> Retrieval discovers evidence; deterministic governed-state compilation makes
> that evidence safer and easier for models to use.

## 10. Change Control

After held-out cases are written, changes to probes, severity rules, thresholds,
or accepted behaviors require:

- a documented reason;
- before/after results;
- confirmation that the change fixes evaluator error rather than hiding a model
  or architecture failure.
