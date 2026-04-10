"""Tree Generation Test: Can Mirus build its own reasoning trees?

Few-shot prompting: give 3 Holden-generated trees as examples,
then ask Mirus to generate a tree for a new function.

If the tree is usable (valid JSON, reasonable hypotheses, answerable
leaf questions), Holden drops out of the loop entirely.
"""

import asyncio
import json
import os
import sys
import time
from pathlib import Path

import aiohttp

sys.path.insert(0, str(Path(__file__).parent))
from config import OLLAMA_URL

import builtins
_real_open = builtins.open

MIRUS_MODEL = "llama3.2:latest"

# 3 example trees (from Holden, validated at 80% precision)
EXAMPLE_TREES = [
    {
        "source": '''def _get_memory_snapshot(self, thread_id: str) -> Dict[str, Any]:
    memory_path = self._resolve_memory_db_path(thread_id)
    if not memory_path:
        return {}
    try:
        conn = sqlite3.connect(memory_path, timeout=30.0)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        columns = {str(row[1]).lower() for row in cursor.execute("PRAGMA table_info(memories)").fetchall()}
        if not {"text", "confidence"}.issubset(columns):
            conn.close()
            return {}
        rows = cursor.execute(query, tuple(params)).fetchall()
        conn.close()
        return snapshot
    except Exception as e:
        logger.debug(f"Error: {e}")
        return {}''',
        "tree": {
            "branches": [
                {
                    "category": "resource_management",
                    "risk_hypothesis": "Database connection leaks if an exception is raised after conn is opened but before conn.close()",
                    "leaves": [
                        {"question": "Is conn.close() called inside a finally block or context manager?", "safe_answer": "YES", "unsafe_answer": "NO"},
                        {"question": "Can cursor.execute() raise an exception before conn.close() is reached?", "safe_answer": "NO", "unsafe_answer": "YES"}
                    ]
                },
                {
                    "category": "sql_safety",
                    "risk_hypothesis": "Dynamic query construction could allow SQL injection",
                    "leaves": [
                        {"question": "Is thread_id passed as a parameterized query argument (?) rather than interpolated?", "safe_answer": "YES", "unsafe_answer": "NO"}
                    ]
                }
            ]
        }
    },
    {
        "source": '''def execute_action(self, action_data, thread_id, dry_run=False):
    action_type = action_data.get("action", "none").lower()
    if action_type == "none":
        return {"success": True, "action": "none"}
    if action_type == "post":
        return self._execute_post(action_data, thread_id, dry_run)
    elif action_type == "comment":
        return self._execute_comment(action_data, thread_id, dry_run)
    else:
        return {"success": False, "error": f"Unknown: {action_type}"}''',
        "tree": {
            "branches": [
                {
                    "category": "null_handling",
                    "risk_hypothesis": "action_data being None causes .get() to crash with AttributeError",
                    "leaves": [
                        {"question": "Is action_data checked for None before calling .get()?", "safe_answer": "YES", "unsafe_answer": "NO"}
                    ]
                },
                {
                    "category": "exception_handling",
                    "risk_hypothesis": "Delegated _execute_* methods may raise exceptions that propagate uncaught",
                    "leaves": [
                        {"question": "Is there a try/except wrapping the _execute_* calls?", "safe_answer": "YES", "unsafe_answer": "NO"}
                    ]
                }
            ]
        }
    },
    {
        "source": '''def sanitize_action(self, action_data):
    result = action_data.copy()
    if "content" in result and isinstance(result["content"], str):
        result["content"] = result["content"][:self.MAX_CONTENT_LENGTH]
    if "title" in result and isinstance(result["title"], str):
        result["title"] = result["title"][:self.MAX_POST_TITLE_LENGTH]
    for field in ["title", "content"]:
        if field in result and isinstance(result[field], str):
            result[field] = result[field].replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    return result''',
        "tree": {
            "branches": [
                {
                    "category": "logic",
                    "risk_hypothesis": "HTML escape only covers &, <, > — quotes are not escaped, allowing XSS in attribute contexts",
                    "leaves": [
                        {"question": "Are double-quote and single-quote characters escaped?", "safe_answer": "YES", "unsafe_answer": "NO"}
                    ]
                },
                {
                    "category": "logic",
                    "risk_hypothesis": "Escaping does not check for already-escaped entities, causing double-escaping",
                    "leaves": [
                        {"question": "Does the escape logic check whether the string is already HTML-escaped?", "safe_answer": "YES", "unsafe_answer": "NO"}
                    ]
                }
            ]
        }
    },
]

# Test functions — ones Mirus hasn't seen trees for
TEST_FUNCTIONS = [
    {
        "name": "parse_llm_response",
        "source": '''def parse_llm_response(self, response_text: str) -> Dict[str, Any]:
    try:
        import re
        match = re.search(r"\\{.*\\}", response_text, re.DOTALL)
        if match:
            data = json.loads(match.group(0))
            return data
    except Exception as e:
        logger.debug(f"Failed to parse: {e}")
    return {"action": "none", "reasoning": (response_text or "")[:200]}''',
    },
    {
        "name": "_curiosity_recently_logged",
        "source": '''def _curiosity_recently_logged(self, thread_id, fingerprint, cooldown_seconds):
    if not self.session_db or not fingerprint:
        return False
    try:
        history = self.session_db.get_heartbeat_history(thread_id, limit=20)
    except Exception:
        return False
    now_ts = time.time()
    for run in history:
        ts = self._safe_float((run or {}).get("timestamp"), 0.0)
        if ts <= 0:
            continue
        if (now_ts - ts) > float(max(0, cooldown_seconds)):
            continue
        for action in (run or {}).get("actions") or []:
            if not isinstance(action, dict):
                continue
            if str(action.get("fingerprint") or "") == fingerprint:
                return True
    return False''',
    },
    {
        "name": "_get_ledger_feed",
        "source": '''def _get_ledger_feed(self, limit=10):
    if not self.session_db:
        return []
    try:
        conn = self.session_db._get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT p.id, p.title, p.content, p.author, p.created_at,
                   COALESCE(SUM(CASE WHEN v.direction='up' THEN 1 ELSE -1 END), 0) as vote_count
            FROM posts p LEFT JOIN votes v ON p.id = v.post_id
            GROUP BY p.id ORDER BY p.created_at DESC LIMIT ?
        """, (limit,))
        rows = cursor.fetchall()
        conn.close()
        return [{"id": r[0], "title": r[1], "content": r[2], "author": r[3],
                 "created_at": r[4], "vote_count": r[5]} for r in rows]
    except Exception as e:
        logger.debug(f"Error: {e}")
        return []''',
    },
]


def p(msg):
    print(msg, flush=True)


async def generate_tree(session, func_source, func_name):
    """Ask Mirus to generate a reasoning tree given few-shot examples."""

    examples = ""
    for i, ex in enumerate(EXAMPLE_TREES):
        examples += f"\nEXAMPLE {i+1}:\nCode:\n```python\n{ex['source']}\n```\nTree:\n```json\n{json.dumps(ex['tree'], indent=2)}\n```\n"

    prompt = (
        f"You are a code auditor. Generate a REASONING TREE for auditing Python functions.\n\n"
        f"Here are 3 examples of code and their reasoning trees:\n"
        f"{examples}\n\n"
        f"Now generate a reasoning tree for this function:\n"
        f"```python\n{func_source}\n```\n\n"
        f"Output ONLY valid JSON. No markdown fences, no explanation. Just the JSON object.\n"
        f"Follow the exact same format as the examples above.\n"
        f"Focus on: crashes, data corruption, resource leaks, security vulnerabilities.\n"
        f"2-4 branches, 1-2 leaves per branch."
    )

    payload = {
        "model": MIRUS_MODEL,
        "prompt": prompt,
        "system": "You generate JSON reasoning trees for code auditing. Output ONLY valid JSON.",
        "stream": False,
        "options": {"temperature": 0.1, "num_predict": 800, "num_ctx": 8192},
    }

    async with session.post(f"{OLLAMA_URL}/api/generate", json=payload,
                           timeout=aiohttp.ClientTimeout(total=60)) as resp:
        data = await resp.json()
    return data.get("response", "")


def parse_tree(raw):
    """Try to extract valid JSON tree from model output."""
    # Strip markdown fences if present
    if "```json" in raw:
        raw = raw.split("```json")[1].split("```")[0].strip()
    elif "```" in raw:
        raw = raw.split("```")[1].split("```")[0].strip()

    # Find JSON object
    start = raw.find("{")
    end = raw.rfind("}") + 1
    if start == -1 or end == 0:
        return None

    try:
        tree = json.loads(raw[start:end])
        return tree
    except json.JSONDecodeError:
        return None


def evaluate_tree(tree, func_name):
    """Score a generated tree on structural quality."""
    checks = {
        "valid_json": tree is not None,
        "has_branches": isinstance(tree, dict) and "branches" in tree,
        "branches_non_empty": False,
        "has_categories": False,
        "has_hypotheses": False,
        "has_leaves": False,
        "leaves_have_questions": False,
        "leaves_have_answers": False,
    }

    if not checks["has_branches"]:
        return checks

    branches = tree.get("branches", [])
    checks["branches_non_empty"] = len(branches) > 0

    if not branches:
        return checks

    checks["has_categories"] = all("category" in b for b in branches)
    checks["has_hypotheses"] = all("risk_hypothesis" in b for b in branches)
    checks["has_leaves"] = all("leaves" in b and len(b["leaves"]) > 0 for b in branches)

    all_leaves = [l for b in branches for l in b.get("leaves", [])]
    if all_leaves:
        checks["leaves_have_questions"] = all("question" in l for l in all_leaves)
        checks["leaves_have_answers"] = all(
            "safe_answer" in l and "unsafe_answer" in l for l in all_leaves
        )

    return checks


async def run():
    p("=" * 60)
    p("TREE GENERATION TEST: Can Mirus build its own trees?")
    p("=" * 60)
    p(f"Model: {MIRUS_MODEL}")
    p(f"Examples: {len(EXAMPLE_TREES)} trees from Holden")
    p(f"Test functions: {len(TEST_FUNCTIONS)}")
    p("=" * 60)

    async with aiohttp.ClientSession() as session:
        for i, func in enumerate(TEST_FUNCTIONS):
            p(f"\n{'='*50}")
            p(f"TEST {i+1}/{len(TEST_FUNCTIONS)}: {func['name']}")
            p(f"{'='*50}")

            t0 = time.time()
            raw = await generate_tree(session, func["source"], func["name"])
            gen_time = time.time() - t0

            p(f"\n  Generated in {gen_time:.1f}s")
            p(f"  Raw output ({len(raw)} chars):")
            for line in raw.split("\n")[:20]:
                p(f"    {line}")

            tree = parse_tree(raw)
            checks = evaluate_tree(tree, func["name"])

            p(f"\n  Quality checks:")
            passed = 0
            for check, result in checks.items():
                icon = "+" if result else "!"
                p(f"    [{icon}] {check}: {result}")
                if result:
                    passed += 1

            p(f"\n  Score: {passed}/{len(checks)}")

            if tree and "branches" in tree:
                p(f"\n  Generated tree:")
                for b in tree["branches"]:
                    p(f"    [{b.get('category', '?')}] {b.get('risk_hypothesis', '?')[:80]}")
                    for l in b.get("leaves", []):
                        p(f"      Q: {l.get('question', '?')[:70]}")
                        p(f"      Safe: {l.get('safe_answer', '?')[:40]}")

            p(f"\n  {'USABLE' if passed >= 6 else 'NOT USABLE'}")


if __name__ == "__main__":
    asyncio.run(run())
