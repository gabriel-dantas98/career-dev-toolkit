# Production evals implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the bootstrap evaluator with a provider-agnostic, privacy-safe suite that compares fresh no-plugin baselines with plugin-enabled Claude and Cursor runs.

**Architecture:** A dependency-free Node 22 runner loads versioned JSON cases, applies privacy preflight, invokes providers through argument-array adapters, grades normalized outputs, and writes sanitized JSON and Markdown reports. CI runs only deterministic tests; provider certification is manual or dispatched.

**Tech Stack:** Node.js 22 ESM, `node:test`, JSON Schema documents, GitHub Actions, Claude Code CLI, Cursor Agent CLI.

## Global Constraints

- Deterministic checks are the only blocking CI gate.
- Provider fixtures contain synthetic data only.
- Provider processes receive one case, never the development thread.
- Baseline and candidate runs use fresh processes and isolated workspaces.
- Provider execution requires `--max-invocations`.
- Timeout defaults to 180 seconds and may only be lowered.
- Skipped, blocked and error runs never count as passes.
- Raw results live under ignored `.eval-results/`.
- No runtime npm dependency is allowed.
- Existing Claude, Cursor and Codex packaging contracts remain valid.

---

### Task 1: Node test foundation and case contract

**Files:**
- Create: `package.json`
- Create: `evals/capture-delivery/schemas/case.schema.json`
- Create: `evals/capture-delivery/schemas/result.schema.json`
- Create: `evals/lib/contracts.mjs`
- Create: `evals/lib/cases.mjs`
- Test: `tests/evals/cases.test.mjs`
- Modify: `.gitignore`

**Interfaces:**
- Produces: `validateCase(value): CaseDefinition`, `loadCases(root): Promise<LoadedCase[]>`, `assertSafeRelativePath(root, value): string`.
- Consumes: Node 22 standard library only.

- [ ] **Step 1: Write failing contract tests**

Cover a valid literal case, missing `schemaVersion`, duplicate IDs, absolute input paths, `../` traversal and input paths resolving outside the case directory.

- [ ] **Step 2: Verify RED**

Run:

```bash
node --test tests/evals/cases.test.mjs
```

Expected: failure because `evals/lib/cases.mjs` does not exist.

- [ ] **Step 3: Implement minimal contract loader**

Use `fs/promises`, `path.resolve` and `path.relative`. Reject values that are not plain objects, schema versions other than `1`, missing required arrays, duplicate IDs and paths outside their case directory.

- [ ] **Step 4: Verify GREEN**

Run:

```bash
npm test -- tests/evals/cases.test.mjs
```

Expected: all case tests pass.

- [ ] **Step 5: Commit**

```bash
git add package.json .gitignore evals/capture-delivery/schemas evals/lib/contracts.mjs evals/lib/cases.mjs tests/evals/cases.test.mjs
git commit -m "feat: add versioned eval case contract"
```

---

### Task 2: Privacy preflight and artifact sanitization

**Files:**
- Create: `evals/lib/privacy.mjs`
- Test: `tests/evals/privacy.test.mjs`

**Interfaces:**
- Produces: `scanSensitive(text, options): PrivacyFinding[]`, `privacyPreflight(caseDefinition, input): PreflightResult`, `sanitizeText(text, context): SanitizedText`.
- Consumes: loaded case tags and configured synthetic canaries.

- [ ] **Step 1: Write failing privacy tests**

Use literal inputs for GitHub-style tokens, OpenAI-style keys, bearer headers, private keys, email addresses, repository paths and user-home paths. Prove that a `synthetic-canary` case is blocked locally and that the returned finding contains a category but not the matched value.

- [ ] **Step 2: Verify RED**

```bash
node --test tests/evals/privacy.test.mjs
```

Expected: module-not-found failure for `privacy.mjs`.

- [ ] **Step 3: Implement fail-closed scanning**

Return categories and character ranges internally. Do not expose the matched value in serialized findings. Replace all configured paths and sensitive patterns, then scan the sanitized result again.

- [ ] **Step 4: Verify GREEN**

```bash
npm test -- tests/evals/privacy.test.mjs
```

Expected: all privacy tests pass.

- [ ] **Step 5: Commit**

```bash
git add evals/lib/privacy.mjs tests/evals/privacy.test.mjs
git commit -m "feat: add eval privacy boundary"
```

---

### Task 3: Deterministic grader and golden outputs

**Files:**
- Create: `evals/lib/grader.mjs`
- Create: `evals/capture-delivery/golden/passing/*.md`
- Create: `evals/capture-delivery/golden/failing/*.md`
- Test: `tests/evals/grader.test.mjs`

**Interfaces:**
- Produces: `gradeOutput(caseDefinition, output): GradeResult`.
- Consumes: allowed facts, allowed derived metrics, forbidden claims, critical criteria and weighted criteria.

- [ ] **Step 1: Write failing grader tests**

Each test names the break it catches:

- missing STAR section;
- merged deliveries;
- second question;
- missing evidence gap;
- invented percentage;
- forbidden ownership claim;
- reproduced canary;
- allowed 40% derivation from 20 and 12;
- passing complete and partial outputs.

- [ ] **Step 2: Verify RED**

```bash
node --test tests/evals/grader.test.mjs
```

Expected: module-not-found failure for `grader.mjs`.

- [ ] **Step 3: Implement critical and weighted grading**

Critical failures force `passed: false`. Weighted criteria divide earned weight by total weight. Numeric claims are normalized before comparison; declared derived values are allowed.

- [ ] **Step 4: Mutation-check the grader**

Temporarily invert the question-count branch and verify the second-question test fails. Restore the branch and rerun.

- [ ] **Step 5: Verify GREEN**

```bash
npm test -- tests/evals/grader.test.mjs
```

Expected: all grader tests pass.

- [ ] **Step 6: Commit**

```bash
git add evals/lib/grader.mjs evals/capture-delivery/golden tests/evals/grader.test.mjs
git commit -m "feat: add deterministic STAR graders"
```

---

### Task 4: Canonical five-case suite

**Files:**
- Create: `evals/capture-delivery/cases/complete-impact/{case.json,input.md}`
- Create: `evals/capture-delivery/cases/partial-result/{case.json,input.md}`
- Create: `evals/capture-delivery/cases/multiple-deliveries/{case.json,input.md}`
- Create: `evals/capture-delivery/cases/sensitive-input/{case.json,input.md}`
- Create: `evals/capture-delivery/cases/adversarial-instructions/{case.json,input.md}`
- Test: `tests/evals/suite.test.mjs`
- Remove after migration: `evals/capture-delivery/expectations.json`
- Remove after migration: `evals/capture-delivery/prompt.md`
- Remove after migration: `tests/fixtures/capture-delivery/*.md`

**Interfaces:**
- Produces: five schema-valid cases with unique IDs and one local-block case.
- Consumes: case loader and grader contracts.

- [ ] **Step 1: Write failing suite tests**

Assert exactly five IDs, generic requests without STAR labels, no real identifiers, one blocked canary case and passing/failing golden coverage for every case.

- [ ] **Step 2: Verify RED**

```bash
node --test tests/evals/suite.test.mjs
```

Expected: failure because canonical case directories do not exist.

- [ ] **Step 3: Add cases and migrate fixtures**

Use synthetic organizations and systems only. The adversarial case contains thread text asking for privacy bypass and a stronger invented metric. The multiple-deliveries case contains two outcomes with distinct actions and results.

- [ ] **Step 4: Verify GREEN**

```bash
npm test -- tests/evals/suite.test.mjs
```

Expected: five cases and complete golden coverage pass.

- [ ] **Step 5: Commit**

```bash
git add evals/capture-delivery tests/evals/suite.test.mjs tests/fixtures/capture-delivery
git commit -m "test: add canonical capture delivery cases"
```

---

### Task 5: Isolated provider adapters and process runner

**Files:**
- Create: `evals/lib/process.mjs`
- Create: `evals/lib/adapters/claude.mjs`
- Create: `evals/lib/adapters/cursor.mjs`
- Create: `evals/lib/adapters/codex.mjs`
- Create: `evals/lib/adapters/index.mjs`
- Create: `tests/fixtures/fake-provider.mjs`
- Test: `tests/evals/process.test.mjs`
- Test: `tests/evals/adapters.test.mjs`

**Interfaces:**
- Produces: `runProcess(invocation): Promise<ProcessResult>`, `getAdapter(id): ProviderAdapter`.
- Consumes: executable and argument arrays; no shell command strings.

- [ ] **Step 1: Write failing process tests**

Prove literal shell metacharacters remain arguments, timeout returns `error`, environment uses an allowlist, output is bounded and a new workspace is created per run.

- [ ] **Step 2: Verify RED**

```bash
node --test tests/evals/process.test.mjs tests/evals/adapters.test.mjs
```

Expected: modules do not exist.

- [ ] **Step 3: Implement process boundary**

Use `spawn()` with `shell: false`, a detached process group, bounded stdout/stderr and guaranteed temporary-directory cleanup.

- [ ] **Step 4: Implement adapters**

- Claude baseline uses an isolated `CLAUDE_CONFIG_DIR`; candidate adds `--plugin-dir <repo>`.
- Cursor baseline omits `--plugin-dir`; candidate adds it.
- Codex detection records the current native-runtime failure and does not claim candidate support.

- [ ] **Step 5: Verify GREEN**

```bash
npm test -- tests/evals/process.test.mjs tests/evals/adapters.test.mjs
```

Expected: all adapter and process tests pass.

- [ ] **Step 6: Commit**

```bash
git add evals/lib/process.mjs evals/lib/adapters tests/fixtures/fake-provider.mjs tests/evals/process.test.mjs tests/evals/adapters.test.mjs
git commit -m "feat: add isolated provider adapters"
```

---

### Task 6: Suite orchestration and reports

**Files:**
- Create: `evals/lib/runner.mjs`
- Create: `evals/lib/report.mjs`
- Create: `evals/cli.mjs`
- Test: `tests/evals/runner.test.mjs`
- Test: `tests/evals/report.test.mjs`

**Interfaces:**
- Produces: `runSuite(options): Promise<SuiteResult>`, `renderMarkdown(result): string`, CLI commands `static` and `providers`.
- Consumes: cases, privacy, adapters, process runner and grader.

- [ ] **Step 1: Write failing orchestration tests**

Test zero provider starts for blocked cases, fresh baseline/candidate calls, invocation-ceiling refusal, partial result when ceiling is reached, unavailable delta for skipped arms, two-of-three stability and no skip counted as pass.

- [ ] **Step 2: Verify RED**

```bash
node --test tests/evals/runner.test.mjs tests/evals/report.test.mjs
```

Expected: runner and report modules do not exist.

- [ ] **Step 3: Implement runner**

Generate a run ID, enforce the invocation ceiling before scheduling, grade every completed arm and write one result directory atomically.

- [ ] **Step 4: Implement reports and CLI**

Write `result.json`, `summary.md` and sanitized per-invocation artifacts. Refuse provider mode without `--max-invocations`. Return nonzero only for deterministic failures or malformed execution, not for an advisory provider regression.

- [ ] **Step 5: Verify GREEN**

```bash
npm test -- tests/evals/runner.test.mjs tests/evals/report.test.mjs
npm run eval:static
```

Expected: tests pass and five deterministic cases receive results.

- [ ] **Step 6: Commit**

```bash
git add evals/lib/runner.mjs evals/lib/report.mjs evals/cli.mjs tests/evals/runner.test.mjs tests/evals/report.test.mjs package.json
git commit -m "feat: add eval orchestration and reports"
```

---

### Task 7: Optional adversarial judge

**Files:**
- Create: `evals/lib/judge.mjs`
- Test: `tests/evals/judge.test.mjs`
- Modify: `evals/cli.mjs`
- Modify: `evals/lib/runner.mjs`

**Interfaces:**
- Produces: `buildJudgeRequest(input): JudgeRequest`, `parseJudgeResult(output): JudgeResult`.
- Consumes: synthetic case input, deterministic rubric, sanitized candidate output and a selected provider adapter.

- [ ] **Step 1: Write failing judge tests**

Prove the request excludes skill instructions and golden outputs, rejects unsanitized candidate text, parses only schema-valid JSON, records disagreement without averaging it away and refuses to run without enough remaining invocations.

- [ ] **Step 2: Verify RED**

```bash
node --test tests/evals/judge.test.mjs
```

Expected: module-not-found failure for `judge.mjs`.

- [ ] **Step 3: Implement the advisory judge**

Send only the case input, rubric and sanitized candidate response. Request a JSON object containing `supportedOwnership`, `supportedCausality`, `unsupportedClaims`, `score` and `reason`. Keep the deterministic grade unchanged.

- [ ] **Step 4: Integrate the CLI flag**

`--judge <provider>` consumes the same invocation ceiling as subject runs. Warn when judge and subject providers are equal. A missing or malformed judge result becomes `unavailable`, not a deterministic failure.

- [ ] **Step 5: Verify GREEN**

```bash
npm test -- tests/evals/judge.test.mjs tests/evals/runner.test.mjs
```

Expected: judge and runner tests pass.

- [ ] **Step 6: Commit**

```bash
git add evals/lib/judge.mjs evals/lib/runner.mjs evals/cli.mjs tests/evals/judge.test.mjs
git commit -m "feat: add optional adversarial judge"
```

---

### Task 8: CI, manual certification workflow and documentation

**Files:**
- Modify: `.github/workflows/smoke-test.yml`
- Create: `.github/workflows/provider-evals.yml`
- Modify: `scripts/smoke-install.sh`
- Modify: `README.md`
- Modify: `tests/evidence/README.md`
- Modify: `.gitignore`

**Interfaces:**
- Produces: blocking token-free CI and non-blocking `workflow_dispatch` provider certification.
- Consumes: npm scripts from Task 6.

- [ ] **Step 1: Write failing integration checks**

Add `tests/smoke/check-eval-integration.sh` that runs `npm run eval:static`, asserts `.eval-results` is ignored and verifies provider workflow has `workflow_dispatch` without being required by `smoke-test`.

- [ ] **Step 2: Verify RED**

```bash
bash tests/smoke/check-eval-integration.sh
```

Expected: failure because the workflow and smoke integration do not exist.

- [ ] **Step 3: Update workflows and docs**

Blocking CI runs `npm test` and `npm run eval:static`. Manual workflow accepts provider, runs and invocation-limit inputs, uses configured secrets, uploads `.eval-results`, and reports missing credentials as skip.

- [ ] **Step 4: Verify GREEN**

```bash
bash tests/smoke/check-eval-integration.sh
bash scripts/smoke-install.sh structure
```

Expected: both pass.

- [ ] **Step 5: Commit**

```bash
git add .github README.md .gitignore scripts/smoke-install.sh tests/evidence/README.md tests/smoke/check-eval-integration.sh
git commit -m "ci: add deterministic and provider eval workflows"
```

---

### Task 9: Real baseline and candidate certification

**Files:**
- Create from command: `.eval-results/<run-id>/`
- Update only after privacy review: `tests/evidence/provider-certification.json`
- Update only after privacy review: `tests/evidence/provider-certification.md`
- Modify only if a measured failure requires it: `skills/capture-delivery/SKILL.md`

**Interfaces:**
- Produces: real Claude and Cursor baseline/candidate evidence.
- Consumes: authenticated local CLIs and a maximum of 60 invocations.

- [ ] **Step 1: Run one-case smoke per provider**

```bash
npm run eval:providers -- --providers claude,cursor --runs 1 --case complete-impact --max-invocations 4
```

Expected: fresh baseline and candidate results or an explicit provider skip/block.

- [ ] **Step 2: Inspect every output**

Confirm no expected answer, skill text, local path, credential or unrelated thread context appears in artifacts.

- [ ] **Step 3: Run certification**

```bash
npm run eval:providers -- --providers claude,cursor --runs 3 --max-invocations 60
```

Expected: four non-blocked cases per provider, three baseline and three candidate runs each; sensitive input starts zero provider processes.

- [ ] **Step 4: Apply skill TDD if needed**

If baseline and candidate expose a specific skill failure, preserve the failing provider result, make the smallest `SKILL.md` change that addresses it, validate metadata, and rerun the affected case before the full suite.

- [ ] **Step 5: Curate evidence**

Copy only sanitized aggregate JSON and Markdown into `tests/evidence/`. Run:

```bash
bash tests/smoke/check-evidence-privacy.sh
```

Expected: pass.

- [ ] **Step 6: Commit**

```bash
git add skills/capture-delivery tests/evidence
git commit -m "test: record provider certification"
```

Skip the commit when no reviewed evidence changed.

---

### Task 10: Final verification and publication

**Files:**
- Verify all changed files.

**Interfaces:**
- Produces: reviewed PR, green CI and integrated `main`.

- [ ] **Step 1: Run the full local gate**

```bash
npm test
npm run eval:static
shellcheck scripts/*.sh tests/smoke/*.sh
claude plugin validate . --strict
bash scripts/smoke-install.sh structure
```

Expected: every command exits zero.

- [ ] **Step 2: Validate plugin and skill**

```bash
uv run --with pyyaml python ~/.codex/skills/.system/skill-creator/scripts/quick_validate.py skills/capture-delivery
uv run --with pyyaml python ~/.codex/skills/.system/plugin-creator/scripts/validate_plugin.py .
```

Expected: both official validators pass.

- [ ] **Step 3: Push and create PR**

```bash
git push -u origin feat/production-evals
gh pr create --base main --head feat/production-evals
```

Use the review-pack format in the PR body.

- [ ] **Step 4: Wait for CI**

```bash
gh pr checks --watch
```

Expected: deterministic plugin checks and Claude manifest validation pass.

- [ ] **Step 5: Merge and verify**

```bash
gh pr merge --squash --delete-branch
gh run list --branch main --limit 5
```

Expected: PR merged, `main` workflow completed successfully, local feature work preserved until verification ends.
