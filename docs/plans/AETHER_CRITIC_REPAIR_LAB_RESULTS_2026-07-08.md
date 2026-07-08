# Aether Critic Repair Lab Results - 2026-07-08

## Question

Can a local model improve Aether's abstract/governed synthesis more reliably as
a bounded critic than as the primary answer writer?

## Scope

Lab:

```text
D:\AI_round2\labs\critic_repair_lab
```

Result artifact:

```text
D:\AI_round2\labs\critic_repair_lab\results\critic_repair_lab_v2.json
```

The prompt set is intentionally abstract but directed at real risks:

- scoring meaning without turning scores into truth
- competing memories that could harm the user
- correctness versus epistemic integrity when governance is wrong
- sensitive GPT/archive history as evidence, not identity truth
- mempalace / contradiction / meaning weight
- stronger model routing without outsourcing authority

## Result

First pass:

```text
raw:             0/6, avg 0.2052
governed_draft:  0/6, avg 0.3157
critic:          2/6, avg 0.7187
governed_repair: 6/6, avg 0.8177
```

Hardened v2 pass:

```text
raw:             0/6, avg 0.2083
governed_draft:  0/6, avg 0.3288
critic:          6/6, avg 0.9093
governed_repair: 6/6, avg 0.8519
```

Verification:

```text
python labs\critic_repair_lab\critic_repair_lab.py --output critic_repair_lab_v2.json
python -m pytest tests\test_critic_repair_lab.py -q
8 passed
```

## Read

The useful pattern is not "ask the model to solve the abstract problem."

The useful pattern is:

```text
governed draft -> bounded critic rubric -> governed repair contract -> final
```

Raw answers drift generic. Governed drafts stay closer to Aether but can be too
thin or under-specified. The critic pass is good at identifying missing
dimensions such as staleness, source authority, review state, contradiction,
risk boundaries, and implemented-vs-conceptual separation. The repair only
works when governance treats the rubric as a contract rather than letting the
critic become authority.

The v2 hardening pass addressed the strongest critique of the first result:
the evaluator could reward dimension-name inclusion more than case-specific
reasoning. Repairs now have hard gates for directness, risk handling, grounded
examples where required, case specificity, and forbidden patterns in an
endorsing stance. Critic mode now has role-specific metrics:
`performed_role`, `found_required_gaps`, `repair_relevance`, and
`false_positive_rate`.

The result remains proof-of-direction, not proof that the product should wire
this broadly yet. The clean claim is narrower: in this abstract governance
pack, bounded critique plus governed repair is much more reliable than asking
the same local-style answer path to synthesize the final answer directly.

## Product Implication

This supports a future Workbench architecture for abstract/high-risk synthesis:

```text
intent packet
-> governed draft
-> critic rubric over public answer only
-> allowed critique filter
-> governed repair
-> trace-visible final
```

Do not wire this broadly yet. Next useful step is a narrow live/Ollama version
on 3-4 prompts to see whether a local model critic produces useful findings
without adding too much latency or generic critique.

## Safety Boundary

The lab stores only public critique/rubric signals.

No raw hidden chain-of-thought is stored.
No memory, support, reflection, or policy writes are performed.
Critic findings are review-only inputs, not truth.
