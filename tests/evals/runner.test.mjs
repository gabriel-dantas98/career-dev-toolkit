import assert from "node:assert/strict";
import path from "node:path";
import test from "node:test";

import {
  runSuite,
  summarizeProvider,
} from "../../evals/lib/runner.mjs";

const suiteRoot = path.resolve("evals/capture-delivery");
const pluginRoot = path.resolve(".");

function fakeAdapter(id = "fake") {
  return {
    id,
    buildInvocation(input) {
      return {
        command: "fake",
        args: [input.arm, input.prompt],
        env: {},
        isolatedWorkspace: true,
      };
    },
    classifyExit(result) {
      return result.exitCode === 0
        ? { status: "completed", reason: null }
        : { status: "skipped", reason: "authentication-unavailable" };
    },
  };
}

const passingOutput = `### Reduced CI feedback time
- Situation: CI feedback took 20 minutes for six engineers.
- Task: Improve feedback speed without increasing flaky-test retries.
- Action: I profiled the suites and introduced bounded parallel execution.
- Result: Median duration fell from 20 minutes to 12 minutes, a 40% reduction, with no increase in flaky-test retries.
- Evidence: 20 minutes, 12 minutes, six engineers, no increase in flaky-test retries.
- Confidence: complete
`;

test("runSuite blocks sensitive input without starting a provider", async () => {
  let calls = 0;
  const result = await runSuite({
    mode: "providers",
    suiteRoot,
    pluginRoot,
    providers: ["fake"],
    runs: 1,
    maxInvocations: 2,
    caseFilter: "sensitive-input",
    getAdapter: () => fakeAdapter(),
    runProcess: async () => {
      calls += 1;
      throw new Error("provider must not start");
    },
  });

  assert.equal(calls, 0);
  assert.equal(result.cases[0].observedExecutionStatus, "blocked");
  assert.equal(result.cases[0].meetsExpectation, true);
});

test("runSuite starts fresh baseline and candidate invocations", async () => {
  const calls = [];
  const result = await runSuite({
    mode: "providers",
    suiteRoot,
    pluginRoot,
    providers: ["fake"],
    runs: 1,
    maxInvocations: 2,
    caseFilter: "complete-impact",
    getAdapter: () => fakeAdapter(),
    runProcess: async (invocation) => {
      calls.push(invocation);
      return {
        status: "completed",
        exitCode: 0,
        stdout: passingOutput,
        stderr: "",
        truncated: false,
        workspace: `/tmp/fresh-${calls.length}`,
      };
    },
  });

  assert.deepEqual(
    calls.map((call) => call.args[0]),
    ["baseline", "candidate"],
  );
  assert.notEqual(calls[0], calls[1]);
  assert.equal(result.invocations.used, 2);
});

test("provider mode refuses to run without an invocation ceiling", async () => {
  await assert.rejects(
    () =>
      runSuite({
        mode: "providers",
        suiteRoot,
        pluginRoot,
        providers: ["fake"],
        runs: 1,
      }),
    /maxInvocations/,
  );
});

test("runSuite stops scheduling after the invocation ceiling", async () => {
  let calls = 0;
  const result = await runSuite({
    mode: "providers",
    suiteRoot,
    pluginRoot,
    providers: ["fake"],
    runs: 2,
    maxInvocations: 1,
    caseFilter: "complete-impact",
    getAdapter: () => fakeAdapter(),
    runProcess: async () => {
      calls += 1;
      return {
        status: "completed",
        exitCode: 0,
        stdout: passingOutput,
        stderr: "",
        truncated: false,
        workspace: `/tmp/fresh-${calls}`,
      };
    },
  });

  assert.equal(calls, 1);
  assert.equal(result.invocations.limitReached, true);
  assert.ok(
    result.cases[0].providerResults[0].runs.some(
      (run) => run.executionStatus === "error",
    ),
  );
});

test("summarizeProvider leaves delta unavailable when an arm is skipped", () => {
  const summary = summarizeProvider([
    {
      arm: "baseline",
      executionStatus: "skipped",
      grade: null,
    },
    {
      arm: "candidate",
      executionStatus: "completed",
      grade: { passed: true, score: 1 },
    },
  ]);

  assert.equal(summary.delta, null);
  assert.equal(summary.certificationStatus, "unavailable");
});

test("summarizeProvider requires two passing candidate runs out of three", () => {
  const runs = [
    { arm: "baseline", executionStatus: "completed", grade: { passed: true, score: 0.7 } },
    { arm: "baseline", executionStatus: "completed", grade: { passed: true, score: 0.7 } },
    { arm: "baseline", executionStatus: "completed", grade: { passed: true, score: 0.7 } },
    { arm: "candidate", executionStatus: "completed", grade: { passed: true, score: 1 } },
    { arm: "candidate", executionStatus: "completed", grade: { passed: true, score: 0.9 } },
    { arm: "candidate", executionStatus: "completed", grade: { passed: false, score: 0.8 } }
  ];
  const summary = summarizeProvider(runs);

  assert.equal(summary.candidatePassRate, 2 / 3);
  assert.equal(summary.stable, true);
  assert.equal(summary.certificationStatus, "healthy");
});

test("runSuite attaches an advisory judge result within the same ceiling", async () => {
  let calls = 0;
  const result = await runSuite({
    mode: "providers",
    suiteRoot,
    pluginRoot,
    providers: ["fake"],
    judge: "fake",
    runs: 1,
    maxInvocations: 3,
    caseFilter: "complete-impact",
    getAdapter: () => fakeAdapter(),
    runProcess: async () => {
      calls += 1;
      return {
        status: "completed",
        exitCode: 0,
        stdout:
          calls === 3
            ? JSON.stringify({
                supportedOwnership: true,
                supportedCausality: true,
                unsupportedClaims: [],
                score: 0.95,
                reason: "Claims are supported.",
              })
            : passingOutput,
        stderr: "",
        truncated: false,
        workspace: `/tmp/fresh-${calls}`,
      };
    },
  });

  const candidate = result.cases[0].providerResults[0].runs.find(
    (run) => run.arm === "candidate",
  );
  assert.equal(calls, 3);
  assert.equal(result.invocations.used, 3);
  assert.equal(candidate.judge.result.score, 0.95);
  assert.equal(candidate.judge.warning, "judge-and-subject-provider-match");
});
