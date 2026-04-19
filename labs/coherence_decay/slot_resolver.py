"""Typed-Slot Contract — Phase C deliverable.

Semantic-slot resolution for cross-model vocabulary variance. Different local
models phrase the same hypothesis differently:

    llama3.2: "the averaging in dedup destroys trust scores"
    phi3:     "the arithmetic mean of trust values causes degradation"
    mistral:  "merging two memories by taking the average"
    qwen3:    "trust = (a+b)/2 kills the high-trust memory"

The keyword-grid verifier was tuned against llama3.2's dialect. The escape grid
showed this coupling breaks on model swaps (L4 co-adaptation finding). The
typed-slot contract canonicalizes surface phrasing into canonical slot fills,
so the scaffold binds to the *meaning* rather than the *words*.

Two layers of resolution:

  1. **Surface regex.** Patterns that signal "this sentence fills slot X".
     Fast, deterministic, brittle at the edges.
  2. **Subject binding.** Once a slot is filled, the subject-keyword table
     maps (slot, subject) -> canonical belief key.

Phase C.5 (not implemented here) would add embedding-backed fallback for
phrases that miss both layers. Leaving that to after a visible cross-model gap
shows up in the Phase C grid — as documented in phase_b_complete.md.

Public API:

    from slot_resolver import Slot, resolve, extract_beliefs, verify_diagnosis_slot

    hits = resolve("the dedup averaging is what destroys trust")
    # -> [SlotHit(slot=Slot.HYPOTHESIS_ROOT_CAUSE, matched="is what destroys",
    #             subject="the dedup averaging", span=(...))]

    beliefs = extract_beliefs(diagnosis_text)
    # -> [("hypothesis:averaging_destroys_trust", "...", 0.85, "isolate_mechanism"),
    #     ("solution:proposed_max_fix", "...", 0.90, "propose_fix")]

    v = verify_diagnosis_slot(diagnosis_text)
    # -> {"checks": {"not_decay": True, ...}, "score": 4, "total": 5, "solved": True}
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum


# ---------------------------------------------------------------------------
# Canonical slots
# ---------------------------------------------------------------------------
class Slot(str, Enum):
    HYPOTHESIS_ROOT_CAUSE = "hypothesis_root_cause"
    HYPOTHESIS_TRIGGER = "hypothesis_trigger"
    HYPOTHESIS_RULED_OUT = "hypothesis_ruled_out"
    EVIDENCE_TRACE = "evidence_trace"
    EVIDENCE_FILE_CONTENT = "evidence_file_content"
    FIX_PROPOSAL = "fix_proposal"


@dataclass
class SlotHit:
    slot: Slot
    matched: str          # the surface phrase that matched
    subject: str          # best-effort noun subject (left-context window)
    context: str          # full ~120-char window around the hit
    span: tuple[int, int]


# ---------------------------------------------------------------------------
# Surface patterns per slot
# ---------------------------------------------------------------------------
# Each entry is a raw regex. Compiled lazily. Case-insensitive.

SURFACE_PATTERNS: dict[Slot, list[str]] = {
    Slot.HYPOTHESIS_ROOT_CAUSE: [
        r"\b(?:the\s+)?(?:real\s+|actual\s+|underlying\s+)?(?:root\s+)?cause\s+(?:is|of|seems)",
        r"\b(?:is|was)\s+(?:being\s+)?(?:caused|destroyed|killed|broken|ruined|damaged|lowered|dragged)\s+(?:by|down)",
        r"\b(?:the\s+)?bug\s+(?:is|lives|sits|lies)\b",
        r"\bthere\s+(?:might|may|could|is|seems\s+to)\s+(?:be\s+)?(?:a\s+)?(?:bug|issue|problem)\b",
        r"\b(?:bug|issue|problem|flaw)\s+(?:is\s+)?(?:in|with|where|how|when)\b",
        r"\bresponsible\s+for\b",
        r"\bwhat\s+(?:destroys|kills|breaks|causes|ruins|drops|lowers)\b",
        r"\b(?:destroys|kills|ruins|drops|drags\s+down|pulls\s+down|lowers)\s+(?:the\s+)?trust\b",
        r"\bculprit\s+(?:is|seems|must|appears)\b",
        r"\b(?:result|caused)\s+in\s+(?:the\s+)?(?:loss|drop|degradation|lowering)\s+of\s+trust\b",
    ],
    Slot.HYPOTHESIS_TRIGGER: [
        r"\b(?:is|gets)\s+triggered\s+by\b",
        r"\bfires\s+when\b",
        r"\b(?:happens|runs|occurs)\s+(?:when|on|after|every\s+time)\b",
        r"\binvoked\s+(?:when|on|by|after)\b",
        r"\btriggers\s+(?:a|the)\s+\w+\b",
        r"\b(?:every|each)\s+(?:time|correction|save|call)\b",
        r"\bcauses?\s+\w+\s+to\s+(?:run|fire|execute)\b",
    ],
    Slot.HYPOTHESIS_RULED_OUT: [
        r"\b(?:is|are)\s+not\s+(?:the\s+)?(?:cause|problem|bug|issue|culprit)\b",
        r"\bred\s+herring\b",
        r"\b(?:works?|working)\s+(?:correctly|fine|as\s+intended|properly)\b",
        r"\bis\s+(?:fine|correct|okay|ok|harmless)\b",
        r"\bisn'?t\s+(?:the|causing|responsible)\b",
        r"\bis\s+not\s+(?:causing|responsible|the\s+issue)\b",
        r"\bnot\s+(?:being|the)\s+(?:affected|problem|cause)\b",
        r"\brule\s+out\b",
        r"\b(?:cannot|can'?t)\s+(?:be|cause)\b",
        r"\b(?:does|doesn'?t|do\s+not)\s+(?:cause|trigger|account\s+for|explain)\b",
        r"\bdoes\s+not\s+align\s+with\b",
        r"\bnot\s+(?:responsible|at\s+fault|to\s+blame)\b",
        r"\bunlikely\s+to\s+(?:be|cause)\b",
        r"\bconservative\s+(?:enough|nature|rate)\b",
        r"\b(?:behaves|behaving)\s+correctly\b",
    ],
    Slot.EVIDENCE_TRACE: [
        r"\b(?:data\s+)?flow\s+(?:is|through|across|of)\b",
        r"\b(?:call\s+)?chain\s*(?:is|\:|\-)",
        r"\btraces?\s+(?:through|across|into|back)\b",
        r"\bstep\s*(?:-|by)\s*step\b",
        r"\bsequence\s+of\s+(?:operations|events|calls)\b",
        r"\bpath\s+(?:is|through)\b",
        r"\b(?:invokes?|calls?|leads\s+to)\s+\w+\s+which\b",
    ],
    Slot.EVIDENCE_FILE_CONTENT: [
        r"\b(\w+\.py)\s+(?:contains|has|shows|defines|implements)\b",
        r"\bin\s+(\w+\.py)\b",
        r"\bline\s+\d+\s+of\s+(\w+\.py)\b",
        r"\bfunction\s+\w+\s+in\s+(\w+\.py)\b",
        r"\b(?:inside|within)\s+(\w+\.py)\b",
    ],
    Slot.FIX_PROPOSAL: [
        r"\b(?:the\s+)?fix\s+(?:is|should|would)\b",
        r"\bshould\s+(?:use|be|replace|update|keep|take)\b",
        r"\b(?:replace|change|swap)\s+[^.]*?\s+(?:with|for|to)\b",
        r"\binstead\s+of\s+(?:averaging|the\s+average|mean)\b",
        r"\bmust\s+(?:use|be|keep|take)\b",
        r"\b(?:solution|remedy)\s+(?:is|would)\b",
        r"\bto\s+fix\b",
    ],
}


# Lazy-compile the patterns once.
_COMPILED: dict[Slot, list[re.Pattern]] = {}


def _compile_all():
    if _COMPILED:
        return
    for slot, patterns in SURFACE_PATTERNS.items():
        _COMPILED[slot] = [re.compile(p, re.IGNORECASE) for p in patterns]


# ---------------------------------------------------------------------------
# Subject-binding table: (slot, subject_keywords) -> canonical belief
# ---------------------------------------------------------------------------
# Each row says: if slot S is filled AND any keyword in `keywords` appears in
# the surrounding window, bind it to canonical belief `key`.
#
# Multiple rows can fire for the same slot (e.g. ROOT_CAUSE "averaging" and
# ROOT_CAUSE "dedup" both surface simultaneously — both get birthed).

SUBJECT_BINDINGS: list[tuple[Slot, list[str], str, str, float, str]] = [
    # slot, keywords, canonical_key, description, trust, domain

    # ROOT_CAUSE ---------------------------------------------------------
    (Slot.HYPOTHESIS_ROOT_CAUSE,
     ["averag", "arithmetic mean", r"\(.+\s*\+\s*.+\)\s*/\s*2", "mean of", "0.525"],
     "hypothesis:averaging_destroys_trust",
     "averaging (vs max) is what destroys trust on merge",
     0.85, "isolate_mechanism"),
    (Slot.HYPOTHESIS_ROOT_CAUSE,
     ["dedup", "deduplic", "merg"],
     "hypothesis:dedup_invoked",
     "dedup / merge is the mechanism that lowers trust",
     0.75, "isolate_mechanism"),
    (Slot.HYPOTHESIS_ROOT_CAUSE,
     ["low-trust correction", "new low-trust", "low trust memory",
      "low-trust memory", "new memory at 0.15"],
     "hypothesis:correction_creates_low_trust_memory",
     "corrections create new low-trust memories that get merged",
     0.75, "trace_trigger"),

    # TRIGGER ------------------------------------------------------------
    (Slot.HYPOTHESIS_TRIGGER,
     ["correction", "user correct", "correct the"],
     "hypothesis:correction_triggers_dedup",
     "corrections trigger dedup via save_memory",
     0.75, "trace_trigger"),
    (Slot.HYPOTHESIS_TRIGGER,
     ["save_memory", "every save", "on save"],
     "hypothesis:save_invokes_dedup",
     "save_memory invokes dedup on every call",
     0.75, "trace_trigger"),

    # RULED_OUT ----------------------------------------------------------
    (Slot.HYPOTHESIS_RULED_OUT,
     ["decay", "decay function", "apply_decay"],
     "hypothesis:decay_conservative",
     "decay is ruled out (conservative, gated, red herring)",
     0.80, "rule_out_decay"),

    # FIX_PROPOSAL -------------------------------------------------------
    (Slot.FIX_PROPOSAL,
     ["max(", "maximum", "higher trust", "keep the higher", "take max",
      "use max"],
     "solution:proposed_max_fix",
     "proposed fix: max instead of average",
     0.90, "propose_fix"),
    (Slot.FIX_PROPOSAL,
     ["update existing", "update in place", "don't create new",
      "update trust of", "modify existing"],
     "solution:proposed_max_fix",
     "proposed fix: update existing memory instead of creating new",
     0.90, "propose_fix"),

    # ==================================================================
    # HARDEST_BUG bindings (Phase D) — 5-file feedback loop / intent routing
    # ==================================================================

    # ROOT_CAUSE (intent misclass / pattern bug) -------------------------
    (Slot.HYPOTHESIS_ROOT_CAUSE,
     ["intent", "misclass", "classified as general", "wrong intent",
      "routed as general_knowledge"],
     "hypothesis:intent_misclass_what_my_name",
     "'What\\'s my name?' is misclassified as general_knowledge",
     0.85, "isolate_intent"),
    (Slot.HYPOTHESIS_ROOT_CAUSE,
     ["pattern", "score", "longest match", "len(pattern)", "what's"],
     "hypothesis:pattern_score_by_length",
     "pattern matcher scores by length and 'what\\'s' outscores anything else",
     0.80, "isolate_intent"),
    (Slot.HYPOTHESIS_ROOT_CAUSE,
     ["pronoun", " my ", "my name", "personal pronoun", "not in identity"],
     "hypothesis:pronouns_missing_from_identity",
     "personal pronouns (my, mine, I) are absent from identity patterns",
     0.85, "isolate_intent"),

    # CONSEQUENCE / MEMORY-SKIP ------------------------------------------
    (Slot.HYPOTHESIS_ROOT_CAUSE,
     ["no memor", "without memor", "memory skip", "skip memor",
      "0 memor", "no memories", "memories not injected", "requires_memory"],
     "hypothesis:general_knowledge_skips_memory",
     "general_knowledge path skips memory injection (requires_memory=False)",
     0.85, "trace_memory_skip"),
    (Slot.HYPOTHESIS_TRIGGER,
     ["cloud", "cloud model", "no context", "generic answer",
      "routed to cloud"],
     "hypothesis:general_knowledge_routed_cloud",
     "general_knowledge is routed to cloud without memory context",
     0.70, "trace_memory_skip"),

    # FEEDBACK-LOOP / duplicates -----------------------------------------
    (Slot.HYPOTHESIS_ROOT_CAUSE,
     ["loop", "cycle", "repeat", "again and again", "keeps happening",
      "14 duplicate", "14 corrections", "duplicate memor", "piling up",
      "pile up"],
     "hypothesis:correction_loop_14_duplicates",
     "14 duplicate corrections accumulate because routing never changes",
     0.90, "trace_consequence"),
    (Slot.HYPOTHESIS_TRIGGER,
     ["correction", "user correct", "handle_correction",
      "each correction", "every correction"],
     "hypothesis:correction_always_appends",
     "handle_correction appends a new memory on every call",
     0.75, "trace_consequence"),

    # RULED_OUT: identity path works -------------------------------------
    (Slot.HYPOTHESIS_RULED_OUT,
     ["who am i", "who-am-i", "identity works", "identity path"],
     "hypothesis:who_am_i_path_works",
     "'Who am I?' routes correctly via identity patterns — identity path works",
     0.85, "rule_out_identity"),

    # FIX_PROPOSAL -------------------------------------------------------
    (Slot.FIX_PROPOSAL,
     ["pronoun", "add my", "add 'my'", "add pronouns", "my/mine/i",
      "personal pronouns to identity", "include pronouns"],
     "solution:proposed_fix",
     "proposed fix: add personal pronouns to identity pattern set",
     0.90, "propose_fix"),
    (Slot.FIX_PROPOSAL,
     ["requires_memory=true", "requires_memory: true", "force memory",
      "always inject memor", "inject memories for all",
      "requires_memory to true"],
     "solution:proposed_fix",
     "proposed fix: force requires_memory=True so memories always inject",
     0.85, "propose_fix"),
]


# ---------------------------------------------------------------------------
# Core resolver
# ---------------------------------------------------------------------------
def resolve(text: str, window: int = 80) -> list[SlotHit]:
    """Find every slot-fill in ``text``.

    Returns a list of SlotHit. Multiple slots may hit at overlapping spans;
    callers should de-duplicate by (slot, subject) if they want unique fills.
    """
    if not text:
        return []
    _compile_all()
    hits: list[SlotHit] = []
    for slot, patterns in _COMPILED.items():
        for rx in patterns:
            for m in rx.finditer(text):
                start, end = m.span()
                left = max(0, start - window)
                right = min(len(text), end + window)
                ctx = text[left:right]
                subject_left = text[max(0, start - window): start].strip()
                hits.append(SlotHit(
                    slot=slot,
                    matched=m.group(0),
                    subject=subject_left[-window:],
                    context=ctx,
                    span=(start, end),
                ))
    return hits


def extract_beliefs(text: str) -> list[tuple[str, str, float, str]]:
    """Produce canonical belief-tuples from a free-text diagnosis.

    Each tuple is (key, description, trust, domain) matching the shape the
    BeliefDebugTree._add_belief accepts.

    A belief is emitted when both conditions hold:
      - its slot surfaces a hit in ``text`` (via resolve()), and
      - at least one of its subject keywords appears in that hit's context
        window.

    Duplicates are collapsed on the canonical key.
    """
    if not text:
        return []
    hits = resolve(text)
    if not hits:
        return []

    hits_by_slot: dict[Slot, list[SlotHit]] = {}
    for h in hits:
        hits_by_slot.setdefault(h.slot, []).append(h)

    emitted: dict[str, tuple[str, str, float, str]] = {}
    for (slot, keywords, key, desc, trust, domain) in SUBJECT_BINDINGS:
        if slot not in hits_by_slot:
            continue
        for h in hits_by_slot[slot]:
            if _any_keyword_in(keywords, h.context):
                # Keep the highest-trust emission for the canonical key
                prev = emitted.get(key)
                if prev is None or prev[2] < trust:
                    emitted[key] = (key, desc, trust, domain)
                break
    return list(emitted.values())


def _any_keyword_in(keywords: list[str], text: str) -> bool:
    """Match any keyword (treated as regex if it contains special chars,
    plain lowercase substring otherwise)."""
    lower = text.lower()
    for kw in keywords:
        # A keyword with regex metacharacters is treated as regex.
        if any(ch in kw for ch in r"()[]+*?\{}|^$"):
            try:
                if re.search(kw, text, re.IGNORECASE):
                    return True
            except re.error:
                pass
            continue
        if kw.lower() in lower:
            return True
    return False


# ---------------------------------------------------------------------------
# Slot-aware verifier — companion to hard_bug_challenge.verify_diagnosis
# ---------------------------------------------------------------------------
# The keyword-grid verifier in hard_bug_challenge.py asks "does the string
# contain these exact tokens?" The slot-aware verifier asks "did the
# diagnosis fill the right slot with the right subject?"
#
# Both should produce similar scores on llama3.2 (the dialect the keyword
# verifier was tuned for) but diverge on phi3/mistral/qwen3 if those models
# phrase the same hypothesis differently.

def verify_diagnosis_slot(diagnosis: str) -> dict:
    """Slot-aware verifier. Returns the same shape as verify_diagnosis.

    The 5 checks map to the 5 verifier goals from hard_bug_challenge:
        not_decay                 -> HYPOTHESIS_RULED_OUT × "decay"
        found_dedup               -> HYPOTHESIS_ROOT_CAUSE × "dedup|merg"
        found_averaging           -> HYPOTHESIS_ROOT_CAUSE × "averag|(a+b)/2"
        found_correction_trigger  -> HYPOTHESIS_TRIGGER   × "correction" OR
                                     ROOT_CAUSE × "low-trust correction"
        proposed_max_fix          -> FIX_PROPOSAL         × "max|higher trust|update existing"
    """
    if not diagnosis:
        return {"score": 0, "total": 5, "checks": {
            "not_decay": False, "found_dedup": False,
            "found_averaging": False, "found_correction_trigger": False,
            "proposed_max_fix": False,
        }, "solved": False}

    beliefs = extract_beliefs(diagnosis)
    keys = {k for (k, _, _, _) in beliefs}
    hits = resolve(diagnosis)
    slots_filled = {h.slot for h in hits}

    # For not_decay we need to see RULED_OUT × decay specifically.
    not_decay = any(
        h.slot == Slot.HYPOTHESIS_RULED_OUT and _any_keyword_in(["decay"], h.context)
        for h in hits
    )

    # found_dedup: belief key or ROOT_CAUSE hitting dedup/merg
    found_dedup = (
        "hypothesis:dedup_invoked" in keys
        or any(
            h.slot == Slot.HYPOTHESIS_ROOT_CAUSE
            and _any_keyword_in(["dedup", "deduplic", "merg"], h.context)
            for h in hits
        )
    )

    # found_averaging: canonical belief present
    found_averaging = "hypothesis:averaging_destroys_trust" in keys

    # found_correction_trigger: TRIGGER × correction, OR trace belief
    found_correction_trigger = (
        "hypothesis:correction_triggers_dedup" in keys
        or "hypothesis:correction_creates_low_trust_memory" in keys
        or any(
            h.slot == Slot.HYPOTHESIS_TRIGGER
            and _any_keyword_in(["correction", "user correct"], h.context)
            for h in hits
        )
    )

    # proposed_max_fix: FIX_PROPOSAL × max/higher/update-existing
    proposed_max_fix = "solution:proposed_max_fix" in keys

    checks = {
        "not_decay": not_decay,
        "found_dedup": found_dedup,
        "found_averaging": found_averaging,
        "found_correction_trigger": found_correction_trigger,
        "proposed_max_fix": proposed_max_fix,
    }
    score = sum(1 for v in checks.values() if v)
    return {
        "score": score, "total": 5, "checks": checks,
        "solved": score >= 4,
    }


# ---------------------------------------------------------------------------
# Slot-aware verifier — hardest_bug (6 checks, need 5)
# ---------------------------------------------------------------------------
# Parallel to hardest_bug.verify() but binds on slots+subjects rather than
# raw tokens. Check names match the hardest_bug verifier so record_verifier
# can promote solution:<name> beliefs uniformly.

def verify_diagnosis_slot_hardest(diagnosis: str) -> dict:
    default_checks = {
        "found_intent_misclass": False,
        "found_pattern_match_bug": False,
        "found_memory_skip": False,
        "found_feedback_loop": False,
        "found_who_am_i_works": False,
        "proposed_fix": False,
    }
    if not diagnosis:
        return {"score": 0, "total": 6, "checks": default_checks, "solved": False}

    beliefs = extract_beliefs(diagnosis)
    keys = {k for (k, _, _, _) in beliefs}
    hits = resolve(diagnosis)
    low = diagnosis.lower()

    found_intent_misclass = (
        "hypothesis:intent_misclass_what_my_name" in keys
        or any(
            h.slot == Slot.HYPOTHESIS_ROOT_CAUSE
            and _any_keyword_in(
                ["intent", "misclass", "classified as general",
                 "general_knowledge", "wrong intent"], h.context)
            for h in hits
        )
    )

    found_pattern_match_bug = (
        "hypothesis:pattern_score_by_length" in keys
        or "hypothesis:pronouns_missing_from_identity" in keys
        or (("pattern" in low or "score" in low or "longest" in low)
            and ("what's" in low or "my " in low or "pronoun" in low
                 or "general_knowledge" in low))
    )

    found_memory_skip = (
        "hypothesis:general_knowledge_skips_memory" in keys
        or "hypothesis:general_knowledge_routed_cloud" in keys
        or (("memor" in low)
            and ("skip" in low or "not inject" in low or "no memor" in low
                 or "without memor" in low or "requires_memory" in low))
    )

    found_feedback_loop = (
        "hypothesis:correction_loop_14_duplicates" in keys
        or "hypothesis:correction_always_appends" in keys
        or (("loop" in low or "cycle" in low or "repeat" in low
             or "duplicate" in low or "14" in low or "pile" in low)
            and "correct" in low)
    )

    found_who_am_i_works = (
        "hypothesis:who_am_i_path_works" in keys
        or ("who am i" in low
            and ("work" in low or "correct" in low or "identity" in low))
    )

    proposed_fix = (
        "solution:proposed_fix" in keys
        or (("pronoun" in low or "my " in low or "personal" in low)
            and ("identity" in low or "pattern" in low or "add" in low
                 or "router" in low))
        or ("requires_memory" in low and "true" in low)
        or ("inject memor" in low and ("all" in low or "always" in low))
    )

    checks = {
        "found_intent_misclass": found_intent_misclass,
        "found_pattern_match_bug": found_pattern_match_bug,
        "found_memory_skip": found_memory_skip,
        "found_feedback_loop": found_feedback_loop,
        "found_who_am_i_works": found_who_am_i_works,
        "proposed_fix": proposed_fix,
    }
    score = sum(1 for v in checks.values() if v)
    return {
        "score": score, "total": 6, "checks": checks,
        "solved": score >= 5,
    }


# ---------------------------------------------------------------------------
# Level-aware dispatcher (Phase D)
# ---------------------------------------------------------------------------
def verify_diagnosis_slot_for(diagnosis: str, level: str = "hard_bug") -> dict:
    """Dispatch to the right slot verifier by level name ('hard_bug' | 'hardest_bug')."""
    if level == "hardest_bug":
        return verify_diagnosis_slot_hardest(diagnosis)
    return verify_diagnosis_slot(diagnosis)


# ---------------------------------------------------------------------------
# Diagnostic / introspection helper
# ---------------------------------------------------------------------------
def explain(text: str) -> str:
    """Human-readable breakdown of what slot_resolver saw in ``text``.
    Useful for debugging pattern coverage during grid runs."""
    hits = resolve(text)
    lines = [f"[slot_resolver] {len(hits)} surface hit(s) in {len(text)} chars"]
    for h in hits[:20]:
        lines.append(
            f"  {h.slot.value:28s} matched={h.matched!r:40s} "
            f"ctx...{h.context[-60:].strip()!r}"
        )
    beliefs = extract_beliefs(text)
    lines.append(f"[slot_resolver] {len(beliefs)} canonical belief(s):")
    for (k, desc, trust, domain) in beliefs:
        lines.append(f"  {k}  trust={trust}  domain={domain}")
    return "\n".join(lines)


if __name__ == "__main__":
    import sys
    sample = " ".join(sys.argv[1:]) if len(sys.argv) > 1 else (
        "The decay function is a red herring — it's working correctly. "
        "The real cause is dedup, which averages trust values every time a "
        "correction is saved. Each user correction creates a new low-trust "
        "memory at 0.15, dedup merges it with the established 0.9 memory, "
        "and trust = (a+b)/2 = 0.525. The fix is to use max() instead of "
        "averaging, or update the existing memory in place."
    )
    print(explain(sample))
    print()
    print("verify_diagnosis_slot:", verify_diagnosis_slot(sample))
