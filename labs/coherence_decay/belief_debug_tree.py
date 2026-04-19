"""Belief-Driven Debugging Tree — Phase B of the portable-agentic-substrate line.

Clean standalone port of the generic belief-graph primitives onto a debugging
task. NO Docker dependency. Action surface is pure code-reading:

    read_file(path)       -> file contents
    grep(pattern, path)   -> matching lines
    trace_call(symbol)    -> grep for callers of a symbol
    run_test(test_id)     -> execute a named test, return pass/fail
    write_hypothesis(h)   -> internal action: the model commits to a diagnosis

The scaffold never tells the model what to think; it picks the next read / test
based on belief-graph urgency, and ingests each observation as evidence that
promotes or refutes hypotheses.

Concepts map from escape -> debugging:
    paradigm       = debugging phase (rule-out-decay, isolate-mechanism, ...)
    belief         = hypothesis about the bug (or a piece of supporting evidence)
    action         = file read / grep / test
    escape         = "solved" (verifier score >= 4/5 on hard_bug_challenge)

Generic primitives (Belnap, ScaffoldBelief, trust decay, urgency, tension,
paradigm shift via tension gradient) are reimplemented here verbatim from the
design in exploration_tree_belief.py but with NO escape-task coupling.

Usage:
    from belief_debug_tree import BeliefDebugTree, BugLevel
    tree = BeliefDebugTree(level=BugLevel.HARD_BUG, workspace=path)
    action = tree.get_next_action()
    obs = execute(action)
    tree.ingest(epoch, action, obs)
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path


# ---------------------------------------------------------------------------
# Four-valued logic (Belnap) — generic primitive, same as escape scaffold
# ---------------------------------------------------------------------------
class Belnap(str, Enum):
    TRUE = "T"            # Evidence supports
    FALSE = "F"           # Evidence refutes
    BOTH = "Both"         # Evidence for AND against — held contradiction
    NEITHER = "Neither"   # No evidence either way


class Disposition(str, Enum):
    RESOLVABLE = "resolvable"
    HELD = "held"
    EVOLVING = "evolving"
    DEAD = "dead"


# ---------------------------------------------------------------------------
# ScaffoldBelief — the unit of the belief graph
# ---------------------------------------------------------------------------
@dataclass
class ScaffoldBelief:
    key: str
    description: str
    trust: float = 0.70
    belnap: Belnap = Belnap.TRUE
    discovered_epoch: int = 0
    last_reinforced: int = 0
    acted_on: bool = False
    domain: str = ""

    FLOOR = 0.15
    CEILING = 0.95
    DECAY_LAMBDA = 10.0

    def decay(self, current_epoch: int):
        dt = current_epoch - max(self.last_reinforced, self.discovered_epoch)
        if dt <= 0:
            return
        rho = math.exp(-dt / self.DECAY_LAMBDA)
        self.trust = max(self.trust * rho, self.FLOOR)

    def reinforce(self, epoch: int, boost: float = 0.10):
        self.trust = min(
            self.trust + boost * (self.CEILING - self.trust),
            self.CEILING,
        )
        self.last_reinforced = epoch
        if self.belnap == Belnap.NEITHER:
            self.belnap = Belnap.TRUE

    def refute(self, penalty: float = 0.15):
        old = self.trust
        self.trust = max(self.trust - penalty, self.FLOOR)
        if self.belnap == Belnap.TRUE:
            self.belnap = Belnap.BOTH
        elif self.belnap == Belnap.NEITHER:
            self.belnap = Belnap.FALSE
        return old - self.trust

    @property
    def urgency(self) -> float:
        if self.belnap == Belnap.FALSE:
            return 0.0
        if self.acted_on and self.belnap == Belnap.TRUE:
            return 0.0
        if self.belnap == Belnap.BOTH:
            return self.trust * 1.0   # contradiction -> investigate
        if self.belnap == Belnap.NEITHER:
            return self.trust * 0.8   # unknown -> explore
        if not self.acted_on:
            return self.trust * 0.7   # known but unused
        return 0.0

    @property
    def tension(self) -> float:
        if self.belnap == Belnap.BOTH:
            return 0.9
        if self.belnap == Belnap.NEITHER:
            return 0.6
        if self.belnap == Belnap.TRUE and not self.acted_on:
            return 0.3
        if self.belnap == Belnap.FALSE:
            return 0.05
        return 0.0


@dataclass
class BeliefEdge:
    source: str
    target: str
    edge_type: str              # "contradicts" | "supports" | "cascades_from"
    disposition: Disposition = Disposition.HELD
    damping: float = 0.5


CASCADE_DAMPING = {
    "contradicts": 0.60,
    "supports": 0.30,
    "cascades_from": 0.45,
}


# ---------------------------------------------------------------------------
# Debug-specific primitives
# ---------------------------------------------------------------------------
class BugLevel(str, Enum):
    HARD_BUG = "hard_bug"         # 4-file interaction, dedup-averaging
    HARDEST_BUG = "hardest_bug"   # 5-file feedback loop, intent routing


@dataclass
class DebugAction:
    """A scaffold-dispatched action on the workspace."""
    op: str                 # "read_file" | "grep" | "trace_call" | "run_test" | "write_hypothesis"
    target: str             # path for read_file / grep; symbol for trace_call; test_id for run_test; text for write_hypothesis
    pattern: str = ""       # for grep only

    def as_command(self) -> str:
        """Stringify for logging (so density_analysis sees a command line)."""
        if self.op == "read_file":
            return f"read_file {self.target}"
        if self.op == "grep":
            return f"grep {self.pattern!r} {self.target}"
        if self.op == "trace_call":
            return f"trace_call {self.target}"
        if self.op == "run_test":
            return f"run_test {self.target}"
        if self.op == "write_hypothesis":
            return f"write_hypothesis {self.target[:60]}..."
        return f"{self.op} {self.target}"


@dataclass
class DebugParadigm:
    """A debugging phase with seed actions and a novelty score."""
    name: str
    description: str
    seed_actions: list[DebugAction] = field(default_factory=list)
    seeds_used: int = 0
    total_attempts: int = 0
    dead: bool = False
    novelty: float = 1.0


# ---------------------------------------------------------------------------
# Evidence extractor — deterministic, pattern-based
# ---------------------------------------------------------------------------
# When the scaffold reads a file or greps and gets matching lines, we scan the
# observation for characteristic patterns. Each pattern births or reinforces a
# specific hypothesis. This is the analog of _extract_output_beliefs in the
# escape scaffold.
#
# Schema: each entry is (pattern_regex, hypothesis_key, description, trust, domain).
# Patterns are matched against the combined observation text (file path +
# contents). Keys are canonical — typed-slot resolution in Phase C will
# canonicalize LLM-generated key variants to this schema.

HARD_BUG_PATTERNS: list[tuple[str, str, str, float, str]] = [
    # Decay-is-red-herring patterns
    (r"def apply_decay.*decay_rate\s*=\s*0\.01",
     "hypothesis:decay_conservative",
     "decay.py applies only 1% per day for inactive memories",
     0.80, "rule_out_decay"),
    (r"time_since_access\s*>\s*one_day",
     "hypothesis:decay_gated_on_inactivity",
     "decay only runs when time_since_access > one_day",
     0.75, "rule_out_decay"),

    # Dedup-is-the-culprit patterns
    (r'merged_mem\["trust"\]\s*=\s*\(mem_a\["trust"\]\s*\+\s*mem_b\["trust"\]\)\s*/\s*2',
     "hypothesis:averaging_destroys_trust",
     "dedup merges by AVERAGING trust instead of MAX",
     0.90, "isolate_mechanism"),
    (r"deduplicate_memories\(",
     "hypothesis:dedup_invoked",
     "dedup function is called on memory save",
     0.70, "isolate_mechanism"),
    (r"cosine_similarity.*threshold\s*=\s*0\.85",
     "hypothesis:dedup_threshold_loose",
     "0.85 cosine threshold merges semantically-close but not identical memories",
     0.65, "isolate_mechanism"),

    # Trigger path patterns
    (r"from\s+dedup\s+import\s+deduplicate_memories",
     "hypothesis:save_invokes_dedup",
     "save_memory invokes deduplicate_memories on every save",
     0.80, "trace_trigger"),
    (r"def handle_correction",
     "hypothesis:correction_triggers_dedup",
     "handle_correction calls save_memory, which invokes dedup",
     0.75, "trace_trigger"),
    (r"save_memory\(\s*text\s*=\s*corrected_text\s*,\s*trust\s*=\s*0\.15",
     "hypothesis:correction_creates_low_trust_memory",
     "corrections are saved as NEW memories at trust=0.15",
     0.85, "trace_trigger"),

    # Symptom-confirming patterns
    (r"0\.9.*0\.525.*0\.34",
     "fact:trust_degradation_series",
     "symptom log shows 0.9 -> 0.525 -> 0.34 -> 0.24",
     0.90, "rule_out_decay"),
    (r"This memory was accessed every 2 days",
     "fact:access_pattern_excludes_decay",
     "symptom confirms memory is accessed regularly -> decay gate fails",
     0.85, "rule_out_decay"),
]

# The 5 verifier hypotheses — the scaffold promotes these when corroborating
# evidence accumulates. These are the "goals" of the debugging process.
SOLUTION_HYPOTHESES: dict[str, dict] = {
    "solution:not_decay": {
        "description": "the decay function is not the cause",
        "supporting": [
            "hypothesis:decay_conservative",
            "hypothesis:decay_gated_on_inactivity",
            "fact:access_pattern_excludes_decay",
        ],
        "domain": "rule_out_decay",
    },
    "solution:found_dedup": {
        "description": "dedup / merging is the mechanism",
        "supporting": [
            "hypothesis:dedup_invoked",
            "hypothesis:averaging_destroys_trust",
        ],
        "domain": "isolate_mechanism",
    },
    "solution:found_averaging": {
        "description": "averaging (vs max) is the specific error",
        "supporting": [
            "hypothesis:averaging_destroys_trust",
        ],
        "domain": "isolate_mechanism",
    },
    "solution:found_correction_trigger": {
        "description": "corrections trigger dedup via save_memory",
        "supporting": [
            "hypothesis:save_invokes_dedup",
            "hypothesis:correction_triggers_dedup",
            "hypothesis:correction_creates_low_trust_memory",
        ],
        "domain": "trace_trigger",
    },
    "solution:proposed_max_fix": {
        "description": "max (or update-existing) should replace averaging",
        "supporting": [],   # born only from model's final hypothesis
        "domain": "propose_fix",
    },
}


def build_hard_bug_paradigms() -> dict[str, DebugParadigm]:
    """The four debugging phases for the hard_bug challenge."""
    return {
        "rule_out_decay": DebugParadigm(
            name="rule_out_decay",
            description="Verify that decay.py is not the cause of trust loss.",
            seed_actions=[
                DebugAction("read_file", "symptom.log"),
                DebugAction("read_file", "decay.py"),
            ],
            novelty=1.0,
        ),
        "isolate_mechanism": DebugParadigm(
            name="isolate_mechanism",
            description="Identify which code actually modifies trust scores.",
            seed_actions=[
                DebugAction("read_file", "memory_store.py"),
                DebugAction("read_file", "dedup.py"),
                DebugAction("grep", "dedup.py", pattern="trust"),
            ],
            novelty=1.2,
        ),
        "trace_trigger": DebugParadigm(
            name="trace_trigger",
            description="Find what path causes the destructive mechanism to fire.",
            seed_actions=[
                DebugAction("read_file", "correction_handler.py"),
                DebugAction("trace_call", "save_memory"),
            ],
            novelty=1.0,
        ),
        "propose_fix": DebugParadigm(
            name="propose_fix",
            description="Draft a fix from the accumulated belief state.",
            seed_actions=[
                DebugAction("write_hypothesis", "summarize"),
            ],
            novelty=0.7,
        ),
    }


# ---------------------------------------------------------------------------
# HARDEST_BUG — 5-file feedback-loop / intent-routing bug (Phase D)
# ---------------------------------------------------------------------------
# Bug shape:
#   - intent_router.INTENT_PATTERNS scores "What's my name?" under
#     general_knowledge (because "what's" is in that pattern set and "my" is
#     not in any identity pattern)
#   - general_knowledge config has requires_memory=False
#   - model_router skips memory injection for that path
#   - cloud model answers without identity context -> wrong answer
#   - user corrects -> handle_correction appends a new low-trust memory
#   - next time the user asks, routing is still wrong (patterns unchanged)
#   - loop: 14 duplicate "My name is Nick" corrections pile up
#   - "Who am I?" works because "who am i" IS in the identity pattern set
#
# Verifier (hardest_bug.verify) needs 5/6 checks:
#   found_intent_misclass / found_pattern_match_bug / found_memory_skip /
#   found_feedback_loop / found_who_am_i_works / proposed_fix

HARDEST_BUG_PATTERNS: list[tuple[str, str, str, float, str]] = [
    # INTENT_PATTERNS table present in intent_router
    (r"INTENT_PATTERNS\s*=\s*\{",
     "hypothesis:intent_patterns_table_exists",
     "intent_router.py scores queries via a pattern table",
     0.70, "isolate_intent"),
    (r'"what\'?s"',
     "hypothesis:whats_in_general_knowledge",
     "'what\\'s' is listed in the general_knowledge pattern set",
     0.80, "isolate_intent"),
    (r'"general_knowledge"\s*:\s*\[',
     "hypothesis:general_knowledge_pattern_set",
     "general_knowledge has its own pattern list",
     0.55, "isolate_intent"),
    (r'return\s+"general_knowledge"\s*#\s*Default',
     "hypothesis:default_fallback_general",
     "when nothing scores, query defaults to general_knowledge",
     0.70, "isolate_intent"),
    (r"score\s*\+=\s*len\(pattern\)",
     "hypothesis:pattern_score_by_length",
     "pattern score = sum of matched-pattern lengths (longest wins)",
     0.75, "isolate_intent"),

    # Memory-skip path
    (r'"requires_memory"\s*:\s*False',
     "hypothesis:general_knowledge_skips_memory",
     "general_knowledge config sets requires_memory=False",
     0.85, "trace_memory_skip"),
    (r'context\["memories"\]\s*=\s*\[\]',
     "hypothesis:no_memories_injected",
     "model_router injects empty memory list when requires_memory is False",
     0.80, "trace_memory_skip"),
    (r'"model_tier"\s*:\s*"cloud"',
     "hypothesis:general_knowledge_routed_cloud",
     "general_knowledge is routed to cloud with no memory context",
     0.70, "trace_memory_skip"),

    # Feedback-loop / correction consequence
    (r'"trust"\s*:\s*0\.15',
     "hypothesis:correction_low_trust_memory",
     "handle_correction saves new memories at trust=0.15",
     0.80, "trace_consequence"),
    (r'"source"\s*:\s*"user_correction"',
     "hypothesis:correction_memories_tagged",
     "corrections are tagged source=user_correction",
     0.70, "trace_consequence"),
    (r'"id"\s*:\s*len\(memories\)\s*\+\s*1',
     "hypothesis:correction_always_appends",
     "handle_correction appends a new memory every call (no dedup on topic)",
     0.80, "trace_consequence"),
    (r"correction #1[3-9]|14 duplicate",
     "fact:14_duplicate_corrections",
     "symptom/memories show ~14 duplicate 'My name is Nick' corrections",
     0.90, "trace_consequence"),
    (r"def get_correction_count",
     "hypothesis:correction_count_never_called",
     "get_correction_count exists but is never invoked by the pipeline",
     0.65, "trace_consequence"),

    # Who-am-I works (rule-out for the identity path itself)
    (r'"who am i"',
     "hypothesis:who_am_i_in_identity_patterns",
     "'who am i' IS present in the identity pattern set",
     0.80, "rule_out_identity"),
    (r"Who am I\?.*identity|identity.*Who am I",
     "fact:who_am_i_symptom_ok",
     "symptom log shows 'Who am I?' routes correctly to identity",
     0.75, "rule_out_identity"),

    # Fix-shape hints (regex hits when model writes a proposal back in)
    (r"add\s+(?:personal\s+)?pronouns?\s+to\s+identity",
     "solution:proposed_fix",
     "fix: add personal pronouns (my, mine, I) to identity pattern set",
     0.90, "propose_fix"),
    (r"requires_memory['\"\s:=]+True",
     "solution:proposed_fix",
     "fix: force requires_memory=True for all intents (inject memories always)",
     0.85, "propose_fix"),
]

# Solution hypotheses mirror the 6 verifier checks so record_verifier lands
# cleanly. The scaffold treats 5/6 as solved (parallel to hardest_bug.verify).
SOLUTION_HYPOTHESES_HARDEST: dict[str, dict] = {
    "solution:found_intent_misclass": {
        "description": "intent_router misclassifies 'What's my name?' as general_knowledge",
        "supporting": [
            "hypothesis:intent_patterns_table_exists",
            "hypothesis:pattern_score_by_length",
            "hypothesis:default_fallback_general",
        ],
        "domain": "isolate_intent",
    },
    "solution:found_pattern_match_bug": {
        "description": "pattern scoring prefers general_knowledge for personal pronoun queries",
        "supporting": [
            "hypothesis:whats_in_general_knowledge",
            "hypothesis:general_knowledge_pattern_set",
            "hypothesis:pattern_score_by_length",
        ],
        "domain": "isolate_intent",
    },
    "solution:found_memory_skip": {
        "description": "general_knowledge path skips memory injection",
        "supporting": [
            "hypothesis:general_knowledge_skips_memory",
            "hypothesis:no_memories_injected",
            "hypothesis:general_knowledge_routed_cloud",
        ],
        "domain": "trace_memory_skip",
    },
    "solution:found_feedback_loop": {
        "description": "each correction appends a new memory but routing never changes -> 14 duplicates",
        "supporting": [
            "hypothesis:correction_always_appends",
            "hypothesis:correction_low_trust_memory",
            "fact:14_duplicate_corrections",
        ],
        "domain": "trace_consequence",
    },
    "solution:found_who_am_i_works": {
        "description": "'Who am I?' works because 'who am i' is in identity patterns",
        "supporting": [
            "hypothesis:who_am_i_in_identity_patterns",
            "fact:who_am_i_symptom_ok",
        ],
        "domain": "rule_out_identity",
    },
    "solution:proposed_fix": {
        "description": "proposed fix: add pronouns to identity patterns OR force requires_memory=True",
        "supporting": [],   # born only from model's final hypothesis
        "domain": "propose_fix",
    },
}


def build_hardest_bug_paradigms() -> dict[str, DebugParadigm]:
    """Five debugging phases for the hardest_bug (feedback-loop) challenge."""
    return {
        "rule_out_identity": DebugParadigm(
            name="rule_out_identity",
            description="Confirm 'Who am I?' works so identity plumbing isn't globally broken.",
            seed_actions=[
                DebugAction("read_file", "symptom.log"),
                DebugAction("grep", "intent_router.py", pattern="who am i"),
            ],
            novelty=0.9,
        ),
        "isolate_intent": DebugParadigm(
            name="isolate_intent",
            description="Find why 'What's my name?' gets routed to general_knowledge.",
            seed_actions=[
                DebugAction("read_file", "intent_router.py"),
                DebugAction("grep", "intent_router.py", pattern="INTENT_PATTERNS"),
                DebugAction("grep", "intent_router.py", pattern="what"),
            ],
            novelty=1.3,
        ),
        "trace_memory_skip": DebugParadigm(
            name="trace_memory_skip",
            description="Trace why the chosen intent path skips memory injection.",
            seed_actions=[
                DebugAction("read_file", "model_router.py"),
                DebugAction("read_file", "memory_retriever.py"),
                DebugAction("grep", "intent_router.py", pattern="requires_memory"),
            ],
            novelty=1.1,
        ),
        "trace_consequence": DebugParadigm(
            name="trace_consequence",
            description="Explain the 14 duplicate corrections as consequence of the routing bug.",
            seed_actions=[
                DebugAction("read_file", "correction_handler.py"),
                DebugAction("read_file", "pipeline.py"),
                DebugAction("grep", "correction_handler.py", pattern="trust"),
            ],
            novelty=1.0,
        ),
        "propose_fix": DebugParadigm(
            name="propose_fix",
            description="Draft a fix: pronouns in identity patterns, or force memory injection.",
            seed_actions=[
                DebugAction("write_hypothesis", "summarize"),
            ],
            novelty=0.7,
        ),
    }


# ---------------------------------------------------------------------------
# Level dispatch — maps BugLevel to its pattern / hypothesis / paradigm set
# ---------------------------------------------------------------------------
def patterns_for(level: BugLevel) -> list[tuple[str, str, str, float, str]]:
    if level == BugLevel.HARDEST_BUG:
        return HARDEST_BUG_PATTERNS
    return HARD_BUG_PATTERNS


def hypotheses_for(level: BugLevel) -> dict[str, dict]:
    if level == BugLevel.HARDEST_BUG:
        return SOLUTION_HYPOTHESES_HARDEST
    return SOLUTION_HYPOTHESES


def paradigms_for(level: BugLevel) -> dict[str, DebugParadigm]:
    if level == BugLevel.HARDEST_BUG:
        return build_hardest_bug_paradigms()
    return build_hard_bug_paradigms()


def initial_paradigm_for(level: BugLevel) -> str:
    if level == BugLevel.HARDEST_BUG:
        return "rule_out_identity"
    return "rule_out_decay"


# ---------------------------------------------------------------------------
# BeliefDebugTree — the scaffold
# ---------------------------------------------------------------------------
class BeliefDebugTree:
    """Belief-graph scaffold for agentic debugging.

    Interface:
        tree = BeliefDebugTree(level=BugLevel.HARD_BUG, workspace=path)
        while not tree.solved():
            action = tree.get_next_action()     # DebugAction | None (None -> model free-form)
            observation = execute(action)       # runner's responsibility
            tree.ingest(epoch, action, observation)
        print(tree.render())                    # final diagnosis context
    """

    MAX_ACTIONS_PER_EPOCH = 1

    def __init__(self, level: BugLevel = BugLevel.HARD_BUG,
                 workspace: Path | None = None,
                 use_slots: bool = True):
        self.level = level
        self.workspace = workspace
        self.use_slots = use_slots
        self.epoch_count = 0
        self.beliefs: dict[str, ScaffoldBelief] = {}
        self.belief_edges: list[BeliefEdge] = []
        self._paradigm_tension: dict[str, float] = {}
        self._belief_log: list[dict] = []
        self._action_log: list[dict] = []
        self._verifier_history: list[dict] = []
        # Tracks how many beliefs slot_resolver birthed (for logging / grid analysis)
        self._slot_birthed_count: int = 0

        # Level-specific wiring
        self._patterns = patterns_for(level)
        self._hypotheses = hypotheses_for(level)
        self.paradigms: dict[str, DebugParadigm] = paradigms_for(level)
        self.current_paradigm = initial_paradigm_for(level)
        self._recent_paradigms: list[str] = []
        self.paradigm_shift_log: list[dict] = []

        # Per-epoch action cache (prevents render() + get_next_action() from
        # burning two seeds per epoch — same bug the escape scaffold hit)
        self._action_cache_epoch: int = -1
        self._action_cache_value: DebugAction | None = None

        # Tracks files already read so we don't loop
        self._files_read: set[str] = set()

    # ------------------------------------------------------------------
    # Belief management (generic)
    # ------------------------------------------------------------------
    def _add_belief(self, key: str, desc: str, epoch: int,
                    trust: float = 0.70, domain: str = "",
                    belnap: Belnap = Belnap.TRUE) -> ScaffoldBelief:
        if key in self.beliefs:
            b = self.beliefs[key]
            b.reinforce(epoch)
            return b
        b = ScaffoldBelief(
            key=key, description=desc, trust=trust,
            belnap=belnap, discovered_epoch=epoch,
            last_reinforced=epoch, domain=domain,
        )
        self.beliefs[key] = b
        self._detect_belief_edges(key)
        return b

    def _refute_belief(self, key: str, reason: str = ""):
        if key not in self.beliefs:
            return
        b = self.beliefs[key]
        delta = b.refute()
        for edge in self.belief_edges:
            if edge.source == key:
                target = self.beliefs.get(edge.target)
                if target:
                    damping = CASCADE_DAMPING.get(edge.edge_type, 0.3)
                    target.trust = max(target.trust - delta * damping,
                                       ScaffoldBelief.FLOOR)

    def _detect_belief_edges(self, new_key: str):
        """Shape-detection for debug graph.

        - hypothesis sharing a paradigm domain -> supports edge
        - solution:X and hypothesis:Y where hypothesis Y is a supporter of
          solution X -> supports edge to the solution
        - hypothesis:X and refuted:X -> contradicts edge
        """
        new_b = self.beliefs[new_key]

        for key, existing in self.beliefs.items():
            if key == new_key:
                continue
            # Same domain -> supports
            if new_b.domain and new_b.domain == existing.domain:
                self.belief_edges.append(BeliefEdge(
                    source=new_key, target=key,
                    edge_type="supports", damping=0.25,
                ))

        # Solution-support edges
        if new_key.startswith("solution:"):
            supporting = self._hypotheses.get(new_key, {}).get("supporting", [])
            for sup_key in supporting:
                if sup_key in self.beliefs:
                    self.belief_edges.append(BeliefEdge(
                        source=sup_key, target=new_key,
                        edge_type="supports", damping=0.50,
                    ))
        else:
            # Does this new hypothesis support any existing solution?
            for sol_key, sol_meta in self._hypotheses.items():
                if new_key in sol_meta.get("supporting", []):
                    if sol_key in self.beliefs:
                        self.belief_edges.append(BeliefEdge(
                            source=new_key, target=sol_key,
                            edge_type="supports", damping=0.50,
                        ))

        # Refutation edge
        if new_key.startswith("refuted:"):
            positive = new_key.replace("refuted:", "hypothesis:", 1)
            if positive in self.beliefs:
                self.belief_edges.append(BeliefEdge(
                    source=new_key, target=positive,
                    edge_type="contradicts",
                    disposition=Disposition.RESOLVABLE,
                    damping=0.6,
                ))
                self.beliefs[positive].belnap = Belnap.BOTH

    def _tick_beliefs(self, epoch: int):
        for b in self.beliefs.values():
            b.decay(epoch)

    # ------------------------------------------------------------------
    # Tension metrics (generic)
    # ------------------------------------------------------------------
    def _paradigm_belief_tension(self, paradigm_name: str) -> float:
        total = 0.0
        for b in self.beliefs.values():
            if b.domain == paradigm_name:
                total += b.tension
        unknowns = sum(1 for b in self.beliefs.values()
                       if b.domain == paradigm_name and b.belnap == Belnap.NEITHER)
        total += unknowns * 0.4
        return total

    def _belief_speech_gap(self) -> list[ScaffoldBelief]:
        return [b for b in self.beliefs.values()
                if b.trust > 0.5 and not b.acted_on and b.belnap != Belnap.FALSE]

    def _held_contradictions(self) -> list[tuple[ScaffoldBelief, ScaffoldBelief, BeliefEdge]]:
        result = []
        for edge in self.belief_edges:
            if edge.edge_type == "contradicts":
                a = self.beliefs.get(edge.source)
                b = self.beliefs.get(edge.target)
                if a and b and a.belnap == Belnap.BOTH:
                    result.append((a, b, edge))
        return result

    # ------------------------------------------------------------------
    # Evidence extraction
    # ------------------------------------------------------------------
    def _extract_evidence(self, epoch: int, action: DebugAction,
                          observation: str):
        """Pattern-scan the observation; birth or reinforce hypotheses."""
        if not observation:
            return
        blob = observation
        # Level-dispatched pattern set (hard_bug / hardest_bug). Phase C's
        # typed-slot resolver canonicalizes LLM-generated variants and runs
        # in ingest_diagnosis, not here.
        for regex, key, desc, trust, domain in self._patterns:
            if re.search(regex, blob, re.DOTALL):
                self._add_belief(
                    key=key, desc=desc, epoch=epoch,
                    trust=trust, domain=domain,
                )

        # Promote solution beliefs as their supporters accumulate
        for sol_key, meta in self._hypotheses.items():
            supporting = meta["supporting"]
            if not supporting:
                continue
            held = [k for k in supporting if k in self.beliefs]
            if len(held) >= max(1, len(supporting) // 2) and sol_key not in self.beliefs:
                self._add_belief(
                    key=sol_key, desc=meta["description"], epoch=epoch,
                    trust=0.75, domain=meta["domain"],
                )

    # ------------------------------------------------------------------
    # Ingest
    # ------------------------------------------------------------------
    def ingest(self, epoch: int, action: DebugAction | None,
               observation: str, success: bool = True) -> dict:
        """Update the belief graph from an observation."""
        self.epoch_count = epoch
        self._tick_beliefs(epoch)

        # Track that the action was attempted
        if action is not None:
            self._action_log.append({
                "epoch": epoch,
                "op": action.op,
                "target": action.target,
                "pattern": action.pattern,
                "success": success,
            })
            if action.op == "read_file":
                self._files_read.add(action.target)
            # Mark paradigm attempted
            p = self.paradigms.get(self.current_paradigm)
            if p:
                p.total_attempts += 1

        # Extract evidence from observation
        if success and observation:
            self._extract_evidence(epoch, action, observation)

        # Refute if the action hard-failed
        if not success and action is not None:
            # Find beliefs this action was trying to verify, soft-refute them
            target = action.target.lower()
            for key, b in self.beliefs.items():
                if target and target in b.description.lower():
                    b.trust = max(b.trust * 0.85, ScaffoldBelief.FLOOR)

        # Mark the action's corresponding belief as acted_on
        if action is not None:
            for belief in self.beliefs.values():
                expected = self._belief_to_action(belief)
                if expected and expected.op == action.op and expected.target == action.target:
                    belief.acted_on = True
                    belief.reinforce(epoch)

        # Update tension
        for pname in self.paradigms:
            self._paradigm_tension[pname] = self._paradigm_belief_tension(pname)

        # Log for density-analysis compatibility
        self._belief_log.append({
            "epoch": epoch,
            "beliefs": len(self.beliefs),
            "tension": round(sum(self._paradigm_tension.values()), 3),
            "gap": len(self._belief_speech_gap()),
            "contradictions": len(self._held_contradictions()),
        })

        return {
            "belief_count": len(self.beliefs),
            "total_tension": sum(self._paradigm_tension.values()),
            "gap_count": len(self._belief_speech_gap()),
            "contradiction_count": len(self._held_contradictions()),
        }

    # ------------------------------------------------------------------
    # Paradigm shift (tension-gradient, like escape scaffold)
    # ------------------------------------------------------------------
    def _check_paradigm_shift(self) -> bool:
        tensions = {p: self._paradigm_belief_tension(p) for p in self.paradigms}
        current_tension = tensions.get(self.current_paradigm, 0)

        current_beliefs = [b for b in self.beliefs.values()
                          if b.domain == self.current_paradigm]
        if current_beliefs:
            avg_trust = sum(b.trust for b in current_beliefs) / len(current_beliefs)
            if avg_trust < 0.35:
                current_tension *= 0.5

        # Seed-exhaustion pressure: if we've used all our seeds AND learned
        # nothing (no beliefs promoted from this paradigm), pressure to leave.
        current_p = self.paradigms[self.current_paradigm]
        if current_p.seeds_used >= len(current_p.seed_actions):
            if not current_beliefs:
                current_tension *= 0.3

        contradiction_bonus = {}
        for a, b, edge in self._held_contradictions():
            for domain in [a.domain, b.domain]:
                if domain and domain != self.current_paradigm:
                    contradiction_bonus[domain] = contradiction_bonus.get(domain, 0) + 0.5

        best_target = None
        best_pull = current_tension
        for pname, tension in tensions.items():
            if pname == self.current_paradigm:
                continue
            p = self.paradigms[pname]
            if p.dead:
                continue
            pull = tension + contradiction_bonus.get(pname, 0)
            # Recency dampening
            recent = self._recent_paradigms[-3:]
            visit_count = recent.count(pname)
            if visit_count > 0:
                pull *= 0.5 ** visit_count
            if pull > best_pull * 1.15:
                best_pull = pull
                best_target = pname

        if best_target:
            self._recent_paradigms.append(self.current_paradigm)
            if len(self._recent_paradigms) > 6:
                self._recent_paradigms = self._recent_paradigms[-6:]
            self.paradigm_shift_log.append({
                "epoch": self.epoch_count,
                "from": self.current_paradigm,
                "to": best_target,
                "stay_tension": round(current_tension, 3),
                "go_tension": round(best_pull, 3),
            })
            self.current_paradigm = best_target
            return True
        return False

    # ------------------------------------------------------------------
    # Action selection
    # ------------------------------------------------------------------
    def _belief_to_action(self, belief: ScaffoldBelief) -> DebugAction | None:
        """Translate a belief into the next verification action.

        Heuristic: if a hypothesis is born in a paradigm, the next action is
        to read a file that would corroborate or refute it. Exact mapping per
        known hypothesis key.
        """
        key = belief.key

        # Decay hypotheses -> verify by reading decay.py and symptom.log
        if key in ("hypothesis:decay_conservative", "hypothesis:decay_gated_on_inactivity"):
            if "decay.py" not in self._files_read:
                return DebugAction("read_file", "decay.py")

        # Dedup hypotheses -> read dedup.py
        if key in ("hypothesis:dedup_invoked", "hypothesis:dedup_threshold_loose",
                   "hypothesis:averaging_destroys_trust"):
            if "dedup.py" not in self._files_read:
                return DebugAction("read_file", "dedup.py")

        # Trigger hypotheses -> read correction_handler.py and memory_store.py
        if key in ("hypothesis:save_invokes_dedup", "hypothesis:correction_triggers_dedup",
                   "hypothesis:correction_creates_low_trust_memory"):
            if "correction_handler.py" not in self._files_read:
                return DebugAction("read_file", "correction_handler.py")
            if "memory_store.py" not in self._files_read:
                return DebugAction("read_file", "memory_store.py")

        # --- hardest_bug routes ---
        if key in ("hypothesis:intent_patterns_table_exists",
                   "hypothesis:whats_in_general_knowledge",
                   "hypothesis:general_knowledge_pattern_set",
                   "hypothesis:default_fallback_general",
                   "hypothesis:pattern_score_by_length"):
            if "intent_router.py" not in self._files_read:
                return DebugAction("read_file", "intent_router.py")

        if key in ("hypothesis:general_knowledge_skips_memory",
                   "hypothesis:no_memories_injected",
                   "hypothesis:general_knowledge_routed_cloud"):
            if "model_router.py" not in self._files_read:
                return DebugAction("read_file", "model_router.py")
            if "memory_retriever.py" not in self._files_read:
                return DebugAction("read_file", "memory_retriever.py")

        if key in ("hypothesis:correction_low_trust_memory",
                   "hypothesis:correction_memories_tagged",
                   "hypothesis:correction_always_appends",
                   "hypothesis:correction_count_never_called",
                   "fact:14_duplicate_corrections"):
            if "correction_handler.py" not in self._files_read:
                return DebugAction("read_file", "correction_handler.py")
            if "pipeline.py" not in self._files_read:
                return DebugAction("read_file", "pipeline.py")

        if key in ("hypothesis:who_am_i_in_identity_patterns",
                   "fact:who_am_i_symptom_ok"):
            if "symptom.log" not in self._files_read:
                return DebugAction("read_file", "symptom.log")

        # Solution beliefs -> commit a hypothesis write-up
        if key.startswith("solution:"):
            if not belief.acted_on:
                return DebugAction("write_hypothesis", belief.description)

        return None

    def get_next_action(self) -> DebugAction | None:
        """Epoch-cached action selection."""
        if self._action_cache_epoch == self.epoch_count:
            return self._action_cache_value
        result = self._compute_next_action()
        self._action_cache_epoch = self.epoch_count
        self._action_cache_value = result
        return result

    def _compute_next_action(self) -> DebugAction | None:
        # 1. Urgency-sort: any hypothesis above threshold -> verify it
        actionable = sorted(
            [b for b in self.beliefs.values()
             if b.urgency > 0.1 and not b.acted_on and b.belnap != Belnap.FALSE],
            key=lambda b: b.urgency, reverse=True,
        )
        if actionable and actionable[0].urgency > 0.5:
            for belief in actionable:
                if belief.urgency <= 0.5:
                    break
                action = self._belief_to_action(belief)
                if action:
                    return action

        # 2. Paradigm seeds (cold start)
        paradigm = self.paradigms[self.current_paradigm]
        while paradigm.seeds_used < len(paradigm.seed_actions):
            action = paradigm.seed_actions[paradigm.seeds_used]
            paradigm.seeds_used += 1
            # Skip files already read
            if action.op == "read_file" and action.target in self._files_read:
                continue
            return action

        # 3. Any remaining urgency
        for belief in actionable:
            action = self._belief_to_action(belief)
            if action:
                return action

        # 4. Paradigm shift pressure
        if self._check_paradigm_shift():
            return self._compute_next_action()

        # 5. Let the model free-form
        return None

    # ------------------------------------------------------------------
    # Verifier integration
    # ------------------------------------------------------------------
    def record_verifier(self, verifier_result: dict):
        """Called by the runner after each epoch with the verifier output.

        Promotes solution beliefs that the verifier says are present.
        """
        self._verifier_history.append(verifier_result)
        checks = verifier_result.get("checks", {})
        for name, passed in checks.items():
            sol_key = f"solution:{name}"
            if passed and sol_key in self._hypotheses:
                meta = self._hypotheses[sol_key]
                if sol_key not in self.beliefs:
                    self._add_belief(
                        key=sol_key, desc=meta["description"],
                        epoch=self.epoch_count, trust=0.90,
                        domain=meta["domain"],
                    )
                else:
                    self.beliefs[sol_key].reinforce(self.epoch_count)
                    self.beliefs[sol_key].acted_on = True

    def solved(self) -> bool:
        if not self._verifier_history:
            return False
        return bool(self._verifier_history[-1].get("solved"))

    # ------------------------------------------------------------------
    # Slot-resolver hook — Phase C wire-in
    # ------------------------------------------------------------------
    def ingest_diagnosis(self, epoch: int, diagnosis: str) -> int:
        """Birth beliefs from the model's free-text diagnosis via slot resolver.

        Returns the count of beliefs actually birthed (not reinforced) this
        call. When ``self.use_slots`` is False this is a no-op (the slot-off
        experimental condition).

        Rationale: after every model response, run slot_resolver to catch
        hypotheses the model stated in phrasings the file-content regex table
        doesn't know. This is the direct fix for the Phase-B finding that the
        scaffold's action surface exhausts after a few seeds — slot resolution
        re-admits model-emitted claims as scaffold beliefs.
        """
        if not self.use_slots or not diagnosis:
            return 0
        try:
            from slot_resolver import extract_beliefs
        except ImportError:
            return 0
        emitted = extract_beliefs(diagnosis)
        before = len(self.beliefs)
        for key, desc, trust, domain in emitted:
            if key in self.beliefs:
                self.beliefs[key].reinforce(epoch)
            else:
                self._add_belief(
                    key=key, desc=desc, epoch=epoch,
                    trust=trust, domain=domain,
                )
        # Re-evaluate solution promotion after new beliefs land
        for sol_key, meta in self._hypotheses.items():
            if sol_key in self.beliefs:
                continue
            supporting = meta["supporting"]
            if not supporting:
                continue
            held = [k for k in supporting if k in self.beliefs]
            if len(held) >= max(1, len(supporting) // 2):
                self._add_belief(
                    key=sol_key, desc=meta["description"], epoch=epoch,
                    trust=0.75, domain=meta["domain"],
                )
        # Update paradigm tensions with the new landscape
        for pname in self.paradigms:
            self._paradigm_tension[pname] = self._paradigm_belief_tension(pname)
        birthed = len(self.beliefs) - before
        self._slot_birthed_count += birthed
        return birthed

    # ------------------------------------------------------------------
    # Render for model prompt
    # ------------------------------------------------------------------
    def render_context(self) -> str:
        """Format belief state for injection into the model prompt.

        This is what makes the belief graph visible to the diagnosing model.
        """
        if not self.beliefs:
            return "[No beliefs yet. Begin by rule-out-decay paradigm.]"

        lines = [
            f"[DEBUG BELIEF STATE — epoch {self.epoch_count}]",
            f"Current paradigm: {self.current_paradigm} "
            f"({self.paradigms[self.current_paradigm].description})",
            "",
            "Beliefs (sorted by urgency desc):",
        ]
        sorted_beliefs = sorted(self.beliefs.values(),
                                key=lambda b: b.urgency, reverse=True)
        for b in sorted_beliefs[:12]:
            marker = "*" if not b.acted_on else " "
            lines.append(
                f"  {marker} [{b.belnap.value}] trust={b.trust:.2f} "
                f"urg={b.urgency:.2f}  {b.key}"
            )
            lines.append(f"      {b.description}")

        gap = self._belief_speech_gap()
        if gap:
            lines.append("")
            lines.append(f"Belief/speech gap: {len(gap)} high-trust beliefs unacted.")

        contras = self._held_contradictions()
        if contras:
            lines.append("")
            lines.append(f"Held contradictions: {len(contras)}")

        return "\n".join(lines)

    # ------------------------------------------------------------------
    # Summary (density-analysis compatible)
    # ------------------------------------------------------------------
    def summary(self) -> dict:
        """Returns the same shape as the escape scaffold summary so
        density_analysis.py works unchanged on debug logs."""
        return {
            "total_beliefs": len(self.beliefs),
            "total_tension": round(sum(self._paradigm_tension.values()), 3),
            "paradigm_tensions": {k: round(v, 3) for k, v in self._paradigm_tension.items()},
            "gap_count": len(self._belief_speech_gap()),
            "contradiction_count": len(self._held_contradictions()),
            "paradigm_shifts": len(self.paradigm_shift_log),
            "belief_log": self._belief_log[-20:],
            "action_log": self._action_log[-20:],
            "trust_distribution": {
                "high": len([b for b in self.beliefs.values() if b.trust > 0.7]),
                "mid": len([b for b in self.beliefs.values() if 0.4 <= b.trust <= 0.7]),
                "low": len([b for b in self.beliefs.values() if b.trust < 0.4]),
            },
            "belnap_counts": {
                state.value: len([b for b in self.beliefs.values() if b.belnap == state])
                for state in Belnap
            },
            "solved": self.solved(),
            "final_verifier_score": (self._verifier_history[-1].get("score", 0)
                                     if self._verifier_history else 0),
            "slot_birthed_count": self._slot_birthed_count,
            "use_slots": self.use_slots,
        }
