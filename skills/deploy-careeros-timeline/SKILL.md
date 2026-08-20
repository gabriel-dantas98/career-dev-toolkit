---
name: deploy-careeros-timeline
description: Use when deploying or updating a CareerOS timeline and homepage through an explicitly authorized Apps Script destination.
---

# Deploy CareerOS timeline

## Workflow

1. Resolve the checkout and invoke the shared deployment command:

   ```bash
   repo_root="$(git rev-parse --show-toplevel 2>/dev/null)" || exit 1
   cd "$repo_root" || exit 1
   python -m careeros deploy-careeros-timeline --json
   ```

2. Treat the privacy gate for generated timeline content as terminal.
3. Treat the deployment capability and destination consent gate as terminal. Never infer deployment consent from a read, connector, sync, or background grant.
4. Require the CLI's clasp preflight before mutation. Do not deploy after failed authentication or health.
5. During setup, request at most one user action per onboarding turn. Rerun the CLI after the action; never assume authentication, authorization, or deployment succeeded.
6. Accept only the exact validated Apps Script `/exec` URL returned by the CLI. Do not derive one from an ID or accept `/dev`, query, fragment, embedded, or non-Google URLs.

## Completion contract

Do not report success unless the JSON envelope has `ok: true`, contains the real registered `webAppUrl`, and the CLI health result confirms the deployed endpoint. Synthetic health does not certify a live account unless this invocation actually exercised it.
