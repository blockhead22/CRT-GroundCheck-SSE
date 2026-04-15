---
name: plan_aether_bench_v0
description: Detailed goal-oriented plan for Aether Bench v0 — the week-long lab to prove the substrate matters. Descriptive per-step rationale, success criteria, and push-further paths.
type: plan
date: 2026-04-15
supersedes_partial: plan_2026_04_15_lab_week.md
window: 7 days (2026-04-15 → 2026-04-22)
originSessionId: 687eb415-8a05-49fd-922f-f876d7150297
---

# Aether Bench v0 — The Plan

## Why this week exists

Everything we've built for the past year — the belief dependency graph, the
fidelity mirror, the cascade preview, the MCP substrate, the governance gate,
the sanction layer — is *plausible*. It looks sensible. It demos well. But
nobody outside this room has reason to believe it improves anything.

This week's job is to produce **one chart + one honest writeup** that moves
Aether from "plausible" to "measured." If the substrate works, the chart is
the pitch. If it partially works, the chart shows *where* it works and we
position around that. If it doesn't work, we've spent a week and learned
something real — which is cheaper than spending another year on a story we
can't defend.

The chart is the deliverable. Not a paper. Not a demo. Not a README. A chart.

## What we're testing — THREE claims, not one

Most "does the substrate help" questions collapse into one claim. Ours has
three, each with a different business implication. The week must separate
them cleanly, because muddling them gives a single number with no narrative.

### Claim 1 — Does the substrate measurably help at all?

**Question:** Same brain, same task, two arms (Cold = brain alone; Warm =
brain + Aether MCP substrate). Does Warm beat Cold on tokens, correctness,
tool-call count, or wall time?

**Why it matters:** This is the baseline. If Warm doesn't beat Cold, nothing
else in this plan matters. Everything downstream assumes claim 1 holds.

**How we prove it:** 15+ paired tasks. Each task runs in both arms on the
same brain. Paired t-test on token cost. Sign test on correctness. Blind
LLM-judge scores correctness without seeing which arm produced the answer.

**Success looks like:** statistically meaningful token reduction (say, 20%+)
AND non-worse correctness, OR correctness gain at equal tokens. Either is a
win. Both together is the dream.

**Failure modes we need to be honest about:** Warm uses the substrate tools
but *hurts* because tool call overhead > information gain. Or Warm is a wash
because the task doesn't actually need memory. Both are real results.

### Claim 2 — Does it hold across brain size / vendor?

**Question:** Does the Cold-vs-Warm *gap* change as brain capability grows?

**Why it matters:** This decides the positioning.
- Gap shrinks as brains get stronger → "Aether is a crutch for weak models."
  Real product, but ceiling'd at sub-frontier.
- Gap stays flat → "Aether is a universal substrate." Bigger TAM.
- Gap *grows* with stronger brains → "Aether unlocks frontier capability
  otherwise inaccessible." Biggest story, hardest to prove.

The shape of that curve is the pitch. One data point can't tell us; three
tiers can.

**How we prove it:** Same 15+ tasks, run on three brain tiers.
- Small tier: Qwen2.5-7B-Instruct on TPU v5e. 7B class, weak but cheap.
- Large tier: Qwen2.5-Coder-32B or Llama-3.3-70B on TPU v4 / larger v5e pod.
- API tier: gpt-4.1 via OpenAI, claude-opus via Anthropic, optionally
  CookieBrain (leaked-session Claude) for the "what if you're on the
  consumer-plan escape hatch" angle.

Three tiers × two arms = six conditions. 15 tasks each = 90 trials minimum.

**Success looks like:** a chart where the Warm bar is shorter (tokens) and
taller (correctness) than Cold at every tier, and we can *interpret* the
slope honestly.

**Failure modes:** Warm wins on small, vanishes on API tier → the frontier-
model hypothesis dies. Warm wins nowhere → claim 1 failed. Warm wins only
on API tier → substrate is a top-end differentiator, not a rescue pad.

### Claim 3 — Does persistence across brain swaps actually pay off?

**Question:** If we run turn 1 on brain A and turn 2 on brain B, can brain B
answer correctly using the belief state that brain A wrote to Aether — state
that would not be inferable from the user's turn-2 message alone?

**Why it matters:** This is the deepest differentiator. "The model is the
mouth, persistence is the self." Every other vendor's context is per-model
and per-session. Aether's state survives the swap. If claim 3 holds, we're
selling something nobody else has. If it doesn't, Aether is "prompt caching
with extra steps."

**How we prove it:** A new task category — `continuity` — with 3–5
multi-turn scenarios. Shape:
- Turn 1: user gives brain A a piece of information that will only be
  relevant later. (E.g. "by the way, we're freezing merges after Thursday.")
- Turn 2: (with brain *swapped* to B) user asks a question that requires
  turn-1 info to answer correctly. (E.g. "should I merge this PR Friday?")
- Success metric: does B recall and apply the turn-1 fact *without* the user
  restating it?

Cold arm: B gets no Aether access — just the turn-2 message. Baseline should
be "B has no idea."
Warm arm: B queries Aether at turn 2, finds the turn-1 fact, applies it.

**Success looks like:** Cold correctness near zero. Warm correctness high.
The bigger that gap, the louder the persistence claim.

**Failure modes:** Warm B fails to *query* Aether unless instructed (i.e.
organic tool-use is weak). Warm B queries but Aether doesn't surface the
right memory (retrieval is bad). Cold accidentally works because the turn-2
message is more leading than we thought (bad task design).

**This category is NOT in the current tasks.json.** Day 1 addendum: add 3
continuity tasks before D2 starts.

## What NOT to test this week

- Fine-tuning. (Per Nick: "don't give a flying fuck about training right now.")
- `aether-bench` as a public open-source benchmark. First we need our own
  result; then we open-source the harness.
- New MCP tools. The 32 tools shipped at `0bd0213d` are the set.
- Electron polish, frontend work, UX.
- LLM fallback for done-check (worthwhile, but not this week).
- More than 3 brain tiers. The matrix is tight enough as is.

## Day-by-day — what we do, and why each step matters

### Day 1 (Wednesday 2026-04-15) — plumbing

**Goal:** harness end-to-end on a stub brain. No real LLM calls.

**Done already this session:**
- `labs/aether_bench/tasks.json` — 15 paired tasks across search/recall,
  cross-file, audit, governance.
- `labs/aether_bench/harness.py` — Cold/Warm runner, SQLite persistence,
  stub brain, smoke-test entrypoint.
- `labs/aether_bench/judge.py` — blind judge with stub scoring and a slot
  for a real LLM-judge.
- `labs/aether_bench/report.py` — markdown + PNG aggregation with paired
  t-test on tokens and sign test on correctness.
- Smoke test verified end-to-end: trial → judgment → chart.

**Remaining D1 work:**
1. Add `continuity` category to `tasks.json`. 3 scenarios, 2 turns each.
2. Harness needs multi-turn support: a task can declare `turns: [...]`, and
   optionally a `swap_brain_after_turn: N` directive so turn N+1 runs on a
   different brain. This is a small additive change — existing single-turn
   tasks remain untouched.
3. Aether side-task: fix the `source: mcp_client` whitelist in
   `/api/memory/store` so the MCP `aether_remember` tool stops 400'ing.

**Why it matters:** the plumbing is the scaffold everything else rides on.
If the harness is flaky we'll spend D3-D7 debugging infrastructure instead
of analyzing results.

### Day 2 (Thursday 2026-04-16) — small brain, first signal

**Goal:** first real chart — Cold vs Warm on Qwen2.5-7B.

**Steps:**
1. Spin up `aether-tpu-1` on v5e in a TRC-free zone (europe-west4-b or
   us-west4-a). Spot, cheapest. Boot disk 150 GB (model + workspace).
2. Install vLLM + Qwen2.5-7B-Instruct on the TPU VM. Expose OpenAI-compatible
   HTTP endpoint on port 8000. Keep ssh open for monitoring.
3. Back on local rig, add `TpuBrain` to harness as a BrainProvider. It hits
   `http://<tpu-ip>:8000/v1/chat/completions`. No keys go to the TPU.
4. Run all tasks × both arms × Qwen7B. 15+ × 2 = 30+ trials.
5. Run `judge.py` and `report.py`. First chart on disk.

**Why it matters:** first real number. If Warm doesn't beat Cold even on the
weakest brain, we have a big problem and re-plan D3 onwards.

**Infra cost check:** TPU chips free under TRC. Pay: ~$5 boot disk + near-zero
egress. Inside $300 credit by four orders of magnitude.

### Day 3 (Friday 2026-04-17) — large brain

**Goal:** second chart — Cold vs Warm on 32-70B class.

**Steps:**
1. Spin up `aether-tpu-2`. v4-32 on-demand in us-central2-b (free under TRC,
   and on-demand avoids preemption at critical moment). Boot disk 250 GB.
2. Install vLLM with Qwen2.5-Coder-32B. If v4 HBM supports it, swap to
   Llama-3.3-70B instead (bigger is more convincing).
3. Register `TpuLargeBrain`. Rerun all 30+ trials.
4. Aggregate. Now we have a 2-tier chart. Compare slopes: small vs large.

**Why it matters:** this is the first data point for claim 2 (does it hold
across brain size). If Warm's advantage *grew* from small to large, that's
our loudest story. If it *shrank*, we learn that Aether is a crutch.

### Day 4 (Saturday 2026-04-18) — API tier

**Goal:** third chart — Cold vs Warm on top-shelf API brains.

**Steps:**
1. Run gpt-4.1 via OpenAI (cloud_openai brain, already wired). 30+ trials.
2. Run claude-opus via Anthropic API. 30+ trials.
3. Optionally, run CookieBrain for "consumer escape hatch" story. 30+ trials.
4. Aggregate. Now the chart has 3–4 tiers.

**Why it matters:** completes claim 2. Frontier brains either show the gap
persisting or they don't. Either answer is publishable — one is a better
story than the other, but honesty is the asset.

**Cost check:** OpenAI gpt-4.1 at ~$5/Mtok, ~30 trials × 15 tasks × ~2k
tokens average = ~1M tokens. ~$5 OpenAI, ~$10 Anthropic. Budget cap: $50.

### Day 5 (Sunday 2026-04-19) — aggregate, interrogate weak spots

**Goal:** make sense of the data, not just display it.

**Steps:**
1. Full aggregate report: tokens, correctness, wall time, tool-call count
   per (brain × arm × category). Paired t, sign test.
2. Identify the weakest result. Pull trial logs. Ask: when did Warm not
   help, and why? Four common failure modes to check for:
   - Task didn't actually need memory (bad task design).
   - Brain didn't call substrate tools organically (Warm reduced to Cold).
   - Substrate returned wrong memory (retrieval bug).
   - Substrate returned right memory but brain ignored it (grounding bug).
3. Categorize each failure. This goes in the writeup as an honest section.

**Why it matters:** the failure analysis is what separates this from a
standard benchmark paper. Everyone publishes aggregate wins. Explaining
where and why the method breaks is what makes the result trustworthy.

### Day 6 (Monday 2026-04-20) — second pass + writeup

**Goal:** tightened chart, draft writeup, one extra codebase if time.

**Steps:**
1. Rerun any condition with clean-up issues from D5 analysis (mid-trial
   error, judge flakiness, etc).
2. Optional: run a subset on a second repo (httpx or pydantic) to show the
   result isn't codebase-specific. Even 5 tasks × 3 brains is useful signal.
3. Draft `docs/aether_bench_v0_results.md`. Sections: methodology, raw
   results, statistical analysis, failure modes, limitations, next steps.

**Why it matters:** the writeup forces us to say out loud what the chart
actually shows. If we can't articulate the claim in prose, the chart isn't
ready.

### Day 7 (Tuesday 2026-04-21) — decision day

**Goal:** decide Aether's positioning for the public pitch based on data.

**Three possible outcomes, each with a pre-committed response:**

1. **Substrate clearly wins across all tiers.** → Ship the chart. Schedule
   the PyPI publish for next week. Open-source the harness as aether-bench.
   Start drafting the public post. The pitch is: "measurable belief
   substrate, works across brains."

2. **Substrate wins on some tiers, weak on others.** → Publish honestly.
   Chart includes the honest slope. Position around *where* it wins —
   probably weaker or cheaper brains, or continuity tasks specifically.
   The pitch becomes narrower but still real.

3. **Substrate doesn't measurably help.** → Publish the negative finding.
   Decide whether to (a) fix the substrate (retrieval bug? grounding bug?)
   or (b) pivot the project. Either way, we don't keep telling the story
   for free — we spent 7 days, got a number, and the number drives the
   next decision.

**Why it matters:** pre-committing to the decision matrix means we can't
retroactively re-interpret weak results as wins. Every serious lab does this.

## If it works — push further

User asked: "if it works and we prove things. can we push it further?"

Yes. Here's the realistic push-further ladder, in order of cost:

### Push 1 — cross-codebase generalization (cheap, ~2 days)
Run the same harness on 3–5 non-Aether codebases (httpx, pydantic, fastapi,
something in Go, something in a language Aether has no prior context on).
Does the win hold when Aether has to build state from scratch on unfamiliar
code? This hardens the "universal substrate" claim.

### Push 2 — multi-turn depth (medium, ~3-5 days)
Extend continuity tasks from 2 turns to 5+. Does Aether's advantage grow
with conversation length? Expected yes — claim 3 should compound.

### Push 3 — public benchmark release (medium, ~1 week)
Open-source `aether-bench` as a standalone repo. Pin tasks. Publish
a leaderboard. Let others submit brain-substrate pairs. This is the
"establish the category" move.

### Push 4 — Aether vs other substrates (expensive, weeks)
Run the same harness with Mem0, LangMem, LlamaIndex MemoryBuffer, raw
prompt caching — any competing substrate. Pair each substrate with each
brain tier. This is a much bigger chart and a much stronger claim ("Aether
measurably beats other memory substrates across brains"). Needs us to not
cheat on our own benchmark — we'd want to hold out the task pool during
development and only reveal it when measuring.

### Push 5 — adversarial / evolving tasks (expensive, weeks)
Auto-generate tasks that specifically target known failure modes of naive
memory systems (temporal contradiction, contested facts, domain drift).
This is where CRT's cascade and contradiction machinery should win biggest.
Turns the benchmark into a *test of substrate intelligence*, not just
memory-hit-rate.

### Push 6 — paper-quality (expensive, months)
Full ablation, multiple judges, human-eval subset, statistical rigor
(bootstrapped CIs, effect sizes, not just t-stats), submit to a workshop.
By this point we'd want someone else in the field to co-sign the result.

## First action of D1 remainder

1. Add `continuity` category to `labs/aether_bench/tasks.json` — 3 scenarios,
   2 turns each, with `swap_brain_after_turn: 1`.
2. Extend `harness.py` to support multi-turn tasks and mid-task brain swap.
3. Flag the Aether `source: mcp_client` whitelist bug as a side task.

Then D2 opens with a clean harness and a real chart to chase.

## One-paragraph carry

Three claims — does the substrate help, does it hold across brain size, does
persistence across swaps pay off. One chart as deliverable. Three brain
tiers, two arms, 15+ paired tasks with continuity additions. Pre-committed
decision matrix on day 7. Push-further ladder sized in weeks, not months.
Week-one cost fits in the $300 GCP credit with room to spare. If it works
we publish and scale; if it doesn't we learn and pivot. That's the whole
plan.
