#!/usr/bin/env bash

set -uo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
evidence_dir="${repo_root}/tests/evidence"
user_home_root="$(cd && pwd)"
codex_config_root="${CODEX_HOME:-${HOME}/.codex}"
skill_validator="${codex_config_root}/skills/.system/skill-creator/scripts/quick_validate.py"
plugin_validator="${codex_config_root}/skills/.system/plugin-creator/scripts/validate_plugin.py"
timeout_runner="${repo_root}/scripts/run-with-timeout.mjs"
mkdir -p "$evidence_dir"

PASS=0
FAIL=1
SKIP=2
BLOCKED=3

sanitize_file() {
  local file="$1"
  local sanitized="${file}.sanitized"

  sed -E \
    -e "s#${repo_root}#<repo>#g" \
    -e "s#${user_home_root}#<user-home>#g" \
    -e 's/(gh[pousr]_[A-Za-z0-9_]{6})[A-Za-z0-9_]+/\1<redacted>/g' \
    -e 's/(sk-[A-Za-z0-9]{6})[A-Za-z0-9_-]+/\1<redacted>/g' \
    -e 's/(Bearer )[A-Za-z0-9._~+\/=-]+/\1<redacted>/g' \
    "$file" > "$sanitized"
  mv "$sanitized" "$file"
}

capture() {
  local output_file="$1"
  shift

  "$@" > "$output_file" 2>&1
  local status=$?
  sanitize_file "$output_file"
  return "$status"
}

print_result() {
  local target="$1"
  local status="$2"
  local detail="$3"

  case "$status" in
    "$PASS") printf '%s: PASS — %s\n' "$target" "$detail" ;;
    "$FAIL") printf '%s: FAIL — %s\n' "$target" "$detail" >&2 ;;
    "$SKIP") printf '%s: SKIP — %s\n' "$target" "$detail" ;;
    "$BLOCKED") printf '%s: BLOCKED — %s\n' "$target" "$detail" ;;
  esac
}

run_structure() {
  local evidence="${evidence_dir}/structure.txt"
  : > "$evidence"

  local commands=(
    "bash tests/smoke/validate-structure.sh"
    "bash tests/smoke/check-capture-skill.sh"
    "bash tests/smoke/check-timeout.sh"
    "bash tests/smoke/check-evidence-privacy.sh"
  )

  local command
  for command in "${commands[@]}"; do
    printf '$ %s\n' "$command" >> "$evidence"
    (
      cd "$repo_root" || exit 1
      /bin/bash -lc "$command"
    ) >> "$evidence" 2>&1
    local status=$?
    if (( status != 0 )); then
      sanitize_file "$evidence"
      print_result "structure" "$FAIL" "see tests/evidence/structure.txt"
      return "$FAIL"
    fi
  done

  if [[ -f "$skill_validator" && -f "$plugin_validator" && -x "$(command -v uv || true)" ]]; then
    printf '$ official skill and plugin validators\n' >> "$evidence"
    (
      cd "$repo_root" || exit 1
      uv run --with pyyaml python "$skill_validator" skills/capture-delivery
      uv run --with pyyaml python "$plugin_validator" .
    ) >> "$evidence" 2>&1
    local validator_status=$?
    if (( validator_status != 0 )); then
      sanitize_file "$evidence"
      print_result "structure" "$FAIL" "official validation failed"
      return "$FAIL"
    fi
  else
    printf 'SKIP: official Codex validators are not installed in this environment.\n' >> "$evidence"
  fi

  sanitize_file "$evidence"
  print_result "structure" "$PASS" "deterministic checks passed"
  return "$PASS"
}

run_claude() {
  if ! command -v claude >/dev/null 2>&1; then
    print_result "claude" "$SKIP" "CLI not installed"
    return "$SKIP"
  fi

  local validate_evidence="${evidence_dir}/claude-validate.txt"
  if ! capture "$validate_evidence" claude plugin validate "$repo_root" --strict; then
    print_result "claude" "$FAIL" "strict plugin validation failed"
    return "$FAIL"
  fi

  local install_evidence="${evidence_dir}/claude-install.txt"
  : > "$install_evidence"

  (
    cd "$repo_root" || exit 1
    claude plugin marketplace add ./ || {
      claude plugin marketplace list 2>&1 | grep -Fq "career-dev-toolkit" ||
        exit 1
    }
    claude plugin install career-dev-toolkit@career-dev-toolkit
    claude plugin details career-dev-toolkit@career-dev-toolkit
  ) >> "$install_evidence" 2>&1
  local status=$?
  sanitize_file "$install_evidence"

  if (( status != 0 )); then
    if grep -Eqi 'not logged in|authentication|unauthorized|api key' "$install_evidence"; then
      print_result "claude" "$SKIP" "authentication unavailable"
      return "$SKIP"
    fi
    print_result "claude" "$FAIL" "installation failed"
    return "$FAIL"
  fi

  print_result "claude" "$PASS" "validated, installed and inspected"
  return "$PASS"
}

run_cursor() {
  if ! command -v cursor >/dev/null 2>&1; then
    print_result "cursor" "$SKIP" "CLI not installed"
    return "$SKIP"
  fi

  local evidence="${evidence_dir}/cursor-oneshot.txt"
  local prompt="Use capture-delivery on this thread: I reduced CI duration from 20 to 12 minutes by parallelizing tests. Return STAR labels."

  capture "$evidence" node "$timeout_runner" "${CURSOR_SMOKE_TIMEOUT_SECONDS:-180}" \
    cursor agent --plugin-dir "$repo_root" --print --mode ask --trust "$prompt"
  local status=$?

  if (( status != 0 )); then
    if (( status == 124 )); then
      print_result "cursor" "$BLOCKED" "one-shot exceeded the configured timeout"
      return "$BLOCKED"
    fi
    if grep -Eqi 'not logged in|authentication|unauthorized|api key' "$evidence"; then
      print_result "cursor" "$SKIP" "authentication unavailable"
      return "$SKIP"
    fi
    print_result "cursor" "$FAIL" "one-shot command failed"
    return "$FAIL"
  fi

  local label
  for label in Situation Task Action Result; do
    if ! grep -Fqi "$label" "$evidence"; then
      print_result "cursor" "$FAIL" "response is missing ${label}"
      return "$FAIL"
    fi
  done

  print_result "cursor" "$PASS" "plugin loaded and returned all STAR labels"
  return "$PASS"
}

run_codex() {
  local evidence="${evidence_dir}/codex-diagnostic.txt"
  : > "$evidence"

  if [[ ! -f "$plugin_validator" || ! -x "$(command -v uv || true)" ]]; then
    printf 'Official Codex plugin validator is not installed.\n' >> "$evidence"
    sanitize_file "$evidence"
    print_result "codex" "$SKIP" "official validator unavailable"
    return "$SKIP"
  fi

  (
    cd "$repo_root" || exit 1
    uv run --with pyyaml python "$plugin_validator" .
  ) >> "$evidence" 2>&1
  local validator_status=$?

  if (( validator_status != 0 )); then
    sanitize_file "$evidence"
    print_result "codex" "$FAIL" "manifest validation failed"
    return "$FAIL"
  fi

  if ! command -v codex >/dev/null 2>&1; then
    printf '\nCodex CLI is not installed.\n' >> "$evidence"
    sanitize_file "$evidence"
    print_result "codex" "$SKIP" "manifest valid; CLI not installed"
    return "$SKIP"
  fi

  printf '\n$ codex --version\n' >> "$evidence"
  codex --version >> "$evidence" 2>&1
  local runtime_status=$?
  sanitize_file "$evidence"

  if (( runtime_status != 0 )); then
    if grep -Fq "ENOENT" "$evidence"; then
      print_result "codex" "$BLOCKED" "manifest valid; local CLI native package is broken"
      return "$BLOCKED"
    fi
    print_result "codex" "$FAIL" "runtime diagnostic failed"
    return "$FAIL"
  fi

  print_result "codex" "$PASS" "manifest valid and CLI starts"
  return "$PASS"
}

run_target() {
  case "$1" in
    structure) run_structure ;;
    claude) run_claude ;;
    cursor) run_cursor ;;
    codex) run_codex ;;
    *)
      printf 'Usage: %s {structure|claude|cursor|codex|all}\n' "$0" >&2
      return "$FAIL"
      ;;
  esac
}

run_all() {
  local overall="$PASS"
  local target

  for target in structure claude cursor codex; do
    run_target "$target"
    local status=$?

    if (( status == FAIL )); then
      overall="$FAIL"
    elif (( status == BLOCKED && overall != FAIL )); then
      overall="$BLOCKED"
    elif (( status == SKIP && overall == PASS )); then
      overall="$SKIP"
    fi
  done

  return "$overall"
}

target="${1:-all}"
if [[ "$target" == "all" ]]; then
  run_all
else
  run_target "$target"
fi
