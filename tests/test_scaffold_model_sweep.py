from io import StringIO

from labs.meaning_compression_lab.scaffold_model_sweep import (
    LiveSweepReporter,
    aggregate_sweep,
    run,
    summarize_model,
)


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
        calls.append((kwargs["model"], len(kwargs["scenarios"])))
        return _fake_result(raw_passes=1, scaffold_passes=3)

    out = run(
        models=["a", "b"],
        include_hardening=True,
        write_results=False,
        runner=fake_runner,
    )

    assert calls == [("a", 19), ("b", 19)]
    assert out["include_hardening"] is True
    assert out["scenario_count"] == 19
    assert out["aggregate"]["models_with_scaffold_advantage"] == 2
    assert out["aggregate"]["models_with_perfect_scaffold"] == 2
    assert [row["model"] for row in out["model_results"]] == ["a", "b"]


def test_live_reporter_explains_case_and_running_score():
    stream = StringIO()
    reporter = LiveSweepReporter(stream=stream)
    reporter.start_sweep(models=["fake-model"], scenario_count=1)
    reporter.start_model("fake-model", 1)
    reporter(
        {
            "type": "case_started",
            "case_index": 1,
            "case_count": 1,
            "scenario": "identity_flip",
            "purpose": "Keep the corrected name current.",
            "query": "What's my name?",
            "scaffold": "CURRENT name = Emily\nPROVISIONAL name = Sarah",
        }
    )
    reporter(
        {
            "type": "answer_completed",
            "arm": "raw",
            "answer": "Sarah",
            "judgment": {
                "passed": False,
                "contains_ok": False,
                "excludes_ok": False,
                "expected_contains": ["emily"],
                "expected_excludes": ["sarah"],
            },
        }
    )
    row = _fake_result(raw_passes=0, scaffold_passes=1, case_count=1)["scenarios"][0]
    reporter(
        {
            "type": "answer_completed",
            "arm": "scaffold",
            "answer": "Emily",
            "judgment": row["scaffold_judgment"],
        }
    )
    reporter({"type": "case_completed", "row": row})

    text = stream.getvalue()
    assert "MODEL 1/1: fake-model" in text
    assert "Governed state:" in text
    assert "RAW VERDICT: FAIL — missing emily; leaked sarah" in text
    assert "SCAFFOLD VERDICT: PASS" in text
    assert "RUNNING SCORE: RAW 0/1  |  SCAFFOLD 1/1" in text


def test_run_forwards_live_events_to_runner():
    stream = StringIO()
    reporter = LiveSweepReporter(stream=stream, show_scaffold=False)

    def fake_runner(**kwargs):
        callback = kwargs["event_callback"]
        callback(
            {
                "type": "case_started",
                "case_index": 1,
                "case_count": 1,
                "scenario": "case_0",
                "purpose": "test",
                "query": "question",
                "scaffold": "CURRENT x = y",
            }
        )
        return _fake_result(raw_passes=1, scaffold_passes=1, case_count=1)

    run(
        models=["fake-model"],
        include_adversarial=False,
        write_results=False,
        runner=fake_runner,
        live_reporter=reporter,
    )

    assert "MODEL COMPLETE: fake-model" in stream.getvalue()
