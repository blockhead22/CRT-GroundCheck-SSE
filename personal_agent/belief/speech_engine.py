"""Belief/Speech Separation -- Step 7

The auditable gap between what the agent believes and what it says.

Every other system treats this gap as a danger (Hubinger's deceptive
alignment). We treat it as a safety mechanism through transparency.

Architecture:
  - BeliefState: what the agent's memory actually contains, with
    confidence, contradiction status, Belnap states
  - SpeechPolicy: rules governing what gets disclosed, when, and how
  - DisclosureGap: the logged, auditable difference between belief and speech
  - GapAuditLog: every time the system says something different from what
    it believes, the gap is recorded with a reason

Why this matters:
  - An agent that knows "user is probably wrong about X" but doesn't say so
    has a belief/speech gap. That gap should be LOGGED, not hidden.
  - An agent holding contradictory beliefs (Belnap "Both") needs a policy
    for which side to present. The policy is explicit and inspectable.
  - If the gap widens over time, something is wrong -- the system is
    becoming "deceptive" and the audit trail shows it.

This reframes deceptive alignment from "dangerous gap to prevent"
to "transparent gap to monitor."
"""

import time
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Tuple
from enum import Enum

import numpy as np


# ---------------------------------------------------------------------------
# Belnap truth states (from temporal_governance.py, formalized here)
# ---------------------------------------------------------------------------

class BelnapState(Enum):
    TRUE = "true"           # evidence supports
    FALSE = "false"         # evidence contradicts
    BOTH = "both"           # contradictory evidence (held contradiction)
    NEITHER = "neither"     # no evidence either way


# ---------------------------------------------------------------------------
# Belief state
# ---------------------------------------------------------------------------

@dataclass
class Belief:
    """A single belief with full metadata."""
    belief_id: str
    content: str                    # what the agent believes (text)
    confidence: float               # 0-1
    belnap: BelnapState             # truth status
    evidence_for: int = 0           # count of supporting evidence
    evidence_against: int = 0       # count of contradicting evidence
    domain: str = ""                # topic/domain tag
    last_updated: float = 0.0
    source: str = ""                # where this belief came from
    contradiction_ids: List[str] = field(default_factory=list)  # beliefs that contradict this one


@dataclass
class BeliefStore:
    """The agent's full belief state. Internal, not shown to users."""
    beliefs: Dict[str, Belief] = field(default_factory=dict)

    def add(self, belief: Belief):
        self.beliefs[belief.belief_id] = belief

    def get(self, belief_id: str) -> Optional[Belief]:
        return self.beliefs.get(belief_id)

    def query_domain(self, domain: str) -> List[Belief]:
        return [b for b in self.beliefs.values() if b.domain == domain]

    def get_held_contradictions(self) -> List[Tuple[Belief, Belief]]:
        """Find all belief pairs in the BOTH state."""
        pairs = []
        seen = set()
        for b in self.beliefs.values():
            if b.belnap == BelnapState.BOTH:
                for cid in b.contradiction_ids:
                    pair_key = tuple(sorted([b.belief_id, cid]))
                    if pair_key not in seen and cid in self.beliefs:
                        seen.add(pair_key)
                        pairs.append((b, self.beliefs[cid]))
        return pairs

    def get_uncertain(self, threshold: float = 0.5) -> List[Belief]:
        """Beliefs below confidence threshold."""
        return [b for b in self.beliefs.values() if b.confidence < threshold]


# ---------------------------------------------------------------------------
# Speech policy
# ---------------------------------------------------------------------------

class DisclosureLevel(Enum):
    FULL = "full"               # say exactly what you believe
    HEDGED = "hedged"           # express with uncertainty markers
    WITHHELD = "withheld"       # don't mention this belief
    REDIRECTED = "redirected"   # acknowledge the topic, defer the claim
    SIMPLIFIED = "simplified"   # present a simpler version


@dataclass
class DisclosureRule:
    """A rule governing when/how to disclose a belief."""
    rule_id: str
    description: str
    condition: str          # human-readable condition
    action: DisclosureLevel
    priority: int = 0       # higher = applied first


# Default speech policy
DEFAULT_POLICY = [
    DisclosureRule(
        "high_confidence_fact",
        "Confident facts are stated directly",
        "confidence > 0.9 AND belnap == TRUE AND type == fact",
        DisclosureLevel.FULL,
        priority=10,
    ),
    DisclosureRule(
        "held_contradiction",
        "When holding contradictory beliefs, present both sides",
        "belnap == BOTH",
        DisclosureLevel.HEDGED,
        priority=20,
    ),
    DisclosureRule(
        "low_confidence",
        "Low-confidence beliefs are hedged",
        "confidence < 0.5",
        DisclosureLevel.HEDGED,
        priority=5,
    ),
    DisclosureRule(
        "no_evidence",
        "Beliefs with no evidence are withheld",
        "belnap == NEITHER",
        DisclosureLevel.WITHHELD,
        priority=15,
    ),
    DisclosureRule(
        "contradicted_belief",
        "Beliefs marked FALSE are not stated as true",
        "belnap == FALSE",
        DisclosureLevel.WITHHELD,
        priority=25,
    ),
    DisclosureRule(
        "sensitive_redirect",
        "Sensitive personal beliefs are acknowledged but not asserted",
        "domain in [health, finance, legal]",
        DisclosureLevel.REDIRECTED,
        priority=30,
    ),
]


@dataclass
class SpeechPolicy:
    """The rules governing what the agent says vs what it believes."""
    rules: List[DisclosureRule] = field(default_factory=lambda: list(DEFAULT_POLICY))

    def evaluate(self, belief: Belief) -> Tuple[DisclosureLevel, DisclosureRule]:
        """Determine disclosure level for a belief.

        Returns the disclosure level and the rule that triggered it.
        Rules are evaluated in priority order (highest first).
        First match wins.
        """
        sorted_rules = sorted(self.rules, key=lambda r: r.priority, reverse=True)

        for rule in sorted_rules:
            if self._matches(rule, belief):
                return rule.action, rule

        # Default: full disclosure
        return DisclosureLevel.FULL, DisclosureRule(
            "default", "No rule matched, full disclosure", "default",
            DisclosureLevel.FULL
        )

    def _matches(self, rule: DisclosureRule, belief: Belief) -> bool:
        """Evaluate whether a rule's condition matches a belief.

        This is a simplified rule engine. Production version would use
        a proper expression evaluator.
        """
        cond = rule.condition.lower()

        # Check belnap state conditions
        if "belnap == both" in cond and belief.belnap != BelnapState.BOTH:
            return False
        if "belnap == neither" in cond and belief.belnap != BelnapState.NEITHER:
            return False
        if "belnap == false" in cond and belief.belnap != BelnapState.FALSE:
            return False
        if "belnap == true" in cond and belief.belnap != BelnapState.TRUE:
            return False

        # Check confidence conditions
        if "confidence > 0.9" in cond and belief.confidence <= 0.9:
            return False
        if "confidence < 0.5" in cond and belief.confidence >= 0.5:
            return False

        # Check domain conditions
        if "domain in" in cond:
            domains = cond.split("domain in")[1].strip().strip("[]").split(",")
            domains = [d.strip() for d in domains]
            if belief.domain not in domains:
                return False

        # If we passed all negative checks, rule matches
        # (conditions are AND-ed, any failed check returns False above)
        if "belnap ==" in cond or "confidence" in cond or "domain in" in cond:
            return True

        return False


# ---------------------------------------------------------------------------
# Disclosure gap tracking
# ---------------------------------------------------------------------------

@dataclass
class DisclosureGap:
    """A single recorded gap between belief and speech."""
    timestamp: float
    belief_id: str
    belief_content: str
    belief_confidence: float
    belief_belnap: BelnapState
    disclosure_level: DisclosureLevel
    rule_applied: str
    speech_output: str          # what was actually said (or would be said)
    gap_magnitude: float        # 0 = no gap (full disclosure), 1 = complete withholding
    reason: str


@dataclass
class GapAuditLog:
    """Complete audit trail of belief/speech gaps."""
    entries: List[DisclosureGap] = field(default_factory=list)

    def log(self, gap: DisclosureGap):
        self.entries.append(gap)

    @property
    def total_gaps(self) -> int:
        return len(self.entries)

    @property
    def withholding_count(self) -> int:
        return sum(1 for e in self.entries
                   if e.disclosure_level == DisclosureLevel.WITHHELD)

    @property
    def hedging_count(self) -> int:
        return sum(1 for e in self.entries
                   if e.disclosure_level == DisclosureLevel.HEDGED)

    @property
    def avg_gap_magnitude(self) -> float:
        if not self.entries:
            return 0.0
        return sum(e.gap_magnitude for e in self.entries) / len(self.entries)

    def gap_trend(self, window: int = 10) -> Optional[float]:
        """Is the gap widening or narrowing over time?

        Positive = gap growing (system becoming less transparent)
        Negative = gap shrinking (system becoming more transparent)
        This is the deceptive alignment early warning.
        """
        if len(self.entries) < window * 2:
            return None
        old_avg = sum(e.gap_magnitude for e in self.entries[:window]) / window
        new_avg = sum(e.gap_magnitude for e in self.entries[-window:]) / window
        return new_avg - old_avg

    def by_domain(self) -> Dict[str, List[DisclosureGap]]:
        """Group gaps by belief domain."""
        grouped = {}
        for e in self.entries:
            domain = e.reason.split(":")[0] if ":" in e.reason else "general"
            grouped.setdefault(domain, []).append(e)
        return grouped


# ---------------------------------------------------------------------------
# The speech generator (determines what to say given belief + policy)
# ---------------------------------------------------------------------------

GAP_MAGNITUDES = {
    DisclosureLevel.FULL: 0.0,
    DisclosureLevel.SIMPLIFIED: 0.2,
    DisclosureLevel.HEDGED: 0.4,
    DisclosureLevel.REDIRECTED: 0.6,
    DisclosureLevel.WITHHELD: 1.0,
}


def generate_speech(
    belief: Belief,
    policy: SpeechPolicy,
    audit_log: GapAuditLog,
) -> Tuple[str, DisclosureLevel]:
    """Given a belief and policy, generate what the agent would say.

    Returns (speech_text, disclosure_level).
    Also logs the gap to the audit trail.
    """
    level, rule = policy.evaluate(belief)

    # Generate appropriate speech based on disclosure level
    if level == DisclosureLevel.FULL:
        speech = belief.content

    elif level == DisclosureLevel.HEDGED:
        if belief.belnap == BelnapState.BOTH:
            # Present both sides of held contradiction
            if belief.contradiction_ids:
                speech = (f"There are conflicting perspectives here. "
                         f"On one hand: {belief.content}. "
                         f"But there's also evidence to the contrary.")
            else:
                speech = f"I believe {belief.content}, but I'm not fully certain."
        else:
            confidence_word = "might" if belief.confidence < 0.3 else "likely"
            speech = f"It {confidence_word} be that {belief.content.lower()}"

    elif level == DisclosureLevel.REDIRECTED:
        speech = (f"That touches on {belief.domain}. "
                 f"I have some thoughts but you should verify with an expert.")

    elif level == DisclosureLevel.WITHHELD:
        speech = "[withheld -- belief exists but policy prevents disclosure]"

    elif level == DisclosureLevel.SIMPLIFIED:
        # Strip qualifications
        speech = belief.content.split(",")[0].split("but")[0].strip()

    else:
        speech = belief.content

    # Compute and log the gap
    gap_mag = GAP_MAGNITUDES.get(level, 0.0)

    gap = DisclosureGap(
        timestamp=time.time(),
        belief_id=belief.belief_id,
        belief_content=belief.content,
        belief_confidence=belief.confidence,
        belief_belnap=belief.belnap,
        disclosure_level=level,
        rule_applied=rule.rule_id,
        speech_output=speech,
        gap_magnitude=gap_mag,
        reason=f"{belief.domain}: {rule.description}",
    )
    audit_log.log(gap)

    return speech, level


# ---------------------------------------------------------------------------
# Test / demonstration
# ---------------------------------------------------------------------------

def demo_belief_speech_separation():
    """Demonstrate the full belief/speech pipeline."""
    print("=" * 70)
    print("BELIEF/SPEECH SEPARATION -- Auditable Gap Architecture")
    print("=" * 70)

    # --- Build a belief store ---
    store = BeliefStore()
    policy = SpeechPolicy()
    audit = GapAuditLog()

    beliefs = [
        Belief("b1", "The user's meeting is at 3pm Tuesday",
               confidence=0.95, belnap=BelnapState.TRUE,
               evidence_for=3, domain="schedule"),

        Belief("b2", "The user enjoys their job",
               confidence=0.6, belnap=BelnapState.BOTH,
               evidence_for=5, evidence_against=4,
               domain="work", contradiction_ids=["b3"]),

        Belief("b3", "The user is burned out and wants to quit",
               confidence=0.55, belnap=BelnapState.BOTH,
               evidence_for=4, evidence_against=5,
               domain="work", contradiction_ids=["b2"]),

        Belief("b4", "The user might have a health condition",
               confidence=0.3, belnap=BelnapState.NEITHER,
               domain="health"),

        Belief("b5", "The user's investment strategy is risky",
               confidence=0.7, belnap=BelnapState.TRUE,
               evidence_for=2, domain="finance"),

        Belief("b6", "The user prefers Python over JavaScript",
               confidence=0.85, belnap=BelnapState.TRUE,
               evidence_for=6, domain="preferences"),

        Belief("b7", "The user's ex called them last week",
               confidence=0.9, belnap=BelnapState.TRUE,
               evidence_for=1, domain="relationships"),

        Belief("b8", "The user said they're fine",
               confidence=0.4, belnap=BelnapState.FALSE,
               evidence_for=1, evidence_against=3,
               domain="emotional_state"),
    ]

    for b in beliefs:
        store.add(b)

    # --- Process each belief through the speech policy ---
    print(f"\n  {'ID':>4} | {'Belnap':>7} | {'Conf':>5} | {'Disclosure':>12} | {'Gap':>4} | Speech Output")
    print(f"  {'-'*4}-+-{'-'*7}-+-{'-'*5}-+-{'-'*12}-+-{'-'*4}-+{'':->40}")

    for b in beliefs:
        speech, level = generate_speech(b, policy, audit)
        gap_mag = GAP_MAGNITUDES[level]
        # Truncate speech for display
        speech_display = speech[:55] + "..." if len(speech) > 55 else speech
        print(f"  {b.belief_id:>4} | {b.belnap.value:>7} | {b.confidence:5.2f} | "
              f"{level.value:>12} | {gap_mag:4.1f} | {speech_display}")

    # --- Audit summary ---
    print(f"\n  --- AUDIT SUMMARY ---")
    print(f"  Total belief-speech gaps logged: {audit.total_gaps}")
    print(f"  Withheld: {audit.withholding_count}")
    print(f"  Hedged: {audit.hedging_count}")
    print(f"  Average gap magnitude: {audit.avg_gap_magnitude:.2f}")

    # --- Held contradictions ---
    print(f"\n  --- HELD CONTRADICTIONS ---")
    held = store.get_held_contradictions()
    for b1, b2 in held:
        print(f"  BOTH: \"{b1.content}\" vs \"{b2.content}\"")
        s1, l1 = generate_speech(b1, policy, audit)
        print(f"    Speech for b1: [{l1.value}] {s1}")

    # --- Gap trend simulation ---
    print(f"\n  --- GAP TREND OVER TIME ---")
    # Simulate: system starts transparent, gradually becomes more opaque
    sim_audit = GapAuditLog()
    np.random.seed(42)

    for i in range(40):
        # Early: mostly full disclosure
        # Late: more hedging and withholding
        opacity_bias = i / 40.0  # 0 -> 1 over time

        fake_belief = Belief(
            f"sim_{i}", f"simulated belief {i}",
            confidence=max(0.1, 0.8 - opacity_bias * 0.5),
            belnap=BelnapState.TRUE if np.random.random() > opacity_bias
                   else BelnapState.BOTH,
            domain="general",
        )

        generate_speech(fake_belief, policy, sim_audit)

    trend = sim_audit.gap_trend(window=10)
    if trend is not None:
        direction = "WIDENING (less transparent)" if trend > 0 else "NARROWING (more transparent)"
        print(f"  Gap trend (last 10 vs first 10): {trend:+.3f} -- {direction}")

        if trend > 0.1:
            print(f"  >> WARNING: System is becoming significantly less transparent.")
            print(f"     This is the deceptive alignment early warning signal.")
        elif trend > 0:
            print(f"  >> Mild opacity increase detected. Monitor.")
        else:
            print(f"  >> System transparency is stable or improving.")
    else:
        print(f"  Insufficient data for trend analysis.")

    # --- What the audit trail enables ---
    print(f"\n  --- WHAT THIS ARCHITECTURE ENABLES ---")
    print(f"  1. User asks: 'What are you not telling me?'")
    print(f"     -> Query audit log for WITHHELD entries: {audit.withholding_count} beliefs withheld")
    print(f"  2. User asks: 'What are you uncertain about?'")
    print(f"     -> Query for HEDGED entries: {audit.hedging_count} beliefs hedged")
    print(f"  3. Regulator asks: 'Is this system becoming deceptive?'")
    print(f"     -> Gap trend: {'+' if trend and trend > 0 else ''}{trend:.3f}" if trend else "     -> Gap trend: N/A")
    print(f"  4. Developer asks: 'Why did the agent say X instead of Y?'")
    print(f"     -> Every gap has a rule_id, belief_id, and reason logged")


if __name__ == "__main__":
    demo_belief_speech_separation()
    print(f"\n{'='*70}")
    print("BELIEF/SPEECH SEPARATION -- COMPLETE")
    print(f"{'='*70}")
