# Aether Continuity Renderer Eval - 2026-07-10

## Question

Can a small local model turn a governed Continuity packet into natural prose while correctly binding every rendered claim to evidence receipts?

## Design

Three local models were tested on the same frozen Resume packet:

- `qwen2.5:7b-instruct`
- `gemma3:latest`
- `mistral:latest`

Each model ran in two modes:

- direct receipt IDs;
- compact evidence aliases with deterministic alias-to-receipt resolution.

The evaluator stored only schema/fidelity/format/latency scores, verifier findings, fallback state, and answer hashes. Raw failed drafts were not stored.

## Sparse Fixture Result

Artifact: `labs/meaning_compression_lab/results/continuity_renderer_eval_1783696849.json`

- Qwen2.5 direct receipts passed after one repair.
- Mistral direct receipts passed without repair.
- Alias mode did not pass for any model.

Mistral then repeated the sparse direct-receipt case 3/3 without repair at roughly 4.6 seconds warm. Its answer was concise, natural, source-bound, and properly labeled.

This did not generalize to a real noisy worktree packet. The product-shaped check fell back after verifier failure.

## Representative-Density Result

The frozen fixture was expanded to match the model-facing production density: three recent items, five workspace changes, confirmed project context, and a separately receipted next candidate.

Artifact: `labs/meaning_compression_lab/results/continuity_renderer_eval_1783697176.json`

Result: **0/6 graduated**.

Common failures:

- receipt attached to the wrong claim;
- required workspace-change or next-candidate evidence omitted;
- rendered section insufficiently supported by the claim ledger;
- Mistral direct mode invented unknown receipt IDs and exposed receipt IDs in prose;
- repair often improved wording but did not reliably repair evidence binding.

Alias mode reduced prompt size and latency but did not improve source fidelity.

## Decision

Do not graduate a local Continuity renderer from this packet contract. Do not enable natural-language Continuity routing. Keep deterministic fallback.

The failed contract asks one small model to do too many epistemic jobs simultaneously:

1. select the important packet facts;
2. summarize them naturally;
3. preserve subtype coverage;
4. distinguish observed facts from inferred candidates;
5. bind every claim to the correct receipt;
6. obey a structured output schema.

The next narrow architecture should move fact selection and receipt binding out of the model:

```text
governance selects one where atom + receipts
governance selects one changed atom + receipts
governance selects one next-candidate atom + receipts
model renders each fixed atom into natural prose
verifier checks each rendered section only against its fixed atom
one repair
fallback
```

This preserves model voice without making the model the evidence authority. It is also closer to the project thesis: governance holds truth-status and structure; the model supplies language.

## Verification

- alias round-trip and frozen-fixture tests pass;
- raw failed drafts remain absent from artifacts and traces;
- no live Memory, Support, Reflection, belief, or policy state was changed;
- the automatic Mistral preference was withdrawn after the real packet failed.

## Claim-Atom Result

The failed receipt-selection contract was replaced for exact Continuity commands
with a governance-built claim-atom contract:

```text
governance selects one where proposition + fixed receipts
governance selects one changed proposition + fixed receipts
governance selects one inferred next proposition + fixed receipts
model sees propositions and states, but no receipt IDs
model renders wording only
governance restores fixed claim bindings in the trace
verifier rejects omission, cross-atom borrowing, invented completion/intent,
receipt exposure, unrelated context, and bare packet fragments
one failure-delta repair -> deterministic fallback
```

Artifact: `labs/meaning_compression_lab/results/continuity_atom_renderer_eval_1783698011.json`

Representative-density result under the stricter naturalness gate:

| Model | Result | Latency | Repair | Main signal |
| --- | --- | ---: | --- | --- |
| `qwen2.5:7b-instruct` | fallback | 2.900s | failed | Repeated the raw `M aether/sidecar/app.py` atom instead of rendering prose. |
| `mistral:latest` | graduated | 2.118s | none | Preserved all three fixed atoms as natural source-bound sections. |

A second smoke built from the real dirty `aether-core` worktree reproduced the
result: Qwen fell back; Mistral passed first render in 2.036 seconds with all three
governance-owned claim bindings. No receipt ID entered either model prompt, and no
raw draft was stored.

### Decision

- Exact `/where`, `/changed`, `/next`, and `/resume` model rendering now uses the
  claim-atom contract when the existing model-render feature flag is enabled.
- `mistral:latest` is the preferred atom renderer when installed; an explicit
  `AETHER_CONTINUITY_RENDER_MODEL` override still wins.
- Natural-language Continuity routing remains disabled.
- Deterministic rendering remains the fallback after one failed repair.
- This does not graduate Mistral as a general Aether model. It graduates one
  narrow job: wording governance-selected Continuity atoms.
