"""
Layer 2-3 — File and project tools.

Layer 2 (read-only): read_file(), list_directory(), git_status(), scan_project()
Layer 3 (write): write_file(), apply_edit(), generate_diff()
All with allowed-path enforcement.
"""

import difflib
import json
import logging
import os
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Allowed paths configuration
# ---------------------------------------------------------------------------

_SETTINGS_PATH = Path("personal_agent/.file_tools_settings.json")

_DEFAULT_ALLOWED_PATHS: List[str] = ["D:/AI_round2", "D:/"]


def _load_allowed_paths() -> List[str]:
    """Load allowed paths from settings file, falling back to defaults."""
    try:
        if _SETTINGS_PATH.exists():
            data = json.loads(_SETTINGS_PATH.read_text(encoding="utf-8"))
            paths = data.get("allowed_paths", _DEFAULT_ALLOWED_PATHS)
            if isinstance(paths, list) and paths:
                return paths
    except Exception as e:
        logger.warning("[FILE_TOOLS] Failed to load settings: %s", e)
    return list(_DEFAULT_ALLOWED_PATHS)


def _save_allowed_paths(paths: List[str]) -> None:
    """Persist allowed paths to settings file."""
    _SETTINGS_PATH.parent.mkdir(parents=True, exist_ok=True)
    _SETTINGS_PATH.write_text(
        json.dumps({"allowed_paths": paths}, indent=2),
        encoding="utf-8",
    )
    logger.info("[FILE_TOOLS] Saved allowed paths: %s", paths)


def get_allowed_paths() -> List[str]:
    return _load_allowed_paths()


def set_allowed_paths(paths: List[str]) -> List[str]:
    """Validate and save new allowed paths. Returns the saved list."""
    cleaned = []
    for p in paths:
        resolved = str(Path(p).resolve()).replace("\\", "/")
        cleaned.append(resolved)
    _save_allowed_paths(cleaned)
    return cleaned


def _check_path_allowed(path: str) -> Optional[str]:
    """Return None if path is allowed, or an error message if not."""
    resolved = str(Path(path).resolve()).replace("\\", "/")
    allowed = _load_allowed_paths()
    for prefix in allowed:
        norm_prefix = str(Path(prefix).resolve()).replace("\\", "/")
        if resolved.startswith(norm_prefix):
            return None
    return f"Path '{resolved}' is outside allowed paths: {allowed}"


# ---------------------------------------------------------------------------
# Binary file detection
# ---------------------------------------------------------------------------

_BINARY_EXTENSIONS = frozenset([
    ".exe", ".dll", ".so", ".dylib", ".bin", ".obj", ".o", ".a", ".lib",
    ".pyc", ".pyo", ".class", ".jar", ".war",
    ".zip", ".tar", ".gz", ".bz2", ".xz", ".7z", ".rar",
    ".png", ".jpg", ".jpeg", ".gif", ".bmp", ".ico", ".webp", ".svg",
    ".mp3", ".mp4", ".avi", ".mkv", ".mov", ".wav", ".flac",
    ".pdf", ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx",
    ".ttf", ".otf", ".woff", ".woff2", ".eot",
    ".db", ".sqlite", ".sqlite3",
    ".lock",
])


def _is_binary(path: str) -> bool:
    ext = Path(path).suffix.lower()
    if ext in _BINARY_EXTENSIONS:
        return True
    # Sniff first 8KB for null bytes
    try:
        with open(path, "rb") as f:
            chunk = f.read(8192)
            return b"\x00" in chunk
    except Exception:
        return False


# ---------------------------------------------------------------------------
# read_file
# ---------------------------------------------------------------------------

def read_file(path: str, max_lines: int = 200) -> Dict[str, Any]:
    """Read a text file. Truncates to max_lines."""
    err = _check_path_allowed(path)
    if err:
        return {"error": err, "path": path}

    resolved = str(Path(path).resolve()).replace("\\", "/")

    if not os.path.exists(resolved):
        return {"error": f"File not found: {resolved}", "path": resolved}

    if os.path.isdir(resolved):
        return {"error": f"Path is a directory, not a file: {resolved}", "path": resolved}

    if _is_binary(resolved):
        size = os.path.getsize(resolved)
        return {
            "error": f"Binary file ({Path(resolved).suffix}), {size:,} bytes",
            "path": resolved,
            "size_bytes": size,
        }

    try:
        size = os.path.getsize(resolved)
        with open(resolved, "r", encoding="utf-8", errors="replace") as f:
            lines = f.readlines()

        total_lines = len(lines)
        truncated = total_lines > max_lines
        content = "".join(lines[:max_lines])
        if truncated:
            content += f"\n... ({total_lines - max_lines} more lines truncated)"

        logger.info("[FILE_TOOLS] read_file %s — %d lines, %d bytes%s",
                    resolved, total_lines, size, " (truncated)" if truncated else "")

        return {
            "path": resolved,
            "content": content,
            "lines": total_lines,
            "size_bytes": size,
            "truncated": truncated,
        }
    except Exception as e:
        return {"error": str(e), "path": resolved}


# ---------------------------------------------------------------------------
# list_directory
# ---------------------------------------------------------------------------

def list_directory(path: str, max_entries: int = 100, show_hidden: bool = False) -> Dict[str, Any]:
    """List directory contents. Dirs first, then files alphabetically."""
    err = _check_path_allowed(path)
    if err:
        return {"error": err, "path": path}

    resolved = str(Path(path).resolve()).replace("\\", "/")

    if not os.path.exists(resolved):
        return {"error": f"Directory not found: {resolved}", "path": resolved}

    if not os.path.isdir(resolved):
        return {"error": f"Not a directory: {resolved}", "path": resolved}

    try:
        entries_raw = os.listdir(resolved)
    except PermissionError:
        return {"error": f"Permission denied: {resolved}", "path": resolved}

    dirs = []
    files = []
    for name in sorted(entries_raw, key=str.lower):
        if not show_hidden and name.startswith("."):
            continue
        full = os.path.join(resolved, name)
        if os.path.isdir(full):
            dirs.append({"name": name, "type": "dir"})
        else:
            try:
                size = os.path.getsize(full)
            except OSError:
                size = 0
            files.append({"name": name, "type": "file", "size": size})

    entries = dirs + files
    total = len(entries)
    truncated = total > max_entries
    entries = entries[:max_entries]

    logger.info("[FILE_TOOLS] list_directory %s — %d dirs, %d files%s",
                resolved, len(dirs), len(files), " (truncated)" if truncated else "")

    return {
        "path": resolved,
        "entries": entries,
        "total": total,
        "truncated": truncated,
    }


# ---------------------------------------------------------------------------
# git_status
# ---------------------------------------------------------------------------

def git_status(project_path: str) -> Dict[str, Any]:
    """Run git status/branch/log and return structured result."""
    err = _check_path_allowed(project_path)
    if err:
        return {"error": err, "path": project_path}

    resolved = str(Path(project_path).resolve()).replace("\\", "/")

    if not os.path.isdir(os.path.join(resolved, ".git")):
        return {"error": f"Not a git repo: {resolved}", "path": resolved}

    def _run(args: List[str]) -> str:
        r = subprocess.run(
            args, capture_output=True, text=True, timeout=10, cwd=resolved,
        )
        return r.stdout.strip()

    try:
        # Branch
        branch = _run(["git", "branch", "--show-current"])

        # Porcelain status
        raw_status = _run(["git", "status", "--porcelain"])
        modified = []
        untracked = []
        staged = []
        for line in raw_status.splitlines():
            if not line or len(line) < 3:
                continue
            x, y = line[0], line[1]
            fname = line[3:]
            if x == "?" and y == "?":
                untracked.append(fname)
            elif x in ("M", "A", "D", "R"):
                staged.append(fname)
            elif y in ("M", "D"):
                modified.append(fname)

        # Recent commits
        raw_log = _run(["git", "log", "--oneline", "-5"])
        recent_commits = raw_log.splitlines() if raw_log else []

        clean = not modified and not untracked and not staged

        logger.info("[FILE_TOOLS] git_status %s — branch=%s clean=%s modified=%d untracked=%d staged=%d",
                    resolved, branch, clean, len(modified), len(untracked), len(staged))

        return {
            "path": resolved,
            "branch": branch,
            "clean": clean,
            "modified": modified,
            "staged": staged,
            "untracked": untracked,
            "recent_commits": recent_commits,
        }
    except subprocess.TimeoutExpired:
        return {"error": "git command timed out", "path": resolved}
    except FileNotFoundError:
        return {"error": "git not found on PATH", "path": resolved}
    except Exception as e:
        return {"error": str(e), "path": resolved}


# ---------------------------------------------------------------------------
# scan_project
# ---------------------------------------------------------------------------

_PROJECT_MARKERS = {
    "package.json": "node",
    "requirements.txt": "python",
    "pyproject.toml": "python",
    "setup.py": "python",
    "Cargo.toml": "rust",
    "go.mod": "go",
    "pom.xml": "java",
    "build.gradle": "java",
    "Gemfile": "ruby",
    "composer.json": "php",
    "CMakeLists.txt": "cpp",
    "Makefile": "make",
    "Dockerfile": "docker",
}

_ENTRY_POINTS = {
    "node": ["src/index.ts", "src/index.tsx", "src/index.js", "index.ts", "index.js", "src/main.ts", "src/main.tsx"],
    "python": ["main.py", "app.py", "manage.py", "src/main.py", "crt_api.py"],
    "rust": ["src/main.rs"],
    "go": ["main.go", "cmd/main.go"],
}


def scan_project(project_path: str) -> Dict[str, Any]:
    """Scan a project: git status + dir listing + project type detection."""
    err = _check_path_allowed(project_path)
    if err:
        return {"error": err, "path": project_path}

    resolved = str(Path(project_path).resolve()).replace("\\", "/")

    if not os.path.isdir(resolved):
        return {"error": f"Not a directory: {resolved}", "path": resolved}

    # Detect project type
    project_type = "unknown"
    for marker, ptype in _PROJECT_MARKERS.items():
        if os.path.exists(os.path.join(resolved, marker)):
            project_type = ptype
            break

    # Find entry point
    entry_point = None
    candidates = _ENTRY_POINTS.get(project_type, [])
    for ep in candidates:
        if os.path.exists(os.path.join(resolved, ep)):
            entry_point = ep
            break

    # Git info
    git = git_status(resolved)

    # Directory listing (shallow)
    files = list_directory(resolved, max_entries=50)

    logger.info("[FILE_TOOLS] scan_project %s — type=%s entry=%s",
                resolved, project_type, entry_point)

    return {
        "path": resolved,
        "type": project_type,
        "entry_point": entry_point,
        "git": git,
        "files": files,
    }


# ---------------------------------------------------------------------------
# Format helpers (for LLM consumption)
# ---------------------------------------------------------------------------

def format_file_result(result: Dict[str, Any]) -> str:
    """Format read_file result as readable text."""
    if "error" in result:
        return f"Error reading {result.get('path', '?')}: {result['error']}"
    path = result["path"]
    lines = result["lines"]
    trunc = " (truncated)" if result.get("truncated") else ""
    return f"File: {path} ({lines} lines, {result['size_bytes']:,} bytes{trunc})\n\n{result['content']}"


def format_dir_result(result: Dict[str, Any]) -> str:
    """Format list_directory result as readable text."""
    if "error" in result:
        return f"Error listing {result.get('path', '?')}: {result['error']}"
    parts = [f"Directory: {result['path']} ({result['total']} entries)"]
    for e in result["entries"]:
        if e["type"] == "dir":
            parts.append(f"  [dir]  {e['name']}/")
        else:
            size = e.get("size", 0)
            parts.append(f"  [file] {e['name']} ({size:,} bytes)")
    if result.get("truncated"):
        parts.append(f"  ... ({result['total'] - len(result['entries'])} more entries)")
    return "\n".join(parts)


def format_git_result(result: Dict[str, Any]) -> str:
    """Format git_status result as readable text."""
    if "error" in result:
        return f"Git error in {result.get('path', '?')}: {result['error']}"
    parts = [f"Git: {result['path']} (branch: {result['branch']})"]
    if result["clean"]:
        parts.append("  Working tree clean")
    else:
        if result["staged"]:
            parts.append(f"  Staged: {', '.join(result['staged'])}")
        if result["modified"]:
            parts.append(f"  Modified: {', '.join(result['modified'])}")
        if result["untracked"]:
            parts.append(f"  Untracked: {', '.join(result['untracked'])}")
    if result.get("recent_commits"):
        parts.append("  Recent commits:")
        for c in result["recent_commits"]:
            parts.append(f"    {c}")
    return "\n".join(parts)


def format_project_result(result: Dict[str, Any]) -> str:
    """Format scan_project result as readable text."""
    if "error" in result:
        return f"Project scan error: {result['error']}"
    parts = [
        f"Project: {result['path']}",
        f"  Type: {result['type']}",
    ]
    if result.get("entry_point"):
        parts.append(f"  Entry point: {result['entry_point']}")

    git = result.get("git", {})
    if not git.get("error"):
        status = "clean" if git.get("clean") else "dirty"
        mod_count = len(git.get("modified", [])) + len(git.get("staged", [])) + len(git.get("untracked", []))
        parts.append(f"  Git: branch={git.get('branch', '?')}, {status} ({mod_count} changes)")
        if git.get("recent_commits"):
            parts.append("  Recent commits:")
            for c in git["recent_commits"][:3]:
                parts.append(f"    {c}")

    files = result.get("files", {})
    if not files.get("error"):
        entries = files.get("entries", [])
        dir_count = sum(1 for e in entries if e["type"] == "dir")
        file_count = sum(1 for e in entries if e["type"] == "file")
        parts.append(f"  Contents: {dir_count} dirs, {file_count} files")

    return "\n".join(parts)


# ---------------------------------------------------------------------------
# generate_diff (Layer 3 helper)
# ---------------------------------------------------------------------------

def generate_diff(old_content: str, new_content: str, filename: str = "file") -> str:
    """Produce a unified diff string. Truncates to 20 lines with a note."""
    diff_lines = list(difflib.unified_diff(
        old_content.splitlines(keepends=True),
        new_content.splitlines(keepends=True),
        fromfile=f"a/{filename}",
        tofile=f"b/{filename}",
    ))
    if not diff_lines:
        return "(no changes)"
    total = len(diff_lines)
    if total > 20:
        diff_lines = diff_lines[:20]
        diff_lines.append(f"\n... ({total - 20} more lines)\n")
    return "".join(diff_lines)


# ---------------------------------------------------------------------------
# write_file (Layer 3 — requires checkpoint approval)
# ---------------------------------------------------------------------------

def write_file(path: str, content: str) -> Dict[str, Any]:
    """Write content to a file. Reads existing content first for diff.

    Returns dict with path, written_bytes, created, previous_content, diff_preview.
    """
    err = _check_path_allowed(path)
    if err:
        return {"error": err, "path": path}

    resolved = str(Path(path).resolve()).replace("\\", "/")

    # Read existing content for diff
    previous_content = None
    created = True
    if os.path.exists(resolved):
        created = False
        if not os.path.isfile(resolved):
            return {"error": f"Path exists but is not a file: {resolved}", "path": resolved}
        try:
            with open(resolved, "r", encoding="utf-8", errors="replace") as f:
                previous_content = f.read()
        except Exception as e:
            return {"error": f"Cannot read existing file for diff: {e}", "path": resolved}

    try:
        # Ensure parent directory exists
        os.makedirs(os.path.dirname(resolved), exist_ok=True)
        with open(resolved, "w", encoding="utf-8", newline="") as f:
            f.write(content)
        written_bytes = len(content.encode("utf-8"))

        # Generate diff preview
        diff_preview = ""
        if previous_content is not None:
            filename = os.path.basename(resolved)
            diff_preview = generate_diff(previous_content, content, filename)
        else:
            # New file — show first 20 lines
            lines = content.splitlines()[:20]
            diff_preview = "\n".join(f"+{line}" for line in lines)
            if len(content.splitlines()) > 20:
                diff_preview += f"\n... ({len(content.splitlines()) - 20} more lines)"

        logger.info("[FILE_TOOLS] write_file %s — %d bytes, created=%s",
                    resolved, written_bytes, created)

        return {
            "path": resolved,
            "written_bytes": written_bytes,
            "created": created,
            "previous_content": previous_content,
            "diff_preview": diff_preview,
        }
    except Exception as e:
        return {"error": str(e), "path": resolved}


# ---------------------------------------------------------------------------
# apply_edit (Layer 3 — find-and-replace in a file)
# ---------------------------------------------------------------------------

def apply_edit(path: str, old_text: str, new_text: str) -> Dict[str, Any]:
    """Find old_text in file and replace with new_text.

    Returns dict with path, replaced, diff_preview — or error if old_text not found.
    """
    err = _check_path_allowed(path)
    if err:
        return {"error": err, "path": path}

    resolved = str(Path(path).resolve()).replace("\\", "/")

    if not os.path.exists(resolved):
        return {"error": f"File not found: {resolved}", "path": resolved}

    if not os.path.isfile(resolved):
        return {"error": f"Not a file: {resolved}", "path": resolved}

    try:
        with open(resolved, "r", encoding="utf-8", errors="replace") as f:
            original = f.read()
    except Exception as e:
        return {"error": f"Cannot read file: {e}", "path": resolved}

    if old_text not in original:
        return {"error": "old_text not found in file", "path": resolved, "replaced": False}

    new_content = original.replace(old_text, new_text, 1)

    try:
        with open(resolved, "w", encoding="utf-8", newline="") as f:
            f.write(new_content)
    except Exception as e:
        return {"error": f"Cannot write file: {e}", "path": resolved}

    filename = os.path.basename(resolved)
    diff_preview = generate_diff(original, new_content, filename)

    logger.info("[FILE_TOOLS] apply_edit %s — replaced %d chars with %d chars",
                resolved, len(old_text), len(new_text))

    return {
        "path": resolved,
        "replaced": True,
        "diff_preview": diff_preview,
    }
