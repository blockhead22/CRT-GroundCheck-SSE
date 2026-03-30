# On the Complexity of Belief Revision Cascades in Dependency Graphs

**Nick Block**
Aeteros Research

---

## Abstract

We introduce *belief revision cascades* — the transitive propagation of belief changes through a dependency graph within a single agent's epistemic state. While AGM belief revision handles individual revisions and iterated revision handles sequences of external inputs, neither framework models what happens when revising belief $A$ forces re-evaluation of dependent beliefs $B$, $C$, $D$, and so on. We formalize this gap through *Belief Dependency Graphs* (BDGs), prove bounds on cascade depth and width, and establish two convergence results: *per-node* impact decays geometrically when the damping factor $\rho = L \cdot w_{\max} < 1$ (the single-agent analog of DeGroot's theorem), while *graph-wide* total impact converges only under the stricter condition $d \cdot \rho < 1$ where $d$ is the out-degree. We characterize iterated cascade instability on cyclic graphs and conjecture NP-hardness of optimal cascade ordering. A key result: *held contradictions* — beliefs the system deliberately does not resolve — act as cascade firewalls, bounding propagation and preventing catastrophic revision storms. We validate on both constructed examples and a production BDG (599 beliefs), finding that real belief graphs have high fan-out ($d \approx 8$), making graph-wide cascade reach inherently broad even when per-node impact is well-controlled.

**Keywords:** belief revision, dependency graphs, cascade complexity, held contradictions, epistemic stability, AGM, opinion dynamics

---

## 1. Introduction

Consider an AI assistant that learns "the user moved from Portland to Austin." This single fact triggers a cascade of downstream revisions: the user's commute time is now invalid, their neighborhood preferences need updating, their weather-related preferences shift, and their local social circle has changed. Meanwhile, "the user's favorite team is the Lakers" is unaffected — it has no dependency on location.

This example illustrates a gap in the formal epistemology literature. The AGM framework (Alchourrón, Gärdenfors, & Makinson, 1985) provides elegant axioms for *individual* belief revision — how to contract, expand, or revise a belief set in response to new information. The Darwiche-Pearl postulates (1997) extend AGM to *iterated* revision — how to handle a *sequence* of external inputs. But neither framework addresses the *internal propagation* that follows a revision: when revising one belief forces re-evaluation of others through dependency relationships.

Three adjacent communities study related problems without occupying this intersection:

1. **AGM belief revision** handles one revision at a time. Dependencies between beliefs are implicit in the epistemic entrenchment ordering but never modeled as an explicit graph structure.

2. **Opinion dynamics** (DeGroot, 1974; Friedkin & Johnsen, 1990; Hegselmann & Krause, 2002) models cascade-like propagation, but across *populations of agents*. Nobody has applied cascade dynamics to a *single agent's* internal belief state.

3. **Belief propagation** (Pearl, 1982) computes posterior marginals in probabilistic graphical models. This is *inference* (computing what follows from a fixed model) not *revision* (incorporating information that contradicts the model). Inference preserves the model; revision changes it.

**Our contribution.** We introduce *Belief Dependency Graphs* (BDGs) as a formal structure for studying intra-agent belief revision cascades. We provide:

- Formal definitions grounding belief states, dependency structures, revision events, and cascade propagation, including an explicit multi-parent aggregation rule (Section 3)
- Complexity bounds: cascade depth is bounded by the longest DAG path (Theorem 4.1), width by $O(\min(d^k, n))$ (Theorem 4.2)
- Two convergence results: *per-node* impact decays geometrically when $\rho = L \cdot w_{\max} < 1$ (Theorem 4.3); *graph-wide* total impact converges only when $d \cdot \rho < 1$ (Corollary 4.3.1), where $d$ is the maximum out-degree
- An iterated cascade instability condition: cyclic dependencies with strong coupling produce divergent revision sequences (Theorem 4.4) — formalizing cognitive dissonance spirals
- A conjecture that optimal cascade ordering is NP-hard via reduction from Minimum Linear Arrangement (Conjecture 4.5)
- A philosophical result: *held contradictions* — beliefs the system deliberately preserves in tension — act as cascade firewalls (Proposition 5.3), connecting epistemic pluralism to system stability
- Empirical validation on a production BDG (599 beliefs), confirming per-node damping and revealing that real belief graphs have $d \cdot \rho \gg 1$, making broad cascade reach a structural property of typical belief systems (Section 7.5)

All definitions map to modules in a running system. This is not a paper about that system — the contribution is the mathematics — but the implementation demonstrates that the formalism captures real mechanics.

---

## 2. Preliminaries

### 2.1 AGM Belief Revision

A *belief set* $K$ is a deductively closed set of sentences. AGM revision $K * \varphi$ incorporates sentence $\varphi$ into $K$, potentially removing existing beliefs to maintain consistency. The six AGM postulates constrain this operation (closure, success, inclusion, vacuity, consistency, extensionality). The *Levi identity* decomposes revision into contraction followed by expansion: $K * \varphi = (K \div \neg\varphi) + \varphi$.

**Epistemic entrenchment** (Gärdenfors & Makinson, 1988) orders beliefs by how resistant they are to removal. More entrenched beliefs survive revision; less entrenched beliefs are contracted first.

### 2.2 Iterated Belief Revision

Darwiche & Pearl (1997) extend AGM to sequences of revisions. Given a *conditional belief state* $\Psi$ and input $\varphi$, the revised state $\Psi * \varphi$ must satisfy four additional postulates constraining how $\Psi * \varphi$ responds to further revision by $\psi$. The key insight: a single belief state $\Psi$ encodes not just current beliefs but dispositions toward future revision.

### 2.3 Opinion Dynamics

DeGroot's model (1974): agents $1, \ldots, n$ hold opinions $x_i(t) \in [0,1]$. At each step, $x_i(t+1) = \sum_j w_{ij} x_j(t)$ where $W = [w_{ij}]$ is a row-stochastic weight matrix. Convergence to consensus is guaranteed when $W$ is connected and aperiodic — formally, when the spectral radius of $W - \mathbf{1}\pi^T$ is less than 1.

### 2.4 Notation

| Symbol | Meaning |
|--------|---------|
| $b = (\mu, \Sigma, \alpha, t)$ | Belief state (Definition 3.1) |
| $G = (V, E, w)$ | Belief Dependency Graph (Definition 3.2) |
| $r = (b, b')$ | Revision event (Definition 3.3) |
| $\delta(r)$ | Revision impact |
| $d_F(\cdot, \cdot)$ | Fisher-Rao distance |
| $\tau$ | Cascade trigger threshold |
| $C(r)$ | Revision cascade from event $r$ |
| $\mathcal{D}(v)$ | Disposition of node $v$ |

---

## 3. Belief Dependency Graphs

### Definition 3.1 (Belief State)

A **belief state** is a tuple $b = (\mu, \Sigma, \alpha, t)$ where:

- $\mu \in \mathbb{R}^d$ is the content embedding (the semantic center of the belief)
- $\Sigma \in \mathbb{R}^{d \times d}_{++}$ is a positive definite covariance matrix encoding *uncertainty* — the shape and extent of the region in semantic space consistent with this belief
- $\alpha \in [0, 1]$ is the confidence (how strongly the belief contributes to the agent's world model)
- $t \in \mathbb{R}_{\geq 0}$ is the timestamp of last modification

In practice, $\Sigma$ is restricted to diagonal covariance $\Sigma = \mathrm{diag}(\sigma_1, \ldots, \sigma_d)$, reducing storage from $O(d^2)$ to $O(d)$ while preserving per-dimension uncertainty.

**Interpretation.** A belief state is a Gaussian splat in semantic space — a soft probabilistic region rather than a hard point. A tight splat ($\sigma_i$ small) represents a settled belief; a wide splat represents an uncertain or contested belief. The covariance encodes *where* the uncertainty lives, not just *how much* there is.

> **Implementation.** Class `MemorySplat` in `memory_splats.py`: fields `mu` ($\mu$), `sigma` ($\Sigma_{\mathrm{diag}}$), `alpha` ($\alpha$), `last_updated` ($t$). Phase 1 uses diagonal covariance; Phase 2 extends to low-rank $\Sigma = D + UU^T$.

### Definition 3.2 (Belief Dependency Graph)

A **Belief Dependency Graph** (BDG) is a weighted directed graph $G = (V, E, w)$ where:

- $V = \{b_1, \ldots, b_n\}$ is a set of belief states
- $E \subseteq V \times V$ is a set of directed edges encoding *evidential support*: $(b_i, b_j) \in E$ means $b_j$ depends on $b_i$ (revision of $b_i$ may necessitate revision of $b_j$)
- $w: E \to (0, 1]$ is a weight function encoding *dependency strength*: $w(b_i, b_j) = 1$ means $b_j$ is fully dependent on $b_i$; smaller weights mean weaker coupling

Edges are *typed*. We distinguish:

- **CONTRADICTS**: $b_i$ and $b_j$ are in detected semantic tension (NLI score above threshold)
- **SUPERSEDES**: $b_j$ is a temporal update of $b_i$ (same topic, later timestamp)
- **SUPPORTS**: $b_j$ is evidentially grounded in $b_i$ (revision of $b_i$ undermines the basis for $b_j$)

> **Implementation.** NetworkX digraph with typed edges, weighted by dependency strength. Edge types mirror `ContradictionType` in `crt_ledger.py` (REFINEMENT, REVISION, TEMPORAL, CONFLICT). Node attributes are `MemorySplat` instances.

### Definition 3.3 (Revision Event)

A **revision event** is a pair $r = (b, b')$ that replaces belief state $b$ with $b'$ at some node $v \in V$, triggered by external input.

The **revision impact** of $r$ is:

$$\delta(r) = d_F(b, b')$$

where $d_F$ is the Fisher-Rao distance on the space of belief states. For diagonal Gaussian splats:

$$d_F(b, b')^2 = \sum_{i=1}^{d} \frac{(\mu_i - \mu'_i)^2}{\bar{\sigma}_i} + \frac{1}{2}\sum_{i=1}^{d} \left(\log \frac{\sigma_i}{\sigma'_i}\right)^2$$

where $\bar{\sigma}_i = (\sigma_i + \sigma'_i)/2$.

**Why Fisher-Rao?** Cosine distance ignores uncertainty: two beliefs with identical centers but different confidence levels ($\alpha = 0.95$ vs. $\alpha = 0.3$) have cosine distance 0. Fisher-Rao distance respects the information geometry — disagreement on dimensions where the agent is *certain* weighs more than disagreement where the agent is already *uncertain*.

> **Implementation.** `fisher_rao_distance()` in `info_geometry.py`. Experimentally validated: Fisher distance between certain-belief pairs is $3.16\times$ larger than between uncertain-belief pairs with identical center displacement. Cosine sees them as equal ($1.00\times$).

### Definition 3.4 (Cascade Trigger)

A revision event $r$ on node $v$ **triggers a cascade** to successor $v'$ if:

$$w(v, v') \cdot \delta(r) > \tau$$

where $\tau > 0$ is a threshold parameter. The triggered node $v'$ must be *re-evaluated* — its belief state is updated in light of the revised $v$.

**Interpretation.** A cascade triggers when the revision is large enough *and* the dependency is strong enough. A small revision to a weakly-connected neighbor does not propagate. A large revision to a strongly-connected neighbor does.

### Definition 3.5 (Revision Cascade)

The **revision cascade** $C(r)$ from revision event $r$ on node $v_0$ is the pair $(S, \delta)$ where $S \subseteq V$ is the set of affected nodes and $\delta: S \to \mathbb{R}_{> 0}$ assigns an impact to each, defined by:

1. $v_0 \in S$ with $\delta(v_0) = \delta(r)$ (the initial revision impact)
2. For each node $u' \in V$ with at least one predecessor $u \in S$ such that $(u, u') \in E$, define the **incoming impact**:

$$\delta_{\mathrm{in}}(u') = \max_{u \in S : (u, u') \in E} \, w(u, u') \cdot \delta(u)$$

If $\delta_{\mathrm{in}}(u') > \tau$, then $u' \in S$ with $\delta(u') = L_{u'} \cdot \delta_{\mathrm{in}}(u')$, where $L_{u'}$ is the Lipschitz constant of the local revision function at $u'$.

3. Propagation proceeds in topological order on DAGs. For graphs with cycles, see Theorem 4.4.

**Multi-parent aggregation.** When a node has multiple predecessors in $S$, we take the *maximum* incoming impact (not the sum). This is the conservative choice: it ensures the per-node impact bound $\delta(v) \leq \rho^{d(v)} \cdot \delta_0$ (where $d(v)$ is the depth of $v$) still holds. Summation would be more realistic for some applications but breaks the geometric decay guarantee (see Section 7.5).

**Remark.** The choice of MAX vs. SUM aggregation is a modeling decision. MAX preserves per-node decay bounds at the cost of underestimating total disruption. SUM better captures the intuition that a node with many revised predecessors faces more pressure, but requires a different convergence analysis.

### Definition 3.6 (Cascade Disposition)

Each triggered re-evaluation at a node $v$ inherits a **disposition** $\mathcal{D}(v)$ from the disposition classifier:

- **TEMPORAL** ($\mathcal{D}(v) = T$): the downstream belief is time-indexed; the revision is a routine temporal update. Propagation continues with reduced impact.
- **CONFLICT** ($\mathcal{D}(v) = C$): the downstream belief genuinely contradicts the revision. Full cascade impact applies.
- **REFINEMENT** ($\mathcal{D}(v) = R$): the downstream belief is a specialization that needs adjustment. Moderate cascade impact.
- **HELD** ($\mathcal{D}(v) = H$): the downstream belief is in genuine tension with the revision but *should not be auto-resolved*. **Cascade propagation stops at held nodes.** The tension is preserved.

> **Implementation.** `classify_contradiction()` in `disposition_classifier.py`. Four-way classification using subjectivity, temporal gap, entity specificity, sentiment, and domain signals. 18/18 on test suite covering all disposition types.

---

## 4. Complexity Results

### Theorem 4.1 (Cascade Depth Bound)

**Statement.** For a BDG $G = (V, E, w)$ that is a directed acyclic graph (DAG) with maximum directed path length $k$, the worst-case cascade depth from a single revision event is exactly $k$.

**Proof.**

*Upper bound.* In a DAG, every directed path has length at most $k$. A cascade propagates along directed edges. Since $G$ is acyclic, no node can be visited twice (visiting $v$ twice requires a cycle through $v$). Therefore the cascade can traverse at most $k$ edges from the initial node, giving depth $\leq k$. $\square$

*Tightness.* Construct a path graph $v_0 \to v_1 \to \cdots \to v_k$ with $w(v_i, v_{i+1}) = 1$ for all $i$. Let the initial revision have impact $\delta_0 > \tau$, and let the revision impact function preserve impact exactly: $L_i = 1$ at each node, so $\delta_{i+1} = \delta_i$ (each re-evaluation produces impact equal to its input, with $\rho = L \cdot w = 1$). Then every node in the path is triggered, giving cascade depth exactly $k$. Note that tightness requires $\rho = 1$ exactly; for any $\rho < 1$, the cascade terminates before depth $k$ (at depth $\lceil \log(\delta_0/\tau) / \log(1/\rho) \rceil$ per Theorem 4.3). $\square$

**Remark.** The DAG assumption is critical. With cycles, *iterated* cascades can revisit nodes (see Theorem 4.4).

### Theorem 4.2 (Cascade Width)

**Statement.** The number of nodes affected by a cascade in a BDG with $n$ nodes, maximum out-degree $d$, and cascade depth $k$ is $O(\min(d^k, n))$.

**Proof.** At each level of cascade propagation, each triggered node can trigger at most $d$ successors. Starting from a single node at depth 0:

- Depth 0: 1 node
- Depth 1: at most $d$ nodes
- Depth $j$: at most $d^j$ nodes

Total affected: $\sum_{j=0}^{k} d^j = \frac{d^{k+1} - 1}{d - 1} = O(d^k)$ for $d \geq 2$.

This is bounded by $n$ since no node is visited twice in a DAG. Therefore the cascade width is $O(\min(d^k, n))$. $\square$

**Corollary 4.2.1 (Sparse Graphs).** For BDGs with bounded out-degree $d = O(1)$, cascade width is $O(\min(c^k, n))$ for constant $c$. For $k = O(\log n)$ (as in balanced dependency structures), total cascade size is polynomial.

**Corollary 4.2.2 (Dense Graphs).** For BDGs with $d = O(n)$, a single revision can trigger $\Theta(n)$ re-evaluations in one step. Dense dependency structures admit catastrophic cascades.

### Theorem 4.3 (Per-Node Cascade Damping)

**Statement.** Let $G = (V, E, w)$ be a BDG (DAG) with:

1. $w_{\max} = \max_{(u,v) \in E} w(u,v) < 1$ (all dependency weights strictly subunitary)
2. The revision impact function at each node is Lipschitz continuous with constant $L > 0$: if the input impact is $\delta_{\mathrm{in}}$, the output impact satisfies $\delta_{\mathrm{out}} \leq L \cdot \delta_{\mathrm{in}}$

If $\rho = L \cdot w_{\max} < 1$, then under MAX aggregation (Definition 3.5):

(a) The impact at any node $v$ at depth $j$ from the source satisfies $\delta(v) \leq \rho^j \cdot \delta_0$

(b) The cascade terminates in at most $k^* = \lceil \log(\delta_0 / \tau) / \log(1/\rho) \rceil$ depth steps

(c) The total impact along any single directed path is bounded: $\sum_{j=0}^{k^*} \delta_j \leq \frac{\delta_0}{1 - \rho}$

**Proof.**

*(a) Per-node geometric decay.* At depth 0, the impact is $\delta_0$. At depth 1, each triggered successor receives incoming impact at most $w_{\max} \cdot \delta_0$ (since MAX over predecessors is bounded by the single-predecessor case). After local re-evaluation: $\delta(v) \leq L \cdot w_{\max} \cdot \delta_0 = \rho \cdot \delta_0$. By induction at depth $j$: $\delta(v) \leq \rho^j \cdot \delta_0$. Since $\rho < 1$, this is geometric decay. The MAX aggregation rule is critical: it ensures that multiple predecessors do not accumulate impact beyond the worst single predecessor. $\square$

*(b) Finite termination.* The cascade terminates when $\rho^j \cdot \delta_0 \leq \tau$, giving $j \geq \log(\delta_0/\tau) / \log(1/\rho)$. $\square$

*(c) Per-path total.* Along any single path from source to leaf: $\sum_{j=0}^{k^*} \delta_j \leq \sum_{j=0}^{k^*} \rho^j \cdot \delta_0 \leq \delta_0 / (1 - \rho)$. $\square$

**Remark.** Part (c) bounds the total impact along *one path*, not the total across the entire graph. See Corollary 4.3.1 for the graph-wide bound.

**Corollary 4.3.1 (Graph-Wide Cascade Cost).** Let $W_j$ denote the set of nodes at depth $j$ from the source in the cascade. The total impact across all affected nodes is bounded by:

$$\sum_{v \in C(r)} \delta(v) \leq \delta_0 \sum_{j=0}^{k^*} |W_j| \cdot \rho^j$$

Since $|W_j| \leq \min(d^j, n)$ where $d$ is the maximum out-degree (Theorem 4.2), this gives:

$$\sum_{v \in C(r)} \delta(v) \leq \delta_0 \sum_{j=0}^{k^*} \min(d^j, n) \cdot \rho^j$$

If $d \cdot \rho < 1$, the graph-wide total converges to at most $\delta_0 / (1 - d\rho)$, independent of graph size. If $d \cdot \rho \geq 1$, the total can grow as $O(n \cdot \delta_0)$ — a single revision can produce aggregate impact proportional to graph size.

*Proof.* Each node at depth $j$ has impact $\leq \rho^j \cdot \delta_0$ by Theorem 4.3(a). Summing over all nodes at each depth level and applying the width bound from Theorem 4.2 gives the result. $\square$

**Interpretation.** The condition $\rho < 1$ guarantees that *per-node* impacts decay geometrically — no individual belief is revised too violently. The stronger condition $d \cdot \rho < 1$ guarantees that *aggregate* disruption is bounded — the system as a whole absorbs the cascade without proportional damage. When $\rho < 1$ but $d \cdot \rho \geq 1$ (which is the typical case in real BDGs — see Section 7.5), individual nodes are safe but the cascade reaches most of the graph. This is the single-agent analog of the distinction in opinion dynamics between *local* convergence (each agent stabilizes) and *global* convergence (the population reaches consensus): DeGroot's theorem requires the spectral radius of the full influence matrix $W$ to be subunitary, not just the maximum single entry.

**Remark.** The Lipschitz constant $L$ captures how much a node *amplifies* incoming revisions. If $L < 1$, the node dampens; if $L > 1$, it amplifies. Amplifying nodes are dangerous only when coupled with strong dependencies ($L \cdot w_{\max} \geq 1$).

### Theorem 4.4 (Iterated Cascade Instability)

Definition 3.5 defines a single cascade as a one-shot propagation through the BDG (in topological order for DAGs). On DAGs, cascades always terminate — acyclicity alone guarantees this, independent of $\rho$. When cycles are present, however, we must consider what happens when cascades are *iterated*: the output state of one cascade becomes the input to the next.

**Definition 4.4.1 (Iterated Cascade).** Given a BDG with a directed cycle $\gamma = v_1 \to v_2 \to \cdots \to v_m \to v_1$, an **iterated cascade** is a sequence of single cascades $C^{(0)}, C^{(1)}, \ldots$ where each $C^{(t+1)}$ is triggered by the revised belief states produced by $C^{(t)}$. Specifically: after $C^{(t)}$ revises $v_m$, the revised state of $v_m$ triggers a new cascade $C^{(t+1)}$ starting at $v_1$ (via the edge $v_m \to v_1$).

**Statement.** If the BDG contains a directed cycle $\gamma = v_1 \to v_2 \to \cdots \to v_m \to v_1$ and the revision impact functions at each node have Lipschitz constants $L_1, \ldots, L_m$ that remain constant across iterations, then the impact at $v_1$ after $k$ iterations satisfies:

$$\delta^{(k)} \leq \lambda^k \cdot \delta^{(0)}$$

where $\lambda = \prod_{i=1}^{m} w(v_i, v_{i+1 \bmod m}) \cdot L_i$ is the **cycle amplification factor**.

If $\lambda > 1$, impacts grow without bound: $\delta^{(k)} \to \infty$ as $k \to \infty$.

**Proof.** Each iteration traverses the cycle once. The impact entering $v_1$ at iteration $t$ propagates through $v_2, \ldots, v_m$, accumulating the product of edge weights and Lipschitz constants. By the Lipschitz property at each node, the impact returning to $v_1$ is at most $\lambda \cdot \delta^{(t)}$. By induction: $\delta^{(k)} \leq \lambda^k \cdot \delta^{(0)}$. $\square$

**Caveat: constant-$L$ assumption.** The proof assumes the Lipschitz constants $L_i$ are the same on every iteration. In practice, belief revision is nonlinear: after a large revision at $v_i$, the belief state changes, and the effective Lipschitz constant on the next pass may differ. If revisions cause the belief to approach a fixed point, $L_i$ may decrease across iterations, producing convergence even when $\lambda > 1$ at the first iteration. The theorem characterizes instability of the *linearized* dynamics around the current state, analogous to how eigenvalue analysis characterizes local stability of nonlinear dynamical systems.

**Interpretation.** This formalizes *cognitive dissonance spirals*. When two or more beliefs are circularly dependent and strongly coupled, attempting to resolve tension at one node amplifies tension at another, which feeds back to the first. The diagnostic is $\lambda > 1$: if the product of coupling strengths around any cycle exceeds 1, the linearized belief dynamics are unstable. In a real system, this instability manifests as oscillating revisions with increasing intensity until either (a) a nonlinear saturation effect stabilizes the system, or (b) the system implements a cycle-breaking mechanism (see Proposition 5.3 — held contradictions as firewalls).

**Remark.** Theorems 4.3 and 4.4 partition the design space. For DAGs: cascades always terminate, and $\rho < 1$ gives tight bounds on depth and per-node impact. For cyclic graphs: single cascades still terminate (Definition 3.5 processes each node once), but *iterated* cascades can diverge when $\lambda > 1$. The practical implication: cycle detection in the BDG is a safety diagnostic. Any cycle with $\lambda > 1$ should be broken by designating one node as HELD (Proposition 5.3).

### Conjecture 4.5 (NP-Hardness of Optimal Cascade Ordering)

**Problem (OPTIMAL-CASCADE-ORDER).** Given a BDG $G = (V, E, w)$, a set of $k$ simultaneous revision events $\{r_1, \ldots, r_k\}$ at distinct nodes, and an objective of minimizing total post-cascade contradiction:

$$\min_{\pi} \sum_{v \in V} \phi_\pi(v)$$

where $\pi$ is a permutation of $\{1, \ldots, k\}$ and $\phi_\pi(v)$ is the contradiction at $v$ after applying revisions in order $r_{\pi(1)}, \ldots, r_{\pi(k)}$ with full cascade propagation between each. Is finding the optimal $\pi$ NP-hard?

**Intuition.** When revision cascades from different events overlap — i.e., $C(r_i) \cap C(r_j) \neq \emptyset$ — the order matters. Applying $r_i$ first may leave shared nodes in a state that amplifies the cascade from $r_j$, or dampens it.

**Approach to proof.** The most promising reduction is from **Minimum Linear Arrangement** (MLA), known NP-hard (Garey, Johnson, & Stockmeyer, 1976). Given a graph $H = (V_H, E_H)$, MLA asks for a permutation $\pi$ of $V_H$ minimizing $\sum_{(u,v) \in E_H} |\pi(u) - \pi(v)|$.

*Reduction sketch.* Each vertex in $H$ becomes a revision event. Each edge in $H$ becomes a shared downstream node in the BDG. The cascade interaction cost between revisions $r_i, r_j$ sharing a downstream node is monotone in $|\pi(i) - \pi(j)|$: revisions far apart in the ordering interact more destructively because intermediate revisions have modified the shared state.

**Status: open.** The reduction has the right structure — permutation to permutation, with interaction cost depending on ordering distance — but a formal proof that the BDG cascade cost faithfully encodes the MLA objective has not been completed. The key gap: showing that cascade interactions between non-adjacent events do not introduce structure that makes the problem easier. We have also investigated reductions from Minimum Weighted Vertex Cover and MAX-SAT (see Appendix B); neither maps cleanly to the permutation structure of cascade ordering.

**Remark.** If this conjecture is *false* — i.e., optimal ordering is polynomial — that is equally publishable. It would mean AI systems can efficiently schedule multi-revision cascades, a positive result for practical system design.

---

## 5. Special Cases and Properties

### Proposition 5.1 (AGM as Special Case)

Standard AGM belief revision is the special case of cascade theory where the BDG has no edges ($E = \emptyset$). All theorems reduce to single-node revision: cascade depth is 0, width is 1, and convergence is trivially satisfied.

*Proof.* With $E = \emptyset$, no cascade can propagate. A revision event affects only the revised node. The six AGM postulates apply locally at that node. $\square$

### Proposition 5.2 (Tree-Structured BDGs)

For tree-structured BDGs (each node has at most one parent), cascade computation is linear in the number of affected nodes: $O(|C(r)|)$. No ordering ambiguity exists — there is exactly one propagation path to each affected node.

*Proof.* In a tree, the subgraph reachable from any node is itself a tree. Cascade propagation visits each node at most once, in topological order (guaranteed unique for trees). No re-visitation, no ordering choice. $\square$

### Proposition 5.3 (Held Contradictions as Cascade Firewalls)

**Statement.** If nodes with disposition $\mathcal{D}(v) = H$ (HELD) block cascade propagation — i.e., a triggered re-evaluation at a held node does not propagate to its successors — then the cascade width is bounded by the number of non-held nodes reachable from the revision point.

Formally, let $V_H = \{v \in V : \mathcal{D}(v) = H\}$ be the set of held nodes. The *effective reachable set* from $v_0$ is:

$$R_H(v_0) = \{v \in V : \exists \text{ directed path } v_0 \to v \text{ that passes through no node in } V_H\}$$

Then $|C(r)| \leq |R_H(v_0)|$.

*Proof.* Cascade propagation follows directed paths. If propagation stops at every held node, only paths that avoid held nodes contribute to the cascade. The set of nodes reachable via such paths is exactly $R_H(v_0)$, which has cardinality $|R_H(v_0)| \leq |V \setminus V_H|$. $\square$

**Philosophical interpretation.** The system's ability to *hold* a contradiction without resolving it is also a *stability mechanism*. A held contradiction says "I acknowledge the tension but will not propagate a resolution." This prevents local tension from cascading into global belief system disruption.

This connects to value pluralism: an agent that insists on resolving every contradiction is vulnerable to cascade storms. An agent that can tolerate genuine tension — "I love my job" and "my job is killing me" coexisting — is structurally more stable.

**Corollary 5.3.1 (Firewall placement).** If held nodes form a vertex cut in $G$ separating the revision source from a subgraph $G'$, then no node in $G'$ is affected by the cascade. Strategic placement of held contradictions can isolate subsystems.

### Conjecture 5.4 (Fisher-Weighted Cascade Priority)

**Statement.** If cascade re-evaluations at each depth level are ordered by Fisher-Rao distance from the revised predecessor (highest information distance first), the expected total contradiction after cascade completion is minimized among greedy orderings.

**Intuition.** Revising the most informationally distant dependent first allows downstream nodes to absorb the largest perturbation early, when the system has the most room to adjust. Late revisions face a landscape already partially relaxed.

**Status: unproven.** A natural proof strategy would show that contradiction reduction under greedy ordering is submodular, then apply the $(1-1/e)$ greedy approximation bound. However: (1) submodularity of contradiction reduction has not been established — it depends on the interaction structure of the BDG, which is problem-specific; (2) the standard greedy bound applies to submodular *maximization*, whereas minimizing total contradiction is a *minimization* problem, requiring the objective to be *supermodular* for the greedy bound to apply. These are not equivalent. We state this as a conjecture pending a proof or counterexample.

> **Implementation.** `fisher_rao_distance()` in `info_geometry.py` provides the ordering metric. Empirically, Fisher-distance ordering outperforms random ordering in cascade simulations, but we have not established theoretical optimality.

---

## 6. Connection to Existing Frameworks

### 6.1 AGM Belief Revision

Cascade theory *extends* AGM, it does not violate it. At each node in the BDG, the local belief revision satisfies the AGM postulates: the revision is consistent (postulate 5), the result includes the new information (postulate 2), and the change is minimal (postulate 4, via epistemic entrenchment). Cascade theory adds inter-node propagation *on top of* local AGM compliance.

### 6.2 Darwiche-Pearl Iterated Revision

Iterated revision is the special case where all revision events are *external* — each revision comes from outside the agent, not from propagation through the dependency graph. Cascade theory adds *internal* propagation: the agent's response to a single external revision may itself generate a sequence of internal revisions, each satisfying Darwiche-Pearl postulates locally.

### 6.3 DeGroot Opinion Dynamics

DeGroot's convergence theorem states that iterated weighted averaging converges to consensus iff the influence matrix $W$ has spectral radius less than 1 (excluding the unit eigenvalue). Theorem 4.3 is the single-agent analog: cascade damping converges iff $\rho = L \cdot w_{\max} < 1$. The correspondence is:

| Opinion Dynamics | Cascade Theory |
|-----------------|---------------|
| Agent $i$ | Belief node $v_i$ |
| Influence weight $w_{ij}$ | Dependency weight $w(v_i, v_j)$ |
| Opinion update | Belief re-evaluation |
| Spectral radius of $W$ $< 1$ | Per-node: $\rho = L \cdot w_{\max} < 1$; Graph-wide: $d \cdot \rho < 1$ |
| Consensus | Cascade termination |

**Important distinction.** DeGroot's convergence condition involves the spectral radius of the *full weight matrix* $W$, which captures global graph structure. Our per-node condition $\rho < 1$ is analogous to bounding the *maximum entry* of $W$, which is necessary but not sufficient for global convergence. The graph-wide condition $d \cdot \rho < 1$ (Corollary 4.3.1) is the closer analog to DeGroot's spectral condition, though it uses a degree-based bound rather than the true spectral radius.

### 6.4 Belief Propagation

Pearl's belief propagation computes marginal probabilities by passing messages along a graphical model. Cascade propagation resembles message passing, but there is a fundamental difference: BP messages are *conservative* (they compute what follows from a fixed model) while cascade messages are *destructive* (they modify the model as they propagate). BP has a unique fixed point on trees; cascade propagation has a unique result on DAGs (Proposition 5.2) but may diverge on cyclic structures (Theorem 4.4).

### 6.5 Kumiho (Baek et al., 2026)

The closest recent work is Kumiho (arXiv 2603.17244), which provides an AGM-compliant belief revision framework for LLMs using entrenchment orderings derived from token surprisal. However, Kumiho *explicitly does not model cascades* — each revision is treated independently. Our framework extends this: Kumiho's local revision mechanics could serve as the node-level revision function within a BDG.

---

## 7. Empirical Illustration

We demonstrate cascade mechanics on small BDGs (10-20 nodes) using the running implementation.

### 7.1 Setup

Belief states are `MemorySplat` instances with $d = 384$ (matching standard sentence embedding dimensionality). Dependencies are constructed by hand for interpretability. Revision impact is Fisher-Rao distance (`info_geometry.py`). Dispositions are classified by the Phase 1 rule-based classifier (`disposition_classifier.py`).

### 7.2 Example: Location Change Cascade

**BDG structure.** 8 beliefs connected by typed dependencies:

```
location("Portland") ─SUPPORTS→ commute("20 min bike")
                      ─SUPPORTS→ neighborhood("Pearl District")
                      ─SUPPORTS→ weather_pref("rain gear")
                      ─SUPPORTS→ social("Portland friends")

job_satisfaction("love my job") ─CONTRADICTS→ burnout("feeling exhausted")

favorite_team("Lakers")  [no dependencies]
```

**Revision event.** $r$: `location` changes from "Portland" to "Austin."

**Expected cascade:**
- `commute`, `neighborhood`, `weather_pref`, `social` are all triggered (SUPPORTS edges from `location`)
- `job_satisfaction`, `burnout`, `favorite_team` are unaffected (no path from `location`)
- Cascade depth: 1 (all dependents are direct successors)
- Cascade width: 4

### 7.3 Example: Held Contradiction as Firewall

**BDG structure.** Chain: `career_goal` → `job_type` → `work_hours` → `life_balance`

With held contradiction at `job_type` (user says "I want a high-powered career" and "I want a chill job"):

**Without firewall:** Revising `career_goal` cascades through all 4 nodes (depth 3).

**With firewall:** Revising `career_goal` triggers `job_type`, but `job_type` has disposition HELD. Cascade stops. `work_hours` and `life_balance` are unaffected. The held contradiction *absorbs* the cascade.

### 7.4 Example: Damping Curve

Construct a chain of 10 nodes with $w = 0.8$ on each edge and $L = 0.9$ (slightly dampening revision function). Initial impact $\delta_0 = 1.0$, threshold $\tau = 0.01$.

Damping factor: $\rho = 0.8 \times 0.9 = 0.72$.

| Depth | Impact | Triggered? |
|-------|--------|-----------|
| 0 | 1.000 | Yes |
| 1 | 0.720 | Yes |
| 2 | 0.518 | Yes |
| 3 | 0.373 | Yes |
| 4 | 0.269 | Yes |
| 5 | 0.193 | Yes |
| 6 | 0.139 | Yes |
| 7 | 0.100 | Yes |
| 8 | 0.072 | Yes |
| 9 | 0.052 | Yes |
| 10 | 0.037 | Yes |
| 11 | 0.027 | Yes |
| 12 | 0.019 | Yes |
| 13 | 0.014 | Yes |
| 14 | 0.010 | No ($\leq \tau$) |

Cascade terminates at depth 14, matching the bound: $\lceil \log(1.0/0.01) / \log(1/0.72) \rceil = \lceil 4.605 / 0.329 \rceil = 14$.

### 7.5 Production BDG: Empirical Topology and Cascade Behavior

We construct a BDG from a production personal AI assistant's memory database (599 active memories, 384-dimensional sentence embeddings). Unlike the preceding small-scale illustrations (Sections 7.2–7.4), this section reports on a real belief graph not designed to validate the theory.

**Graph construction.** Nodes are memories with embeddings, trust scores, confidence, and timestamps. Edges are assigned by pairwise cosine similarity: RELATED_TO for pairs with cosine similarity $> 0.5$ (directed from older to newer memory), and CONTRADICTS for pairs above $0.7$ that additionally trigger geometric contradiction detection (overlap integral with divergent centers). The resulting graph has 599 nodes, 4,976 edges (3,558 RELATED_TO, 1,418 CONTRADICTS), and density 0.014.

**Topology.** The graph has 74 connected components. The largest component contains 498 nodes (83% of the graph); 64 nodes are isolated. The RELATED_TO subgraph is a DAG with longest directed path 27. Cycles exist in the full graph but are entirely from bidirectional CONTRADICTS edges (A contradicts B and B contradicts A), producing 500+ length-2 cycles. No support-chain cycles exist.

| Statistic | Value |
|-----------|-------|
| Nodes | 599 |
| Edges | 4,976 |
| Largest component | 498 (83%) |
| Isolated nodes | 64 |
| RELATED_TO subgraph | DAG, longest path 27 |
| Cycles | All from bidirectional CONTRADICTS |
| Mean out-degree | 8.3 |
| Max out-degree | 52 |
| Median out-degree | 3 |
| Nodes with fan-in > 1 | 407 (68%) |
| Max fan-in | 54 |
| Mean edge weight | 0.63 |

**Cascade results.** We run cascades from the three highest out-degree nodes with $L = 0.9$, $\tau = 0.01$, and MAX aggregation (Definition 3.5). Results are consistent across sources:

| Source | Depth | Max Width | Nodes Affected | Total Impact |
|--------|-------|-----------|----------------|--------------|
| Node A (out=52) | 8 | 207 | 383 (64%) | 109.8 |
| Node B (out=48) | 8 | 169 | 381 (64%) | 106.8 |
| Node C (out=44) | 9 | 228 | 375 (63%) | 109.0 |

**Damping curve.** Per-node impact decays geometrically as Theorem 4.3 predicts. Averaging across the three cascades:

| Depth | Avg Impact | Predicted ($\rho^j$, $\rho = 0.57$) |
|-------|------------|--------------------------------------|
| 0 | 1.000 | 1.000 |
| 1 | 0.566 | 0.570 |
| 2 | 0.314 | 0.325 |
| 3 | 0.178 | 0.185 |
| 4 | 0.102 | 0.106 |
| 5 | 0.060 | 0.060 |
| 6 | 0.039 | 0.034 |

The per-node bound holds. However, the *graph-wide* total impact (Corollary 4.3.1) vastly exceeds the per-path bound: actual total $\approx 109$ vs. the per-path bound $\delta_0 / (1-\rho) = 2.33$. This is because $d \cdot \rho \approx 8.3 \times 0.57 = 4.7 \gg 1$: fan-out dominates damping, and a single revision affects 64% of the graph.

**Key empirical findings:**

1. **Multi-parent is the norm.** 68% of nodes have fan-in > 1. The single-path assumption of Theorem 4.3(c) does not describe typical cascade behavior.
2. **Cascades are broad, not deep.** Depth 8–9 is well below the DAG longest path (27). Damping kills propagation vertically, but fan-out spreads it horizontally.
3. **All cycles are contradiction-pair cycles.** Real BDGs do not exhibit support-chain cycles. Theorem 4.4's instability condition applies only to CONTRADICTS edges, making it a diagnostic for contradiction management rather than general cascade dynamics.
4. **64% cascade reach is stable across sources.** The three highest-degree nodes all affect approximately the same 380 nodes — suggesting the reachable set is a structural property of the graph, not source-dependent.
5. **The graph-wide convergence condition $d \cdot \rho < 1$ is not satisfied.** For real BDGs with mean out-degree $\sim 8$, graph-wide convergence requires $\rho < 0.12$ — much stricter than the per-node condition $\rho < 1$. This means cascade *reach* is inherently broad in typical belief graphs, even when per-node impact is well-controlled.

### 7.6 Firewall Experiment (Proposition 5.3)

We simulate held contradictions as cascade firewalls on the production BDG. Held nodes absorb incoming cascade impact but do not propagate to their successors.

**Baseline.** From the highest out-degree source (out=53), the cascade affects 385 nodes with total impact 110.7.

**Strategy 1: Block high fan-in nodes (sinks).** The top fan-in nodes (in-degree 42–55) have low out-degree (6–13). Blocking 1–5 of them reduces node count by 0% and impact by < 0.4%. High fan-in nodes are *sinks*, not *hubs* — they absorb cascades but don't spread them.

**Strategy 2: Block high out-degree nodes (spreaders).** Blocking the top 10 out-degree nodes (excluding the source) reduces impact by 18.5%. Better, but the graph routes around them.

**Strategy 3: Firewall ring at depth 1.** Blocking the source's direct successors creates a vertex cut (Corollary 5.3.1):

| Depth-1 firewalls | Nodes affected | Reduction | Impact | Reduction |
|---|---|---|---|---|
| 5 of 53 | 383 | 0.5% | 90.6 | 18.2% |
| 10 of 53 | 382 | 0.8% | 88.1 | 20.4% |
| 20 of 53 | 361 | 6.2% | 77.5 | 30.0% |
| **All 53** | **54** | **86.0%** | **31.2** | **71.8%** |

**Strategy 4: Articulation points.** The graph has 53 articulation points (nodes whose removal disconnects the graph). Blocking the top 20 by degree reduces nodes by only 7.3% — the graph is too densely connected for individual structural bottlenecks to matter.

**Key findings for Proposition 5.3:**

1. **Firewalls are ineffective individually on dense graphs.** No single node blocks more than 0.5% of the cascade. The high connectivity of real BDGs provides many alternate paths.
2. **Firewall placement matters more than firewall count.** 20 depth-1 firewalls (38% of the ring) cut 30% of impact. 20 random articulation points cut only 7.3% of nodes.
3. **Complete vertex cuts are dramatically effective.** Blocking all depth-1 successors eliminates 86% of cascade reach — confirming Corollary 5.3.1 on real data.
4. **The effectiveness curve is nonlinear.** 38% of the firewall ring gives 30% reduction; 100% gives 86%. There is a sharp phase transition between "barely helps" and "nearly total containment."
5. **Practical implication.** In real systems, held contradictions are useful as firewalls only when they form a nearly complete cut. Sparse held beliefs in a dense graph provide negligible protection.

---

## 8. Discussion

### 8.1 Implications for AI Safety

Uncontrolled belief revision cascades are a formal model of *catastrophic forgetting* in a structured setting. Theorem 4.3 gives precise conditions under which cascades are safe (bounded, convergent). Theorem 4.4 identifies dangerous configurations (cyclic dependencies with amplification). These results provide actionable design constraints: AI systems that maintain dependency metadata can diagnose cascade vulnerability before it manifests.

### 8.2 Implications for Alignment

Proposition 5.3 connects epistemic pluralism to system stability: an agent that can hold contradictions without resolving them is structurally more stable than one that insists on consistency. This has implications for value alignment — a system that maintains multiple, potentially conflicting values as *held* beliefs rather than forcing resolution may be both more robust and more aligned with the genuine complexity of human values.

### 8.3 Open Problems

1. **Continuous belief spaces.** Our formalism assumes a discrete set of belief nodes. Extending to continuous belief fields (e.g., a function over semantic space) would require functional analysis tools.

2. **Probabilistic dependencies.** Current dependency weights are deterministic. Extending to stochastic dependencies (each edge fires with probability $p(e)$) yields a richer model with connections to percolation theory.

3. **Causal vs. evidential dependency.** Our current framework treats all dependencies as evidential (B depends on A because A provides evidence for B). Causal dependencies (A causes B) would require integration with Pearl's causal calculus.

4. **Multi-agent cascade interaction.** When two agents with overlapping belief systems communicate, their cascades can interact. This bridges our single-agent framework back to opinion dynamics.

5. **Learning the BDG.** Our current BDG is constructed from contradiction detection and temporal ordering. Learning the dependency structure from observation — which beliefs actually influence which — is a learning problem we have not addressed.

---

## References

- Alchourrón, C. E., Gärdenfors, P., & Makinson, D. (1985). On the logic of theory change: Partial meet contraction and revision functions. *Journal of Symbolic Logic*, 50(2), 510-530.
- Baek, J. et al. (2026). Kumiho: AGM-compliant belief revision for large language models. *arXiv:2603.17244*.
- Darwiche, A., & Pearl, J. (1997). On the logic of iterated belief revision. *Artificial Intelligence*, 89(1-2), 1-29.
- DeGroot, M. H. (1974). Reaching a consensus. *Journal of the American Statistical Association*, 69(345), 118-121.
- Festinger, L. (1957). *A Theory of Cognitive Dissonance*. Stanford University Press.
- Friedkin, N. E., & Johnsen, E. C. (1990). Social influence and opinions. *Journal of Mathematical Sociology*, 15(3-4), 193-206.
- Gärdenfors, P., & Makinson, D. (1988). Revisions of knowledge systems using epistemic entrenchment. In *TARK '88*, 83-95.
- Hegselmann, R., & Krause, U. (2002). Opinion dynamics and bounded confidence: models, analysis and simulation. *JASSS*, 5(3).
- Hubinger, E., van Merwijk, C., Mikulik, V., Skalse, J., & Garrabrant, S. (2019). Risks from learned optimization in advanced machine learning systems. *arXiv:1906.01820*.
- Pearl, J. (1982). Reverend Bayes on inference engines: A distributed hierarchical approach. In *AAAI-82*, 133-136.
- Vilnis, L., & McCallum, A. (2015). Word representations via Gaussian embedding. In *ICLR 2015*.

---

## Appendix A: Code-to-Definition Mapping

| Definition | Code Module | Key Function/Class |
|-----------|------------|-------------------|
| 3.1 Belief State | `memory_splats.py` | `MemorySplat(mu, sigma, alpha, ...)` |
| 3.2 Belief Dependency Graph | `memory_graph.py` | `BeliefDependencyGraph` (NetworkX digraph) |
| 3.3 Revision Event / Impact | `info_geometry.py` | `fisher_rao_distance(a, b)` |
| 3.4 Cascade Trigger | `memory_graph.py` | `should_cascade(node, impact, threshold)` |
| 3.5 Revision Cascade | `memory_graph.py` | `propagate_cascade(event, graph)` |
| 3.6 Cascade Disposition | `disposition_classifier.py` | `classify_contradiction(text_a, text_b, ...)` |
| — Contradiction ledger | `crt_ledger.py` | `ContradictionEntry`, `ContradictionLedger` |
| — Temporal governance | `temporal_governance.py` | Type-dependent decay, Belnap states |
