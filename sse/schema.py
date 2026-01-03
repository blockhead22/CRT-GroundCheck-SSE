try:
    from jsonschema import validate, ValidationError
    _HAS_JSONSCHEMA = True
except Exception:
    _HAS_JSONSCHEMA = False

INDEX_SCHEMA = {
    "type": "object",
    "required": ["doc_id", "timestamp", "chunks", "clusters", "claims", "contradictions"],
}


def validate_index_schema(index):
    if _HAS_JSONSCHEMA:
        try:
            validate(instance=index, schema=INDEX_SCHEMA)
        except ValidationError:
            raise
    else:
        # minimal fallback validation
        for k in ["doc_id", "timestamp", "chunks", "clusters", "claims", "contradictions"]:
            if k not in index:
                raise AssertionError(f"Missing required key: {k}")
    return True
