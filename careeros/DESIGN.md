# CareerOS Python Runtime

## Goal

Provide a shared, deterministic Python runtime that exposes one CLI entry point (`python -m careeros`) and typed domain contracts consumed by portable skills and later pipeline stages. Task 2 adds fail-closed privacy scanning, SQLCipher-backed encrypted persistence, versioned migrations, and scoped revocable consent. Task 3 adds Brazilian date parsing, taxonomy classification, deterministic deduplication, and integrity validators.

## Non-goals

- Call external providers or bypass privacy gates.
- Infer metrics, ownership, dates, causality, or impact.
- Expose platform-specific behavior that diverges across Claude Code, Cursor, or Codex.
- Offer plaintext SQLite fallback or downgrade when SQLCipher or the OS keychain is unavailable.
- Infer background-job consent from destination or connector grants.

## Inputs

- CLI arguments for registered commands.
- Optional `--json` flag requesting machine-readable envelopes.
- Bounded text for `scan_sensitive(text)` privacy preflight.
- `StoreConfig` path and a keyring backend (`get_password` / `set_password` / `delete_password`).
- Consent grants keyed by grant type, canonical resource ID, and explicit scopes.
- Period strings with optional `reference_year` for yearless ranges.
- Delivery and kudos records plus an external evidence mapping keyed by record ID.
- Observations with namespaced `source_id`, Jira/PR/evidence keys, and provenance tuples.
- Bounded `CollectRequest` payloads for thread excerpts, GitHub `gh api` queries, and Google gateway actions.
- `HarvestRequest` observation batches normalized, deduplicated, validated, and persisted transactionally.

## Outputs

- `CommandResult` envelopes with deterministic JSON shape.
- Typed contracts: `DeliveryRecord`, `RecordMetadata`, `EvidenceRef`, and `ValidationIssue`.
- `PrivacyFinding` lists with category and span offsets, never echoing matched secret substrings.
- `EncryptedStore` backed by SQLCipher with migrated tables for records, evidence, grants, sync runs, and migrations.
- `ConsentService` grant, require, and revoke operations with destination, connector, and background isolation.
- `Connector.collect(request) -> tuple[Observation, ...]` from thread, GitHub, and Google adapters.
- `HarvestService.run(request) -> HarvestResult` with merged records, validation issues, and persist status.
- `StoreUnavailable` and `ConsentDenied` terminal errors that identify the failed rule without leaking keys or sensitive input.

## Privacy contract

- `scan_sensitive(text)` detects private keys, bearer tokens, GitHub tokens, API keys, and email addresses using deterministic patterns aligned with the eval privacy boundary.
- Findings return category, start, and end offsets only; serialized output must not reproduce matched values.

## Store contract

- Production connects exclusively through `sqlcipher3` via the `sqlcipher_driver` import boundary; stdlib `sqlite3` is test-only to prove refusal.
- A 256-bit key is generated locally, stored in the OS keychain under `careeros` / `db-key:<resolved-path>`, and validated as 64 lowercase hex characters before `PRAGMA key` interpolation (parameter binding is unsupported by the driver).
- Startup executes `PRAGMA key` immediately, requires a nonempty `PRAGMA cipher_version`, applies versioned migrations, and refuses when applied migration versions exceed runtime support.
- On POSIX, existing database files with group or world read/write bits fail closed; newly created files are chmod `0600`. Broad existing files are never silently repaired.
- Keychain, driver, cipher, migration, and permission failures map deterministically to `StoreUnavailable` without echoing key material. Connections are closed on every startup failure.

## Consent contract

- Grants are scoped by type (`destination`, `connector`, `background`), canonical resource ID, and explicit scope tuple.
- Resource IDs accept namespaced IDs (`sheet:…`, `doc:…`, `job:…`, `connector:…`) and Google Sheets/Docs URLs, extracting stable document IDs into `sheet:{id}` or `doc:{id}` form.
- Empty, ambiguous display names, and unsupported URL shapes raise `InvalidResourceId`.
- `require` re-checks grant presence, revocation state, and scope immediately before adapter use. Background jobs never inherit destination grants.

## Dates contract

- `parse_period(value, reference_year)` parses PT-BR day dates (`DD/MM/YYYY`), yearless month ranges (`jan–mar`), month precision (`mar 2026`), and quarters (`Q2 2026`).
- Invalid calendar dates (for example `31/02/2026`) are rejected; unsupported shapes raise `ValueError`.
- `quarters_for(period)` returns quarter badges for single- and multi-quarter spans.
- `sort_start(period)` returns the ISO start date, clamping open-start ranges to `reference_year-01-01`.

## Taxonomy contract

- `TAG_PREFIXES` and `prefix_for_tag()` are the canonical prefix mapping shared by taxonomy and validation.
- `classify_context(record)` resolves context from primary tags, then title prefix fallback, defaulting to `delivery`.
- `normalize_delivery_prefix(title, tags=...)` adds the canonical prefix when missing.
- `apply_confidence_cap(record)` downgrades `complete` to `partial` when no evidence is attached.

## Deduplication contract

- `deduplicate(observations)` unions observations transitively across namespaced `source_id` values and secondary keys (`jira`, normalized `pr`, `evidence`).
- Merge closure is order-independent; canonical rows prefer observations with a namespaced `source_id`.
- All provenance connectors and merged source IDs are preserved; nothing is deleted silently.

## Validation contract

- `validate_records(records, evidence)` returns `ValidationIssue` objects with deterministic `rule_id` values, never prose-only booleans.
- Typed `DeliveryRecord` metadata (`jira_key`, `pr_status`, `narrative_status`, `epic_parent`) is preserved through `RecordMetadata` with backward-compatible defaults.
- Impact validation consults both per-record evidence and the external `evidence` mapping keyed by record ID; disjoint locators raise `impact.evidence.inconsistent`.
- Rule IDs include: `kudos.name.required`, `kudos.month.required`, `title.tags.mismatch`, `jira.duplicate`, `github.pr.narrative_mismatch`, `impact.evidence.missing`, `impact.evidence.inconsistent`, `epic.duplicate`, `taxonomy.prefix.required`, `taxonomy.confidence.exceeds_cap`.

## Connector contract

- `Connector.collect(request) -> tuple[Observation, ...]` is the shared protocol for bounded source collection.
- Thread ingestion accepts only caller-provided excerpts up to `MAX_THREAD_EXCERPT` and runs `scan_sensitive` before parsing.
- GitHub invokes `gh api` through argv (`shell=False`) with explicit `fields` and bounded `max_results`.
- `ConsentService.require("connector", "connector:github", "read")` runs immediately before `gh api` execution.
- Google allows only `calendar.search`, `gmail.search`, `drive.search`, `docs.read`, and `sheets.read`.
- Google search actions require a bounded `time_window` with finite ISO-8601 start/end (`start < end`) and `max_results`.
- Client-side `max_results` truncation applies to GitHub and Google search responses even when providers over-return.
- `ConsentService.require("connector", "connector:google", action)` runs immediately before gateway invocation.
- Connector observations use provider source timestamps when present and current UTC observation time otherwise; epoch placeholders are never fabricated.

## Harvest contract

- `HarvestService.run` normalizes observations, applies transitive `deduplicate`, always runs `validate_records`, and persists only when no error-severity issues remain.
- Additional validators may extend the core gate but cannot disable `validate_records`.
- Merged records preserve all provenance connectors and `merged_source_ids` on `RecordMetadata`.
- Evidence refs carry a `connector` field for each contributing source.
- Production persistence uses `EncryptedRecordStore` over the SQLCipher connection with atomic commit/rollback.
- `MemoryStore` remains test-only.

## Voice/Tone

Direct, calm, and specific. Errors identify the failed rule or command without echoing sensitive input or key material.

## Open questions

- Which additional commands register in Task 4+ without breaking the envelope contract?
- How will schema version bumps propagate through skills and eval artifacts?
- Which connector-specific resource ID namespaces beyond Google Sheets/Docs need canonicalization rules?
