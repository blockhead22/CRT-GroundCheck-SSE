"""Tasking loop for planner -> coverage checking -> optional expansion.

Lightweight, in-memory only (no DB writes) to avoid complexity and sprawl.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class TaskItem:
    task_id: str
    goal: str
    acceptance_criteria: str
    status: str = "planned"
    output: Optional[str] = None
    summary: Optional[str] = None


@dataclass
class TaskPlan:
    tasks: List[TaskItem] = field(default_factory=list)
    notes: Optional[str] = None


@dataclass
class CoverageResult:
    score: float
    missing_items: List[str] = field(default_factory=list)
    notes: Optional[str] = None


@dataclass
class TaskingResult:
    final_answer: str
    plan: TaskPlan
    coverage: CoverageResult
    passes: int
    mode: str = "plan+coverage"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "mode": self.mode,
            "passes": self.passes,
            "final_answer": self.final_answer,
            "plan": {
                "notes": self.plan.notes,
                "tasks": [
                    {
                        "task_id": t.task_id,
                        "goal": t.goal,
                        "acceptance_criteria": t.acceptance_criteria,
                        "status": t.status,
                        "summary": t.summary,
                    }
                    for t in self.plan.tasks
                ],
            },
            "coverage": {
                "score": self.coverage.score,
                "missing_items": self.coverage.missing_items,
                "notes": self.coverage.notes,
            },
        }


def _safe_json_from_text(text: str) -> Optional[Dict[str, Any]]:
    """Best-effort JSON extraction from LLM output."""
    if not text:
        return None
    text = text.strip()
    try:
        return json.loads(text)
    except Exception:
        pass
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end <= start:
        return None
    try:
        return json.loads(text[start : end + 1])
    except Exception:
        return None


class TaskingLoop:
    """Planner -> coverage checker -> optional expansion."""

    def __init__(
        self,
        llm_client: Optional[Any] = None,
        max_tasks: int = 6,
        max_passes: int = 2,
    ) -> None:
        self.llm = llm_client
        self.max_tasks = max_tasks
        self.max_passes = max_passes

    def plan_tasks(self, request: str) -> TaskPlan:
        if not self.llm:
            return TaskPlan(tasks=[
                TaskItem(
                    task_id="task-1",
                    goal="Respond to the user request.",
                    acceptance_criteria="Answer satisfies the request and constraints.",
                )
            ])

        prompt = f"""You are a planner. Break the user request into 1-6 atomic tasks.
Return JSON ONLY with this shape:
{{
  "tasks": [
    {{"id": "task-1", "goal": "...", "acceptance_criteria": "..."}}
  ],
  "notes": "optional"
}}

User request:
{request}
"""
        raw = self.llm.generate(prompt, max_tokens=400, temperature=0.2)
        data = _safe_json_from_text(raw)
        if not data or "tasks" not in data:
            return TaskPlan(tasks=[
                TaskItem(
                    task_id="task-1",
                    goal="Respond to the user request.",
                    acceptance_criteria="Answer satisfies the request and constraints.",
                )
            ])

        tasks: List[TaskItem] = []
        for idx, item in enumerate(data.get("tasks", [])[: self.max_tasks]):
            goal = str(item.get("goal") or "").strip()
            if not goal:
                continue
            task_id = str(item.get("id") or f"task-{idx + 1}").strip()
            acceptance = str(item.get("acceptance_criteria") or "Task completed.").strip()
            tasks.append(TaskItem(task_id=task_id, goal=goal, acceptance_criteria=acceptance))

        if not tasks:
            tasks.append(
                TaskItem(
                    task_id="task-1",
                    goal="Respond to the user request.",
                    acceptance_criteria="Answer satisfies the request and constraints.",
                )
            )

        return TaskPlan(tasks=tasks, notes=str(data.get("notes") or "").strip() or None)

    def coverage_check(self, request: str, answer: str, plan: TaskPlan) -> CoverageResult:
        if not self.llm:
            return CoverageResult(score=1.0, missing_items=[], notes="LLM unavailable; skipping check.")

        task_lines = "\n".join(
            f"- {t.goal} | Accept: {t.acceptance_criteria}" for t in plan.tasks
        )
        prompt = f"""You are a coverage checker. Compare the user request, task list, and answer.
Return JSON ONLY with this shape:
{{
  "score": 0.0,
  "missing_items": ["..."],
  "notes": "optional"
}}

User request:
{request}

Task list:
{task_lines}

Answer:
{answer}
"""
        raw = self.llm.generate(prompt, max_tokens=300, temperature=0.1)
        data = _safe_json_from_text(raw)
        if not data:
            return CoverageResult(score=1.0, missing_items=[], notes="Coverage parse failed; assuming covered.")

        try:
            score = float(data.get("score", 1.0))
        except Exception:
            score = 1.0
        missing = [str(m).strip() for m in data.get("missing_items", []) if str(m).strip()]
        notes = str(data.get("notes") or "").strip() or None
        return CoverageResult(score=score, missing_items=missing, notes=notes)

    def expand_answer(self, request: str, answer: str, missing_items: List[str]) -> str:
        if not self.llm or not missing_items:
            return answer
        missing = "\n".join(f"- {m}" for m in missing_items)
        prompt = f"""Revise the answer to cover the missing items.
Keep the original tone. Only add what is missing. Return the revised answer only.

User request:
{request}

Missing items:
{missing}

Current answer:
{answer}
"""
        return self.llm.generate(prompt, max_tokens=500, temperature=0.3)

    def run(self, request: str, base_answer: str, allow_expansion: bool = True) -> TaskingResult:
        plan = self.plan_tasks(request)
        coverage = self.coverage_check(request, base_answer, plan)
        answer = base_answer
        passes = 1

        if allow_expansion:
            while coverage.missing_items and passes < self.max_passes:
                answer = self.expand_answer(request, answer, coverage.missing_items)
                passes += 1
                coverage = self.coverage_check(request, answer, plan)

        return TaskingResult(final_answer=answer, plan=plan, coverage=coverage, passes=passes)
