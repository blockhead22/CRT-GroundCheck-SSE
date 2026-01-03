from sse.render import render_index
import json


def test_render_natural():
    index = {
        "doc_id": "test.txt",
        "timestamp": "2025-01-01T00:00:00Z",
        "chunks": [{"chunk_id": "c0", "text": "Test chunk"}],
        "clusters": [{"cluster_id": "cl0", "chunk_ids": ["c0"]}],
        "claims": [
            {
                "claim_id": "clm0",
                "claim_text": "The sky is blue.",
                "supporting_quotes": [{"quote_text": "The sky is blue.", "chunk_id": "c0", "start_char": 0, "end_char": 16}],
                "ambiguity": {"hedge_score": 0, "open_questions": []}
            }
        ],
        "contradictions": []
    }
    output = render_index(index, style="natural")
    assert "The sky is blue" in output
    assert "DOCUMENT SUMMARY" in output


def test_render_conflict_style():
    index = {
        "doc_id": "test.txt",
        "timestamp": "2025-01-01T00:00:00Z",
        "chunks": [{"chunk_id": "c0", "text": "Test"}],
        "clusters": [{"cluster_id": "cl0", "chunk_ids": ["c0"]}],
        "claims": [
            {
                "claim_id": "clm0",
                "claim_text": "A is true.",
                "supporting_quotes": [{"quote_text": "A is true.", "chunk_id": "c0"}],
                "ambiguity": {"hedge_score": 0, "open_questions": []}
            },
            {
                "claim_id": "clm1",
                "claim_text": "A is not true.",
                "supporting_quotes": [{"quote_text": "A is not true.", "chunk_id": "c0"}],
                "ambiguity": {"hedge_score": 0, "open_questions": []}
            }
        ],
        "contradictions": [
            {
                "pair": {"claim_id_a": "clm0", "claim_id_b": "clm1"},
                "label": "contradiction",
                "evidence_quotes": []
            }
        ]
    }
    output = render_index(index, style="conflict")
    assert "CONTRADICTION" in output
    assert "A is true" in output
