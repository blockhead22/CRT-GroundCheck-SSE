from labs.meaning_compression_lab.slot_inference_ablation import run


def test_slot_inference_ablation_never_confidently_fetches_wrong_slot():
    out = run(write_results=False)

    assert out["aggregate"]["resolved_correct"] >= 5
    assert out["aggregate"]["confidently_wrong"] == 0
    assert out["aggregate"]["contract_correct"] == out["aggregate"]["case_count"]
