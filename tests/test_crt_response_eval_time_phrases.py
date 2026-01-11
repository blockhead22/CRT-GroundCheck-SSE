import pytest

from crt_response_eval import evaluate_turn


def test_memory_claim_named_entities_grounded_ignores_am_pm_time_markers():
    # Regression: the named-phrase extractor previously treated "AM and" as a named entity,
    # causing false failures when responses mentioned times like "9 AM and 5 PM".
    user_prompt = "Can you explain your process for updating your knowledge of The Printing Lair's business hours?"
    assistant_answer = (
        "I remember it opens at 9 AM and closes at 5 PM. "
        "Provenance: this answer uses stored memories."
    )

    result = {
        "answer": assistant_answer,
        "retrieved_memories": [],
        "retrieved_docs": [],
        "contradiction_detected": False,
        "mode": "memory",
        "confidence": 0.5,
        "unresolved_contradictions": 0,
    }

    checks = evaluate_turn(user_prompt=user_prompt, result=result, expectations={})

    memory_checks = [c for c in checks if c.check == "memory_claim_named_entities_grounded"]
    assert memory_checks, "Expected memory_claim_named_entities_grounded check to be present"

    assert memory_checks[0].passed, memory_checks[0]
