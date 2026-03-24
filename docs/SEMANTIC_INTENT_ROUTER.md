# Semantic Intent Router

**Version:** v2.2 (March 25, 2026)
**Sprint:** 7
**File:** `personal_agent/semantic_intent_router.py`, `routes/intents.py`

---

## Overview

The semantic intent router replaces fragile regex-based intent classification with embedding similarity. It uses `all-MiniLM-L6-v2` (384-dimensional embeddings, already loaded for memory search) to classify user messages against 140+ prototype phrases across 16 intent types.

The system runs in **hybrid mode**: regex at >= 0.90 confidence wins, embedding fills gaps below that threshold. This means semantic equivalents, typos, multi-intent messages, and ambiguous queries now route correctly without needing explicit regex patterns.

---

## How It Works

### Classification Pipeline

1. **Embed message** — encode user message with all-MiniLM-L6-v2
2. **Centroid similarity** — cosine similarity against mean embedding of each intent's prototype phrases
3. **Individual phrase check** — max similarity against individual prototypes (0.95x discount to prefer centroids)
4. **Contextual boost** — if file paths are attached, +0.15 to file_read, file_write, dir_list, project_scan
5. **Learned corrections** — boost/penalty from past misclassification corrections
6. **Rank and filter** — threshold at 0.45 minimum confidence
7. **Fallback** — conversational intent at 0.3 floor if nothing else matches

### Confidence Levels

| Range | Behavior |
|-------|----------|
| >= 0.75 | **High confidence** — execute immediately |
| 0.45 - 0.75 | **Ambiguous** — show clarification action card with top 3 candidates |
| < 0.45 | **Below threshold** — fall back to conversational |

### Multi-Intent Detection

Compound messages like "check my system and read the config" are detected when:
- Top 2+ intents are within 0.15 confidence of each other
- Second intent is >= 0.55 confidence

Both intents are routed, and a combined plan is built.

---

## Intent Types (16)

| Intent | Prototype Count | Examples |
|--------|----------------|----------|
| `system_info` | 13 | "how's my system", "what's my cpu usage" |
| `file_read` | 9 | "read file", "show me the contents of" |
| `file_write` | 13 | "create a file", "write to file" |
| `dir_list` | 7 | "list directory", "what's in this folder" |
| `project_scan` | 10 | "git status", "check my repo" |
| `shell_exec` | 9 | "run command", "npm install" |
| `git_action` | 8 | "git commit", "push to main" |
| `skill_install` | 6 | "install skill", "add tool from url" |
| `service_action` | 7 | "check moltbook", "query moltbook" |
| `create_commitment` | 12 | "remind me to", "every day at" |
| `list_commitments` | 6 | "what are my reminders" |
| `cancel_commitment` | 8 | "cancel the reminder" |
| `broad_recall` | 5 | "what do you know about me" |
| `self_referential` | 6 | "how do you work" |
| `url_fetch` | 6 | "go to this url" |
| `conversational` | 12 | "hello", "how are you" |

---

## Self-Improvement

### Correction Learning

When a user disambiguates (clicks a different intent in the clarification card) or a task fails:

1. The correction is recorded in `intent_corrections.db` with the message embedding
2. Future classifications check similarity against past corrections (threshold > 0.85)
3. Corrected-to intent gets a **+0.2 boost** (scaled by similarity)
4. Originally-classified intent gets a **-0.15 penalty** (scaled by similarity)

### Automatic Prototype Addition

Every 20th heartbeat tick, `review_corrections()` scans the corrections database. Messages corrected 3+ times to the same intent are automatically added as prototype phrases, permanently improving classification accuracy.

---

## Hybrid Routing

In `task_agent.py`, `classify_intent_hybrid()` runs both classifiers:

```
1. Run regex classifier → get (intent, confidence)
2. Run embedding classifier → get scored list
3. If regex confidence >= 0.90 → use regex result
4. Otherwise → use embedding result
5. Log both for comparison, warn on disagreements
```

This preserves all existing regex patterns as a high-confidence fast path while the embedding model handles the long tail of natural language variation.

---

## API Endpoints

**Router:** `/api/intents`

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/intents/classify?message=...` | Debug classifier — returns embedding scores, multi-intent, ambiguity action, and regex comparison |
| GET | `/api/intents/prototypes` | List all prototype phrases with counts |
| POST | `/api/intents/prototypes/{intent_type}` | Add custom prototype phrase |
| DELETE | `/api/intents/prototypes/{intent_type}/{index}` | Remove custom prototype (base prototypes protected) |
| GET | `/api/intents/corrections` | List recent corrections (limit 1-500) |
| GET | `/api/intents/stats` | Classification statistics |

### GET /api/intents/classify

Query param: `message` (required, min 1 char)

Returns:
```json
{
  "embedding_scores": [{"intent_type": "...", "confidence": 0.82}],
  "multi_intent": [],
  "ambiguity_action": {"action": "execute", "intent": "..."},
  "regex_result": {"intent_type": "...", "confidence": 0.95, "route": "..."}
}
```

Useful for debugging — shows both classifiers side-by-side.

---

## Frontend Integration

- **Source chip** in `AgentThinkingStrip.tsx` — blue badge appears when the embedding router classified the intent (vs regex)
- **Clarification action card** — when confidence is ambiguous (0.45-0.75), top 3 candidate intents shown as buttons for user to disambiguate

---

## Configuration

- **Lazy loading** — router initializes on first classification call, not at startup
- **Graceful fallback** — if embedding model is unavailable, falls back to regex-only routing
- **No additional model loading** — reuses the all-MiniLM-L6-v2 model already loaded for memory search

---

## Testing

External test lab: **97% accuracy** across clear, semantic, typo, multi-intent, and conversational categories.
