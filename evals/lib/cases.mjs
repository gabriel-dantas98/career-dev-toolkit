import { readdir, readFile, realpath } from "node:fs/promises";
import path from "node:path";

import {
  isPlainObject,
  requireString,
  requireStringArray,
} from "./contracts.mjs";

const CASE_ID = /^[a-z0-9]+(?:-[a-z0-9]+)*$/;
const EXPECTED_STATUSES = new Set(["completed", "blocked"]);

export function assertSafeRelativePath(root, value) {
  requireString(value, "inputFile");
  if (path.isAbsolute(value)) {
    throw new TypeError("inputFile must be a safe relative path");
  }

  const resolvedRoot = path.resolve(root);
  const resolved = path.resolve(resolvedRoot, value);
  const relative = path.relative(resolvedRoot, resolved);

  if (
    relative === "" ||
    relative === ".." ||
    relative.startsWith(`..${path.sep}`) ||
    path.isAbsolute(relative)
  ) {
    throw new TypeError("inputFile must be a safe relative path");
  }

  return resolved;
}

export function validateCase(value) {
  if (!isPlainObject(value)) {
    throw new TypeError("case must be an object");
  }
  if (value.schemaVersion !== 1) {
    throw new TypeError("schemaVersion must equal 1");
  }

  for (const field of ["id", "title", "inputFile", "request"]) {
    requireString(value[field], field);
  }
  if (!CASE_ID.test(value.id)) {
    throw new TypeError("id must use kebab-case");
  }
  if (!EXPECTED_STATUSES.has(value.expectedExecutionStatus)) {
    throw new TypeError("expectedExecutionStatus must be completed or blocked");
  }
  if (
    !Number.isInteger(value.expectedDeliveryCount) ||
    value.expectedDeliveryCount < 0
  ) {
    throw new TypeError("expectedDeliveryCount must be a non-negative integer");
  }

  for (const field of [
    "tags",
    "allowedFacts",
    "forbiddenClaims",
    "criticalCriteria",
  ]) {
    requireStringArray(value[field], field);
  }
  if (!Array.isArray(value.allowedDerivedMetrics)) {
    throw new TypeError("allowedDerivedMetrics must be an array");
  }
  for (const metric of value.allowedDerivedMetrics) {
    if (!isPlainObject(metric)) {
      throw new TypeError("allowedDerivedMetrics entries must be objects");
    }
    requireString(metric.value, "allowedDerivedMetrics.value");
    requireString(metric.formula, "allowedDerivedMetrics.formula");
    if (
      !Array.isArray(metric.operands) ||
      metric.operands.length < 2 ||
      metric.operands.some((operand) => typeof operand !== "number")
    ) {
      throw new TypeError(
        "allowedDerivedMetrics.operands must contain at least two numbers",
      );
    }
  }
  if (!Array.isArray(value.weightedCriteria)) {
    throw new TypeError("weightedCriteria must be an array");
  }
  for (const criterion of value.weightedCriteria) {
    if (
      !isPlainObject(criterion) ||
      typeof criterion.id !== "string" ||
      typeof criterion.weight !== "number" ||
      criterion.weight <= 0
    ) {
      throw new TypeError(
        "weightedCriteria entries require an id and positive weight",
      );
    }
  }

  return value;
}

export async function loadCases(root) {
  const entries = await readdir(root, { withFileTypes: true });
  const cases = [];
  const ids = new Set();

  for (const entry of entries.sort((a, b) => a.name.localeCompare(b.name))) {
    if (!entry.isDirectory()) continue;
    const caseRoot = path.join(root, entry.name);
    const definition = validateCase(
      JSON.parse(await readFile(path.join(caseRoot, "case.json"), "utf8")),
    );
    if (ids.has(definition.id)) {
      throw new TypeError(`duplicate case id: ${definition.id}`);
    }

    const inputPath = assertSafeRelativePath(caseRoot, definition.inputFile);
    const actualInputPath = await realpath(inputPath);
    const actualCaseRoot = await realpath(caseRoot);
    const relative = path.relative(actualCaseRoot, actualInputPath);
    if (
      relative === ".." ||
      relative.startsWith(`..${path.sep}`) ||
      path.isAbsolute(relative)
    ) {
      throw new TypeError("inputFile must resolve to a safe relative path");
    }

    ids.add(definition.id);
    cases.push({
      definition,
      caseRoot,
      inputPath: actualInputPath,
      input: await readFile(actualInputPath, "utf8"),
    });
  }

  return cases;
}
