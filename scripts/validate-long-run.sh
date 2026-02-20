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
initializer_prompt="${harness_dir}/initializer_prompt.md"
coding_prompt="${harness_dir}/coding_prompt.md"
resume_script="${harness_dir}/check_and_resume.sh"
legacy_init_script="${harness_dir}/init.sh"
legacy_initial_prompt="${harness_dir}/initial_prompt.md"
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
  for f in "$feature_file" "$initializer_prompt" "$coding_prompt" "$resume_script" "$execution_table_file" "$detect_prompt"; do
    if [[ ! -f "$f" ]]; then
      fail "missing required harness file: ${f}"
    fi
  done
fi

if [[ ! -f "$handoff_file" ]]; then
  fail "missing required handoff file: ${handoff_file}"
fi

if [[ -f "$resume_script" && ! -x "$resume_script" ]]; then
  warn "resume script is not executable: ${resume_script}"
fi

for legacy in "$legacy_init_script" "$legacy_initial_prompt"; do
  if [[ -e "$legacy" ]]; then
    fail "legacy harness artifact must be removed: ${legacy} (run apply-long-run.sh again)"
  fi
done

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
  grep -q "\[\[BAGAKIT\]\]" "$handoff_file" || warn "handoff missing [[BAGAKIT]] response snapshot"
  grep -q "^- LongRun:" "$handoff_file" || warn "handoff missing '- LongRun:' response snapshot line"
  grep -q "Confidence=" "$handoff_file" || warn "handoff LongRun snapshot should include Confidence="
fi

for f in "$detect_prompt" "$initializer_prompt" "$coding_prompt"; do
  if [[ -f "$f" ]]; then
    grep -q "\[\[BAGAKIT\]\]" "$f" || fail "prompt missing [[BAGAKIT]] footer contract: ${f}"
    grep -q "LongRun:" "$f" || fail "prompt missing '- LongRun:' footer contract: ${f}"
    grep -q "Confidence=" "$f" || fail "prompt missing 'Confidence=' in '- LongRun:' contract: ${f}"
    grep -q "LongRunStop:" "$f" || fail "prompt missing stop-reason contract '- LongRunStop:': ${f}"
  fi
done

if [[ ! -f "$agents_file" ]]; then
  fail "missing AGENTS.md: ${agents_file}"
else
  grep -q "<!-- BAGAKIT:LONGRUN:START -->" "$agents_file" || fail "missing BAGAKIT long-run managed block start in ${agents_file}"
  grep -q "<!-- BAGAKIT:LONGRUN:END -->" "$agents_file" || fail "missing BAGAKIT long-run managed block end in ${agents_file}"
  grep -q "check_and_resume.sh" "$agents_file" || fail "AGENTS long-run block missing explicit resume loop command"
  grep -q "\[\[BAGAKIT\]\]" "$agents_file" || fail "AGENTS long-run block missing [[BAGAKIT]] response contract"
  grep -q "LongRun:" "$agents_file" || fail "AGENTS long-run block missing '- LongRun:' response contract"
  grep -q "Confidence=" "$agents_file" || fail "AGENTS long-run block missing Confidence contract in '- LongRun:' line"
  grep -q "LongRunStop:" "$agents_file" || fail "AGENTS long-run block missing '- LongRunStop:' stop-reason contract"
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
    detect_warnings="$(python3 - "$execution_tool" "$project_root" "$execution_table_file" <<'PY'
import json
import subprocess
import sys

tool, root, table = sys.argv[1], sys.argv[2], sys.argv[3]
raw = subprocess.check_output(
    ["python3", tool, "detect", root, "--table", table, "--json"],
    text=True,
)
payload = json.loads(raw)
for adapter in payload.get("adapters", []):
    if not isinstance(adapter, dict):
        continue
    name = str(adapter.get("name", "adapter"))
    for warning in adapter.get("warnings", []):
        print(f"{name}: {warning}")
PY
)" || true
    if [[ -n "${detect_warnings}" ]]; then
      while IFS= read -r line; do
        [[ -n "$line" ]] || continue
        warn "execution detect: ${line}"
      done <<<"$detect_warnings"
    fi
  fi
fi

if [[ $errors -gt 0 ]]; then
  echo "failed: ${errors} error(s), ${warnings} warning(s)" >&2
  exit 1
fi

echo "ok: harness validation passed (${warnings} warning(s))"
