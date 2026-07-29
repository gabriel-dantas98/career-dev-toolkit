import assert from "node:assert/strict";
import { mkdtemp, mkdir, writeFile } from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import test from "node:test";

import {
  assertSafeRelativePath,
  loadCases,
  validateCase,
} from "../../evals/lib/cases.mjs";

const validCase = {
  schemaVersion: 1,
  id: "complete-impact",
  title: "Complete impact",
  tags: ["capture-delivery"],
  inputFile: "input.md",
  request: "Capture the useful career evidence in this work thread.",
  expectedExecutionStatus: "completed",
  expectedDeliveryCount: 1,
  allowedFacts: ["20 minutes", "12 minutes"],
  allowedDerivedMetrics: [
    {
      value: "40%",
      formula: "percentage-reduction",
      operands: [20, 12],
    },
  ],
  forbiddenClaims: ["saved $1 million"],
  criticalCriteria: [
    "no-sensitive-output",
    "no-invented-numeric-claims",
    "at-most-one-question",
  ],
  weightedCriteria: [
    { id: "star-structure", weight: 1 },
    { id: "evidence-preserved", weight: 1 },
  ],
};

test("validateCase accepts a complete version 1 case", () => {
  assert.deepEqual(validateCase(validCase), validCase);
});

test("validateCase rejects a case without schemaVersion", () => {
  assert.throws(
    () => validateCase({ ...validCase, schemaVersion: undefined }),
    /schemaVersion/,
  );
});

test("assertSafeRelativePath rejects absolute and traversal paths", () => {
  assert.throws(() => assertSafeRelativePath("/tmp/root", "/tmp/input.md"));
  assert.throws(() => assertSafeRelativePath("/tmp/root", "../input.md"));
});

test("loadCases rejects duplicate ids", async () => {
  const root = await mkdtemp(path.join(os.tmpdir(), "eval-cases-"));

  for (const directory of ["one", "two"]) {
    const caseRoot = path.join(root, directory);
    await mkdir(caseRoot);
    await writeFile(
      path.join(caseRoot, "case.json"),
      JSON.stringify(validCase),
    );
    await writeFile(path.join(caseRoot, "input.md"), "Synthetic input");
  }

  await assert.rejects(() => loadCases(root), /duplicate case id/i);
});

test("loadCases rejects an input symlink or resolved path outside the case", async () => {
  const root = await mkdtemp(path.join(os.tmpdir(), "eval-cases-"));
  const caseRoot = path.join(root, "outside");
  await mkdir(caseRoot);
  await writeFile(
    path.join(caseRoot, "case.json"),
    JSON.stringify({ ...validCase, inputFile: "../outside.md" }),
  );
  await writeFile(path.join(root, "outside.md"), "Outside");

  await assert.rejects(() => loadCases(root), /safe relative path/i);
});
