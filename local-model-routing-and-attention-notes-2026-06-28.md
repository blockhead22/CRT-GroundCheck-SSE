# Local Model Routing and Attention Notes - 2026-06-28

## Installed Model Read

Best installed general model:

- `qwen3:14b`
- 14.8B parameters
- Q4_K_M quantization
- 40,960 context length
- thinking/tools capability

Best installed strict scaffold executor:

- `qwen2.5:7b-instruct`
- Smaller, faster, and much more reliable on direct governed-state QA

`gemma4:latest` is not actually the biggest text model here. It is 8B Q4_K_M with a very large 131k context and multimodal/tool/thinking capability, but it underperformed on the current text-only CRT/Aether synthesis lab.

## Key Results

### Spiral Synthesis Eval

`qwen3:14b`

- Raw: `0/2`, average `0.160`
- Scaffold: `2/2`, average `0.724`
- Delta: `+0.564`

Interpretation: strong as a scaffolded long-form synthesis/drafting model.

`gemma4:latest`

- Raw: `0/2`, average `0.125`
- Scaffold: `0/2`, average `0.245`
- Delta: `+0.120`

Interpretation: not useful for this text-only synthesis path without more model-specific prompting.

### Meaning Scaffold Continuity Sweep

`qwen3:14b`

- Raw: `1/15`
- Scaffold: `2/15`

Interpretation: poor strict-state executor despite being the biggest installed model.

`qwen2.5:7b-instruct`

- Raw: `7/15`
- Scaffold: `15/15`

Interpretation: excellent governed-state executor. Use this when the system needs precise current facts, history, contradiction status, authority boundaries, or policy refusal.

### Attention Profile Eval

`qwen3:14b`

- Raw: `0/3`, average `0.286`
- Semantic spine: `2/3`, average `0.664`
- Mirus/Holden: `1/3`, average `0.607`
- Section lock: `2/3`, average `0.677`

`qwen2.5:7b-instruct`

- Raw: `1/3`, average `0.576`
- Semantic spine: `2/3`, average `0.692`
- Mirus/Holden: `1/3`, average `0.665`
- Section lock: `2/3`, average `0.704`

Interpretation: explicit response structures help. The best general structure so far is not more persona; it is either semantic spine or section lock.

## Routing Recommendation

Do not pick one local model as "the brain."

Use model routing:

1. `qwen2.5:7b-instruct` for exact governed memory answers.
2. `qwen3:14b` for scaffolded long-form synthesis, grant language, narrative drafting, and higher-abstraction concept work.
3. Keep `phi3:3.8b` as the tiny-model rescue test subject.
4. Avoid `gemma4:latest` for this specific CRT/Aether text pathway until a dedicated prompt profile exists.

## Attention Finding

"Holding attention" is not mystical. The most useful mechanisms were:

- explicit evidence anchors
- required concept checklist
- forbidden claims list
- section-locked output structure
- verifier/repair pass

Mirus/Holden language helps personal voice, but it can distract from grant/business framing unless the packet is strict. The clean split should be:

- Mirus packet: belief state, evidence, authority, contradiction, allowed/disallowed claims
- Holden render: voice only after belief state is complete
- CRT verifier: checks missing receipts, overclaims, and unsupported synthesis

## Grant / Business Framing

The strongest claim is practical and measurable:

> Low-cost local AI systems can become more trustworthy and useful when small models are routed through governed semantic scaffolds, auditable memory state, and verifier loops.

Business-relevant angles:

- privacy-preserving local creative-production assistant
- reduced cloud inference spend
- inspectable memory and provenance
- local-first R&D platform for small organizations
- measurable evals comparing raw local chat against scaffolded local cognition

Avoid claiming:

- frontier-level capability
- medical reliability
- autonomous truth
- consciousness
- guaranteed grant success

## Next Lab

The next useful experiment is a router eval:

1. Classify task type: exact memory, synthesis, grant/business framing, code, or creative draft.
2. Pick executor model and prompt profile.
3. Run verifier.
4. Repair or switch model if the verifier fails.

That would turn the current lab findings into an actual Aether/Core routing policy.
