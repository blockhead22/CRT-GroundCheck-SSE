Future idea: topic drift + reflection bounds (for later)

---

Future idea: BRG epistemic elevation + proactive gentle surfacing (for later)

Concept
- Walker traverses BRG and finds connection types:
  1. Strong connection (high-trust anchor → low-trust node): epistemically elevate the low-trust node
     for this context window. Trust flows through the edge. Inject as a connected pair.
  2. Weak/surprising connection: queue for gentle proactive surface — not an alert, just a natural
     "hey I noticed something, no rush" at the right conversational moment.
  3. Isolated memory (no strong connections to current context): deprioritize or skip injection entirely.

- Proactive surface queue: accumulated by walker during heartbeat/walk, held until a natural
  conversational opening (topic shift, idle moment, user asking how things are going).
  Tone: low-pressure, user-led from there.

Why
- BRG edges currently wasted — trust doesn't flow through them. Memory A (0.92) supporting
  Memory B (0.41) should lift B. The connection is evidence.
- Stops force-injecting all memories as equally important. Gravity rooms rank by mass;
  BRG edges tell you which memories actually belong together in THIS context.
- Replaces the alarming red-flag contradiction surface with something organic.

Related: salience gate (same yield-to-model mechanism, pointed inward), backward influence
propagation (trust flowing through revision cascade — extend to topology).

---

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
