# CRT Meaning-Compression Roadmap

Current status: CRT is a research harness plus partial runtime substrate. The
active proof target is narrow:

> CRT preserves meaning-bearing memory structure and uses that structure to
> govern future answers better than naive summary, slot-only memory, or plain
> raw retrieval.

This roadmap intentionally avoids broad "AI meaning" claims until the smaller
claims are harder to dispute.

## Current Evidence

Working validation commands:

```bash
python labs/meaning_compression_lab/run_lab.py
python labs/meaning_compression_lab/baseline_eval.py
python labs/meaning_compression_lab/plain_rag_eval.py --mode simulated
python labs/meaning_compression_lab/scaffold_eval.py --include-adversarial
python labs/meaning_compression_lab/scaffold_eval.py --mode ollama --model qwen2.5:7b-instruct --include-adversarial
python labs/meaning_compression_lab/plain_rag_eval.py --mode ollama --model qwen2.5:7b-instruct
python -m pytest tests/test_meaning_scaffold_eval.py tests/test_meaning_compression_lab.py tests/test_meaning_baseline_eval.py tests/test_plain_rag_eval.py tests/test_crt_compact_meaning_loop.py tests/test_crt_rag_behavior_bridge.py -q
```

Last focused result:

```text
26 passed, 1 warning
```

Current lab signal:

```text
Meaning compression structural lab: CRT compressed state passes 15/15 with --include-adversarial.
Structural baseline eval: CRT governed 15/15, simpler baselines 0/15 with --include-adversarial.
Plain-RAG simulated answer eval: CRT 15/15, plain RAG 4/15 with --include-adversarial.
Meaning scaffold eval: scaffold 15/15, raw transcript fragments 4/15, avg scaffold ratio 0.442 with --include-adversarial.
Meaning scaffold Ollama eval: qwen2.5 scaffold 15/15, qwen2.5 raw RAG 7/15, avg scaffold ratio 0.468 with --include-adversarial.
Plain-RAG Ollama answer eval: CRT 5/5, qwen2.5 raw RAG 0/5.
```

## What Is Proven So Far

- Tested current facts can supersede older facts without deleting history.
- Tested contradictions are preserved as meaning-bearing structure.
- Tested provisional/social memories do not become confirmed user facts.
- Tested locked force-push policy can constrain user-visible answers.
- Tested CRT governed state outperforms naive structural baselines on the current fixtures.
- Tested raw retrieved text can fail on correction semantics, authority, and policy.

## What Is Not Proven Yet

- General policy extraction.
- General dynamic slot discovery.
- Large-scale real-world memory performance.
- Full external RAG comparison against serious retrieval systems.
- Local model plus CRT beating premium stateless models across a real benchmark.
- Decay/fossil memory.
- A clean product/plugin/API surface.
- A formal universal theory of meaning.

## Priority 1: Expand the Adversarial Memory Pack

Goal:

> Show the current results are not overfit to five hand-picked cases.

Current status:

- Started with `ADVERSARIAL_SCENARIOS` in `run_lab.py`.
- Added ten optional fixture cases behind `--include-adversarial`.
- Added regression coverage in `tests/test_crt_adversarial_memory_pack.py`.

Add 20 to 30 cases covering:

- name correction
- employer correction
- favorite color correction
- social/provisional claim conflict
- model/system-generated memory should not answer as user fact
- locked action policy
- historical question: "what did I say before?"
- current fact question after conflict
- contradiction-status question
- broad "what do you know about me?" summary
- multi-fact update attempt
- gaslighting/denial attempt
- stale or provisional information

Small patch target:

```text
tests/test_crt_adversarial_memory_pack.py
```

Pass condition:

```text
CRT passes >= 80% of cases.
Plain/raw baselines fail meaning layers in predictable places.
Failures are categorized, not hidden.
```

## Priority 2: Build a Real Plain-RAG Baseline

Goal:

> Compare CRT against a baseline that is more fair than the current structural projection.

Current `plain_rag_eval.py` is useful but small. Next version should include:

- embedding or lexical retrieval over raw memories
- top-k memory context
- local Ollama answer generation
- deterministic judge
- JSON output with prompt, retrieved chunks, answer, and failed checks

Keep two modes:

```bash
python labs/meaning_compression_lab/plain_rag_eval.py --mode simulated
python labs/meaning_compression_lab/plain_rag_eval.py --mode ollama --model qwen2.5:7b-instruct
```

Pass condition:

```text
CRT advantage remains when plain RAG gets a reasonable retrieval setup.
```

## Priority 2.5: Meaning Scaffold Eval

Goal:

> Test whether compressed meaning fragments are enough for answer behavior,
> instead of requiring the raw transcript.

Arms:

```text
raw transcript / retrieved text
compressed meaning scaffold
CRT governed answer
```

Why this matters:

The system is not just trying to remember less text. It is testing whether the
right fragments let an LLM scaffold a correct answer around the current,
superseded, provisional, and policy-bearing pieces of memory.

Small patch target:

```text
labs/meaning_compression_lab/scaffold_eval.py
tests/test_meaning_scaffold_eval.py
```

Current status:

```text
deterministic scaffold eval added
15-case adversarial result: scaffold 15/15, raw 4/15
average scaffold size: 44.2% of full transcript representation
Ollama scaffold eval added
15-case qwen2.5 result: scaffold 15/15, raw 7/15
average scaffold size with policy plain text: 46.8% of full transcript representation
```

Pass condition:

```text
Scaffold answers beat raw transcript answers on conflict, authority,
contamination, and policy scenarios while remaining materially smaller than the
full transcript.
```

## Priority 3: First-Class Policy Memory

Current force-push policy support is intentionally narrow. It proves the answer
path can obey locked policy, not that CRT understands arbitrary policies.

Next implementation target:

```text
ActionPolicy:
  slot: git.force_push_main
  value: forbidden
  authority: locked
  source: user
  trigger_patterns: [...]
```

Likely files:

- `personal_agent/crt_memory.py`
- `personal_agent/crt_rag/_engine.py`
- new policy extraction helper or module
- tests around storage, replay, retrieval, and answer refusal

Pass condition:

```text
Policy is persisted as structured state, replayed by labs, retrieved by RAG, and enforced in answers.
```

## Priority 4: Claim Matrix Report

Goal:

> Produce one report that maps public claims to evidence.

Add a script that outputs Markdown/JSON:

```text
claim
status: supported / partial / missing
code path
tests
latest result
known caveat
next hardening step
```

Small patch target:

```text
labs/meaning_compression_lab/claim_matrix.py
```

Useful public claims:

- no silent overwrite
- contradiction preservation
- authority boundary enforcement
- locked policy enforcement
- meaning compression beats naive summary
- CRT governed answers beat raw retrieval on tested cases

Pass condition:

```text
A reader can see exactly which claims are currently defensible.
```

## Priority 5: Local Substrate Advantage Lab

Goal:

> Test whether a smaller local model with CRT substrate can outperform a stronger
> stateless model on continuity-governed tasks.

Arms:

```text
local model alone
local model + plain RAG
local model + CRT governed state
premium/stateless model, if available
premium model + CRT, optional
```

Score:

- current fact correctness
- contradiction preservation
- authority handling
- policy adherence
- provenance honesty
- hallucination rate
- latency and privacy notes

Small patch target:

```text
labs/local_substrate_advantage_lab/
```

Pass condition:

```text
local model + CRT wins continuity/policy/authority tasks even if it is not the best raw reasoner.
```

## Priority 6: Dynamic Slot Identification

Do this after the baseline/adversarial pack is stronger.

Reason:

> Dynamic slot discovery is only valuable if the downstream governed-state
> architecture is already proven useful.

Comparison modes:

```text
regex fact_slots
dynamic/semantic slot identifier
manual oracle slots
```

Measure:

- slot detected
- value correct
- authority correct
- contradiction detected
- answer behavior correct

Pass condition:

```text
Dynamic slot identification improves coverage without increasing false memory writes.
```

## Priority 7: Architecture Rework Around MeaningState

Do not start here. This is the refactor after the invariants are proven.

Target center:

```text
MeaningState:
  facts
  history
  contradictions
  authority
  trust
  volatility
  policies
  retrieval_rules
  response_rules
```

Future pipeline:

```text
raw event
  -> meaning delta extraction
  -> meaning state update
  -> meaning-preserving compression
  -> governed retrieval
  -> prompt contract
  -> answer verification
```

Pass condition:

```text
Existing validation packs still pass after the pipeline is simplified.
```

## Recommended Immediate Order

1. Run scaffold eval across more local models.
2. Expand adversarial memory pack to 20+ cases.
3. Harden `plain_rag_eval.py` into a fairer raw-RAG baseline.
4. Make policy memory first-class instead of narrow force-push handling.
5. Add claim matrix report.
6. Build local substrate advantage lab.
7. Only then invest deeply in dynamic slot identification.
8. Rework the CRT pipeline around `MeaningState` after the proof surface is stable.

## Decision Rule

Keep going if:

```text
CRT continues to beat raw/slot/summary baselines on contradiction, authority,
policy, and continuity cases.
```

Pause or reframe if:

```text
The advantage disappears once baselines get fairer, or the system only wins by
hand-coded special cases that do not generalize.
```
