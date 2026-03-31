"""Code Intelligence Agent — Analyzes codebase structure using the orchestrator.

Modes:
  1. file_map: Read a file, summarize every function/class, note dependencies
  2. trace: For a specific function, find all callers and callees across the codebase
  3. full_audit: Map a file + trace all its public functions + write structured doc
  4. detect: Find dead code, circular deps, undocumented functions, inconsistencies

Usage:
    python personal_agent/code_intel.py file_map personal_agent/crt_memory.py
    python personal_agent/code_intel.py trace personal_agent/crt_memory.py update_trust
    python personal_agent/code_intel.py full_audit personal_agent/memory_graph.py
"""

import os
import sys
import io
import json
import time

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
os.environ.setdefault("OLLAMA_BASE_URL", "http://localhost:11434")


# ---------------------------------------------------------------------------
# Prompt templates for each mode
# ---------------------------------------------------------------------------

FILE_MAP_PROMPT = """Analyze this Python file and produce a structured code map.

For EACH class and function defined in this file, provide:
1. Name and type (class/method/function)
2. Line number (approximate from the content)
3. One-line purpose
4. Parameters and return type (if discernible)
5. Key dependencies (what it imports or calls)

Format as a structured list. Be thorough — don't skip private methods.
Group methods under their parent class.

File: {file_path}
"""

TRACE_PROMPT = """I need to trace the function `{function_name}` defined in `{file_path}`.

I've already read the file and found the function. Now I need you to:
1. Search the codebase for every file that CALLS this function
2. Search for every function/method that THIS function calls internally
3. Build a caller/callee map

Use search_code to find references. Search for:
- "{function_name}(" to find callers
- Look at the function body (already provided) for what it calls

Produce a structured trace showing:
- WHO calls this function (file:line)
- WHAT this function calls (function_name → file)
- Any circular dependencies detected
"""

FULL_AUDIT_PROMPT = """Perform a full code audit of {file_path}.

Step 1: Read the file and map every class/function
Step 2: For each PUBLIC function (not starting with _), search for callers across the codebase
Step 3: Identify:
  - Dead code (public functions with zero external callers)
  - Undocumented functions (no docstring)
  - Functions with high fan-out (calls many other functions)
  - Any inconsistencies between function names and what they actually do

Write the complete audit report to workspace/audit_{file_name}.md

Be thorough but concise. Focus on actionable findings.
"""

DETECT_PROMPT = """Analyze this code for potential issues:

File: {file_path}

Look for:
1. Logic errors or potential bugs
2. Contradictions between comments and code behavior
3. Error handling gaps (bare except, swallowed errors)
4. Security concerns (hardcoded secrets, SQL injection, path traversal)
5. Performance issues (O(n²) in hot paths, unnecessary recomputation)
6. Dead imports
7. Type mismatches or None-safety issues

For each finding, specify:
- Severity: high/medium/low
- Line (approximate)
- Description
- Suggested fix

Be specific. Don't flag style issues — focus on correctness and safety.
"""


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------

def run_code_intel(mode: str, file_path: str, function_name: str = None):
    """Run the code intelligence agent in the specified mode."""
    from personal_agent.cookie_orchestrator import Orchestrator, ClaudeCliBrain

    # Resolve file path
    if not os.path.isabs(file_path):
        file_path = os.path.relpath(file_path)

    file_name = os.path.basename(file_path).replace(".py", "")

    if mode == "file_map":
        objective = FILE_MAP_PROMPT.format(file_path=file_path)
        objective += f"\n\nFirst, read the file using file_read, then analyze it and respond with the map."

    elif mode == "trace":
        if not function_name:
            print("ERROR: trace mode requires a function name")
            return
        objective = TRACE_PROMPT.format(
            function_name=function_name,
            file_path=file_path,
        )
        objective += f"\n\nStart by reading {file_path} to see the function, then use search_code to find callers."

    elif mode == "full_audit":
        objective = FULL_AUDIT_PROMPT.format(
            file_path=file_path,
            file_name=file_name,
        )

    elif mode == "detect":
        objective = DETECT_PROMPT.format(file_path=file_path)
        objective += f"\n\nFirst read the file, then analyze and respond with findings."

    else:
        print(f"Unknown mode: {mode}. Available: file_map, trace, full_audit, detect")
        return

    print(f"\n{'#'*70}")
    print(f"# CODE INTEL: {mode}")
    print(f"# File: {file_path}")
    if function_name:
        print(f"# Function: {function_name}")
    print(f"{'#'*70}")

    orch = Orchestrator(brain=ClaudeCliBrain(), max_iterations=12)
    t0 = time.perf_counter()

    for event in orch.run(objective):
        etype = event.get("type", "")
        if etype == "thinking":
            print(f"  💭 {event['content'][:300]}")
        elif etype == "tool_call":
            tool = event["tool"]
            args = str(event.get("args", ""))[:80]
            status = event["status"]
            print(f"  🔧 {tool}({args}) → {status}")
            if tool == "search_code" and event.get("result"):
                # Show search results compactly
                lines = event["result"].split("\n")[:5]
                for l in lines:
                    print(f"     {l[:120]}")
                if len(event["result"].split("\n")) > 5:
                    print(f"     ... ({len(event['result'].split(chr(10)))} total matches)")
        elif etype == "response":
            print(f"\n{'='*60}")
            print("RESULT:")
            print(f"{'='*60}")
            print(event["content"])
        elif etype == "done":
            elapsed = time.perf_counter() - t0
            print(f"\n  ✅ {event.get('steps', 0)} steps, {elapsed:.1f}s total")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python code_intel.py <mode> <file_path> [function_name]")
        print("Modes: file_map, trace, full_audit, detect")
        print("\nExamples:")
        print("  python code_intel.py file_map personal_agent/memory_graph.py")
        print("  python code_intel.py trace personal_agent/crt_memory.py update_trust")
        print("  python code_intel.py full_audit personal_agent/memory_graph.py")
        print("  python code_intel.py detect personal_agent/crt_critic.py")
        sys.exit(1)

    mode = sys.argv[1]
    file_path = sys.argv[2]
    func_name = sys.argv[3] if len(sys.argv) > 3 else None

    run_code_intel(mode, file_path, func_name)
