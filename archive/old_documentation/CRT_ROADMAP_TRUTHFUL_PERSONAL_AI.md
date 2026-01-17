# Roadmap: a personal AI that learns and grows with you — but won’t lie

You don’t get “won’t lie” by making the model smarter; you get it by making truthfulness a *product constraint* and forcing all personalization/learning to flow through that constraint.

## 1) Define the truth contract (non‑negotiables)
- Never assert as fact without support.
  - Support = retrieved memory text, user-provided fact, or explicitly cited source.
- If unsupported: ask, abstain, or label as speculation.
- If conflict: don’t overwrite; reconcile via clarification + ledger.

## 2) Build the two‑lane architecture (core)
- **Belief lane**: what the system is allowed to *store and treat as true* (facts with provenance + timestamps + trust).
- **Speech lane**: what the system can *say* to be helpful, but must label when it’s not grounded.
- Enforce: belief updates only via explicit user input / consent signals.

## 3) Make memory safe, consented, and auditable
- Memory schema should include: `{slot/value, source, timestamp, confidence, trust, provenance, revocable}`.
- UX primitives: “store this”, “forget that”, “show me what you know about me”, “why did you say that”.

## 4) Grounding enforcement (anti‑lie engine)
- Gates like: if answer contains named entities not present in prompt+retrieved memory, either cite or downgrade to uncertainty.
- Require citation mode for “from our chat / I remember” claims.

## 5) Contradiction handling as a first‑class workflow
- Hard conflicts create a ledger entry + a single clarifying question.
- Once clarified, resolve ledger and propagate to belief lane with a new “latest truth” record (don’t delete history).

## 6) Learning that “grows with you” (without becoming a bullshitter)
- Learn preferences, goals, and stable personal facts aggressively (because they’re user-supplied).
- Learn strategies (what helps the user) as metadata/suggestions, not as new “world facts”.
- Attach learning to a traceable event: “you told me X” / “you approved storing Y”.

## 7) Prove it continuously with batches + metrics
- Track rates: memory-claim hallucination, contradiction-on-question, gate-trigger accuracy, “uncertainty when warranted”.
- Run adversarial campaigns regularly (multi-run, seeded) and block merges on regressions.

## 8) Background learning + background research (without lying)
Background learning is viable **if** it only writes into safe, provenance-tagged memory and never upgrades “research” into personal facts without user confirmation.

Recommended pipeline:
- **Capture**: background jobs gather candidate notes (read-only page text, snippets, summaries).
- **Normalize**: convert into structured artifacts with URLs/timestamps.
- **Store as low-trust**: write into memory as *research notes* (not user facts), with provenance.
- **Promote by consent**: only promote to stable facts/preferences when the user explicitly approves.

## 9) Browser bridge (Tampermonkey + local server)
If you want the AI to do “live research” in the browser, use a **local-only** bridge:
- Browser (Tampermonkey userscript) connects to `ws://127.0.0.1`.
- Server requires a shared token + domain allowlist.
- Default to read-only commands; require user confirmation for click/type/navigate.

See: `BROWSER_BRIDGE_README.md`.
