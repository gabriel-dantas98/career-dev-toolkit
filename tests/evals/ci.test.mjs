import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import test from "node:test";
import { fileURLToPath } from "node:url";

const HERE = path.dirname(fileURLToPath(import.meta.url));
const WORKFLOW_PATH = path.resolve(
  HERE,
  "../../.github/workflows/smoke-test.yml",
);

test("blocking smoke CI installs pytest and runs deterministic Python tests", () => {
  const workflow = fs.readFileSync(WORKFLOW_PATH, "utf8");

  assert.match(workflow, /actions\/setup-python@v6/);
  assert.match(workflow, /python -m pip install pytest/);
  assert.match(workflow, /npm run test:python/);
  assert.doesNotMatch(workflow, /pip install [^\n]*(sqlcipher|keyring)/i);
});
