"""XGBoost-based classifiers for belief type and policy action."""

from __future__ import annotations

import pickle
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np
from sklearn.preprocessing import LabelEncoder
from xgboost import XGBClassifier

from .features import FEATURE_NAMES, extract_features
from .types import BeliefType, ContradictionPair, PolicyAction


def _pairs_to_matrix(
    pairs: List[ContradictionPair],
) -> np.ndarray:
    """Convert a list of pairs into a (N, F) feature matrix."""
    rows = []
    for pair in pairs:
        feats = extract_features(pair)
        rows.append([feats[name] for name in FEATURE_NAMES])
    return np.array(rows, dtype=np.float32)


# ── Belief Classifier ───────────────────────────────────────────────────────


class BeliefClassifier:
    """XGBoost classifier that maps a ContradictionPair -> BeliefType."""

    def __init__(self, model_path: Optional[str] = None) -> None:
        self._label_encoder = LabelEncoder()
        self._label_encoder.fit([bt.value for bt in BeliefType])
        self._model: Optional[XGBClassifier] = None

        if model_path and Path(model_path).exists():
            self.load(model_path)

    @property
    def is_trained(self) -> bool:
        return self._model is not None

    def train(
        self,
        pairs: List[ContradictionPair],
        labels: List[BeliefType],
    ) -> Dict[str, float]:
        """Train the XGBoost belief classifier.

        Returns a dict of training metrics (accuracy, etc.).
        """
        X = _pairs_to_matrix(pairs)
        y = self._label_encoder.transform([lb.value for lb in labels])

        self._model = XGBClassifier(
            n_estimators=100,
            max_depth=4,
            learning_rate=0.1,
            use_label_encoder=False,
            eval_metric="mlogloss",
            random_state=42,
        )
        self._model.fit(X, y)

        train_acc = float(np.mean(self._model.predict(X) == y))
        return {"train_accuracy": train_acc}

    def predict(
        self, pair: ContradictionPair
    ) -> Tuple[BeliefType, float]:
        """Predict the BeliefType and confidence for a single pair."""
        if self._model is None:
            raise RuntimeError("Model not trained — call train() or load() first.")

        X = _pairs_to_matrix([pair])
        proba = self._model.predict_proba(X)[0]
        idx = int(np.argmax(proba))
        label_str = self._label_encoder.inverse_transform([idx])[0]
        confidence = float(proba[idx])
        return BeliefType(label_str), confidence

    def predict_batch(
        self, pairs: List[ContradictionPair]
    ) -> List[Tuple[BeliefType, float]]:
        """Predict for multiple pairs at once."""
        if self._model is None:
            raise RuntimeError("Model not trained — call train() or load() first.")

        X = _pairs_to_matrix(pairs)
        proba = self._model.predict_proba(X)
        results = []
        for row in proba:
            idx = int(np.argmax(row))
            label_str = self._label_encoder.inverse_transform([idx])[0]
            results.append((BeliefType(label_str), float(row[idx])))
        return results

    def save(self, path: str) -> None:
        """Persist model + label encoder to a pickle file."""
        with open(path, "wb") as f:
            pickle.dump({"model": self._model, "le": self._label_encoder}, f)

    def load(self, path: str) -> None:
        """Load model + label encoder from a pickle file."""
        with open(path, "rb") as f:
            data = pickle.load(f)
        self._model = data["model"]
        self._label_encoder = data["le"]


# ── Policy Classifier ───────────────────────────────────────────────────────


class PolicyClassifier:
    """XGBoost classifier that maps (ContradictionPair, BeliefType) -> PolicyAction."""

    def __init__(self, model_path: Optional[str] = None) -> None:
        self._label_encoder = LabelEncoder()
        self._label_encoder.fit([pa.value for pa in PolicyAction])
        self._belief_encoder = LabelEncoder()
        self._belief_encoder.fit([bt.value for bt in BeliefType])
        self._model: Optional[XGBClassifier] = None

        if model_path and Path(model_path).exists():
            self.load(model_path)

    @property
    def is_trained(self) -> bool:
        return self._model is not None

    def _augment_features(
        self,
        pairs: List[ContradictionPair],
        belief_labels: List[BeliefType],
    ) -> np.ndarray:
        """Build feature matrix with the belief label appended as an extra feature."""
        base = _pairs_to_matrix(pairs)
        belief_col = self._belief_encoder.transform(
            [bl.value for bl in belief_labels]
        ).reshape(-1, 1).astype(np.float32)
        return np.hstack([base, belief_col])

    def train(
        self,
        pairs: List[ContradictionPair],
        belief_labels: List[BeliefType],
        policy_labels: List[PolicyAction],
    ) -> Dict[str, float]:
        """Train the XGBoost policy classifier."""
        X = self._augment_features(pairs, belief_labels)
        y = self._label_encoder.transform([pl.value for pl in policy_labels])

        self._model = XGBClassifier(
            n_estimators=100,
            max_depth=4,
            learning_rate=0.1,
            use_label_encoder=False,
            eval_metric="mlogloss",
            random_state=42,
        )
        self._model.fit(X, y)

        train_acc = float(np.mean(self._model.predict(X) == y))
        return {"train_accuracy": train_acc}

    def predict(
        self, pair: ContradictionPair, belief: BeliefType
    ) -> Tuple[PolicyAction, float]:
        """Predict the PolicyAction and confidence for a single pair."""
        if self._model is None:
            raise RuntimeError("Model not trained — call train() or load() first.")

        X = self._augment_features([pair], [belief])
        proba = self._model.predict_proba(X)[0]
        idx = int(np.argmax(proba))
        label_str = self._label_encoder.inverse_transform([idx])[0]
        return PolicyAction(label_str), float(proba[idx])

    def predict_batch(
        self,
        pairs: List[ContradictionPair],
        beliefs: List[BeliefType],
    ) -> List[Tuple[PolicyAction, float]]:
        """Predict for multiple pairs at once."""
        if self._model is None:
            raise RuntimeError("Model not trained — call train() or load() first.")

        X = self._augment_features(pairs, beliefs)
        proba = self._model.predict_proba(X)
        results = []
        for row in proba:
            idx = int(np.argmax(row))
            label_str = self._label_encoder.inverse_transform([idx])[0]
            results.append((PolicyAction(label_str), float(row[idx])))
        return results

    def save(self, path: str) -> None:
        with open(path, "wb") as f:
            pickle.dump(
                {
                    "model": self._model,
                    "le": self._label_encoder,
                    "be": self._belief_encoder,
                },
                f,
            )

    def load(self, path: str) -> None:
        with open(path, "rb") as f:
            data = pickle.load(f)
        self._model = data["model"]
        self._label_encoder = data["le"]
        self._belief_encoder = data["be"]


# ── Convenience Resolver ─────────────────────────────────────────────────────


class ContradictionResolver:
    """Convenience wrapper combining both classifiers into a single pipeline."""

    def __init__(
        self,
        belief_model_path: Optional[str] = None,
        policy_model_path: Optional[str] = None,
    ) -> None:
        self.belief = BeliefClassifier(belief_model_path)
        self.policy = PolicyClassifier(policy_model_path)

    @property
    def is_trained(self) -> bool:
        return self.belief.is_trained and self.policy.is_trained

    def resolve(
        self, pair: ContradictionPair
    ) -> Tuple[BeliefType, PolicyAction, float, float]:
        """Full pipeline: classify belief, then determine policy.

        Returns (belief_type, policy_action, belief_confidence, policy_confidence).
        """
        belief, b_conf = self.belief.predict(pair)
        policy, p_conf = self.policy.predict(pair, belief)
        return belief, policy, b_conf, p_conf

    def resolve_batch(
        self, pairs: List[ContradictionPair]
    ) -> List[Tuple[BeliefType, PolicyAction, float, float]]:
        """Resolve multiple pairs."""
        belief_results = self.belief.predict_batch(pairs)
        beliefs = [b for b, _ in belief_results]
        policy_results = self.policy.predict_batch(pairs, beliefs)

        return [
            (b, p, bc, pc)
            for (b, bc), (p, pc) in zip(belief_results, policy_results)
        ]
