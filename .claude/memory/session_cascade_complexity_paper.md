---
name: session_cascade_complexity_paper
description: Session thread for writing the belief cascade complexity paper. Definitions, theorems, proofs. Highest-novelty contribution — nobody has formalized single-agent belief revision cascades. Zero compute needed.
type: project
---

# Session Thread: Belief Cascade Complexity Paper

## Why this paper

Three communities (formal epistemology, AI safety, knowledge representation) study adjacent problems but nobody occupies the intersection:

- **AGM belief revision** handles one revision at a time. Iterated revision (Darwiche-Pearl) handles a sequence of external inputs. Neither models internal propagation through a dependency graph.
- **Opinion dynamics** (DeGroot, Friedkin-Johnsen, Deffuant-Weisbuch, Hegselmann-Krause) models populations of agents influencing each other. Nobody has applied cascade dynamics to a SINGLE agent's internal belief state.
- **Belief propagation** (Pearl 1982) does probabilistic inference (computing marginals), not belief revision (incorporating contradictory information). Inference preserves the model; revision changes it.

The gap: **what happens when you revise belief A, and B depends on A, and C depends on B?** No formal treatment exists.

Nick's system (`memory_graph.py`, `crt_ledger.py`, `disposition_classifier.py`) already implements the concrete mechanics. This paper gives it mathematical foundations.

## Paper target

**Title:** "On the Complexity of Belief Revision Cascades in Dependency Graphs"

**Venue options:**
- KR 2026 (Knowledge Representation and Reasoning) — perfect fit
- IJCAI 2026 — broader audience
- AAAI 2026 — if results are strong enough
- Journal of Philosophical Logic — if the formal epistemology angle is strongest
- Artificial Intelligence (Elsevier) — long-form if it grows

## Structure

### Section 1: Introduction
- Motivating example: an AI assistant learns "User moved to Austin" — what happens to "User's commute is 20 minutes" (depends on location) and "User likes their neighborhood cafe" (depends on location) and "User's favorite team is the Lakers" (independent)?
- State the gap: AGM handles the initial revision. Nothing handles the cascade.
- Contribution summary: formal framework + complexity results + stability conditions + connection to existing axiom systems.

### Section 2: Preliminaries
- AGM belief revision (contraction, expansion, revision, the 6 postulates)
- Iterated revision (Darwiche-Pearl postulates)
- Belief dependency (define formally — what does it mean for belief B to "depend on" belief A?)
- Notation for graphs, contradictions, trust weights

### Section 3: Belief Dependency Graphs (NEW DEFINITIONS)

**Definition 3.1 (Belief State).** A belief state is a tuple b = (mu, Sigma, alpha, t) where mu is the content embedding, Sigma encodes uncertainty, alpha is confidence/trust, and t is timestamp. (This IS the splat formalism — grounded in existing code.)

**Definition 3.2 (Belief Dependency Graph).** A BDG is a weighted directed graph G = (V, E, w) where:
- V is a set of belief states
- E subset V x V encodes evidential support (B depends on A iff there exists edge A -> B)
- w: E -> [0,1] encodes dependency strength

**Definition 3.3 (Revision Event).** A revision event r = (b, b') replaces belief b with b' due to external input. The REVISION IMPACT on b is delta(b, b') = d_F(b, b') where d_F is Fisher-Rao distance (connects to info_geometry.py).

**Definition 3.4 (Cascade Trigger).** A revision event r on node v triggers a cascade if there exists v' in successors(v) such that w(v, v') * delta(r) > threshold tau. The triggered node must then be re-evaluated.

**Definition 3.5 (Revision Cascade).** The transitive closure of triggered re-evaluations from a single revision event. Formally: the cascade C(r) is the smallest set S such that:
- v in S (the initial revised node)
- if u in S and there exists edge u -> u' with w(u, u') * delta_cumulative > tau, then u' in S

**Definition 3.6 (Cascade Disposition).** Each triggered re-evaluation inherits a disposition from the disposition classifier:
- TEMPORAL: downstream belief is time-indexed, revision is a temporal update
- CONFLICT: downstream belief genuinely contradicts the revision
- REFINEMENT: downstream belief is a specialization that needs updating
- HELD: downstream belief is in genuine tension but should be preserved (not auto-resolved)

### Section 4: Complexity Results (THEOREMS)

**Theorem 4.1 (Cascade Depth Bound).** For a BDG with maximum dependency depth k (longest directed path), the worst-case cascade depth from a single revision is exactly k.

*Proof sketch:* Each node can be triggered at most once (revisions propagate forward, the graph is a DAG). The longest chain of triggers follows the longest path. Upper bound is tight — construct a chain where every edge has w=1 and delta never decays.

**Theorem 4.2 (Cascade Width).** The number of nodes affected by a cascade in a BDG with n nodes, maximum out-degree d, and depth k is O(min(d^k, n)).

*Proof sketch:* Each triggered node can trigger at most d successors. After k levels, the branching tree has at most d^k leaves. Bounded by n since nodes aren't revisited.

**Theorem 4.3 (Cascade Damping and Convergence).** If dependency weights satisfy w(u,v) < 1 for all edges, and the revision impact function delta is Lipschitz continuous with constant L < 1/max(w), then:
- The cumulative cascade impact decays geometrically: impact at depth j <= (L * w_max)^j * delta_0
- The cascade terminates in finite steps for any tau > 0
- Total cascade cost (sum of all revision impacts) is bounded by delta_0 / (1 - L * w_max)

*This is the stability theorem. It says: if beliefs don't amplify each other too much, cascades always converge.* The damping factor L * w_max is the key parameter — analogous to the spectral radius condition in opinion dynamics.

**Theorem 4.4 (Cascade Instability Condition).** If there exists a cycle in the dependency graph (violating DAG assumption) with product of edge weights > 1/L, then a revision cascade can diverge — revision impacts grow without bound.

*This is the instability theorem. It says: circular dependencies + strong coupling = belief system collapse.* This connects to psychological literature on cognitive dissonance spirals.

**Theorem 4.5 (Optimal Cascade Ordering is NP-hard).** [CONJECTURE — needs proof or disproof]
Given a BDG, a set of k simultaneous revision events, and a goal of minimizing total contradiction in the post-cascade state: finding the optimal order to apply the revisions is NP-hard.

*Approach:* Reduction from minimum vertex cover or maximum satisfiability. The intuition: if revisions interact (A's cascade affects the same nodes as B's cascade), the order matters, and finding the best order requires exploring exponentially many possibilities.

*Alternative:* If this is polynomial, that's ALSO interesting — it means cascade ordering can be solved efficiently, which is a positive result for AI systems.

### Section 5: Special Cases and Properties

**Proposition 5.1 (AGM as Special Case).** Standard AGM belief revision is the special case of cascade theory where the BDG has no edges. All theorems reduce to single-node revision.

**Proposition 5.2 (Tree-Structured BDGs).** For tree-structured dependency graphs, cascade computation is linear in the number of affected nodes (no re-visitation, no ordering ambiguity).

**Proposition 5.3 (Disposition-Aware Cascades).** If HELD contradictions block cascade propagation (the cascade stops at held nodes), then the cascade width is bounded by the number of non-held nodes reachable from the revision point. Held contradictions act as firewalls.

*This is philosophically important: the system's ability to hold contradictions without resolving them is also a stability mechanism that prevents cascade blowup.*

**Proposition 5.4 (Fisher-Weighted Cascade Priority).** If cascade re-evaluations are ordered by Fisher-Rao distance (highest information gain first), the expected total contradiction after cascade completion is minimized among greedy orderings.

### Section 6: Connection to Existing Frameworks

- AGM: cascade theory extends AGM with dependency structure. AGM postulates apply at each node locally.
- Darwiche-Pearl: iterated revision is the special case where all revision events are external (no internal propagation). Cascade theory adds internal propagation.
- Opinion dynamics: DeGroot convergence theorem has an analog in Theorem 4.3. The spectral radius condition on the weight matrix parallels the damping condition.
- Belief propagation: cascade propagation resembles message passing, but messages are revisions (destructive) not marginals (conservative). Different fixed-point properties.

### Section 7: Empirical Illustration
- Small examples from the running system (memory_graph.py)
- Show a concrete cascade on 10-20 beliefs
- Demonstrate damping, held-contradiction firewalls, disposition-aware routing
- NOT the main contribution — the theory is. But reviewers want to see it work.

### Section 8: Discussion
- Implications for AI safety: uncontrolled cascades = catastrophic forgetting; cascade theory gives formal conditions for stability
- Implications for alignment: held contradictions as cascade firewalls connects to value pluralism — the system doesn't need to resolve everything, and that's a feature
- Open problems: cascade theory for continuous belief spaces (not just graphs), cascade theory with probabilistic dependencies, connection to causal inference

## Key references to cite

- Alchourron, Gardenfors, Makinson (1985) — original AGM
- Darwiche & Pearl (1997) — iterated belief revision
- DeGroot (1974) — opinion dynamics convergence
- Friedkin & Johnsen (1990) — social influence networks
- Pearl (1982/1988) — belief propagation
- Kumiho (arXiv March 2026, 2603.17244) — closest competitor, AGM-compliant but no cascades
- "On Definite Iterated Belief Revision with Belief Algebras" (IJCAI 2025)
- Hubinger et al. (2019) — deceptive alignment (motivation for stability analysis)
- Festinger (1957) — cognitive dissonance (psychological analog of cascade instability)
- Vilnis & McCallum (2015) — Gaussian embeddings (foundation for belief states)
- Dec 2025 impossibility result on fixed covariance — motivates context-dependent splats

## What the session should produce

1. LaTeX draft of the paper (or clean markdown that converts to LaTeX)
2. Formal proofs for Theorems 4.1-4.4 (complete)
3. Proof or disproof of Theorem 4.5 (NP-hardness conjecture)
4. Small worked examples for Section 7
5. Figures: example BDGs, cascade propagation diagrams, damping curves

## What's needed from Nick's codebase

- `memory_graph.py` — the concrete BDG implementation (NetworkX graph with typed edges)
- `crt_ledger.py` — contradiction tracking without silent overwrites
- `disposition_classifier.py` — the 4-way classification that feeds Proposition 5.3
- `info_geometry.py` — Fisher-Rao distance that feeds Definition 3.3 and Proposition 5.4
- `memory_splats.py` — the belief state definition (Definition 3.1)

All exist and are tested. The paper formalizes what's already built.

## Feasibility

- Zero compute needed. Theorems are analytic.
- Small examples run on any machine (10-20 node graphs in NetworkX).
- Estimated time: 1-2 focused sessions for definitions + theorems, 1 session for proofs, 1 session for writing.
- No dependency on external data (unlike the corpus study which needs the OpenAI export).

## Risk assessment

- **Scoop risk: VERY LOW.** Nobody is looking at this intersection. AGM people don't model graphs. Opinion dynamics people model populations. KR people do ontology, not revision cascades.
- **Reinvention risk: LOW.** Checked literature thoroughly. Kumiho (March 2026) is the closest work and explicitly does NOT model cascades.
- **Review risk: MODERATE.** Formal epistemology reviewers will scrutinize the AGM connection. Need to be precise about how cascade theory extends (not violates) AGM postulates. KR reviewers will want the NP-hardness result to be airtight.
- **Framing risk:** Must NOT oversell. This is a formal framework contribution with complexity results, not a system paper. The implementation exists but the paper's value is the math.
