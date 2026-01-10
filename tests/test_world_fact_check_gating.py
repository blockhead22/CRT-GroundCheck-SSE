import pytest


from personal_agent.reasoning import ReasoningEngine


@pytest.mark.parametrize(
    "answer, expected",
    [
        ("Your name is Nick.", False),
        ("I remember you said you run The Printing Lair.", False),
        ("From our chat, you told me your employer is Acme.", False),
        ("Provenance: this answer uses stored memories.", False),
        ("The capital of France is Lyon.", True),
        ("Paris is the capital of France.", True),
        ("The speed of light is 300,000 km/s.", True),
        ("You said the capital of France is Lyon.", False),
    ],
)
def test_should_run_world_fact_check(answer: str, expected: bool):
    assert ReasoningEngine.should_run_world_fact_check(answer) is expected
