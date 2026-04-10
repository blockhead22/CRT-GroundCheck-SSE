"""Self-Validation Test: Can Mirus verify its own answers?

After answering a leaf question, Mirus gets a follow-up:
"You said X. Quote the exact line from the code that supports your answer."

If it can cite real code → high confidence
If it can't or cites wrong code → flag as uncertain

This tests whether we can drop Holden from validation entirely.
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


def p(msg):
    print(msg, flush=True)


# Test cases: question + code + known answer + the line that proves it
TESTS = [
    {
        "id": "conn_finally",
        "code": '''    try:
        conn = sqlite3.connect(mem_db_path, timeout=30.0)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        rows = cursor.execute(query, tuple(params)).fetchall()
        conn.close()
        return [str(row["memory_id"]) for row in rows if row["memory_id"]]
    except Exception as e:
        logger.debug(f"Error: {e}")
        return []''',
        "question": "Is conn.close() called inside a finally block or context manager?",
        "expected_answer": "NO",
        "proof_line": "conn.close() appears on its own line, not inside finally or with",
    },
    {
        "id": "parameterized_query",
        "code": '''    query = "SELECT memory_id FROM memories WHERE thread_id = ?"
    params: List[Any] = [thread_id]
    if has_deprecated:
        query += " AND COALESCE(deprecated, 0) = 0"
    query += " ORDER BY timestamp DESC LIMIT ?"
    params.append(max(1, int(limit)))
    rows = cursor.execute(query, tuple(params)).fetchall()''',
        "question": "Is thread_id interpolated directly into the SQL string, or passed as a parameter?",
        "expected_answer": "PARAMETER",
        "proof_line": 'query uses ? placeholder and params = [thread_id]',
    },
    {
        "id": "null_guard",
        "code": '''def _resolve_memory_db_path(self, thread_id: str) -> Optional[str]:
    tid = sanitize_thread_id(str(thread_id or "default"))
    pa_dir = self._default_personal_agent_dir()''',
        "question": "Does this function handle thread_id=None before using it?",
        "expected_answer": "YES",
        "proof_line": 'str(thread_id or "default") — the or catches None',
    },
    {
        "id": "html_escape",
        "code": '''    for field in ["title", "content"]:
        if field in result and isinstance(result[field], str):
            result[field] = result[field].replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")''',
        "question": "Are double-quote and single-quote characters escaped?",
        "expected_answer": "NO",
        "proof_line": "only &, <, > are in the replace chain — no quote escaping",
    },
    {
        "id": "exception_swallow",
        "code": '''    try:
        history = self.session_db.get_heartbeat_history(thread_id, limit=20)
    except Exception:
        return False''',
        "question": "Does the except block log the exception before returning?",
        "expected_answer": "NO",
        "proof_line": "except Exception: return False — no logging call",
    },
    {
        "id": "int_cast",
        "code": '''    cooldown = int((config or {}).get("curiosity_cooldown_seconds") or 7200)
    cooldown = max(900, cooldown)''',
        "question": "If config contains curiosity_cooldown_seconds='fast', does this crash?",
        "expected_answer": "YES",
        "proof_line": "int('fast') raises ValueError — no try/except here",
    },
    {
        "id": "regex_greedy",
        "code": '''    import re
    match = re.search(r"\\{.*\\}", response_text, re.DOTALL)
    if match:
        data = json.loads(match.group(0))
        return data''',
        "question": "Does the regex use a greedy quantifier (.*)?",
        "expected_answer": "YES",
        "proof_line": r'pattern is \{.*\} — .* is greedy, not .*?',
    },
    {
        "id": "tricky_false",
        "code": '''    if self.memory_db_path:
        try:
            rendered = str(self.memory_db_path).format(thread_id=tid)
        except Exception:
            rendered = str(self.memory_db_path)
        candidates.append(Path(rendered))''',
        "question": "If .format() raises an exception, is the error logged anywhere?",
        "expected_answer": "NO",
        "proof_line": "except Exception: rendered = ... — no logging, just silent fallback",
    },
]


async def ask_and_verify(session, test):
    """Ask the question, then ask for proof."""

    # Step 1: Answer the question
    prompt1 = (
        f"Read this code:\n\n```python\n{test['code']}\n```\n\n"
        f"QUESTION: {test['question']}\n\n"
        f"Answer YES or NO, then explain in one sentence."
    )

    payload = {
        "model": MIRUS_MODEL,
        "prompt": prompt1,
        "system": "Answer factual questions about Python code. Start with YES or NO.",
        "stream": False,
        "options": {"temperature": 0.0, "num_predict": 100, "num_ctx": 2048},
    }

    async with session.post(f"{OLLAMA_URL}/api/generate", json=payload,
                           timeout=aiohttp.ClientTimeout(total=20)) as resp:
        data = await resp.json()
    answer = data.get("response", "").strip()

    # Check if answer is correct
    answer_correct = test["expected_answer"].lower() in answer.lower()[:20]

    # Step 2: Ask for proof
    prompt2 = (
        f"You just answered: \"{answer[:100]}\"\n\n"
        f"Now PROVE it. Quote the EXACT line or expression from this code that supports your answer:\n\n"
        f"```python\n{test['code']}\n```\n\n"
        f"Format: PROOF: [exact code snippet that proves your answer]"
    )

    payload2 = {
        "model": MIRUS_MODEL,
        "prompt": prompt2,
        "system": "Quote the exact code that supports your previous answer. Be precise — copy the relevant expression or line.",
        "stream": False,
        "options": {"temperature": 0.0, "num_predict": 150, "num_ctx": 2048},
    }

    async with session.post(f"{OLLAMA_URL}/api/generate", json=payload2,
                           timeout=aiohttp.ClientTimeout(total=20)) as resp:
        data = await resp.json()
    proof = data.get("response", "").strip()

    # Check if proof contains actual code from the snippet
    code_lines = [l.strip() for l in test["code"].split("\n") if l.strip()]
    proof_has_real_code = any(
        line in proof for line in code_lines if len(line) > 10
    )

    return {
        "answer": answer,
        "answer_correct": answer_correct,
        "proof": proof,
        "proof_has_real_code": proof_has_real_code,
        "both_correct": answer_correct and proof_has_real_code,
    }


async def run():
    p("=" * 60)
    p("SELF-VALIDATION: Can Mirus prove its own answers?")
    p("=" * 60)
    p(f"Model: {MIRUS_MODEL}")
    p(f"Tests: {len(TESTS)}")
    p(f"Method: answer + proof citation")
    p("=" * 60)

    results = []
    async with aiohttp.ClientSession() as session:
        for i, test in enumerate(TESTS):
            t0 = time.time()
            result = await ask_and_verify(session, test)
            elapsed = time.time() - t0

            answer_icon = "+" if result["answer_correct"] else "!"
            proof_icon = "+" if result["proof_has_real_code"] else "!"

            p(f"\n  [{answer_icon}] {test['id']} ({elapsed:.1f}s)")
            p(f"    Q: {test['question'][:70]}")
            p(f"    Expected: {test['expected_answer']}")
            p(f"    Answer: {result['answer'][:80]}")
            p(f"    [{proof_icon}] Proof: {result['proof'][:100]}")
            p(f"    Real code cited: {result['proof_has_real_code']}")

            results.append(result)

    # Summary
    answer_correct = sum(1 for r in results if r["answer_correct"])
    proof_correct = sum(1 for r in results if r["proof_has_real_code"])
    both_correct = sum(1 for r in results if r["both_correct"])

    p(f"\n{'='*60}")
    p("RESULTS")
    p(f"{'='*60}")
    p(f"  Answer correct: {answer_correct}/{len(results)} ({answer_correct/len(results)*100:.0f}%)")
    p(f"  Proof cites real code: {proof_correct}/{len(results)} ({proof_correct/len(results)*100:.0f}%)")
    p(f"  Both correct: {both_correct}/{len(results)} ({both_correct/len(results)*100:.0f}%)")

    p(f"\n  If both >= 75%: self-validation is viable → Holden drops from validation")
    p(f"  If answer high but proof low: model guesses correctly but can't explain why")
    p(f"  If both low: model can't self-validate")


if __name__ == "__main__":
    asyncio.run(run())
