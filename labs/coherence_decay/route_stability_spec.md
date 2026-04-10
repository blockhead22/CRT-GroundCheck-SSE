# Route Stability Classifier — Spec

## What It Does

Takes a sequence of generation spans (from the coherence decay experiment) and classifies the reasoning "route" as one of three states:

- **stable**: Low entropy, no contradictions, consistent output. This route is reliable.
- **volatile**: High entropy, contradictions detected, or entropy trend increasing. This route is unreliable — freeze it.
- **exploratory**: Untested or insufficient data. Allow with monitoring.

## Input Format

A list of span dicts, each with:
```python
{
    "span_index": 0,
    "text": "generated text...",
    "token_count": 50,
    "entropy_mean": 0.45,
    "entropy_max": 1.2,
    "entropy_per_token": [0.3, 0.5, ...],  # may be empty
    "was_rerun": False,
    "rerun_reason": None
}
```

Plus metadata:
```python
{
    "model_tier": "local_small",
    "strategy": "L2_burst_50",
    "domain": "memory",
    "prompt_id": "mem_01"
}
```

## Output Format

```python
{
    "classification": "stable" | "volatile" | "exploratory",
    "confidence": 0.0-1.0,
    "reasons": ["list of why this classification"],
    "entropy_trend": "increasing" | "stable" | "decreasing",
    "recommendation": "reuse" | "freeze" | "monitor"
}
```

## Classification Rules

1. **stable** if ALL of:
   - Mean entropy across spans < 1.0
   - Entropy trend is "stable" or "decreasing"
   - No reruns triggered
   - At least 3 spans of data

2. **volatile** if ANY of:
   - Mean entropy > 2.0
   - Entropy trend is "increasing" AND mean entropy > 1.0
   - More than 30% of spans were reruns
   - Any single span has entropy_max > 3.5

3. **exploratory** if:
   - Fewer than 3 spans (insufficient data)
   - OR doesn't meet stable or volatile criteria

## Function Signature

```python
def classify_route(spans: list[dict], metadata: dict) -> dict:
    """Classify a generation route as stable, volatile, or exploratory."""
    ...
```

## File Location

Write to: `labs/coherence_decay/route_classifier.py`
