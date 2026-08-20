# Task 8b Report: Portable CareerOS CLI Commands

## Status

VERIFIED for the deterministic local scope on
`cursor/connector-harvest-9d3e` at implementation commit
`2ec57a55909f6270d7b43bc64c9f982458512351`.

All seven portable skill commands are registered and emit `CommandResult`
envelopes. The implementation retains `version` and `run-job`.

## Design

`careeros/DESIGN.md` was updated before production code. It defines stdin,
store, destination, privacy, validation, reconciliation, deployment, packet,
and foreground/background sync behavior for:

- `capture-delivery`
- `harvest-retrospective`
- `validate-bragsheet-integrity`
- `write-bragsheet-safe`
- `deploy-careeros-timeline`
- `build-promo-packet`
- `sync-careeros`

## TDD evidence

The initial CLI test collection failed because the new handlers were absent:

```text
ImportError: cannot import name 'handle_sync_careeros_background'
```

The non-persisting capture path failed before `HarvestRequest.persist` existed:

```text
TypeError: HarvestRequest.__init__() got an unexpected keyword argument 'persist'
```

The deployment registry test failed before its configured file adapter existed:

```text
ImportError: cannot import name 'FileDeploymentRegistry'
```

The connector-output privacy regression initially persisted the record:

```text
AssertionError: assert True is False
CommandResult(... 'persisted': True ...)
```

After the privacy gate was placed between collection and harvest, the focused
regression passed and the memory store remained empty.

## Implementation

- Added shared command handlers and bounded JSON-to-domain conversion in
  `careeros/cli_commands.py`.
- Registered all portable commands in `careeros/cli.py` while preserving the
  existing command envelope and `run-job` behavior.
- Capture uses `ThreadConnector` and `HarvestService` with persistence
  disabled. Every absent STAR field begins with `Evidence gap:`.
- Harvest scans both caller input and collected connector observations,
  requires existing connector consent, validates, and persists only error-free
  records through `EncryptedRecordStore`.
- Validation emits only `rule_id`, `severity`, and `field`; any error severity
  makes the envelope unsuccessful.
- Foreground write/sync uses projection plus `SyncService.write_and_verify`.
  Read-back mismatches return `reconciliation_required`.
- Background sync delegates to `JobRunner`, preserving `already_running` and
  treating missing or revoked background consent as terminal.
- Deployment uses configured clasp and private file-registry adapters through
  `DeployService`; only an exact Google Apps Script `/exec` URL can succeed.
- Promotion packet output is serialized directly from `build_promo_packet`;
  missing work cards remain missing.
- The skill smoke check executes every command and rejects missing,
  wrong-command, or `unknown_command` envelopes.

## Verification

CLI-focused:

```text
$ python3 -m pytest tests/careeros/test_cli.py -q
16 passed in 1.21s
```

The final full Python run includes the additional connector-output privacy
regression:

```text
$ python3 -m pytest tests/careeros -q
219 passed in 2.06s
```

Portable skill smoke:

```text
$ bash tests/smoke/check-careeros-skills.sh
PASS: portable CareerOS skill contracts are valid.
```

Node:

```text
$ npm test
66 passed, 0 failed
```

Compilation and whitespace:

```text
$ python3 -m compileall -q careeros
exit 0

$ git diff --check
exit 0
```

## Concerns

1. No live Google connector, Sheets write/read-back, clasp deployment, or
   Google authorization was exercised. Those outcomes require explicit local
   grants and real account configuration and are not claimed here.
2. Deployment requires `CAREEROS_DEPLOY_RESOURCE_ID` with a destination grant
   scoped to `deploy:timeline`; this keeps deployment fail-closed but requires
   one explicit local setup step.
3. The task examples use `python`, while this environment provides only
   `python3`. The smoke check prefers `python` and falls back to `python3`;
   verification used `python3`.
