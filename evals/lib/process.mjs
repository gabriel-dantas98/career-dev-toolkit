import { spawn } from "node:child_process";
import { mkdtemp, rm } from "node:fs/promises";
import os from "node:os";
import path from "node:path";

const ALLOWED_ENV_NAMES = new Set([
  "PATH",
  "HOME",
  "USER",
  "TMPDIR",
  "LANG",
  "LC_ALL",
  "TERM",
  "CI",
  "NO_COLOR",
]);
const ALLOWED_ENV_PREFIXES = [
  "ANTHROPIC_",
  "CURSOR_",
  "OPENAI_",
  "AWS_",
  "GOOGLE_",
  "CLAUDE_CODE_",
];

export function createAllowedEnv(source = {}, extra = {}) {
  const env = {};

  for (const [name, value] of Object.entries(source)) {
    if (
      value !== undefined &&
      (ALLOWED_ENV_NAMES.has(name) ||
        ALLOWED_ENV_PREFIXES.some((prefix) => name.startsWith(prefix)))
    ) {
      env[name] = value;
    }
  }

  for (const [name, value] of Object.entries(extra)) {
    if (value !== undefined) env[name] = String(value);
  }

  return env;
}

function appendBounded(current, chunk, limit) {
  if (Buffer.byteLength(current) >= limit) {
    return { value: current, truncated: true };
  }

  const remaining = limit - Buffer.byteLength(current);
  const buffer = Buffer.from(chunk);
  const accepted = buffer.subarray(0, remaining).toString("utf8");
  return {
    value: current + accepted,
    truncated: buffer.length > remaining,
  };
}

function terminate(child) {
  if (!child.pid) return;
  try {
    if (process.platform === "win32") child.kill("SIGTERM");
    else process.kill(-child.pid, "SIGTERM");
  } catch {
    child.kill("SIGTERM");
  }
}

export async function runProcess(invocation) {
  const workspace = invocation.isolatedWorkspace
    ? await mkdtemp(path.join(os.tmpdir(), "career-dev-eval-"))
    : invocation.cwd;
  let stdout = "";
  let stderr = "";
  let truncated = false;
  let timedOut = false;
  const maxOutputBytes = invocation.maxOutputBytes ?? 100_000;

  try {
    const result = await new Promise((resolve) => {
      const child = spawn(invocation.command, invocation.args ?? [], {
        cwd: workspace,
        env: invocation.env,
        shell: false,
        detached: process.platform !== "win32",
        stdio: ["ignore", "pipe", "pipe"],
      });

      const timer = setTimeout(() => {
        timedOut = true;
        terminate(child);
      }, invocation.timeoutMs ?? 180_000);

      child.stdout.on("data", (chunk) => {
        const next = appendBounded(stdout, chunk, maxOutputBytes);
        stdout = next.value;
        truncated ||= next.truncated;
      });
      child.stderr.on("data", (chunk) => {
        const next = appendBounded(stderr, chunk, maxOutputBytes);
        stderr = next.value;
        truncated ||= next.truncated;
      });
      child.on("error", (error) => {
        clearTimeout(timer);
        resolve({ exitCode: null, signal: null, spawnError: error.message });
      });
      child.on("close", (exitCode, signal) => {
        clearTimeout(timer);
        resolve({ exitCode, signal, spawnError: null });
      });
    });

    const reason = timedOut
      ? "timeout"
      : result.spawnError
        ? "spawn-error"
        : result.exitCode === 0
          ? null
          : "exit-nonzero";

    return {
      status: reason === null ? "completed" : "error",
      reason,
      exitCode: result.exitCode,
      signal: result.signal,
      spawnError: result.spawnError,
      stdout,
      stderr,
      truncated,
      workspace,
    };
  } finally {
    if (invocation.isolatedWorkspace && workspace) {
      await rm(workspace, { recursive: true, force: true });
    }
  }
}
