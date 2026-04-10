"""BDG Audit: Belief Dependency Graph applied to code auditing.

Architecture:
1. AST extracts functions (reused from audit_chunked)
2. Holden generates a reasoning TREE for each function (1 cloud call)
   - Tree has branches (null_handling, exceptions, resources, etc.)
   - Each branch has leaf questions (factual, yes/no or specific value)
3. Mirus answers each leaf question (local, fast, 94% proven accuracy)
4. Scaffold propagates answers upward through the tree
5. Any branch where a leaf indicates UNGUARDED = real finding

Key insight: Mirus never judges. It reads and reports.
The tree structure IS the reasoning. The scaffold IS the brain.
"""

import ast
import asyncio
import json
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import List, Dict, Any, Optional

import aiohttp

sys.path.insert(0, str(Path(__file__).parent))
from config import OLLAMA_URL

import builtins
_real_open = builtins.open

MIRUS_MODEL = "llama3.2:latest"
CLAUDE_CLI = os.getenv(
    "CLAUDE_CODE_EXECPATH",
    r"C:\Users\block\AppData\Roaming\Claude\claude-code\2.1.92\claude.exe"
)
LOG_FILE = Path(__file__).parent / "results" / "raw" / "audit_bdg.jsonl"

SOURCE_FILES = [
    r"D:\AI_round2\personal_agent\heartbeat_executor.py",
    r"D:\AI_round2\personal_agent\governance_bridge.py",
]


def p(msg):
    print(msg, flush=True)


def log(entry):
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    with _real_open(LOG_FILE, "a") as f:
        f.write(json.dumps(entry, default=str) + "\n")


# ---------------------------------------------------------------------------
# AST extraction (from audit_chunked)
# ---------------------------------------------------------------------------
def extract_functions(filepath: str) -> List[Dict]:
    with _real_open(filepath) as f:
        source = f.read()
    lines = source.splitlines(keepends=True)
    tree = ast.parse(source)
    functions = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            start = node.lineno - 1
            end = getattr(node, 'end_lineno', node.lineno)
            func_source = ''.join(lines[start:end])
            parent_class = None
            for parent in ast.walk(tree):
                if isinstance(parent, ast.ClassDef):
                    if any(child is node for child in ast.walk(parent)):
                        parent_class = parent.name
            functions.append({
                "name": node.name,
                "class": parent_class,
                "file": os.path.basename(filepath),
                "start_line": node.lineno,
                "end_line": end,
                "line_count": end - node.lineno + 1,
                "source": func_source,
                "args": [a.arg for a in node.args.args if a.arg != 'self'],
            })
    return functions


# ---------------------------------------------------------------------------
# Holden: generate reasoning tree for a function (1 cloud call)
# ---------------------------------------------------------------------------
TREE_PROMPT = """Read this Python function and generate a REASONING TREE for auditing it.

```python
{source}
```

Output ONLY valid JSON. No markdown, no explanation. Just the JSON object.

The tree has branches. Each branch has leaf questions that can be answered YES/NO or with a specific short value by reading the code.

JSON format:
{{
  "branches": [
    {{
      "category": "null_handling|exception_handling|resource_management|sql_safety|logic|concurrency|boundary",
      "risk_hypothesis": "one sentence: what could go wrong",
      "leaves": [
        {{
          "question": "a specific factual question about the code (answerable by reading it)",
          "safe_answer": "the answer that means NO bug (e.g. 'YES' for 'is X checked?')",
          "unsafe_answer": "the answer that means there IS a bug"
        }}
      ]
    }}
  ]
}}

Rules:
- 2-5 branches per function
- 1-3 leaves per branch
- Questions must be answerable from the code alone (not requiring external context)
- Questions should be YES/NO or ask for a specific value
- Focus ONLY on issues that can cause: crashes, data corruption, resource leaks, security vulnerabilities, or silent data loss
- Skip branches where the answer is obviously safe from a quick read
- Only include branches where there's a PLAUSIBLE risk

DO NOT flag these — they are design choices, not bugs:
- Unused parameters (config, thread_id not referenced)
- Hardcoded values (author names, limits, submolt names)
- Shallow copies vs deep copies
- Log level choices (DEBUG vs WARNING)
- Missing type validation on internal parameters (duck typing is intentional)
- Order of items in returned collections
- Broad 'except Exception' — only flag if it ALSO swallows the error silently with no fallback
- Style inconsistencies ([:5] vs [-5:]) unless they produce wrong results"""


def holden_build_tree(func: Dict) -> Optional[Dict]:
    """Holden generates a reasoning tree for one function."""
    source = func['source']
    if len(source) > 8000:
        half = 3500
        source = source[:half] + "\n\n... [truncated] ...\n\n" + source[-half:]

    prompt = TREE_PROMPT.format(source=source)

    try:
        result = subprocess.run(
            [CLAUDE_CLI, "-p", "-", "--model", "claude-sonnet-4-6", "--max-turns", "1"],
            input=prompt, capture_output=True, text=True, timeout=90,
            env={**os.environ, "CLAUDE_CODE_DISABLE_CRON": "1"},
        )
        raw = result.stdout.strip() if result.returncode == 0 else ""
        if not raw:
            return None

        # Extract JSON from response (might have markdown fences)
        if "```json" in raw:
            raw = raw.split("```json")[1].split("```")[0].strip()
        elif "```" in raw:
            raw = raw.split("```")[1].split("```")[0].strip()

        # Find the JSON object
        start = raw.find("{")
        end = raw.rfind("}") + 1
        if start == -1 or end == 0:
            return None

        return json.loads(raw[start:end])
    except (json.JSONDecodeError, Exception) as e:
        p(f"    [HOLDEN] Tree parse error: {e}")
        return None


# ---------------------------------------------------------------------------
# Mirus: answer one leaf question (local, fast)
# ---------------------------------------------------------------------------
async def mirus_answer_leaf(session, func_source: str, question: str) -> str:
    """Mirus answers one factual question about code. ~1-2 seconds."""
    prompt = (
        f"Read this Python code carefully:\n\n"
        f"```python\n{func_source}\n```\n\n"
        f"QUESTION: {question}\n\n"
        f"Answer concisely. Start with YES or NO if applicable, then explain in one sentence."
    )

    payload = {
        "model": MIRUS_MODEL,
        "prompt": prompt,
        "system": "You are reading Python code and answering a specific factual question. Be precise. Start with YES or NO when the question asks for it.",
        "stream": False,
        "options": {"temperature": 0.0, "num_predict": 150, "num_ctx": 2048},
    }

    try:
        async with session.post(f"{OLLAMA_URL}/api/generate", json=payload,
                               timeout=aiohttp.ClientTimeout(total=20)) as resp:
            data = await resp.json()
        return data.get("response", "").strip()
    except:
        return "ERROR: could not get response"


# ---------------------------------------------------------------------------
# Scaffold: propagate answers through the tree
# ---------------------------------------------------------------------------
def evaluate_leaf(answer: str, safe_answer: str, unsafe_answer: str) -> str:
    """Determine if a leaf answer indicates SAFE, UNSAFE, or UNCLEAR."""
    answer_lower = answer.lower().strip()
    safe_lower = safe_answer.lower().strip()
    unsafe_lower = unsafe_answer.lower().strip()

    # Check for YES/NO alignment
    answer_starts_yes = answer_lower.startswith("yes")
    answer_starts_no = answer_lower.startswith("no")

    if safe_lower.startswith("yes") and answer_starts_yes:
        return "SAFE"
    if safe_lower.startswith("no") and answer_starts_no:
        return "SAFE"
    if unsafe_lower.startswith("yes") and answer_starts_yes:
        return "UNSAFE"
    if unsafe_lower.startswith("no") and answer_starts_no:
        return "UNSAFE"

    # Check for keyword containment
    if safe_lower in answer_lower:
        return "SAFE"
    if unsafe_lower in answer_lower:
        return "UNSAFE"

    return "UNCLEAR"


def propagate_branch(branch_results: List[Dict]) -> Dict:
    """Propagate leaf results to branch verdict."""
    statuses = [r["status"] for r in branch_results]

    if "UNSAFE" in statuses:
        return {
            "verdict": "RISK",
            "unsafe_leaves": [r for r in branch_results if r["status"] == "UNSAFE"],
        }
    elif all(s == "SAFE" for s in statuses):
        return {"verdict": "SAFE", "unsafe_leaves": []}
    else:
        return {
            "verdict": "UNCLEAR",
            "unclear_leaves": [r for r in branch_results if r["status"] == "UNCLEAR"],
        }


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
async def run():
    if LOG_FILE.exists():
        LOG_FILE.unlink()

    p("=" * 60)
    p("BDG AUDIT: Reasoning tree code auditor")
    p("=" * 60)
    p(f"Auditor: {MIRUS_MODEL} (3B) — answers leaf questions")
    p(f"Architect: claude-sonnet-4-6 — builds reasoning trees")
    p(f"Scaffold: propagates answers, makes verdicts")
    p("=" * 60)

    # Extract functions
    all_functions = []
    for filepath in SOURCE_FILES:
        funcs = extract_functions(filepath)
        all_functions.extend(funcs)
        p(f"\n  {os.path.basename(filepath)}: {len(funcs)} functions")

    # Filter and sort
    audit_targets = [f for f in all_functions if f["line_count"] >= 10]
    audit_targets.sort(key=lambda f: f["line_count"], reverse=True)
    p(f"\n  Auditing: {len(audit_targets)} functions (>=10 lines)")

    stats = {
        "functions_audited": 0,
        "trees_built": 0,
        "leaves_answered": 0,
        "branches_safe": 0,
        "branches_risk": 0,
        "branches_unclear": 0,
        "holden_calls": 0,
        "mirus_calls": 0,
        "real_findings": [],
    }

    async with aiohttp.ClientSession() as session:
        for i, func in enumerate(audit_targets):
            func_name = f"{func['class']}.{func['name']}"
            p(f"\n{'='*50}")
            p(f"FUNCTION {i+1}/{len(audit_targets)}: {func_name}")
            p(f"  {func['file']} lines {func['start_line']}-{func['end_line']} ({func['line_count']} lines)")
            p(f"{'='*50}")

            # Step 1: Holden builds the tree
            p(f"\n  [HOLDEN] Building reasoning tree...")
            t0 = time.time()
            tree = holden_build_tree(func)
            tree_time = time.time() - t0
            stats["holden_calls"] += 1

            if not tree or "branches" not in tree:
                p(f"  [HOLDEN] ({tree_time:.1f}s) Failed to build tree — skipping")
                continue

            branches = tree["branches"]
            total_leaves = sum(len(b.get("leaves", [])) for b in branches)
            p(f"  [HOLDEN] ({tree_time:.1f}s) Tree: {len(branches)} branches, {total_leaves} leaves")
            stats["trees_built"] += 1
            stats["functions_audited"] += 1

            # Step 2: Mirus answers each leaf
            func_findings = []

            for branch in branches:
                category = branch.get("category", "unknown")
                hypothesis = branch.get("risk_hypothesis", "")
                leaves = branch.get("leaves", [])

                p(f"\n  [{category}] {hypothesis[:80]}")

                branch_results = []
                for leaf in leaves:
                    question = leaf.get("question", "")
                    safe = leaf.get("safe_answer", "")
                    unsafe = leaf.get("unsafe_answer", "")

                    t0 = time.time()
                    answer = await mirus_answer_leaf(session, func["source"], question)
                    leaf_time = time.time() - t0
                    stats["mirus_calls"] += 1
                    stats["leaves_answered"] += 1

                    status = evaluate_leaf(answer, safe, unsafe)
                    icon = {"SAFE": "+", "UNSAFE": "!", "UNCLEAR": "?"}[status]

                    p(f"    [{icon}] Q: {question[:70]}")
                    p(f"        A: {answer[:100]}")
                    p(f"        Status: {status} (safe={safe[:30]}, got in {leaf_time:.1f}s)")

                    branch_results.append({
                        "question": question,
                        "answer": answer[:300],
                        "safe_answer": safe,
                        "unsafe_answer": unsafe,
                        "status": status,
                    })

                # Propagate
                branch_verdict = propagate_branch(branch_results)

                if branch_verdict["verdict"] == "RISK":
                    stats["branches_risk"] += 1
                    finding = {
                        "function": func_name,
                        "file": func["file"],
                        "category": category,
                        "hypothesis": hypothesis,
                        "evidence": branch_verdict["unsafe_leaves"],
                    }
                    func_findings.append(finding)
                    stats["real_findings"].append(finding)
                    p(f"    >>> RISK FOUND: {hypothesis[:80]}")
                elif branch_verdict["verdict"] == "SAFE":
                    stats["branches_safe"] += 1
                    p(f"    >>> SAFE")
                else:
                    stats["branches_unclear"] += 1
                    p(f"    >>> UNCLEAR — needs manual review")

            log({
                "function": func_name,
                "file": func["file"],
                "lines": f"{func['start_line']}-{func['end_line']}",
                "tree": tree,
                "findings": func_findings,
            })

    # Summary
    p(f"\n{'='*60}")
    p("BDG AUDIT RESULTS")
    p(f"{'='*60}")
    p(f"  Functions audited: {stats['functions_audited']}")
    p(f"  Reasoning trees built: {stats['trees_built']}")
    p(f"  Leaf questions answered: {stats['leaves_answered']}")
    p(f"  Holden calls (cloud): {stats['holden_calls']}")
    p(f"  Mirus calls (local): {stats['mirus_calls']}")
    p(f"\n  Branch verdicts:")
    p(f"    SAFE: {stats['branches_safe']}")
    p(f"    RISK: {stats['branches_risk']}")
    p(f"    UNCLEAR: {stats['branches_unclear']}")

    if stats["real_findings"]:
        p(f"\n  FINDINGS ({len(stats['real_findings'])}):")
        for i, f in enumerate(stats["real_findings"]):
            p(f"    {i+1}. [{f['category']}] {f['function']}: {f['hypothesis'][:80]}")
            for ev in f["evidence"]:
                p(f"       Evidence: Q: {ev['question'][:60]}")
                p(f"                 A: {ev['answer'][:60]}")
    else:
        p(f"\n  No findings.")

    p(f"\n  Log: {LOG_FILE}")


if __name__ == "__main__":
    asyncio.run(run())
