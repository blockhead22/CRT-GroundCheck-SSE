from __future__ import annotations

import personal_agent.continuous_loops as loops


class _FakeReflectionClient:
    def __init__(self, text: str):
        self.model = "fake-reflection-model"
        self._text = text

    def generate(self, *args, **kwargs):  # noqa: ANN002, ANN003
        return self._text


def _sample_interactions() -> list[dict]:
    return [
        {
            "user": "What do you know about me?",
            "assistant": "There is no information available.",
        },
        {
            "user": "Who is Nick Block to you?",
            "assistant": "I don't have a reliable stored memory for your assistant_name yet - if you tell me, I can remember it going forward.",
        },
        {
            "user": "Who is Nick Block to you?",
            "assistant": "I don't have a reliable stored memory for your assistant_name yet - if you tell me, I can remember it going forward.",
        },
    ]


def test_build_reflection_scorecard_adds_meta_awareness():
    interactions = _sample_interactions()
    messages = [row["user"] for row in interactions]
    scorecard = loops.build_reflection_scorecard(
        "tg_meta",
        messages,
        interactions=interactions,
    )

    meta = scorecard.get("meta_awareness") or {}
    assert meta.get("assistant_fallback_count", 0) >= 2
    assert float(meta.get("assistant_repetition_ratio", 0.0)) > 0.0
    assert float(meta.get("user_rephrase_ratio", 0.0)) > 0.0
    assert meta.get("meta_reflection_priority") in {"medium", "high"}


def test_build_personality_profile_includes_growth_and_traits():
    interactions = _sample_interactions()
    messages = [row["user"] for row in interactions]
    scorecard = loops.build_reflection_scorecard(
        "tg_meta",
        messages,
        interactions=interactions,
    )

    profile = loops.build_personality_profile(
        "tg_meta",
        messages,
        reflection_scorecard=scorecard,
    )

    assert isinstance(profile.get("growth_targets"), list)
    assert profile["growth_targets"]
    assert isinstance(profile.get("traits"), dict)
    assert "grounded" in profile["traits"]
    assert isinstance(profile.get("curiosity_agenda"), list)
    assert profile["curiosity_agenda"]
    assert isinstance(profile.get("learning_drive"), float)
    assert 0.0 <= float(profile.get("learning_drive") or 0.0) <= 1.0
    assert profile.get("mood") in {"self_correcting", "focused", "curious", "steady"}
    assert profile.get("meta_awareness") == scorecard.get("meta_awareness")


def test_build_llm_reflection_post_rejects_prompt_dump(monkeypatch):
    leaked = (
        "Thread\n"
        "First, the user wants a reflection post in a specific style.\n"
        "The output must be in JSON format with keys: title and body.\n"
        "One thing to improve and one open question to myself.\n"
    )
    monkeypatch.setattr(loops, "_get_journal_llm_client", lambda: _FakeReflectionClient(leaked))

    interactions = _sample_interactions()
    scorecard = loops.build_reflection_scorecard(
        "tg_meta",
        [row["user"] for row in interactions],
        interactions=interactions,
    )

    title, body, model = loops._build_llm_reflection_post(interactions, scorecard, profile={"verbosity": "balanced"})
    assert title is None
    assert body is None
    assert model is None


def test_build_llm_reflection_post_accepts_clean_json(monkeypatch):
    clean = (
        '{"title":"Quick check-in","body":"I stayed grounded and acknowledged uncertainty clearly. '
        'I should shorten my fallback wording so it sounds less robotic. '
        'Open question: should I ask a clarifying question sooner? '
        'Next step: summarize one known fact before asking for more context."}'
    )
    monkeypatch.setattr(loops, "_get_journal_llm_client", lambda: _FakeReflectionClient(clean))

    interactions = _sample_interactions()
    scorecard = loops.build_reflection_scorecard(
        "tg_meta",
        [row["user"] for row in interactions],
        interactions=interactions,
    )

    title, body, model = loops._build_llm_reflection_post(interactions, scorecard, profile={"verbosity": "balanced"})
    assert title == "Quick check-in"
    assert body is not None and "next step" in body.lower()
    assert model == "fake-reflection-model"
