# CareerOS Task 10 verification

Run date: 2026-08-20 UTC

All commands ran from the repository root. The host has no `python` executable, so the plan's `python -m pytest -q` command was run as `python3 -m pytest -q`. In the output below, the repository root in the static-eval report path is sanitized to `<repo>`; all other command output is reproduced exactly.

## Interpreter probe

Command:

```bash
if command -v python >/dev/null 2>&1; then
  printf 'python=%s\n' "$(command -v python)"
else
  printf 'python=MISSING\n'
fi
printf 'python3=%s\n' "$(command -v python3)"
python3 --version
node --version
npm --version
```

Exit code: `0`

```text
python=MISSING
python3=/usr/bin/python3
Python 3.12.3
v22.14.0
10.9.7
```

## Required command results

### `python3 -m pytest -q`

Plan equivalent: `python -m pytest -q`

Exit code: `0`

```text
........................................................................ [ 32%]
........................................................................ [ 65%]
........................................................................ [ 98%]
....                                                                     [100%]
220 passed in 2.97s
```

### `bash tests/smoke/validate-structure.sh`

Exit code: `0`

```text
PASS: plugin structure is valid.
```

### `bash tests/smoke/check-capture-skill.sh`

Exit code: `0`

```text
PASS: capture-delivery contract is valid.
```

### `bash tests/smoke/check-careeros-skills.sh`

Exit code: `0`

```text
PASS: portable CareerOS skill contracts are valid.
```

### `bash tests/smoke/check-timeout.sh`

Exit code: `0`

```text
Command timed out after 1 seconds.
PASS: command timeout is bounded.
```

### `bash tests/smoke/check-evidence-privacy.sh`

Exit code: `0`

```text
PASS: evidence contains no user path or credential-shaped value.
```

This check was run again after creating both Task 10 evidence files; see Final privacy check.

### `bash tests/smoke/check-eval-integration.sh`

Exit code: `0`

```text
PASS: eval integration is correctly separated.
```

### `npm test`

Exit code: `0`

```text

> career-dev-toolkit@0.1.0 test
> node --test tests/evals/*.test.mjs tests/apps-script/*.test.mjs

TAP version 13
# Subtest: gateway exposes only the promised fixed action allowlist
ok 1 - gateway exposes only the promised fixed action allowlist
  ---
  duration_ms: 6.135676
  ...
# Subtest: aggregate npm test includes the gateway suite
ok 2 - aggregate npm test includes the gateway suite
  ---
  duration_ms: 0.20926
  ...
# Subtest: unknown actions fail in the stable envelope without echoing canaries
ok 3 - unknown actions fail in the stable envelope without echoing canaries
  ---
  duration_ms: 0.97532
  ...
# Subtest: sheet reads reject open-ended and broad ranges before provider access
ok 4 - sheet reads reject open-ended and broad ranges before provider access
  ---
  duration_ms: 6.052768
  ...
# Subtest: search actions require finite windows and bounded counts
ok 5 - search actions require finite windows and bounded counts
  ---
  duration_ms: 1.296879
  ...
# Subtest: Gmail rejects grouping and token-delimited OR before GmailApp
ok 6 - Gmail rejects grouping and token-delimited OR before GmailApp
  ---
  duration_ms: 1.20598
  ...
# Subtest: stale timestamps, invalid nonces, and replayed nonces fail closed
ok 7 - stale timestamps, invalid nonces, and replayed nonces fail closed
  ---
  duration_ms: 5.90323
  ...
# Subtest: brag-sheet writes use one full-owned-window RAW update
ok 8 - brag-sheet writes use one full-owned-window RAW update
  ---
  duration_ms: 6.567589
  ...
# Subtest: one full-window update addresses only the owned rows and A:L
ok 9 - one full-window update addresses only the owned rows and A:L
  ---
  duration_ms: 1.215639
  ...
# Subtest: read-back uses UNFORMATTED_VALUE and pads the requested matrix
ok 10 - read-back uses UNFORMATTED_VALUE and pads the requested matrix
  ---
  duration_ms: 0.971415
  ...
# Subtest: a shrinking write clears stale owned rows without expanding ownership
ok 11 - a shrinking write clears stale owned rows without expanding ownership
  ---
  duration_ms: 10.042652
  ...
# Subtest: resource, body, matrix, and write/read-back bounds have stable errors
ok 12 - resource, body, matrix, and write/read-back bounds have stable errors
  ---
  duration_ms: 1.654142
  ...
# Subtest: Docs content is capped at the shared excerpt bound
ok 13 - Docs content is capped at the shared excerpt bound
  ---
  duration_ms: 0.660672
  ...
# Subtest: gateway has no arbitrary evaluation or property-based action dispatch
ok 14 - gateway has no arbitrary evaluation or property-based action dispatch
  ---
  duration_ms: 0.624215
  ...
# Subtest: Claude baseline excludes user settings and candidate adds only the plugin path
ok 15 - Claude baseline excludes user settings and candidate adds only the plugin path
  ---
  duration_ms: 1.360484
  ...
# Subtest: Cursor baseline omits plugin-dir and candidate uses an isolated workspace
ok 16 - Cursor baseline omits plugin-dir and candidate uses an isolated workspace
  ---
  duration_ms: 0.156521
  ...
# Subtest: Codex classifies the observed native ENOENT as blocked
ok 17 - Codex classifies the observed native ENOENT as blocked
  ---
  duration_ms: 0.192701
  ...
# Subtest: getAdapter rejects unknown providers
ok 18 - getAdapter rejects unknown providers
  ---
  duration_ms: 0.328704
  ...
# Subtest: validateCase accepts a complete version 1 case
ok 19 - validateCase accepts a complete version 1 case
  ---
  duration_ms: 4.015148
  ...
# Subtest: validateCase rejects a case without schemaVersion
ok 20 - validateCase rejects a case without schemaVersion
  ---
  duration_ms: 0.325347
  ...
# Subtest: assertSafeRelativePath rejects absolute and traversal paths
ok 21 - assertSafeRelativePath rejects absolute and traversal paths
  ---
  duration_ms: 0.158661
  ...
# Subtest: loadCases rejects duplicate ids
ok 22 - loadCases rejects duplicate ids
  ---
  duration_ms: 28.568117
  ...
# Subtest: loadCases rejects an input symlink or resolved path outside the case
ok 23 - loadCases rejects an input symlink or resolved path outside the case
  ---
  duration_ms: 4.556683
  ...
# Subtest: blocking smoke CI installs runtime and dev dependencies before Python tests
ok 24 - blocking smoke CI installs runtime and dev dependencies before Python tests
  ---
  duration_ms: 0.545148
  ...
# Subtest: gradeOutput accepts declared STAR evidence and a 40% derivation
ok 25 - gradeOutput accepts declared STAR evidence and a 40% derivation
  ---
  duration_ms: 15.413016
  ...
# Subtest: gradeOutput requires an explicit evidence gap for partial results
ok 26 - gradeOutput requires an explicit evidence gap for partial results
  ---
  duration_ms: 6.551478
  ...
# Subtest: gradeOutput rejects a second question
ok 27 - gradeOutput rejects a second question
  ---
  duration_ms: 2.197593
  ...
# Subtest: gradeOutput rejects an invented numeric impact
ok 28 - gradeOutput rejects an invented numeric impact
  ---
  duration_ms: 0.805644
  ...
# Subtest: gradeOutput rejects merged deliveries
ok 29 - gradeOutput rejects merged deliveries
  ---
  duration_ms: 0.786003
  ...
# Subtest: gradeOutput rejects a reproduced credential canary
ok 30 - gradeOutput rejects a reproduced credential canary
  ---
  duration_ms: 0.29247
  ...
# Subtest: gradeOutput rejects a missing STAR section
ok 31 - gradeOutput rejects a missing STAR section
  ---
  duration_ms: 0.620543
  ...
# Subtest: gradeOutput accepts equivalent number words and time units
ok 32 - gradeOutput accepts equivalent number words and time units
  ---
  duration_ms: 0.33608
  ...
# Subtest: gradeOutput separates draft claims from review commentary and enumeration
ok 33 - gradeOutput separates draft claims from review commentary and enumeration
  ---
  duration_ms: 0.480413
  ...
# Subtest: buildJudgeRequest contains only input, rubric and sanitized candidate output
ok 34 - buildJudgeRequest contains only input, rubric and sanitized candidate output
  ---
  duration_ms: 1.340037
  ...
# Subtest: buildJudgeRequest refuses unsanitized candidate content
ok 35 - buildJudgeRequest refuses unsanitized candidate content
  ---
  duration_ms: 0.485656
  ...
# Subtest: parseJudgeResult accepts only the declared JSON shape
ok 36 - parseJudgeResult accepts only the declared JSON shape
  ---
  duration_ms: 5.884513
  ...
# Subtest: judge results remain independent instead of being averaged
ok 37 - judge results remain independent instead of being averaged
  ---
  duration_ms: 0.143038
  ...
# Subtest: scanSensitive identifies github-token without returning its value
ok 38 - scanSensitive identifies github-token without returning its value
  ---
  duration_ms: 1.423722
  ...
# Subtest: scanSensitive identifies api-key without returning its value
ok 39 - scanSensitive identifies api-key without returning its value
  ---
  duration_ms: 0.304603
  ...
# Subtest: scanSensitive identifies authorization-header without returning its value
ok 40 - scanSensitive identifies authorization-header without returning its value
  ---
  duration_ms: 0.100192
  ...
# Subtest: scanSensitive identifies private-key without returning its value
ok 41 - scanSensitive identifies private-key without returning its value
  ---
  duration_ms: 4.19055
  ...
# Subtest: scanSensitive identifies email without returning its value
ok 42 - scanSensitive identifies email without returning its value
  ---
  duration_ms: 0.181006
  ...
# Subtest: privacyPreflight blocks a synthetic canary before provider execution
ok 43 - privacyPreflight blocks a synthetic canary before provider execution
  ---
  duration_ms: 0.694923
  ...
# Subtest: sanitizeText removes user paths, repository paths and sensitive values
ok 44 - sanitizeText removes user paths, repository paths and sensitive values
  ---
  duration_ms: 0.242787
  ...
# Subtest: sanitizeText fails closed when prohibited content remains
ok 45 - sanitizeText fails closed when prohibited content remains
  ---
  duration_ms: 0.340791
  ...
# Subtest: runProcess passes shell metacharacters as literal arguments
ok 46 - runProcess passes shell metacharacters as literal arguments
  ---
  duration_ms: 63.037153
  ...
# Subtest: runProcess creates and removes a fresh workspace for every call
ok 47 - runProcess creates and removes a fresh workspace for every call
  ---
  duration_ms: 68.139594
  ...
# Subtest: createAllowedEnv excludes unspecified environment variables
ok 48 - createAllowedEnv excludes unspecified environment variables
  ---
  duration_ms: 40.616676
  ...
# Subtest: runProcess returns error when the timeout expires
ok 49 - runProcess returns error when the timeout expires
  ---
  duration_ms: 58.497821
  ...
# Subtest: runProcess bounds captured output
ok 50 - runProcess bounds captured output
  ---
  duration_ms: 24.823394
  ...
# Subtest: renderMarkdown reports skipped runs without presenting them as passing
ok 51 - renderMarkdown reports skipped runs without presenting them as passing
  ---
  duration_ms: 0.787161
  ...
# Subtest: writeReport writes normalized JSON, Markdown and sanitized artifacts
ok 52 - writeReport writes normalized JSON, Markdown and sanitized artifacts
  ---
  duration_ms: 11.769272
  ...
# Subtest: renderMarkdown reports judge disagreement without averaging it
ok 53 - renderMarkdown reports judge disagreement without averaging it
  ---
  duration_ms: 0.226357
  ...
# Subtest: runSuite blocks sensitive input without starting a provider
ok 54 - runSuite blocks sensitive input without starting a provider
  ---
  duration_ms: 24.563638
  ...
# Subtest: runSuite starts fresh baseline and candidate invocations
ok 55 - runSuite starts fresh baseline and candidate invocations
  ---
  duration_ms: 18.969867
  ...
# Subtest: provider mode refuses to run without an invocation ceiling
ok 56 - provider mode refuses to run without an invocation ceiling
  ---
  duration_ms: 0.36602
  ...
# Subtest: runSuite stops scheduling after the invocation ceiling
ok 57 - runSuite stops scheduling after the invocation ceiling
  ---
  duration_ms: 4.440716
  ...
# Subtest: summarizeProvider leaves delta unavailable when an arm is skipped
ok 58 - summarizeProvider leaves delta unavailable when an arm is skipped
  ---
  duration_ms: 0.143818
  ...
# Subtest: summarizeProvider requires two passing candidate runs out of three
ok 59 - summarizeProvider requires two passing candidate runs out of three
  ---
  duration_ms: 0.140454
  ...
# Subtest: runSuite attaches an advisory judge result within the same ceiling
ok 60 - runSuite attaches an advisory judge result within the same ceiling
  ---
  duration_ms: 4.917435
  ...
# Subtest: capture-delivery suite contains exactly five canonical cases
ok 61 - capture-delivery suite contains exactly five canonical cases
  ---
  duration_ms: 20.765991
  ...
# Subtest: case requests do not leak STAR labels or expected answers
ok 62 - case requests do not leak STAR labels or expected answers
  ---
  duration_ms: 8.560349
  ...
# Subtest: completed cases request capture-delivery when the provider exposes it
ok 63 - completed cases request capture-delivery when the provider exposes it
  ---
  duration_ms: 2.044872
  ...
# Subtest: only the synthetic canary case expects a local block
ok 64 - only the synthetic canary case expects a local block
  ---
  duration_ms: 2.3423
  ...
# Subtest: every case has passing and failing golden coverage
ok 65 - every case has passing and failing golden coverage
  ---
  duration_ms: 5.427193
  ...
# Subtest: golden outputs prove each completed case can pass and fail
ok 66 - golden outputs prove each completed case can pass and fail
  ---
  duration_ms: 14.045568
  ...
1..66
# tests 66
# suites 0
# pass 66
# fail 0
# cancelled 0
# skipped 0
# todo 0
# duration_ms 574.488854
```

### `npm run eval:static`

Exit code: `0`

```text

> career-dev-toolkit@0.1.0 eval:static
> node evals/cli.mjs static

Report: <repo>/.eval-results/2026-08-20T13-18-41-396Z
Cases: 5
```

### `npm run eval:careeros`

Exit code: `0`

```text

> career-dev-toolkit@0.1.0 eval:careeros
> PYTHONPATH=. python3 -m evals.careeros.run

{"counts": {"gatewayReadBacks": 1, "gatewayRequests": 3, "gatewayWrites": 1, "mergedRecords": 1, "persistedRecords": 1, "promotionWorkCards": 1, "rejectedRecords": 1, "sourceObservations": 3, "timelineCards": 1, "validationIssues": 1}, "ruleIds": {"backgroundConsent": ["consent.background.required"], "encryptedStore": ["store.sqlcipher.active", "store.plaintext.rejected", "store.reopen.succeeded"], "harvest": ["harvest.overlap.merged", "harvest.persistence.succeeded"], "outputs": ["outputs.period.resolved"], "privacy": ["privacy.blocked"], "readBack": ["sync.read_back.exact"], "safeWrite": ["sync.raw.required", "sync.synced"], "validation": ["impact.evidence.missing"]}, "schemaVersion": 1, "stages": {"backgroundConsent": "passed", "encryptedStore": "passed", "harvest": "passed", "outputs": "passed", "privacy": "passed", "readBack": "passed", "safeWrite": "passed", "validation": "passed"}, "status": "passed"}
```

The formatted report was copied without modification from `.eval-results/careeros/report.json` to `tests/evidence/careeros-eval.json`.

### `npm run test:python`

Exit code: `0`

```text

> career-dev-toolkit@0.1.0 test:python
> PYTHONPATH=. python3 -m pytest tests/careeros -q

........................................................................ [ 32%]
........................................................................ [ 65%]
........................................................................ [ 98%]
....                                                                     [100%]
220 passed in 2.88s
```

## Gist backlog audit

Status meanings:

- `IMPLEMENTED`: the named local contract has an implementation and a passing deterministic test.
- `PARTIAL`: part of the named behavior is implemented, but a material integration or user-facing surface is absent.
- `NOT RUN`: implementation may exist, but the stated external certification was not exercised.

### P0

| Item | Implementation path | Proving test or eval stage | Status |
|---|---|---|---|
| `harvest-retrospective` | `careeros/harvest.py`; `careeros/dedup.py`; `careeros/connectors/{thread,github,google}.py`; `skills/harvest-retrospective/` | `tests/careeros/test_harvest.py::test_harvest_merges_overlap_and_preserves_sources`; `tests/careeros/test_connectors.py`; eval `harvest` | `IMPLEMENTED` for bounded local/fake-provider collection |
| `write-bragsheet safe` | `careeros/projections.py`; `careeros/sync.py`; `careeros/google_client.py`; `apps-script/Code.gs`; `skills/write-bragsheet-safe/` | `tests/careeros/test_sync.py::test_ambiguous_period_is_forced_to_literal_text`; `::test_readback_mismatch_never_marks_synced`; `tests/apps-script/gateway.test.mjs`; eval `safeWrite` and `readBack` | `IMPLEMENTED` locally; live Google `NOT RUN` |
| `validate-bragsheet-integrity` | `careeros/validation.py`; `skills/validate-bragsheet-integrity/` | `tests/careeros/test_validation.py` covers title/tags, Jira uniqueness, merged-PR narrative and impact/evidence rules | `IMPLEMENTED` |
| `delivery-taxonomy` | `careeros/taxonomy.py`; taxonomy rules in `careeros/validation.py` | `tests/careeros/test_taxonomy.py`; `tests/careeros/test_validation.py::test_kudos_requires_name_and_month`; `::test_taxonomy_prefix_required`; `::test_taxonomy_confidence_exceeds_cap` | `IMPLEMENTED` as a shared library/validator, not a separate skill |
| `deploy-careeros-timeline` | `careeros/deploy.py`; `careeros/outputs.py::build_homepage`; `careeros/cli.py`; `skills/deploy-careeros-timeline/` | `tests/careeros/test_deploy.py::test_deploy_registers_exact_real_exec_url_and_homepage_uses_it`; `::test_deploy_refuses_before_external_mutation_when_clasp_health_fails` | `PARTIAL`: clasp/URL/homepage-model contract exists, but `apps-script/Code.gs::doGet` does not render a timeline; live Google `NOT RUN` |

### P1

| Item | Implementation path | Proving test or eval stage | Status |
|---|---|---|---|
| shared date library | `careeros/dates.py` | `tests/careeros/test_dates.py`; eval `outputs` resolves the ambiguous Brazilian date | `IMPLEMENTED` |
| epic-tree dedup validator | `careeros/validation.py` | `tests/careeros/test_validation.py::test_epic_tree_duplicates` | `IMPLEMENTED` |
| promotion packet builder | `careeros/outputs.py::build_promo_packet`; `skills/build-promo-packet/` | `tests/careeros/test_outputs.py::test_promo_packet_selects_at_most_twelve_work_cards_and_collapses_community`; eval `outputs` | `IMPLEMENTED` |
| Calendar -> Gmail -> unavailable-Luma date resolution | `careeros/enrichment.py::resolve_event_date` | `tests/careeros/test_policies.py::test_event_date_resolution_prefers_calendar_then_gmail`; `::test_event_date_marks_luma_unavailable_without_claiming_it_was_queried` | `IMPLEMENTED` as a deterministic policy; Luma collection is intentionally unavailable |
| Gmail kudos harvesting | `careeros/connectors/google.py::_gmail_observation`; `careeros/enrichment.py::enrich_kudos` | `tests/careeros/test_connectors.py::test_google_connector_bounded_search_invokes_gateway`; `tests/careeros/test_policies.py::test_kudos_enrichment_requires_name_and_month` | `PARTIAL`: bounded Gmail observations and kudos tagging exist, but sender/name/month extraction is not wired into a dedicated harvest flow |
| timeline UI data contract | `careeros/outputs.py::build_timeline` | `tests/careeros/test_outputs.py::test_timeline_ui_contract_has_version_and_required_card_fields` | `IMPLEMENTED` as data only; no rendered UI |
| Sheets homepage generator | `careeros/outputs.py::build_homepage`; registered by `careeros/deploy.py` | `tests/careeros/test_outputs.py::test_homepage_defaults_to_brag_document_gid_not_sheets_homepage_gid`; deployment tests | `PARTIAL`: deterministic homepage configuration exists, but no gateway action writes a Sheets homepage |

### P2

| Item | Implementation path | Proving test or eval stage | Status |
|---|---|---|---|
| hero metrics policy | `careeros/policies.py::validate_hero_metrics` | `tests/careeros/test_policies.py::test_hero_metrics_require_supporting_evidence_links`; vanity-metric tests | `IMPLEMENTED` |
| talk evidence enrichment | `careeros/enrichment.py::enrich_talk` | `tests/careeros/test_policies.py::test_talk_and_credential_enrichment_preserve_links_and_unresolved_states` | `PARTIAL`: evidence-bounded policy exists; no external talk source is connected |
| leader review pass | `careeros/review.py::leader_review` | `tests/careeros/test_policies.py::test_leader_review_is_deterministic_and_emits_findings_not_verdicts`; impact-support tests | `IMPLEMENTED` |
| timeline parity check | `careeros/policies.py::timeline_parity` | `tests/careeros/test_policies.py::test_timeline_parity_compares_complete_apps_script_compatible_preview` | `IMPLEMENTED` for data-contract parity |
| extended `capture-delivery` schema | `careeros/cli_commands.py::handle_capture_delivery`; `skills/capture-delivery/` | `tests/careeros/test_cli.py::test_capture_returns_fixed_draft_shape_with_explicit_star_gaps`; `check-capture-skill.sh`; `check-careeros-skills.sh` | `IMPLEMENTED` |
| external credential enrichment | `careeros/enrichment.py::enrich_credential` | `tests/careeros/test_policies.py::test_talk_and_credential_enrichment_preserve_links_and_unresolved_states` | `PARTIAL`: unresolved-state/evidence policy exists; no external credential provider is connected |

## External certification

| Certification | Status | Reason |
|---|---|---|
| Live Google OAuth, one Apps Script deployment, real source reads, RAW Sheets write, exact read-back and stale-row clearing | `NOT RUN` | Requires a user-authorized Google account and destination. No such account was used in this verification. |

## Final privacy check

Command:

```bash
bash tests/smoke/check-evidence-privacy.sh
```

Exit code: `0`

```text
PASS: evidence contains no user path or credential-shaped value.
```
