#!/usr/bin/env bash

set -uo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
failures=0

fail() {
  printf 'FAIL: %s\n' "$1" >&2
  failures=$((failures + 1))
}

skills=(
  "capture-delivery"
  "harvest-retrospective"
  "validate-bragsheet-integrity"
  "write-bragsheet-safe"
  "deploy-careeros-timeline"
  "build-promo-packet"
  "sync-careeros"
)

required_design_sections=(
  "Goal"
  "Non-goals"
  "Inputs"
  "Outputs"
  "Voice/Tone"
  "Open questions"
)

required_skill_phrases=(
  'repo_root='
  'git rev-parse --show-toplevel'
  'cd "$repo_root"'
  'python -m careeros'
  '--json'
  'at most one user action per onboarding turn'
)

for skill in "${skills[@]}"; do
  design_file="${repo_root}/skills/${skill}/DESIGN.md"
  skill_file="${repo_root}/skills/${skill}/SKILL.md"

  if [[ ! -f "$design_file" ]]; then
    fail "missing skills/${skill}/DESIGN.md"
  else
    for section in "${required_design_sections[@]}"; do
      grep -Fqx "## ${section}" "$design_file" ||
        fail "skills/${skill}/DESIGN.md is missing section: ${section}"
    done
  fi

  if [[ ! -f "$skill_file" ]]; then
    fail "missing skills/${skill}/SKILL.md"
    continue
  fi

  [[ "$(sed -n '1p' "$skill_file")" == "---" ]] ||
    fail "skills/${skill}/SKILL.md must start with YAML frontmatter"
  grep -Fqx "name: ${skill}" "$skill_file" ||
    fail "skills/${skill}/SKILL.md has the wrong name"
  grep -Eq '^description: Use when ' "$skill_file" ||
    fail "skills/${skill}/SKILL.md description must start with Use when"

  for phrase in "${required_skill_phrases[@]}"; do
    grep -Fq -- "$phrase" "$skill_file" ||
      fail "skills/${skill}/SKILL.md is missing portable contract: ${phrase}"
  done

  grep -Fq "python -m careeros ${skill}" "$skill_file" ||
    fail "skills/${skill}/SKILL.md does not invoke its CareerOS command"

  if grep -Eqi '(Claude Code|Cursor|Codex|\.claude-plugin|\.cursor-plugin|\.codex-plugin)' "$skill_file"; then
    fail "skills/${skill}/SKILL.md contains platform-specific behavior"
  fi
done

mutating_skills=(
  "harvest-retrospective"
  "write-bragsheet-safe"
  "deploy-careeros-timeline"
  "sync-careeros"
)

for skill in "${mutating_skills[@]}"; do
  skill_file="${repo_root}/skills/${skill}/SKILL.md"
  [[ -f "$skill_file" ]] || continue
  grep -Fqi "privacy gate" "$skill_file" ||
    fail "skills/${skill}/SKILL.md must state its privacy gate"
  grep -Fqi "consent gate" "$skill_file" ||
    fail "skills/${skill}/SKILL.md must state its consent gate"
done

for skill in "write-bragsheet-safe" "sync-careeros"; do
  skill_file="${repo_root}/skills/${skill}/SKILL.md"
  [[ -f "$skill_file" ]] || continue
  grep -Fqi "read-back result" "$skill_file" ||
    fail "skills/${skill}/SKILL.md must require the CLI read-back result"
  grep -Fqi "do not report success unless" "$skill_file" ||
    fail "skills/${skill}/SKILL.md must gate write success claims"
done

deploy_file="${repo_root}/skills/deploy-careeros-timeline/SKILL.md"
if [[ -f "$deploy_file" ]]; then
  grep -Fqi "health result" "$deploy_file" ||
    fail "deploy-careeros-timeline must require the CLI health result"
  grep -Fqi "do not report success unless" "$deploy_file" ||
    fail "deploy-careeros-timeline must gate deployment success claims"
fi

capture_file="${repo_root}/skills/capture-delivery/SKILL.md"
if [[ -f "$capture_file" ]]; then
  bragdoc_fields=(
    "record_id"
    "period"
    "title"
    "tags"
    "context"
    "confidence"
    "situation"
    "task"
    "action"
    "result"
    "evidence"
    "evidence_gaps"
  )
  for field in "${bragdoc_fields[@]}"; do
    grep -Fqi "$field" "$capture_file" ||
      fail "capture-delivery is missing bragdoc field: ${field}"
  done
  grep -Fqi "do not invent impact" "$capture_file" ||
    fail "capture-delivery must forbid invented impact"
fi

if (( failures > 0 )); then
  printf 'CareerOS skill validation failed with %d error(s).\n' "$failures" >&2
  exit 1
fi

printf 'PASS: portable CareerOS skill contracts are valid.\n'
