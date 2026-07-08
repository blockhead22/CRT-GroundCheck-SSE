# Critic Repair Lab

This lab tests whether a local model is more useful as a bounded critic than as
the primary answer writer for Aether's abstract/governed synthesis prompts.

The lab compares:

- `raw`: generic model-style answer
- `governed_draft`: current Aether-ish governed answer
- `critic`: role-specific rubric findings against the governed draft
- `governed_repair`: deterministic governed repair using allowed critic findings,
  followed by post-repair critique

The evaluator is intentionally stricter than the first pass:

- critic mode is scored on whether it finds useful repair constraints, not
  whether it answers the original prompt
- repaired answers must directly answer the prompt when the prompt asks a direct
  question
- risk-focused prompts must include risk handling
- forbidden pattern checks are stance-aware, so "avoid automatic writes" is not
  treated as endorsing automatic writes
- post-repair findings are labeled separately from pre-repair findings
- template-ish dimension naming is penalized when it is not applied to the case

The prompts are intentionally abstract but risk-directed: meaning scoring,
competing harmful memories, correctness vs epistemic integrity, sensitive archive
history, mempalace/contradiction weight, and frontier-model authority boundaries.

Safety contract:

- no raw hidden chain-of-thought storage
- no memory writes
- no support/reflection writes
- no policy mutation
- critic findings are review-only inputs

Run:

```powershell
python labs\critic_repair_lab\critic_repair_lab.py
python -m pytest tests\test_critic_repair_lab.py -q
```
