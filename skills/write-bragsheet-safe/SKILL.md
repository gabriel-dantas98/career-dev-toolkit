---
name: write-bragsheet-safe
description: Use when previewing or writing validated local career records to one explicitly authorized brag-sheet destination.
---

# Write brag-sheet safely

## Workflow

1. Resolve the checkout and run the shared safe-write command:

   ```bash
   repo_root="$(git rev-parse --show-toplevel 2>/dev/null)" || exit 1
   cd "$repo_root" || exit 1
   python -m careeros write-bragsheet-safe --json
   ```

2. Use only an exact spreadsheet ID, sheet name, and start row accepted by the CLI. Show the deterministic preview before external mutation.
3. Treat the privacy gate and integrity findings as terminal. Do not send records that fail either check.
4. Treat the scoped destination consent gate as terminal immediately before the write and again before read-back. Never infer it from connector or background consent.
5. During setup, request at most one user action per onboarding turn. Rerun the CLI to verify the action.
6. Preserve the CLI's RAW serialization and exact read-back result. Never substitute an accepted write response for verification.

## Completion contract

Do not report success unless the JSON envelope has `ok: true` and the CLI read-back result reports an exact match with status `synced`. Report any other post-write state as `reconciliation_required`; do not retry or alter the destination outside the CLI contract.
