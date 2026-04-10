"""Verify the production structural_tension module against test pairs."""

import sys
import importlib.util
import types
from pathlib import Path

# Project root is D:\AI_round2
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
PA_DIR = PROJECT_ROOT / "personal_agent"

sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PA_DIR))

# Create a minimal personal_agent package stub so relative imports work
# without triggering the full __init__.py import chain
pa_pkg = types.ModuleType("personal_agent")
pa_pkg.__path__ = [str(PA_DIR)]
pa_pkg.__package__ = "personal_agent"
sys.modules["personal_agent"] = pa_pkg

# Load structural_tension directly
spec = importlib.util.spec_from_file_location(
    "personal_agent.structural_tension",
    str(PA_DIR / "structural_tension.py"),
    submodule_search_locations=[str(PA_DIR)]
)
mod = importlib.util.module_from_spec(spec)
sys.modules["personal_agent.structural_tension"] = mod
spec.loader.exec_module(mod)
StructuralTensionMeter = mod.StructuralTensionMeter


def p(msg):
    print(msg, flush=True)


TESTS = [
    {
        "id": "direct_contradiction",
        "text_a": "Nick lives in Milwaukee, Wisconsin",
        "text_b": "Nick lives in Chicago, Illinois",
        "trust_a": 0.9, "trust_b": 0.3,
        "source_a": "user_fact", "source_b": "user_correction",
        "expected": "CONFLICT",
    },
    {
        "id": "complementary",
        "text_a": "Nick is a developer",
        "text_b": "Nick works on AI systems",
        "trust_a": 0.85, "trust_b": 0.7,
        "source_a": "user_fact", "source_b": "inferred",
        "expected": "COMPATIBLE",
    },
    {
        "id": "stale_override",
        "text_a": "Nick's favorite language is Python",
        "text_b": "Nick's favorite language is Rust",
        "trust_a": 0.6, "trust_b": 0.8,
        "source_a": "user_fact", "source_b": "user_correction",
        "timestamp_a": 1000.0, "timestamp_b": 2000.0,
        "expected": "CONFLICT",
    },
    {
        "id": "unrelated",
        "text_a": "Nick lives in Milwaukee",
        "text_b": "Nick prefers dark mode in editors",
        "trust_a": 0.9, "trust_b": 0.7,
        "source_a": "user_fact", "source_b": "preference",
        "expected": "UNRELATED",
    },
    {
        "id": "confidence_decay",
        "text_a": "Nick said he enjoys hiking",
        "text_b": "Nick has not mentioned hiking in 8 months",
        "trust_a": 0.4, "trust_b": 0.5,
        "source_a": "user_fact", "source_b": "observation",
        "expected": "DECAYED",
    },
    {
        "id": "exact_duplicate",
        "text_a": "Nick is a freelance developer",
        "text_b": "Nick is a freelance developer",
        "trust_a": 0.85, "trust_b": 0.6,
        "source_a": "user_fact", "source_b": "user_fact",
        "expected": "DUPLICATE",
    },
    {
        "id": "refinement",
        "text_a": "Nick lives in Wisconsin",
        "text_b": "Nick lives in Milwaukee, Wisconsin",
        "trust_a": 0.7, "trust_b": 0.85,
        "source_a": "user_fact", "source_b": "user_fact",
        "expected": "REFINEMENT",
    },
    {
        "id": "temporal_sequence",
        "text_a": "Nick is learning Rust",
        "text_b": "Nick built a project in Rust",
        "trust_a": 0.6, "trust_b": 0.75,
        "source_a": "user_fact", "source_b": "user_fact",
        "timestamp_a": 1000.0, "timestamp_b": 2000.0,
        "expected": "COMPATIBLE",
    },
]


def main():
    p("=" * 60)
    p("VERIFY: Production StructuralTensionMeter")
    p("=" * 60)

    meter = StructuralTensionMeter()
    correct = 0
    total = len(TESTS)

    for test in TESTS:
        result = meter.measure(
            text_a=test["text_a"],
            text_b=test["text_b"],
            trust_a=test["trust_a"],
            trust_b=test["trust_b"],
            source_a=test["source_a"],
            source_b=test["source_b"],
            timestamp_a=test.get("timestamp_a", 0.0),
            timestamp_b=test.get("timestamp_b", 0.0),
        )

        match = result.relationship.value.upper() == test["expected"].upper()
        if match:
            correct += 1

        icon = "+" if match else "!"
        p(f"\n  [{icon}] {test['id']}")
        p(f"    A: {test['text_a'][:60]}")
        p(f"    B: {test['text_b'][:60]}")
        p(f"    Similarity: {result.supporting_signals.get('embedding_similarity', '?')}")
        p(f"    Slots A: {result.supporting_signals.get('slots_a_count', 0)}, B: {result.supporting_signals.get('slots_b_count', 0)}, Shared: {result.supporting_signals.get('shared_slots', 0)}")
        if result.slot_overlaps:
            for o in result.slot_overlaps:
                p(f"    Slot [{o.slot}]: '{o.value_a}' vs '{o.value_b}' → {o.match_type}")
        p(f"    Verdict: {result.relationship.value} (expected {test['expected']})")
        p(f"    Action: {result.action.value}")
        p(f"    Score: {result.tension_score:.2f}, Confidence: {result.confidence:.2f}")

    p(f"\n{'='*60}")
    p(f"RESULT: {correct}/{total} ({correct/total*100:.0f}%)")
    p(f"{'='*60}")


if __name__ == "__main__":
    main()
