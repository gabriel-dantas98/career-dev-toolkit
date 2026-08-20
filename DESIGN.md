# Career Dev Toolkit

## Goal

Provide local-first career infrastructure that turns bounded thread, GitHub and Google observations into evidence-proportional career records. The same Python runtime and skill contract serve Claude Code, Cursor and Codex.

The implemented pipeline is:

```text
bounded harvest -> privacy gate -> normalize/deduplicate -> validate
  -> encrypted local store -> preview -> consent check -> Google write
  -> exact read-back -> local outputs
```

The repository proves this behavior with local tests and synthetic providers. A real Google account has not been used for certification.

## Non-goals

- Treat Google Sheets as canonical storage or fall back to plaintext SQLite.
- Send full threads, mailboxes, drives or sensitive values to an external provider.
- Infer metrics, ownership, dates, causality, Jira relationships or impact.
- Produce promotion, level or performance verdicts.
- Claim that fake-provider checks certify live Google OAuth or deployment.
- Provide LinkedIn PDF import, Luma collection, a rendered Career Canvas or Ollama support in this release.

## Inputs

- A caller-supplied, bounded excerpt from the current agent thread.
- Bounded GitHub reads through authenticated `gh`.
- Bounded Calendar, Gmail, Drive, Docs and Sheets reads through one user-deployed Apps Script web app.
- Existing records from the encrypted local database.
- Explicit connector, destination and background grants stored in that database.
- Operator configuration such as exact resource IDs, review periods, sheet name, start row and web-app URL.

## Outputs

- STAR drafts and persisted delivery records with visible evidence gaps.
- Machine-readable privacy and integrity findings with stable rule IDs.
- Safe brag-sheet projections written with RAW values and checked by exact read-back.
- Promotion-packet, homepage and timeline data contracts.
- Structured deployment, sync and background-job states.
- Sanitized deterministic eval evidence that contains counts and rule IDs rather than private source bodies.

## Storage and key requirements

`careeros/` keeps the local database canonical. `open_encrypted_store` obtains a random 256-bit key through Python `keyring`, opens the database with the packaged SQLCipher driver, applies `PRAGMA key`, and requires a nonempty `PRAGMA cipher_version` before migrations or records are touched.

Startup fails closed when the SQLCipher driver, cipher support, operating-system keychain, stored key, migration version or supported file-permission check is invalid. No code path substitutes standard plaintext SQLite. Tests use temporary SQLCipher databases, synthetic records and fake keyring backends; they do not certify every operating-system keychain.

## Google boundary

A single Apps Script deployment serves the fixed gateway actions for Calendar, Gmail, Drive, Docs and Sheets. Its manifest asks for read-only Calendar, Gmail, Drive and Docs scopes plus a Sheets scope that permits bounded reads and writes. The web app executes as, and is restricted to, the deploying user.

One deployment is an operational convenience, not blanket local consent. The gateway still requires:

- a fixed action allowlist;
- explicit resource identifiers;
- bounded search windows, result counts, ranges and payload sizes;
- fresh timestamps and single-use nonces;
- RAW brag-sheet values in a fixed owned window;
- minimal structured responses;
- exact read-back before a sync can become `synced`.

The repository has no project-bound `.clasp.json`, so an operator must link or create the Apps Script project and authenticate `clasp`. Deployment code rejects failed health checks and anything other than one real Google `/exec` URL.

**Live Google deployment certification: NOT RUN.** Local gateway tests and the fake end-to-end eval do not exercise OAuth, a user account, a deployed web app or Google APIs.

## Consent, onboarding and revocation

Consent is scoped by grant type, canonical resource ID and capability:

- connector grants permit named source reads;
- destination grants permit an exact resource write or deployment;
- background grants permit a named unattended job.

Foreground sync requires destination consent and shows a deterministic projection before mutation. A destination grant never implies background consent. Background sync requires its own `job:<id>` grant and rechecks it before each external call; exclusive locks and idempotency receipts prevent overlapping or repeated writes from being presented as new syncs.

Revoking a local grant takes effect at the next gate. It does not disable the Apps Script deployment or revoke Google OAuth access; those are separate Google-side actions.

Current onboarding is operator-oriented. The CLI verifies runtime commands and fail-closed states, while grants are managed through `ConsentService`; no consent-management or guided onboarding command exists yet. Skill contracts ask for at most one setup action at a time and rerun the CLI after that action.

## CLI contract

The entry point is:

```text
python3 -m careeros <command> --json
```

Implemented commands are:

- `version`
- `capture-delivery`
- `harvest-retrospective`
- `validate-bragsheet-integrity`
- `write-bragsheet-safe`
- `build-promo-packet`
- `sync-careeros`
- `run-job <job-id>`
- `deploy-careeros-timeline`

Portable commands consume one JSON object from standard input. Persistent and external commands also require matching environment configuration and grants. All commands use the same `{ok, command, data, errors}` envelope; blocked, `already_running` and `reconciliation_required` states must remain visible.

## Verification boundary

The full local verification runs Python tests, shell contract checks, Node tests, the static eval and the CareerOS fake-provider eval. `npm run eval:careeros` covers overlapping observations, privacy rejection, invalid-impact rejection, real SQLCipher storage with a synthetic keyring, safe ambiguous-date serialization, a local Apps Script-compatible HTTP fixture, exact read-back, output builders and missing background consent.

That eval cannot certify:

- live Google authorization or scope prompts;
- `clasp` login, project linkage or deployment;
- a real `/exec` endpoint or Google read/write behavior;
- a user's native keychain or scheduler environment;
- provider quality on private career content.

## Voice/Tone

Direct, calm and specific. Claims stay proportional to recorded evidence. Missing context is reported as a gap rather than filled with plausible prose, and readiness states are not promotion judgments.

## Open questions

- What supported UX should create, inspect and revoke grants without requiring direct Python API use?
- Which user-authorized account and test sheet should be used for the first live Google certification?
- How should project creation/linking and Google-side revocation be guided without broadening the local consent boundary?
- What is the smallest explicit authentication and privacy contract for a future Luma connector?
