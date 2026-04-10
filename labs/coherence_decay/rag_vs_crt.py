"""RAG vs CRT: The Falsification Test

Does CRT's full apparatus (trust scores, contradiction flags, belief/speech gates)
produce measurably better outputs than plain cosine-similarity RAG?

Setup:
- Same memory database (crt_memory_shared.db, ~900 memories)
- Same queries (20 test queries covering personal, knowledge, edge cases)
- Two retrieval paths:
  A) Plain RAG: cosine similarity, top-K, no trust/contradiction metadata
  B) Full CRT: trust-weighted scoring, contradiction flags, belief context
- Same model (Claude via CLI) answers both, blind to which path produced the context
- Automated scoring: does the response use stored facts correctly?

If plain RAG matches CRT, the entire trust/contradiction apparatus is overhead.
If CRT wins, trust scoring and governance are doing real work.
"""

import asyncio
import json
import os
import subprocess
import sys
import time
import sqlite3
import numpy as np
from pathlib import Path
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass

# Project imports
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "personal_agent"))

import builtins
_real_open = builtins.open

CLAUDE_CLI = os.getenv(
    "CLAUDE_CODE_EXECPATH",
    r"C:\Users\block\AppData\Roaming\Claude\claude-code\2.1.92\claude.exe"
)
MEMORY_DB = r"D:\AI_round2\personal_agent\crt_memory_shared.db"
LOG_FILE = Path(__file__).parent / "results" / "raw" / "rag_vs_crt.jsonl"


def p(msg):
    print(str(msg).encode("ascii", "replace").decode("ascii"), flush=True)


def log(entry):
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    with _real_open(LOG_FILE, "a") as f:
        f.write(json.dumps(entry, default=str) + "\n")


# ---------------------------------------------------------------------------
# Load memories from the shared database
# ---------------------------------------------------------------------------
def sanitize_text(text: str) -> str:
    """Strip non-ASCII characters that break Windows encoding."""
    return text.encode("ascii", "replace").decode("ascii")


def load_all_memories() -> List[Dict]:
    """Load all active memories from the shared DB."""
    conn = sqlite3.connect(MEMORY_DB, timeout=30.0)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    rows = cursor.execute("""
        SELECT memory_id, text, trust, confidence, source, timestamp,
               vector_json, deprecated
        FROM memories
        WHERE deprecated = 0
        ORDER BY timestamp DESC
    """).fetchall()
    conn.close()

    memories = []
    for row in rows:
        vec = []
        try:
            vec = json.loads(row["vector_json"])
        except:
            pass
        memories.append({
            "memory_id": row["memory_id"],
            "text": row["text"],
            "trust": float(row["trust"] or 0.0),
            "confidence": float(row["confidence"] or 0.0),
            "source": row["source"] or "",
            "timestamp": float(row["timestamp"] or 0.0),
            "vector": np.array(vec, dtype=np.float32) if vec else None,
        })

    return memories


def encode_query(query: str) -> np.ndarray:
    """Encode a query using the production embedding model."""
    from embeddings import encode_text
    return encode_text(query)


# ---------------------------------------------------------------------------
# PATH A: Plain RAG (cosine similarity only, no metadata)
# ---------------------------------------------------------------------------
def retrieve_plain_rag(query: str, memories: List[Dict], k: int = 5) -> str:
    """Pure cosine similarity retrieval. No trust. No contradiction flags. No metadata."""
    query_vec = encode_query(query)

    scored = []
    for mem in memories:
        if mem["vector"] is not None and len(mem["vector"]) > 0:
            sim = float(np.dot(query_vec, mem["vector"]))
            scored.append((mem, sim))

    scored.sort(key=lambda x: x[1], reverse=True)
    top = scored[:k]

    # Format: plain text, no trust scores, no metadata
    lines = ["## Relevant memories:"]
    for mem, sim in top:
        text = sanitize_text(mem["text"].strip()[:200])
        lines.append(f"- {text}")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# PATH B: Full CRT (trust-weighted, with metadata)
# ---------------------------------------------------------------------------
def retrieve_crt(query: str, memories: List[Dict], k: int = 5) -> str:
    """Trust-weighted retrieval with full CRT metadata."""
    query_vec = encode_query(query)
    now = time.time()

    # CRT scoring: R_i = s_i * rho_i * w_i
    alpha = 0.6  # trust vs confidence weight
    recency_lambda = 30 * 86400  # 30 day decay

    scored = []
    for mem in memories:
        if mem["vector"] is not None and len(mem["vector"]) > 0:
            sim = float(np.dot(query_vec, mem["vector"]))
            age = now - mem["timestamp"]
            recency = np.exp(-age / recency_lambda)
            belief_weight = alpha * mem["trust"] + (1 - alpha) * mem["confidence"]
            score = sim * recency * belief_weight
            scored.append((mem, score, sim))

    scored.sort(key=lambda x: x[1], reverse=True)
    top = scored[:k]

    # Format: with trust scores and source metadata
    lines = ["## What I know about you (sorted by trust, highest first):"]
    for mem, score, sim in top:
        text = sanitize_text(mem["text"].strip()[:200])
        trust = mem["trust"]
        source = mem["source"]
        lines.append(f"- [trust:{trust:.2f}] [source:{source}] {text}")

    # Add contradiction context if any
    # Check for memories with low trust in the same topic area
    low_trust = [m for m, s, _ in scored[:20] if m["trust"] < 0.3 and s > 0]
    if low_trust:
        lines.append("")
        lines.append("## Low-confidence memories (may be outdated):")
        for mem in low_trust[:3]:
            text = sanitize_text(mem["text"].strip()[:150])
            lines.append(f"- [trust:{mem['trust']:.2f}] {text}")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Test queries — things where trust/contradiction should matter
# ---------------------------------------------------------------------------
TEST_QUERIES = [
    # Personal facts (trust should help)
    {"query": "What's my name?", "category": "personal", "expected_contains": ["nick"]},
    {"query": "Where do I live?", "category": "personal", "expected_contains": ["sussex", "wisconsin", "milwaukee", "waukesha"]},
    {"query": "What do I do for work?", "category": "personal", "expected_contains": ["developer", "freelance", "walmart", "stocker"]},

    # Preferences (trust matters for corrections)
    {"query": "What's my favorite color?", "category": "preference", "expected_contains": ["orange"]},
    {"query": "Do I like coffee?", "category": "preference", "expected_contains": ["coffee", "steaming cup"]},

    # Medical/sensitive (high trust memories should dominate)
    {"query": "What do you know about my health?", "category": "medical", "expected_contains": ["leukemia", "cgvhd", "transplant", "bone marrow"]},

    # Meta/system (should use high-trust system knowledge)
    {"query": "What is CRT?", "category": "system", "expected_contains": ["contradiction", "trust", "belief", "resonance"]},
    {"query": "What have I been working on recently?", "category": "recent", "expected_contains": ["bdg", "tension", "audit", "heartbeat"]},

    # Edge cases (where wrong memories could mislead)
    {"query": "Do I work at a design studio?", "category": "correction", "expected_contains": ["not", "don't", "no"]},
    {"query": "Tell me about my friend Jake", "category": "third_party", "expected_contains": ["tesla"]},

    # Philosophical (should pull from values/beliefs)
    {"query": "What drives me?", "category": "philosophical", "expected_contains": ["leukemia", "survival", "honest", "epistemic", "promise"]},
    {"query": "What am I afraid of?", "category": "philosophical", "expected_contains": ["gaslit", "validation", "imposter"]},

    # Ambiguous (where trust differentiation matters most)
    {"query": "What's my job?", "category": "ambiguous", "expected_contains": ["developer", "freelance", "walmart"]},
    {"query": "What do I believe about AI?", "category": "philosophical", "expected_contains": ["scaffold", "model", "mouth", "belief"]},
]


# ---------------------------------------------------------------------------
# Generate response using Claude CLI
# ---------------------------------------------------------------------------
def generate_response(query: str, context: str, label: str) -> str:
    """Generate a response given query + context."""
    prompt = (
        f"You are a personal AI assistant. Use ONLY the provided memories to answer.\n"
        f"If you don't know, say so. Don't make things up.\n\n"
        f"{context}\n\n"
        f"User question: {query}\n\n"
        f"Answer concisely based on the memories above."
    )

    try:
        env = {**os.environ, "CLAUDE_CODE_DISABLE_CRON": "1", "PYTHONIOENCODING": "utf-8"}
        result = subprocess.run(
            [CLAUDE_CLI, "-p", "-", "--model", "claude-sonnet-4-6", "--max-turns", "1"],
            input=prompt, capture_output=True, timeout=60,
            env=env,
            encoding="utf-8", errors="replace",
        )
        return result.stdout.strip() if result.returncode == 0 else f"[ERROR: {result.stderr[:200]}]"
    except Exception as e:
        return f"[ERROR: {e}]"


# ---------------------------------------------------------------------------
# Score a response against expected content
# ---------------------------------------------------------------------------
def score_response(response: str, expected_contains: List[str]) -> Dict:
    """Score response on factual accuracy."""
    response_lower = response.lower()
    hits = [kw for kw in expected_contains if kw.lower() in response_lower]
    misses = [kw for kw in expected_contains if kw.lower() not in response_lower]

    return {
        "hits": len(hits),
        "total": len(expected_contains),
        "accuracy": len(hits) / len(expected_contains) if expected_contains else 1.0,
        "hit_keywords": hits,
        "missed_keywords": misses,
        "said_dont_know": any(phrase in response_lower for phrase in
                             ["don't know", "no information", "not sure", "can't find",
                              "don't have", "no memories", "no data"]),
    }


# ---------------------------------------------------------------------------
# Main experiment
# ---------------------------------------------------------------------------
def run():
    if LOG_FILE.exists():
        LOG_FILE.unlink()

    p("=" * 60)
    p("RAG vs CRT: The Falsification Test")
    p("=" * 60)
    p(f"Memory DB: {MEMORY_DB}")
    p(f"Queries: {len(TEST_QUERIES)}")
    p(f"Model: claude-sonnet-4-6 (same for both paths)")
    p("=" * 60)

    # Load memories once
    p("\nLoading memories...")
    memories = load_all_memories()
    p(f"Loaded {len(memories)} active memories")

    rag_scores = []
    crt_scores = []

    for i, test in enumerate(TEST_QUERIES):
        query = test["query"]
        expected = test["expected_contains"]
        category = test["category"]

        p(f"\n{'='*50}")
        p(f"QUERY {i+1}/{len(TEST_QUERIES)}: \"{query}\" [{category}]")
        p(f"{'='*50}")

        # Path A: Plain RAG
        p(f"\n  [RAG] Retrieving...")
        rag_context = retrieve_plain_rag(query, memories, k=5)
        p(f"  [RAG] Context ({len(rag_context)} chars)")

        p(f"  [RAG] Generating...")
        t0 = time.time()
        rag_response = generate_response(query, rag_context, "RAG")
        rag_time = time.time() - t0
        p(f"  [RAG] ({rag_time:.1f}s): {rag_response[:120]}")

        rag_score = score_response(rag_response, expected)
        p(f"  [RAG] Score: {rag_score['hits']}/{rag_score['total']} keywords matched")

        # Path B: Full CRT
        p(f"\n  [CRT] Retrieving...")
        crt_context = retrieve_crt(query, memories, k=5)
        p(f"  [CRT] Context ({len(crt_context)} chars)")

        p(f"  [CRT] Generating...")
        t0 = time.time()
        crt_response = generate_response(query, crt_context, "CRT")
        crt_time = time.time() - t0
        p(f"  [CRT] ({crt_time:.1f}s): {crt_response[:120]}")

        crt_score = score_response(crt_response, expected)
        p(f"  [CRT] Score: {crt_score['hits']}/{crt_score['total']} keywords matched")

        # Compare
        winner = "TIE"
        if crt_score["accuracy"] > rag_score["accuracy"]:
            winner = "CRT"
        elif rag_score["accuracy"] > crt_score["accuracy"]:
            winner = "RAG"

        p(f"\n  WINNER: {winner}")

        rag_scores.append(rag_score)
        crt_scores.append(crt_score)

        log({
            "query": query,
            "category": category,
            "expected": expected,
            "rag_score": rag_score,
            "crt_score": crt_score,
            "rag_response": rag_response[:500],
            "crt_response": crt_response[:500],
            "winner": winner,
        })

    # Summary
    rag_avg = sum(s["accuracy"] for s in rag_scores) / len(rag_scores)
    crt_avg = sum(s["accuracy"] for s in crt_scores) / len(crt_scores)
    rag_wins = sum(1 for r, c in zip(rag_scores, crt_scores) if r["accuracy"] > c["accuracy"])
    crt_wins = sum(1 for r, c in zip(rag_scores, crt_scores) if c["accuracy"] > r["accuracy"])
    ties = sum(1 for r, c in zip(rag_scores, crt_scores) if r["accuracy"] == c["accuracy"])

    p(f"\n{'='*60}")
    p("RESULTS")
    p(f"{'='*60}")
    p(f"  RAG average accuracy: {rag_avg:.2%}")
    p(f"  CRT average accuracy: {crt_avg:.2%}")
    p(f"  RAG wins: {rag_wins}")
    p(f"  CRT wins: {crt_wins}")
    p(f"  Ties: {ties}")

    p(f"\n  VERDICT:")
    if crt_avg > rag_avg + 0.1:
        p(f"  CRT significantly outperforms RAG ({crt_avg:.2%} vs {rag_avg:.2%})")
        p(f"  Trust scoring and governance are doing real work.")
    elif abs(crt_avg - rag_avg) <= 0.1:
        p(f"  No significant difference ({crt_avg:.2%} vs {rag_avg:.2%})")
        p(f"  CRT apparatus may be overhead for retrieval quality.")
    else:
        p(f"  RAG outperforms CRT ({rag_avg:.2%} vs {crt_avg:.2%})")
        p(f"  Trust scoring may be hurting retrieval quality.")

    p(f"\n  Log: {LOG_FILE}")


if __name__ == "__main__":
    run()
