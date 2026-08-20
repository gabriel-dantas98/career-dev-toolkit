# Task 7 Report: Consent-safe background jobs and native schedulers

## Status

VERIFIED for the deterministic local Task 7 scope on branch
`cursor/connector-harvest-9d3e` at implementation commit
`243e08e3c1859639a91394cdce609084c45140b4`.

Real launchd, Windows Task Scheduler, and systemd user installations were not
performed and are not claimed. Their generated files and command invocations
are covered with isolated unit tests.

## Design

`careeros/DESIGN.md` was updated before production code. It now defines:

- atomic per-job locking and clean overlap behavior;
- independent background and destination consent gates;
- consent re-checks before every external write and read-back;
- one idempotency key shared by every call in an acquired run;
- successful in-run write retry deduplication;
- native user-level scheduling on macOS, Windows, and Linux;
- structured unsupported/error results with no cron fallback.

## TDD: RED

The brief's `python` command is unavailable in this environment:

```text
$ python -m pytest tests/careeros/test_jobs.py -q
python: command not found
```

Using the available interpreter produced the expected missing-module failure:

```text
$ python3 -m pytest tests/careeros/test_jobs.py -q
ModuleNotFoundError: No module named 'careeros.jobs'
1 error during collection
```

The destination-revocation regression failed before `SyncService` was changed:

```text
$ python3 -m pytest tests/careeros/test_sync.py::test_sync_rechecks_destination_consent_before_readback -q
Failed: DID NOT RAISE ConsentDenied
1 failed
```

The retry regression also failed with two underlying writes before the
per-run gateway added successful-write deduplication:

```text
$ python3 -m pytest tests/careeros/test_jobs.py::test_retried_write_within_run_does_not_call_gateway_twice -q
AssertionError: assert 2 == 1
1 failed
```

Each failure exercised missing behavior rather than a malformed fixture.

## Implementation

### Job runner

- `JobRunner.run(job_id)` validates configured IDs and acquires an atomic
  `O_CREAT | O_EXCL` lock before consent or sync work.
- An overlap returns `JobResult(status="already_running")` without allocating
  an idempotency key or making a second sync/gateway call.
- Acquired locks are released in `finally` after success, consent denial, or
  sync failure.
- A background `job:{id}` / `run` grant is required independently of the
  projection's destination grant.
- Every acquired run creates one idempotency key. A guarded gateway adds it to
  every call and serves repeated successful write payloads from the per-run
  cache.
- The guarded gateway checks background consent directly before each
  underlying external invocation.

### Sync consent adjacency

`SyncService.write_and_verify` accepts an optional idempotency key, includes it
in write/read-back payloads, and re-checks destination consent before both
external calls. Revocation after a write therefore blocks read-back and leaves
the existing reconciliation error path active.

### Native scheduler adapters

- macOS writes a user launch-agent plist and invokes `launchctl` in the
  `gui/{uid}` domain.
- Windows invokes `schtasks` for the current user's Task Scheduler.
- Linux writes user service/timer units and uses only `systemctl --user`.
- Unsupported systems return `scheduler.unsupported` without executing a
  command. No adapter invokes or generates cron.
- Command and filesystem failures return structured scheduler errors.

## Committed test coverage

`tests/careeros/test_jobs.py` covers:

- real concurrent overlap with exactly one sync entry;
- destination-only consent denial;
- revoked background consent before network access;
- background revocation between write and read-back;
- one idempotency key per run and distinct keys across runs;
- successful in-run write retry deduplication;
- lock release after both successful and failed work;
- launchd, Task Scheduler, and systemd user command selection;
- native scheduler removal;
- structured unsupported-platform behavior and absence of cron fallback.

`tests/careeros/test_sync.py` adds destination revocation between write and
read-back and updates the ordering assertion to require a second consent check.

## Verification

Targeted Task 7 and sync:

```text
$ python3 -m pytest tests/careeros/test_jobs.py tests/careeros/test_sync.py -q
33 passed in 0.28s
```

All configured Python tests:

```text
$ python3 -m pytest -q
186 passed in 0.92s
```

Node:

```text
$ npm test
66 passed, 0 failed
```

Compilation and diff validation:

```text
$ python3 -m compileall -q careeros
exit 0

$ git diff --check
exit 0
```

## Requirement audit

| Requirement | Evidence | Result |
|---|---|---|
| Exclusive lock | Real threaded overlap test | PASS |
| Overlap avoids second gateway/sync | Sync count remains one; gateway remains untouched by overlap | PASS |
| Revoked background grant blocks before network | Revocation test has zero gateway calls | PASS |
| Destination grant does not imply background | Destination-only runner raises `ConsentDenied` | PASS |
| One idempotency key per run | Exact payload key assertions across two runs | PASS |
| Retried work does not double-write | Repeated write payload reaches underlying gateway once | PASS |
| Consent before each external call | Background and destination mid-run revocation tests | PASS |
| Lock release after success and failure | Parameterized reacquisition test | PASS |
| User-level macOS scheduling | Launch-agent path and `gui/{uid}` launchctl command | PASS |
| User-level Windows scheduling | `schtasks` current-user task command | PASS |
| User-level Linux scheduling | User units and `systemctl --user` commands | PASS |
| Unsupported environment is structured | Exact `scheduler.unsupported` result and zero commands | PASS |
| No cron fallback | All recorded native commands reject `cron` content | PASS |
| Regression suites | 186 Python and 66 Node tests, zero failures | PASS |

## Concerns

1. Native scheduler behavior is verified through generated artifacts and
   synthetic command runners. Actual host policy, login-session availability,
   and executable discovery remain platform certification work.
2. The portable atomic lock intentionally fails closed if a process is killed
   before `finally` executes; that can leave a stale lock file requiring local
   cleanup. Normal success and Python exception paths release it deterministically.
3. The repository brief uses `python`, but this environment exposes only
   `python3`; verification used `python3` throughout.

## Critical and Important review follow-up

Status: VERIFIED at implementation commit
`5c0a902574502e48e6f1e59f5daecb927aa7c987`.

The follow-up fixes and tests now prove:

- Linux timer text includes both `OnStartupSec` and `OnUnitActiveSec`; the
  inapplicable monotonic-timer `Persistent` setting is gone.
- Tests read the exact Linux service/timer text and macOS plist keys, assert
  Windows cadence argv and `0600` artifact modes, and scan the generated tree
  to prove that no cron artifact exists.
- Live-PID locks remain exclusive. Dead-PID locks are reclaimed, and malformed
  locks become reclaimable after a fixed one-hour age bound. Lock and receipt
  directories are `0700` on POSIX.
- Confirmed writes leave a hash-only `0600` local receipt. A later runner that
  shares the receipt store and repeats the same key/payload skips the write.
  Browser transport does not retry an ambiguous write.
- DESIGN now states that Apps Script does not honor `idempotencyKey`; it is a
  correlation token at that boundary, not a remote exactly-once guarantee.
- `python -m careeros run-job <job-id> [--json]` builds and invokes
  `JobRunner`, closes the encrypted store, and emits the standard JSON
  envelope. Missing runtime configuration also returns a structured envelope.
- Non-integer intervals fail validation, and unrepresentable Windows intervals
  return `scheduler.invalid_schedule` without invoking `schtasks`.

TDD RED was observed before the fixes:

```text
$ python3 -m pytest tests/careeros/test_jobs.py tests/careeros/test_sync.py -q
19 failed, 30 passed in 0.41s

$ python3 -m pytest tests/careeros/test_jobs.py::test_old_malformed_lock_is_reclaimed_instead_of_wedging_forever -q
1 failed in 0.07s
```

Fresh verification after `5c0a902574502e48e6f1e59f5daecb927aa7c987`:

```text
$ python3 -m pytest tests/careeros/test_jobs.py -q
29 passed in 0.08s

$ python3 -m pytest -q
203 passed in 0.95s

$ npm test
66 passed, 0 failed

$ python3 -m compileall -q careeros
exit 0

$ env -u CAREEROS_WEB_APP_URL -u CAREEROS_BRAGSHEET_ID python3 -m careeros run-job daily --json
{"ok": false, "command": "run-job", "data": {}, "errors": [{"code": "job.configuration", "message": "CAREEROS_WEB_APP_URL is required for run-job"}]}
exit 1 (expected structured configuration failure)
```

Remaining concerns:

1. Native installation is still covered by generated-artifact and command
   tests, not certification on real macOS and Windows hosts.
2. Local receipts prevent repeats only after a confirmed successful response.
   A process crash after a remote write but before receipt creation remains an
   ambiguous reconciliation case; no remote exactly-once claim is made.
3. This environment provides `python3`, not a `python` executable. Scheduler
   callers must use an interpreter argv that exists on the target host.
