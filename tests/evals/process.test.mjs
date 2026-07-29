import assert from "node:assert/strict";
import { access } from "node:fs/promises";
import path from "node:path";
import test from "node:test";

import {
  createAllowedEnv,
  runProcess,
} from "../../evals/lib/process.mjs";

const fakeProvider = path.resolve("tests/fixtures/fake-provider.mjs");

test("runProcess passes shell metacharacters as literal arguments", async () => {
  const result = await runProcess({
    command: process.execPath,
    args: [fakeProvider, "echo", "$(touch /tmp/never-run)", ";", "|"],
    env: createAllowedEnv(process.env),
    timeoutMs: 2_000,
    maxOutputBytes: 20_000,
    isolatedWorkspace: true,
  });
  const payload = JSON.parse(result.stdout);

  assert.equal(result.status, "completed");
  assert.deepEqual(payload.args, [
    "echo",
    "$(touch /tmp/never-run)",
    ";",
    "|",
  ]);
});

test("runProcess creates and removes a fresh workspace for every call", async () => {
  const first = await runProcess({
    command: process.execPath,
    args: [fakeProvider, "cwd"],
    env: createAllowedEnv(process.env),
    timeoutMs: 2_000,
    maxOutputBytes: 20_000,
    isolatedWorkspace: true,
  });
  const second = await runProcess({
    command: process.execPath,
    args: [fakeProvider, "cwd"],
    env: createAllowedEnv(process.env),
    timeoutMs: 2_000,
    maxOutputBytes: 20_000,
    isolatedWorkspace: true,
  });

  assert.notEqual(first.workspace, second.workspace);
  await assert.rejects(() => access(first.workspace));
  await assert.rejects(() => access(second.workspace));
});

test("createAllowedEnv excludes unspecified environment variables", async () => {
  const env = createAllowedEnv(
    {
      PATH: process.env.PATH,
      SHOULD_NOT_LEAK: "private",
    },
    { ALLOWED_TEST_VALUE: "visible" },
  );
  const result = await runProcess({
    command: process.execPath,
    args: [fakeProvider, "env"],
    env,
    timeoutMs: 2_000,
    maxOutputBytes: 20_000,
    isolatedWorkspace: true,
  });
  const payload = JSON.parse(result.stdout);

  assert.equal(payload.env.ALLOWED_TEST_VALUE, "visible");
  assert.equal(payload.env.SHOULD_NOT_LEAK, undefined);
});

test("runProcess returns error when the timeout expires", async () => {
  const result = await runProcess({
    command: process.execPath,
    args: [fakeProvider, "hang"],
    env: createAllowedEnv(process.env),
    timeoutMs: 50,
    maxOutputBytes: 20_000,
    isolatedWorkspace: true,
  });

  assert.equal(result.status, "error");
  assert.equal(result.reason, "timeout");
});

test("runProcess bounds captured output", async () => {
  const result = await runProcess({
    command: process.execPath,
    args: [fakeProvider, "large"],
    env: createAllowedEnv(process.env),
    timeoutMs: 2_000,
    maxOutputBytes: 100,
    isolatedWorkspace: true,
  });

  assert.equal(result.stdout.length, 100);
  assert.equal(result.truncated, true);
});
