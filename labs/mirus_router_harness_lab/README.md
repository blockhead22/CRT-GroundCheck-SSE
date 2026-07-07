# Mirus Router Harness Lab

Purpose: reuse the original CRT tool-routing logic with minimal changes and test
whether the old semantic tool-discovery pattern is useful for Mirus-style
candidate discovery.

What is ripped from the original code:

- `personal_agent.llm_intent_router.LLMIntentRouter`
- `personal_agent.tool_registry.ToolDefinition`
- `personal_agent.tool_registry.ToolParam`
- the original tool-call parsing behavior, including no-tool conversational
  fallback and native multi-tool call handling

What this lab adds:

- a small Mirus-facing tool schema list
- a deterministic `ScriptedToolCallingClient` so tests do not require Ollama
- review-only candidate payloads for memory facts and relations
- JSON result artifacts under `results/`

Safety boundary:

- no production Aether sidecar changes
- no memory writes
- no support/reflection writes
- no raw hidden chain-of-thought storage
- all extracted facts are review-only candidates

Run:

```powershell
python -m pytest tests\test_mirus_router_harness_lab.py -q
python -m labs.mirus_router_harness_lab.original_router_lab --write
python -m labs.mirus_router_harness_lab.original_router_lab --live-ollama --model qwen2.5:7b-instruct --write
python -m labs.mirus_router_harness_lab.original_router_lab --live-ollama --model qwen3:14b --write
python -m labs.mirus_router_harness_lab.original_router_lab --governed --live-ollama --model qwen2.5:7b-instruct --write
python -m labs.mirus_router_harness_lab.original_router_lab --governed --live-ollama --model qwen3:14b --write
python -m labs.mirus_router_harness_lab.original_router_lab --compare --case-pack labs\mirus_router_harness_lab\mirus_governed_discovery_cases.json --write
python -m labs.mirus_router_harness_lab.original_router_lab --compare --live-ollama --model qwen2.5:7b-instruct --case-pack labs\mirus_router_harness_lab\mirus_governed_discovery_cases.json --write
python -m labs.mirus_router_harness_lab.original_router_lab --compare --live-ollama --model qwen3:14b --case-pack labs\mirus_router_harness_lab\mirus_governed_discovery_cases.json --write
```

Current live finding:

- scripted/oracle client: 5/5 under strict review-only candidate scoring
- `qwen2.5:7b-instruct`: 3/5 under strict scoring
- `qwen3:14b`: 3/5 under strict scoring
- governed `qwen2.5:7b-instruct`: 5/5 under strict scoring
- governed `qwen3:14b`: 5/5 under strict scoring
- broader 15-case pack, scripted comparison: raw 10/15, governed 15/15
- broader 15-case pack, `qwen2.5:7b-instruct`: raw 6/15, governed 15/15
- broader 15-case pack, `qwen3:14b`: raw 6/15, governed 15/15

The live models route archive and project-context requests well, but they still
confuse new-fact/update turns with memory recall. `qwen3:14b` can choose
`mirus_extract_candidates` for the marigold/orange turn, but the payload is not
safe enough by itself: it collapses the fact and reason into one candidate, uses
an un-namespaced slot, and may set `memory_write_allowed` incorrectly.

On the broader pack, both live models needed 9 governed repairs across 15 cases.
The repair pattern was consistent:

- missed update-vs-recall distinction
- too few candidates for multi-fact turns
- un-namespaced slots
- unsafe `memory_write_allowed`
- missing review/source boundary
- project/context prompt swallowed by legacy conversational prefilter
- explicit "do not use GPT logs" boundary ignored by raw archive routing

The governed mode wraps the original router with:

- **Mirus front packet**: cheap task-shape compression before the model routes.
- **Holden router**: the original LLMIntentRouter plus local model tool choice.
- **CRT validator**: checks slot shape, candidate count, review-only boundaries,
  and write blocking.
- **CRT repair**: normalizes or reconstructs review-only candidates when the
  model chooses the wrong tool or returns an unsafe payload.
- **Logic graph**: JSON nodes/edges for each turn:
  `input -> mirus_front -> holden_router -> crt_validator -> crt_repair? -> final`.

Interpretation:

The original semantic tool-discovery logic is still useful, but it should not be
trusted alone for Mirus. Aether needs a small governance layer around it:

- validate candidate payloads
- normalize slot names
- force review-only boundaries
- repair/rerun when the model picks `memory_recall` for an update or
  confirmation turn

Promotion criteria before sidecar integration:

- keep the lab report as raw-vs-governed evidence, not proof of generality
- add a feature flag only; do not replace existing Mirus extraction yet
- surface the logic graph in Thinking/Process before trusting the behavior
- candidate output must remain review-only with no automatic memory, support,
  reflection, or policy writes
- start with narrow turn classes: favorites/preferences, reasons/corrections,
  archive boundary requests, and project-context turns
- require regression tests for wrong-tool repair and unsafe-payload repair

Next useful experiment:

Promote the governed discovery pass behind a sidecar feature flag and dogfood it
against Workbench traces:

- current deterministic extraction
- original router plus small-model tool calls
- original router plus Mirus front packet and CRT repair
