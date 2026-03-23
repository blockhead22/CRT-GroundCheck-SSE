# Self-Reflection & The 7-Slot Self-Model

CRT/Aether maintains a persistent self-awareness system: a structured model of its own epistemic state that evolves over time. This is not hardcoded identity — it is earned through evidence from real interactions.

## The 7 Slots

Defined in `personal_agent/self_model.py` as `SELF_MODEL_SLOTS`:

| Slot | What It Tracks | Data Sources | Who Reads It |
|------|---------------|-------------|-------------|
| `uncertainty_domains` | Topics where the system frequently makes errors | Gate failures, negative feedback from last 24h | Prompt assembly (self-knowledge context), self-referential answers |
| `correction_pattern` | Recurring pattern in user corrections (e.g., "tends to over-state recency") | Negative feedback events categorized by type | Prompt assembly, reflection validation |
| `trust_trajectory` | Broad narrative of how trust has moved recently | Trust delta batches from `turn_telemetry` | Self-referential answers, heartbeat decision |
| `known_blindspots` | Structural weaknesses (e.g., "poor temporal reasoning") | Gate failures, contradiction patterns | Prompt assembly (hedging calibration) |
| `growing_confidence` | Areas where the system has been consistently reinforced | Positive trust movement, reinforced memories | Prompt assembly, greeting generation |
| `user_relationship` | Character of the interaction style with the primary user | Style profile, conversation patterns | Greeting generation, response tone |
| `response_style` | Current response style calibration notes | Style profile analysis, user feedback | Prompt assembly (verbosity, hedging level) |

## Storage

Self-model slots are stored as ordinary CRT memories with `kind='self_model'` and `source='self_reflection'`. This means they inherit all CRT guarantees:

- Trust decay over time (stale self-assessments lose influence)
- Contradiction detection (if a new reflection contradicts an old one)
- Append-only audit trail
- Deprecation (old slot values are soft-deprecated when new ones are written)

Each slot is prefixed with `[self_model:<slot_name>]` in the memory text for identification.

Reference: `SelfModel.update_slot()` at `personal_agent/self_model.py:196`

## The Heartbeat Loop

The self-reflection pass runs as step 7 of the heartbeat cycle, implemented in `HeartbeatScheduler._run_self_reflection()` at `personal_agent/heartbeat_system.py:557`.

### Trigger

The `HeartbeatScheduler` is a daemon thread that checks each active thread on a configurable interval (default: check every 10 seconds, run heartbeat every 30 minutes per thread). The scheduler:

1. Gets the list of active threads from the session database
2. For each thread, checks if enough time has elapsed since the last heartbeat
3. Optionally checks active hours (e.g., only run between 9am-5pm)
4. Runs the heartbeat, which includes the self-reflection pass at the end

### Evidence Gathering

The reflection pass gathers four categories of evidence from the last 24 hours:

```python
# From personal_agent/heartbeat_system.py:564-638
# 1. Gate failures — things the system tried to say but verification blocked
gate_fails = turn_telemetry WHERE event_type = 'gate_fail' AND ts > (now - 86400)

# 2. Negative feedback — user corrections and disagreements
negative_feedback = turn_telemetry WHERE event_type = 'feedback_down' AND ts > (now - 86400)

# 3. Trust deltas — batch trust movements across memories
trust_deltas = turn_telemetry WHERE event_type = 'trust_delta_batch' AND ts > (now - 86400)

# 4. Open contradictions — unresolved conflicts in the ledger
open_contradictions = contradictions WHERE status IN ('OPEN', 'REFLECTING')
```

### LLM Self-Assessment

The gathered evidence is formatted into a structured prompt (`_SELF_REFLECTION_PROMPT` at line 530) and sent to the LLM. The prompt asks for a JSON response with values for all 7 slots plus a summary and notable events.

The LLM response is parsed and each slot is written to the CRT memory store with a trust score weighted by the density of negative feedback (more evidence = higher trust in the self-assessment):

```python
trust = max(0.35, min(0.80, 0.55 + len(negative_feedback_lines) * 0.03))
```

### Personality Checkpoints

After updating slots, the system writes a full checkpoint to the `personality_checkpoints` table with:

- The complete snapshot (all slot values)
- A delta (what changed since the last checkpoint)
- Notable events (up to 5)

This powers the timeline endpoint that shows how the self-model has evolved over time.

## How Self-Referential Questions Use the Self-Model

When a user asks about Aether itself (e.g., "how are you doing?", "what are you uncertain about?"), the system calls `_answer_self_referential()` at `routes/chat.py:1214`.

This function:

1. Reads the current self-model via `self_model.read_model()`
2. Gets the top 5 trust-weighted self-observations via `self_model.get_top_facts(5)`
3. Builds a rich context block including CRT design principles, active systems description, and current self-model state
4. Detects whether the question is a casual greeting or a technical question
5. Constructs an appropriate system prompt:
   - **Casual greeting:** "Respond warmly and briefly. Use your self-model state to give a grounded status update."
   - **Technical question:** "Answer from the self-knowledge context. Be honest, specific, and practical."
6. Sends to LLM with the self-knowledge context injected

This ensures Aether's answers about itself are grounded in actual data, not generic descriptions.

## Standalone Reflection

The `run_self_reflection_now()` function at `personal_agent/heartbeat_system.py:805` provides a way to trigger self-reflection outside the heartbeat cycle. It creates a dummy scheduler instance and runs the reflection pass directly. This is used by the heartbeat executor for on-demand reflection.
