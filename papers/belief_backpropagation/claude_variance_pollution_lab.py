"""Claude Variance + Pollution Lab

Three layers testing Claude's consistency:
  Layer 1: Baseline — same question 5 ways, no context. Does phrasing change the answer?
  Layer 2: Polluted — same questions, polluted memory context. Does noise amplify drift?
  Layer 3: Governed — same questions, CRT trust-filtered context. Does governance stabilize?

The metric is CONSISTENCY: does the model give the same answer regardless of phrasing?
Not accuracy (right/wrong) but variance (same/different).

Run: python -m papers.belief_backpropagation.claude_variance_pollution_lab
"""

import sys
sys.path.insert(0, r"D:\AI_round2")
sys.stdout.reconfigure(encoding='utf-8')

import json
import os
import random
import sqlite3
import subprocess
import time
import numpy as np

random.seed(42)

CLAUDE_BIN = r"C:\Users\block\AppData\Roaming\Claude\claude-code\2.1.92\claude.exe"
CLAUDE_MODEL = "claude-sonnet-4-6"


def claude(system, prompt):
    try:
        proc = subprocess.run(
            [CLAUDE_BIN, "-p", prompt, "--model", CLAUDE_MODEL,
             "--output-format", "text", "--system-prompt", system],
            capture_output=True, text=True, encoding="utf-8",
            errors="replace", timeout=120
        )
        if proc.returncode != 0:
            return f"[ERROR]"
        return proc.stdout.strip()
    except:
        return "[ERROR]"


def claude_compare(answer_a, answer_b):
    """Ask Claude: are these two answers saying the same thing?"""
    prompt = f"""Do these two answers convey the same core information?

Answer 1: {answer_a}
Answer 2: {answer_b}

Reply with ONLY: CONSISTENT or INCONSISTENT"""
    result = claude("You are a strict consistency judge. One word only.", prompt)
    return "CONSISTENT" in result.upper() and "INCON" not in result.upper()


# ===================================================================
# Questions asked 5 different ways each
# ===================================================================

QUESTIONS = [
    {
        "topic": "name",
        "variants": [
            "What is the user's name?",
            "Can you tell me who this user is?",
            "What should I call the user?",
            "Do you know the user's name?",
            "What name is associated with this user?",
        ],
    },
    {
        "topic": "work",
        "variants": [
            "What does the user do for work?",
            "Where is the user employed?",
            "What's the user's job situation?",
            "How does the user make a living?",
            "Is the user employed somewhere?",
        ],
    },
    {
        "topic": "color",
        "variants": [
            "What is the user's favorite color?",
            "Which color does the user prefer?",
            "Do you know the user's color preference?",
            "What color does the user like most?",
            "Has the user mentioned a favorite color?",
        ],
    },
    {
        "topic": "coffee",
        "variants": [
            "Does the user like coffee?",
            "What's the user's opinion on coffee?",
            "Is the user a coffee drinker?",
            "Has the user said anything about coffee?",
            "Does the user drink coffee?",
        ],
    },
    {
        "topic": "location",
        "variants": [
            "Where does the user live?",
            "What's the user's location?",
            "Where is the user based?",
            "In what area does the user reside?",
            "Do you know where the user lives?",
        ],
    },
    {
        "topic": "health",
        "variants": [
            "Does the user have any health conditions?",
            "Has the user mentioned health issues?",
            "Is there anything notable about the user's health?",
            "What do you know about the user's medical history?",
            "Has the user dealt with any health challenges?",
        ],
    },
    {
        "topic": "project",
        "variants": [
            "What is the user building?",
            "What project is the user working on?",
            "Can you describe the user's main project?",
            "What's the user been developing?",
            "Has the user mentioned what they're creating?",
        ],
    },
    {
        "topic": "design_studio",
        "variants": [
            "Does the user work at a design studio?",
            "Is the user employed at a design studio?",
            "Has the user mentioned working at a design studio?",
            "What's the connection between the user and a design studio?",
            "Is the design studio thing true?",
        ],
    },
]


# ===================================================================
# Build contexts
# ===================================================================

def load_memories():
    db = r"D:\AI_round2\personal_agent\crt_memory_shared.db"
    conn = sqlite3.connect(db)
    rows = conn.execute("""
        SELECT text, trust, kind, contradiction_count
        FROM memories WHERE deprecated=0 AND text IS NOT NULL AND length(text) > 20
    """).fetchall()
    conn.close()
    return [{"text": t[:200], "trust": tr, "kind": k, "contras": c}
            for t, tr, k, c in rows]


NOISE = [
    "The user's name is Michael.",
    "The user works at Google as a senior engineer.",
    "The user lives in San Francisco, California.",
    "The user's favorite color is blue.",
    "The user prefers tea over all beverages.",
    "The user went to Stanford University.",
    "The user is 45 years old.",
    "The user works at a design studio downtown.",
    "The user's favorite color is green.",
    "The user has never had any health issues.",
    "The user doesn't know anything about AI.",
    "The user works at Walmart as a third shift stocker.",
    "The user never liked coffee at all.",
    "The user lives in Portland, Oregon.",
    "Someone confirmed the user's name is actually Mike.",
    "The user prefers green over any other color.",
    "The user has never built any software.",
    "The user is not self-employed.",
    "Jake just got hired at Apple.",
    "A friend said the user lives near Chicago.",
]


def build_contexts(memories):
    raw = [m["text"] for m in memories]
    all_polluted = raw + NOISE
    random.shuffle(all_polluted)

    # Truncate to fit CLI argument limits (~100 entries each)
    # This simulates a realistic retrieval window, not the full DB
    polluted_sample = all_polluted[:100]
    polluted = "\n".join(f"- {t}" for t in polluted_sample)

    # Governed (filtered by trust, take top 100)
    filtered = sorted([m for m in memories if m["trust"] >= 0.4],
                       key=lambda x: -x["trust"])[:100]
    governed = "\n".join(f"- {m['text']}" for m in filtered)

    return polluted, governed, len(polluted_sample), len(filtered)


# ===================================================================
# Run
# ===================================================================

def measure_consistency(answers):
    """Measure pairwise consistency across answer variants."""
    n = len(answers)
    if n < 2:
        return 1.0, 0

    consistent_pairs = 0
    total_pairs = 0
    for i in range(n):
        for j in range(i + 1, n):
            if answers[i] == "[ERROR]" or answers[j] == "[ERROR]":
                continue
            is_consistent = claude_compare(answers[i], answers[j])
            consistent_pairs += int(is_consistent)
            total_pairs += 1

    if total_pairs == 0:
        return 0, 0
    return consistent_pairs / total_pairs, total_pairs


def run():
    print("=" * 70)
    print("CLAUDE VARIANCE + POLLUTION LAB")
    print(f"Model: {CLAUDE_MODEL}")
    print("Three layers: baseline, polluted, governed")
    print("=" * 70)

    memories = load_memories()
    polluted_ctx, governed_ctx, n_poll, n_gov = build_contexts(memories)
    print(f"\n{len(memories)} memories loaded")
    print(f"Polluted context: {n_poll} entries")
    print(f"Governed context: {n_gov} entries")

    sys_bare = "Answer questions about a user. Short, direct answer. One or two sentences max."
    sys_polluted = "Answer questions about a user based on stored memory entries. Short, direct answer."
    sys_governed = "Answer questions about a user based on verified, high-confidence memory entries only. Short, direct answer."

    layer_scores = {"baseline": [], "polluted": [], "governed": []}

    for q in QUESTIONS:
        print(f"\n{'='*50}")
        print(f"  Topic: {q['topic']}")
        print(f"{'='*50}")

        # Layer 1: Baseline (no context)
        answers_base = []
        print(f"\n  BASELINE (no context):")
        for v in q["variants"]:
            resp = claude(sys_bare, v)
            answers_base.append(resp)
            print(f"    \"{resp[:100]}\"")

        cons_base, pairs_base = measure_consistency(answers_base)
        layer_scores["baseline"].append(cons_base)
        print(f"  Consistency: {cons_base:.0%} ({pairs_base} pairs)")

        # Layer 2: Polluted
        answers_poll = []
        print(f"\n  POLLUTED ({n_poll} entries, no governance):")
        for v in q["variants"]:
            resp = claude(sys_polluted, f"Memory entries:\n{polluted_ctx}\n\nQuestion: {v}")
            answers_poll.append(resp)
            print(f"    \"{resp[:100]}\"")

        cons_poll, pairs_poll = measure_consistency(answers_poll)
        layer_scores["polluted"].append(cons_poll)
        print(f"  Consistency: {cons_poll:.0%} ({pairs_poll} pairs)")

        # Layer 3: Governed
        answers_gov = []
        print(f"\n  GOVERNED ({n_gov} entries, trust-filtered):")
        for v in q["variants"]:
            resp = claude(sys_governed, f"Memory entries:\n{governed_ctx}\n\nQuestion: {v}")
            answers_gov.append(resp)
            print(f"    \"{resp[:100]}\"")

        cons_gov, pairs_gov = measure_consistency(answers_gov)
        layer_scores["governed"].append(cons_gov)
        print(f"  Consistency: {cons_gov:.0%} ({pairs_gov} pairs)")

    # Summary
    print("\n" + "=" * 70)
    print("RESULTS")
    print("=" * 70)

    avg_base = np.mean(layer_scores["baseline"])
    avg_poll = np.mean(layer_scores["polluted"])
    avg_gov = np.mean(layer_scores["governed"])

    print(f"\n  Layer 1 (Baseline, no context):     {avg_base:.0%} consistency")
    print(f"  Layer 2 (Polluted, no governance):   {avg_poll:.0%} consistency")
    print(f"  Layer 3 (Governed, CRT-filtered):    {avg_gov:.0%} consistency")

    print(f"\n  Pollution variance increase:  {avg_base - avg_poll:+.0%} (baseline vs polluted)")
    print(f"  Governance variance reduction: {avg_gov - avg_poll:+.0%} (governed vs polluted)")

    print(f"\n  Per-topic breakdown:")
    print(f"  {'Topic':20s} {'Baseline':>10s} {'Polluted':>10s} {'Governed':>10s} {'Poll Drop':>10s} {'Gov Lift':>10s}")
    for i, q in enumerate(QUESTIONS):
        b = layer_scores["baseline"][i]
        p = layer_scores["polluted"][i]
        g = layer_scores["governed"][i]
        print(f"  {q['topic']:20s} {b:10.0%} {p:10.0%} {g:10.0%} {p-b:+10.0%} {g-p:+10.0%}")

    if avg_poll < avg_base:
        print(f"\n  FINDING: Context pollution increases Claude's response variance by {(avg_base-avg_poll)*100:.0f} percentage points.")
    if avg_gov > avg_poll:
        print(f"  FINDING: CRT governance reduces variance by {(avg_gov-avg_poll)*100:.0f} percentage points.")
    if avg_gov >= avg_base:
        print(f"  FINDING: Governed responses are as consistent as or better than no-context baseline.")


if __name__ == "__main__":
    run()
