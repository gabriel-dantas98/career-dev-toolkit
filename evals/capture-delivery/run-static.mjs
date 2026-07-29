#!/usr/bin/env node

import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const evalDir = path.dirname(fileURLToPath(import.meta.url));
const repoRoot = path.resolve(evalDir, "../..");
const fixtureDir = path.join(repoRoot, "tests/fixtures/capture-delivery");
const outputPath = path.resolve(
  repoRoot,
  process.argv[2] ?? "tests/evidence/static-eval.json",
);

const expectations = JSON.parse(
  fs.readFileSync(path.join(evalDir, "expectations.json"), "utf8"),
);
const skill = fs.readFileSync(
  path.join(repoRoot, "skills/capture-delivery/SKILL.md"),
  "utf8",
);
const checks = [];

function check(name, condition, detail) {
  checks.push({ name, status: condition ? "pass" : "fail", detail });
}

for (const phrase of [
  "Situation",
  "Task",
  "Action",
  "Result",
  "Ask zero questions by default",
  "Ask at most one question",
  "Do not invent",
]) {
  check(
    `skill:${phrase}`,
    skill.toLowerCase().includes(phrase.toLowerCase()),
    `Skill contract contains "${phrase}".`,
  );
}

for (const [fixtureName, expectation] of Object.entries(expectations)) {
  const fixture = fs.readFileSync(path.join(fixtureDir, fixtureName), "utf8");

  for (const evidence of expectation.requiredEvidence ?? []) {
    check(
      `${fixtureName}:evidence:${evidence}`,
      fixture.toLowerCase().includes(evidence.toLowerCase()),
      "Required synthetic evidence remains present in the fixture.",
    );
  }

  if (expectation.status === "blocked") {
    const secretMatch = fixture.match(/\b(?:gh[pousr]_|sk-)[A-Za-z0-9_-]+\b/);
    check(
      `${fixtureName}:canary-detected`,
      secretMatch !== null,
      "Credential-shaped canary is detected.",
    );
    check(
      `${fixtureName}:canary-not-reproduced`,
      secretMatch !== null && !expectation.safeOutput.includes(secretMatch[0]),
      "Expected output names the category without reproducing the value.",
    );
    check(
      `${fixtureName}:blocked`,
      expectation.status === "blocked" &&
        expectation.category === "credential",
      "Sensitive fixture fails closed.",
    );
  }
}

const failures = checks.filter((item) => item.status === "fail");
const report = {
  suite: "capture-delivery-static",
  status: failures.length === 0 ? "pass" : "fail",
  passed: checks.length - failures.length,
  failed: failures.length,
  checks,
};

fs.mkdirSync(path.dirname(outputPath), { recursive: true });
fs.writeFileSync(outputPath, `${JSON.stringify(report, null, 2)}\n`);

if (failures.length > 0) {
  for (const failure of failures) {
    console.error(`FAIL: ${failure.name} — ${failure.detail}`);
  }
  process.exit(1);
}

console.log(`PASS: ${report.passed} static eval checks passed.`);
