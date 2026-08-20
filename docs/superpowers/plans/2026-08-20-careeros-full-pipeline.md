# CareerOS Full Pipeline Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the complete self-contained CareerOS harvest, validation, encrypted storage, safe Google sync, output generation, deployment, and background-job pipeline.

**Architecture:** A shared Python package owns deterministic domain behavior and exposes one CLI. Thin portable skills call that CLI. A bounded Apps Script gateway is the only Google integration surface, and the encrypted local database remains canonical.

**Tech Stack:** Python 3.11+, stdlib `argparse`/`dataclasses`/`sqlite3`, `pysqlcipher3`, `keyring`, `pytest`, Google Apps Script, Node 22 deterministic eval harness.

## Global Constraints

- Never fall back to plaintext SQLite when SQLCipher or keychain access fails.
- Never weaken a privacy, consent, validation, or read-back gate.
- Never infer metrics, ownership, dates, causality, or impact.
- Use synthetic canaries only in tests and eval artifacts.
- Keep imports at module tops.
- Maintain one skill contract across Claude Code, Cursor, and Codex.
- One broad Apps Script deployment may serve Google sources and destinations, but every action remains allowlisted and bounded.
- Background synchronization requires a grant separate from connector and destination grants.
- Luma is an explicit unavailable extension point in this release.

---

### Task 1: Python package and deterministic contracts

**Files:**
- Create: `pyproject.toml`
- Create: `careeros/__init__.py`
- Create: `careeros/models.py`
- Create: `careeros/cli.py`
- Create: `careeros/__main__.py`
- Create: `careeros/DESIGN.md`
- Test: `tests/careeros/test_cli.py`
- Modify: `package.json`

**Interfaces:**
- Produces: `DeliveryRecord`, `EvidenceRef`, `ValidationIssue`, `CommandResult`, and `python -m careeros`.

- [ ] **Step 1: Write the failing CLI contract test**

```python
def test_version_is_machine_readable(run_cli):
    result = run_cli("version", "--json")
    assert result.returncode == 0
    assert json.loads(result.stdout) == {
        "ok": True,
        "command": "version",
        "data": {"schemaVersion": 1, "version": "0.2.0"},
        "errors": [],
    }
```

- [ ] **Step 2: Verify RED**

Run: `python -m pytest tests/careeros/test_cli.py -q`
Expected: FAIL because package `careeros` does not exist.

- [ ] **Step 3: Implement the typed result envelope and CLI**

```python
@dataclass(frozen=True)
class CommandResult:
    ok: bool
    command: str
    data: Mapping[str, object]
    errors: tuple[Mapping[str, object], ...] = ()

    def as_dict(self) -> dict[str, object]:
        return {
            "ok": self.ok,
            "command": self.command,
            "data": dict(self.data),
            "errors": [dict(error) for error in self.errors],
        }
```

Register `version`, JSON output, and a nonzero structured error for unknown commands. Add `npm run test:python`.

- [ ] **Step 4: Verify GREEN**

Run: `python -m pytest tests/careeros/test_cli.py -q && npm test`
Expected: both suites pass.

- [ ] **Step 5: Commit**

```bash
git add pyproject.toml careeros tests/careeros package.json
git commit -m "feat: add CareerOS Python runtime contracts"
```

### Task 2: Privacy, SQLCipher store, migrations, and consent

**Files:**
- Create: `careeros/privacy.py`
- Create: `careeros/crypto.py`
- Create: `careeros/store.py`
- Create: `careeros/consent.py`
- Create: `careeros/migrations/001_initial.sql`
- Test: `tests/careeros/test_privacy.py`
- Test: `tests/careeros/test_store.py`
- Test: `tests/careeros/test_consent.py`

**Interfaces:**
- Consumes: `CommandResult`.
- Produces: `scan_sensitive(text)`, `open_encrypted_store(config, keyring)`, `ConsentService.grant()`, `ConsentService.require()`, and `ConsentService.revoke()`.

- [ ] **Step 1: Write failing fail-closed tests**

```python
def test_store_refuses_driver_without_cipher(fake_keyring, tmp_path):
    with pytest.raises(StoreUnavailable, match="SQLCipher"):
        open_encrypted_store(
            StoreConfig(tmp_path / "career.db"),
            fake_keyring,
            connect=sqlite3.connect,
        )

def test_background_grant_does_not_follow_destination_grant(store):
    consent = ConsentService(store)
    consent.grant("destination", "sheet:synthetic-123", ("write:bragsheet",))
    with pytest.raises(ConsentDenied):
        consent.require("background", "job:daily-sync", "run")
```

- [ ] **Step 2: Verify RED**

Run: `python -m pytest tests/careeros/test_privacy.py tests/careeros/test_store.py tests/careeros/test_consent.py -q`
Expected: FAIL because the modules do not exist.

- [ ] **Step 3: Implement encrypted startup and scoped grants**

On connection execute `PRAGMA key`, then require a nonempty row from `PRAGMA cipher_version`. Store only keychain account metadata outside the database. Create versioned tables for records, evidence, grants, sync runs, and migrations. Re-check a grant immediately before each adapter call.

- [ ] **Step 4: Verify GREEN**

Run: `python -m pytest tests/careeros/test_privacy.py tests/careeros/test_store.py tests/careeros/test_consent.py -q`
Expected: all pass, including no-plaintext fallback and revocation.

- [ ] **Step 5: Commit**

```bash
git add careeros tests/careeros
git commit -m "feat: add encrypted store and scoped consent"
```

### Task 3: Dates, taxonomy, deduplication, and integrity validators

**Files:**
- Create: `careeros/dates.py`
- Create: `careeros/taxonomy.py`
- Create: `careeros/dedup.py`
- Create: `careeros/validation.py`
- Test: `tests/careeros/test_dates.py`
- Test: `tests/careeros/test_taxonomy.py`
- Test: `tests/careeros/test_validation.py`

**Interfaces:**
- Produces: `parse_period(value, reference_year)`, `quarters_for(period)`, `sort_start(period)`, `classify_context(record)`, `deduplicate(observations)`, and `validate_records(records, evidence)`.

- [ ] **Step 1: Write failing policy tests**

```python
@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("jan–mar", ("2026-01-01", "2026-03-31")),
        ("03/04/2026", ("2026-04-03", "2026-04-03")),
        ("Q2 2026", ("2026-04-01", "2026-06-30")),
    ],
)
def test_periods_parse_pt_br(value, expected):
    assert parse_period(value, reference_year=2026).iso_bounds == expected

def test_kudos_requires_name_and_month():
    issues = validate_records([synthetic_kudos(name="", month=None)], {})
    assert {issue.rule_id for issue in issues} == {
        "kudos.name.required",
        "kudos.month.required",
    }
```

Add cases for multi-quarter badges, start clamping, title↔tags, Jira uniqueness, merged PR narrative mismatch, Impact without evidence links, epic-tree duplicates, prefixes, and confidence caps.

- [ ] **Step 2: Verify RED**

Run: `python -m pytest tests/careeros/test_dates.py tests/careeros/test_taxonomy.py tests/careeros/test_validation.py -q`
Expected: FAIL because modules do not exist.

- [ ] **Step 3: Implement pure deterministic functions**

Return values and rule IDs, never prose-only booleans. Dedup groups observations by namespaced source IDs first, then normalized Jira/PR/evidence keys, preserving all provenance.

- [ ] **Step 4: Verify GREEN**

Run: `python -m pytest tests/careeros/test_dates.py tests/careeros/test_taxonomy.py tests/careeros/test_validation.py -q`
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add careeros tests/careeros
git commit -m "feat: add CareerOS domain policies and validators"
```

### Task 4: Connector protocol and retrospective harvest

**Files:**
- Create: `careeros/connectors/base.py`
- Create: `careeros/connectors/thread.py`
- Create: `careeros/connectors/github.py`
- Create: `careeros/connectors/google.py`
- Create: `careeros/harvest.py`
- Test: `tests/careeros/test_connectors.py`
- Test: `tests/careeros/test_harvest.py`

**Interfaces:**
- Produces: `Connector.collect(request) -> tuple[Observation, ...]`, `HarvestService.run(request) -> HarvestResult`.
- Google actions: `calendar.search`, `gmail.search`, `drive.search`, `docs.read`, `sheets.read`.

- [ ] **Step 1: Write failing bounded-collection tests**

```python
def test_google_connector_rejects_unbounded_mail_query(fake_gateway):
    connector = GoogleConnector(fake_gateway, consent=allow_google())
    with pytest.raises(ConnectorRequestInvalid, match="time window"):
        connector.collect(CollectRequest(source="gmail", query="recognition"))

def test_harvest_merges_overlap_and_preserves_sources():
    result = HarvestService(memory_store(), validators=[]).run(overlap_request())
    assert len(result.records) == 1
    assert {ref.connector for ref in result.records[0].evidence} == {
        "thread",
        "github",
    }
```

- [ ] **Step 2: Verify RED**

Run: `python -m pytest tests/careeros/test_connectors.py tests/careeros/test_harvest.py -q`
Expected: FAIL because connector modules do not exist.

- [ ] **Step 3: Implement connectors and transactional harvest**

GitHub invokes `gh api` with explicit fields and limits. Google sends only allowlisted action payloads. Thread ingestion accepts a caller-provided bounded excerpt and rejects sensitive input before parsing. Persist only after deterministic validation has no errors.

- [ ] **Step 4: Verify GREEN**

Run: `python -m pytest tests/careeros/test_connectors.py tests/careeros/test_harvest.py -q`
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add careeros tests/careeros
git commit -m "feat: harvest evidence through bounded connectors"
```

### Task 5: Safe brag-sheet projection and Apps Script gateway

**Files:**
- Create: `careeros/projections.py`
- Create: `careeros/sync.py`
- Create: `careeros/google_client.py`
- Create: `apps-script/Code.gs`
- Create: `apps-script/appsscript.json`
- Create: `apps-script/DESIGN.md`
- Test: `tests/careeros/test_sync.py`
- Test: `tests/apps-script/gateway.test.mjs`

**Interfaces:**
- Produces: `serialize_period(value)`, `SyncService.preview()`, `SyncService.write_and_verify()`.
- Apps Script response: `{ok, requestId, data, errors, version}`.

- [ ] **Step 1: Write failing safe-write tests**

```python
@pytest.mark.parametrize("value", ["03/04/2026", "04/03/2026", "1/2"])
def test_ambiguous_period_is_forced_to_literal_text(value):
    cell = serialize_period(value)
    assert cell.value == f"'{value}"
    assert cell.input_mode == "RAW"

def test_readback_mismatch_never_marks_synced(sync_service):
    with pytest.raises(ReadbackMismatch):
        sync_service.write_and_verify(synthetic_projection(), mismatching_gateway())
    assert sync_service.last_run.status == "reconciliation_required"
```

The Node gateway test must prove unknown actions are rejected, broad ranges are bounded, and response bodies never contain synthetic authorization canaries.

- [ ] **Step 2: Verify RED**

Run: `python -m pytest tests/careeros/test_sync.py -q && node --test tests/apps-script/gateway.test.mjs`
Expected: FAIL because sync and gateway files do not exist.

- [ ] **Step 3: Implement preview, raw writes, read-back, and allowlisted gateway**

Do not expose arbitrary method names. Reject requests outside fixed limits. Require request timestamp and nonce. Route Google reads and Sheets/Docs writes through named functions.

- [ ] **Step 4: Manually validate HTTP response structure**

Run a local synthetic gateway fixture and POST:

```bash
curl -sS -X POST http://127.0.0.1:8765/exec \
  -H 'content-type: application/json' \
  --data '{"action":"health","requestId":"synthetic-request","timestamp":1787198400,"nonce":"synthetic-nonce"}'
```

Expected JSON keys: `ok`, `requestId`, `data`, `errors`, `version`; `requestId` equals `synthetic-request`.

- [ ] **Step 5: Verify GREEN and commit**

Run: `python -m pytest tests/careeros/test_sync.py -q && node --test tests/apps-script/gateway.test.mjs`
Expected: all pass.

```bash
git add careeros apps-script tests
git commit -m "feat: add safe Sheets sync and Google gateway"
```

### Task 6: Deployment, homepage, timeline, promo packet, and P2 policies

**Files:**
- Create: `careeros/deploy.py`
- Create: `careeros/outputs.py`
- Create: `careeros/policies.py`
- Create: `careeros/review.py`
- Create: `careeros/enrichment.py`
- Test: `tests/careeros/test_deploy.py`
- Test: `tests/careeros/test_outputs.py`
- Test: `tests/careeros/test_policies.py`

**Interfaces:**
- Produces: `DeployService.deploy()`, `build_homepage()`, `build_timeline()`, `build_promo_packet()`, `leader_review()`, and enrichment results with explicit unresolved states.

- [ ] **Step 1: Write failing output policy tests**

```python
def test_promo_packet_has_twelve_or_fewer_work_cards_and_collapses_community():
    packet = build_promo_packet(thirteen_work_records(), community_records())
    assert 10 <= len(packet.work_cards) <= 12
    assert packet.community_summary.count == len(community_records())

def test_deploy_registers_real_exec_url(deployer):
    result = deployer.deploy()
    assert result.web_app_url.startswith("https://script.google.com/")
    assert result.web_app_url.endswith("/exec")
    assert result.homepage["webAppUrl"] == result.web_app_url
```

Add hero metrics evidence policy, talks evidence, leader review, external credential, UI contract, timeline parity, homepage `gid`, and Calendar→Gmail→unavailable-Luma resolution tests.

- [ ] **Step 2: Verify RED**

Run: `python -m pytest tests/careeros/test_deploy.py tests/careeros/test_outputs.py tests/careeros/test_policies.py -q`
Expected: FAIL because modules do not exist.

- [ ] **Step 3: Implement deterministic builders and deployment checks**

`DeployService` fails unless clasp health succeeds and the deployed URL is a real `/exec` URL. Builders include source links and evidence gaps; they never create impact metrics.

- [ ] **Step 4: Verify GREEN and commit**

Run: `python -m pytest tests/careeros/test_deploy.py tests/careeros/test_outputs.py tests/careeros/test_policies.py -q`
Expected: all pass.

```bash
git add careeros tests/careeros
git commit -m "feat: build and deploy CareerOS outputs"
```

### Task 7: Background jobs and revocation-safe orchestration

**Files:**
- Create: `careeros/jobs.py`
- Create: `careeros/scheduler.py`
- Test: `tests/careeros/test_jobs.py`

**Interfaces:**
- Produces: `JobRunner.run(job_id)`, `Scheduler.install(schedule)`, `Scheduler.remove(job_id)`.

- [ ] **Step 1: Write failing concurrency and revocation tests**

```python
def test_overlapping_job_exits_without_second_sync(locked_runner):
    result = locked_runner.run("daily")
    assert result.status == "already_running"
    assert locked_runner.gateway.calls == []

def test_revoked_background_grant_blocks_before_network(runner):
    runner.consent.revoke("background", "job:daily")
    with pytest.raises(ConsentDenied):
        runner.run("daily")
    assert runner.gateway.calls == []
```

- [ ] **Step 2: Verify RED**

Run: `python -m pytest tests/careeros/test_jobs.py -q`
Expected: FAIL because job modules do not exist.

- [ ] **Step 3: Implement exclusive locks, idempotency keys, and OS scheduler adapters**

Use user-level launchd on macOS, Task Scheduler on Windows, and systemd user timers on Linux. Unsupported scheduler environments return a structured error and do not silently install cron.

- [ ] **Step 4: Verify GREEN and commit**

Run: `python -m pytest tests/careeros/test_jobs.py -q`
Expected: all pass.

```bash
git add careeros tests/careeros
git commit -m "feat: add consent-safe background sync"
```

### Task 8: Portable skills and extended capture contract

**Files:**
- Create: `skills/harvest-retrospective/{DESIGN.md,SKILL.md}`
- Create: `skills/validate-bragsheet-integrity/{DESIGN.md,SKILL.md}`
- Create: `skills/write-bragsheet-safe/{DESIGN.md,SKILL.md}`
- Create: `skills/deploy-careeros-timeline/{DESIGN.md,SKILL.md}`
- Create: `skills/build-promo-packet/{DESIGN.md,SKILL.md}`
- Create: `skills/sync-careeros/{DESIGN.md,SKILL.md}`
- Modify: `skills/capture-delivery/{DESIGN.md,SKILL.md}`
- Modify: `tests/smoke/validate-structure.sh`
- Create: `tests/smoke/check-careeros-skills.sh`

**Interfaces:**
- Consumes: the CLI commands from Tasks 1–7.
- Produces: identical discoverable workflows on all three plugin platforms.

- [ ] **Step 1: Extend structure tests first**

Require every named skill to have `SKILL.md` and `DESIGN.md`, require all mutating workflows to state privacy and consent gates, and reject copied platform-specific behavior from skill bodies.

- [ ] **Step 2: Verify RED**

Run: `bash tests/smoke/validate-structure.sh && bash tests/smoke/check-careeros-skills.sh`
Expected: FAIL listing the missing skill files.

- [ ] **Step 3: Write thin skill contracts**

Each skill resolves repository root, invokes `python -m careeros`, requests at most one user action per onboarding turn, and never claims a write or deployment succeeded without the CLI's read-back/health result.

- [ ] **Step 4: Verify GREEN and commit**

Run: `bash tests/smoke/validate-structure.sh && bash tests/smoke/check-careeros-skills.sh`
Expected: both pass.

```bash
git add skills tests/smoke
git commit -m "feat: package portable CareerOS skills"
```

### Task 9: Deterministic full-pipeline eval

**Files:**
- Create: `evals/careeros/fake_gateway.py`
- Create: `evals/careeros/run.py`
- Create: `evals/careeros/schemas/report.schema.json`
- Create: `tests/careeros/test_e2e_eval.py`
- Modify: `package.json`

**Interfaces:**
- Produces: `npm run eval:careeros` and a sanitized report under `.eval-results/careeros/`.

- [ ] **Step 1: Write the failing E2E acceptance test**

```python
def test_eval_proves_required_pipeline(tmp_path):
    report = run_eval(tmp_path)
    assert report["status"] == "passed"
    assert report["stages"] == {
        "harvest": "passed",
        "privacy": "passed",
        "validation": "passed",
        "encryptedStore": "passed",
        "safeWrite": "passed",
        "readBack": "passed",
        "outputs": "passed",
        "backgroundConsent": "passed",
    }
    assert "SYNTHETIC_SECRET_CANARY" not in json.dumps(report)
```

- [ ] **Step 2: Verify RED**

Run: `python -m pytest tests/careeros/test_e2e_eval.py -q`
Expected: FAIL because the eval runner does not exist.

- [ ] **Step 3: Implement the synthetic E2E**

Use overlapping thread/GitHub/Google observations, one invalid impact record, one ambiguous BR date, a fake encrypted-store adapter that proves cipher activation, and an Apps Script-compatible HTTP fixture. Emit counts and rule IDs, not source bodies.

- [ ] **Step 4: Verify GREEN and commit**

Run: `python -m pytest tests/careeros/test_e2e_eval.py -q && npm run eval:careeros`
Expected: test passes and report status is `passed`.

```bash
git add evals tests/careeros package.json
git commit -m "test: add CareerOS end-to-end eval"
```

### Task 10: Documentation, full verification, and requirement audit

**Files:**
- Modify: `README.md`
- Modify: `DESIGN.md`
- Create: `tests/evidence/careeros-eval.json`
- Create: `tests/evidence/careeros-verification.md`

**Interfaces:**
- Produces: user setup/runbook, fresh verification evidence, and item-by-item P0/P1/P2 mapping.

- [ ] **Step 1: Update docs without unsupported claims**

Document keychain/SQLCipher requirements, one-deployment Google permissions, foreground/background consent, onboarding, commands, revocation, fake eval limits, and live Google certification status.

- [ ] **Step 2: Run complete verification**

```bash
python -m pytest -q
bash tests/smoke/validate-structure.sh
bash tests/smoke/check-capture-skill.sh
bash tests/smoke/check-careeros-skills.sh
bash tests/smoke/check-timeout.sh
bash tests/smoke/check-evidence-privacy.sh
bash tests/smoke/check-eval-integration.sh
npm test
npm run eval:static
npm run eval:careeros
```

Expected: every command exits 0. Preserve exact sanitized outputs in evidence files.

- [ ] **Step 3: Audit every gist item**

Record each P0/P1/P2 item, implementation path, proving test/eval stage, and status. Mark live Google deployment certification separately as `not run` unless a real user-authorized account was tested.

- [ ] **Step 4: Commit**

```bash
git add README.md DESIGN.md tests/evidence
git commit -m "docs: publish CareerOS verification evidence"
```
