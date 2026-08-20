# CareerOS Full Pipeline

## Goal

Transform Career Dev Toolkit from a capture-only packaging slice into local-first career infrastructure that can harvest evidence, validate it deterministically, persist it encrypted, project it safely into Google Sheets and Docs, and deploy a CareerOS timeline.

The product follows this pipeline:

```text
harvest -> normalize -> privacy gate -> validate -> encrypted local store
        -> preview -> authorized sync -> read-back verification -> deploy
```

It adapts Tapioca's Google Apps Script browser-mode mechanism while remaining self-contained. End users do not need a GCP project, API keys, the Tapioca plugin, or terminal interaction. Claude Code, Cursor, and Codex discover the same skills and invoke the same Python runtime.

## Non-goals

- Treat Google Sheets as the source of truth.
- Infer metrics, ownership, dates, causality, Jira relationships, or impact.
- Send a full thread or mailbox to an external model.
- Bypass a privacy, consent, integrity, or read-back failure to keep syncing.
- Depend on Tapioca at runtime.
- Reproduce the existing QuintoAndar HTML artifact as a generic product surface.
- Support arbitrary CRM, HRIS, Slack, or issue-tracker providers in the first connector release.

## Inputs

- Current agent thread, provided explicitly to the CLI as a bounded excerpt.
- GitHub evidence collected through authenticated `gh` read operations.
- Google Calendar events, Gmail messages, Drive files, Docs, and Sheets accessed through one user-deployed Apps Script web app.
- Existing local CareerOS records.
- User configuration for review periods, taxonomy aliases, authorized destinations, connector scopes, and background synchronization.

## Outputs

- Versioned local delivery, evidence, event, kudos, credential, and sync records in an encrypted SQLite database.
- Deterministic validation reports with machine-readable rule identifiers.
- Safe, idempotent brag-sheet writes followed by read-back verification.
- A promotion packet containing 10–12 work cards with community contributions collapsed separately.
- Timeline data, homepage configuration, and deploy metadata for the Apps Script web app.
- Sanitized eval artifacts proving the pipeline behavior without containing private source content.

## Architecture

### Shared Python core

`careeros/` is a Python package with one CLI entry point:

```text
python -m careeros <command>
```

The package is split by responsibility:

- `privacy`: fail-closed content scanning and bounded excerpts.
- `crypto`: SQLCipher connection and keychain-backed key lifecycle.
- `store`: schema migrations and repositories.
- `consent`: destination grants, connector grants, background grants, and revocation.
- `dates`: Brazilian period parsing, quarter derivation, clamped sorting, and multi-quarter expansion.
- `taxonomy`: delivery prefixes, confidence caps, context classification, and kudos requirements.
- `validation`: brag-sheet integrity, epic-tree deduplication, evidence consistency, and policy checks.
- `connectors`: thread, GitHub, and Apps Script gateway adapters.
- `harvest`: normalization, provenance tracking, and deterministic deduplication.
- `sync`: preview, safe serialization, write, read-back, and reconciliation.
- `outputs`: promotion packet, timeline model, homepage model, and evidence enrichment.
- `jobs`: foreground orchestration and background lock/retry state.
- `deploy`: clasp health, deployment update, and real web-app URL registration.

Imports point inward to domain contracts. Connectors and storage do not depend on skill prompts.

### Thin portable skills

Skills are user-facing workflows over the CLI:

- `harvest-retrospective`
- `validate-bragsheet-integrity`
- `write-bragsheet-safe`
- `deploy-careeros-timeline`
- `build-promo-packet`
- `sync-careeros`

Smaller backlog capabilities such as taxonomy, date handling, deduplication, event-date resolution, kudos harvesting, homepage generation, and enrichment are CLI commands and libraries used by these workflows. This avoids exposing a separate skill for every implementation detail while preserving independently testable contracts.

All three platform manifests point at `skills/`; platform-specific files contain discovery metadata only.

### Encrypted canonical store

The canonical store is SQLite encrypted through a SQLCipher-capable DB-API driver. A random 256-bit database key is generated locally and stored in the operating-system credential store through Python `keyring`.

Startup fails closed when:

- SQLCipher support is unavailable;
- the keychain is locked or unavailable;
- the database cannot prove cipher support;
- migrations are newer than the runtime;
- file permissions are broader than user-only where the OS supports that check.

There is no plaintext fallback. Tests use an in-memory fake keyring and synthetic records.

### Consent model

Consent is scoped and revocable:

- connector grant: which Google/GitHub sources may be read;
- destination grant: which exact spreadsheet/document may receive which projection;
- background grant: whether a named job may run unattended, its schedule, sources, and destination.

A destination is authorized once and may subsequently sync without per-batch confirmation. The user still receives a deterministic preview and result report. Background synchronization requires an additional grant and cannot be inferred from a destination grant.

Revocation takes effect before the next external call. Grants are stored encrypted and identified by normalized resource IDs, never by ambiguous display names.

### Google Apps Script gateway

One Apps Script web app provides Calendar, Gmail, Drive/Docs, Sheets, and deployment metadata actions. This deliberately accepts a broad Google authorization surface, as selected, but limits each request through:

- a fixed action allowlist;
- bounded query windows and result counts;
- explicit resource IDs;
- read/write capability checks;
- request nonce and timestamp validation;
- no generic method dispatch or arbitrary Apps Script evaluation;
- minimal response fields;
- structured errors that never echo credentials or full source bodies.

Onboarding follows Tapioca's browser-mode pattern:

1. resolve the packaged runtime;
2. run local setup and status checks;
3. deploy/update with `clasp` when authenticated, otherwise guide the user through Apps Script UI one step at a time;
4. open a dedicated browser profile for Google authorization;
5. register the real `/exec` URL;
6. perform a synthetic health check;
7. store connector consent only after the check succeeds.

The local browser client uses POST, bounded retries for transient Google interstitials, and accepts only JSON-shaped responses.

## Canonical data contracts

Every harvested item records:

- stable local ID;
- type and schema version;
- source connector and immutable source locator;
- source timestamps and observed-at timestamp;
- bounded evidence excerpts or links;
- normalized title, period, tags, context, and confidence;
- STAR fields where applicable;
- evidence gaps;
- content fingerprint for deduplication;
- supersession and sync state.

The local ID is never derived solely from mutable prose. Connector-native IDs are namespaced. Cross-source deduplication uses normalized evidence keys and records merge provenance instead of deleting source observations.

## Backlog mapping

### P0

- `harvest-retrospective`: connector orchestration, normalization, provenance, dedup.
- `write-bragsheet safe`: apostrophe-safe ambiguous periods, raw writes, and read-back.
- `validate-bragsheet-integrity`: title/tags, Jira uniqueness, GitHub PR status/narrative, impact/evidence links.
- `delivery-taxonomy`: prefixes, confidence caps, kudos name/month.
- `deploy-careeros-timeline`: clasp health, real `webAppUrl`, homepage registration.

### P1

- shared date library;
- epic-tree dedup validator;
- promotion packet builder;
- Calendar -> Gmail -> Luma-style fallback contract, with Luma connector deferred but represented as unavailable rather than fabricated;
- Gmail kudos harvesting;
- timeline UI data contract;
- Sheets homepage generator.

### P2

- hero metrics policy;
- talk evidence enrichment;
- leader review pass;
- timeline parity check;
- extended capture-delivery schema;
- external credential enrichment.

The Luma network connector remains an extension point because the selected first release sources are thread, GitHub, and Google. `resolve-event-dates` reports an unresolved result after Calendar and Gmail rather than silently pretending Luma was queried.

## Data flow

1. The skill requests only the minimum source window required.
2. The connector grant and privacy preflight are checked.
3. Raw provider responses are reduced immediately to typed observations.
4. Observations are normalized and deduplicated.
5. Deterministic validators produce errors, warnings, and evidence gaps.
6. Valid records are written transactionally to the encrypted store.
7. A projection preview is generated.
8. Destination consent is checked immediately before the network write.
9. Ambiguous periods are serialized as literal text; no unrestricted `USER_ENTERED` write is allowed.
10. The written ranges are read back and compared to the intended canonical values.
11. Sync state advances only after an exact semantic match.

## Error handling

- Privacy, consent, encryption, validation, and read-back errors are terminal for the affected operation.
- Provider authentication expiry pauses the job and requests reauthorization without discarding local state.
- Transient HTTP/browser errors use bounded exponential backoff.
- Background jobs use an exclusive lock and idempotency key; overlapping runs exit cleanly.
- Partial external writes remain `reconciliation_required` and are never marked synced.
- Destructive sheet, document, or deployment operations require a separately named capability even when the destination is authorized.
- User-facing errors identify the failed rule and remediation without reproducing sensitive input.

## Testing and evaluation

Behavior is built test-first.

Deterministic tests cover:

- privacy fail-closed behavior;
- SQLCipher/keychain startup and no-plaintext fallback;
- consent grant, scope, and revocation;
- date parsing and quarter behavior;
- taxonomy and every integrity validator;
- deduplication and provenance;
- safe period serialization and exact read-back;
- connector bounds and Apps Script action allowlist;
- foreground/background idempotency and locking;
- promo packet, timeline, homepage, and enrichment policies;
- skill and manifest parity.

The E2E eval runs against fake GitHub and Apps Script providers with synthetic canaries. It harvests overlapping evidence, rejects an invalid record, stores valid records, projects a brag sheet, verifies read-back, builds outputs, and emits a sanitized machine-readable report. A failure in any required stage makes the eval fail.

Live Google certification is separate and manual because it requires a user's Google account and broad OAuth approval. It must never be represented as passing from the fake-provider eval.

## Delivery sequence

1. Contracts, privacy, consent, encryption, and migrations.
2. Dates, taxonomy, deduplication, and validators.
3. Thread/GitHub/Google connector interfaces and harvest.
4. Safe projection and Apps Script gateway.
5. Timeline deployment and homepage.
6. Promotion packet and P2 policy passes.
7. Background scheduler.
8. Portable skills, docs, complete eval, and requirement audit.

Each slice lands with failing tests first, the smallest implementation that passes, and fresh full-suite verification before the next external-facing capability is claimed.

## Voice/Tone

Direct, calm, specific, and evidence-proportional. The product should sound like an honest self-review assistant, not a promotion scorer. It reports uncertainty and missing evidence plainly.

## Open questions

- A live Google account is required to certify actual OAuth and Apps Script deployment; CI can only prove the packaged gateway and fake-provider protocol.
- Luma remains a connector extension point until its explicit authentication and privacy contract is designed.
- Operating systems without a usable native keychain are unsupported rather than downgraded to plaintext storage.
