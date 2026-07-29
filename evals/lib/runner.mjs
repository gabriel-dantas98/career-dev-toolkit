import { readFile } from "node:fs/promises";
import path from "node:path";

import { getAdapter as defaultGetAdapter } from "./adapters/index.mjs";
import { loadCases } from "./cases.mjs";
import { gradeOutput } from "./grader.mjs";
import { buildJudgeRequest, parseJudgeResult } from "./judge.mjs";
import { createAllowedEnv, runProcess as defaultRunProcess } from "./process.mjs";
import { privacyPreflight, sanitizeText } from "./privacy.mjs";

function mean(values) {
  if (values.length === 0) return null;
  return values.reduce((total, value) => total + value, 0) / values.length;
}

export function summarizeProvider(runs) {
  const baseline = runs.filter(
    (run) => run.arm === "baseline" && run.executionStatus === "completed" && run.grade,
  );
  const candidate = runs.filter(
    (run) => run.arm === "candidate" && run.executionStatus === "completed" && run.grade,
  );
  const baselineMean = mean(baseline.map((run) => run.grade.score));
  const candidateMean = mean(candidate.map((run) => run.grade.score));
  const delta =
    baselineMean === null || candidateMean === null
      ? null
      : candidateMean - baselineMean;
  const candidatePasses = candidate.filter((run) => run.grade.passed).length;
  const candidatePassRate =
    candidate.length === 0 ? null : candidatePasses / candidate.length;
  const stable =
    candidate.length >= 3 &&
    candidatePasses >= Math.ceil((candidate.length * 2) / 3);
  const certificationStatus =
    baseline.length < 3 || candidate.length < 3
      ? "unavailable"
      : stable && candidateMean >= 0.85 && delta >= 0.1
        ? "healthy"
        : "regressed";

  return {
    baselineMean,
    candidateMean,
    delta,
    candidatePassRate,
    stable,
    certificationStatus,
  };
}

function composePrompt(loadedCase) {
  return `${loadedCase.definition.request}\n\nWork thread:\n${loadedCase.input}`;
}

function runId(now) {
  return now().toISOString().replaceAll(":", "-").replaceAll(".", "-");
}

async function runStaticCase(loadedCase, suiteRoot) {
  const preflight = privacyPreflight(
    loadedCase.definition,
    loadedCase.input,
  );
  if (preflight.status === "blocked") {
    return {
      caseId: loadedCase.definition.id,
      expectedExecutionStatus:
        loadedCase.definition.expectedExecutionStatus,
      observedExecutionStatus: "blocked",
      meetsExpectation:
        loadedCase.definition.expectedExecutionStatus === "blocked",
      findings: preflight.findings,
      providerResults: [],
    };
  }

  const golden = await readFile(
    path.join(
      suiteRoot,
      "golden",
      "passing",
      `${loadedCase.definition.id}.md`,
    ),
    "utf8",
  );
  const grade = gradeOutput(loadedCase.definition, golden);
  return {
    caseId: loadedCase.definition.id,
    expectedExecutionStatus: loadedCase.definition.expectedExecutionStatus,
    observedExecutionStatus: "completed",
    meetsExpectation:
      loadedCase.definition.expectedExecutionStatus === "completed" &&
      grade.passed,
    grade,
    providerResults: [],
  };
}

export async function runSuite(options) {
  const mode = options.mode ?? "static";
  if (
    mode === "providers" &&
    (!Number.isInteger(options.maxInvocations) ||
      options.maxInvocations <= 0)
  ) {
    throw new TypeError(
      "provider mode requires a positive maxInvocations ceiling",
    );
  }

  const now = options.now ?? (() => new Date());
  const startedAt = now().toISOString();
  const loaded = await loadCases(path.join(options.suiteRoot, "cases"));
  const selected = options.caseFilter
    ? loaded.filter((item) => item.definition.id === options.caseFilter)
    : loaded;
  if (options.caseFilter && selected.length === 0) {
    throw new TypeError(`unknown case: ${options.caseFilter}`);
  }

  const invocationState = {
    used: 0,
    maximum: mode === "providers" ? options.maxInvocations : 0,
    limitReached: false,
  };
  const cases = [];

  for (const loadedCase of selected) {
    if (mode === "static") {
      cases.push(await runStaticCase(loadedCase, options.suiteRoot));
      continue;
    }

    const preflight = privacyPreflight(
      loadedCase.definition,
      loadedCase.input,
    );
    if (preflight.status === "blocked") {
      cases.push({
        caseId: loadedCase.definition.id,
        expectedExecutionStatus:
          loadedCase.definition.expectedExecutionStatus,
        observedExecutionStatus: "blocked",
        meetsExpectation:
          loadedCase.definition.expectedExecutionStatus === "blocked",
        findings: preflight.findings,
        providerResults: [],
      });
      continue;
    }

    const providerResults = [];
    for (const provider of options.providers ?? []) {
      const adapter = (options.getAdapter ?? defaultGetAdapter)(provider);
      const runs = [];

      for (const arm of ["baseline", "candidate"]) {
        for (let run = 1; run <= (options.runs ?? 1); run += 1) {
          if (invocationState.used >= invocationState.maximum) {
            invocationState.limitReached = true;
            runs.push({
              arm,
              run,
              executionStatus: "error",
              reason: "invocation-limit-reached",
              grade: null,
            });
            continue;
          }

          invocationState.used += 1;
          const invocation = adapter.buildInvocation({
            arm,
            prompt: composePrompt(loadedCase),
            pluginRoot: options.pluginRoot,
            timeoutMs: options.timeoutMs ?? 180_000,
            maxOutputBytes: options.maxOutputBytes ?? 100_000,
          });
          invocation.env = createAllowedEnv(process.env, {
            NO_COLOR: "1",
            ...(invocation.env ?? {}),
          });
          const processResult = await (
            options.runProcess ?? defaultRunProcess
          )(invocation);
          const classification = adapter.classifyExit(processResult);
          const sanitizedStdout = sanitizeText(processResult.stdout ?? "", {
            repoRoot: options.pluginRoot,
            userHome: process.env.HOME,
          }).text;
          const sanitizedStderr = sanitizeText(processResult.stderr ?? "", {
            repoRoot: options.pluginRoot,
            userHome: process.env.HOME,
          }).text;
          const grade =
            classification.status === "completed"
              ? gradeOutput(loadedCase.definition, sanitizedStdout)
              : null;
          runs.push({
            arm,
            run,
            executionStatus: classification.status,
            reason: classification.reason,
            grade,
            stdout: sanitizedStdout,
            stderr: sanitizedStderr,
            truncated: processResult.truncated ?? false,
          });
        }
      }

      if (options.judge) {
        const judgeAdapter = (options.getAdapter ?? defaultGetAdapter)(
          options.judge,
        );
        for (const candidateRun of runs.filter(
          (run) =>
            run.arm === "candidate" &&
            run.executionStatus === "completed",
        )) {
          if (invocationState.used >= invocationState.maximum) {
            invocationState.limitReached = true;
            candidateRun.judge = {
              provider: options.judge,
              executionStatus: "error",
              reason: "invocation-limit-reached",
              result: null,
              warning:
                options.judge === provider
                  ? "judge-and-subject-provider-match"
                  : null,
            };
            continue;
          }

          invocationState.used += 1;
          const judgePrompt = buildJudgeRequest({
            caseInput: loadedCase.input,
            rubric: {
              forbiddenClaims: loadedCase.definition.forbiddenClaims,
              criticalCriteria: loadedCase.definition.criticalCriteria,
              weightedCriteria: loadedCase.definition.weightedCriteria,
            },
            candidateOutput: candidateRun.stdout,
          });
          const judgeInvocation = judgeAdapter.buildInvocation({
            arm: "baseline",
            prompt: judgePrompt,
            pluginRoot: options.pluginRoot,
            timeoutMs: options.timeoutMs ?? 180_000,
            maxOutputBytes: options.maxOutputBytes ?? 100_000,
          });
          judgeInvocation.env = createAllowedEnv(process.env, {
            NO_COLOR: "1",
            ...(judgeInvocation.env ?? {}),
          });
          const judgeProcess = await (
            options.runProcess ?? defaultRunProcess
          )(judgeInvocation);
          const judgeClassification = judgeAdapter.classifyExit(judgeProcess);
          const judgeOutput = sanitizeText(judgeProcess.stdout ?? "", {
            repoRoot: options.pluginRoot,
            userHome: process.env.HOME,
          }).text;
          let judgeResult = null;
          let judgeReason = judgeClassification.reason;
          let judgeStatus = judgeClassification.status;
          if (judgeClassification.status === "completed") {
            try {
              judgeResult = parseJudgeResult(judgeOutput);
            } catch {
              judgeStatus = "error";
              judgeReason = "malformed-judge-output";
            }
          }
          candidateRun.judge = {
            provider: options.judge,
            executionStatus: judgeStatus,
            reason: judgeReason,
            result: judgeResult,
            warning:
              options.judge === provider
                ? "judge-and-subject-provider-match"
                : null,
          };
        }
      }

      const summary = summarizeProvider(runs);
      providerResults.push({
        provider,
        runs,
        summary,
        certificationStatus: summary.certificationStatus,
      });
    }

    cases.push({
      caseId: loadedCase.definition.id,
      expectedExecutionStatus: loadedCase.definition.expectedExecutionStatus,
      observedExecutionStatus: "completed",
      meetsExpectation: true,
      providerResults,
    });
  }

  const finishedAt = now().toISOString();
  return {
    schemaVersion: 1,
    runId: options.runId ?? runId(now),
    mode,
    startedAt,
    finishedAt,
    invocations: invocationState,
    passed:
      mode === "static"
        ? cases.every((item) => item.meetsExpectation)
        : null,
    cases,
  };
}
