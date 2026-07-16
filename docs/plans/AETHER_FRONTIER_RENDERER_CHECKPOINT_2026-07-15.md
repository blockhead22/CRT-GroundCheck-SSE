# Aether Frontier Renderer Checkpoint - 2026-07-15

## Result

The frontier ceiling is proven on the same frozen evidence-ownership packets
that exposed the local-model boundary.

| Renderer | First pass | Final pass | Total latency |
|---|---:|---:|---:|
| qwen2.5:7b-instruct | 1/3 | 2/3 | 16.73 s |
| mistral:latest | 2/3 | 2/3 | 12.96 s |
| qwen3:14b | 2/3 | 2/3 | 84.59 s |
| Grok 4.5 through Grok Build | 3/3 | 3/3 | 41.45 s |

Grok 4.5 passed owner-safe daily advice, Aether identity plus builder, and the
full identity plus name plus favorite-color ownership weave without repair. The
result isolates model composition capability as a real limiting layer for this
answer class. It does not make governance redundant: Aether still selected the
facts, assigned their owners, constrained the job, and graded the result.

Artifacts:

```text
D:\AI_round2\aether-core\.eval-runs\model_boundary_eval_2026-07-15.json
D:\AI_round2\aether-core\.eval-runs\frontier_boundary_eval_grok45_real_2026-07-15.json
D:\AI_round2\aether-core\.eval-runs\frontier_boundary_eval_grok45_2026-07-15.json
```

## Provider boundary

The Grok Build integration is a wording-provider boundary, not an agent handoff:

```text
Aether selects bounded evidence and claim ownership
  -> Grok 4.5 renders prose in an isolated empty workspace
  -> Aether verifies the answer
  -> one bounded repair or existing local/fallback path
```

Grok receives no workspace, project instructions, MCP servers, tools, memory
store, routing authority, contradiction authority, writes, or policy authority.
It cannot inspect the repository. The adapter uses a dedicated fail-closed
configuration and authentication source, disables compatibility discovery and
telemetry, and creates a fresh temporary `GROK_HOME` and working directory for
each preflight and render. Only the structured final answer and usage metadata
cross the adapter boundary; private reasoning and rejected drafts are discarded.

A live isolation check on Grok Build 0.2.101 rendered one synthetic bounded fact
in 5.14 seconds. After completion, the persistent shadow home contained no
session, log, memtrace, or active-session files.

## Important implementation finding

Grok Build 0.2.101 fails open when `--tools` contains only unknown tool names:
it warns that it is keeping the full toolset. The adapter therefore allowlists
one real tool and then explicitly denies that tool and every peer. Any full-tool
warning, MCP startup message, enabled MCP server, project root, project
instruction, or compatibility surface causes fail-closed rejection.

## Product decision

Do not replace every local answer with Grok. Add an explicit opt-in external
renderer only for high-composition, already-bounded prose jobs. Keep simple
general knowledge, exact memory recall, tool/workspace work, Continuity commands,
evidence selection, and all writes local/governed. Provider failure must be
trace-visible and fall back to the existing local path without changing the
answer contract.

The first product slice should expose provider selection, model, latency,
verification, repair, and fallback in public Thinking. It must default off and
must never silently consume the external provider.

## First opt-in product slice

The narrow hook is now implemented behind:

```text
AETHER_EXTERNAL_RENDER_PROVIDER=grok_build
```

It is eligible only for `compound_identity_profile` and
`compound_identity_profile_validation`. Merely injecting or configuring the
renderer does not activate it. Plain identity, general knowledge, exact memory,
Continuity, and tool/workspace routes continue through their existing paths.

The first product-shaped synthetic call exposed a useful live-verifier gap. Grok
initially wrote that Aether was `the voice around the model`, reversing the
intended model/voice relationship. The frozen evaluator would have rejected that
claim, but the runtime character verifier only checked vocabulary. The runtime
verifier now requires the same model-to-voice and memory-to-self relationships.

The repeated live call then followed the intended path:

```text
first external draft: rejected for relationship binding
bounded repair: accepted
final model: grok-4.5
external calls: 2
external latency: 20.00 s
local fallback: false
tools/writes/raw reasoning storage: false
```

Accepted synthetic answer:

```text
I'm Aether - the governed assistant around the model; the model is the voice,
and governed memory is the persistent self. You're Casey Vale, and your favorite
color is amber.
```

The public trace includes requested/eligible/selected state, provider/model,
attempts, latency, repair calls, effective model, and fallback state. The stored
trace is finalized after verification so it records the renderer that actually
produced the accepted answer.

Focused verification after the hook: 98 provider/trace/character tests passed;
the broader RAG/model-boundary/character/provider set passed 100 tests before the
relational verifier tightening. The persistent Grok shadow home remained free of
sessions, logs, memtrace, and active-session files after both product calls.

## Live transcript regression batch

The first user dogfood batch exposed that provider quality alone was not enough.
Older answer paths still stole compound jobs before the frontier renderer could
run:

- identity plus name/color was reduced to a deterministic two-fact card;
- `who are you / who am I / why does the distinction matter` became a full
  profile dossier;
- a profile-ownership trap entered unconstrained local generation and invented
  biography;
- a personal/architecture/limitation request entered broad Context Bridge and
  invented a `modular, distributed framework`.

The repair is precedence plus evidence contracts, not four canned answers:

- identity-component detection now covers explicit identity/model distinctions;
- `who am I` can release only the confirmed name atom for compound synthesis;
- profile-ownership challenges receive requested user-owned atoms and a strict
  no-impersonation/no-shared-memory contract;
- the evidence triplet receives one governance-selected confirmed personal fact,
  one fixed architecture atom, and one honest renderer limitation;
- relationship verifiers reject `Aether is the voice`, unsupported biography,
  generic privacy limitations, and invented architecture;
- direct dossier and multi-fact cards defer when one of these bounded composition
  contracts owns the turn.

Real Grok 4.5 results on a disposable equivalent profile:

| Prompt shape | Result | Calls | External latency |
|---|---|---:|---:|
| identity/model/user distinction + name/color | complete bounded fallback after repair | 2 | 29.77 s |
| exactly three identity/distinction sentences | first render passed | 1 | 6.31 s |
| `your favorites`, ownership trap | first render passed | 1 | 5.01 s |
| personal fact + architecture + limitation | first render passed | 1 | 9.45 s |

The distinction fallback was subsequently expanded so it preserves the requested
architectural significance, ownership, replaceable-model boundary, and model
change continuity even when both frontier drafts fail verification. The exact
rerun ended with `guidance_repair_failed=false`.

Verification after this batch: 89 character tests and 141 focused RAG, direct,
governance, model-boundary, provider, and character tests passed. Workbench was
restarted with the child-process-only provider setting after the final changes.
