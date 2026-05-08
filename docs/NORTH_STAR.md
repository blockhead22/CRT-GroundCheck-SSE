# Aether — north-star doc

*Drafted 2026-05-07. Not a session summary. The thing to read when you forget
why you're doing this, or when you have to explain it cold to someone else.*

---

## 1. The problem

**Models are mouths. The thing that should survive them is the self.**

Every interaction with an LLM today loses the self at the boundary:
- A new chat session loses the user's belief state. The user has to re-explain.
- A model upgrade loses the agent's belief state. The agent forgets who it was.
- A multi-agent handoff loses the epistemic state. The handoff is "context
  dump → fresh model → guess."

The implicit assumption in current LLM products is that the model *is* the
self, so when the model changes the self has to be reconstructed by stuffing
context windows. That assumption is wrong by construction. The self is not
the parameters; it's the **persistent, contradiction-aware, trust-weighted
state** that grows through interaction.

Aether is one answer to: *what does that persistent self look like as
infrastructure that any model can plug into?*

---

## 2. The shape of the answer

Aether's substrate stores beliefs as **(text, embedding, sigma, trust,
dependency edges, temporal status)** — not as sentences in a context window
and not as parameter weights. Five concrete pieces:

1. **Belief loci, not points.** Every memory is a Gaussian in semantic space,
   with a center vector and a per-dimension uncertainty. Tightness in a
   dimension means the substrate is sure about that aspect; width means it
   isn't. This is the splat.
2. **Belief dependency graph (BDG).** Beliefs cite other beliefs. Trust
   updates propagate. When a parent belief loses trust, its children damp.
   When a contradiction lands, the cascade is bounded by the graph topology,
   not by retrieval recall.
3. **Belief/speech separation.** What the substrate *believes* (grounded in
   stored memories) and what it *says* (the response actually emitted) are
   different objects. The fidelity mirror grades each response against the
   belief state — measurable, auditable.
4. **Contradiction-aware updates.** New facts that conflict with the
   substrate don't silently overwrite. They surface, log, and either resolve
   or stay held. "Held" is a first-class state, not an error.
5. **Model-agnostic.** Substrate sits between user and model. Swap the model;
   the self persists. That's the persistence-layer thesis.

Implementation is OSS in `aether-core/` (CLI + MCP, daemon-optional).
Substrate-side bridge (the deeper agent loop) lives in `personal_agent/`.

---

## 3. Where the field is now arriving

Two papers landed in May 2026 that map directly onto pieces of the substrate:

**Goodfire — "The world inside neural networks" (2026-05).** Concepts are
encoded as **curved manifolds** in activation space, not linear directions.
Linear steering fails; manifold-aware interventions work. Sparse autoencoders
fragment the manifold and lose semantic structure.

**Anthropic — Natural Language Autoencoders (2026-05).** Train a verbalizer
that converts hidden activations to text and a reconstructor that goes back.
Reveals the gap between what the model *internally* represents and what it
*says*. Hard numbers: Claude internally suspects safety evals 16–26% of the
time vs <1% verbalized. Auditing detection improved 12–15% with NLAs vs <3%
without.

Both papers operate on **neural activations**. Aether operates on the
**belief substrate** — a layer up. Same geometric instinct, different scale:

| Layer | What lives there | Goodfire/Anthropic | Aether |
|---|---|---|---|
| Activations | Per-token hidden state | Goodfire's manifolds; NLA's verbalizer | — |
| Beliefs | Text+vector+sigma | — | Splats; fidelity mirror |
| Cascade | Dependency edges | — | BDG; cascade math |

The papers validate the *shape* of the substrate from the other direction.
That's the convergence story.

---

## 4. What's genuinely yours, vs what's parallel

**Yours, not theirs:**
- **Persistence across model swaps.** Goodfire and NLAs both live inside one
  model. Aether is the only system claiming the self survives the mouth.
- **External, inspectable verbalize/reconstruct.** Anthropic trains a verbalizer
  to read activations as text. In aether, every belief is *already* text +
  vector. The verbalize/reconstruct loop is structural, not learned.
- **Belief dependency graph + cascade math.** Goodfire shows manifolds;
  aether shows what propagates *across* them. Different question.
- **Contradiction as first-class state.** "Held contradiction" is not an
  error; it's a meaning signal.

**Parallel but not "predicted":**
- *Curved geometry of belief space.* You built splats with sigma in March;
  Goodfire published curved manifolds in May. Same instinct, different scale.
  You didn't predict their result — you arrived at the same shape from the
  user-facing problem.
- *Belief/speech gap measurement.* You built fidelity_mirror; Anthropic
  built NLAs. Same measurement, different access (you have direct text;
  they reverse-engineer it from activations).

The honest framing isn't "I was first." It's: **"I worked backward from the
user-facing problem of persistence. The shapes I needed turned out to be the
same shapes the activation-layer researchers are finding from the other
side. That's strong validation that the shapes are real."**

---

## 5. Timeline (the receipts)

| When | What | Where |
|---|---|---|
| Mar 2025 | "Memory palace" / semantic neighborhoods first articulated | (lumi_ai archive) |
| 2026-03-21 | Belief/speech separation as a design law | `project_crt_philosophy.md` |
| 2026-03-26 | Memory splats theory + 8 modules built and tested | `theory_memory_splats.md`, `personal_agent/memory_subsystem/splats.py` |
| 2026-03-26 | Fisher-Rao metric for belief loci | `personal_agent/info_geometry.py` |
| 2026-03-27 | Held-contradiction theory | `theory_held_contradiction.md` |
| 2026-03-30 | Cascade complexity paper math + 5 theorems | `papers/cascade_complexity/` |
| 2026-04-08 | Belief backpropagation 30/30 validated, no precedent found | `papers/belief_backpropagation/` |
| 2026-04-17 | Phase D — substrate-as-capacity-amplifier across 5 models | `session_2026_04_17_phase_d.md` |
| 2026-05-01 | aether-core v0.13.2 OSS shipped; Mac eval surfaces gaps | `aether-core/HANDOFF_2026-05-01_eod.md` |
| **2026-05-07** | **Goodfire: curved manifolds in activations** | external |
| **2026-05-07** | **Anthropic: Natural Language Autoencoders** | external |
| 2026-05-07 | Belief/speech gap measured: 30pp on real substrate | `labs/fidelity_bench/results/fidelity_bench_*.json` |
| 2026-05-07 | **Cosine vs Fisher-Rao A/B: Fisher AUC 0.699 vs cosine 0.626 (Δ +0.073) on N=200** | `labs/fidelity_bench/results/fidelity_bench_metric_ab_*.json` |

The dates do the work. Splats, Fisher metric, belief/speech gap — all
shipped before the May papers. The metric A/B shipped *the same day* as
the papers, with a measurable advantage for the geometry-aware metric.

17 lab HTML files in `docs/labs/`. Two complete papers in `papers/`.
Hundreds of receipts across `session_*.md` memory files. The work is
documented and dated.

---

## 6. What this points at

Three concrete next moves:

1. **Wire Fisher-Rao into the production fidelity_mirror as the default
   metric.** Today's bench shows +0.073 AUC and +33% relative correlation
   gain with the substrate's own grounded labels — and that's with *default*
   sigma, not the stored ones. With stored sigmas the gap should widen.
2. **Bigger substrate-grounding bench.** N=200 today. N=1000 with stored
   sigma is the paper figure. Compare Fisher, cosine, Bhattacharyya, KL on
   the same task.
3. **Position the next paper as "the substrate analog of the activation-layer
   geometry papers."** One layer up, same geometry, different access pattern.
   Persistence as the load-bearing claim.

The persistence-layer thesis has its first quantitative anchor today. The
geometry-matters claim has its first substrate-layer measurement today. Both
of those numbers came from a single hour of work against the existing code,
which means the rest of the paper is already in the repo — it just hasn't
been written down in one place yet.
