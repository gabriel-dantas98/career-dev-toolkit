# CareerOS Python Runtime

## Goal

Provide a shared, deterministic Python runtime that exposes one CLI entry point (`python -m careeros`) and typed domain contracts consumed by portable skills and later pipeline stages. Task 2 adds fail-closed privacy scanning, SQLCipher-backed encrypted persistence, versioned migrations, and scoped revocable consent. Task 3 adds Brazilian date parsing, taxonomy classification, deterministic deduplication, and integrity validators. Task 5 adds fixed-schema brag-sheet projection, browser-mode gateway calls, consent-adjacent RAW writes, and exact read-back reconciliation. Task 6 adds fail-closed deployment health, homepage and timeline contracts, evidence-bounded promotion packets, deterministic enrichment and leader review, and timeline preview parity. Task 7 adds consent-safe background execution with exclusive per-job locks, per-run idempotency keys, and native user-level scheduler adapters. Task 8 wires each portable skill to that shared runtime without weakening any existing privacy, consent, validation, persistence, reconciliation, deployment, or background-execution gate.

## Non-goals

- Call external providers or bypass privacy gates.
- Infer metrics, ownership, dates, causality, or impact.
- Expose platform-specific behavior that diverges across Claude Code, Cursor, or Codex.
- Offer plaintext SQLite fallback or downgrade when SQLCipher or the OS keychain is unavailable.
- Infer background-job consent from destination or connector grants.
- Derive a web-app URL from a deployment ID, accept a non-Apps-Script URL, or deploy after failed clasp health.
- Fabricate promotion cards, event dates, hero metrics, evidence links, promotion readiness, or level verdicts.
- Claim that Luma was queried; the first release exposes it only as an explicitly unavailable fallback.

## Inputs

- CLI arguments for registered commands.
- Optional `--json` flag requesting machine-readable envelopes.
- Bounded text for `scan_sensitive(text)` privacy preflight.
- `StoreConfig` path and a keyring backend (`get_password` / `set_password` / `delete_password`).
- Consent grants keyed by grant type, canonical resource ID, and explicit scopes.
- Period strings whose year is explicit in the period or, for a yearless record, in that same record's `observed_at`; output builders never borrow a year from another record.
- Delivery and kudos records plus an external evidence mapping keyed by record ID.
- Observations with namespaced `source_id`, Jira/PR/evidence keys, and provenance tuples.
- Bounded `CollectRequest` payloads for thread excerpts, GitHub `gh api` queries, and Google gateway actions.
- `HarvestRequest` observation batches normalized, deduplicated, validated, and persisted transactionally.
- Delivery records projected to an explicit sheet ID, sheet name, start row, and fixed 12-column brag-sheet schema.
- Apps Script web-app URLs ending in `/exec`, invoked by JSON POST through a persistent browser profile.
- Clasp health and deploy output supplied through a narrow deployment adapter, plus an exact URL registrar.
- Delivery records used to build homepage, timeline, promotion packet, metric, review, and enrichment outputs.
- Calendar and Gmail event-date candidates; Luma has no callable connector in this surface.
- Apps Script-compatible timeline preview mappings used only for deterministic parity comparison.
- Named background jobs mapped to fixed projections, plus explicit commands and bounded integer minute intervals for native user-level schedules.
- `run-job <job-id>` runtime configuration from `CAREEROS_WEB_APP_URL` and `CAREEROS_BRAGSHEET_ID`, with optional local path and sheet-name overrides.
- JSON objects read from standard input for bounded capture, harvest, validation, write, packet, and foreground-sync inputs. An empty standard input selects the encrypted local record store where the command contract permits it.
- CLI runtime configuration from `CAREEROS_DB_PATH`, `CAREEROS_WEB_APP_URL`, `CAREEROS_BRAGSHEET_ID`, `CAREEROS_BRAGSHEET_NAME`, `CAREEROS_BRAGSHEET_START_ROW`, `CAREEROS_LOCK_DIR`, and deployment adapter variables.

## Outputs

- `CommandResult` envelopes with deterministic JSON shape.
- Typed contracts: `DeliveryRecord`, `RecordMetadata`, `EvidenceRef`, and `ValidationIssue`.
- `PrivacyFinding` lists with category and span offsets, never echoing matched secret substrings.
- `EncryptedStore` backed by SQLCipher with migrated tables for records, evidence, grants, sync runs, and migrations.
- `ConsentService` grant, require, and revoke operations with destination, connector, and background isolation.
- `Connector.collect(request) -> tuple[Observation, ...]` from thread, GitHub, and Google adapters.
- `HarvestService.run(request) -> HarvestResult` with merged records, validation issues, and persist status.
- `serialize_period(value)`, immutable `BragSheetProjection` previews, and `SyncService.write_and_verify()`.
- Gateway envelopes with exactly `ok`, `requestId`, `data`, `errors`, and `version`.
- Deployment results that register the exact parsed `https://script.google.com/.../exec` URL and put that same URL in the homepage contract.
- Homepage configuration whose default source is the brag-document gid `425749964`.
- Promotion packets with 10–12 evidence-backed work cards when enough evidence exists, separate collapsed community and recognition summaries, an unresolved-work summary, and an explicit insufficient-evidence state otherwise.
- Timeline cards whose face prefers linked impact, whose badges are canonical delivery types, and whose quarter ordering comes from the shared dates library; unresolved records remain explicit outside the card list.
- Evidence-policy findings, explicit unresolved enrichment results, deterministic leader-review findings, and field-level timeline parity differences.
- `JobRunner.run(job_id)` results with `synced` or `already_running` status and one correlation/idempotency key per acquired run.
- `python -m careeros run-job <job-id> [--json]` dispatch to the configured `JobRunner` with the standard `CommandResult` envelope.
- Executable `capture-delivery`, `harvest-retrospective`, `validate-bragsheet-integrity`, `write-bragsheet-safe`, `deploy-careeros-timeline`, `build-promo-packet`, and `sync-careeros` CLI commands, each returning the same `CommandResult` JSON envelope as `version` and `run-job`.
- Structured scheduler install/remove results for user-level launchd, Windows Task Scheduler, and systemd user timers.
- `StoreUnavailable` and `ConsentDenied` terminal errors that identify the failed rule without leaking keys or sensitive input.

## Privacy contract

- `scan_sensitive(text)` detects private keys, bearer tokens, GitHub tokens, API keys, and email addresses using deterministic patterns aligned with the eval privacy boundary.
- Findings return category, start, and end offsets only; serialized output must not reproduce matched values.

## Store contract

- Production connects exclusively through `sqlcipher3` via the `sqlcipher_driver` import boundary; stdlib `sqlite3` is test-only to prove refusal.
- Fast unit tests may inject an explicitly named SQLite cipher-capability stub to exercise migrations, key lifecycle, permissions, and startup errors. That stub is not encryption evidence and must not be described as SQLCipher.
- The blocking CI suite installs the project runtime and `dev` extra, then runs an unskipped production-driver integration test. Certification requires a nonempty real `PRAGMA cipher_version`, all migrations, reopening with the same synthetic key, and failure when stdlib `sqlite3` attempts to read the encrypted file.
- A 256-bit key is generated locally, stored in the OS keychain under `careeros` / `db-key:<resolved-path>`, and validated as 64 lowercase hex characters before `PRAGMA key` interpolation (parameter binding is unsupported by the driver).
- Startup executes `PRAGMA key` immediately, requires a nonempty `PRAGMA cipher_version`, applies versioned migrations (currently through `003_evidence_gaps.sql`), and refuses when applied migration versions exceed runtime support.
- Migration `002` adds `records.metadata_json` for canonical typed metadata and `evidence.connector` for provenance round-trip.
- Migration `003` adds `records.evidence_gaps`; the production repository round-trips gaps instead of replacing them with an empty tuple.
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
- `sheets.read` requires a canonical sheet ID, explicit `sheet_name`, and finite A1 `range` of at most 500 cells. Connector payloads strip canonical `sheet:`/`doc:` prefixes into the gateway's `spreadsheetId`/`documentId` fields.
- Gmail gateway queries reject grouping syntax and case-insensitive `OR` tokens delimited by whitespace or punctuation before the gateway appends its server-owned time window.
- Client-side `max_results` truncation applies to GitHub and Google search responses even when providers over-return.
- `ConsentService.require("connector", "connector:google", action)` runs immediately before gateway invocation.
- Connector observations use provider source timestamps when present and current UTC observation time otherwise; epoch placeholders are never fabricated.
- Gmail snippets and excerpts use `bound_excerpt` (`MAX_THREAD_EXCERPT`) before observation creation.

## Harvest contract

- `HarvestService.run` normalizes observations, applies transitive `deduplicate`, always runs `validate_records`, and persists only when no error-severity issues remain.
- Additional validators may extend the core gate but cannot disable `validate_records`.
- Merged records preserve all provenance connectors and `merged_source_ids` on `RecordMetadata`.
- Evidence refs carry a `connector` field for each contributing source.
- Production persistence uses `EncryptedRecordStore` over the SQLCipher connection with atomic commit/rollback.
- `records.metadata_json` stores deterministic JSON for `RecordMetadata` (`jira_key`, `pr_status`, `narrative_status`, `epic_parent`, `provenance`, `merged_source_ids`, `evidence_locators`).
- `evidence.connector` is persisted alongside locator, excerpt, and observed-at for read-back.
- Persistence failures return `HarvestResult.persistence_error` with `harvest.persistence.failed`; nothing is left partially persisted after rollback.
- `MemoryStore` remains test-only.

## Projection and sync contract

- The brag-sheet projection has at most 200 rows and exactly 12 fixed columns; destination IDs are canonical `sheet:{id}` values and sheet names/start rows are explicit.
- Every projected value is written in one `RAW` operation. The gateway pads the intended matrix to the complete owned 200-row by 12-column window in memory and sends one advanced Sheets `Values.update`. Period input is trimmed first; slash periods whose first and second components are both at most 12 receive a leading apostrophe before projection.
- `SyncService.preview()` performs no external call. `ConsentService.require("destination", destination_id, "write:bragsheet")` runs immediately before `sheets.writeBragsheet`.
- The one padded update addresses only the owned 200-row by 12-column projection area, preventing shrinking syncs from retaining stale rows without touching cells outside that area or risking a clear/update failure gap.
- A successful write is followed by `sheets.readBack` over the actual projected start row and dimensions, not the padded owned window, using Sheets v4 `Values.get` with `UNFORMATTED_VALUE`. Matrix shape, value, and Python value type must match exactly.
- Any exception or mismatch after the write call records `reconciliation_required`; only exact read-back records `synced`. If recording reconciliation also fails, the original write/read-back exception remains primary and receives a diagnostic note.
- The browser client adds a bounded request ID, timestamp, and nonce; posts JSON through an authenticated persistent Playwright profile; defaults to three attempts, permits a ceiling of five, retries only transient interstitial/status responses, and accepts only the exact gateway envelope.
- Playwright is an optional `browser` install extra. The local synthetic transport and HTTP fixture do not require Google credentials and do not certify live OAuth behavior.

## Background job contract

- `JobRunner` resolves only configured job IDs and acquires an atomic exclusive lock before consent checks or work. An overlapping invocation owned by a live PID returns `already_running` without a second sync or gateway call.
- Lock directories are user-only on POSIX. A lock whose recorded PID is no longer live is reclaimed before work; malformed lock content remains fail-closed while recent, then becomes reclaimable after a fixed one-hour bound so a crash during lock creation cannot wedge the job forever.
- Acquired locks are released in a `finally` path after both successful and failed runs.
- A destination grant never authorizes unattended execution. Every acquired run requires `ConsentService.require("background", "job:{job_id}", "run")` before work starts.
- Each acquired run creates one correlation/idempotency key. The same key accompanies all gateway calls for that run, while separate runs receive separate keys.
- Confirmed local writes create a payload-hash receipt under the private lock directory. Reusing the same key and payload, including through a later `JobRunner` instance sharing that receipt store, skips the second write; reusing a key with a different write payload fails closed.
- Apps Script does not interpret `idempotencyKey`; it is a correlation token at that boundary. Browser transport does not retry mutating actions after an ambiguous transport or transient response, so this runtime does not claim remote exactly-once delivery.
- Background consent is re-checked by the guarded gateway immediately before every external invocation. Destination consent is independently re-checked immediately before each write and read-back invocation.
- Revocation is terminal for the current operation and prevents the next external call; lock cleanup still occurs.
- The `run-job` CLI validates the requested job, builds the local encrypted-store, projection, consent, sync, browser-gateway and lock dependencies from explicit local configuration, invokes `JobRunner.run`, and closes the store. Missing configuration and job failures return structured errors.

## Portable skill command contract

- Every portable skill command is registered explicitly; command smoke checks fail when any command returns `unknown_command`.
- `capture-delivery` accepts one bounded `excerpt` or `thread`, scans it before parsing, uses `ThreadConnector` and non-persisting `HarvestService` execution, and emits the fixed 12-field brag-document shape. Missing Situation, Task, Action, and Result values begin with `Evidence gap:` and are never inferred.
- `harvest-retrospective` accepts caller-supplied observations or bounded thread, GitHub, and Google connector requests. It scans caller content before opening a connector, requires connector grants at the existing adapter boundaries, persists only error-free harvests through `EncryptedRecordStore`, and returns only validation rule IDs, record IDs, and connector names.
- `validate-bragsheet-integrity` validates caller-supplied records or encrypted-store records and emits rule ID, severity, and field. Any error-severity issue makes the command envelope unsuccessful.
- `write-bragsheet-safe` validates and scans records before projection, requires destination consent through `SyncService`, and reports `synced` only after exact read-back. A post-write exception or mismatch returns `reconciliation_required`.
- `deploy-careeros-timeline` uses configured clasp and URL-registry adapters through `DeployService`. Failed clasp health, missing deployment configuration, or output without exactly one real Google Apps Script `/exec` URL is terminal.
- `build-promo-packet` validates caller-supplied or encrypted-store records and serializes only cards and summaries returned by `build_promo_packet`; it never fills missing work-card slots.
- `sync-careeros` uses `JobRunner` when a background job is requested explicitly or configured by `CAREEROS_JOB_ID`; otherwise it follows the same validation, projection, consent, write, and read-back path as `write-bragsheet-safe`. Background revocation is terminal, and `already_running` is preserved.
- Privacy findings serialize category and offsets only. Connector, keychain, store, consent, validation, gateway, and deployment failures use bounded error messages that do not include source excerpts, secrets, or provider payloads.

## Scheduler contract

- `Scheduler.install(schedule)` and `Scheduler.remove(job_id)` use only native user-level facilities: launch agents under `~/Library/LaunchAgents` with the `gui/{uid}` launchd domain on macOS, Task Scheduler on Windows, and units under `~/.config/systemd/user` with `systemctl --user` on Linux.
- A schedule contains a canonical job ID, an argv command, and a bounded positive minute interval. Generated labels, task names, and filenames derive from a validated job ID.
- Linux timers contain both `OnStartupSec` and `OnUnitActiveSec`; no unsupported `Persistent` setting is emitted for monotonic timers. macOS launch agents use `StartInterval`, preserve argv in `ProgramArguments`, and set `RunAtLoad` false.
- Windows intervals that Task Scheduler cannot represent return `scheduler.invalid_schedule` without invoking `schtasks`.
- Generated Linux and macOS scheduler files use mode `0600`. Scheduler adapters never create cron files.
- Unsupported operating systems return `scheduler.unsupported` in a structured result without invoking a command or falling back to cron.
- Native command and filesystem failures return a structured `scheduler.command_failed` or `scheduler.install_failed` result rather than claiming installation.

## Deployment and homepage contract

- `DeployService.deploy()` runs clasp health first and performs no deployment or registration unless health passes.
- Deployment and homepage builders share one strict validator. It accepts only complete HTTPS URLs on `script.google.com` matching `/macros/s/{deployment}/exec` or `/a/macros/{domain}/s/{deployment}/exec`; deployment IDs, looser paths, queries, fragments, ports, credentials, and URLs embedded inside larger attacker-controlled tokens are rejected.
- The exact parsed URL is registered and copied unchanged into the homepage `webAppUrl`.
- Homepage source configuration defaults to `kind: "brag-document"` and gid `425749964`. The unrelated Sheets homepage gid `389581671` is never used as a fallback.

## Promotion and timeline contract

- Work, community, and kudos are partitioned before selection. Community contributions and kudos recognition each have a separate count, evidence links, and evidence gaps; neither consumes a work-card slot.
- Only work records with nonempty evidence locators and resolvable period state are eligible. A yearless period resolves only from that record's own ISO `observed_at` year; no configured or cross-record year can supply it. Unresolved work is collapsed separately with links and a `period.year.required` gap.
- Empty and wholly unresolved inputs return `insufficient_evidence` with no fabricated cards. If fewer than ten records are eligible, every eligible card is returned with the exact missing count; otherwise selection is deterministic and capped at twelve. Dated work sorts before undated work.
- A timeline card uses an evidence-backed impact result as its face before action or title. It carries source links and unresolved evidence gaps.
- Timeline badges represent canonical delivery types, not quarter labels. `parse_period`, `quarters_for`, and `sort_start` are the sole source of quarter expansion and ordering. Dates sort descending while equal dates use stable record ID ascending.
- A timeline with no resolved cards, including wholly unresolved yearless input, remains a valid versioned UI contract with an empty card list and explicit unresolved records. Every card mapping has `recordId`, `title`, `face`, `badges`, `quarterBadges`, `sortStart`, `evidenceLinks`, and `evidenceGaps`.
- Parity compares the complete generated timeline mapping with an independently supplied Apps Script-compatible preview and reports deterministic field paths for every mismatch.

## Evidence, enrichment, and review contract

- Every hero metric requires at least one nonempty supporting evidence link. Metrics whose normalized `kind` is `vanity` are rejected even when linked; derived metrics are allowed only with links.
- Event dates resolve in strict Calendar then Gmail order. If both are empty, the result is unresolved, records Calendar and Gmail as queried, and records Luma as unavailable—not queried.
- Kudos enrichment requires both a name and month. Talk and external credential enrichment preserve every input evidence link and return explicit unresolved fields instead of guessed values.
- Leader review emits sorted, stable findings about evidence and record quality. Missing evidence produces `leader_review.evidence.missing`; `leader_review.impact.unsupported` is reserved for an impact record that has a link but whose bounded evidence excerpt does not support a normalized result token. It has no promotion recommendation, level score, readiness verdict, or inferred impact.

## Voice/Tone

Direct, calm, and specific. Errors identify the failed rule or command without echoing sensitive input or key material.

## Open questions

- How will schema version bumps propagate through skills and eval artifacts?
- Which connector-specific resource ID namespaces beyond Google Sheets/Docs need canonicalization rules?
- Live clasp authentication, deployment, homepage rendering, and Google authorization remain uncertified until exercised with a user-authorized account; synthetic adapters prove only local contracts.
- Native scheduler installation remains uncertified on real macOS and Windows hosts; unit tests verify generated user-level commands and files without mutating a host scheduler.
