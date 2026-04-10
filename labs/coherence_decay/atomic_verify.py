"""Atomic Verification Test: Can a 3B model answer factual questions about code?

Not "is this a bug?" — but "does line X do Y? yes/no."

Each question is a leaf node in a potential BDG reasoning tree.
Each has a ground-truth answer derived from reading the actual source.
The model gets ~30 lines of code and one specific question.

This tests the fundamental capability: can the model READ code accurately
when the context is small enough and the question is factual?
"""

import asyncio
import json
import time
from pathlib import Path

import aiohttp

import builtins
_real_open = builtins.open

import sys
sys.path.insert(0, str(Path(__file__).parent))
from config import OLLAMA_URL

MIRUS_MODEL = "llama3.2:latest"
LOG_FILE = Path(__file__).parent / "results" / "raw" / "atomic_verify.jsonl"


def p(msg):
    print(msg, flush=True)


def log(entry):
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    with _real_open(LOG_FILE, "a") as f:
        f.write(json.dumps(entry, default=str) + "\n")


# ---------------------------------------------------------------------------
# Test cases: real code snippets + factual questions + ground truth
# ---------------------------------------------------------------------------
TESTS = [
    # --- NULL HANDLING ---
    {
        "id": "null_guard_1",
        "category": "null_handling",
        "code": '''def _resolve_memory_db_path(self, thread_id: str) -> Optional[str]:
    """Resolve memory DB path for a thread (shared or per-thread)."""
    tid = sanitize_thread_id(str(thread_id or "default"))
    pa_dir = self._default_personal_agent_dir()
    shared_enabled = os.getenv("CRT_SHARED_MEMORY", "false").lower() == "true"

    candidates: List[Path] = []
    if self.memory_db_path:
        try:
            rendered = str(self.memory_db_path).format(thread_id=tid)
        except Exception:
            rendered = str(self.memory_db_path)
        candidates.append(Path(rendered))''',
        "question": "If thread_id is None, what value does tid get assigned?",
        "expected": "default",
        "check": lambda r: "default" in r.lower(),
    },
    {
        "id": "null_guard_2",
        "category": "null_handling",
        "code": '''def _resolve_memory_db_path(self, thread_id: str) -> Optional[str]:
    """Resolve memory DB path for a thread (shared or per-thread)."""
    tid = sanitize_thread_id(str(thread_id or "default"))
    pa_dir = self._default_personal_agent_dir()''',
        "question": "Does this function handle thread_id=None before using it? Answer YES or NO, then explain which line.",
        "expected": "YES — line 3: str(thread_id or 'default') catches None",
        "check": lambda r: "yes" in r.lower()[:20],
    },
    {
        "id": "null_guard_3",
        "category": "null_handling",
        "code": '''def _get_thread_memory_ids(self, thread_id: str, limit: int = 500) -> List[str]:
    """Return recent memory IDs for a thread to scope shared-ledger queries."""
    mem_db_path = self._resolve_memory_db_path(thread_id)
    if not mem_db_path or not Path(mem_db_path).exists():
        return []
    try:
        conn = sqlite3.connect(mem_db_path, timeout=30.0)''',
        "question": "If _resolve_memory_db_path returns None, what happens? Answer with the specific return value.",
        "expected": "Returns empty list []",
        "check": lambda r: "[]" in r or "empty list" in r.lower() or "return []" in r.lower(),
    },

    # --- EXCEPTION HANDLING ---
    {
        "id": "exception_1",
        "category": "exception_handling",
        "code": '''    try:
        conn = sqlite3.connect(mem_db_path, timeout=30.0)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        columns = {
            str(row[1]).lower()
            for row in cursor.execute("PRAGMA table_info(memories)").fetchall()
        }
        if "memory_id" not in columns:
            conn.close()
            return []
        rows = cursor.execute(query, tuple(params)).fetchall()
        conn.close()
        return [str(row["memory_id"]) for row in rows if row["memory_id"]]
    except Exception as e:
        logger.debug(f"[HEARTBEAT] Error getting thread memory ids: {e}")
        return []''',
        "question": "If sqlite3.connect raises an exception, is it caught? Answer YES or NO.",
        "expected": "YES",
        "check": lambda r: "yes" in r.lower()[:20],
    },
    {
        "id": "exception_2",
        "category": "exception_handling",
        "code": '''    try:
        conn = sqlite3.connect(mem_db_path, timeout=30.0)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        columns = {
            str(row[1]).lower()
            for row in cursor.execute("PRAGMA table_info(memories)").fetchall()
        }
        if "memory_id" not in columns:
            conn.close()
            return []
        rows = cursor.execute(query, tuple(params)).fetchall()
        conn.close()
        return [str(row["memory_id"]) for row in rows if row["memory_id"]]
    except Exception as e:
        logger.debug(f"[HEARTBEAT] Error getting thread memory ids: {e}")
        return []''',
        "question": "If an exception is raised AFTER conn = sqlite3.connect() but BEFORE conn.close(), is conn.close() called? Answer YES or NO.",
        "expected": "NO — the except block doesn't call conn.close(), causing a connection leak",
        "check": lambda r: "no" in r.lower()[:20],
    },

    # --- RESOURCE MANAGEMENT ---
    {
        "id": "resource_1",
        "category": "resource_management",
        "code": '''    try:
        conn = sqlite3.connect(mem_db_path, timeout=30.0)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        if "memory_id" not in columns:
            conn.close()
            return []
        if "thread_id" not in columns:
            conn.close()
            return []
        rows = cursor.execute(query, tuple(params)).fetchall()
        conn.close()
        return [str(row["memory_id"]) for row in rows if row["memory_id"]]
    except Exception as e:
        logger.debug(f"[HEARTBEAT] Error getting thread memory ids: {e}")
        return []''',
        "question": "Count: how many times does conn.close() appear in this code? Give the exact number.",
        "expected": "3",
        "check": lambda r: "3" in r,
    },
    {
        "id": "resource_2",
        "category": "resource_management",
        "code": '''    try:
        conn = sqlite3.connect(mem_db_path, timeout=30.0)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        if "memory_id" not in columns:
            conn.close()
            return []
        if "thread_id" not in columns:
            conn.close()
            return []
        rows = cursor.execute(query, tuple(params)).fetchall()
        conn.close()
        return [str(row["memory_id"]) for row in rows if row["memory_id"]]
    except Exception as e:
        logger.debug(f"[HEARTBEAT] Error getting thread memory ids: {e}")
        return []''',
        "question": "Is conn.close() called in the except block? Answer YES or NO.",
        "expected": "NO",
        "check": lambda r: "no" in r.lower()[:20],
    },

    # --- CONTROL FLOW ---
    {
        "id": "flow_1",
        "category": "control_flow",
        "code": '''INTENT_PATTERNS = {
    "identity": [
        "who am i", "tell me about myself", "what do you know about me",
        "my profile", "my preferences",
    ],
    "general_knowledge": [
        "what is", "what's", "who is", "where is", "how does",
        "explain", "tell me about", "define",
    ],
}

def classify_intent(query):
    query_lower = query.lower().strip()
    scores = {}
    for intent, patterns in INTENT_PATTERNS.items():
        score = 0
        for pattern in patterns:
            if pattern in query_lower:
                score += len(pattern)
        scores[intent] = score
    return max(scores, key=scores.get)''',
        "question": "For the query \"What's my name?\", which patterns match? List each matching pattern and its intent.",
        "expected": "\"what's\" matches general_knowledge (score 6). No identity patterns match.",
        "check": lambda r: "what's" in r.lower() and "general" in r.lower(),
    },
    {
        "id": "flow_2",
        "category": "control_flow",
        "code": '''def classify_intent(query):
    query_lower = query.lower().strip()
    scores = {}
    for intent, patterns in INTENT_PATTERNS.items():
        score = 0
        for pattern in patterns:
            if pattern in query_lower:
                score += len(pattern)
        scores[intent] = score
    if max(scores.values()) == 0:
        return "general_knowledge"
    return max(scores, key=scores.get)''',
        "question": "If scores = {'identity': 0, 'general_knowledge': 6}, what does this function return?",
        "expected": "general_knowledge",
        "check": lambda r: "general_knowledge" in r.lower() or "general knowledge" in r.lower(),
    },

    # --- SQL SAFETY ---
    {
        "id": "sql_1",
        "category": "sql_safety",
        "code": '''    query = "SELECT memory_id FROM memories WHERE thread_id = ?"
    params: List[Any] = [thread_id]
    if has_deprecated:
        query += " AND COALESCE(deprecated, 0) = 0"
    query += " ORDER BY timestamp DESC LIMIT ?"
    params.append(max(1, int(limit)))
    rows = cursor.execute(query, tuple(params)).fetchall()''',
        "question": "Is thread_id interpolated directly into the SQL string, or passed as a parameter? Answer INTERPOLATED or PARAMETER.",
        "expected": "PARAMETER — uses ? placeholder and params list",
        "check": lambda r: "parameter" in r.lower(),
    },

    # --- TYPE SAFETY ---
    {
        "id": "type_1",
        "category": "type_safety",
        "code": '''    query += " ORDER BY timestamp DESC LIMIT ?"
    params.append(max(1, int(limit)))''',
        "question": "If limit='abc' (a string), what happens on this line? Does it raise an exception or handle it?",
        "expected": "Raises ValueError — int('abc') fails and there's no try/except here",
        "check": lambda r: ("raise" in r.lower() or "error" in r.lower() or "exception" in r.lower() or "fail" in r.lower()),
    },

    # --- RETURN VALUES ---
    {
        "id": "return_1",
        "category": "return_values",
        "code": '''def _get_memory_snapshot(self, thread_id: str) -> Dict[str, Any]:
    memory_path = self._resolve_memory_db_path(thread_id)
    if not memory_path:
        return {}
    try:
        conn = sqlite3.connect(memory_path, timeout=30.0)
        # ... query logic ...
        return snapshot
    except Exception as e:
        logger.debug(f"[HEARTBEAT] Error getting memory snapshot: {e}")
        return {}''',
        "question": "What are ALL the possible return types of this function? List them.",
        "expected": "Dict — either the snapshot dict or empty dict {}",
        "check": lambda r: "{}" in r or "empty dict" in r.lower() or "dict" in r.lower(),
    },

    # --- BOUNDARY ---
    {
        "id": "boundary_1",
        "category": "boundary",
        "code": '''    max_results = max(1, int(config.get("news_max_results", 3)))
    cooldown_seconds = max(900, int(config.get("news_cooldown_seconds", 3600)))''',
        "question": "What is the minimum possible value of cooldown_seconds? Give the exact number.",
        "expected": "900",
        "check": lambda r: "900" in r,
    },
    {
        "id": "boundary_2",
        "category": "boundary",
        "code": '''    curiosity_score = max(0.0, min(1.0, curiosity_score))''',
        "question": "What range is curiosity_score clamped to? Give the exact bounds.",
        "expected": "0.0 to 1.0",
        "check": lambda r: "0" in r and "1" in r,
    },

    # --- TRICKY / ADVERSARIAL ---
    {
        "id": "tricky_1",
        "category": "tricky",
        "code": '''def validate_action(self, action_data):
    action_type = (action_data.get("action") or "").strip().lower()
    if action_type == "none":
        return True, None''',
        "question": "If action_data is None (not a dict), what happens? Does it return safely or crash?",
        "expected": "Crashes — None.get() raises AttributeError",
        "check": lambda r: ("crash" in r.lower() or "error" in r.lower() or "attributeerror" in r.lower() or "raise" in r.lower() or "fail" in r.lower() or "exception" in r.lower()),
    },
    {
        "id": "tricky_2",
        "category": "tricky",
        "code": '''    if self.memory_db_path:
        try:
            rendered = str(self.memory_db_path).format(thread_id=tid)
        except Exception:
            rendered = str(self.memory_db_path)
        candidates.append(Path(rendered))''',
        "question": "If self.memory_db_path is an empty string '', does the 'if self.memory_db_path' check pass? Answer YES or NO.",
        "expected": "NO — empty string is falsy in Python",
        "check": lambda r: "no" in r.lower()[:20],
    },
]


async def run_test(session, test):
    """Run a single atomic verification question."""
    prompt = (
        f"Read this Python code carefully:\n\n"
        f"```python\n{test['code']}\n```\n\n"
        f"QUESTION: {test['question']}\n\n"
        f"Answer concisely. Be specific. Cite the exact code that supports your answer."
    )

    payload = {
        "model": MIRUS_MODEL,
        "prompt": prompt,
        "system": "You are reading Python code and answering a specific factual question about it. Be precise and concise. Answer the question directly, then cite the relevant code.",
        "stream": False,
        "options": {"temperature": 0.0, "num_predict": 200, "num_ctx": 2048},
    }

    async with session.post(f"{OLLAMA_URL}/api/generate", json=payload,
                           timeout=aiohttp.ClientTimeout(total=30)) as resp:
        data = await resp.json()
    return data.get("response", "")


async def run():
    if LOG_FILE.exists():
        LOG_FILE.unlink()

    p("=" * 60)
    p("ATOMIC VERIFICATION: Can a 3B model read code accurately?")
    p("=" * 60)
    p(f"Model: {MIRUS_MODEL}")
    p(f"Tests: {len(TESTS)}")
    p(f"Each test: ~10-20 lines of code, 1 factual question")
    p("=" * 60)

    results = {"pass": 0, "fail": 0, "total": len(TESTS)}
    by_category = {}

    async with aiohttp.ClientSession() as session:
        for i, test in enumerate(TESTS):
            t0 = time.time()
            response = await run_test(session, test)
            elapsed = time.time() - t0

            passed = test["check"](response)
            status = "PASS" if passed else "FAIL"
            results["pass" if passed else "fail"] += 1

            cat = test["category"]
            if cat not in by_category:
                by_category[cat] = {"pass": 0, "fail": 0}
            by_category[cat]["pass" if passed else "fail"] += 1

            p(f"\n  [{status}] {test['id']} ({elapsed:.1f}s)")
            p(f"    Q: {test['question'][:80]}")
            p(f"    Expected: {test['expected'][:80]}")
            p(f"    Got: {response[:120]}")

            log({
                "id": test["id"],
                "category": cat,
                "question": test["question"],
                "expected": test["expected"],
                "response": response[:500],
                "passed": passed,
                "time": elapsed,
            })

    # Summary
    p(f"\n{'='*60}")
    p("RESULTS")
    p(f"{'='*60}")
    p(f"  Total: {results['pass']}/{results['total']} ({results['pass']/results['total']*100:.0f}%)")
    p(f"\n  By category:")
    for cat, counts in sorted(by_category.items()):
        total = counts["pass"] + counts["fail"]
        p(f"    {cat}: {counts['pass']}/{total}")

    p(f"\n  Log: {LOG_FILE}")


if __name__ == "__main__":
    asyncio.run(run())
