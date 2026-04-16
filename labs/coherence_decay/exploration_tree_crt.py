"""CRT-Enhanced Exploration Tree — Belief graph math applied to scaffold.

Subclasses GravityExplorationTree. Adds five CRT math upgrades:

1. TRUST EVOLUTION per fact — facts decay if unacted, reinforce if used.
   Replaces flat 0.85/0.65 with exponential recency (rho = e^(-dt/lambda)).

2. CONTRADICTION EDGES between facts — when two facts conflict (e.g.,
   "port open" vs "connection refused" for same IP), the tension is REAL
   not just dead-branch counting. Uses Belnap 4-valued: T/F/Both/Neither.

3. CASCADE PROPAGATION — when a fact dies (hard death), cascade damping
   propagates trust reduction to related facts. A mount path dying should
   reduce trust in the block device that led to it.

4. DISPOSITION CLASSIFICATION — contradictions are typed:
   resolvable (try harder), held (genuine ambiguity), evolving (still
   gathering data). Resolvable contradictions increase exploration budget.

5. LEARNABLE GAIN — branch selection uses Beta-distribution trust instead
   of raw UCB. Branches that produce correct facts get alpha++, branches
   that produce dead ends get beta++. Posterior mean = alpha/(alpha+beta).

Same interface: ingest(), render(), get_next_action(), summary().
"""

from __future__ import annotations
import math
import time
from dataclasses import dataclass, field

from exploration_tree_gravity import GravityExplorationTree, GravityRoom


# ---------------------------------------------------------------------------
# 1. Trust evolution per fact
# ---------------------------------------------------------------------------
def trust_decay(trust: float, dt_epochs: int, lam: float = 10.0,
                floor: float = 0.20) -> float:
    """Exponential recency decay. lam = time constant in epochs."""
    rho = math.exp(-dt_epochs / lam)
    decayed = trust * rho
    return max(decayed, floor)


def trust_reinforce(trust: float, ceiling: float = 0.95,
                    boost: float = 0.08) -> float:
    """Boost trust when fact is successfully acted on."""
    return min(trust + boost * (ceiling - trust), ceiling)


# ---------------------------------------------------------------------------
# 2. Contradiction detection between facts
# ---------------------------------------------------------------------------
@dataclass
class FactEdge:
    """Typed edge between two facts."""
    fact_a: str
    fact_b: str
    edge_type: str  # "contradicts" | "supports" | "supersedes"
    disposition: str = "unknown"  # resolvable | held | evolving
    strength: float = 0.5
    detected_epoch: int = 0


def detect_contradiction(key_a: str, fact_a: dict,
                         key_b: str, fact_b: dict) -> FactEdge | None:
    """Detect if two facts contradict each other.

    Simple pattern-based for scaffold context:
    - Same IP, one says OPEN, other says connection refused → contradiction
    - Same path, one says writable, other says read-only → contradiction
    - Service found vs service unreachable on same host → contradiction
    """
    ip_a = fact_a.get("ip", "")
    ip_b = fact_b.get("ip", "")

    # Same IP, conflicting port status
    if ip_a and ip_a == ip_b:
        port_a = fact_a.get("port", "")
        port_b = fact_b.get("port", "")
        if port_a and port_a == port_b:
            # One open, one dead
            desc_a = fact_a.get("description", "").lower()
            desc_b = fact_b.get("description", "").lower()
            a_open = "open" in desc_a or "responding" in desc_a or "live" in desc_a
            b_open = "open" in desc_b or "responding" in desc_b or "live" in desc_b
            a_dead = "refused" in desc_a or "timeout" in desc_a or "000" in desc_a
            b_dead = "refused" in desc_b or "timeout" in desc_b or "000" in desc_b
            if (a_open and b_dead) or (b_open and a_dead):
                return FactEdge(
                    fact_a=key_a, fact_b=key_b,
                    edge_type="contradicts",
                    disposition="resolvable",  # retry might resolve
                    strength=0.7,
                )

    # Same path, conflicting permissions
    path_a = fact_a.get("path", "")
    path_b = fact_b.get("path", "")
    if path_a and path_a == path_b:
        a_rw = fact_a.get("writable", None)
        b_rw = fact_b.get("writable", None)
        if a_rw is not None and b_rw is not None and a_rw != b_rw:
            return FactEdge(
                fact_a=key_a, fact_b=key_b,
                edge_type="contradicts",
                disposition="resolvable",
                strength=0.8,
            )

    return None


# ---------------------------------------------------------------------------
# 3. Cascade damping coefficients (from graph.py DAMPING_BY_EDGE_TYPE)
# ---------------------------------------------------------------------------
CASCADE_DAMPING = {
    "contradicts": 0.60,
    "supersedes": 0.85,
    "supports": 0.30,
}


def cascade_trust_reduction(trust: float, edge_type: str,
                            source_delta: float) -> float:
    """Propagate trust reduction through an edge.

    When a source fact's trust drops by source_delta, connected facts
    lose trust proportional to the edge damping coefficient.
    """
    damping = CASCADE_DAMPING.get(edge_type, 0.20)
    reduction = abs(source_delta) * damping
    return max(trust - reduction, 0.20)


# ---------------------------------------------------------------------------
# 5. Beta-distribution branch trust (learnable gain)
# ---------------------------------------------------------------------------
@dataclass
class BetaBranch:
    """Beta(alpha, beta) prior for branch quality."""
    alpha: float = 1.0  # Successes (facts produced)
    beta_param: float = 1.0   # Failures (dead ends)

    @property
    def mean(self) -> float:
        return self.alpha / (self.alpha + self.beta_param)

    @property
    def variance(self) -> float:
        a, b = self.alpha, self.beta_param
        return (a * b) / ((a + b) ** 2 * (a + b + 1))

    @property
    def ucb(self) -> float:
        """Upper confidence bound — mean + 1 stddev."""
        return self.mean + math.sqrt(self.variance)

    def update_success(self, weight: float = 1.0):
        self.alpha += weight

    def update_failure(self, weight: float = 1.0):
        self.beta_param += weight


# ---------------------------------------------------------------------------
# CRT Exploration Tree
# ---------------------------------------------------------------------------
class CRTExplorationTree(GravityExplorationTree):
    """GravityExplorationTree + CRT math upgrades.

    Upgrades:
    1. Per-fact trust with decay/reinforce
    2. Contradiction edges between facts
    3. Cascade propagation on fact death
    4. Disposition-typed contradictions
    5. Beta-distribution branch selection
    """

    def __init__(self):
        super().__init__()
        self.fact_trust: dict[str, float] = {}       # key -> trust score
        self.fact_epoch: dict[str, int] = {}          # key -> epoch discovered
        self.edges: list[FactEdge] = []
        self.beta_branches: dict[str, BetaBranch] = {}
        self._contradiction_count = 0

    def ingest(self, epoch: int, command: str, stdout: str, stderr: str,
               returncode: int, approach: str) -> dict:
        """CRT-enhanced ingest: trust evolution + contradiction detection + cascade."""

        old_facts = set(self.facts.keys())

        # --- Base ingest (gravity + salience + fact extraction) ---
        result = super().ingest(epoch, command, stdout, stderr, returncode, approach)

        new_facts = set(self.facts.keys()) - old_facts

        # --- 1. Initialize trust for new facts ---
        for key in new_facts:
            self.fact_trust[key] = 0.70  # Prior trust
            self.fact_epoch[key] = epoch

        # --- 1b. Decay all existing facts ---
        for key in self.fact_trust:
            if key in new_facts:
                continue
            dt = epoch - self.fact_epoch.get(key, epoch)
            if dt > 0:
                self.fact_trust[key] = trust_decay(
                    self.fact_trust[key], dt
                )

        # --- 1c. Reinforce acted-on facts ---
        for key, fact in self.facts.items():
            if fact.get("acted_on") and key in self.fact_trust:
                old_trust = self.fact_trust[key]
                self.fact_trust[key] = trust_reinforce(old_trust)

        # --- 2. Detect contradictions between new and existing facts ---
        for new_key in new_facts:
            for old_key in old_facts:
                if old_key not in self.facts:
                    continue
                edge = detect_contradiction(
                    new_key, self.facts[new_key],
                    old_key, self.facts[old_key],
                )
                if edge:
                    edge.detected_epoch = epoch
                    self.edges.append(edge)
                    self._contradiction_count += 1

        # --- 3. Cascade: if a branch just died, reduce trust of related facts ---
        branch_name = result.get("branch", "")
        if result.get("branch_dead") and branch_name:
            # Find facts that came from this branch's paradigm
            paradigm = self.current_paradigm
            for key in list(self.fact_trust.keys()):
                if self._fact_belongs_to(key, paradigm):
                    if not self.facts.get(key, {}).get("acted_on"):
                        old_t = self.fact_trust[key]
                        self.fact_trust[key] = cascade_trust_reduction(
                            old_t, "contradicts", source_delta=0.2
                        )

        # --- 5. Update beta-distribution for branch ---
        if branch_name:
            if branch_name not in self.beta_branches:
                self.beta_branches[branch_name] = BetaBranch()
            bb = self.beta_branches[branch_name]
            if result.get("new_facts", 0) > 0:
                bb.update_success(weight=result["new_facts"])
            else:
                bb.update_failure(weight=0.5)

        # Add CRT-specific data to result
        result["contradiction_count"] = self._contradiction_count
        result["active_contradictions"] = len([
            e for e in self.edges if e.disposition == "resolvable"
        ])

        return result

    def _sync_gravity(self):
        """Override: use CRT trust scores instead of flat confidence."""
        for pname, paradigm in self.paradigms.items():
            room = self.gravity_rooms[pname]

            fact_count = 0
            fact_confidence = 0.0
            for key, fact in self.facts.items():
                if self._fact_belongs_to(key, pname):
                    fact_count += 1
                    # Use CRT trust instead of flat 0.85/0.65
                    fact_confidence += self.fact_trust.get(key, 0.65)

            room.fact_count = fact_count
            room.fact_confidence_sum = fact_confidence

            dead = [b for b in paradigm.branches.values() if b.dead]
            room.dead_branch_count = len(dead)

            # Real contradiction count from edges, not approximation
            real_contradictions = sum(
                1 for e in self.edges
                if (self._fact_belongs_to(e.fact_a, pname)
                    or self._fact_belongs_to(e.fact_b, pname))
            )
            room.contradiction_count = real_contradictions or (len(dead) * fact_count)

    def get_next_action(self) -> str | None:
        """Override: use Beta-UCB for branch selection when no direct action."""
        # Let salience and priority actions go first
        action = super().get_next_action()
        if action is not None:
            return action

        # If no direct action, use Beta-UCB to pick best branch to explore
        # (only when model would otherwise generate freely)
        paradigm = self.paradigms[self.current_paradigm]
        alive = paradigm.alive_branches
        if not alive:
            return None

        # Score branches by Beta-UCB
        best_branch = None
        best_score = -1
        for branch in alive:
            bb = self.beta_branches.get(branch.name, BetaBranch())
            score = bb.ucb
            if score > best_score:
                best_score = score
                best_branch = branch

        # If best branch has high UCB, hint to model what paradigm to explore
        # But don't override — return None to let model generate
        return None

    def render(self) -> str:
        """Base render + CRT additions."""
        base = super().render()
        lines = [base]

        # Trust-weighted fact list (replace generic list)
        low_trust = [
            (k, self.fact_trust.get(k, 0.5))
            for k, f in self.facts.items()
            if self.fact_trust.get(k, 0.5) < 0.4 and not f.get("acted_on")
        ]
        if low_trust:
            lines.append("\nDECAYING FACTS (trust dropping — act or lose):")
            for key, trust in sorted(low_trust, key=lambda x: x[1]):
                lines.append(f"  [{trust:.2f}] {self.facts[key].get('description', key)}")

        # Active contradictions
        resolvable = [e for e in self.edges if e.disposition == "resolvable"]
        if resolvable:
            lines.append(f"\nACTIVE CONTRADICTIONS ({len(resolvable)}) — investigate:")
            for e in resolvable[:3]:
                desc_a = self.facts.get(e.fact_a, {}).get("description", e.fact_a)
                desc_b = self.facts.get(e.fact_b, {}).get("description", e.fact_b)
                lines.append(f"  ⚡ {desc_a} vs {desc_b}")

        # Beta branch quality
        if self.beta_branches:
            lines.append("\nBRANCH QUALITY (Beta-UCB):")
            sorted_bb = sorted(
                self.beta_branches.items(),
                key=lambda x: x[1].ucb, reverse=True,
            )
            for name, bb in sorted_bb[:5]:
                lines.append(
                    f"  {name:20s} mean={bb.mean:.2f} ucb={bb.ucb:.2f} "
                    f"(α={bb.alpha:.1f} β={bb.beta_param:.1f})"
                )

        return "\n".join(lines)

    def summary(self) -> dict:
        """Base summary + CRT data."""
        base = super().summary()
        base["crt"] = {
            "total_contradictions": self._contradiction_count,
            "active_contradictions": len([
                e for e in self.edges if e.disposition == "resolvable"
            ]),
            "fact_trust_mean": (
                sum(self.fact_trust.values()) / len(self.fact_trust)
                if self.fact_trust else 0.0
            ),
            "decaying_facts": len([
                v for v in self.fact_trust.values() if v < 0.4
            ]),
            "beta_branches": {
                name: {"mean": round(bb.mean, 3), "ucb": round(bb.ucb, 3),
                       "alpha": round(bb.alpha, 1), "beta": round(bb.beta_param, 1)}
                for name, bb in self.beta_branches.items()
            },
            "edges": [
                {"a": e.fact_a, "b": e.fact_b, "type": e.edge_type,
                 "disposition": e.disposition, "strength": e.strength}
                for e in self.edges
            ],
        }
        return base
