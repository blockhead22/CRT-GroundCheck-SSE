"""BDG Intent Router: Replace pattern matching with reasoning trees.

Instead of 50+ regex patterns that miss "What's my name?",
use 5 factual leaf questions answered by Mirus at 94% accuracy.

The tree structure IS the routing logic. Propagation IS the decision.

Test against the exact failure case from hardest_bug.py:
- "What's my name?" should route to identity/fact_question
- "Who am I?" should route to identity/fact_question
- "What is the capital of France?" should route to knowledge_query
- "Write me a python function" should route to task_code
"""

import asyncio
import json
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


# ---------------------------------------------------------------------------
# The BDG routing tree — each branch is a routing hypothesis
# Leaves are factual questions about the query, not the code
# Propagation determines the route
# ---------------------------------------------------------------------------
ROUTING_TREE = {
    "branches": [
        {
            "id": "personal_identity",
            "route": "fact_question",
            "inject_memories": True,
            "priority": 1,
            "description": "Query is about the user's personal identity or stored facts",
            "leaves": [
                {
                    "question": "Does this query contain a personal pronoun referring to the user (my, I, me, mine, I'm, myself)?",
                    "id": "has_pronoun",
                    "signal": "YES",
                },
                {
                    "question": "Does this query ask about the USER's own personal attribute (the user's name, age, location, job, preference, favorite, birthday)? Asking about someone else (a president, a celebrity) does NOT count.",
                    "id": "has_personal_attr",
                    "signal": "YES",
                },
                {
                    "question": "Is this query asking Aether to recall something it was previously told about the user?",
                    "id": "asks_recall",
                    "signal": "YES",
                },
            ],
            "rule": "any",  # ANY leaf signaling YES → route here
        },
        {
            "id": "correction",
            "route": "fact_correction",
            "inject_memories": True,
            "priority": 0,  # highest priority
            "description": "User is correcting something Aether said or believes",
            "leaves": [
                {
                    "question": "Does this query start with a word that explicitly negates or corrects a previous statement (no, nope, actually, wrong, incorrect, that's not right)? Normal question words like 'what', 'who', 'how' do NOT count as corrections.",
                    "id": "starts_correction",
                    "signal": "YES",
                },
                {
                    "question": "Does this query provide NEW or CORRECTED factual information that replaces something said before (e.g. 'it's actually X', 'not X but Y', 'I meant X')? Simply asking a question does NOT count as a correction.",
                    "id": "has_replacement",
                    "signal": "YES",
                },
            ],
            "rule": "any",
        },
        {
            "id": "meta_memory",
            "route": "meta_memory",
            "inject_memories": True,
            "priority": 2,
            "description": "User is asking about what Aether knows/remembers",
            "leaves": [
                {
                    "question": "Does this query EXPLICITLY ask what the assistant knows, remembers, or has stored? It must directly reference the assistant's memory or knowledge (e.g. 'what do you know about me', 'what have I told you', 'show my memories'). A simple question like 'hello' or 'what's the weather' does NOT count.",
                    "id": "asks_about_memory",
                    "signal": "YES",
                },
            ],
            "rule": "any",
        },
        {
            "id": "knowledge",
            "route": "knowledge_query",
            "inject_memories": False,
            "priority": 5,
            "description": "General knowledge question not about the user",
            "leaves": [
                {
                    "question": "Is this query asking about general world knowledge (history, science, geography, definitions) rather than about the user personally?",
                    "id": "is_world_knowledge",
                    "signal": "YES",
                },
                {
                    "question": "Does this query mention the user or use personal pronouns (my, I, me)?",
                    "id": "has_personal_ref",
                    "signal": "NO",  # Must NOT have personal references
                },
            ],
            "rule": "all",  # ALL leaves must signal → route here
        },
        {
            "id": "task_code",
            "route": "task_code",
            "inject_memories": False,
            "priority": 4,
            "description": "User wants code written or a programming task done",
            "leaves": [
                {
                    "question": "Does this query ask for code to be written, a program to be created, or a technical implementation?",
                    "id": "asks_code",
                    "signal": "YES",
                },
            ],
            "rule": "any",
        },
        {
            "id": "greeting",
            "route": "chat_greeting",
            "inject_memories": False,
            "priority": 3,
            "description": "Simple greeting with no embedded question",
            "leaves": [
                {
                    "question": "Is this ONLY a greeting (hello, hi, hey) with no other question or request embedded in it?",
                    "id": "pure_greeting",
                    "signal": "YES",
                },
            ],
            "rule": "any",
        },
    ]
}


# ---------------------------------------------------------------------------
# Mirus answers leaf questions about the user's query
# ---------------------------------------------------------------------------
async def answer_leaf(session, query: str, leaf_question: str) -> str:
    """Ask Mirus a factual question about the user's query."""
    prompt = (
        f"A user sent this message to an AI assistant:\n\n"
        f"USER MESSAGE: \"{query}\"\n\n"
        f"QUESTION: {leaf_question}\n\n"
        f"Answer YES or NO. Then explain in one short sentence."
    )

    payload = {
        "model": MIRUS_MODEL,
        "prompt": prompt,
        "system": "You analyze user messages and answer factual questions about them. Start with YES or NO.",
        "stream": False,
        "options": {"temperature": 0.0, "num_predict": 80, "num_ctx": 1024},
    }

    async with session.post(f"{OLLAMA_URL}/api/generate", json=payload,
                           timeout=aiohttp.ClientTimeout(total=15)) as resp:
        data = await resp.json()
    return data.get("response", "").strip()


def check_signal(answer: str, expected_signal: str) -> bool:
    """Check if the answer matches the expected signal."""
    answer_lower = answer.lower().strip()
    if expected_signal == "YES":
        return answer_lower.startswith("yes")
    elif expected_signal == "NO":
        return answer_lower.startswith("no")
    return False


# ---------------------------------------------------------------------------
# BDG propagation: evaluate all branches, pick the best route
# ---------------------------------------------------------------------------
async def route_query(session, query: str) -> Dict:
    """Route a query through the BDG tree."""
    results = []

    for branch in ROUTING_TREE["branches"]:
        leaf_results = []
        for leaf in branch["leaves"]:
            answer = await answer_leaf(session, query, leaf["question"])
            matched = check_signal(answer, leaf["signal"])
            leaf_results.append({
                "id": leaf["id"],
                "question": leaf["question"],
                "answer": answer[:100],
                "expected_signal": leaf["signal"],
                "matched": matched,
            })

        # Propagation rule
        if branch["rule"] == "any":
            branch_fires = any(lr["matched"] for lr in leaf_results)
        elif branch["rule"] == "all":
            branch_fires = all(lr["matched"] for lr in leaf_results)
        else:
            branch_fires = False

        results.append({
            "branch_id": branch["id"],
            "route": branch["route"],
            "inject_memories": branch["inject_memories"],
            "priority": branch["priority"],
            "fires": branch_fires,
            "leaves": leaf_results,
        })

    # Pick the highest-priority branch that fires
    firing = [r for r in results if r["fires"]]
    if firing:
        firing.sort(key=lambda r: r["priority"])
        winner = firing[0]
    else:
        winner = {
            "branch_id": "fallback",
            "route": "unknown",
            "inject_memories": True,  # inject memories for unknown queries (safe default)
            "priority": 99,
            "fires": False,
            "leaves": [],
        }

    return {
        "route": winner["route"],
        "inject_memories": winner["inject_memories"],
        "branch_id": winner["branch_id"],
        "all_branches": results,
    }


# ---------------------------------------------------------------------------
# Test cases — including the hardest_bug failure case
# ---------------------------------------------------------------------------
TEST_CASES = [
    # THE BUG: "What's my name?" was classified as knowledge_query
    {"query": "What's my name?", "expected_route": "fact_question", "expected_memories": True},
    {"query": "What is my name?", "expected_route": "fact_question", "expected_memories": True},
    {"query": "Do you know my name?", "expected_route": "fact_question", "expected_memories": True},
    {"query": "Who am I?", "expected_route": "fact_question", "expected_memories": True},
    {"query": "Where do I live?", "expected_route": "fact_question", "expected_memories": True},
    {"query": "What's my favorite color?", "expected_route": "fact_question", "expected_memories": True},

    # Knowledge queries — should NOT inject memories
    {"query": "What is the capital of France?", "expected_route": "knowledge_query", "expected_memories": False},
    {"query": "Who was the first president?", "expected_route": "knowledge_query", "expected_memories": False},
    {"query": "How does photosynthesis work?", "expected_route": "knowledge_query", "expected_memories": False},

    # Corrections
    {"query": "No, my name is Sarah", "expected_route": "fact_correction", "expected_memories": True},
    {"query": "Actually, I live in Chicago", "expected_route": "fact_correction", "expected_memories": True},

    # Code tasks
    {"query": "Write me a python hello world", "expected_route": "task_code", "expected_memories": False},
    {"query": "Create a function that sorts a list", "expected_route": "task_code", "expected_memories": False},

    # Greetings
    {"query": "Hello", "expected_route": "chat_greeting", "expected_memories": False},
    {"query": "Hey there", "expected_route": "chat_greeting", "expected_memories": False},

    # Meta
    {"query": "What do you know about me?", "expected_route": "meta_memory", "expected_memories": True},
    {"query": "What have I told you?", "expected_route": "meta_memory", "expected_memories": True},

    # Edge cases — the tricky ones
    {"query": "What's the weather like?", "expected_route": "knowledge_query", "expected_memories": False},
    {"query": "Hello, what's my name?", "expected_route": "fact_question", "expected_memories": True},
    {"query": "Tell me about myself", "expected_route": "fact_question", "expected_memories": True},
]

# Also test against the original regex router for comparison
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "personal_agent"))


def regex_route(query: str) -> Tuple[str, bool]:
    """Route using the original regex router for comparison."""
    try:
        from intent_router import IntentRouter, Intent
        router = IntentRouter()
        result = router.classify(query)
        # Map to our route names
        intent_to_route = {
            Intent.FACT_QUESTION: "fact_question",
            Intent.FACT_STATEMENT: "fact_statement",
            Intent.FACT_CORRECTION: "fact_correction",
            Intent.KNOWLEDGE_QUERY: "knowledge_query",
            Intent.KNOWLEDGE_OPINION: "knowledge_opinion",
            Intent.TASK_CODE: "task_code",
            Intent.TASK_EXPLAIN: "task_explain",
            Intent.TASK_GENERAL: "task_general",
            Intent.TASK_SUMMARIZE: "task_summarize",
            Intent.CHAT_GREETING: "chat_greeting",
            Intent.CHAT_FAREWELL: "chat_farewell",
            Intent.CHAT_SMALLTALK: "chat_smalltalk",
            Intent.CHAT_EMOTION: "chat_emotion",
            Intent.META_SYSTEM: "meta_system",
            Intent.META_MEMORY: "meta_memory",
            Intent.UNKNOWN: "unknown",
        }
        route = intent_to_route.get(result.intent, "unknown")
        # Memory injection: only for fact/meta intents in the original system
        inject = route in ("fact_question", "fact_statement", "fact_correction", "meta_memory")
        return route, inject
    except Exception as e:
        return f"error: {e}", False


async def run():
    p("=" * 60)
    p("BDG INTENT ROUTER: Tree-based query routing")
    p("=" * 60)
    p(f"Model: {MIRUS_MODEL}")
    p(f"Test cases: {len(TEST_CASES)}")
    p(f"Comparing: BDG tree vs regex patterns")
    p("=" * 60)

    bdg_correct = 0
    regex_correct = 0
    memory_correct_bdg = 0
    memory_correct_regex = 0

    async with aiohttp.ClientSession() as session:
        for i, test in enumerate(TEST_CASES):
            query = test["query"]
            expected = test["expected_route"]
            expected_mem = test["expected_memories"]

            # BDG route
            t0 = time.time()
            bdg_result = await route_query(session, query)
            bdg_time = time.time() - t0

            # Regex route
            regex_result, regex_mem = regex_route(query)

            # Score
            bdg_match = bdg_result["route"] == expected
            regex_match = regex_result == expected
            bdg_mem_match = bdg_result["inject_memories"] == expected_mem
            regex_mem_match = regex_mem == expected_mem

            if bdg_match:
                bdg_correct += 1
            if regex_match:
                regex_correct += 1
            if bdg_mem_match:
                memory_correct_bdg += 1
            if regex_mem_match:
                memory_correct_regex += 1

            bdg_icon = "+" if bdg_match else "!"
            regex_icon = "+" if regex_match else "!"
            mem_icon = "+" if bdg_mem_match else "!"

            p(f"\n  [{bdg_icon}] \"{query}\"")
            p(f"    Expected: {expected} (memories={expected_mem})")
            p(f"    BDG:   {bdg_result['route']} via {bdg_result['branch_id']} (memories={bdg_result['inject_memories']}) [{bdg_time:.1f}s]")
            p(f"    Regex: {regex_result} (memories={regex_mem})")

            # Show leaf details for mismatches
            if not bdg_match:
                for branch in bdg_result["all_branches"]:
                    if branch["fires"]:
                        p(f"    FIRED: {branch['branch_id']}")
                        for leaf in branch["leaves"]:
                            p(f"      {leaf['id']}: {leaf['answer'][:60]}")

    total = len(TEST_CASES)
    p(f"\n{'='*60}")
    p("RESULTS")
    p(f"{'='*60}")
    p(f"  BDG routing:    {bdg_correct}/{total} ({bdg_correct/total*100:.0f}%)")
    p(f"  Regex routing:  {regex_correct}/{total} ({regex_correct/total*100:.0f}%)")
    p(f"  BDG memories:   {memory_correct_bdg}/{total} ({memory_correct_bdg/total*100:.0f}%)")
    p(f"  Regex memories: {memory_correct_regex}/{total} ({memory_correct_regex/total*100:.0f}%)")
    p(f"\n  THE BUG TEST:")
    p(f"    'What's my name?' → BDG: {bdg_correct}/{total}, Regex: {regex_correct}/{total}")


if __name__ == "__main__":
    asyncio.run(run())
