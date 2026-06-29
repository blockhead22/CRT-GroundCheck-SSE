# Local Router Replay v0 Report - 2026-06-28

## Purpose

This replay checks whether the Aether local-router idea is more than prompt
tasting. It compares raw local-model answers against routed answers using:

1. request classification
2. model/profile routing
3. semantic-spine or section-lock scaffolds
4. CRT-style verifier grading
5. one repair pass when needed

The pack was built from ChatGPT export logs, with secrets and IP-like values
redacted. The pack is useful as a first real-log stress test, but it still needs
human curation before it becomes grant/report evidence.

## Replay Pack

Pack:

```text
labs/meaning_compression_lab/replay_packs/local_router_replay_v0.json
```

Current pack shape:

```text
16 total cases
4 architecture_synthesis
4 personal_synthesis
4 grant_business
4 code_reasoning
```

The 12-case replay used architecture, personal synthesis, and grant/business
cases. Code reasoning was left for a separate pass because that bucket is still
the noisiest.

## Latest 12-Case Result

Raw baseline:

```text
Pass: 0/12
Average score: 0.405
```

Routed local path, after verifier false-positive fix and rescore:

```text
Pass: 10/12
Average score: 0.761
Average delta: +0.356
Repairs used in original run: 5
Fallbacks: 0
```

The saved run artifact is:

```text
labs/meaning_compression_lab/results/local_router_replay_1782692982.json
```

That JSON was produced before fixing the negated "not a network router" judge
false positive. The rescored result above reflects the corrected verifier.

## Remaining Failures

`gptlog_005_personal_synthesis`

- Routed score: `0.570`
- Problem: the answer became generic founder advice.
- Meaning: personal synthesis needs stronger memory receipts and less generic
  business/founder framing.

`gptlog_010_grant_business`

- Routed score: `0.735`
- Problem: it used "guaranteed results" language in a risky way.
- Meaning: grant/business answers need stricter language around outcomes,
  promises, and measurable claims.

## What Worked

The useful mechanism is not "bigger model equals deeper answer." The useful
mechanism is:

```text
classify request -> build Mirus packet -> choose scaffold -> render with model
-> verify -> repair
```

The strongest visible structure remains:

```text
Receipts
Pattern
Limits
Next Useful Move
```

The Mirus/Holden language works best as internal architecture:

```text
Mirus: evidence, belief state, authority, contradiction boundaries
Holden: final voice/rendering layer
CRT: verifier for overclaim, drift, unsupported claims, and weird symbolic misuse
```

## Roadmap Decision

This work is worth continuing if it stays attached to Aether/Core as validation
infrastructure. It should not become a separate chatbot side quest.

One new requirement comes out of the Activity/Thinking screenshots: the router
should persist durable thinking traces. This does not mean storing raw hidden
chain-of-thought. It means storing inspectable trace artifacts:

```text
request classification
retrieved memories / past-chat references
Mirus packet summary
chosen model and scaffold
verification failures
repair/fallback decisions
confidence and contradiction notes
learning candidates created from the turn
```

After restart, Aether should be able to reopen a historical message and show why
the answer happened: what it remembered, what it inferred, what it refused to
claim, and what the system learned or flagged for review.

Classify this phase as successful when:

```text
1. A curated 30-50 case replay pack exists.
2. Routed local answers beat raw local answers by at least +0.20 average score.
3. Routed pass rate clears 70% on curated cases.
4. Repairs fix more failures than they introduce.
5. The judge catches unsupported claims without over-flagging explicit negations.
6. At least one Aether UI or CLI request path can call the router and log traces.
7. Historical messages can reload their trace summaries after restart.
```

Bring it forward into the main roadmap only after the router survives:

```text
exact memory questions
personal synthesis
grant/business framing
architecture explanation
creative-production planning
code/repo reasoning
multi-turn correction
```

## Next Move

The next useful step is not more model shopping. It is curation:

```text
1. Manually review the 16-case replay pack.
2. Remove quoted assistant artifacts and vague non-requests.
3. Expand to 30-50 clean real prompts.
4. Run raw vs routed across the full pack.
5. Promote the router into a real Aether CLI/app request path only if the lift
   holds.
```

## Tangent Policy

Do not leave viable options behind, but keep the lab pointed at roadmap exit.

Worth exploring if discovered:

```text
trace reload proof
cleaner replay curation
failure taxonomy
same-scaffold model comparison
learning-candidate extraction from verifier failures
Workbench Activity/Trace schema mapping
```

Not high leverage right now:

```text
new hardware shopping
more random model downloads
persona-only tuning
internal-thinking speculation
huge context-window tests before retrieval discipline
polished UI before trace/reload proof
```

Current evidence read:

```text
The lab supports the governance path. It does not show local models competing
with frontier models globally; it shows governed external cognition improving
raw local chat for Aether's use case.
```
