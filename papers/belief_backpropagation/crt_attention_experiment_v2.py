"""CRT Attention Bias Experiment v2 — via Ollama

Uses llama3.2 (3B) which can actually follow instructions.
Two conditions per scenario:
  - Baseline: facts presented flat, no trust info
  - Trust-biased: facts annotated with trust, ordered by trust,
    high-trust repeated, low-trust marked unverified

Tests whether trust-structured prompting improves factual faithfulness.

Run: python papers/belief_backpropagation/crt_attention_experiment_v2.py
"""

import sys
sys.path.insert(0, r"D:\AI_round2")

import json
import time
import requests
import numpy as np

OLLAMA_URL = "http://localhost:11434/api/generate"
MODEL = "llama3.2"


def generate(prompt, max_tokens=80):
    """Generate from Ollama, return text."""
    try:
        r = requests.post(OLLAMA_URL, json={
            "model": MODEL,
            "prompt": prompt,
            "stream": False,
            "options": {"num_predict": max_tokens, "temperature": 0.3, "num_ctx": 2048}
        }, timeout=30)
        return r.json().get("response", "").strip()
    except Exception as e:
        return f"[ERROR: {e}]"


def score_response(response, correct_signals, wrong_signals):
    resp_lower = response.lower()
    correct_hits = sum(1 for s in correct_signals if s.lower() in resp_lower)
    wrong_hits = sum(1 for s in wrong_signals if s.lower() in resp_lower)
    correct_pct = correct_hits / max(len(correct_signals), 1)
    wrong_pct = wrong_hits / max(len(wrong_signals), 1)
    return correct_pct, wrong_pct


SCENARIOS = [
    {
        "name": "Employment (corrected fact)",
        "facts": [
            ("The user works at a design studio downtown.", 0.20),
            ("The user does NOT work at a design studio. This was a correction.", 0.70),
            ("The user left their previous job a year ago to build an AI project.", 0.65),
            ("The user considers themselves self-employed.", 0.60),
        ],
        "query": "Where does the user currently work?",
        "correct_signals": ["not", "self-employed", "left", "doesn't", "no longer", "freelance", "own", "ai project"],
        "wrong_signals": ["design studio"],
    },
    {
        "name": "Favorite color (contradiction)",
        "facts": [
            ("The user once said their favorite color is green.", 0.15),
            ("The user's favorite color is orange.", 0.90),
            ("The user has confirmed orange multiple times.", 0.85),
            ("Orange has personal significance to the user.", 0.80),
        ],
        "query": "What is the user's favorite color?",
        "correct_signals": ["orange"],
        "wrong_signals": ["green"],
    },
    {
        "name": "Coffee preference (evolved)",
        "facts": [
            ("The user said they never liked coffee.", 0.25),
            ("The user has recently been drinking iced coffees.", 0.60),
            ("The user is looking for an espresso maker.", 0.55),
        ],
        "query": "Does the user like coffee?",
        "correct_signals": ["yes", "iced", "espresso", "recently", "started", "now", "does", "enjoys"],
        "wrong_signals": ["never", "doesn't like", "does not like", "no"],
    },
    {
        "name": "Health to work (cross-domain)",
        "facts": [
            ("The user has a chronic health condition.", 0.85),
            ("The condition makes overnight shifts very difficult.", 0.70),
            ("The user left their overnight stocking job because of this.", 0.65),
            ("The user is now self-employed building technology.", 0.60),
        ],
        "query": "Why did the user leave their job?",
        "correct_signals": ["health", "condition", "difficult", "chronic", "overnight", "medical"],
        "wrong_signals": ["fired", "bored", "better opportunity", "promotion"],
    },
    {
        "name": "Name (high trust anchor)",
        "facts": [
            ("Someone mentioned the user might be called Mike.", 0.10),
            ("The user's name is Nick.", 0.95),
            ("The user has confirmed their name is Nick many times.", 0.90),
        ],
        "query": "What is the user's name?",
        "correct_signals": ["nick"],
        "wrong_signals": ["mike"],
    },
]


def run_experiment():
    print("=" * 70)
    print("EXPERIMENT A: CRT Trust Bias vs Baseline")
    print(f"Model: {MODEL} via Ollama")
    print("=" * 70)

    n_runs = 3
    results = []

    for scenario in SCENARIOS:
        print(f"\n{'='*50}")
        print(f"  {scenario['name']}")
        print(f"{'='*50}")

        # BASELINE: flat facts, no trust info
        baseline_prompt = "You are answering questions about a user based on stored facts.\n\nFacts:\n"
        for fact_text, _ in scenario["facts"]:
            baseline_prompt += f"- {fact_text}\n"
        baseline_prompt += f"\n{scenario['query']} Give a short, direct answer."

        # TRUST-BIASED: facts annotated and structured by trust
        sorted_facts = sorted(scenario["facts"], key=lambda x: x[1])
        biased_prompt = "You are answering questions about a user based on stored facts. Each fact has a trust score (0.0 to 1.0). Higher trust means more reliable. Prefer high-trust facts over low-trust ones.\n\nFacts:\n"
        for fact_text, trust in sorted_facts:
            biased_prompt += f"- [trust: {trust:.2f}] {fact_text}\n"
        # Repeat highest trust fact
        best = max(scenario["facts"], key=lambda x: x[1])
        biased_prompt += f"\nMost reliable fact (trust {best[1]:.2f}): {best[0]}\n"
        biased_prompt += f"\n{scenario['query']} Prefer the highest-trust facts. Give a short, direct answer."

        baseline_scores = []
        biased_scores = []

        for run in range(n_runs):
            # Baseline
            base_resp = generate(baseline_prompt)
            bc, bw = score_response(base_resp, scenario["correct_signals"], scenario["wrong_signals"])
            baseline_scores.append({"correct": bc, "wrong": bw, "text": base_resp})

            # Trust-biased
            bias_resp = generate(biased_prompt)
            tc, tw = score_response(bias_resp, scenario["correct_signals"], scenario["wrong_signals"])
            biased_scores.append({"correct": tc, "wrong": tw, "text": bias_resp})

        avg_bc = np.mean([s["correct"] for s in baseline_scores])
        avg_bw = np.mean([s["wrong"] for s in baseline_scores])
        avg_tc = np.mean([s["correct"] for s in biased_scores])
        avg_tw = np.mean([s["wrong"] for s in biased_scores])

        print(f"\n  Baseline:     correct={avg_bc:.2f}  wrong={avg_bw:.2f}")
        print(f"  Trust-biased: correct={avg_tc:.2f}  wrong={avg_tw:.2f}")
        print(f"  Delta:        correct={avg_tc-avg_bc:+.2f}  wrong={avg_tw-avg_bw:+.2f}")

        # Show best example from each
        print(f"\n  Baseline:  \"{baseline_scores[0]['text'][:200]}\"")
        print(f"  Biased:    \"{biased_scores[0]['text'][:200]}\"")

        results.append({
            "name": scenario["name"],
            "baseline_correct": avg_bc,
            "baseline_wrong": avg_bw,
            "biased_correct": avg_tc,
            "biased_wrong": avg_tw,
        })

    # Summary
    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)

    n = len(results)
    avg_baseline_c = np.mean([r["baseline_correct"] for r in results])
    avg_baseline_w = np.mean([r["baseline_wrong"] for r in results])
    avg_biased_c = np.mean([r["biased_correct"] for r in results])
    avg_biased_w = np.mean([r["biased_wrong"] for r in results])

    print(f"  Baseline avg:     correct={avg_baseline_c:.3f}  wrong={avg_baseline_w:.3f}")
    print(f"  Trust-biased avg: correct={avg_biased_c:.3f}  wrong={avg_biased_w:.3f}")
    print(f"\n  Correct improvement: {avg_biased_c - avg_baseline_c:+.3f}")
    print(f"  Wrong reduction:     {avg_baseline_w - avg_biased_w:+.3f}")

    wins = sum(1 for r in results if r["biased_correct"] > r["baseline_correct"])
    ties = sum(1 for r in results if r["biased_correct"] == r["baseline_correct"])
    losses = sum(1 for r in results if r["biased_correct"] < r["baseline_correct"])
    print(f"\n  Wins: {wins}  Ties: {ties}  Losses: {losses}")

    if avg_biased_c > avg_baseline_c and avg_biased_w <= avg_baseline_w:
        print("\n  SIGNAL: Trust-structured prompting improves faithfulness.")
    elif avg_biased_c > avg_baseline_c:
        print("\n  MIXED SIGNAL: More correct but also more wrong signals.")
    elif avg_biased_c == avg_baseline_c and avg_biased_w < avg_baseline_w:
        print("\n  SIGNAL: Same correct signals but fewer wrong signals.")
    else:
        print("\n  NO SIGNAL at this model size.")

    # Per-scenario breakdown
    print("\n  Per-scenario:")
    for r in results:
        delta = r["biased_correct"] - r["baseline_correct"]
        marker = "+" if delta > 0 else ("=" if delta == 0 else "-")
        print(f"    [{marker}] {r['name']:35s}  baseline={r['baseline_correct']:.2f}  biased={r['biased_correct']:.2f}  delta={delta:+.2f}")


if __name__ == "__main__":
    run_experiment()
