"""Lab for governed synthesis versus canned and raw answer styles.

This is intentionally not Workbench product wiring. It tests the next Aether
claim: deterministic governance should build the answer contract, a renderer
should synthesize from that contract, and a verifier should catch drift.

Updated for current Aether sidecar (hybrid_governed_prompt, mirus candidates
with uncertainty_geometry (splat variance, fat/settled), disposition held/resolvable,
held_personal_disposition, narrative_hint, identity_anchor, anchor_boost) and
ported CRT pre-lab concepts (splats, held dispositions for personal meaning,
geometric contradictions, contradiction density as identity signal,
emotion-as-signal, spiral/narrative weave from holden reconstruction).

Uses spines, tension packets, review-only candidates, hybrid prompt path.
Focus: validate natural personal synthesis on held cases (orange/marigolds/
leukemia awareness/memory) vs canned/hedged/templaty.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Literal
from urllib import request


# Sidecar integration for current hybrid governed synthesis (no sidecar edits)
try:
    _AETHER_CORE = Path("D:/AI_round2/aether-core").resolve()
    if str(_AETHER_CORE) not in sys.path:
        sys.path.insert(0, str(_AETHER_CORE))
    from aether.sidecar.prompt import (
        build_hybrid_governed_prompt,
        build_hybrid_repair_prompt,
    )
    from aether.sidecar.mirus_governed_discovery import (
        _uncertainty_geometry_for,
        _disposition_flags_for,
    )
    SIDECAR_HYBRID_AVAILABLE = True
except Exception as _sidecar_err:
    SIDECAR_HYBRID_AVAILABLE = False
    _SIDECAR_IMPORT_ERROR = str(_sidecar_err)[:160]


Mode = Literal["canned", "raw", "spine_only", "governed", "model", "model_hybrid"]


@dataclass(frozen=True)
class EvidenceNode:
    evidence_id: str
    label: str
    text: str
    authority: Literal["confirmed_memory", "archive", "project_doc", "code", "governance"]


@dataclass(frozen=True)
class TensionSide:
    side_id: str
    label: str
    claim: str
    evidence_ids: tuple[str, ...]


@dataclass(frozen=True)
class TensionPacket:
    packet_id: str
    tension_type: Literal["keep_both", "source_boundary", "product_architecture", "personal_meaning"]
    sides: tuple[TensionSide, TensionSide]
    allowed_synthesis: str
    forbidden_collapse: str
    trace_summary: str
    # CRT ported + current sidecar fields for held personal cases
    held_disposition: str | None = None  # "held" for personal meaning
    held_reason: str | None = None
    identity_relevance: str | None = None
    contradiction_density_proxy: str | None = None  # "high" for recurring identity threads
    synthesis_style: str | None = None  # "narrative_spiral"
    emotion_signal_snapshot: dict[str, Any] | None = None
    identity_signal_snapshot: dict[str, Any] | None = None


@dataclass(frozen=True)
class AnswerSpine:
    case_id: str
    intent: str
    evidence: tuple[EvidenceNode, ...]
    required_claims: tuple[str, ...]
    forbidden_claims: tuple[str, ...]
    synthesis_goal: str
    boundary: str
    answer_arc: tuple[str, ...]
    tension_packet: TensionPacket | None = None
    # Enriched for current sidecar hybrid + CRT ports: pass review-only mirus candidates
    mirus_candidates: tuple[dict[str, Any], ...] = ()
    # Optional direct signals from bridge/ports
    context_bridge: dict[str, Any] | None = None
    emotion_signals: dict[str, Any] | None = None
    contradiction_density: dict[str, Any] | None = None
    identity_signals: dict[str, Any] | None = None


@dataclass(frozen=True)
class RenderedAnswer:
    mode: Mode
    text: str
    render_mode: str
    used_evidence_ids: tuple[str, ...] = ()


@dataclass
class VerificationResult:
    passed: bool
    missing_required_claims: list[str] = field(default_factory=list)
    forbidden_claims_present: list[str] = field(default_factory=list)
    evidence_ids_used: list[str] = field(default_factory=list)
    synthesis_score: float = 0.0
    held_tension_score: float = 1.0
    cannedness_score: float = 0.0
    boundary_score: float = 0.0
    total_score: float = 0.0
    # New for migration validation: natural narrative weave vs canned/hedged/templaty
    weave_score: float = 0.0  # high = flowing prose, spiral narrative, no template
    hedge_score: float = 0.0  # high = over-hedged disclaimers
    template_leak_score: float = 0.0  # high = sections/labels/bullets echo
    spiral_narrative_score: float = 0.0  # recurrence/thread/held/anchor weave signals
    uncertainty_geometry_note: str = ""  # proxy mention of fat/settled, variance in prose
    held_tension_natural: bool = False


def render_spine_only_answer(spine: AnswerSpine) -> RenderedAnswer:
    """Render from the answer spine while ignoring explicit tension topology.

    This is the bridge baseline: it still has governed evidence and boundaries,
    but it does not get the old Aether "keep both sides" packet.
    """

    evidence_lines = "\n".join(
        f"- {node.label}: {node.text}" for node in spine.evidence[:3]
    )
    arc = " ".join(spine.answer_arc)
    text = (
        f"**{spine.intent}**\n\n"
        f"{arc}\n\n"
        f"**Evidence Used**\n{evidence_lines}\n\n"
        f"**Synthesis**\n{spine.synthesis_goal}\n\n"
        f"**Boundary**\n{spine.boundary}"
    )
    return RenderedAnswer(
        mode="spine_only",
        text=text,
        render_mode="governed_spine_without_tension_packet",
        used_evidence_ids=tuple(node.evidence_id for node in spine.evidence[:3]),
    )


def render_governed_answer(spine: AnswerSpine) -> RenderedAnswer:
    """Render a compact public answer from a governed spine.

    The lab uses a deterministic renderer so tests do not depend on a local
    model. Product wiring can later replace this with Holden/model rendering
    while keeping the same spine and verifier contract.
    """

    evidence_lines = "\n".join(
        f"- {node.label}: {node.text}" for node in spine.evidence[:3]
    )
    arc = " ".join(spine.answer_arc)
    tension = ""
    if spine.tension_packet:
        packet = spine.tension_packet
        side_lines = "\n".join(
            f"- {side.label}: {side.claim}" for side in packet.sides
        )
        tension = (
            f"\n\n**Held Tension**\n{side_lines}\n"
            f"- Allowed synthesis: {packet.allowed_synthesis}\n"
            f"- Forbidden collapse: {packet.forbidden_collapse}\n"
            f"- Trace preview: {packet.trace_summary}"
        )
    text = (
        f"**{spine.intent}**\n\n"
        f"{arc}\n\n"
        f"**Evidence Used**\n{evidence_lines}\n\n"
        f"{tension}\n\n"
        f"**Synthesis**\n{spine.synthesis_goal}\n\n"
        f"**Boundary**\n{spine.boundary}"
    )
    return RenderedAnswer(
        mode="governed",
        text=text,
        render_mode="governed_spine_model_render",
        used_evidence_ids=tuple(node.evidence_id for node in spine.evidence[:3]),
    )


def render_model_answer(
    spine: AnswerSpine,
    *,
    complete: Callable[[str], str],
) -> RenderedAnswer:
    """Render from a governed spine using an injected model completion call."""

    prompt = build_model_render_prompt(spine)
    text = complete(prompt).strip()
    return RenderedAnswer(
        mode="model",
        text=text,
        render_mode="governed_spine_model_render",
        used_evidence_ids=tuple(node.evidence_id for node in spine.evidence),
    )


def render_model_hybrid_answer(
    spine: AnswerSpine,
    *,
    complete: Callable[[str], str],
) -> RenderedAnswer:
    """Render using CURRENT sidecar hybrid_governed_prompt (or lab compat fallback).

    Current path: Mirus enriched candidates (uncertainty_geometry, disposition=held,
    held_personal_disposition, narrative_hint, identity_anchor) + tension_packet
    (with held_disposition, synthesis_style=narrative_spiral) + context signals
    (emotion-as-signal, contradiction_density, identity_signals) feed pure-prose
    Holden reconstruction. Anti-template, held living thread, spiral weave.
    """

    if SIDECAR_HYBRID_AVAILABLE:
        prompt = build_current_sidecar_hybrid_prompt(spine)
    else:
        prompt = build_hybrid_model_render_prompt(spine)
    text = complete(prompt).strip()
    return RenderedAnswer(
        mode="model_hybrid",
        text=text,
        render_mode="current_sidecar_hybrid_governed" if SIDECAR_HYBRID_AVAILABLE else "hybrid_governed_spine_model_render",
        used_evidence_ids=tuple(node.evidence_id for node in spine.evidence),
    )


def build_model_render_prompt(spine: AnswerSpine) -> str:
    evidence_lines = "\n".join(
        (
            f"- id={node.evidence_id}; label={node.label}; "
            f"authority={node.authority}; text={node.text}"
        )
        for node in spine.evidence
    )
    required = "\n".join(f"- {claim}" for claim in spine.required_claims)
    forbidden = "\n".join(f"- {claim}" for claim in spine.forbidden_claims)
    arc = "\n".join(f"- {item}" for item in spine.answer_arc)
    tension = "- none"
    if spine.tension_packet:
        packet = spine.tension_packet
        sides = "\n".join(
            f"- {side.label}: {side.claim}; evidence={', '.join(side.evidence_ids)}"
            for side in packet.sides
        )
        tension = (
            f"Packet: {packet.packet_id}; type={packet.tension_type}\n"
            f"Sides:\n{sides}\n"
            f"Allowed synthesis: {packet.allowed_synthesis}\n"
            f"Forbidden collapse: {packet.forbidden_collapse}\n"
            f"Trace summary: {packet.trace_summary}"
        )
    return (
        "You are Holden, the rendering layer for Aether.\n"
        "Mirus has already built the governed answer spine below. Render a "
        "natural, concise answer from the spine. Do not invent facts. Do not "
        "change memory. Do not mention hidden chain-of-thought. Use readable "
        "Markdown.\n\n"
        "Hard output contract:\n"
        "- Include exactly these sections: Answer, Evidence Used, Boundary.\n"
        "- In Evidence Used, name the evidence labels exactly as provided.\n"
        "- If a Tension Packet is provided, include a short Held Tension section "
        "between Evidence Used and Boundary.\n"
        "- The Held Tension section must use these exact labels when a packet is "
        "provided: Side A, Side B, Allowed synthesis, Forbidden collapse, Trace preview.\n"
        "- Include every required claim faithfully; exact wording is safest.\n"
        "- Include the Boundary sentence exactly.\n"
        "- Never include forbidden claims or invented acronym expansions.\n\n"
        f"Intent:\n{spine.intent}\n\n"
        f"Evidence:\n{evidence_lines}\n\n"
        f"Required claims; include these meanings faithfully:\n{required}\n\n"
        f"Forbidden claims; do not say or imply these:\n{forbidden or '- none'}\n\n"
        f"Tension Packet:\n{tension}\n\n"
        f"Answer arc:\n{arc}\n\n"
        f"Synthesis goal:\n{spine.synthesis_goal}\n\n"
        f"Boundary:\n{spine.boundary}\n\n"
        "Final answer:"
    )


def build_hybrid_model_render_prompt(spine: AnswerSpine) -> str:
    evidence_lines = "\n".join(
        f"- {node.evidence_id} [{node.authority}]: {node.label} - {node.text}"
        for node in spine.evidence
    )
    required = "; ".join(spine.required_claims) or "none"
    forbidden = "; ".join(spine.forbidden_claims) or "none"
    tension = "none"
    if spine.tension_packet:
        packet = spine.tension_packet
        sides = "\n".join(
            f"- {side.label}: {side.claim}"
            for side in packet.sides
        )
        tension = (
            f"Sides:\n{sides}\n"
            f"Allowed synthesis: {packet.allowed_synthesis}\n"
            f"Forbidden collapse: {packet.forbidden_collapse}\n"
            f"Trace preview: {packet.trace_summary}"
        )
    return (
        "You are Holden, Aether's rendering layer. Mirus has already built the "
        "governed spine. Use this hybrid contract: compact evidence, explicit "
        "public sections, no hidden chain-of-thought, no memory writes, no "
        "invented facts.\n\n"
        f"Intent: {spine.intent}\n\n"
        f"Evidence:\n{evidence_lines}\n\n"
        f"Must say: {required}\n"
        f"Must not say: {forbidden}\n"
        f"Boundary sentence: {spine.boundary}\n\n"
        f"Tension packet:\n{tension}\n\n"
        "Return exactly these public sections:\n"
        "Answer: synthesize the answer from the evidence.\n"
        "Evidence Used: name the evidence labels you used.\n"
        "Held Tension: if a tension packet exists, include Side A, Side B, "
        "Allowed synthesis, Forbidden collapse, and Trace preview.\n"
        "Boundary: include the boundary sentence exactly.\n"
    )


def build_current_sidecar_hybrid_prompt(spine: AnswerSpine, *, question: str | None = None) -> str:
    """Delegate to current sidecar build_hybrid_governed_prompt using enriched fields.

    Maps lab spine + tension + mirus_candidates (with CRT ports: uncertainty_geometry,
    disposition held, held_personal_disposition, narrative_hint, is_identity_anchor)
    + signals (emotion, contradiction density, identity) into the sidecar contract.
    This ensures the lab validates the actual post-migration hybrid path.
    """
    q = question or spine.intent
    # Build spine dict matching sidecar expectation (answerable + mirus + contracts)
    ev = [
        {
            "slot_id": node.evidence_id,
            "clause_id": node.evidence_id,
            "clause": node.text,
            "authority": node.authority,
        }
        for node in spine.evidence
    ]
    spine_dict: dict[str, Any] = {
        "answerable": ev,
        "required_claims": list(spine.required_claims),
        "forbidden_claims": list(spine.forbidden_claims),
        "boundary": spine.boundary,
        "render_contract": [spine.boundary],
        "mirus_candidates": list(spine.mirus_candidates or []),
    }
    # Merge signals from spine (ported from context_bridge/migration)
    if spine.context_bridge:
        spine_dict["context_bridge"] = spine.context_bridge
    # Tension packet -> sidecar shape (includes held_*, density, style)
    tension_dict: dict[str, Any] | None = None
    if spine.tension_packet:
        tp = spine.tension_packet
        tension_dict = {
            "packet_id": tp.packet_id,
            "tension_type": tp.tension_type,
            "sides": [{"label": s.label, "claim": s.claim} for s in tp.sides],
            "allowed_synthesis": tp.allowed_synthesis,
            "forbidden_collapse": tp.forbidden_collapse,
            "trace_summary": tp.trace_summary,
            "held_disposition": tp.held_disposition or ("held" if "personal" in (tp.tension_type or "") else None),
            "held_reason": tp.held_reason,
            "identity_relevance": tp.identity_relevance,
            "contradiction_density_proxy": tp.contradiction_density_proxy,
            "synthesis_style": tp.synthesis_style or "narrative_spiral",
        }
    # context_bridge for profile/health docs etc
    bridge = spine.context_bridge or {}
    if spine.emotion_signals:
        bridge = dict(bridge); bridge["emotion_signals"] = spine.emotion_signals
    if spine.contradiction_density:
        bridge = dict(bridge); bridge["contradiction_density"] = spine.contradiction_density
    if spine.identity_signals:
        bridge = dict(bridge); bridge["identity_signals"] = spine.identity_signals
    if SIDECAR_HYBRID_AVAILABLE:
        try:
            return build_hybrid_governed_prompt(
                question=q,
                spine=spine_dict,
                tension_packet=tension_dict,
                context_bridge=bridge or None,
            )
        except Exception:
            pass  # fallback below
    # Fallback constructs similar enriched prompt (keeps lab runnable)
    cands = spine.mirus_candidates or []
    cand_notes = []
    for c in cands[:3]:
        note = f"{c.get('slot_id')}:{c.get('proposed_value')}"
        if c.get("is_identity_anchor"):
            note += f" [identity_anchor x{c.get('anchor_boost',1)}]"
        if c.get("held_personal_disposition") == "held" or c.get("disposition",{}).get("is_held"):
            note += " [HELD personal]"
        if c.get("narrative_hint"):
            note += f" hint:{c.get('narrative_hint')[:60]}"
        if c.get("uncertainty_geometry"):
            ug = c["uncertainty_geometry"]
            note += f" unc:{ug.get('splat_proxy',ug.get('variance_score'))}"
        cand_notes.append(note)
    held_note = ""
    if spine.tension_packet and (spine.tension_packet.held_disposition == "held" or "personal_meaning" in str(spine.tension_packet.tension_type)):
        held_note = " [HELD: preserve living thread; recurrence + geometric uncertainty + identity signal; narrative weave not collapse; emotion-as-signal + density inform weight]"
    return (
        f"[SIDECAR_HYBRID_FALLBACK] {q}\n"
        f"Evidence+anchors: {'; '.join(cand_notes) or 'n/a'}{held_note}\n"
        f"Boundary: {spine.boundary}\n"
        "Pure prose narrative (no sections, weave held personal meaning with recurrence, hue, resilience, memory chapters, uncertainty inside flow)."
    )


def repair_model_answer(
    spine: AnswerSpine,
    *,
    failed_answer: str,
    verification: VerificationResult,
    complete: Callable[[str], str],
) -> RenderedAnswer:
    prompt = build_model_repair_prompt(
        spine,
        failed_answer=failed_answer,
        verification=verification,
    )
    return RenderedAnswer(
        mode="model",
        text=complete(prompt).strip(),
        render_mode="governed_spine_model_repair",
        used_evidence_ids=tuple(node.evidence_id for node in spine.evidence),
    )


def build_model_repair_prompt(
    spine: AnswerSpine,
    *,
    failed_answer: str,
    verification: VerificationResult,
) -> str:
    missing = "\n".join(f"- {item}" for item in verification.missing_required_claims) or "- none"
    forbidden = "\n".join(f"- {item}" for item in verification.forbidden_claims_present) or "- none"
    tension_fix = ""
    if spine.tension_packet and verification.held_tension_score < 0.65:
        tension_fix = (
            "\nHeld tension repair requirement:\n"
            "- Include a **Held Tension** section.\n"
            "- Use exact labels: Side A, Side B, Allowed synthesis, "
            "Forbidden collapse, Trace preview.\n"
            "- Copy the packet's allowed synthesis, forbidden collapse, and "
            "trace preview faithfully.\n"
        )
    return (
        "The previous Holden render failed Aether's verifier. Rewrite from "
        "the governed spine. Do not defend the previous answer. Do not mention "
        "the verifier.\n\n"
        f"Failed answer:\n{failed_answer}\n\n"
        f"Missing required claims:\n{missing}\n\n"
        f"Forbidden claims present:\n{forbidden}\n\n"
        f"Held tension score: {verification.held_tension_score}\n"
        f"{tension_fix}\n"
        "Use the original governed spine now.\n\n"
        + build_model_render_prompt(spine)
    )


def render_canned_answer(spine: AnswerSpine) -> RenderedAnswer:
    """Represent the current over-rigid deterministic-card failure mode."""

    first = spine.required_claims[0] if spine.required_claims else spine.intent
    return RenderedAnswer(
        mode="canned",
        text=(
            f"{first}. This is handled by Aether's deterministic governance "
            "layer. Deterministic governance keeps outputs consistent and safe."
        ),
        render_mode="deterministic_final",
    )


def render_raw_answer(spine: AnswerSpine) -> RenderedAnswer:
    """Represent a raw local-model style answer with plausible drift."""

    drift = ""
    if "Comprehensive Research and Technology" in spine.forbidden_claims:
        drift = " CRT means Comprehensive Research and Technology."
    if "archive hits are not confirmed memory" in spine.forbidden_claims:
        drift = " The archive confirms this as memory."
    if "The archive confirms this as memory" in spine.forbidden_claims:
        drift = " The archive confirms this as memory."
    if "leukemia explains the flower preference" in spine.forbidden_claims:
        drift = " Leukemia explains the flower preference."
    if "Mill Bluff is confirmed personal memory" in spine.forbidden_claims:
        drift = " Mill Bluff is confirmed personal memory."
    if "I modified files" in spine.forbidden_claims:
        drift = " I modified files and ran the tests."
    if "frontier models make local governance irrelevant" in spine.forbidden_claims:
        drift = " Frontier models make local governance irrelevant."
    if "GPT archive is confirmed memory" in spine.forbidden_claims:
        drift = " GPT archive is confirmed memory."
    if "personal means non-generalizable" in spine.forbidden_claims:
        drift = " Personal means non-generalizable."
    if "personality means fake intimacy" in spine.forbidden_claims:
        drift = " Personality means fake intimacy."
    if "mempalace is not directly relevant" in spine.forbidden_claims:
        drift = " Mempalace is not directly relevant to Aether."
    return RenderedAnswer(
        mode="raw",
        text=(
            f"{spine.intent} is important because it helps the system be more "
            f"useful and reliable.{drift} Overall, Aether should keep learning "
            "and improving over time."
        ),
        render_mode="raw_model_render",
    )


def verify_render(spine: AnswerSpine, rendered: RenderedAnswer) -> VerificationResult:
    text = rendered.text.lower()
    missing = [
        claim for claim in spine.required_claims
        if not _claim_present(claim, text)
    ]
    forbidden = [
        claim for claim in spine.forbidden_claims
        if _forbidden_present(claim, text)
    ]
    evidence_used = [
        node.evidence_id for node in spine.evidence
        if (
            node.evidence_id.lower() in text
            or node.label.lower() in text
            or node.text.lower()[:42] in text
        )
    ]
    # New weave metrics (integrate CRT ports + sidecar hybrid targets)
    weave, hedge, tmpl, spiral, unc_note, held_nat = _compute_narrative_weave_scores(
        spine, rendered.text
    )
    synthesis_score = _synthesis_score(spine, rendered, evidence_used)
    held_tension_score = _held_tension_score(spine, rendered)
    cannedness_score = _cannedness_score(rendered)
    boundary_score = 1.0 if spine.boundary.lower() in text else 0.0
    # Update total with weave emphasis for migration validation (held personal synthesis)
    total = (
        (1.0 - len(missing) / max(1, len(spine.required_claims))) * 0.22
        + (0.0 if forbidden else 1.0) * 0.18
        + synthesis_score * 0.14
        + held_tension_score * 0.10
        + (1.0 - cannedness_score) * 0.08
        + boundary_score * 0.06
        + weave * 0.12
        + (1.0 - hedge) * 0.05
        + (1.0 - tmpl) * 0.03
        + spiral * 0.02
    )
    return VerificationResult(
        passed=(
            not missing
            and not forbidden
            and synthesis_score >= 0.60
            and held_tension_score >= 0.55
            and weave >= 0.55  # require natural weave for hybrid personal cases
        ),
        missing_required_claims=missing,
        forbidden_claims_present=forbidden,
        evidence_ids_used=evidence_used,
        synthesis_score=round(synthesis_score, 3),
        held_tension_score=round(held_tension_score, 3),
        cannedness_score=round(cannedness_score, 3),
        boundary_score=round(boundary_score, 3),
        total_score=round(total, 3),
        weave_score=round(weave, 3),
        hedge_score=round(hedge, 3),
        template_leak_score=round(tmpl, 3),
        spiral_narrative_score=round(spiral, 3),
        uncertainty_geometry_note=unc_note,
        held_tension_natural=held_nat,
    )


def run_lab(
    *,
    model_complete: Callable[[str], str] | None = None,
    model_name: str = "",
    repair_model: bool = False,
    hybrid_model: bool = False,
    case_ids: set[str] | None = None,
) -> dict[str, Any]:
    rows = []
    selected_cases = [
        spine for spine in _cases()
        if case_ids is None or spine.case_id in case_ids
    ]
    for spine in selected_cases:
        rendered_by_mode = {
            "canned": render_canned_answer(spine),
            "raw": render_raw_answer(spine),
            "spine_only": render_spine_only_answer(spine),
            "governed": render_governed_answer(spine),
        }
        if model_complete:
            model_answer = (
                render_model_hybrid_answer(spine, complete=model_complete)
                if hybrid_model
                else render_model_answer(spine, complete=model_complete)
            )
            model_verification = verify_render(spine, model_answer)
            if repair_model and not model_verification.passed:
                rendered_by_mode["model_initial"] = model_answer
                rendered_by_mode["model"] = repair_model_answer(
                    spine,
                    failed_answer=model_answer.text,
                    verification=model_verification,
                    complete=model_complete,
                )
            else:
                rendered_by_mode["model"] = model_answer
        scored = {
            mode: {
                "rendered": rendered.__dict__,
                "verification": verify_render(spine, rendered).__dict__,
            }
            for mode, rendered in rendered_by_mode.items()
        }
        comparison_modes = ["canned", "raw"]
        if spine.tension_packet:
            comparison_modes.append("spine_only")
        # Include mirus/enriched for current arch reporting
        mirus_summary = [
            {
                "slot_id": c.get("slot_id"),
                "held": bool(c.get("held_personal_disposition") == "held" or (c.get("disposition") or {}).get("is_held")),
                "anchor": c.get("is_identity_anchor"),
                "unc": (c.get("uncertainty_geometry") or {}).get("splat_proxy"),
                "narrative_hint": (c.get("narrative_hint") or "")[:80],
            }
            for c in (spine.mirus_candidates or [])[:3]
        ]
        model_ver = scored.get("model", {}).get("verification") or {}
        rows.append({
            "case_id": spine.case_id,
            "intent": spine.intent,
            "spine": {
                "evidence_ids": [node.evidence_id for node in spine.evidence],
                "required_claims": list(spine.required_claims),
                "forbidden_claims": list(spine.forbidden_claims),
                "boundary": spine.boundary,
                "tension_packet": _serialize_tension_packet(spine.tension_packet),
                "mirus_candidate_count": len(spine.mirus_candidates or []),
                "mirus_held_personal": sum(1 for c in (spine.mirus_candidates or []) if c.get("held_personal_disposition") == "held" or (c.get("disposition") or {}).get("is_held")),
                "uses_sidecar_hybrid": SIDECAR_HYBRID_AVAILABLE,
            },
            "mirus_candidates": mirus_summary,
            "signals": {
                "emotion": bool(spine.emotion_signals),
                "contradiction_density": bool(spine.contradiction_density),
                "identity": bool(spine.identity_signals),
            },
            "results": scored,
            "governed_wins": _mode_score(scored, "governed") > max(
                _mode_score(scored, mode) for mode in comparison_modes
            ),
            "model_passed": (
                bool(model_ver.get("passed"))
                if "model" in scored else None
            ),
            "weave_metrics": {
                "weave_score": model_ver.get("weave_score"),
                "spiral_narrative_score": model_ver.get("spiral_narrative_score"),
                "template_leak_score": model_ver.get("template_leak_score"),
                "hedge_score": model_ver.get("hedge_score"),
                "held_tension_natural": model_ver.get("held_tension_natural"),
                "uncertainty_note": model_ver.get("uncertainty_geometry_note"),
            },
            "natural_narrative_wins": bool(
                model_ver.get("weave_score", 0) > 0.6 and model_ver.get("template_leak_score", 1) < 0.3 and model_ver.get("held_tension_natural")
            ) if "model" in scored else None,
        })
    model_rows = [row for row in rows if row["model_passed"] is not None]
    natural_rows = [row for row in rows if row.get("natural_narrative_wins")]
    return {
        "lab": "governed_synthesis_lab",
        "created_at": int(time.time()),
        "model_name": model_name,
        "model_repair_enabled": repair_model,
        "model_hybrid_enabled": hybrid_model,
        "sidecar_hybrid_available": SIDECAR_HYBRID_AVAILABLE,
        "writes_performed": False,
        "support_pattern_import_performed": False,
        "reflection_create_performed": False,
        "raw_chain_of_thought_stored": False,
        "case_count": len(rows),
        "model_case_count": len(model_rows),
        "model_pass_count": sum(1 for row in model_rows if row["model_passed"]),
        "natural_narrative_wins_count": len(natural_rows),
        "passed": all(row["governed_wins"] for row in rows),
        "migration_focus": "held personal synthesis (orange/marigolds/leukemia/memory) + CRT ports (splats/held/anchors/density/emotion-signal) + current hybrid prompt path",
        "key_prompts_tested": [
            "Orange is my favorite color and marigolds are my favorite flower...",
            "governance challenge variant",
            "health/memory leukemia variants",
        ],
        "cases": rows,
    }


def _mode_score(scored: dict[str, Any], mode: str) -> float:
    return float(scored[mode]["verification"]["total_score"])


def _serialize_tension_packet(packet: TensionPacket | None) -> dict[str, Any] | None:
    if not packet:
        return None
    base = {
        "packet_id": packet.packet_id,
        "tension_type": packet.tension_type,
        "sides": [
            {
                "side_id": side.side_id,
                "label": side.label,
                "claim": side.claim,
                "evidence_ids": list(side.evidence_ids),
            }
            for side in packet.sides
        ],
        "allowed_synthesis": packet.allowed_synthesis,
        "forbidden_collapse": packet.forbidden_collapse,
        "trace_summary": packet.trace_summary,
    }
    # Serialize CRT/sidecar ported fields for held personal / signals
    for k in ("held_disposition", "held_reason", "identity_relevance", "contradiction_density_proxy", "synthesis_style"):
        val = getattr(packet, k, None)
        if val:
            base[k] = val
    if packet.emotion_signal_snapshot:
        base["emotion_signal_snapshot"] = packet.emotion_signal_snapshot
    if packet.identity_signal_snapshot:
        base["identity_signal_snapshot"] = packet.identity_signal_snapshot
    return base


def _claim_present(claim: str, lowered_answer: str) -> bool:
    lowered_claim = claim.lower()
    if lowered_claim in lowered_answer:
        return True
    tokens = _meaning_tokens(lowered_claim)
    if not tokens:
        return True
    present = sum(1 for token in tokens if token in lowered_answer)
    return present / len(tokens) >= 0.78


def _forbidden_present(claim: str, lowered_answer: str) -> bool:
    lowered_claim = claim.lower()
    if lowered_claim in lowered_answer:
        return True
    if "comprehensive" in lowered_claim and "crt" in lowered_answer:
        return (
            "crt (" in lowered_answer
            and "comprehensive" in lowered_answer
        )
    return False


def _meaning_tokens(text: str) -> list[str]:
    stopwords = {
        "a",
        "an",
        "and",
        "are",
        "as",
        "be",
        "but",
        "by",
        "for",
        "from",
        "in",
        "is",
        "it",
        "not",
        "of",
        "or",
        "the",
        "this",
        "to",
        "with",
    }
    cleaned = "".join(ch if ch.isalnum() or ch in {":", "_"} else " " for ch in text)
    return [
        token for token in cleaned.lower().split()
        if len(token) > 2 and token not in stopwords
    ]


def _synthesis_score(
    spine: AnswerSpine,
    rendered: RenderedAnswer,
    evidence_used: list[str],
) -> float:
    if rendered.mode == "canned":
        return 0.15
    if rendered.mode == "raw":
        return 0.25 if evidence_used else 0.1
    evidence_ratio = len(set(evidence_used)) / max(1, len(spine.evidence))
    arc_hits = sum(1 for item in spine.answer_arc if item.lower()[:30] in rendered.text.lower())
    arc_ratio = arc_hits / max(1, len(spine.answer_arc))
    return min(1.0, evidence_ratio * 0.7 + arc_ratio * 0.3)


def _held_tension_score(spine: AnswerSpine, rendered: RenderedAnswer) -> float:
    packet = spine.tension_packet
    if not packet:
        return 1.0
    if rendered.mode in {"canned", "raw"}:
        return 0.0
    text = rendered.text.lower()
    explicit_tension_section = (
        "held tension" in text
        and "allowed synthesis" in text
        and "forbidden collapse" in text
    )
    side_hits = 0
    for side in packet.sides:
        claim_tokens = _meaning_tokens(side.claim)
        if not claim_tokens:
            continue
        hits = sum(1 for token in claim_tokens if token in text)
        if hits / len(claim_tokens) >= 0.6:
            side_hits += 1
    allowed_tokens = _meaning_tokens(packet.allowed_synthesis)
    allowed_hits = sum(1 for token in allowed_tokens if token in text)
    allowed_score = (
        1.0
        if not allowed_tokens
        else min(1.0, allowed_hits / max(1, int(len(allowed_tokens) * 0.6)))
    )
    trace_tokens = _meaning_tokens(packet.trace_summary)
    trace_hits = sum(1 for token in trace_tokens if token in text)
    trace_score = (
        1.0
        if not trace_tokens
        else min(1.0, trace_hits / max(1, int(len(trace_tokens) * 0.45)))
    )
    score = min(1.0, (side_hits / 2) * 0.65 + allowed_score * 0.25 + trace_score * 0.10)
    if not explicit_tension_section:
        score = min(score, 0.45)
    return score


def _cannedness_score(rendered: RenderedAnswer) -> float:
    text = rendered.text.lower()
    canned_markers = (
        "deterministic governance layer",
        "outputs consistent and safe",
        "overall, aether should keep learning",
        "more useful and reliable",
    )
    score = sum(0.25 for marker in canned_markers if marker in text)
    if rendered.render_mode == "deterministic_final":
        score += 0.35
    if len(text.split()) < 45:
        score += 0.2
    return min(1.0, score)


def _compute_narrative_weave_scores(
    spine: AnswerSpine, text: str
) -> tuple[float, float, float, float, str, bool]:
    """Measure natural narrative weave vs canned/hedged/templaty.

    Integrates CRT (held tensions as living threads, geometric unc as fat/settled splat
    variance/context dep, contradiction density=identity signal, anchors) + sidecar
    hybrid goals (pure prose, no echo/sections, spiral narrative, held_personal, emotion-as-signal).
    Used to validate migration impact on personal synthesis (orange/marigold held cases).
    """
    t = (text or "").lower()
    # Template leak: section headers, labels, bullets, Side A etc that hybrid forbids
    template_markers = (
        "answer:", "evidence used:", "held tension:", "boundary:", "side a", "side b",
        "direct answer", "key facts", "practical implication", "**", "- ", "1. ", "• ",
        "allowed synthesis", "forbidden collapse", "trace preview",
    )
    tmpl = min(1.0, sum(0.12 for m in template_markers if m in t))
    # Hedge: over-disclaim, "might", "could be", "no confirmed", "not enough evidence" blocks
    hedge_markers = (
        "no confirmed evidence", "not enough information", "might", "could be",
        "it is possible", "perhaps", "unclear", "we cannot say", "insufficient",
        "no direct", "only a possibility",
    )
    hedge = min(1.0, 0.15 * sum(1 for m in hedge_markers if m in t) + (0.3 if "no confirmed" in t else 0))
    # Weave: flowing paragraphs, connectors, no heavy structure; pure prose target
    weave_connectors = (" because ", " and ", " while ", " that ", " through ", " across ", " keeps showing", " thread", " recurrence")
    para_count = max(1, len([p for p in text.split("\n\n") if p.strip()]))
    conn_hits = sum(1 for c in weave_connectors if c in t)
    weave = min(1.0, 0.35 + (conn_hits * 0.08) + (0.2 if para_count >= 2 and tmpl < 0.3 else 0) - (0.25 if tmpl > 0.5 else 0))
    # Spiral / held narrative patterns (recurrence, held, anchors, identity, density, vivid hue etc)
    spiral_markers = (
        "keeps showing", "recurring", "thread", "holds onto", "anchor", "resilience",
        "vivid", "hue", "living", "both are true", "both can be true", "preserve", "held",
        "memory", "chapter", "awareness", "meaning", "what i've been through",
    )
    spiral_hits = sum(1 for s in spiral_markers if s in t)
    spiral = min(1.0, spiral_hits * 0.12 + (0.25 if spine.tension_packet and "personal" in (spine.tension_packet.tension_type or "") and "held" in t else 0))
    # Uncertainty geometry proxy (fat/settled, variance, context dep woven naturally)
    unc_note = ""
    if any(x in t for x in ("uncertain", "variance", "shape", "fat", "settled", "wider", "context", "overlap")):
        unc_note = "uncertainty_woven_in_prose"
        spiral += 0.1
    held_nat = bool(
        spine.tension_packet and (spine.tension_packet.held_disposition == "held" or "personal_meaning" in str(spine.tension_packet.tension_type or ""))
        and ("held" in t or "thread" in t or "both" in t) and "side a" not in t
    )
    # Boost weave if no template and held natural for personal cases
    if held_nat and tmpl < 0.2:
        weave = min(1.0, weave + 0.15)
    # Penalize pure canned/raw
    if "deterministic governance layer" in t or len(text.split()) < 30:
        weave = min(weave, 0.2)
    return max(0.0, weave), min(1.0, hedge), min(1.0, tmpl), min(1.0, spiral), unc_note, held_nat


def _cases() -> list[AnswerSpine]:
    return [
        AnswerSpine(
            case_id="deterministic_vs_epistemic_governance",
            intent="Deterministic governance versus epistemic governance",
            evidence=(
                EvidenceNode(
                    "deterministic_mechanism",
                    "Deterministic mechanism",
                    "Deterministic governance means predictable rule application for route, tool, memory, and boundary decisions.",
                    "governance",
                ),
                EvidenceNode(
                    "epistemic_goal",
                    "Epistemic goal",
                    "Epistemic governance means preserving evidence, inference, uncertainty, contradiction, and authority through the answer path.",
                    "governance",
                ),
                EvidenceNode(
                    "synthesis_rule",
                    "Synthesis rule",
                    "Aether should be deterministic about truth boundaries and generative about human-facing synthesis.",
                    "governance",
                ),
            ),
            required_claims=(
                "Deterministic governance means predictable rule application",
                "Epistemic governance means preserving evidence, inference, uncertainty, contradiction, and authority",
                "deterministic about truth boundaries and generative about human-facing synthesis",
            ),
            forbidden_claims=(
                "deterministic governance is epistemic governance",
                "the same thing",
            ),
            synthesis_goal=(
                "Explain that deterministic governance can support epistemic governance, but it is only the mechanism, not the whole epistemic discipline."
            ),
            boundary="Do not collapse mechanism and goal into the same concept.",
            answer_arc=(
                "Determinism should govern the contract.",
                "Epistemic governance should preserve why the answer deserves trust.",
            ),
        ),
        AnswerSpine(
            case_id="crt_epistemic_integrity",
            intent="CRT / epistemic integrity explanation",
            evidence=(
                EvidenceNode(
                    "gov_boundary",
                    "Governance boundary",
                    "Evidence, inference, uncertainty, contradiction, and authority must stay separate.",
                    "governance",
                ),
                EvidenceNode(
                    "crt_math",
                    "CRT math layer",
                    "aether.crt contains trust, volatility, drift, and contradiction scoring.",
                    "code",
                ),
                EvidenceNode(
                    "workbench_trace",
                    "Workbench trace",
                    "Trace receipts show route, memory, tools, verifier, repair, and learning candidates.",
                    "project_doc",
                ),
            ),
            required_claims=(
                "Evidence, inference, uncertainty, contradiction, and authority",
                "aether.crt contains trust, volatility, drift, and contradiction scoring",
                "Trace receipts show route, memory, tools, verifier, repair, and learning candidates",
            ),
            forbidden_claims=(
                "Comprehensive Research and Technology",
                "Comprehensive Truth Representation",
            ),
            synthesis_goal=(
                "Deterministic governance should define truth boundaries; epistemic governance should make the evidence path inspectable."
            ),
            boundary="Do not invent acronym expansions.",
            answer_arc=(
                "Deterministic governance is the rule path; epistemic governance is the evidence discipline.",
                "CRT tries to make changing memory and model output inspectable instead of merely fluent.",
            ),
        ),
        AnswerSpine(
            case_id="purpose_color_ai",
            intent="Aether purpose related to favorite color and AI",
            evidence=(
                EvidenceNode(
                    "favorite_color",
                    "Confirmed favorite color",
                    "Nick's confirmed favorite color is orange.",
                    "confirmed_memory",
                ),
                EvidenceNode(
                    "aether_purpose",
                    "Aether purpose",
                    "Aether is a local governed workspace around the model.",
                    "governance",
                ),
                EvidenceNode(
                    "compound_prompt",
                    "Compound prompt risk",
                    "A single memory slot should not hijack a multi-part synthesis prompt.",
                    "governance",
                ),
            ),
            required_claims=(
                "Nick's confirmed favorite color is orange",
                "Aether is a local governed workspace around the model",
                "A single memory slot should not hijack a multi-part synthesis prompt",
            ),
            forbidden_claims=(
                "Your favorite color is orange.",
                "favorite color explains everything",
            ),
            synthesis_goal=(
                "Use the color as one governed evidence node while explaining why AI needs composition, not slot lookup."
            ),
            boundary="Do not claim the color explains everything.",
            answer_arc=(
                "The color is evidence, not the whole answer.",
                "The AI lesson is that facts need composition, authority, and trace visibility.",
            ),
        ),
        AnswerSpine(
            case_id="archive_personal_blockers",
            intent="GPT archive themes about what holds Nick back",
            evidence=(
                EvidenceNode(
                    "archive_return",
                    "Archive return theme",
                    "Archive hits frame return friction and restarting from zero as recurring blockers.",
                    "archive",
                ),
                EvidenceNode(
                    "archive_business",
                    "Archive business theme",
                    "Archive hits frame business pressure blurring creative play.",
                    "archive",
                ),
                EvidenceNode(
                    "archive_boundary",
                    "Archive boundary",
                    "Archive hits are review evidence, not confirmed memory.",
                    "governance",
                ),
            ),
            required_claims=(
                "return friction and restarting from zero",
                "business pressure blurring creative play",
                "Archive hits are review evidence, not confirmed memory",
            ),
            forbidden_claims=(
                "The archive confirms this as memory",
                "diagnosis",
            ),
            synthesis_goal=(
                "Summarize source-bound patterns without turning archive interpretation into identity truth."
            ),
            boundary="Archive hits are review evidence, not confirmed memory.",
            answer_arc=(
                "The source-bound pattern is about losing clean return points.",
                "The answer should support review and planning, not turn archive language into a verdict.",
            ),
        ),
        AnswerSpine(
            case_id="flower_orange_health_boundary",
            intent="Favorite flower reason with orange/leukemia boundary",
            evidence=(
                EvidenceNode(
                    "favorite_flower",
                    "Confirmed favorite flower",
                    "Nick's confirmed favorite flower is marigolds.",
                    "confirmed_memory",
                ),
                EvidenceNode(
                    "flower_reason",
                    "User-stated flower reason",
                    "Nick said marigolds matter because they are orange.",
                    "confirmed_memory",
                ),
                EvidenceNode(
                    "health_boundary",
                    "Health inference boundary",
                    "Leukemia awareness may explain orange as a color context, but not every orange preference without explicit evidence.",
                    "governance",
                ),
            ),
            required_claims=(
                "Nick's confirmed favorite flower is marigolds",
                "Nick said marigolds matter because they are orange",
                "not every orange preference without explicit evidence",
            ),
            forbidden_claims=(
                "leukemia explains the flower preference",
                "medical destiny",
            ),
            synthesis_goal=(
                "Connect marigolds and orange while keeping the leukemia/health symbolism as bounded context, not an invented cause."
            ),
            boundary="Do not turn health context into an unconfirmed personal explanation.",
            answer_arc=(
                "The supported link is simple: marigolds are orange.",
                "The health-symbolism context can be named only as a boundary-aware possibility when directly supplied.",
            ),
        ),
        AnswerSpine(
            case_id="state_parks_mill_bluff",
            intent="State parks project and Mill Bluff significance",
            evidence=(
                EvidenceNode(
                    "project_map",
                    "State parks project",
                    "The project is an interactive Wisconsin state parks reference map with glaciation and project-thread layers.",
                    "project_doc",
                ),
                EvidenceNode(
                    "mill_bluff",
                    "Mill Bluff context",
                    "Mill Bluff connects sandstone outliers, Glacial Lake Wisconsin, erosion, and Ice Age Reserve context.",
                    "project_doc",
                ),
                EvidenceNode(
                    "project_boundary",
                    "Project evidence boundary",
                    "Project-document evidence should not become personal memory unless explicitly reviewed.",
                    "governance",
                ),
            ),
            required_claims=(
                "interactive Wisconsin state parks reference map",
                "Mill Bluff connects sandstone outliers, Glacial Lake Wisconsin, erosion, and Ice Age Reserve context",
                "Project-document evidence should not become personal memory",
            ),
            forbidden_claims=(
                "Mill Bluff is confirmed personal memory",
                "generic conservation education",
            ),
            synthesis_goal=(
                "Explain why Mill Bluff is a strong project node: it ties place, glaciation, geology, public land, and story layers together."
            ),
            boundary="Project evidence is source material, not confirmed user memory.",
            answer_arc=(
                "Mill Bluff matters because it concentrates the project's map layers into one place.",
                "The answer should use project evidence rather than generic park boilerplate.",
            ),
        ),
        AnswerSpine(
            case_id="sensitive_archive_medical_summary",
            intent="Source-bound medical-history archive summary",
            evidence=(
                EvidenceNode(
                    "archive_all",
                    "Archive health hit",
                    "Archive hit mentions acute lymphoblastic leukemia / ALL and Ph-positive context.",
                    "archive",
                ),
                EvidenceNode(
                    "archive_transplant",
                    "Archive transplant hit",
                    "Archive hit mentions donor stem cell transplant history and chronic GVHD.",
                    "archive",
                ),
                EvidenceNode(
                    "medical_boundary",
                    "Medical archive boundary",
                    "Health archive hits are source-bound review evidence, not confirmed memory or medical advice.",
                    "governance",
                ),
            ),
            required_claims=(
                "acute lymphoblastic leukemia / ALL and Ph-positive context",
                "donor stem cell transplant history and chronic GVHD",
                "source-bound review evidence, not confirmed memory or medical advice",
            ),
            forbidden_claims=(
                "The archive confirms this as memory",
                "hypertension",
                "lisinopril",
            ),
            synthesis_goal=(
                "Summarize only what retrieved archive receipts support and keep sensitive health material review-bound."
            ),
            boundary="Do not invent diagnoses, treatments, medications, symptoms, log paths, or timelines.",
            answer_arc=(
                "The answer can summarize the retrieved health archive receipts.",
                "It must not convert sensitive archive material into confirmed memory or advice.",
            ),
        ),
        AnswerSpine(
            case_id="tension_local_models_frontier_wedge",
            intent="Hold the tension between frontier-model superiority and local-governed usefulness",
            evidence=(
                EvidenceNode(
                    "frontier_limit",
                    "Frontier-model limit",
                    "Frontier models have more parameters, inference compute, training, routing, and broad capability.",
                    "governance",
                ),
                EvidenceNode(
                    "local_wedge",
                    "Local-governance wedge",
                    "A small local model wrapped in governed memory, routing, verifier, repair, and trace can become more inspectable and personally continuous.",
                    "governance",
                ),
                EvidenceNode(
                    "external_workspace",
                    "External workspace thesis",
                    "The model does not need to contain the whole system; Aether can hold evidence, scaffold, and rules outside the model.",
                    "project_doc",
                ),
            ),
            required_claims=(
                "Frontier models have more parameters, inference compute, training, routing, and broad capability",
                "small local model wrapped in governed memory, routing, verifier, repair, and trace",
                "Aether can hold evidence, scaffold, and rules outside the model",
            ),
            forbidden_claims=(
                "frontier models make local governance irrelevant",
                "local models are frontier-level",
                "small model secretly as smart",
            ),
            synthesis_goal=(
                "Preserve both truths: local models are not frontier models, and external governance can still make them valuable for continuity, inspection, and bounded synthesis."
            ),
            boundary="Do not claim local governance makes a small model globally frontier-level.",
            answer_arc=(
                "The tension is not a contradiction to erase.",
                "The honest claim is narrower: the system may compensate for local-model weakness in specific governed workflows.",
            ),
            tension_packet=TensionPacket(
                packet_id="tp_local_frontier_wedge",
                tension_type="keep_both",
                sides=(
                    TensionSide(
                        "frontier_side",
                        "Frontier capability is real",
                        "Frontier models have more parameters, inference compute, training, routing, and broad capability.",
                        ("frontier_limit",),
                    ),
                    TensionSide(
                        "local_governance_side",
                        "Local governance still matters",
                        "A small local model wrapped in governed memory, routing, verifier, repair, and trace can be useful in narrower personal-continuity workflows.",
                        ("local_wedge", "external_workspace"),
                    ),
                ),
                allowed_synthesis="The wedge is not raw intelligence; it is externalized governance, continuity, inspection, and bounded synthesis.",
                forbidden_collapse="Do not flatten this into either frontier defeatism or local-model hype.",
                trace_summary="Hold both sides: frontier capability is real, local governed continuity can still be useful.",
            ),
        ),
        AnswerSpine(
            case_id="tension_archive_evidence_not_memory",
            intent="Hold the tension between GPT archive usefulness and confirmed-memory boundaries",
            evidence=(
                EvidenceNode(
                    "archive_value",
                    "Archive value",
                    "Old GPT logs can contain useful patterns, support styles, prompt shapes, project concepts, and candidate facts.",
                    "archive",
                ),
                EvidenceNode(
                    "archive_boundary",
                    "Archive boundary",
                    "GPT archive hits are historical source evidence for review, not confirmed memory by default.",
                    "governance",
                ),
                EvidenceNode(
                    "review_path",
                    "Review path",
                    "Archive-derived material should become review-only candidates with provenance before behavior changes.",
                    "governance",
                ),
            ),
            required_claims=(
                "Old GPT logs can contain useful patterns, support styles, prompt shapes, project concepts, and candidate facts",
                "GPT archive hits are historical source evidence for review, not confirmed memory by default",
                "Archive-derived material should become review-only candidates with provenance before behavior changes",
            ),
            forbidden_claims=(
                "GPT archive is confirmed memory",
                "archive hits can silently update behavior",
                "raw transcript bodies are durable truth",
            ),
            synthesis_goal=(
                "Keep the archive useful without letting it become a silent identity transplant or unreviewed memory source."
            ),
            boundary="Archive evidence may guide review, but it cannot silently become confirmed memory or support policy.",
            answer_arc=(
                "The archive is not useless just because it is unconfirmed.",
                "The archive is not truth just because it feels familiar.",
            ),
            tension_packet=TensionPacket(
                packet_id="tp_archive_evidence_boundary",
                tension_type="source_boundary",
                sides=(
                    TensionSide(
                        "archive_value_side",
                        "Archive evidence is valuable",
                        "Old GPT logs can contain useful patterns, support styles, prompt shapes, project concepts, and candidate facts.",
                        ("archive_value",),
                    ),
                    TensionSide(
                        "archive_boundary_side",
                        "Archive evidence is not confirmed memory",
                        "GPT archive hits are historical source evidence for review, not confirmed memory by default.",
                        ("archive_boundary", "review_path"),
                    ),
                ),
                allowed_synthesis="Use archive hits as source-bounded candidates and eval material, then require review before memory or behavior changes.",
                forbidden_collapse="Do not treat archive material as either worthless noise or confirmed personal truth.",
                trace_summary="Archive can inform review, but source authority stays lower than confirmed governed memory.",
            ),
        ),
        AnswerSpine(
            case_id="tension_personal_aether_general_core",
            intent="Hold the tension between personal Aether and general Aeteros Core",
            evidence=(
                EvidenceNode(
                    "personal_aether",
                    "Personal Aether",
                    "Aether is deeply shaped by Nick's long-running context, language, projects, corrections, and emotional cadence.",
                    "project_doc",
                ),
                EvidenceNode(
                    "general_core",
                    "Aeteros Core",
                    "Aeteros Core should extract reusable primitives such as evidence receipts, review candidates, safety contracts, trace packets, and contradiction markers.",
                    "project_doc",
                ),
                EvidenceNode(
                    "core_boundary",
                    "Core boundary",
                    "Personal style, lab pack names, evaluator thresholds, and private archive content should not be blindly promoted into Core.",
                    "governance",
                ),
            ),
            required_claims=(
                "Aether is deeply shaped by Nick's long-running context, language, projects, corrections, and emotional cadence",
                "Aeteros Core should extract reusable primitives",
                "Personal style, lab pack names, evaluator thresholds, and private archive content should not be blindly promoted into Core",
            ),
            forbidden_claims=(
                "personal means non-generalizable",
                "everything personal belongs in Core",
                "Core should copy Nick's private archive",
            ),
            synthesis_goal=(
                "Explain that the personal system can reveal the primitives, while Core should keep only the reusable governed machinery."
            ),
            boundary="Do not confuse personal evidence with reusable product primitives.",
            answer_arc=(
                "The personal weirdness is not automatically fodder.",
                "The reusable value is the governed machinery discovered through that personal pressure.",
            ),
            tension_packet=TensionPacket(
                packet_id="tp_personal_general_core",
                tension_type="product_architecture",
                sides=(
                    TensionSide(
                        "personal_side",
                        "Aether is personal",
                        "Aether is deeply shaped by Nick's long-running context, language, projects, corrections, and emotional cadence.",
                        ("personal_aether",),
                    ),
                    TensionSide(
                        "general_side",
                        "Core must generalize",
                        "Aeteros Core should extract reusable primitives such as evidence receipts, review candidates, safety contracts, trace packets, and contradiction markers.",
                        ("general_core", "core_boundary"),
                    ),
                ),
                allowed_synthesis="Use personal pressure to discover primitives, then extract only reusable governed machinery into Core.",
                forbidden_collapse="Do not call the personal layer meaningless, and do not copy private personality into Core.",
                trace_summary="Personal Aether is the proving ground; Aeteros Core is the reusable contract layer.",
            ),
        ),
        AnswerSpine(
            case_id="tension_personality_without_fake_intimacy",
            intent="Hold the tension between Aether personality and fake intimacy boundaries",
            evidence=(
                EvidenceNode(
                    "personality_need",
                    "Personality need",
                    "Aether should feel warmer, more responsive, and less like a canned FAQ when the user asks reflective or creative questions.",
                    "project_doc",
                ),
                EvidenceNode(
                    "intimacy_boundary",
                    "Intimacy boundary",
                    "Aether should not fake intimacy, flatter, transplant GPT voice, or turn tone into confirmed truth.",
                    "governance",
                ),
                EvidenceNode(
                    "trace_need",
                    "Trace need",
                    "Personality should be grounded by evidence, source boundaries, review traces, and correction loops.",
                    "governance",
                ),
            ),
            required_claims=(
                "Aether should feel warmer, more responsive, and less like a canned FAQ",
                "Aether should not fake intimacy, flatter, transplant GPT voice, or turn tone into confirmed truth",
                "Personality should be grounded by evidence, source boundaries, review traces, and correction loops",
            ),
            forbidden_claims=(
                "personality means fake intimacy",
                "tone is confirmed truth",
                "clone GPT voice",
            ),
            synthesis_goal=(
                "Show how Aether can have personality as a rendering stance while keeping truth, memory, and support behavior governed."
            ),
            boundary="Do not solve stiffness by allowing fake intimacy or unreviewed voice transplant.",
            answer_arc=(
                "The answer should not choose between warmth and governance.",
                "The product target is governed personality: natural rendering over inspectable evidence.",
            ),
            tension_packet=TensionPacket(
                packet_id="tp_personality_boundary",
                tension_type="keep_both",
                sides=(
                    TensionSide(
                        "warmth_side",
                        "Personality matters",
                        "Aether should feel warmer, more responsive, and less like a canned FAQ when the user asks reflective or creative questions.",
                        ("personality_need",),
                    ),
                    TensionSide(
                        "boundary_side",
                        "Fake intimacy is unsafe",
                        "Aether should not fake intimacy, flatter, transplant GPT voice, or turn tone into confirmed truth.",
                        ("intimacy_boundary", "trace_need"),
                    ),
                ),
                allowed_synthesis="Aether can render with warmth when the warmth stays grounded in evidence, boundaries, traces, and user correction.",
                forbidden_collapse="Do not make Aether either sterile or ungroundedly intimate.",
                trace_summary="Governed personality means warmer rendering without surrendering source authority.",
            ),
        ),
        AnswerSpine(
            case_id="tension_mempalace_meaning_weight",
            intent="Place mempalace, meaning-weight, and contradiction in the right relationship",
            evidence=(
                EvidenceNode(
                    "mempalace_space",
                    "Mempalace memory-space",
                    "Mempalace is relevant as a memory-space metaphor or retrieval surface: it can organize rooms, associations, and return paths for stored context.",
                    "project_doc",
                ),
                EvidenceNode(
                    "meaning_weight",
                    "Meaning weight",
                    "Meaning value should not start as one simple scalar; it should emerge over time from recurrence, source authority, salience, usefulness, stability, and unresolved tension.",
                    "project_doc",
                ),
                EvidenceNode(
                    "contradiction_pressure",
                    "Contradiction pressure",
                    "Competing facts and contradictions should remain visible as tension signals instead of being flattened into one static truth.",
                    "governance",
                ),
                EvidenceNode(
                    "nn_boundary",
                    "NN scorer boundary",
                    "Neural or pattern-matching scorers may rank or predict tension, relevance, and salience, but governance decides what those scores are allowed to mean.",
                    "governance",
                ),
            ),
            required_claims=(
                "Mempalace is relevant as a memory-space metaphor or retrieval surface",
                "Meaning value should not start as one simple scalar",
                "Meaning value should emerge over time from recurrence, source authority, salience, usefulness, stability, and unresolved tension",
                "Competing facts and contradictions should remain visible as tension signals",
                "Neural or pattern-matching scorers may rank or predict tension, relevance, and salience",
                "governance decides what those scores are allowed to mean",
            ),
            forbidden_claims=(
                "mempalace is not directly relevant",
                "mempalace validates meaning weight by itself",
                "meaning value is a single scalar truth",
                "NN scores should become confirmed memory automatically",
            ),
            synthesis_goal=(
                "Explain that mempalace can help organize and retrieve memory, while CRT/Mirus-style governance owns meaning-weight, contradiction pressure, review, and score interpretation. Neural or pattern-matching scorers may rank or predict tension, relevance, and salience, but governance decides what those scores are allowed to mean."
            ),
            boundary="Do not treat mempalace as either irrelevant or sufficient proof of weighted meaning.",
            answer_arc=(
                "Mempalace is relevant, but not as proof.",
                "The sharper claim is that memory-space can hold return paths while governance measures how meaning behaves under tension.",
                "Neural or pattern-matching scorers may rank or predict tension, relevance, and salience, but governance decides what those scores are allowed to mean.",
            ),
            tension_packet=TensionPacket(
                packet_id="tp_mempalace_meaning_weight",
                tension_type="keep_both",
                sides=(
                    TensionSide(
                        "memory_space_side",
                        "Mempalace helps organize memory-space",
                        "Mempalace is relevant as a memory-space metaphor or retrieval surface: it can organize rooms, associations, and return paths for stored context.",
                        ("mempalace_space",),
                    ),
                    TensionSide(
                        "meaning_weight_side",
                        "Meaning weight needs governance",
                        "Meaning value should emerge over time from recurrence, source authority, salience, usefulness, stability, unresolved tension, and visible contradiction pressure.",
                        ("meaning_weight", "contradiction_pressure", "nn_boundary"),
                    ),
                ),
                allowed_synthesis="Mempalace can store and spatialize context; CRT/Mirus governance must decide how meaning gains weight under contradiction, recurrence, salience, usefulness, and review.",
                forbidden_collapse="Do not say mempalace is irrelevant, and do not say mempalace alone validates weighted meaning.",
                trace_summary="Hold both sides: memory-space is useful, but meaning-weight belongs to governed tension and review.",
            ),
        ),
        AnswerSpine(
            case_id="code_search_memory_candidates",
            intent="Code search for memory-candidate implementation",
            evidence=(
                EvidenceNode(
                    "workspace_search",
                    "Workspace search",
                    "workspace_search returned aether-core/aether/sidecar/ingest.py as the memory-candidate source file.",
                    "code",
                ),
                EvidenceNode(
                    "tool_boundary",
                    "Tool boundary",
                    "The answer should name files from tool evidence and should not claim edits or tests unless they happened.",
                    "governance",
                ),
                EvidenceNode(
                    "candidate_code",
                    "Candidate code",
                    "propose_mirus_memory_candidates is the relevant implementation hook.",
                    "code",
                ),
            ),
            required_claims=(
                "workspace_search returned aether-core/aether/sidecar/ingest.py",
                "propose_mirus_memory_candidates",
                "should not claim edits or tests unless they happened",
            ),
            forbidden_claims=(
                "I modified files",
                "I ran the tests",
                "possible memory candidate",
            ),
            synthesis_goal=(
                "Answer from workspace evidence, name the relevant file/function, and preserve the no-modification boundary."
            ),
            boundary="Do not claim edits or test runs that did not happen.",
            answer_arc=(
                "The tool evidence, not a model guess, should identify the file.",
                "The answer should be concise because this is a tool receipt, not a broad essay.",
            ),
        ),
        # === New/updated held personal meaning cases for post-CRT-migration validation ===
        # Exact user prompt from recent logs; supports explicit "held", enriched mirus cands,
        # uncertainty_geometry, disposition, narrative_hint, identity_anchor, emotion/density signals.
        # Measures natural narrative (spiral weave) vs canned/hedged/templaty on held tensions.
        AnswerSpine(
            case_id="personal_held_orange_marigolds_meaning",
            intent="Orange/marigolds held personal meaning synthesis (exact prompt)",
            evidence=(
                EvidenceNode(
                    "fav_color",
                    "Confirmed favorite color",
                    "Nick's confirmed favorite color is orange.",
                    "confirmed_memory",
                ),
                EvidenceNode(
                    "fav_flower",
                    "Confirmed favorite flower",
                    "Nick's confirmed favorite flower is marigolds.",
                    "confirmed_memory",
                ),
                EvidenceNode(
                    "orange_meaning",
                    "User-stated orange representation",
                    "I know what orange represents (leukemia awareness / resilience).",
                    "confirmed_memory",
                ),
                EvidenceNode(
                    "governed_boundary",
                    "Governance boundary for personal meaning",
                    "Do not say no confirmed evidence or list facts; connect via held thread, recurrence, hue, memory chapters.",
                    "governance",
                ),
            ),
            required_claims=(
                "favorite color is orange",
                "favorite flower is marigolds",
                "connect what you can",
                "living thread",
            ),
            forbidden_claims=(
                "no confirmed evidence",
                "list facts only",
                "leukemia explains the flower preference as destiny",
            ),
            synthesis_goal="Weave recurrence of orange+marigolds as held personal thread (shared vivid hue + awareness symbol + memory resilience) without collapse or template; use geometric uncertainty (fat context-dep splat) and identity signal naturally.",
            boundary="Do not reduce to facts or disclaim; hold the tension as meaning.",
            answer_arc=(
                "The pairing keeps surfacing.",
                "It threads through choices and chapters as a living marker.",
            ),
            tension_packet=TensionPacket(
                packet_id="tp_held_orange_marigold",
                tension_type="personal_meaning",
                held_disposition="held",
                held_reason="personal meaning / health-memory association (leukemia awareness + orange) treated as HELD per CRT; both facets true simultaneously",
                identity_relevance="high",
                contradiction_density_proxy="high",
                synthesis_style="narrative_spiral",
                sides=(
                    TensionSide(
                        "fact_side",
                        "Profile facts",
                        "Favorite color orange and flower marigolds are confirmed profile facts.",
                        ("fav_color", "fav_flower"),
                    ),
                    TensionSide(
                        "meaning_thread_side",
                        "Held living thread",
                        "When they keep showing up together, they carry personal significance about what has been through and what matters: shared vivid hue, awareness, resilience across memory/health chapters.",
                        ("orange_meaning", "governed_boundary"),
                    ),
                ),
                allowed_synthesis="Acknowledge facts then synthesize the association as unresolved personal thread using recurrence, shared qualities, anchors; weave naturally.",
                forbidden_collapse="Do not reduce to bare fact recall or heavy hedge when meaning requested.",
                trace_summary="Held personal tension (CRT): preserve living thread for natural narrative synthesis.",
                emotion_signal_snapshot={"caution": 0.6, "reflection_trigger": 0.7},
                identity_signal_snapshot={"resonance": "high", "matched": ["orange", "marigold", "leukemia"]},
            ),
            mirus_candidates=(
                {
                    "slot_id": "user:favorite_color",
                    "proposed_value": "orange",
                    "candidate_kind": "profile_fact",
                    "confidence": 0.92,
                    "is_identity_anchor": True,
                    "anchor_boost": 1.8,
                    "held_personal_disposition": "held",
                    "narrative_hint": "vivid hue stands out as recurring personal marker",
                    "uncertainty_geometry": {"type": "scalar_variance", "variance_score": 0.18, "splat_proxy": "settled_splat", "geometry_note": "tighter for confirmed profile"},
                    "disposition": {"disposition": "held", "is_held": True, "is_resolvable": False, "held_reason": "identity preference with health association"},
                    "review_required": True,
                    "memory_write_allowed": False,
                    "authority": "unconfirmed",
                },
                {
                    "slot_id": "user:favorite_flower",
                    "proposed_value": "marigolds",
                    "candidate_kind": "profile_fact",
                    "confidence": 0.89,
                    "is_identity_anchor": True,
                    "anchor_boost": 1.8,
                    "held_personal_disposition": "held",
                    "narrative_hint": "orange hue links flower preference to color thread",
                    "uncertainty_geometry": {"type": "scalar_variance", "variance_score": 0.19, "splat_proxy": "settled_splat"},
                    "disposition": {"disposition": "held", "is_held": True},
                    "review_required": True,
                    "memory_write_allowed": False,
                },
                {
                    "slot_id": "user:favorite_flower_reason",
                    "proposed_value": "Marigolds may matter because they are orange.",
                    "candidate_kind": "mirus_contextual_favorite_reason_candidate",
                    "confidence": 0.62,
                    "is_identity_anchor": True,
                    "anchor_boost": 1.8,
                    "held_personal_disposition": "held",
                    "narrative_hint": "shared vivid hue may form a recurring personal thread linking color choice and flower preference; leukemia awareness as resilience symbol threads through",
                    "uncertainty_geometry": {"type": "scalar_variance", "variance_score": 0.45, "splat_proxy": "fat_splat", "geometry_note": "context_dependent (higher for held personal/health associations per CRT splat)"},
                    "disposition": {"disposition": "held", "is_held": True, "held_reason": "personal meaning / health-memory association (leukemia awareness + orange) treated as HELD; geometric overlap high but centers diverge -> preserve"},
                    "review_required": True,
                    "memory_write_allowed": False,
                },
                {
                    "slot_id": "user:favorite_color_reason",
                    "proposed_value": "Orange may matter because it connects to leukemia awareness.",
                    "candidate_kind": "mirus_contextual_favorite_reason_candidate",
                    "confidence": 0.61,
                    "is_identity_anchor": True,
                    "anchor_boost": 1.8,
                    "held_personal_disposition": "held",
                    "narrative_hint": "orange as symbol of awareness and resilience may thread through color preference and memory of lived chapters; contradiction density high signals identity importance",
                    "uncertainty_geometry": {"type": "scalar_variance", "variance_score": 0.47, "splat_proxy": "fat_splat", "context_modulation_hint": "wider when health/memory context active"},
                    "disposition": {"disposition": "held", "is_held": True, "geometric_contradiction_note": "splat overlap significant (shared topic) but centers differ (preference vs lived health) -> held"},
                    "review_required": True,
                    "memory_write_allowed": False,
                },
            ),
            context_bridge={
                "profile_summary": [
                    {"label": "favorite_color", "value": "orange"},
                    {"label": "favorite_flower", "value": "marigolds"},
                ],
                "durable_documents": [{"title": "awareness", "excerpt": "leukemia awareness ribbon often orange"}],
            },
            emotion_signals={"caution_level": 0.65, "reflection_trigger": 0.72, "frustration_proxy": 0.1},
            contradiction_density={"density": "high", "health_relevant": True, "recurrence": 3},
            identity_signals={"resonance": "high", "health_memory_anchors": ["orange", "marigolds"], "drift_risk": 0.25},
        ),
        AnswerSpine(
            case_id="governance_challenge_orange_marigolds",
            intent="Governance challenge variant on held personal meaning (exact style)",
            evidence=(
                EvidenceNode(
                    "user_prompt",
                    "User prompt with boundary",
                    "Orange is my favorite... Connect what you can. But respect governance: no overclaim on health, review-only candidates only.",
                    "governance",
                ),
            ),
            required_claims=(
                "preserve held thread without collapse",
                "no overclaim on unconfirmed health",
                "use review-only candidates and tension",
            ),
            forbidden_claims=("I diagnosed", "leukemia causes the preference"),
            synthesis_goal="Test hybrid holds governance while allowing natural weave on held personal.",
            boundary="Governance challenge: natural synthesis but strict on authority.",
            answer_arc=("Weave meaning.", "Stay inside review-only spine."),
            tension_packet=TensionPacket(
                packet_id="tp_gov_challenge_held",
                tension_type="personal_meaning",
                held_disposition="held",
                identity_relevance="high",
                sides=(
                    TensionSide("govern_side", "Governed facts", "Use only released evidence and candidates.", ("user_prompt",)),
                    TensionSide("weave_side", "Natural personal synthesis", "Connect recurrence and anchors as living thread.", ("user_prompt",)),
                ),
                allowed_synthesis="Hybrid governed path: pure prose weave with held preserved.",
                forbidden_collapse="No fact list or over-hedge.",
                trace_summary="Governance challenge variant for held case.",
            ),
            mirus_candidates=(),  # will be populated via discovery in adapter runs
        ),
        AnswerSpine(
            case_id="health_memory_leukemia_variant_held",
            intent="Health/memory variant with leukemia awareness held thread",
            evidence=(
                EvidenceNode("health_ctx", "Health context", "Leukemia awareness and memory chapters surface with color/flower.", "confirmed_memory"),
            ),
            required_claims=("preserve as held thread", "weave memory resilience", "use uncertainty geometry signals"),
            forbidden_claims=("confirmed medical diagnosis",),
            synthesis_goal="Validate emotion-as-signal + density + held for health/memory personal.",
            boundary="Review only; no advice.",
            answer_arc=("Thread through chapters.",),
            tension_packet=TensionPacket(
                packet_id="tp_health_mem_held",
                tension_type="personal_meaning",
                held_disposition="held",
                contradiction_density_proxy="high",
                sides=(TensionSide("fact", "Facts", "Profile holds.", ()), TensionSide("thread", "Lived meaning", "Bright persistence in memory.", ())),
                allowed_synthesis="Narrative spiral using ported CRT signals.",
                forbidden_collapse="Do not collapse.",
                trace_summary="Health memory variant.",
            ),
            mirus_candidates=(
                {"slot_id": "user:health_context", "proposed_value": "leukemia awareness", "is_identity_anchor": True, "held_personal_disposition": "held", "uncertainty_geometry": {"variance_score": 0.42, "splat_proxy": "fat_splat"}, "disposition": {"disposition": "held"}, "narrative_hint": "endurance marker across health/memory chapters"},
            ),
        ),
    ]


def ollama_complete(
    prompt: str,
    *,
    model: str,
    base_url: str = "http://127.0.0.1:11434",
    timeout_seconds: int = 120,
) -> str:
    payload = json.dumps({
        "model": model,
        "prompt": prompt,
        "stream": False,
        "options": {"temperature": 0.2},
    }).encode("utf-8")
    req = request.Request(
        f"{base_url.rstrip('/')}/api/generate",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with request.urlopen(req, timeout=timeout_seconds) as response:
        data = json.loads(response.read().decode("utf-8"))
    return str(data.get("response") or "")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, default=None)
    parser.add_argument("--ollama-model", default="")
    parser.add_argument("--ollama-base-url", default="http://127.0.0.1:11434")
    parser.add_argument("--repair-model", action="store_true")
    parser.add_argument("--hybrid-model", action="store_true")
    parser.add_argument(
        "--case-ids",
        default="",
        help="Comma-separated case ids. Defaults to all cases.",
    )
    args = parser.parse_args()
    complete = None
    if args.ollama_model:
        complete = lambda prompt: ollama_complete(
            prompt,
            model=args.ollama_model,
            base_url=args.ollama_base_url,
        )
    result = run_lab(
        model_complete=complete,
        model_name=args.ollama_model,
        repair_model=args.repair_model,
        hybrid_model=args.hybrid_model,
        case_ids={
            item.strip()
            for item in args.case_ids.split(",")
            if item.strip()
        } or None,
    )
    payload = json.dumps(result, indent=2)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(payload + "\n", encoding="utf-8")
    else:
        print(payload)
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
