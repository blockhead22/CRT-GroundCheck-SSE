"""BDG Frontier Tests: Three experiments to close the thread.

Test 1: Leaf accuracy degradation curve (code length vs accuracy)
Test 2: BDG on beliefs (can the tree verify memory contradictions?)
Test 3: Hybrid leaves (embedding + LLM + regex in one tree)

Each test runs independently. Results determine what transfers to CRT.
"""

import asyncio
import json
import time
import re
import math
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import aiohttp

import builtins
_real_open = builtins.open

import sys
sys.path.insert(0, str(Path(__file__).parent))
from config import OLLAMA_URL

MIRUS_MODEL = "llama3.2:latest"
EMBED_MODEL = "llama3.2:latest"  # Same model for embeddings via Ollama


def p(msg):
    print(msg, flush=True)


# ===================================================================
# SHARED: Mirus LLM leaf
# ===================================================================
async def llm_leaf(session, context: str, question: str) -> str:
    """Ask Mirus a factual question. Returns raw answer."""
    prompt = (
        f"Read this carefully:\n\n{context}\n\n"
        f"QUESTION: {question}\n\n"
        f"Answer YES or NO, then explain in one sentence."
    )
    payload = {
        "model": MIRUS_MODEL,
        "prompt": prompt,
        "system": "Answer factual questions. Start with YES or NO.",
        "stream": False,
        "options": {"temperature": 0.0, "num_predict": 80, "num_ctx": 2048},
    }
    async with session.post(f"{OLLAMA_URL}/api/generate", json=payload,
                           timeout=aiohttp.ClientTimeout(total=20)) as resp:
        data = await resp.json()
    return data.get("response", "").strip()


# ===================================================================
# SHARED: Embedding leaf
# ===================================================================
async def get_embedding(session, text: str) -> List[float]:
    """Get embedding vector from Ollama."""
    payload = {"model": EMBED_MODEL, "input": text}
    async with session.post(f"{OLLAMA_URL}/api/embed", json=payload,
                           timeout=aiohttp.ClientTimeout(total=15)) as resp:
        data = await resp.json()
    embeddings = data.get("embeddings", [[]])
    return embeddings[0] if embeddings else []


def cosine_similarity(a: List[float], b: List[float]) -> float:
    """Cosine similarity between two vectors."""
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(x * x for x in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


# ===================================================================
# TEST 1: Degradation curve — accuracy vs code length
# ===================================================================
async def test_degradation(session):
    """Test leaf accuracy at increasing code lengths."""
    p("\n" + "=" * 60)
    p("TEST 1: Leaf accuracy degradation curve")
    p("=" * 60)

    # Base code that we'll pad to different lengths
    base_code = '''def _get_thread_memory_ids(self, thread_id: str, limit: int = 500) -> List[str]:
    mem_db_path = self._resolve_memory_db_path(thread_id)
    if not mem_db_path or not Path(mem_db_path).exists():
        return []
    try:
        conn = sqlite3.connect(mem_db_path, timeout=30.0)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        columns = {{str(row[1]).lower() for row in cursor.execute("PRAGMA table_info(memories)").fetchall()}}
        if "memory_id" not in columns:
            conn.close()
            return []
        rows = cursor.execute(query, tuple(params)).fetchall()
        conn.close()
        return [str(row["memory_id"]) for row in rows if row["memory_id"]]
    except Exception as e:
        logger.debug(f"Error: {{e}}")
        return []'''

    # Padding: realistic-looking code to increase length without changing the target
    padding_block = '''
    def _helper_{n}(self, data):
        """Process data chunk {n}."""
        result = []
        for item in data:
            if isinstance(item, dict):
                value = item.get("value", 0)
                if value > 0:
                    result.append(value * 1.5)
                else:
                    result.append(0)
            elif isinstance(item, str):
                result.append(item.strip().lower())
        return result
'''

    # Question that has a definite answer in the base code
    question = "Is conn.close() called inside a finally block or context manager?"
    expected = "NO"

    lengths = [20, 50, 100, 200, 400, 800]
    results = []

    for target_lines in lengths:
        # Build padded code
        code = base_code
        n = 0
        while len(code.split("\n")) < target_lines:
            n += 1
            code = code + padding_block.format(n=n)

        actual_lines = len(code.split("\n"))

        t0 = time.time()
        answer = await llm_leaf(session, f"```python\n{code}\n```", question)
        elapsed = time.time() - t0

        correct = expected.lower() in answer.lower()[:20]
        results.append({
            "target_lines": target_lines,
            "actual_lines": actual_lines,
            "correct": correct,
            "time": elapsed,
            "answer": answer[:80],
        })

        icon = "+" if correct else "!"
        p(f"  [{icon}] {actual_lines} lines: {'CORRECT' if correct else 'WRONG'} ({elapsed:.1f}s) — {answer[:60]}")

    p(f"\n  Degradation curve:")
    for r in results:
        bar = "█" * (10 if r["correct"] else 0) + "░" * (10 if not r["correct"] else 0)
        p(f"    {r['actual_lines']:>4} lines: {bar} {'✓' if r['correct'] else '✗'} ({r['time']:.1f}s)")

    crossover = None
    for r in results:
        if not r["correct"]:
            crossover = r["actual_lines"]
            break
    if crossover:
        p(f"\n  CROSSOVER: accuracy drops at ~{crossover} lines")
    else:
        p(f"\n  NO CROSSOVER: accurate through {results[-1]['actual_lines']} lines")

    return results


# ===================================================================
# TEST 2: BDG on beliefs — can the tree verify memory contradictions?
# ===================================================================
async def test_beliefs(session):
    """Test BDG tree on belief/memory verification."""
    p("\n" + "=" * 60)
    p("TEST 2: BDG on beliefs")
    p("=" * 60)

    # Simulated memory pairs with known relationships
    belief_tests = [
        {
            "id": "direct_contradiction",
            "memory_a": "Nick lives in Milwaukee, Wisconsin. Trust: 0.9, Source: user_fact",
            "memory_b": "Nick lives in Chicago, Illinois. Trust: 0.3, Source: user_correction",
            "leaves": [
                {"question": "Do both memories make a claim about where Nick lives?",
                 "expected": "YES"},
                {"question": "Do the two memories agree on the location?",
                 "expected": "NO"},
                {"question": "Is memory A's trust score higher than memory B's?",
                 "expected": "YES"},
            ],
            "expected_verdict": "CONTRADICTION",
        },
        {
            "id": "complementary",
            "memory_a": "Nick is a developer. Trust: 0.85, Source: user_fact",
            "memory_b": "Nick works on AI systems. Trust: 0.7, Source: inferred",
            "leaves": [
                {"question": "Do both memories make a claim about Nick's work or profession?",
                 "expected": "YES"},
                {"question": "Do the two memories contradict each other?",
                 "expected": "NO"},
                {"question": "Could both memories be true simultaneously?",
                 "expected": "YES"},
            ],
            "expected_verdict": "COMPATIBLE",
        },
        {
            "id": "stale_override",
            "memory_a": "Nick's favorite language is Python. Trust: 0.6, Source: user_fact, Age: 6 months",
            "memory_b": "Nick's favorite language is Rust. Trust: 0.8, Source: user_correction, Age: 2 days",
            "leaves": [
                {"question": "Do both memories claim a favorite programming language?",
                 "expected": "YES"},
                {"question": "Do they agree on which language is the favorite?",
                 "expected": "NO"},
                {"question": "Is memory B more recent than memory A?",
                 "expected": "YES"},
                {"question": "Is memory B's trust score higher than memory A's?",
                 "expected": "YES"},
            ],
            "expected_verdict": "SUPERSEDED",
        },
        {
            "id": "unrelated",
            "memory_a": "Nick lives in Milwaukee. Trust: 0.9, Source: user_fact",
            "memory_b": "Nick prefers dark mode in editors. Trust: 0.7, Source: preference",
            "leaves": [
                {"question": "Do both memories discuss the same topic (location, work, preferences, etc)?",
                 "expected": "NO"},
                {"question": "Could any information in memory A affect the validity of memory B?",
                 "expected": "NO"},
            ],
            "expected_verdict": "UNRELATED",
        },
        {
            "id": "confidence_decay",
            "memory_a": "Nick said he enjoys hiking. Trust: 0.4, Source: user_fact, Age: 1 year",
            "memory_b": "Nick has not mentioned hiking in 8 months. Trust: N/A, Source: observation",
            "leaves": [
                {"question": "Does memory A contain a positive claim about a preference?",
                 "expected": "YES"},
                {"question": "Does memory B suggest the preference may no longer be current?",
                 "expected": "YES"},
                {"question": "Is memory A's trust score above 0.5?",
                 "expected": "NO"},
            ],
            "expected_verdict": "DECAYED",
        },
    ]

    total_leaves = 0
    correct_leaves = 0
    correct_verdicts = 0

    for test in belief_tests:
        context = (
            f"MEMORY A: {test['memory_a']}\n"
            f"MEMORY B: {test['memory_b']}"
        )

        p(f"\n  [{test['id']}]")
        p(f"    A: {test['memory_a'][:70]}")
        p(f"    B: {test['memory_b'][:70]}")

        leaf_correct = 0
        for leaf in test["leaves"]:
            answer = await llm_leaf(session, context, leaf["question"])
            expected = leaf["expected"]
            is_correct = expected.lower() in answer.lower()[:20]
            total_leaves += 1
            if is_correct:
                correct_leaves += 1
                leaf_correct += 1

            icon = "+" if is_correct else "!"
            p(f"    [{icon}] Q: {leaf['question'][:60]}")
            p(f"        Expected: {expected}, Got: {answer[:50]}")

        # Simple verdict propagation
        all_correct = leaf_correct == len(test["leaves"])
        if all_correct:
            correct_verdicts += 1
        p(f"    Verdict: {'CORRECT' if all_correct else 'WRONG'} (expected {test['expected_verdict']})")

    p(f"\n  RESULTS:")
    p(f"    Leaf accuracy: {correct_leaves}/{total_leaves} ({correct_leaves/total_leaves*100:.0f}%)")
    p(f"    Verdict accuracy: {correct_verdicts}/{len(belief_tests)} ({correct_verdicts/len(belief_tests)*100:.0f}%)")

    return {"leaf_accuracy": correct_leaves / total_leaves, "verdict_accuracy": correct_verdicts / len(belief_tests)}


# ===================================================================
# TEST 3: Hybrid leaves — embedding + LLM + regex in one tree
# ===================================================================
async def test_hybrid(session):
    """Test hybrid leaf types for intent routing."""
    p("\n" + "=" * 60)
    p("TEST 3: Hybrid leaves (embedding + LLM + regex)")
    p("=" * 60)

    # Build prototype embeddings for personal vs knowledge queries
    p("  Building prototype embeddings...")
    personal_protos = [
        "What is my name?",
        "Where do I live?",
        "What's my favorite color?",
        "Tell me about myself",
        "Do you remember my birthday?",
    ]
    knowledge_protos = [
        "What is the capital of France?",
        "How does photosynthesis work?",
        "Who was the first president?",
        "What is the speed of light?",
        "Explain quantum mechanics",
    ]

    personal_embeddings = []
    knowledge_embeddings = []
    for text in personal_protos:
        emb = await get_embedding(session, text)
        if emb:
            personal_embeddings.append(emb)
    for text in knowledge_protos:
        emb = await get_embedding(session, text)
        if emb:
            knowledge_embeddings.append(emb)

    if not personal_embeddings or not knowledge_embeddings:
        p("  ERROR: Could not build prototype embeddings")
        return None

    # Average prototype embeddings
    def avg_embedding(embeddings):
        if not embeddings:
            return []
        n = len(embeddings)
        dim = len(embeddings[0])
        return [sum(e[i] for e in embeddings) / n for i in range(dim)]

    personal_centroid = avg_embedding(personal_embeddings)
    knowledge_centroid = avg_embedding(knowledge_embeddings)
    p(f"  Built centroids: personal ({len(personal_centroid)} dims), knowledge ({len(knowledge_centroid)} dims)")

    # Hybrid routing tree
    test_queries = [
        {"query": "What's my name?", "expected": "personal", "expected_memories": True},
        {"query": "What is my name?", "expected": "personal", "expected_memories": True},
        {"query": "Who am I?", "expected": "personal", "expected_memories": True},
        {"query": "Where do I live?", "expected": "personal", "expected_memories": True},
        {"query": "What's my favorite color?", "expected": "personal", "expected_memories": True},
        {"query": "What is the capital of France?", "expected": "knowledge", "expected_memories": False},
        {"query": "Who was the first president?", "expected": "knowledge", "expected_memories": False},
        {"query": "How does photosynthesis work?", "expected": "knowledge", "expected_memories": False},
        {"query": "What's the weather like?", "expected": "knowledge", "expected_memories": False},
        {"query": "Hello", "expected": "greeting", "expected_memories": False},
        {"query": "No, my name is Sarah", "expected": "correction", "expected_memories": True},
        {"query": "Actually, I live in Chicago", "expected": "correction", "expected_memories": True},
        {"query": "Write me a python function", "expected": "task", "expected_memories": False},
        {"query": "Tell me about myself", "expected": "personal", "expected_memories": True},
        {"query": "What do you know about me?", "expected": "personal", "expected_memories": True},
    ]

    correct_route = 0
    correct_memory = 0

    for test in test_queries:
        query = test["query"]
        query_lower = query.lower().strip()

        # LEAF 1: Regex — contains personal pronoun?
        has_pronoun = bool(re.search(r'\b(my|i|me|mine|myself|i\'m|i\'ve|i\'d)\b', query_lower))

        # LEAF 2: Regex — starts with correction?
        starts_correction = bool(re.search(r'^(no|nope|actually|wrong|incorrect|that\'s not)', query_lower))

        # LEAF 3: Regex — pure greeting?
        is_greeting = bool(re.match(r'^(hi|hello|hey|howdy|yo|sup|greetings)[!.,]?\s*$', query_lower))

        # LEAF 4: Regex — asks for code?
        asks_code = bool(re.search(r'(write|create|code|build|implement|generate)\s.*(function|script|program|code|python|javascript)', query_lower))

        # LEAF 5: Embedding — closer to personal or knowledge?
        query_emb = await get_embedding(session, query)
        personal_sim = cosine_similarity(query_emb, personal_centroid) if query_emb else 0
        knowledge_sim = cosine_similarity(query_emb, knowledge_centroid) if query_emb else 0
        embedding_says_personal = personal_sim > knowledge_sim

        # LEAF 6: LLM — does this ask the user to recall stored information?
        # Only called when embedding is ambiguous
        llm_says_recall = False
        used_llm = False
        if abs(personal_sim - knowledge_sim) < 0.05 and has_pronoun:
            answer = await llm_leaf(session, f'User message: "{query}"',
                                   "Is the user asking the assistant to remember or recall something about them?")
            llm_says_recall = answer.lower().startswith("yes")
            used_llm = True

        # PROPAGATION
        if is_greeting:
            route = "greeting"
            inject = False
        elif starts_correction and has_pronoun:
            route = "correction"
            inject = True
        elif starts_correction:
            route = "correction"
            inject = True
        elif has_pronoun and embedding_says_personal:
            route = "personal"
            inject = True
        elif has_pronoun and not embedding_says_personal and llm_says_recall:
            route = "personal"
            inject = True
        elif has_pronoun:
            route = "personal"  # pronoun = personal as default
            inject = True
        elif asks_code:
            route = "task"
            inject = False
        elif not embedding_says_personal:
            route = "knowledge"
            inject = False
        else:
            route = "knowledge"
            inject = False

        match = route == test["expected"]
        mem_match = inject == test["expected_memories"]
        if match:
            correct_route += 1
        if mem_match:
            correct_memory += 1

        icon = "+" if match else "!"
        mem_icon = "+" if mem_match else "!"
        p(f"  [{icon}][{mem_icon}] \"{query}\"")
        p(f"    Route: {route} (expected {test['expected']}), Memories: {inject}")
        p(f"    Signals: pronoun={has_pronoun}, correction={starts_correction}, greeting={is_greeting}, code={asks_code}")
        p(f"    Embedding: personal={personal_sim:.3f}, knowledge={knowledge_sim:.3f} → {'personal' if embedding_says_personal else 'knowledge'}")
        if used_llm:
            p(f"    LLM fallback: recall={llm_says_recall}")

    total = len(test_queries)
    p(f"\n  RESULTS:")
    p(f"    Route accuracy: {correct_route}/{total} ({correct_route/total*100:.0f}%)")
    p(f"    Memory accuracy: {correct_memory}/{total} ({correct_memory/total*100:.0f}%)")
    p(f"\n  COMPARISON:")
    p(f"    Pure regex (production):  ~70% (known failures on 'What's my name?')")
    p(f"    Pure BDG LLM leaves:      65-70% (semantic judgment ceiling)")
    p(f"    Hybrid (regex+embed+LLM): {correct_route/total*100:.0f}%")


# ===================================================================
# MAIN
# ===================================================================
async def run():
    p("=" * 60)
    p("BDG FRONTIER: Three closing experiments")
    p("=" * 60)
    p(f"Model: {MIRUS_MODEL}")
    p("=" * 60)

    async with aiohttp.ClientSession() as session:
        degradation = await test_degradation(session)
        beliefs = await test_beliefs(session)
        await test_hybrid(session)

    p(f"\n{'='*60}")
    p("SESSION SUMMARY")
    p(f"{'='*60}")
    p(f"  Test 1 (degradation): {'Crossover found' if any(not r['correct'] for r in degradation) else 'No crossover'}")
    p(f"  Test 2 (beliefs): {beliefs['leaf_accuracy']*100:.0f}% leaf, {beliefs['verdict_accuracy']*100:.0f}% verdict")
    p(f"  Test 3 (hybrid): see above")


if __name__ == "__main__":
    asyncio.run(run())
