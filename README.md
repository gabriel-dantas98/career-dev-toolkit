# Career Dev Toolkit

Career Dev Toolkit turns bounded work evidence into reviewable career records. It keeps an encrypted local database as the canonical source, applies deterministic privacy and integrity checks, and can project authorized records through a bounded Google Apps Script gateway.

## Status

This repository is an implementation and packaging slice, not a live-service certification. It includes the shared CareerOS Python runtime, portable skill contracts for Claude Code, Cursor and Codex, an encrypted local store, bounded thread/GitHub/Google connectors, safe brag-sheet projection with read-back, output builders, and native background scheduler adapters.

Local deterministic tests and a fake-provider end-to-end eval exercise those contracts. They do not prove that a real Google account can authorize, deploy or execute the Apps Script web app. **Live Google deployment certification: NOT RUN.**

Guided end-user onboarding and consent-management CLI commands are not implemented. Current setup is operator-oriented and requires terminal access.

## Who it is for

Career Dev Toolkit is for people working in technology at any level who want to keep useful evidence while the context is fresh. It is designed for everyday capture as well as quarter, semester and performance-review preparation.

## How capture works

Invoke `capture-delivery` at the end of a useful thread. The skill:

1. looks for one or more concrete deliveries in the context already available;
2. separates Situation, Task, Action and Result;
3. keeps missing evidence visible instead of filling gaps with plausible claims;
4. returns a draft for review without saving or syncing it.

Example:

```text
Use capture-delivery to turn this bounded thread excerpt into a STAR delivery draft.
```

## Privacy and local storage

Privacy checks are fail-closed. The runtime blocks recognized credentials, tokens, private keys, personal contact data and customer identifiers without echoing the matched value. Connectors accept bounded excerpts, time windows, result counts and resource IDs rather than unrestricted threads, mailboxes or drives.

Persistent commands use a SQLCipher-capable DB-API driver. On first open, CareerOS generates a random 256-bit database key and stores it through Python `keyring` in the operating-system credential store. It verifies `PRAGMA cipher_version` before migrations or data access. If SQLCipher, the keychain, the stored key or supported file permissions cannot be verified, startup stops; there is no plaintext SQLite fallback.

The default database path is `~/.local/share/careeros/careeros.db`. Tests use synthetic records and isolated keyring adapters.

## Install and operator onboarding

Requirements:

- Python 3.11 or newer and an operating-system credential backend supported by `keyring`;
- SQLCipher support provided by the packaged `sqlcipher3` dependency;
- Node.js 22 or newer for Node tests and eval tooling;
- authenticated `gh` for GitHub collection;
- authenticated `clasp` plus a linked Apps Script project for Google deployment.

Clone and install:

```bash
git clone https://github.com/gabriel-dantas98/career-dev-toolkit.git
cd career-dev-toolkit
python3 -m pip install -e '.[dev]'
npm install
python3 -m careeros version --json
```

The repository does not include a project-bound `.clasp.json`. Before the deployment command can work, an operator must create or link an Apps Script project, place its project configuration in `apps-script/`, run `clasp login`, and authorize the web app.

### One Google deployment

One user-deployed Apps Script web app handles the allowlisted Calendar, Gmail, Drive, Docs and Sheets actions. Its manifest requests:

- read-only Calendar, Gmail, Drive and Docs access;
- Sheets access for bounded reads and authorized brag-sheet writes.

The deployment executes as the deploying user and is restricted to that user. This is still a broad Google authorization surface. The gateway narrows each request with fixed actions, explicit resource IDs, finite windows and counts, nonce/timestamp checks, fixed write dimensions, RAW values and exact read-back. Deploying once does not grant CareerOS local consent to every source or destination.

Configure the runtime with environment variables as needed:

```bash
export CAREEROS_DB_PATH="$HOME/.local/share/careeros/careeros.db"
export CAREEROS_WEB_APP_URL="https://script.google.com/macros/s/REPLACE_WITH_DEPLOYMENT/exec"
export CAREEROS_BRAGSHEET_ID="sheet:REPLACE_WITH_SPREADSHEET_ID"
export CAREEROS_BRAGSHEET_NAME="Brag Sheet"
export CAREEROS_BRAGSHEET_START_ROW="2"
export CAREEROS_DEPLOY_RESOURCE_ID="sheet:REPLACE_WITH_SPREADSHEET_ID"
```

Do not treat the placeholder URL as valid; deployment accepts only an actual Google `/exec` URL returned by `clasp`.

### Consent and revocation

Consent has three independent grant types:

- `connector`: permits named read actions for a connector;
- `destination`: permits a named write or deployment capability for one exact resource;
- `background`: permits one named job to run unattended.

Foreground sync requires destination consent. It does not require or create background consent. Background sync requires both the destination grant used by the write and a separate `background` grant for `job:<id>`. Every relevant grant is checked again immediately before an external call.

There is not yet a supported consent-management CLI. Operators can provision and revoke grants through the Python API while the same encrypted store and keychain are available:

```python
from pathlib import Path

import keyring

from careeros.consent import ConsentService
from careeros.store import StoreConfig, open_encrypted_store

store = open_encrypted_store(
    StoreConfig(Path("~/.local/share/careeros/careeros.db").expanduser()),
    keyring,
)
try:
    consent = ConsentService(store)
    consent.grant(
        "connector",
        "connector:google",
        ("calendar.search", "gmail.search", "drive.search", "docs.read", "sheets.read"),
    )
    consent.grant("destination", "sheet:YOUR_ID", ("write:bragsheet",))
    consent.grant("background", "job:daily", ("run",))

    # Revocation blocks the next checked call.
    consent.revoke("background", "job:daily")
finally:
    store.close()
```

Local revocation does not undeploy the Apps Script web app or revoke Google's OAuth authorization. Disable the deployment and revoke account access separately in Google when that is the intended boundary.

Onboarding should ask for one user action at a time and rerun the relevant check after each action. The current repository supplies the checks and fail-closed runtime contracts, but not a guided onboarding wizard.

## CLI

All commands emit the shared result envelope with `--json`. Portable commands read one JSON object from standard input; they do not accept command-specific flags.

```bash
python3 -m careeros version --json
printf '%s\n' '{"excerpt":"Title: [Delivery] Synthetic local example"}' \
  | python3 -m careeros capture-delivery --json
printf '%s\n' '{"records":[]}' \
  | python3 -m careeros validate-bragsheet-integrity --json

python3 -m careeros harvest-retrospective --json
python3 -m careeros write-bragsheet-safe --json
python3 -m careeros build-promo-packet --json
python3 -m careeros sync-careeros --json
printf '%s\n' '{"background":true,"job_id":"daily"}' \
  | python3 -m careeros sync-careeros --json
python3 -m careeros run-job daily --json
python3 -m careeros deploy-careeros-timeline --json
```

The empty-input examples only show command shape. Persistent, connector, sync and deployment commands need bounded JSON input, configured environment values and matching grants. A foreground write is successful only after exact read-back reports `synced`; a mismatch remains `reconciliation_required`.

### Agent packaging

#### Claude Code

```bash
claude plugin validate . --strict
claude plugin marketplace add ./
claude plugin install career-dev-toolkit@career-dev-toolkit
claude plugin details career-dev-toolkit@career-dev-toolkit
```

#### Cursor

Cursor can load the checkout without a persistent installation:

```bash
cursor agent --plugin-dir . --print --mode ask --trust \
  "Use capture-delivery on this thread: I reduced CI duration from 20 to 12 minutes by parallelizing tests. Return STAR labels."
```

#### Codex

The repository includes a Codex plugin manifest and validates it with the official plugin validator. Runtime installation is not yet documented as supported because the local Codex CLI used for this bootstrap currently fails before plugin loading. The diagnostic is kept in `tests/evidence/` rather than presented as a passing install.

## Test and evaluate

The blocking test path is local, repeatable and does not call a model:

```bash
bash tests/smoke/validate-structure.sh
bash tests/smoke/check-capture-skill.sh
bash tests/smoke/check-careeros-skills.sh
bash tests/smoke/check-timeout.sh
bash tests/smoke/check-evidence-privacy.sh
bash tests/smoke/check-eval-integration.sh
python3 -m pytest -q
npm test
npm run eval:static
npm run eval:careeros
npm run test:python
```

Run the local CLI matrix:

```bash
bash scripts/smoke-install.sh all
```

Provider certification is separate because it needs authenticated CLIs and consumes model calls. Every run requires a hard invocation ceiling:

```bash
npm run eval:providers -- \
  --providers claude,cursor \
  --runs 3 \
  --max-invocations 60
```

Add `--judge claude` or `--judge cursor` for a second opinion. Judge calls consume the same ceiling and remain separate from the deterministic score.

Reports are written to the ignored `.eval-results/` directory. They contain sanitized provider output, but should still be reviewed before anything is committed or shared. A missing CLI or credential is reported as unavailable, never as a passing evaluation.

`npm run eval:careeros` uses synthetic thread, GitHub and Apps Script fixtures. It proves the local pipeline can reject a sensitive input and invalid impact record, merge overlapping evidence, use a real SQLCipher database with a synthetic keyring, safely project an ambiguous date, verify fake-gateway read-back, build outputs and block a background run without its separate grant. It does not contact Google, exercise OAuth, certify `clasp`, verify a live web-app URL or prove behavior in a user's keychain and scheduler environment.

The committed Task 10 evidence is in `tests/evidence/careeros-verification.md` and `tests/evidence/careeros-eval.json`. It is a sanitized snapshot, not a substitute for rerunning checks in the target environment.

The `smoke-test` workflow blocks pull requests using only deterministic checks. The manual `provider-evals` workflow reads `ANTHROPIC_API_KEY` and `CURSOR_API_KEY` from repository secrets, skips providers whose credentials are unavailable and uploads reports for 14 days.

## Remaining gaps

- guided onboarding and consent-management commands;
- live Google OAuth, Apps Script deployment and read/write certification;
- a Luma connector (the current policy returns it as explicitly unavailable);
- LinkedIn PDF import and provider preference onboarding;
- a rendered Career Canvas UI beyond the tested timeline data contract.

Ollama is not planned for the first version.

## Relationship to Bragflow and Tapioca

Career Dev Toolkit is an independent spin-off from Bragflow. Bragflow remains the product for brag-document automation; this repository focuses on the local agent workflow and portable career skills.

Its packaging conventions borrow from [Tapioca](https://github.com/gabriel-dantas98/tapioca), especially the shared skill source used by Claude Code and Cursor. The Google Apps Script integration adapts its browser-mode pattern without a runtime dependency on Tapioca.

## Contributing

The public API and operator setup are still taking shape. Small fixes, test cases and privacy edge cases are welcome. Open an issue before building a new integration so its data boundary can be agreed first.
