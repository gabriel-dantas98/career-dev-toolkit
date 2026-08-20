# CareerOS Python Runtime

## Goal

Provide a shared, deterministic Python runtime that exposes one CLI entry point (`python -m careeros`) and typed domain contracts consumed by portable skills and later pipeline stages. Task 2 adds fail-closed privacy scanning, SQLCipher-backed encrypted persistence, versioned migrations, and scoped revocable consent.

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

## Outputs

- `CommandResult` envelopes with deterministic JSON shape.
- Typed contracts: `DeliveryRecord`, `EvidenceRef`, and `ValidationIssue`.
- `PrivacyFinding` lists with category and span offsets, never echoing matched secret substrings.
- `EncryptedStore` backed by SQLCipher with migrated tables for records, evidence, grants, sync runs, and migrations.
- `ConsentService` grant, require, and revoke operations with destination, connector, and background isolation.
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

## Voice/Tone

Direct, calm, and specific. Errors identify the failed rule or command without echoing sensitive input or key material.

## Open questions

- Which additional commands register in Task 3+ without breaking the envelope contract?
- How will schema version bumps propagate through skills and eval artifacts?
- Which connector-specific resource ID namespaces beyond Google Sheets/Docs need canonicalization rules?
