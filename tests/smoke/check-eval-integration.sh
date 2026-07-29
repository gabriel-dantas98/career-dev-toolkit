#!/usr/bin/env bash

set -uo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
failures=0

fail() {
  printf 'FAIL: %s\n' "$1" >&2
  failures=$((failures + 1))
}

assert_contains() {
  local file="$1"
  local pattern="$2"
  local message="$3"

  grep -Fq "$pattern" "${repo_root}/${file}" || fail "$message"
}

assert_not_contains() {
  local file="$1"
  local pattern="$2"
  local message="$3"

  if grep -Fq "$pattern" "${repo_root}/${file}"; then
    fail "$message"
  fi
}

assert_contains "package.json" '"eval:static"' \
  "package.json must expose eval:static"
assert_contains "package.json" '"eval:providers"' \
  "package.json must expose eval:providers"

assert_contains ".github/workflows/smoke-test.yml" "npm test" \
  "blocking CI must run the Node test suite"
assert_contains ".github/workflows/smoke-test.yml" "npm run eval:static" \
  "blocking CI must run deterministic evals"
assert_not_contains ".github/workflows/smoke-test.yml" "eval:providers" \
  "blocking CI must not call paid providers"

provider_workflow="${repo_root}/.github/workflows/provider-evals.yml"
if [[ ! -f "$provider_workflow" ]]; then
  fail "manual provider workflow is missing"
else
  assert_contains ".github/workflows/provider-evals.yml" "workflow_dispatch:" \
    "provider workflow must be manually dispatched"
  assert_contains ".github/workflows/provider-evals.yml" "max_invocations:" \
    "provider workflow must require an invocation ceiling"
  assert_contains ".github/workflows/provider-evals.yml" "actions/upload-artifact@" \
    "provider workflow must preserve sanitized reports"
fi

if [[ -f "${repo_root}/evals/capture-delivery/run-static.mjs" ]]; then
  fail "obsolete static runner must be removed"
fi

if ! git -C "$repo_root" check-ignore -q .eval-results/probe; then
  fail ".eval-results must remain ignored"
fi

if (( failures > 0 )); then
  printf 'Eval integration validation failed with %d error(s).\n' "$failures" >&2
  exit 1
fi

printf 'PASS: eval integration is correctly separated.\n'
