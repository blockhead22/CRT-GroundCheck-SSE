#!/usr/bin/env python3
"""
Cloud provider test harness — CLI runner.

Usage:
    python tests/cloud_providers/run_all.py --provider openai
    python tests/cloud_providers/run_all.py --provider ccproxy
    python tests/cloud_providers/run_all.py --provider cookie
    python tests/cloud_providers/run_all.py --provider all
    python tests/cloud_providers/run_all.py --list          # show available providers
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

# Add project root to path so we can load .env
project_root = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(project_root))

# Load .env file
env_path = project_root / ".env"
if env_path.exists():
    for line in env_path.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, _, value = line.partition("=")
            os.environ[key.strip()] = value.strip()

from tests.cloud_providers.providers import get_provider, get_available_providers, CloudProvider, ProviderResult
from tests.cloud_providers.prompts import (
    slot_classification_prompt, SLOT_TEST_CASES,
    nli_contradiction_prompt, NLI_TEST_CASES,
    reflection_validation_prompt, REFLECTION_TEST_CASES,
)


# ── Colors ───────────────────────────────────────────────────────

GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
CYAN = "\033[96m"
DIM = "\033[2m"
BOLD = "\033[1m"
RESET = "\033[0m"


def status_icon(result: ProviderResult) -> str:
    if result.error:
        return f"{RED}FAIL{RESET}"
    if result.parsed is not None:
        return f"{GREEN}OK{RESET}"
    return f"{YELLOW}WARN{RESET}"


def fmt_cost(cost: float) -> str:
    if cost == 0:
        return f"{DIM}$0 (sub){RESET}"
    return f"${cost:.6f}"


def fmt_tokens(tokens: int) -> str:
    if tokens == 0:
        return f"{DIM}n/a{RESET}"
    return str(tokens)


# ── Test Runners ─────────────────────────────────────────────────

def run_slot_tests(provider: CloudProvider) -> list[ProviderResult]:
    results = []
    for i, case in enumerate(SLOT_TEST_CASES):
        system, prompt = slot_classification_prompt(case["statement"], case["existing_slots"])
        result = provider.complete(system, prompt)
        results.append(result)
        icon = status_icon(result)
        print(f"  Slot #{i+1}: {icon}  {case['statement'][:50]}...")
        if result.parsed:
            print(f"    → {json.dumps(result.parsed, indent=None)[:120]}")
        if result.error:
            print(f"    {RED}Error: {result.error}{RESET}")
        print(f"    {DIM}{fmt_tokens(result.tokens_used)} tokens | {fmt_cost(result.cost_est)} | {result.latency_ms:.0f}ms{RESET}")
    return results


def run_nli_tests(provider: CloudProvider) -> list[ProviderResult]:
    results = []
    for i, case in enumerate(NLI_TEST_CASES):
        system, prompt = nli_contradiction_prompt(case["fact_a"], case["fact_b"])
        result = provider.complete(system, prompt)
        results.append(result)
        icon = status_icon(result)
        print(f"  NLI  #{i+1}: {icon}  {case['fact_a'][:30]} vs {case['fact_b'][:30]}")
        if result.parsed:
            rel = result.parsed.get("relation", "?")
            conf = result.parsed.get("confidence", "?")
            print(f"    → {rel} (confidence: {conf})")
        if result.error:
            print(f"    {RED}Error: {result.error}{RESET}")
        print(f"    {DIM}{fmt_tokens(result.tokens_used)} tokens | {fmt_cost(result.cost_est)} | {result.latency_ms:.0f}ms{RESET}")
    return results


def run_reflection_tests(provider: CloudProvider) -> list[ProviderResult]:
    results = []
    for i, case in enumerate(REFLECTION_TEST_CASES):
        system, prompt = reflection_validation_prompt(case["evidence"], case["proposed_update"])
        result = provider.complete(system, prompt)
        results.append(result)
        icon = status_icon(result)
        valid_str = result.parsed.get("valid", "?") if result.parsed else "?"
        print(f"  Refl #{i+1}: {icon}  valid={valid_str}")
        if result.parsed:
            concerns = result.parsed.get("concerns", [])
            if concerns:
                print(f"    → Concerns: {concerns[:2]}")
        if result.error:
            print(f"    {RED}Error: {result.error}{RESET}")
        print(f"    {DIM}{fmt_tokens(result.tokens_used)} tokens | {fmt_cost(result.cost_est)} | {result.latency_ms:.0f}ms{RESET}")
    return results


# ── Summary ──────────────────────────────────────────────────────

def print_summary(provider_name: str, all_results: list[ProviderResult]):
    total_tokens = sum(r.tokens_used for r in all_results)
    total_cost = sum(r.cost_est for r in all_results)
    total_time = sum(r.latency_ms for r in all_results)
    ok_count = sum(1 for r in all_results if r.parsed is not None and not r.error)
    fail_count = sum(1 for r in all_results if r.error)
    total = len(all_results)

    print(f"\n{'='*60}")
    print(f"{BOLD}Summary: {provider_name}{RESET}")
    print(f"  Tests:  {ok_count}/{total} passed, {fail_count} failed")
    print(f"  Tokens: {total_tokens}")
    print(f"  Cost:   {fmt_cost(total_cost)}")
    print(f"  Time:   {total_time:.0f}ms total ({total_time/max(total,1):.0f}ms avg)")
    print(f"{'='*60}")


# ── Main ─────────────────────────────────────────────────────────

def run_for_provider(provider: CloudProvider):
    print(f"\n{BOLD}{CYAN}=== Testing provider: {provider.name} ==={RESET}")
    all_results = []

    print(f"\n{BOLD}── Slot Classification ──{RESET}")
    all_results.extend(run_slot_tests(provider))

    print(f"\n{BOLD}── NLI Contradiction Detection ──{RESET}")
    all_results.extend(run_nli_tests(provider))

    print(f"\n{BOLD}── Reflection Validation ──{RESET}")
    all_results.extend(run_reflection_tests(provider))

    print_summary(provider.name, all_results)
    return all_results


def main():
    parser = argparse.ArgumentParser(description="Cloud provider test harness")
    parser.add_argument("--provider", "-p", default="openai",
                        help="Provider to test: openai, ccproxy, cookie, all")
    parser.add_argument("--list", "-l", action="store_true",
                        help="List available providers")
    args = parser.parse_args()

    if args.list:
        available = get_available_providers()
        print(f"{BOLD}Available providers:{RESET}")
        for p in available:
            print(f"  {GREEN}●{RESET} {p.name}")
        from tests.cloud_providers.providers import PROVIDERS
        for name in PROVIDERS:
            if not any(p.name == name for p in available):
                print(f"  {RED}○{RESET} {name} (not configured)")
        return

    if args.provider == "all":
        available = get_available_providers()
        if not available:
            print(f"{RED}No providers available. Check your API keys and environment.{RESET}")
            return
        all_provider_results = {}
        for p in available:
            all_provider_results[p.name] = run_for_provider(p)

        # Comparison table
        if len(all_provider_results) > 1:
            print(f"\n{BOLD}{CYAN}=== Comparison ==={RESET}")
            for name, results in all_provider_results.items():
                ok = sum(1 for r in results if r.parsed and not r.error)
                cost = sum(r.cost_est for r in results)
                time_ms = sum(r.latency_ms for r in results)
                print(f"  {name:12s}  {ok}/{len(results)} passed  {fmt_cost(cost):>12s}  {time_ms:.0f}ms")
    else:
        provider = get_provider(args.provider)
        if not provider.is_available():
            print(f"{RED}Provider '{args.provider}' is not available.{RESET}")
            print(f"Check configuration. Run with --list to see available providers.")
            return
        run_for_provider(provider)


if __name__ == "__main__":
    main()
