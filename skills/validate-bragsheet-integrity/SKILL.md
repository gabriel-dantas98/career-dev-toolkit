---
name: validate-bragsheet-integrity
description: Use when checking local brag-sheet records for taxonomy, evidence, Jira, GitHub status, confidence, or deduplication problems.
---

# Validate brag-sheet integrity

## Workflow

1. Resolve the checkout and invoke the shared validator:

   ```bash
   repo_root="$(git rev-parse --show-toplevel 2>/dev/null)" || exit 1
   cd "$repo_root" || exit 1
   python -m careeros validate-bragsheet-integrity --json
   ```

2. Use only CLI-supported record or period filters. Keep unrelated private records outside the validation input.
3. During setup, request at most one user action per onboarding turn. Rerun the CLI after that action.
4. Present every returned rule ID, severity, field, and evidence gap. Do not rewrite an error as a warning or fill a gap with inferred metrics, ownership, dates, causality, relationships, or impact.

## Completion contract

Call the selection valid only when the JSON envelope has `ok: true` and the CLI reports no error-severity findings. Validation is read-only: do not persist, sync, deploy, or publish records from this workflow.
