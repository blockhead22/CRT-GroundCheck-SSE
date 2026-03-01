from __future__ import annotations

import json
from pathlib import Path


def _iter_strings(value):
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for v in value.values():
            yield from _iter_strings(v)
    elif isinstance(value, list):
        for v in value:
            yield from _iter_strings(v)


def test_objective_cards_have_no_canned_user_questions():
    path = Path(__file__).resolve().parent.parent / "tools" / "agentic_eval" / "agentic_eval_objectives.v1.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    objectives = payload.get("objectives")
    assert isinstance(objectives, list) and objectives, "objectives list must exist"

    banned_fields = {"example_prompt", "example_question", "prompt_templates", "question_bank", "sample_turns"}
    for item in objectives:
        assert isinstance(item, dict)
        assert banned_fields.isdisjoint(set(item.keys())), "objective cards must not include canned prompt fields"

    all_strings = list(_iter_strings(payload))
    assert all("?" not in s for s in all_strings), "objective card content should be instruction-only, not fixed questions"
