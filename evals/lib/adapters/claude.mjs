const commonArgs = [
  "-p",
  "--output-format",
  "text",
  "--no-session-persistence",
  "--setting-sources",
  "project,local",
  "--tools",
  "",
  "--permission-mode",
  "plan",
];

export const claudeAdapter = {
  id: "claude",
  buildInvocation(input) {
    const args = [...commonArgs];
    if (input.arm === "candidate") {
      args.push("--plugin-dir", input.pluginRoot);
    }
    args.push(input.prompt);

    return {
      command: "claude",
      args,
      shell: false,
      timeoutMs: input.timeoutMs,
      maxOutputBytes: input.maxOutputBytes,
      isolatedWorkspace: true,
    };
  },
  classifyExit(result) {
    if (result.exitCode === 0) return { status: "completed", reason: null };
    const diagnostic = `${result.stdout}\n${result.stderr}`;
    if (/not logged in|authentication|api key|unauthorized/i.test(diagnostic)) {
      return { status: "skipped", reason: "authentication-unavailable" };
    }
    if (/ENOENT|not found/i.test(diagnostic)) {
      return { status: "blocked", reason: "cli-unavailable" };
    }
    return { status: "error", reason: "provider-exit" };
  },
};
