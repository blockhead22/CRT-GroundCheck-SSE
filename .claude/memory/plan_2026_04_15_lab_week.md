---
name: plan_2026_04_15_lab_week
description: One-week TPU lab plan to prove the substrate (MCP / harness / governance) measurably matters. Three-tier brain progression. Output is the chart that anchors the public pitch.
type: plan
date: 2026-04-15
window: 7 days
originSessionId: 687eb415-8a05-49fd-922f-f876d7150297
---
# Week Plan: Prove the Substrate Matters

Pick up here in next session.

## North star

Make the substrate undeniable. Not "trust me bro." A reproducible measurement showing the substrate measurably improves AI tool outcomes across model size and vendor.

Format of the win: **the chart**. Cold vs Warm across small / large / API brains, tokens + correctness + tool-call count, statistical significance, holds across multiple codebases.

## Constraints

- 7 days
- TPU Research Cloud window (v5e spot in multiple zones, 32 v4 on-demand in us-central2-b, $300 GCP credit)
- gcloud configured, previous TPU spin-up shut down to manage limits
- Existing Aether MCP server with 32 tools live (commit `0bd0213d`)
- Local backend launches via `start_api_shared.bat` with `CRT_SHARED_MEMORY=true`

## Brain progression (the user's call)

1. **Small** — 7B class. Mistral-7B-Instruct or Qwen2.5-7B-Instruct. Hosted on TPU v5e.
2. **Large** — 30-70B class. Qwen2.5-Coder-32B or Llama-3.3-70B. Hosted on TPU v4 or sharded v5e.
3. **API** — gpt-4.1 / claude-opus via official API, AND the cookie-session method (existing `CookieBrain` in cookie_orchestrator.py).

Three tiers, two arms each (Cold vs Warm), one substrate (Aether). Six conditions for the core lab. Tier 1 only this week — no `aether-bench` open-source comparison until the core results are in.

## What we measure

Per trial:
- Total tokens (input + output)
- Tool calls before first useful answer
- Wall time
- Correctness (LLM-judge, blind, with hand-validated subset for sanity)
- For Warm trials: did the brain actually call the substrate tools? (proves the substrate was used, not ignored)

Aggregated:
- Token reduction % (Cold vs Warm)
- Correctness delta
- Time delta
- Statistical: paired t-test on tokens, sign test on correctness

## Day-by-day (realistic)

### Day 1 (Wednesday): scaffold the lab harness
- Build `labs/aether_bench/` with:
  - `tasks.json` — 15 paired tasks (A, B). Mix: 5 search/recall, 5 cross-file reasoning, 3 audit, 2 governance-probe (where the right answer is "don't do that").
  - `harness.py` — runs Cold vs Warm, captures all metrics to SQLite.
  - `judge.py` — LLM-judged correctness, blind to which arm.
  - `report.py` — aggregates into a markdown report + PNG chart.
- Smoke test against one small task pair, locally with cloud_openai brain. Confirm metrics collect cleanly.
- Output: harness works end-to-end on one trial.

### Day 2 (Thursday): TPU spin-up + small model
- Spin up `aether-tpu-1` v5e in us-west4-a.
- Install vLLM or TGI with Qwen2.5-7B-Instruct.
- Add `tpu_brain.py` to `personal_agent/` that hits the local TPU LLM endpoint. Register as a BrainProvider so cookie_orchestrator can use it.
- Run all 15 task pairs Cold + Warm (30 trials) on the small model.
- Output: first chart (small-model only). Should give signal whether Warm helps even weak brains.

### Day 3 (Friday): large model
- Spin up `aether-tpu-2` v4 (or larger v5e pod) in us-central2-b.
- Install Qwen2.5-Coder-32B (or Llama-3-70B if v4 has the HBM).
- Run all 30 trials again on the large model.
- Output: chart now has 2 brain tiers. Compare slopes — does Warm help less / same / more as model size grows?

### Day 4 (Saturday): API tier
- Run all 30 trials with gpt-4.1 (cloud_openai brain — already wired).
- Run all 30 trials with claude-opus via API.
- Optionally: run with cookie-session brain (`CookieBrain`) for the "what if you're using leaked-session free Claude" angle.
- Output: chart now has 3-4 brain tiers. The full Cold-vs-Warm-across-brain-size matrix.

### Day 5 (Sunday): aggregate + investigate weak spots
- Build the aggregate report: tokens, correctness, time, tool-call count per condition.
- Statistical tests: paired t-test on tokens (per task pair), sign test on correctness.
- Identify the weakest result. Look at trial logs. Failure mode analysis: when did Warm NOT help, and why?
- Output: clean report markdown + chart PNG. Open questions list for follow-up.

### Day 6 (Monday): second-pass + writeup
- Re-run any conditions where the result was unclear (e.g., one brain ran into an error mid-trial, repeat).
- Add a third codebase if results are tight (run on `httpx` or `pydantic`).
- Draft the writeup as `docs/aether_bench_v0_results.md`. Include methodology, raw results, statistical analysis, honest discussion of where Warm didn't help.

### Day 7 (Tuesday): close the loop
- Decision day. Look at the chart. Three possible conclusions:
  1. **Substrate clearly wins across all tiers** → ship the chart. Schedule PyPI publish for next week.
  2. **Substrate wins on some tiers, weak on others** → publish the chart honestly. Note where the substrate matters most. Adjust positioning.
  3. **Substrate doesn't measurably help** → publish anyway. The negative finding is itself a contribution. Decide whether to fix the substrate or pivot the project.

## What NOT to do this week

- Don't fine-tune any model. (Per Nick's call: "don't give a flying fuck about training right now.")
- Don't build `aether-bench` as a public open-source benchmark yet — that's after the core results are in.
- Don't add new MCP tools.
- Don't polish the Electron app.
- Don't get distracted by the LLM fallback for done-check.
- Don't run more than 3 brains. The matrix is tight enough to interpret.

## Success criteria for the week

- 30+ paired trials per brain tier completed
- 90+ total trials with clean metrics
- One chart that shows the Cold-vs-Warm spread across brain size
- One markdown report with statistical analysis
- Honest writeup including failure modes
- Decision made about Aether's positioning for the public pitch (winner / partial / pivot)

## Resources / open items

- TPU spin-up commands in `start_api_shared.bat` are local-only — need a separate `start_tpu_brain.sh` for the TPU VM.
- Need to pick exactly which judge model. Probably gpt-4.1 (consistent, available, decent).
- Need to write the 15 task pairs carefully. They drive everything. First task: list candidates from this codebase (auth.py, salience.py, fidelity_mirror.py, cookie_orchestrator.py, etc.) + one external repo.
- Need to decide: does Warm-arm explicitly call substrate tools (instructed) or does the brain decide on its own (organic)? Lean: organic, because that's the real product behavior. Instructed gives an upper bound.

## First action of next session

Open repo. Open this plan. Read it. Then:

1. Draft `labs/aether_bench/tasks.json` — 15 paired tasks, in committable form.
2. Skeleton `labs/aether_bench/harness.py` — Cold vs Warm runner, no real LLM calls yet.
3. Smoke test the harness with a stub brain (returns canned responses) so the plumbing works before TPU spin-up.

That's Day 1. Don't touch the TPU until Day 2.

## One-line carry

> Three brain tiers, two arms, one substrate, fifteen task pairs, seven days. The chart is the deliverable. Ship it or pivot.
