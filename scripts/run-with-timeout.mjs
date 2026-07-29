#!/usr/bin/env node

import { spawn } from "node:child_process";

const [rawSeconds, command, ...args] = process.argv.slice(2);
const seconds = Number(rawSeconds);

if (!Number.isFinite(seconds) || seconds <= 0 || !command) {
  console.error(
    "Usage: node scripts/run-with-timeout.mjs <seconds> <command> [args...]",
  );
  process.exit(64);
}

const child = spawn(command, args, {
  detached: process.platform !== "win32",
  stdio: "inherit",
});
let timedOut = false;

const timer = setTimeout(() => {
  timedOut = true;
  console.error(`Command timed out after ${seconds} seconds.`);

  if (process.platform === "win32") {
    child.kill("SIGTERM");
  } else {
    process.kill(-child.pid, "SIGTERM");
  }
}, seconds * 1000);

child.on("error", (error) => {
  clearTimeout(timer);
  console.error(error.message);
  process.exit(127);
});

child.on("exit", (code, signal) => {
  clearTimeout(timer);

  if (timedOut) {
    process.exit(124);
  }
  if (signal) {
    console.error(`Command stopped by ${signal}.`);
    process.exit(1);
  }
  process.exit(code ?? 1);
});
