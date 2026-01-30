import json

from personal_agent.tasking_loop import TaskingLoop


class DummyLLM:
    def __init__(self, responses):
        self._responses = list(responses)
        self.calls = 0

    def generate(self, _prompt, **_kwargs):
        if self.calls >= len(self._responses):
            raise AssertionError("DummyLLM ran out of responses")
        resp = self._responses[self.calls]
        self.calls += 1
        return resp


def test_plan_tasks_parses_json():
    payload = {
        "tasks": [
            {"id": "task-1", "goal": "Do thing", "acceptance_criteria": "Done"},
        ],
        "notes": "ok",
    }
    llm = DummyLLM([json.dumps(payload)])
    loop = TaskingLoop(llm_client=llm)
    plan = loop.plan_tasks("request")
    assert len(plan.tasks) == 1
    assert plan.tasks[0].task_id == "task-1"
    assert plan.tasks[0].goal == "Do thing"


def test_plan_tasks_fallback_on_bad_json():
    llm = DummyLLM(["not json"])
    loop = TaskingLoop(llm_client=llm)
    plan = loop.plan_tasks("request")
    assert len(plan.tasks) == 1
    assert "Respond to the user request" in plan.tasks[0].goal


def test_run_expands_when_missing_items():
    plan_payload = {
        "tasks": [
            {"id": "task-1", "goal": "Answer", "acceptance_criteria": "Covers request"},
        ],
        "notes": "",
    }
    coverage_missing = {"score": 0.4, "missing_items": ["Add example"], "notes": "missing example"}
    coverage_ok = {"score": 1.0, "missing_items": [], "notes": "ok"}

    llm = DummyLLM([
        json.dumps(plan_payload),          # plan
        json.dumps(coverage_missing),      # coverage check 1
        "Expanded answer with example.",   # expansion
        json.dumps(coverage_ok),           # coverage check 2
    ])
    loop = TaskingLoop(llm_client=llm, max_passes=2)
    result = loop.run("request", "base answer", allow_expansion=True)
    assert result.final_answer == "Expanded answer with example."
    assert result.passes == 2
    assert result.coverage.score == 1.0
