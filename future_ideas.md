Future idea: topic drift + reflection bounds (for later)

Concept
- Track topic interest with decay (recent spikes vs fading topics).
- Run lightweight background reflection every N messages or N hours.
- Detect rising topics, fading topics, and update a short "current focus".
- Optional future step: web search when a topic spikes and data is stale.
- Store results as reference packets (no hard overwrite).

Signals
- Topic frequency (recent vs historical)
- Decay rate to fade older interests
- Thresholds: rising, stable, fading

Outcomes
- Prefer current topics in suggestions/prompts
- De-prioritize fading topics
- Queue research jobs when staleness + rising signal
