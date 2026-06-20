import json
from pathlib import Path

from labs.meaning_compression_lab.scaffold_failure_analysis import analyze_sweep


def test_completed_sweep_failures_are_fully_categorized():
    path = Path("labs/meaning_compression_lab/results/scaffold_model_sweep_1781846924.json")
    report = analyze_sweep(json.loads(path.read_text(encoding="utf-8")))

    assert report["failure_count"] == 20
    assert report["category_counts"] == {
        "executor_content_loss": 2,
        "executor_scope_leak": 8,
        "judge_contract_strictness": 7,
        "state_construction_error": 3,
    }
