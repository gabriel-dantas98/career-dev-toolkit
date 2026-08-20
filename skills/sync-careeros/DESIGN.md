# Sync CareerOS

## Goal

Run a bounded CareerOS sync through preview, privacy, consent, external write, and exact read-back verification while preserving explicit reconciliation state.

## Non-goals

- Infer connector, destination, or background consent from another grant.
- Start unattended sync without a separate background grant.
- Retry without bounds, double-write within one run, or overlap an active job.
- Mark a partial or mismatched write as synced.

## Inputs

- A named foreground or background job with bounded sources and destination.
- Connector, destination, and, when unattended, background grants.
- Valid local records and a configured gateway.

## Outputs

- The CLI preview and gate results.
- One idempotency key for each acquired run.
- `synced` only after exact read-back; otherwise blocked, already-running, or reconciliation-required state.

## Voice/Tone

Operational and concise. Identify the failed gate or state without echoing private source content.

## Open questions

- Which CLI status command will summarize the last reconciliation-required run?
