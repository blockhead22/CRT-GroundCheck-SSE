from personal_agent.task_agent import classify_intent
from routes.chat import _is_self_referential_question


def test_chat_self_referential_detects_what_matters_to_you():
    assert _is_self_referential_question("Aether, what matters to you?") is True


def test_task_agent_classifies_what_matters_to_you_as_self_referential():
    intent = classify_intent("Aether, what matters to you?")

    assert intent.intent_type == "self_referential"
    assert intent.route == "conversational"
