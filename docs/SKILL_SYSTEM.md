# Skill System

**Version:** v1.7 (March 23, 2026)
**Sprint:** Foundation
**Layer:** 5 — per-service gate
**Files:** `personal_agent/skill_registry.py`, `data/managed_skills/`

---

## Overview

The skill system lets Aether integrate with external services via SKILL.md files. Skills define API endpoints, authentication, and request templates in a standardized format. Users can install skills from URLs, and Aether remembers installed skills as memory facts.

---

## SKILL.md Format

Each skill is a markdown file with YAML frontmatter:

```markdown
---
name: moltbook
version: 1.0
description: Moltbook API integration
author: nickblockdesigns
---

## API Base
https://api.moltbook.com

## Authentication
API key via header: `Authorization: Bearer {api_key}`

## Endpoints

### GET /api/threads
List all threads

### POST /api/threads
Create a new thread
```

The frontmatter is parsed for `name`, `version`, `description`, and `author`. The body contains API documentation used by the LLM tool loop for making API calls.

A template is available at `data/managed_skills/_template/SKILL.md`.

---

## Skill Registry (`skill_registry.py`)

### Trust Levels

| Level | Description |
|-------|-------------|
| `untrusted` | Newly installed, no verification |
| `trusted` | User has explicitly trusted |
| `verified` | Verified source |
| `blocked` | Explicitly blocked from execution |

### Database Schema

SQLite table `skills` in `data/skills_registry.db`:

| Column | Type | Description |
|--------|------|-------------|
| `name` | TEXT PK | Normalized lowercase [a-z0-9._-] |
| `description` | TEXT | Skill description |
| `source_path` | TEXT | Original location |
| `install_path` | TEXT | Managed copy location |
| `version` | TEXT | Version string |
| `trust_level` | TEXT | untrusted/trusted/verified/blocked |
| `enabled` | INTEGER | Active or not |
| `installed` | INTEGER | Successfully installed |
| `metadata_json` | TEXT | Extra data as JSON |
| `discovered_at` | REAL | First seen timestamp |
| `last_installed_at` | REAL | Last install timestamp |
| `updated_at` | REAL | Last modified |

### SkillRegistry Class

| Method | Description |
|--------|-------------|
| `list_skills()` | List all registered skills |
| `get_skill(name)` | Get specific skill details |
| `discover_skills(roots=None)` | Scan directories for SKILL.md files, upsert into DB |
| `install_skill(name, source_path, enabled=True, trust_level=None)` | Copy to managed_skills dir, register |
| `update_skill(name)` | Re-install from source |
| `set_enabled(name, enabled)` | Enable/disable |
| `set_trust_level(name, level)` | Change trust level |
| `uninstall_skill(name, remove_files=True)` | Remove files and deactivate |

Default discovery roots: `.agents/skills` and `.github/skills`

---

## Install Pipeline

When a user says "add skill from [URL]":

1. **Intent match** — `skill_install` regex matches add/install/register/connect + skill/service/tool + URL
2. **Fetch** — downloads the SKILL.md from the URL
3. **Parse frontmatter** — extracts name, version, description, author (falls back to URL hostname if name missing)
4. **Save** — copies to `data/managed_skills/{name}/SKILL.md`
5. **Register** — upserts into skills registry DB
6. **Update routing** — adds to `_KNOWN_SERVICES` at runtime, rebuilds service regex
7. **Store credentials** — saves skill_url + api_base in credential store
8. **Memory fact** — writes installation as a memory fact (T:0.95) so Aether remembers
9. **Prompt for API key** — deterministic response asking user to provide API key

### Deterministic Response

```
Installed skill: moltbook (v1.0) from https://example.com/SKILL.md
API base: https://api.moltbook.com
Please provide your API key to complete setup.
```

No LLM hallucination on install results.

---

## Skill Execution (LLM Tool Loop)

When a service action is routed to a skill:

1. **Smart section extraction** — keyword-scored API doc sections (not naive truncation)
2. **Credential injection** — API keys injected from credential store into request templates
3. **LLM tool loop** — iterative curl-based API calls (max 8, expandable to 15)
4. **Think-out-loud** — LLM narrates reasoning before/after each tool call
5. **Result rendering** — API responses rendered through CRT governance pipeline

### Service Continuation

Layer 4 detection: "any new threads?" inherits context from the last completed skill task.

---

## Memory Integration

- Installed skills stored as memory facts with trust 0.95
- Aether can answer "what skills do I have installed?" from memory
- Skill URLs and API bases persisted in credential store

---

## Directory Structure

```
data/managed_skills/
├── _template/
│   └── SKILL.md          # Template for new skills
├── moltbook/
│   └── SKILL.md          # Installed skill
└── nickblockdesigns/
    └── helloworld.txt     # Example skill
```
