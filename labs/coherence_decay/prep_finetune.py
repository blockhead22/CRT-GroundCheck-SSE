"""Prepare fine-tuning data from BDG audit results.

Extracts (function_source, tree_json) pairs from audit_bdg.jsonl
and formats them for Ollama fine-tuning.
"""

import json
from pathlib import Path

import builtins
_real_open = builtins.open

LOG_FILE = Path(__file__).parent / "results" / "raw" / "audit_bdg.jsonl"
OUTPUT_FILE = Path(__file__).parent / "results" / "finetune_trees.jsonl"

# Source files for extracting function source
SOURCE_FILES = {
    "heartbeat_executor.py": r"D:\AI_round2\personal_agent\heartbeat_executor.py",
    "governance_bridge.py": r"D:\AI_round2\personal_agent\governance_bridge.py",
}


def load_sources():
    """Load source files into memory."""
    sources = {}
    for name, path in SOURCE_FILES.items():
        with _real_open(path) as f:
            sources[name] = f.readlines()
    return sources


def extract_function_source(sources, file_name, lines_str):
    """Extract function source from line range."""
    if file_name not in sources:
        return None
    try:
        start, end = lines_str.split("-")
        start = int(start) - 1  # 0-indexed
        end = int(end)
        return "".join(sources[file_name][start:end])
    except (ValueError, IndexError):
        return None


def main():
    sources = load_sources()

    with _real_open(LOG_FILE) as f:
        entries = [json.loads(line) for line in f if line.strip()]

    training_pairs = []

    for entry in entries:
        tree = entry.get("tree")
        if not tree or "branches" not in tree:
            continue

        file_name = entry.get("file", "")
        lines = entry.get("lines", "")
        func_name = entry.get("function", "")

        source = extract_function_source(sources, file_name, lines)
        if not source:
            continue

        # Truncate very large functions
        if len(source) > 8000:
            half = 3500
            source = source[:half] + "\n... [truncated] ...\n" + source[-half:]

        # Format as Ollama training pair
        system = (
            "You are a code auditor. Generate a JSON reasoning tree for auditing Python functions. "
            "Focus on crashes, data corruption, resource leaks, and security vulnerabilities. "
            "Output ONLY valid JSON."
        )

        prompt = (
            f"Generate a reasoning tree for auditing this Python function:\n\n"
            f"```python\n{source}\n```\n\n"
            f"Output a JSON object with 'branches', each containing 'category', "
            f"'risk_hypothesis', and 'leaves' with 'question', 'safe_answer', 'unsafe_answer'."
        )

        # Clean tree — remove findings, keep only the tree structure
        clean_tree = {"branches": tree["branches"]}

        training_pairs.append({
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": prompt},
                {"role": "assistant", "content": json.dumps(clean_tree, indent=2)},
            ],
            "metadata": {
                "function": func_name,
                "file": file_name,
                "lines": lines,
            }
        })

    # Write training data
    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    with _real_open(OUTPUT_FILE, "w") as f:
        for pair in training_pairs:
            f.write(json.dumps(pair) + "\n")

    print(f"Prepared {len(training_pairs)} training pairs")
    print(f"Output: {OUTPUT_FILE}")

    # Stats
    total_branches = sum(
        len(json.loads(line)["messages"][2]["content"].replace("```json", "").replace("```", ""))
        for line in _real_open(OUTPUT_FILE)
        if line.strip()
    ) if False else "N/A"

    branch_counts = []
    leaf_counts = []
    for pair in training_pairs:
        tree = json.loads(pair["messages"][2]["content"])
        branch_counts.append(len(tree.get("branches", [])))
        leaf_counts.append(sum(len(b.get("leaves", [])) for b in tree.get("branches", [])))

    print(f"Branches per tree: min={min(branch_counts)}, max={max(branch_counts)}, avg={sum(branch_counts)/len(branch_counts):.1f}")
    print(f"Leaves per tree: min={min(leaf_counts)}, max={max(leaf_counts)}, avg={sum(leaf_counts)/len(leaf_counts):.1f}")


if __name__ == "__main__":
    main()
