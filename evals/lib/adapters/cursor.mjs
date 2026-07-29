export const cursorAdapter = {
  id: "cursor",
  buildInvocation(input) {
    const args = [
      "agent",
      "--print",
      "--output-format",
      "text",
      "--mode",
      "ask",
      "--trust",
      "--workspace",
      ".",
    ];
    if (input.arm === "candidate") {
      args.push("--plugin-dir", input.pluginRoot);
    }
    args.push(input.prompt);

    return {
      command: "cursor",
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
