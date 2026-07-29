#!/usr/bin/env bash

set -uo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
runner="${repo_root}/scripts/run-with-timeout.mjs"

if [[ ! -f "$runner" ]]; then
  printf 'FAIL: missing scripts/run-with-timeout.mjs\n' >&2
  exit 1
fi

started_at="$(date +%s)"
node "$runner" 1 node -e 'setTimeout(() => {}, 5000)'
status=$?
elapsed=$(( $(date +%s) - started_at ))

if (( status != 124 )); then
  printf 'FAIL: expected timeout exit 124, got %d\n' "$status" >&2
  exit 1
fi

if (( elapsed > 3 )); then
  printf 'FAIL: timeout took %d seconds\n' "$elapsed" >&2
  exit 1
fi

printf 'PASS: command timeout is bounded.\n'
