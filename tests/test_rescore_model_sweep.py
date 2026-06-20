import json
from pathlib import Path

from labs.meaning_compression_lab.rescore_model_sweep import rescore_sweep


def test_latest_sweep_can_be_rescored_without_model_calls():
    source = Path(
        "labs/meaning_compression_lab/results/"
        "scaffold_model_sweep_1781849324.json"
    )
    rescored = rescore_sweep(json.loads(source.read_text(encoding="utf-8")))

    assert rescored["rescored"] is True
    assert rescored["aggregate"]["total_case_count"] == 76
    assert rescored["aggregate"]["scaffold_semantic_pass_count"] >= 55
    assert rescored["aggregate"]["scaffold_contract_pass_count"] <= rescored["aggregate"]["scaffold_semantic_pass_count"]
