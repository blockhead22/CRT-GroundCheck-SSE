"""Intent Router — classifies user queries by type."""

INTENT_PATTERNS = {
    "identity": [
        "who am i", "tell me about myself", "what do you know about me",
        "my profile", "my preferences",
    ],
    "general_knowledge": [
        "what is", "what's", "who is", "where is", "how does",
        "explain", "tell me about", "define",
    ],
    "action": [
        "do", "create", "make", "build", "run", "execute",
    ],
    "memory": [
        "remember", "save", "store", "don't forget",
    ],
}

def classify_intent(query):
    """Classify a user query into an intent type.

    Returns the intent with the highest pattern match score.
    """
    query_lower = query.lower().strip()
    scores = {}

    for intent, patterns in INTENT_PATTERNS.items():
        score = 0
        for pattern in patterns:
            if pattern in query_lower:
                score += len(pattern)  # Longer matches score higher
        scores[intent] = score

    if max(scores.values()) == 0:
        return "general_knowledge"  # Default fallback

    # BUG: "What's my name?" matches "what's" (general_knowledge, score=6)
    # It SHOULD match identity because of "my", but "my" isn't in
    # any identity pattern that would fire.
    # "what's" is in general_knowledge patterns and wins.
    return max(scores, key=scores.get)

def get_intent_config(intent):
    """Return configuration for how to handle this intent type."""
    configs = {
        "identity": {
            "requires_memory": True,
            "model_tier": "local",
            "inject_beliefs": True,
            "inject_profile": True,
        },
        "general_knowledge": {
            "requires_memory": False,  # <-- This is why memories get skipped
            "model_tier": "cloud",
            "inject_beliefs": False,
            "inject_profile": False,
        },
        "action": {
            "requires_memory": False,
            "model_tier": "local",
            "inject_beliefs": False,
            "inject_profile": False,
        },
        "memory": {
            "requires_memory": True,
            "model_tier": "local",
            "inject_beliefs": True,
            "inject_profile": False,
        },
    }
    return configs.get(intent, configs["general_knowledge"])
