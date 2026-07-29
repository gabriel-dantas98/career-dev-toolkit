#!/usr/bin/env node

import path from "node:path";
import { fileURLToPath } from "node:url";

import { writeReport } from "./lib/report.mjs";
import { runSuite } from "./lib/runner.mjs";

const evalRoot = path.dirname(fileURLToPath(import.meta.url));
const repoRoot = path.resolve(evalRoot, "..");
const suiteRoot = path.join(evalRoot, "capture-delivery");

function parseArgs(argv) {
  const [mode = "static", ...tokens] = argv;
  const options = { mode };

  for (let index = 0; index < tokens.length; index += 1) {
    const token = tokens[index];
    const value = tokens[index + 1];
    if (!token.startsWith("--") || value === undefined) {
      throw new TypeError(`invalid argument: ${token}`);
    }
    index += 1;
    if (token === "--providers") options.providers = value.split(",");
    else if (token === "--runs") options.runs = Number(value);
    else if (token === "--max-invocations")
      options.maxInvocations = Number(value);
    else if (token === "--case") options.caseFilter = value;
    else if (token === "--timeout-seconds")
      options.timeoutMs = Number(value) * 1_000;
    else if (token === "--judge") options.judge = value;
    else throw new TypeError(`unknown argument: ${token}`);
  }

  return options;
}

try {
  const options = parseArgs(process.argv.slice(2));
  if (!["static", "providers"].includes(options.mode)) {
    throw new TypeError("mode must be static or providers");
  }
  if (options.mode === "providers" && !options.providers?.length) {
    throw new TypeError("provider mode requires --providers");
  }
  if ((options.timeoutMs ?? 180_000) > 180_000) {
    throw new TypeError("timeout cannot exceed 180 seconds");
  }

  const result = await runSuite({
    ...options,
    suiteRoot,
    pluginRoot: repoRoot,
  });
  const reportRoot = await writeReport(
    result,
    path.join(repoRoot, ".eval-results"),
  );
  console.log(`Report: ${reportRoot}`);
  console.log(`Cases: ${result.cases.length}`);

  if (options.mode === "static" && !result.passed) process.exitCode = 1;
} catch (error) {
  console.error(error.message);
  process.exitCode = 1;
}
