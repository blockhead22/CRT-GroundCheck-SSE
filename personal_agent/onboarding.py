"""First-run onboarding utilities.

Goal: after a memory wipe / first run, collect a few user-provided facts and
preferences in an explicit, product-configurable way.

This module is intentionally simple and deterministic: it stores exactly what
the user types as structured memory lines ("FACT:" / "PREF:") so CRT can
reason about them via fact slots and contradiction tracking.
"""

from __future__ import annotations

from typing import Any, Callable, Dict, Iterable, List, Optional

from .crt_core import MemorySource


def get_onboarding_config(runtime_config: Dict[str, Any]) -> Dict[str, Any]:
    cfg = runtime_config.get("onboarding") if isinstance(runtime_config, dict) else None
    return cfg if isinstance(cfg, dict) else {}


def get_onboarding_questions(runtime_config: Dict[str, Any]) -> List[Dict[str, str]]:
    cfg = get_onboarding_config(runtime_config)
    qs = cfg.get("questions")
    if isinstance(qs, list):
        out: List[Dict[str, str]] = []
        for q in qs:
            if not isinstance(q, dict):
                continue
            slot = (q.get("slot") or "").strip()
            prompt = (q.get("prompt") or "").strip()
            kind = (q.get("kind") or "").strip().lower() or "fact"
            if not slot or not prompt:
                continue
            if kind not in ("fact", "pref"):
                kind = "fact"
            out.append({"slot": slot, "prompt": prompt, "kind": kind})
        if out:
            return out
    return []


def store_onboarding_answer(
    rag,
    *,
    slot: str,
    value: str,
    kind: str,
    important: bool = True,
) -> None:
    slot = (slot or "").strip()
    value = (value or "").strip()
    kind = (kind or "fact").strip().lower()
    if not slot or not value:
        return

    prefix = "FACT" if kind == "fact" else "PREF"
    text = f"{prefix}: {slot} = {value}"

    rag.memory.store_memory(
        text=text,
        confidence=0.95,
        source=MemorySource.USER,
        context={"type": "onboarding", "kind": kind, "slot": slot},
        user_marked_important=important,
    )


def run_onboarding_interactive(
    rag,
    runtime_config: Dict[str, Any],
    *,
    input_fn: Callable[[str], str] = input,
    print_fn: Callable[[str], None] = print,
) -> Dict[str, str]:
    """Prompt the user and store onboarding answers.

    Returns a dict of {slot: value} for what was stored.
    """

    cfg = get_onboarding_config(runtime_config)
    enabled = bool(cfg.get("enabled", True))
    if not enabled:
        return {}

    questions = get_onboarding_questions(runtime_config)
    if not questions:
        return {}

    print_fn("\n🧩 Quick setup (you can skip any question):\n")

    stored: Dict[str, str] = {}
    for q in questions:
        prompt = q["prompt"].rstrip() + " "
        ans = (input_fn(prompt) or "").strip()
        if not ans:
            continue

        store_onboarding_answer(
            rag,
            slot=q["slot"],
            value=ans,
            kind=q["kind"],
            important=True,
        )
        stored[q["slot"]] = ans

    if stored:
        print_fn("\n✓ Setup saved. You can change any of this later by telling me updated facts.\n")
    else:
        print_fn("\n✓ Setup skipped.\n")

    return stored
