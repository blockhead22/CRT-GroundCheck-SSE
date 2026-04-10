"""Correction Handler — processes user corrections to memory."""
from memory_store import save_memory, get_memory

def handle_correction(original_text, corrected_text):
    """User corrects a fact. Save the correction as a new memory.

    The correction is saved as a NEW memory with low trust (0.15)
    because it hasn't been verified yet. This is correct behavior.

    However, this creates a problem: the new memory is very similar
    to the existing one (it's a correction of the same fact).
    When save_memory runs, it triggers dedup, which merges the new
    low-trust correction with the old high-trust memory...
    """
    existing = get_memory(original_text)

    # Save correction as new memory (trust=0.15, unverified)
    new_mem = save_memory(
        text=corrected_text,
        trust=0.15,
        source="user_correction",
    )

    return {
        "status": "corrected",
        "old": existing,
        "new": new_mem,
    }
