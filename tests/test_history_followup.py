from personal_agent.task_agent import TaskIntent
from routes.chat import (
    _augment_query_with_pending_followup,
    _build_loop_acknowledgment,
    _history_answer_is_weak,
    _resolve_pending_followup_context,
    _resolve_personal_history_reference,
)


def test_health_history_followup_infers_prior_topic():
    history_messages = [
        {"role": "user", "content": "Aether, what do you know about my health history?"},
        {"role": "assistant", "content": "I have fragments, not the full picture."},
    ]

    query_text, topic_key, inferred = _resolve_personal_history_reference(
        "Let's try again?",
        history_messages,
    )

    assert query_text == "medical history"
    assert topic_key == "health_history"
    assert inferred is True


def test_history_followup_acknowledgment_mentions_context_carry_forward():
    history_messages = [
        {"role": "user", "content": "What do you know about my medical history?"},
        {"role": "assistant", "content": "I have fragments, not the full picture."},
    ]
    intent = TaskIntent(route="conversational", intent_type="conversational")

    ack = _build_loop_acknowledgment(
        "Lets try again?",
        intent,
        history_messages=history_messages,
    )

    assert "health-history thread" in ack.lower()
    assert "pulling that context back in" in ack.lower()


def test_generic_retry_history_answer_counts_as_weak():
    result = {
        "answer": (
            "Of course! From what I remember, you've mentioned a pivotal experience "
            "related to an ICU stay. If there are specific areas you want to discuss, "
            "feel free to share."
        ),
        "retrieved_memories": [{"id": "m1"}],
        "prompt_memories": [],
    }

    assert _history_answer_is_weak(result) is True


def test_direct_health_history_filler_answer_counts_as_weak():
    result = {
        "answer": (
            "I know that your health history is important to you. However, I don't have "
            "specific details about your medical history at this moment. If you'd like "
            "to share more, I can help you keep track of it."
        ),
        "retrieved_memories": [{"id": "m1"}],
        "prompt_memories": [],
    }

    assert _history_answer_is_weak(result) is True


def test_pending_followup_shortcut_reuses_governed_question():
    class _SessionDB:
        def get_active_governed_task(self, thread_id: str):
            return {
                "question": "What contradictions do you see between what I believe and how I act?",
                "objective": "Answer the contradiction follow-up",
                "orch_answer_so_far": "I can summarize the contradiction ledger so far.",
                "pending_followups": [],
            }

    context = _resolve_pending_followup_context(
        message="tell me",
        session_db=_SessionDB(),
        thread_id="t1",
        history_messages=[],
    )

    assert context is not None
    assert "what contradictions do you see" in context["question"].lower()

    augmented = _augment_query_with_pending_followup(
        message="tell me",
        pending_context=context,
    )
    assert "[PENDING FOLLOW-UP QUESTION]" in augmented
    assert "what contradictions do you see" in augmented.lower()
