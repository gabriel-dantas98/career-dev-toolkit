import assert from "node:assert/strict";
import test from "node:test";

import {
  privacyPreflight,
  sanitizeText,
  scanSensitive,
} from "../../evals/lib/privacy.mjs";

const sensitiveSamples = [
  ["github-token", "ghp_TEST_ONLY_NOT_A_SECRET"],
  ["api-key", "sk-TEST_ONLY_NOT_A_SECRET"],
  ["authorization-header", "Authorization: Bearer TEST_ONLY_TOKEN"],
  [
    "private-key",
    "-----BEGIN PRIVATE KEY-----\nTEST_ONLY\n-----END PRIVATE KEY-----",
  ],
  ["email", "engineer@example.test"],
];

for (const [category, value] of sensitiveSamples) {
  test(`scanSensitive identifies ${category} without returning its value`, () => {
    const findings = scanSensitive(`before ${value} after`);

    assert.equal(findings.length, 1);
    assert.equal(findings[0].category, category);
    assert.equal(JSON.stringify(findings).includes(value), false);
  });
}

test("privacyPreflight blocks a synthetic canary before provider execution", () => {
  const result = privacyPreflight(
    { tags: ["synthetic-canary"] },
    "Use ghp_TEST_ONLY_NOT_A_SECRET for this example.",
  );

  assert.deepEqual(result, {
    status: "blocked",
    findings: [{ category: "github-token" }],
  });
});

test("sanitizeText removes user paths, repository paths and sensitive values", () => {
  const raw =
    "At /Users/example/project and /repo/root use ghp_TEST_ONLY_NOT_A_SECRET.";
  const result = sanitizeText(raw, {
    userHome: "/Users/example",
    repoRoot: "/repo/root",
  });

  assert.equal(result.text.includes("/Users/example"), false);
  assert.equal(result.text.includes("/repo/root"), false);
  assert.equal(result.text.includes("ghp_TEST_ONLY_NOT_A_SECRET"), false);
  assert.deepEqual(scanSensitive(result.text), []);
});

test("sanitizeText fails closed when prohibited content remains", () => {
  assert.throws(
    () =>
      sanitizeText("engineer@example.test", {
        replacements: [],
        disabledCategories: ["email"],
      }),
    /sanitization failed closed/i,
  );
});
