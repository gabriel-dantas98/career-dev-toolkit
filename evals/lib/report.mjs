import { mkdir, rename, rm, writeFile } from "node:fs/promises";
import path from "node:path";

export function renderMarkdown(result) {
  const lines = [
    `# Evaluation report: ${result.runId}`,
    "",
    `Mode: ${result.mode}`,
    `Started: ${result.startedAt}`,
    `Finished: ${result.finishedAt}`,
    "",
    "## Cases",
    "",
  ];

  for (const caseResult of result.cases) {
    lines.push(
      `### ${caseResult.caseId}`,
      "",
      `Execution: ${caseResult.observedExecutionStatus}`,
      `Expectation met: ${caseResult.meetsExpectation ? "yes" : "no"}`,
    );
    for (const provider of caseResult.providerResults ?? []) {
      lines.push(
        "",
        `${provider.provider}: ${provider.certificationStatus}`,
        `Delta: ${provider.summary.delta ?? "unavailable"}`,
      );
      for (const run of provider.runs) {
        lines.push(
          `- ${run.arm} ${run.run}: ${run.executionStatus}${run.reason ? ` (${run.reason})` : ""}`,
        );
      }
    }
    lines.push("");
  }

  return `${lines.join("\n")}\n`;
}

export async function writeReport(result, outputRoot) {
  await mkdir(outputRoot, { recursive: true });
  const finalRoot = path.join(outputRoot, result.runId);
  const temporaryRoot = path.join(outputRoot, `.tmp-${result.runId}`);
  await rm(temporaryRoot, { recursive: true, force: true });
  await mkdir(temporaryRoot, { recursive: true });

  await writeFile(
    path.join(temporaryRoot, "result.json"),
    `${JSON.stringify(result, null, 2)}\n`,
  );
  await writeFile(
    path.join(temporaryRoot, "summary.md"),
    renderMarkdown(result),
  );

  for (const caseResult of result.cases) {
    for (const provider of caseResult.providerResults ?? []) {
      for (const run of provider.runs) {
        if (run.stdout === undefined && run.stderr === undefined) continue;
        const artifactRoot = path.join(
          temporaryRoot,
          "artifacts",
          caseResult.caseId,
          provider.provider,
        );
        await mkdir(artifactRoot, { recursive: true });
        const prefix = `${run.arm}-${run.run}`;
        await writeFile(
          path.join(artifactRoot, `${prefix}.stdout.txt`),
          run.stdout ?? "",
        );
        await writeFile(
          path.join(artifactRoot, `${prefix}.stderr.txt`),
          run.stderr ?? "",
        );
      }
    }
  }

  await rm(finalRoot, { recursive: true, force: true });
  await rename(temporaryRoot, finalRoot);
  return finalRoot;
}
