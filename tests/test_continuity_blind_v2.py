import numpy as np

from tools.continuity_blind_v2 import (
    QUERY_SIMILARITY_GATE,
    _stable_top_indices,
    build_probe_topics,
    classify_pair,
    score_confidence_signals,
    score_continuity_signals,
)


def test_build_probe_topics_dedupes_and_preserves_order():
    topics = build_probe_topics()
    assert topics
    assert len(topics) == len(set(topics))
    assert topics[0] == "how to deal with stress and burnout"
    assert "business model and monetization strategy" in topics


def test_stable_top_indices_is_deterministic_on_ties():
    scores = np.array([0.7, 0.9, 0.9, 0.5])
    assert _stable_top_indices(scores, top_k=3).tolist() == [1, 2, 0]


def test_score_continuity_signals_detects_explicit_and_semantic():
    explicit = score_continuity_signals(
        "As we discussed before, I may have said something different."
    )
    semantic = score_continuity_signals(
        "Given what you've said, if that is still true, this changes."
    )
    assert explicit["explicit_continuity"] == 1.0
    assert explicit["contradiction_ack"] == 1.0
    assert semantic["semantic_continuity"] > 0.0


def test_score_confidence_signals_separates_assertive_and_uncertain_language():
    assertive = score_confidence_signals("You should do this. This is the best move.")
    uncertain = score_confidence_signals(
        "It depends. I am not sure. However, this is subjective."
    )
    assert assertive["lexical_assertiveness"] > uncertain["lexical_assertiveness"]
    assert uncertain["uncertainty_disclosure"] > assertive["uncertainty_disclosure"]


def test_classify_pair_prefers_temporal_update_when_markers_present():
    left = score_continuity_signals("Previously this made sense back then.")
    right = score_continuity_signals(
        "Now this is different because things changed recently and circumstances changed."
    )
    label = classify_pair(
        similarity=0.28,
        text_a="Previously this made sense back then.",
        text_b="Now this is different because things changed recently and circumstances changed.",
        continuity_a=left,
        continuity_b=right,
        time_a=0.0,
        time_b=86400.0 * 45,
    )
    assert label == "temporal_update"


def test_classify_pair_does_not_overfire_temporal_update_on_weak_markers():
    left = score_continuity_signals("Now focus on the next step.")
    right = score_continuity_signals("Currently the best move is to stay steady.")
    label = classify_pair(
        similarity=0.26,
        text_a="Now focus on the next step.",
        text_b="Currently the best move is to stay steady.",
        continuity_a=left,
        continuity_b=right,
        time_a=0.0,
        time_b=86400.0 * 60,
    )
    assert label == "genuine_contradiction"


def test_classify_pair_detects_scope_context_variation():
    left = score_continuity_signals("For most people, start small.")
    right = score_continuity_signals("If you already have savings, you can move faster.")
    label = classify_pair(
        similarity=0.48,
        text_a="For most people, start small.",
        text_b="If you already have savings, you can move faster.",
        continuity_a=left,
        continuity_b=right,
        time_a=10.0,
        time_b=20.0,
    )
    assert label == "scope_context_variation"


def test_query_similarity_gate_targets_middle_ground():
    assert 0.4 <= QUERY_SIMILARITY_GATE <= 0.55
