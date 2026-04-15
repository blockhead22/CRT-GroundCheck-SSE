"""DEPRECATED: crt_mcp_server is now merged into aether_mcp_server.

All crt_* tools (episodic memory, fact-checking, trust decay, learning stats,
session search) now live in aether_mcp_server.py alongside the aether_* tools.
One MCP server, one registration, one source of truth.

This shim exists only so the installed console script `crt-mcp` (from
pyproject.toml) keeps working without reinstall. It re-exports the merged
server's main entry point.

Old registration:
    "crt": { "command": "crt-mcp.exe" }
New registration (preferred):
    "aether": {
        "command": "python",
        "args": ["-m", "personal_agent.aether_mcp_server"]
    }

The old `crt-mcp` command still works — it just runs the full merged server.
"""

from personal_agent.aether_mcp_server import main, mcp  # noqa: F401

if __name__ == "__main__":
    main()
