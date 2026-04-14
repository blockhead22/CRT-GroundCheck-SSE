---
name: CRT Core Philosophy Laws
description: Three foundational design laws from Nick's year-long CRT development — belief/speech separation, contradiction resolution policy, and emergent structure principle. Sourced from ChatGPT institutional memory (March 2026).
type: project
---

## Three Core Laws of CRT (from ChatGPT institutional memory, confirmed by Nick)

### 1. Belief vs Speech: "The mouth should never outweigh the self"
- Belief lives in memory structure. Speech is a provisional surface act.
- LLM generation is downstream expression, NOT a source of belief.
- Fallback LLMs are "vocal cords, not epistemic authorities."
- If fallback contradicts memory, the response must be marked suspect/degraded and the conflict logged — never silently adopted.
- The system may hold unresolved tension internally without collapsing it into a fake confident answer.
- **How to apply:** Never let LLM output overwrite memory-backed truth. Trust thresholds gate disclosure, but the deeper rule is that generation cannot redefine what the system believes.

### 2. Contradiction Resolution: Earned, Never Destructive
- Contradictions are signals, not errors to erase.
- Auto-resolve ONLY when there is strong asymmetry in evidence or trust.
- Otherwise hold open. Never destroy the losing side without trace.
- System may lean, quarantine, downgrade, or mark provisionally resolved.
- Full resolution must be earned through: corroboration, trusted source hierarchy, deterministic receipts, or later confirmation.
- Silent destructive resolution is explicitly forbidden.
- **How to apply:** When implementing contradiction handling, always preserve both sides. Deprecation (with reason) is acceptable; deletion is not.

### 3. Emergent Structure, Not Hardcoded Logic
- Nick has repeatedly rejected hardcoded conditional hacks ("if user says X, answer Y") unless they exist as protected memory or anchor structure.
- Behavior should emerge from memory, reflection, compression, and contradiction handling — not runtime cheats.
- Dynamic slot discovery is a natural extension of this principle.
- **How to apply:** When building new features (fact extraction, intent routing, etc.), prefer learned/emergent approaches over rigid pattern matching. Regex is acceptable as a fast tier but should not be the ceiling.
