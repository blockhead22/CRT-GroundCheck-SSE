from labs.meaning_compression_lab.scaffold_model_sweep import aggregate_sweep, run, summarize_model


def _fake_result(raw_passes, scaffold_passes, case_count=3):
    rows = []
    for idx in range(case_count):
        raw_passed = idx < raw_passes
        scaffold_passed = idx < scaffold_passes
        rows.append(
            {
                "scenario": f"case_{idx}",
                "probe": "probe",
                "raw_answer": "raw",
                "scaffold_answer": "scaffold",
                "raw_judgment": {"passed": raw_passed},
                "scaffold_judgment": {"passed": scaffold_passed},
                "crt_judgment": {"passed": True},
            }
        )
    return {
        "aggregate": {
            "case_count": case_count,
            "raw_pass_count": raw_passes,
            "scaffold_pass_count": scaffold_passes,
            "crt_pass_count": case_count,
            "raw_pass_rate": round(raw_passes / case_count, 3),
            "scaffold_pass_rate": round(scaffold_passes / case_count, 3),
            "avg_scaffold_compression_ratio": 0.5,
        },
        "scenarios": rows,
    }


def test_summarize_model_reports_delta_and_failures():
    row = summarize_model("fake-model", _fake_result(raw_passes=1, scaffold_passes=2))

    assert row["model"] == "fake-model"
    assert row["raw_pass_count"] == 1
    assert row["scaffold_pass_count"] == 2
    assert row["delta_pass_count"] == 1
    assert row["failure_count"] == 1
    assert [failure["scenario"] for failure in row["failures"]] == ["case_1", "case_2"]


def test_aggregate_sweep_counts_model_level_advantage():
    rows = [
        summarize_model("a", _fake_result(raw_passes=1, scaffold_passes=3)),
        summarize_model("b", _fake_result(raw_passes=2, scaffold_passes=2)),
    ]

    aggregate = aggregate_sweep(rows)

    assert aggregate["model_count"] == 2
    assert aggregate["models_with_scaffold_advantage"] == 1
    assert aggregate["models_with_perfect_scaffold"] == 1
    assert aggregate["avg_delta_pass_count"] == 1.0


def test_run_accepts_injected_runner_without_ollama():
    calls = []

    def fake_runner(**kwargs):
        calls.append(kwargs["model"])
        return _fake_result(raw_passes=1, scaffold_passes=3)

    out = run(models=["a", "b"], write_results=False, runner=fake_runner)

    assert calls == ["a", "b"]
    assert out["aggregate"]["models_with_scaffold_advantage"] == 2
    assert out["aggregate"]["models_with_perfect_scaffold"] == 2
    assert [row["model"] for row in out["model_results"]] == ["a", "b"]
