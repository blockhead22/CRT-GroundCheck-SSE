"""Structural Belief Verification: Zero LLM calls.

Replace the LLM contradiction leaf with slot extraction + value comparison.
The entire belief verification tree runs on regex + embeddings + slot matching.
No cloud calls. No 3B model judgment. Pure structural analysis.

Contradiction = same slot + different value + high topic similarity
Compatible = same topic + different slots (or same slot + same value)
Refinement = same slot + one value contains the other
Duplicate = near-identical embedding
"""

import asyncio
import json
import math
import re
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Set

import aiohttp

import builtins
_real_open = builtins.open

import sys
sys.path.insert(0, str(Path(__file__).parent))
from config import OLLAMA_URL

EMBED_MODEL = "llama3.2:latest"


def p(msg):
    print(msg, flush=True)


# ===================================================================
# Embedding
# ===================================================================
async def get_embedding(session, text: str) -> List[float]:
    payload = {"model": EMBED_MODEL, "input": text}
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


# ===================================================================
# Regex extraction
# ===================================================================
def extract_trust(text: str) -> Optional[float]:
    m = re.search(r'[Tt]rust:\s*([\d.]+)', text)
    return float(m.group(1)) if m else None


def extract_age(text: str) -> Optional[str]:
    m = re.search(r'[Aa]ge:\s*(.+?)(?:,|$)', text)
    return m.group(1).strip() if m else None


def extract_source(text: str) -> Optional[str]:
    m = re.search(r'[Ss]ource:\s*(\w+)', text)
    return m.group(1).strip() if m else None


def age_to_days(age_str: str) -> Optional[float]:
    if not age_str:
        return None
    m = re.search(r'(\d+)\s*(day|week|month|year|hour|minute)', age_str.lower())
    if not m:
        return None
    num = float(m.group(1))
    unit = m.group(2)
    return num * {"minute": 1/1440, "hour": 1/24, "day": 1, "week": 7, "month": 30, "year": 365}.get(unit, 1)


def strip_metadata(text: str) -> str:
    """Strip Trust/Source/Age metadata, return just the factual content."""
    return re.sub(r'\s*(?:Trust|Source|Age):.*$', '', text).strip()


# ===================================================================
# Slot extraction — structural fact decomposition
# ===================================================================
SLOT_PATTERNS = {
    "location": [
        r"lives? in (.+?)(?:\.|,|$)",
        r"from (.+?)(?:\.|,|$)",
        r"located in (.+?)(?:\.|,|$)",
        r"based in (.+?)(?:\.|,|$)",
    ],
    "name": [
        r"name is (.+?)(?:\.|,|$)",
        r"called (.+?)(?:\.|,|$)",
        r"^(\w+) is the user",
    ],
    "occupation": [
        r"is a (.+?)(?:\.|,|$)",
        r"works as (.+?)(?:\.|,|$)",
        r"occupation is (.+?)(?:\.|,|$)",
    ],
    "preference": [
        r"(?:favorite|favourite|preferred) (\w+) is (.+?)(?:\.|,|$)",
        r"prefers (.+?)(?:\.|,|$)",
        r"likes? (.+?)(?:\.|,|$)",
        r"enjoys? (.+?)(?:\.|,|$)",
    ],
    "language": [
        r"favorite language is (.+?)(?:\.|,|$)",
        r"(?:learning|using|writing|built.+?in) (.+?)(?:\.|,|$)",
    ],
    "skill": [
        r"is learning (.+?)(?:\.|,|$)",
        r"built a (.+?)(?:\.|,|$)",
        r"works on (.+?)(?:\.|,|$)",
    ],
}


def extract_slots(text: str) -> Dict[str, str]:
    """Extract structured slots from memory text."""
    fact = strip_metadata(text).lower()
    slots = {}

    for slot_name, patterns in SLOT_PATTERNS.items():
        for pattern in patterns:
            m = re.search(pattern, fact, re.IGNORECASE)
            if m:
                # Use last group (handles patterns with multiple groups)
                value = m.group(m.lastindex or 1).strip()
                if value and len(value) > 1:
                    slots[slot_name] = value
                    break

    return slots


def values_contradict(val_a: str, val_b: str) -> str:
    """Determine relationship between two slot values."""
    a = val_a.lower().strip()
    b = val_b.lower().strip()

    if a == b:
        return "SAME"
    if a in b:
        return "A_SUBSET_OF_B"  # B is more specific
    if b in a:
        return "B_SUBSET_OF_A"  # A is more specific
    return "DIFFERENT"


# ===================================================================
# Test cases
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
    """Fully structural evaluation — zero LLM calls."""
    mem_a = test["memory_a"]
    mem_b = test["memory_b"]
    leaves = []

    # --- REGEX: metadata ---
    trust_a = extract_trust(mem_a)
    trust_b = extract_trust(mem_b)
    age_a = extract_age(mem_a)
    age_b = extract_age(mem_b)
    days_a = age_to_days(age_a)
    days_b = age_to_days(age_b)
    source_a = extract_source(mem_a)
    source_b = extract_source(mem_b)
    is_correction = source_b == "user_correction" or source_a == "user_correction"

    leaves.append({"type": "regex", "id": "trust", "detail": f"A={trust_a}, B={trust_b}"})
    leaves.append({"type": "regex", "id": "source", "detail": f"A={source_a}, B={source_b}"})
    if days_a is not None and days_b is not None:
        leaves.append({"type": "regex", "id": "recency", "detail": f"A={age_a}, B={age_b}"})

    # --- REGEX: slot extraction ---
    slots_a = extract_slots(mem_a)
    slots_b = extract_slots(mem_b)

    leaves.append({"type": "slot", "id": "slots_a", "detail": str(slots_a)})
    leaves.append({"type": "slot", "id": "slots_b", "detail": str(slots_b)})

    # Find overlapping slots
    shared_slots = set(slots_a.keys()) & set(slots_b.keys())
    slot_relationships = {}
    for slot in shared_slots:
        rel = values_contradict(slots_a[slot], slots_b[slot])
        slot_relationships[slot] = rel
        leaves.append({"type": "slot", "id": f"slot_{slot}", "detail": f"A='{slots_a[slot]}' vs B='{slots_b[slot]}' → {rel}"})

    has_contradicting_slot = any(r == "DIFFERENT" for r in slot_relationships.values())
    has_refinement_slot = any(r in ("A_SUBSET_OF_B", "B_SUBSET_OF_A") for r in slot_relationships.values())
    has_same_slot = any(r == "SAME" for r in slot_relationships.values())
    only_different_slots = len(shared_slots) == 0 and bool(slots_a) and bool(slots_b)

    # --- EMBEDDING: topic similarity ---
    fact_a = strip_metadata(mem_a)
    fact_b = strip_metadata(mem_b)
    emb_a = await get_embedding(session, fact_a)
    emb_b = await get_embedding(session, fact_b)
    similarity = cosine_sim(emb_a, emb_b)

    leaves.append({"type": "embedding", "id": "similarity", "detail": f"cosine={similarity:.4f}"})

    same_topic = similarity > 0.75
    near_dup = similarity > 0.95 and not has_contradicting_slot
    is_observation = source_b == "observation" or source_a == "observation"
    trust_a_low = trust_a is not None and trust_a < 0.5
    b_newer = days_a is not None and days_b is not None and days_b < days_a

    # --- PROPAGATION ---
    if near_dup and has_same_slot:
        verdict = "DUPLICATE"
        action = "merge_keep_higher_trust"
    elif near_dup and not has_contradicting_slot:
        verdict = "DUPLICATE"
        action = "merge_keep_higher_trust"
    elif has_contradicting_slot and is_correction and b_newer:
        verdict = "SUPERSEDED"
        action = "demote_older"
    elif has_contradicting_slot:
        verdict = "CONTRADICTION"
        action = "keep_higher_trust"
    elif has_refinement_slot and same_topic:
        verdict = "REFINEMENT"
        action = "keep_more_specific"
    elif same_topic and not has_contradicting_slot:
        if trust_a_low and is_observation:
            verdict = "DECAYED"
            action = "flag_for_review"
        else:
            verdict = "COMPATIBLE"
            action = "keep_both"
    elif trust_a_low and is_observation:
        verdict = "DECAYED"
        action = "flag_for_review"
    else:
        verdict = "UNRELATED"
        action = "keep_both"

    return {"verdict": verdict, "action": action, "leaves": leaves,
            "similarity": similarity, "slots_a": slots_a, "slots_b": slots_b,
            "shared_slots": shared_slots, "slot_relationships": slot_relationships}


async def run():
    p("=" * 60)
    p("STRUCTURAL BELIEF VERIFICATION: Zero LLM calls")
    p("=" * 60)
    p(f"Embed model: {EMBED_MODEL}")
    p(f"Tests: {len(BELIEF_TESTS)} memory pairs")
    p(f"Leaf types: regex (metadata + slots) + embedding (similarity)")
    p(f"LLM calls: ZERO")
    p("=" * 60)

    correct_verdicts = 0
    correct_actions = 0

    async with aiohttp.ClientSession() as session:
        for test in BELIEF_TESTS:
            t0 = time.time()
            result = await evaluate_pair(session, test)
            elapsed = time.time() - t0

            v_match = result["verdict"] == test["expected_verdict"]
            a_match = result["action"] == test["expected_action"]
            if v_match:
                correct_verdicts += 1
            if a_match:
                correct_actions += 1

            v_icon = "+" if v_match else "!"
            a_icon = "+" if a_match else "!"

            p(f"\n  [{v_icon}] {test['id']}")
            p(f"    A: {strip_metadata(test['memory_a'])[:60]}")
            p(f"    B: {strip_metadata(test['memory_b'])[:60]}")
            p(f"    Similarity: {result['similarity']:.4f}")
            p(f"    Slots A: {result['slots_a']}")
            p(f"    Slots B: {result['slots_b']}")
            if result["slot_relationships"]:
                for slot, rel in result["slot_relationships"].items():
                    p(f"    Slot [{slot}]: {rel}")
            p(f"    [{v_icon}] Verdict: {result['verdict']} (expected {test['expected_verdict']})")
            p(f"    [{a_icon}] Action: {result['action']} (expected {test['expected_action']})")
            p(f"    Time: {elapsed:.1f}s")

    total = len(BELIEF_TESTS)
    p(f"\n{'='*60}")
    p("RESULTS")
    p(f"{'='*60}")
    p(f"  Verdict accuracy: {correct_verdicts}/{total} ({correct_verdicts/total*100:.0f}%)")
    p(f"  Action accuracy:  {correct_actions}/{total} ({correct_actions/total*100:.0f}%)")
    p(f"  LLM calls: 0")
    p(f"  Embedding calls: {total * 2} (one per memory)")

    p(f"\n  PROGRESSION:")
    p(f"    Pure LLM leaves:     40% verdict")
    p(f"    Hybrid (regex+emb+LLM): 38% verdict")
    p(f"    Structural (regex+emb+slots): {correct_verdicts/total*100:.0f}% verdict")

    if correct_verdicts / total >= 0.75:
        p(f"\n  VIABLE for breathing loop. Zero LLM cost per cycle.")
    else:
        p(f"\n  Slot patterns need tuning or more coverage.")


if __name__ == "__main__":
    asyncio.run(run())
