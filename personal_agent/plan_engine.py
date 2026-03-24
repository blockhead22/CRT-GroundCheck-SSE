"""PlanEngine — generates, manages, and advances task plans (v2.9.2).

Responsibilities:
  - Decide if a user message warrants a plan
  - Ask an LLM to break a request into structured steps
  - Advance steps after tool execution
  - Handle user-input for waiting_input steps
"""

from __future__ import annotations

import json
import logging
import re
import time
from typing import Any, Optional

logger = logging.getLogger(__name__)

# Keywords that suggest the user wants multi-step work
_PLAN_KEYWORDS = re.compile(
    r"\b(plan|steps|todo|today i want|first .+ then|phase|workflow|checklist"
    r"|and then|after that|followed by|next|finally)\b",
    re.IGNORECASE,
)

# Multi-action patterns (3+ actions separated by commas/and)
_MULTI_ACTION = re.compile(
    r"(?:,\s*(?:and\s+)?|;\s*|\band\b\s+){2,}",
    re.IGNORECASE,
)

_PLAN_GENERATION_PROMPT = """\
You are a task planning assistant. Break the user's request into concrete, actionable steps.

For each step, provide:
- title: short action phrase (e.g., "Create tool registry")
- description: optional detail about what this step involves
- tool_name: if a specific tool/action is needed (file_read, web_search, git_commit, etc.), otherwise null
- needs_user_input: if the step needs user clarification before executing, describe what's needed; otherwise null

Return ONLY valid JSON, no markdown fences:
{
  "title": "overall plan title",
  "description": "brief summary of the plan",
  "steps": [
    {"title": "...", "description": "...", "tool_name": null, "needs_user_input": null},
    ...
  ]
}

User request: """


class PlanEngine:
    """Generates, manages, and executes plans from natural language."""

    def __init__(self, llm_client=None, session_db=None):
        self.llm_client = llm_client
        self.db = session_db

    def should_create_plan(self, message: str, intent=None) -> bool:
        """Decide if a message warrants a plan vs direct execution.

        Returns True if the message looks like multi-step work.
        """
        # Explicit plan keywords
        if _PLAN_KEYWORDS.search(message):
            return True
        # Multiple actions (3+ comma/and separated clauses)
        if _MULTI_ACTION.search(message):
            return True
        # Long messages (> 100 chars) with multiple sentences often describe projects
        sentences = [s.strip() for s in re.split(r'[.!?]+', message) if s.strip()]
        if len(sentences) >= 3 and len(message) > 100:
            return True
        return False

    def generate_plan(
        self, user_message: str, conversation_history: list[dict] | None = None,
    ) -> dict | None:
        """Ask the LLM to break a request into a structured plan with steps.

        Returns the saved plan dict, or None if generation fails.
        """
        if not self.llm_client or not self.db:
            logger.debug("[PLAN] No LLM client or DB — cannot generate plan")
            return None

        prompt = _PLAN_GENERATION_PROMPT + user_message

        try:
            # Use the LLM client to generate the plan
            response = self.llm_client.generate(
                prompt=prompt,
                system="You are a concise task planner. Return only JSON.",
                max_tokens=1024,
            )
            if not response:
                return None

            # Parse JSON from response
            text = response.strip()
            # Strip markdown fences if present
            if text.startswith("```"):
                text = re.sub(r"^```(?:json)?\s*", "", text)
                text = re.sub(r"\s*```$", "", text)

            plan_data = json.loads(text)
            title = plan_data.get("title", "Untitled Plan")
            description = plan_data.get("description")
            steps = plan_data.get("steps", [])

            if not steps:
                logger.debug("[PLAN] LLM returned no steps")
                return None

            # Save to DB
            plan = self.db.create_plan(
                title=title,
                description=description,
                created_by="aether",
                steps=steps,
            )
            logger.info("[PLAN] Generated plan '%s' with %d steps", title, len(steps))
            return plan

        except (json.JSONDecodeError, KeyError) as e:
            logger.warning("[PLAN] Failed to parse LLM plan response: %s", e)
            return None
        except Exception as e:
            logger.warning("[PLAN] Plan generation failed: %s", e)
            return None

    def advance_step(
        self, plan_id: str, step_result: str | None = None,
    ) -> dict | None:
        """Mark current step complete, return next step (or None if done).

        Args:
            plan_id: The plan to advance.
            step_result: Optional output from the completed step.

        Returns:
            Next step dict, or None if all steps are done.
        """
        if not self.db:
            return None

        # If there's a result, store it on the current in_progress step
        if step_result:
            steps = self.db.get_plan_steps(plan_id)
            for s in steps:
                if s["status"] == "in_progress":
                    self.db.update_step(
                        s["id"],
                        output_json=step_result,
                        status="completed",
                        completed_at=time.time(),
                    )
                    break

        return self.db.advance_plan(plan_id)

    def handle_user_input(
        self, plan_id: str, user_input: str,
    ) -> dict | None:
        """Process user input for a step that was waiting.

        Returns the step, now ready for execution, or None.
        """
        if not self.db:
            return None

        steps = self.db.get_plan_steps(plan_id)
        for s in steps:
            if s["status"] == "waiting_input":
                self.db.update_step(
                    s["id"],
                    user_input=user_input,
                    status="in_progress",
                )
                s["user_input"] = user_input
                s["status"] = "in_progress"
                return s
        return None

    def get_plan_progress_summary(self, plan_id: str) -> str:
        """Return a human-readable progress string like 'Step 2 of 5 complete'."""
        if not self.db:
            return ""
        steps = self.db.get_plan_steps(plan_id)
        if not steps:
            return ""
        completed = sum(1 for s in steps if s["status"] == "completed")
        total = len(steps)
        current = next(
            (s for s in steps if s["status"] in ("in_progress", "waiting_input")),
            None,
        )
        if completed == total:
            return f"All {total} steps complete!"
        if current:
            return f"Step {completed + 1} of {total}: {current['title']}"
        return f"{completed}/{total} steps complete"
