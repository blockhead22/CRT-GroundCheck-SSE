# Action Execution Layer

**Version:** v1.9 (March 24, 2026)
**Sprint:** 3
**Layers:** 2 (read), 3 (write), 4 (shell/git)
**Files:** `personal_agent/file_tools.py`, `personal_agent/shell_tools.py`, `personal_agent/action_receipts.py`, `routes/action_receipts.py`

---

## Overview

The action execution layer gives Aether the ability to read files, write code, run shell commands, and execute git operations — all gated by the checkpoint system. Every write/exec action creates an audit-trailed ActionReceipt in SQLite. The frontend shows diff previews and command previews in the action card before execution.

---

## Access Layer Model

| Layer | Tools | Gate | Preview |
|-------|-------|------|---------|
| **Layer 2** | file_read, dir_list, project_scan | No gate (first access checkpoint, then trusted) | Content displayed directly |
| **Layer 3** | file_write, content_generate | High checkpoint (always) | Unified diff |
| **Layer 4** | shell_exec, git_action | Highest checkpoint (always) | Command in code block |

---

## File Tools (`file_tools.py`)

### Path Security

All file operations enforce an **allowed paths** whitelist:

- Default: `['D:/AI_round2', 'D:/']`
- Configurable via `GET/PUT /api/settings/allowed-paths`
- Persisted to `.file_tools_settings.json`
- Every path checked before any read or write

### Read Operations

| Function | Description |
|----------|-------------|
| `read_file(path, max_lines=200)` | Returns content, line count, size, truncated flag |
| `list_directory(path, max_entries=100, show_hidden=False)` | Dirs first, then files alphabetically |
| `git_status(project_path)` | Branch, clean/dirty, modified/staged/untracked, recent commits |
| `scan_project(project_path)` | Project type detection + git info + directory listing |

**Binary detection:** 40+ extensions (.exe, .dll, .zip, .png, .pdf, .db, .lock, etc.) plus null-byte sniffing of the first 8KB.

**Project type detection:** Recognizes 13 project markers:
- `package.json` → node
- `requirements.txt` / `pyproject.toml` → python
- `Cargo.toml` → rust
- `go.mod` → go
- `pom.xml` → java
- And 7 more

Automatically finds entry points per project type (e.g. `src/index.ts` for node, `main.py` for python).

### Write Operations

| Function | Description |
|----------|-------------|
| `write_file(path, content)` | Reads existing for diff, creates parent dirs, returns diff_preview |
| `apply_edit(path, old_text, new_text)` | Find-and-replace (first occurrence), returns diff_preview |
| `generate_diff(old, new, filename)` | Unified diff output, truncated to 20 lines |

**Content generation:** When the user describes what a file should contain (instead of literal content), the LLM generates the code/content first, then writes it. Detection: word count + file extension heuristic.

### Deterministic Responses

Layer 2 tools return actual file/directory content in structured format — no LLM summarization. This prevents hallucinated file contents.

---

## Shell Tools (`shell_tools.py`)

### Blocked Commands (10 patterns)

Regex-matched patterns that are never executed:

- `rm -rf /` and `rm -rf *`
- `format C:`
- `del /s /q C:\`
- `shutdown`
- `mkfs`
- `> /dev/sdX` and `dd of=/dev/sd`
- `rd /s /q C:\`

### execute_command(command, cwd=None, timeout=30)

1. Validates `cwd` against allowed paths
2. Checks against blocked patterns
3. Runs via `subprocess` with `shell=True`
4. Truncates stdout/stderr to 5000 chars
5. Returns: command, exit_code, stdout, stderr, duration_ms, cwd

### execute_git(args, cwd, timeout=30)

Wrapper for `subprocess.run(['git'] + args)`. Same return structure. Gated by high-tier checkpoint.

---

## Action Receipts (`action_receipts.py`)

Every write/exec action creates an immutable audit record.

### Receipt Schema

| Field | Type | Description |
|-------|------|-------------|
| `receipt_id` | UUID | Unique identifier |
| `timestamp` | float | When the action occurred |