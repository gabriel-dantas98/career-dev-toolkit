#!/usr/bin/env bash

set -uo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
failures=0

fail() {
  printf 'FAIL: %s\n' "$1" >&2
  failures=$((failures + 1))
}

required_files=(
  "README.md"
  "DESIGN.md"
  "AGENTS.md"
  ".claude-plugin/plugin.json"
  ".claude-plugin/marketplace.json"
  ".cursor-plugin/plugin.json"
  ".cursor-plugin/marketplace.json"
  ".codex-plugin/plugin.json"
)

required_skills=(
  "capture-delivery"
  "harvest-retrospective"
  "validate-bragsheet-integrity"
  "write-bragsheet-safe"
  "deploy-careeros-timeline"
  "build-promo-packet"
  "sync-careeros"
)

for skill in "${required_skills[@]}"; do
  required_files+=(
    "skills/${skill}/SKILL.md"
    "skills/${skill}/DESIGN.md"
  )
done

for relative_path in "${required_files[@]}"; do
  [[ -f "${repo_root}/${relative_path}" ]] || fail "missing ${relative_path}"
done

read_json() {
  local file="$1"
  local expression="$2"
  node -e '
    const fs = require("node:fs");
    const [file, expression] = process.argv.slice(1);
    const value = expression.split(".").reduce(
      (current, key) => current?.[key],
      JSON.parse(fs.readFileSync(file, "utf8")),
    );
    if (value === undefined || value === null) process.exit(2);
    process.stdout.write(typeof value === "string" ? value : JSON.stringify(value));
  ' "$file" "$expression" 2>/dev/null
}

manifest_paths=(
  ".claude-plugin/plugin.json"
  ".cursor-plugin/plugin.json"
  ".codex-plugin/plugin.json"
)

for relative_path in "${manifest_paths[@]}"; do
  file="${repo_root}/${relative_path}"
  [[ -f "$file" ]] || continue
  name="$(read_json "$file" "name")" || {
    fail "invalid JSON or missing name in ${relative_path}"
    continue
  }
  [[ "$name" == "career-dev-toolkit" ]] || fail "${relative_path} has name ${name}"
done

marketplace_paths=(
  ".claude-plugin/marketplace.json"
  ".cursor-plugin/marketplace.json"
)

for relative_path in "${marketplace_paths[@]}"; do
  file="${repo_root}/${relative_path}"
  [[ -f "$file" ]] || continue
  source="$(read_json "$file" "plugins.0.source")" || {
    fail "invalid JSON or missing plugin source in ${relative_path}"
    continue
  }
  [[ "$source" == "./" ]] || fail "${relative_path} source must equal ./"
done

cursor_manifest="${repo_root}/.cursor-plugin/plugin.json"
if [[ -f "$cursor_manifest" ]]; then
  cursor_skills="$(read_json "$cursor_manifest" "skills")" || cursor_skills=""
  [[ "$cursor_skills" == "./skills/" ]] || fail "Cursor skills path must equal ./skills/"
fi

codex_manifest="${repo_root}/.codex-plugin/plugin.json"
if [[ -f "$codex_manifest" ]]; then
  codex_description="$(read_json "$codex_manifest" "description")" || codex_description=""
  [[ -n "$codex_description" ]] || fail "Codex description must not be empty"
  codex_skills="$(read_json "$codex_manifest" "skills")" || codex_skills=""
  [[ "$codex_skills" == "./skills/" ]] || fail "Codex skills path must equal ./skills/"
fi

for platform in ".claude-plugin" ".cursor-plugin" ".codex-plugin"; do
  if [[ -e "${repo_root}/${platform}/skills" ]]; then
    fail "${platform} must discover the shared skills/ directory, not a platform copy"
  fi
done

if (( failures > 0 )); then
  printf 'Structure validation failed with %d error(s).\n' "$failures" >&2
  exit 1
fi

printf 'PASS: plugin structure is valid.\n'
