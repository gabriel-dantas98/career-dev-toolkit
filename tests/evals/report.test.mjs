import assert from "node:assert/strict";
import { access, mkdtemp, readFile } from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import test from "node:test";

import {
  renderMarkdown,
  writeReport,
} from "../../evals/lib/report.mjs";

const result = {
  schemaVersion: 1,
  runId: "run-test",
  mode: "providers",
  startedAt: "2026-07-29T00:00:00.000Z",
  finishedAt: "2026-07-29T00:01:00.000Z",
  invocations: { used: 1, maximum: 4, limitReached: false },
  cases: [
    {
      caseId: "complete-impact",
      observedExecutionStatus: "completed",
      meetsExpectation: true,
      providerResults: [
        {
          provider: "cursor",
          certificationStatus: "unavailable",
          summary: { delta: null },
          runs: [
            {
              arm: "baseline",
              executionStatus: "skipped",
              reason: "authentication-unavailable",
            },
          ],
        },
      ],
    },
  ],
};

test("renderMarkdown reports skipped runs without presenting them as passing", () => {
  const markdown = renderMarkdown(result);

  assert.match(markdown, /skipped/i);
  assert.match(markdown, /unavailable/i);
  assert.doesNotMatch(markdown, /cursor: pass/i);
});

test("writeReport writes normalized JSON, Markdown and sanitized artifacts", async () => {
  const root = await mkdtemp(path.join(os.tmpdir(), "eval-report-"));
  const output = await writeReport(result, root);

  await access(path.join(output, "result.json"));
  await access(path.join(output, "summary.md"));
  const persisted = JSON.parse(
    await readFile(path.join(output, "result.json"), "utf8"),
  );
  assert.equal(persisted.runId, "run-test");
});
