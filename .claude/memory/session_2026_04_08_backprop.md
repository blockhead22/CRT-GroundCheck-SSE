---
name: session_2026_04_08_backprop
description: Belief backpropagation validated (30/30), deep research confirms no precedent, Archive/lumi_ai explored, anchor clustering measured, breathing loop identified as missing gate
type: project
---

# Session: April 8, 2026 — Belief Backpropagation & Breathing Loop

## What happened

### Belief Backpropagation — Theory to Validation
- Nick's "stoner brain" proposed three ideas: backward error propagation through BDG, domain volatility from correction frequency, self-model as nodes in same graph
- Deep research (web search) confirmed ALL THREE are genuinely novel — no direct precedent in literature
- Built `backprop_engine.py` (EpistemicLoss, DomainVolatility, compute_backward_gradients)
- Added `propagate_backward()` to `memory_graph.py` (BFS over in_edges, mirrors forward cascade)
- Wrote 6 lab experiments, all passed 30/30
- Key results: contraction ratio 0.13, 2.25x volatile domain impact, self-model adjusts per-domain
- 4 publishable theorem targets: Banach convergence, AGM unification, self-referential nodes, discrete active inference
- Paper updated with results section + research landscape

### Documentation Published
- Created `docs/belief-backprop.html` (full theory + results page with MathJax)
- Added backprop lab section to `docs/labs.html`
- Added to `docs/docs.js` DOCS array (main nav)
- Added paper card to `docs/index.html` research chapter
- Updated 6 more pages for continuity: glossary (5 new terms), cascade-complexity (forward reference), architecture (Trust Evolution card), index (What's Running + Where It Goes), about (paper count), experiments (validation card)
- All deployed to Cloudflare (`aeteros-research.pages.dev`)

### Archive Deep Dive — The Through Line
- Explored `D:\lumi_ai\lumi_ai` — original Mirus/Holden/Semantic String Engine from 2025
- Explored `J:\Archive\core\` — intermediate generation (SSE MVP, March-May 2025)
- Key finding: Nick built anchor truths, breathing cycles, contradiction-as-promotion, quantum memory collapse, mood-as-epistemic-signal, fallback quarantine — ALL unguided
- The thesis was always the same: "the system should speak from memory, not from a model"

### Anchor Clustering Analysis (Production Data)
- Ran analysis on 635 production memories from `crt_memory_shared.db`
- Anchors (42) do NOT cluster with each other (mean similarity 0.10 = random) — they're semantic poles
- Non-anchors (593) DO collapse toward anchors: mean nearest-anchor similarity 0.45, 77% within cosine 0.3
- Densest clusters: system self-description (56 satellites), greeting (51), "My name is Nick" (40), favorite color orange (30)
- Script at `workspace/anchor_cluster_analysis.py`

### Missing Pieces Identified
1. **Breathing cycle is gone** — Holden's compress→inflate→collapse→validate doesn't exist in CRT. No post-generation fidelity check.
2. **Fallback quarantine is gone** — hallucinated memories stored at face value (directly related to Bug #8)
3. **Quantum memory collapse is gone** — retrieval is deterministic, no probabilistic "refusal to answer"
4. **Reflection queue is gone** — no async re-evaluation of weak outputs

### Next Work Identified (TWO TASKS)
1. **Breathing Loop / Response Mirror** — post-generation epistemic fidelity gate. Three checks: belief fidelity (did it use injected memories?), request alignment (did it answer the question?), factual grounding (are claims traceable to memories?). Failure = loss signal for backprop (correction_source="system", weight 0.6).
2. **Bug #5: Replace flat 0.4x demotion with BDG cascade** — precursor to wiring backprop into production. Currently contradictions get flat 0.4x trust multiplier. Should flow through BDG with damping instead.

### Wobble / Query Resonance / SSE Revival
- Explored J:\Archive\core\quantum_memory.py — original QuantumMemoryBreather (3 states: confident collapse, weak breathing, refusal)
- Built wobble mechanism: query vector drops into BDG, resonance propagates through SUPPORTS edges (forward + backward, damped)
- 4 synthetic labs (13-16): all 10/10. Key result: health query surfaces 5 work facts and 2 preference facts through edges that cosine alone returns ~0 on.
- Production lab (17-20): 867 real memories, 2,298 edges. 26 extra memories surfaced across 5 queries. 60 tension pairs found. Cross-domain strings confirmed.
- Wobble wired into fidelity mirror (`_wobble_expand` in fidelity_mirror.py). Falls back to text-matching when memory IDs unavailable.
- Fixed fidelity mirror: short responses get neutral grounding instead of 0.00. Text-based BDG node matching for legacy path.
- Nick's insight: SSE was never about compression. It was a map of who someone is, rendered as tension between beliefs. The strings ARE the cross-domain connections. The wobble IS the SSE query mechanism. The BDG is the string engine.
- Key quote from 2025 GPT logs: "its designed to self criticizes more than it is to make a declaration"
- Compressed epistemic lab (Labs 7-12): 3-bit preserves epistemic structure (identical gradients, 92.9% anchor basins). 2-bit breaks it (71.4%). PCA-96 is lossless. Published as docs/epistemic-compression.html.

## Files created/modified this session
- NEW: `papers/belief_backpropagation/backprop_engine.py`
- NEW: `papers/belief_backpropagation/experiments.py`
- NEW: `docs/belief-backprop.html`
- NEW: `workspace/anchor_cluster_analysis.py`
- MODIFIED: `personal_agent/memory_graph.py` (added `propagate_backward()`)
- MODIFIED: `papers/belief_backpropagation/belief_backprop.md` (results section + research landscape)
- NEW: `papers/belief_backpropagation/wobble_lab.py`
- NEW: `papers/belief_backpropagation/sse_production_lab.py`
- NEW: `papers/belief_backpropagation/compressed_epistemic_lab.py`
- NEW: `docs/epistemic-compression.html`
- MODIFIED: `personal_agent/fidelity_mirror.py` (wobble expansion added)
- MODIFIED: `docs/belief-backprop.html` (wobble section added)
- MODIFIED: `docs/index.html`, `docs/labs.html`, `docs/docs.js`, `docs/glossary.html`, `docs/cascade-complexity.html`, `docs/architecture.html`, `docs/about.html`, `docs/experiments.html`

### Experiment A: Trust-Biased Prompting (PASSED)
- Tested on llama3.2 (3B), gemma3 (4B), phi3 (3.8B), Claude Opus
- Same result every scale: trust scores suppress unreliable facts
- Opus baseline: merges contradictory facts 5/5 times. Trust-biased: 2/5, both flagged as unreliable
- Gemma3 hard test: low-trust contamination 9/15 → 0/15. Complete suppression.
- Signal confirmed: trust-structured prompting changes model behavior regardless of model size

### Experiment B v1: CRT Fine-Tune (PARTIAL)
- Phi-3 3.8B + QLoRA, 2000 examples, 2 epochs, 50 minutes on RTX 3060
- Loss: 1.53 → 1.18. Token accuracy: 67%. Training succeeded.
- Model absorbed conversation patterns instead of facts (overfit to GPT conversation format)
- Signal: adapter shifted model behavior massively. Wrong content format.

### Experiment B v2: Belief-Grounded Fine-Tune (RUNNING OVERNIGHT)
- Phi-3 3.8B + QLoRA, 16,957 examples (4 types: fact assertion, Q&A, trust-filtered conversations, correction pairs)
- Trust distribution mean: 0.881 (high-trust oversampled 4x)
- 6,360 steps, 3 epochs, ~8.8 hours on RTX 3060
- Output: models/phi3-crt-adapter-v2
- CHECK RESULTS NEXT SESSION: the adapter should answer factual questions from weights alone

### Business Insight
- Trust-weighted fine-tuning is a new training paradigm: not RLHF (preference), not Constitutional AI (principles), not domain fine-tuning (data). Training signal is earned epistemic state from a belief graph.
- The adapter is the product pipeline, not the personal model. Any organization's correction history → trust scores → training signal → faithful adapter.
- EU AI Act deadline August 2026 creates compliance demand for exactly this auditability.

### Claude Variance + Pollution Lab (new experiment)
- Built and ran context pollution sensitivity test on Claude Sonnet via CLI
- Three conditions: baseline (no context), polluted (100 entries + noise), governed (trust-filtered)
- 8 topics x 5 phrasings x 3 conditions
- Key findings on Claude:
  - Baseline: 92% consistency but EMPTY — doesn't know color, coffee, location, health
  - Polluted: 82% consistency — finds facts but merges noise (color: "cyan AND orange AND green")
  - Governed: 78% aggregate BUT wins decisively on contested facts:
    - Color: 50% polluted → 90% governed
    - Health: 70% polluted → 100% governed
    - Coffee: 80% polluted → 100% governed
    - Location: 90% polluted → 100% governed
  - Lower governed scores on name/work/project because governed gives MORE detail (penalized by consistency metric)
- This is a NEW experiment type (context pollution sensitivity), distinct from variance probing and continuity-blind
- Claude's markdown memory system stores project info but NOT personal facts

### Claude Code Architecture Analyzed
- Explored leaked Claude Code source at D:\AI_round2\src\src
- Memory system: markdown-based session memory + auto memory in ~/.claude/projects/
- Zero trust scores, zero contradiction detection, zero belief graph
- Correction handling: save a markdown "feedback" note. Nothing reads it structurally.
- No confidence tracking on outputs. No persistence of belief state beyond flat markdown.

### Trust Recalibration Applied
- Found trust decay bug: 413:1 downward vs upward pressure
- Compaction decay hitting -0.150 per pass, reinforcement giving +0.02
- 48% of memories ground to 0.20 floor despite 100+ accesses
- Three fixes: access-count decay protection, retrieval reinforcement, one-time recalibration of 765 memories
- Trust distribution now healthy — high-access memories at 0.85-0.88 where they should be

### Adapter Training v2 (lean, running)
- Phi-3 3.8B + QLoRA, ~6k examples, 2 epochs
- Checkpoint saves every 500 steps (safe to interrupt)
- Currently at 24%, loss 1.40, token accuracy 66%
- ETA: ~3.5 hours remaining

### Modal Attempted
- Set up Modal account for cloud GPU training
- $5 free credits burned on failed runs (RoPE config bug + timeout)
- Training script works but needs longer timeout or direct terminal execution
- Scripts saved: modal_train.py, modal_prep_data.py

### Google TPU Research Cloud
- Application submitted for free compute grant
- 9 papers, production system, validated results cited

### Context Pollution Lab (gemma3, partial)
- First run on gemma3 was killed mid-experiment (pivoted to Claude-only)
- Partial results lost but experiment redesigned for Claude CLI

### Business / Strategy Discussions
- Trust-weighted fine-tuning identified as new training paradigm
- Open source harness, moat the training signal
- Adapter pipeline as service (correction history → trust scores → adapter)
- EU AI Act August 2026 deadline creates compliance demand
- Trust-native foundation model as long-term play (corpus from deployed harnesses)
- Anthropic shipped advisor pattern same day — converging on multi-model but without memory/trust
- Pricing estimates: seed $4-8M, Series A $20-50M if pipeline validated at scale

### Original Whitepaper Found
- `C:\Users\block\OneDrive\Documents\workingfinal (1) (1).pdf` — May 2025
- Contains: Mirus, Holden, MMH, SSE, CSR, DNNT — all four systems
- Page 18: "its designed to self criticizes more than it is to make a declaration"
- Page 18: "I see fancy prediction that could care less if its right, masquerading as intelligence"
- Every concept in current CORE traces to this document
- nick_paper.html rebuilt with original whitepaper quotes + "this became →" annotations
