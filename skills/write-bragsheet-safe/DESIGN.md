# Write Brag-sheet Safely

## Goal

Preview and write the fixed CareerOS brag-sheet projection only after privacy, integrity, and destination-consent gates, then require exact CLI read-back verification.

## Non-goals

- Treat the sheet as the source of truth.
- Use unrestricted `USER_ENTERED` writes or mutate cells outside the owned projection window.
- Continue after privacy, consent, validation, write, or read-back failure.
- Claim success from an accepted write response alone.

## Inputs

- Valid local records.
- An exact canonical spreadsheet ID, sheet name, and start row.
- A scoped destination grant for `write:bragsheet`.

## Outputs

- A deterministic preview before mutation.
- One bounded RAW projection write followed by exact read-back comparison.
- `synced` only when the CLI reports an exact match; otherwise a blocked or reconciliation-required result.

## Voice/Tone

Calm and explicit about the destination, row count, consent scope, and verification state.

## Open questions

- Which CLI option will present the preview separately from the authorized write?
