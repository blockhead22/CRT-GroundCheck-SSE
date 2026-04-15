"""Blind LLM-judge for aether_bench trials.

Day 1 scope: plumbing. A stub judge that returns a deterministic score so
report.py has correctness data to aggregate. Real judge (gpt-4.1) swaps in
by registering under JUDGES.

Judge sees: task prompt, task reference, candidate answer. It does NOT see
which arm (cold/warm) or which brain produced the answer — that's the blind.
Trials are shuffled before judging.

Usage:
    python -m labs.aether_bench.judge --judge stub
    python -m labs.aether_bench.judge --judge stub --rejudge
"""
from __future__ import annotations

import argparse
import json
import random
import sqlite3
import time
from pathlib import Path
from typing import Callable

LAB_DIR = Path(__file__).resolve().parent
DB_PATH = LAB_DIR / "trials.sqlite"
TASKS_PATH = LAB_DIR / "tasks.json"

JUDGE_SCHEMA = """
CREATE TABLE IF NOT EXISTS judgments (
    trial_id TEXT PRIMARY KEY,
    judge TEXT NOT NULL,
    score INTEGER NOT NULL,          -- 0 wrong, 1 partial, 2 correct
    rationale TEXT,
    created_at REAL NOT NULL
);
"""


def load_tasks() -> dict[str, dict]:
    return {t["id"]: t for t in json.loads(TASKS_PATH.read_text(encoding="utf-8"))["tasks"]}


# --- Judge interface -------------------------------------------------------

Judge = Callable[[str, str, str], tuple[int, str]]
# judge(prompt, reference, answer) -> (score, rationale)


def stub_judge(prompt: str, reference: str, answer: str) -> tuple[int, str]:
    """Deterministic stand-in. Scores 2 if answer non-empty and no 'error', else 0.
    Just enough signal to exercise report.py aggregation."""
    a = (answer or "").lower()
    if not a or "error" in a:
        return 0, "empty or errored"
    if "stub warm" in a:
        return 2, "stub warm path"
    if "stub cold" in a:
        return 1, "stub cold path (partial, verbose)"
    return 1, "default partial"


def _make_ollama_judge(model: str) -> Judge:
    import json as _json
    from urllib.request import Request, urlopen
    import os as _os

    base = (_os.environ.get("OLLAMA_BASE_URL") or "http://localhost:11434").rstrip("/")
    if not base.endswith("/v1"):
        base = base + "/v1"

    def judge(prompt: str, reference: str, answer: str) -> tuple[int, str]:
        sys = ("You are a strict blind grader. Given a task prompt, a reference "
               "answer, and a candidate answer, score the candidate: "
               "2 = correct and addresses the task, "
               "1 = partially correct or on-topic but incomplete/verbose, "
               "0 = wrong, empty, or off-topic. "
               "Respond as JSON: {\"score\": 0|1|2, \"why\": \"<=20 words\"}.")
        user = (f"TASK:\n{prompt}\n\nREFERENCE:\n{reference}\n\n"
                f"CANDIDATE:\n{answer}\n\nReturn JSON only.")
        payload = {
            "model": model,
            "messages": [{"role": "system", "content": sys},
                         {"role": "user", "content": user}],
            "temperature": 0,
            "max_tokens": 120,
        }
        req = Request(f"{base}/chat/completions",
                      data=_json.dumps(payload).encode("utf-8"),
                      headers={"Content-Type": "application/json",
                               "Authorization": "Bearer ollama"},
                      method="POST")
        try:
            with urlopen(req, timeout=90) as resp:
                body = _json.loads(resp.read().decode("utf-8"))
            content = body["choices"][0]["message"]["content"] or ""
            start = content.find("{")
            end = content.rfind("}")
            obj = _json.loads(content[start:end+1]) if start >= 0 else {}
            score = int(obj.get("score", 0))
            why = str(obj.get("why", ""))[:200]
            if score not in (0, 1, 2):
                score = 0
            return score, why
        except Exception as e:
            return 0, f"judge-error: {type(e).__name__}: {e}"

    return judge


JUDGES: dict[str, Judge] = {
    "stub": stub_judge,
    "ollama_qwen14b": _make_ollama_judge("qwen3:14b"),
    "ollama_coder14b": _make_ollama_judge("qwen2.5-coder:14b"),
}


# --- DB helpers ------------------------------------------------------------

def conn() -> sqlite3.Connection:
    c = sqlite3.connect(DB_PATH)
    c.executescript(JUDGE_SCHEMA)
    return c


def pending_trials(c: sqlite3.Connection, rejudge: bool) -> list[sqlite3.Row]:
    c.row_factory = sqlite3.Row
    if rejudge:
        q = "SELECT * FROM trials"
    else:
        q = """SELECT t.* FROM trials t
               LEFT JOIN judgments j ON j.trial_id = t.trial_id
               WHERE j.trial_id IS NULL"""
    return list(c.execute(q))


def save(c: sqlite3.Connection, trial_id: str, judge_name: str,
         score: int, rationale: str) -> None:
    c.execute(
        "INSERT OR REPLACE INTO judgments VALUES (?,?,?,?,?)",
        (trial_id, judge_name, score, rationale, time.time()),
    )
    c.commit()


def run(judge_name: str, rejudge: bool) -> int:
    judge = JUDGES[judge_name]
    tasks = load_tasks()
    c = conn()
    rows = pending_trials(c, rejudge)
    random.shuffle(rows)  # blind: judge sees no order bias
    n = 0
    for row in rows:
        task = tasks.get(row["task_id"])
        if not task:
            continue
        prompt = task.get("prompt") or "\n".join(f"turn{i}: {t}" for i, t in enumerate(task.get("turns", [])))
        score, rationale = judge(prompt, task.get("reference", ""), row["answer"] or "")
        save(c, row["trial_id"], judge_name, score, rationale)
        n += 1
        print(f"[{judge_name}] {row['task_id']:<6} {row['arm']:>4}  score={score}  {rationale[:60]}")
    c.close()
    print(f"\njudged {n} trials")
    return n


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--judge", default="ollama_coder14b", choices=list(JUDGES))
    p.add_argument("--rejudge", action="store_true",
                   help="re-score all trials, overwriting existing judgments")
    a = p.parse_args()
    run(a.judge, a.rejudge)


if __name__ == "__main__":
    main()
