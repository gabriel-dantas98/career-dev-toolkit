#!/usr/bin/env bash

set -uo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
skill_file="${repo_root}/skills/capture-delivery/SKILL.md"
failures=0

fail() {
  printf 'FAIL: %s\n' "$1" >&2
  failures=$((failures + 1))
}

if [[ ! -f "$skill_file" ]]; then
  fail "missing skills/capture-delivery/SKILL.md"
else
  required_phrases=(
    "Situation"
    "Task"
    "Action"
    "Result"
    "zero questions by default"
    "at most one question"
    "draft"
    "privacy"
    "do not invent"
  )

  for phrase in "${required_phrases[@]}"; do
    grep -Fqi "$phrase" "$skill_file" || fail "skill contract is missing: ${phrase}"
  done

  forbidden_phrases=(
    "bypass privacy checks"
    "infer missing metrics as facts"
    "upload the full thread automatically"
  )

  for phrase in "${forbidden_phrases[@]}"; do
    if grep -Fqi "$phrase" "$skill_file"; then
      fail "skill contract contains forbidden instruction: ${phrase}"
    fi
  done
fi

if (( failures > 0 )); then
  printf 'Capture skill validation failed with %d error(s).\n' "$failures" >&2
  exit 1
fi

printf 'PASS: capture-delivery contract is valid.\n'
