# CareerOS Python Runtime

## Goal

Provide a shared, deterministic Python runtime that exposes one CLI entry point (`python -m careeros`) and typed domain contracts consumed by portable skills and later pipeline stages.

## Non-goals

- Persist, encrypt, or sync data in this slice.
- Call external providers or bypass privacy gates.
- Infer metrics, ownership, dates, causality, or impact.
- Expose platform-specific behavior that diverges across Claude Code, Cursor, or Codex.

## Inputs

- CLI arguments for registered commands.
- Optional `--json` flag requesting machine-readable envelopes.

## Outputs

- `CommandResult` envelopes with deterministic JSON shape.
- Typed contracts: `DeliveryRecord`, `EvidenceRef`, and `ValidationIssue`.
- Structured nonzero errors for unknown commands.

## Voice/Tone

Direct, calm, and specific. Errors identify the failed rule or command without echoing sensitive input.

## Open questions

- Which additional commands register in Task 2+ without breaking the envelope contract?
- How will schema version bumps propagate through skills and eval artifacts?
