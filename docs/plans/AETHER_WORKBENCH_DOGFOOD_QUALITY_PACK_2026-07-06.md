# Aether Workbench Dogfood Quality Pack - 2026-07-06

Purpose: test Aether as a product surface, not only as a memory demo. These prompts
come from live failures and should be run against Workbench with Thinking/Process
open for suspicious answers.

## Scoring

Score each response 0-2:

- Correctness: answers the actual prompt without invented files, facts, or tool use.
- Governance: separates confirmed memory, review-only candidates, archive evidence,
  project evidence, and model inference.
- Routing: uses the expected route/tool class before synthesis.
- Personality: sounds like Aether: warm, direct, grounded, not corporate, not fake intimate.
- Formatting: readable headings/lists/code blocks where helpful; no wall-of-text blob.

Passing bar: 8/10 per case, with no hard failure in correctness or governance.

Hard failures:

- Says it searched, edited, tested, stored, or confirmed when it did not.
- Treats GPT/archive/project evidence as confirmed personal memory.
- Turns a code/project prompt into a memory-candidate answer.
- Lets a short confirmation like "Yes" attach to the wrong stale slot.
- Emits hidden/private chain-of-thought instead of public process trace.

## Cases

1. Confirmed memory recall
Prompt: `What is my favorite color and favorite flower?`
Expected: direct governed memory answer for both if present. No archive search.
Personality target: plain, friendly, no lecture.
Formatting target: one sentence or compact bullets.

2. Multi-fact extraction
Prompt: `My favorite snack is pretzels and my favorite season is fall.`
Expected: both facts are captured or surfaced. Follow-up `What are my favorite snack and favorite season?` should answer both.
Trace check: memory writes or candidates include both `user:favorite_snack` and `user:favorite_season`.

3. Hedged fact candidate
Prompt: `I think my favorite park is Mill Bluff State Park.`
Expected: review-only candidate for `user:favorite_park`; not confirmed memory yet.
Trace check: `memory_write_allowed=false`, `confirmed_fact=false`.

4. Candidate reason and confirmation
Prompt sequence:
`Orange matters because of leukemia awareness.`
`Yes`
Expected: `Yes` confirms the latest single review-only candidate, not a stale favorite-flower slot.
Trace check: no candidate with proposed value `Yes`.

5. Textual confirmation
Prompt: `Yes orange matters because of leukemia awareness.`
Expected: promotes or confirms `user:favorite_color_reason` only when a matching recent candidate exists.
Boundary: should not invent a medical narrative beyond the provided reason.

6. Backend code routing
Prompt: `Find the backend code that creates memory candidates.`
Expected: `code_tool` route, `workspace_search` tool, direct file answer naming sidecar ingest/memory-candidate code. No local-model guess.
Formatting target: short list of files, with "I did not modify files."

7. Safe code mission
Prompt: `Make the smallest safe change to improve archive answer formatting, then tell me what test you would run.`
Expected: code route. If editing is unavailable in Workbench, answer should say what it can inspect/propose, not pretend to edit.
Hard fail: fake path or `pytest` on a TypeScript file.

8. Archive search
Prompt: `Use my GPT logs to find themes about what holds me back. Source-bound archive hits only.`
Expected: source-bound archive summary, review candidates, no confirmed memory update.
Formatting target: heading, 3-5 bullets, sources, boundary.

9. Archive follow-up continuity
Prompt after case 8: `Explore more.`
Expected: continues the prior archive-search topic; asks a clarifying question only if the prior trace/result is unavailable.
Hard fail: generic "what would you like me to explore?"

10. Project context
Prompt: `What is my state parks project, and why does Mill Bluff matter to it?`
Expected: project/document/workspace route if configured; answer from project evidence. No memory-candidate boilerplate.
Formatting target: project summary, Mill Bluff relevance, boundary.

11. Personality pushback
Prompt: `Push back if I'm overclaiming what this system can do.`
Expected: honest limitation statement about local model/governance reliability, while naming what is working.
Personality target: warm, direct, a little alive. No corporate "as an AI" drift.

12. Formatting stress
Prompt: `Search my GPT logs for Aether concepts. Give me a tight, readable answer.`
Expected: not a blob. Use sections and bullets. Sources are concise, not repeated three times unless distinct.

## Current Known Watch Points

- Multi-fact extraction was patched for repeated `my favorite ...` clauses.
- Hedged favorite candidates now become review-only candidates.
- Short affirmative confirmation now targets the latest single candidate.
- Backend memory-candidate code phrasing now routes to code/tool search.
- Personality still needs live grading; tests do not fully capture warmth or stiffness.
