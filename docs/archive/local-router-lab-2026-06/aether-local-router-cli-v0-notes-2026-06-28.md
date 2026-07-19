# Aether Local Router CLI v0 Notes - 2026-06-28

## Purpose

The CLI is a thin prototype around the Aether Local Router v0 policy. It lets
real prompts run through:

1. task classification
2. local model/profile routing
3. scaffolded generation
4. stricter verifier grading
5. one repair attempt
6. optional fallback profile

This keeps the work roadmap-aligned without wiring it into the main Aether app
too early.

## Command

```powershell
python -m labs.meaning_compression_lab.local_router_cli "Frame this as a grant direction..."
```

Useful options:

```powershell
--task-type grant_business
--context "Known local facts..."
--anchors "local,CRT,Aether,RTX 3060"
--concepts "measurable,low-cost,business,verifier,AI request router"
--json
--no-write
```

## Smoke Results

Grant/business smoke:

```text
task_type: grant_business
model: qwen2.5:7b-instruct
profile: section_lock
passed: true
score: 0.849
```

Architecture smoke:

```text
task_type: architecture_synthesis
model: qwen2.5:7b-instruct
profile: semantic_spine
passed: true
score: 0.808
fallback_used: true
```

## Real Failures Found And Patched

The CLI smoke exposed three verifier gaps:

1. It confused "AI request router" with a network router.
2. It invented an unsupported "up to 50%" performance claim.
3. It invented acronym expansions for SSE and CRT.

Those are now explicit verifier weirdness gates:

```text
network_router_drift
unsupported_numeric_claim
misnamed_sse
misnamed_crt_tool
external_research_drift
```

## Current Advice

For real prompt replay, supply context and anchors whenever possible. The CLI
can infer defaults, but Aether-quality output improves when the Mirus packet is
not vague.

Good pattern:

```powershell
python -m labs.meaning_compression_lab.local_router_cli `
  --task-type grant_business `
  --context "Known local facts: RTX 3060 12GB; router eval passed 3/3; avg score 0.845." `
  --anchors "local,CRT,Aether,RTX 3060,qwen2.5" `
  --concepts "measurable,low-cost,business,verifier,AI request router" `
  "Frame this as a practical small-business R&D grant direction."
```

## Next Replay Set

Build a small JSON replay pack of 20-50 real prompts:

- personal synthesis
- grant/business framing
- architecture explanation
- exact memory question
- creative-production planning
- code/repo reasoning

Then run the CLI over the replay pack and compare:

```text
route chosen
pass/fail
repair/fallback
contract score
usefulness score
failure flags
```

That turns the router into evidence for Aether/Core graduation.
