---
name: sync-careeros
description: Use when synchronizing validated local CareerOS records to an authorized destination in the foreground or through a named background job.
---

# Sync CareerOS

## Workflow

1. Resolve the checkout and invoke the shared sync command:

   ```bash
   repo_root="$(git rev-parse --show-toplevel 2>/dev/null)" || exit 1
   cd "$repo_root" || exit 1
   python -m careeros sync-careeros --json
   ```

2. Keep the source window and destination explicit. Show the CLI preview before mutation.
3. Treat the privacy gate and validation errors as terminal.
4. Treat each connector and destination consent gate as independent and terminal. For unattended work, require a separate background consent gate; no grant implies another.
5. During setup, request at most one user action per onboarding turn. Rerun the CLI after the action.
6. Preserve the CLI lock and idempotency behavior. An `already_running` result is not a successful second sync.
7. Require the CLI read-back result after every write. Stop if consent is revoked before the next external call.

## Completion contract

Do not report success unless the JSON envelope has `ok: true` and the CLI read-back result reports an exact match with status `synced`. Preserve `already_running`, blocked, and `reconciliation_required` states exactly; never conceal a partial write with a retry claim.
