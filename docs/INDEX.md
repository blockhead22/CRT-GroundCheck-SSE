# CRT/Aether Documentation

## Core Architecture
| Document | Description |
|----------|-------------|
| [Three Laws](THREE_LAWS.md) | The three design laws governing every subsystem: belief > speech, preserve contradictions, emergent structure |
| [Architecture](ARCHITECTURE.md) | 7-tier subsystem overview: Memory, Verification, Reflection, Compression, Routing, ViLT, CRT-as-Critic |
| [Request Lifecycle](REQUEST_LIFECYCLE.md) | Full request flow from user input through intent routing, fact extraction, memory retrieval, gates, generation, and trust evolution |
| [What Makes CRT Different](WHAT_MAKES_CRT_DIFFERENT.md) | Comparison with ChatGPT memory, RAG, MemGPT, and other approaches |

## Subsystems
| Document | Description |
|----------|-------------|
| [Memory Lifecycle](MEMORY_LIFECYCLE.md) | Memory creation, trust scoring, confidence vs trust, compression tiers, deprecation policy |
| [Cloud Routing](CLOUD_ROUTING.md) | 3-tier routing (Local, OpenAI Tier 1, Claude Tier 2), escalation policy, fallback logic |
| [Compression](COMPRESSION.md) | V(t)-driven semantic compression, significance scoring, tier transitions (10D/64D/384D) |
| [Self-Model](SELF_MODEL.md) | 7-slot self-awareness system, heartbeat reflection, personality checkpoints, behavioral directives |
| [Configuration](CONFIGURATION.md) | Runtime config reference, JSON schema, environment variables, product modes |
| [ViLT Technical Writeup](VILT_TECHNICAL_WRITEUP.md) | Verification-In-the-Loop Training: trust-weighted loss, GroundCheck mid-training, SmolLM/Qwen results |

## Getting Started
| Document | Description |
|----------|-------------|
| [Quick Start](QUICK_START.md) | Installation, environment setup, frontend/backend startup, first conversation walkthrough |
| [CRT White Paper](CRT_WHITE_PAPER.md) | Theoretical foundations: trust math, contradiction theory, epistemic governance |

## Testing & Quality
| Document | Description |
|----------|-------------|
| [Testing Patterns](TESTING_PATTERNS.md) | Test design principles, adversarial categories, stress test methodology |
| [Testing Methods](TESTING_METHODS.md) | Unit/integration/stress test approaches |
| [Adversarial Stress Test Report](ADVERSARIAL_STRESS_TEST_REPORT.md) | 50-turn attack results: 79% handled, gaslighting/identity wipe analysis |
| [Anti-Patterns](ANTI_PATTERNS.md) | What NOT to do: silent overwrites, hardcoded routes, trust leaks |

## Specs
| Document | Description |
|----------|-------------|
| [API Contract](specs/API_CONTRACT.md) | API endpoint definitions and contracts |
| [Architecture Spec](specs/ARCHITECTURE.md) | Detailed architecture specification (Feb 2026) |
| [Freeze Manifest](specs/FREEZE_MANIFEST.md) | Defines what is frozen for stability |
| [Innovation Pillars](specs/INNOVATION_PILLARS.md) | Philosophical pillars for design decisions |

## Archive
Superseded documents moved to `archive/`:
- `IMPLEMENTATION_PLAN.md` — superseded by [ROADMAP.md](../ROADMAP.md)
- `PATTERN_FIXES_SESSION.md` — Jan 2026 session notes
- `SESSION_COMPLETE.md` — Jan 2026 session wrap-up
- `SYSTEM_ASSESSMENT.md` — Jan 2026 architecture snapshot
- `TECHNICAL_REFERENCE.md` — content migrated to active docs
