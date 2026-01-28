"""First-run onboarding utilities.

Goal: after a memory wipe / first run, collect a few user-provided facts and
preferences in an explicit, product-configurable way.

This module is intentionally simple and deterministic: it stores exactly what
the user types as structured memory lines ("FACT:" / "PREF:") so CRT can
reason about them via fact slots and contradiction tracking.

Extended with OnboardingStateMachine for API-driven step-by-step onboarding.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from enum import Enum
from typing import Any, Callable, Dict, Iterable, List, Optional, Tuple

from .crt_core import MemorySource

logger = logging.getLogger(__name__)


class OnboardingState(str, Enum):
    """Onboarding state machine states."""
    NOT_STARTED = "not_started"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    SKIPPED = "skipped"


@dataclass
class OnboardingStatus:
    """Current onboarding status for a thread."""
    state: OnboardingState
    current_step: int  # 0-indexed question number
    total_steps: int
    current_question: Optional[Dict[str, str]]  # {slot, prompt, kind}
    answers_collected: Dict[str, str]  # slot -> value
    
    @property
    def is_complete(self) -> bool:
        return self.state in (OnboardingState.COMPLETED, OnboardingState.SKIPPED)
    
    @property
    def progress_percent(self) -> int:
        if self.total_steps == 0:
            return 100
        return int((self.current_step / self.total_steps) * 100)


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
    
    # Also store in GlobalUserProfile for cross-thread access
    if hasattr(rag, 'user_profile') and rag.user_profile:
        try:
            rag.user_profile.update_from_text(f"My {slot} is {value}")
            logger.debug(f"[ONBOARDING] Stored {slot}={value} in GlobalUserProfile")
        except Exception as e:
            logger.debug(f"[ONBOARDING] Failed to store in GlobalUserProfile: {e}")


class OnboardingStateMachine:
    """
    State machine for API-driven step-by-step onboarding.
    
    Orchestrates the onboarding flow:
    1. Check if onboarding needed (memory empty + config enabled)
    2. Present questions one at a time
    3. Store answers in thread memory + GlobalUserProfile
    4. Track progress in session DB
    5. Allow skipping optional questions
    
    Usage:
        machine = OnboardingStateMachine(thread_id, rag, runtime_config, session_db)
        status = machine.get_status()
        
        if not status.is_complete:
            # Present status.current_question to user
            # When user answers:
            machine.submit_answer(answer_text)
            # Or to skip:
            machine.skip_current()
    """
    
    def __init__(
        self,
        thread_id: str,
        rag,  # CRTEnhancedRAG
        runtime_config: Dict[str, Any],
        session_db=None  # ThreadSessionDB
    ):
        self.thread_id = thread_id
        self.rag = rag
        self.runtime_config = runtime_config
        
        # Get session DB (optional)
        self.session_db = session_db
        if session_db is None:
            try:
                from .db_utils import get_thread_session_db
                self.session_db = get_thread_session_db()
            except ImportError:
                pass
        
        self.questions = get_onboarding_questions(runtime_config)
        self._answers: Dict[str, str] = {}
    
    def get_status(self) -> OnboardingStatus:
        """Get current onboarding status."""
        config = get_onboarding_config(self.runtime_config)
        enabled = bool(config.get("enabled", True))
        
        # Check session DB for progress
        current_step = 0
        completed = False
        
        if self.session_db:
            try:
                session = self.session_db.get_or_create_session(self.thread_id)
                current_step = session.get("onboarding_step", 0)
                completed = bool(session.get("onboarding_completed", False))
            except Exception as e:
                logger.debug(f"[ONBOARDING] Error getting session: {e}")
        
        if not enabled or completed:
            return OnboardingStatus(
                state=OnboardingState.COMPLETED if completed else OnboardingState.SKIPPED,
                current_step=len(self.questions),
                total_steps=len(self.questions),
                current_question=None,
                answers_collected=self._answers,
            )
        
        if not self.questions:
            return OnboardingStatus(
                state=OnboardingState.SKIPPED,
                current_step=0,
                total_steps=0,
                current_question=None,
                answers_collected={},
            )
        
        # Check if we should auto-start onboarding
        auto_run = bool(config.get("auto_run_when_memory_empty", True))
        if auto_run and not self._has_user_memories():
            state = OnboardingState.NOT_STARTED if current_step == 0 else OnboardingState.IN_PROGRESS
        else:
            state = OnboardingState.IN_PROGRESS if current_step < len(self.questions) else OnboardingState.COMPLETED
        
        # Get current question
        current_question = None
        if current_step < len(self.questions):
            current_question = self.questions[current_step]
        else:
            state = OnboardingState.COMPLETED
        
        return OnboardingStatus(
            state=state,
            current_step=current_step,
            total_steps=len(self.questions),
            current_question=current_question,
            answers_collected=self._answers,
        )
    
    def _has_user_memories(self) -> bool:
        """Check if thread has any USER memories (indicating prior interaction)."""
        try:
            all_memories = self.rag.memory._load_all_memories()
            return any(m.source == MemorySource.USER for m in all_memories)
        except Exception:
            return True  # Assume has memories on error (don't trigger onboarding)
    
    def submit_answer(self, answer: str) -> OnboardingStatus:
        """
        Submit answer for current question and advance to next.
        
        Args:
            answer: User's answer text (empty string to skip)
        
        Returns:
            Updated status after processing answer
        """
        status = self.get_status()
        
        if status.is_complete or not status.current_question:
            return status
        
        answer = (answer or "").strip()
        question = status.current_question
        
        # Store answer if provided
        if answer:
            store_onboarding_answer(
                self.rag,
                slot=question["slot"],
                value=answer,
                kind=question["kind"],
                important=True,
            )
            self._answers[question["slot"]] = answer
            
            # Update session DB with user name if this was the name question
            if question["slot"] == "name" and self.session_db:
                try:
                    self.session_db.set_user_name(self.thread_id, answer)
                except Exception as e:
                    logger.debug(f"[ONBOARDING] Error setting user name: {e}")
        
        # Advance to next question
        return self._advance_step()
    
    def skip_current(self) -> OnboardingStatus:
        """Skip current question and advance to next."""
        return self.submit_answer("")
    
    def skip_all(self) -> OnboardingStatus:
        """Skip all remaining questions and complete onboarding."""
        if self.session_db:
            try:
                self.session_db.mark_onboarding_completed(self.thread_id)
            except Exception as e:
                logger.debug(f"[ONBOARDING] Error marking completed: {e}")
        
        return OnboardingStatus(
            state=OnboardingState.SKIPPED,
            current_step=len(self.questions),
            total_steps=len(self.questions),
            current_question=None,
            answers_collected=self._answers,
        )
    
    def _advance_step(self) -> OnboardingStatus:
        """Advance to next onboarding step."""
        status = self.get_status()
        next_step = status.current_step + 1
        
        if self.session_db:
            try:
                if next_step >= len(self.questions):
                    self.session_db.mark_onboarding_completed(self.thread_id)
                else:
                    self.session_db.update_onboarding_step(self.thread_id, next_step)
            except Exception as e:
                logger.debug(f"[ONBOARDING] Error updating step: {e}")
        
        return self.get_status()
    
    def get_welcome_message(self) -> str:
        """Get welcome message for starting onboarding."""
        return (
            "👋 Welcome! I'd like to learn a bit about you so I can be more helpful.\n"
            "You can skip any question by leaving it blank or saying 'skip'."
        )
    
    def get_completion_message(self) -> str:
        """Get message shown when onboarding completes."""
        collected = len(self._answers)
        if collected == 0:
            return "✓ Setup complete. Feel free to tell me about yourself anytime!"
        elif collected == 1:
            return "✓ Got it! You can always update this info by telling me new facts."
        else:
            return f"✓ Thanks! I've stored {collected} pieces of info. You can update any of this later."


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


def should_run_onboarding(
    thread_id: str,
    rag,
    runtime_config: Dict[str, Any],
    session_db=None
) -> Tuple[bool, Optional[OnboardingStateMachine]]:
    """
    Check if onboarding should be presented for this thread.
    
    Returns:
        (should_run, state_machine) - state_machine is None if should_run is False
    """
    config = get_onboarding_config(runtime_config)
    enabled = bool(config.get("enabled", True))
    
    if not enabled:
        return False, None
    
    machine = OnboardingStateMachine(thread_id, rag, runtime_config, session_db)
    status = machine.get_status()
    
    if status.is_complete:
        return False, None
    
    # Only auto-run if memory is empty and config allows
    auto_run = bool(config.get("auto_run_when_memory_empty", True))
    if auto_run and not machine._has_user_memories():
        return True, machine
    
    # If in progress, continue
    if status.state == OnboardingState.IN_PROGRESS:
        return True, machine
    
    return False, None
