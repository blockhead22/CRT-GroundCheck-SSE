# Appendix B: On the Complexity of Optimal Cascade Ordering

## Conjecture 4.5 Revisited

**Problem (OPTIMAL-CASCADE-ORDER).** Given:
- A BDG $G = (V, E, w)$
- A set of $k$ simultaneous revision events $R = \{r_1, \ldots, r_k\}$, each at a distinct node
- A contradiction metric $\phi: V \to \mathbb{R}_{\geq 0}$ measuring post-cascade contradiction at each node

Find a permutation $\pi$ of $\{1, \ldots, k\}$ that minimizes the total post-cascade contradiction:

$$\min_{\pi} \sum_{v \in V} \phi_\pi(v)$$

where $\phi_\pi(v)$ is the contradiction at $v$ after applying revisions in order $r_{\pi(1)}, r_{\pi(2)}, \ldots, r_{\pi(k)}$, with full cascade propagation between each.

## Proof Attempt: Reduction from Minimum Weighted Completion Time

We attempt a reduction from **Precedence-Constrained Scheduling with Weighted Completion Time** (known NP-hard, Lawler 1978).

### The scheduling problem

**Instance.** $n$ jobs with processing times $p_j$, weights $w_j$, and precedence constraints (a DAG). One machine.

**Question.** Find a schedule respecting precedence that minimizes $\sum_j w_j C_j$ where $C_j$ is the completion time of job $j$.

### Reduction

Given a scheduling instance $(J, P, W, \text{DAG})$:

1. **Construct BDG.** For each job $j$, create two nodes: a *revision node* $r_j$ and a *measurement node* $m_j$. Add edge $r_j \to m_j$ with weight 1.

2. **Encode precedence.** For each precedence constraint $j \prec j'$, add edge $m_j \to r_{j'}$ with weight 1. This ensures the cascade from $r_j$ must reach $m_j$ before $r_{j'}$ can meaningfully fire.

3. **Encode interaction.** For jobs $j, j'$ that share a measurement node (via additional "shared resource" nodes), the order in which their cascades arrive determines the final contradiction.

### Why this doesn't quite work

The difficulty is that cascade propagation in a BDG is *deterministic* for a given ordering — there's no stochastic element. The post-cascade state at each node is fully determined by the ordering of revision events. This means:

- The objective function $\sum_v \phi_\pi(v)$ is a deterministic function of the permutation $\pi$
- But it's not clear that this function has the right structure to embed scheduling

The core issue: in scheduling, job durations accumulate (completion time = sum of preceding durations). In cascade ordering, impacts *interact nonlinearly* — the cascade from $r_i$ may change the state that $r_j$ encounters, and this change depends on the full cascade dynamics, not just on processing time.

## Alternative: Reduction from MAX-SAT

A more promising approach:

### Construction

Given a MAX-SAT instance with variables $x_1, \ldots, x_n$ and clauses $C_1, \ldots, C_m$:

1. **Variables as revision events.** Each variable $x_i$ becomes a revision event $r_i$ with two possible revision targets: $b_i^T$ (true) and $b_i^F$ (false). The ordering determines which "wins" at shared nodes.

2. **Clauses as measurement nodes.** Each clause $C_j$ becomes a measurement node $m_j$ that depends on the variables appearing in it.

3. **Contradiction at measurement nodes.** $\phi(m_j)$ is 0 if the clause is satisfied by the final state and 1 otherwise.

4. **Ordering encodes truth assignment.** The order in which variable revisions cascade through determines the truth assignment: whichever revision arrives *last* at a shared measurement node determines its final state.

### Why this is also incomplete

The gap: cascade ordering is a *permutation* of $k$ events, but MAX-SAT is an *assignment* of $n$ binary variables. Each variable in MAX-SAT has 2 choices; each position in the permutation has $k$ choices. The encoding from permutations to truth assignments is not clean.

## Current Status

The conjecture remains open. The most promising approach is:

**Reduction from Minimum Linear Arrangement (MLA):** Given a graph $H$, find a permutation of vertices that minimizes $\sum_{(u,v) \in E} |\pi(u) - \pi(v)|$. MLA is NP-hard (Garey, Johnson, Stockmeyer 1976).

The mapping: each vertex in $H$ becomes a revision event. Each edge in $H$ becomes a shared downstream node in the BDG. The cascade interaction cost between two revisions $r_i, r_j$ that share a downstream node is monotone in $|\pi(i) - \pi(j)|$ (revisions that are far apart in the ordering have cascades that interact more destructively, because more intermediate revisions have modified the shared state).

This reduction has the right structure (permutation → permutation, interaction cost depends on ordering distance) but needs a formal proof that the cascade interaction cost is faithfully encoded.

## Regardless: Both Outcomes Publish

- **NP-hard:** AI systems cannot efficiently optimize multi-revision scheduling. Greedy orderings (Proposition 5.4) are the best practical approach, and the $(1-1/e)$ approximation guarantee matters.

- **Polynomial:** AI systems CAN efficiently schedule revisions. This is a positive algorithmic result — cascade ordering can be solved optimally. The polynomial algorithm itself would be the contribution.

Either way, the complexity of this problem is interesting and novel. Nobody has asked the question.
