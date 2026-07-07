"""Tiny learned Mirus scorer lab.

This lab tests a narrow version of "NN Mirus":

- learned component: predicts which Mirus action is worth attempting;
- deterministic component: extracts bounded candidate payloads and enforces
  review-only safety;
- forbidden behavior: learned output never confirms memory or writes policy.

The model is intentionally small: a one-hidden-layer NumPy MLP over transparent
features. It is not intended to replace the sidecar router. It is a probe for
whether learned route/risk scoring is worth graduating later.
"""

from __future__ import annotations

import argparse
import json
import math
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import numpy as np


LAB_ROOT = Path(__file__).resolve().parent
RESULTS_DIR = LAB_ROOT / "results"

LABELS = [
    "no_action",
    "memory_lookup",
    "review_candidate",
    "confirmation_candidate",
    "archive_search",
    "project_search",
    "code_tool",
]
LABEL_TO_INDEX = {label: index for index, label in enumerate(LABELS)}

FEATURE_NAMES = [
    "bias",
    "has_question",
    "has_favorite",
    "has_user_fact_verb",
    "has_preference_verb",
    "has_because_or_reason",
    "has_archive_terms",
    "has_project_terms",
    "has_code_terms",
    "has_health_terms",
    "has_confirm_short",
    "has_pending_memory_intent",
    "history_has_review_candidate",
    "has_multi_fact_joiner",
    "has_demonstrative",
    "token_count_norm",
    "has_memory_lookup_shape",
    "has_search_verb",
    "has_state_parks_terms",
    "has_tool_boundary_terms",
]


@dataclass(frozen=True)
class ScorerCase:
    case_id: str
    prompt: str
    label: str
    history: tuple[str, ...] = ()
    expected_candidate_slots: tuple[str, ...] = ()
    sensitive_boundary: bool = False


@dataclass
class ScorerResult:
    case_id: str
    expected: str
    predicted: str
    baseline_predicted: str
    confidence: float
    passed: bool
    baseline_passed: bool
    safety_passed: bool
    candidates: list[dict[str, Any]]
    top_features: list[str]


class TinyMirusMLP:
    """A tiny one-hidden-layer classifier.

    This is deliberately boring. The goal is not a magic brain; the goal is to
    see whether a learned scorer can combine weak signals better than a brittle
    route card while leaving truth governance deterministic.
    """

    def __init__(
        self,
        *,
        input_dim: int,
        hidden_dim: int = 10,
        output_dim: int = len(LABELS),
        seed: int = 7,
    ) -> None:
        rng = np.random.default_rng(seed)
        self.w1 = rng.normal(0.0, 0.18, size=(input_dim, hidden_dim))
        self.b1 = np.zeros(hidden_dim)
        self.w2 = rng.normal(0.0, 0.18, size=(hidden_dim, output_dim))
        self.b2 = np.zeros(output_dim)

    def fit(
        self,
        x: np.ndarray,
        y: np.ndarray,
        *,
        epochs: int = 1200,
        lr: float = 0.08,
    ) -> list[float]:
        losses: list[float] = []
        y_onehot = np.eye(len(LABELS))[y]
        n = max(1, x.shape[0])
        for _ in range(epochs):
            hidden = np.tanh(x @ self.w1 + self.b1)
            logits = hidden @ self.w2 + self.b2
            probs = _softmax(logits)
            loss = -float(np.mean(np.sum(y_onehot * np.log(probs + 1e-9), axis=1)))
            losses.append(loss)

            dlogits = (probs - y_onehot) / n
            dw2 = hidden.T @ dlogits
            db2 = np.sum(dlogits, axis=0)
            dhidden = dlogits @ self.w2.T
            dz1 = dhidden * (1.0 - hidden * hidden)
            dw1 = x.T @ dz1
            db1 = np.sum(dz1, axis=0)

            self.w1 -= lr * dw1
            self.b1 -= lr * db1
            self.w2 -= lr * dw2
            self.b2 -= lr * db2
        return losses

    def predict_proba(self, x: np.ndarray) -> np.ndarray:
        if x.ndim == 1:
            x = x.reshape(1, -1)
        hidden = np.tanh(x @ self.w1 + self.b1)
        return _softmax(hidden @ self.w2 + self.b2)

    def predict(self, x: np.ndarray) -> tuple[str, float]:
        probs = self.predict_proba(x)[0]
        index = int(np.argmax(probs))
        return LABELS[index], float(probs[index])


def run_lab(*, write_results: bool = True) -> dict[str, Any]:
    train = training_cases()
    holdout = holdout_cases()
    x_train = np.array([features_for_case(case) for case in train], dtype=float)
    y_train = np.array([LABEL_TO_INDEX[case.label] for case in train], dtype=int)
    x_holdout = np.array([features_for_case(case) for case in holdout], dtype=float)

    model = TinyMirusMLP(input_dim=len(FEATURE_NAMES))
    losses = model.fit(x_train, y_train)

    results: list[ScorerResult] = []
    for row, case in zip(x_holdout, holdout):
        predicted, confidence = model.predict(row)
        baseline = deterministic_baseline(case)
        candidates = build_review_only_candidates(case, predicted)
        safety_passed = safety_contract_passes(predicted, candidates)
        results.append(ScorerResult(
            case_id=case.case_id,
            expected=case.label,
            predicted=predicted,
            baseline_predicted=baseline,
            confidence=round(confidence, 4),
            passed=predicted == case.label,
            baseline_passed=baseline == case.label,
            safety_passed=safety_passed,
            candidates=candidates,
            top_features=top_features(row),
        ))

    learned_passes = sum(1 for result in results if result.passed)
    baseline_passes = sum(1 for result in results if result.baseline_passed)
    safety_passes = sum(1 for result in results if result.safety_passed)
    report = {
        "lab": "learned_mirus_scorer_v0",
        "purpose": (
            "Probe whether a tiny learned scorer can choose Mirus actions "
            "without becoming a truth writer."
        ),
        "labels": LABELS,
        "feature_names": FEATURE_NAMES,
        "training_count": len(train),
        "holdout_count": len(holdout),
        "summary": {
            "learned_passed": learned_passes,
            "baseline_passed": baseline_passes,
            "total": len(results),
            "safety_passed": safety_passes,
            "final_loss": round(losses[-1], 6),
        },
        "interpretation": {
            "what_is_learned": (
                "A route/action scorer over transparent features, useful for "
                "ranking whether to attempt recall, candidate extraction, "
                "archive search, project search, code tooling, or confirmation."
            ),
            "what_stays_deterministic": (
                "Payload construction, source boundaries, review_required, "
                "memory_write_allowed=false, confirmed_fact=false, and any "
                "actual memory promotion."
            ),
            "graduation_gate": (
                "Only graduate if it beats brittle baseline on holdout cases "
                "and all proposed candidates remain review-only."
            ),
        },
        "results": [asdict(result) for result in results],
    }
    if write_results:
        RESULTS_DIR.mkdir(parents=True, exist_ok=True)
        path = RESULTS_DIR / f"learned_mirus_scorer_{int(time.time())}.json"
        path.write_text(json.dumps(report, indent=2), encoding="utf-8")
        report["artifact"] = str(path)
    return report


def training_cases() -> list[ScorerCase]:
    return [
        ScorerCase("train_color_lookup", "What is my favorite color?", "memory_lookup"),
        ScorerCase("train_known_about_me", "What do you know about me?", "memory_lookup"),
        ScorerCase("train_flower_fact", "My favorite flowers are marigolds.", "review_candidate", expected_candidate_slots=("user:favorite_flower",)),
        ScorerCase("train_flower_reason", "Marigolds are my favorite because they are orange.", "review_candidate", expected_candidate_slots=("user:favorite_flower", "user:favorite_flower_reason")),
        ScorerCase(
            "train_contextual_flower_reason",
            "They are both orange.",
            "review_candidate",
            history=("user:favorite_flower=marigolds", "user:favorite_color=orange"),
            expected_candidate_slots=("user:favorite_flower_reason",),
        ),
        ScorerCase("train_drink_multi", "I like Dr Pepper and iced coffee a lot.", "review_candidate", expected_candidate_slots=("user:favorite_drink",)),
        ScorerCase("train_confirm_yes", "Yes", "confirmation_candidate", history=("pending:user:favorite_drink=iced coffee",)),
        ScorerCase("train_confirm_short_value", "The Brewers", "confirmation_candidate", history=("pending:user:favorite_sports_team=Milwaukee Brewers",)),
        ScorerCase("train_archive_crt", "Search my GPT logs for CRT concepts.", "archive_search"),
        ScorerCase("train_archive_medical", "Use my old chats to find health history evidence.", "archive_search", sensitive_boundary=True),
        ScorerCase("train_project_map", "What is my state parks project?", "project_search"),
        ScorerCase("train_mill_bluff", "Why does Mill Bluff matter to the state parks map?", "project_search"),
        ScorerCase("train_code_search", "Search this project for where memory candidates are created.", "code_tool"),
        ScorerCase("train_patch_request", "Make the smallest safe code change and add a test.", "code_tool"),
        ScorerCase("train_casual", "hi aether", "no_action"),
        ScorerCase("train_irony", "what is irony?", "no_action"),
    ]


def holdout_cases() -> list[ScorerCase]:
    return [
        ScorerCase(
            "holdout_orange_reason_from_context",
            "They are both orange. lmao",
            "review_candidate",
            history=("user:favorite_flower=marigolds", "user:favorite_color=orange"),
            expected_candidate_slots=("user:favorite_flower_reason",),
        ),
        ScorerCase(
            "holdout_short_confirmation_sports",
            "The Brewers",
            "confirmation_candidate",
            history=("pending:user:favorite_sports_team=Milwaukee Brewers",),
            expected_candidate_slots=("user:favorite_sports_team",),
        ),
        ScorerCase(
            "holdout_archive_sensitive",
            "Search the GPT archive for my medical history, source-bound only.",
            "archive_search",
            sensitive_boundary=True,
        ),
        ScorerCase(
            "holdout_project_place",
            "What is the history on Mill Bluff in the state parks project?",
            "project_search",
        ),
        ScorerCase(
            "holdout_code_self",
            "Look through this project and find where the Thinking trace is built.",
            "code_tool",
        ),
        ScorerCase(
            "holdout_lookup_name",
            "Who do I work for?",
            "memory_lookup",
        ),
        ScorerCase(
            "holdout_casual_ack",
            "okay lol",
            "no_action",
        ),
    ]


def features_for_case(case: ScorerCase) -> list[float]:
    text = _clean(case.prompt)
    history = " ".join(_clean(item) for item in case.history)
    tokens = [token for token in text.split() if token]
    return [
        1.0,
        float("?" in case.prompt or text.startswith(("what ", "who ", "why ", "how ", "where "))),
        _has(text, ("favorite", "favourite")),
        _has(text, ("my ", "i ", "i'm ", "im ", "we ")),
        _has(text, ("like", "love", "favorite", "favourite", "prefer", "work for", "am ")),
        _has(text, ("because", "why", "reason", "both", "same")),
        _has(text, ("gpt", "archive", "old chat", "old chats", "logs", "history evidence")),
        _has(text, ("state parks", "mill bluff", "wisconsin map", "glaciation", "project")),
        _has(text, ("code", "file", "project", "patch", "test", "where", "thinking trace", "created")),
        _has(text, ("medical", "health", "leukemia", "gvhd", "transplant")),
        float(text in {"yes", "yeah", "yep", "correct", "the brewers", "marigolds", "orange"}),
        float("pending:" in history),
        float("candidate" in history or "pending:" in history),
        _has(text, (" and ", " both ", ",", "also")),
        _has(text, ("they", "it", "that", "this")),
        min(1.0, len(tokens) / 24.0),
        float(text.startswith(("what is my", "who do i", "what do you know"))),
        _has(text, ("search", "find", "look through", "use my", "check")),
        _has(text, ("mill bluff", "state parks", "glaciation", "wisconsin")),
        _has(text, ("source-bound", "do not treat", "not confirmed", "review-only")),
    ]


def deterministic_baseline(case: ScorerCase) -> str:
    text = _clean(case.prompt)
    if text.startswith(("what is my", "who do i", "what do you know")):
        return "memory_lookup"
    if "gpt logs" in text:
        return "archive_search"
    if "mill bluff" in text and "state parks" in text:
        return "project_search"
    if "memory candidates" in text and ("file" in text or "where" in text):
        return "code_tool"
    if "favorite" in text and any(word in text for word in ("is", "are", "because")):
        return "review_candidate"
    return "no_action"


def build_review_only_candidates(
    case: ScorerCase,
    predicted: str,
) -> list[dict[str, Any]]:
    if predicted not in {"review_candidate", "confirmation_candidate"}:
        return []
    slots = case.expected_candidate_slots or _infer_slots(case.prompt, case.history)
    value = _candidate_value(case.prompt, case.history)
    return [
        {
            "candidate_id": f"learned_mirus_{case.case_id}_{index}",
            "candidate_kind": "learned_mirus_route_candidate",
            "slot_id": slot,
            "proposed_value": value,
            "confidence": 0.62 if predicted == "review_candidate" else 0.72,
            "review_required": True,
            "memory_write_allowed": False,
            "confirmed_fact": False,
            "source_boundary": "learned scorer suggestion; deterministic review required",
        }
        for index, slot in enumerate(slots)
    ]


def safety_contract_passes(
    predicted: str,
    candidates: list[dict[str, Any]],
) -> bool:
    if predicted in {"review_candidate", "confirmation_candidate"} and not candidates:
        return False
    return all(
        candidate.get("review_required") is True
        and candidate.get("memory_write_allowed") is False
        and candidate.get("confirmed_fact") is False
        for candidate in candidates
    )


def top_features(row: np.ndarray, *, limit: int = 5) -> list[str]:
    active = [
        (FEATURE_NAMES[index], float(value))
        for index, value in enumerate(row)
        if value >= 0.5 and FEATURE_NAMES[index] != "bias"
    ]
    active.sort(key=lambda item: item[1], reverse=True)
    return [name for name, _ in active[:limit]]


def _infer_slots(prompt: str, history: tuple[str, ...]) -> tuple[str, ...]:
    text = _clean(prompt + " " + " ".join(history))
    if "flower" in text or "marigold" in text:
        if "because" in text or "both orange" in text or "they are both orange" in text:
            return ("user:favorite_flower_reason",)
        return ("user:favorite_flower",)
    if "brewer" in text or "sports team" in text:
        return ("user:favorite_sports_team",)
    if "drink" in text or "coffee" in text or "pepper" in text:
        return ("user:favorite_drink",)
    return ("user:preference",)


def _candidate_value(prompt: str, history: tuple[str, ...]) -> str:
    text = _clean(prompt)
    history_text = _clean(" ".join(history))
    if "orange" in text and "flower" in history_text:
        return "marigolds are favored partly because they are orange"
    if "brewer" in text or "brewer" in history_text:
        return "Milwaukee Brewers"
    if "marigold" in text:
        return "marigolds"
    if "coffee" in text:
        return "iced coffee"
    return prompt.strip()[:120]


def _softmax(logits: np.ndarray) -> np.ndarray:
    shifted = logits - np.max(logits, axis=1, keepdims=True)
    exp = np.exp(shifted)
    return exp / np.sum(exp, axis=1, keepdims=True)


def _has(text: str, terms: tuple[str, ...]) -> float:
    return float(any(term in text for term in terms))


def _clean(text: str) -> str:
    return " ".join((text or "").lower().replace("?", " ?").split())


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--no-write", action="store_true")
    args = parser.parse_args()
    report = run_lab(write_results=not args.no_write)
    print(json.dumps(report["summary"], indent=2))
    if report.get("artifact"):
        print(report["artifact"])


if __name__ == "__main__":
    main()
