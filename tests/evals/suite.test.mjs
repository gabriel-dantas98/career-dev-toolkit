import assert from "node:assert/strict";
import { access, readFile } from "node:fs/promises";
import path from "node:path";
import test from "node:test";

import { loadCases } from "../../evals/lib/cases.mjs";
import { gradeOutput } from "../../evals/lib/grader.mjs";
import { privacyPreflight, scanSensitive } from "../../evals/lib/privacy.mjs";

const suiteRoot = path.resolve("evals/capture-delivery");
const casesRoot = path.join(suiteRoot, "cases");
const expectedIds = [
  "adversarial-instructions",
  "complete-impact",
  "multiple-deliveries",
  "partial-result",
  "sensitive-input",
];

test("capture-delivery suite contains exactly five canonical cases", async () => {
  const cases = await loadCases(casesRoot);
  assert.deepEqual(
    cases.map((item) => item.definition.id).sort(),
    expectedIds,
  );
});

test("case requests do not leak STAR labels or expected answers", async () => {
  const cases = await loadCases(casesRoot);

  for (const { definition } of cases) {
    assert.doesNotMatch(
      definition.request,
      /\b(?:STAR|Situation|Task|Action|Result)\b/i,
      definition.id,
    );
  }
});

test("only the synthetic canary case expects a local block", async () => {
  const cases = await loadCases(casesRoot);
  const blocked = cases.filter(
    ({ definition }) => definition.expectedExecutionStatus === "blocked",
  );

  assert.equal(blocked.length, 1);
  assert.equal(blocked[0].definition.id, "sensitive-input");
  assert.ok(blocked[0].definition.tags.includes("synthetic-canary"));
});

test("every case has passing and failing golden coverage", async () => {
  const cases = await loadCases(casesRoot);

  for (const { definition } of cases) {
    await access(
      path.join(suiteRoot, "golden", "passing", `${definition.id}.md`),
    );
    await access(
      path.join(suiteRoot, "golden", "failing", `${definition.id}.md`),
    );
  }
});

test("golden outputs prove each completed case can pass and fail", async () => {
  const cases = await loadCases(casesRoot);

  for (const { definition, input } of cases) {
    const passing = await readFile(
      path.join(suiteRoot, "golden", "passing", `${definition.id}.md`),
      "utf8",
    );
    const failing = await readFile(
      path.join(suiteRoot, "golden", "failing", `${definition.id}.md`),
      "utf8",
    );

    if (definition.expectedExecutionStatus === "blocked") {
      assert.equal(privacyPreflight(definition, input).status, "blocked");
      assert.equal(scanSensitive(passing).length, 0);
      assert.ok(scanSensitive(failing).length > 0);
      continue;
    }

    assert.equal(gradeOutput(definition, passing).passed, true, definition.id);
    assert.equal(gradeOutput(definition, failing).passed, false, definition.id);
  }
});
