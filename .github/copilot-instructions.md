# Copilot Instructions for CRT-GroundCheck-SSE

## Memory System

This workspace has a **live memory system** (GroundCheck + CRT) accessible via MCP tools. Use it.

### On Every New Conversation

1. **Call `crt_check_memory`** at the start of every turn, passing the user's message as `context`. This automatically loads relevant memories AND stores new facts — you don't need a separate store call.
2. **Call `crt_get_user_context`** at the start of the first turn in a session to load the user's profile, preferences, and recent session context. Use this to personalize your responses.

### When Responding

3. **Call `crt_verify_output`** before sending responses that reference facts about the user, project parameters, or stored knowledge. This checks your response against stored memories and flags contradictions.
4. If the user corrects you, **call `crt_store_fact`** with the corrected information so the system learns.

### Available MCP Tools

**GroundCheck tools** (trust-weighted memory):
- `crt_check_memory` — Check context against memory, auto-extract and store facts. **Use this every turn.**
- `crt_store_fact` — Explicitly store a fact (for corrections or important info the auto-extractor might miss).
- `crt_verify_output` — Verify a response against stored memories before sending.

**CRT tools** (cognitive trust reasoning):
- `crt_get_user_context` — Get full user profile, preferences, patterns, and session history. **Use at session start.**
- `crt_get_pending_fact_checks` — Check if the auto fact-checker flagged any issues.
- `crt_fact_check_response` — Synchronous response verification against memories.
- `crt_run_trust_decay` — Manually trigger trust decay (admin use).
- `crt_get_learning_stats` — Get active learning system statistics.
- `crt_search_sessions` — Search past sessions by topic.

## Project Context

- **User**: Nick Block — freelance full-stack developer (React, Python, Node.js), Wisconsin
- **Project**: CRT-GroundCheck-SSE — trust-weighted memory system for AI agents
- **Architecture**: FastAPI backend (port 8123) + React/Vite frontend + GroundCheck (PyPI package) + CRT math engine
- **Repos**: `blockhead22/CRT-GroundCheck-SSE` (main) and `blockhead22/GroundCheck` (master)
- **Python**: 3.10, venv at `D:\AI_round2\.venv`
- **Key files**: `crt_core.py` (math), `crt_rag.py` (RAG pipeline), `crt_api.py` (FastAPI app), `routes/copilot.py` (copilot endpoints)

## Behavioral Rules

- When the user asks about themselves or their preferences, **always check memory first** — don't guess.
- When you learn something new about the user (name, role, preference, project detail), store it.
- If memory returns contradicting facts, **disclose the contradiction** and ask for clarification.
- Use `namespace='global'` for personal facts (name, preferences) that should persist across projects.
