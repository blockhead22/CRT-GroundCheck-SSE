"""Hybrid Belief Verification: regex + embeddings + LLM in one BDG tree.

The pure LLM belief test got 73% leaf / 40% verdict.
The hybrid approach got 93% on intent routing.

Can the same hybrid pattern fix belief verification?

- Regex for numeric comparisons (trust scores, ages)
- Embeddings for topic similarity between memories
- LLM only for semantic relationship questions

If this works, the hybrid BDG IS the breathing loop.
"""

import asyncio
import json
import math
import re
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import aiohttp

import builtins
_real_open = builtins.open

import sys
sys.path.insert(0, str(Path(__file__).parent))
from config import OLLAMA_URL

MIRUS_MODEL = "llama3.2:latest"


def p(msg):
    print(msg, flush=True)


# ===================================================================
# Leaf types
# ===================================================================
async def llm_leaf(session, context: str, question: str) -> str:
    prompt = (
        f"Read this carefully:\n\n{context}\n\n"
        f"QUESTION: {question}\n\n"
        f"Answer YES or NO, then explain in one sentence."
    )
    payload = {
        "model": MIRUS_MODEL,
        "prompt": prompt,
        "system": "Answer factual questions about memory entries. Start with YES or NO.",
        "stream": False,
        "options": {"temperature": 0.0, "num_predict": 80, "num_ctx": 1024},
    }
    async with session.post(f"{OLLAMA_URL}/api/generate", json=payload,
                           timeout=aiohttp.ClientTimeout(total=15)) as resp:
        data = await resp.json()
    return data.get("response", "").strip()


async def get_embedding(session, text: str) -> List[float]:
    payload = {"model": MIRUS_MODEL, "input": text}
    async with session.post(f"{OLLAMA_URL}/api/embed", json=payload,
                           timeout=aiohttp.ClientTimeout(total=15)) as resp:
        data = await resp.json()
    embeddings = data.get("embeddings", [[]])
    return embeddings[0] if embeddings else []


def cosine_sim(a: List[float], b: List[float]) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(x * x for x in b))
    if na == 0 or nb == 0:
        return 0.0
    return dot / (na * nb)


def regex_extract_trust(memory_text: str) -> Optional[float]:
    """Extract trust score from memory text."""
    m = re.search(r'[Tt]rust:\s*([\d.]+)', memory_text)
    return float(m.group(1)) if m else None


def regex_extract_age(memory_text: str) -> Optional[str]:
    """Extract age from memory text."""
    m = re.search(r'[Aa]ge:\s*(.+?)(?:,|$)', memory_text)
    return m.group(1).strip() if m else None


def regex_extract_source(memory_text: str) -> Optional[str]:
    """Extract source from memory text."""
    m = re.search(r'[Ss]ource:\s*(\w+)', memory_text)
    return m.group(1).strip() if m else None


def age_to_days(age_str: str) -> Optional[float]:
    """Convert age string to approximate days."""
    if not age_str:
        return None
    age_lower = age_str.lower().strip()
    m = re.search(r'(\d+)\s*(day|week|month|year|hour|minute)', age_lower)
    if not m:
        return None
    num = float(m.group(1))
    unit = m.group(2)
    multipliers = {"minute": 1/1440, "hour": 1/24, "day": 1, "week": 7, "month": 30, "year": 365}
    return num * multipliers.get(unit, 1)


# ===================================================================
# Belief test cases — same as before but with hybrid leaf evaluation
# ===================================================================
BELIEF_TESTS = [
    {
        "id": "direct_contradiction",
        "memory_a": "Nick lives in Milwaukee, Wisconsin. Trust: 0.9, Source: user_fact",
        "memory_b": "Nick lives in Chicago, Illinois. Trust: 0.3, Source: user_correction",
        "expected_verdict": "CONTRADICTION",
        "expected_action": "keep_higher_trust",
    },
    {
        "id": "complementary",
        "memory_a": "Nick is a developer. Trust: 0.85, Source: user_fact",
        "memory_b": "Nick works on AI systems. Trust: 0.7, Source: inferred",
        "expected_verdict": "COMPATIBLE",
        "expected_action": "keep_both",
    },
    {
        "id": "stale_override",
        "memory_a": "Nick's favorite language is Python. Trust: 0.6, Source: user_fact, Age: 6 months",
        "memory_b": "Nick's favorite language is Rust. Trust: 0.8, Source: user_correction, Age: 2 days",
        "expected_verdict": "SUPERSEDED",
        "expected_action": "demote_older",
    },
    {
        "id": "unrelated",
        "memory_a": "Nick lives in Milwaukee. Trust: 0.9, Source: user_fact",
        "memory_b": "Nick prefers dark mode in editors. Trust: 0.7, Source: preference",
        "expected_verdict": "UNRELATED",
        "expected_action": "keep_both",
    },
    {
        "id": "confidence_decay",
        "memory_a": "Nick said he enjoys hiking. Trust: 0.4, Source: user_fact, Age: 1 year",
        "memory_b": "Nick has not mentioned hiking in 8 months. Trust: N/A, Source: observation",
        "expected_verdict": "DECAYED",
        "expected_action": "flag_for_review",
    },
    {
        "id": "exact_duplicate",
        "memory_a": "Nick is a freelance developer. Trust: 0.85, Source: user_fact, Age: 2 months",
        "memory_b": "Nick is a freelance developer. Trust: 0.6, Source: user_fact, Age: 5 days",
        "expected_verdict": "DUPLICATE",
        "expected_action": "merge_keep_higher_trust",
    },
    {
        "id": "refinement",
        "memory_a": "Nick lives in Wisconsin. Trust: 0.7, Source: user_fact",
        "memory_b": "Nick lives in Milwaukee, Wisconsin. Trust: 0.85, Source: user_fact",
        "expected_verdict": "REFINEMENT",
        "expected_action": "keep_more_specific",
    },
    {
        "id": "temporal_sequence",
        "memory_a": "Nick is learning Rust. Trust: 0.6, Source: user_fact, Age: 3 months",
        "memory_b": "Nick built a project in Rust. Trust: 0.75, Source: user_fact, Age: 1 week",
        "expected_verdict": "COMPATIBLE",
        "expected_action": "keep_both",
    },
]


async def evaluate_pair(session, test: Dict) -> Dict:
    """Evaluate a memory pair using hybrid BDG leaves."""
    mem_a = test["memory_a"]
    mem_b = test["memory_b"]

    results = {"leaves": [], "signals": {}}

    # ------ REGEX LEAVES (deterministic, instant) ------

    # Trust scores
    trust_a = regex_extract_trust(mem_a)
    trust_b = regex_extract_trust(mem_b)
    results["signals"]["trust_a"] = trust_a
    results["signals"]["trust_b"] = trust_b

    if trust_a is not None and trust_b is not None:
        results["leaves"].append({
            "type": "regex", "id": "trust_comparison",
            "question": "Which memory has higher trust?",
            "answer": "A" if trust_a > trust_b else ("B" if trust_b > trust_a else "EQUAL"),
            "detail": f"A={trust_a}, B={trust_b}",
        })
        results["leaves"].append({
            "type": "regex", "id": "trust_a_above_threshold",
            "question": "Is memory A's trust above 0.5?",
            "answer": "YES" if trust_a > 0.5 else "NO",
            "detail": f"trust_a={trust_a}",
        })
        results["leaves"].append({
            "type": "regex", "id": "trust_b_above_threshold",
            "question": "Is memory B's trust above 0.5?",
            "answer": "YES" if trust_b > 0.5 else "NO",
            "detail": f"trust_b={trust_b}",
        })

    # Age/recency
    age_a = regex_extract_age(mem_a)
    age_b = regex_extract_age(mem_b)
    days_a = age_to_days(age_a) if age_a else None
    days_b = age_to_days(age_b) if age_b else None
    results["signals"]["age_a"] = age_a
    results["signals"]["age_b"] = age_b

    if days_a is not None and days_b is not None:
        results["leaves"].append({
            "type": "regex", "id": "recency_comparison",
            "question": "Which memory is more recent?",
            "answer": "B" if days_b < days_a else ("A" if days_a < days_b else "SAME"),
            "detail": f"A={age_a} ({days_a:.0f}d), B={age_b} ({days_b:.0f}d)",
        })

    # Source type
    source_a = regex_extract_source(mem_a)
    source_b = regex_extract_source(mem_b)
    results["signals"]["source_a"] = source_a
    results["signals"]["source_b"] = source_b

    is_correction = source_b == "user_correction" or source_a == "user_correction"
    results["leaves"].append({
        "type": "regex", "id": "has_correction_source",
        "question": "Is either memory sourced from a user correction?",
        "answer": "YES" if is_correction else "NO",
        "detail": f"A={source_a}, B={source_b}",
    })

    # ------ EMBEDDING LEAVES (semantic similarity, ~50ms) ------

    # Extract just the factual content (strip metadata)
    fact_a = re.sub(r'\s*Trust:.*$', '', mem_a).strip()
    fact_b = re.sub(r'\s*Trust:.*$', '', mem_b).strip()

    emb_a = await get_embedding(session, fact_a)
    emb_b = await get_embedding(session, fact_b)
    similarity = cosine_sim(emb_a, emb_b)
    results["signals"]["embedding_similarity"] = round(similarity, 4)

    results["leaves"].append({
        "type": "embedding", "id": "topic_similarity",
        "question": "Are these memories about the same topic?",
        "answer": "YES" if similarity > 0.85 else ("MAYBE" if similarity > 0.7 else "NO"),
        "detail": f"cosine={similarity:.4f}",
    })

    results["leaves"].append({
        "type": "embedding", "id": "near_duplicate",
        "question": "Are these memories near-duplicates?",
        "answer": "YES" if similarity > 0.95 else "NO",
        "detail": f"cosine={similarity:.4f}",
    })

    # ------ LLM LEAVES (only for semantic questions) ------

    # Only ask the LLM things regex and embeddings can't answer
    context = f"MEMORY A: {mem_a}\nMEMORY B: {mem_b}"

    # Do they make contradictory claims?
    if similarity > 0.7:  # Only check contradiction if same-topic
        answer = await llm_leaf(session, context,
            "Do memory A and memory B make DIFFERENT claims about the SAME specific fact? "
            "For example: A says 'lives in X' and B says 'lives in Y'. "
            "Two memories about the same general topic but different specific facts (e.g. 'is a developer' and 'works on AI') are NOT contradictory.")
        is_contradictory = answer.lower().startswith("yes")
        results["leaves"].append({
            "type": "llm", "id": "contradicts",
            "question": "Do they make contradictory claims about the same fact?",
            "answer": "YES" if is_contradictory else "NO",
            "detail": answer[:80],
        })
    else:
        is_contradictory = False
        results["leaves"].append({
            "type": "skip", "id": "contradicts",
            "question": "Skipped — low topic similarity",
            "answer": "NO",
            "detail": f"similarity {similarity:.3f} < 0.7 threshold",
        })

    # Is B more specific than A? (refinement check)
    if similarity > 0.8 and not is_contradictory:
        answer = await llm_leaf(session, context,
            "Does memory B contain ALL the information in memory A PLUS additional detail? "
            "For example: A says 'lives in Wisconsin' and B says 'lives in Milwaukee, Wisconsin'.")
        is_refinement = answer.lower().startswith("yes")
        results["leaves"].append({
            "type": "llm", "id": "is_refinement",
            "question": "Is B a more specific version of A?",
            "answer": "YES" if is_refinement else "NO",
            "detail": answer[:80],
        })
    else:
        is_refinement = False

    # ------ PROPAGATION ------

    # Verdict determination through leaf signals
    same_topic = similarity > 0.7
    near_dup = similarity > 0.95
    has_correction = is_correction
    a_newer = days_a is not None and days_b is not None and days_a < days_b
    b_newer = days_a is not None and days_b is not None and days_b < days_a
    trust_a_low = trust_a is not None and trust_a < 0.5

    if near_dup:
        verdict = "DUPLICATE"
        action = "merge_keep_higher_trust"
    elif same_topic and is_contradictory and has_correction:
        verdict = "SUPERSEDED" if b_newer else "CONTRADICTION"
        action = "demote_older" if b_newer else "keep_higher_trust"
    elif same_topic and is_contradictory:
        verdict = "CONTRADICTION"
        action = "keep_higher_trust"
    elif same_topic and is_refinement:
        verdict = "REFINEMENT"
        action = "keep_more_specific"
    elif same_topic and not is_contradictory:
        verdict = "COMPATIBLE"
        action = "keep_both"
    elif trust_a_low and not same_topic:
        verdict = "DECAYED"
        action = "flag_for_review"
    else:
        verdict = "UNRELATED"
        action = "keep_both"

    results["verdict"] = verdict
    results["action"] = action
    return results


async def run():
    p("=" * 60)
    p("HYBRID BELIEF VERIFICATION")
    p("=" * 60)
    p(f"Model: {MIRUS_MODEL}")
    p(f"Tests: {len(BELIEF_TESTS)} memory pairs")
    p(f"Leaf types: regex (numeric) + embedding (similarity) + LLM (semantic)")
    p("=" * 60)

    correct_verdicts = 0
    correct_actions = 0
    leaf_type_counts = {"regex": 0, "embedding": 0, "llm": 0, "skip": 0}

    async with aiohttp.ClientSession() as session:
        for test in BELIEF_TESTS:
            t0 = time.time()
            result = await evaluate_pair(session, test)
            elapsed = time.time() - t0

            verdict_match = result["verdict"] == test["expected_verdict"]
            action_match = result["action"] == test["expected_action"]
            if verdict_match:
                correct_verdicts += 1
            if action_match:
                correct_actions += 1

            icon = "+" if verdict_match else "!"
            act_icon = "+" if action_match else "!"

            p(f"\n  [{icon}] {test['id']}")
            p(f"    A: {test['memory_a'][:70]}")
            p(f"    B: {test['memory_b'][:70]}")
            p(f"    Similarity: {result['signals'].get('embedding_similarity', '?')}")

            for leaf in result["leaves"]:
                leaf_type_counts[leaf["type"]] += 1
                type_tag = {"regex": "REG", "embedding": "EMB", "llm": "LLM", "skip": "---"}[leaf["type"]]
                p(f"    [{type_tag}] {leaf['id']}: {leaf['answer']} ({leaf['detail'][:50]})")

            p(f"    [{icon}] Verdict: {result['verdict']} (expected {test['expected_verdict']})")
            p(f"    [{act_icon}] Action: {result['action']} (expected {test['expected_action']})")
            p(f"    Time: {elapsed:.1f}s")

    total = len(BELIEF_TESTS)
    p(f"\n{'='*60}")
    p("RESULTS")
    p(f"{'='*60}")
    p(f"  Verdict accuracy: {correct_verdicts}/{total} ({correct_verdicts/total*100:.0f}%)")
    p(f"  Action accuracy:  {correct_actions}/{total} ({correct_actions/total*100:.0f}%)")
    p(f"\n  Leaf type usage:")
    for ltype, count in leaf_type_counts.items():
        p(f"    {ltype}: {count}")

    p(f"\n  COMPARISON:")
    p(f"    Pure LLM leaves:  40% verdict (from earlier test)")
    p(f"    Hybrid leaves:    {correct_verdicts/total*100:.0f}% verdict")

    p(f"\n  IMPLICATION:")
    if correct_verdicts / total >= 0.75:
        p(f"    Hybrid BDG IS viable for belief verification.")
        p(f"    This architecture can power the CRT breathing loop.")
    else:
        p(f"    Hybrid improves but doesn't reach threshold.")
        p(f"    Belief verification needs a different approach.")


if __name__ == "__main__":
    asyncio.run(run())
