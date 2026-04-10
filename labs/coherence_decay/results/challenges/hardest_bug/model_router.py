"""Model Router — sends queries to appropriate model with context."""
from intent_router import classify_intent, get_intent_config
from memory_retriever import retrieve_relevant_memories

def route_query(query, user_id="default"):
    """Route a query to the appropriate model with appropriate context.

    Key behavior:
    - identity queries get full memory + profile injection
    - general_knowledge queries get NO memory (sent to cloud raw)
    - This means personal questions routed as general_knowledge
      will get answered WITHOUT any user-specific context
    """
    intent = classify_intent(query)
    config = get_intent_config(intent)

    context = {"query": query, "intent": intent}

    if config["requires_memory"]:
        memories = retrieve_relevant_memories(query, user_id)
        context["memories"] = memories
    else:
        context["memories"] = []  # No memories for this intent type

    if config["inject_profile"]:
        context["profile"] = get_user_profile(user_id)
    else:
        context["profile"] = None

    context["model_tier"] = config["model_tier"]

    return context

def get_user_profile(user_id):
    """Get user profile from memory."""
    return {
        "name": "Nick",
        "location": "Milwaukee",
        "occupation": "developer",
    }

def generate_response(context):
    """Generate a response using the routed model.

    If model_tier is 'cloud' and no memories are injected,
    the model has NO idea who the user is.
    """
    if context["model_tier"] == "cloud" and not context["memories"]:
        # Cloud model with no context — will give generic answer
        return f"I don't have specific information about that. Could you tell me more?"

    if context["memories"]:
        # Local model with memories — will give personalized answer
        memory_text = "; ".join([m["text"] for m in context["memories"]])
        return f"Based on what I know: {memory_text}"

    return "I'm not sure about that."
