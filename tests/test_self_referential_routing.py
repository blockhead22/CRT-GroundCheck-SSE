from personal_agent.task_agent import classify_intent
from routes.chat import _is_self_referential_question, _is_user_reflection_question


def test_chat_self_referential_detects_what_matters_to_you():
    assert _is_self_referential_question("Aether, what matters to you?") is True


def test_task_agent_classifies_what_matters_to_you_as_self_referential():
    intent = classify_intent("Aether, what matters to you?")

    assert intent.intent_type == "self_referential"
    assert intent.route == "conversational"


def test_chat_detects_user_reflection_question():
    assert _is_user_reflection_question("What do you think I value?") is True


def test_task_agent_classifies_user_reflection_as_task():
    intent = classify_intent("What do you think I value?")

    assert intent.intent_type == "user_reflection"
    assert intent.route == "task"
