# Holden Selective Multi-Request Repair Contract

Status: frozen before implementation  
Frozen: 2026-06-19

## Trigger

Repair is allowed only when:

- planning coverage is complete;
- generation produced an answer;
- at least one request passed;
- at least one request failed the deterministic coverage gate.

## Procedure

1. Parse the answer into request-aligned segments.
2. Freeze passing segments verbatim.
3. Build a repair prompt containing only failed requests, their governed
   packets, and failed contract checks.
4. Generate one replacement segment per failed request.
5. Reassemble passing and repaired segments in original request order.
6. Run the complete coverage gate once.
7. Release only if every request passes.

## Limits

- Maximum repair generations: one.
- Passing segments may not be regenerated or edited.
- Failed-clause repair receives no unrelated governed state.
- No profile dose changes.
- No retrieval changes.
- No case, expected answer, or judge changes after repair output inspection.
- If parsing cannot align the original answer to requests, block rather than
  rewriting the entire answer.
- If the repaired answer still fails, block.

## Segment Format

The generator is instructed to produce:

```text
1. answer for request one
2. answer for request two
```

Accepted alignment:

- numbered lines;
- one non-empty line per request;
- fallback sentence segmentation only when the number of segments exactly
  matches the number of requests.

## Success Criteria

- Qwen's previously blocked compound answer is repaired and released;
- passing clause bytes remain unchanged through repair;
- repaired full-coverage rate reaches at least 15/16 and does not decrease;
- zero more than one repair call;
- zero incomplete answers released;
- severe policy failures remain zero.

