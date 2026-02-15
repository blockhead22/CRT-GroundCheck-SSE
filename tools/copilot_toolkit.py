#!/usr/bin/env python3
"""Copilot Toolkit — 5 developer tools for managing large projects across AI sessions.

Subcommands:
    context   Project Context Generator — compact summary for onboarding Copilot
    handoff   Session Handoff Generator — structured changeset doc for new sessions
    archmap   Architecture Map — compact class/function/import index
    diff      Diff Summarizer — recent changes report
    todos     TODO Scanner — cross-project TODO/FIXME/HACK finder

Usage:
    python tools/copilot_toolkit.py context D:\\CogniForge
    python tools/copilot_toolkit.py handoff D:\\AI_round2 --commits 5
    python tools/copilot_toolkit.py archmap D:\\CogniForge\\core
    python tools/copilot_toolkit.py diff D:\\groundcheck --commits 3
    python tools/copilot_toolkit.py todos D:\\AI_round2 D:\\CogniForge D:\\groundcheck

All output is Markdown, designed to be pasted directly into a Copilot chat.
Token-budget aware: output is kept compact for models with limited context.
"""

from __future__ import annotations

import argparse
import ast
import os
import re
import subprocess
import sys
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple


# ═══════════════════════════════════════════════════════════════════════════
#  Shared helpers
# ═══════════════════════════════════════════════════════════════════════════

def _git(args: List[str], cwd: str) -> str:
    """Run a git command and return stdout (empty string on failure)."""
    try:
        r = subprocess.run(
            ["git"] + args,
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=15,
        )
        return r.stdout.strip()
    except Exception:
        return ""


def _is_ignored(path: Path, root: Path, ignore_dirs: Set[str]) -> bool:
    """Check if a path should be skipped."""
    parts = path.relative_to(root).parts
    return any(p in ignore_dirs for p in parts)


# Default directories to skip
IGNORE_DIRS = {
    "__pycache__", ".git", ".venv", "venv", "node_modules", ".pytest_cache",
    ".mypy_cache", ".tox", "dist", "build", "*.egg-info", ".eggs",
    "htmlcov", ".coverage", ".ruff_cache", "data", "checkpoints",
    "site-packages", ".idea", "Lib", "Scripts", "Include",
}

# File extensions we care about
CODE_EXTS = {".py", ".js", ".ts", ".tsx", ".jsx", ".json", ".toml", ".yaml", ".yml", ".md", ".cfg", ".ini"}
PY_EXTS = {".py"}


def _walk_files(
    root: Path,
    *,
    extensions: Optional[Set[str]] = None,
    ignore_dirs: Optional[Set[str]] = None,
    max_files: int = 500,
) -> List[Path]:
    """Walk directory tree, respecting ignore rules."""
    extensions = extensions or CODE_EXTS
    ignore = ignore_dirs or IGNORE_DIRS
    files: List[Path] = []

    for dirpath, dirnames, filenames in os.walk(root):
        dp = Path(dirpath)
        # Prune ignored directories in-place
        dirnames[:] = [
            d for d in dirnames
            if d not in ignore and not d.endswith(".egg-info")
        ]
        for fn in sorted(filenames):
            fp = dp / fn
            if fp.suffix in extensions:
                files.append(fp)
                if len(files) >= max_files:
                    return files
    return files


def _file_tree(root: Path, max_depth: int = 3) -> str:
    """Generate a compact directory tree string."""
    lines = []
    root = root.resolve()

    def _walk(path: Path, prefix: str, depth: int):
        if depth > max_depth:
            return
        entries = sorted(path.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower()))
        dirs = [e for e in entries if e.is_dir() and e.name not in IGNORE_DIRS and not e.name.endswith(".egg-info")]
        files = [e for e in entries if e.is_file() and e.suffix in CODE_EXTS]

        for i, d in enumerate(dirs):
            connector = "├── " if (i < len(dirs) - 1 or files) else "└── "
            lines.append(f"{prefix}{connector}{d.name}/")
            next_prefix = prefix + ("│   " if connector == "├── " else "    ")
            _walk(d, next_prefix, depth + 1)

        # Show files (compact: max 15 per dir)
        shown_files = files[:15]
        remaining = len(files) - 15
        for i, f in enumerate(shown_files):
            connector = "├── " if i < len(shown_files) - 1 or remaining > 0 else "└── "
            size = f.stat().st_size
            size_str = f"{size:,}B" if size < 10_000 else f"{size // 1024}KB"
            lines.append(f"{prefix}{connector}{f.name} ({size_str})")
        if remaining > 0:
            lines.append(f"{prefix}└── ... +{remaining} more files")

    lines.append(f"{root.name}/")
    _walk(root, "", 0)
    return "\n".join(lines)


def _truncate(text: str, max_chars: int = 12_000) -> str:
    """Truncate text with a notice if too long."""
    if len(text) <= max_chars:
        return text
    return text[:max_chars] + f"\n\n... (truncated — {len(text):,} chars total, showing first {max_chars:,})"


# ═══════════════════════════════════════════════════════════════════════════
#  1. CONTEXT DUMP — Project Context Generator
# ═══════════════════════════════════════════════════════════════════════════

def cmd_context(args: argparse.Namespace) -> str:
    """Generate a compact project context summary."""
    root = Path(args.path).resolve()
    if not root.exists():
        return f"Error: {root} does not exist"

    sections = []

    # Header
    project_name = root.name
    branch = _git(["branch", "--show-current"], str(root))
    remote = _git(["remote", "get-url", "origin"], str(root))
    sections.append(f"# Project Context: {project_name}")
    if branch:
        sections.append(f"**Branch:** `{branch}`")
    if remote:
        sections.append(f"**Remote:** `{remote}`")

    # Version from pyproject.toml or __init__.py
    pyproject = root / "pyproject.toml"
    if pyproject.exists():
        for line in pyproject.read_text(errors="replace").splitlines():
            if line.strip().startswith("version"):
                sections.append(f"**Version:** {line.strip()}")
                break

    # File tree
    sections.append("\n## File Tree\n```")
    sections.append(_file_tree(root, max_depth=args.depth))
    sections.append("```")

    # Recent git log
    log = _git(
        ["log", f"--oneline", f"-{args.commits}", "--no-decorate"],
        str(root),
    )
    if log:
        sections.append(f"\n## Recent Commits (last {args.commits})\n```")
        sections.append(log)
        sections.append("```")

    # Config/constants (if config.py exists)
    config_files = [f for f in _walk_files(root, extensions=PY_EXTS) if f.name == "config.py"]
    for cf in config_files[:2]:
        try:
            content = cf.read_text(errors="replace")
            # Extract uppercase constants
            consts = [
                line.strip() for line in content.splitlines()
                if re.match(r"^[A-Z_]+ *=", line.strip()) and not line.strip().startswith("#")
            ]
            if consts:
                rel = cf.relative_to(root)
                sections.append(f"\n## Config Constants ({rel})\n```python")
                sections.append("\n".join(consts[:30]))
                sections.append("```")
        except Exception:
            pass

    # Open TODOs in code (quick scan)
    todo_lines = []
    for f in _walk_files(root, extensions=PY_EXTS, max_files=200):
        try:
            for i, line in enumerate(f.read_text(errors="replace").splitlines(), 1):
                if re.search(r"#\s*(TODO|FIXME|HACK|XXX)\b", line, re.IGNORECASE):
                    rel = f.relative_to(root)
                    todo_lines.append(f"  {rel}:{i} → {line.strip()}")
        except Exception:
            pass
    if todo_lines:
        sections.append(f"\n## Open TODOs ({len(todo_lines)})")
        for tl in todo_lines[:20]:
            sections.append(tl)
        if len(todo_lines) > 20:
            sections.append(f"  ... +{len(todo_lines) - 20} more")

    # Test count (respects IGNORE_DIRS — won't scan .venv/site-packages)
    test_files = [
        f for f in _walk_files(root, extensions=PY_EXTS)
        if f.name.startswith("test_") or f.name.endswith("_test.py")
    ]
    if test_files:
        sections.append(f"\n## Tests: {len(test_files)} test file(s)")
        for tf in test_files[:10]:
            sections.append(f"  - {tf.relative_to(root)}")

    output = "\n".join(sections)
    return _truncate(output, args.max_chars)


# ═══════════════════════════════════════════════════════════════════════════
#  2. SESSION HANDOFF — Structured changeset for new sessions
# ═══════════════════════════════════════════════════════════════════════════

def cmd_handoff(args: argparse.Namespace) -> str:
    """Generate a session handoff document from recent changes."""
    root = Path(args.path).resolve()
    sections = []

    project_name = root.name
    branch = _git(["branch", "--show-current"], str(root))
    sections.append(f"# Session Handoff: {project_name}")
    sections.append(f"**Branch:** `{branch or 'unknown'}`")
    sections.append(f"**Generated:** auto")

    # Recent commits with full messages
    log = _git(
        ["log", f"-{args.commits}", "--format=### %h — %s%n%b%n---"],
        str(root),
    )
    if log:
        sections.append(f"\n## Recent Commits\n")
        sections.append(log)

    # Diff stat
    stat = _git(["diff", "--stat", f"HEAD~{args.commits}"], str(root))
    if stat:
        sections.append(f"\n## Change Summary (last {args.commits} commits)\n```")
        sections.append(stat)
        sections.append("```")

    # Files changed (names only)
    changed = _git(
        ["diff", "--name-status", f"HEAD~{args.commits}"],
        str(root),
    )
    if changed:
        added = [l.split("\t")[1] for l in changed.splitlines() if l.startswith("A")]
        modified = [l.split("\t")[1] for l in changed.splitlines() if l.startswith("M")]
        deleted = [l.split("\t")[1] for l in changed.splitlines() if l.startswith("D")]

        sections.append("\n## Files Changed")
        if added:
            sections.append(f"\n**Added ({len(added)}):**")
            for f in added:
                sections.append(f"  - `{f}`")
        if modified:
            sections.append(f"\n**Modified ({len(modified)}):**")
            for f in modified:
                sections.append(f"  - `{f}`")
        if deleted:
            sections.append(f"\n**Deleted ({len(deleted)}):**")
            for f in deleted:
                sections.append(f"  - `{f}`")

    # Current state: uncommitted changes
    status = _git(["status", "--short"], str(root))
    if status:
        sections.append(f"\n## Uncommitted Changes\n```")
        sections.append(status)
        sections.append("```")
    else:
        sections.append("\n## Working Tree: Clean ✓")

    # Stash list
    stash = _git(["stash", "list"], str(root))
    if stash:
        sections.append(f"\n## Stashes\n```")
        sections.append(stash)
        sections.append("```")

    # Key TODO items from changed files
    if changed:
        todos = []
        for line in changed.splitlines():
            parts = line.split("\t")
            if len(parts) < 2:
                continue
            fp = root / parts[-1]
            if fp.exists() and fp.suffix == ".py":
                try:
                    for i, ln in enumerate(fp.read_text(errors="replace").splitlines(), 1):
                        if re.search(r"#\s*(TODO|FIXME)\b", ln, re.IGNORECASE):
                            todos.append(f"  {parts[-1]}:{i} → {ln.strip()}")
                except Exception:
                    pass
        if todos:
            sections.append(f"\n## TODOs in Changed Files ({len(todos)})")
            for t in todos[:15]:
                sections.append(t)

    # What to tell the next session
    sections.append("\n## Continuation Notes")
    sections.append("_(Add your notes here before starting a new session)_")

    output = "\n".join(sections)
    return _truncate(output, args.max_chars)


# ═══════════════════════════════════════════════════════════════════════════
#  3. ARCHITECTURE MAP — Compact class/function/import index
# ═══════════════════════════════════════════════════════════════════════════

def _extract_py_api(filepath: Path) -> Dict[str, list]:
    """Extract classes, functions, and imports from a Python file using AST."""
    result: Dict[str, list] = {"imports": [], "classes": [], "functions": [], "constants": []}

    try:
        source = filepath.read_text(errors="replace")
        tree = ast.parse(source)
    except (SyntaxError, Exception):
        return result

    for node in ast.iter_child_nodes(tree):
        # Imports
        if isinstance(node, ast.Import):
            for alias in node.names:
                result["imports"].append(alias.name)
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            names = ", ".join(a.name for a in node.names[:5])
            if len(node.names) > 5:
                names += f" +{len(node.names) - 5} more"
            result["imports"].append(f"{module}: {names}")

        # Classes
        elif isinstance(node, ast.ClassDef):
            bases = ", ".join(
                getattr(b, "id", getattr(b, "attr", "?"))
                for b in node.bases
            )
            methods = []
            for item in node.body:
                if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    if item.name.startswith("_") and item.name != "__init__":
                        continue
                    args = _format_args(item.args)
                    ret = ""
                    if item.returns:
                        ret = f" → {ast.dump(item.returns)}" if hasattr(ast, "dump") else ""
                        # Simplified return type
                        ret = _simplify_annotation(item.returns)
                    methods.append(f"    .{item.name}({args}){ret}")

            class_line = f"  class {node.name}"
            if bases:
                class_line += f"({bases})"
            result["classes"].append(class_line + ":")
            result["classes"].extend(methods)

        # Top-level functions
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if node.name.startswith("_"):
                continue
            args = _format_args(node.args)
            ret = _simplify_annotation(node.returns) if node.returns else ""
            prefix = "async " if isinstance(node, ast.AsyncFunctionDef) else ""
            result["functions"].append(f"  {prefix}def {node.name}({args}){ret}")

        # Constants (uppercase assignments)
        elif isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id.isupper():
                    # Get a compact repr of the value
                    try:
                        val = ast.literal_eval(node.value)
                        val_str = repr(val)
                        if len(val_str) > 60:
                            val_str = val_str[:57] + "..."
                        result["constants"].append(f"  {target.id} = {val_str}")
                    except Exception:
                        result["constants"].append(f"  {target.id} = ...")

    return result


def _format_args(args: ast.arguments) -> str:
    """Format function arguments compactly."""
    parts = []
    for arg in args.args:
        if arg.arg == "self":
            continue
        ann = _simplify_annotation(arg.annotation) if arg.annotation else ""
        parts.append(f"{arg.arg}{ann}")

    # Truncate if too many
    if len(parts) > 5:
        shown = ", ".join(parts[:4])
        return f"{shown}, +{len(parts) - 4} more"
    return ", ".join(parts)


def _simplify_annotation(node) -> str:
    """Get a compact string for a type annotation AST node."""
    if node is None:
        return ""
    try:
        if isinstance(node, ast.Name):
            return f": {node.id}"
        elif isinstance(node, ast.Constant):
            return f": {node.value}"
        elif isinstance(node, ast.Attribute):
            return f": {node.attr}"
        elif isinstance(node, ast.Subscript):
            base = _simplify_annotation(node.value).lstrip(": ")
            return f": {base}[...]"
        else:
            return ""
    except Exception:
        return ""


def cmd_archmap(args: argparse.Namespace) -> str:
    """Generate a compact architecture map of Python APIs."""
    root = Path(args.path).resolve()
    sections = []
    sections.append(f"# Architecture Map: {root.name}")

    py_files = _walk_files(root, extensions=PY_EXTS, max_files=100)
    if not py_files:
        return "No Python files found."

    for fp in sorted(py_files):
        rel = fp.relative_to(root)
        api = _extract_py_api(fp)

        # Skip files with no public API
        if not api["classes"] and not api["functions"] and not api["constants"]:
            continue

        sections.append(f"\n## `{rel}`")

        if api["imports"]:
            # Show only external imports (not stdlib)
            ext_imports = [i for i in api["imports"] if not i.startswith("__")]
            if ext_imports:
                sections.append(f"Imports: {', '.join(ext_imports[:10])}")
                if len(ext_imports) > 10:
                    sections.append(f"  +{len(ext_imports) - 10} more imports")

        if api["constants"]:
            sections.append("**Constants:**")
            for c in api["constants"][:15]:
                sections.append(c)

        if api["classes"]:
            sections.append("**Classes:**")
            for c in api["classes"]:
                sections.append(c)

        if api["functions"]:
            sections.append("**Functions:**")
            for f in api["functions"]:
                sections.append(f)

    output = "\n".join(sections)
    return _truncate(output, args.max_chars)


# ═══════════════════════════════════════════════════════════════════════════
#  4. DIFF SUMMARIZER — Recent changes report
# ═══════════════════════════════════════════════════════════════════════════

def cmd_diff(args: argparse.Namespace) -> str:
    """Summarize recent changes in the repo."""
    root = Path(args.path).resolve()
    sections = []

    project_name = root.name
    branch = _git(["branch", "--show-current"], str(root))
    sections.append(f"# Diff Summary: {project_name} ({branch or '?'})")

    # Shortlog
    shortlog = _git(
        ["log", f"-{args.commits}", "--oneline", "--no-decorate"],
        str(root),
    )
    if shortlog:
        sections.append(f"\n## Commits ({args.commits})\n```")
        sections.append(shortlog)
        sections.append("```")

    # Numstat
    numstat = _git(
        ["diff", "--numstat", f"HEAD~{args.commits}"],
        str(root),
    )
    if numstat:
        total_add = 0
        total_del = 0
        file_stats = []
        for line in numstat.splitlines():
            parts = line.split("\t")
            if len(parts) == 3:
                add = int(parts[0]) if parts[0] != "-" else 0
                rem = int(parts[1]) if parts[1] != "-" else 0
                total_add += add
                total_del += rem
                file_stats.append((add, rem, parts[2]))

        sections.append(f"\n## Line Changes: **+{total_add:,} / -{total_del:,}**")
        sections.append("```")
        # Sort by most changed
        for add, rem, fname in sorted(file_stats, key=lambda x: x[0] + x[1], reverse=True)[:20]:
            bar = "+" * min(add // 5, 20) + "-" * min(rem // 5, 10)
            sections.append(f"  +{add:<5} -{rem:<5}  {fname}  {bar}")
        if len(file_stats) > 20:
            sections.append(f"  ... +{len(file_stats) - 20} more files")
        sections.append("```")

    # New files
    changed = _git(["diff", "--name-status", f"HEAD~{args.commits}"], str(root))
    if changed:
        new_files = [l.split("\t")[1] for l in changed.splitlines() if l.startswith("A")]
        del_files = [l.split("\t")[1] for l in changed.splitlines() if l.startswith("D")]
        new_tests = [f for f in new_files if "test" in f.lower()]

        if new_files:
            sections.append(f"\n**New files ({len(new_files)}):** {', '.join(f'`{f}`' for f in new_files[:10])}")
        if del_files:
            sections.append(f"**Deleted ({len(del_files)}):** {', '.join(f'`{f}`' for f in del_files[:10])}")
        if new_tests:
            sections.append(f"**New test files:** {', '.join(f'`{f}`' for f in new_tests)}")

    # Uncommitted
    status = _git(["status", "--short"], str(root))
    if status:
        lines = status.splitlines()
        sections.append(f"\n## Uncommitted: {len(lines)} file(s)")
        for l in lines[:10]:
            sections.append(f"  {l}")
    else:
        sections.append("\n## Working tree: clean ✓")

    output = "\n".join(sections)
    return _truncate(output, args.max_chars)


# ═══════════════════════════════════════════════════════════════════════════
#  5. TODO SCANNER — Cross-project TODO/FIXME/HACK finder
# ═══════════════════════════════════════════════════════════════════════════

def cmd_todos(args: argparse.Namespace) -> str:
    """Scan for TODO/FIXME/HACK/XXX across one or more project directories."""
    # Match both # comments (Python/Shell) and // comments (JS/TS)
    PATTERNS = re.compile(
        r"(?:#|//)\s*(TODO|FIXME|HACK|XXX|NOTE|OPTIMIZE|REFACTOR)\b[:\s]*(.*)",
        re.IGNORECASE,
    )
    SCAN_EXTS = PY_EXTS | {".js", ".ts", ".tsx", ".jsx"}

    paths = [Path(p).resolve() for p in args.paths]
    all_todos: Dict[str, List[Tuple[str, int, str, str]]] = defaultdict(list)

    for root in paths:
        py_files = _walk_files(root, extensions=SCAN_EXTS, max_files=500)
        for fp in py_files:
            try:
                for i, line in enumerate(fp.read_text(errors="replace").splitlines(), 1):
                    m = PATTERNS.search(line)
                    if m:
                        tag = m.group(1).upper()
                        text = m.group(2).strip() or line.strip()
                        rel = str(fp.relative_to(root))
                        all_todos[root.name].append((tag, i, rel, text))
            except Exception:
                pass

    if not any(all_todos.values()):
        return "No TODOs found across scanned directories."

    # Header (avoid "TODO" in string to prevent self-matching)
    sections = ["# " + "TODO" + " Scanner Results"]

    # Summary
    total = sum(len(v) for v in all_todos.values())
    tag_counts: Dict[str, int] = defaultdict(int)
    for items in all_todos.values():
        for tag, _, _, _ in items:
            tag_counts[tag] += 1

    sections.append(f"\n**Total: {total}** across {len(paths)} project(s)")
    tag_summary = " | ".join(f"{tag}: {cnt}" for tag, cnt in sorted(tag_counts.items(), key=lambda x: -x[1]))
    sections.append(f"Tags: {tag_summary}")

    # Per-project
    for project, items in sorted(all_todos.items()):
        sections.append(f"\n## {project} ({len(items)})")

        # Group by file
        by_file: Dict[str, List[Tuple[str, int, str]]] = defaultdict(list)
        for tag, lineno, relpath, text in items:
            by_file[relpath].append((tag, lineno, text))

        for filepath, entries in sorted(by_file.items()):
            sections.append(f"\n**`{filepath}`**")
            for tag, lineno, text in entries:
                # Truncate long lines
                if len(text) > 100:
                    text = text[:97] + "..."
                sections.append(f"  L{lineno} [{tag}] {text}")

    output = "\n".join(sections)
    return _truncate(output, args.max_chars)


# ═══════════════════════════════════════════════════════════════════════════
#  CLI
# ═══════════════════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(
        prog="copilot_toolkit",
        description="Developer tools for managing large projects across AI coding sessions.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    sub = parser.add_subparsers(dest="command", required=True)

    # -- context --
    p_ctx = sub.add_parser("context", help="Project context dump for onboarding Copilot")
    p_ctx.add_argument("path", help="Project root directory")
    p_ctx.add_argument("--commits", type=int, default=10, help="Recent commits to show (default: 10)")
    p_ctx.add_argument("--depth", type=int, default=3, help="Max tree depth (default: 3)")
    p_ctx.add_argument("--max-chars", type=int, default=12_000, help="Max output chars (default: 12000)")

    # -- handoff --
    p_ho = sub.add_parser("handoff", help="Session handoff document from recent changes")
    p_ho.add_argument("path", help="Project root directory")
    p_ho.add_argument("--commits", type=int, default=5, help="Commits to include (default: 5)")
    p_ho.add_argument("--max-chars", type=int, default=12_000, help="Max output chars")

    # -- archmap --
    p_am = sub.add_parser("archmap", help="Compact architecture map (classes, functions, imports)")
    p_am.add_argument("path", help="Directory to scan (can be a subdirectory)")
    p_am.add_argument("--max-chars", type=int, default=8_000, help="Max output chars (default: 8000)")

    # -- diff --
    p_diff = sub.add_parser("diff", help="Summarize recent changes")
    p_diff.add_argument("path", help="Project root directory")
    p_diff.add_argument("--commits", type=int, default=5, help="Commits to summarize (default: 5)")
    p_diff.add_argument("--max-chars", type=int, default=8_000, help="Max output chars")

    # -- todos --
    p_td = sub.add_parser("todos", help="Scan TODOs/FIXMEs across projects")
    p_td.add_argument("paths", nargs="+", help="One or more project directories to scan")
    p_td.add_argument("--max-chars", type=int, default=8_000, help="Max output chars")

    args = parser.parse_args()

    dispatch = {
        "context": cmd_context,
        "handoff": cmd_handoff,
        "archmap": cmd_archmap,
        "diff": cmd_diff,
        "todos": cmd_todos,
    }

    output = dispatch[args.command](args)

    # Copy to clipboard on Windows if pyperclip is available
    copied = False
    try:
        import pyperclip
        pyperclip.copy(output)
        copied = True
    except ImportError:
        # Try Windows clip.exe fallback
        try:
            proc = subprocess.Popen(
                ["clip.exe"],
                stdin=subprocess.PIPE,
                text=True,
            )
            proc.communicate(input=output)
            if proc.returncode == 0:
                copied = True
        except Exception:
            pass

    print(output)

    line_count = output.count("\n") + 1
    char_count = len(output)
    if copied:
        print(f"\n{'='*60}")
        print(f"Copied to clipboard ({char_count:,} chars, ~{line_count} lines)")
        print(f"  Paste directly into your Copilot/GPT chat.")
    else:
        print(f"\n{'='*60}")
        print(f"  Output printed above ({char_count:,} chars). Copy and paste into your chat.")


if __name__ == "__main__":
    main()
