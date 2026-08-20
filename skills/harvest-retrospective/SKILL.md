---
name: harvest-retrospective
description: Use when gathering career evidence retrospectively from a bounded thread, GitHub, or Google source window.
---

# Harvest retrospective

## Workflow

1. Resolve the checkout that owns the shared runtime:

   ```bash
   repo_root="$(git rev-parse --show-toplevel 2>/dev/null)" || exit 1
   cd "$repo_root" || exit 1
   python -m careeros harvest-retrospective --json
   ```

2. Pass only the smallest useful source window or thread excerpt through CLI-supported arguments. Never send an unbounded thread, mailbox, calendar, or repository history.
3. Treat the CLI privacy gate as terminal. Do not quote a finding or continue with affected content.
4. Treat the connector consent gate as terminal. A missing, insufficient, or revoked grant blocks collection; do not infer consent.
5. During setup, request at most one user action per onboarding turn. Resume by rerunning the CLI instead of assuming the action succeeded.
6. Return the CLI's provenance, validation issues, and persistence status. Do not invent metrics, ownership, dates, causality, impact, or missing evidence.

## Completion contract

Report records as persisted only when the JSON envelope has `ok: true`, no error-severity validation issue, and `data.persisted: true`. Otherwise report the blocking rule or persistence state without reproducing private source content.
