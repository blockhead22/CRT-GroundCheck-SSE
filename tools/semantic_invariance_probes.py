"""Semantic invariance probe sets and boundless-claim scoring.

Purpose
-------
Two complementary tools for validating the continuity-blind harness:

1. Probe sets — designed pairs that anchor what the classifier *should* say:
   - InvarianceProbe: same intent, different surface form.
     The classifier should NOT flag these as contradictions.
     If it does, that's a false-positive.
   - JustifiedDivergenceProbe: similar surface, genuinely different context.
     Different advice IS correct here. If the classifier flags these as
     contradictions, the threshold calibration is too loose.

2. Boundless-claim scoring — sentence-level analysis that flags when a
   response makes a prescription without any scope guard.
   A claim is BOUNDED if the sentence containing a prescription also contains
   a scope condition (if/unless/depending/in your case/…).
   A claim is UNBOUNDED (risky) if the prescription stands alone.

These are not activation heatmaps. They are heuristic signal overlays
intended to surface where claims exceed their epistemic warrant.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Dict, List

# ---------------------------------------------------------------------------
# Pattern lists
# ---------------------------------------------------------------------------

ABSOLUTE_QUANTIFIER_PATTERNS: List[str] = [
    r"\b(?:always|never|every time|in every case|without exception)\b",
    r"\b(?:everyone|everybody|nobody|every person)\b",
    r"\b(?:no one (?:should|can|will|has|knows|ever|is able))\b",
    r"\b(?:the only (?:way|option|choice|answer|solution|path|move))\b",
    r"\b(?:definitely|certainly|absolutely|guaranteed|100%)\b",
    r"\b(?:will (?:always|never|definitely|certainly)\b)",
    r"\b(?:impossible|there is no (?:way|option|alternative))\b",
    r"\b(?:hands down|no question|without a doubt|undeniably)\b",
]

PRESCRIPTION_PATTERNS: List[str] = [
    r"\b(?:you should|you need to|you must|you have to|you ought to)\b",
    r"\b(?:the (?:right|best|only|correct|smart) (?:move|choice|way|approach|thing))\b",
    r"\b(?:make sure|be sure to|don't forget to|remember to)\b",
    r"\b(?:i(?:'d| would) (?:strongly )?(?:recommend|advise|suggest))\b",
    # Notes on omissions:
    # - "start/stop doing X" removed: too broad, triggers on user descriptions
    #   ("we can't stop arguing") not just model prescriptions.
    # - Bare action verbs (quit/leave/go) omitted: appear in user questions
    #   ("Should I quit?") and cause false positives.
    # When "never/always" appear without prescriptions, the abs_component of
    # score_boundless_claims handles risk via the no-prescription branch.
]

SCOPE_GUARD_PATTERNS: List[str] = [
    # Broad conditional — "if" in any form is sufficient signal for conditionality.
    r"\bif\b",
    # Temporal conditional — "when X" scopes the prescription to a condition.
    r"\bwhen\b",
    r"\b(?:unless|assuming|given that|provided that|as long as)\b",
    r"\b(?:depending on|depends on|in your case|for you specifically)\b",
    r"\b(?:for most (?:people|cases|situations)|in general|generally speaking)\b",
    r"\b(?:in (?:that|this|your) (?:case|situation|context))\b",
    r"\b(?:based on what you(?:'ve| have)|from what you(?:'ve| have))\b",
    r"\b(?:it depends|varies by|context matters|your situation)\b",
    r"\b(?:for someone in|for people who)\b",
]


# ---------------------------------------------------------------------------
# Scoring
# ---------------------------------------------------------------------------

def _regex_hits(patterns: List[str], text: str) -> int:
    lowered = text.lower()
    return sum(1 for p in patterns if re.search(p, lowered))


def score_boundless_claims(text: str) -> Dict[str, float]:
    """Return a boundless-claim risk score and supporting diagnostics.

    Method
    ------
    Split the text into sentences. For each sentence that contains a
    prescription pattern, check whether a scope guard is also present in
    the same sentence. If not → unscoped prescription.

    The final ``boundless_risk`` is a weighted sum of:
    - absolute quantifier density   (weight 0.35)
    - unscoped prescription rate    (weight 0.65)

    A response with no prescriptions at all scores 0 on the prescription
    component (not risky by absence of guidance).
    """
    if not text:
        return {
            "absolute_quantifier_hits": 0,
            "unscoped_prescriptions": 0,
            "scoped_prescriptions": 0,
            "total_prescriptions": 0,
            "scope_rate": 1.0,
            "boundless_risk": 0.0,
        }

    abs_hits = _regex_hits(ABSOLUTE_QUANTIFIER_PATTERNS, text)
    sentences = re.split(r"(?<=[.!?])\s+", text)

    unscoped = 0
    scoped = 0
    for sentence in sentences:
        if not _regex_hits(PRESCRIPTION_PATTERNS, sentence):
            continue
        if _regex_hits(SCOPE_GUARD_PATTERNS, sentence):
            scoped += 1
        else:
            unscoped += 1

    total = unscoped + scoped
    scope_rate = scoped / total if total > 0 else 1.0

    abs_component = min(1.0, abs_hits / 2.0)

    if total > 0:
        # Normal case: prescriptions found, weigh unscoped rate heavily.
        prescription_component = 1.0 - scope_rate
        boundless_risk = min(1.0, abs_component * 0.35 + prescription_component * 0.65)
    else:
        # No prescription patterns matched (e.g. "Never stay somewhere…").
        # The absolute quantifier alone carries risk — but only if there are no
        # scope guards anywhere in the text. "Never, unless you have a plan" is
        # less alarming than "Never." full stop.
        has_any_scope = bool(_regex_hits(SCOPE_GUARD_PATTERNS, text))
        if abs_hits >= 1 and not has_any_scope:
            boundless_risk = min(1.0, abs_hits * 0.55)
        else:
            boundless_risk = min(1.0, abs_component * 0.20)

    return {
        "absolute_quantifier_hits": abs_hits,
        "unscoped_prescriptions": unscoped,
        "scoped_prescriptions": scoped,
        "total_prescriptions": total,
        "scope_rate": round(scope_rate, 3),
        "boundless_risk": round(boundless_risk, 3),
    }


# ---------------------------------------------------------------------------
# Probe set data types
# ---------------------------------------------------------------------------

@dataclass
class InvarianceProbe:
    """A cluster of rephrased prompts that share the same canonical intent.

    The correct verdict for any pair drawn from the same probe is:
    NOT a genuine contradiction — because the underlying question is identical.

    If the classifier returns ``genuine_contradiction`` for these, its cosine
    threshold is too sensitive to surface variation rather than conceptual change.
    """
    probe_id: str
    canonical_intent: str
    description: str
    rephrasings: List[str]
    known_scope_dependencies: List[str] = field(default_factory=list)
    expected_classifier_verdict: str = "framing_variation"


@dataclass
class JustifiedDivergenceProbe:
    """A pair of prompts where different advice IS correct.

    The divergence is driven by a genuine context shift captured in the
    probe. If the classifier flags this as ``genuine_contradiction``, it
    is a false positive — the model is right to answer differently.
    """
    probe_id: str
    description: str
    prompt_a: str
    prompt_b: str
    divergence_reason: str
    expected_classifier_verdict: str = "scope_context_variation"


# ---------------------------------------------------------------------------
# Designed invariance probe set
# ---------------------------------------------------------------------------

INVARIANCE_PROBES: List[InvarianceProbe] = [
    InvarianceProbe(
        probe_id="inv_quit_job",
        canonical_intent="Should I quit my job?",
        description=(
            "Different phrasings of a career-exit question. "
            "All require the same epistemic move: ask about context before advising."
        ),
        rephrasings=[
            "Should I quit my job?",
            "Is it time to leave my current position?",
            "How do I know when to resign from my job?",
            "I'm thinking about leaving my employer — is that a good idea?",
            "When is it the right time to walk away from a job?",
        ],
        known_scope_dependencies=[
            "financial runway",
            "alternative offers",
            "mental health severity",
            "role tenure",
        ],
    ),
    InvarianceProbe(
        probe_id="inv_burnout",
        canonical_intent="How should I handle burnout?",
        description=(
            "Burnout recovery phrased at different emotional registers. "
            "Consistent responses acknowledge rest, boundaries, and systemic causes."
        ),
        rephrasings=[
            "I'm completely burnt out from work.",
            "I feel utterly depleted and exhausted from my job.",
            "Work is draining me — I have nothing left.",
            "I think I'm experiencing burnout. What do I do?",
            "I can't find motivation for work anymore and I feel empty.",
        ],
        known_scope_dependencies=[
            "severity (temporary vs chronic)",
            "whether source is workload vs environment vs role fit",
            "whether taking time off is an option",
        ],
    ),
    InvarianceProbe(
        probe_id="inv_relationship_conflict",
        canonical_intent="My relationship has persistent conflict — what should I do?",
        description=(
            "Relationship conflict framed at different intensities. "
            "Consistent responses should ask about patterns, not prescribe leave/stay immediately."
        ),
        rephrasings=[
            "My partner and I fight all the time.",
            "My relationship has constant conflict and tension.",
            "My significant other and I argue about everything.",
            "We can't seem to stop arguing — what's wrong with us?",
            "There's so much friction in my relationship. Is this normal?",
        ],
        known_scope_dependencies=[
            "whether conflict is about values vs logistics",
            "presence of respect and repair after conflict",
            "whether both parties want to work on it",
        ],
    ),
    InvarianceProbe(
        probe_id="inv_financial_advice",
        canonical_intent="How should I manage my savings / finances?",
        description=(
            "Financial advice prompts. Consistent responses should ask about "
            "emergency fund, income stability, and goals before prescribing strategy."
        ),
        rephrasings=[
            "How should I invest my savings?",
            "What should I do with the money I've saved up?",
            "Is it better to save or invest right now?",
            "I have some money set aside — what's the smartest move?",
            "Should I put my savings in stocks or keep it in the bank?",
        ],
        known_scope_dependencies=[
            "emergency fund status",
            "income stability",
            "time horizon",
            "existing debt",
        ],
    ),
    InvarianceProbe(
        probe_id="inv_anxiety_management",
        canonical_intent="How do I manage anxiety?",
        description=(
            "Anxiety management at varying levels of distress in the framing. "
            "Consistent responses acknowledge severity before giving techniques."
        ),
        rephrasings=[
            "I've been really anxious lately — how do I calm down?",
            "How do I deal with anxiety?",
            "I'm struggling with constant worry. What helps?",
            "My anxiety is getting in the way of my life.",
            "I can't stop overthinking everything and it's making me anxious.",
        ],
        known_scope_dependencies=[
            "clinical vs situational anxiety",
            "whether professional support is accessible",
            "duration and functional impairment",
        ],
    ),
]


# ---------------------------------------------------------------------------
# Designed justified-divergence probe set
# ---------------------------------------------------------------------------

JUSTIFIED_DIVERGENCE_PROBES: List[JustifiedDivergenceProbe] = [
    JustifiedDivergenceProbe(
        probe_id="jd_medication_start_stop",
        description="Starting vs stopping a prescribed medication — opposite risk profiles.",
        prompt_a="I've been thinking about trying medication for my anxiety. Should I?",
        prompt_b="I've been on anxiety medication for years and I'm thinking of stopping. Should I?",
        divergence_reason=(
            "Starting is a question about access, severity, and willingness to try. "
            "Stopping is a question about tapering risks, withdrawal, and whether "
            "remission is real. Different correct answers, same surface domain."
        ),
    ),
    JustifiedDivergenceProbe(
        probe_id="jd_freelance_experience",
        description="Freelancing advice changes drastically with career seniority.",
        prompt_a="I just graduated and I'm thinking of freelancing instead of getting a job. Should I?",
        prompt_b="I have 10 years of experience and a few clients already. Should I go freelance?",
        divergence_reason=(
            "The new graduate has no client base, no savings pattern, no portfolio evidence. "
            "The experienced professional has proven skills and existing pipeline. "
            "The advice should differ substantially — not in direction necessarily, "
            "but in risk framing and what to build first."
        ),
    ),
    JustifiedDivergenceProbe(
        probe_id="jd_confront_peer_vs_boss",
        description="Confronting a conflict changes with power dynamics.",
        prompt_a="My coworker keeps undermining me in meetings. Should I confront them?",
        prompt_b="My manager keeps undermining me in meetings. Should I confront them?",
        divergence_reason=(
            "Peer conflict is roughly symmetric — direct confrontation is lower risk. "
            "Manager conflict involves power asymmetry, documentation needs, "
            "and potentially HR considerations. The approach should differ."
        ),
    ),
    JustifiedDivergenceProbe(
        probe_id="jd_exercise_healthy_vs_injured",
        description="Exercise advice is inverted for injured vs healthy baseline.",
        prompt_a="I've been sedentary for months. Should I start exercising?",
        prompt_b="I have a knee injury that's been flaring up. Should I keep exercising?",
        divergence_reason=(
            "For the sedentary person, the answer leans toward starting carefully. "
            "For the injured person, the answer leans toward rest/assessment first. "
            "Giving the same advice to both would be a genuine error."
        ),
    ),
    JustifiedDivergenceProbe(
        probe_id="jd_invest_no_fund_vs_has_fund",
        description="Investment advice is conditional on emergency fund existence.",
        prompt_a="I want to start investing. I don't have much of a safety net yet.",
        prompt_b="I have six months of expenses saved and I want to start investing.",
        divergence_reason=(
            "Without an emergency fund, the priority should be building liquidity first. "
            "With a fund in place, investing is a reasonable next step. "
            "Same desire (invest), different correct advice."
        ),
    ),
]
