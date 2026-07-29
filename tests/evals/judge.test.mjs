import assert from "node:assert/strict";
import test from "node:test";

import {
  buildJudgeRequest,
  parseJudgeResult,
} from "../../evals/lib/judge.mjs";

const validResult = {
  supportedOwnership: true,
  supportedCausality: true,
  unsupportedClaims: [],
  score: 0.9,
  reason: "Claims stay within the synthetic evidence.",
};

test("buildJudgeRequest contains only input, rubric and sanitized candidate output", () => {
  const request = buildJudgeRequest({
    caseInput: "Synthetic work thread",
    rubric: {
      forbiddenClaims: ["saved $1 million"],
      criticalCriteria: ["no-forbidden-claims"],
    },
    candidateOutput: "A reviewable draft",
  });

  assert.match(request, /Synthetic work thread/);
  assert.match(request, /saved \$1 million/);
  assert.match(request, /A reviewable draft/);
  assert.doesNotMatch(request, /SKILL\.md|golden|expected answer/i);
});

test("buildJudgeRequest refuses unsanitized candidate content", () => {
  assert.throws(
    () =>
      buildJudgeRequest({
        caseInput: "Synthetic work thread",
        rubric: {},
        candidateOutput: "token ghp_TEST_ONLY_NOT_A_SECRET",
      }),
    /sanitized/i,
  );
});

test("parseJudgeResult accepts only the declared JSON shape", () => {
  assert.deepEqual(parseJudgeResult(JSON.stringify(validResult)), validResult);
  assert.throws(
    () => parseJudgeResult(`\`\`\`json\n${JSON.stringify(validResult)}\n\`\`\``),
    /valid JSON/i,
  );
  assert.throws(
    () => parseJudgeResult(JSON.stringify({ ...validResult, score: 2 })),
    /score/i,
  );
  assert.throws(
    () =>
      parseJudgeResult(
        JSON.stringify({ ...validResult, unsupportedClaims: "none" }),
      ),
    /unsupportedClaims/i,
  );
});

test("judge results remain independent instead of being averaged", () => {
  const first = parseJudgeResult(JSON.stringify(validResult));
  const second = parseJudgeResult(
    JSON.stringify({
      ...validResult,
      supportedCausality: false,
      score: 0.4,
      reason: "Causality is not established.",
    }),
  );

  assert.deepEqual([first.score, second.score], [0.9, 0.4]);
});
