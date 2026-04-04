from personal_agent.task_agent import classify_intent
from routes.chat import (
    _answer_personal_fact_bundle,
    _extract_personal_fact_bundle_slots,
    _is_self_referential_question,
    _is_user_reflection_question,
)


def test_chat_self_referential_detects_what_matters_to_you():
    assert _is_self_referential_question("Aether, what matters to you?") is True


def test_task_agent_classifies_what_matters_to_you_as_self_referential():
    intent = classify_intent("Aether, what matters to you?")

    assert intent.intent_type == "self_referential"
    assert intent.route == "task"


def test_chat_detects_user_reflection_question():
    assert _is_user_reflection_question("What do you think I value?") is True


def test_task_agent_classifies_user_reflection_as_task():
    intent = classify_intent("What do you think I value?")

    assert intent.intent_type == "user_reflection"
    assert intent.route == "task"


def test_extracts_bundled_personal_fact_slots():
    slots = _extract_personal_fact_bundle_slots(
        "What is my name, my favorite color and my favorite drink?"
    )

    assert slots == ["name", "favorite_color", "favorite_drink"]


def test_task_agent_classifies_bundled_personal_fact_question_as_task():
    intent = classify_intent("What is my name, my favorite color and my favorite drink?")

    assert intent.intent_type == "broad_recall"
    assert intent.route == "task"
    assert intent.slots.get("requested_slots") == ["name", "favorite_color", "favorite_drink"]


def test_personal_fact_bundle_answers_each_field_independently():
    class _Engine:
        def get_effective_user_facts(self, thread_id=None):
            return {
                "name": {"value": "Nick"},
                "favorite_color": {"value": "orange"},
            }

        def get_fact_history(self, slot, thread_id=None):
            histories = {
                "name": [{"value": "Nick"}],
                "favorite_color": [{"value": "orange"}, {"value": "red"}, {"value": "burgundy"}],
                "favorite_drink": [],
            }
            return histories.get(slot, [])

    answer = _answer_personal_fact_bundle(
        "What is my name, my favorite color and my favorite drink?",
        _Engine(),
        "t1",
    )

    lowered = answer.lower()
    assert "name: nick" in lowered
    assert "favorite color: conflicted" in lowered
    assert "orange" in lowered
    assert "red" in lowered
    assert "favorite drink: i don't have a grounded value for that yet." in lowered
