from labs.meaning_compression_lab.compare_temporal_hybrid import compare


def test_compare_preserves_model_specific_reversal():
    hybrid = {
        "model_results": [
            {"model": "a", "case_count": 2},
            {"model": "b", "case_count": 2},
        ],
        "raw_results": {
            "a": {
                "scenarios": [
                    {
                        "scenario": "identity_flip",
                        "scaffold_judgment": {
                            "semantic_passed": True,
                            "contract_passed": True,
                            "meaning_passed": True,
                            "scope_passed": True,
                            "format_passed": True,
                        },
                    },
                    {
                        "scenario": "employer_correction",
                        "scaffold_judgment": {
                            "semantic_passed": True,
                            "contract_passed": True,
                            "meaning_passed": True,
                            "scope_passed": True,
                            "format_passed": True,
                        },
                    },
                ]
            },
            "b": {
                "scenarios": [
                    {
                        "scenario": "identity_flip",
                        "scaffold_judgment": {
                            "semantic_passed": True,
                            "contract_passed": True,
                            "meaning_passed": True,
                            "scope_passed": True,
                            "format_passed": True,
                        },
                    },
                    {
                        "scenario": "employer_correction",
                        "scaffold_judgment": {
                            "semantic_passed": False,
                            "contract_passed": False,
                            "meaning_passed": False,
                            "scope_passed": True,
                            "format_passed": True,
                        },
                    },
                ]
            },
        },
    }
    temporal = [
        {
            "model": "a",
            "aggregate": {
                "semantic_pass_count": 1,
                "contract_pass_count": 1,
                "severe_failure_count": 0,
            },
        },
        {
            "model": "b",
            "aggregate": {
                "semantic_pass_count": 2,
                "contract_pass_count": 2,
                "severe_failure_count": 0,
            },
        },
    ]

    report = compare(hybrid, temporal)

    assert report["models"][0]["semantic_delta_count"] == 1
    assert report["models"][1]["semantic_delta_count"] == -1
    assert report["aggregate"]["models_where_hybrid_wins"] == 1
    assert report["aggregate"]["models_where_temporal_wins"] == 1
