#!/usr/bin/env python3
"""SessionStart hook: keep aether-core current.

Runs `pip install -U --no-deps aether-core` quietly. Skips deps so we
don't churn torch / sentence-transformers on every startup. Logs to
stderr so it shows in Claude Code's hook output panel without
polluting the conversation.

Failures are silent — never block session start.
"""

from __future__ import annotations
import subprocess
import sys


def main() -> int:
    try:
        result = subprocess.run(
            [sys.executable, "-m", "pip", "install",
             "-U", "--no-deps", "--quiet", "aether-core"],
            capture_output=True,
            text=True,
            timeout=25,
        )
        if result.returncode == 0:
            # Detect whether anything was actually upgraded
            if "Successfully installed" in (result.stdout + result.stderr):
                print("[aether] upgraded aether-core", file=sys.stderr)
            # Otherwise silent — no upgrade needed
        else:
            # pip exit non-zero — log but don't block
            print(f"[aether] upgrade check failed (rc={result.returncode}); "
                  f"continuing with installed version", file=sys.stderr)
    except subprocess.TimeoutExpired:
        print("[aether] upgrade check timed out; continuing", file=sys.stderr)
    except Exception as e:
        print(f"[aether] upgrade check error: {e}; continuing", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
