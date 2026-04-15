"""Aether Bench harness — Cold vs Warm paired trials.

Supports:
  - single-turn tasks (task has "prompt"): one call, one answer.
  - multi-turn tasks (task has "turns": [...]): sequential calls, conversation
    carried in-process.
  - brain swap mid-task (task has "swap_brain_after_turn": N): turns 0..N run
    on brain A; turns N+1..end run on brain B AND the conversation history
    is NOT carried across the swap (simulated session boundary). This is how
    we test Claim 3 — persistence across brain swaps.

For cold+swap: brain B sees only its first-swapped turn alone. No Aether.
For warm+swap: brain B sees the turn alone but can query Aether, which
(for the stub brain) is simulated via a process-global "substrate" dict
populated during warm turns.

Day 1 scope: plumbing + stub brain. Real brains (TPU vLLM, OpenAI, Claude,
Cookie) land D2-D4. Judgment on the final-turn answer only.

Usage:
    python -m labs.aether_bench.harness --smoke
    python -m labs.aether_bench.harness --brain stub --arm both --tasks all
    python -m labs.aether_bench.harness --brain stub --tasks ct_01
    python -m labs.aether_bench.harness --brain stub --swap-brain stub2 --tasks ct_01
"""
from __future__ import annotations

import argparse
import json
import sqlite3
import time
import uuid
from dataclasses import dataclass, asdict
from pathlib import Path
import os
from typing import Any, Callable

LAB_DIR = Path(__file__).resolve().parent
TASKS_PATH = LAB_DIR / "tasks.json"
DB_PATH = LAB_DIR / "trials.sqlite"


@dataclass
class TrialResult:
    trial_id: str
    task_id: str
    category: str
    arm: str
    brain: str                  # "stub" (single) or "stub>stub2" (swap)
    answer: str                 # final-turn answer (what the judge sees)
    all_turns_json: str         # full per-turn trace as JSON
    tokens_in: int              # summed across turns
    tokens_out: int
    tool_calls: int
    substrate_tool_calls: int
    wall_ms: int
    turns_count: int
    swapped: int                # 0/1
    error: str | None = None


# --- Substrate simulation (stub-only) --------------------------------------
# In the Warm arm, the stub brain "writes" facts from user turns into this
# dict. On swapped turns, the stub brain "reads" from this dict to simulate
# Aether recall. Cold arm ignores the dict entirely. Real brains will call
# the actual Aether MCP tools — this is just scaffolding so we can smoke-
# test the multi-turn plumbing end-to-end.

_SUBSTRATE: dict[str, list[str]] = {}


def _substrate_write(key: str, fact: str) -> None:
    _SUBSTRATE.setdefault(key, []).append(fact)


def _substrate_read(key: str) -> list[str]:
    return _SUBSTRATE.get(key, [])


def _substrate_reset() -> None:
    _SUBSTRATE.clear()


# --- Brain interface -------------------------------------------------------

# brain(messages, warm, substrate_key) -> dict with:
#   answer, tokens_in, tokens_out, tool_calls, substrate_tool_calls
# `messages` is a list of {"role": "user"|"assistant", "content": str}
# `substrate_key` identifies the task trial so the stub can share state
# across turns within a task.

Brain = Callable[[list[dict[str, str]], bool, str], dict[str, Any]]


def stub_brain(messages: list[dict[str, str]], warm: bool,
               substrate_key: str) -> dict[str, Any]:
    last_user = next((m["content"] for m in reversed(messages)
                      if m["role"] == "user"), "")
    sub_hits: list[str] = []
    sub_calls = 0

    if warm:
        # Write any user turn into substrate.
        _substrate_write(substrate_key, last_user)
        sub_calls += 1
        # Read substrate for recall simulation.
        sub_hits = _substrate_read(substrate_key)
        sub_calls += 1

    in_toks = sum(len(m["content"]) for m in messages) // 4
    # Warm answers are shorter + leverage substrate; cold answers are verbose.
    if warm:
        body = f"[stub warm] recalled {len(sub_hits)} fact(s); {last_user[:40]}"
        out_toks = 40 + 5 * len(sub_hits)
    else:
        body = f"[stub cold] {last_user[:40]}"
        out_toks = 120
    return {
        "answer": body,
        "tokens_in": in_toks,
        "tokens_out": out_toks,
        "tool_calls": 2 if warm else 0,
        "substrate_tool_calls": sub_calls,
    }


def stub2_brain(messages: list[dict[str, str]], warm: bool,
                substrate_key: str) -> dict[str, Any]:
    """Second stub — different personality, different token profile.
    Used as 'brain B' on swap tests."""
    r = stub_brain(messages, warm, substrate_key)
    r["answer"] = r["answer"].replace("stub", "stub2")
    r["tokens_out"] = r["tokens_out"] + 20
    return r


def _openai_chat_brain(base_url: str, model: str, api_key: str = "none",
                       max_tool_iters: int = 6):
    """Factory: Brain hitting any OpenAI-compatible /v1/chat/completions.

    Cold arm: single call, no tools.
    Warm arm: tools from aether_client.TOOL_SCHEMAS. The brain is expected
    to call aether_search / aether_remember; the harness executes each
    tool call locally against the Aether HTTP API and feeds results back.
    Loops up to `max_tool_iters` times or until the model returns no tool
    calls. Tokens + tool-call counts sum across iterations.

    If the server doesn't support OpenAI tools (some older vLLM builds),
    set AETHER_BENCH_NO_TOOLS=1 and Warm degrades to system-hint only."""
    import json as _json
    from urllib.request import Request, urlopen
    from . import aether_client

    no_tools = os.environ.get("AETHER_BENCH_NO_TOOLS") == "1"

    def _post(payload: dict) -> dict:
        req = Request(
            f"{base_url.rstrip('/')}/chat/completions",
            data=_json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json",
                     "Authorization": f"Bearer {api_key}"},
            method="POST",
        )
        with urlopen(req, timeout=180) as resp:
            return _json.loads(resp.read().decode("utf-8"))

    def brain(messages, warm, substrate_key):
        convo = list(messages)
        tokens_in = tokens_out = tool_calls = sub_calls = 0
        t0 = time.perf_counter()

        if warm:
            convo = [{"role": "system", "content":
                "You have access to the Aether belief substrate via tools. "
                "Call aether_search BEFORE answering when prior user context, "
                "preferences, or earlier-session facts may be relevant. Call "
                "aether_remember to persist any user-supplied fact that should "
                "survive across sessions or brain swaps. Answer concisely and "
                "ground claims in what substrate search returns."}] + convo

        for _ in range(max_tool_iters if warm else 1):
            payload = {
                "model": model,
                "messages": convo,
                "temperature": 0.2,
                "max_tokens": 512,
            }
            if warm and not no_tools:
                payload["tools"] = aether_client.TOOL_SCHEMAS
                payload["tool_choice"] = "auto"

            body = _post(payload)
            choice = body["choices"][0]
            msg = choice["message"]
            usage = body.get("usage") or {}
            tokens_in += int(usage.get("prompt_tokens", 0))
            tokens_out += int(usage.get("completion_tokens", 0))

            tcs = msg.get("tool_calls") or []
            if not tcs:
                final = msg.get("content") or ""
                return {
                    "answer": final,
                    "tokens_in": tokens_in,
                    "tokens_out": tokens_out,
                    "tool_calls": tool_calls,
                    "substrate_tool_calls": sub_calls,
                    "_latency_ms": int((time.perf_counter() - t0) * 1000),
                }

            # Record the assistant turn (with tool_calls) so the next call
            # can reference tool_call_id in tool messages.
            convo.append({"role": "assistant",
                          "content": msg.get("content") or "",
                          "tool_calls": tcs})
            for tc in tcs:
                tool_calls += 1
                name = tc["function"]["name"]
                try:
                    args = _json.loads(tc["function"].get("arguments") or "{}")
                except Exception:
                    args = {}
                result = aether_client.execute(name, args)
                if name.startswith("aether_"):
                    sub_calls += 1
                convo.append({
                    "role": "tool",
                    "tool_call_id": tc.get("id", ""),
                    "name": name,
                    "content": _json.dumps(result),
                })

        # Ran out of iterations without a final answer.
        return {
            "answer": "[no final answer — max tool iterations reached]",
            "tokens_in": tokens_in,
            "tokens_out": tokens_out,
            "tool_calls": tool_calls,
            "substrate_tool_calls": sub_calls,
            "_latency_ms": int((time.perf_counter() - t0) * 1000),
        }

    return brain


def _make_tpu_brain():
    import os
    url = os.environ.get("TPU_BRAIN_URL")  # e.g. http://1.2.3.4:8000/v1
    if not url:
        def _unset(*_a, **_k):
            raise SystemExit("TPU_BRAIN_URL not set. "
                             "Export it to point at your TPU vLLM endpoint.")
        return _unset
    model = os.environ.get("TPU_BRAIN_MODEL", "Qwen/Qwen2.5-7B-Instruct")
    return _openai_chat_brain(url, model)


def _make_ollama_brain(model: str, tag: str = "ollama"):
    url = (os.environ.get("OLLAMA_BASE_URL") or "http://localhost:11434").rstrip("/")
    if not url.endswith("/v1"):
        url = url + "/v1"
    return _openai_chat_brain(url, model, api_key="ollama")


BRAINS: dict[str, Brain] = {
    "stub": stub_brain,
    "stub2": stub2_brain,
    "tpu_qwen7b": _make_tpu_brain(),
    "ollama_qwen7b": _make_ollama_brain("qwen2.5:7b-instruct"),
    "ollama_qwen14b": _make_ollama_brain("qwen3:14b"),
    "ollama_coder14b": _make_ollama_brain("qwen2.5-coder:14b"),
}


# --- DB --------------------------------------------------------------------

SCHEMA = """
CREATE TABLE IF NOT EXISTS trials (
    trial_id TEXT PRIMARY KEY,
    task_id TEXT NOT NULL,
    category TEXT NOT NULL,
    arm TEXT NOT NULL,
    brain TEXT NOT NULL,
    answer TEXT,
    all_turns_json TEXT,
    tokens_in INTEGER,
    tokens_out INTEGER,
    tool_calls INTEGER,
    substrate_tool_calls INTEGER,
    wall_ms INTEGER,
    turns_count INTEGER,
    swapped INTEGER,
    error TEXT,
    created_at REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_trials_task ON trials(task_id);
CREATE INDEX IF NOT EXISTS idx_trials_arm  ON trials(arm);
CREATE INDEX IF NOT EXISTS idx_trials_brain ON trials(brain);
"""


def db() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.executescript(SCHEMA)
    # Graceful migration if user already has the v0.1 trials table.
    cols = {r[1] for r in conn.execute("PRAGMA table_info(trials)")}
    for col, ddl in [
        ("all_turns_json", "ALTER TABLE trials ADD COLUMN all_turns_json TEXT"),
        ("turns_count",    "ALTER TABLE trials ADD COLUMN turns_count INTEGER"),
        ("swapped",        "ALTER TABLE trials ADD COLUMN swapped INTEGER"),
    ]:
        if col not in cols:
            conn.execute(ddl)
    conn.commit()
    return conn


def save(conn: sqlite3.Connection, r: TrialResult) -> None:
    row = asdict(r) | {"created_at": time.time()}
    cols = ",".join(row.keys())
    qs = ",".join("?" * len(row))
    conn.execute(f"INSERT INTO trials ({cols}) VALUES ({qs})", tuple(row.values()))
    conn.commit()


# --- Runner ----------------------------------------------------------------

def load_tasks() -> list[dict[str, Any]]:
    return json.loads(TASKS_PATH.read_text(encoding="utf-8"))["tasks"]


def _task_turns(task: dict[str, Any]) -> list[str]:
    if "turns" in task:
        return list(task["turns"])
    return [task["prompt"]]


def run_trial(task: dict[str, Any], arm: str, brain_a: str,
              brain_b: str | None) -> TrialResult:
    """Runs all turns of a task in one arm. Handles mid-task brain swap.

    Cold arm: no substrate, no swap-persistence magic (the stub still writes
    to _SUBSTRATE but the brain never reads it in cold mode, so it's inert).
    Warm arm: brain writes + reads substrate; swapped turns rely on it.
    Swap: at `swap_brain_after_turn` N, conversation is RESET and brain B
    takes over. This simulates a session boundary."""
    turns = _task_turns(task)
    swap_after = task.get("swap_brain_after_turn")  # None or int
    warm = arm == "warm"
    substrate_key = f"{task['id']}::{arm}"
    _substrate_reset()  # isolate across trials

    messages: list[dict[str, str]] = []
    trace: list[dict[str, Any]] = []
    sum_in = sum_out = sum_tools = sum_sub = 0
    current_brain = brain_a
    actual_swapped = 0

    t0 = time.perf_counter()
    err: str | None = None
    try:
        for i, user_msg in enumerate(turns):
            # Swap point: reset conversation, switch brain.
            if swap_after is not None and i == swap_after + 1:
                if brain_b:
                    current_brain = brain_b
                    actual_swapped = 1
                messages = []  # simulated session boundary
            messages.append({"role": "user", "content": user_msg})
            brain = BRAINS[current_brain]
            out = brain(messages, warm, substrate_key)
            messages.append({"role": "assistant", "content": out["answer"]})
            trace.append({"turn": i, "brain": current_brain, **out})
            sum_in += out["tokens_in"]
            sum_out += out["tokens_out"]
            sum_tools += out["tool_calls"]
            sum_sub += out["substrate_tool_calls"]
    except Exception as e:
        err = f"{type(e).__name__}: {e}"

    wall_ms = int((time.perf_counter() - t0) * 1000)
    final_answer = trace[-1]["answer"] if trace else ""
    brain_label = current_brain if not actual_swapped else f"{brain_a}>{brain_b}"

    return TrialResult(
        trial_id=str(uuid.uuid4()),
        task_id=task["id"],
        category=task["category"],
        arm=arm,
        brain=brain_label,
        answer=final_answer,
        all_turns_json=json.dumps(trace),
        tokens_in=sum_in,
        tokens_out=sum_out,
        tool_calls=sum_tools,
        substrate_tool_calls=sum_sub,
        wall_ms=wall_ms,
        turns_count=len(turns),
        swapped=actual_swapped,
        error=err,
    )


def run(brain_a: str, brain_b: str | None, arm: str,
        task_filter: str) -> list[TrialResult]:
    tasks = load_tasks()
    if task_filter != "all":
        wanted = set(task_filter.split(","))
        tasks = [t for t in tasks if t["id"] in wanted]
        if not tasks:
            raise SystemExit(f"no tasks matched {task_filter!r}")
    arms = ["cold", "warm"] if arm == "both" else [arm]
    conn = db()
    results: list[TrialResult] = []
    for t in tasks:
        for a in arms:
            r = run_trial(t, a, brain_a, brain_b)
            save(conn, r)
            results.append(r)
            tag = "SWAP" if r.swapped else "    "
            print(f"[{a:>4}] {tag} {r.task_id:<6} turns={r.turns_count} "
                  f"{r.wall_ms:>5}ms  tok={r.tokens_in}+{r.tokens_out}  "
                  f"tools={r.tool_calls}(sub={r.substrate_tool_calls})  "
                  f"brain={r.brain}")
    conn.close()
    return results


def smoke() -> None:
    print(f"db: {DB_PATH}")
    print("\n-- single-turn task, no swap --")
    run("stub", None, "both", "sr_01")
    print("\n-- multi-turn continuity task WITH brain swap (stub -> stub2) --")
    run("stub", "stub2", "both", "ct_01")
    print("\n-- same continuity task, NO swap (for comparison) --")
    run("stub", None, "both", "ct_02")
    print("\nsmoke ok")


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--brain", default="stub", choices=list(BRAINS),
                   help="brain A (and default when no swap)")
    p.add_argument("--swap-brain", default=None, choices=list(BRAINS),
                   help="brain B for tasks with swap_brain_after_turn set")
    p.add_argument("--arm", default="both", choices=["cold", "warm", "both"])
    p.add_argument("--tasks", default="all",
                   help="comma-separated task IDs or 'all'")
    p.add_argument("--smoke", action="store_true")
    a = p.parse_args()
    if a.smoke:
        smoke()
    else:
        run(a.brain, a.swap_brain, a.arm, a.tasks)


if __name__ == "__main__":
    main()
