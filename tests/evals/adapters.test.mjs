import assert from "node:assert/strict";
import test from "node:test";

import { getAdapter } from "../../evals/lib/adapters/index.mjs";

const input = {
  arm: "candidate",
  prompt: "Literal prompt ; $(do-not-run)",
  pluginRoot: "/plugin/root",
  timeoutMs: 30_000,
  maxOutputBytes: 100_000,
};

test("Claude baseline excludes user settings and candidate adds only the plugin path", () => {
  const adapter = getAdapter("claude");
  const baseline = adapter.buildInvocation({ ...input, arm: "baseline" });
  const candidate = adapter.buildInvocation(input);

  assert.equal(baseline.command, "claude");
  assert.equal(baseline.shell, false);
  assert.ok(baseline.args.includes("--setting-sources"));
  assert.ok(baseline.args.includes("project,local"));
  assert.deepEqual(
    baseline.args.slice(
      baseline.args.indexOf("--tools"),
      baseline.args.indexOf("--tools") + 2,
    ),
    ["--tools", "Skill"],
  );
  assert.deepEqual(
    baseline.args.slice(
      baseline.args.indexOf("--permission-mode"),
      baseline.args.indexOf("--permission-mode") + 2,
    ),
    ["--permission-mode", "dontAsk"],
  );
  assert.equal(baseline.args.includes("--plugin-dir"), false);
  assert.deepEqual(
    candidate.args.slice(
      candidate.args.indexOf("--plugin-dir"),
      candidate.args.indexOf("--plugin-dir") + 2,
    ),
    ["--plugin-dir", "/plugin/root"],
  );
  assert.equal(candidate.args.at(-1), input.prompt);
});

test("Cursor baseline omits plugin-dir and candidate uses an isolated workspace", () => {
  const adapter = getAdapter("cursor");
  const baseline = adapter.buildInvocation({ ...input, arm: "baseline" });
  const candidate = adapter.buildInvocation(input);

  assert.equal(baseline.command, "cursor");
  assert.equal(baseline.args.includes("--plugin-dir"), false);
  assert.ok(candidate.args.includes("--plugin-dir"));
  assert.ok(candidate.args.includes("--workspace"));
  assert.equal(candidate.args.at(-1), input.prompt);
});

test("Codex classifies the observed native ENOENT as blocked", () => {
  const adapter = getAdapter("codex");
  const result = adapter.classifyExit({
    exitCode: 1,
    stderr: "Error: spawn /vendor/codex ENOENT",
    stdout: "",
  });

  assert.deepEqual(result, {
    status: "blocked",
    reason: "native-runtime-missing",
  });
});

test("getAdapter rejects unknown providers", () => {
  assert.throws(() => getAdapter("unknown"), /unknown provider/i);
});
