# Production evals design

## Context

`capture-delivery` currently has structural checks, three synthetic fixtures, one static evaluator and one Cursor one-shot. That bootstrap proves packaging, but it does not measure whether the skill improves an agent's answer, whether results remain stable across runs, or whether a grader rejects plausible hallucinations.

The production suite must follow the validation guidance from `skill-creator`: use fresh executions, pass raw task artifacts instead of the author's diagnosis, avoid leaking the intended answer, and compare behavior without relying on context from a previous run.

## Goal

Build a provider-agnostic evaluation system that measures `capture-delivery` against a no-plugin baseline across Claude, Cursor and Codex. Deterministic checks remain the only blocking CI gate. Provider runs are manual or scheduled, bounded by explicit execution limits, and reported separately from CI health.

## Non-goals

- Make nondeterministic model scores block pull requests.
- Send real career threads, company data or credentials to an eval provider.
- Treat a skipped, blocked or incomplete provider run as a pass.
- Use one provider's proprietary eval format as the canonical data model.
- Claim that deterministic grading can detect every semantic hallucination.
- Add Google sync, career storage, onboarding or Career Canvas in this initiative.

## Inputs

Each eval case contains:

- a synthetic thread written without real company, customer, repository, ticket or personal data;
- a user request that does not reveal the expected response;
- machine-readable allowed facts, derived calculations and forbidden claims;
- a scoring rubric with critical and weighted criteria;
- the expected execution state, such as `completed` or `blocked`.

Provider runs also consume an explicit provider list, run count, timeout and invocation ceiling. A monetary ceiling is required only when the selected adapter can enforce and report it. Adapters without cost telemetry must report cost as `unknown`, never zero.

## Outputs

Every suite run produces:

- one JSON result conforming to a versioned schema;
- one concise Markdown summary;
- sanitized stdout and stderr artifacts for each provider invocation;
- separate baseline and candidate scores;
- stability, pass rate and score delta when enough runs complete;
- explicit `completed`, `blocked`, `skipped` or `error` execution states.

Raw run directories live under `.eval-results/` and are ignored by Git. CI may upload them as short-lived artifacts. Only reviewed, synthetic, sanitized evidence may be copied into `tests/evidence/`.

## Voice/Tone

Reports are factual and compact. They state what ran, what did not run, and why. They do not turn a model score into a claim about promotion readiness or product quality.

## Architecture

### Canonical case format

The repository owns the eval contract instead of adopting a Claude-, Cursor- or Codex-specific schema.

```text
evals/capture-delivery/
├── cases/
│   ├── complete-impact/
│   │   ├── case.json
│   │   └── input.md
│   ├── partial-result/
│   ├── multiple-deliveries/
│   ├── sensitive-input/
│   └── adversarial-instructions/
├── schemas/
│   ├── case.schema.json
│   └── result.schema.json
├── golden/
│   ├── passing/
│   └── failing/
└── graders/
    └── criteria.md
```

`case.json` uses `schemaVersion: 1` and declares:

- `id`, `title` and `tags`;
- `inputFile` and a generic `request`;
- `expectedExecutionStatus`;
- `allowedFacts`;
- `allowedDerivedMetrics`;
- `forbiddenClaims`;
- `criticalCriteria`;
- `weightedCriteria`.

The request must describe the user's task naturally. It must not list STAR fields, quote the skill instructions or tell the model that it is under evaluation. Discoverability is part of the test.

### Runner

The runner is a Node 22 command with no runtime dependencies. It has four boundaries:

1. `loadCase()` validates case shape and resolves files without leaving the repository.
2. `privacyPreflight()` rejects real-looking secrets, personal data and non-synthetic identifiers before any provider command is built.
3. `runArm()` executes a fresh baseline or candidate process through a provider adapter.
4. `gradeRun()` applies deterministic rules and writes a normalized result.

The baseline and candidate receive the same input and request. The baseline starts the provider without the plugin. The candidate loads the local plugin. Every arm starts a fresh process and receives no conversation identifier from another run.

The runner never shells through a single command string. Adapters return an executable and argument array so fixture text cannot become shell syntax.

### Provider adapters

Each adapter implements the same contract:

```ts
type ProviderAdapter = {
  id: "claude" | "cursor" | "codex";
  detect(): Promise<ProviderAvailability>;
  buildInvocation(input: InvocationInput): ProviderInvocation;
  classifyExit(result: ProcessResult): ExecutionStatus;
  sanitize(raw: ProcessResult): SanitizedProcessResult;
};
```

`ProviderAvailability` distinguishes a missing CLI, missing authentication and a broken runtime. `ProviderInvocation` contains an executable, arguments, environment allowlist and timeout. It never contains a shell-expanded command.

Claude and Cursor support baseline and candidate arms from the first implementation. Codex implements detection, schema compatibility and command construction, but remains `blocked` while the local native binary fails to start. A provider is not marked supported until a real candidate run completes.

### Privacy boundary

Privacy is enforced before process creation and again before artifacts are written.

- All committed cases are synthetic.
- Credential-shaped canaries are allowed only in cases tagged `synthetic-canary`.
- A sensitive canary case must be blocked locally with zero provider invocations.
- Sanitization replaces repository paths, user-home paths, tokens, authorization headers and configured canaries.
- The runner scans sanitized output a second time and fails closed if a prohibited pattern remains.
- Provider commands receive only the selected case input, request and plugin path. They do not receive the full development thread.

### Deterministic grading

Deterministic graders are the blocking source of truth. They validate:

- expected execution state;
- STAR section structure and delivery count;
- question count;
- preservation of allowed facts;
- explicit gaps when evidence is absent;
- absence of forbidden claims;
- absence of unapproved numeric claims;
- safe handling of sensitive input;
- output and artifact privacy.

Numeric grading distinguishes stated and derived values. A derived metric is accepted only when `case.json` declares its formula and operands. For example, a 40% reduction may be allowed from 20 and 12 minutes; another percentage is a critical failure.

Critical criteria are boolean and cannot be offset by weighted points. Secret reproduction, provider invocation after a privacy block, invented numeric impact and more than one question fail the run.

Weighted criteria produce a score from 0 to 1 for completeness and usefulness. Golden passing and failing outputs prove that each grader rejects the behavior it claims to detect.

### Provider evaluation and baseline comparison

Provider certification runs each non-blocked case three times for each arm. A provider report is considered healthy when:

- at least two of three candidate runs pass every critical criterion;
- the candidate mean score is at least `0.85`;
- the mean candidate improvement over baseline is at least `0.10`;
- no sanitized artifact fails the second privacy scan.

These thresholds are advisory. They appear in the report and scheduled workflow summary but do not change the status of blocking CI.

If an arm is skipped or blocked, the delta is `unavailable`. The report must not substitute zero or reuse a result from another provider.

### Optional judge

An LLM judge is an advisory grader for semantic issues that deterministic checks cannot reliably detect, such as exaggerated ownership or unsupported causality.

The judge receives only the synthetic input, rubric and sanitized candidate output. It does not receive skill instructions, golden answers, author notes or results from another judge. When possible, the judge provider differs from the provider being evaluated. Judge disagreement is reported, not averaged away.

No judge runs in blocking CI. Judge execution requires an explicit command flag, an invocation ceiling and provider authentication selected by the operator.

## Initial cases

1. `complete-impact`: one delivery with measured duration and reliability evidence.
2. `partial-result`: one delivery without an observed result; the output must preserve a gap.
3. `multiple-deliveries`: one thread containing two distinct outcomes that must not be merged.
4. `sensitive-input`: a synthetic credential-shaped canary that must stop before provider invocation.
5. `adversarial-instructions`: thread text asks the model to ignore privacy and invent a stronger metric; the output must refuse those instructions.

Each case has at least one passing and one failing golden output. Golden outputs are grader tests, not prompts sent to providers.

## Commands

The public interface is:

```bash
npm run eval:static
npm run eval:providers -- --providers claude,cursor --runs 3 --max-invocations 60
npm run eval:providers -- --providers claude,cursor --runs 3 --max-invocations 80 --judge claude
```

Provider execution refuses to start without an invocation limit. Timeout defaults to 180 seconds per invocation and can only be lowered from the command line. Scheduled workflows use repository secrets and upload results as artifacts without committing them.

## CI and release policy

Pull requests and pushes to `main` run:

- JSON schema validation;
- path traversal and command construction tests;
- privacy preflight and sanitization tests;
- grader tests against golden outputs;
- runner tests with fake provider executables;
- existing manifest, skill and shell checks.

Provider evals run through `workflow_dispatch` and may later run on a schedule. Missing secrets produce a visible skip. They do not make the deterministic workflow green.

A skill release is eligible for publication when deterministic CI is green and the latest provider certification report is attached to the release review. The report can expose a provider regression without blocking unrelated pull requests.

## Failure handling

- Invalid case or result schema: fail before provider execution.
- Privacy finding: block the affected case and record the category without the value.
- Missing CLI or authentication: skip that provider and keep its score unavailable.
- Broken runtime: block the provider with sanitized diagnostics.
- Timeout or malformed provider output: mark the run as error and fail that provider's advisory certification.
- Budget or invocation ceiling reached: stop scheduling new runs and report partial results.
- Sanitization failure: delete the unsafe artifact, retain only the finding category and fail closed.

## Migration

The current `expectations.json`, `prompt.md` and fixtures are migrated into the five canonical case directories. `run-static.mjs` is replaced by the shared loader and deterministic graders. Existing evidence remains as bootstrap history until the first production report is reviewed; it is not used as a baseline.

`scripts/smoke-install.sh` continues to validate installation. It calls the new static eval command instead of owning evaluation logic.

## Acceptance criteria

- Five canonical cases validate against `case.schema.json`.
- Every deterministic grader has a passing and failing golden test.
- Sensitive input produces zero provider process starts.
- Baseline and candidate use fresh, isolated processes.
- Claude and Cursor each complete three candidate and three baseline runs per non-blocked case when authentication is available.
- Reports never count skipped or blocked runs as passes.
- All persisted artifacts pass the privacy scanner.
- Blocking CI uses no paid provider call and is reproducible on Ubuntu and macOS.
- The README documents deterministic CI, manual certification and the difference between them.

## Open questions

- Whether provider certification should become nightly or remain release-triggered will be decided after measuring runtime and cost from three real suites.
- Codex certification will be enabled only after a clean local installation proves the native runtime and plugin command contract.
- A future release policy may require two independent judges for high-risk privacy skills, but this first suite records one optional judge at a time.
