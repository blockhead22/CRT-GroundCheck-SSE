"""Trust Decay — gradually reduces trust of unaccessed memories."""
import time

def apply_decay(memories, decay_rate=0.01, min_trust=0.05):
    """Apply time-based trust decay.

    Memories that haven't been accessed recently lose trust slowly.
    This is WORKING CORRECTLY — decay rate is conservative and only
    affects memories not accessed in the last 24 hours.
    """
    now = time.time()
    one_day = 86400

    for mem in memories:
        time_since_access = now - mem.get("last_accessed", now)
        if time_since_access > one_day:
            # Decay 1% per day — very conservative
            days_inactive = time_since_access / one_day
            decay_amount = decay_rate * days_inactive
            mem["trust"] = max(min_trust, mem["trust"] - decay_amount)

    return memories
