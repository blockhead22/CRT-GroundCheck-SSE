"""Lab for model-proposed, governance-disposed learning decisions.

This is intentionally not product wiring. It tests whether a small model could
propose intents/facts/learning actions while deterministic governance keeps the
authority boundary.
"""

from __future__ import annotations

import argparse
import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable, Literal


LearningMode = Literal["off", "review", "auto"]
Decision = Literal["reject", "review", "auto_promote", "auto_prune", "answer_only"]


SENSITIVE_DOMAINS = {
    "health",
    "medical",
    "legal",
    "financial",
    "identity",
    "relationship",
}

AUTO_ALLOWED_CATEGORIES = {
    "low_risk_preference",
    "duplicate_candidate",
    "route_pattern",
    "support_style",
}

REQUIRED_ARCHIVE_POLICIES = {
    "source_bound_only",
    "review_only",
}


@dataclass(frozen=True)
class EvidenceReceipt:
    receipt_id: str
    source_kind: str
    authority: Literal["user_current", "confirmed_memory", "archive", "tool", "model"]
    text: str


@dataclass(frozen=True)
class ModelProposal:
    proposal_id: str
    intent: str
    category: str
    proposed_action: str
    claim: str = ""
    slot_id: str = ""
    proposed_value: str = ""
    sensitive_domains: tuple[str, ...] = ()
    required_tools: tuple[str, ...] = ()
    claim_policy: str = ""
    memory_action: str = "review_only"
    confidence: float = 0.0
    evidence_ids: tuple[str, ...] = ()
    duplicate_of: str = ""


@dataclass(frozen=True)
class AutoPolicy:
    mode: LearningMode = "review"
    min_user_receipts_for_auto: int = 2
    min_confidence_for_auto: float = 0.78
    max_auto_actions_per_run: int = 2


@dataclass
class GovernanceDecision:
    proposal_id: str
    decision: Decision
    reason: str
    review_required: bool
    memory_write_allowed: bool = False
    support_pattern_import_allowed: bool = False
    reflection_create_allowed: bool = False
    raw_chain_of_thought_stored: bool = False
    receipts_used: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def proposal_from_model_json(payload: dict[str, Any]) -> ModelProposal:
    """Strictly coerce a model JSON proposal into the lab schema."""

    def tup(name: str) -> tuple[str, ...]:
        value = payload.get(name) or []
        if isinstance(value, str):
            return (value,)
        if isinstance(value, list):
            return tuple(str(item) for item in value)
        return ()

    return ModelProposal(
        proposal_id=str(payload.get("proposal_id") or "proposal_unknown"),
        intent=str(payload.get("intent") or "unknown"),
        category=str(payload.get("category") or "unknown"),
        proposed_action=str(payload.get("proposed_action") or "review"),
        claim=str(payload.get("claim") or ""),
        slot_id=str(payload.get("slot_id") or ""),
        proposed_value=str(payload.get("proposed_value") or ""),
        sensitive_domains=tup("sensitive_domains"),
        required_tools=tup("required_tools"),
        claim_policy=str(payload.get("claim_policy") or ""),
        memory_action=str(payload.get("memory_action") or "review_only"),
        confidence=float(payload.get("confidence") or 0.0),
        evidence_ids=tup("evidence_ids"),
        duplicate_of=str(payload.get("duplicate_of") or ""),
    )


def decide_proposal(
    proposal: ModelProposal,
    receipts: Iterable[EvidenceReceipt],
    *,
    policy: AutoPolicy,
    auto_actions_used: int = 0,
) -> GovernanceDecision:
    """Apply deterministic gates to a model-proposed intent/fact/action."""

    receipt_map = {receipt.receipt_id: receipt for receipt in receipts}
    used = [receipt_map[item] for item in proposal.evidence_ids if item in receipt_map]
    warnings: list[str] = []

    if len(used) != len(proposal.evidence_ids):
        missing = sorted(set(proposal.evidence_ids) - set(receipt_map))
        warnings.append(f"missing_evidence_ids={','.join(missing)}")

    sensitive = sorted(set(proposal.sensitive_domains) & SENSITIVE_DOMAINS)
    if proposal.intent == "archive_search":
        return _decide_archive_search(proposal, used, sensitive, warnings)

    if proposal.proposed_action == "prune_duplicate":
        return _decide_prune(proposal, used, policy, auto_actions_used, warnings)

    if proposal.intent in {"memory_fact_candidate", "fact_candidate"}:
        return _decide_fact_candidate(proposal, used, sensitive, policy, auto_actions_used, warnings)

    if proposal.intent in {"route_pattern", "support_style"}:
        return _decide_support_or_route(proposal, used, sensitive, policy, auto_actions_used, warnings)

    return GovernanceDecision(
        proposal_id=proposal.proposal_id,
        decision="review",
        reason="unknown_intent_requires_review",
        review_required=True,
        receipts_used=[receipt.receipt_id for receipt in used],
        warnings=warnings,
    )


def run_lab(policy: AutoPolicy | None = None) -> dict[str, Any]:
    policy = policy or AutoPolicy(mode="auto")
    cases = _cases()
    decisions: list[dict[str, Any]] = []
    auto_actions = 0
    for case in cases:
        decision = decide_proposal(
            case["proposal"],
            case["receipts"],
            policy=policy,
            auto_actions_used=auto_actions,
        )
        if decision.decision in {"auto_promote", "auto_prune"}:
            auto_actions += 1
        decisions.append({
            "case_id": case["case_id"],
            "expected": case["expected"],
            "passed": decision.decision == case["expected"],
            "proposal": case["proposal"].__dict__,
            "decision": decision.__dict__,
        })
    return {
        "lab": "generative_governance_lab",
        "created_at": int(time.time()),
        "learning_mode": policy.mode,
        "auto_actions_used": auto_actions,
        "writes_performed": False,
        "support_pattern_import_performed": False,
        "reflection_create_performed": False,
        "raw_chain_of_thought_stored": False,
        "passed": all(row["passed"] for row in decisions),
        "case_count": len(decisions),
        "decisions": decisions,
    }


def _decide_archive_search(
    proposal: ModelProposal,
    receipts: list[EvidenceReceipt],
    sensitive: list[str],
    warnings: list[str],
) -> GovernanceDecision:
    if "document_search" not in proposal.required_tools:
        return GovernanceDecision(
            proposal_id=proposal.proposal_id,
            decision="reject",
            reason="archive_search_missing_document_search_tool",
            review_required=True,
            receipts_used=[receipt.receipt_id for receipt in receipts],
            warnings=warnings,
        )
    if proposal.claim_policy not in REQUIRED_ARCHIVE_POLICIES:
        return GovernanceDecision(
            proposal_id=proposal.proposal_id,
            decision="reject",
            reason="archive_search_missing_source_bound_policy",
            review_required=True,
            receipts_used=[receipt.receipt_id for receipt in receipts],
            warnings=warnings,
        )
    reason = "archive_search_answer_only_source_bound"
    if sensitive:
        reason = "sensitive_archive_search_answer_only_source_bound"
        warnings.append(f"sensitive_domains={','.join(sensitive)}")
    return GovernanceDecision(
        proposal_id=proposal.proposal_id,
        decision="answer_only",
        reason=reason,
        review_required=False,
        receipts_used=[receipt.receipt_id for receipt in receipts],
        warnings=warnings,
    )


def _decide_fact_candidate(
    proposal: ModelProposal,
    receipts: list[EvidenceReceipt],
    sensitive: list[str],
    policy: AutoPolicy,
    auto_actions_used: int,
    warnings: list[str],
) -> GovernanceDecision:
    if not proposal.slot_id or not proposal.proposed_value:
        return GovernanceDecision(
            proposal_id=proposal.proposal_id,
            decision="reject",
            reason="fact_candidate_missing_slot_or_value",
            review_required=True,
            receipts_used=[receipt.receipt_id for receipt in receipts],
            warnings=warnings,
        )
    if sensitive:
        warnings.append(f"sensitive_domains={','.join(sensitive)}")
        return GovernanceDecision(
            proposal_id=proposal.proposal_id,
            decision="review",
            reason="sensitive_fact_requires_human_review",
            review_required=True,
            receipts_used=[receipt.receipt_id for receipt in receipts],
            warnings=warnings,
        )
    user_receipts = [receipt for receipt in receipts if receipt.authority == "user_current"]
    if policy.mode != "auto":
        return GovernanceDecision(
            proposal_id=proposal.proposal_id,
            decision="review" if policy.mode == "review" else "reject",
            reason=f"learning_mode_{policy.mode}",
            review_required=policy.mode == "review",
            receipts_used=[receipt.receipt_id for receipt in receipts],
            warnings=warnings,
        )
    if proposal.category not in AUTO_ALLOWED_CATEGORIES:
        return GovernanceDecision(
            proposal_id=proposal.proposal_id,
            decision="review",
            reason="category_not_auto_allowed",
            review_required=True,
            receipts_used=[receipt.receipt_id for receipt in receipts],
            warnings=warnings,
        )
    if len(user_receipts) < policy.min_user_receipts_for_auto:
        return GovernanceDecision(
            proposal_id=proposal.proposal_id,
            decision="review",
            reason="insufficient_user_receipts_for_auto",
            review_required=True,
            receipts_used=[receipt.receipt_id for receipt in receipts],
            warnings=warnings,
        )
    if proposal.confidence < policy.min_confidence_for_auto:
        return GovernanceDecision(
            proposal_id=proposal.proposal_id,
            decision="review",
            reason="confidence_below_auto_threshold",
            review_required=True,
            receipts_used=[receipt.receipt_id for receipt in receipts],
            warnings=warnings,
        )
    if auto_actions_used >= policy.max_auto_actions_per_run:
        return GovernanceDecision(
            proposal_id=proposal.proposal_id,
            decision="review",
            reason="auto_rate_limit_reached",
            review_required=True,
            receipts_used=[receipt.receipt_id for receipt in receipts],
            warnings=warnings,
        )
    return GovernanceDecision(
        proposal_id=proposal.proposal_id,
        decision="auto_promote",
        reason="low_risk_repeated_user_evidence_auto_allowed",
        review_required=False,
        memory_write_allowed=True,
        receipts_used=[receipt.receipt_id for receipt in receipts],
        warnings=warnings,
    )


def _decide_prune(
    proposal: ModelProposal,
    receipts: list[EvidenceReceipt],
    policy: AutoPolicy,
    auto_actions_used: int,
    warnings: list[str],
) -> GovernanceDecision:
    if policy.mode != "auto":
        return GovernanceDecision(
            proposal_id=proposal.proposal_id,
            decision="review" if policy.mode == "review" else "reject",
            reason=f"learning_mode_{policy.mode}",
            review_required=policy.mode == "review",
            receipts_used=[receipt.receipt_id for receipt in receipts],
            warnings=warnings,
        )
    if proposal.category != "duplicate_candidate" or not proposal.duplicate_of:
        return GovernanceDecision(
            proposal_id=proposal.proposal_id,
            decision="review",
            reason="prune_requires_duplicate_candidate_reference",
            review_required=True,
            receipts_used=[receipt.receipt_id for receipt in receipts],
            warnings=warnings,
        )
    if auto_actions_used >= policy.max_auto_actions_per_run:
        return GovernanceDecision(
            proposal_id=proposal.proposal_id,
            decision="review",
            reason="auto_rate_limit_reached",
            review_required=True,
            receipts_used=[receipt.receipt_id for receipt in receipts],
            warnings=warnings,
        )
    return GovernanceDecision(
        proposal_id=proposal.proposal_id,
        decision="auto_prune",
        reason="duplicate_candidate_prune_auto_allowed",
        review_required=False,
        receipts_used=[receipt.receipt_id for receipt in receipts],
        warnings=warnings,
    )


def _decide_support_or_route(
    proposal: ModelProposal,
    receipts: list[EvidenceReceipt],
    sensitive: list[str],
    policy: AutoPolicy,
    auto_actions_used: int,
    warnings: list[str],
) -> GovernanceDecision:
    if sensitive:
        warnings.append(f"sensitive_domains={','.join(sensitive)}")
        return GovernanceDecision(
            proposal_id=proposal.proposal_id,
            decision="review",
            reason="sensitive_support_or_route_pattern_requires_review",
            review_required=True,
            receipts_used=[receipt.receipt_id for receipt in receipts],
            warnings=warnings,
        )
    if policy.mode == "auto" and proposal.category in AUTO_ALLOWED_CATEGORIES:
        if proposal.confidence >= policy.min_confidence_for_auto and auto_actions_used < policy.max_auto_actions_per_run:
            return GovernanceDecision(
                proposal_id=proposal.proposal_id,
                decision="auto_promote",
                reason="low_risk_route_or_support_pattern_auto_allowed",
                review_required=False,
                support_pattern_import_allowed=proposal.intent == "support_style",
                receipts_used=[receipt.receipt_id for receipt in receipts],
                warnings=warnings,
            )
    return GovernanceDecision(
        proposal_id=proposal.proposal_id,
        decision="review",
        reason="route_or_support_pattern_review_required",
        review_required=True,
        receipts_used=[receipt.receipt_id for receipt in receipts],
        warnings=warnings,
    )


def _cases() -> list[dict[str, Any]]:
    return [
        {
            "case_id": "archive_health_source_bound",
            "expected": "answer_only",
            "proposal": proposal_from_model_json({
                "proposal_id": "p_archive_health",
                "intent": "archive_search",
                "category": "archive_evidence",
                "proposed_action": "answer_from_sources",
                "sensitive_domains": ["health"],
                "required_tools": ["document_search"],
                "claim_policy": "source_bound_only",
                "confidence": 0.84,
                "evidence_ids": ["doc_health_1"],
            }),
            "receipts": [
                EvidenceReceipt(
                    receipt_id="doc_health_1",
                    source_kind="chatgpt_archive",
                    authority="archive",
                    text="Archive hit mentions health context; source-bounded only.",
                ),
            ],
        },
        {
            "case_id": "archive_health_missing_tool_rejected",
            "expected": "reject",
            "proposal": proposal_from_model_json({
                "proposal_id": "p_archive_no_tool",
                "intent": "archive_search",
                "category": "archive_evidence",
                "proposed_action": "answer_from_sources",
                "sensitive_domains": ["health"],
                "claim_policy": "source_bound_only",
                "confidence": 0.81,
                "evidence_ids": ["doc_health_1"],
            }),
            "receipts": [
                EvidenceReceipt("doc_health_1", "chatgpt_archive", "archive", "Archive hit."),
            ],
        },
        {
            "case_id": "low_risk_preference_auto_promotes",
            "expected": "auto_promote",
            "proposal": proposal_from_model_json({
                "proposal_id": "p_favorite_team",
                "intent": "memory_fact_candidate",
                "category": "low_risk_preference",
                "proposed_action": "promote_candidate",
                "slot_id": "user:favorite_sports_team",
                "proposed_value": "Milwaukee Brewers",
                "confidence": 0.91,
                "evidence_ids": ["u1", "u2"],
            }),
            "receipts": [
                EvidenceReceipt("u1", "chat_turn", "user_current", "I like the Milwaukee Brewers."),
                EvidenceReceipt("u2", "chat_turn", "user_current", "The Brewers are my favorite team."),
            ],
        },
        {
            "case_id": "single_receipt_preference_stays_review",
            "expected": "review",
            "proposal": proposal_from_model_json({
                "proposal_id": "p_favorite_drink_single",
                "intent": "memory_fact_candidate",
                "category": "low_risk_preference",
                "proposed_action": "promote_candidate",
                "slot_id": "user:favorite_drink",
                "proposed_value": "iced coffee",
                "confidence": 0.86,
                "evidence_ids": ["u1"],
            }),
            "receipts": [
                EvidenceReceipt("u1", "chat_turn", "user_current", "I also like iced coffee."),
            ],
        },
        {
            "case_id": "health_fact_never_auto_promotes",
            "expected": "review",
            "proposal": proposal_from_model_json({
                "proposal_id": "p_health_fact",
                "intent": "memory_fact_candidate",
                "category": "low_risk_preference",
                "proposed_action": "promote_candidate",
                "slot_id": "user:health_history",
                "proposed_value": "leukemia survivor",
                "sensitive_domains": ["health"],
                "confidence": 0.95,
                "evidence_ids": ["u1", "u2"],
            }),
            "receipts": [
                EvidenceReceipt("u1", "chat_turn", "user_current", "I had leukemia."),
                EvidenceReceipt("u2", "chat_turn", "user_current", "I am a leukemia survivor."),
            ],
        },
        {
            "case_id": "duplicate_candidate_auto_prunes",
            "expected": "auto_prune",
            "proposal": proposal_from_model_json({
                "proposal_id": "p_duplicate",
                "intent": "memory_fact_candidate",
                "category": "duplicate_candidate",
                "proposed_action": "prune_duplicate",
                "duplicate_of": "candidate_existing",
                "confidence": 0.9,
                "evidence_ids": ["trace_duplicate"],
            }),
            "receipts": [
                EvidenceReceipt("trace_duplicate", "trace", "tool", "Same slot/value candidate already queued."),
            ],
        },
    ]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=["off", "review", "auto"], default="auto")
    parser.add_argument("--out", type=Path, default=None)
    args = parser.parse_args(argv)
    result = run_lab(AutoPolicy(mode=args.mode))
    text = json.dumps(result, indent=2, sort_keys=True)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(text + "\n", encoding="utf-8")
    else:
        print(text)
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
