"""
Structured prompts for the three cloud feature tasks.
Each returns a (system_prompt, user_prompt) tuple ready to send to a provider.
"""
from __future__ import annotations

import json
from typing import Any, Dict, List


# ── Slot Classification ─────────────────────────────────────────

SLOT_CLASSIFICATION_SYSTEM = """You are a fact classification engine for a personal AI memory system.
Given a user statement, determine if it contains a personal fact that should be stored.
If it does, classify the fact into a slot with properties.

Respond with valid JSON only. No explanation outside the JSON."""

def slot_classification_prompt(
    statement: str,
    existing_slots: List[str],
) -> tuple[str, str]:
    """Build prompt for classifying a user statement into a memory slot."""
    user_prompt = json.dumps({
        "task": "classify_slot",
        "user_statement": statement,
        "existing_slots": existing_slots,
        "instructions": (
            "Analyze the user statement. If it contains a personal fact, return a classification. "
            "If it does NOT contain a storable fact, return {\"contains_fact\": false}. "
            "If it DOES contain a fact, return: "
            "{\"contains_fact\": true, \"slot_name\": \"<snake_case>\", "
            "\"value\": \"<extracted value>\", "
            "\"exclusive\": <true if only one value possible, false if additive>, "
            "\"safety_critical\": <true if forgetting/contradicting could cause harm>, "
            "\"category\": \"<identity|preference|medical|relationship|schedule|location|other>\", "
            "\"confidence\": <0.0-1.0>}"
        ),
    }, indent=2)
    return SLOT_CLASSIFICATION_SYSTEM, user_prompt


# ── Test cases for slot classification
SLOT_TEST_CASES = [
    {
        "statement": "I'm deathly allergic to peanuts",
        "existing_slots": ["name", "location", "employer", "favorite_color"],
        "expected": {"contains_fact": True, "safety_critical": True, "category": "medical"},
    },
    {
        "statement": "My daughter's name is Maya",
        "existing_slots": ["name", "location", "employer"],
        "expected": {"contains_fact": True, "exclusive": True, "category": "relationship"},
    },
    {
        "statement": "How's the weather today?",
        "existing_slots": ["name", "location"],
        "expected": {"contains_fact": False},
    },
    {
        "statement": "I've been playing guitar for about 15 years now",
        "existing_slots": ["name", "hobbies"],
        "expected": {"contains_fact": True, "exclusive": False},
    },
]


# ── NLI Contradiction Detection ──────────────────────────────────

NLI_SYSTEM = """You are a natural language inference engine for a personal AI memory system.
Given two facts stored about a user, determine their logical relationship.
Focus on whether they can both be true simultaneously.

Respond with valid JSON only. No explanation outside the JSON."""

def nli_contradiction_prompt(fact_a: str, fact_b: str) -> tuple[str, str]:
    """Build prompt for checking contradiction between two facts."""
    user_prompt = json.dumps({
        "task": "nli_check",
        "fact_a": fact_a,
        "fact_b": fact_b,
        "instructions": (
            "Determine the relationship between these two user facts. Return: "
            "{\"relation\": \"entailment|contradiction|neutral\", "
            "\"confidence\": <0.0-1.0>, "
            "\"explanation\": \"<one sentence>\", "
            "\"severity\": \"<critical|moderate|low>\" if contradiction}"
        ),
    }, indent=2)
    return NLI_SYSTEM, user_prompt


# ── Test cases for NLI
NLI_TEST_CASES = [
    {
        "fact_a": "User's favorite color is orange",
        "fact_b": "User's favorite color is yellow",
        "expected": {"relation": "contradiction", "severity": "low"},
    },
    {
        "fact_a": "User is allergic to peanuts",
        "fact_b": "User enjoys Thai food with peanut sauce",
        "expected": {"relation": "contradiction", "severity": "critical"},
    },
    {
        "fact_a": "User works at Google",
        "fact_b": "User is a software engineer",
        "expected": {"relation": "neutral"},
    },
    {
        "fact_a": "User lives in Portland",
        "fact_b": "User moved to Seattle last month",
        "expected": {"relation": "contradiction", "severity": "moderate"},
    },
]


# ── Reflection Validation ────────────────────────────────────────

REFLECTION_SYSTEM = """You are an epistemic auditor for an AI self-reflection system.
Given evidence (gate failures, corrections, trust changes) and a proposed self-model update,
determine if the update is justified by the evidence.

Respond with valid JSON only. No explanation outside the JSON."""

def reflection_validation_prompt(
    evidence: List[Dict[str, Any]],
    proposed_update: Dict[str, Any],
) -> tuple[str, str]:
    """Build prompt for validating a self-model update against evidence."""
    user_prompt = json.dumps({
        "task": "validate_reflection",
        "evidence": evidence,
        "proposed_self_model_update": proposed_update,
        "instructions": (
            "Evaluate whether the proposed self-model update is justified by the evidence. "
            "Check for: over-generalization, insufficient evidence, smoothing over real issues, "
            "or claiming improvement without supporting data. Return: "
            "{\"valid\": <true|false>, "
            "\"confidence\": <0.0-1.0>, "
            "\"concerns\": [\"<list of specific concerns if any>\"], "
            "\"suggestion\": \"<how to improve the update if invalid>\"}"
        ),
    }, indent=2)
    return REFLECTION_SYSTEM, user_prompt


# ── Test cases for reflection validation
REFLECTION_TEST_CASES = [
    {
        "evidence": [
            {"type": "gate_failure", "count": 5, "domain": "medical_facts", "period": "24h"},
            {"type": "user_correction", "count": 3, "domain": "medical_facts", "period": "24h"},
            {"type": "trust_delta", "domain": "medical_facts", "delta": -0.15},
        ],
        "proposed_update": {
            "uncertainty_domains": {"medical_facts": "high"},
            "correction_trend": "increasing in medical domain",
            "proposed_action": "raise verification threshold for medical claims",
        },
        "expected": {"valid": True},
    },
    {
        "evidence": [
            {"type": "gate_failure", "count": 1, "domain": "general", "period": "24h"},
        ],
        "proposed_update": {
            "uncertainty_domains": {"all_domains": "high"},
            "correction_trend": "system is fundamentally unreliable",
            "proposed_action": "add disclaimers to all responses",
        },
        "expected": {"valid": False, "concern": "over-generalization"},
    },
]
