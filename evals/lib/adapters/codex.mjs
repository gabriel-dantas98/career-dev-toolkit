export const codexAdapter = {
  id: "codex",
  buildInvocation(input) {
    return {
      command: "codex",
      args: ["exec", "--skip-git-repo-check", input.prompt],
      shell: false,
      timeoutMs: input.timeoutMs,
      maxOutputBytes: input.maxOutputBytes,
      isolatedWorkspace: true,
    };
  },
  classifyExit(result) {
    if (result.exitCode === 0) return { status: "completed", reason: null };
    const diagnostic = `${result.stdout}\n${result.stderr}`;
    if (/ENOENT/.test(diagnostic)) {
      return { status: "blocked", reason: "native-runtime-missing" };
    }
    if (/not logged in|authentication|api key|unauthorized/i.test(diagnostic)) {
      return { status: "skipped", reason: "authentication-unavailable" };
    }
    return { status: "error", reason: "provider-exit" };
  },
};
