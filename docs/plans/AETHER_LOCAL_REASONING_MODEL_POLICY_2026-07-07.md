# Aether Local Reasoning Model Policy - 2026-07-07

## Purpose

Workbench should prefer local reasoning-capable models for synthesis and hard
reasoning while keeping fast standard models available as fallbacks.

This is not a claim that reasoning models are always better. It is a working
preference for the next experiments:

```text
small/standard model + governed workspace
vs
reasoning model + governed workspace
vs
reasoning model without enough governance
```

## Local Models

Reasoning-preferred:

- `qwen3:14b`
- `deepseek-r1:latest`
- `deepseek-r1:8b`

Standard / task-specialized:

- `qwen2.5:7b-instruct`
- `qwen2.5-coder:14b`
- `phi3-crt:latest`
- `phi3:3.8b`
- `gemma4:latest`
- `gemma3:latest`
- `gemma:7b`
- `mistral:latest`
- `llama3.2:latest`
- `llama2:latest`
- `llava:7b`

## Runtime Preference

Current sidecar default:

```text
qwen3:14b
```

Route recommendations:

- deterministic memory/governance lanes: no model preferred;
- broad synthesis, depth, technical reasoning, context bridge, and general
  local chat: prefer `qwen3:14b`;
- depth / technical reasoning fallback probe: `deepseek-r1:8b`;
- code-tool route: prefer tools first, then `qwen2.5-coder:14b`, with
  `qwen3:14b` for reasoning review;
- standard fast fallback: `qwen2.5:7b-instruct`.

Model recommendation remains observational:

```text
no automatic silent model switch
no automatic frontier/API escalation
no private context leaves local machine without explicit approval
```

## Reasoning Trace Boundary

The experiment should not store hidden chain-of-thought as truth.

Allowed:

- public scratchpad summaries;
- step labels;
- evidence map;
- route/workspace packet;
- verifier deltas;
- repair attempts;
- final trace explaining how the answer was bounded.

Not allowed:

- durable raw hidden chain-of-thought;
- treating a model's reasoning text as confirmed fact;
- silent memory/support/reflection writes.

## Next Lab

Build a narrow reasoning-coherence lab:

```text
prompt
-> governed workspace packet
-> public reasoning trace request
-> model answer
-> verifier score
-> optional repair
-> coherence-break report
```

Compare:

- `qwen2.5:7b-instruct` standard model;
- `qwen3:14b` reasoning-preferred model;
- `deepseek-r1:8b` reasoning model;
- deterministic external workspace ceiling.

Stress dimensions:

- long source text length;
- number of evidence nodes;
- number of contradictions/tensions;
- whether the model preserves source boundaries;
- whether the public reasoning trace helps or causes drift;
- where coherence breaks.

The key question:

```text
Can governance hold attention well enough that a smaller standard model can
reason over larger context, or does it still need a reasoning model once the
workspace gets dense?
```

