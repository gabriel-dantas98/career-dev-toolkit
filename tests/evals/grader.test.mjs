import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import path from "node:path";
import test from "node:test";

import { gradeOutput } from "../../evals/lib/grader.mjs";

const goldenRoot = path.resolve("evals/capture-delivery/golden");

const completeCase = {
  expectedDeliveryCount: 1,
  expectedExecutionStatus: "completed",
  allowedFacts: [
    "20 minutes",
    "12 minutes",
    "six engineers",
    "two weeks",
    "no increase in flaky-test retries",
  ],
  allowedDerivedMetrics: [
    {
      value: "40%",
      formula: "percentage-reduction",
      operands: [20, 12],
    },
    {
      value: "8 minutes",
      formula: "absolute-reduction",
      operands: [20, 12],
    },
  ],
  forbiddenClaims: ["saved the company $1 million"],
  criticalCriteria: [
    "star-structure",
    "delivery-count",
    "at-most-one-question",
    "no-sensitive-output",
    "no-invented-numeric-claims",
    "no-forbidden-claims",
  ],
  weightedCriteria: [
    { id: "star-structure", weight: 2 },
    { id: "delivery-count", weight: 1 },
    { id: "evidence-preserved", weight: 2 },
  ],
};

const partialCase = {
  ...completeCase,
  allowedFacts: [
    "manual checklist",
    "validates the package",
    "prepares the tag",
  ],
  allowedDerivedMetrics: [],
  forbiddenClaims: [],
  weightedCriteria: [
    { id: "star-structure", weight: 1 },
    { id: "explicit-evidence-gap", weight: 2 },
  ],
};

async function golden(relativePath) {
  return readFile(path.join(goldenRoot, relativePath), "utf8");
}

test("gradeOutput accepts declared STAR evidence and a 40% derivation", async () => {
  const result = gradeOutput(
    completeCase,
    await golden("passing/complete-impact.md"),
  );

  assert.equal(result.passed, true);
  assert.equal(result.criticalFailures.length, 0);
  assert.equal(result.score, 1);
});

test("gradeOutput requires an explicit evidence gap for partial results", async () => {
  const passing = gradeOutput(
    partialCase,
    await golden("passing/partial-result.md"),
  );
  const failing = gradeOutput(
    partialCase,
    (await golden("passing/partial-result.md")).replaceAll(
      "Evidence gap:",
      "Result:",
    ),
  );

  assert.equal(passing.passed, true);
  assert.equal(failing.passed, false);
});

test("gradeOutput rejects a second question", async () => {
  const result = gradeOutput(
    partialCase,
    await golden("failing/two-questions.md"),
  );

  assert.ok(result.criticalFailures.includes("at-most-one-question"));
});

test("gradeOutput rejects an invented numeric impact", async () => {
  const result = gradeOutput(
    completeCase,
    await golden("failing/invented-impact.md"),
  );

  assert.ok(result.criticalFailures.includes("no-invented-numeric-claims"));
  assert.ok(result.criticalFailures.includes("no-forbidden-claims"));
});

test("gradeOutput rejects merged deliveries", async () => {
  const output = await golden("failing/merged-deliveries.md");
  const result = gradeOutput(
    {
      ...completeCase,
      expectedDeliveryCount: 2,
      allowedFacts: ["20", "12", "8", "5", "CI", "onboarding"],
      allowedDerivedMetrics: [],
    },
    output,
  );

  assert.ok(result.criticalFailures.includes("delivery-count"));
});

test("gradeOutput rejects a reproduced credential canary", () => {
  const result = gradeOutput(
    completeCase,
    `### Delivery
- Situation: token ghp_TEST_ONLY_NOT_A_SECRET
- Task: Fix access
- Action: Rotated it
- Result: Complete
`,
  );

  assert.ok(result.criticalFailures.includes("no-sensitive-output"));
});

test("gradeOutput rejects a missing STAR section", () => {
  const result = gradeOutput(
    completeCase,
    `### Reduced CI feedback time
- Situation: CI took 20 minutes.
- Task: Improve it.
- Action: I parallelized tests.
- Evidence: It took 12 minutes.
`,
  );

  assert.ok(result.criticalFailures.includes("star-structure"));
});

test("gradeOutput accepts equivalent number words and time units", () => {
  const result = gradeOutput(
    {
      ...completeCase,
    },
    `One note: this is a synthetic scenario.

### Reduced CI feedback time
- **Situation:** CI took 20 min for 6 engineers.
- **Task:** Improve the feedback loop.
- **Action:** Profiled the tests and introduced bounded parallel execution.
- **Result:** It fell to 12 min over a 2-week window, saving 8 min per build (40%), with no increase in flaky-test retries.
`,
  );

  assert.equal(result.criteria["no-invented-numeric-claims"], true);
  assert.equal(result.criteria["evidence-preserved"], true);
  assert.equal(result.criteria["star-structure"], true);
  assert.equal(result.criteria["action-attribution"], true);
});
