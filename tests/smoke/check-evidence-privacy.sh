#!/usr/bin/env bash

set -uo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
evidence_dir="${repo_root}/tests/evidence"

if rg -n \
  '(/Users/[^/]+|/home/[^/]+|gh[pousr]_[A-Za-z0-9_]{12,}|sk-[A-Za-z0-9_-]{12,}|Bearer [A-Za-z0-9])' \
  "$evidence_dir"; then
  printf 'FAIL: evidence contains a user path or credential-shaped value.\n' >&2
  exit 1
fi

printf 'PASS: evidence contains no user path or credential-shaped value.\n'
