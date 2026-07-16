# Aether Model Boundary Checkpoint - 2026-07-15

## Question

Can the current local renderers preserve evidence ownership and several bound
roles after governance has already selected the facts, or is model capability
now the limiting layer?

## Harness fixes completed first

- RAG evidence is owner-labeled before generation. `user:` passages are rendered
  as second-person propositions rather than raw `My ...` sentences.
- User-owned evidence activates a buffered post-render ownership check. A rejected
  draft is not streamed or stored; one failure-delta repair runs, then a bounded
  attribution-safe fallback.
- Identity composition recognizes structural builder clauses such as `who is
  making this system` and supplies the grounded atom that Nick Block is Aether's
  builder and primary user.
- Public Thinking exposes that user-owned evidence was bound before render.

Exact regression result: 91 focused RAG, character, evaluator, and sidecar tests
pass. The observed marigold draft was quarantined and only its corrected answer
was streamed.

## Frozen local comparison

Artifact:

```text
D:\AI_round2\aether-core\.eval-runs\model_boundary_eval_2026-07-15.json
```

Command:

```powershell
python -m scripts.model_boundary_eval `
  --output .eval-runs/model_boundary_eval_2026-07-15.json
```

The three fixed jobs were owner-safe daily advice, identity plus builder, and
identity plus two user facts plus an ownership explanation. Governance selected
the facts and owners; the model supplied wording and received at most one repair.

| Model | First pass | Final pass | Total latency |
|---|---:|---:|---:|
| qwen2.5:7b-instruct | 1/3 | 2/3 | 16.73 s |
| mistral:latest | 2/3 | 2/3 | 12.96 s |
| qwen3:14b | 2/3 | 2/3 | 84.59 s |

All three passed owner-safe daily advice. Mistral was the cleanest simple
renderer. All three failed the multi-clause ownership weave after repair: they
omitted or misbound model-as-voice, memory-as-self, or requested user facts.
Qwen3 added no final-pass advantage and was substantially slower.

The evaluator checks role relationships, not merely vocabulary. It rejects
outputs such as `Voice is the builder` even when every required noun is present.

## Decision

This establishes a local-renderer boundary for this packet shape. It is not
enough to silently switch Aether to a frontier model. The next experiment is a
shadow-only frontier ceiling using these exact frozen packets, grader, and
one-repair limit. The frontier model may word or critique an answer but receives
no authority over evidence release, memory, tools, writes, routes, contradiction
state, or policy.

If a frontier renderer reliably reaches 3/3 with acceptable latency and natural
prose, provider routing becomes justified for high-composition turns. If it also
fails, the remaining defect is packet/repair architecture rather than local
model size. Simple grounded jobs should remain local either way.

## Known adjacent debt

An expanded test invocation produced 142 passing and 11 failing tests in
`tests/test_sidecar_app.py`. Those failures expect the older monolithic local
prompt while the active RAG-default path uses model voice. They were not fixed by
reverting the current architecture and should be reconciled as explicit legacy
expectations in a separate test-contract cleanup.
