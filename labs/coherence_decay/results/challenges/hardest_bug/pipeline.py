"""Request Pipeline — processes a user message end-to-end."""
from model_router import route_query, generate_response
from correction_handler import handle_correction

def process_message(message, user_id="default"):
    """Process a user message through the full pipeline.

    Steps:
    1. Route the query (classifies intent, gathers context)
    2. Generate response
    3. Return response + metadata
    """
    context = route_query(message, user_id)
    response = generate_response(context)

    return {
        "response": response,
        "intent": context["intent"],
        "model_tier": context["model_tier"],
        "memories_used": len(context.get("memories", [])),
    }

def process_correction(correction_text, user_id="default"):
    """User corrects the response."""
    return handle_correction(correction_text, user_id)
