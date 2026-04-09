"""Tests for the belief classifier package."""

from __future__ import annotations

import os
import tempfile
import time

import pytest

from belief_classifier.classifier import (
    BeliefClassifier,
    ContradictionResolver,
    PolicyClassifier,
)
from belief_classifier.exporter import LedgerExporter
from belief_classifier.features import FEATURE_NAMES, extract_features
from belief_classifier.labeler import AutoLabeler
from belief_classifier.types import BeliefType, ContradictionPair, PolicyAction


# ── Fixtures ─────────────────────────────────────────────────────────────────

def _make_pair(
    old_text: str = "I like blue",
    new_text: str = "I like dark blue",
    old_trust: float = 0.8,
    new_trust: float = 0.85,
    time_gap_hours: float = 1.0,
    slot_name: str | None = None,
    is_exclusive: bool = False,
    similarity: float = 0.9,
) -> ContradictionPair:
    now = time.time()
    return ContradictionPair(
        old_text=old_text,
        new_text=new_text,
        old_trust=old_trust,
        new_trust=new_trust,
        old_timestamp=now - time_gap_hours * 3600,
        new_timestamp=now,
        slot_name=slot_name,
        is_exclusive_slot=is_exclusive,
        similarity_score=similarity,
        thread_id="test-thread",
    )


# ── Test feature extraction ─────────────────────────────────────────────────

class TestFeatureExtraction:
    def test_feature_count(self):
        pair = _make_pair()
        feats = extract_features(pair)
        assert len(feats) == len(FEATURE_NAMES)

    def test_feature_keys_match(self):
        pair = _make_pair()
        feats = extract_features(pair)
        assert set(feats.keys()) == set(FEATURE_NAMES)

    def test_all_values_are_float(self):
        pair = _make_pair()
        feats = extract_features(pair)
        for k, v in feats.items():
            assert isinstance(v, float), f"{k} is {type(v)}, expected float"

    def test_correction_language_detected(self):
        pair = _make_pair(new_text="Actually I prefer red")
        feats = extract_features(pair)
        assert feats["has_correction_language"] == 1.0

    def test_temporal_language_detected(self):
        pair = _make_pair(new_text="I used to live there but moved")
        feats = extract_features(pair)
        assert feats["has_temporal_language"] == 1.0

    def test_negation_detected(self):
        pair = _make_pair(new_text="I never liked that")
        feats = extract_features(pair)
        assert feats["has_negation"] == 1.0

    def test_fact_format_detected(self):
        pair = _make_pair(old_text="FACT: employer = Google")
        feats = extract_features(pair)
        assert feats["is_fact_format"] == 1.0

    def test_exclusive_slot(self):
        pair = _make_pair(slot_name="color", is_exclusive=True)
        feats = extract_features(pair)
        assert feats["is_exclusive"] == 1.0
        assert feats["has_slot"] == 1.0


# ── Test auto-labeler ────────────────────────────────────────────────────────

class TestAutoLabeler:
    def setup_method(self):
        self.labeler = AutoLabeler()

    def test_refinement(self):
        pair = _make_pair(
            old_text="I like blue",
            new_text="I like dark blue",
            similarity=0.92,
        )
        belief, conf = self.labeler.label_belief(pair)
        assert belief == BeliefType.REFINEMENT
        assert conf > 0.5

    def test_revision(self):
        pair = _make_pair(
            old_text="I work at Google",
            new_text="Actually I work at Microsoft",
            slot_name="employer",
            is_exclusive=True,
            similarity=0.4,
        )
        belief, conf = self.labeler.label_belief(pair)
        assert belief == BeliefType.REVISION
        assert conf > 0.5

    def test_temporal(self):
        pair = _make_pair(
            old_text="I live in Seattle",
            new_text="I moved to Denver last month",
            time_gap_hours=48,
            similarity=0.35,
        )
        belief, conf = self.labeler.label_belief(pair)
        assert belief == BeliefType.TEMPORAL
        assert conf > 0.5

    def test_conflict(self):
        pair = _make_pair(
            old_text="I don't have siblings",
            new_text="I never said I don't have siblings",
            new_trust=0.85,
            similarity=0.3,
        )
        belief, conf = self.labeler.label_belief(pair)
        assert belief == BeliefType.CONFLICT
        assert conf > 0.5

    def test_policy_refinement_preserves(self):
        pair = _make_pair(similarity=0.92)
        policy, _ = self.labeler.label_policy(pair, BeliefType.REFINEMENT)
        assert policy == PolicyAction.PRESERVE

    def test_policy_conflict_high_trust_asks(self):
        pair = _make_pair(old_trust=0.9, new_trust=0.9)
        policy, _ = self.labeler.label_policy(pair, BeliefType.CONFLICT)
        assert policy == PolicyAction.ASK_USER


# ── Test synthetic data ──────────────────────────────────────────────────────

class TestSyntheticData:
    def test_covers_all_belief_types(self):
        exporter = LedgerExporter([])
        data = exporter.generate_synthetic_pairs(200)
        belief_types = {d[1] for d in data}
        for bt in BeliefType:
            assert bt in belief_types, f"Missing belief type: {bt}"

    def test_covers_all_policy_actions(self):
        exporter = LedgerExporter([])
        data = exporter.generate_synthetic_pairs(200)
        policy_actions = {d[2] for d in data}
        for pa in PolicyAction:
            assert pa in policy_actions, f"Missing policy action: {pa}"

    def test_requested_count(self):
        exporter = LedgerExporter([])
        data = exporter.generate_synthetic_pairs(100)
        assert len(data) == 100

    def test_pairs_are_valid(self):
        exporter = LedgerExporter([])
        data = exporter.generate_synthetic_pairs(50)
        for pair, belief, policy in data:
            assert isinstance(pair, ContradictionPair)
            assert isinstance(belief, BeliefType)
            assert isinstance(policy, PolicyAction)
            assert pair.new_timestamp > pair.old_timestamp
            assert 0.0 <= pair.old_trust <= 1.0
            assert 0.0 <= pair.new_trust <= 1.0


# ── Test train/predict round-trip ────────────────────────────────────────────

class TestTrainPredict:
    @pytest.fixture(autouse=True)
    def _setup_data(self):
        exporter = LedgerExporter([])
        self.data = exporter.generate_synthetic_pairs(200)
        self.pairs = [d[0] for d in self.data]
        self.beliefs = [d[1] for d in self.data]
        self.policies = [d[2] for d in self.data]

    def test_belief_classifier_round_trip(self):
        clf = BeliefClassifier()
        assert not clf.is_trained
        metrics = clf.train(self.pairs, self.beliefs)
        assert clf.is_trained
        assert metrics["train_accuracy"] > 0.5

        belief, conf = clf.predict(self.pairs[0])
        assert isinstance(belief, BeliefType)
        assert 0.0 <= conf <= 1.0

    def test_policy_classifier_round_trip(self):
        clf = PolicyClassifier()
        assert not clf.is_trained
        metrics = clf.train(self.pairs, self.beliefs, self.policies)
        assert clf.is_trained
        assert metrics["train_accuracy"] > 0.5

        policy, conf = clf.predict(self.pairs[0], self.beliefs[0])
        assert isinstance(policy, PolicyAction)
        assert 0.0 <= conf <= 1.0

    def test_batch_predict(self):
        clf = BeliefClassifier()
        clf.train(self.pairs, self.beliefs)
        results = clf.predict_batch(self.pairs[:10])
        assert len(results) == 10
        for belief, conf in results:
            assert isinstance(belief, BeliefType)


# ── Test ContradictionResolver end-to-end ────────────────────────────────────

class TestContradictionResolver:
    @pytest.fixture(autouse=True)
    def _setup(self):
        exporter = LedgerExporter([])
        data = exporter.generate_synthetic_pairs(200)
        self.pairs = [d[0] for d in data]
        self.beliefs = [d[1] for d in data]
        self.policies = [d[2] for d in data]

    def test_end_to_end(self):
        resolver = ContradictionResolver()
        resolver.belief.train(self.pairs, self.beliefs)
        resolver.policy.train(self.pairs, self.beliefs, self.policies)
        assert resolver.is_trained

        belief, policy, b_conf, p_conf = resolver.resolve(self.pairs[0])
        assert isinstance(belief, BeliefType)
        assert isinstance(policy, PolicyAction)
        assert 0.0 <= b_conf <= 1.0
        assert 0.0 <= p_conf <= 1.0

    def test_batch_resolve(self):
        resolver = ContradictionResolver()
        resolver.belief.train(self.pairs, self.beliefs)
        resolver.policy.train(self.pairs, self.beliefs, self.policies)

        results = resolver.resolve_batch(self.pairs[:5])
        assert len(results) == 5


# ── Test save/load cycle ─────────────────────────────────────────────────────

class TestSaveLoad:
    def test_belief_save_load(self):
        exporter = LedgerExporter([])
        data = exporter.generate_synthetic_pairs(100)
        pairs = [d[0] for d in data]
        beliefs = [d[1] for d in data]

        clf = BeliefClassifier()
        clf.train(pairs, beliefs)

        with tempfile.NamedTemporaryFile(suffix=".pkl", delete=False) as f:
            path = f.name

        try:
            clf.save(path)
            loaded = BeliefClassifier(path)
            assert loaded.is_trained

            # Predictions should match
            orig = clf.predict(pairs[0])
            after = loaded.predict(pairs[0])
            assert orig[0] == after[0]
            assert abs(orig[1] - after[1]) < 1e-6
        finally:
            os.unlink(path)

    def test_policy_save_load(self):
        exporter = LedgerExporter([])
        data = exporter.generate_synthetic_pairs(100)
        pairs = [d[0] for d in data]
        beliefs = [d[1] for d in data]
        policies = [d[2] for d in data]

        clf = PolicyClassifier()
        clf.train(pairs, beliefs, policies)

        with tempfile.NamedTemporaryFile(suffix=".pkl", delete=False) as f:
            path = f.name

        try:
            clf.save(path)
            loaded = PolicyClassifier(path)
            assert loaded.is_trained

            orig = clf.predict(pairs[0], beliefs[0])
            after = loaded.predict(pairs[0], beliefs[0])
            assert orig[0] == after[0]
            assert abs(orig[1] - after[1]) < 1e-6
        finally:
            os.unlink(path)

    def test_resolver_with_saved_models(self):
        exporter = LedgerExporter([])
        data = exporter.generate_synthetic_pairs(100)
        pairs = [d[0] for d in data]
        beliefs = [d[1] for d in data]
        policies = [d[2] for d in data]

        with tempfile.TemporaryDirectory() as tmpdir:
            belief_path = os.path.join(tmpdir, "belief.pkl")
            policy_path = os.path.join(tmpdir, "policy.pkl")

            # Train and save
            b_clf = BeliefClassifier()
            b_clf.train(pairs, beliefs)
            b_clf.save(belief_path)

            p_clf = PolicyClassifier()
            p_clf.train(pairs, beliefs, policies)
            p_clf.save(policy_path)

            # Load into resolver
            resolver = ContradictionResolver(belief_path, policy_path)
            assert resolver.is_trained

            belief, policy, b_conf, p_conf = resolver.resolve(pairs[0])
            assert isinstance(belief, BeliefType)
            assert isinstance(policy, PolicyAction)
