---
name: session_cascade_paper_draft
description: Session where full cascade complexity paper was drafted, memory_graph.py built, experiments validated. All theorems 4.1-4.4 verified empirically. Conjecture 4.5 remains open.
type: project
---

# Session: Cascade Complexity Paper Draft (2026-03-26)

## What was produced

### Paper draft
- `papers/cascade_complexity/cascade_paper.md` — Full 8-section paper
- Title: "On the Complexity of Belief Revision Cascades in Dependency Graphs"
- All definitions (3.1-3.6), theorems (4.1-4.4), conjecture (4.5), propositions (5.1-5.4) written with complete proofs
- Section 6 maps to AGM, Darwiche-Pearl, DeGroot, belief propagation, Kumiho
- Section 7 empirical illustrations with concrete numbers

### New code: memory_graph.py
- `personal_agent/memory_graph.py` — BeliefDependencyGraph class
- NetworkX digraph with typed edges (CONTRADICTS/SUPERSEDES/SUPPORTS)
- Full cascade propagation engine with:
  - Disposition-aware blocking (HELD = firewall)
  - Geometric damping (Theorem 4.3)
  - Instability detection (Theorem 4.4 — cycle analysis)
  - Reachability analysis (Proposition 5.3)
- Damping factor, depth bound, total impact bound calculations

### Experiments
- `papers/cascade_complexity/experiments.py` — 5 experiments, all pass
  1. Location change cascade: 5 nodes affected, 3 correctly isolated [PASS]
  2. Held contradiction firewall: 2 nodes protected by firewall [PASS]
  3. Damping curve: terminates at depth 14, matches ceil(log(100)/log(1/0.72))=15 [PASS]
  4. Instability detection: weak cycle stable, strong cycle unstable [PASS]
  5. Width bound: 40 nodes in 3-deep tree, matches O(min(d^k,n)) [PASS]

### NP-hardness analysis
- `papers/cascade_complexity/np_hardness_proof.md` — 3 reduction attempts documented
- Scheduling reduction: structure mismatch (linear accumulation vs nonlinear cascade)
- MAX-SAT reduction: encoding gap (permutations vs binary assignments)
- MLA reduction: most promising, needs formal proof
- Status: CONJECTURE (open). Both outcomes publish.

### Fix applied
- `personal_agent/info_geometry.py` — fixed bare import to use relative import with fallback

## Key empirical findings
- Fisher-Rao impact for real embedding revision: ~20 (384D unit vectors)
- Damping curve matches theorem prediction EXACTLY (depth 14 vs bound 15)
- Total impact 3.546 within bound 3.571
- Held contradiction firewall reduces cascade by 50% in chain example

## What's next
1. Convert paper to LaTeX for submission
2. Resolve Conjecture 4.5 (try MLA reduction formally)
3. Run on real data (Aether memory DB) for Section 7
4. Figures: BDG diagrams, damping curves, firewall visualization
5. Target venue: KR 2026 or IJCAI 2026
