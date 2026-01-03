import json
from sse.schema import validate_index_schema

def test_schema_validation_minimal(tmp_path):
    idx = {
        "doc_id": "d",
        "timestamp": "t",
        "chunks": [],
        "clusters": [],
        "claims": [],
        "contradictions": []
    }
    assert validate_index_schema(idx) is True
