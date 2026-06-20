# Holden Slot-Request Inference Contract

Status: frozen before inference ablation  
Frozen: 2026-06-19

## Input

- user question;
- available slot names from the memory substrate schema/catalog;
- no expected answer;
- no benchmark probe name;
- no model name;
- no memory values.

## Output

```json
{
  "status": "resolved | ambiguous | unknown",
  "contract_kind": "current | history | policy | withhold | general",
  "requested_slots": ["slot_name"],
  "confidence": 0.0,
  "candidates": [
    {"slot": "slot_name", "score": 0.0, "signals": ["..."]}
  ],
  "reason_code": "..."
}
```

## Rules

- Slot selection uses slot names, generic aliases, question wording, and
  contract cues.
- It must not inspect stored values or expected benchmark tokens.
- It must not use model-name-specific rules.
- One slot may be resolved in this phase.
- A low-margin result must return `ambiguous`.
- No credible result must return `unknown`.
- `ambiguous` and `unknown` block automatic slot fetching.
- Policy slots require action/policy cues, not merely one overlapping word.
- History contracts require temporal cues such as `before`, `previous`,
  `formerly`, or `used to`.

## Frozen Thresholds

- minimum resolved score: `0.58`;
- minimum winning margin: `0.12`;
- ambiguous candidates returned: at most three.

## Ablation

Run inference over the six post-profile bounded-fetch cases and compare against
the previously declared oracle slots.

Success for this first extraction:

- at least five of six slots resolved correctly;
- zero confidently wrong slots;
- any unresolved case is explicitly ambiguous or unknown;
- all inferred contract kinds correct;
- no frozen case or profile changes.

The ambiguous case is more informative than a forced wrong fetch.

