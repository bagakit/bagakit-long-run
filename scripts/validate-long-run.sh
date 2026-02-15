#!/usr/bin/env bash
set -euo pipefail

usage() {
  echo "Usage: $(basename "$0") <project_root>" >&2
  exit 1
}

if [[ $# -ne 1 ]]; then
  usage
fi

project_root="$1"
script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
harness_dir="${project_root}/.bagakit-long-run"
feature_file="${harness_dir}/feature-list.json"
progress_file="${harness_dir}/claude-progress.md"
initial_prompt="${harness_dir}/initial_prompt.md"
coding_prompt="${harness_dir}/coding_prompt.md"
init_script="${harness_dir}/init.sh"
feature_tool="${script_dir}/bagakit_long_run_features.py"

errors=0
warnings=0

fail() {
  echo "error: $1" >&2
  errors=$((errors + 1))
}

warn() {
  echo "warn: $1" >&2
  warnings=$((warnings + 1))
}

if [[ ! -d "$harness_dir" ]]; then
  fail "missing harness dir: ${harness_dir}"
else
  for f in "$feature_file" "$progress_file" "$initial_prompt" "$coding_prompt" "$init_script"; do
    if [[ ! -f "$f" ]]; then
      fail "missing required harness file: ${f}"
    fi
  done
fi

if [[ -f "$init_script" && ! -x "$init_script" ]]; then
  warn "init script is not executable: ${init_script}"
fi

if [[ -f "$feature_file" ]]; then
  if command -v python3 >/dev/null 2>&1; then
    if [[ ! -f "$feature_tool" ]]; then
      fail "missing feature tool: ${feature_tool}"
    else
      if ! python3 "$feature_tool" validate "$feature_file" >/dev/null; then
        fail "feature list validation failed: ${feature_file}"
      fi
    fi
  else
    warn "python3 not found; skipped JSON validation"
  fi
fi

if [[ -f "$progress_file" ]]; then
  grep -q "^## Current Feature" "$progress_file" || warn "progress missing '## Current Feature' section"
  grep -q "^- Feature ID:" "$progress_file" || warn "progress missing '- Feature ID:' line"
  grep -q "^## Next Session" "$progress_file" || warn "progress missing '## Next Session' section"
fi

if [[ $errors -gt 0 ]]; then
  echo "failed: ${errors} error(s), ${warnings} warning(s)" >&2
  exit 1
fi

echo "ok: harness validation passed (${warnings} warning(s))"
