# .aether/

This directory is the project's belief substrate. It records facts about
this codebase that survive across sessions and developers.

## What lives here

- `state.json` — the substrate. Memories, edges, Belnap states.
- `state_trust_history.json` — append-only log of every trust change.
- `state_embeddings.npz` — sentence-transformers vectors (if [ml] is installed).

## Sharing with your team

Commit `state.json` and `state_trust_history.json` to git. Onboarding a
new developer pulls the project's accumulated decisions for free.

Don't commit `state_embeddings.npz` — it's regenerated from text on
demand, costs cycles to load, and can be huge. Add it to `.gitignore`
(this `init` already did that for you).

## Working with it

In any agent client that speaks MCP (Claude Code, Cursor, Cline, etc.),
the aether-core MCP server will discover this directory automatically
when started from anywhere inside the project tree. Tools like
`aether_remember`, `aether_search`, `aether_sanction`, `aether_fidelity`
will read and write here instead of the user-global substrate at
`~/.aether/mcp_state.json`.

To force the user-global substrate instead, set
`AETHER_NO_REPO_DISCOVERY=1`.
