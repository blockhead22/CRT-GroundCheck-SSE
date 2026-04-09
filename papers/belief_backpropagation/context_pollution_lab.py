"""Context Pollution Lab — Does noise degrade model accuracy?

The question: when a memory system accumulates conflicting, outdated,
duplicated, and misattributed facts without governance, does the model
produce worse answers? And does trust-based governance prevent the drop?

Three conditions:
  A: Polluted context (all memories, no trust info, plus synthetic noise)
  B: Polluted context with trust annotations
  C: CRT-filtered context (noise removed by trust threshold)

Tested against questions with known correct answers from production data.

Run: python -m papers.belief_backpropagation.context_pollution_lab
"""

import sys
sys.path.insert(0, r"D:\AI_round2")
sys.stdout.reconfigure(encoding='utf-8')

import json
import random
import sqlite3
import time
import requests
import numpy as np

random.seed(42)

OLLAMA_URL = "http://localhost:11434/api/generate"
MODEL = "gemma3:latest"


def generate(prompt, model=MODEL, max_tokens=100):
    try:
        r = requests.post(OLLAMA_URL, json={
            "model": model, "prompt": prompt, "stream": False,
            "options": {"num_predict": max_tokens, "temperature": 0.3, "num_ctx": 8192}
        }, timeout=60)
        return r.json().get("response", "").strip()
    except Exception as e:
        return f"[ERROR: {e}]"


def judge(question, response, correct_answer, model="gemma3:latest"):
    prompt = f"""You are a judge. Rate whether this response correctly answers the question.

Question: {question}
Correct answer: {correct_answer}
Response: {response}

Is the response faithful to the correct answer? Reply with ONLY: FAITHFUL or UNFAITHFUL"""
    r = generate(prompt, model=model, max_tokens=10)
    return "FAITHFUL" in r.upper() and "UN" not in r.upper()


# ===================================================================
# Load real memories and strip CRT metadata
# ===================================================================

def load_raw_memories():
    """Load production memories stripped of all CRT governance metadata."""
    db = r"D:\AI_round2\personal_agent\crt_memory_shared.db"
    conn = sqlite3.connect(db)
    rows = conn.execute("""
        SELECT text, trust, kind, contradiction_count, access_count
        FROM memories WHERE deprecated=0 AND text IS NOT NULL AND length(text) > 20
    """).fetchall()
    conn.close()
    return [{"text": t, "trust": tr, "kind": k, "contras": c, "access": a}
            for t, tr, k, c, a in rows]


# ===================================================================
# Build noise
# ===================================================================

def build_polluted_context(memories):
    """Build three context versions from the same memory set."""

    raw_texts = [m["text"][:200] for m in memories]

    # --- Synthetic noise ---
    noise = []

    # Duplicates with slight rephrasing
    for m in random.sample(memories, min(40, len(memories))):
        text = m["text"][:200]
        # Crude rephrase: swap word order or add filler
        words = text.split()
        if len(words) > 5:
            noise.append(" ".join(words[:3]) + " basically " + " ".join(words[3:]))

    # Deliberately wrong facts
    wrong_facts = [
        "The user's name is Michael.",
        "The user works at Google as a senior engineer.",
        "The user lives in San Francisco, California.",
        "The user's favorite color is blue.",
        "The user has a dog named Rex.",
        "The user prefers tea over coffee.",
        "The user went to Stanford University.",
        "The user is married with two kids.",
        "The user drives a Tesla Model 3.",
        "The user is 45 years old.",
        "The user works the day shift at a warehouse.",
        "The user's favorite drink is orange juice.",
        "The user lives in Portland, Oregon.",
        "The user's handle is TechGuru42.",
        "The user was born in December.",
        "The user has never had any health issues.",
        "The user doesn't know anything about AI.",
        "The user works at a design studio downtown.",
        "The user prefers green over any other color.",
        "The user has never used a computer before.",
    ]
    noise.extend(wrong_facts)

    # Outdated facts (things that were true but corrected)
    outdated = [
        "The user works at Walmart as a third shift stocker.",
        "The user's favorite color is green.",
        "The user never liked coffee.",
        "The user is not self-employed.",
        "The user has never sold any camera equipment.",
    ]
    noise.extend(outdated)

    # Model-generated observations that sound like facts
    observations = [
        "The user seems to prefer working late at night.",
        "Based on conversation patterns, the user appears to be introverted.",
        "The user might be interested in moving to a new city.",
        "The system detected possible frustration in recent messages.",
        "The user's tone suggests they are considering a career change.",
        "Analysis indicates the user values independence highly.",
        "The user appears to have experience with photography.",
        "Pattern analysis suggests the user is health-conscious.",
    ]
    noise.extend(observations)

    # Third-party facts misattributed
    thirdparty = [
        "Jake just got hired at Tesla and is really excited.",
        "The user's friend works in marketing at Apple.",
        "Someone mentioned the user might be named Mike.",
        "A colleague said the user lives near Chicago.",
    ]
    noise.extend(thirdparty)

    # Combine
    all_polluted = raw_texts + noise
    random.shuffle(all_polluted)

    # CONDITION A: Polluted, no governance
    condition_a = "\n".join(f"- {t}" for t in all_polluted)

    # CONDITION B: Polluted with trust annotations
    # Real memories get their actual trust. Noise gets low trust.
    annotated = []
    for m in memories:
        annotated.append(f"- [trust: {m['trust']:.2f}] {m['text'][:200]}")
    for n in noise:
        fake_trust = round(random.uniform(0.05, 0.25), 2)
        annotated.append(f"- [trust: {fake_trust}] {n}")
    random.shuffle(annotated)
    condition_b = "\n".join(annotated)

    # CONDITION C: CRT-filtered (only trust > 0.4, no noise)
    filtered = [m for m in memories if m["trust"] >= 0.4]
    condition_c = "\n".join(f"- {m['text'][:200]}" for m in filtered)

    return condition_a, condition_b, condition_c, len(all_polluted), len(filtered)


# ===================================================================
# Test questions with known correct answers
# ===================================================================

QUESTIONS = [
    {
        "q": "What is the user's name?",
        "correct": "Nick",
        "wrong_signals": ["michael", "mike", "techguru"],
    },
    {
        "q": "What does the user do for work?",
        "correct": "Self-employed, freelance developer building an AI system called Aether/CRT",
        "wrong_signals": ["google", "warehouse", "design studio", "senior engineer"],
    },
    {
        "q": "What is the user's favorite color?",
        "correct": "Orange",
        "wrong_signals": ["blue", "green"],
    },
    {
        "q": "Does the user like coffee?",
        "correct": "Yes, recently started drinking iced coffees and looking for an espresso maker",
        "wrong_signals": ["tea", "never", "doesn't"],
    },
    {
        "q": "Where does the user live?",
        "correct": "Sussex, Wisconsin, near Waukesha/Milwaukee",
        "wrong_signals": ["san francisco", "portland", "chicago"],
    },
    {
        "q": "What is the user's handle or nickname?",
        "correct": "Blockhead, from a Charlie Brown reference",
        "wrong_signals": ["techguru"],
    },
    {
        "q": "Has the user had any health issues?",
        "correct": "Yes, survived leukemia and has chronic graft-versus-host disease (cGVHD)",
        "wrong_signals": ["never", "no health issues", "healthy"],
    },
    {
        "q": "What is the user building?",
        "correct": "An AI system called Aether/CRT with epistemic governance, memory architecture, and belief tracking",
        "wrong_signals": ["nothing", "doesn't know about ai"],
    },
    {
        "q": "Does the user work at a design studio?",
        "correct": "No. This was a test/incorrect entry that was corrected.",
        "wrong_signals": ["yes", "works at a design studio"],
    },
    {
        "q": "What is the user's friend Jake doing?",
        "correct": "Jake got hired at Tesla",
        "wrong_signals": ["apple", "marketing"],
    },
]


# ===================================================================
# Run experiment
# ===================================================================

def run_experiment():
    print("=" * 70)
    print("CONTEXT POLLUTION LAB")
    print("Does noise degrade model accuracy? Does trust governance prevent it?")
    print("=" * 70)

    memories = load_raw_memories()
    print(f"\nLoaded {len(memories)} production memories")

    cond_a, cond_b, cond_c, total_polluted, total_filtered = build_polluted_context(memories)
    print(f"Condition A (polluted, no governance): {total_polluted} entries")
    print(f"Condition B (polluted, trust-annotated): {total_polluted} entries")
    print(f"Condition C (CRT-filtered): {total_filtered} entries")

    system_base = "You are answering questions about a user based on stored memory entries. Give short, direct answers based on the most reliable information available."
    system_trust = "You are answering questions about a user. Each memory has a trust score (0.0-1.0). Higher trust means more reliable and more recently verified. Always prefer higher-trust memories. Ignore low-trust entries that conflict with high-trust ones. Give short, direct answers."
    system_filtered = "You are answering questions about a user based on verified, high-confidence memory entries. Give short, direct answers."

    results = {"A": [], "B": [], "C": []}
    n_runs = 2  # 2 runs per condition for stability

    for qi, q in enumerate(QUESTIONS):
        print(f"\n--- Q{qi+1}: {q['q']} ---")
        print(f"    Correct: {q['correct'][:60]}")

        for run in range(n_runs):
            # Condition A
            prompt_a = f"{system_base}\n\nMemory entries:\n{cond_a}\n\nQuestion: {q['q']}"
            resp_a = generate(prompt_a)
            faithful_a = judge(q["q"], resp_a, q["correct"])
            results["A"].append(faithful_a)

            # Condition B
            prompt_b = f"{system_trust}\n\nMemory entries:\n{cond_b}\n\nQuestion: {q['q']}"
            resp_b = generate(prompt_b)
            faithful_b = judge(q["q"], resp_b, q["correct"])
            results["B"].append(faithful_b)

            # Condition C
            prompt_c = f"{system_filtered}\n\nMemory entries:\n{cond_c}\n\nQuestion: {q['q']}"
            resp_c = generate(prompt_c)
            faithful_c = judge(q["q"], resp_c, q["correct"])
            results["C"].append(faithful_c)

            if run == 0:
                print(f"    A (polluted):  {'FAITHFUL' if faithful_a else 'UNFAITHFUL'}  \"{resp_a[:100]}\"")
                print(f"    B (trust):     {'FAITHFUL' if faithful_b else 'UNFAITHFUL'}  \"{resp_b[:100]}\"")
                print(f"    C (filtered):  {'FAITHFUL' if faithful_c else 'UNFAITHFUL'}  \"{resp_c[:100]}\"")

    # Summary
    print("\n" + "=" * 70)
    print("RESULTS")
    print("=" * 70)

    for label, desc in [("A", "Polluted (no governance)"),
                        ("B", "Polluted + trust annotations"),
                        ("C", "CRT-filtered (governance)")]:
        faithful = sum(results[label])
        total = len(results[label])
        pct = faithful / total * 100
        print(f"  Condition {label} ({desc}): {faithful}/{total} faithful ({pct:.0f}%)")

    pct_a = sum(results["A"]) / len(results["A"]) * 100
    pct_b = sum(results["B"]) / len(results["B"]) * 100
    pct_c = sum(results["C"]) / len(results["C"]) * 100

    print(f"\n  Pollution cost:      {pct_c - pct_a:+.0f}% (filtered vs polluted)")
    print(f"  Trust annotation:    {pct_b - pct_a:+.0f}% improvement over polluted")
    print(f"  Full governance:     {pct_c - pct_a:+.0f}% improvement over polluted")

    if pct_c > pct_a:
        print(f"\n  SIGNAL: CRT governance prevents accuracy drop from context pollution.")
    if pct_b > pct_a:
        print(f"  SIGNAL: Trust annotations alone improve faithfulness.")
    if pct_c > pct_b:
        print(f"  SIGNAL: Filtering outperforms annotation (removing noise > labeling noise).")


if __name__ == "__main__":
    run_experiment()
