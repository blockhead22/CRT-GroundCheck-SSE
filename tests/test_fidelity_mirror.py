from __future__ import annotations

import numpy as np

from personal_agent import fidelity_mirror
from personal_agent.fidelity_mirror import check_fidelity


def test_generated_speech_does_not_ground_itself(monkeypatch):
    vectors = {
        "What do you know about my employer?": np.array([0.0, 1.0, 0.0], dtype=np.float32),
        "You work at OpenAI.": np.array([1.0, 0.0, 0.0], dtype=np.float32),
    }

    def fake_encode(text: str):
        return vectors.get(text, np.array([0.0, 0.0, 1.0], dtype=np.float32))

    monkeypatch.setattr(fidelity_mirror, "_encode", fake_encode)

    score = check_fidelity(
        response="You work at OpenAI.",
        query="What do you know about my employer?",
        memories=[
            {
                "text": "You work at OpenAI.",
                "trust": 0.95,
                "source": "system",
                "kind": "observation",
            }
        ],
    )

    assert score.passed is False
    assert score.belief_fidelity == 0.0
    assert score.factual_grounding == 0.0
    assert any("Excluded 1 generated-speech" in f for f in score.findings)
    assert any("No belief-support memories" in f for f in score.findings)


def test_user_fact_still_counts_as_belief_support(monkeypatch):
    vectors = {
        "What do you know about my employer?": np.array([1.0, 0.0, 0.0], dtype=np.float32),
        "You work at OpenAI.": np.array([1.0, 0.0, 0.0], dtype=np.float32),
        "My employer is OpenAI.": np.array([1.0, 0.0, 0.0], dtype=np.float32),
    }

    def fake_encode(text: str):
        return vectors.get(text, np.array([0.0, 0.0, 1.0], dtype=np.float32))

    monkeypatch.setattr(fidelity_mirror, "_encode", fake_encode)

    score = check_fidelity(
        response="You work at OpenAI.",
        query="What do you know about my employer?",
        memories=[
            {
                "text": "My employer is OpenAI.",
                "trust": 0.95,
                "source": "user",
                "kind": "user_fact",
            }
        ],
    )

    assert score.passed is True
    assert score.belief_fidelity > 0.9
    assert score.factual_grounding > 0.9
    assert not any("generated-speech" in f for f in score.findings)
