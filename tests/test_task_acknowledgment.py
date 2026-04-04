from personal_agent.task_agent import TaskIntent, _generate_acknowledgment


def test_broad_recall_acknowledgment_mentions_history_context():
    intent = TaskIntent(route="task", intent_type="broad_recall")
    ack = _generate_acknowledgment(intent, "What do you know about my medical history?")
    assert "check what i already know" in ack.lower()
    assert "history context" in ack.lower()


def test_file_read_acknowledgment_explains_plan():
    intent = TaskIntent(route="task", intent_type="file_read")
    ack = _generate_acknowledgment(intent, "read app.tsx")
    assert "inspect" in ack.lower()
    assert "tell you what matters" in ack.lower()
