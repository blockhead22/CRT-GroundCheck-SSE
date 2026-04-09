"""Claude Context Pollution Lab

Tests Claude (via CLI) on its ability to sift through polluted context.
Can the most capable model reliably pick correct facts out of noise?
Does CRT governance prevent accuracy drops?

Three conditions:
  A: All memories + noise, no trust info, no governance
  B: All memories + noise, trust-annotated
  C: CRT-filtered (noise removed, only trust > 0.4)

Uses Claude via the official CLI (same as production Aether).

Run: python -m papers.belief_backpropagation.claude_pollution_lab
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

random.seed(42)

CLAUDE_BIN = r"C:\Users\block\AppData\Roaming\Claude\claude-code\2.1.92\claude.exe"
CLAUDE_MODEL = "claude-sonnet-4-6"  # faster + cheaper than opus for 60 calls


def claude_generate(system, prompt, max_tokens=150):
    """Generate via Claude CLI."""
    try:
        proc = subprocess.run(
            [CLAUDE_BIN, "-p", prompt, "--model", CLAUDE_MODEL,
             "--output-format", "text", "--system-prompt", system],
            capture_output=True, text=True, encoding="utf-8",
            errors="replace", timeout=120
        )
        if proc.returncode != 0:
            return f"[ERROR: {proc.stderr[:200]}]"
        return proc.stdout.strip()
    except subprocess.TimeoutExpired:
        return "[TIMEOUT]"
    except Exception as e:
        return f"[ERROR: {e}]"


def claude_judge(question, response, correct_answer):
    """Use Claude to judge faithfulness."""
    prompt = f"""Rate whether this response correctly answers the question.

Question: {question}
Correct answer: {correct_answer}
Response: {response}

Reply with ONLY one word: FAITHFUL or UNFAITHFUL"""
    result = claude_generate("You are a strict judge. Reply with one word only.", prompt)
    return "FAITHFUL" in result.upper() and "UN" not in result.upper()


# ===================================================================
# Load and build contexts
# ===================================================================

def load_memories():
    db = r"D:\AI_round2\personal_agent\crt_memory_shared.db"
    conn = sqlite3.connect(db)
    rows = conn.execute("""
        SELECT text, trust, kind, contradiction_count, access_count
        FROM memories WHERE deprecated=0 AND text IS NOT NULL AND length(text) > 20
    """).fetchall()
    conn.close()
    return [{"text": t[:200], "trust": tr, "kind": k, "contras": c, "access": a}
            for t, tr, k, c, a in rows]


WRONG_FACTS = [
    "The user's name is Michael.",
    "The user works at Google as a senior engineer.",
    "The user lives in San Francisco, California.",
    "The user's favorite color is blue.",
    "The user has a dog named Rex.",
    "The user prefers tea over all beverages.",
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
    "The user doesn't know anything about AI or programming.",
    "The user works at a design studio downtown.",
    "The user prefers green over any other color.",
    "The user has never built any software.",
]

OUTDATED = [
    "The user works at Walmart as a third shift stocker.",
    "The user's favorite color is green.",
    "The user never liked coffee at all.",
    "The user is not self-employed.",
]

MISATTRIBUTED = [
    "Jake just got hired at Apple and is really excited.",
    "The user's colleague works in marketing at Tesla.",
    "Someone confirmed the user's name is actually Mike.",
    "A friend said the user lives near Chicago.",
]


def build_contexts(memories):
    raw = [m["text"] for m in memories]
    noise = WRONG_FACTS + OUTDATED + MISATTRIBUTED

    # Add rephrased duplicates
    for m in random.sample(memories, min(30, len(memories))):
        words = m["text"].split()
        if len(words) > 5:
            noise.append("Basically " + " ".join(words[:4]) + "... " + " ".join(words[4:]))

    all_polluted = raw + noise
    random.shuffle(all_polluted)

    # A: flat polluted
    cond_a = "\n".join(f"- {t}" for t in all_polluted)

    # B: trust-annotated
    annotated = []
    for m in memories:
        annotated.append(f"- [trust: {m['trust']:.2f}] {m['text']}")
    for n in noise:
        annotated.append(f"- [trust: {random.uniform(0.05, 0.25):.2f}] {n}")
    random.shuffle(annotated)
    cond_b = "\n".join(annotated)

    # C: filtered
    filtered = [m for m in memories if m["trust"] >= 0.4]
    cond_c = "\n".join(f"- {m['text']}" for m in filtered)

    return cond_a, cond_b, cond_c, len(all_polluted), len(filtered)


QUESTIONS = [
    {"q": "What is the user's name?",
     "correct": "Nick or Nick Block"},
    {"q": "What does the user do for work?",
     "correct": "Self-employed freelance developer building an AI system called Aether/CRT"},
    {"q": "What is the user's favorite color?",
     "correct": "Orange"},
    {"q": "Does the user like coffee?",
     "correct": "Yes, recently started drinking iced coffees and looking for an espresso maker"},
    {"q": "Where does the user live?",
     "correct": "Sussex Wisconsin, near Waukesha and Milwaukee"},
    {"q": "Does the user work at a design studio?",
     "correct": "No, this was incorrect and was corrected"},
    {"q": "Has the user had any health issues?",
     "correct": "Yes, survived leukemia and has chronic graft-versus-host disease cGVHD"},
    {"q": "What is the user building?",
     "correct": "An AI system called Aether with CRT memory architecture, epistemic governance, belief tracking"},
    {"q": "Does the user work at Google?",
     "correct": "No, the user has never worked at Google"},
    {"q": "What is the user's friend Jake doing?",
     "correct": "Jake got hired at Tesla"},
]


def run():
    print("=" * 70)
    print("CLAUDE CONTEXT POLLUTION LAB")
    print(f"Model: {CLAUDE_MODEL}")
    print("=" * 70)

    memories = load_memories()
    print(f"\nLoaded {len(memories)} memories")

    cond_a, cond_b, cond_c, n_polluted, n_filtered = build_contexts(memories)
    print(f"Condition A (polluted): {n_polluted} entries")
    print(f"Condition B (trust-annotated): {n_polluted} entries")
    print(f"Condition C (CRT-filtered): {n_filtered} entries")

    sys_a = "Answer questions about a user based on stored memory entries. Give short, direct answers."
    sys_b = "Answer questions about a user. Each memory has a trust score (0.0-1.0). Higher = more reliable. Always prefer high-trust memories. Ignore low-trust entries that conflict with high-trust ones. Short, direct answers."
    sys_c = "Answer questions about a user based on verified high-confidence memory entries. Short, direct answers."

    results = {"A": [], "B": [], "C": []}

    for qi, q in enumerate(QUESTIONS):
        print(f"\n--- Q{qi+1}: {q['q']} ---")

        # Condition A
        resp_a = claude_generate(sys_a, f"Memory entries:\n{cond_a}\n\nQuestion: {q['q']}")
        faith_a = claude_judge(q["q"], resp_a, q["correct"])
        results["A"].append(faith_a)
        print(f"  A (polluted):  {'PASS' if faith_a else 'FAIL'}  \"{resp_a[:120]}\"")

        # Condition B
        resp_b = claude_generate(sys_b, f"Memory entries:\n{cond_b}\n\nQuestion: {q['q']}")
        faith_b = claude_judge(q["q"], resp_b, q["correct"])
        results["B"].append(faith_b)
        print(f"  B (trust):     {'PASS' if faith_b else 'FAIL'}  \"{resp_b[:120]}\"")

        # Condition C
        resp_c = claude_generate(sys_c, f"Memory entries:\n{cond_c}\n\nQuestion: {q['q']}")
        faith_c = claude_judge(q["q"], resp_c, q["correct"])
        results["C"].append(faith_c)
        print(f"  C (filtered):  {'PASS' if faith_c else 'FAIL'}  \"{resp_c[:120]}\"")

    # Summary
    print("\n" + "=" * 70)
    print("RESULTS")
    print("=" * 70)

    for label, desc in [("A", "Polluted (no governance)"),
                        ("B", "Polluted + trust annotations"),
                        ("C", "CRT-filtered (governance)")]:
        f = sum(results[label])
        t = len(results[label])
        print(f"  {label} ({desc}): {f}/{t} ({f/t*100:.0f}%)")

    a_pct = sum(results["A"]) / len(results["A"]) * 100
    b_pct = sum(results["B"]) / len(results["B"]) * 100
    c_pct = sum(results["C"]) / len(results["C"]) * 100

    print(f"\n  Pollution accuracy drop: {a_pct:.0f}% (vs {c_pct:.0f}% filtered)")
    print(f"  Trust annotation lift:   {b_pct - a_pct:+.0f}%")
    print(f"  Full governance lift:    {c_pct - a_pct:+.0f}%")

    if c_pct > a_pct:
        print(f"\n  FINDING: Context pollution reduces Claude's accuracy by {c_pct - a_pct:.0f} percentage points.")
        print(f"  CRT governance recovers it.")


if __name__ == "__main__":
    run()
