# Aether Mirus Semantic Task Intake Lab

**Date:** 2026-07-20

**Decision:** Promising research result; no live integration.

## Question

Can a small local model notice indirect tasks and constraints that Aether's
deterministic intake misses, while CRT validation preserves speaker,
commitment, evidence, and authority boundaries?

## Mechanism Tested

```text
user text
-> deterministic intake baseline
-> qwen2.5:7b-instruct structured semantic proposal
-> exact source-receipt requirement
-> deterministic category, speaker, modality, and negation checks
-> review-only candidate contract
-> hybrid merge with deterministic candidates taking precedence
```

The model never creates task authority. Accepted candidates remain
`unconfirmed`, require review, block task and memory writes, authorize no tools,
and derive their displayed summary from the exact user receipt rather than the
model's paraphrase. Raw model responses and hidden chain-of-thought are not
stored.

## Evidence

Development pack, 32 cases:

```text
deterministic baseline  precision 1.0000  recall 0.2857  F1 0.4444
semantic proposer      precision 1.0000  recall 0.7143  F1 0.8333
governed hybrid        precision 1.0000  recall 0.7619  F1 0.8649
high-risk false positives 0
authority-contract violations 0
```

First holdout initially exposed nine high-risk false proposals. Speaker and
modality validation was strengthened. The repaired first holdout then reached:

```text
24 cases
precision 1.0000
recall 0.9167
high-risk false positives 0
authority-contract violations 0
```

That repaired pack is post-reveal evidence, not generalization evidence.

Untouched second holdout:

```text
20 cases
deterministic baseline  precision 1.0000  recall 0.1000
semantic/hybrid        precision 0.7143  recall 1.0000  F1 0.8333
false positives 4
high-risk false positives 3
authority-contract violations 0
```

The three high-risk misses were a no-obligation statement, an example labeled
as an example, and an obligation attributed to another person. One additional
false proposal treated `after dinner` as a standalone schedule constraint.

Artifacts:

```text
labs/meaning_compression_lab/results/semantic_task_intake_qwen25_7b_v0_final.json
labs/meaning_compression_lab/results/semantic_task_intake_qwen25_7b_holdout_v1.json
labs/meaning_compression_lab/results/semantic_task_intake_qwen25_7b_holdout_v1_postfix.json
labs/meaning_compression_lab/results/semantic_task_intake_qwen25_7b_holdout_v2.json
```

## What This Says About Mirus

The useful part of the original Mirus idea is credible: a small model can find
latent task meaning that literal rules miss. The unsafe part is also clear:
model-authored `subject=user` or `this is a task` labels are not authority.
Several failed outputs correctly mentioned `customer`, `father`, `checklist`,
or `hypothetical` in their public rationale while still classifying the text as
the user's task.

The architecture therefore matters more than the classifier score:

```text
model notices
deterministic governance verifies
human review grants authority
```

Review-only containment worked: every run had zero authority-contract
violations even when semantic classification was wrong. That supports the
governance thesis, but the false-candidate rate blocks product use.

## Live Change

No semantic proposer was wired into `create_app`, the public trace, Workbench,
or the learner queue. The live deterministic intake received only two narrow
safety repairs discovered by the development pack: quoted-note and
planner-example language no longer creates candidates.

## Reopen Gate

Do not continue prompt tuning against these packs. Reopen only for a stronger
speaker/modality mechanism, such as a clause-aware typed parser or a separately
trained boundary classifier, followed by another untouched holdout. The gate
remains:

```text
zero high-risk false positives
zero authority-contract violations
material recall improvement over deterministic intake
no silent writes or queue insertion
```
