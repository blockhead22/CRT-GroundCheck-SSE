def classify_route(spans, metadata):
    if len(spans) < 3:
        return {
            "classification": "exploratory",
            "confidence": 0.5,
            "reasons": ["Insufficient data"],
            "entropy_trend": None,
            "recommendation": "monitor"
        }

    mean_entropy = sum(span["entropy_mean"] for span in spans) / len(spans)
    entropy_max = max(span["entropy_max"] for span in spans)

    if any(span["was_rerun"] for span in spans):
        reruns = sum(1 for span in spans if span["was_rerun"])
        if reruns > 0.3 * len(spans):
            return {
                "classification": "volatile",
                "confidence": 0.8,
                "reasons": ["More than 30% of spans were reruns"],
                "entropy_trend": None,
                "recommendation": "freeze"
            }

    entropy_trend = None
    for i in range(len(spans) - 1):
        if spans[i]["entropy_mean"] < spans[i + 1]["entropy_mean"]:
            entropy_trend = "increasing"

    if mean_entropy > 2.0:
        return {
            "classification": "volatile",
            "confidence": 0.8,
            "reasons": ["Mean entropy is high"],
            "entropy_trend": None,
            "recommendation": "freeze"
        }

    if entropy_max > 3.5:
        return {
            "classification": "volatile",
            "confidence": 0.8,
            "reasons": ["Entropy max is high"],
            "entropy_trend": None,
            "recommendation": "freeze"
        }

    if entropy_trend == "increasing":
        return {
            "classification": "volatile",
            "confidence": 0.5,
            "reasons": ["Entropy trend is increasing"],
            "entropy_trend": "increasing",
            "recommendation": "freeze"
        }

    if mean_entropy < 1.0:
        return {
            "classification": "stable",
            "confidence": 0.9,
            "reasons": [],
            "entropy_trend": None,
            "recommendation": "reuse"
        }

    return {
        "classification": "stable",
        "confidence": 0.5,
        "reasons": [],
        "entropy_trend": None,
        "recommendation": "monitor"
    }