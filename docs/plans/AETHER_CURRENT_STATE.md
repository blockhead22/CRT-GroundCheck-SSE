# Aether Current State

Last updated: 2026-06-29

Start new Codex threads here:

```text
D:\AI_round2\docs\plans\AETHER_CRT_WORKBENCH_HANDOFF_2026-06-29.md
```

Current lane:

```text
Aether Core validation infrastructure:
local router -> Mirus packet -> scaffold -> model render -> CRT verifier
-> repair/fallback -> durable thinking trace -> replay eval
```

The local-router lab is now roadmap-relevant only as Aether/Core
infrastructure. Do not continue it as loose prompt tuning.

Read next:

```text
D:\AI_round2\docs\plans\AETHER_DURABLE_THINKING_TRACE_REQUIREMENT_2026-06-29.md
D:\AI_round2\local-router-replay-v0-report-2026-06-28.md
D:\AI_round2\docs\plans\AETHER_AETEROS_MASTER_PLAN_2026-06-26.md
D:\AI_round2\docs\plans\AETHER_WORKBENCH_V1.md
```

Current decision:

```text
Keep working on the lab if the next phase builds durable structured trace.
Stop or pause if the work becomes only model shopping or prompt tasting.
```

Next work:

```text
1. Add trace JSON output to local_router_cli.
2. Make replay eval grade trace quality.
3. Curate a 30-50 case replay pack.
4. Prove historical answer + trace reload after restart.
5. Bring the trace pattern into Workbench only after the lab evidence holds.
```

Contract:

```text
Do not store raw hidden chain-of-thought as truth.
Do store structured CRT trace artifacts:
classification, retrieval, Mirus packet, route, scaffold, verifier flags,
repair/fallback, confidence, contradiction notes, and learning candidates.
```
