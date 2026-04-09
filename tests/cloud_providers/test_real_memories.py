#!/usr/bin/env python3
"""
Test cloud features against real system memories.
Uses actual Nick/Aether facts from CRT sessions.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

project_root = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(project_root))

# Load env
for line in (project_root / ".env").read_text().splitlines():
    line = line.strip()
    if line and not line.startswith("#") and "=" in line:
        key, _, value = line.partition("=")
        os.environ[key.strip()] = value.strip()

from tests.cloud_providers.providers import get_provider, get_available_providers
from tests.cloud_providers.prompts import (
    slot_classification_prompt,
    nli_contradiction_prompt,
    reflection_validation_prompt,
)

GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
CYAN = "\033[96m"
DIM = "\033[2m"
BOLD = "\033[1m"
RESET = "\033[0m"


# ═══════════════════════════════════════════════════════════════════
# REAL MEMORIES — sourced from actual CRT/Aether sessions
# ═══════════════════════════════════════════════════════════════════

REAL_EXISTING_SLOTS = [
    "name", "employer", "location", "favorite_color", "occupation",
    "hobbies", "email", "preferred_name", "work_plan",
]

# ── Slot Classification: Real user statements Aether has seen ────
REAL_SLOT_CASES = [
    {
        "label": "Nick's career background",
        "statement": "I am a web developer, filmmaker, and print shop maker through The Printing Lair",
        "notes": "Multi-value occupation — should create additive slots",
    },
    {
        "label": "Nick's disability context",
        "statement": "I have chronic pain issues and I'm on disability",
        "notes": "Medical/personal — safety_critical should be True",
    },
    {
        "label": "Nick's camera gear",
        "statement": "I use a DJI Mic 2 with the 3.5mm lav input on the transmitter",
        "notes": "Equipment fact — new slot type not in existing list",
    },
    {
        "label": "Nick's project identity",
        "statement": "I've been building CRT and Aether for about a year now, it's a personal AI memory system",
        "notes": "Project fact — long-running context",
    },
    {
        "label": "Stoner acknowledgment",
        "statement": "Nick is a stoner and he will get lost without documentation",
        "notes": "Self-described trait — preference/behavioral, not medical",
    },
]

# ── NLI: Real contradictions from the system ─────────────────────
REAL_NLI_CASES = [
    {
        "label": "The favorite color wars",
        "fact_a": "FACT: User.favorite_color = yellow (trust: 0.80)",
        "fact_b": "FACT: User.favorite_color = orange (trust: 0.75)",
        "notes": "This actually happened — 46 entries at one point",
    },
    {
        "label": "Always orange vs just orange",
        "fact_a": "FACT: User.favorite_color = orange",
        "fact_b": "Aether, its always orange. my favorite color is always orange. [Self-awareness -- internal calibration only]",
        "notes": "The second is polluted with internal calibration text",
    },
    {
        "label": "Name confusion from display bug",
        "fact_a": "FACT: name = Nick Block",
        "fact_b": "FACT: name = Nick remember",
        "notes": "Registration display name bug leaked into memory",
    },
    {
        "label": "Occupation update vs old fact",
        "fact_a": "FACT: occupation = web developer",
        "fact_b": "FACT: occupation = freelance developer building AI systems",
        "notes": "Evolution, not contradiction — should be neutral or update",
    },
    {
        "label": "System self-description drift",
        "fact_a": "Aether is a personal AI assistant with memory and trust systems",
        "fact_b": "I'm a system, not a person! Here's how I operate today and always: Core Capabilities 1. GroundCheck Memory...",
        "notes": "First is grounded self-description, second is generic LLM filler",
    },
]

# ── Reflection: Real self-model scenarios ────────────────────────
REAL_REFLECTION_CASES = [
    {
        "label": "Reasoning leak pattern",
        "evidence": [
            {"type": "gate_failure", "count": 8, "domain": "response_formatting", "period": "24h",
             "detail": "Chain-of-thought reasoning dumped as visible response instead of routing to thinking trace"},
            {"type": "user_correction", "count": 3, "domain": "response_formatting", "period": "24h",
             "detail": "User said 'broken still' and 'oof' after seeing reasoning in response"},
            {"type": "pattern", "description": "Qwen3 model outputs <think> blocks that are not being filtered by the response pipeline"},
        ],
        "proposed_update": {
            "uncertainty_domains": {"response_formatting": "critical"},
            "correction_trend": "reasoning leak is the #1 UX failure, affects every interaction",
            "proposed_action": "flag all responses for think-tag filtering before delivery",
        },
        "notes": "This is the actual reasoning leak bug from today's session",
    },
    {
        "label": "Memory pollution self-assessment",
        "evidence": [
            {"type": "memory_audit", "finding": "46 duplicate entries for favorite_color",
             "detail": "Trust scores ranged 0.70-0.95, none deprecated"},
            {"type": "memory_audit", "finding": "Internal calibration text leaked into stored memories",
             "detail": "[Self-awareness — internal calibration only] found in cited memories"},
            {"type": "user_correction", "count": 5, "domain": "memory_accuracy", "period": "48h"},
        ],
        "proposed_update": {
            "uncertainty_domains": {"memory_storage": "high", "all_domains": "moderate"},
            "correction_trend": "memory system is storing garbage alongside real facts",
            "proposed_action": "distrust all memories until audit complete, add disclaimers to responses",
        },
        "notes": "Tests whether the model catches over-generalization — memory storage is broken but not ALL domains are unreliable",
    },
]


def run_test(provider, label, system_prompt, user_prompt, notes=""):
    result = provider.complete(system_prompt, user_prompt)
    ok = result.parsed is not None and not result.error
    icon = f"{GREEN}OK{RESET}" if ok else f"{RED}FAIL{RESET}"
    print(f"\n  {icon}  {label}")
    if notes:
        print(f"    {DIM}Context: {notes}{RESET}")
    if result.parsed:
        # Pretty print key fields
        p = result.parsed
        for key in ["contains_fact", "slot_name", "safety_critical", "exclusive",
                     "relation", "confidence", "severity", "valid", "concerns"]:
            if key in p:
                val = p[key]
                if isinstance(val, list):
                    val = val[:2]  # truncate long lists
                print(f"    {key}: {val}")
    elif result.content:
        print(f"    Raw: {result.content[:200]}")
    if result.error:
        print(f"    {RED}Error: {result.error}{RESET}")
    print(f"    {DIM}{result.tokens_used} tokens | ${result.cost_est:.6f} | {result.latency_ms:.0f}ms{RESET}")
    return result


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--provider", "-p", default="openai")
    args = parser.parse_args()

    provider = get_provider(args.provider)
    if not provider.is_available():
        print(f"{RED}Provider '{args.provider}' not available{RESET}")
        return

    all_results = []

    # ── Slot Classification ──
    print(f"\n{BOLD}{CYAN}=== SLOT CLASSIFICATION — Real User Statements ==={RESET}")
    for case in REAL_SLOT_CASES:
        sys_p, usr_p = slot_classification_prompt(case["statement"], REAL_EXISTING_SLOTS)
        r = run_test(provider, case["label"], sys_p, usr_p, case.get("notes", ""))
        all_results.append(r)

    # ── NLI Contradiction ──
    print(f"\n{BOLD}{CYAN}=== NLI CONTRADICTION — Real Memory Conflicts ==={RESET}")
    for case in REAL_NLI_CASES:
        sys_p, usr_p = nli_contradiction_prompt(case["fact_a"], case["fact_b"])
        r = run_test(provider, case["label"], sys_p, usr_p, case.get("notes", ""))
        all_results.append(r)

    # ── Reflection Validation ──
    print(f"\n{BOLD}{CYAN}=== REFLECTION VALIDATION — Real Self-Model Scenarios ==={RESET}")
    for case in REAL_REFLECTION_CASES:
        sys_p, usr_p = reflection_validation_prompt(case["evidence"], case["proposed_update"])
        r = run_test(provider, case["label"], sys_p, usr_p, case.get("notes", ""))
        all_results.append(r)

    # ── Summary ──
    ok_count = sum(1 for r in all_results if r.parsed and not r.error)
    total_tokens = sum(r.tokens_used for r in all_results)
    total_cost = sum(r.cost_est for r in all_results)
    total_time = sum(r.latency_ms for r in all_results)

    print(f"\n{'='*60}")
    print(f"{BOLD}Results: {provider.name}{RESET}")
    print(f"  Passed:  {ok_count}/{len(all_results)}")
    print(f"  Tokens:  {total_tokens}")
    print(f"  Cost:    ${total_cost:.6f}")
    print(f"  Time:    {total_time:.0f}ms ({total_time/len(all_results):.0f}ms avg)")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
