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
harness_dir="${project_root}/.bagakit/long-run"
agents_file="${project_root}/AGENTS.md"
feature_file="${harness_dir}/feature-list.json"
handoff_file="${harness_dir}/bk-execution-handoff.md"
execution_table_file="${harness_dir}/bk-execution-table.json"
detect_prompt="${harness_dir}/detect_prompt.md"
initial_prompt="${harness_dir}/initial_prompt.md"
coding_prompt="${harness_dir}/coding_prompt.md"
init_script="${harness_dir}/init.sh"
feature_tool="${script_dir}/bagakit_long_run_features.py"
execution_tool="${script_dir}/bagakit_long_run_execution.py"

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

if ! command -v python3 >/dev/null 2>&1; then
  fail "python3 is required for long-run validation"
fi

if [[ ! -d "$harness_dir" ]]; then
  fail "missing harness dir: ${harness_dir}"
else
  for f in "$feature_file" "$initial_prompt" "$coding_prompt" "$init_script" "$execution_table_file" "$detect_prompt"; do
    if [[ ! -f "$f" ]]; then
      fail "missing required harness file: ${f}"
    fi
  done
fi

if [[ ! -f "$handoff_file" ]]; then
  fail "missing required handoff file: ${handoff_file}"
fi

if [[ -f "$init_script" && ! -x "$init_script" ]]; then
  warn "init script is not executable: ${init_script}"
fi

if [[ -f "$feature_file" ]]; then
  if [[ ! -f "$feature_tool" ]]; then
    fail "missing feature tool: ${feature_tool}"
  else
    if ! python3 "$feature_tool" validate "$feature_file" >/dev/null; then
      fail "feature list validation failed: ${feature_file}"
    fi
  fi
fi

if [[ -f "$handoff_file" ]]; then
  grep -q "^## Current Execution Item" "$handoff_file" || warn "handoff missing '## Current Execution Item' section"
  grep -q "^- Execution Item ID:" "$handoff_file" || warn "handoff missing '- Execution Item ID:' line"
  grep -q "^## Next Run" "$handoff_file" || warn "handoff missing '## Next Run' section"
fi

if [[ ! -f "$agents_file" ]]; then
  fail "missing AGENTS.md: ${agents_file}"
else
  grep -q "<!-- BAGAKIT:LONGRUN:START -->" "$agents_file" || fail "missing BAGAKIT long-run managed block start in ${agents_file}"
  grep -q "<!-- BAGAKIT:LONGRUN:END -->" "$agents_file" || fail "missing BAGAKIT long-run managed block end in ${agents_file}"
  grep -q "sh .bagakit/long-run/init.sh" "$agents_file" || warn "AGENTS long-run block missing explicit init loop command"
fi

if [[ -f "$execution_table_file" ]]; then
  if [[ ! -f "$execution_tool" ]]; then
    fail "missing execution tool: ${execution_tool}"
  else
    if ! python3 "$execution_tool" validate-table "$project_root" --table "$execution_table_file" >/dev/null; then
      fail "execution table quality validation failed: ${execution_table_file}"
    fi
    if ! python3 "$execution_tool" plan "$project_root" --table "$execution_table_file" >/dev/null; then
      fail "execution table plan failed: ${execution_table_file}"
    fi
  fi
fi

if [[ $errors -gt 0 ]]; then
  echo "failed: ${errors} error(s), ${warnings} warning(s)" >&2
  exit 1
fi

echo "ok: harness validation passed (${warnings} warning(s))"
