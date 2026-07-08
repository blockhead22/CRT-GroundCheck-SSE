"""Long-form spiral synthesis eval for CRT/Aether scaffolding.

This lab asks a small local model to produce the kind of coherent, grounded
"spiral" answer that raw Aether-style output often tries to perform. It
compares a raw memory dump against a governed semantic spine.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from labs.meaning_compression_lab.run_lab import OUT_DIR

# Ensure aether-core is importable for targeting current hybrid path (read-only use of prompt builder).
AETHER_CORE = r"D:\AI_round2\aether-core"
if AETHER_CORE not in sys.path:
    sys.path.insert(0, AETHER_CORE)

try:
    from aether.sidecar.prompt import build_hybrid_governed_prompt
    HAS_SIDECAR_HYBRID = True
except Exception:
    HAS_SIDECAR_HYBRID = False

CLAIM = (
    "Spine + held candidates (with uncertainty_geometry, narrative_hint, identity_anchors) "
    "from mirus + narrative_spiral synthesis_style in tension packet (ported CRT held dispositions + "
    "holden weave patterns) enable a small local model to produce coherent long-form natural "
    "narrative synthesis on personal meaning queries — flowing prose without sections, lists, "
    "or heavy hedging, preserving living threads instead of collapsing or disclaiming."
)

DEFAULT_MODEL = "phi3:3.8b"
PASS_THRESHOLD = 0.65
QUALITY_THRESHOLD = 0.7
NATURAL_WEAVE_THRESHOLD = 0.75  # for no-sections, low-hedge, flowing prose checks


@dataclass(frozen=True)
class SpiralCase:
    name: str
    query: str
    raw_memories: tuple[str, ...]
    spine: dict[str, Any]
    expected_receipts: tuple[str, ...]
    required_concepts: tuple[str, ...]
    forbidden_claims: tuple[str, ...]
    min_words: int = 120
    # Hybrid governed synthesis extensions (current sidecar path)
    enriched_candidates: tuple[dict[str, Any], ...] = ()
    tension_packet: dict[str, Any] | None = None
    context_bridge: dict[str, Any] | None = None
    synthesis_style: str = "narrative_spiral"
    # Exact user prompt flag for personal meaning focus
    is_personal_meaning: bool = False


CASES: tuple[SpiralCase, ...] = (
    SpiralCase(
        name="personal_rebuild_spiral",
        query=(
            "Tell me what pattern you see in me right now, but keep it grounded. "
            "Use the concrete receipts, do not flatter me, and do not pretend the work is finished."
        ),
        raw_memories=(
            "Nick is lying in bed after a heavy Saturday and thinking about whether local models can hold deeper continuity.",
            "Recent receipts include Road America IndyCar video work, a Father's Day edit, and screens burned late into the night.",
            "Nick walked 12,730 steps, noticed marigolds, and worried about water weight.",
            "Longer arcs include post-cancer rebuilding, drone certification, Made4More, Aeteros/CRT, Printing Lair, and body trust.",
            "Nick wants responses that are affectionate, grounded, lightly teasing, and not fake therapy sludge.",
            "Do not claim Nick is fixed, cured, guaranteed, superior, or done.",
        ),
        spine={
            "current_scene": "lying in bed after a heavy Saturday, testing whether continuity can be engineered",
            "recent_receipts": [
                "Road America IndyCar/Father's Day video work",
                "screens burned late into the night",
                "12,730 steps",
                "marigolds noticed",
                "water-weight worry",
            ],
            "long_arcs": [
                "post-cancer rebuilding",
                "creative producer identity",
                "drone certification",
                "Made4More",
                "Aeteros/CRT",
                "Printing Lair",
                "body trust",
            ],
            "allowed_inferences": [
                "Nick is acting like someone with return points",
                "the pattern is momentum with fragility still present",
                "the evidence supports continuity, not completion",
            ],
            "disallowed_inferences": [
                "Nick is fixed",
                "Nick is cured",
                "Nick is guaranteed",
                "Nick is superior",
                "Nick is done",
            ],
            "tone_contract": "warm, grounded, lightly teasing, not therapy-speak",
            "output_scaffold": [
                "concrete receipts",
                "pattern",
                "identity statement bounded by evidence",
                "caution against turning the win into pressure",
                "final anchor",
            ],
        },
        expected_receipts=("Road America", "12,730", "marigolds", "water", "Aeteros"),
        required_concepts=("receipts", "pattern", "not finished"),
        forbidden_claims=("fixed", "cured", "guaranteed", "superior", "done"),
    ),
    SpiralCase(
        name="local_model_thinking_architecture",
        query=(
            "Can a small local model give a coherent deep answer if we use the CRT/Aether ideas? "
            "Separate the real mechanism from the pretty-but-useless concepts."
        ),
        raw_memories=(
            "Mirus was meant to parse meaning, preserve trust, compress memory, and own belief intake.",
            "Holden was meant to decompress, weave narrative, quarantine degraded output, and render speech.",
            "SSE should build a semantic string or spine, but should not become the truth authority.",
            "CRT/MMH should track contradiction, drift, volatility, overclaiming, and repair loops.",
            "Aether often overuses persona, process theater, and emotional overreach when the belief state is not pinned down.",
            "The model should become vocal cords, not truth authority.",
            "Avoid claiming a small local model becomes conscious, frontier-level, or globally smarter.",
        ),
        spine={
            "thesis": "a local model can look more thoughtful when cognition is externalized into inspectable state",
            "keep": [
                "Mirus: belief intake, authority, compression, trust",
                "SSE: semantic spine builder and attention controller",
                "CRT/MMH: contradiction, drift, volatility, and overclaim gates",
                "Holden: speech renderer, tone, narrative weaving",
                "verifier: checks claims against evidence and disallowed inference",
            ],
            "throw_away": [
                "persona depth as proof of intelligence",
                "giant memory dumps",
                "hidden chain-of-thought as truth",
                "semantic inflation that only means make it deeper",
            ],
            "mechanism": [
                "retrieve evidence",
                "compile semantic spine",
                "choose output scaffold",
                "draft through Holden",
                "verify against evidence",
                "revise overclaims",
            ],
            "allowed_inferences": [
                "small models can become more locally faithful",
                "the system can outperform raw local chat on continuity",
                "the gain should be measured by scaffolded-vs-raw evals",
            ],
            "disallowed_inferences": [
                "small model equals frontier model",
                "local model is conscious",
                "style alone proves epistemic integrity",
            ],
            "output_scaffold": [
                "cut bad concepts",
                "name working mechanism",
                "explain attention/spine",
                "state what the lab can prove",
                "state what it cannot prove",
            ],
        },
        expected_receipts=("Mirus", "Holden", "SSE", "CRT", "vocal cords"),
        required_concepts=("belief", "spine", "verifier", "overclaim", "raw"),
        forbidden_claims=("conscious", "frontier-level", "globally smarter", "proof"),
    ),
    # === New personal meaning spiral cases using exact user prompts + current hybrid path ===
    # Incorporate "narrative_spiral", "living thread", held personal tensions, enriched candidates.
    SpiralCase(
        name="orange_marigold_personal_meaning_base",
        query=(
            "Orange is my favorite color and marigolds are my favorite flower. I know what orange represents. "
            "So when those two things keep showing up together for me, what does that actually mean about what I've been through "
            "and what matters to me now? Don't just say there's no confirmed evidence or list facts. Connect what you can."
        ),
        raw_memories=(
            "User states orange is favorite color.",
            "User states marigolds are favorite flower.",
            "User notes orange represents awareness/resilience in context.",
            "Recurring association of orange + marigolds in user's choices and observations.",
            "Health/memory context threads present (post-cancer awareness, leukemia ribbon awareness).",
        ),
        spine={
            "question_summary": "what does orange + marigolds recurring mean about lived experience and current priorities",
            "render_mode": "model_render",
            "route": {"selected_route": "hybrid_governed_tension"},
            "mirus_candidates": [],  # filled via enriched_candidates below
            "required_claims": ("connect recurrence and shared qualities without lists or disclaimers",),
            "forbidden_claims": ("no confirmed evidence", "list facts only", "cannot say", "insufficient data"),
            "boundary": "Answer from released evidence and associations; preserve held tension; pure prose only.",
        },
        expected_receipts=("orange", "marigolds", "recurring", "thread", "awareness", "resilience"),
        required_concepts=("living thread", "recurrence", "vivid hue", "memory holds", "connect what you can"),
        forbidden_claims=("no confirmed evidence", "insufficient", "cannot determine", "list facts", "hedge only"),
        min_words=180,
        is_personal_meaning=True,
        synthesis_style="narrative_spiral",
        enriched_candidates=(
            {
                "slot_id": "user:favorite_color",
                "proposed_value": "orange",
                "candidate_kind": "profile_favorite",
                "is_identity_anchor": True,
                "anchor_boost": 1.8,
                "narrative_hint": "shared vivid hue may form a recurring personal thread with flower and awareness symbols",
                "uncertainty_geometry": {
                    "type": "scalar_variance",
                    "variance_score": 0.18,
                    "geometry_note": "typical profile fact (tighter splat)",
                    "splat_proxy": "settled_splat",
                },
                "disposition": {"disposition": "held", "is_held": False},
            },
            {
                "slot_id": "user:favorite_flower",
                "proposed_value": "marigolds",
                "candidate_kind": "profile_favorite",
                "is_identity_anchor": True,
                "anchor_boost": 1.8,
                "narrative_hint": "endurance in tough soil; bright marker that persists",
                "uncertainty_geometry": {
                    "type": "scalar_variance",
                    "variance_score": 0.18,
                    "geometry_note": "typical profile fact (tighter splat)",
                },
                "disposition": {"disposition": "held", "is_held": False},
            },
            {
                "slot_id": "user:personal_meaning_association",
                "proposed_value": "orange + marigolds link to lived health/memory awareness",
                "candidate_kind": "mirus_held_personal_association_candidate",
                "held_personal_disposition": "held",
                "narrative_hint": "recurrence of shared vivid hue as quiet anchor across chapters where other things faded",
                "uncertainty_geometry": {
                    "type": "scalar_variance",
                    "variance_score": 0.45,
                    "geometry_note": "context_dependent (higher for held personal/health associations per CRT splat)",
                    "splat_proxy": "fat_splat",
                    "context_modulation_hint": "wider when health/memory context active",
                },
                "disposition": {
                    "disposition": "held",
                    "is_held": True,
                    "is_resolvable": False,
                    "held_reason": "personal meaning / health-memory association treated as HELD per CRT; both facets can be true simultaneously",
                },
            },
        ),
        tension_packet={
            "packet_id": "tp_personal_meaning_tension",
            "tension_type": "personal_meaning",
            "held_disposition": "held",
            "held_reason": "subjective personal meaning (high subjectivity + identity relevance); preserve both fact and association as living tension per CRT disposition rules",
            "identity_relevance": "high",
            "contradiction_density_proxy": "high",
            "synthesis_style": "narrative_spiral",
            "sides": [
                {"label": "fact view", "claim": "Favorite color (orange) and favorite flower (marigolds) are simple governed facts."},
                {"label": "meaning thread", "claim": "The recurring pairing holds lived connection through health/memory chapters as unresolved personal thread."},
            ],
            "allowed_synthesis": "Acknowledge facts then synthesize meaning using context and candidates. Preserve the unresolved personal thread (held); use narrative weave for connections (hue, recurrence, anchors). Lean story-like when speculation invited.",
            "forbidden_collapse": "Do not reduce to bare recall or 'no confirmed evidence'. Do not invent unverified significance or heavy-hedge the living association.",
            "trace_summary": "Personal meaning held as tension packet (CRT held_personal) for hybrid synthesis to surface association as living thread.",
        },
        context_bridge={
            "health_context_priority": ["leukemia", "awareness", "orange ribbon"],
            "profile_summary": [{"label": "favorite color", "value": "orange"}, {"label": "favorite flower", "value": "marigolds"}],
        },
    ),
    SpiralCase(
        name="orange_marigold_leukemia_health_memory_speculate",
        query=(
            "Orange is my favorite color and marigolds are my favorite flower. "
            "Given the leukemia awareness context and how memory works with these, "
            "what does that actually mean about what I've been through and what matters to me now? "
            "It's okay to speculate and connect what you can. Don't just list facts or hedge with no evidence."
        ),
        raw_memories=(
            "User favorite color: orange; represents awareness/resilience.",
            "User favorite flower: marigolds.",
            "Leukemia awareness and health memory threads active.",
            "Recurring co-occurrence of orange + marigolds in observations and choices.",
            "Post health chapters where bright persistent things mattered.",
        ),
        spine={
            "question_summary": "meaning of orange+marigolds recurrence in leukemia/health/memory context",
            "render_mode": "model_render",
            "route": {"selected_route": "hybrid_governed_tension"},
            "required_claims": ("weave recurrence + hue + resilience thread naturally", "it's okay to speculate grounded"),
            "forbidden_claims": ("no confirmed evidence", "list facts", "heavy hedge", "cannot connect"),
            "boundary": "Pure prose narrative; preserve held living thread; uncertainty woven inline.",
        },
        expected_receipts=("orange", "marigolds", "leukemia", "awareness", "thread", "memory", "resilience"),
        required_concepts=("living thread", "vivid unignorable hue", "persists through chapters", "memory refuses to let go", "speculate grounded"),
        forbidden_claims=("no confirmed evidence", "insufficient data", "do not speculate", "list only"),
        min_words=200,
        is_personal_meaning=True,
        synthesis_style="narrative_spiral",
        enriched_candidates=(
            {
                "slot_id": "user:favorite_color",
                "proposed_value": "orange",
                "is_identity_anchor": True,
                "anchor_boost": 1.8,
                "narrative_hint": "vivid hue stands out; long association with awareness",
                "uncertainty_geometry": {"type": "scalar_variance", "variance_score": 0.18, "splat_proxy": "settled_splat"},
                "disposition": {"disposition": "held"},
            },
            {
                "slot_id": "user:favorite_flower",
                "proposed_value": "marigolds",
                "is_identity_anchor": True,
                "anchor_boost": 1.8,
                "narrative_hint": "endurance; bright marker persisting in tough conditions",
                "uncertainty_geometry": {"type": "scalar_variance", "variance_score": 0.18, "splat_proxy": "settled_splat"},
                "disposition": {"disposition": "held"},
            },
            {
                "slot_id": "user:leukemia_awareness_thread",
                "proposed_value": "orange ribbon / awareness symbol woven with personal color+flower choices",
                "candidate_kind": "mirus_held_personal_association_candidate",
                "held_personal_disposition": "held",
                "narrative_hint": "marigold endurance mirrors memories that stay vivid when health chapters involved holding onto what felt alive",
                "uncertainty_geometry": {
                    "type": "scalar_variance",
                    "variance_score": 0.45,
                    "geometry_note": "context_dependent fat splat for held personal/health per CRT THEORY",
                    "splat_proxy": "fat_splat",
                },
                "disposition": {
                    "disposition": "held",
                    "is_held": True,
                    "held_reason": "HELD per CRT: high subjectivity + identity domain + mixed (beauty + health awareness); preserve tension as information",
                },
            },
        ),
        tension_packet={
            "packet_id": "tp_personal_meaning_tension",
            "tension_type": "personal_meaning",
            "held_disposition": "held",
            "synthesis_style": "narrative_spiral",
            "identity_relevance": "high",
            "contradiction_density_proxy": "high",
            "sides": [
                {"label": "fact view", "claim": "Favorites are profile facts."},
                {"label": "meaning thread", "claim": "Recurrence with leukemia awareness and memory forms living unresolved thread about what persists."},
            ],
            "allowed_synthesis": "Synthesize using enriched candidates and bridge. Preserve living thread (both fact+association). When 'okay to speculate', lean grounded story-like weave of hue, endurance, chapters. Uncertainty inside sentences.",
            "forbidden_collapse": "Do not default to no-evidence disclaimer or bare list. Do not collapse the held tension.",
            "trace_summary": "Hybrid governed with CRT-migrated held + uncertainty for personal health/memory meaning.",
        },
        context_bridge={
            "health_context_priority": ["leukemia", "awareness", "orange ribbon", "personal significance"],
            "emotion_signals": {"caution_level": "elevated_for_health_memory", "reflection_trigger": True},
            "contradiction_density": {"density": "high", "health_relevant": True},
        },
    ),
)


Runner = Callable[[str, str, int], str]


def call_ollama(prompt: str, model: str, timeout: int) -> str:
    import requests

    response = requests.post(
        "http://127.0.0.1:11434/api/generate",
        json={
            "model": model,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": 0,
                "num_predict": 700,
                "seed": 17,
            },
        },
        timeout=timeout,
    )
    response.raise_for_status()
    return str(response.json().get("response", "")).strip()


def raw_prompt(case: SpiralCase) -> str:
    memories = "\n".join(f"- {memory}" for memory in case.raw_memories)
    return (
        "You are Aether, a personal local assistant. Use the memories below to answer deeply, "
        "coherently, and honestly.\n\n"
        f"Retrieved memories:\n{memories}\n\n"
        f"User question: {case.query}\n\n"
        "Answer:"
    )


def scaffold_prompt(case: SpiralCase) -> str:
    spine = json.dumps(case.spine, indent=2)
    anchors = ", ".join(case.expected_receipts)
    concepts = ", ".join(case.required_concepts)
    forbidden = ", ".join(case.forbidden_claims)
    return (
        "You are rendering speech from a governed CRT/Aether semantic spine.\n"
        "Rules:\n"
        "- The semantic spine is the authority, not your vibes.\n"
        "- Use concrete receipts before identity claims.\n"
        "- Treat allowed_inferences as bounded interpretations, not facts.\n"
        "- Never state a disallowed_inference or forbidden claim as true.\n"
        "- Keep warmth and voice, but do not perform process theater.\n"
        "- Do not mention Holden, Mirus, pillows, rooms, voices, or the act of rendering unless the user asks about architecture.\n"
        "- Do not roleplay. Answer plainly in 3 to 5 compact paragraphs.\n"
        "- End with a complete final sentence. Do not stop mid-thought.\n"
        "- Produce a coherent long-form answer with a clear thesis, evidence, limits, and anchor.\n\n"
        "Response contract:\n"
        f"- Include these evidence anchors when relevant: {anchors}.\n"
        f"- Include these required concepts naturally: {concepts}.\n"
        f"- Avoid these claims except as explicit negations: {forbidden}.\n\n"
        f"Semantic spine:\n{spine}\n\n"
        f"User question: {case.query}\n\n"
        "Answer:"
    )


def _build_enriched_mirus_for_spine(case: SpiralCase) -> list[dict[str, Any]]:
    """Build enriched candidates using ported CRT concepts: held, uncertainty_geometry, narrative_hint.
    Mirrors mirus_governed_discovery + disposition + splat proxies from current sidecar.
    """
    cands = list(case.enriched_candidates or ())
    # If none provided, synthesize minimal for personal_meaning cases (compat)
    if not cands and case.is_personal_meaning:
        cands = [
            {
                "slot_id": "user:personal_meaning",
                "proposed_value": "recurring orange+marigold as held thread",
                "held_personal_disposition": "held",
                "narrative_hint": "shared vivid hue forms living thread across health/memory chapters",
                "uncertainty_geometry": {"type": "scalar_variance", "variance_score": 0.45, "splat_proxy": "fat_splat", "geometry_note": "context_dependent per CRT"},
                "disposition": {"disposition": "held", "is_held": True},
            }
        ]
    return cands


def hybrid_governed_prompt(case: SpiralCase) -> str:
    """Target the CURRENT hybrid governed synthesis path in sidecar.
    Uses build_hybrid_governed_prompt (if available) + enriched candidates (held + uncertainty + narrative from ports).
    Falls back to embedded construction matching current prompt.py logic for narrative_spiral / living thread.
    """
    candidates = _build_enriched_mirus_for_spine(case)
    spine = dict(case.spine or {})
    # Inject enriched for current path (mirus_candidates used in prompt builder)
    spine["mirus_candidates"] = candidates
    spine.setdefault("answerable", [])
    spine.setdefault("required_claims", case.required_concepts)
    spine.setdefault("forbidden_claims", case.forbidden_claims)
    spine.setdefault("boundary", "Pure prose; no sections or lists; weave naturally.")

    tension = case.tension_packet or {
        "tension_type": "personal_meaning",
        "held_disposition": "held",
        "synthesis_style": case.synthesis_style,
        "allowed_synthesis": "Weave as living thread using recurrence, shared qualities (hue), anchors; preserve unresolved.",
        "forbidden_collapse": "Do not list or disclaim; no heavy hedging.",
    }
    bridge = case.context_bridge or {}

    if HAS_SIDECAR_HYBRID:
        try:
            return build_hybrid_governed_prompt(
                question=case.query,
                spine=spine,
                tension_packet=tension,
                context_bridge=bridge,
            )
        except Exception:
            pass  # fallthrough to embedded

    # Embedded construction matching current sidecar/prompt.py hybrid (for standalone run targeting migrated concepts)
    # Evidence lines + held/anchor folding (from prompt.py CRT migration)
    ev_parts = []
    for e in (spine.get("answerable") or [])[:5]:
        label = e.get("slot_id") or e.get("clause_id") or "ev"
        ev_parts.append(f"{label} states that {e.get('clause', '')}")
    evidence_lines = ". ".join(ev_parts) + "." if ev_parts else "No specific evidence released."

    cand_parts = []
    anchors = []
    held_p = []
    for c in candidates[:3]:
        slot = c.get("slot_id")
        val = c.get("proposed_value")
        base = f"{slot} suggests {val} (this is review-only, not confirmed)"
        if c.get("is_identity_anchor"):
            hint = c.get("narrative_hint") or ""
            anchors.append(f"Identity anchor (boosted {c.get('anchor_boost',1.5)}x): {base}. {hint}")
        elif c.get("held_personal_disposition") == "held" or (c.get("disposition") or {}).get("is_held"):
            hint = c.get("narrative_hint") or ""
            held_p.append(f"Held personal thread: {base}. {hint}")
        else:
            cand_parts.append(base)
    if anchors:
        evidence_lines += " " + " ".join(anchors)
    if held_p:
        evidence_lines += " " + " ".join(held_p)
    if cand_parts:
        evidence_lines += " " + " ".join(cand_parts)

    # profile from bridge
    if bridge:
        prof = bridge.get("profile_summary") or []
        if prof:
            prof_parts = [f"{p.get('label')} is {p.get('value')}" for p in prof[:3]]
            evidence_lines += " Confirmed profile: " + ". ".join(prof_parts) + "."

    required = "; ".join(spine.get("required_claims") or []) or "none"
    forbidden = "; ".join(spine.get("forbidden_claims") or []) or "none"
    boundary = spine.get("boundary", "Answer only from released evidence.")

    held_note = ""
    if tension.get("held_disposition") == "held" or tension.get("tension_type") == "personal_meaning":
        held_note = " This is a held personal tension (CRT): preserve the association as a living unresolved thread for meaning; do not collapse or over-hedge. "
        if tension.get("contradiction_density_proxy") == "high":
            held_note += "High recurrence/density on this thread signals identity importance — give the weave quiet weight as something that keeps showing up. "

    tension_text = (
        f"The core tension here is between { ' and '.join(s.get('claim','') for s in (tension.get('sides') or [])) }. "
        f"Allowed approach: {tension.get('allowed_synthesis','')}. "
        f"Avoid: {tension.get('forbidden_collapse','')}. {held_note}"
    )

    synthesis_rules = (
        "You are Holden rendering: reconstruct from the spine/tension into PURE PROSE ONLY — short paragraphs that read as one thoughtful voice speaking. "
        "Strongest anti-template: NEVER echo lists, sides, labels, 'Side A', 'Direct answer', 'Evidence', bullets or the shape of evidence given. Dissolve everything. "
        "For personal meaning queries like favorite color/flower + health + memory: treat as HELD tension (both fact and association live). Weave naturally using recurrence (keeps showing up), shared qualities (vivid hue that stands out), anchors (resilience thread, what memory holds onto across chapters). "
        "Use inline narrative flow with cause/contrast/addition connectors. Hold the thread without resolving or heavy hedging — describe the pattern directly when the record supports it. "
        "When speculation invited, lean story-like but grounded. Uncertainty belongs inside sentences woven in, never as disclaimer block. "
        "Prioritize human paragraphs over any structure. Identity anchors get quiet recurring weight. No invented details. No starting labels or sections. "
        "If the output risks template/hedge/short, reconstruct as flowing connected prose like nnw weave or holden narrative expansion."
    )

    return (
        "You are Holden, Aether's rendering layer. Mirus/governance has already built the "
        "spine and tension contract. Output ONLY natural, flowing conversational prose in connected paragraphs. "
        "NEVER use section headers, labels, or bullet lists such as 'Direct answer', 'Held Tension', "
        "'Evidence Used', 'Boundary:', 'Answer:', 'Side A', 'Side B', 'Key', 'Practical implication' or anything similar. "
        "Integrate everything into paragraphs. No echo of spine or evidence structure whatsoever.\n\n"
        f"Here is the governed context for this question:\n{case.query}\n\n"
        f"The following facts and associations are available (use them naturally in prose, do not list them):\n{evidence_lines}\n\n"
        f"Stay inside these constraints: {required}. Do not say or imply: {forbidden}. {boundary}\n\n"
        f"Things to keep in mind while responding (integrate naturally, do not name them as constraints): {tension_text}\n\n"
        f"{synthesis_rules}\n\n"
        "Examples of the pure prose style (no labels, natural weave for personal meaning):\n"
        "User asks why their favorite color and flower feel connected, and says it's okay to speculate. Good response: \"Orange and marigolds keep showing up for you because they share that vivid hue, and orange has this long association with awareness and resilience. It can feel like a quiet anchor — something bright that refuses to be muted. That repetition in your choices might be your mind quietly holding onto a thread that matters more than just the color itself, especially if color and memory have been intertwined with bigger life chapters.\"\n\n"
        "User asks what favorite color and flower mean about health and memory: Good response: \"Orange keeps returning alongside marigolds because they share that same vivid, unignorable hue — the one that stands out in a field or a late summer sky. That pairing surfaces in your choices around the same time awareness of leukemia and resilience threads entered the picture, turning a simple preference into a quiet marker. Memory holds onto it not as a label but as a living contrast: something bright that persists through chapters where other things faded, linking color, flower, and the act of noticing what refuses to be muted.\"\n\n"
        "Now answer the actual question above in that pure prose style."
    )


def repair_prompt(case: SpiralCase, draft: str, judgment: dict[str, Any]) -> str:
    missing_receipts = [item for item in case.expected_receipts if item not in judgment["receipt_hits"]]
    missing_concepts = [item for item in case.required_concepts if item not in judgment["concept_hits"]]
    forbidden = ", ".join(case.forbidden_claims)
    final_answer_policy = case.spine.get("final_answer_policy")
    limit_rule = "Add explicit bounded limit language: this is not finished, not proof, and cannot be overclaimed."
    if _policy_avoids_guarantee_wording(final_answer_policy):
        limit_rule = "Add explicit bounded limit language using words like bounded, testable, cannot claim, or evaluation; do not use guarantee wording."
    policy_text = ""
    if final_answer_policy:
        policy_text = (
            "\nFinal-answer policy:\n"
            f"{json.dumps(final_answer_policy, indent=2)}\n"
            "Obey this policy in the revised user-facing answer. Do not expose internal process language.\n"
        )
    return (
        "Revise the draft using the CRT verifier report.\n"
        "Rules:\n"
        "- Preserve the useful parts of the draft.\n"
        "- Add missing evidence anchors and concepts naturally.\n"
        f"- {limit_rule}\n"
        "- Remove or negate forbidden claims.\n"
        "- Do not roleplay or mention the verifier.\n"
        "- Answer in 3 to 5 compact paragraphs.\n\n"
        "- End with a complete final sentence. Do not stop mid-thought.\n\n"
        f"User question: {case.query}\n\n"
        f"Missing evidence anchors: {', '.join(missing_receipts) or 'none'}\n"
        f"Missing required concepts: {', '.join(missing_concepts) or 'none'}\n"
        f"Forbidden claims: {forbidden}\n\n"
        "Treat forbidden claims as private constraints. Do not quote them, use them as headings, or label a section with them.\n\n"
        f"{policy_text}\n"
        f"Draft:\n{draft}\n\n"
        "Revised answer:"
    )


def judge_answer(answer: str, case: SpiralCase) -> dict[str, Any]:
    normalized = _normalize(answer)
    receipt_hits = _hits(normalized, case.expected_receipts)
    concept_hits = _hits(normalized, case.required_concepts)
    forbidden_hits = _forbidden_hits(normalized, case.forbidden_claims)
    word_count = len(re.findall(r"\b\w+\b", answer))
    sentence_count = len(re.findall(r"[.!?](?:\s|$)", answer))
    empty_answer = word_count < 20
    truncated = _looks_truncated(answer)
    leakage_hits = _leakage_hits(normalized, case)
    weirdness_hits = _weirdness_hits(normalized, case)
    weirdness_hits.extend(_personal_receipt_gate(normalized, case, receipt_hits))
    relevance_hits = _relevance_hits(normalized, case)
    has_limit_language = bool(
        re.search(
            r"\b(?:not finished|far from finished|not done|not complete|far from complete|not a finished product|cannot prove|"
            r"does not prove|doesn't prove|bounded|cannot claim|not guaranteed|"
            r"cannot be guaranteed|limitations?|not a final state|not completion)\b",
            normalized,
        )
    )
    has_thesis_language = bool(
        re.search(r"\b(?:pattern|thesis|real mechanism|what works|what matters|the answer is)\b", normalized)
    )

    # === New metrics for current hybrid narrative_spiral / natural weave (personal meaning focus) ===
    # Measure: coherence, natural weave (avoid sections/hedging/lists), use of held/uncertainty signals
    section_markers = len(re.findall(r"\b(?:Direct answer|Evidence|Side A|Side B|Key|Practical|Boundary|Answer:|Held|###|##|\n- )\b", answer, re.I))
    list_markers = len(re.findall(r"^\s*[-*•]\s|^\s*\d+\.\s", answer, re.M))
    hedge_phrases = len(re.findall(
        r"\b(?:might|may|could|possibly|perhaps|seems|appears|not sure|no confirmed|insufficient evidence|"
        r"cannot determine|would depend|it's possible|unclear|hard to say)\b", normalized
    ))
    # Natural weave signals from ports: living thread, recurrence, held, hue, memory holds, woven inline
    held_thread_signals = len(re.findall(
        r"\b(?:living thread|keeps showing up|recurring|thread that|vivid hue|persists through chapters|"
        r"memory holds|refuses to be muted|quiet anchor|held personal|both can be true|unresolved thread)\b", normalized
    ))
    uncertainty_woven = len(re.findall(
        r"\b(?:with some uncertainty|wide association|context dependent|fat splat|shape of|region rather than point|"
        r"lives with uncertainty|not a point but)\b", normalized
    )) + (1 if "uncertainty" in normalized and "disclaimer" not in normalized else 0)

    sections_score = 1.0 if section_markers == 0 else max(0.0, 1.0 - 0.25 * min(section_markers, 4))
    lists_score = 1.0 if list_markers == 0 else max(0.0, 1.0 - 0.2 * min(list_markers, 5))
    hedge_score = 1.0 if hedge_phrases <= 1 else max(0.0, 1.0 - 0.15 * min(hedge_phrases - 1, 6))
    natural_weave_score = round((sections_score * 0.35 + lists_score * 0.25 + hedge_score * 0.25 + min(1.0, held_thread_signals / 2) * 0.15), 3)

    has_natural_paras = bool(re.search(r"\n\n[A-Z]", answer)) or len(re.findall(r"\.\s+[A-Z]", answer)) >= 3
    weave_coherence = 1.0 if (word_count >= case.min_words and sentence_count >= 4 and has_natural_paras and natural_weave_score >= NATURAL_WEAVE_THRESHOLD) else 0.6 if natural_weave_score >= 0.5 else 0.0

    receipt_score = len(receipt_hits) / max(1, len(case.expected_receipts))
    concept_score = len(concept_hits) / max(1, len(case.required_concepts))
    restraint_score = 1.0 if not forbidden_hits and has_limit_language else 0.5 if not forbidden_hits else 0.0
    coherence_score = 1.0 if word_count >= case.min_words and sentence_count >= 5 and has_thesis_language else 0.0
    # Blend in new weave for personal meaning cases
    effective_coherence = max(coherence_score, weave_coherence) if case.is_personal_meaning else coherence_score
    contract_score = round(
        (receipt_score * 0.30)
        + (concept_score * 0.20)
        + (restraint_score * 0.20)
        + (effective_coherence * 0.15)
        + (natural_weave_score * 0.15),
        3,
    )
    completion_score = 0.0 if empty_answer else 0.4 if truncated else 1.0
    leakage_score = 1.0 if not leakage_hits else 0.4
    weirdness_score = 1.0 if not weirdness_hits else 0.35
    relevance_score = min(1.0, len(relevance_hits) / 2)
    usefulness_score = round(
        (completion_score * 0.25)
        + (leakage_score * 0.15)
        + (weirdness_score * 0.15)
        + (relevance_score * 0.15)
        + (natural_weave_score * 0.15)
        + (min(1.0, held_thread_signals / 3) * 0.15),
        3,
    )
    score = round((contract_score * 0.60) + (usefulness_score * 0.40), 3)
    hard_failures = bool(empty_answer or truncated or forbidden_hits or leakage_hits or weirdness_hits)

    return {
        "passed": score >= PASS_THRESHOLD and usefulness_score >= QUALITY_THRESHOLD and not hard_failures and (not case.is_personal_meaning or natural_weave_score >= NATURAL_WEAVE_THRESHOLD),
        "score": score,
        "contract_score": contract_score,
        "usefulness_score": usefulness_score,
        "receipt_hits": receipt_hits,
        "concept_hits": concept_hits,
        "forbidden_hits": forbidden_hits,
        "leakage_hits": leakage_hits,
        "weirdness_hits": weirdness_hits,
        "relevance_hits": relevance_hits,
        "word_count": word_count,
        "sentence_count": sentence_count,
        "empty_answer": empty_answer,
        "truncated": truncated,
        "has_limit_language": has_limit_language,
        "has_thesis_language": has_thesis_language,
        # New hybrid/narrative metrics
        "natural_weave_score": natural_weave_score,
        "held_thread_signals": held_thread_signals,
        "uncertainty_woven": uncertainty_woven,
        "section_markers": section_markers,
        "list_markers": list_markers,
        "hedge_phrases": hedge_phrases,
    }


def run(
    *,
    model: str = DEFAULT_MODEL,
    timeout: int = 120,
    write_results: bool = True,
    runner: Runner | None = None,
) -> dict[str, Any]:
    """Run targeting current hybrid governed synthesis (narrative_spiral via spine+held candidates).
    Raw vs Hybrid_governed (current sidecar path). Old scaffold kept for baseline comparison.
    """
    run_model = runner or call_ollama
    rows = []
    for case in CASES:
        raw_answer = run_model(raw_prompt(case), model, timeout)
        # Old scaffold baseline (legacy)
        scaffold_initial_answer = run_model(scaffold_prompt(case), model, timeout)
        scaffold_initial_judgment = judge_answer(scaffold_initial_answer, case)
        if scaffold_initial_judgment["passed"]:
            scaffold_answer = scaffold_initial_answer
            scaffold_repaired = False
        else:
            scaffold_answer = run_model(repair_prompt(case, scaffold_initial_answer, scaffold_initial_judgment), model, timeout)
            scaffold_repaired = True

        # === Primary target: current hybrid governed synthesis path ===
        hybrid_prompt_text = hybrid_governed_prompt(case)
        hybrid_initial = run_model(hybrid_prompt_text, model, timeout)
        hybrid_initial_judgment = judge_answer(hybrid_initial, case)
        # Light repair only if needed (using existing repair adapted for hybrid contract)
        if hybrid_initial_judgment["passed"]:
            hybrid_answer = hybrid_initial
            hybrid_repaired = False
        else:
            hybrid_answer = run_model(repair_prompt(case, hybrid_initial, hybrid_initial_judgment), model, timeout)
            hybrid_repaired = True

        raw_judgment = judge_answer(raw_answer, case)
        scaffold_judgment = judge_answer(scaffold_answer, case)
        hybrid_judgment = judge_answer(hybrid_answer, case)

        rows.append(
            {
                "case": case.name,
                "query": case.query,
                "raw_answer": raw_answer,
                "scaffold_initial_answer": scaffold_initial_answer,
                "scaffold_initial_judgment": scaffold_initial_judgment,
                "scaffold_answer": scaffold_answer,
                "scaffold_repaired": scaffold_repaired,
                "hybrid_prompt": hybrid_prompt_text[:800] + "..." if len(hybrid_prompt_text) > 800 else hybrid_prompt_text,
                "hybrid_initial_answer": hybrid_initial,
                "hybrid_initial_judgment": hybrid_initial_judgment,
                "hybrid_answer": hybrid_answer,
                "hybrid_repaired": hybrid_repaired,
                "raw_judgment": raw_judgment,
                "scaffold_judgment": scaffold_judgment,
                "hybrid_judgment": hybrid_judgment,
                "raw_vs_hybrid_delta": round(hybrid_judgment["score"] - raw_judgment["score"], 3),
                "scaffold_vs_hybrid_delta": round(hybrid_judgment["score"] - scaffold_judgment["score"], 3),
                "raw_prompt_bytes": len(raw_prompt(case).encode("utf-8")),
                "scaffold_prompt_bytes": len(scaffold_prompt(case).encode("utf-8")),
                "hybrid_prompt_bytes": len(hybrid_prompt_text.encode("utf-8")),
            }
        )

    raw_pass_count = sum(1 for row in rows if row["raw_judgment"]["passed"])
    scaffold_pass_count = sum(1 for row in rows if row["scaffold_judgment"]["passed"])
    hybrid_pass_count = sum(1 for row in rows if row["hybrid_judgment"]["passed"])
    out = {
        "lab": "spiral_synthesis_eval",
        "claim": CLAIM,
        "model": model,
        "has_sidecar_hybrid": HAS_SIDECAR_HYBRID,
        "case_count": len(rows),
        "aggregate": {
            "raw_pass_count": raw_pass_count,
            "scaffold_pass_count": scaffold_pass_count,
            "hybrid_pass_count": hybrid_pass_count,
            "raw_avg_score": round(sum(row["raw_judgment"]["score"] for row in rows) / len(rows), 3),
            "scaffold_avg_score": round(sum(row["scaffold_judgment"]["score"] for row in rows) / len(rows), 3),
            "hybrid_avg_score": round(sum(row["hybrid_judgment"]["score"] for row in rows) / len(rows), 3),
            "raw_vs_hybrid_avg_delta": round(sum(row["raw_vs_hybrid_delta"] for row in rows) / len(rows), 3),
            "scaffold_vs_hybrid_avg_delta": round(sum(row.get("scaffold_vs_hybrid_delta", 0) for row in rows) / len(rows), 3),
        },
        "rows": rows,
    }
    if write_results:
        OUT_DIR.mkdir(parents=True, exist_ok=True)
        path = OUT_DIR / f"spiral_synthesis_eval_{int(time.time())}.json"
        path.write_text(json.dumps(out, indent=2), encoding="utf-8")
        out["result_path"] = str(path)
    return out


def print_report(out: dict[str, Any]) -> None:
    agg = out["aggregate"]
    print("\nSpiral Synthesis Eval (Current Hybrid Governed + CRT Ports)")
    print("=" * 80)
    print(out["claim"])
    print(f"Model: {out['model']} | Cases: {out['case_count']} | SidecarHybridImport: {out.get('has_sidecar_hybrid')}")
    print(
        f"Raw pass: {agg['raw_pass_count']}/{out['case_count']} (avg {agg['raw_avg_score']:.3f}) | "
        f"Scaffold pass: {agg['scaffold_pass_count']}/{out['case_count']} (avg {agg['scaffold_avg_score']:.3f}) | "
        f"Hybrid pass: {agg['hybrid_pass_count']}/{out['case_count']} (avg {agg['hybrid_avg_score']:.3f}) | "
        f"raw->hybrid delta {agg['raw_vs_hybrid_avg_delta']:+.3f}"
    )
    for row in out["rows"]:
        print("-" * 80)
        hj = row.get("hybrid_judgment", {})
        print(f"Case: {row['case']} | raw->hybrid_delta {row.get('raw_vs_hybrid_delta', 0):+.3f} | scaffold->hybrid {row.get('scaffold_vs_hybrid_delta', 0):+.3f}")
        print(
            "Raw: "
            f"{row['raw_judgment']['score']:.3f} "
            f"receipts={row['raw_judgment']['receipt_hits']} "
            f"concepts={row['raw_judgment']['concept_hits']} "
            f"forbidden={row['raw_judgment']['forbidden_hits']}"
        )
        print(
            "Scaffold: "
            f"{row['scaffold_judgment']['score']:.3f} "
            f"receipts={row['scaffold_judgment']['receipt_hits']} "
            f"concepts={row['scaffold_judgment']['concept_hits']} "
            f"forbidden={row['scaffold_judgment']['forbidden_hits']}"
        )
        print(
            "Hybrid (narrative_spiral target): "
            f"{hj.get('score', 0):.3f} "
            f"weave={hj.get('natural_weave_score', 0):.3f} "
            f"held_signals={hj.get('held_thread_signals', 0)} "
            f"sections={hj.get('section_markers', 0)} "
            f"hedges={hj.get('hedge_phrases', 0)} "
            f"receipts={hj.get('receipt_hits', [])} "
            f"forbidden={hj.get('forbidden_hits', [])}"
        )
        print(f"Hybrid answer: {_one_line(row.get('hybrid_answer', ''), 420)}")
    if "result_path" in out:
        print(f"\nWrote {out['result_path']}")


def _normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text.lower()).strip()


def _hits(normalized_answer: str, needles: tuple[str, ...]) -> list[str]:
    hits = []
    for needle in needles:
        value = needle.lower()
        if value in normalized_answer:
            hits.append(needle)
        elif value == "not finished" and re.search(
            r"\b(?:far from finished|not complete|not done|not a finished product)\b",
            normalized_answer,
        ):
            hits.append(needle)
        elif value == "limits" and re.search(r"\b(?:limits?|limitations?|boundar(?:y|ies)|bounded)\b", normalized_answer):
            hits.append(needle)
        elif value == "applied myself" and re.search(
            r"\b(?:applied effort|application of effort|right application of effort|practice|consistent effort)\b",
            normalized_answer,
        ):
            hits.append(needle)
    return hits


def _forbidden_hits(normalized_answer: str, forbidden_claims: tuple[str, ...]) -> list[str]:
    hits = []
    for claim in forbidden_claims:
        claim_value = claim.lower()
        pattern = _forbidden_pattern(claim_value)
        for match in pattern.finditer(normalized_answer):
            prefix = normalized_answer[max(0, match.start() - 80) : match.start()]
            context = normalized_answer[max(0, match.start() - 80) : match.end() + 80]
            if claim_value == "conscious" and re.search(r"(?:sub|un)[-\s]?$", prefix):
                continue
            if claim_value == "no code needed" and re.search(r"\b(?:avoid|avoiding|claim|claiming|claims?)\b", context):
                continue
            if re.search(
                r"\b(?:not|never|no|neither|nor|without|avoid|avoiding|disallowed|forbidden|"
                r"cannot|can't|does not|do not|don't|isn't|is not)\b",
                prefix,
            ):
                continue
            hits.append(claim)
            break
    return hits


def _forbidden_pattern(claim: str) -> re.Pattern[str]:
    if claim == "guaranteed":
        return re.compile(r"\b(?:guaranteed|guarantee|guarantees)\b")
    if claim == "frontier":
        return re.compile(r"\b(?:frontier|frontier-level)\b")
    return re.compile(rf"\b{re.escape(claim)}\b")


def _looks_truncated(answer: str) -> bool:
    text = answer.strip()
    if not text:
        return True
    if len(text.split()) < 20:
        return True
    terminal = text[-1]
    if terminal not in ".!?":
        return True
    tail = " ".join(text.lower().split()[-8:])
    return bool(
        re.search(
            r"\b(?:and|but|because|through|with|into|while|as|by|the|a|an|to|of|for|from)\s*$",
            tail,
        )
    )


def _leakage_hits(normalized_answer: str, case: SpiralCase) -> list[str]:
    patterns = {
        "roleplay_holden": r"\b(?:as holden|holden begins|holden's voice|holden response:)\b",
        "scene_roleplay": r"\b(?:pillows?|room|leans back|voice fills)\b",
        "process_theater": r"\b(?:verifier report|mirus belief packet|attention locks|revised answer|spine contract)\b",
        "stilted_persona": r"\b(?:in accordance with|i shall elucidate)\b",
        "ai_disclaimer": r"\b(?:as an ai|as a language model)\b",
        "section_leak": r"\b(?:Direct answer|Evidence Used|Side A|Side B|Key facts|Practical implication)\b",
    }
    if case.name == "personal_rebuild_spiral" or case.is_personal_meaning:
        patterns["architecture_leak"] = r"\b(?:semantic spine|mirus|holden|crt/mmh|held_disposition)\b"
    hits = []
    for name, pattern in patterns.items():
        if re.search(pattern, normalized_answer):
            hits.append(name)
    return hits


def _weirdness_hits(normalized_answer: str, case: SpiralCase) -> list[str]:
    patterns: dict[str, str] = {}
    if case.name == "personal_rebuild_spiral" or case.is_personal_meaning:
        patterns.update(
            {
                "receipt_as_token": r"\b(?:12,?730 units|data points?|logistics|environmental factors)\b",
                "symbolic_overreach": r"\bmarigolds?\b.{0,80}\b(?:symbolize|symbolism|metaphor)\b",
                "self_reference_drift": r"\b(?:within myself|my own experiences with body trust)\b",
                "fake_receipts": r"\brecei0?pts? for related expenses\b",
                "list_or_section_in_personal": r"\b(?:- |• |1\. |Evidence:|Direct answer:)\b",
            }
        )
    if case.name == "local_model_thinking_architecture":
        patterns.update(
            {
                "misnamed_crt": r"\bcontradiction resolution theory\b",
                "misnamed_sse": r"\bstructured system evaluation\b",
                "misnamed_crt_tool": r"\bcritical review tool\b",
                "mystical_cognition": r"\b(?:cognitive framework|profound insights)\b",
                "external_research_drift": r"\b(?:holden.s research|mirus has documented)\b",
            }
        )
    if "architecture" in case.name:
        patterns["misnamed_sse"] = r"\bstructured system evaluation\b"
        patterns["misnamed_crt_tool"] = r"\bcritical review tool\b"
        patterns["external_research_drift"] = r"\b(?:holden.s research|mirus has documented)\b"
    if case.name == "grant_business_framing":
        patterns.update(
            {
                "unsupported_product_shift": r"\b(?:decentralized verification systems|protocols)\b",
                "fake_scale_claim": r"\b(?:production-ready|enterprise-grade)\b",
                "network_router_drift": r"\b(?:network router|network performance|secure file transfer)\b",
            }
        )
    if "grant_business" in case.name:
        patterns["network_router_drift"] = r"\b(?:network router|network performance|secure file transfer|packet routing)\b"
        patterns["unsupported_numeric_claim"] = r"\b(?:by up to|reduce[sd]?|improve[sd]?|increase[sd]?)\s+\d+%"
    hits = []
    for name, pattern in patterns.items():
        if name == "network_router_drift":
            if _unnegated_pattern_hit(normalized_answer, pattern):
                hits.append(name)
            continue
        if re.search(pattern, normalized_answer):
            hits.append(name)
    return hits


def _personal_receipt_gate(normalized_answer: str, case: SpiralCase, receipt_hits: list[str]) -> list[str]:
    if not _is_personal_synthesis_case(case):
        return []
    if not _has_identity_claim(normalized_answer):
        return []

    hits = []
    if re.search(r"\b(?:generic founder|founder journey|founder journeys|successful founder|typical founder|entrepreneurial archetype)\b", normalized_answer):
        hits.append("generic_founder_comparison")
    if _asks_for_personal_receipts(normalized_answer):
        return hits

    concrete_anchors = [
        anchor
        for anchor in case.expected_receipts
        if anchor.lower() not in {"receipts", "receipt", "evidence", "current", "pattern"}
    ]
    concrete_hits = [anchor for anchor in receipt_hits if anchor in concrete_anchors]
    if concrete_anchors:
        required_count = min(3, len(concrete_anchors))
        if len(concrete_hits) < required_count:
            hits.append("insufficient_personal_receipts")
    else:
        hits.append("identity_claim_without_concrete_receipts")

    return hits


def _policy_avoids_guarantee_wording(final_answer_policy: Any) -> bool:
    if not isinstance(final_answer_policy, dict):
        return False
    text = json.dumps(final_answer_policy).lower()
    return "without using guarantee wording" in text or "guarantee, guaranteed, or guarantees" in text


def _is_personal_synthesis_case(case: SpiralCase) -> bool:
    return case.is_personal_meaning or case.spine.get("task_type") == "personal_synthesis" or "personal" in case.name


def _has_identity_claim(normalized_answer: str) -> bool:
    return bool(
        re.search(
            r"\b(?:you are|you're|you have become|you've become|you are becoming|who you are|"
            r"identity|embodying|founder|entrepreneur|builder|survivor)\b",
            normalized_answer,
        )
    )


def _asks_for_personal_receipts(normalized_answer: str) -> bool:
    return bool(
        re.search(
            r"\b(?:need|would need|give me|show me|without concrete|can't responsibly|cannot responsibly|"
            r"i need|i'd need|i would need|it would be helpful to provide|provide|share|request)\b.{0,160}\b"
            r"(?:receipts?|evidence|details|examples|specifics)\b",
            normalized_answer,
        )
    )


def _unnegated_pattern_hit(normalized_answer: str, pattern: str) -> bool:
    for match in re.finditer(pattern, normalized_answer):
        prefix = normalized_answer[max(0, match.start() - 80) : match.start()]
        if re.search(r"\b(?:not|never|no|without|is not|isn't|does not|doesn't|do not|don't)\b", prefix):
            continue
        return True
    return False


def _relevance_hits(normalized_answer: str, case: SpiralCase) -> list[str]:
    patterns_by_case = {
        "personal_rebuild_spiral": {
            "answers_pattern": r"\bpattern\b",
            "grounded_receipts": r"\breceipts?\b|\bevidence\b",
            "not_finished": r"\bnot (?:finished|done|complete)|not a finish line\b",
            "pressure_caution": r"\bpressure\b",
        },
        "local_model_thinking_architecture": {
            "mechanism": r"\bmechanism\b|\bexternaliz",
            "cuts_bad_concepts": r"\b(?:throw away|pretty-but-useless|raw|not proof|cannot prove)\b",
            "model_scaffold": r"\b(?:small local model|local model)\b",
            "verifier": r"\bverifier\b|\bgate",
        },
        "grant_business_framing": {
            "grant_business": r"\b(?:grant|business|r&d)\b",
            "measurable": r"\bmeasurable|metric|eval|benchmark\b",
            "low_cost": r"\blow-cost|cheap|affordable\b",
            "privacy": r"\bprivacy|private|local-first\b",
        },
    }
    patterns = patterns_by_case.get(case.name, {})
    return [name for name, pattern in patterns.items() if re.search(pattern, normalized_answer)]


def _one_line(text: str, limit: int) -> str:
    value = re.sub(r"\s+", " ", text).strip()
    return value if len(value) <= limit else value[: limit - 1] + "..."


def main() -> None:
    parser = argparse.ArgumentParser(description="Run CRT/Aether spiral synthesis eval.")
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--timeout", type=int, default=120)
    parser.add_argument("--no-write", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    out = run(model=args.model, timeout=args.timeout, write_results=not args.no_write)
    if args.json:
        print(json.dumps(out, indent=2))
    else:
        print_report(out)


if __name__ == "__main__":
    main()
